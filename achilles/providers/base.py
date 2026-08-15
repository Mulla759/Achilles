"""What every provider backend has to supply, and the HTTP plumbing they share.

A backend's whole job is: take a system prompt, a user prompt, and a JSON
schema; come back with a dict that validates against that schema. Everything
above this line — the tailoring prompt, the rubric, the render loop — is
provider-agnostic and stays that way.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..errors import UpstreamError
from .keys import redact

# A tailor call on a reasoning model legitimately runs a couple of minutes. The
# ceiling exists to catch a hung socket, not to bound the model's thinking.
TIMEOUT = httpx.Timeout(600.0, connect=15.0)

# The completion callable each backend exports.
Complete = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class Provider:
    """One place to send a prompt.

    `default_model` matters more than it looks: the rubric was calibrated on
    Opus 5, so every other provider's default is chosen as that provider's
    closest frontier model rather than its cheapest one. A weak default here
    shows up later as a mysterious `semantics` gate failure.
    """

    id: str
    label: str
    default_model: str
    env_vars: tuple[str, ...]
    complete: Complete
    console: str = ""
    notes: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)


def _message(payload: Any, status: int) -> str:
    """Pull the human-readable bit out of whatever error shape came back."""
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            for key in ("message", "detail", "code"):
                if isinstance(err.get(key), str) and err[key].strip():
                    return err[key].strip()
        if isinstance(err, str) and err.strip():
            return err.strip()
        for key in ("message", "detail"):
            if isinstance(payload.get(key), str) and payload[key].strip():
                return payload[key].strip()
    if isinstance(payload, list) and payload:
        return _message(payload[0], status)
    return f"HTTP {status}"


def post_json(
    url: str,
    *,
    headers: dict[str, str],
    body: dict[str, Any],
    label: str,
    key: str,
    console: str = "",
) -> dict[str, Any]:
    """POST JSON, or raise a typed `UpstreamError` explaining what went wrong.

    Every failure path here is mapped to the same vocabulary the Anthropic SDK
    path produces, so callers — and the HTTP layer's status mapping — cannot
    tell which backend failed.
    """
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=TIMEOUT)
    except httpx.TimeoutException as exc:
        raise UpstreamError(
            f"{label} timed out.",
            hint="The model was still working after 10 minutes. Try again, or use "
            "fewer passes.",
        ) from exc
    except httpx.HTTPError as exc:
        raise UpstreamError(
            f"Could not reach {label}.",
            hint="Check your network connection and any proxy settings.",
        ) from exc

    if response.status_code >= 400:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        detail = _message(payload, response.status_code)

        if response.status_code in (401, 403):
            raise UpstreamError(
                f"{label} rejected the API key ({redact(key)}).",
                hint="Check the key is current and has credit"
                + (f" at {console}." if console else "."),
            )
        if response.status_code == 429:
            raise UpstreamError(
                f"Rate limited by {label}.",
                hint="Wait a moment and try again, or supply your own API key.",
            )
        if response.status_code == 404:
            raise UpstreamError(
                f"{label} does not recognise that model.",
                hint="Set ACHILLES_MODEL to a model this key can reach.",
            )
        raise UpstreamError(f"{label} error ({response.status_code}): {detail}")

    try:
        return response.json()
    except ValueError as exc:
        raise UpstreamError(f"{label} returned a non-JSON response.") from exc


def loads_or_raise(text: str, *, label: str) -> dict[str, Any]:
    """Parse model output that is supposed to be JSON.

    Structured-output modes make this near-impossible to hit, but "near" is not
    "never" — a truncated response from hitting the token ceiling lands here —
    and a raw `JSONDecodeError` surfacing as a 500 would be the wrong answer.
    """
    text = (text or "").strip()
    if not text:
        raise UpstreamError(
            f"{label} returned an empty response.",
            hint="This is usually a transient upstream problem. Try again.",
        )
    # Some models still fence their JSON despite being asked not to.
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UpstreamError(
            f"{label} returned malformed JSON: {exc}.",
            hint="The response was probably cut off. Try again, or use a model with "
            "a larger output limit.",
        ) from exc
    if not isinstance(parsed, dict):
        raise UpstreamError(f"{label} returned {type(parsed).__name__}, expected an object.")
    return parsed
