"""Sentiment analysis for course reviews and descriptions."""

from __future__ import annotations

import json
import logging

from src.llm.llm_client import LLMClient

logger = logging.getLogger(__name__)

SENTIMENT_SYSTEM_PROMPT = """Analyze the sentiment of this course review.
Return a JSON object with:
- sentiment: float 0-1 (0=very negative, 1=very positive)
- difficulty_impression: float 0-1 (0=very easy, 1=very hard)
- key_themes: list of 1-3 theme strings

Respond with ONLY valid JSON."""

TOPIC_EXTRACTION_PROMPT = """Extract topic tags from this course description.
Return a JSON object with:
- topics: list of topic strings (e.g. ["machine learning", "neural networks", "optimization"])

Respond with ONLY valid JSON."""


def analyze_review_sentiment(
    review_text: str,
    client: LLMClient,
) -> dict[str, float | list[str]]:
    """Analyze sentiment of a course review.

    Returns dict with sentiment, difficulty_impression, and key_themes.
    """
    try:
        response = client.generate(
            prompt=review_text,
            system_prompt=SENTIMENT_SYSTEM_PROMPT,
            max_tokens=256,
        )
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        logger.warning("Sentiment analysis failed: %s", e)

    return {"sentiment": 0.5, "difficulty_impression": 0.5, "key_themes": []}


def extract_course_topics(
    description: str,
    client: LLMClient,
) -> list[str]:
    """Extract topic tags from a course description."""
    try:
        response = client.generate(
            prompt=description,
            system_prompt=TOPIC_EXTRACTION_PROMPT,
            max_tokens=256,
        )
        text = response.strip()
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            data = json.loads(text[start:end])
            return data.get("topics", [])
    except Exception as e:
        logger.warning("Topic extraction failed: %s", e)

    return []
