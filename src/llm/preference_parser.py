"""Parse natural language preferences into structured StudentPreferences."""

from __future__ import annotations

import json
import logging

from src.llm.llm_client import LLMClient
from src.student.preferences import StudentPreferences

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a course scheduling assistant. Parse the user's natural language
preferences into a JSON object with these fields:
- difficulty_preference: integer 1-5 (1=easy, 5=challenging)
- max_credits: integer (default 15)
- min_credits: integer (default 12)
- preferred_topics: list of topic strings (e.g. ["AI", "systems"])
- liked_courses: list of course codes (e.g. ["CS 4710"])
- disliked_courses: list of course codes
- time_blocks_unavailable: list of {days: [...], start_time: "HH:MM", end_time: "HH:MM"}
- prefer_morning: true/false/null

Respond with ONLY valid JSON, no other text."""


def parse_natural_language_preferences(
    user_input: str,
    client: LLMClient,
    max_retries: int = 2,
) -> StudentPreferences:
    """Parse natural language into StudentPreferences.

    Falls back to defaults if parsing fails.
    """
    for attempt in range(max_retries + 1):
        try:
            response = client.generate(
                prompt=user_input,
                system_prompt=SYSTEM_PROMPT,
                max_tokens=512,
            )
            # Try to extract JSON from the response
            raw = _extract_json(response)
            data = json.loads(raw)
            return StudentPreferences(**data)
        except Exception as e:
            logger.warning(
                "Preference parsing attempt %d failed: %s", attempt + 1, e
            )
            if attempt == max_retries:
                logger.warning("Falling back to default preferences")
                return StudentPreferences()

    return StudentPreferences()


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                json_lines.append(line)
        return "\n".join(json_lines)

    # Try to find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]

    return text
