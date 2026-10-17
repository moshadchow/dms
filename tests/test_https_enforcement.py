"""Transport-layer HTTPS enforcement (spec 30).

The middleware is outermost: when FORCE_HTTPS is on and nginx reports the
request arrived over plain HTTP (X-Forwarded-Proto: http), it answers with a
308 redirect to the https equivalent. Requests without the forwarded header
(internal /health checks, direct uvicorn access) and requests already on
https pass through untouched, so this can never loop or break local dev.
"""

import pytest

from core.config import Settings


def _force_https(client_tuple, monkeypatch, value: bool):
    """Turn FORCE_HTTPS on/off for one test and yield the TestClient."""
    test_client, _, _ = client_tuple
    monkeypatch.setattr("core.config.settings.FORCE_HTTPS", value)
    return test_client


# ── Settings ──────────────────────────────────────────────────────────

def test_force_https_defaults_to_off():
    assert Settings.model_fields["FORCE_HTTPS"].default is False


# ── Redirects (FORCE_HTTPS on) ────────────────────────────────────────

def test_plain_http_redirects_to_https(client, monkeypatch):
    test_client = _force_https(client, monkeypatch, True)
    response = test_client.get(
        "/health",
        headers={"x-forwarded-proto": "http"},
        follow_redirects=False,
    )
    assert response.status_code == 308
    assert response.headers["location"] == "https://testserver/health"


def test_redirect_preserves_path_and_query(client, monkeypatch):
    test_client = _force_https(client, monkeypatch, True)
    response = test_client.get(
        "/api/v1/auth/me?foo=bar&baz=1",
        headers={"x-forwarded-proto": "http"},
        follow_redirects=False,
    )
    assert response.status_code == 308
    assert response.headers["location"] == "https://testserver/api/v1/auth/me?foo=bar&baz=1"


def test_redirect_applies_to_api_paths(client, monkeypatch):
    test_client = _force_https(client, monkeypatch, True)
    response = test_client.get(
        "/api/v1/categories",
        headers={"x-forwarded-proto": "http"},
        follow_redirects=False,
    )
    assert response.status_code == 308
    assert response.headers["location"] == "https://testserver/api/v1/categories"


def test_redirect_proto_value_is_case_insensitive(client, monkeypatch):
    test_client = _force_https(client, monkeypatch, True)
    response = test_client.get(
        "/health",
        headers={"x-forwarded-proto": "HTTP"},
        follow_redirects=False,
    )
    assert response.status_code == 308


def test_redirect_uses_first_value_of_chained_header(client, monkeypatch):
    test_client = _force_https(client, monkeypatch, True)
    response = test_client.get(
        "/health",
        headers={"x-forwarded-proto": "http, http"},
        follow_redirects=False,
    )
    assert response.status_code == 308


# ── Pass-through (FORCE_HTTPS on) ─────────────────────────────────────

def test_https_requests_pass_through(client, monkeypatch):
    test_client = _force_https(client, monkeypatch, True)
    response = test_client.get(
        "/health",
        headers={"x-forwarded-proto": "https"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_missing_forwarded_header_passes_through(client, monkeypatch):
    """Internal callers (/health from systemd, localhost curl) never redirect."""
    test_client = _force_https(client, monkeypatch, True)
    response = test_client.get("/health")
    assert response.status_code == 200


# ── Pass-through (FORCE_HTTPS off — the default) ──────────────────────

def test_plain_http_passes_through_when_disabled(client, monkeypatch):
    test_client = _force_https(client, monkeypatch, False)
    response = test_client.get(
        "/health",
        headers={"x-forwarded-proto": "http"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
