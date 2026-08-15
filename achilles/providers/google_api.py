"""Google AI Studio (Gemini).

Its own API shape rather than an OpenAI-compatible one, so it gets its own file:
the system prompt goes in `systemInstruction`, the schema in
`generationConfig.responseSchema`, and the schema has to be the OpenAPI subset
that `schema.google_schema()` produces — no `$ref`, no `additionalProperties`.

The key travels in the `x-goog-api-key` header rather than the query string, so
it stays out of request logs and proxy access logs.
"""

from __future__ import annotations

from typing import Any

from ..errors import UpstreamError
from .base import loads_or_raise, post_json

LABEL = "Google AI Studio"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-pro"
CONSOLE = "aistudio.google.com/apikey"

# Gemini's thinking budget is a token count, not a named tier. These are chosen
# to bracket the same range the other backends' effort levels cover; -1 hands
# the decision back to the model.
_THINKING_BUDGET = {"low": 1024, "medium": 8192, "high": -1, "xhigh": -1, "max": -1}

MAX_OUTPUT_TOKENS = 20000

# Everything except the outright block reasons, which get their own message.
_BENIGN_FINISH = {"STOP", "MAX_TOKENS", ""}


def complete(
    *,
    key: str,
    model: str,
    effort: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    base_url: str = "",
    **_: Any,
) -> dict[str, Any]:
    base = (base_url or BASE_URL).rstrip("/")
    body: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "maxOutputTokens": MAX_OUTPUT_TOKENS,
            "thinkingConfig": {"thinkingBudget": _THINKING_BUDGET.get(effort, -1)},
        },
    }

    payload = post_json(
        f"{base}/models/{model}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        body=body,
        label=LABEL,
        key=key,
        console=CONSOLE,
    )

    feedback = payload.get("promptFeedback") or {}
    if feedback.get("blockReason"):
        raise UpstreamError(
            f"Gemini blocked this request ({feedback['blockReason']}).",
            hint="This usually means the pasted text tripped a safety filter. Try "
            "again with just the resume and job description.",
        )

    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise UpstreamError(f"{LABEL} returned no candidates.")
    candidate = candidates[0] or {}

    reason = str(candidate.get("finishReason") or "")
    if reason == "MAX_TOKENS":
        raise UpstreamError(
            "The model hit its output limit before finishing the resume.",
            hint="Trim the source resume — it is long enough that the rewrite does "
            "not fit in one response.",
        )
    if reason not in _BENIGN_FINISH:
        raise UpstreamError(
            f"Gemini stopped early ({reason}).",
            hint="Try again with just the resume and job description.",
        )

    parts = (candidate.get("content") or {}).get("parts") or []
    # Thinking parts carry `thought: true` and must not be concatenated into the
    # JSON payload, or the parse fails on prose it was never meant to see.
    text = "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and not part.get("thought")
    )
    return loads_or_raise(text, label=LABEL)
