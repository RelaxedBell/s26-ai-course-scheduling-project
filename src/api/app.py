"""FastAPI application — main entry point for the course scheduling API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.api.routes import router
from src.api.state import AppState

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "src" / "ui" / "templates"
STATIC_DIR = PROJECT_ROOT / "src" / "ui" / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="UVA Course Scheduler",
        description="AI-powered course scheduling for UVA CS students",
        version="0.1.0",
    )

    # Initialize shared state
    state = AppState.initialize(PROJECT_ROOT)
    app.state.app_state = state

    # Mount static files and templates
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Include API routes
    app.include_router(router)

    return app


app = create_app()
