"""Course review data schema and loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field


class CourseReview(BaseModel):
    """A single course review."""

    course_code: str
    instructor: str = ""
    semester: str = ""
    difficulty_rating: float = Field(ge=1.0, le=5.0)
    instructor_rating: float = Field(ge=1.0, le=5.0)
    enjoyment_rating: float = Field(ge=1.0, le=5.0)
    workload_hours: float = Field(ge=0.0, default=5.0)
    review_text: str = ""


@dataclass(frozen=True, slots=True)
class CourseSummary:
    """Aggregated review statistics for a course."""

    course_code: str
    avg_difficulty: float
    avg_instructor_rating: float
    avg_enjoyment: float
    avg_workload: float
    review_count: int


def load_reviews(path: str | Path) -> list[CourseReview]:
    """Load reviews from a JSON file."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [CourseReview(**r) for r in raw]


def get_course_summary(
    reviews: list[CourseReview], course_code: str
) -> CourseSummary | None:
    """Compute average ratings for a specific course."""
    matching = [r for r in reviews if r.course_code == course_code]
    if not matching:
        return None
    n = len(matching)
    return CourseSummary(
        course_code=course_code,
        avg_difficulty=sum(r.difficulty_rating for r in matching) / n,
        avg_instructor_rating=sum(r.instructor_rating for r in matching) / n,
        avg_enjoyment=sum(r.enjoyment_rating for r in matching) / n,
        avg_workload=sum(r.workload_hours for r in matching) / n,
        review_count=n,
    )


def get_all_summaries(
    reviews: list[CourseReview],
) -> dict[str, CourseSummary]:
    """Compute summaries for all courses with reviews."""
    codes = {r.course_code for r in reviews}
    summaries = {}
    for code in codes:
        summary = get_course_summary(reviews, code)
        if summary is not None:
            summaries[code] = summary
    return summaries
