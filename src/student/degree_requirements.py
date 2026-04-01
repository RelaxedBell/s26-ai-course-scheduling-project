"""UVA BSCS degree requirement checking."""

from __future__ import annotations

from dataclasses import dataclass

from src.data.course_loader import Course, CourseType


@dataclass(frozen=True, slots=True)
class RequirementConfig:
    """Configurable degree requirement thresholds."""

    required_prerequisite_courses: int = 5  # CS 1110-1113 (one of), CS 2100
    required_core_courses: int = 6          # CS 2120, 2130, 3100, 3120, 3130, 3140
    min_restricted_elective_credits: int = 12  # ~4 courses
    min_integration_elective_credits: int = 9  # ~3 courses


@dataclass(frozen=True, slots=True)
class RequirementStatus:
    """Status of each degree requirement category."""

    remaining_prerequisites: list[str]
    remaining_required: list[str]
    restricted_elective_credits_needed: int
    integration_elective_credits_needed: int
    completed_restricted_electives: list[str]
    completed_integration_electives: list[str]

    @property
    def total_remaining(self) -> int:
        return (
            len(self.remaining_prerequisites)
            + len(self.remaining_required)
            + max(0, self.restricted_elective_credits_needed)
            + max(0, self.integration_elective_credits_needed)
        )

    @property
    def is_complete(self) -> bool:
        return (
            len(self.remaining_prerequisites) == 0
            and len(self.remaining_required) == 0
            and self.restricted_elective_credits_needed <= 0
            and self.integration_elective_credits_needed <= 0
        )


def compute_remaining_requirements(
    completed: frozenset[str],
    course_catalog: dict[str, Course],
    config: RequirementConfig = RequirementConfig(),
) -> RequirementStatus:
    """Compute what a student still needs for the BSCS degree."""
    remaining_prereqs = []
    remaining_required = []
    restricted_credits_earned = 0
    integration_credits_earned = 0
    completed_restricted = []
    completed_integration = []

    for code, course in course_catalog.items():
        if course.course_type == CourseType.PREREQUISITE:
            if code not in completed:
                remaining_prereqs.append(code)
        elif course.course_type == CourseType.REQUIRED:
            if code not in completed:
                remaining_required.append(code)
        elif course.course_type == CourseType.RESTRICTED_ELECTIVE:
            if code in completed:
                restricted_credits_earned += course.credits
                completed_restricted.append(code)
        elif course.course_type == CourseType.INTEGRATION_ELECTIVE:
            if code in completed:
                integration_credits_earned += course.credits
                completed_integration.append(code)

    return RequirementStatus(
        remaining_prerequisites=remaining_prereqs,
        remaining_required=remaining_required,
        restricted_elective_credits_needed=(
            config.min_restricted_elective_credits - restricted_credits_earned
        ),
        integration_elective_credits_needed=(
            config.min_integration_elective_credits - integration_credits_earned
        ),
        completed_restricted_electives=completed_restricted,
        completed_integration_electives=completed_integration,
    )
