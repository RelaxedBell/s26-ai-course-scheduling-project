"""Tests for transcript, degree requirements, and preferences."""

from pathlib import Path

from src.data.course_loader import load_courses
from src.student.degree_requirements import (
    RequirementConfig,
    compute_remaining_requirements,
)
from src.student.preferences import StudentPreferences, TimeBlock
from src.student.transcript import Transcript

COURSES_JSON = Path(__file__).resolve().parent.parent / "courses.json"


class TestTranscript:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)

    def test_from_list(self):
        t = Transcript.from_list(["CS 1110", "CS 2100"])
        assert t.has_completed("CS 1110")
        assert not t.has_completed("CS 3100")

    def test_credits_completed(self):
        t = Transcript.from_list(["CS 1110", "CS 2100"])
        credits = t.credits_completed(self.courses)
        assert credits == 3 + 4  # CS 1110=3, CS 2100=4

    def test_validate_against_catalog(self):
        t = Transcript.from_list(["CS 1110", "FAKE 9999"])
        unknown = t.validate_against_catalog(self.courses)
        assert "FAKE 9999" in unknown
        assert "CS 1110" not in unknown

    def test_empty_transcript(self):
        t = Transcript.from_list([])
        assert t.credits_completed(self.courses) == 0


class TestDegreeRequirements:
    def setup_method(self):
        self.courses = load_courses(COURSES_JSON)

    def test_no_courses_completed(self):
        status = compute_remaining_requirements(
            frozenset(), self.courses
        )
        assert len(status.remaining_prerequisites) > 0
        assert len(status.remaining_required) > 0
        assert not status.is_complete

    def test_some_courses_completed(self):
        completed = frozenset({"CS 1110", "CS 2100", "CS 2120", "CS 2130"})
        status = compute_remaining_requirements(completed, self.courses)
        assert "CS 1110" not in status.remaining_prerequisites
        assert "CS 2120" not in status.remaining_required

    def test_restricted_elective_credits(self):
        # Complete some restricted electives
        completed = frozenset({"CS 4710", "CS 4750"})
        status = compute_remaining_requirements(completed, self.courses)
        assert status.restricted_elective_credits_needed < 12

    def test_full_completion(self):
        # Complete everything
        all_prereqs = [
            c for c, co in self.courses.items()
            if co.course_type.value == "prerequisite"
        ]
        all_required = [
            c for c, co in self.courses.items()
            if co.course_type.value == "required course"
        ]
        # Get enough restricted and integration electives
        restricted = [
            c for c, co in self.courses.items()
            if co.course_type.value == "restricted elective"
        ][:5]
        integration = [
            c for c, co in self.courses.items()
            if co.course_type.value == "integration elective"
        ][:4]
        completed = frozenset(
            all_prereqs + all_required + restricted + integration
        )
        status = compute_remaining_requirements(completed, self.courses)
        assert status.is_complete


class TestPreferences:
    def test_default_preferences(self):
        prefs = StudentPreferences()
        assert prefs.difficulty_preference == 3
        assert prefs.max_credits == 15
        assert prefs.min_credits == 12

    def test_custom_preferences(self):
        prefs = StudentPreferences(
            difficulty_preference=1,
            max_credits=12,
            preferred_topics=["AI", "machine learning"],
            time_blocks_unavailable=[
                TimeBlock(days=["M", "W", "F"], start_time="08:00", end_time="10:00")
            ],
        )
        assert prefs.difficulty_preference == 1
        assert len(prefs.preferred_topics) == 2
        assert len(prefs.time_blocks_unavailable) == 1

    def test_validation_bounds(self):
        import pytest
        with pytest.raises(Exception):
            StudentPreferences(difficulty_preference=0)
        with pytest.raises(Exception):
            StudentPreferences(difficulty_preference=6)

    def test_json_roundtrip(self):
        prefs = StudentPreferences(
            difficulty_preference=2,
            preferred_topics=["AI"],
        )
        json_str = prefs.model_dump_json()
        restored = StudentPreferences.model_validate_json(json_str)
        assert restored.difficulty_preference == 2
        assert restored.preferred_topics == ["AI"]
