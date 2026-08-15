"""Anthropic — the reference backend.

The one backend that does not go through `base.post_json`. The SDK's
`messages.parse` already does schema enforcement, effort control, and typed
errors properly, and this is the path the rubric thresholds were calibrated
against. Treat its behaviour as the definition of correct and the other
backends as approximations of it.
"""

from __future__ import annotations

from typing import Any

import anthropic
from pydantic import BaseModel

from ..errors import UpstreamError
from .keys import redact

DEFAULT_MODEL = "claude-opus-5"
CONSOLE = "console.anthropic.com"

# Enough headroom for a full resume plus reasoning. A one-page resume is ~600
# tokens of JSON; the rest is thinking budget.
MAX_TOKENS = 20000


def complete(
    *,
    key: str,
    model: str,
    effort: str,
    system: str,
    user: str,
    schema: dict[str, Any],
    output_model: type[BaseModel],
    **_: Any,
) -> dict[str, Any]:
    client = anthropic.Anthropic(api_key=key, timeout=600.0)
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=MAX_TOKENS,
            # Byte-stable system prompt, so it caches across the passes of a
            # multi-pass build (Opus 5 caches from 512 tokens).
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_format=output_model,
            output_config={"effort": effort},
            messages=[{"role": "user", "content": user}],
        )
    except anthropic.AuthenticationError as exc:
        raise UpstreamError(
            f"Anthropic rejected the API key ({redact(key)}).",
            hint=f"Check the key is current and has credit at {CONSOLE}/settings/keys.",
        ) from exc
    except anthropic.RateLimitError as exc:
        raise UpstreamError(
            "Rate limited by the Anthropic API.",
            hint="Wait a moment and try again, or use your own API key.",
        ) from exc
    except anthropic.APIStatusError as exc:
        raise UpstreamError(f"Anthropic API error ({exc.status_code}): {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise UpstreamError("Could not reach the Anthropic API.") from exc

    if response.stop_reason == "refusal":
        raise UpstreamError(
            "The model declined this request.",
            hint="This usually means the pasted text tripped a safety filter. Try again "
            "with just the resume and job description.",
        )
    parsed = response.parsed_output
    if parsed is None:
        if response.stop_reason == "max_tokens":
            raise UpstreamError(
                "The model hit its output limit before finishing the resume.",
                hint="Trim the source resume — it is long enough that the rewrite does "
                "not fit in one response.",
            )
        raise UpstreamError("The model returned no structured output.")
    # The registry's contract is dicts in, dicts out, so the caller validates
    # once regardless of which backend produced the payload.
    return parsed.model_dump()
