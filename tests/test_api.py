"""Tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    return TestClient(app)


class TestCourseEndpoints:
    def test_list_courses(self, client):
        resp = client.get("/api/courses")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 100
        assert data[0]["code"]

    def test_get_course(self, client):
        resp = client.get("/api/courses/CS 1110")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Introduction to Programming"

    def test_get_course_not_found(self, client):
        resp = client.get("/api/courses/FAKE 9999")
        assert resp.status_code == 404


class TestTranscriptEndpoint:
    def test_audit(self, client):
        resp = client.post("/api/transcript", json={
            "completed_courses": ["CS 1110", "CS 2100", "CS 2120"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["credits_completed"] > 0
        assert "remaining_prerequisites" in data

    def test_empty_transcript(self, client):
        resp = client.post("/api/transcript", json={"completed_courses": []})
        assert resp.status_code == 200
        assert not resp.json()["is_complete"]


class TestPreferencesEndpoint:
    def test_json_preferences(self, client):
        resp = client.post("/api/preferences", json={
            "mode": "json",
            "preferences": {
                "difficulty_preference": 2,
                "preferred_topics": ["AI"],
            }
        })
        assert resp.status_code == 200
        assert resp.json()["difficulty_preference"] == 2

    def test_natural_language(self, client):
        resp = client.post("/api/preferences", json={
            "mode": "natural",
            "natural_language": "I want an easy semester focused on AI"
        })
        assert resp.status_code == 200
        assert resp.json()["difficulty_preference"] <= 2


class TestGenerateEndpoint:
    def test_generate(self, client):
        resp = client.post("/api/generate", json={
            "completed_courses": ["CS 1110", "CS 2100", "CS 2120", "CS 2130"],
            "preferences": {
                "difficulty_preference": 3,
                "preferred_topics": ["AI"],
            },
            "max_schedules": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["schedules"]) > 0
        sched = data["schedules"][0]
        assert len(sched["sections"]) > 0
        assert sched["total_credits"] > 0


class TestRateEndpoint:
    def test_rate(self, client):
        # First generate a schedule
        client.post("/api/generate", json={
            "completed_courses": ["CS 1110"],
            "preferences": {"difficulty_preference": 3},
            "max_schedules": 1,
        })
        resp = client.post("/api/rate", json={
            "schedule_id": 0,
            "rating": 8,
            "comment": "Good schedule!",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestChatEndpoint:
    def test_chat_greeting(self, client):
        resp = client.post("/api/chat", json={
            "message": "hello",
            "session_id": "test-1",
        })
        assert resp.status_code == 200
        assert "welcome" in resp.json()["reply"].lower()

    def test_chat_flow(self, client):
        sid = "test-flow"
        # Greeting
        client.post("/api/chat", json={"message": "hi", "session_id": sid})
        # Transcript
        resp = client.post("/api/chat", json={
            "message": "CS 1110, CS 2100, CS 2120, CS 2130",
            "session_id": sid,
        })
        assert resp.status_code == 200
        assert "completed" in resp.json()["reply"].lower()

        # Preferences -> should generate schedules
        resp = client.post("/api/chat", json={
            "message": "I want an easy semester focused on AI",
            "session_id": sid,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["schedules"] is not None or "generated" in data["reply"].lower()


class TestHomePage:
    def test_index(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "UVA" in resp.text
