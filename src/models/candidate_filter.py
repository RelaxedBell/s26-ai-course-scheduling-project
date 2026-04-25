"""Pre-CSP candidate filter.

Eliminates courses that cannot appear in any valid schedule so the
Bayes Net scorer and CSP solver don't waste work on them. Runs
strictly before scoring.

Filters applied (see Group Project/Notes.md):
    1. Already-completed courses
    2. Major eligibility for required/prerequisite courses
    3. Elective topic / department preferences
    4. Time-block conflicts (drop if every section conflicts)
    5. Per-course credit ceiling (credits > max_credits + tolerance)
"""

from __future__ import annotations

from dataclasses import dataclass

from src.data.course_loader import Course, CourseType
from src.data.section_data import CourseSection, sections_by_course
from src.student.preferences import StudentPreferences, TimeBlock


# Departments that count toward each declared major. A student in CS
# may only count CS-prefix courses toward major requirements; other
# majors can be added here as the catalog grows.
MAJOR_DEPARTMENTS: dict[str, frozenset[str]] = {
    "CS": frozenset({"CS"}),
    "CPE": frozenset({"CS", "ECE"}),
    "DS": frozenset({"CS", "DS"}),
}


@dataclass(frozen=True)
class FilterReport:
    """Diagnostic record of which courses were kept or dropped and why."""

    kept: tuple[str, ...]
    dropped_already_taken: tuple[str, ...] = ()
    dropped_major_ineligible: tuple[str, ...] = ()
    dropped_time_conflict: tuple[str, ...] = ()
    dropped_elective_mismatch: tuple[str, ...] = ()
    dropped_credits_too_high: tuple[str, ...] = ()

    @property
    def total_dropped(self) -> int:
        return (
            len(self.dropped_already_taken)
            + len(self.dropped_major_ineligible)
            + len(self.dropped_time_conflict)
            + len(self.dropped_elective_mismatch)
            + len(self.dropped_credits_too_high)
        )


def department_of(code: str) -> str:
    """Return the department prefix of a course code ('CS 4710' -> 'CS')."""
    return code.split()[0] if " " in code else code


def _course_matches_topics(course: Course, topics: list[str]) -> bool:
    if not topics:
        return False
    haystack = f"{course.name} {course.description}".lower()
    return any(t.lower() in haystack for t in topics)


def _is_major_eligible(code: str, major: str | None) -> bool:
    if not major:
        return True
    allowed = MAJOR_DEPARTMENTS.get(major.upper())
    if allowed is None:
        return True
    return department_of(code) in allowed


def _section_conflicts_with_block(
    section: CourseSection, block: TimeBlock
) -> bool:
    shared_days = set(section.days) & set(block.days)
    if not shared_days:
        return False
    from src.data.section_data import _times_overlap
    return _times_overlap(
        section.start_time, section.end_time,
        block.start_time, block.end_time,
    )


def _has_viable_section(
    sections: list[CourseSection], blocks: list[TimeBlock]
) -> bool:
    """True if at least one section avoids every unavailable block."""
    if not blocks:
        return True
    for section in sections:
        if not any(_section_conflicts_with_block(section, b) for b in blocks):
            return True
    return False


class CandidateFilter:
    """Shrinks a course candidate list before Bayes scoring and CSP search."""

    def __init__(
        self,
        courses: dict[str, Course],
        sections: list[CourseSection],
        completed: frozenset[str],
        preferences: StudentPreferences,
    ):
        self._courses = courses
        self._sections_by_course = sections_by_course(sections)
        self._completed = completed
        self._prefs = preferences

    def filter(
        self, candidate_codes: list[str]
    ) -> tuple[list[str], FilterReport]:
        kept: list[str] = []
        already_taken: list[str] = []
        major_ineligible: list[str] = []
        time_conflict: list[str] = []
        elective_mismatch: list[str] = []
        too_heavy: list[str] = []

        credit_ceiling = self._prefs.max_credits + self._prefs.credit_tolerance

        for code in candidate_codes:
            if code in self._completed:
                already_taken.append(code)
                continue

            course = self._courses.get(code)
            if course is None:
                continue

            if course.credits > credit_ceiling:
                too_heavy.append(code)
                continue

            is_elective = course.course_type in (
                CourseType.RESTRICTED_ELECTIVE,
                CourseType.INTEGRATION_ELECTIVE,
            )

            if is_elective:
                if not self._elective_matches(course):
                    elective_mismatch.append(code)
                    continue
            else:
                if not _is_major_eligible(code, self._prefs.declared_major):
                    major_ineligible.append(code)
                    continue

            course_sections = self._sections_by_course.get(code, [])
            if course_sections and not _has_viable_section(
                course_sections, self._prefs.time_blocks_unavailable
            ):
                time_conflict.append(code)
                continue

            kept.append(code)

        report = FilterReport(
            kept=tuple(kept),
            dropped_already_taken=tuple(already_taken),
            dropped_major_ineligible=tuple(major_ineligible),
            dropped_time_conflict=tuple(time_conflict),
            dropped_elective_mismatch=tuple(elective_mismatch),
            dropped_credits_too_high=tuple(too_heavy),
        )
        return kept, report

    def _elective_matches(self, course: Course) -> bool:
        topics = self._prefs.preferred_topics
        depts = {d.upper() for d in self._prefs.preferred_departments}

        if not topics and not depts:
            return True

        dept_match = department_of(course.code) in depts if depts else False
        topic_match = (
            _course_matches_topics(course, topics) if topics else False
        )
        return dept_match or topic_match


def schedule_credits_in_window(
    total_credits: int, preferences: StudentPreferences
) -> bool:
    """Check whether a schedule's total credits fall in the tolerance window."""
    low = preferences.min_credits - preferences.credit_tolerance
    high = preferences.max_credits + preferences.credit_tolerance
    return low <= total_credits <= high
