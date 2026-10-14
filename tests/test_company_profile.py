"""Tests for Company Profile Management — SUPERADMIN-only CRUD."""

import pytest


# ──────────────────────────────────────────────
# SUPERADMIN CRUD
# ──────────────────────────────────────────────

def test_superadmin_can_create_company(client, seeded_data, auth_headers):
    """SUPERADMIN can create a company."""
    _, engine, _ = client
    payload = {
        "company_id": "ACME-001",
        "full_name": "ACME Corporation",
        "short_name": "ACME",
        "address": "123 Main St",
        "contact_person": "John Doe",
        "contact_no": "+1234567890",
        "email_address": "info@acme.com",
    }
    resp = client[0].post(
        "/api/v1/companies",
        json=payload,
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["company_id"] == "ACME-001"
    assert data["full_name"] == "ACME Corporation"
    assert data["short_name"] == "ACME"
    assert data["is_active"] is True


def test_superadmin_can_list_companies(client, seeded_data, auth_headers):
    """SUPERADMIN can list companies."""
    # Create a company first
    client[0].post(
        "/api/v1/companies",
        json={"company_id": "LIST-001", "full_name": "List Corp", "short_name": "LIST"},
        headers=auth_headers["superadmin"],
    )
    resp = client[0].get("/api/v1/companies", headers=auth_headers["superadmin"])
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_superadmin_can_get_company_by_id(client, seeded_data, auth_headers):
    """SUPERADMIN can get a company by ID."""
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "GET-001", "full_name": "Get Corp", "short_name": "GET"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]
    resp = client[0].get(f"/api/v1/companies/{company_id}", headers=auth_headers["superadmin"])
    assert resp.status_code == 200
    assert resp.json()["company_id"] == "GET-001"


def test_superadmin_can_update_company(client, seeded_data, auth_headers):
    """SUPERADMIN can update a company."""
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "UPD-001", "full_name": "Old Name", "short_name": "UPD"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]
    resp = client[0].patch(
        f"/api/v1/companies/{company_id}",
        json={"full_name": "New Name"},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "New Name"


def test_superadmin_can_deactivate_company(client, seeded_data, auth_headers):
    """SUPERADMIN can deactivate a company."""
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "DEAC-001", "full_name": "Deac Corp", "short_name": "DEAC"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]
    resp = client[0].patch(
        f"/api/v1/companies/{company_id}/deactivate",
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_superadmin_can_activate_company(client, seeded_data, auth_headers):
    """SUPERADMIN can activate a company."""
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "ACT-001", "full_name": "Act Corp", "short_name": "ACT"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]
    # Deactivate first
    client[0].patch(f"/api/v1/companies/{company_id}/deactivate", headers=auth_headers["superadmin"])
    # Then activate
    resp = client[0].patch(
        f"/api/v1/companies/{company_id}/activate",
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


# ──────────────────────────────────────────────
# ADMIN CANNOT ACCESS
# ──────────────────────────────────────────────

def test_admin_cannot_create_company(client, seeded_data, auth_headers):
    """ADMIN cannot create a company (SUPERADMIN-only)."""
    resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "ADM-001", "full_name": "Admin Corp", "short_name": "ADM"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 403


def test_admin_cannot_update_company(client, seeded_data, auth_headers):
    """ADMIN cannot update a company."""
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "ADM-002", "full_name": "Admin Corp 2", "short_name": "ADM2"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]
    resp = client[0].patch(
        f"/api/v1/companies/{company_id}",
        json={"full_name": "Hacked"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 403


def test_admin_cannot_deactivate_company(client, seeded_data, auth_headers):
    """ADMIN cannot deactivate a company."""
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "ADM-003", "full_name": "Admin Corp 3", "short_name": "ADM3"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]
    resp = client[0].patch(
        f"/api/v1/companies/{company_id}/deactivate",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 403


# ──────────────────────────────────────────────
# UNAUTHENTICATED
# ──────────────────────────────────────────────

def test_unauthenticated_cannot_access_companies(client, seeded_data):
    """Unauthenticated requests are rejected."""
    resp = client[0].get("/api/v1/companies")
    assert resp.status_code == 401


# ──────────────────────────────────────────────
# VALIDATION
# ──────────────────────────────────────────────

def test_duplicate_company_id_rejected(client, seeded_data, auth_headers):
    """Duplicate company_id is rejected with 409."""
    payload = {"company_id": "DUP-001", "full_name": "Dup Corp", "short_name": "DUP1"}
    client[0].post("/api/v1/companies", json=payload, headers=auth_headers["superadmin"])
    payload2 = {"company_id": "DUP-001", "full_name": "Dup Corp 2", "short_name": "DUP2"}
    resp = client[0].post("/api/v1/companies", json=payload2, headers=auth_headers["superadmin"])
    assert resp.status_code == 409


def test_duplicate_short_name_rejected(client, seeded_data, auth_headers):
    """Duplicate short_name is rejected with 409."""
    payload = {"company_id": "DUP-SN1", "full_name": "Dup SN Corp", "short_name": "DUPSN"}
    client[0].post("/api/v1/companies", json=payload, headers=auth_headers["superadmin"])
    payload2 = {"company_id": "DUP-SN2", "full_name": "Dup SN Corp 2", "short_name": "DUPSN"}
    resp = client[0].post("/api/v1/companies", json=payload2, headers=auth_headers["superadmin"])
    assert resp.status_code == 409


def test_invalid_email_rejected(client, seeded_data, auth_headers):
    """Invalid email format is rejected with 422."""
    payload = {"company_id": "EMAIL-001", "full_name": "Email Corp", "short_name": "EMAIL", "email_address": "not-an-email"}
    resp = client[0].post("/api/v1/companies", json=payload, headers=auth_headers["superadmin"])
    assert resp.status_code == 422


def test_required_fields_validated(client, seeded_data, auth_headers):
    """Missing required fields are rejected with 422."""
    resp = client[0].post(
        "/api/v1/companies",
        json={},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 422


def test_deactivation_does_not_delete(client, seeded_data, auth_headers):
    """Deactivation does not physically delete the record."""
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "NODEL-001", "full_name": "NoDel Corp", "short_name": "NODEL"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]
    # Deactivate
    client[0].patch(f"/api/v1/companies/{company_id}/deactivate", headers=auth_headers["superadmin"])
    # Record still exists
    resp = client[0].get(f"/api/v1/companies/{company_id}", headers=auth_headers["superadmin"])
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


# ──────────────────────────────────────────────
# AUDIT
# ──────────────────────────────────────────────

def test_audit_events_generated(client, seeded_data, auth_headers):
    """Company operations generate audit events."""
    from sqlmodel import Session, select
    from audit.models import AuditLog

    _, engine, _ = client

    # Create a company
    create_resp = client[0].post(
        "/api/v1/companies",
        json={"company_id": "AUD-001", "full_name": "Audit Corp", "short_name": "AUD"},
        headers=auth_headers["superadmin"],
    )
    company_id = create_resp.json()["id"]

    with Session(engine) as session:
        logs = session.exec(
            select(AuditLog).where(AuditLog.entity_name == "company")
        ).all()
        actions = [log.action if isinstance(log.action, str) else log.action.value for log in logs]
        assert "create_company" in actions
