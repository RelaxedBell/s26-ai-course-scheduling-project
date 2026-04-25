"""CSP-based schedule generation with hard and soft constraints.

Uses backtracking search with MRV heuristic and forward checking
to generate valid semester schedules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.data.course_graph import CourseGraph
from src.data.section_data import CourseSection, sections_by_course
from src.student.preferences import StudentPreferences, TimeBlock


@dataclass(frozen=True)
class Schedule:
    """A complete semester schedule."""

    sections: tuple[CourseSection, ...]
    score: float = 0.0

    @property
    def course_codes(self) -> list[str]:
        return [s.course_code for s in self.sections]

    @property
    def total_credits(self) -> int:
        # Deduplicate by course code in case of labs
        seen: dict[str, int] = {}
        for s in self.sections:
            if s.course_code not in seen:
                # Credits come from the section's course; approximate from code
                seen[s.course_code] = 1
        return len(seen)  # Will be replaced with actual credit lookup


def _section_conflicts_with_block(
    section: CourseSection, block: TimeBlock
) -> bool:
    """Check if a section overlaps with an unavailable time block."""
    shared_days = set(section.days) & set(block.days)
    if not shared_days:
        return False
    from src.data.section_data import _times_overlap
    return _times_overlap(
        section.start_time, section.end_time,
        block.start_time, block.end_time,
    )


def _sections_conflict(a: CourseSection, b: CourseSection) -> bool:
    """Check if two sections have a time conflict."""
    return a.conflicts_with(b)


class ScheduleGenerator:
    """Generate valid schedules using CSP with backtracking."""

    def __init__(
        self,
        course_graph: CourseGraph,
        all_sections: list[CourseSection],
        completed: frozenset[str],
        preferences: StudentPreferences,
        course_scores: dict[str, float] | None = None,
        credit_lookup: dict[str, int] | None = None,
    ):
        self._graph = course_graph
        self._sections_by_course = sections_by_course(all_sections)
        self._completed = completed
        self._preferences = preferences
        self._scores = course_scores or {}
        self._credit_lookup = credit_lookup or {}

    def generate(
        self,
        candidate_codes: list[str] | None = None,
        max_schedules: int = 10,
        max_courses: int = 6,
        min_courses: int = 3,
    ) -> list[Schedule]:
        """Generate up to max_schedules valid schedules.

        Args:
            candidate_codes: Course codes to consider. If None, uses all
                available courses based on prerequisites.
            max_schedules: Maximum number of schedules to return.
            max_courses: Maximum courses per schedule.
            min_courses: Minimum courses per schedule.
        """
        if candidate_codes is None:
            candidate_codes = list(
                self._graph.courses_available_after(self._completed)
            )

        # Filter to courses with available sections
        candidate_codes = [
            c for c in candidate_codes
            if c in self._sections_by_course
        ]

        # Sort by Bayes Net score (highest first) for better search ordering
        candidate_codes.sort(
            key=lambda c: self._scores.get(c, 0.5), reverse=True
        )

        # Limit candidates to top N for performance
        candidate_codes = candidate_codes[:20]

        schedules: list[Schedule] = []
        # Run multiple search attempts with randomization for diversity
        attempts = max_schedules * 5
        for _ in range(attempts):
            if len(schedules) >= max_schedules:
                break
            result = self._backtrack_search(
                candidate_codes, max_courses, min_courses, randomize=True
            )
            if result is not None and not self._is_duplicate(result, schedules):
                score = self._score_schedule(result)
                schedules.append(Schedule(
                    sections=tuple(result),
                    score=score,
                ))

        # Sort by score descending
        schedules.sort(key=lambda s: s.score, reverse=True)
        return schedules[:max_schedules]

    def _backtrack_search(
        self,
        candidates: list[str],
        max_courses: int,
        min_courses: int,
        randomize: bool = False,
    ) -> list[CourseSection] | None:
        """Backtracking search with forward checking."""
        assignment: list[CourseSection] = []
        remaining = list(candidates)
        if randomize:
            remaining = list(candidates)
            random.shuffle(remaining)

        return self._backtrack(
            assignment, remaining, max_courses, min_courses
        )

    def _credit_total(self, assignment: list[CourseSection]) -> int:
        seen: set[str] = set()
        total = 0
        for s in assignment:
            if s.course_code in seen:
                continue
            seen.add(s.course_code)
            total += self._credit_lookup.get(s.course_code, 3)
        return total

    def _assignment_in_window(self, assignment: list[CourseSection]) -> bool:
        total = self._credit_total(assignment)
        low = self._preferences.min_credits - self._preferences.credit_tolerance
        high = self._preferences.max_credits + self._preferences.credit_tolerance
        return low <= total <= high

    def _backtrack(
        self,
        assignment: list[CourseSection],
        remaining: list[str],
        max_courses: int,
        min_courses: int,
    ) -> list[CourseSection] | None:
        credit_ceiling = (
            self._preferences.max_credits + self._preferences.credit_tolerance
        )
        current_credits = self._credit_total(assignment)

        # If we have enough courses AND credits land in the window, accept.
        if (
            len(assignment) >= min_courses
            and self._assignment_in_window(assignment)
        ):
            if len(assignment) >= max_courses or not remaining:
                return list(assignment)
            # Current assignment is valid; keep exploring for a better fit
            # but fall back to this if deeper search fails.

        if not remaining:
            if (
                len(assignment) >= min_courses
                and self._assignment_in_window(assignment)
            ):
                return list(assignment)
            return None

        # MRV heuristic: pick the course with fewest valid sections
        best_idx = self._mrv_select(remaining, assignment)
        if best_idx is None:
            if (
                len(assignment) >= min_courses
                and self._assignment_in_window(assignment)
            ):
                return list(assignment)
            return None

        course_code = remaining[best_idx]
        new_remaining = remaining[:best_idx] + remaining[best_idx + 1:]

        # Skip this course if adding it would exceed the credit ceiling.
        course_credits = self._credit_lookup.get(course_code, 3)
        can_add = current_credits + course_credits <= credit_ceiling

        sections = list(self._sections_by_course.get(course_code, []))
        random.shuffle(sections)

        if can_add:
            for section in sections:
                if self._is_consistent(section, assignment):
                    assignment.append(section)
                    result = self._backtrack(
                        assignment, new_remaining, max_courses, min_courses
                    )
                    if result is not None:
                        return result
                    assignment.pop()

        # Try skipping this course entirely
        result = self._backtrack(
            assignment, new_remaining, max_courses, min_courses
        )
        if result is not None:
            return result

        if (
            len(assignment) >= min_courses
            and self._assignment_in_window(assignment)
        ):
            return list(assignment)
        return None

    def _mrv_select(
        self,
        remaining: list[str],
        assignment: list[CourseSection],
    ) -> int | None:
        """Select the variable (course) with minimum remaining values."""
        best_idx = None
        best_count = float("inf")

        for i, code in enumerate(remaining):
            sections = self._sections_by_course.get(code, [])
            valid = sum(
                1 for s in sections if self._is_consistent(s, assignment)
            )
            if valid == 0:
                continue
            if valid < best_count:
                best_count = valid
                best_idx = i

        return best_idx

    def _is_consistent(
        self, section: CourseSection, assignment: list[CourseSection]
    ) -> bool:
        """Check all hard constraints for adding this section."""
        # No duplicate courses
        for existing in assignment:
            if existing.course_code == section.course_code:
                return False

        # No time conflicts
        for existing in assignment:
            if _sections_conflict(section, existing):
                return False

        # Check unavailable time blocks
        for block in self._preferences.time_blocks_unavailable:
            if _section_conflicts_with_block(section, block):
                return False

        return True

    def _score_schedule(self, sections: list[CourseSection]) -> float:
        """Score a schedule based on Bayes Net scores and soft constraints."""
        if not sections:
            return 0.0

        score = 0.0

        # Bayes Net score component (weighted heavily)
        bayes_scores = [
            self._scores.get(s.course_code, 0.5) for s in sections
        ]
        score += 0.6 * (sum(bayes_scores) / len(bayes_scores))

        # Credit count alignment
        total_credits = sum(
            self._credit_lookup.get(s.course_code, 3) for s in sections
        )
        target = (self._preferences.min_credits + self._preferences.max_credits) / 2
        credit_diff = abs(total_credits - target)
        score += 0.2 * max(0, 1.0 - credit_diff / 6.0)

        # Time preference bonus
        if self._preferences.prefer_morning is not None:
            morning_count = sum(
                1 for s in sections
                if int(s.start_time.split(":")[0]) < 12
            )
            morning_ratio = morning_count / len(sections)
            if self._preferences.prefer_morning:
                score += 0.1 * morning_ratio
            else:
                score += 0.1 * (1.0 - morning_ratio)
        else:
            score += 0.05

        # Compactness bonus: fewer gaps between classes
        score += 0.1 * self._compactness_score(sections)

        return score

    def _compactness_score(self, sections: list[CourseSection]) -> float:
        """Score how compact the schedule is (fewer gaps = better)."""
        if len(sections) <= 1:
            return 1.0

        from src.data.section_data import _parse_time

        # Group by day and check gaps
        by_day: dict[str, list[tuple[int, int]]] = {}
        for s in sections:
            for day in s.days:
                by_day.setdefault(day, []).append(
                    (_parse_time(s.start_time), _parse_time(s.end_time))
                )

        total_gap = 0
        total_days = 0
        for times in by_day.values():
            if len(times) < 2:
                continue
            times.sort()
            for i in range(len(times) - 1):
                gap = times[i + 1][0] - times[i][1]
                total_gap += max(0, gap)
            total_days += 1

        if total_days == 0:
            return 1.0

        avg_gap = total_gap / total_days
        # Normalize: 0 gap = 1.0, 180+ min gap = 0.0
        return max(0.0, 1.0 - avg_gap / 180.0)

    def _is_duplicate(
        self, sections: list[CourseSection], existing: list[Schedule]
    ) -> bool:
        """Check if a schedule has the same course set as an existing one."""
        new_codes = frozenset(s.course_code for s in sections)
        return any(
            frozenset(s.course_code for s in sched.sections) == new_codes
            for sched in existing
        )
