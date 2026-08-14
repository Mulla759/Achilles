"""Adversarial tests for `api._guard` -- the CORS allowlist and rate limiter.

`_guard.py` is loaded the way Vercel loads it: as a bare module living in
`api/`, imported via `from _lib import ...`-style resolution rather than a
package. These tests replicate that by putting `api/` on `sys.path` before
importing, matching the pattern in `tests/test_api.py`.

No network, no real clock: every timing-sensitive test drives `now=`
explicitly instead of sleeping.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
API_DIR = ROOT / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import _guard  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_guard_state():
    """Prevent state leaking between tests (and from this module into others)."""
    _guard.reset()
    yield
    _guard.reset()


class _FakeHandler:
    """Stand-in for BaseHTTPRequestHandler: just `.headers.get` and `.client_address`."""

    def __init__(self, headers=None, client_address=None):
        self.headers = headers or {}
        self.client_address = client_address


# --------------------------------------------------------------------------
# 1. check_rate_limit -- allow up to the limit, block the next one
# --------------------------------------------------------------------------


def test_nth_request_allowed_n_plus_1th_blocked_with_float_retry():
    limit = 3
    for i in range(limit):
        assert _guard.check_rate_limit("k1", limit, now=1000.0 + i) is None
    retry = _guard.check_rate_limit("k1", limit, now=1000.0 + limit)
    assert isinstance(retry, float)
    assert retry > 0


# --------------------------------------------------------------------------
# 2. The window slides
# --------------------------------------------------------------------------


def test_window_slides_caller_allowed_again_after_window_seconds():
    limit = 2
    assert _guard.check_rate_limit("k2", limit, now=0.0) is None
    assert _guard.check_rate_limit("k2", limit, now=1.0) is None
    assert _guard.check_rate_limit("k2", limit, now=2.0) is not None  # 3rd blocked
    later = 0.0 + _guard.WINDOW_SECONDS + 1.0
    assert _guard.check_rate_limit("k2", limit, now=later) is None


# --------------------------------------------------------------------------
# 3. Distinct keys have independent buckets
# --------------------------------------------------------------------------


def test_distinct_keys_do_not_share_a_bucket():
    # ATTACK surface check: a key collision here would let one caller's
    # traffic starve an unrelated caller's quota (or the reverse: a shared
    # bucket that never blocks anyone).
    limit = 1
    assert _guard.check_rate_limit("client-a", limit, now=0.0) is None
    assert _guard.check_rate_limit("client-b", limit, now=0.0) is None
    assert _guard.check_rate_limit("client-a", limit, now=0.0) is not None
    assert _guard.check_rate_limit("client-c", limit, now=0.0) is None


# --------------------------------------------------------------------------
# 4. limit <= 0 disables limiting
# --------------------------------------------------------------------------


def test_zero_and_negative_limits_never_block():
    for limit in (0, -1, -100):
        for i in range(50):
            assert _guard.check_rate_limit("disabled", limit, now=float(i)) is None


# --------------------------------------------------------------------------
# 5. cors_origin
# --------------------------------------------------------------------------


def test_cors_no_origin_header_returns_none(monkeypatch):
    monkeypatch.setenv("ACHILLES_ALLOWED_ORIGINS", "https://a.com")
    assert _guard.cors_origin(None) is None
    assert _guard.cors_origin("") is None


def test_cors_origin_not_on_allowlist_returns_none(monkeypatch):
    monkeypatch.setenv("ACHILLES_ALLOWED_ORIGINS", "https://a.com")
    # ATTACK: a page on evil.com trying to piggyback on the allowlisted UI's
    # cross-origin access must get no CORS header, not a copy-paste mistake.
    assert _guard.cors_origin("https://evil.com") is None


def test_cors_origin_on_allowlist_is_echoed_back(monkeypatch):
    monkeypatch.setenv("ACHILLES_ALLOWED_ORIGINS", "https://a.com")
    assert _guard.cors_origin("https://a.com") == "https://a.com"


def test_cors_wildcard_only_when_allowlist_literally_contains_star(monkeypatch):
    monkeypatch.setenv("ACHILLES_ALLOWED_ORIGINS", "*")
    assert _guard.cors_origin("https://anything.example") == "*"


def test_cors_no_allowlist_configured_returns_none(monkeypatch):
    monkeypatch.delenv("ACHILLES_ALLOWED_ORIGINS", raising=False)
    assert _guard.cors_origin("https://a.com") is None


def test_cors_trailing_slash_mismatch_resolves_both_directions(monkeypatch):
    # Allowlist entry has a trailing slash, the browser's Origin never does.
    monkeypatch.setenv("ACHILLES_ALLOWED_ORIGINS", "https://a.com/")
    assert _guard.cors_origin("https://a.com") == "https://a.com"
    # Allowlist entry has no trailing slash, but somehow the origin does.
    monkeypatch.setenv("ACHILLES_ALLOWED_ORIGINS", "https://a.com")
    assert _guard.cors_origin("https://a.com/") == "https://a.com"


# --------------------------------------------------------------------------
# 6. client_ip
# --------------------------------------------------------------------------


def test_client_ip_prefers_first_x_forwarded_for_entry():
    # ATTACK relevance: if a caller could inject extra X-Forwarded-For hops
    # after the real one, using anything but the first entry would let them
    # pick which IP the rate limiter buckets them under.
    h = _FakeHandler(
        headers={"x-forwarded-for": "1.2.3.4, 5.6.7.8"},
        client_address=("9.9.9.9", 1234),
    )
    assert _guard.client_ip(h) == "1.2.3.4"


def test_client_ip_falls_back_to_x_real_ip():
    h = _FakeHandler(headers={"x-real-ip": "2.2.2.2"}, client_address=("9.9.9.9", 1234))
    assert _guard.client_ip(h) == "2.2.2.2"


def test_client_ip_falls_back_to_client_address():
    h = _FakeHandler(headers={}, client_address=("3.3.3.3", 1234))
    assert _guard.client_ip(h) == "3.3.3.3"


def test_client_ip_never_raises_when_everything_absent():
    class _NoAddr:
        headers: dict = {}

    assert _guard.client_ip(_NoAddr()) == "unknown"


# --------------------------------------------------------------------------
# 7. Eviction -- the tracked-client map must not grow unbounded
# --------------------------------------------------------------------------


def test_stale_entries_are_evicted_once_max_tracked_clients_exceeded():
    # ATTACK: a flood of distinct source IPs (or spoofed X-Forwarded-For
    # values) each making one request should not be able to grow the
    # in-process map without bound and exhaust memory.
    old_now = 0.0
    for i in range(_guard.MAX_TRACKED_CLIENTS):
        _guard.check_rate_limit(f"stale-{i}", 100, now=old_now)
    assert len(_guard._hits) == _guard.MAX_TRACKED_CLIENTS

    fresh_now = old_now + _guard.WINDOW_SECONDS + 1.0
    _guard.check_rate_limit("fresh", 100, now=fresh_now)

    assert len(_guard._hits) < _guard.MAX_TRACKED_CLIENTS
    assert "fresh" in _guard._hits
