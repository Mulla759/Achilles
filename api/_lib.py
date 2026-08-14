"""Shared plumbing for the Vercel Python functions.

Vercel's Python runtime hands us a `BaseHTTPRequestHandler`, so there is no
framework doing JSON parsing, error mapping, or CORS. This module is that layer,
kept in one place so each endpoint file is just its own logic.

Files prefixed with `_` are not routed by Vercel, so this is importable but not
reachable over HTTP.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import uuid
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from pydantic import ValidationError

# The function bundle puts `achilles/` and `templates/` next to `api/` (see
# includeFiles in vercel.json); make the package importable either way.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from _guard import check_rate_limit, client_ip, cors_origin  # noqa: E402

from achilles.errors import AchillesError, InputError  # noqa: E402
from achilles.models import Resume  # noqa: E402

MAX_BODY_BYTES = 1_000_000  # a pasted JD + resume is ~20KB; 1MB is generous


def _send(
    handler: BaseHTTPRequestHandler,
    status: int,
    payload: dict[str, Any],
    *,
    retry_after: float | None = None,
) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")

    # CORS is opt-in, not wildcard. The bundled UI is same-origin so it needs no
    # CORS header at all; a wildcard here would let any page on the internet
    # drive /api/tailor and spend this deployment's API credits.
    origin = cors_origin(handler.headers.get("Origin"))
    if origin:
        handler.send_header("Access-Control-Allow-Origin", origin)
        handler.send_header("Vary", "Origin")
        handler.send_header("Access-Control-Allow-Headers", "Content-Type")
        handler.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")

    # Defence-in-depth on a JSON API: nothing here should ever be framed,
    # sniffed into another content type, or leak a referrer to a third party.
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("X-Frame-Options", "DENY")

    if retry_after is not None:
        handler.send_header("Retry-After", str(max(1, int(retry_after))))

    handler.end_headers()
    handler.wfile.write(body)


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    if length > MAX_BODY_BYTES:
        raise InputError(
            "Request body too large.",
            hint="The JD plus resume should be well under 1 MB of text.",
        )
    raw = handler.rfile.read(length)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InputError(
            f"Body is not valid JSON: {exc}",
            hint="Send a JSON object with Content-Type: application/json.",
        ) from exc
    if not isinstance(data, dict):
        raise InputError(
            "Body must be a JSON object.",
            hint='Expected something like {"jd_text": "...", "resume_text": "..."}.',
        )
    return data


def json_route(
    fn: Callable[[dict[str, Any]], dict[str, Any]],
    *,
    limit_for: Callable[[dict[str, Any]], int] | None = None,
    route: str = "",
) -> type[BaseHTTPRequestHandler]:
    """Wrap a plain `dict -> dict` function into a Vercel handler class.

    `limit_for` receives the parsed body and returns this request's per-minute
    cap, so an endpoint can charge a stricter rate when the caller is spending
    the server's API key rather than their own.
    """

    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            _send(self, 204, {})

        def do_GET(self) -> None:  # noqa: N802
            self._run({})

        def do_POST(self) -> None:  # noqa: N802
            try:
                body = _read_json(self)
            except AchillesError as exc:
                _send(self, exc.http_status, exc.to_dict())
                return

            if limit_for is not None:
                retry_after = check_rate_limit(
                    f"{route}:{client_ip(self)}", limit_for(body)
                )
                if retry_after is not None:
                    _send(
                        self,
                        429,
                        {
                            "error": "rate_limited",
                            "message": "Too many requests.",
                            "hint": (
                                f"Wait {max(1, int(retry_after))}s and try again. "
                                "Supplying your own API key raises the limit."
                            ),
                        },
                        retry_after=retry_after,
                    )
                    return
            self._run(body)

        def _run(self, body: dict[str, Any]) -> None:
            try:
                _send(self, 200, fn(body))
            except AchillesError as exc:
                _send(self, exc.http_status, exc.to_dict())
            except Exception:
                # The exception *message* is not safe to return. Typst errors
                # carry absolute template paths, upstream SDK errors carry
                # request internals, and a KeyError leaks field names — all of
                # which map the server for an attacker. Log it with an id and
                # hand the caller only that id.
                incident = uuid.uuid4().hex[:12]
                print(
                    f"UNHANDLED [{incident}] {route or 'route'}:\n{traceback.format_exc()}",
                    file=sys.stderr,
                )
                _send(
                    self,
                    500,
                    {
                        "error": "internal_error",
                        "message": "Something broke on our side.",
                        "hint": (
                            "This is a bug in Achilles, not your input. Quote "
                            f"incident {incident} if you report it."
                        ),
                        "incident": incident,
                    },
                )

        def log_message(self, *args: Any) -> None:
            # Silence the default stderr access log; Vercel already logs requests.
            pass

    return Handler


def require_str(
    body: dict[str, Any],
    key: str,
    *,
    required: bool = False,
    min_len: int = 0,
    message: str | None = None,
    hint: str | None = None,
) -> str:
    """Pull a stripped string out of a JSON body, or raise `InputError` (400).

    Request JSON is user-controlled and untyped: `body[key]` can be a list, a
    dict, a number, anything. Without this check that value rides straight
    into `.strip()` and blows up as an uncaught `AttributeError` -> 500,
    instead of the documented 400 `bad_input`.
    """
    value = body.get(key)
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise InputError(
            message or f"'{key}' must be a string, got {type(value).__name__}.",
            hint=hint or f"Send '{key}' as plain text.",
        )
    value = value.strip()
    if required and not value:
        raise InputError(
            message or f"'{key}' is required.",
            hint=hint or f"Provide a non-empty '{key}'.",
        )
    if min_len and len(value) < min_len:
        raise InputError(
            message or f"'{key}' must be at least {min_len} characters.",
            hint=hint or f"Provide a longer '{key}' (at least {min_len} characters).",
        )
    return value


def parse_resume_field(body: dict[str, Any]) -> Resume | None:
    """Validate `body['resume']` into a `Resume`, or raise `InputError` (400).

    `Resume.model_validate()` raises `pydantic.ValidationError`, not an
    `AchillesError`, so left uncaught it falls through `json_route`'s handler
    to the generic `except Exception` branch and comes back as a 500
    `internal_error` instead of the documented 400 `bad_input`. Catch it here,
    at the point of parsing, so every caller gets the 400 for free.
    """
    raw = body.get("resume")
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise InputError(
            f"'resume' must be a JSON object, got {type(raw).__name__}.",
            hint="Send 'resume' as a Resume object (see docs/API.md), or use resume_text instead.",
        )
    try:
        return Resume.model_validate(raw)
    except ValidationError as exc:
        # Summarize the first few field errors with their location, e.g.
        # "contact.name: Field required" -- readable without a stack trace.
        details = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '<root>'}: {err['msg']}"
            for err in exc.errors()[:3]
        )
        raise InputError(
            f"'resume' does not match the Resume schema: {details}",
            hint="Check the field(s) named above against the Resume schema in docs/API.md.",
        ) from exc


def flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def scan_payload(report: Any) -> dict[str, Any]:
    """ScanReport's percentages are computed properties, so `model_dump()` alone
    would drop exactly the numbers the UI renders."""
    return {
        **report.model_dump(),
        "score": report.score,
        "required_score": report.required_score,
        "matched": report.matched,
        "total": report.total,
        "gaps": report.gaps,
    }


def build_payload(result: Any) -> dict[str, Any]:
    return {
        "ready": result.ready,
        "pages": result.pages,
        "passes": result.passes,
        "resume": result.resume.model_dump(),
        "source_resume": (
            result.source_resume.model_dump() if result.source_resume else None
        ),
        "typst_source": result.typst_source,
        "pdf_b64": result.pdf_b64,
        "text": result.text,
        "scan": scan_payload(result.scan),
        "rubric": {**result.rubric.model_dump(), "passed": result.rubric.passed,
                   "score": result.rubric.score},
        "notes": result.notes,
    }
