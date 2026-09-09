"""Tests for the SUPERADMIN role."""

import pytest
from sqlmodel import Session, select

from core.security import create_access_token, hash_password
from users.models import (
    Permission,
    PermissionAction,
    Role,
    RoleName,
    RolePermissionLink,
    User,
    UserRoleLink,
)


# ── Helpers ────────────────────────────────────

def _create_superadmin_fixture(engine):
    """Create SUPERADMIN role + user in the test DB. Returns (role, user)."""
    with Session(engine) as session:
        # Create SUPERADMIN role with all permissions
        sa_role = Role(name=RoleName.SUPERADMIN, description="Super Admin")
        session.add(sa_role)
        session.flush()

        for action in PermissionAction:
            perm = session.exec(
                select(Permission).where(Permission.action == action)
            ).first()
            if perm:
                session.add(RolePermissionLink(role_id=sa_role.id, permission_id=perm.id))

        # Create superadmin user
        sa_user = User(
            full_name="Super Admin",
            email="superadmin@test.com",
            hashed_password=hash_password("SuperAdmin@1234"),
            is_active=True,
        )
        session.add(sa_user)
        session.flush()

        session.add(UserRoleLink(user_id=sa_user.id, role_id=sa_role.id))
        session.commit()

        return {"role_id": sa_role.id, "user_id": sa_user.id}


# ── Model Tests ────────────────────────────────

