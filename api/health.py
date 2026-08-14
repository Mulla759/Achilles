from __future__ import annotations

import os
from typing import Any

from _lib import flag, json_route

from achilles import __version__
from achilles.config import DEFAULT_MODEL
from achilles.render import active_backend


def _health(_body: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "version": __version__,
        "model": os.environ.get("ACHILLES_MODEL") or DEFAULT_MODEL,
        "renderer": active_backend(),
        "byo_key_only": flag("ACHILLES_BYO_KEY_ONLY"),
        "server_key": bool((os.environ.get("ANTHROPIC_API_KEY") or "").strip()),
    }


handler = json_route(_health)
