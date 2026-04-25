"""Generate natural language explanations for recommended schedules."""

from __future__ import annotations

import logging

from src.data.course_loader import Course, CourseType
from src.data.review_data import CourseSummary
from src.llm.llm_client import LLMClient, TemplateLLMClient
from src.models.constraint_solver import Schedule
from src.student.degree_requirements import compute_remaining_requirements
from src.student.preferences import StudentPreferences

logger = logging.getLogger(__name__)

STYLE_REWRITE_SYSTEM_PROMPT = """You are a warm, concise academic advisor.
Rewrite the grounded explanation into natural language a student would enjoy reading.

Rules:
- Preserve all concrete facts and course-level reasons from the source.
- Do not invent courses, requirements, or constraints.
- Keep it specific to this schedule, not generic.
- Mention each selected course at least once.
- Tone: confident, helpful, and personalized.
- Length: 2-4 short paragraphs or a brief intro plus bullet list."""


def explain_schedule(
    schedule: Schedule,
    preferences: StudentPreferences,
    courses: dict[str, Course],
    bayes_scores: dict[str, float],
    client: LLMClient,
    summaries: dict[str, CourseSummary] | None = None,
    completed_courses: frozenset[str] | None = None,
) -> str:
    """Generate a natural language explanation of why a schedule was recommended."""
    grounded_explanation = _fallback_explanation(
        schedule,
        preferences,
        courses,
        bayes_scores,
        summaries,
        completed_courses,
    )

    # Template backend cannot add style diversity, so return grounded text.
    if isinstance(client, TemplateLLMClient):
        return grounded_explanation

    try:
        llm_response = client.generate(
            prompt=(
                "Use the grounded explanation below as source of truth.\n\n"
                f"{grounded_explanation}\n\n"
                "Rewrite this for a student-facing explanation."
            ),
            system_prompt=STYLE_REWRITE_SYSTEM_PROMPT,
            max_tokens=512,
            temperature=0.85,
        )
        # If model response is unexpectedly vague, fall back to deterministic
        # explanation that references concrete course-level reasons.
        if not any(sec.course_code in llm_response for sec in schedule.sections):
            return grounded_explanation
        return llm_response
    except Exception as e:
        logger.warning("Schedule explanation failed: %s", e)
        return grounded_explanation


def _fallback_explanation(
    schedule: Schedule,
    preferences: StudentPreferences,
    courses: dict[str, Course],
    bayes_scores: dict[str, float],
    summaries: dict[str, CourseSummary] | None = None,
    completed_courses: frozenset[str] | None = None,
) -> str:
    """Generate a concrete, course-by-course explanation without an LLM."""
    completed = completed_courses or frozenset()
    before = compute_remaining_requirements(completed, courses)
    after = compute_remaining_requirements(
        completed | frozenset(s.course_code for s in schedule.sections), courses
    )

    total_credits = sum(
        courses.get(section.course_code, Course(
            code=section.course_code,
            name="Unknown",
            description="",
            credits=3,
            course_type=CourseType.UNKNOWN,
            prerequisites_raw="",
            prerequisites_parsed=None,
        )).credits
        for section in schedule.sections
    )

    intro = [
        (
            f"This schedule is targeted to your {preferences.min_credits}-"
            f"{preferences.max_credits} credit preference and includes "
            f"{total_credits} credits."
        ),
        (
            "Each class below was chosen for a specific reason tied to your degree "
            "progress and preference fit:"
        ),
        "",
    ]

    lines = list(intro)
    for section in schedule.sections:
        course = courses.get(section.course_code)
        if course is None:
            lines.append(
                f"- {section.course_code}: included as an available option that fits the "
                "schedule constraints."
            )
            continue

        score = bayes_scores.get(section.course_code, 0.5)
        summary = summaries.get(section.course_code) if summaries else None
        reasons = _course_reasons(course, score, preferences, before, summary)
        lines.append(
            f"- {course.code} ({course.name}): "
            f"{'; '.join(reasons)} (affinity score {score:.0%})."
        )

    progress_bits = []
    if before.remaining_required and len(after.remaining_required) < len(before.remaining_required):
        progress_bits.append(
            f"required courses remaining dropped from {len(before.remaining_required)} "
            f"to {len(after.remaining_required)}"
        )
    if after.restricted_elective_credits_needed < before.restricted_elective_credits_needed:
        progress_bits.append(
            "restricted elective credits needed decreased from "
            f"{max(0, before.restricted_elective_credits_needed)} to "
            f"{max(0, after.restricted_elective_credits_needed)}"
        )
    if after.integration_elective_credits_needed < before.integration_elective_credits_needed:
        progress_bits.append(
            "integration elective credits needed decreased from "
            f"{max(0, before.integration_elective_credits_needed)} to "
            f"{max(0, after.integration_elective_credits_needed)}"
        )

    if progress_bits:
        lines.append("")
        lines.append("Overall degree progress with this schedule:")
        lines.extend([f"- {bit}." for bit in progress_bits])

    lines.append("")
    lines.append(
        "All selected sections satisfy prerequisite and conflict constraints."
    )
    return "\n".join(lines)


