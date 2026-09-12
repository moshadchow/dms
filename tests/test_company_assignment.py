"""Tests for Company Assignment — SUPERADMIN creates ADMIN with company."""

import pytest
from sqlmodel import Session, select

from company_profile.models import Company
from core.security import hash_password
from users.models import RoleName, User, UserRoleLink


def _get_role_id(session, role_name: RoleName):
    """Helper to get role ID by name."""
    from users.models import Role
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    return role.id if role else None


def _create_company(session, company_id="TEST-001", short_name="TEST", is_active=True):
    """Helper to create a test company."""
    company = Company(
        company_id=company_id,
        full_name=f"Test Corp {company_id}",
        short_name=short_name,
        is_active=is_active,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


# ──────────────────────────────────────────────
# SUPERADMIN → ADMIN with company
# ──────────────────────────────────────────────

def test_superadmin_can_create_admin_with_company(client, seeded_data, auth_headers):
    """SUPERADMIN can create ADMIN with a valid active company."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "COMP-001", "COMP1")
        admin_role_id = _get_role_id(session, RoleName.ADMIN)

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "New Admin",
            "email": "newadmin@test.com",
            "password": "Admin@1234",
            "role_ids": [admin_role_id],
            "company_id": company.id,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["email"] == "newadmin@test.com"
    assert data["company"] is not None
    assert data["company"]["id"] == company.id
    assert data["company"]["company_id"] == "COMP-001"


def test_superadmin_cannot_create_admin_without_company(client, seeded_data, auth_headers):
    """SUPERADMIN cannot create ADMIN without company."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "No Company Admin",
            "email": "nocompany@test.com",
            "password": "Admin@1234",
            "role_ids": [admin_role_id],
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 422


def test_superadmin_cannot_assign_nonexistent_company(client, seeded_data, auth_headers):
    """SUPERADMIN cannot assign a nonexistent company."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Bad Company Admin",
            "email": "badcompany@test.com",
            "password": "Admin@1234",
            "role_ids": [admin_role_id],
            "company_id": 99999,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 400


def test_superadmin_cannot_assign_inactive_company(client, seeded_data, auth_headers):
    """SUPERADMIN cannot assign an inactive company."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "INACT-001", "INACT", is_active=False)
        admin_role_id = _get_role_id(session, RoleName.ADMIN)

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Inactive Company Admin",
            "email": "inactivecompany@test.com",
            "password": "Admin@1234",
            "role_ids": [admin_role_id],
            "company_id": company.id,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 400


def test_created_admin_has_correct_company(client, seeded_data, auth_headers):
    """Created ADMIN contains the correct company relationship."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "CORR-001", "CORR")
        admin_role_id = _get_role_id(session, RoleName.ADMIN)

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Correct Admin",
            "email": "correctadmin@test.com",
            "password": "Admin@1234",
            "role_ids": [admin_role_id],
            "company_id": company.id,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["company"]["id"] == company.id
    assert data["company"]["company_id"] == "CORR-001"
    assert data["company"]["full_name"] == "Test Corp CORR-001"


# ──────────────────────────────────────────────
# SUPERADMIN role restrictions (already exist, verifying no regression)
# ──────────────────────────────────────────────

def test_superadmin_cannot_create_maker(client, seeded_data, auth_headers):
    """SUPERADMIN cannot create MAKER."""
    _, engine, _ = client
    with Session(engine) as session:
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        company = _create_company(session, "MKR-001", "MKR")

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "New Maker",
            "email": "newmaker@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
            "company_id": company.id,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 403


def test_superadmin_cannot_create_checker(client, seeded_data, auth_headers):
    """SUPERADMIN cannot create CHECKER."""
    _, engine, _ = client
    with Session(engine) as session:
        checker_role_id = _get_role_id(session, RoleName.CHECKER)
        company = _create_company(session, "CHK-001", "CHK")

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "New Checker",
            "email": "newchecker@test.com",
            "password": "Checker@1234",
            "role_ids": [checker_role_id],
            "company_id": company.id,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 403


def test_superadmin_cannot_create_auditor(client, seeded_data, auth_headers):
    """SUPERADMIN cannot create AUDITOR."""
    _, engine, _ = client
    with Session(engine) as session:
        auditor_role_id = _get_role_id(session, RoleName.AUDITOR)
        company = _create_company(session, "AUD-001", "AUD")

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "New Auditor",
            "email": "newauditor@test.com",
            "password": "Auditor@1234",
            "role_ids": [auditor_role_id],
            "company_id": company.id,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 403


def test_superadmin_cannot_create_superadmin(client, seeded_data, auth_headers):
    """SUPERADMIN cannot create another SUPERADMIN."""
    _, engine, _ = client
    with Session(engine) as session:
        superadmin_role_id = _get_role_id(session, RoleName.SUPERADMIN)
        company = _create_company(session, "SUP-001", "SUP")

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "New SuperAdmin",
            "email": "newsuperadmin@test.com",
            "password": "SuperAdmin@1234",
            "role_ids": [superadmin_role_id],
            "company_id": company.id,
        },
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 403


# ──────────────────────────────────────────────
# Existing behavior unchanged
# ──────────────────────────────────────────────

def test_admin_user_creation_inherits_company(client, seeded_data, auth_headers):
    """ADMIN creating users automatically inherits admin's company."""
    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Admin Created",
            "email": "admincreated@test.com",
            "password": "Admin@1234",
            "role_ids": [seeded_data.get("admin_role_id", 1)],
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    data = resp.json()
    # New user should inherit admin's company
    assert data["company"] is not None
    assert data["company"]["id"] == seeded_data["company_id"]
    assert data["company"]["company_id"] == "TEST-COMP-001"


# ──────────────────────────────────────────────
# ADMIN Company Inheritance — New Tests
# ──────────────────────────────────────────────

def test_admin_different_company_inherits_correctly(client, seeded_data, auth_headers):
    """ADMIN with Company B creates user → user gets Company B."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        company_b = _create_company(session, "COMP-B", "COMPB")

    # Create admin with Company B
    admin_b_id = _create_admin_via_api(client, auth_headers, admin_role_id, company_b.id)

    # Login as admin_b to create user
    from core.security import create_access_token
    admin_b_headers = {"Authorization": f"Bearer {create_access_token(admin_b_id)}"}

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Maker from Admin B",
            "email": "makerb@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
        },
        headers=admin_b_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["company"] is not None
    assert data["company"]["id"] == company_b.id
    assert data["company"]["company_id"] == "COMP-B"


def test_admin_cannot_override_inherited_company(client, seeded_data, auth_headers):
    """ADMIN sends company_id in request → ignored, gets admin's company."""
    _, engine, _ = client
    with Session(engine) as session:
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        company_other = _create_company(session, "OTHER-001", "OTHER")

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Maker with Override Attempt",
            "email": "override@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
            "company_id": company_other.id,  # Attempt to override
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    data = resp.json()
    # Should inherit admin's company, not the provided one
    assert data["company"] is not None
    assert data["company"]["id"] == seeded_data["company_id"]
    assert data["company"]["company_id"] == "TEST-COMP-001"


def test_admin_without_company_cannot_create_user(client, seeded_data, auth_headers):
    """ADMIN without company cannot create user."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        # Create admin WITHOUT company
        admin_no_company = User(
            full_name="Admin No Company",
            email="adminnocomp@test.com",
            hashed_password=hash_password("Admin@1234"),
            is_active=True,
        )
        session.add(admin_no_company)
        session.flush()
        session.add(UserRoleLink(user_id=admin_no_company.id, role_id=admin_role_id))
        session.commit()
        admin_no_company_id = admin_no_company.id

    from core.security import create_access_token
    admin_no_company_headers = {"Authorization": f"Bearer {create_access_token(admin_no_company_id)}"}

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Maker from Admin No Company",
            "email": "makernocomp@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
        },
        headers=admin_no_company_headers,
    )
    assert resp.status_code == 400
    assert "must be assigned to a Company Profile before creating users" in resp.json()["detail"]


def test_admin_with_inactive_company_cannot_create_user(client, seeded_data, auth_headers):
    """ADMIN with inactive company cannot create user."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        # Create inactive company
        inactive_company = _create_company(session, "INACT-003", "INACT3", is_active=False)
        # Create admin with inactive company
        admin_inactive = User(
            full_name="Admin Inactive Company",
            email="admininactive@test.com",
            hashed_password=hash_password("Admin@1234"),
            is_active=True,
            company_id=inactive_company.id,
        )
        session.add(admin_inactive)
        session.flush()
        session.add(UserRoleLink(user_id=admin_inactive.id, role_id=admin_role_id))
        session.commit()
        admin_inactive_id = admin_inactive.id

    from core.security import create_access_token
    admin_inactive_headers = {"Authorization": f"Bearer {create_access_token(admin_inactive_id)}"}

    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Maker from Inactive Company Admin",
            "email": "makerinactive@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
        },
        headers=admin_inactive_headers,
    )
    assert resp.status_code == 400
    assert "Admin's company is inactive" in resp.json()["detail"]


