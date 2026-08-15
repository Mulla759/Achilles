"""The provider registry: one key in, one validated `Resume` out.

Everything above this package — the tailoring prompt, the rubric, the render
loop — is provider-agnostic. This is the only place that knows Anthropic from
Gemini.

Resolution order, first match wins:

  1. a key passed in explicitly (the visitor's own, from the UI, CLI, or TUI)
  2. `ACHILLES_API_KEY` — provider-neutral, for people who switch often
  3. each provider's conventional variable, in `_ENV_ORDER`

The provider is then inferred from the key's shape unless `ACHILLES_PROVIDER`
names one, which is the escape hatch for gateways and self-hosted endpoints
whose keys look like nothing in particular.

A caveat worth repeating from the README: the rubric was calibrated against
Opus 5. Other models tailor perfectly well but tend to fail the `semantics`
gate more often, which costs an extra repair pass.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from ..errors import InputError, MissingKeyError, UpstreamError
from . import anthropic_api, google_api, openai_api
from .base import Provider
from .keys import KeyIdentity, identify, redact
from .schema import google_schema, openai_schema

__all__ = [
    "KeyIdentity",
    "Provider",
    "REGISTRY",
    "Resolution",
    "describe",
    "identify",
    "provider_ids",
    "redact",
    "resolve",
    "structured_call",
]


def _openai_family(provider_id: str) -> Provider:
    label, _base, model, _tier, console = openai_api.ENDPOINTS[provider_id]
    return Provider(
        id=provider_id,
        label=label,
        default_model=model,
        env_vars=_ENV_VARS[provider_id],
        complete=openai_api.complete,
        console=console,
    )


# Conventional environment variables per provider. GITHUB_TOKEN is deliberately
# absent: CI sets it automatically for unrelated reasons, and silently routing a
# build's Actions token to an inference endpoint is a surprise nobody wants.
# GitHub Models has to be opted into by name.
_ENV_VARS: dict[str, tuple[str, ...]] = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "google": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "groq": ("GROQ_API_KEY",),
    "xai": ("XAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "github": ("GITHUB_MODELS_TOKEN",),
}

REGISTRY: dict[str, Provider] = {
    "anthropic": Provider(
        id="anthropic",
        label="Anthropic",
        default_model=anthropic_api.DEFAULT_MODEL,
        env_vars=_ENV_VARS["anthropic"],
        complete=anthropic_api.complete,
        console=f"{anthropic_api.CONSOLE}/settings/keys",
        notes="The reference backend. The rubric thresholds are calibrated here.",
        aliases=("claude",),
    ),
    "google": Provider(
        id="google",
        label="Google AI Studio",
        default_model=google_api.DEFAULT_MODEL,
        env_vars=_ENV_VARS["google"],
        complete=google_api.complete,
        console=google_api.CONSOLE,
        aliases=("gemini",),
    ),
    "openai": _openai_family("openai"),
    "deepseek": _openai_family("deepseek"),
    "groq": _openai_family("groq"),
    "xai": _openai_family("xai"),
    "openrouter": _openai_family("openrouter"),
    "github": _openai_family("github"),
}

# The order environment variables are consulted in. Anthropic leads because it
# is the calibrated path, so a machine holding several keys gets the best
# results by default rather than whichever key sorts first.
_ENV_ORDER = ("anthropic", "openai", "google", "deepseek", "groq", "xai", "openrouter", "github")

_ALIASES = {alias: p.id for p in REGISTRY.values() for alias in p.aliases}


def provider_ids() -> list[str]:
    return list(REGISTRY)


def describe() -> list[tuple[str, str, str]]:
    """(id, label, default model) for every provider — for `--help` and the TUI."""
    return [(p.id, p.label, p.default_model) for p in REGISTRY.values()]


def lookup(name: str) -> Provider:
    key = (name or "").strip().lower()
    key = _ALIASES.get(key, key)
    provider = REGISTRY.get(key)
    if provider is None:
        raise InputError(
            f"Unknown provider {name!r}.",
            hint=f"Supported: {', '.join(REGISTRY)}.",
        )
    return provider


@dataclass(frozen=True)
class Resolution:
    """Everything a call needs, settled: who, with what key, on which model."""

    provider: Provider
    key: str
    model: str
    effort: str
    base_url: str = ""
    # How we arrived at this provider, for the UI to show and for error messages
    # to quote. Never contains the key itself.
    source: str = ""

    @property
    def summary(self) -> str:
        return f"{self.provider.label} · {self.model} · key {redact(self.key)}"


def resolve(
    *,
    api_key: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    effort: str = "high",
    base_url: str = "",
    byo_key_only: bool = False,
    env: dict[str, str] | None = None,
) -> Resolution:
    """Settle provider, key, and model from the caller's input and the environment."""
    env = env if env is not None else dict(os.environ)
    explicit_provider = (provider or env.get("ACHILLES_PROVIDER") or "").strip()
    supplied = (api_key or "").strip().strip("'\"")

    key, source = supplied, "supplied key"
    if not key:
        if byo_key_only:
            raise MissingKeyError(
                "This deployment requires you to bring your own API key.",
            )
        neutral = (env.get("ACHILLES_API_KEY") or "").strip()
        if neutral:
            key, source = neutral, "ACHILLES_API_KEY"
        else:
            for pid in _ENV_ORDER:
                for var in REGISTRY[pid].env_vars:
                    candidate = (env.get(var) or "").strip()
                    if candidate:
                        key, source = candidate, var
                        break
                if key:
                    break

    if not key:
        raise MissingKeyError()

    identity = identify(key)

    if explicit_provider:
        chosen = lookup(explicit_provider)
        # An explicit setting always wins, but a confident shape mismatch is
        # worth saying out loud — it is nearly always a paste into the wrong
        # box, and the upstream 401 would not explain it.
        if identity.usable and identity.confident and identity.provider != chosen.id:
            raise InputError(
                f"ACHILLES_PROVIDER is {chosen.id!r}, but that key ({redact(key)}) "
                f"is {REGISTRY[identity.provider].label}'s.",
                hint=f"Either unset ACHILLES_PROVIDER, or supply a {chosen.label} key.",
            )
        # An unrecognised shape is fine here — naming the provider is exactly
        # the escape hatch for gateway and self-hosted keys.
    elif identity.usable:
        chosen = REGISTRY[identity.provider]
        source = f"{source} (detected as {chosen.label})"
    else:
        raise InputError(
            identity.reason or "That API key was not recognised.",
            hint=identity.hint
            or f"Supported providers: {', '.join(REGISTRY)}. Set ACHILLES_PROVIDER "
            "to name one explicitly.",
        )

    return Resolution(
        provider=chosen,
        key=key,
        model=(model or "").strip() or chosen.default_model,
        effort=effort,
        base_url=base_url or env.get("ACHILLES_BASE_URL", ""),
        source=source,
    )


