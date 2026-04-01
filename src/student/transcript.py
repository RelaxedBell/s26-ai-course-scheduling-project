"""Student transcript model and validation."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.data.course_loader import Course


@dataclass(frozen=True, slots=True)
class Transcript:
    """A student's academic record of completed courses."""

    completed_courses: frozenset[str]
    grades: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_list(
        cls, courses: list[str], grades: dict[str, str] | None = None
    ) -> Transcript:
        return cls(
            completed_courses=frozenset(courses),
            grades=grades or {},
        )

    def credits_completed(self, course_catalog: dict[str, Course]) -> int:
        """Calculate total credits completed based on the course catalog."""
        total = 0
        for code in self.completed_courses:
            course = course_catalog.get(code)
            if course is not None:
                total += course.credits
        return total

    def has_completed(self, course_code: str) -> bool:
        return course_code in self.completed_courses

    def validate_against_catalog(
        self, course_catalog: dict[str, Course]
    ) -> list[str]:
        """Return list of course codes not found in the catalog."""
        return [
            code
            for code in self.completed_courses
            if code not in course_catalog
        ]
