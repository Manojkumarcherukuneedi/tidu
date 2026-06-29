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
from pydantic import BaseModel, ConfigDict, field_validator

from .models import (
    DEFAULT_CATEGORY,
    DEFAULT_PRIORITY,
    DayPlan,
    PlanItem,
    Priority,
    TaskCreate,
)

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


def _complete(system: str, user: str, max_tokens: int = 300) -> str:
    """The single network boundary: send one prompt, return the text response.

    Low temperature for consistent structured output. Every LLM feature
    (enrichment, subtask breakdown, plan-my-day) goes through here, so a single
    monkeypatch in tests blocks all real network calls.
    """
    client = _get_client()
    response = client.messages.create(
        model=LLM_MODEL,
        max_tokens=max_tokens,
        temperature=0,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _call_llm(raw_text: str, today: date) -> str:
    """Enrichment-specific call. Kept as its own function so the existing tests
    can monkeypatch just the enrichment path."""
    return _complete(_SYSTEM_PROMPT, _build_user_prompt(raw_text, today), max_tokens=300)


def _strip_code_fences(text: str) -> str:
    """Remove an accidental ```json ... ``` (or ``` ... ```) wrapper if present."""
    stripped = text.strip()
    fenced = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL | re.IGNORECASE
    )
    return fenced.group(1).strip() if fenced else stripped


def _parse_json(text: str):
    """Strip fences and parse JSON, recovering an embedded object/array if the
    model wrapped it in stray prose. Raises if nothing parseable is found.

    Shared by all three AI features — this is the "turn hopeful text into data"
    step that precedes Pydantic validation.
    """
    cleaned = _strip_code_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for open_c, close_c in (("{", "}"), ("[", "]")):
            start, end = cleaned.find(open_c), cleaned.rfind(close_c)
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(cleaned[start : end + 1])
                except json.JSONDecodeError:
                    continue
        raise


def _parse_enrichment(text: str) -> EnrichedTask:
    """Parse + validate enrichment text into an EnrichedTask, or raise."""
    return EnrichedTask(**_parse_json(text))  # validates priority + due_date


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


# =============================================================================
# Slice 7 — two more AI features, same pattern: prompt for structured JSON ->
# _parse_json -> validate with a Pydantic model -> graceful fallback on ANY
# failure. Both route through _complete, so tests block them with one patch.
# =============================================================================

PRIORITY_RANK = {"High": 0, "Medium": 1, "Low": 2}


def _task_title(task: dict) -> str:
    return task.get("title") or task.get("raw_text") or "Untitled task"


def _due_str(task: dict):
    due = task.get("due_date")
    if due is None:
        return None
    return due.isoformat() if hasattr(due, "isoformat") else str(due)


# --- Feature 1: subtask breakdown --------------------------------------------
class _SubtaskBreakdown(BaseModel):
    """Validated shape of the breakdown response: a list of non-empty strings."""

    model_config = ConfigDict(extra="ignore")

    subtasks: list[str]

    @field_validator("subtasks")
    @classmethod
    def _clean(cls, value: list) -> list[str]:
        cleaned = [s.strip() for s in value if isinstance(s, str) and s.strip()]
        if not cleaned:
            raise ValueError("no usable subtasks")
        return cleaned[:6]  # cap at 6 even if the model returns more


_SUBTASK_SYSTEM = (
    "You break a single to-do task into 3-6 small, concrete, actionable steps.\n"
    'Respond with ONLY a JSON object: {"subtasks": ["step 1", "step 2", ...]}.\n'
    "No prose, no explanation, no markdown fences. Each step is short, starts "
    "with a verb, and is something the user can actually check off."
)


def generate_subtasks(task_text: str) -> list[str]:
    """Return 3-6 subtask strings for a task, or [] on any failure (never raises)."""
    try:
        raw = _complete(_SUBTASK_SYSTEM, f"Task: {task_text}\n\nReturn the JSON object.", max_tokens=400)
        data = _parse_json(raw)
        if isinstance(data, list):  # tolerate a bare array
            data = {"subtasks": data}
        return _SubtaskBreakdown(**data).subtasks
    except Exception as exc:  # noqa: BLE001 - graceful degradation
        logger.warning(
            "AI subtask breakdown failed (%s: %s); returning none.",
            type(exc).__name__,
            exc,
        )
        return []


# --- Feature 2: plan my day --------------------------------------------------
class _PlanItemModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_id: int
    reason: str


class _DayPlanModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str
    items: list[_PlanItemModel]


_PLAN_SYSTEM = (
    "You are a focus coach. Given a user's open tasks, produce a short "
    "prioritized plan for today.\n"
    "Respond with ONLY a JSON object: "
    '{"summary": "1-2 sentence overview", "items": [{"task_id": <int>, '
    '"reason": "one short line on why it is ordered here"}]}.\n'
    "Order items from do-first to do-later. Use ONLY task_id values from the "
    "provided list. Include the 3-7 most important tasks. No prose, no fences."
)


def _build_plan_prompt(tasks: list[dict], today: date) -> str:
    compact = [
        {
            "task_id": t["id"],
            "title": _task_title(t),
            "priority": t.get("priority") or "Medium",
            "due_date": _due_str(t),
        }
        for t in tasks
    ]
    return (
        f"Today is {today.isoformat()} ({today:%A}).\n"
        f"Open tasks:\n{json.dumps(compact)}\n\nReturn the JSON object."
    )


def _plan_sort_key(today: date):
    """Order: tasks with a due date first (earliest), then by priority."""
    def key(t: dict):
        due = _due_str(t)
        return (
            0 if due else 1,
            due or "9999-12-31",
            PRIORITY_RANK.get(t.get("priority"), 1),
        )

    return key


def _fallback_plan(tasks: list[dict], today: date) -> DayPlan:
    """Deterministic plan used when the AI is unavailable: due date, then priority."""
    ordered = sorted(tasks, key=_plan_sort_key(today))[:7]
    items = []
    for t in ordered:
        due = _due_str(t)
        reason = f"{t.get('priority') or 'Medium'} priority"
        reason += f", due {due}" if due else ", no due date"
        items.append(PlanItem(task_id=t["id"], title=_task_title(t), reason=reason))
    return DayPlan(
        summary="Basic plan: sorted by due date, then priority (AI unavailable).",
        items=items,
        source="fallback",
    )


def plan_day(tasks: list[dict], today: Optional[date] = None) -> DayPlan:
    """Return a prioritized day plan. Falls back to a basic sort on AI failure."""
    today = today or date.today()
    if not tasks:
        return DayPlan(summary="Nothing to plan — you have no open tasks.", items=[], source="ai")

    try:
        raw = _complete(_PLAN_SYSTEM, _build_plan_prompt(tasks, today), max_tokens=700)
        parsed = _DayPlanModel(**_parse_json(raw))
        by_id = {t["id"]: t for t in tasks}
        items = []
        for item in parsed.items:
            task = by_id.get(item.task_id)  # ignore ids the model invented
            if task is None:
                continue
            items.append(
                PlanItem(task_id=item.task_id, title=_task_title(task), reason=item.reason.strip() or "—")
            )
        if not items:
            raise ValueError("AI plan referenced no real tasks")
        return DayPlan(summary=parsed.summary.strip(), items=items, source="ai")
    except Exception as exc:  # noqa: BLE001 - graceful degradation
        logger.warning(
            "AI plan-my-day failed (%s: %s); using basic sort.",
            type(exc).__name__,
            exc,
        )
        return _fallback_plan(tasks, today)