class TestSuperAdminRoleEnum:
    def test_superadmin_role_name_exists(self):
        assert hasattr(RoleName, "SUPERADMIN")
        assert RoleName.SUPERADMIN == "superadmin"

    def test_superadmin_is_admin_true(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # Use the existing SUPERADMIN role from seeded_data
            role = session.exec(
                select(Role).where(Role.name == RoleName.SUPERADMIN)
            ).first()
            assert role is not None

            user = User(
                full_name="SA User",
                email="sa_model@test.com",
                hashed_password=hash_password("Test@1234"),
                is_active=True,
            )
            session.add(user)
            session.flush()
            session.add(UserRoleLink(user_id=user.id, role_id=role.id))
            session.commit()

            # Re-fetch to load relationships
            user = session.get(User, user.id)
            assert user.is_admin() is True


# ── Seed Tests ─────────────────────────────────

class TestSuperAdminSeed:
    def test_seed_creates_superadmin_role(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            role = session.exec(
                select(Role).where(Role.name == RoleName.SUPERADMIN)
            ).first()
            assert role is not None
            assert role.name == RoleName.SUPERADMIN
            assert role.description == "Full system access; manages admins & companies"

    def test_seed_creates_superadmin_user(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == "superadmin@dms.local")
            ).first()
            assert user is not None
            assert user.full_name == "Super Administrator"
            assert any(r.name == RoleName.SUPERADMIN for r in user.roles)

    def test_seed_superadmin_has_all_permissions(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            role = session.exec(
                select(Role).where(Role.name == RoleName.SUPERADMIN)
            ).first()
            assert role is not None
            perm_actions = {p.action for p in role.permissions}
            assert perm_actions == {
                PermissionAction.VIEW,
                PermissionAction.DOWNLOAD,
                PermissionAction.CREATE,
                PermissionAction.UPDATE,
                PermissionAction.DELETE,
            }

    def test_seed_idempotent_no_duplicate_role(self, seeded_data, client):
        _, engine, _ = client
        # Run seed logic again
        from seed import seed
        seed()

        with Session(engine) as session:
            roles = session.exec(
                select(Role).where(Role.name == RoleName.SUPERADMIN)
            ).all()
            assert len(roles) == 1

    def test_seed_idempotent_no_duplicate_user(self, seeded_data, client):
        _, engine, _ = client
        from seed import seed
        seed()

        with Session(engine) as session:
            users = session.exec(
                select(User).where(User.email == "superadmin@dms.local")
            ).all()
            assert len(users) == 1


# ── Auth Tests ─────────────────────────────────

class TestSuperAdminAuth:
    def test_superadmin_can_login(self, seeded_data, client):
        test_client, engine, _ = client
        response = test_client.post(
            "/api/v1/auth/login",
            json={"email": "superadmin@dms.local", "password": "SuperAdmin@1234"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_superadmin_auth_headers(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == "superadmin@dms.local")
            ).first()
            assert user is not None
            token = create_access_token(user.id)
            assert token is not None


# ── Authorization Tests ────────────────────────

class TestSuperAdminAuthorization:
    def _get_superadmin_headers(self, engine):
        with Session(engine) as session:
            user = session.exec(
                select(User).where(User.email == "superadmin@dms.local")
            ).first()
            if not user:
                pytest.skip("Super admin user not seeded")
            token = create_access_token(user.id)
            return {"Authorization": f"Bearer {token}"}

    def test_superadmin_can_create_admin_user(self, seeded_data, client):
        test_client, engine, _ = client
        headers = self._get_superadmin_headers(engine)

        # Get admin role ID and create a test company
        with Session(engine) as session:
            admin_role = session.exec(
                select(Role).where(Role.name == RoleName.ADMIN)
            ).first()
            admin_role_id = admin_role.id

            from company_profile.models import Company
            company = Company(
                company_id="TEST-SA-001",
                full_name="Test Company",
                short_name="TST",
                is_active=True,
            )
            session.add(company)
            session.commit()
            session.refresh(company)
            company_id = company.id

        response = test_client.post(
            "/api/v1/users",
            json={
                "full_name": "New Admin",
                "email": "new_admin@test.com",
                "password": "Admin@1234",
                "is_active": True,
                "role_ids": [admin_role_id],
                "company_id": company_id,
            },
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "new_admin@test.com"
        assert any(r["name"] == "admin" for r in data["roles"])
        assert data["company"]["id"] == company_id

    def test_superadmin_cannot_create_maker(self, seeded_data, client):
        test_client, engine, _ = client
        headers = self._get_superadmin_headers(engine)

        with Session(engine) as session:
            maker_role = session.exec(
                select(Role).where(Role.name == RoleName.MAKER)
            ).first()
            maker_role_id = maker_role.id

        response = test_client.post(
            "/api/v1/users",
            json={
                "full_name": "New Maker",
                "email": "new_maker@test.com",
                "password": "Maker@1234",
                "is_active": True,
                "role_ids": [maker_role_id],
            },
            headers=headers,
        )
        assert response.status_code == 403
        assert "Super Admin can only create Admin users" in response.json()["detail"]

    def test_superadmin_cannot_create_checker(self, seeded_data, client):
        test_client, engine, _ = client
        headers = self._get_superadmin_headers(engine)

        with Session(engine) as session:
            checker_role = session.exec(
                select(Role).where(Role.name == RoleName.CHECKER)
            ).first()
            checker_role_id = checker_role.id

        response = test_client.post(
            "/api/v1/users",
            json={
                "full_name": "New Checker",
                "email": "new_checker@test.com",
                "password": "Checker@1234",
                "is_active": True,
                "role_ids": [checker_role_id],
            },
            headers=headers,
        )
        assert response.status_code == 403

    def test_superadmin_cannot_create_auditor(self, seeded_data, client):
        test_client, engine, _ = client
        headers = self._get_superadmin_headers(engine)

        with Session(engine) as session:
            auditor_role = session.exec(
                select(Role).where(Role.name == RoleName.AUDITOR)
            ).first()
            auditor_role_id = auditor_role.id

        response = test_client.post(
            "/api/v1/users",
            json={
                "full_name": "New Auditor",
                "email": "new_auditor@test.com",
                "password": "Auditor@1234",
                "is_active": True,
                "role_ids": [auditor_role_id],
            },
            headers=headers,
        )
        assert response.status_code == 403

    def test_superadmin_cannot_create_superadmin(self, seeded_data, client):
        test_client, engine, _ = client
        headers = self._get_superadmin_headers(engine)

        with Session(engine) as session:
            sa_role = session.exec(
                select(Role).where(Role.name == RoleName.SUPERADMIN)
            ).first()
            sa_role_id = sa_role.id

        response = test_client.post(
            "/api/v1/users",
            json={
                "full_name": "Another SA",
                "email": "another_sa@test.com",
                "password": "SuperAdmin@1234",
                "is_active": True,
                "role_ids": [sa_role_id],
            },
            headers=headers,
        )
        assert response.status_code == 403

    def test_superadmin_bypasses_rbac_middleware(self, seeded_data, client):
        test_client, engine, _ = client
        headers = self._get_superadmin_headers(engine)

        # Super admin can list users (requires admin, which SA bypasses)
        response = test_client.get("/api/v1/users", headers=headers)
        assert response.status_code == 200

    def test_superadmin_can_list_roles(self, seeded_data, client):
        test_client, engine, _ = client
        headers = self._get_superadmin_headers(engine)

        response = test_client.get("/api/v1/users/roles/all", headers=headers)
        assert response.status_code == 200
        roles = response.json()
        role_names = {r["name"] for r in roles}
        assert "superadmin" in role_names
        assert "admin" in role_names


# ── Role Protection Tests ──────────────────────

class TestSuperAdminRoleProtection:
    def test_cannot_create_superadmin_role_via_api(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        response = test_client.post(
            "/api/v1/users/roles",
            json={
                "name": "superadmin",
                "description": "Hacked role",
                "permission_ids": [],
            },
            headers=auth_headers["admin"],
        )
        assert response.status_code == 403
        assert "Cannot create Super Admin role via API" in response.json()["detail"]


# ── Regression Tests ───────────────────────────

class TestRegression:
    def test_admin_role_still_works(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        response = test_client.get(
            "/api/v1/users",
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200

    def test_maker_role_unchanged(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            role = session.exec(
                select(Role).where(Role.name == RoleName.MAKER)
            ).first()
            assert role is not None
            perm_actions = {p.action for p in role.permissions}
            assert perm_actions == {
                PermissionAction.VIEW,
                PermissionAction.DOWNLOAD,
                PermissionAction.CREATE,
                PermissionAction.UPDATE,
            }

    def test_checker_role_unchanged(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            role = session.exec(
                select(Role).where(Role.name == RoleName.CHECKER)
            ).first()
            # Checker may not be seeded in tests, but if it exists, verify
            if role:
                perm_actions = {p.action for p in role.permissions}
                assert perm_actions == {
                    PermissionAction.VIEW,
                    PermissionAction.DOWNLOAD,
                    PermissionAction.UPDATE,
                }

    def test_auditor_role_unchanged(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            role = session.exec(
                select(Role).where(Role.name == RoleName.AUDITOR)
            ).first()
            if role:
                perm_actions = {p.action for p in role.permissions}
                assert perm_actions == {
                    PermissionAction.VIEW,
                    PermissionAction.DOWNLOAD,
                }

    def test_existing_admin_user_unaffected(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        response = test_client.get(
            f"/api/v1/users/{seeded_data['admin_id']}",
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "admin@example.com"
        assert any(r["name"] == "admin" for r in data["roles"])
