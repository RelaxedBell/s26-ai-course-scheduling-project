"""LLM client abstraction for preference parsing and explanations.

Supports Ollama (local) and falls back to a template-based approach
when no LLM server is available.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Abstract LLM client interface."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        """Generate text from a prompt."""


class OllamaClient(LLMClient):
    """LLM client using Ollama local server."""

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
    ):
        self._model = model
        self._base_url = base_url

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        import httpx

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            resp = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": messages,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
        except Exception as e:
            logger.warning("Ollama request failed: %s", e)
            raise


class AnthropicClient(LLMClient):
    """LLM client using the Anthropic Claude API."""

    def __init__(self, model: str = "claude-haiku-4-5"):
        import os
        import anthropic

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set.")
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        try:
            message = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system_prompt if system_prompt else "",
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.warning("Anthropic request failed: %s", e)
            raise


class TemplateLLMClient(LLMClient):
    """Fallback template-based 'LLM' for when no server is available.

    Uses keyword matching and templates instead of actual inference.
    Suitable for development and testing.
    """

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        max_tokens: int = 1024,
    ) -> str:
        # Try to detect what kind of request this is
        prompt_lower = prompt.lower()

        if "parse" in system_prompt.lower() or "preference" in system_prompt.lower():
            return self._parse_preferences(prompt)
        if "explain" in system_prompt.lower() or "schedule" in system_prompt.lower():
            return self._explain_schedule(prompt)
        if "sentiment" in system_prompt.lower():
            return self._analyze_sentiment(prompt)

        return "I can help you with course scheduling. Please tell me about your preferences."

    def _parse_preferences(self, text: str) -> str:
        """Extract preferences from natural language using keyword matching."""
        text_lower = text.lower()

        prefs: dict = {
            "difficulty_preference": 3,
            "max_credits": 15,
            "min_credits": 12,
            "preferred_topics": [],
            "liked_courses": [],
            "disliked_courses": [],
            "time_blocks_unavailable": [],
            "prefer_morning": None,
        }

        # Difficulty
        if any(w in text_lower for w in ["easy", "light", "relaxed", "chill"]):
            prefs["difficulty_preference"] = 1
        elif any(w in text_lower for w in ["moderate", "balanced"]):
            prefs["difficulty_preference"] = 3
        elif any(w in text_lower for w in ["hard", "challenging", "rigorous"]):
            prefs["difficulty_preference"] = 5

        # Credits
        import re
        credit_match = re.search(r"(\d{1,2})\s*credits?", text_lower)
        if credit_match:
            n = int(credit_match.group(1))
            prefs["max_credits"] = min(21, n + 1)
            prefs["min_credits"] = max(3, n - 1)

        # Topics
        topic_keywords = {
            "ai": "AI", "artificial intelligence": "AI",
            "machine learning": "machine learning", "ml": "machine learning",
            "security": "security", "cyber": "security",
            "systems": "systems", "operating": "systems",
            "data": "data", "database": "data",
            "web": "web", "software": "software engineering",
            "theory": "theory", "algorithm": "algorithms",
            "graphics": "graphics", "vision": "computer vision",
            "nlp": "NLP", "natural language": "NLP",
            "robotics": "robotics", "robot": "robotics",
        }
        for keyword, topic in topic_keywords.items():
            if keyword in text_lower:
                if topic not in prefs["preferred_topics"]:
                    prefs["preferred_topics"].append(topic)

        # Time preferences
        if any(w in text_lower for w in ["morning", "early"]):
            prefs["prefer_morning"] = True
        elif any(w in text_lower for w in ["afternoon", "late", "evening"]):
            prefs["prefer_morning"] = False

        # No-before time blocks
        time_match = re.search(
            r"(?:no|not|can't|cannot|don't).*(?:before|until)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            text_lower,
        )
        if time_match:
            hour = int(time_match.group(1))
            minute = time_match.group(2) or "00"
            ampm = time_match.group(3)
            if ampm == "pm" and hour < 12:
                hour += 12
            prefs["time_blocks_unavailable"] = [{
                "days": ["M", "T", "W", "R", "F"],
                "start_time": "08:00",
                "end_time": f"{hour:02d}:{minute}",
            }]

        return json.dumps(prefs)

    def _explain_schedule(self, prompt: str) -> str:
        """Generate a template-based schedule explanation."""
        return (
            "This schedule was selected based on your preferences. "
            "The courses were chosen to balance your desired difficulty level, "
            "topic interests, and time constraints while satisfying degree requirements. "
            "Each course was scored using a Naive Bayes model trained on review data "
            "and your stated preferences, then validated against prerequisite requirements "
            "and time conflict constraints."
        )

    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment scoring."""
        positive = ["great", "excellent", "loved", "amazing", "good", "enjoy"]
        negative = ["terrible", "boring", "bad", "hate", "awful", "difficult"]
        text_lower = text.lower()
        pos = sum(1 for w in positive if w in text_lower)
        neg = sum(1 for w in negative if w in text_lower)
        score = 0.5 + 0.1 * (pos - neg)
        return json.dumps({"sentiment": max(0, min(1, score))})


def create_llm_client(
    backend: str = "auto",
    model: str = "qwen2.5:7b",
) -> LLMClient:
    """Create an LLM client with the specified backend.

    Args:
        backend: 'ollama', 'anthropic', 'template', or 'auto'
                 (try ollama → anthropic → template).
        model: Model name for Ollama.
    """
    if backend == "template":
        return TemplateLLMClient()

    if backend == "ollama":
        return OllamaClient(model=model)

    if backend == "anthropic":
        return AnthropicClient()

    # Auto: try Ollama → Anthropic → template
    if backend == "auto":
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
            if resp.status_code == 200:
                logger.info("Ollama server detected, using Ollama backend")
                return OllamaClient(model=model)
        except Exception:
            pass

        try:
            import os
            if os.environ.get("ANTHROPIC_API_KEY"):
                client = AnthropicClient()
                logger.info("Anthropic API key found, using Anthropic backend")
                return client
        except Exception:
            pass

        logger.info("No LLM backend available, using template backend")
        return TemplateLLMClient()

    raise ValueError(f"Unknown backend: {backend}")
