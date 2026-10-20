"""Tests for SUPERADMIN visibility hiding and company-scoped ADMIN user list."""

import pytest
from sqlmodel import Session, select

from company_profile.models import Company
from core.security import hash_password
from users.models import RoleName, User, UserRoleLink


def _create_user(session, email, full_name, role_name, company_id=None):
    """Create a user with a single role and return (user, role_id)."""
    from users.models import Role
    role = session.exec(select(Role).where(Role.name == role_name)).first()
    user = User(
        full_name=full_name,
        email=email,
        hashed_password=hash_password("Test@1234"),
        is_active=True,
        company_id=company_id,
    )
    session.add(user)
    session.flush()
    session.add(UserRoleLink(user_id=user.id, role_id=role.id))
    session.commit()
    return user, role.id


def _create_company(session, company_id="COMP-001", short_name="COMP"):
    """Helper to create a test company."""
    company = Company(
        company_id=company_id,
        full_name=f"Test Corp {company_id}",
        short_name=short_name,
        is_active=True,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


# ──────────────────────────────────────────────
# SUPERADMIN visibility
# ──────────────────────────────────────────────

def test_superadmin_list_sees_all_users(client, seeded_data, auth_headers):
    """SUPERADMIN user list must contain all users including other SUPERADMINs."""
    _, engine, _ = client
    with Session(engine) as session:
        _create_user(session, "sa2@test.com", "Second SuperAdmin", RoleName.SUPERADMIN)

    resp = client[0].get(
        "/api/v1/users",
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "sa2@test.com" in emails
    role_names_flat = []
    for user in data["items"]:
        for r in user["roles"]:
            role_names_flat.append(r["name"])
    assert RoleName.SUPERADMIN.value in role_names_flat


def test_superadmin_cross_company_visible(client, seeded_data, auth_headers):
    """SUPERADMIN sees users from all companies."""
    _, engine, _ = client
    with Session(engine) as session:
        comp_b = _create_company(session, "COMP-B", "COMPB")
        _create_user(session, "b_maker@test.com", "B Maker", RoleName.MAKER, comp_b.id)

    resp = client[0].get(
        "/api/v1/users",
        params={"limit": 200},
        headers=auth_headers["superadmin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "b_maker@test.com" in emails
    assert "admin@example.com" in emails


# ──────────────────────────────────────────────
# ADMIN cannot see SUPERADMIN
# ──────────────────────────────────────────────

def test_admin_list_excludes_superadmin(client, seeded_data, auth_headers):
    """ADMIN user list must not contain SUPERADMIN users."""
    resp = client[0].get(
        "/api/v1/users",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    for user in data["items"]:
        role_names = [r["name"] for r in user["roles"]]
        assert RoleName.SUPERADMIN.value not in role_names


def test_admin_search_cannot_find_superadmin(client, seeded_data, auth_headers):
    """ADMIN searching for 'superadmin' must return zero SUPERADMIN results."""
    _, engine, _ = client
    with Session(engine) as session:
        from users.models import Role
        sa_role = session.exec(select(Role).where(Role.name == RoleName.SUPERADMIN)).first()
        sa = User(
            full_name="Super Admin Hidden",
            email="hidden_superadmin@test.com",
            hashed_password=hash_password("Test@1234"),
            is_active=True,
        )
        session.add(sa)
        session.flush()
        session.add(UserRoleLink(user_id=sa.id, role_id=sa_role.id))
        session.commit()

    # Search by name
    resp = client[0].get(
        "/api/v1/users",
        params={"search": "Super Admin"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    for user in data["items"]:
        role_names = [r["name"] for r in user["roles"]]
        assert RoleName.SUPERADMIN.value not in role_names

    # Search by email
    resp = client[0].get(
        "/api/v1/users",
        params={"search": "hidden_superadmin@test.com"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0


# ──────────────────────────────────────────────
# Company isolation — ADMIN sees only own company
# ──────────────────────────────────────────────

def test_admin_sees_own_company_users(client, seeded_data, auth_headers):
    """ADMIN sees users from their own company (TESTCO)."""
    resp = client[0].get(
        "/api/v1/users",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    # seeded admin and maker are both in TESTCO
    assert "admin@example.com" in emails
    assert "maker@example.com" in emails


def test_admin_does_not_see_other_company_users(client, seeded_data, auth_headers):
    """ADMIN from Company A does not see Company B users."""
    _, engine, _ = client
    with Session(engine) as session:
        comp_b = _create_company(session, "OTHER-COMP", "OTHER")
        _create_user(session, "other_maker@test.com", "Other Maker", RoleName.MAKER, comp_b.id)
        _create_user(session, "other_admin@test.com", "Other Admin", RoleName.ADMIN, comp_b.id)

    resp = client[0].get(
        "/api/v1/users",
        params={"limit": 200},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "other_maker@test.com" not in emails
    assert "other_admin@test.com" not in emails


def test_admin_company_b_sees_only_company_b(client, seeded_data, auth_headers):
    """ADMIN from Company B sees only Company B users."""
    _, engine, _ = client
    with Session(engine) as session:
        comp_b = _create_company(session, "COMP-B2", "COMPB2")
        b_admin_user, _ = _create_user(session, "b_admin@test.com", "B Admin", RoleName.ADMIN, comp_b.id)
        _create_user(session, "b_maker@test.com", "B Maker", RoleName.MAKER, comp_b.id)
        b_admin_id = b_admin_user.id

    # Login as Company B admin
    from core.security import create_access_token
    b_headers = {"Authorization": f"Bearer {create_access_token(b_admin_id)}"}

    resp = client[0].get(
        "/api/v1/users",
        params={"limit": 200},
        headers=b_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "b_maker@test.com" in emails
    assert "b_admin@test.com" in emails
    # Company A users must not appear
    assert "admin@example.com" not in emails
    assert "maker@example.com" not in emails


def test_admin_no_company_sees_nothing(client, seeded_data, auth_headers):
    """ADMIN with company_id=None gets empty list."""
    _, engine, _ = client
    with Session(engine) as session:
        _create_user(session, "nocomp_admin@test.com", "No Comp Admin", RoleName.ADMIN)

    from core.security import create_access_token
    with Session(engine) as session:
        nocomp = session.exec(select(User).where(User.email == "nocomp_admin@test.com")).first()
        nocomp_headers = {"Authorization": f"Bearer {create_access_token(nocomp.id)}"}

    resp = client[0].get(
        "/api/v1/users",
        headers=nocomp_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0


# ──────────────────────────────────────────────
# Search scoped to company
# ──────────────────────────────────────────────

def test_admin_search_cross_company_no_results(client, seeded_data, auth_headers):
    """ADMIN searching for another company's user returns no results."""
    _, engine, _ = client
    with Session(engine) as session:
        comp_b = _create_company(session, "SEARCH-COMP", "SRCH")
        _create_user(session, "search_other@test.com", "Other Person", RoleName.MAKER, comp_b.id)

    resp = client[0].get(
        "/api/v1/users",
        params={"search": "Other Person"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert len(data["items"]) == 0

    resp = client[0].get(
        "/api/v1/users",
        params={"search": "search_other@test.com"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0


def test_admin_search_finds_own_company_user(client, seeded_data, auth_headers):
    """ADMIN searching finds users from their own company."""
    resp = client[0].get(
        "/api/v1/users",
        params={"search": "Maker"},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "maker@example.com" in emails


# ──────────────────────────────────────────────
# Pagination scoped to company
# ──────────────────────────────────────────────

def test_pagination_total_scoped_to_company(client, seeded_data, auth_headers):
    """Pagination total reflects company-scoped count."""
    _, engine, _ = client
    with Session(engine) as session:
        # Same company users (TESTCO)
        _create_user(session, "same1@test.com", "Same 1", RoleName.MAKER, seeded_data["company_id"])
        _create_user(session, "same2@test.com", "Same 2", RoleName.MAKER, seeded_data["company_id"])
        # Different company user
        comp_b = _create_company(session, "PAG-COMP", "PAGC")
        _create_user(session, "diff1@test.com", "Diff 1", RoleName.MAKER, comp_b.id)

    resp = client[0].get(
        "/api/v1/users",
        params={"limit": 200},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    full_data = resp.json()
    emails = [u["email"] for u in full_data["items"]]
    # Same company users visible
    assert "same1@test.com" in emails
    assert "same2@test.com" in emails
    # Different company user not visible
    assert "diff1@test.com" not in emails
    # Total should be admin + maker + same1 + same2 = 4
    assert full_data["total"] == 4


def test_pagination_page_scoped_to_company(client, seeded_data, auth_headers):
    """Pagination page only contains same-company users."""
    _, engine, _ = client
    with Session(engine) as session:
        _create_user(session, "page_a@test.com", "Page A", RoleName.MAKER, seeded_data["company_id"])
        comp_b = _create_company(session, "PAGE-COMP", "PAGEC")
        _create_user(session, "page_b@test.com", "Page B", RoleName.MAKER, comp_b.id)

    resp = client[0].get(
        "/api/v1/users",
        params={"skip": 0, "limit": 2},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    for user in data["items"]:
        # Every returned user must be from the admin's company (TESTCO) or be the admin itself
        company = user.get("company")
        if company is not None:
            assert company["id"] == seeded_data["company_id"]
        else:
            # Admin user has a company, so this should not happen
            assert user["email"] == "admin@example.com"


# ──────────────────────────────────────────────
# Filters scoped to company
# ──────────────────────────────────────────────

def test_admin_filter_by_status_scoped_to_company(client, seeded_data, auth_headers):
    """Filtering by is_active applies company scope."""
    _, engine, _ = client
    with Session(engine) as session:
        comp_b = _create_company(session, "STATUS-COMP", "STC")
        _create_user(session, "status_other@test.com", "Status Other", RoleName.MAKER, comp_b.id)

    resp = client[0].get(
        "/api/v1/users",
        params={"is_active": True},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "status_other@test.com" not in emails


def test_admin_filter_by_level_scoped_to_company(client, seeded_data, auth_headers):
    """Filtering by user_level_id applies company scope."""
    _, engine, _ = client
    with Session(engine) as session:
        comp_b = _create_company(session, "LEVEL-COMP", "LVC")
        _create_user(session, "level_other@test.com", "Level Other", RoleName.MAKER, comp_b.id)

    resp = client[0].get(
        "/api/v1/users",
        params={"user_level_id": seeded_data["high_level_id"]},
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    for user in data["items"]:
        role_names = [r["name"] for r in user["roles"]]
        assert RoleName.SUPERADMIN.value not in role_names
    emails = [u["email"] for u in data["items"]]
    assert "level_other@test.com" not in emails


# ──────────────────────────────────────────────
# Company column
# ──────────────────────────────────────────────

def test_company_column_still_returns_for_visible_users(client, seeded_data, auth_headers):
    """Company data must still be returned for non-SUPERADMIN users."""
    resp = client[0].get(
        "/api/v1/users",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    admin_users = [u for u in data["items"] if u["email"] == "admin@example.com"]
    assert len(admin_users) == 1
    assert admin_users[0]["company"] is not None
    assert admin_users[0]["company"]["short_name"] == "TESTCO"


def test_company_column_populated_for_company_users(client, seeded_data, auth_headers):
    """Users in the same company should have company data populated."""
    resp = client[0].get(
        "/api/v1/users",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    for user in data["items"]:
        if user["email"] in ("admin@example.com", "maker@example.com"):
            assert user["company"] is not None
            assert user["company"]["short_name"] == "TESTCO"


# ──────────────────────────────────────────────
# Regression — other roles unaffected
# ──────────────────────────────────────────────

def test_admin_still_sees_own_company_roles(client, seeded_data, auth_headers):
    """ADMIN can see MAKER, CHECKER, AUDITOR, and other ADMIN users in same company."""
    _, engine, _ = client
    with Session(engine) as session:
        _create_user(session, "reg_checker@test.com", "Reg Checker", RoleName.CHECKER, seeded_data["company_id"])
        _create_user(session, "reg_auditor@test.com", "Reg Auditor", RoleName.AUDITOR, seeded_data["company_id"])

    resp = client[0].get(
        "/api/v1/users",
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data["items"]]
    assert "admin@example.com" in emails
    assert "maker@example.com" in emails
    assert "reg_checker@test.com" in emails
    assert "reg_auditor@test.com" in emails
