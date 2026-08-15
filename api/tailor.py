"""The main endpoint: rewrite -> render -> grade.

Defaults to a single pass because Vercel caps this function at 60s (see
vercel.json) and one Opus 5 pass runs 30-50s. The client refines by POSTing the
returned `resume` back in — each call is then one pass and stays inside the
budget. Raise `maxDuration` and `max_passes` together if you are on a plan that
allows longer functions.
"""

from __future__ import annotations

from typing import Any

from _guard import SERVER_KEY_TAILOR_LIMIT, TAILOR_LIMIT
from _lib import build_payload, json_route, parse_resume_field, require_str

from achilles.config import load_settings
from achilles.errors import InputError
from achilles.pipeline import build

SERVERLESS_DEFAULT_PASSES = 1
MIN_MAX_PASSES = 1
MAX_MAX_PASSES = 5


def _parse_max_passes(requested: Any) -> int:
    """Validate/coerce the optional `max_passes` request field into 1..5.

    `str.isdigit()` alone is not a safe gate for `int()`: it also returns
    True for non-ASCII "digit" characters such as "²" (superscript two),
    which satisfy `.isdigit()` but make `int()` raise `ValueError` -- turning
    a bad request into an internal 500 instead of the documented 400
    `bad_input`. We require the string to be ASCII on top of `.isdigit()` so
    only real base-10 digit strings ("3", "10") get through to `int()`.

    `bool` is deliberately rejected even though Python treats it as an `int`
    subclass (`isinstance(True, int)` is `True`), so a stray `true` in the
    JSON body doesn't silently become `max_passes=1`. Values that parse but
    fall outside 1..5 -- including 0, which `build()` would otherwise treat
    as falsy and silently replace with `settings.max_passes` -- are rejected
    here rather than clamped, so the caller finds out their request was
    ignored instead of getting a different pass count than they asked for.
    """
    if requested is None:
        return SERVERLESS_DEFAULT_PASSES

    range_hint = f"Send max_passes as an integer between {MIN_MAX_PASSES} and {MAX_MAX_PASSES}."

    if isinstance(requested, bool):
        raise InputError(
            "max_passes must be an integer, not a boolean.",
            hint=range_hint,
        )

    if isinstance(requested, int):
        value = requested
    elif isinstance(requested, str) and requested.isascii() and requested.isdigit():
        value = int(requested)
    else:
        raise InputError(
            f"max_passes must be an integer between {MIN_MAX_PASSES} and {MAX_MAX_PASSES}, "
            f"got {requested!r}.",
            hint=range_hint,
        )

    if not (MIN_MAX_PASSES <= value <= MAX_MAX_PASSES):
        raise InputError(
            f"max_passes must be between {MIN_MAX_PASSES} and {MAX_MAX_PASSES}, got {value}.",
            hint=range_hint,
        )
    return value


def _tailor(body: dict[str, Any]) -> dict[str, Any]:
    jd_text = require_str(body, "jd_text")
    target_role = require_str(body, "target_role")
    resume_text = require_str(body, "resume_text")
    resume = parse_resume_field(body)

    if not resume and not resume_text:
        raise InputError(
            "No resume provided.",
            hint="Paste your current resume into the resume box.",
        )

    availability = require_str(body, "availability")
    api_key = require_str(body, "api_key")
    provider = require_str(body, "provider")
    model = require_str(body, "model")
    passes = _parse_max_passes(body.get("max_passes"))

    settings = load_settings()
    if model:
        # Per-request model override. Only honoured alongside a caller-supplied
        # key: letting an anonymous request pick the model would let anyone
        # spend the server's credits on the most expensive one available.
        if not api_key:
            raise InputError(
                "A model can only be chosen when you bring your own API key.",
                hint="Add your key to the request, or drop the `model` field to use "
                "this deployment's default.",
            )
        settings.model = model

    result = build(
        jd_text=jd_text,
        target_role=target_role,
        resume=resume,
        resume_text=resume_text or None,
        availability=availability,
        api_key=api_key or None,
        provider=provider or None,
        settings=settings,
        max_passes=passes,
    )
    return build_payload(result)


def _limit_for(body: dict[str, Any]) -> int:
    """A caller spending their own key is rate-limited far more loosely than one
    spending ours — the cost of abuse is what differs, not the work done."""
    supplied_own_key = bool(str(body.get("api_key") or "").strip())
    return TAILOR_LIMIT if supplied_own_key else SERVER_KEY_TAILOR_LIMIT


handler = json_route(_tailor, limit_for=_limit_for, route="tailor")
