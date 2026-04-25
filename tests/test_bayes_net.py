"""Tests for the Naive Bayes Net course scorer."""

from pathlib import Path

import pytest

from src.data.course_loader import load_courses
from src.data.review_data import get_all_summaries, load_reviews
from src.models.bayes_net import NaiveBayesScorer
from src.models.feature_extractor import (
    compute_preference_alignment,
    extract_course_features,
    extract_topic_vector,
)
from src.student.preferences import StudentPreferences

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "courses.json"
REVIEWS_PATH = PROJECT_ROOT / "data" / "reviews" / "synthetic_reviews.json"


class TestFeatureExtractor:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)
        self.reviews = load_reviews(REVIEWS_PATH)
        self.summaries = get_all_summaries(self.reviews)

    def test_extract_course_features_shape(self):
        course = self.courses["CS 1110"]
        summary = self.summaries.get("CS 1110")
        feat = extract_course_features(course, summary)
        assert feat.shape == (18,)
        assert all(0.0 <= v <= 1.5 for v in feat)

    def test_extract_without_summary(self):
        course = self.courses["CS 1110"]
        feat = extract_course_features(course, None)
        assert feat.shape == (18,)

    def test_topic_vector(self):
        topics = extract_topic_vector(
            "This course covers artificial intelligence and machine learning."
        )
        assert topics["ai"] == 1.0
        assert topics["graphics"] == 0.0

    def test_preference_alignment_liked(self):
        course = self.courses["CS 4710"]  # AI course
        summary = self.summaries.get("CS 4710")
        prefs = StudentPreferences(
            difficulty_preference=3,
            preferred_topics=["AI", "machine learning"],
            liked_courses=["CS 4710"],
        )
        score = compute_preference_alignment(course, summary, prefs)
        assert score > 0.5

    def test_preference_alignment_disliked(self):
        course = self.courses["CS 4710"]
        summary = self.summaries.get("CS 4710")
        prefs = StudentPreferences(
            disliked_courses=["CS 4710"],
        )
        score = compute_preference_alignment(course, summary, prefs)
        assert score < 0.7  # Should be lower than default


class TestNaiveBayesScorer:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)
        self.reviews = load_reviews(REVIEWS_PATH)
        self.summaries = get_all_summaries(self.reviews)

    def test_train_and_score(self):
        scorer = NaiveBayesScorer()
        prefs = StudentPreferences(
            difficulty_preference=2,
            preferred_topics=["AI"],
        )
        scorer.train(self.courses, self.summaries, prefs)
        results = scorer.score_courses(self.courses, self.summaries)
        assert len(results) == len(self.courses)
        # All scores between 0 and 1
        for code, score in results:
            assert 0.0 <= score <= 1.0

    def test_scores_are_sorted_descending(self):
        scorer = NaiveBayesScorer()
        prefs = StudentPreferences(preferred_topics=["systems"])
        scorer.train(self.courses, self.summaries, prefs)
        results = scorer.score_courses(self.courses, self.summaries)
        scores = [s for _, s in results]
        assert scores == sorted(scores, reverse=True)

    def test_untrained_raises(self):
        scorer = NaiveBayesScorer()
        with pytest.raises(RuntimeError):
            scorer.score_courses(self.courses, self.summaries)

    def test_ai_student_prefers_ai_courses(self):
        """Student who likes AI should rank AI courses higher on average."""
        scorer = NaiveBayesScorer()
        prefs = StudentPreferences(
            difficulty_preference=3,
            preferred_topics=["AI", "machine learning", "neural"],
        )
        scorer.train(self.courses, self.summaries, prefs)
        results = scorer.score_courses(self.courses, self.summaries)

        scores_dict = dict(results)
        # CS 4710 (AI) should have a reasonably high score
        ai_score = scores_dict.get("CS 4710", 0)
        all_scores = [s for _, s in results]
        median_score = sorted(all_scores)[len(all_scores) // 2]
        assert ai_score >= median_score * 0.8  # At least close to median

    def test_score_single(self):
        scorer = NaiveBayesScorer()
        prefs = StudentPreferences()
        scorer.train(self.courses, self.summaries, prefs)
        course = self.courses["CS 2100"]
        summary = self.summaries.get("CS 2100")
        score = scorer.score_single(course, summary)
        assert 0.0 <= score <= 1.0

    def test_empty_preferences(self):
        """Default preferences should still produce valid scores."""
        scorer = NaiveBayesScorer()
        prefs = StudentPreferences()
        scorer.train(self.courses, self.summaries, prefs)
        results = scorer.score_courses(self.courses, self.summaries)
        assert len(results) > 0

    def test_scores_not_all_saturated(self):
        """Calibrated scores should have readable spread, not all 100%."""
        scorer = NaiveBayesScorer()
        prefs = StudentPreferences(preferred_topics=["AI"])
        scorer.train(self.courses, self.summaries, prefs)
        results = scorer.score_courses(self.courses, self.summaries)
        scores = [s for _, s in results]
        assert max(scores) <= 0.951
        assert min(scores) >= 0.049
        assert len(set(round(s, 3) for s in scores)) > 3
