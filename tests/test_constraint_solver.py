"""Tests for the CSP schedule generator."""

from pathlib import Path

from src.data.course_graph import CourseGraph
from src.data.course_loader import load_courses
from src.data.review_data import get_all_summaries, load_reviews
from src.data.section_data import load_sections
from src.models.bayes_net import NaiveBayesScorer
from src.models.constraint_solver import ScheduleGenerator
from src.student.preferences import StudentPreferences, TimeBlock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "courses.json"
REVIEWS_PATH = PROJECT_ROOT / "data" / "reviews" / "synthetic_reviews.json"
SECTIONS_PATH = PROJECT_ROOT / "data" / "sections" / "fall_2026_sections.json"


class TestScheduleGenerator:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)
        self.graph = CourseGraph(self.courses)
        self.sections = load_sections(SECTIONS_PATH)
        self.reviews = load_reviews(REVIEWS_PATH)
        self.summaries = get_all_summaries(self.reviews)
        self.credit_lookup = {
            code: c.credits for code, c in self.courses.items()
        }

    def test_generates_schedules(self):
        prefs = StudentPreferences()
        completed = frozenset({"CS 1110", "CS 2100", "CS 2120", "CS 2130"})
        gen = ScheduleGenerator(
            self.graph, self.sections, completed, prefs,
            credit_lookup=self.credit_lookup,
        )
        schedules = gen.generate(max_schedules=5)
        assert len(schedules) > 0

    def test_no_time_conflicts(self):
        prefs = StudentPreferences()
        completed = frozenset({"CS 1110"})
        gen = ScheduleGenerator(
            self.graph, self.sections, completed, prefs,
            credit_lookup=self.credit_lookup,
        )
        schedules = gen.generate(max_schedules=5)
        for sched in schedules:
            sections = list(sched.sections)
            for i in range(len(sections)):
                for j in range(i + 1, len(sections)):
                    assert not sections[i].conflicts_with(sections[j]), (
                        f"Time conflict: {sections[i].course_code} "
                        f"vs {sections[j].course_code}"
                    )

    def test_no_duplicate_courses(self):
        prefs = StudentPreferences()
        completed = frozenset({"CS 1110"})
        gen = ScheduleGenerator(
            self.graph, self.sections, completed, prefs,
            credit_lookup=self.credit_lookup,
        )
        schedules = gen.generate(max_schedules=5)
        for sched in schedules:
            codes = [s.course_code for s in sched.sections]
            assert len(codes) == len(set(codes))

    def test_respects_time_blocks(self):
        prefs = StudentPreferences(
            time_blocks_unavailable=[
                TimeBlock(
                    days=["M", "W", "F"],
                    start_time="08:00",
                    end_time="12:00",
                )
            ]
        )
        completed = frozenset({"CS 1110", "CS 2100", "CS 2120"})
        gen = ScheduleGenerator(
            self.graph, self.sections, completed, prefs,
            credit_lookup=self.credit_lookup,
        )
        schedules = gen.generate(max_schedules=5)
        for sched in schedules:
            for section in sched.sections:
                if set(section.days) & {"M", "W", "F"}:
                    from src.data.section_data import _parse_time
                    start = _parse_time(section.start_time)
                    block_end = _parse_time("12:00")
                    block_start = _parse_time("08:00")
                    end = _parse_time(section.end_time)
                    # Should not overlap with 8:00-12:00
                    if start < block_end and block_start < end:
                        assert False, (
                            f"{section.course_code} at {section.start_time}-"
                            f"{section.end_time} conflicts with blocked time"
                        )

    def test_schedules_sorted_by_score(self):
        prefs = StudentPreferences()
        completed = frozenset({"CS 1110", "CS 2100"})
        gen = ScheduleGenerator(
            self.graph, self.sections, completed, prefs,
            credit_lookup=self.credit_lookup,
        )
        schedules = gen.generate(max_schedules=5)
        scores = [s.score for s in schedules]
        assert scores == sorted(scores, reverse=True)

    def test_with_bayes_scores(self):
        prefs = StudentPreferences(preferred_topics=["AI"])
        scorer = NaiveBayesScorer()
        scorer.train(self.courses, self.summaries, prefs)
        results = scorer.score_courses(self.courses, self.summaries)
        scores_dict = dict(results)

        completed = frozenset({"CS 1110", "CS 2100", "CS 2120", "CS 2130"})
        gen = ScheduleGenerator(
            self.graph, self.sections, completed, prefs,
            course_scores=scores_dict,
            credit_lookup=self.credit_lookup,
        )
        schedules = gen.generate(max_schedules=5)
        assert len(schedules) > 0
        # Scores should be positive
        for sched in schedules:
            assert sched.score > 0

    def test_empty_candidates(self):
        prefs = StudentPreferences()
        # Complete everything — nothing should be available
        completed = frozenset(self.courses.keys())
        gen = ScheduleGenerator(
            self.graph, self.sections, completed, prefs,
            credit_lookup=self.credit_lookup,
        )
        schedules = gen.generate(max_schedules=5)
        assert len(schedules) == 0