def _course_reasons(
    course: Course,
    affinity_score: float,
    preferences: StudentPreferences,
    before_reqs,
    summary: CourseSummary | None = None,
) -> list[str]:
    reasons: list[str] = []

    if course.code in before_reqs.remaining_required:
        reasons.append("it fulfills a remaining required core course")
    elif course.code in before_reqs.remaining_prerequisites:
        reasons.append("it fulfills a remaining prerequisite")

    if (
        course.course_type == CourseType.RESTRICTED_ELECTIVE
        and before_reqs.restricted_elective_credits_needed > 0
    ):
        reasons.append("it contributes restricted elective credit toward graduation")
    if (
        course.course_type == CourseType.INTEGRATION_ELECTIVE
        and before_reqs.integration_elective_credits_needed > 0
    ):
        reasons.append("it contributes integration elective credit toward graduation")

    if preferences.preferred_topics:
        haystack = f"{course.name} {course.description}".lower()
        matched_topics = [
            topic for topic in preferences.preferred_topics
            if topic.lower() in haystack
        ]
        if matched_topics:
            reasons.append(
                f"it matches your topic interests ({', '.join(matched_topics[:2])})"
            )

    if preferences.difficulty_preference <= 2 and affinity_score >= 0.6:
        reasons.append("it aligns with your easier-semester preference")
    elif preferences.difficulty_preference >= 4 and affinity_score >= 0.6:
        reasons.append("it aligns with your challenging-semester preference")
    elif affinity_score >= 0.7:
        reasons.append("it has a strong predicted fit based on your profile")

    if not reasons:
        reasons.append("it improves your overall schedule fit and degree progress")

    if summary is not None and summary.review_count > 0:
        reasons.extend(_review_driven_reasons(summary, preferences))

    return reasons


def _review_driven_reasons(
    summary: CourseSummary,
    preferences: StudentPreferences,
) -> list[str]:
    """Translate aggregate review stats into like/dislike-style reasons."""
    reasons: list[str] = []

    if summary.avg_instructor_rating >= 4.2:
        reasons.append(
            f"students often praise teaching quality "
            f"({summary.avg_instructor_rating:.1f}/5 instructor rating across "
            f"{summary.review_count} reviews)"
        )
    elif summary.avg_instructor_rating <= 2.8:
        reasons.append(
            f"possible downside: instructor experience is mixed "
            f"({summary.avg_instructor_rating:.1f}/5)"
        )

    if summary.avg_enjoyment >= 4.0:
        reasons.append(
            f"students generally enjoy the class ({summary.avg_enjoyment:.1f}/5 enjoyment)"
        )
    elif summary.avg_enjoyment <= 2.8:
        reasons.append(
            f"possible downside: past students report lower enjoyment "
            f"({summary.avg_enjoyment:.1f}/5)"
        )

    if summary.avg_workload >= 10:
        reasons.append(
            f"possible downside: workload is heavier (~{summary.avg_workload:.1f} hours/week outside class)"
        )
    elif summary.avg_workload <= 5:
        reasons.append(
            f"outside-of-class workload is relatively light (~{summary.avg_workload:.1f} hours/week)"
        )

    if preferences.difficulty_preference <= 2 and summary.avg_difficulty <= 2.8:
        reasons.append(
            f"difficulty aligns with your lighter-semester goal ({summary.avg_difficulty:.1f}/5)"
        )
    elif preferences.difficulty_preference <= 2 and summary.avg_difficulty >= 4.0:
        reasons.append(
            f"possible downside for your preferences: difficulty trends high ({summary.avg_difficulty:.1f}/5)"
        )
    elif preferences.difficulty_preference >= 4 and summary.avg_difficulty >= 3.8:
        reasons.append(
            f"difficulty aligns with your challenging-semester goal ({summary.avg_difficulty:.1f}/5)"
        )

    return reasons
