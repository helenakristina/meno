"""Business logic for MHT medication tracking."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from app.exceptions import ValidationError
from app.models.medications import (
    MedicationChangeDose,
    MedicationChangeDoseResponse,
    MedicationContext,
    MedicationCreate,
    MedicationReferenceCreate,
    MedicationReferenceResult,
    MedicationResponse,
    MedicationUpdate,
    SymptomComparisonResponse,
    SymptomComparisonRow,
)
from app.repositories.medication_repository import MedicationRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.repositories.user_repository import UserRepository
from app.services.medication_base import MedicationServiceBase
from app.utils.logging import hash_user_id
from app.utils.stats import calculate_frequency_stats

logger = logging.getLogger(__name__)

# Threshold below which a comparison window is flagged as sparse
_SPARSE_LOG_THRESHOLD = 14
# Max days in the comparison window
_MAX_COMPARISON_DAYS = 90
# Minimum percentage-point change to show a directional arrow
_DIRECTION_THRESHOLD_PP = 10.0
# Cap medication context sent to LLM (to stay within token budget)
_MAX_CURRENT_MEDS_FOR_LLM = 10
_MAX_RECENT_CHANGES_FOR_LLM = 5


class MedicationService(MedicationServiceBase):
    """Handles MHT medication CRUD and the before/after symptom comparison."""

    def __init__(
        self,
        medication_repo: MedicationRepository,
        symptoms_repo: SymptomsRepository,
        user_repo: UserRepository,
    ):
        self.medication_repo = medication_repo
        self.symptoms_repo = symptoms_repo
        self.user_repo = user_repo

    # ------------------------------------------------------------------
    # Reference table
    # ------------------------------------------------------------------

    async def search_reference(
        self, user_id: str, query: str
    ) -> list[MedicationReferenceResult]:
        """Search medications_reference by brand or generic name."""
        return await self.medication_repo.search_reference(query, user_id)

    async def create_reference_entry(
        self, user_id: str, data: MedicationReferenceCreate
    ) -> MedicationReferenceResult:
        """Create a user-scoped medications_reference entry."""
        return await self.medication_repo.create_reference_entry(user_id, data)

    # ------------------------------------------------------------------
    # user_medications CRUD
    # ------------------------------------------------------------------

    async def list(self, user_id: str) -> list[MedicationResponse]:
        """List all medication stints for a user."""
        return await self.medication_repo.list_all(user_id)

    async def list_current(self, user_id: str) -> list[MedicationResponse]:
        """Return active stints only; empty list if tracking disabled."""
        settings = await self.user_repo.get_settings(user_id)
        if not settings.mht_tracking_enabled:
            return []
        return await self.medication_repo.list_current(user_id)

    async def get(self, user_id: str, medication_id: str) -> MedicationResponse:
        """Get a single medication stint by ID."""
        return await self.medication_repo.get(user_id, medication_id)

    async def create(
        self, user_id: str, data: MedicationCreate
    ) -> MedicationResponse:
        """Create a new medication stint."""
        if data.start_date > date.today():
            raise ValidationError("start_date cannot be in the future")

        result = await self.medication_repo.create(user_id, data)
        logger.info("Medication created user=%s", hash_user_id(user_id))
        return result

    async def update(
        self, user_id: str, medication_id: str, data: MedicationUpdate
    ) -> MedicationResponse:
        """Update notes and/or end_date on a medication stint."""
        # Validate date ordering if end_date is being set
        if "end_date" in data.model_fields_set and data.end_date is not None:
            existing = await self.medication_repo.get(user_id, medication_id)
            if data.end_date < existing.start_date:
                raise ValidationError("end_date cannot be before start_date")

        return await self.medication_repo.update(user_id, medication_id, data)

    async def change_dose(
        self, user_id: str, medication_id: str, data: MedicationChangeDose
    ) -> MedicationChangeDoseResponse:
        """Atomically end the current stint and create a new one.

        Validates effective_date > start_date at the service layer before
        delegating to the atomic RPC function.
        """
        existing = await self.medication_repo.get(user_id, medication_id)

        if existing.end_date is not None:
            raise ValidationError("Cannot change dose on a medication that has already been stopped")

        if data.effective_date <= existing.start_date:
            raise ValidationError("Effective date must be after the medication's start date")

        new_id = await self.medication_repo.change_dose(
            user_id=user_id,
            medication_id=medication_id,
            data=data,
            medication_name=existing.medication_name,
            medication_ref_id=existing.medication_ref_id,
        )
        logger.info("Medication dose changed user=%s", hash_user_id(user_id))
        return MedicationChangeDoseResponse(
            new_medication_id=new_id,
            previous_medication_id=medication_id,
        )

    async def delete(self, user_id: str, medication_id: str) -> None:
        """Delete a medication stint."""
        await self.medication_repo.delete(user_id, medication_id)

    async def list_active_during(
        self, user_id: str, range_start: date, range_end: date
    ) -> list[MedicationResponse]:
        """Return medications active at any point within a date range."""
        return await self.medication_repo.list_active_during(user_id, range_start, range_end)

    # ------------------------------------------------------------------
    # Before/after symptom comparison
    # ------------------------------------------------------------------

    async def get_symptom_comparison(
        self, user_id: str, medication_id: str
    ) -> SymptomComparisonResponse:
        """Build a before/after symptom frequency comparison for a medication stint.

        The comparison window length N = min(days since start_date, 90).
        - Before window: [start_date - N days, start_date - 1 day]
        - After window:  [start_date, start_date + N days] (or end_date if earlier)

        If the medication was started today (N=0), returns has_after_data=False.
        Always shows available data even when sparse; sets before/after_is_sparse=True
        when fewer than 14 days of log data exist in a window.

        Args:
            user_id: Owner's user ID.
            medication_id: Medication stint UUID.

        Returns:
            SymptomComparisonResponse with side-by-side frequency rows.
        """
        stint = await self.medication_repo.get(user_id, medication_id)
        today = date.today()

        n_days = min((today - stint.start_date).days, _MAX_COMPARISON_DAYS)

        base = SymptomComparisonResponse(
            medication_id=medication_id,
            medication_name=stint.medication_name,
            dose=stint.dose,
            delivery_method=stint.delivery_method,
            start_date=stint.start_date,
            end_date=stint.end_date,
            window_days=n_days,
        )

        if n_days == 0:
            base.has_after_data = False
            return base

        before_start = stint.start_date - timedelta(days=n_days)
        before_end = stint.start_date - timedelta(days=1)
        after_start = stint.start_date
        after_end = min(stint.end_date or today, after_start + timedelta(days=n_days))

        base.before_start = before_start
        base.before_end = before_end
        base.after_start = after_start
        base.after_end = after_end

        # Fetch logs for both windows concurrently
        (before_logs, ref), (after_logs, _) = await asyncio.gather(
            self.symptoms_repo.get_logs_with_reference(user_id, before_start, before_end),
            self.symptoms_repo.get_logs_with_reference(user_id, after_start, after_end),
        )

        base.before_log_days = len(before_logs)
        base.after_log_days = len(after_logs)
        base.before_is_sparse = len(before_logs) < _SPARSE_LOG_THRESHOLD
        base.after_is_sparse = len(after_logs) < _SPARSE_LOG_THRESHOLD

        if not before_logs and not after_logs:
            return base

        before_stats = {s.symptom_id: s for s in calculate_frequency_stats(before_logs, ref)}
        after_stats = {s.symptom_id: s for s in calculate_frequency_stats(after_logs, ref)}

        # Build union of symptom IDs from both windows
        all_ids = set(before_stats) | set(after_stats)

        before_total = max(len(before_logs), 1)
        after_total = max(len(after_logs), 1)

        rows: list[SymptomComparisonRow] = []
        for sid in all_ids:
            before_s = before_stats.get(sid)
            after_s = after_stats.get(sid)

            b_count = before_s.count if before_s else 0
            a_count = after_s.count if after_s else 0
            b_pct = round(b_count / before_total * 100, 1)
            a_pct = round(a_count / after_total * 100, 1)
            diff = a_pct - b_pct

            if diff < -_DIRECTION_THRESHOLD_PP:
                direction = "improved"
            elif diff > _DIRECTION_THRESHOLD_PP:
                direction = "worsened"
            else:
                direction = "stable"

            ref_entry = ref.get(sid, {})
            rows.append(
                SymptomComparisonRow(
                    symptom_id=sid,
                    symptom_name=ref_entry.get("name", "Unknown"),
                    category=ref_entry.get("category", ""),
                    before_count=b_count,
                    before_days=before_total,
                    before_pct=b_pct,
                    after_count=a_count,
                    after_days=after_total,
                    after_pct=a_pct,
                    direction=direction,
                )
            )

        # Sort by before_pct descending (most prominent before-window symptoms first)
        rows.sort(key=lambda r: r.before_pct, reverse=True)
        base.rows = rows

        # Check for confounding medication changes within either window
        base.has_confounding_changes = await self._has_confounding_changes(
            user_id, medication_id, before_start, after_end
        )

        return base

    # ------------------------------------------------------------------
    # Integration context
    # ------------------------------------------------------------------

    async def get_context_if_enabled(self, user_id: str) -> MedicationContext | None:
        """Return medication context for LLM injection, or None if tracking disabled.

        Checks mht_tracking_enabled before fetching. Returns None on any failure
        so callers can degrade gracefully.

        Args:
            user_id: Owner's user ID.

        Returns:
            MedicationContext if enabled, else None.
        """
        try:
            settings = await self.user_repo.get_settings(user_id)
            if not settings.mht_tracking_enabled:
                return None
            ctx = await self.medication_repo.get_context(user_id)
            # Cap to stay within LLM token budget
            ctx.current_medications = ctx.current_medications[:_MAX_CURRENT_MEDS_FOR_LLM]
            ctx.recent_changes = ctx.recent_changes[:_MAX_RECENT_CHANGES_FOR_LLM]
            return ctx
        except Exception as exc:
            logger.warning(
                "Failed to get medication context for user=%s (degrading gracefully): %s",
                hash_user_id(user_id), exc,
            )
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _has_confounding_changes(
        self,
        user_id: str,
        medication_id: str,
        window_start: date,
        window_end: date,
    ) -> bool:
        """Check if other medication events fall within the comparison window.

        A confounding change is any other medication stint starting or ending
        within the window (excluding the current stint itself).
        """
        try:
            all_meds = await self.medication_repo.list_all(user_id)
            for med in all_meds:
                if med.id == medication_id:
                    continue
                if window_start <= med.start_date <= window_end:
                    return True
                if med.end_date and window_start <= med.end_date <= window_end:
                    return True
        except Exception:
            pass
        return False