def test_multiple_users_same_admin_receive_same_company(client, seeded_data, auth_headers):
    """Multiple users created by same ADMIN receive the same current company."""
    _, engine, _ = client
    with Session(engine) as session:
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        checker_role_id = _get_role_id(session, RoleName.CHECKER)
        auditor_role_id = _get_role_id(session, RoleName.AUDITOR)

    # Create multiple users
    for role_id, role_name in [(maker_role_id, "maker"), (checker_role_id, "checker"), (auditor_role_id, "auditor")]:
        resp = client[0].post(
            "/api/v1/users",
            json={
                "full_name": f"Test {role_name.capitalize()}",
                "email": f"test{role_name}@test.com",
                "password": f"{role_name.capitalize()}@1234",
                "role_ids": [role_id],
            },
            headers=auth_headers["admin"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["company"] is not None
        assert data["company"]["id"] == seeded_data["company_id"]


def test_admin_company_change_affects_new_users(client, seeded_data, auth_headers):
    """If ADMIN's company changes, subsequently created users receive the new company."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        company_b = _create_company(session, "COMP-B", "COMPB")
        company_b_id = company_b.id

    # Get admin ID from seeded data
    admin_id = seeded_data["admin_id"]

    # Update admin's company to Company B (SUPERADMIN can do this)
    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"company_id": company_b_id},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    assert resp.json()["company"]["id"] == company_b_id

    # Now create a new user as the admin - should get Company B
    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Maker After Company Change",
            "email": "makerafterchange@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["company"] is not None
    assert data["company"]["id"] == company_b_id
    assert data["company"]["company_id"] == "COMP-B"


def test_admin_creates_maker_checker_auditor_all_inherit_company(client, seeded_data, auth_headers):
    """ADMIN creates MAKER, CHECKER, AUDITOR — all inherit admin's company."""
    _, engine, _ = client
    with Session(engine) as session:
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        checker_role_id = _get_role_id(session, RoleName.CHECKER)
        auditor_role_id = _get_role_id(session, RoleName.AUDITOR)

    for role_id, role_name in [(maker_role_id, "maker"), (checker_role_id, "checker"), (auditor_role_id, "auditor")]:
        resp = client[0].post(
            "/api/v1/users",
            json={
                "full_name": f"Test {role_name.capitalize()}",
                "email": f"test{role_name}2@test.com",
                "password": f"{role_name.capitalize()}@1234",
                "role_ids": [role_id],
            },
            headers=auth_headers["admin"],
        )
        assert resp.status_code == 201, f"Failed to create {role_name}: {resp.text}"
        data = resp.json()
        assert data["company"] is not None, f"{role_name} should have company"
        assert data["company"]["id"] == seeded_data["company_id"], f"{role_name} should inherit admin's company"


def test_unauthenticated_cannot_create_user(client, seeded_data):
    """Unauthenticated requests are rejected."""
    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Unauth User",
            "email": "unauth@test.com",
            "password": "Test@1234",
            "role_ids": [1],
        },
    )
    assert resp.status_code == 401


