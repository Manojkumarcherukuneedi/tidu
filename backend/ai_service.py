"""LLM task-enrichment service.

Design contract (and why each piece exists):

  enrich_task(raw_text) -> EnrichedTask
      The ONLY entry point routes are allowed to call. It takes raw natural
      language and returns a *validated* EnrichedTask. It never raises and
      never blocks task creation: any failure (API error, timeout, network
      failure, malformed JSON, or schema-validation failure) is caught and
      turned into safe defaults. The route can therefore always persist.

  apply_enrichment(payload, enrichment) -> TaskCreate
      Merges the AI's guesses into the user's request under the "user wins"
      rule: the model only fills fields the user left blank. The human is the
      authority; the AI is a helpful default.

Routes never touch the LLM directly — they call these two functions.

Two robustness ideas worth calling out for interviews:
  1. "Validate before trusting." The model returns *text we hope is JSON*. We
     strip accidental markdown fences, parse it, and then run it through a
     Pydantic model (EnrichedTask). That converts "hope" into "guaranteed, or
     caught" — a bad priority like "Urgent" fails validation and we fall back.
  2. Today's date is injected into the prompt. The model has no reliable sense
     of "now," so to resolve "Friday" or "tomorrow" into a real date it must be
     told today's date. We never hardcode it.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import date
from typing import Optional

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict

from .models import DEFAULT_CATEGORY, DEFAULT_PRIORITY, Priority, TaskCreate

load_dotenv()

logger = logging.getLogger("ai_task_organizer.ai")

# Read config from the environment. The API key is read here and passed to the
# SDK — it is NEVER logged anywhere in this module. We accept LLM_API_KEY first
# (the app's own name) and fall back to ANTHROPIC_API_KEY (the SDK's native var).
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5")
LLM_TIMEOUT_SECONDS = 10.0  # a hung API call must not hang the endpoint


class EnrichedTask(BaseModel):
    """Validated shape of the LLM's response.

    `priority` reuses the same Literal["High","Medium","Low"] as the rest of
    the app, so a model that returns "Urgent" fails validation here and we fall
    back — the bad value never reaches the database.
    """

    model_config = ConfigDict(extra="ignore")  # tolerate extra keys, ignore them

    category: str
    priority: Priority
    due_date: Optional[date] = None


def _fallback() -> EnrichedTask:
    """The safe defaults used whenever enrichment can't be trusted."""
    return EnrichedTask(
        category=DEFAULT_CATEGORY,
        priority=DEFAULT_PRIORITY,
        due_date=None,
    )


# --- Prompt construction ------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a task-enrichment assistant for a to-do app. You read a single "
    "task written in natural language and extract structured metadata.\n"
    "Respond with ONLY a JSON object — no prose, no explanation, no markdown "
    "code fences. The JSON must have EXACTLY these three keys:\n"
    '  "category":  a short 1-2 word category such as "Work", "Health", '
    '"School", "Personal", "Finance", or "Errands".\n'
    '  "priority":  exactly one of "High", "Medium", "Low".\n'
    '  "due_date":  a date as "YYYY-MM-DD" if the task implies a deadline, '
    "otherwise null.\n"
)


def _build_user_prompt(raw_text: str, today: date) -> str:
    """Build the per-task prompt, injecting today's date for relative dates."""
    return (
        f"Today's date is {today.isoformat()} ({today:%A}). "
        'Use it to resolve relative dates like "tomorrow", "Friday", '
        '"next week", or "in 3 days".\n\n'
        f"Task: {raw_text}\n\n"
        "Return only the JSON object."
    )


# --- LLM call + parsing -------------------------------------------------------
_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    """Lazily construct the Anthropic client so import never fails on a missing key."""
    global _client
    if _client is None:
        if not LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY is not set in the environment")
        _client = anthropic.Anthropic(api_key=LLM_API_KEY, timeout=LLM_TIMEOUT_SECONDS)
    return _client


def _call_llm(raw_text: str, today: date) -> str:
    """Make the actual model call and return the raw text response.

    Low temperature for consistent, deterministic structured output. Small
    max_tokens because the answer is a tiny JSON object. Isolated in its own
    function so tests can monkeypatch it without touching the parse/fallback
    logic — which is exactly how we exercise the "bad AI response" path.
    """
    client = _get_client()
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=300,
        temperature=0,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(raw_text, today)}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _strip_code_fences(text: str) -> str:
    """Remove an accidental ```json ... ``` (or ``` ... ```) wrapper if present."""
    stripped = text.strip()
    fenced = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL | re.IGNORECASE
    )
    return fenced.group(1).strip() if fenced else stripped


def _parse_enrichment(text: str) -> EnrichedTask:
    """Turn raw model text into a validated EnrichedTask, or raise.

    Order of defense: strip fences -> json.loads -> (last resort) grab the
    outermost {...} if the model wrapped the JSON in a stray sentence ->
    Pydantic validation. Anything that fails here raises, and enrich_task turns
    that into safe defaults.
    """
    cleaned = _strip_code_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start == -1 or end == -1:
            raise
        data = json.loads(cleaned[start : end + 1])
    return EnrichedTask(**data)  # Pydantic validates priority + due_date here


# --- Public API ---------------------------------------------------------------
def enrich_task(raw_text: str, today: Optional[date] = None) -> EnrichedTask:
    """Enrich a raw task. Never raises; falls back to safe defaults on any error."""
    today = today or date.today()
    try:
        raw_response = _call_llm(raw_text, today)
        enrichment = _parse_enrichment(raw_response)
        logger.info(
            "Enriched task -> category=%s priority=%s due_date=%s",
            enrichment.category,
            enrichment.priority,
            enrichment.due_date,
        )
        return enrichment
    except Exception as exc:  # noqa: BLE001 - graceful degradation is the point
        # NOTE: we log the failure *type and message* but never the API key.
        logger.warning(
            "AI enrichment failed (%s: %s); using safe defaults.",
            type(exc).__name__,
            exc,
        )
        return _fallback()


def needs_enrichment(payload: TaskCreate) -> bool:
    """True if the user left any AI-fillable field blank (else we can skip the call)."""
    return payload.category is None or payload.priority is None or payload.due_date is None


def apply_enrichment(payload: TaskCreate, enrichment: EnrichedTask) -> TaskCreate:
    """Merge AI guesses into the user's request — user-provided values win.

    Only fields the user left as None get the AI's value. `raw_text` and
    `title` are never touched by the AI.
    """
    data = payload.model_dump()
    if data["category"] is None:
        data["category"] = enrichment.category
    if data["priority"] is None:
        data["priority"] = enrichment.priority
    if data["due_date"] is None:
        data["due_date"] = enrichment.due_date
    return TaskCreate(**data)  # re-validate the merged result
