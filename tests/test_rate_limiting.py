"""Rate limiting and DDoS mitigation (spec 31).

Per-IP token buckets in middleware/ratelimit.py: a strict rule for
/api/v1/auth/login, the default rule for everything else under /api/v1,
rejects answered with 429 + Retry-After before any RBAC/audit/DB work.
conftest disables the middleware globally (the whole suite bursts from one
TestClient IP); these tests re-enable it with tiny limits, a fake monotonic
clock, and a fresh limiter per test.
"""

import pytest

import middleware.ratelimit as ratelimit
from core.config import Settings

LOGIN = "/api/v1/auth/login"
BAD_LOGIN = {"email": "nobody@example.com", "password": "wrong"}


@pytest.fixture()
def clock(monkeypatch):
    """Deterministic monotonic clock for the limiter (advance to refill)."""

    class Clock:
        def __init__(self):
            self.now = 1_000.0

        def __call__(self):
            return self.now

        def advance(self, seconds):
            self.now += seconds

    c = Clock()
    monkeypatch.setattr(ratelimit, "_now", c)
    return c


@pytest.fixture()
def rl(client, monkeypatch, clock):
    """The suite's client with rate limiting enabled and small limits."""
    test_client, _, _ = client
    monkeypatch.setattr("core.config.settings.RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr("core.config.settings.RATE_LIMIT_REQUESTS", 5)
    monkeypatch.setattr("core.config.settings.RATE_LIMIT_AUTH_REQUESTS", 3)
    monkeypatch.setattr("core.config.settings.RATE_LIMIT_WINDOW_SECONDS", 60)
    monkeypatch.setattr("core.config.settings.RATE_LIMIT_MAX_KEYS", 100)
    ratelimit.limiter.reset()
    yield test_client
    ratelimit.limiter.reset()


def _exhaust_login(test_client, count=3, headers=None):
    for _ in range(count):
        test_client.post(LOGIN, json=BAD_LOGIN, headers=headers or {})


# ── Settings defaults ─────────────────────────────────────────────────

def test_rate_limit_settings_default_enabled():
    assert Settings.model_fields["RATE_LIMIT_ENABLED"].default is True
    assert Settings.model_fields["RATE_LIMIT_REQUESTS"].default == 600
    assert Settings.model_fields["RATE_LIMIT_WINDOW_SECONDS"].default == 60
    assert Settings.model_fields["RATE_LIMIT_AUTH_REQUESTS"].default == 10


# ── Throttling behaviour (middleware enabled) ────────────────────────

def test_login_throttled_after_auth_limit(rl):
    _exhaust_login(rl, 3)
    response = rl.post(LOGIN, json=BAD_LOGIN)
    assert response.status_code == 429


def test_429_has_retry_after_and_json_detail(rl):
    _exhaust_login(rl, 3)
    response = rl.post(LOGIN, json=BAD_LOGIN)
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) >= 1
    assert "Too many requests" in response.json()["detail"]


def test_window_recovery_allows_requests_again(rl, clock):
    _exhaust_login(rl, 3)
    assert rl.post(LOGIN, json=BAD_LOGIN).status_code == 429
    clock.advance(60)  # full refill after one window
    assert rl.post(LOGIN, json=BAD_LOGIN).status_code != 429


def test_default_rule_throttles_non_login_api(rl, auth_headers):
    headers = auth_headers["admin"]
    for _ in range(5):  # RATE_LIMIT_REQUESTS in the rl fixture
        assert rl.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert rl.get("/api/v1/auth/me", headers=headers).status_code == 429


def test_other_ip_is_not_locked_out_by_a_flooder(rl):
    _exhaust_login(rl, 3, headers={"X-Real-IP": "203.0.113.10"})
    assert rl.post(LOGIN, json=BAD_LOGIN, headers={"X-Real-IP": "203.0.113.10"}).status_code == 429
    other = rl.post(LOGIN, json=BAD_LOGIN, headers={"X-Real-IP": "203.0.113.20"})
    assert other.status_code != 429


# ── Exemptions ───────────────────────────────────────────────────────

def test_health_never_rate_limited(rl):
    for _ in range(50):  # far beyond RATE_LIMIT_REQUESTS=5
        assert rl.get("/health").status_code == 200


def test_docs_never_rate_limited(rl):
    for _ in range(20):
        assert rl.get("/docs").status_code == 200


def test_options_requests_are_not_counted(rl):
    for _ in range(10):  # beyond the default limit of 5
        assert rl.options("/api/v1/auth/me").status_code != 429


# ── Disabled (the conftest default) ──────────────────────────────────

def test_disabled_never_throttles(client, monkeypatch):
    test_client, _, _ = client
    # RATE_LIMIT_ENABLED stays False (tests/conftest.py), limits are tiny.
    monkeypatch.setattr("core.config.settings.RATE_LIMIT_REQUESTS", 2)
    monkeypatch.setattr("core.config.settings.RATE_LIMIT_AUTH_REQUESTS", 2)
    for _ in range(10):
        assert test_client.get("/api/v1/auth/me").status_code == 401
        assert test_client.post(LOGIN, json=BAD_LOGIN).status_code != 429