# ──────────────────────────────────────────────
# Edit User — ADMIN company assignment
# ──────────────────────────────────────────────

def _create_admin_via_api(client, auth_headers, admin_role_id, company_id):
    """Helper to create an admin user via API (requires company_id for SUPERADMIN)."""
    payload = {
        "full_name": "Test Admin",
        "email": f"testadmin{company_id}@test.com",
        "password": "Admin@1234",
        "role_ids": [admin_role_id],
        "company_id": company_id,
    }
    resp = client[0].post("/api/v1/users", json=payload, headers=auth_headers["superadmin"])
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_maker_via_api(client, auth_headers, maker_role_id):
    """Helper to create a maker user via API (using ADMIN credentials)."""
    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Test Maker",
            "email": "testmaker@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_checker_via_api(client, auth_headers, checker_role_id):
    """Helper to create a checker user via API (using ADMIN credentials)."""
    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Test Checker",
            "email": "testchecker@test.com",
            "password": "Checker@1234",
            "role_ids": [checker_role_id],
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_auditor_via_api(client, auth_headers, auditor_role_id):
    """Helper to create an auditor user via API (using ADMIN credentials)."""
    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Test Auditor",
            "email": "testauditor@test.com",
            "password": "Auditor@1234",
            "role_ids": [auditor_role_id],
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_admin_user_update_company(client, seeded_data, auth_headers):
    """Existing ADMIN user can be updated with a valid active company_id."""
    _, engine, _ = client
    with Session(engine) as session:
        company_a = _create_company(session, "COMP-A", "COMPA")
        company_b = _create_company(session, "COMP-B", "COMPB")
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        company_a_id = company_a.id
        company_b_id = company_b.id

    # Create admin via API with initial company
    admin_id = _create_admin_via_api(client, auth_headers, admin_role_id, company_a_id)

    # Update to company B
    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"company_id": company_b_id},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["company"] is not None
    assert data["company"]["id"] == company_b_id


