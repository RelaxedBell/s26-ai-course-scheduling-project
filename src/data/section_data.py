"""Course section schedule data schema and loading."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CourseSection(BaseModel):
    """A specific section of a course with time/instructor info."""

    course_code: str
    section_id: str
    instructor: str = ""
    days: list[str] = Field(
        description="Days of week, e.g. ['M', 'W', 'F']"
    )
    start_time: str = Field(description="e.g. '09:00'")
    end_time: str = Field(description="e.g. '09:50'")
    location: str = ""
    semester: str = ""
    enrollment_cap: int = 0
    enrollment_current: int = 0

    def conflicts_with(self, other: CourseSection) -> bool:
        """Check if two sections have overlapping times on shared days."""
        shared_days = set(self.days) & set(other.days)
        if not shared_days:
            return False
        return _times_overlap(
            self.start_time, self.end_time,
            other.start_time, other.end_time,
        )


def _times_overlap(
    start1: str, end1: str, start2: str, end2: str
) -> bool:
    """Check if two time ranges overlap."""
    s1 = _parse_time(start1)
    e1 = _parse_time(end1)
    s2 = _parse_time(start2)
    e2 = _parse_time(end2)
    return s1 < e2 and s2 < e1


def _parse_time(t: str) -> int:
    """Parse 'HH:MM' to minutes since midnight."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def load_sections(path: str | Path) -> list[CourseSection]:
    """Load course sections from a JSON file."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    return [CourseSection(**s) for s in raw]


def sections_by_course(
    sections: list[CourseSection],
) -> dict[str, list[CourseSection]]:
    """Group sections by course code."""
    grouped: dict[str, list[CourseSection]] = {}
    for section in sections:
        grouped.setdefault(section.course_code, []).append(section)
    return grouped
