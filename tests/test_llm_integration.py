"""Tests for LLM integration (using template client, no live LLM needed)."""

from pathlib import Path

from src.data.course_loader import load_courses
from src.llm.explainer import explain_schedule
from src.llm.llm_client import TemplateLLMClient, create_llm_client
from src.llm.preference_parser import parse_natural_language_preferences
from src.llm.sentiment_analyzer import analyze_review_sentiment, extract_course_topics
from src.models.constraint_solver import Schedule
from src.data.section_data import CourseSection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "courses.json"


class TestTemplateLLMClient:
    def setup_method(self):
        self.client = TemplateLLMClient()

    def test_create_client_auto_falls_back(self):
        # No Ollama running, should fall back to template
        client = create_llm_client(backend="auto")
        assert isinstance(client, TemplateLLMClient)

    def test_basic_generation(self):
        resp = self.client.generate("Hello", system_prompt="")
        assert len(resp) > 0


class TestPreferenceParser:
    def setup_method(self):
        self.client = TemplateLLMClient()

    def test_parse_easy_semester(self):
        prefs = parse_natural_language_preferences(
            "I want an easy semester with about 12 credits, "
            "interested in AI and machine learning",
            self.client,
        )
        assert prefs.difficulty_preference <= 2
        assert prefs.max_credits <= 15
        assert len(prefs.preferred_topics) > 0

    def test_parse_time_constraint(self):
        prefs = parse_natural_language_preferences(
            "I can't do anything before 10am. "
            "I prefer afternoon classes.",
            self.client,
        )
        assert prefs.prefer_morning is False

    def test_parse_challenging_with_topics(self):
        prefs = parse_natural_language_preferences(
            "I want a challenging semester focused on security and systems",
            self.client,
        )
        assert prefs.difficulty_preference >= 4
        assert any("security" in t.lower() for t in prefs.preferred_topics)

    def test_empty_input_returns_defaults(self):
        prefs = parse_natural_language_preferences("", self.client)
        assert prefs.difficulty_preference == 3
        assert prefs.max_credits == 15


class TestSentimentAnalyzer:
    def setup_method(self):
        self.client = TemplateLLMClient()

    def test_positive_review(self):
        result = analyze_review_sentiment(
            "Great course! Really enjoyed the material. Excellent professor.",
            self.client,
        )
        assert "sentiment" in result
        assert result["sentiment"] >= 0.5

    def test_negative_review(self):
        result = analyze_review_sentiment(
            "Terrible course. Boring lectures. Awful experience.",
            self.client,
        )
        assert result["sentiment"] <= 0.5

    def test_topic_extraction(self):
        topics = extract_course_topics(
            "Introduction to artificial intelligence and machine learning",
            self.client,
        )
        # Template client returns empty list for topic extraction
        assert isinstance(topics, list)


class TestExplainer:
    def setup_method(self):
        self.client = TemplateLLMClient()
        self.courses = load_courses(COURSES_JSON)

    def test_explain_schedule(self):
        from src.student.preferences import StudentPreferences

        sections = (
            CourseSection(
                course_code="CS 4710",
                section_id="001",
                days=["M", "W", "F"],
                start_time="10:00",
                end_time="10:50",
                instructor="Dr. Smith",
            ),
            CourseSection(
                course_code="CS 3100",
                section_id="001",
                days=["T", "R"],
                start_time="14:00",
                end_time="15:15",
                instructor="Dr. Jones",
            ),
        )
        schedule = Schedule(sections=sections, score=0.85)
        prefs = StudentPreferences(preferred_topics=["AI"])
        bayes_scores = {"CS 4710": 0.8, "CS 3100": 0.6}

        explanation = explain_schedule(
            schedule, prefs, self.courses, bayes_scores, self.client
        )
        assert len(explanation) > 50
        assert "schedule" in explanation.lower() or "course" in explanation.lower()
