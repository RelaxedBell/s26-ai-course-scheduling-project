"""Load and validate course data from courses.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from src.data.prerequisite_ast import ReqNode
from src.data.prerequisite_parser import parse_prerequisite


class CourseType(Enum):
    PREREQUISITE = "prerequisite"
    REQUIRED = "required course"
    RESTRICTED_ELECTIVE = "restricted elective"
    INTEGRATION_ELECTIVE = "integration elective"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Course:
    code: str
    name: str
    description: str
    credits: int
    course_type: CourseType
    prerequisites_raw: str
    prerequisites_parsed: ReqNode | None


def _parse_credits(raw: Any) -> int:
    """Parse credits, handling ranges like '1 to 3' by taking the max."""
    if isinstance(raw, int):
        return raw
    s = str(raw)
    numbers = [int(x) for x in s.split() if x.isdigit()]
    return max(numbers) if numbers else 3


def _parse_course_type(raw: str) -> CourseType:
    try:
        return CourseType(raw)
    except ValueError:
        return CourseType.UNKNOWN


def load_courses(path: str | Path = "courses.json") -> dict[str, Course]:
    """Load courses from JSON file and return a dict keyed by course code."""
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        raw_data = json.load(f)

    courses: dict[str, Course] = {}
    for code, info in raw_data.items():
        prereq_str = info.get("prerequisites", "")
        courses[code] = Course(
            code=code,
            name=info.get("name", ""),
            description=info.get("description", ""),
            credits=_parse_credits(info.get("credits", 3)),
            course_type=_parse_course_type(info.get("type", "unknown")),
            prerequisites_raw=prereq_str,
            prerequisites_parsed=parse_prerequisite(prereq_str),
        )
    return courses
