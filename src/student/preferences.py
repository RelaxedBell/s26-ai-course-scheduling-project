"""Student preference schema with validation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TimeBlock(BaseModel):
    """A time range when the student is unavailable."""

    days: list[str] = Field(
        description="Days of week, e.g. ['M', 'W', 'F']"
    )
    start_time: str = Field(description="Start time, e.g. '08:00'")
    end_time: str = Field(description="End time, e.g. '10:00'")


class StudentPreferences(BaseModel):
    """All soft preferences a student can specify."""

    difficulty_preference: int = Field(
        default=3,
        ge=1,
        le=5,
        description="1=easy semester, 5=challenging semester",
    )
    max_credits: int = Field(default=15, ge=3, le=21)
    min_credits: int = Field(default=12, ge=3, le=21)
    preferred_topics: list[str] = Field(
        default_factory=list,
        description="Keywords like 'AI', 'systems', 'security'",
    )
    liked_courses: list[str] = Field(
        default_factory=list,
        description="Course codes the student enjoyed",
    )
    disliked_courses: list[str] = Field(
        default_factory=list,
        description="Course codes the student disliked",
    )
    time_blocks_unavailable: list[TimeBlock] = Field(
        default_factory=list,
        description="Time blocks for extracurriculars",
    )
    instructor_preferences: dict[str, int] = Field(
        default_factory=dict,
        description="Instructor name -> rating (1-5)",
    )
    prefer_morning: bool | None = Field(
        default=None,
        description="True=prefer morning, False=prefer afternoon, None=no preference",
    )
