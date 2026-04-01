"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.student.preferences import StudentPreferences, TimeBlock


class TranscriptRequest(BaseModel):
    completed_courses: list[str] = Field(
        description="List of course codes, e.g. ['CS 1110', 'CS 2100']"
    )


class RequirementStatusResponse(BaseModel):
    remaining_prerequisites: list[str]
    remaining_required: list[str]
    restricted_elective_credits_needed: int
    integration_elective_credits_needed: int
    completed_restricted_electives: list[str]
    completed_integration_electives: list[str]
    is_complete: bool
    credits_completed: int


class PreferencesRequest(BaseModel):
    mode: str = Field(
        default="json",
        description="'json' for structured input, 'natural' for NL parsing"
    )
    preferences: StudentPreferences | None = None
    natural_language: str | None = None


class ScheduleSectionResponse(BaseModel):
    course_code: str
    course_name: str
    section_id: str
    instructor: str
    days: list[str]
    start_time: str
    end_time: str
    bayes_score: float


class ScheduleResponse(BaseModel):
    schedule_id: int
    sections: list[ScheduleSectionResponse]
    score: float
    total_credits: int


class GenerateRequest(BaseModel):
    completed_courses: list[str]
    preferences: StudentPreferences
    max_schedules: int = Field(default=5, ge=1, le=20)


class GenerateResponse(BaseModel):
    schedules: list[ScheduleResponse]


class ExplainRequest(BaseModel):
    schedule_id: int
    completed_courses: list[str]
    preferences: StudentPreferences


class ExplainResponse(BaseModel):
    explanation: str


class RateRequest(BaseModel):
    schedule_id: int
    rating: int = Field(ge=1, le=10)
    comment: str = ""


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseModel):
    reply: str
    preferences_parsed: StudentPreferences | None = None
    schedules: list[ScheduleResponse] | None = None


class CourseResponse(BaseModel):
    code: str
    name: str
    description: str
    credits: int
    course_type: str
    prerequisites_raw: str
