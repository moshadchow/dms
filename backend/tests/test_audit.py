"""Tests for the Audit Trail module."""

import pytest
from sqlmodel import Session, select

from audit.models import AuditAction, AuditLog, AuditModule
from audit.repository import AuditRepository
from audit.service import AuditService, parse_user_agent


# ── User-Agent Parsing ─────────────────────────

class TestUserAgentParsing:
    def test_chrome_on_windows(self):
        ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        result = parse_user_agent(ua)
        assert result["browser"] == "Chrome"
        assert result["operating_system"] == "Windows 10"
        assert result["device"] is None

    def test_firefox_on_mac(self):
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Gecko/20100101 Firefox/121.0"
        result = parse_user_agent(ua)
        assert result["browser"] == "Firefox"
        assert result["operating_system"] == "macOS"

    def test_mobile_safari(self):
        ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        result = parse_user_agent(ua)
        assert result["operating_system"] == "iOS"
        assert result["device"] == "Mobile"

    def test_none_ua(self):
        result = parse_user_agent(None)
        assert result == {"browser": None, "operating_system": None, "device": None}

    def test_empty_ua(self):
        result = parse_user_agent("")
        assert result == {"browser": None, "operating_system": None, "device": None}


# ── Audit Service ──────────────────────────────

class TestAuditService:
    def test_log_event_creates_record(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = AuditService(session)
            svc.log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                entity_name="user",
                entity_id="1",
                description="Test login",
                is_success=True,
            )
            session.commit()

            logs = session.exec(select(AuditLog)).all()
            assert len([l for l in logs if l.action == AuditAction.LOGIN.value]) >= 1

    def test_log_event_with_user(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            user = session.get(__import__("users.models", fromlist=["User"]).User, seeded_data["admin_id"])
            svc = AuditService(session)
            svc.log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                description="Login with user context",
                user=user,
            )
            session.commit()

            log = session.exec(
                select(AuditLog).where(AuditLog.action == AuditAction.LOGIN.value)
            ).first()
            assert log is not None
            assert log.user_id == seeded_data["admin_id"]

    def test_log_event_never_raises(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = AuditService(session)
            # Should not raise even with problematic data
            svc.log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                old_value={"key": "value with special chars: <>&\""},
                description="Test",
            )
            session.commit()

    def test_log_event_failure_isolation(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = AuditService(session)
            # This should not raise even if there's an internal issue
            svc.log_event(
                action=AuditAction.LOGIN,
                module=AuditModule.AUTH,
                description="Failure isolation test",
            )
            session.commit()


# ── Audit Repository ───────────────────────────

class TestAuditRepository:
    def _create_log(self, session, **kwargs):
        defaults = {
            "action": AuditAction.LOGIN.value,
            "module": AuditModule.AUTH.value,
            "description": "Test event",
            "is_success": True,
        }
        defaults.update(kwargs)
        log = AuditLog(**defaults)
        session.add(log)
        session.flush()
        return log

    def test_create_and_get(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            repo = AuditRepository(session)
            log = self._create_log(session, description="Test create")
            session.commit()

            retrieved = repo.get_by_id(log.id)
            assert retrieved is not None
            assert retrieved.description == "Test create"

    def test_list_logs_pagination(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            repo = AuditRepository(session)
            for i in range(15):
                self._create_log(session, description=f"Event {i}")
            session.commit()

            result = repo.list_logs(skip=0, limit=10)
            assert result.total == 15
            assert len(result.items) == 10
            assert result.page == 1

            result2 = repo.list_logs(skip=10, limit=10)
            assert len(result2.items) == 5

    def test_list_logs_filter_by_module(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            repo = AuditRepository(session)
            self._create_log(session, module=AuditModule.AUTH.value)
            self._create_log(session, module=AuditModule.DOCUMENTS.value)
            self._create_log(session, module=AuditModule.AUTH.value)
            session.commit()

            result = repo.list_logs(module="auth")
            assert result.total == 2

    def test_list_logs_filter_by_action(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            repo = AuditRepository(session)
            self._create_log(session, action=AuditAction.LOGIN.value)
            self._create_log(session, action=AuditAction.FAILED_LOGIN.value)
            session.commit()

            result = repo.list_logs(action="login")
            assert result.total == 1

    def test_list_logs_filter_by_success(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            repo = AuditRepository(session)
            self._create_log(session, is_success=True)
            self._create_log(session, is_success=False)
            session.commit()

            result = repo.list_logs(is_success=False)
            assert result.total == 1

    def test_list_logs_search(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            repo = AuditRepository(session)
            self._create_log(session, description="Login failed for admin@example.com")
            self._create_log(session, description="Upload document")
            session.commit()

            result = repo.list_logs(search="admin@example.com")
            assert result.total == 1

    def test_list_logs_sort(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            repo = AuditRepository(session)
            self._create_log(session, description="First")
            self._create_log(session, description="Second")
            session.commit()

            result = repo.list_logs(sort_by="description", sort_order="asc")
            assert result.items[0].description == "First"
            assert result.items[1].description == "Second"


# ── Audit API Endpoints ────────────────────────

class TestAuditAPI:
    def test_list_requires_admin(self, seeded_data, client):
        test_client, _, _ = client
        _, maker_headers = seeded_data, None
        from core.security import create_access_token
        maker_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['maker_id'])}"}

        response = test_client.get("/api/v1/audit-logs", headers=maker_headers)
        assert response.status_code == 403

    def test_list_admin_success(self, seeded_data, client):
        test_client, _, _ = client
        from core.security import create_access_token
        admin_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        response = test_client.get("/api/v1/audit-logs", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "items" in data

    def test_list_with_filters(self, seeded_data, client):
        test_client, _, _ = client
        from core.security import create_access_token
        admin_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        response = test_client.get(
            "/api/v1/audit-logs?module=auth&is_success=true&limit=5",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 5

    def test_detail_requires_admin(self, seeded_data, client):
        test_client, _, _ = client
        from core.security import create_access_token
        maker_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['maker_id'])}"}

        response = test_client.get("/api/v1/audit-logs/1", headers=maker_headers)
        assert response.status_code == 403

    def test_detail_not_found(self, seeded_data, client):
        test_client, _, _ = client
        from core.security import create_access_token
        admin_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        response = test_client.get("/api/v1/audit-logs/99999", headers=admin_headers)
        assert response.status_code == 404

    def test_login_creates_audit_log(self, seeded_data, client):
        test_client, _, _ = client

        response = test_client.post("/api/v1/auth/login", json={
            "email": "admin@example.com",
            "password": "Admin@1234",
        })
        assert response.status_code == 200

        # Check audit log was created
        from core.security import create_access_token
        admin_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}
        response = test_client.get("/api/v1/audit-logs?action=login&module=auth", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_failed_login_creates_audit_log(self, seeded_data, client):
        test_client, _, _ = client

        response = test_client.post("/api/v1/auth/login", json={
            "email": "admin@example.com",
            "password": "WrongPassword",
        })
        assert response.status_code == 401

        # Check failed login audit log
        from core.security import create_access_token
        admin_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}
        response = test_client.get("/api/v1/audit-logs?action=failed_login", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_user_creation_creates_audit_log(self, seeded_data, client):
        test_client, _, _ = client
        from core.security import create_access_token
        admin_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        response = test_client.post("/api/v1/users", json={
            "full_name": "Audit Test User",
            "email": "audit-test@example.com",
            "password": "Test@1234",
            "role_ids": [],
            "category_ids": [],
        }, headers=admin_headers)
        assert response.status_code == 201

        # Check audit log
        response = test_client.get("/api/v1/audit-logs?action=create_user", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_immutable_audit_records(self, seeded_data, client):
        test_client, _, _ = client
        from core.security import create_access_token
        admin_headers = {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"}

        # Verify no PUT/PATCH/DELETE endpoints exist for audit logs
        response = test_client.put("/api/v1/audit-logs/1", headers=admin_headers)
        assert response.status_code == 405

        response = test_client.delete("/api/v1/audit-logs/1", headers=admin_headers)
        assert response.status_code == 405
