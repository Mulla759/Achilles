"""Every OpenAI-compatible endpoint: OpenAI, DeepSeek, Groq, xAI, OpenRouter,
GitHub Models, and whatever gateway you point `ACHILLES_BASE_URL` at.

One implementation covers all of them because they all speak
`POST /chat/completions` with the same body. What differs is the base URL, the
default model, and how much of the structured-output spec each one actually
honours — which is why `strict` degrades in three steps rather than being
assumed:

  1. `response_format: {type: json_schema, strict: true}` — real constrained
     decoding. OpenAI, Groq, xAI, and GitHub Models support it.
  2. `response_format: {type: json_object}` — guarantees parseable JSON but not
     the shape. DeepSeek's documented mode.
  3. Nothing — the schema is in the prompt and we validate on the way out.

Every tier ends with the same Pydantic validation, so a provider that quietly
ignores the schema fails loudly here rather than producing a broken PDF.
"""

from __future__ import annotations

import json
from typing import Any

from ..errors import UpstreamError
from .base import loads_or_raise, post_json

# provider id -> (label, base url, default model, structured-output tier, console)
ENDPOINTS: dict[str, tuple[str, str, str, str, str]] = {
    "openai": (
        "OpenAI",
        "https://api.openai.com/v1",
        "gpt-5",
        "json_schema",
        "platform.openai.com/api-keys",
    ),
    "deepseek": (
        "DeepSeek",
        "https://api.deepseek.com/v1",
        "deepseek-reasoner",
        "json_object",
        "platform.deepseek.com/api_keys",
    ),
    "groq": (
        "Groq",
        "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile",
        "json_schema",
        "console.groq.com/keys",
    ),
    "xai": (
        "xAI",
        "https://api.x.ai/v1",
        "grok-4",
        "json_schema",
        "console.x.ai",
    ),
    "openrouter": (
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        "anthropic/claude-opus-4.1",
        "json_schema",
        "openrouter.ai/keys",
    ),
    "github": (
        "GitHub Models",
        "https://models.github.ai/inference",
        "openai/gpt-5",
        "json_schema",
        "github.com/settings/personal-access-tokens",
    ),
}

# Reasoning-effort support is per-model, not per-provider, and sending the field
# to a model that doesn't take it is a 400. Only the families known to accept it
# get it.
_EFFORT_PREFIXES = ("gpt-5", "o1", "o3", "o4", "grok-4", "openai/gpt-5", "openai/o")

_EFFORT_MAP = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}


def _supports_effort(model: str) -> bool:
    return model.startswith(_EFFORT_PREFIXES)


def complete(
    *,
    provider: str,
    key: str,
    model: str,
    effort: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    base_url: str = "",
    schema_name: str = "resume",
    **_: Any,
) -> dict[str, Any]:
    label, default_base, _default_model, tier, console = ENDPOINTS.get(
        provider, ("OpenAI-compatible endpoint", "", "", "json_object", "")
    )
    base = (base_url or default_base).rstrip("/")
    if not base:
        raise UpstreamError(
            f"No base URL configured for provider {provider!r}.",
            hint="Set ACHILLES_BASE_URL to the endpoint's /v1 root.",
        )

    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    if tier == "json_schema":
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        }
    else:
        # No constrained decoding available, so the schema has to travel in the
        # prompt. The API requires the literal word "json" in a message for
        # json_object mode, which the appended instruction satisfies.
        body["response_format"] = {"type": "json_object"}
        body["messages"][1]["content"] = (
            f"{user}\n\nReturn a single json object matching this schema exactly, "
            f"with no commentary and no markdown fence:\n{json.dumps(schema)}"
        )

    if _supports_effort(model):
        body["reasoning_effort"] = _EFFORT_MAP.get(effort, "high")

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        # OpenRouter attributes traffic by these; harmless everywhere else, but
        # only sent where it means something.
        headers["HTTP-Referer"] = "https://github.com/Mulla759/Achilles"
        headers["X-Title"] = "Achilles"

    payload = post_json(
        f"{base}/chat/completions",
        headers=headers,
        body=body,
        label=label,
        key=key,
        console=console,
    )

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise UpstreamError(f"{label} returned no choices.")
    choice = choices[0] or {}

    if choice.get("finish_reason") == "content_filter":
        raise UpstreamError(
            f"{label} filtered this request.",
            hint="This usually means the pasted text tripped a safety filter. Try "
            "again with just the resume and job description.",
        )

    message = choice.get("message") or {}
    if message.get("refusal"):
        raise UpstreamError(
            "The model declined this request.",
            hint=str(message["refusal"])[:200],
        )

    content = message.get("content")
    if isinstance(content, list):
        # Some gateways return the multimodal content-array shape even for text.
        content = "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    if not isinstance(content, str) or not content.strip():
        if choice.get("finish_reason") == "length":
            raise UpstreamError(
                "The model hit its output limit before finishing the resume.",
                hint="Trim the source resume, or use a model with a larger output limit.",
            )
        raise UpstreamError(f"{label} returned an empty message.")

    return loads_or_raise(content, label=label)
