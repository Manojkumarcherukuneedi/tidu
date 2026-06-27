"""Tests for AI enrichment: parsing, validation, fallback, and the user-wins merge.

Per project conventions we test the parsing/validation logic and the route
wiring — NOT the live LLM call. Every test here monkeypatches `_call_llm`, so
the real model is never hit and no API key is required.

The integration tests use FastAPI's TestClient, which runs the real route ->
real crud -> real MySQL in-process, with only the model call faked. That lets
us prove "bad AI response still saves the task with defaults, 201 not 500"
against the live database.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import ai_service
from backend.ai_service import EnrichedTask, apply_enrichment, enrich_task, needs_enrichment
from backend.main import app
from backend.models import TaskCreate

# --- Pure parsing / validation -----------------------------------------------


def test_parse_strips_markdown_fences():
    text = '```json\n{"category": "Work", "priority": "High", "due_date": null}\n```'
    result = ai_service._parse_enrichment(text)
    assert result.category == "Work"
    assert result.priority == "High"
    assert result.due_date is None


def test_parse_handles_stray_prose_around_json():
    text = 'Sure! Here is the result: {"category": "Health", "priority": "Low", "due_date": null} Hope that helps.'
    result = ai_service._parse_enrichment(text)
    assert result.category == "Health"
    assert result.priority == "Low"


def test_build_user_prompt_includes_today():
    today = date(2026, 6, 27)
    prompt = ai_service._build_user_prompt("call dentist tomorrow", today)
    assert "2026-06-27" in prompt
    assert "call dentist tomorrow" in prompt


# --- enrich_task fallback behavior (the heart of graceful degradation) --------


def test_enrich_falls_back_on_invalid_json(monkeypatch):
    monkeypatch.setattr(ai_service, "_call_llm", lambda raw, today: "this is not json")
    result = enrich_task("buy milk")
    assert result.category == "Uncategorized"
    assert result.priority == "Medium"
    assert result.due_date is None


def test_enrich_falls_back_on_invalid_priority(monkeypatch):
    # "Urgent" is not in the allowed set, so Pydantic validation fails -> defaults.
    bad = '{"category": "Work", "priority": "Urgent", "due_date": "2026-07-01"}'
    monkeypatch.setattr(ai_service, "_call_llm", lambda raw, today: bad)
    result = enrich_task("finish report")
    assert result.category == "Uncategorized"
    assert result.priority == "Medium"
    assert result.due_date is None


def test_enrich_falls_back_on_api_error(monkeypatch):
    def boom(raw, today):
        raise RuntimeError("simulated API/timeout failure")

    monkeypatch.setattr(ai_service, "_call_llm", boom)
    result = enrich_task("anything")
    assert result == ai_service._fallback()


def test_enrich_happy_path(monkeypatch):
    good = '{"category": "Health", "priority": "Medium", "due_date": "2026-06-28"}'
    monkeypatch.setattr(ai_service, "_call_llm", lambda raw, today: good)
    result = enrich_task("call dentist tomorrow")
    assert result.category == "Health"
    assert result.priority == "Medium"
    assert result.due_date == date(2026, 6, 28)


# --- user-wins merge ----------------------------------------------------------


def test_needs_enrichment():
    assert needs_enrichment(TaskCreate(raw_text="x")) is True
    assert needs_enrichment(TaskCreate(raw_text="x", category="Work")) is True
    full = TaskCreate(
        raw_text="x", category="Work", priority="High", due_date=date(2026, 1, 1)
    )
    assert needs_enrichment(full) is False


def test_apply_enrichment_user_priority_wins():
    payload = TaskCreate(raw_text="finish DB assignment", priority="High")
    enrichment = EnrichedTask(category="School", priority="Low", due_date=date(2026, 7, 3))
    merged = apply_enrichment(payload, enrichment)
    assert merged.priority == "High"          # user value preserved
    assert merged.category == "School"        # AI filled the blank
    assert merged.due_date == date(2026, 7, 3)  # AI filled the blank


# --- Integration: real route + real DB, faked model ---------------------------


def test_post_bad_ai_still_saves_with_defaults(monkeypatch):
    """Forced invalid JSON -> task STILL saves with defaults and returns 201."""
    monkeypatch.setattr(ai_service, "_call_llm", lambda raw, today: "{ broken json ::")
    with TestClient(app) as client:
        resp = client.post("/tasks", json={"raw_text": "something the AI mangles"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["category"] == "Uncategorized"
        assert body["priority"] == "Medium"
        assert body["due_date"] is None
        # confirm it actually persisted
        got = client.get(f"/tasks/{body['id']}")
        assert got.status_code == 200
        client.delete(f"/tasks/{body['id']}")  # cleanup


def test_post_user_priority_not_overridden_by_ai(monkeypatch):
    """User passes priority -> AI does not override it; AI fills the blanks."""
    ai = '{"category": "Health", "priority": "Low", "due_date": null}'
    monkeypatch.setattr(ai_service, "_call_llm", lambda raw, today: ai)
    with TestClient(app) as client:
        resp = client.post("/tasks", json={"raw_text": "call dentist", "priority": "High"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["priority"] == "High"      # user wins
        assert body["category"] == "Health"    # AI filled the blank
        client.delete(f"/tasks/{body['id']}")  # cleanup


def test_post_enriches_relative_date(monkeypatch):
    """Plumbing proof for the happy path: AI's category/priority/due_date are saved."""
    tomorrow = date.today() + timedelta(days=1)
    ai = f'{{"category": "Health", "priority": "Medium", "due_date": "{tomorrow.isoformat()}"}}'
    monkeypatch.setattr(ai_service, "_call_llm", lambda raw, today: ai)
    with TestClient(app) as client:
        resp = client.post("/tasks", json={"raw_text": "call dentist tomorrow"})
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["category"] == "Health"
        assert body["priority"] == "Medium"
        assert body["due_date"] == tomorrow.isoformat()
        client.delete(f"/tasks/{body['id']}")  # cleanup
