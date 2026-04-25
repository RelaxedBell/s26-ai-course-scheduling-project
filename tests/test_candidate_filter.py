"""Tests for the pre-CSP candidate filter."""

from pathlib import Path

from src.data.course_loader import load_courses
from src.data.section_data import load_sections
from src.models.candidate_filter import (
    CandidateFilter,
    department_of,
    schedule_credits_in_window,
)
from src.student.preferences import StudentPreferences, TimeBlock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "courses.json"
SECTIONS_PATH = PROJECT_ROOT / "data" / "sections" / "fall_2026_sections.json"


class TestCandidateFilter:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)
        self.sections = load_sections(SECTIONS_PATH)
        self.all_codes = list(self.courses.keys())

    def test_department_of(self):
        assert department_of("CS 4710") == "CS"
        assert department_of("MATH 1320") == "MATH"
        assert department_of("BARE") == "BARE"

    def test_drops_completed_courses(self):
        prefs = StudentPreferences()
        completed = frozenset({"CS 1110", "CS 2100"})
        filt = CandidateFilter(
            self.courses, self.sections, completed, prefs
        )
        kept, report = filt.filter(self.all_codes)
        assert "CS 1110" in report.dropped_already_taken
        assert "CS 2100" in report.dropped_already_taken
        assert "CS 1110" not in kept
        assert "CS 2100" not in kept

    def test_drops_courses_with_all_sections_blocked(self):
        # Block every MWF morning; any MWF-morning-only course should drop.
        prefs = StudentPreferences(
            time_blocks_unavailable=[
                TimeBlock(
                    days=["M", "T", "W", "R", "F"],
                    start_time="00:00",
                    end_time="23:59",
                )
            ]
        )
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, report = filt.filter(self.all_codes)
        # With the entire week blocked, any course that has sections
        # should be dropped for time conflict.
        courses_with_sections = {s.course_code for s in self.sections}
        for code in courses_with_sections:
            assert code not in kept

    def test_keeps_course_with_one_viable_section(self):
        # No time blocks -> every course with sections is viable
        prefs = StudentPreferences()
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, report = filt.filter(self.all_codes)
        assert len(report.dropped_time_conflict) == 0

    def test_major_eligibility_keeps_cs_for_cs_major(self):
        prefs = StudentPreferences(declared_major="CS")
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, report = filt.filter(self.all_codes)
        # All non-elective kept codes should be CS
        for code in kept:
            course = self.courses[code]
            if course.course_type.value not in (
                "restricted elective", "integration elective"
            ):
                assert department_of(code) == "CS"

    def test_elective_department_filter(self):
        # Restrict electives to MATH department; since the catalog is
        # all-CS, all electives should be dropped as mismatched.
        prefs = StudentPreferences(preferred_departments=["MATH"])
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, report = filt.filter(self.all_codes)
        # Any kept elective must match MATH prefix
        for code in kept:
            course = self.courses[code]
            if course.course_type.value in (
                "restricted elective", "integration elective"
            ):
                assert department_of(code) == "MATH"

    def test_elective_topic_filter_accepts_matching(self):
        prefs = StudentPreferences(preferred_topics=["machine learning"])
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, _ = filt.filter(self.all_codes)
        # There should be at least one AI/ML-related elective kept
        assert len(kept) > 0

    def test_elective_topic_and_department_union(self):
        # Either topic OR department match should keep an elective.
        prefs = StudentPreferences(
            preferred_topics=["security"],
            preferred_departments=["CS"],
        )
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, _ = filt.filter(self.all_codes)
        # Any CS elective should be kept via department match
        cs_electives = [
            c for c, course in self.courses.items()
            if department_of(c) == "CS"
            and course.course_type.value in (
                "restricted elective", "integration elective"
            )
        ]
        for c in cs_electives:
            assert c in kept

    def test_credit_ceiling_drops_oversized_courses(self):
        # Force a very low ceiling; any course above 3 credits drops.
        prefs = StudentPreferences(
            max_credits=3, min_credits=3, credit_tolerance=0
        )
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, report = filt.filter(self.all_codes)
        for code in kept:
            assert self.courses[code].credits <= 3
        # At least one 4-credit course exists in the catalog
        assert len(report.dropped_credits_too_high) > 0

    def test_filter_report_counts_match(self):
        prefs = StudentPreferences(declared_major="CS")
        completed = frozenset({"CS 1110"})
        filt = CandidateFilter(
            self.courses, self.sections, completed, prefs
        )
        kept, report = filt.filter(self.all_codes)
        total = len(report.kept) + report.total_dropped
        # Some courses may be silently dropped (not in catalog), but
        # for codes drawn from the catalog itself the accounting is exact.
        assert total == len(self.all_codes)

    def test_empty_preferences_keeps_most_candidates(self):
        prefs = StudentPreferences()
        filt = CandidateFilter(
            self.courses, self.sections, frozenset(), prefs
        )
        kept, report = filt.filter(self.all_codes)
        assert len(kept) > len(self.all_codes) * 0.5


class TestScheduleCreditWindow:
    def test_inside_window(self):
        prefs = StudentPreferences(
            min_credits=12, max_credits=15, credit_tolerance=2
        )
        assert schedule_credits_in_window(12, prefs)
        assert schedule_credits_in_window(15, prefs)
        assert schedule_credits_in_window(10, prefs)  # 12 - 2
        assert schedule_credits_in_window(17, prefs)  # 15 + 2

    def test_outside_window(self):
        prefs = StudentPreferences(
            min_credits=12, max_credits=15, credit_tolerance=2
        )
        assert not schedule_credits_in_window(9, prefs)
        assert not schedule_credits_in_window(18, prefs)

    def test_zero_tolerance(self):
        prefs = StudentPreferences(
            min_credits=12, max_credits=15, credit_tolerance=0
        )
        assert schedule_credits_in_window(12, prefs)
        assert schedule_credits_in_window(15, prefs)
        assert not schedule_credits_in_window(11, prefs)
        assert not schedule_credits_in_window(16, prefs)
