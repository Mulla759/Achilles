"""Runtime configuration.

Key resolution order, first match wins:
  1. a key passed in explicitly (the visitor's own, from the UI)
  2. ANTHROPIC_API_KEY in the environment

BYO-key-only mode (`ACHILLES_BYO_KEY_ONLY=1`) skips step 2, so a public deploy
never spends the owner's credits.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import MissingKeyError

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "templates"
DEFAULT_TEMPLATE = TEMPLATE_DIR / "typist.typ"

# Tuned on Opus 5. The rubric thresholds below assume this model's calibration;
# dropping to a smaller model tends to fail the `semantics` gate more often.
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "high"

# Ceiling on tailor -> render -> grade cycles. Each pass costs one Claude call;
# in practice pass 2 closes most gaps and pass 3 is the long tail.
DEFAULT_MAX_PASSES = 3


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    model: str = field(default_factory=lambda: os.environ.get("ACHILLES_MODEL") or DEFAULT_MODEL)
    effort: str = field(default_factory=lambda: os.environ.get("ACHILLES_EFFORT") or DEFAULT_EFFORT)
    max_passes: int = field(
        default_factory=lambda: int(os.environ.get("ACHILLES_MAX_PASSES") or DEFAULT_MAX_PASSES)
    )
    byo_key_only: bool = field(default_factory=lambda: _flag("ACHILLES_BYO_KEY_ONLY"))
    template: Path = DEFAULT_TEMPLATE

    def resolve_key(self, user_key: str | None = None) -> str:
        key = (user_key or "").strip()
        if key:
            return key
        if self.byo_key_only:
            raise MissingKeyError(
                "This deployment requires you to bring your own Anthropic API key."
            )
        env = (os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        if env:
            return env
        raise MissingKeyError()


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
