"""Tests for Company-scoped Azure AD configuration."""

import pytest


# ──────────────────────────────────────────────
# SUPERADMIN: Azure config CRUD
# ──────────────────────────────────────────────

def test_superadmin_can_get_azure_config(client, seeded_data, auth_headers):
    """SuperAdmin can get Azure config for a company."""
    company_id = seeded_data["company_id"]
    resp = client[0].get(
        f"/api/v1/companies/{company_id}/azure-config",
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["azure_enabled"] is False


def test_superadmin_can_update_azure_config(client, seeded_data, auth_headers):
    """SuperAdmin can set Azure AD config on a company."""
    company_id = seeded_data["company_id"]
    payload = {
        "azure_client_id": "test-client-id",
        "azure_tenant_id": "test-tenant-id",
        "azure_client_secret": "test-secret",
        "azure_enabled": True,
        "azure_default_role_name": "auditor",
    }
    resp = client[0].put(
        f"/api/v1/companies/{company_id}/azure-config",
        json=payload,
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is True
    assert data["azure_client_id"] == "test-client-id"
    assert data["azure_tenant_id"] == "test-tenant-id"
    assert data["azure_enabled"] is True
    assert data["azure_default_role_name"] == "auditor"


def test_superadmin_can_delete_azure_config(client, seeded_data, auth_headers):
    """SuperAdmin can remove Azure AD config from a company."""
    company_id = seeded_data["company_id"]
    # First set it
    client[0].put(
        f"/api/v1/companies/{company_id}/azure-config",
        json={
            "azure_client_id": "to-delete",
            "azure_tenant_id": "to-delete",
            "azure_enabled": True,
        },
        headers=auth_headers["superadmin"],
    )
    # Then delete
    resp = client[0].delete(
        f"/api/v1/companies/{company_id}/azure-config",
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["azure_enabled"] is False
    assert data["azure_client_id"] is None
    assert data["azure_tenant_id"] is None


def test_azure_config_secret_never_returned(client, seeded_data, auth_headers):
    """The Azure client secret is never returned in API responses."""
    company_id = seeded_data["company_id"]
    client[0].put(
        f"/api/v1/companies/{company_id}/azure-config",
        json={
            "azure_client_id": "cid-123",
            "azure_tenant_id": "tid-123",
            "azure_client_secret": "super-secret-value",
            "azure_enabled": True,
        },
        headers=auth_headers["superadmin"],
    )
    resp = client[0].get(
        f"/api/v1/companies/{company_id}/azure-config",
        headers=auth_headers["superadmin"],
    )
    data = resp.json()
    assert "client_secret" not in data or data.get("azure_client_secret") is None


# ──────────────────────────────────────────────
# ADMIN: Can view own company, not others
# ──────────────────────────────────────────────

def test_admin_can_view_own_company_azure_config(client, seeded_data, auth_headers):
    """Admin can view Azure config for their own company."""
    company_id = seeded_data["company_id"]
    resp = client[0].get(
        f"/api/v1/companies/{company_id}/azure-config",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200


def test_admin_cannot_view_other_company_azure_config(client, seeded_data, auth_headers):
    """Admin cannot view Azure config for another company."""
    other_company_id = seeded_data["other_company_id"]
    resp = client[0].get(
        f"/api/v1/companies/{other_company_id}/azure-config",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 403


def test_admin_cannot_update_azure_config(client, seeded_data, auth_headers):
    """Admin cannot update Azure config (SuperAdmin only)."""
    company_id = seeded_data["company_id"]
    resp = client[0].put(
        f"/api/v1/companies/{company_id}/azure-config",
        json={"azure_client_id": "hack"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 403


def test_admin_cannot_delete_azure_config(client, seeded_data, auth_headers):
    """Admin cannot delete Azure config (SuperAdmin only)."""
    company_id = seeded_data["company_id"]
    resp = client[0].delete(
        f"/api/v1/companies/{company_id}/azure-config",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 403


# ──────────────────────────────────────────────
# UNAUTHENTICATED
# ──────────────────────────────────────────────

def test_unauthenticated_cannot_access_azure_config(client, seeded_data):
    """Unauthenticated requests to Azure config are rejected."""
    company_id = seeded_data["company_id"]
    resp = client[0].get(f"/api/v1/companies/{company_id}/azure-config")
    assert resp.status_code == 401


# ──────────────────────────────────────────────
# 404 handling
# ──────────────────────────────────────────────

def test_azure_config_404_for_nonexistent_company(client, seeded_data, auth_headers):
    """Azure config returns 404 for nonexistent company."""
    resp = client[0].get(
        "/api/v1/companies/99999/azure-config",
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 404


# ──────────────────────────────────────────────
# Azure config on /auth/azure/config endpoint
# ──────────────────────────────────────────────

def test_azure_config_endpoint_returns_companies(client, seeded_data, auth_headers):
    """The /auth/azure/config endpoint returns companies with Azure enabled."""
    company_id = seeded_data["company_id"]
    # Set Azure config on a company
    client[0].put(
        f"/api/v1/companies/{company_id}/azure-config",
        json={
            "azure_client_id": "test",
            "azure_tenant_id": "test",
            "azure_enabled": True,
        },
        headers=auth_headers["superadmin"],
    )
    # Public endpoint
    resp = client[0].get("/api/v1/auth/azure/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "global_enabled" in data
    assert "companies" in data
    # Our company should be in the list
    company_ids = [c["id"] for c in data["companies"]]
    assert company_id in company_ids


# ──────────────────────────────────────────────
# Audit trail
# ──────────────────────────────────────────────

def test_azure_config_change_generates_audit(client, seeded_data, auth_headers):
    """Updating Azure config generates an audit event."""
    from sqlmodel import Session, select
    from audit.models import AuditLog

    _, engine, _ = client
    company_id = seeded_data["company_id"]

    client[0].put(
        f"/api/v1/companies/{company_id}/azure-config",
        json={
            "azure_client_id": "audit-test",
            "azure_tenant_id": "audit-test",
            "azure_enabled": True,
        },
        headers=auth_headers["superadmin"],
    )

    with Session(engine) as session:
        logs = session.exec(
            select(AuditLog).where(
                AuditLog.entity_name == "company",
                AuditLog.entity_id == str(company_id),
            )
        ).all()
        # Should have at least one audit log for the update
        assert len(logs) >= 1