def test_admin_user_update_invalid_company_rejected(client, seeded_data, auth_headers):
    """Invalid company_id is rejected when updating ADMIN."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        company = _create_company(session, "VALID-001", "VALID")
        company_id = company.id

    admin_id = _create_admin_via_api(client, auth_headers, admin_role_id, company_id)

    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"company_id": 99999},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 400


def test_admin_user_update_inactive_company_rejected(client, seeded_data, auth_headers):
    """Inactive company assignment is rejected when updating ADMIN."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "INACT-002", "INACT2", is_active=False)
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        inactive_company_id = company.id
        # Create a valid company for initial admin creation
        valid_company = _create_company(session, "VALID-002", "VALID2")
        valid_company_id = valid_company.id

    admin_id = _create_admin_via_api(client, auth_headers, admin_role_id, valid_company_id)

    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"company_id": inactive_company_id},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 400


def test_admin_user_update_clear_company(client, seeded_data, auth_headers):
    """ADMIN user's company can be cleared (set to null)."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "CLEAR-001", "CLEAR")
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        company_id = company.id

    # Create admin WITH company initially
    admin_id = _create_admin_via_api(client, auth_headers, admin_role_id, company_id)

    # Clear company by setting to null
    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"company_id": None},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"] is None


def test_non_admin_user_update_ignores_company(client, seeded_data, auth_headers):
    """Non-ADMIN users (MAKER, CHECKER, AUDITOR) cannot have company changed through update by SUPERADMIN."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "IGNORE-001", "IGNR")
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        checker_role_id = _get_role_id(session, RoleName.CHECKER)
        auditor_role_id = _get_role_id(session, RoleName.AUDITOR)
        company_id = company.id

    maker_id = _create_maker_via_api(client, auth_headers, maker_role_id)
    checker_id = _create_checker_via_api(client, auth_headers, checker_role_id)
    auditor_id = _create_auditor_via_api(client, auth_headers, auditor_role_id)

    # Verify created users have inherited admin's company
    resp = client[0].get(f"/api/v1/users/{maker_id}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json()["company"]["id"] == seeded_data["company_id"]

    resp = client[0].get(f"/api/v1/users/{checker_id}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json()["company"]["id"] == seeded_data["company_id"]

    resp = client[0].get(f"/api/v1/users/{auditor_id}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert resp.json()["company"]["id"] == seeded_data["company_id"]

    # Try to assign different company to MAKER — should be ignored (no error, but no assignment)
    resp = client[0].patch(
        f"/api/v1/users/{maker_id}",
        json={"company_id": company_id},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # Company should remain unchanged (non-ADMIN users cannot have company reassigned)
    assert data["company"] is not None
    assert data["company"]["id"] == seeded_data["company_id"]

    # Try to assign different company to CHECKER
    resp = client[0].patch(
        f"/api/v1/users/{checker_id}",
        json={"company_id": company_id},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"] is not None
    assert data["company"]["id"] == seeded_data["company_id"]

    # Try to assign different company to AUDITOR
    resp = client[0].patch(
        f"/api/v1/users/{auditor_id}",
        json={"company_id": company_id},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"] is not None
    assert data["company"]["id"] == seeded_data["company_id"]


def test_maker_update_unchanged(client, seeded_data, auth_headers):
    """Existing MAKER update behavior remains unchanged."""
    resp = client[0].patch(
        "/api/v1/users/999",  # non-existent
        json={"full_name": "Updated"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 404


def test_checker_update_unchanged(client, seeded_data, auth_headers):
    """Existing CHECKER update behavior remains unchanged."""
    _, engine, _ = client
    with Session(engine) as session:
        checker_role_id = _get_role_id(session, RoleName.CHECKER)

    checker_id = _create_checker_via_api(client, auth_headers, checker_role_id)

    resp = client[0].patch(
        f"/api/v1/users/{checker_id}",
        json={"full_name": "Updated Checker"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Checker"


def test_auditor_update_unchanged(client, seeded_data, auth_headers):
    """Existing AUDITOR update behavior remains unchanged."""
    _, engine, _ = client
    with Session(engine) as session:
        auditor_role_id = _get_role_id(session, RoleName.AUDITOR)

    auditor_id = _create_auditor_via_api(client, auth_headers, auditor_role_id)

    resp = client[0].patch(
        f"/api/v1/users/{auditor_id}",
        json={"full_name": "Updated Auditor"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    assert resp.json()["full_name"] == "Updated Auditor"


# ──────────────────────────────────────────────
# SUPERADMIN Edit — Read-only Role Display
# ──────────────────────────────────────────────

def _get_superadmin_role_id(session):
    """Helper to get SUPERADMIN role ID."""
    from users.models import Role
    role = session.exec(select(Role).where(Role.name == RoleName.SUPERADMIN)).first()
    return role.id if role else None


def _create_superadmin_directly(session, company_id):
    """Helper to create a superadmin user directly in DB (bypassing API restrictions)."""
    from core.security import hash_password
    from users.models import User, UserRoleLink, Role
    
    superadmin = User(
        full_name="Test SuperAdmin",
        email=f"superadmin{company_id}@test.com",
        hashed_password=hash_password("SuperAdmin@1234"),
        is_active=True,
        auth_provider="local",
        company_id=company_id,
    )
    session.add(superadmin)
    session.flush()
    
    superadmin_role = session.exec(select(Role).where(Role.name == RoleName.SUPERADMIN)).first()
    session.add(UserRoleLink(user_id=superadmin.id, role_id=superadmin_role.id))
    session.commit()
    session.refresh(superadmin)
    return superadmin.id


def test_superadmin_user_has_superadmin_role(client, seeded_data, auth_headers):
    """SUPERADMIN user is returned with role SUPERADMIN."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "TEST-SA-001", "TESTSA")

    superadmin_id = _create_superadmin_directly(session, company.id)

    resp = client[0].get(f"/api/v1/users/{superadmin_id}", headers=auth_headers["superadmin"])
    assert resp.status_code == 200
    data = resp.json()
    role_names = [r["name"] for r in data["roles"]]
    assert "superadmin" in role_names
    assert "admin" not in role_names


def test_superadmin_edit_returns_superadmin_role(client, seeded_data, auth_headers):
    """SUPERADMIN user edit returns SUPERADMIN role."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "TEST-SA-002", "TESTSA2")

    superadmin_id = _create_superadmin_directly(session, company.id)

    # Edit the superadmin user (just update full_name)
    resp = client[0].patch(
        f"/api/v1/users/{superadmin_id}",
        json={"full_name": "Updated SuperAdmin"},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    role_names = [r["name"] for r in data["roles"]]
    assert "superadmin" in role_names
    assert data["full_name"] == "Updated SuperAdmin"


def test_superadmin_cannot_change_role_via_api(client, seeded_data, auth_headers):
    """SUPERADMIN role changes are silently ignored — roles remain unchanged."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        checker_role_id = _get_role_id(session, RoleName.CHECKER)
        auditor_role_id = _get_role_id(session, RoleName.AUDITOR)
        superadmin_role_id = _get_superadmin_role_id(session)
        company = _create_company(session, "TEST-SA-003", "TESTSA3")
        company_id = company.id

    # Create test users
    admin_id = _create_admin_via_api(client, auth_headers, admin_role_id, company_id)
    maker_id = _create_maker_via_api(client, auth_headers, maker_role_id)
    checker_id = _create_checker_via_api(client, auth_headers, checker_role_id)
    auditor_id = _create_auditor_via_api(client, auth_headers, auditor_role_id)
    
    with Session(engine) as session:
        superadmin_id = _create_superadmin_directly(session, company_id)

    # Try to change ADMIN role to MAKER — silently ignored, returns 200
    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"role_ids": [maker_role_id]},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    # Role should remain ADMIN
    with Session(engine) as session:
        user = session.get(User, admin_id)
        assert any(r.name == RoleName.ADMIN for r in user.roles)

    # Try to change MAKER role to ADMIN — silently ignored
    resp = client[0].patch(
        f"/api/v1/users/{maker_id}",
        json={"role_ids": [admin_role_id]},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    with Session(engine) as session:
        user = session.get(User, maker_id)
        assert any(r.name == RoleName.MAKER for r in user.roles)

    # Try to change CHECKER role to ADMIN — silently ignored
    resp = client[0].patch(
        f"/api/v1/users/{checker_id}",
        json={"role_ids": [admin_role_id]},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    with Session(engine) as session:
        user = session.get(User, checker_id)
        assert any(r.name == RoleName.CHECKER for r in user.roles)

    # Try to change AUDITOR role to ADMIN — silently ignored
    resp = client[0].patch(
        f"/api/v1/users/{auditor_id}",
        json={"role_ids": [admin_role_id]},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    with Session(engine) as session:
        user = session.get(User, auditor_id)
        assert any(r.name == RoleName.AUDITOR for r in user.roles)

    # Try to remove SUPERADMIN role — silently ignored
    resp = client[0].patch(
        f"/api/v1/users/{superadmin_id}",
        json={"role_ids": [admin_role_id]},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    with Session(engine) as session:
        user = session.get(User, superadmin_id)
        assert any(r.name == RoleName.SUPERADMIN for r in user.roles)


def test_superadmin_edit_does_not_show_company_dropdown(client, seeded_data, auth_headers):
    """SUPERADMIN user edit does not allow company assignment."""
    _, engine, _ = client
    with Session(engine) as session:
        company = _create_company(session, "TEST-SA-004", "TESTSA4")
        company_id = company.id
        superadmin_id = _create_superadmin_directly(session, company_id)

    # Edit the superadmin user - try to change company
    resp = client[0].patch(
        f"/api/v1/users/{superadmin_id}",
        json={"company_id": company_id},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    # Company should remain unchanged (SUPERADMIN users cannot have company assigned via update)
    assert data["company"] is not None
    assert data["company"]["id"] == company_id


def test_admin_user_edit_shows_company_dropdown(client, seeded_data, auth_headers):
    """ADMIN user edit shows company dropdown with current company pre-selected."""
    _, engine, _ = client
    with Session(engine) as session:
        admin_role_id = _get_role_id(session, RoleName.ADMIN)
        company = _create_company(session, "TEST-ADMIN-001", "TESTADM")

    admin_id = _create_admin_via_api(client, auth_headers, admin_role_id, company.id)

    # Get the admin user - should include company
    resp = client[0].get(f"/api/v1/users/{admin_id}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"] is not None
    assert data["company"]["id"] == company.id


def test_non_admin_edit_returns_correct_role(client, seeded_data, auth_headers):
    """Non-ADMIN users (MAKER, CHECKER, AUDITOR) return their correct roles."""
    _, engine, _ = client
    with Session(engine) as session:
        maker_role_id = _get_role_id(session, RoleName.MAKER)
        checker_role_id = _get_role_id(session, RoleName.CHECKER)
        auditor_role_id = _get_role_id(session, RoleName.AUDITOR)

    maker_id = _create_maker_via_api(client, auth_headers, maker_role_id)
    checker_id = _create_checker_via_api(client, auth_headers, checker_role_id)
    auditor_id = _create_auditor_via_api(client, auth_headers, auditor_role_id)

    # Get MAKER
    resp = client[0].get(f"/api/v1/users/{maker_id}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert any(r["name"] == "maker" for r in resp.json()["roles"])

    # Get CHECKER
    resp = client[0].get(f"/api/v1/users/{checker_id}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert any(r["name"] == "checker" for r in resp.json()["roles"])

    # Get AUDITOR
    resp = client[0].get(f"/api/v1/users/{auditor_id}", headers=auth_headers["admin"])
    assert resp.status_code == 200
    assert any(r["name"] == "auditor" for r in resp.json()["roles"])


# ──────────────────────────────────────────────
# ADMIN Self-Edit — Company Profile Read-Only
# ──────────────────────────────────────────────

def test_admin_self_edit_company_unchanged(client, seeded_data, auth_headers):
    """ADMIN self-edits name/email — company_id remains unchanged."""
    admin_id = seeded_data["admin_id"]
    original_company_id = seeded_data["company_id"]

    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"full_name": "Admin Updated Self"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["full_name"] == "Admin Updated Self"
    assert data["company"] is not None
    assert data["company"]["id"] == original_company_id


def test_admin_self_edit_cannot_change_company(client, seeded_data, auth_headers):
    """ADMIN tries to change own company_id via API — blocked with 403."""
    _, engine, _ = client
    with Session(engine) as session:
        other_company = _create_company(session, "OTHER-SELF", "OTHSELF")

    admin_id = seeded_data["admin_id"]

    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"company_id": other_company.id},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 403
    assert "cannot change their own company" in resp.json()["detail"].lower()


def test_admin_self_edit_preserves_company_for_new_users(client, seeded_data, auth_headers):
    """ADMIN self-edits, then creates a new user — new user still inherits admin's company."""
    _, engine, _ = client
    with Session(engine) as session:
        maker_role_id = _get_role_id(session, RoleName.MAKER)

    admin_id = seeded_data["admin_id"]
    original_company_id = seeded_data["company_id"]

    # Self-edit (change name only)
    resp = client[0].patch(
        f"/api/v1/users/{admin_id}",
        json={"full_name": "Admin After Self Edit"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    assert resp.json()["company"]["id"] == original_company_id

    # Create a new user — should still inherit admin's company
    resp = client[0].post(
        "/api/v1/users",
        json={
            "full_name": "Maker After Self Edit",
            "email": "makerafterselfedit@test.com",
            "password": "Maker@1234",
            "role_ids": [maker_role_id],
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["company"] is not None
    assert data["company"]["id"] == original_company_id
