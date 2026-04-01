"""Generate synthetic review and section data for development/testing."""

from __future__ import annotations

import json
import random
from pathlib import Path

# Ensure reproducible output
random.seed(42)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "courses.json"
REVIEWS_OUT = PROJECT_ROOT / "data" / "reviews" / "synthetic_reviews.json"
SECTIONS_OUT = PROJECT_ROOT / "data" / "sections" / "fall_2026_sections.json"

# Topic keywords for matching against course descriptions
TOPIC_KEYWORDS = {
    "AI": ["artificial intelligence", "machine learning", "neural", "nlp", "vision"],
    "systems": ["operating system", "network", "distributed", "parallel", "cloud"],
    "security": ["security", "cryptograph", "privacy", "vulnerability"],
    "theory": ["algorithm", "complexity", "automata", "formal", "proof", "theory"],
    "software": ["software engineering", "agile", "testing", "design pattern"],
    "data": ["database", "data science", "big data", "analytics"],
    "graphics": ["graphics", "visualization", "rendering", "game"],
    "web": ["web", "internet", "http", "api"],
}

INSTRUCTORS = [
    "Dr. Smith", "Dr. Johnson", "Dr. Williams", "Dr. Brown", "Dr. Jones",
    "Dr. Davis", "Dr. Miller", "Dr. Wilson", "Dr. Moore", "Dr. Taylor",
    "Dr. Anderson", "Dr. Thomas", "Dr. Jackson", "Dr. White", "Dr. Harris",
    "Dr. Martin", "Dr. Thompson", "Dr. Garcia", "Dr. Martinez", "Dr. Robinson",
]

SEMESTERS = ["Fall 2024", "Spring 2025", "Fall 2025", "Spring 2026"]

TIME_SLOTS_MWF = [
    ("09:00", "09:50"), ("10:00", "10:50"), ("11:00", "11:50"),
    ("12:00", "12:50"), ("13:00", "13:50"), ("14:00", "14:50"),
    ("15:00", "15:50"), ("16:00", "16:50"),
]

TIME_SLOTS_TR = [
    ("09:30", "10:45"), ("11:00", "12:15"), ("12:30", "13:45"),
    ("14:00", "15:15"), ("15:30", "16:45"), ("17:00", "18:15"),
]

REVIEW_TEMPLATES_POSITIVE = [
    "Great course! Really enjoyed the material on {topic}.",
    "Professor {instructor} made the lectures engaging and clear.",
    "Challenging but rewarding. Learned a lot about {topic}.",
    "Well-organized course with fair assessments.",
    "One of the best CS courses I've taken. Highly recommend.",
]

REVIEW_TEMPLATES_NEUTRAL = [
    "Decent course. The workload was manageable.",
    "Average difficulty. {topic} was interesting but could use more depth.",
    "Professor {instructor} was okay. Lectures could be more engaging.",
    "Learned some useful things, but not my favorite class.",
]

REVIEW_TEMPLATES_NEGATIVE = [
    "Very difficult course. The exams were brutal.",
    "Too much work for the credit hours. {topic} is not for everyone.",
    "Professor {instructor} wasn't great at explaining concepts.",
    "Disorganized course. Would not recommend unless required.",
]


def _detect_topics(description: str) -> list[str]:
    desc_lower = description.lower()
    return [
        topic
        for topic, keywords in TOPIC_KEYWORDS.items()
        if any(kw in desc_lower for kw in keywords)
    ]


def _generate_reviews_for_course(
    code: str, info: dict, num_reviews: int
) -> list[dict]:
    course_type = info.get("type", "")
    description = info.get("description", "")
    topics = _detect_topics(description) or ["computer science"]

    # Base difficulty depends on course level and type
    level = int(code.split()[-1][0]) if code.split()[-1][0].isdigit() else 3
    base_difficulty = 2.0 + (level - 1) * 0.5
    if course_type == "required course":
        base_difficulty += 0.3

    reviews = []
    for _ in range(num_reviews):
        instructor = random.choice(INSTRUCTORS)
        semester = random.choice(SEMESTERS)
        topic = random.choice(topics)

        difficulty = max(1.0, min(5.0, random.gauss(base_difficulty, 0.7)))
        instructor_rating = max(1.0, min(5.0, random.gauss(3.5, 0.8)))
        enjoyment = max(1.0, min(5.0, random.gauss(3.3, 0.9)))
        workload = max(1.0, min(20.0, random.gauss(6.0 + level, 2.5)))

        # Choose review template based on enjoyment
        if enjoyment >= 3.8:
            template = random.choice(REVIEW_TEMPLATES_POSITIVE)
        elif enjoyment >= 2.5:
            template = random.choice(REVIEW_TEMPLATES_NEUTRAL)
        else:
            template = random.choice(REVIEW_TEMPLATES_NEGATIVE)

        review_text = template.format(topic=topic, instructor=instructor)

        reviews.append({
            "course_code": code,
            "instructor": instructor,
            "semester": semester,
            "difficulty_rating": round(difficulty, 1),
            "instructor_rating": round(instructor_rating, 1),
            "enjoyment_rating": round(enjoyment, 1),
            "workload_hours": round(workload, 1),
            "review_text": review_text,
        })

    return reviews


def _generate_sections_for_course(
    code: str, info: dict, num_sections: int
) -> list[dict]:
    sections = []
    for i in range(num_sections):
        instructor = random.choice(INSTRUCTORS)

        if random.random() < 0.6:
            days = ["M", "W", "F"]
            start, end = random.choice(TIME_SLOTS_MWF)
        else:
            days = ["T", "R"]
            start, end = random.choice(TIME_SLOTS_TR)

        raw_credits = info.get("credits", 3)
        credits = int(raw_credits) if isinstance(raw_credits, (int, float)) else 3
        cap = random.choice([30, 40, 50, 60, 80, 100, 150, 200])
        if credits >= 4:
            cap = min(cap, 60)

        sections.append({
            "course_code": code,
            "section_id": f"{code.replace(' ', '')}-{i + 1:03d}",
            "instructor": instructor,
            "days": days,
            "start_time": start,
            "end_time": end,
            "location": f"Rice {random.randint(100, 400)}",
            "semester": "Fall 2026",
            "enrollment_cap": cap,
            "enrollment_current": random.randint(0, cap),
        })

    return sections


def generate_all():
    with open(COURSES_JSON, encoding="utf-8") as f:
        courses = json.load(f)

    all_reviews = []
    all_sections = []

    for code, info in courses.items():
        num_reviews = random.randint(5, 20)
        all_reviews.extend(
            _generate_reviews_for_course(code, info, num_reviews)
        )

        num_sections = random.randint(1, 4)
        all_sections.extend(
            _generate_sections_for_course(code, info, num_sections)
        )

    REVIEWS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(REVIEWS_OUT, "w", encoding="utf-8") as f:
        json.dump(all_reviews, f, indent=2)

    SECTIONS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(SECTIONS_OUT, "w", encoding="utf-8") as f:
        json.dump(all_sections, f, indent=2)

    print(f"Generated {len(all_reviews)} reviews -> {REVIEWS_OUT}")
    print(f"Generated {len(all_sections)} sections -> {SECTIONS_OUT}")


if __name__ == "__main__":
    generate_all()
