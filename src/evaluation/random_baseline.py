"""Generate random valid schedules as a baseline for comparison."""

from __future__ import annotations

import random

from src.data.course_graph import CourseGraph
from src.data.section_data import CourseSection, sections_by_course
from src.models.constraint_solver import Schedule


def generate_random_schedule(
    course_graph: CourseGraph,
    all_sections: list[CourseSection],
    completed: frozenset[str],
    min_courses: int = 3,
    max_courses: int = 6,
) -> Schedule | None:
    """Generate a random valid schedule (hard constraints only, no preference scoring).

    Only satisfies: no time conflicts, prerequisites met, no duplicates.
    """
    available = list(course_graph.courses_available_after(completed))
    grouped = sections_by_course(all_sections)
    available = [c for c in available if c in grouped]

    if not available:
        return None

    random.shuffle(available)
    target = random.randint(min_courses, max_courses)

    selected: list[CourseSection] = []
    for code in available:
        if len(selected) >= target:
            break

        sections = list(grouped.get(code, []))
        random.shuffle(sections)

        for section in sections:
            conflict = any(
                section.conflicts_with(existing) for existing in selected
            )
            duplicate = any(
                s.course_code == section.course_code for s in selected
            )
            if not conflict and not duplicate:
                selected.append(section)
                break

    if len(selected) < min_courses:
        return None

    return Schedule(sections=tuple(selected), score=0.0)


def generate_random_schedules(
    course_graph: CourseGraph,
    all_sections: list[CourseSection],
    completed: frozenset[str],
    n: int = 10,
) -> list[Schedule]:
    """Generate n random valid schedules."""
    schedules = []
    attempts = n * 5
    for _ in range(attempts):
        if len(schedules) >= n:
            break
        sched = generate_random_schedule(
            course_graph, all_sections, completed
        )
        if sched is not None:
            schedules.append(sched)
    return schedules
