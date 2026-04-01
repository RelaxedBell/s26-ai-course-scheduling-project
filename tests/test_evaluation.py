"""Tests for evaluation framework."""

from pathlib import Path

from src.data.course_graph import CourseGraph
from src.data.course_loader import load_courses
from src.data.section_data import load_sections
from src.evaluation.evaluator import EvaluationResult, RatingCollector
from src.evaluation.random_baseline import (
    generate_random_schedule,
    generate_random_schedules,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "courses.json"
SECTIONS_PATH = PROJECT_ROOT / "data" / "sections" / "fall_2026_sections.json"


class TestRandomBaseline:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)
        self.graph = CourseGraph(self.courses)
        self.sections = load_sections(SECTIONS_PATH)

    def test_generate_random_schedule(self):
        completed = frozenset({"CS 1110", "CS 2100", "CS 2120"})
        sched = generate_random_schedule(
            self.graph, self.sections, completed
        )
        assert sched is not None
        assert len(sched.sections) >= 3

    def test_random_schedule_no_conflicts(self):
        completed = frozenset({"CS 1110"})
        sched = generate_random_schedule(
            self.graph, self.sections, completed
        )
        if sched is not None:
            sections = list(sched.sections)
            for i in range(len(sections)):
                for j in range(i + 1, len(sections)):
                    assert not sections[i].conflicts_with(sections[j])

    def test_generate_multiple(self):
        completed = frozenset({"CS 1110", "CS 2100"})
        scheds = generate_random_schedules(
            self.graph, self.sections, completed, n=5
        )
        assert len(scheds) > 0


class TestEvaluator:
    def test_rating_collector(self, tmp_path):
        collector = RatingCollector()
        collector.add_rating("model", 0, 8, "good")
        collector.add_rating("model", 1, 7)
        collector.add_rating("random", 0, 4)
        collector.add_rating("random", 1, 5)

        # Save and reload
        path = tmp_path / "ratings.json"
        collector.save(path)

        collector2 = RatingCollector()
        collector2.load(path)
        assert len(collector2.ratings) == 4

    def test_evaluation_result(self):
        result = EvaluationResult(
            model_ratings=[8, 7, 9, 8],
            random_ratings=[4, 5, 3, 4],
        )
        assert result.model_avg > result.random_avg
        assert result.improvement > 0
        summary = result.summary()
        assert "outperforms" in summary

    def test_empty_evaluation(self):
        result = EvaluationResult(model_ratings=[], random_ratings=[])
        assert result.model_avg == 0.0
        assert result.improvement == 0.0

    def test_collector_evaluate(self):
        collector = RatingCollector()
        collector.add_rating("model", 0, 9)
        collector.add_rating("random", 0, 3)
        result = collector.evaluate()
        assert result.model_avg == 9.0
        assert result.random_avg == 3.0
