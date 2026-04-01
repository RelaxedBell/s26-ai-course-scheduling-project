"""Tests for the neural network schedule optimizer."""

from pathlib import Path

import pytest

from src.data.course_loader import load_courses
from src.data.review_data import get_all_summaries, load_reviews
from src.data.section_data import load_sections
from src.data.course_graph import CourseGraph
from src.models.bayes_net import NaiveBayesScorer
from src.models.constraint_solver import Schedule, ScheduleGenerator
from src.models.neural_optimizer import ScheduleRanker
from src.student.preferences import StudentPreferences

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "courses.json"
REVIEWS_PATH = PROJECT_ROOT / "data" / "reviews" / "synthetic_reviews.json"
SECTIONS_PATH = PROJECT_ROOT / "data" / "sections" / "fall_2026_sections.json"


def _generate_test_schedules():
    """Generate some schedules for testing."""
    courses = load_courses(COURSES_JSON)
    graph = CourseGraph(courses)
    sections = load_sections(SECTIONS_PATH)
    reviews = load_reviews(REVIEWS_PATH)
    summaries = get_all_summaries(reviews)
    prefs = StudentPreferences(preferred_topics=["AI"])

    scorer = NaiveBayesScorer()
    scorer.train(courses, summaries, prefs)
    scores_dict = dict(scorer.score_courses(courses, summaries))

    completed = frozenset({"CS 1110", "CS 2100", "CS 2120", "CS 2130"})
    credit_lookup = {code: c.credits for code, c in courses.items()}
    gen = ScheduleGenerator(
        graph, sections, completed, prefs,
        course_scores=scores_dict,
        credit_lookup=credit_lookup,
    )
    schedules = gen.generate(max_schedules=10)
    return schedules, courses, summaries, scores_dict


class TestScheduleRanker:
    def setup_method(self):
        result = _generate_test_schedules()
        self.schedules, self.courses, self.summaries, self.scores_dict = result

    def test_train_converges(self):
        ranker = ScheduleRanker()
        # Heuristic labels based on CSP scores
        labels = [s.score for s in self.schedules]
        losses = ranker.train(
            self.schedules, labels,
            self.courses, self.summaries, self.scores_dict,
            epochs=30,
        )
        assert len(losses) == 30
        # Loss should generally decrease
        assert losses[-1] <= losses[0] + 0.1  # Allow small fluctuation

    def test_rerank_preserves_count(self):
        ranker = ScheduleRanker()
        labels = [s.score for s in self.schedules]
        ranker.train(
            self.schedules, labels,
            self.courses, self.summaries, self.scores_dict,
        )
        reranked = ranker.rerank_schedules(
            self.schedules, self.courses, self.summaries, self.scores_dict
        )
        assert len(reranked) == len(self.schedules)

    def test_rerank_sorted_descending(self):
        ranker = ScheduleRanker()
        labels = [s.score for s in self.schedules]
        ranker.train(
            self.schedules, labels,
            self.courses, self.summaries, self.scores_dict,
        )
        reranked = ranker.rerank_schedules(
            self.schedules, self.courses, self.summaries, self.scores_dict
        )
        scores = [s.score for s in reranked]
        assert scores == sorted(scores, reverse=True)

    def test_predict_single(self):
        ranker = ScheduleRanker()
        labels = [s.score for s in self.schedules]
        ranker.train(
            self.schedules, labels,
            self.courses, self.summaries, self.scores_dict,
        )
        score = ranker.predict_score(
            self.schedules[0],
            self.courses, self.summaries, self.scores_dict,
        )
        assert 0.0 <= score <= 1.0

    def test_untrained_raises(self):
        ranker = ScheduleRanker()
        with pytest.raises(RuntimeError):
            ranker.rerank_schedules(
                self.schedules, self.courses, self.summaries, self.scores_dict
            )

    def test_save_and_load(self, tmp_path):
        ranker = ScheduleRanker()
        labels = [s.score for s in self.schedules]
        ranker.train(
            self.schedules, labels,
            self.courses, self.summaries, self.scores_dict,
        )
        model_path = tmp_path / "model.pt"
        ranker.save(model_path)

        ranker2 = ScheduleRanker()
        ranker2.load(model_path)
        score = ranker2.predict_score(
            self.schedules[0],
            self.courses, self.summaries, self.scores_dict,
        )
        assert 0.0 <= score <= 1.0
