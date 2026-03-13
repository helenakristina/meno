"""Chat service for Ask Meno features.

Orchestrates chat-related business logic including personalized starter prompts.
"""

import json
import logging
import random
from pathlib import Path
from typing import Optional

from app.exceptions import DatabaseError
from app.repositories.symptoms_repository import SymptomsRepository
from app.models.symptoms import SymptomLogResponse
from app.utils.dates import get_date_range
from app.utils.logging import hash_user_id, safe_summary

logger = logging.getLogger(__name__)


class ChatService:
    """Service for Ask Meno chat features."""

    def __init__(self, symptoms_repo: SymptomsRepository):
        """Initialize ChatService with dependencies.

        Args:
            symptoms_repo: Repository for accessing symptom logs.
        """
        self.symptoms_repo = symptoms_repo
        self._prompt_config: Optional[dict] = None

    async def get_suggested_prompts(
        self,
        user_id: str,
        days_back: int = 30,
        max_prompts: int = 6,
    ) -> dict:
        """Get personalized starter prompts based on recent symptoms.

        Fetches user's recent symptom logs, looks up prompts for those symptoms,
        and returns up to max_prompts (filled with general prompts if needed).

        Args:
            user_id: User ID.
            days_back: Look back N days for symptoms (default 30).
            max_prompts: Maximum prompts to return (default 6).

        Returns:
            {"prompts": [list of prompt strings, up to max_prompts]}.

        Raises:
            DatabaseError: If symptom fetch fails.
        """
        logger.info(
            "Getting suggested prompts for user: %s (days_back=%d)",
            hash_user_id(user_id),
            days_back,
        )

        try:
            # Step 1: Get recent symptoms (get_logs returns tuple: (logs, count))
            start_date, end_date = get_date_range(days_back)
            logs, _ = await self.symptoms_repo.get_logs(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Step 2: Extract unique symptom names from logs
            # logs is a list of SymptomLogResponse objects with enriched symptoms
            symptom_names = set()
            for log in logs:
                # log.symptoms is a list of SymptomDetail objects with name field
                for symptom_detail in log.symptoms:
                    symptom_names.add(symptom_detail.name)

            logger.debug(
                "Extracted %d unique symptoms from %d logs",
                len(symptom_names),
                len(logs),
            )

            # Step 3: Load prompt config
            prompt_config = self._load_prompt_config()

            # Step 4: Build list of prompts
            prompts = []

            # Add symptom-specific prompts
            for symptom in symptom_names:
                if symptom in prompt_config:
                    symptom_prompts = prompt_config[symptom]
                    # Randomly select 1-2 prompts per symptom
                    selected_count = min(2, len(symptom_prompts))
                    selected = random.sample(symptom_prompts, selected_count)
                    prompts.extend(selected)

            # Step 5: Fill with general prompts if needed
            if len(prompts) < max_prompts:
                general = prompt_config.get("general", [])
                needed = max_prompts - len(prompts)
                if general:
                    additional_count = min(needed, len(general))
                    additional = random.sample(general, additional_count)
                    prompts.extend(additional)

            # Step 6: Return up to max_prompts (remove duplicates while preserving order)
            seen = set()
            final_prompts = []
            for prompt in prompts:
                if prompt not in seen:
                    final_prompts.append(prompt)
                    seen.add(prompt)
                if len(final_prompts) >= max_prompts:
                    break

            logger.info(
                safe_summary(
                    "get suggested prompts",
                    "success",
                    count=len(final_prompts),
                )
            )

            return {"prompts": final_prompts}

        except DatabaseError:
            logger.error("Failed to fetch symptoms for prompts")
            raise
        except Exception as exc:
            logger.error(
                "Failed to generate prompts: %s",
                exc,
                exc_info=True,
            )
            raise DatabaseError(f"Failed to generate prompts: {str(exc)}") from exc

    def _load_prompt_config(self) -> dict:
        """Load prompt config from JSON file.

        Returns config cached in memory on first call.
        Subsequent calls return cached config.

        Returns:
            Dictionary mapping symptom names to lists of prompts.
            Returns empty dict if file not found or invalid JSON.
        """
        if self._prompt_config is not None:
            return self._prompt_config

        config_path = (
            Path(__file__).parent.parent.parent / "config" / "starter_prompts.json"
        )

        try:
            with open(config_path) as f:
                config_data = json.load(f)
                self._prompt_config = config_data.get("starter_prompts", {})
                logger.debug(
                    "Loaded prompt config: %d symptom groups",
                    len(self._prompt_config),
                )
                return self._prompt_config
        except FileNotFoundError:
            logger.error("Prompt config file not found: %s", config_path)
            self._prompt_config = {}
            return {}
        except json.JSONDecodeError:
            logger.error("Failed to parse prompt config: %s", config_path)
            self._prompt_config = {}
            return {}
