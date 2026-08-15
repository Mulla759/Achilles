"""Runtime configuration.

Credential resolution lives in `achilles/providers/__init__.py` — this module's
job is to read the environment and hand it over. The order, first match wins:

  1. a key passed in explicitly (the visitor's own, from the UI, CLI, or TUI)
  2. `ACHILLES_API_KEY`, provider-neutral
  3. each provider's conventional variable (`ANTHROPIC_API_KEY`,
     `OPENAI_API_KEY`, `GEMINI_API_KEY`, …)

The provider is inferred from the key's shape unless `ACHILLES_PROVIDER` names
one. BYO-key-only mode (`ACHILLES_BYO_KEY_ONLY=1`) skips steps 2 and 3, so a
public deploy never spends the owner's credits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .providers import Resolution, resolve

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "typist.typ"

# Left unset, each provider supplies its own default model. Pinning one here
# would be wrong the moment the provider changes — `claude-opus-5` is not a
# model Gemini can serve.
DEFAULT_EFFORT = "high"

# Ceiling on tailor -> render -> grade cycles. Each pass costs one model call;
# in practice pass 2 closes most gaps and pass 3 is the long tail.
DEFAULT_MAX_PASSES = 3


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str) -> str:
    return (os.environ.get(name) or "").strip()


@dataclass
class Settings:
    # Empty means "whatever the resolved provider's default is". An explicit
    # ACHILLES_MODEL always wins, including across a provider switch — which is
    # how you run, say, Sonnet instead of Opus without touching anything else.
    model: str = field(default_factory=lambda: _env("ACHILLES_MODEL"))
    provider: str = field(default_factory=lambda: _env("ACHILLES_PROVIDER"))
    base_url: str = field(default_factory=lambda: _env("ACHILLES_BASE_URL"))
    effort: str = field(default_factory=lambda: _env("ACHILLES_EFFORT") or DEFAULT_EFFORT)
    max_passes: int = field(
        default_factory=lambda: int(os.environ.get("ACHILLES_MAX_PASSES") or DEFAULT_MAX_PASSES)
    )
    byo_key_only: bool = field(default_factory=lambda: _flag("ACHILLES_BYO_KEY_ONLY"))
    template: Path = DEFAULT_TEMPLATE

    def resolve(
        self, user_key: str | None = None, *, provider: str | None = None
    ) -> Resolution:
        """Settle who we are calling, with which key, on which model."""
        return resolve(
            api_key=user_key,
            provider=provider or self.provider,
            model=self.model,
            effort=self.effort,
            base_url=self.base_url,
            byo_key_only=self.byo_key_only,
        )


def load_dotenv(path: Path | None = None) -> None:
    """Load `.env.local` into the environment if present.

    Next.js reads `.env.local` automatically, so without this the web app would
    see the key and the CLI would not — a confusing split where `npm run dev`
    works but `achilles tailor` reports a missing key. Existing environment
    variables always win, so an explicit `ANTHROPIC_API_KEY=... achilles ...`
    still overrides the file.
    """
    env_file = path or (ROOT / ".env.local")
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def load_settings() -> Settings:
    load_dotenv()
    return Settings()
