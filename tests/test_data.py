"""Tests for review data and section data loading."""

from pathlib import Path

from src.data.review_data import (
    CourseReview,
    get_all_summaries,
    get_course_summary,
    load_reviews,
)
from src.data.section_data import CourseSection, load_sections, sections_by_course

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REVIEWS_PATH = PROJECT_ROOT / "data" / "reviews" / "synthetic_reviews.json"
SECTIONS_PATH = PROJECT_ROOT / "data" / "sections" / "fall_2026_sections.json"


class TestReviewData:
    def test_load_reviews(self):
        reviews = load_reviews(REVIEWS_PATH)
        assert len(reviews) > 100

    def test_review_fields_valid(self):
        reviews = load_reviews(REVIEWS_PATH)
        for r in reviews[:10]:
            assert 1.0 <= r.difficulty_rating <= 5.0
            assert 1.0 <= r.instructor_rating <= 5.0
            assert 1.0 <= r.enjoyment_rating <= 5.0
            assert r.workload_hours >= 0

    def test_course_summary(self):
        reviews = load_reviews(REVIEWS_PATH)
        summary = get_course_summary(reviews, "CS 1110")
        assert summary is not None
        assert summary.review_count > 0
        assert 1.0 <= summary.avg_difficulty <= 5.0

    def test_missing_course_summary(self):
        reviews = load_reviews(REVIEWS_PATH)
        summary = get_course_summary(reviews, "FAKE 9999")
        assert summary is None

    def test_all_summaries(self):
        reviews = load_reviews(REVIEWS_PATH)
        summaries = get_all_summaries(reviews)
        assert len(summaries) > 50


class TestSectionData:
    def test_load_sections(self):
        sections = load_sections(SECTIONS_PATH)
        assert len(sections) > 50

    def test_section_fields(self):
        sections = load_sections(SECTIONS_PATH)
        for s in sections[:10]:
            assert len(s.days) > 0
            assert ":" in s.start_time
            assert ":" in s.end_time

    def test_sections_by_course(self):
        sections = load_sections(SECTIONS_PATH)
        grouped = sections_by_course(sections)
        assert "CS 1110" in grouped
        assert len(grouped["CS 1110"]) >= 1

    def test_conflict_detection(self):
        s1 = CourseSection(
            course_code="CS 1110", section_id="001",
            days=["M", "W", "F"], start_time="09:00", end_time="09:50",
        )
        s2 = CourseSection(
            course_code="CS 2100", section_id="001",
            days=["M", "W", "F"], start_time="09:30", end_time="10:20",
        )
        s3 = CourseSection(
            course_code="CS 2120", section_id="001",
            days=["T", "R"], start_time="09:30", end_time="10:45",
        )
        assert s1.conflicts_with(s2)
        assert not s1.conflicts_with(s3)

    def test_no_self_conflict_different_days(self):
        s1 = CourseSection(
            course_code="CS 1110", section_id="001",
            days=["M", "W", "F"], start_time="09:00", end_time="09:50",
        )
        s2 = CourseSection(
            course_code="CS 2100", section_id="001",
            days=["T", "R"], start_time="09:00", end_time="09:50",
        )
        assert not s1.conflicts_with(s2)
