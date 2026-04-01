"""Shared application state — loaded once at startup."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.data.course_graph import CourseGraph
from src.data.course_loader import Course, load_courses
from src.data.review_data import CourseSummary, get_all_summaries, load_reviews
from src.data.section_data import CourseSection, load_sections
from src.llm.llm_client import LLMClient, create_llm_client

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Centralized application state loaded at startup."""

    courses: dict[str, Course]
    course_graph: CourseGraph
    summaries: dict[str, CourseSummary]
    sections: list[CourseSection]
    credit_lookup: dict[str, int]
    llm_client: LLMClient
    ratings: list[dict] = field(default_factory=list)
    chat_sessions: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def initialize(cls, project_root: Path) -> AppState:
        courses_path = project_root / "courses.json"
        reviews_path = project_root / "data" / "reviews" / "synthetic_reviews.json"
        sections_path = project_root / "data" / "sections" / "fall_2026_sections.json"

        logger.info("Loading courses from %s", courses_path)
        courses = load_courses(courses_path)
        course_graph = CourseGraph(courses)

        reviews = load_reviews(reviews_path)
        summaries = get_all_summaries(reviews)

        sections = load_sections(sections_path)

        credit_lookup = {code: c.credits for code, c in courses.items()}

        llm_client = create_llm_client(backend="auto")

        logger.info(
            "Loaded %d courses, %d reviews, %d sections",
            len(courses), len(reviews), len(sections),
        )

        return cls(
            courses=courses,
            course_graph=course_graph,
            summaries=summaries,
            sections=sections,
            credit_lookup=credit_lookup,
            llm_client=llm_client,
        )
