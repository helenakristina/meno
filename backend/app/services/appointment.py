"""AppointmentService — orchestrates Appointment Prep Flow business logic.

Handles Steps 2, 4, and 5 of the Appointment Prep Flow:
- Step 2: Generate clinical narrative from symptom logs (generate_narrative)
- Step 4: Generate practice dismissal scenarios (generate_scenarios)
- Step 5: Generate and upload PDF outputs (generate_pdf)

Routes become thin wrappers that call one method and return the result.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.appointment import (
    AppointmentContext,
    AppointmentPrepGenerateResponse,
    AppointmentPrepNarrativeResponse,
    AppointmentPrepScenariosResponse,
    Concern,
    ScenarioCard,
)
from app.models.symptoms import SymptomFrequency, SymptomPair
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.services.medication_base import MedicationServiceBase
from app.utils.sanitize import sanitize_urgent_symptom
from app.repositories.user_repository import UserRepository
from app.services.llm import LLMService
from app.llm.appointment_prompts import NARRATIVE_SYSTEM, build_narrative_user_prompt
from app.services.pdf import PdfService
from app.services.storage import StorageService
from app.utils.prompt_formatting import (
    format_cooccurrence_stats_for_prompt,
    format_frequency_stats_for_prompt,
    format_medications_for_prompt,
)
from app.utils.logging import hash_user_id, safe_len
from app.utils.stats import calculate_cooccurrence_stats, calculate_frequency_stats

logger = logging.getLogger(__name__)


class AppointmentService:
    """Orchestrates appointment prep flow business logic (Steps 2, 4, 5).

    Each method is independently testable via mocked repositories and services.
    No HTTP concerns — raises domain exceptions (EntityNotFoundError, DatabaseError)
    which routes convert to HTTP responses.
    """

    def __init__(
        self,
        appointment_repo: AppointmentRepository,
        symptoms_repo: SymptomsRepository,
        user_repo: UserRepository,
        llm_service: LLMService,
        storage_service: StorageService,
        pdf_service: PdfService,
        medication_service: Optional[MedicationServiceBase] = None,
        rag_retriever: Optional[Callable] = None,
    ):
        self.appointment_repo = appointment_repo
        self.symptoms_repo = symptoms_repo
        self.user_repo = user_repo
        self.llm_service = llm_service
        self.storage_service = storage_service
        self.pdf_service = pdf_service
        self.medication_service = medication_service
        self.rag_retriever = rag_retriever
        self._scenario_config = self._load_scenario_config()

    # -------------------------------------------------------------------------
    # Step 2: Generate narrative
    # -------------------------------------------------------------------------

    async def generate_narrative(
        self,
        appointment_id: str,
        user_id: str,
        days_back: int,
    ) -> AppointmentPrepNarrativeResponse:
        """Generate AI narrative summary from symptom logs.

        Fetches symptom logs, calculates frequency and co-occurrence patterns,
        and uses LLM to produce a clinical narrative for provider conversation.

        Args:
            appointment_id: UUID of appointment context from Step 1.
            user_id: Authenticated user ID.
            days_back: Number of days of logs to include (1–365).

        Returns:
            AppointmentPrepNarrativeResponse with narrative and next_step.

        Raises:
            EntityNotFoundError: Appointment not found or doesn't belong to user.
            DatabaseError: Database or LLM operation failed.
        """
        # Verify ownership — raises EntityNotFoundError/DatabaseError on failure
        context = await self.appointment_repo.get_context(appointment_id, user_id)

        logger.info(
            "Narrative generation started: appointment_id=%s days_back=%d",
            appointment_id,
            days_back,
        )

        # Fetch user context
        try:
            journey_stage, age = await self.user_repo.get_context(user_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch user context for narrative: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate narrative: {exc}") from exc

        # Fetch symptom logs
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days_back)
        try:
            logs, _ = await self.symptoms_repo.get_logs(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=1000,
            )
        except Exception as exc:
            logger.error(
                "Failed to fetch symptom logs for narrative: user=%s start=%s end=%s error=%s",
                hash_user_id(user_id),
                start_date,
                end_date,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate narrative: {exc}") from exc

        # Handle no logs gracefully
        if not logs:
            empty_narrative = (
                f"No symptom logs found for the past {days_back} days. "
                "Start logging symptoms to generate a narrative summary."
            )
            logger.info(
                "No symptom logs found: appointment_id=%s days_back=%d",
                appointment_id,
                days_back,
            )
            await self.appointment_repo.save_narrative(
                appointment_id, user_id, empty_narrative
            )
            return AppointmentPrepNarrativeResponse(
                appointment_id=appointment_id,
                narrative=empty_narrative,
                next_step="prioritize",
            )

        # Convert to raw format for stat calculation
        raw_logs = [{"symptoms": [sym.id for sym in log.symptoms]} for log in logs]

        # Fetch symptoms reference
        symptom_ids = list(set(sid for log in raw_logs for sid in log["symptoms"]))
        try:
            symptoms_ref = await self.appointment_repo.get_symptom_reference(
                symptom_ids
            )
        except Exception as exc:
            logger.error("Failed to fetch symptoms reference: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to generate narrative: {exc}") from exc

        # Calculate statistics
        try:
            frequency_stats = calculate_frequency_stats(raw_logs, symptoms_ref)
            cooccurrence_stats = calculate_cooccurrence_stats(raw_logs, symptoms_ref)
        except Exception as exc:
            logger.error("Failed to calculate symptom stats: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to generate narrative: {exc}") from exc

        logger.info(
            "Symptom stats calculated: appointment_id=%s freq=%d coocc=%d",
            appointment_id,
            len(frequency_stats),
            len(cooccurrence_stats),
        )

        # Fetch current medications if available — supplementary, degrade gracefully
        current_medications: list = []
        if self.medication_service is not None:
            try:
                current_medications = await self.medication_service.list_current(
                    user_id
                )
            except Exception as exc:
                logger.warning(
                    "Failed to fetch medications for narrative: user=%s error=%s",
                    hash_user_id(user_id),
                    exc,
                )

        # Build prompts
        appt_type_str = context.appointment_type.value.replace("_", " ").title()
        goal_str = context.goal.value.replace("_", " ")
        age_str = str(age) if age else "not specified"
        freq_text = format_frequency_stats_for_prompt(
            frequency_stats, empty_msg="No symptom data."
        )
        coocc_text = format_cooccurrence_stats_for_prompt(cooccurrence_stats)
        med_section = format_medications_for_prompt(current_medications or [])

        user_prompt = build_narrative_user_prompt(
            appt_type_str=appt_type_str,
            goal_str=goal_str,
            age_str=age_str,
            journey_stage=journey_stage,
            days_back=days_back,
            start_date=start_date,
            end_date=end_date,
            freq_text=freq_text,
            coocc_text=coocc_text,
            med_section=med_section,
            what_have_you_tried=context.what_have_you_tried,
            specific_ask=context.specific_ask,
        )

        # Call LLM
        logger.info(
            "Calling LLM to generate narrative: appointment_id=%s", appointment_id
        )
        try:
            narrative = await self.llm_service.generate_narrative(
                system_prompt=NARRATIVE_SYSTEM,
                user_prompt=user_prompt,
            )
        except TimeoutError:
            logger.error(
                "LLM timed out for appointment narrative: appointment_id=%s",
                appointment_id,
            )
            raise DatabaseError("LLM request timed out generating narrative")
        except Exception as exc:
            logger.error(
                "LLM generation failed for narrative: appointment_id=%s error=%s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate narrative: {exc}") from exc

        logger.info(
            "Narrative generated: appointment_id=%s length=%d",
            appointment_id,
            len(narrative),
        )

        # Save narrative to database
        await self.appointment_repo.save_narrative(appointment_id, user_id, narrative)

        # Save frequency stats so Step 5 can reuse them without re-querying logs
        freq_stats_json = [s.model_dump() for s in frequency_stats]
        coocc_stats_json = [p.model_dump() for p in cooccurrence_stats]
        try:
            await self.appointment_repo.save_frequency_stats(
                appointment_id, user_id, freq_stats_json, coocc_stats_json
            )
        except Exception as exc:
            # Non-critical — PDF generation degrades to empty table rather than failing
            logger.warning(
                "Failed to save frequency stats: appointment_id=%s error=%s",
                appointment_id,
                exc,
            )

        return AppointmentPrepNarrativeResponse(
            appointment_id=appointment_id,
            narrative=narrative,
            next_step="prioritize",
        )

    # -------------------------------------------------------------------------
    # Step 4: Generate scenarios
    # -------------------------------------------------------------------------

    async def generate_scenarios(
        self,
        appointment_id: str,
        user_id: str,
    ) -> AppointmentPrepScenariosResponse:
        """Generate practice dismissal scenarios for appointment prep.

        Selects relevant dismissal scenarios based on context, then calls LLM
        to generate evidence-based response suggestions for each.

        Args:
            appointment_id: UUID of appointment context from Step 1.
            user_id: Authenticated user ID.

        Returns:
            AppointmentPrepScenariosResponse with scenario cards and next_step.

        Raises:
            EntityNotFoundError: Appointment not found or doesn't belong to user.
            DatabaseError: Database or LLM operation failed.
        """
        context = await self.appointment_repo.get_context(appointment_id, user_id)

        logger.info(
            "Scenario generation started: appointment_id=%s goal=%s dismissed=%s",
            appointment_id,
            context.goal.value,
            context.dismissed_before.value,
        )

        # Fetch user context
        try:
            journey_stage, age = await self.user_repo.get_context(user_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch user context for scenarios: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate scenarios: {exc}") from exc

        # Select dismissal scenarios based on context
        scenarios_to_generate = self._select_scenarios(context, journey_stage)

        logger.info("Selected %d scenarios for generation", len(scenarios_to_generate))

        # Fetch concerns from Step 3 (gracefully handles not-yet-completed step)
        try:
            concerns = await self.appointment_repo.get_concerns(appointment_id, user_id)
        except Exception as exc:
            logger.warning("Failed to fetch concerns, using empty list: %s", exc)
            concerns = []

        # Format concerns as strings for LLM prompt (comment appended when present)
        concerns_for_llm = [
            f"{c.text}; {c.comment}" if c.comment else c.text for c in concerns
        ]

        # Retrieve RAG chunks for each scenario to ground suggestions in real sources
        all_rag_chunks: list[dict] = []
        if self.rag_retriever is not None:
            try:
                chunk_results = await asyncio.gather(
                    *[
                        self.rag_retriever(s["title"], top_k=5, min_similarity=0.25)
                        for s in scenarios_to_generate
                    ]
                )
                for chunks in chunk_results:
                    all_rag_chunks.extend(chunks)
                logger.info(
                    "RAG retrieval for scenarios: retrieved %d chunks across %d scenarios",
                    len(all_rag_chunks),
                    len(scenarios_to_generate),
                )
            except Exception as exc:
                logger.warning(
                    "RAG retrieval failed for scenarios, continuing without chunks: %s",
                    exc,
                )
                all_rag_chunks = []

        # Call LLM
        try:
            raw_suggestions = await self.llm_service.generate_scenario_suggestions(
                scenarios_to_generate=scenarios_to_generate,
                concerns=concerns_for_llm,
                appointment_type=context.appointment_type.value,
                goal=context.goal.value,
                dismissed_before=context.dismissed_before.value,
                user_age=age,
                rag_chunks=all_rag_chunks,
            )
        except TimeoutError:
            logger.error(
                "LLM timed out for scenarios: appointment_id=%s", appointment_id
            )
            raise DatabaseError("LLM request timed out generating scenarios")
        except Exception as exc:
            logger.error(
                "LLM generation failed for scenarios: appointment_id=%s error=%s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate scenarios: {exc}") from exc

        # Parse JSON response
        try:
            parsed = json.loads(raw_suggestions)
            # Unwrap {"scenarios": [...]} wrapper (JSON mode returns objects, not arrays)
            if isinstance(parsed, dict) and "scenarios" in parsed:
                suggestions_list = parsed["scenarios"]
            elif isinstance(parsed, list):
                suggestions_list = parsed
            else:
                suggestions_list = [parsed]
        except json.JSONDecodeError:
            logger.error(
                "Failed to parse LLM response as JSON: response_len=%d",
                safe_len(raw_suggestions),
            )
            raise DatabaseError("Failed to parse scenario suggestions from LLM")

        # Build scenario cards — scenarios_to_generate is now list[dict] with
        # "title" and "category" keys (category comes from config/scenarios.json)
        scenario_cards: list[ScenarioCard] = []
        for idx, (scenario, suggestion_data) in enumerate(
            zip(scenarios_to_generate, suggestions_list)
        ):
            scenario_title = scenario["title"]
            suggestion_text = (
                suggestion_data.get("suggestion", "")
                if isinstance(suggestion_data, dict)
                else str(suggestion_data)
            )
            sources = (
                suggestion_data.get("sources", [])
                if isinstance(suggestion_data, dict)
                else []
            )
            scenario_cards.append(
                ScenarioCard(
                    id=f"scenario-{idx + 1}",
                    title=scenario_title,
                    situation=f"If your provider says: '{scenario_title}'",
                    suggestion=suggestion_text,
                    category=scenario["category"],
                    sources=sources,
                )
            )

        # Save to database
        scenarios_to_save = [
            {
                "id": card.id,
                "title": card.title,
                "situation": card.situation,
                "suggestion": card.suggestion,
                "category": card.category,
            }
            for card in scenario_cards
        ]
        await self.appointment_repo.save_scenarios(
            appointment_id, user_id, scenarios_to_save
        )

        logger.info(
            "Scenarios generated and saved: appointment_id=%s count=%d",
            appointment_id,
            len(scenario_cards),
        )

        return AppointmentPrepScenariosResponse(
            appointment_id=appointment_id,
            scenarios=scenario_cards,
            next_step="generate",
        )

    # -------------------------------------------------------------------------
    # Step 5: Generate PDFs
    # -------------------------------------------------------------------------

    async def generate_pdf(
        self,
        appointment_id: str,
        user_id: str,
    ) -> AppointmentPrepGenerateResponse:
        """Generate and upload PDF outputs for appointment prep.

        Generates provider summary and personal cheat sheet PDFs, uploads
        to Supabase Storage, and returns public URLs.

        Args:
            appointment_id: UUID of appointment context from Step 1.
            user_id: Authenticated user ID.

        Returns:
            AppointmentPrepGenerateResponse with PDF URLs.

        Raises:
            EntityNotFoundError: Appointment not found or doesn't belong to user.
            DatabaseError: Database, LLM, or storage operation failed.
        """
        context = await self.appointment_repo.get_context(appointment_id, user_id)

        logger.info("PDF generation started: appointment_id=%s", appointment_id)

        # Fetch all appointment data from earlier steps
        try:
            appointment_data = await self.appointment_repo.get_appointment_data(
                appointment_id, user_id
            )
        except (EntityNotFoundError, DatabaseError):
            raise
        except Exception as exc:
            logger.error("Failed to fetch appointment data: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to generate PDF: {exc}") from exc

        narrative = appointment_data.get("narrative")
        if not narrative:
            raise DatabaseError(
                "Narrative not found — Step 2 must be completed before generating PDFs"
            )
        concerns_raw = appointment_data.get("concerns") or []
        scenarios_data = appointment_data.get("scenarios", [])
        frequency_stats_data = appointment_data.get("frequency_stats") or []
        cooccurrence_stats_data = appointment_data.get("cooccurrence_stats") or []

        # Fetch user context
        try:
            _journey_stage, age = await self.user_repo.get_context(user_id)
        except Exception as exc:
            logger.error(
                "Failed to fetch user context for PDF: user=%s error=%s",
                hash_user_id(user_id),
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate PDF: {exc}") from exc

        narrative_text: str = (
            narrative if isinstance(narrative, str) else str(narrative)
        )

        # Deserialize concerns — DB may store old string[] or new Concern[] format
        concerns_list: list[Concern] = []
        for item in concerns_raw if isinstance(concerns_raw, list) else []:
            if isinstance(item, str):
                concerns_list.append(Concern(text=item))
            elif isinstance(item, dict):
                concerns_list.append(Concern(**item))

        # Format concerns as strings for LLM prompts (comment appended when present)
        concerns_for_llm: list[str] = [
            f"{c.text}; {c.comment}" if c.comment else c.text for c in concerns_list
        ]

        scenarios_for_pdf: list[dict] = []
        if scenarios_data and isinstance(scenarios_data, list):
            scenarios_for_pdf = scenarios_data
        elif isinstance(scenarios_data, dict):
            scenarios_for_pdf = [scenarios_data]

        # Deserialize saved frequency stats (empty list degrades gracefully in PDF)
        frequency_stats: list[SymptomFrequency] = []
        cooccurrence_stats: list[SymptomPair] = []
        try:
            frequency_stats = [SymptomFrequency(**s) for s in frequency_stats_data]
            cooccurrence_stats = [SymptomPair(**p) for p in cooccurrence_stats_data]
        except Exception as exc:
            logger.warning(
                "Failed to deserialize frequency stats, PDF will have empty table: %s",
                exc,
            )

        # Generate provider summary and cheat sheet in parallel via LLM
        provider_task = self.llm_service.generate_provider_summary_content(
            narrative=narrative_text,
            concerns=concerns_for_llm,
            appointment_type=context.appointment_type.value,
            goal=context.goal.value,
            user_age=age,
            urgent_symptom=context.urgent_symptom,
            what_have_you_tried=context.what_have_you_tried,
            specific_ask=context.specific_ask,
            history_clotting_risk=context.history_clotting_risk,
            history_breast_cancer=context.history_breast_cancer,
        )

        cheatsheet_task = self.llm_service.generate_cheatsheet_content(
            narrative=narrative_text,
            concerns=concerns_for_llm,
            appointment_type=context.appointment_type.value,
            goal=context.goal.value,
            user_age=age,
            urgent_symptom=context.urgent_symptom,
            scenarios=scenarios_for_pdf,
            specific_ask=context.specific_ask,
        )

        try:
            provider_summary_content, cheatsheet_content = await asyncio.gather(
                provider_task, cheatsheet_task
            )
        except TimeoutError:
            logger.error(
                "LLM timed out during PDF content generation: appointment_id=%s",
                appointment_id,
            )
            raise DatabaseError("LLM request timed out generating PDF content")
        except Exception as exc:
            logger.error(
                "LLM failed during PDF content generation: appointment_id=%s error=%s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate PDF content: {exc}") from exc

        # Build structured PDFs
        try:
            provider_summary_pdf = self.pdf_service.build_provider_summary_pdf(
                content=provider_summary_content,
                narrative=narrative_text,
                frequency_stats=frequency_stats,
                cooccurrence_stats=cooccurrence_stats,
                concerns=concerns_list,
            )
            cheatsheet_pdf = self.pdf_service.build_cheatsheet_pdf(
                content=cheatsheet_content,
                concerns=concerns_list,
                scenarios=scenarios_for_pdf,
                frequency_stats=frequency_stats,
            )
        except Exception as exc:
            logger.error("Failed to build PDFs: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to generate PDF: {exc}") from exc

        # Upload to Supabase Storage
        summary_path = f"{user_id}/{appointment_id}/provider-summary.pdf"
        cheatsheet_path = f"{user_id}/{appointment_id}/personal-cheatsheet.pdf"
        try:
            summary_url = await self.storage_service.upload_pdf(
                bucket="appointment-prep",
                path=summary_path,
                content=provider_summary_pdf,
            )
            cheatsheet_url = await self.storage_service.upload_pdf(
                bucket="appointment-prep",
                path=cheatsheet_path,
                content=cheatsheet_pdf,
            )
        except Exception as exc:
            logger.error("Failed to upload PDFs: %s", exc, exc_info=True)
            raise DatabaseError(f"Failed to upload PDF files: {exc}") from exc

        # Save metadata (non-critical — log warning if it fails but don't abort)
        try:
            await self.appointment_repo.save_pdf_metadata(
                user_id=user_id,
                appointment_id=appointment_id,
                provider_summary_path=summary_path,
                personal_cheatsheet_path=cheatsheet_path,
            )
        except (EntityNotFoundError, DatabaseError):
            raise
        except Exception as exc:
            logger.error("Failed to save PDF metadata: %s", exc, exc_info=True)
            logger.warning(
                "Continuing without metadata save: appointment_id=%s", appointment_id
            )

        logger.info("PDFs generated and uploaded: appointment_id=%s", appointment_id)

        return AppointmentPrepGenerateResponse(
            appointment_id=appointment_id,
            provider_summary_url=summary_url,
            personal_cheat_sheet_url=cheatsheet_url,
            message="Your appointment prep is ready!",
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _load_scenario_config(self) -> dict:
        """Load scenario config from JSON. Called once in __init__ — failure is immediate."""
        config_path = Path(__file__).parent.parent.parent / "config" / "scenarios.json"
        try:
            with config_path.open() as f:
                return json.load(f)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Scenario config not found at {config_path}. "
                "Ensure config/scenarios.json is present."
            ) from exc

    def _select_scenarios(
        self, context: AppointmentContext, journey_stage: str
    ) -> list[dict]:
        """Select 5-7 dismissal scenarios from JSON config based on appointment context.

        Returns list[dict] where each dict has "title" (str) and "category" (str).
        When goal is urgent_symptom, matches against keyword groups. Falls back to
        goal-specific scenarios for other goals.
        """
        config = self._scenario_config
        scenarios: list[dict] = []
        urgent_symptom = sanitize_urgent_symptom(context.urgent_symptom)

        if context.goal.value == "urgent_symptom" and not urgent_symptom:
            urgent_symptom = "perimenopause symptoms"

        if (
            context.goal.value == "urgent_symptom"
            and urgent_symptom
            and urgent_symptom != "perimenopause symptoms"
        ):
            # Find the first keyword group that matches the symptom text
            symptom_lower = urgent_symptom.lower()
            matched = False
            for group in config["symptom_scenarios"].values():
                if any(kw in symptom_lower for kw in group["keywords"]):
                    scenarios.extend(group["dismissals"])
                    matched = True
                    break

            if not matched:
                scenarios.extend(config["urgent_fallback_scenarios"])

            scenarios.extend(config["universal_scenarios"])
        else:
            goal_key = context.goal.value
            scenarios.extend(config["goal_scenarios"].get(goal_key, []))
            # Note: dismissed_before scenarios removed — "What are the triggers?"
            # is an open question, not a dismissal scenario (see config/_dismissed_before_removed)

        # Deduplicate preserving order, cap at 7
        seen: set[str] = set()
        unique: list[dict] = []
        for s in scenarios:
            if s["title"] not in seen:
                unique.append(s)
                seen.add(s["title"])

        logger.info(
            "Selected %d scenarios, has_urgent=%s",
            len(unique),
            bool(urgent_symptom),
        )
        return unique
