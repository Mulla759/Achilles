from __future__ import annotations

from typing import Any

from _lib import flag, json_route

from achilles import __version__
from achilles.config import load_settings
from achilles.errors import AchillesError
from achilles.providers import describe, resolve
from achilles.render import active_backend


def _health(_body: dict[str, Any]) -> dict[str, Any]:
    settings = load_settings()
    provider, model, server_key = settings.provider, settings.model, False

    # Probe with `byo_key_only=False` deliberately: this field answers "is a
    # server key configured", not "will this deployment spend it". The UI reads
    # `byo_key_only` for the second question.
    try:
        resolution = resolve(
            provider=settings.provider,
            model=settings.model,
            effort=settings.effort,
            base_url=settings.base_url,
            byo_key_only=False,
        )
    except AchillesError:
        # No server key, or one whose provider we cannot place. Both are
        # supported deployments — a BYO-key host has no key by design — and the
        # UI still needs the rest of this payload to render its key field.
        pass
    else:
        provider, model, server_key = resolution.provider.id, resolution.model, True

    return {
        "ok": True,
        "version": __version__,
        # Empty when no server key resolves: the provider is then decided per
        # request, from whichever key the visitor brings.
        "provider": provider,
        "model": model,
        "providers": [{"id": pid, "label": label, "model": m} for pid, label, m in describe()],
        "renderer": active_backend(),
        "byo_key_only": flag("ACHILLES_BYO_KEY_ONLY"),
        "server_key": server_key,
    }


handler = json_route(_health)
