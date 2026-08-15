"""Key-shape detection: which provider is this, and is it even an LLM key?

People paste whatever key is on the clipboard, and often it is the right key for
the wrong service — a GitHub PAT, a Stripe secret, an AWS access key. Every one
of those fails upstream as a generic 401 that teaches nobody anything, a network
round trip and thirty seconds later. Prefixes are cheap, so we check them first
and say exactly what went wrong.

The check is deliberately asymmetric:

* A key we can *positively* identify as belonging to a non-LLM service is
  refused up front. `AKIA...` is never going to tailor a resume.
* A key we recognise as an LLM provider's selects that provider.
* An unrecognised shape is **not** refused. New providers appear faster than
  this table gets updated, so an unknown key falls through to whatever provider
  was configured and is allowed to fail honestly upstream.

Nothing here validates a key against the network. That costs a round trip and,
more to the point, a wrong answer here is recoverable while a false rejection is
not.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------
# Shapes
# --------------------------------------------------------------------------

# Longest / most specific prefixes first — "sk-ant-" must beat the bare "sk-"
# fallback, and "sk-or-v1-" (OpenRouter) must beat both.
_LLM_PREFIXES: tuple[tuple[str, str, str], ...] = (
    # prefix, provider id, human label
    ("sk-ant-", "anthropic", "Anthropic"),
    ("sk-or-v1-", "openrouter", "OpenRouter"),
    ("sk-proj-", "openai", "OpenAI"),
    ("sk-svcacct-", "openai", "OpenAI"),
    ("sk-None-", "openai", "OpenAI"),
    ("AIza", "google", "Google AI Studio"),
    ("gsk_", "groq", "Groq"),
    ("xai-", "xai", "xAI"),
    ("github_pat_", "github", "GitHub Models"),
    ("ghp_", "github", "GitHub Models"),
    ("gho_", "github", "GitHub Models"),
    ("ghu_", "github", "GitHub Models"),
    ("ghs_", "github", "GitHub Models"),
)

# Keys that are definitely real credentials for something, and definitely not
# something we can send a prompt to. Refusing these is the whole point of the
# gate: the failure is obvious to us and baffling to the person pasting.
_NOT_LLM: tuple[tuple[str, str], ...] = (
    ("AKIA", "an AWS access key ID"),
    ("ASIA", "a temporary AWS access key ID"),
    ("sk_live_", "a Stripe live secret key"),
    ("sk_test_", "a Stripe test secret key"),
    ("rk_live_", "a Stripe restricted key"),
    ("pk_live_", "a Stripe publishable key"),
    ("pk_test_", "a Stripe publishable key"),
    ("xoxb-", "a Slack bot token"),
    ("xoxp-", "a Slack user token"),
    ("xapp-", "a Slack app token"),
    ("glpat-", "a GitLab personal access token"),
    ("ya29.", "a Google OAuth access token"),
    ("npm_", "an npm access token"),
    ("SG.", "a SendGrid API key"),
    ("shpat_", "a Shopify access token"),
    ("dop_v1_", "a DigitalOcean token"),
    ("-----BEGIN", "a PEM private key"),
    ("eyJ", "a JWT"),
)

# DeepSeek issues `sk-` followed by 32 lowercase hex characters. OpenAI's legacy
# keys are `sk-` plus ~48 mixed-case alphanumerics, and its current ones carry an
# explicit `sk-proj-` / `sk-svcacct-` prefix. That makes the hex run the one
# reliable tell between the two, and it is the only reason a bare `sk-` key can
# be routed at all.
_DEEPSEEK_SHAPE = re.compile(r"^sk-[0-9a-f]{32}$")

# Google AI Studio keys are a fixed 39 characters. Worth checking separately
# from the prefix so a truncated paste is caught here rather than upstream.
_GOOGLE_SHAPE = re.compile(r"^AIza[0-9A-Za-z_-]{35}$")

_WHITESPACE = re.compile(r"\s")


@dataclass(frozen=True)
class KeyIdentity:
    """What we could work out about a pasted key without calling anyone.

    `provider` is empty when the key is unusable; `reason` then explains why in
    words meant for the person who pasted it. `confident` is False when the
    shape only narrowed the field rather than settling it — a bare `sk-` key
    routed to OpenAI by elimination, say — which is the caller's cue to let an
    explicit override win.
    """

    provider: str
    label: str
    confident: bool = True
    reason: str = ""
    hint: str = ""

    @property
    def usable(self) -> bool:
        return bool(self.provider)


def redact(key: str) -> str:
    """A key rendered safe to put in an error message or a log line.

    Keeps the prefix, because the prefix is the diagnostic — it is what tells
    you the key is a GitHub token — and the last four characters, which is
    enough for someone holding three keys to tell which one they pasted. The
    secret bearer portion never survives this function.
    """
    key = (key or "").strip()
    if not key:
        return "(empty)"
    head = ""
    for prefix, _, _ in _LLM_PREFIXES:
        if key.startswith(prefix):
            head = prefix
            break
    if not head:
        for prefix, _ in _NOT_LLM:
            if key.startswith(prefix):
                head = prefix
                break
    if not head:
        head = key[:3]
    tail = key[-4:] if len(key) > len(head) + 8 else ""
    return f"{head}…{tail}" if tail else f"{head}…"


def identify(raw: str) -> KeyIdentity:
    """Classify a pasted key by shape alone."""
    key = (raw or "").strip().strip("'\"")

    if not key:
        return KeyIdentity(
            provider="",
            label="",
            reason="No API key was provided.",
            hint="Paste a key from any supported provider, or set one in .env.local.",
        )

    if _WHITESPACE.search(key):
        return KeyIdentity(
            provider="",
            label="",
            reason="That key contains a space or line break, so it was probably "
            "copied with something extra attached.",
            hint="Re-copy just the key itself, with no surrounding quotes or text.",
        )

    for prefix, service in _NOT_LLM:
        if key.startswith(prefix):
            return KeyIdentity(
                provider="",
                label="",
                reason=f"That looks like {service} ({redact(key)}), not a key for an "
                "AI provider.",
                hint="Achilles needs a key from Anthropic, OpenAI, Google, DeepSeek, "
                "Groq, xAI, OpenRouter, or GitHub Models.",
            )

    for prefix, provider, label in _LLM_PREFIXES:
        if key.startswith(prefix):
            if provider == "google" and not _GOOGLE_SHAPE.fullmatch(key):
                return KeyIdentity(
                    provider="",
                    label=label,
                    reason=f"That looks like a Google AI Studio key but it is "
                    f"{len(key)} characters, not the expected 39.",
                    hint="Copy the whole key from aistudio.google.com/apikey.",
                )
            return KeyIdentity(provider=provider, label=label)

    if _DEEPSEEK_SHAPE.fullmatch(key):
        return KeyIdentity(provider="deepseek", label="DeepSeek")

    if key.startswith("sk-"):
        # Everything left in `sk-` space is an OpenAI legacy key or a
        # self-hosted gateway imitating one. Route it to OpenAI but flag the
        # guess, so an explicit provider setting overrides it.
        return KeyIdentity(provider="openai", label="OpenAI", confident=False)

    return KeyIdentity(
        provider="",
        label="",
        confident=False,
        reason=f"Unrecognised API key format ({redact(key)}).",
        hint="Set ACHILLES_PROVIDER to name the provider explicitly if this key is "
        "for a gateway or a self-hosted endpoint.",
    )
