"""Tests for audit trail company filtering (Spec 19)."""

import pytest
from sqlmodel import Session, select

from audit.models import AuditAction, AuditLog, AuditModule
from audit.repository import AuditRepository
from audit.service import AuditService
from company_profile.models import Company
from users.models import User, UserRoleLink, Role, RoleName


def _create_audit_log(session, *, company_id=None, user_id=None, action=AuditAction.LOGIN, module=AuditModule.AUTH, **kwargs):
    """Helper to create audit log records for testing."""
    log = AuditLog(
        company_id=company_id,
        user_id=user_id,
        action=action.value,
        module=module.value,
        description=kwargs.get("description", "Test event"),
        is_success=kwargs.get("is_success", True),
    )
    session.add(log)
    session.flush()
    return log


# ── ADMIN Company Isolation ────────────────────────


class TestAdminCompanyIsolation:
    def test_admin_sees_own_company_audit_records(self, seeded_data, client):
        """ADMIN should only see audit records from their own company."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            admin_id = seeded_data["admin_id"]

            # Create audit records for admin's company
            _create_audit_log(session, company_id=company_id, user_id=admin_id, description="Own company event 1")
            _create_audit_log(session, company_id=company_id, user_id=admin_id, description="Own company event 2")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

            response = test_client.get("/api/v1/audit-logs", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2

    def test_admin_does_not_see_other_company_records(self, seeded_data, client):
        """ADMIN should NOT see audit records from other companies."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            admin_id = seeded_data["admin_id"]

            # Create audit records for admin's company
            _create_audit_log(session, company_id=company_id, description="Own company")

            # Create audit records for another company
            other_company = Company(
                company_id="OTHER-COMP-999",
                full_name="Other Company",
                short_name="OTHERCO",
                is_active=True,
            )
            session.add(other_company)
            session.flush()
            _create_audit_log(session, company_id=other_company.id, description="Other company")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

            response = test_client.get("/api/v1/audit-logs", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["description"] == "Own company"

    def test_company_b_admin_sees_own_company_records(self, seeded_data, client):
        """Company B admin should only see Company B audit records."""
        _, engine, _ = client
        with Session(engine) as session:
            # Create a second company and admin
            other_company = Company(
                company_id="COMP-B-001",
                full_name="Company B",
                short_name="COMPB",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            other_admin = User(
                full_name="Company B Admin",
                email="admin-b@example.com",
                hashed_password="$2b$12$invalid",
                is_active=True,
                company_id=other_company.id,
            )
            session.add(other_admin)
            session.flush()

            admin_role = session.exec(
                select(Role).where(Role.name == RoleName.ADMIN)
            ).first()
            session.add(UserRoleLink(user_id=other_admin.id, role_id=admin_role.id))
            session.flush()

            # Create audit records for both companies
            _create_audit_log(session, company_id=seeded_data["company_id"], description="Company A event")
            _create_audit_log(session, company_id=other_company.id, description="Company B event")
            _create_audit_log(session, company_id=other_company.id, description="Company B event 2")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(other_admin.id)}"}

            response = test_client.get("/api/v1/audit-logs", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert all(item["company_id"] == other_company.id for item in data["items"])

    def test_admin_cannot_override_company_via_param(self, seeded_data, client):
        """ADMIN should be auto-scoped to their company; company_id param should be ignored."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            admin_id = seeded_data["admin_id"]

            other_company = Company(
                company_id="OTHER-COMP-OVERRIDE",
                full_name="Other Override",
                short_name="OTHEROVR",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            _create_audit_log(session, company_id=company_id, description="Own company")
            _create_audit_log(session, company_id=other_company.id, description="Other company")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

            # Try to request other company's logs via query param
            response = test_client.get(
                f"/api/v1/audit-logs?company_id={other_company.id}",
                headers=headers,
            )
            assert response.status_code == 200
            data = response.json()
            # Should be scoped to own company, not the requested one
            assert data["total"] == 1
            assert data["items"][0]["description"] == "Own company"

    def test_admin_cannot_view_other_company_detail(self, seeded_data, client):
        """ADMIN should not be able to view another company's audit log detail."""
        _, engine, _ = client
        with Session(engine) as session:
            other_company = Company(
                company_id="OTHER-DETAIL",
                full_name="Other Detail",
                short_name="OTHERDTL",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            other_log = _create_audit_log(session, company_id=other_company.id, description="Other company detail")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

            response = test_client.get(f"/api/v1/audit-logs/{other_log.id}", headers=headers)
            assert response.status_code == 403

    def test_admin_export_scoped_to_own_company(self, seeded_data, client):
        """ADMIN export should only contain own-company records."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            admin_id = seeded_data["admin_id"]

            other_company = Company(
                company_id="OTHER-EXPORT",
                full_name="Other Export",
                short_name="OTHEXP",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            _create_audit_log(session, company_id=company_id, description="Own export event")
            _create_audit_log(session, company_id=other_company.id, description="Other export event")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

            response = test_client.get("/api/v1/audit-logs/export", headers=headers)
            assert response.status_code == 200
            csv_content = response.content.decode()
            assert "Own export event" in csv_content
            assert "Other export event" not in csv_content

    def test_search_remains_company_scoped(self, seeded_data, client):
        """Search should remain scoped to the admin's company."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            admin_id = seeded_data["admin_id"]

            other_company = Company(
                company_id="OTHER-SEARCH",
                full_name="Other Search",
                short_name="OTHSEARCH",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            _create_audit_log(session, company_id=company_id, description="admin@example.com login")
            _create_audit_log(session, company_id=other_company.id, description="other@example.com login")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

            response = test_client.get(
                "/api/v1/audit-logs?search=admin@example.com",
                headers=headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1

    def test_pagination_remains_company_scoped(self, seeded_data, client):
        """Pagination should only count own-company records."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            admin_id = seeded_data["admin_id"]

            other_company = Company(
                company_id="OTHER-PAGE",
                full_name="Other Page",
                short_name="OTHPAGE",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            for i in range(5):
                _create_audit_log(session, company_id=company_id, description=f"Own {i}")
            for i in range(10):
                _create_audit_log(session, company_id=other_company.id, description=f"Other {i}")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

            response = test_client.get("/api/v1/audit-logs?limit=3", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 5
            assert len(data["items"]) == 3

    def test_date_filter_remains_company_scoped(self, seeded_data, client):
        """Date filters should remain scoped to the admin's company."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            admin_id = seeded_data["admin_id"]

            other_company = Company(
                company_id="OTHER-DATE",
                full_name="Other Date",
                short_name="OTHDATE",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            _create_audit_log(session, company_id=company_id, description="Own dated event")
            _create_audit_log(session, company_id=other_company.id, description="Other dated event")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(admin_id)}"}

            response = test_client.get("/api/v1/audit-logs", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["description"] == "Own dated event"


# ── SUPERADMIN Company Context ─────────────────────


class TestSuperAdminCompanyContext:
    def test_superadmin_can_request_company_a_logs(self, seeded_data, client):
        """SUPERADMIN should be able to view Company A audit records."""
        _, engine, _ = client
        with Session(engine) as session:
            company_a_id = seeded_data["company_id"]
            superadmin_id = seeded_data["superadmin_id"]

            company_b = Company(
                company_id="COMP-B-CTX",
                full_name="Company B",
                short_name="COMPB",
                is_active=True,
            )
            session.add(company_b)
            session.flush()

            _create_audit_log(session, company_id=company_a_id, description="Company A event")
            _create_audit_log(session, company_id=company_b.id, description="Company B event")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}

            response = test_client.get(
                f"/api/v1/audit-logs?company_id={company_a_id}",
                headers=headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["description"] == "Company A event"

    def test_superadmin_can_request_company_b_logs(self, seeded_data, client):
        """SUPERADMIN should be able to view Company B audit records."""
        _, engine, _ = client
        with Session(engine) as session:
            company_a_id = seeded_data["company_id"]
            superadmin_id = seeded_data["superadmin_id"]

            company_b = Company(
                company_id="COMP-B-CTX2",
                full_name="Company B2",
                short_name="COMPB2",
                is_active=True,
            )
            session.add(company_b)
            session.flush()

            _create_audit_log(session, company_id=company_a_id, description="Company A event")
            _create_audit_log(session, company_id=company_b.id, description="Company B event")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}

            response = test_client.get(
                f"/api/v1/audit-logs?company_id={company_b.id}",
                headers=headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["description"] == "Company B event"

    def test_superadmin_company_a_returns_only_company_a(self, seeded_data, client):
        """SUPERADMIN selecting Company A should see only Company A records."""
        _, engine, _ = client
        with Session(engine) as session:
            company_a_id = seeded_data["company_id"]
            superadmin_id = seeded_data["superadmin_id"]

            company_b = Company(
                company_id="COMP-B-FILTER",
                full_name="Company B Filter",
                short_name="COMPBF",
                is_active=True,
            )
            session.add(company_b)
            session.flush()

            _create_audit_log(session, company_id=company_a_id, description="A1")
            _create_audit_log(session, company_id=company_a_id, description="A2")
            _create_audit_log(session, company_id=company_b.id, description="B1")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}

            response = test_client.get(
                f"/api/v1/audit-logs?company_id={company_a_id}",
                headers=headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2

    def test_superadmin_no_company_returns_empty(self, seeded_data, client):
        """SUPERADMIN with no company_id should see empty results."""
        _, engine, _ = client
        with Session(engine) as session:
            superadmin_id = seeded_data["superadmin_id"]
            _create_audit_log(session, company_id=1, description="Some event")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}

            response = test_client.get("/api/v1/audit-logs", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0

    def test_superadmin_invalid_company_returns_empty(self, seeded_data, client):
        """SUPERADMIN with invalid company_id should return empty results."""
        _, engine, _ = client
        with Session(engine) as session:
            superadmin_id = seeded_data["superadmin_id"]
            _create_audit_log(session, company_id=1, description="Some event")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}

            response = test_client.get("/api/v1/audit-logs?company_id=99999", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0

    def test_superadmin_detail_for_selected_company(self, seeded_data, client):
        """SUPERADMIN should be able to retrieve detail for selected company."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            superadmin_id = seeded_data["superadmin_id"]

            log = _create_audit_log(session, company_id=company_id, description="Detail test")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}

            response = test_client.get(f"/api/v1/audit-logs/{log.id}", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert data["description"] == "Detail test"

    def test_superadmin_export_restricted_to_selected_company(self, seeded_data, client):
        """SUPERADMIN export should only contain records from the selected company."""
        _, engine, _ = client
        with Session(engine) as session:
            company_a_id = seeded_data["company_id"]
            superadmin_id = seeded_data["superadmin_id"]

            company_b = Company(
                company_id="COMP-B-EXP",
                full_name="Company B Export",
                short_name="COMPBEX",
                is_active=True,
            )
            session.add(company_b)
            session.flush()

            _create_audit_log(session, company_id=company_a_id, description="Export A")
            _create_audit_log(session, company_id=company_b.id, description="Export B")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(superadmin_id)}"}

            response = test_client.get(
                f"/api/v1/audit-logs/export?company_id={company_a_id}",
                headers=headers,
            )
            assert response.status_code == 200
            csv_content = response.content.decode()
            assert "Export A" in csv_content
            assert "Export B" not in csv_content


# ── Historical / System Events ─────────────────────


class TestHistoricalAndSystemEvents:
    def test_backfilled_records_have_company_id(self, seeded_data, client):
        """After migration, existing audit records should have company_id backfilled from user."""
        _, engine, _ = client
        with Session(engine) as session:
            admin_id = seeded_data["admin_id"]
            company_id = seeded_data["company_id"]

            # Create audit record with user_id but no company_id (simulating pre-migration)
            log = AuditLog(
                user_id=admin_id,
                action=AuditAction.LOGIN.value,
                module=AuditModule.AUTH.value,
                description="Pre-migration event",
                is_success=True,
            )
            session.add(log)
            session.flush()

            # Simulate backfill
            from sqlmodel import text
            session.execute(text("""
                UPDATE audit_logs
                SET company_id = (
                    SELECT users.company_id
                    FROM users
                    WHERE users.id = audit_logs.user_id
                    AND users.company_id IS NOT NULL
                )
                WHERE audit_logs.user_id IS NOT NULL
                AND audit_logs.company_id IS NULL
            """))
            session.commit()

            session.refresh(log)
            assert log.company_id == company_id

    def test_events_without_user_have_null_company(self, seeded_data, client):
        """System events without user_id should have NULL company_id."""
        _, engine, _ = client
        with Session(engine) as session:
            log = _create_audit_log(session, company_id=None, description="System event")
            session.commit()

            assert log.company_id is None

    def test_user_events_get_company_from_user(self, seeded_data, client):
        """Events with a user should get company_id from that user."""
        _, engine, _ = client
        with Session(engine) as session:
            user = session.get(User, seeded_data["admin_id"])
            svc = AuditService(session)
            svc.log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                company_id=user.company_id,
                description="User login with company",
                is_success=True,
                user=user,
            )
            session.commit()

            log = session.exec(
                select(AuditLog).where(AuditLog.description == "User login with company")
            ).first()
            assert log is not None
            assert log.company_id == seeded_data["company_id"]


# ── Company ID in Audit Log Response ───────────────


class TestAuditLogCompanyIdInResponse:
    def test_list_response_includes_company_id(self, seeded_data, client):
        """Audit log list response should include company_id field."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            _create_audit_log(session, company_id=company_id, description="Response test")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

            response = test_client.get("/api/v1/audit-logs", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) >= 1
            assert "company_id" in data["items"][0]
            assert data["items"][0]["company_id"] == company_id

    def test_detail_response_includes_company_id(self, seeded_data, client):
        """Audit log detail response should include company_id field."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            log = _create_audit_log(session, company_id=company_id, description="Detail response test")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

            response = test_client.get(f"/api/v1/audit-logs/{log.id}", headers=headers)
            assert response.status_code == 200
            data = response.json()
            assert "company_id" in data
            assert data["company_id"] == company_id

    def test_csv_export_includes_company_id(self, seeded_data, client):
        """CSV export should include Company ID column."""
        _, engine, _ = client
        with Session(engine) as session:
            company_id = seeded_data["company_id"]
            _create_audit_log(session, company_id=company_id, description="CSV test")
            session.commit()

            from core.security import create_access_token
            test_client, _, _ = client
            headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

            response = test_client.get("/api/v1/audit-logs/export", headers=headers)
            assert response.status_code == 200
            csv_content = response.content.decode()
            assert "Company ID" in csv_content
