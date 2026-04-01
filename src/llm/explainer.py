"""Generate natural language explanations for recommended schedules."""

from __future__ import annotations

import logging

from src.data.course_loader import Course
from src.llm.llm_client import LLMClient
from src.models.constraint_solver import Schedule
from src.student.preferences import StudentPreferences

logger = logging.getLogger(__name__)

EXPLAIN_SYSTEM_PROMPT = """You are a course scheduling advisor at UVA. Explain why a
recommended schedule is a good fit for the student. Be specific about:
1. How each course matches their preferences
2. How the schedule respects their constraints
3. How it progresses them toward graduation

Keep your explanation concise (2-4 paragraphs). Use a helpful, conversational tone."""


def explain_schedule(
    schedule: Schedule,
    preferences: StudentPreferences,
    courses: dict[str, Course],
    bayes_scores: dict[str, float],
    client: LLMClient,
) -> str:
    """Generate a natural language explanation of why a schedule was recommended."""
    # Build context for the LLM
    course_details = []
    for section in schedule.sections:
        course = courses.get(section.course_code)
        score = bayes_scores.get(section.course_code, 0.5)
        if course:
            course_details.append(
                f"- {section.course_code}: {course.name} "
                f"(affinity score: {score:.2f}, {section.days} "
                f"{section.start_time}-{section.end_time}, "
                f"instructor: {section.instructor})"
            )

    pref_summary = _summarize_preferences(preferences)
    courses_text = "\n".join(course_details)

    prompt = f"""Student preferences:
{pref_summary}

Recommended schedule (score: {schedule.score:.2f}):
{courses_text}

Explain why this schedule is a good fit for this student."""

    try:
        return client.generate(
            prompt=prompt,
            system_prompt=EXPLAIN_SYSTEM_PROMPT,
            max_tokens=512,
        )
    except Exception as e:
        logger.warning("Schedule explanation failed: %s", e)
        return _fallback_explanation(schedule, preferences, courses, bayes_scores)


def _summarize_preferences(prefs: StudentPreferences) -> str:
    parts = []
    diff_map = {1: "easy", 2: "moderate-easy", 3: "moderate", 4: "challenging", 5: "very challenging"}
    parts.append(f"- Difficulty: {diff_map.get(prefs.difficulty_preference, 'moderate')}")
    parts.append(f"- Credits: {prefs.min_credits}-{prefs.max_credits}")
    if prefs.preferred_topics:
        parts.append(f"- Interested in: {', '.join(prefs.preferred_topics)}")
    if prefs.prefer_morning is not None:
        parts.append(f"- Prefers {'morning' if prefs.prefer_morning else 'afternoon'} classes")
    if prefs.time_blocks_unavailable:
        parts.append(f"- Has {len(prefs.time_blocks_unavailable)} unavailable time block(s)")
    return "\n".join(parts)


def _fallback_explanation(
    schedule: Schedule,
    preferences: StudentPreferences,
    courses: dict[str, Course],
    bayes_scores: dict[str, float],
) -> str:
    """Template-based fallback explanation when LLM is unavailable."""
    lines = [
        "This schedule was selected based on your preferences:\n"
    ]

    for section in schedule.sections:
        course = courses.get(section.course_code)
        score = bayes_scores.get(section.course_code, 0.5)
        name = course.name if course else "Unknown"
        reason = "matches your interests" if score > 0.6 else "fulfills degree requirements"
        lines.append(
            f"- **{section.course_code}** ({name}): {reason} "
            f"(affinity: {score:.0%})"
        )

    if preferences.preferred_topics:
        lines.append(
            f"\nYour interest in {', '.join(preferences.preferred_topics)} "
            f"was prioritized in course selection."
        )

    lines.append(
        "\nAll courses have satisfied prerequisite requirements and there "
        "are no time conflicts in this schedule."
    )

    return "\n".join(lines)