def structured_call(
    *,
    resolution: Resolution,
    output_model: type[BaseModel],
    system: str,
    user: str,
) -> Any:
    """Run one structured completion and validate it into `output_model`.

    The schema dialect is chosen per provider; the validation at the end is the
    same for all of them, which is what keeps a provider that ignores its schema
    from silently producing a malformed resume.
    """
    provider = resolution.provider
    if provider.id == "google":
        schema = google_schema(output_model)
    else:
        schema = openai_schema(output_model)

    payload = provider.complete(
        provider=provider.id,
        key=resolution.key,
        model=resolution.model,
        effort=resolution.effort,
        system=system,
        user=user,
        schema=schema,
        base_url=resolution.base_url,
        output_model=output_model,
        schema_name=output_model.__name__.lower(),
    )

    try:
        return output_model.model_validate(payload)
    except ValidationError as exc:
        # Anthropic and OpenAI strict mode make this near-impossible; the
        # json_object tier makes it merely unlikely. Naming the provider matters
        # because switching providers is the usual fix.
        count = len(exc.errors())
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first.get("loc", ())) or "(root)"
        raise UpstreamError(
            f"{provider.label} returned a resume that does not match the schema "
            f"({count} problem(s); first at {where}: {first.get('msg', '')}).",
            hint="This model did not honour the output schema. Try again, or switch "
            "to a provider with strict structured output (Anthropic, OpenAI).",
        ) from exc
