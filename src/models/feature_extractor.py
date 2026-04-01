"""Extract features from courses and student preferences for the Bayes Net."""

from __future__ import annotations

import re

import numpy as np

from src.data.course_loader import Course, CourseType
from src.data.review_data import CourseSummary
from src.student.preferences import StudentPreferences

# Topic keyword sets for matching against course descriptions
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "ai": ["artificial intelligence", "machine learning", "neural", "deep learning"],
    "nlp": ["natural language", "nlp", "text", "language model"],
    "vision": ["computer vision", "image", "visual"],
    "systems": ["operating system", "network", "distributed", "parallel", "cloud"],
    "security": ["security", "cryptograph", "privacy", "vulnerability", "cyber"],
    "theory": ["algorithm", "complexity", "automata", "formal", "proof", "theory"],
    "software": ["software engineering", "agile", "testing", "design pattern"],
    "data": ["database", "data science", "big data", "analytics", "data mining"],
    "graphics": ["graphics", "visualization", "rendering", "game"],
    "web": ["web", "internet", "http", "api", "full-stack"],
    "robotics": ["robot", "autonomous", "control system"],
    "hci": ["human-computer", "interaction", "user experience", "interface"],
}

ALL_TOPICS = sorted(TOPIC_KEYWORDS.keys())


def extract_topic_vector(description: str) -> dict[str, float]:
    """Extract binary topic presence from course description."""
    desc_lower = description.lower()
    return {
        topic: 1.0 if any(kw in desc_lower for kw in keywords) else 0.0
        for topic, keywords in TOPIC_KEYWORDS.items()
    }


def extract_course_features(
    course: Course,
    summary: CourseSummary | None,
) -> np.ndarray:
    """Extract a numeric feature vector for a course.

    Features (18 total):
      0: avg_difficulty (from reviews, or 3.0 default)
      1: avg_instructor_rating
      2: avg_enjoyment
      3: avg_workload (normalized /20)
      4: credit_count (normalized /4)
      5: is_prerequisite
      6: is_required
      7: is_restricted_elective
      8: is_integration_elective
      9: course_level (1-5, from course number)
     10-17: topic vector (8 topics: ai, data, graphics, hci, nlp, robotics,
                          security, software — alphabetical subset)
    """
    # Review-based features
    if summary is not None:
        diff = summary.avg_difficulty / 5.0
        instr = summary.avg_instructor_rating / 5.0
        enjoy = summary.avg_enjoyment / 5.0
        work = summary.avg_workload / 20.0
    else:
        diff = 0.6
        instr = 0.7
        enjoy = 0.66
        work = 0.35

    # Course metadata
    credits = course.credits / 4.0
    is_prereq = float(course.course_type == CourseType.PREREQUISITE)
    is_required = float(course.course_type == CourseType.REQUIRED)
    is_restricted = float(course.course_type == CourseType.RESTRICTED_ELECTIVE)
    is_integration = float(course.course_type == CourseType.INTEGRATION_ELECTIVE)

    # Course level from number
    numbers = re.findall(r"\d+", course.code)
    level = int(numbers[0][0]) / 5.0 if numbers else 0.6

    # Topic vector (subset for manageable feature size)
    topics = extract_topic_vector(course.description)
    # Use a fixed subset of 8 topics
    topic_subset = ["ai", "data", "graphics", "hci", "nlp", "security", "software", "systems"]
    topic_vec = [topics.get(t, 0.0) for t in topic_subset]

    return np.array(
        [diff, instr, enjoy, work, credits, is_prereq, is_required,
         is_restricted, is_integration, level] + topic_vec,
        dtype=np.float32,
    )


FEATURE_DIM = 18  # 10 base + 8 topic


def compute_preference_alignment(
    course: Course,
    summary: CourseSummary | None,
    preferences: StudentPreferences,
) -> float:
    """Compute a 0-1 alignment score between a course and student preferences.

    This is used as training signal / label for the Bayes Net.
    """
    score = 0.5  # neutral baseline

    if summary is not None:
        # Difficulty alignment: student wants easy (1) -> prefer low difficulty
        diff_pref = preferences.difficulty_preference / 5.0
        diff_actual = summary.avg_difficulty / 5.0
        diff_alignment = 1.0 - abs(diff_pref - diff_actual)
        score += 0.15 * diff_alignment

        # Enjoyment bonus
        score += 0.15 * (summary.avg_enjoyment / 5.0)

        # Instructor quality bonus
        score += 0.1 * (summary.avg_instructor_rating / 5.0)

    # Topic alignment
    if preferences.preferred_topics:
        topics = extract_topic_vector(course.description)
        pref_lower = [t.lower() for t in preferences.preferred_topics]
        matching = sum(
            topics.get(t, 0.0)
            for t in pref_lower
            if t in topics
        )
        # Also do fuzzy matching for multi-word topics
        desc_lower = course.description.lower()
        for pref_topic in pref_lower:
            if pref_topic in desc_lower:
                matching += 0.5
        topic_score = min(1.0, matching / max(1, len(pref_lower)))
        score += 0.15 * topic_score

    # Liked/disliked courses
    if course.code in preferences.liked_courses:
        score += 0.1
    if course.code in preferences.disliked_courses:
        score -= 0.2

    return max(0.0, min(1.0, score))