# ── Trusted client IP resolution ─────────────────────────────────────

def test_x_real_ip_takes_precedence_over_forwarded_for(rl):
    # nginx overwrites X-Real-IP with the true client address; a rotating
    # client-supplied first X-Forwarded-For entry must not mint fresh buckets.
    for i in range(3):
        rl.post(
            LOGIN,
            json=BAD_LOGIN,
            headers={"X-Real-IP": "198.51.100.7", "X-Forwarded-For": f"10.0.0.{i}"},
        )
    response = rl.post(
        LOGIN,
        json=BAD_LOGIN,
        headers={"X-Real-IP": "198.51.100.7", "X-Forwarded-For": "10.0.0.99"},
    )
    assert response.status_code == 429


def test_forwarded_for_uses_last_value(rl):
    # nginx APPENDS the real IP to a client-supplied X-Forwarded-For
    # ($proxy_add_x_forwarded_for), so the last entry is authoritative.
    for i in range(3):
        rl.post(LOGIN, json=BAD_LOGIN, headers={"X-Forwarded-For": f"fake{i}, 192.0.2.55"})
    response = rl.post(LOGIN, json=BAD_LOGIN, headers={"X-Forwarded-For": "fake, 192.0.2.55"})
    assert response.status_code == 429


# ── CORS reachability of the 429 ─────────────────────────────────────

def test_429_carries_cors_headers(rl):
    # CORS is the outermost middleware (main.py): a browser must be able to
    # read the 429 body cross-origin.
    from core.config import settings

    origin = settings.CORS_ORIGINS[0]
    _exhaust_login(rl, 3)
    response = rl.post(
        LOGIN,
        json=BAD_LOGIN,
        headers={"Origin": origin},
    )
    assert response.status_code == 429
    assert response.headers.get("access-control-allow-origin") == origin


# ── Limiter unit tests ───────────────────────────────────────────────

class TestLimiter:
    def test_allows_up_to_limit_then_rejects(self):
        lim = ratelimit.Limiter()
        for _ in range(3):
            allowed, retry = lim.allow("auth", "1.1.1.1", limit=3, window=60, max_keys=100, now=0.0)
            assert allowed is True
            assert retry == 0
        allowed, retry = lim.allow("auth", "1.1.1.1", limit=3, window=60, max_keys=100, now=0.0)
        assert allowed is False
        assert retry == 20  # 1 token at 3/60 tokens per second

    def test_partial_refill_still_rejected(self):
        lim = ratelimit.Limiter()
        for _ in range(3):
            lim.allow("auth", "k", limit=3, window=60, max_keys=100, now=0.0)
        allowed, retry = lim.allow("auth", "k", limit=3, window=60, max_keys=100, now=10.0)
        assert allowed is False
        assert retry == 10  # 0.5 tokens refilled; 0.5 more needed

    def test_full_refill_after_window(self):
        lim = ratelimit.Limiter()
        for _ in range(3):
            lim.allow("auth", "k", limit=3, window=60, max_keys=100, now=0.0)
        allowed, _ = lim.allow("auth", "k", limit=3, window=60, max_keys=100, now=63.0)
        assert allowed is True

    def test_rules_have_independent_buckets(self):
        lim = ratelimit.Limiter()
        for i in range(3):
            lim.allow("auth", "k", limit=3, window=60, max_keys=100, now=float(i))
        allowed, _ = lim.allow("default", "k", limit=3, window=60, max_keys=100, now=3.0)
        assert allowed is True

    def test_prune_drops_expired_buckets(self):
        lim = ratelimit.Limiter()
        lim.allow("default", "a", limit=1, window=10, max_keys=100, now=0.0)
        lim.allow("default", "b", limit=1, window=10, max_keys=100, now=0.0)
        assert len(lim._buckets) == 2
        # Both buckets are fully refilled after a window; inserting a third
        # key at cap triggers pruning of the expired ones.
        lim.allow("default", "c", limit=1, window=10, max_keys=2, now=11.0)
        assert set(lim._buckets.keys()) == {("default", "c")}

    def test_key_cap_fails_open(self):
        lim = ratelimit.Limiter()
        for i in range(2):
            allowed, _ = lim.allow("default", f"k{i}", limit=5, window=60, max_keys=2, now=0.0)
            assert allowed is True
        # Cap reached with live (non-expired) buckets: store clears rather
        # than blocking — fail open.
        allowed, _ = lim.allow("default", "new", limit=5, window=60, max_keys=2, now=1.0)
        assert allowed is True
        assert set(lim._buckets.keys()) == {("default", "new")}

    def test_reset_clears_state(self):
        lim = ratelimit.Limiter()
        lim.allow("default", "k", limit=1, window=60, max_keys=100, now=0.0)
        assert len(lim._buckets) == 1
        lim.reset()
        assert len(lim._buckets) == 0
