"""AppointmentService — orchestrates Appointment Prep Flow business logic.

Handles Steps 2, 4, and 5 of the Appointment Prep Flow:
- Step 2: Generate clinical narrative from symptom logs (generate_narrative)
- Step 4: Generate practice dismissal scenarios (generate_scenarios)
- Step 5: Generate and upload PDF outputs (generate_pdf)

Routes become thin wrappers that call one method and return the result.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

from app.exceptions import DatabaseError, EntityNotFoundError
from app.models.appointment import (
    AppointmentContext,
    AppointmentPrepGenerateResponse,
    AppointmentPrepNarrativeResponse,
    AppointmentPrepScenariosResponse,
    ScenarioCard,
)
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.symptoms_repository import SymptomsRepository
from app.services.medication_base import MedicationServiceBase
from app.repositories.user_repository import UserRepository
from app.services.llm import LLMService
from app.services.pdf import PdfService
from app.services.storage import StorageService
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
    ):
        self.appointment_repo = appointment_repo
        self.symptoms_repo = symptoms_repo
        self.user_repo = user_repo
        self.llm_service = llm_service
        self.storage_service = storage_service
        self.pdf_service = pdf_service
        self.medication_service = medication_service

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
        system_prompt, user_prompt = self._build_narrative_prompts(
            context=context,
            frequency_stats=frequency_stats,
            cooccurrence_stats=cooccurrence_stats,
            days_back=days_back,
            start_date=start_date,
            end_date=end_date,
            journey_stage=journey_stage,
            age=age,
            current_medications=current_medications,
        )

        # Call LLM
        logger.info(
            "Calling LLM to generate narrative: appointment_id=%s", appointment_id
        )
        try:
            narrative = await self.llm_service.provider.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=600,
                temperature=0.3,
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

        # Save to database
        await self.appointment_repo.save_narrative(appointment_id, user_id, narrative)

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

        # Call LLM
        try:
            raw_suggestions = await self.llm_service.generate_scenario_suggestions(
                scenarios_to_generate=scenarios_to_generate,
                concerns=concerns,
                appointment_type=context.appointment_type.value,
                goal=context.goal.value,
                dismissed_before=context.dismissed_before.value,
                user_age=age,
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

        # Build scenario cards
        scenario_cards: list[ScenarioCard] = []
        for idx, (scenario_title, suggestion_data) in enumerate(
            zip(scenarios_to_generate, suggestions_list)
        ):
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
                    category=self._get_scenario_category(scenario_title),
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

        narrative = appointment_data.get("narrative", "No narrative available.")
        concerns = appointment_data.get("concerns", [])
        scenarios_data = appointment_data.get("scenarios", [])

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
        concerns_list: list = concerns if isinstance(concerns, list) else []

        scenarios_for_pdf: list[dict] = []
        if scenarios_data and isinstance(scenarios_data, list):
            scenarios_for_pdf = scenarios_data
        elif isinstance(scenarios_data, dict):
            scenarios_for_pdf = [scenarios_data]

        # Generate provider summary via LLM
        try:
            provider_summary_md = await self.llm_service.generate_pdf_content(
                content_type="provider_summary",
                narrative=narrative_text,
                concerns=concerns_list,
                appointment_type=context.appointment_type.value,
                goal=context.goal.value,
                user_age=age,
                urgent_symptom=context.urgent_symptom,
            )
        except TimeoutError:
            logger.error(
                "LLM timed out for provider summary: appointment_id=%s", appointment_id
            )
            raise DatabaseError("LLM request timed out generating provider summary")
        except Exception as exc:
            logger.error(
                "LLM failed for provider summary: appointment_id=%s error=%s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate provider summary: {exc}") from exc

        # Generate personal cheat sheet via LLM
        try:
            cheatsheet_md = await self.llm_service.generate_pdf_content(
                content_type="personal_cheatsheet",
                narrative=narrative_text,
                concerns=concerns_list,
                appointment_type=context.appointment_type.value,
                goal=context.goal.value,
                user_age=age,
                urgent_symptom=context.urgent_symptom,
                scenarios=scenarios_for_pdf,
            )
        except TimeoutError:
            logger.error(
                "LLM timed out for cheat sheet: appointment_id=%s", appointment_id
            )
            raise DatabaseError("LLM request timed out generating cheat sheet")
        except Exception as exc:
            logger.error(
                "LLM failed for cheat sheet: appointment_id=%s error=%s",
                appointment_id,
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate cheat sheet: {exc}") from exc

        # Convert markdown to PDFs
        try:
            provider_summary_pdf = self.pdf_service.markdown_to_pdf(
                provider_summary_md, title="Provider Summary"
            )
            cheatsheet_pdf = self.pdf_service.markdown_to_pdf(
                cheatsheet_md, title="Personal Cheat Sheet"
            )
        except Exception as exc:
            logger.error("Failed to convert markdown to PDF: %s", exc, exc_info=True)
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

    def _build_narrative_prompts(
        self,
        context: AppointmentContext,
        frequency_stats: list,
        cooccurrence_stats: list,
        days_back: int,
        start_date: Any,
        end_date: Any,
        journey_stage: str,
        age: int | None,
        current_medications: Optional[list] = None,
    ) -> tuple[str, str]:
        """Build system and user prompts for narrative LLM call."""
        goal_str = context.goal.value.replace("_", " ").title()
        appt_type_str = context.appointment_type.value.replace("_", " ").title()
        age_str = str(age) if age else "not specified"

        system_prompt = (
            "You are preparing a clinical summary of symptom tracking data for a healthcare provider "
            "appointment. Your role is to present objective patterns from personal health tracking — "
            "not to diagnose, interpret causes, or recommend treatments.\n\n"
            "Rules:\n"
            "- Always use 'logs show' or 'data indicates' — never 'you have' or diagnose\n"
            "- Never suggest a medical condition, cause, or specific treatment\n"
            "- Frame observations as patterns worth discussing with a provider\n"
            "- Professional, neutral, clinical tone\n"
            "- Write 2–3 clear paragraphs suitable for a healthcare conversation\n"
            "- End by noting these patterns are worth discussing with a provider"
        )

        freq_lines = [
            f"- {s.symptom_name} ({s.category}): logged {s.count} time(s)"
            for s in frequency_stats[:10]
        ]
        freq_text = "\n".join(freq_lines) if freq_lines else "No symptom data."

        coocc_lines = [
            f"- {p.symptom1_name} + {p.symptom2_name}: "
            f"co-occurred {p.cooccurrence_count} time(s) "
            f"({round(p.cooccurrence_rate * 100)}% of {p.symptom1_name} logs)"
            for p in cooccurrence_stats[:5]
        ]
        coocc_text = (
            "\n".join(coocc_lines)
            if coocc_lines
            else "No notable co-occurrence patterns."
        )

        med_section = ""
        if current_medications:
            med_lines = [
                f"- {m.medication_name} {m.dose} ({m.delivery_method})"
                + (f", started {m.start_date}" if m.start_date else "")
                for m in current_medications
            ]
            med_section = "\n\nCurrent MHT medications:\n" + "\n".join(med_lines)

        user_prompt = (
            f"Write a 2–3 paragraph clinical summary for a healthcare appointment. "
            f"Patient context: {appt_type_str} appointment, goal is '{goal_str}', "
            f"age {age_str}, journey stage: {journey_stage}. "
            f"Symptom tracking covers {days_back} days "
            f"({start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}).\n\n"
            f"Most frequently logged symptoms:\n{freq_text}\n\n"
            f"Symptom patterns (co-occurrences):\n{coocc_text}"
            f"{med_section}\n\n"
            "Write a clear, objective summary using 'logs show' language throughout. "
            "No diagnoses. No treatment recommendations."
        )

        return system_prompt, user_prompt

    def _select_scenarios(
        self, context: AppointmentContext, journey_stage: str
    ) -> list[str]:
        """Select 5-7 dismissal scenarios based on appointment context.

        When goal is urgent_symptom, selects scenarios specific to that symptom.
        For other goals, uses goal-specific dismissal scenarios.
        """
        urgent_symptom = context.urgent_symptom
        scenarios = []

        if context.goal.value == "urgent_symptom" and not urgent_symptom:
            urgent_symptom = "perimenopause symptoms"

        if (
            context.goal.value == "urgent_symptom"
            and urgent_symptom
            and urgent_symptom != "perimenopause symptoms"
        ):
            if (
                "brain fog" in urgent_symptom.lower()
                or "cognitive" in urgent_symptom.lower()
                or "concentration" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "Cognitive symptoms don't respond to hormone therapy",
                        "Brain fog is just normal aging",
                        "That's probably anxiety, not hormones",
                        "You should see a neurologist, not a gynecologist",
                        "Cognitive decline at your stage is expected",
                    ]
                )
            elif (
                "hot flash" in urgent_symptom.lower()
                or "vasomotor" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "Hormone therapy increases breast cancer risk",
                        "Hot flashes will go away on their own",
                        "You just need to dress in layers and use a fan",
                        "Hot flashes aren't a real medical symptom",
                        "Let's try an antidepressant first",
                    ]
                )
            elif (
                "sleep" in urgent_symptom.lower()
                or "insomnia" in urgent_symptom.lower()
                or "waking" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "Sleep disruption at your age is normal",
                        "You should see a sleep specialist, not discuss hormones",
                        "Melatonin or sleep hygiene will fix this",
                        "Hormone therapy doesn't help sleep",
                        "Let's try an antidepressant first",
                    ]
                )
            elif "anxiety" in urgent_symptom.lower():
                scenarios.extend(
                    [
                        "That sounds like anxiety disorder, you need a psychiatrist",
                        "Let's try an antidepressant first",
                        "Hormone therapy won't help anxiety",
                        "You're just stressed, try meditation",
                        "Anxiety medications are better than hormone therapy",
                    ]
                )
            elif (
                "vaginal" in urgent_symptom.lower()
                or "dryness" in urgent_symptom.lower()
                or "sexual" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "Just use lube, that's the standard treatment",
                        "That's a gynecology issue, not a hormone issue",
                        "Vaginal issues are normal at this stage",
                        "You don't need systemic treatment for local symptoms",
                        "Let's try an antidepressant first",
                    ]
                )
            elif "joint" in urgent_symptom.lower() or "pain" in urgent_symptom.lower():
                scenarios.extend(
                    [
                        "Joint pain isn't related to hormones",
                        "You should see a rheumatologist",
                        "That's just arthritis, not perimenopause",
                        "Exercise will fix this, not hormones",
                        "Your symptoms aren't severe enough to treat",
                    ]
                )
            elif (
                "bladder" in urgent_symptom.lower()
                or "urinary" in urgent_symptom.lower()
                or "incontinence" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "Bladder issues are gynecological, not hormonal",
                        "You need pelvic floor physical therapy, not hormones",
                        "That's normal at your stage, you'll have to manage it",
                        "Kegel exercises should be enough",
                        "Hormone therapy doesn't help bladder symptoms",
                    ]
                )
            elif (
                "mood" in urgent_symptom.lower()
                or "depression" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "That sounds like depression, you need an antidepressant",
                        "Hormone therapy isn't approved for mood",
                        "You should see a psychiatrist",
                        "Mood changes are psychological, not hormonal",
                        "Let's try an antidepressant first",
                    ]
                )
            elif (
                "fatigue" in urgent_symptom.lower() or "tired" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "Fatigue is normal aging, not hormonal",
                        "You just need better sleep hygiene",
                        "That sounds like thyroid or anemia, let me check labs",
                        "Hormone therapy won't fix your energy",
                        "You should get more exercise",
                    ]
                )
            elif (
                "skin" in urgent_symptom.lower()
                or "hair" in urgent_symptom.lower()
                or "nail" in urgent_symptom.lower()
            ):
                scenarios.extend(
                    [
                        "Skin changes are cosmetic, not medical",
                        "You should see a dermatologist",
                        "That's not related to perimenopause",
                        "Hair loss is normal aging",
                        "Hormone therapy doesn't improve skin quality",
                    ]
                )
            else:
                scenarios.extend(
                    [
                        "That symptom isn't really related to perimenopause",
                        "Your symptoms aren't severe enough to treat",
                        "Let's wait and see if it gets better",
                        "That's probably something else, not hormones",
                    ]
                )
            scenarios.extend(
                [
                    "Your symptoms will go away on their own",
                    "You're just stressed or anxious",
                ]
            )
        else:
            if context.goal.value == "explore_hrt":
                scenarios.extend(
                    [
                        "Hormone therapy increases breast cancer risk",
                        "I don't prescribe that, I give the birth control pill instead",
                        "Let's try an antidepressant first",
                    ]
                )
            elif context.goal.value == "optimize_current_treatment":
                scenarios.extend(
                    [
                        "Your symptoms aren't severe enough to treat",
                        "That dose is already too high",
                        "Let's try lifestyle changes first",
                    ]
                )
            elif context.goal.value == "assess_status":
                scenarios.extend(
                    [
                        "Your symptoms will go away on their own",
                        "You're just stressed or anxious",
                    ]
                )

            if context.dismissed_before.value == "multiple_times":
                scenarios.extend(["What are the triggers?"])
            elif context.dismissed_before.value == "once_or_twice":
                scenarios.extend(["What are the triggers?"])

        # Deduplicate and limit to 7
        scenarios = list(dict.fromkeys(scenarios))[:7]

        logger.info(
            "Selected %d scenarios, has_urgent=%s",
            len(scenarios),
            bool(urgent_symptom),
        )
        return scenarios

    def _get_scenario_category(self, title: str) -> str:
        """Determine scenario category from dismissal title for frontend grouping."""
        title_lower = title.lower()

        if "breast cancer" in title_lower or "hormone therapy increases" in title_lower:
            return "hrt-safety"
        elif "antidepressant" in title_lower or "psychiatrist" in title_lower:
            return "wrong-specialist"
        elif (
            "normal" in title_lower
            or "aging" in title_lower
            or "expected" in title_lower
            or "natural" in title_lower
        ):
            return "normalization"
        elif (
            "specialist" in title_lower
            or "dermatologist" in title_lower
            or "rheumatologist" in title_lower
            or "neurologist" in title_lower
            or "sleep specialist" in title_lower
        ):
            return "specialist-referral"
        elif (
            "won't help" in title_lower
            or "doesn't" in title_lower
            or "not related" in title_lower
            or "isn't" in title_lower
        ):
            return "dismissal"
        elif (
            "lube" in title_lower
            or "kegel" in title_lower
            or "lifestyle" in title_lower
            or "meditation" in title_lower
            or "hygiene" in title_lower
            or "dress" in title_lower
            or "fan" in title_lower
        ):
            return "lifestyle-only"
        elif "go away" in title_lower or "wait" in title_lower:
            return "wait-and-see"
        elif (
            "stressed" in title_lower
            or "anxious" in title_lower
            or "psychological" in title_lower
            or "anxiety" in title_lower
        ):
            return "psychology"
        elif (
            "severe" in title_lower
            or "enough" in title_lower
            or "dose" in title_lower
            or "high" in title_lower
        ):
            return "dismissal"
        else:
            return "general"
