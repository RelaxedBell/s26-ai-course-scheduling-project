"""API routes for the course scheduling application."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.api.schemas import (
    ChatRequest,
    ChatResponse,
    CourseResponse,
    ExplainRequest,
    ExplainResponse,
    GenerateRequest,
    GenerateResponse,
    PreferencesRequest,
    RateRequest,
    RequirementStatusResponse,
    ScheduleResponse,
    ScheduleSectionResponse,
    TranscriptRequest,
)
from src.api.state import AppState
from src.llm.explainer import explain_schedule
from src.llm.preference_parser import parse_natural_language_preferences
from src.models.bayes_net import NaiveBayesScorer
from src.models.constraint_solver import ScheduleGenerator
from src.student.degree_requirements import compute_remaining_requirements
from src.student.preferences import StudentPreferences
from src.student.transcript import Transcript

router = APIRouter()

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Store generated schedules for explain/rate endpoints
_schedule_cache: dict[int, object] = {}


def _get_state(request: Request) -> AppState:
    return request.app.state.app_state


# --- HTML Pages ---


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    state = _get_state(request)
    course_list = [
        {"code": code, "name": c.name, "type": c.course_type.value}
        for code, c in sorted(state.courses.items())
    ]
    return templates.TemplateResponse(
        request,
        "index.html",
        {"courses": course_list},
    )


# --- API Endpoints ---


@router.get("/api/courses")
async def list_courses(request: Request) -> list[CourseResponse]:
    state = _get_state(request)
    return [
        CourseResponse(
            code=code,
            name=c.name,
            description=c.description,
            credits=c.credits,
            course_type=c.course_type.value,
            prerequisites_raw=c.prerequisites_raw,
        )
        for code, c in sorted(state.courses.items())
    ]


@router.get("/api/courses/{code}")
async def get_course(request: Request, code: str) -> CourseResponse:
    state = _get_state(request)
    c = state.courses.get(code)
    if c is None:
        raise HTTPException(404, f"Course {code} not found")
    return CourseResponse(
        code=code,
        name=c.name,
        description=c.description,
        credits=c.credits,
        course_type=c.course_type.value,
        prerequisites_raw=c.prerequisites_raw,
    )


@router.post("/api/transcript")
async def audit_transcript(
    request: Request, body: TranscriptRequest
) -> RequirementStatusResponse:
    state = _get_state(request)
    transcript = Transcript.from_list(body.completed_courses)
    status = compute_remaining_requirements(
        transcript.completed_courses, state.courses
    )
    return RequirementStatusResponse(
        remaining_prerequisites=status.remaining_prerequisites,
        remaining_required=status.remaining_required,
        restricted_elective_credits_needed=status.restricted_elective_credits_needed,
        integration_elective_credits_needed=status.integration_elective_credits_needed,
        completed_restricted_electives=status.completed_restricted_electives,
        completed_integration_electives=status.completed_integration_electives,
        is_complete=status.is_complete,
        credits_completed=transcript.credits_completed(state.courses),
    )


@router.post("/api/preferences")
async def parse_preferences(
    request: Request, body: PreferencesRequest
) -> StudentPreferences:
    state = _get_state(request)
    if body.mode == "natural" and body.natural_language:
        return parse_natural_language_preferences(
            body.natural_language, state.llm_client
        )
    if body.preferences:
        return body.preferences
    return StudentPreferences()


@router.post("/api/generate")
async def generate_schedules(
    request: Request, body: GenerateRequest
) -> GenerateResponse:
    state = _get_state(request)
    completed = frozenset(body.completed_courses)

    # Train Bayes Net on this student's preferences
    scorer = NaiveBayesScorer()
    scorer.train(state.courses, state.summaries, body.preferences)
    results = scorer.score_courses(state.courses, state.summaries)
    scores_dict = dict(results)

    # Generate schedules via CSP
    gen = ScheduleGenerator(
        state.course_graph,
        state.sections,
        completed,
        body.preferences,
        course_scores=scores_dict,
        credit_lookup=state.credit_lookup,
    )
    schedules = gen.generate(max_schedules=body.max_schedules)

    # Convert to response
    response_schedules = []
    for i, sched in enumerate(schedules):
        sections = []
        total_credits = 0
        for sec in sched.sections:
            course = state.courses.get(sec.course_code)
            sections.append(ScheduleSectionResponse(
                course_code=sec.course_code,
                course_name=course.name if course else "Unknown",
                section_id=sec.section_id,
                instructor=sec.instructor,
                days=sec.days,
                start_time=sec.start_time,
                end_time=sec.end_time,
                bayes_score=scores_dict.get(sec.course_code, 0.5),
            ))
            if course:
                total_credits += course.credits

        sched_resp = ScheduleResponse(
            schedule_id=i,
            sections=sections,
            score=sched.score,
            total_credits=total_credits,
        )
        response_schedules.append(sched_resp)

        # Cache for explain endpoint
        _schedule_cache[i] = sched

    return GenerateResponse(schedules=response_schedules)


@router.post("/api/explain")
async def explain(
    request: Request, body: ExplainRequest
) -> ExplainResponse:
    state = _get_state(request)
    sched = _schedule_cache.get(body.schedule_id)
    if sched is None:
        raise HTTPException(404, "Schedule not found. Generate schedules first.")

    # Rebuild Bayes scores
    scorer = NaiveBayesScorer()
    scorer.train(state.courses, state.summaries, body.preferences)
    scores_dict = dict(scorer.score_courses(state.courses, state.summaries))

    explanation = explain_schedule(
        sched, body.preferences, state.courses, scores_dict, state.llm_client
    )
    return ExplainResponse(explanation=explanation)


@router.post("/api/rate")
async def rate_schedule(request: Request, body: RateRequest):
    state = _get_state(request)
    state.ratings.append({
        "schedule_id": body.schedule_id,
        "rating": body.rating,
        "comment": body.comment,
    })
    return {"status": "ok", "total_ratings": len(state.ratings)}


@router.post("/api/chat")
async def chat(request: Request, body: ChatRequest) -> ChatResponse:
    state = _get_state(request)
    session = state.chat_sessions.setdefault(body.session_id, {
        "stage": "greeting",
        "completed_courses": [],
        "preferences": None,
    })

    message = body.message.strip().lower()

    if session["stage"] == "greeting":
        session["stage"] = "transcript"
        return ChatResponse(
            reply=(
                "Welcome to the UVA Course Scheduler! "
                "Let's build your ideal schedule. First, please list the "
                "courses you've already completed (comma-separated course codes, "
                "e.g., 'CS 1110, CS 2100, CS 2120')."
            )
        )

    if session["stage"] == "transcript":
        # Parse course codes from message
        codes = [c.strip().upper() for c in body.message.split(",")]
        valid_codes = [c for c in codes if c in state.courses]
        session["completed_courses"] = valid_codes
        session["stage"] = "preferences"

        transcript = Transcript.from_list(valid_codes)
        status = compute_remaining_requirements(
            transcript.completed_courses, state.courses
        )

        return ChatResponse(
            reply=(
                f"Got it! You've completed {len(valid_codes)} courses "
                f"({transcript.credits_completed(state.courses)} credits). "
                f"You still need {len(status.remaining_prerequisites)} prerequisite(s), "
                f"{len(status.remaining_required)} required course(s), "
                f"and more elective credits.\n\n"
                "Now tell me about your preferences — what kind of semester "
                "do you want? (e.g., 'I want an easy semester focused on AI, "
                "about 12 credits, no classes before 10am')"
            )
        )

    if session["stage"] == "preferences":
        # Parse preferences from natural language
        prefs = parse_natural_language_preferences(
            body.message, state.llm_client
        )
        session["preferences"] = prefs
        session["stage"] = "generated"

        # Generate schedules
        completed = frozenset(session["completed_courses"])
        scorer = NaiveBayesScorer()
        scorer.train(state.courses, state.summaries, prefs)
        scores_dict = dict(scorer.score_courses(state.courses, state.summaries))

        gen = ScheduleGenerator(
            state.course_graph,
            state.sections,
            completed,
            prefs,
            course_scores=scores_dict,
            credit_lookup=state.credit_lookup,
        )
        schedules = gen.generate(max_schedules=3)

        response_schedules = []
        for i, sched in enumerate(schedules):
            sections = []
            total_credits = 0
            for sec in sched.sections:
                course = state.courses.get(sec.course_code)
                sections.append(ScheduleSectionResponse(
                    course_code=sec.course_code,
                    course_name=course.name if course else "Unknown",
                    section_id=sec.section_id,
                    instructor=sec.instructor,
                    days=sec.days,
                    start_time=sec.start_time,
                    end_time=sec.end_time,
                    bayes_score=scores_dict.get(sec.course_code, 0.5),
                ))
                if course:
                    total_credits += course.credits

            response_schedules.append(ScheduleResponse(
                schedule_id=i,
                sections=sections,
                score=sched.score,
                total_credits=total_credits,
            ))
            _schedule_cache[i] = sched

        return ChatResponse(
            reply=(
                f"I've generated {len(schedules)} schedule options based on "
                f"your preferences! You can rate them (1-10) or ask me to "
                f"refine the search."
            ),
            preferences_parsed=prefs,
            schedules=response_schedules,
        )

    # Default: allow further refinement
    session["stage"] = "preferences"
    return ChatResponse(
        reply="Tell me more about what you'd like to change in your schedule."
    )
