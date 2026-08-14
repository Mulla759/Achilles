"""Abuse controls for the public endpoints.

The threat is specific and cheap to exploit. `/api/tailor` spends real money on
whoever's key the deployment is configured with, and before this module the
endpoints answered `Access-Control-Allow-Origin: *` with no rate limit — so any
page on the internet could run a loop against a deployment and drain the owner's
Anthropic credits. Nothing about that requires a vulnerability; it is just an
open, billable endpoint.

Three layers, cheapest first:

1. **Origin allowlist.** Same-origin browser requests (the real UI) send no
   `Origin` we need to answer, so the wildcard bought nothing and cost this.
2. **Rate limit** per client IP, stricter when the request is spending the
   *server's* key rather than a key the caller supplied.
3. **`ACHILLES_BYO_KEY_ONLY`** (in `config.py`) is the real answer for a public
   deploy: with it set, a stranger can only ever spend their own credits.

The limiter is in-process, so on serverless it is per-instance and resets on cold
start. That is a genuine weakness and it is not pretending otherwise — it raises
the cost of casual abuse but is not a substitute for BYO-key mode or a platform
WAF on a deployment that matters.
"""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler

# Requests per window, per IP. Tailor is the expensive one; scan is free to run.
TAILOR_LIMIT = int(os.environ.get("ACHILLES_TAILOR_RPM") or 5)
SERVER_KEY_TAILOR_LIMIT = int(os.environ.get("ACHILLES_SERVER_KEY_RPM") or 2)
SCAN_LIMIT = int(os.environ.get("ACHILLES_SCAN_RPM") or 60)
WINDOW_SECONDS = 60.0

# Bounded so a flood of distinct source IPs cannot grow this without limit.
MAX_TRACKED_CLIENTS = 4096

_hits: defaultdict[str, deque[float]] = defaultdict(deque)


def client_ip(handler: BaseHTTPRequestHandler) -> str:
    """Best-effort client identity.

    Vercel terminates TLS upstream, so `client_address` is the proxy. Trust
    `x-forwarded-for`'s first entry only because this always runs behind a proxy
    that sets it; on a directly-exposed server that header is caller-controlled
    and this would be spoofable.
    """
    forwarded = handler.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    real = handler.headers.get("x-real-ip")
    if real:
        return real.strip()
    try:
        return handler.client_address[0]
    except Exception:
        return "unknown"


def allowed_origins() -> list[str]:
    raw = os.environ.get("ACHILLES_ALLOWED_ORIGINS") or ""
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


def cors_origin(request_origin: str | None) -> str | None:
    """The value to echo back, or None to send no CORS header at all.

    Returning None is the safe default: the bundled UI is served from the same
    origin as the API, so it never needs CORS. Cross-origin access is opt-in via
    ACHILLES_ALLOWED_ORIGINS, and `*` must be set deliberately.
    """
    if not request_origin:
        return None
    origin = request_origin.rstrip("/")
    allowed = allowed_origins()
    if "*" in allowed:
        return "*"
    return origin if origin in allowed else None


def check_rate_limit(key: str, limit: int, *, now: float | None = None) -> float | None:
    """Return None if allowed, else seconds until the caller may retry."""
    if limit <= 0:
        return None  # 0 or negative disables the limit
    now = time.monotonic() if now is None else now
    bucket = _hits[key]

    while bucket and now - bucket[0] > WINDOW_SECONDS:
        bucket.popleft()

    if len(bucket) >= limit:
        return max(0.0, WINDOW_SECONDS - (now - bucket[0]))

    bucket.append(now)
    if len(_hits) > MAX_TRACKED_CLIENTS:
        _evict(now)
    return None


def _evict(now: float) -> None:
    for key in [k for k, v in _hits.items() if not v or now - v[-1] > WINDOW_SECONDS]:
        _hits.pop(key, None)


def reset() -> None:
    """Test hook."""
    _hits.clear()
