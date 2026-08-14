"""Typed errors.

Every failure the user can actually cause gets its own class with an
`http_status`, so the API layer maps errors to responses without string
matching. `hint` is written for a student staring at a red box, not a stack
trace.
"""

from __future__ import annotations


class AchillesError(Exception):
    """Base for everything this package raises deliberately."""

    http_status = 500
    code = "internal_error"

    def __init__(self, message: str, *, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def to_dict(self) -> dict:
        return {"error": self.code, "message": self.message, "hint": self.hint}


class InputError(AchillesError):
    """The user gave us something we can't work with."""

    http_status = 400
    code = "bad_input"


class MissingKeyError(AchillesError):
    """No Anthropic API key available from any source."""

    http_status = 401
    code = "missing_api_key"

    def __init__(self, message: str = "No Anthropic API key configured.") -> None:
        super().__init__(
            message,
            hint=(
                "Set ANTHROPIC_API_KEY in .env.local, or paste your own key into "
                "the key field. Get one at console.anthropic.com/settings/keys."
            ),
        )


class UpstreamError(AchillesError):
    """The Claude API refused, rate-limited, or fell over."""

    http_status = 502
    code = "upstream_error"


class RenderError(AchillesError):
    """Typst could not compile the generated source."""

    http_status = 500
    code = "render_failed"

    def __init__(self, message: str, *, source: str = "") -> None:
        super().__init__(
            message,
            hint="This is a template bug, not your input. The Typst error is in `message`.",
        )
        self.source = source


class GroundingError(AchillesError):
    """The model invented a claim that isn't in the source resume."""

    http_status = 422
    code = "ungrounded_claim"
