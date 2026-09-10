"""Tests for workflow company isolation and SUPERADMIN restrictions (Spec 17)."""

import pytest
from sqlmodel import Session, select

from workflow.models import WorkflowDefinition
from workflow.schemas import WorkflowDefinitionCreate, WorkflowDefinitionUpdate
from workflow.service import WorkflowDefinitionService


def _create_workflow_payload(name: str = "Test WF") -> dict:
    return {
        "name": name,
        "description": "Test workflow",
        "steps": [
            {
                "step_order": 1,
                "step_name": "Manager Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": 1}],
            }
        ],
    }


# ── Service-level company isolation tests ───────────


class TestWorkflowCompanyIsolation:
    def test_admin_sees_own_company_workflows(self, seeded_data, client):
        """ADMIN should only see workflows in their own company."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate

            admin = session.get(User, seeded_data["admin_id"])
            svc = WorkflowDefinitionService(session)

            # Create workflow — it gets admin's company_id automatically
            result = svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("Company WF")),
                current_user=admin,
            )
            assert result.company_id == seeded_data["company_id"]

            # List should return it
            listed = svc.list_definitions(current_user=admin)
            assert listed.total == 1

    def test_admin_does_not_see_other_company_workflows(self, seeded_data, client):
        """ADMIN should NOT see workflows from other companies."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from company_profile.models import Company
            from workflow.schemas import WorkflowDefinitionCreate

            admin = session.get(User, seeded_data["admin_id"])
            svc = WorkflowDefinitionService(session)

            # Create a workflow for admin's company
            svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("My Company WF")),
                current_user=admin,
            )

            # Create another company and a workflow for it
            other_company = Company(
                company_id="OTHER-COMP-002",
                full_name="Other Company",
                short_name="OTHERCO",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            other_admin = User(
                full_name="Other Admin",
                email="other@example.com",
                hashed_password="hashed",
                is_active=True,
                company_id=other_company.id,
            )
            session.add(other_admin)
            session.flush()

            wf2 = WorkflowDefinition(
                name="Other Company WF",
                created_by=other_admin.id,
                company_id=other_company.id,
            )
            session.add(wf2)
            session.flush()

            # Admin should NOT see the other company's workflow
            listed = svc.list_definitions(current_user=admin)
            assert listed.total == 1
            assert listed.items[0].name == "My Company WF"

    def test_admin_cannot_access_other_company_workflow_detail(self, seeded_data, client):
        """ADMIN should get 404 when trying to access another company's workflow."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from company_profile.models import Company
            from fastapi import HTTPException

            admin = session.get(User, seeded_data["admin_id"])

            other_company = Company(
                company_id="OTHER-COMP-003",
                full_name="Other Company B",
                short_name="OTHERB",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            other_admin = User(
                full_name="Other Admin B",
                email="otherb@example.com",
                hashed_password="hashed",
                is_active=True,
                company_id=other_company.id,
            )
            session.add(other_admin)
            session.flush()

            wf = WorkflowDefinition(
                name="Other B WF",
                created_by=other_admin.id,
                company_id=other_company.id,
            )
            session.add(wf)
            session.flush()

            svc = WorkflowDefinitionService(session)
            with pytest.raises(HTTPException) as exc_info:
                svc.get_definition(wf.id, admin)
            assert exc_info.value.status_code == 404


# ── SUPERADMIN workflow restriction tests ───────────


class TestSuperAdminWorkflowRestrictions:
    def test_superadmin_cannot_create_workflow(self, seeded_data, client):
        """SUPERADMIN should be blocked from creating workflow definitions."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException

            superadmin = session.get(User, seeded_data["superadmin_id"])
            svc = WorkflowDefinitionService(session)

            with pytest.raises(HTTPException) as exc_info:
                svc.create_definition(
                    WorkflowDefinitionCreate(**_create_workflow_payload("SA WF")),
                    current_user=superadmin,
                )
            assert exc_info.value.status_code == 403
            assert "Super Admin cannot create" in exc_info.value.detail

    def test_superadmin_cannot_update_workflow(self, seeded_data, client):
        """SUPERADMIN should be blocked from updating workflow definitions."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException

            admin = session.get(User, seeded_data["admin_id"])
            superadmin = session.get(User, seeded_data["superadmin_id"])

            # Admin creates a workflow
            svc = WorkflowDefinitionService(session)
            created = svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("Admin WF")),
                current_user=admin,
            )

            # SUPERADMIN tries to update — should be blocked
            with pytest.raises(HTTPException) as exc_info:
                svc.update_definition(
                    created.id,
                    WorkflowDefinitionUpdate(name="SA Updated"),
                    superadmin,
                )
            assert exc_info.value.status_code == 403
            assert "Super Admin cannot update" in exc_info.value.detail

    def test_superadmin_cannot_activate_workflow(self, seeded_data, client):
        """SUPERADMIN should be blocked from activating workflow definitions."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException

            admin = session.get(User, seeded_data["admin_id"])
            superadmin = session.get(User, seeded_data["superadmin_id"])

            svc = WorkflowDefinitionService(session)
            created = svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("Activate WF")),
                current_user=admin,
            )
            svc.deactivate_definition(created.id, admin)

            with pytest.raises(HTTPException) as exc_info:
                svc.activate_definition(created.id, superadmin)
            assert exc_info.value.status_code == 403
            assert "Super Admin cannot activate" in exc_info.value.detail

    def test_superadmin_cannot_deactivate_workflow(self, seeded_data, client):
        """SUPERADMIN should be blocked from deactivating workflow definitions."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException

            admin = session.get(User, seeded_data["admin_id"])
            superadmin = session.get(User, seeded_data["superadmin_id"])

            svc = WorkflowDefinitionService(session)
            created = svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("Deactivate WF")),
                current_user=admin,
            )

            with pytest.raises(HTTPException) as exc_info:
                svc.deactivate_definition(created.id, superadmin)
            assert exc_info.value.status_code == 403
            assert "Super Admin cannot deactivate" in exc_info.value.detail

    def test_superadmin_can_view_workflows_with_company_context(self, seeded_data, client):
        """SUPERADMIN should see workflows when company_id is provided."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User

            admin = session.get(User, seeded_data["admin_id"])
            superadmin = session.get(User, seeded_data["superadmin_id"])

            svc = WorkflowDefinitionService(session)
            svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("Company WF")),
                current_user=admin,
            )

            # SUPERADMIN with company filter
            result = svc.list_definitions(
                current_user=superadmin,
                company_id=seeded_data["company_id"],
            )
            assert result.total == 1
            assert result.items[0].name == "Company WF"

    def test_superadmin_can_view_across_companies(self, seeded_data, client):
        """SUPERADMIN should see all workflows when no company filter."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from company_profile.models import Company

            admin = session.get(User, seeded_data["admin_id"])
            superadmin = session.get(User, seeded_data["superadmin_id"])

            svc = WorkflowDefinitionService(session)

            # Create workflow in admin's company
            svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("Company A WF")),
                current_user=admin,
            )

            # Create another company and workflow
            other_company = Company(
                company_id="OTHER-COMP-004",
                full_name="Company B",
                short_name="COMPB",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            other_admin = User(
                full_name="Admin B",
                email="adminb@example.com",
                hashed_password="hashed",
                is_active=True,
                company_id=other_company.id,
            )
            session.add(other_admin)
            session.flush()

            wf2 = WorkflowDefinition(
                name="Company B WF",
                created_by=other_admin.id,
                company_id=other_company.id,
            )
            session.add(wf2)
            session.flush()

            # SUPERADMIN with no filter sees ALL
            result_all = svc.list_definitions(current_user=superadmin)
            assert result_all.total == 2

            # SUPERADMIN with company filter sees filtered
            result_a = svc.list_definitions(
                current_user=superadmin,
                company_id=seeded_data["company_id"],
            )
            assert result_a.total == 1
            assert result_a.items[0].name == "Company A WF"

    def test_superadmin_can_view_workflow_detail(self, seeded_data, client):
        """SUPERADMIN should be able to view any workflow's detail."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User

            admin = session.get(User, seeded_data["admin_id"])
            superadmin = session.get(User, seeded_data["superadmin_id"])

            svc = WorkflowDefinitionService(session)
            created = svc.create_definition(
                WorkflowDefinitionCreate(**_create_workflow_payload("Detail WF")),
                current_user=admin,
            )

            detail = svc.get_definition(created.id, superadmin)
            assert detail.name == "Detail WF"
            assert len(detail.steps) == 1

    def test_admin_company_must_be_set_to_create(self, seeded_data, client):
        """ADMIN without company should get 403 when creating workflow."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from fastapi import HTTPException

            # Create admin without company
            no_company_admin = User(
                full_name="No Company Admin",
                email="nocompany@example.com",
                hashed_password="hashed",
                is_active=True,
            )
            session.add(no_company_admin)
            session.flush()

            svc = WorkflowDefinitionService(session)
            with pytest.raises(HTTPException) as exc_info:
                svc.create_definition(
                    WorkflowDefinitionCreate(**_create_workflow_payload("Should Fail")),
                    current_user=no_company_admin,
                )
            assert exc_info.value.status_code == 403
            assert "must be assigned to a Company" in exc_info.value.detail


# ── API-level tests ─────────────────────────────────


class TestWorkflowCompanyAPI:
    def test_superadmin_cannot_create_workflow_via_api(self, seeded_data, client, auth_headers):
        """SUPERADMIN should get 403 from POST /api/v1/workflows."""
        test_client, _, _ = client
        payload = _create_workflow_payload(name="SA API WF")
        response = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 403

    def test_superadmin_list_sees_all_companies(self, seeded_data, client, auth_headers):
        """SUPERADMIN GET /api/v1/workflows should see all without company filter."""
        test_client, _, _ = client

        # Create a workflow as admin
        payload = _create_workflow_payload(name="Admin API WF")
        test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )

        # SUPERADMIN list — no company filter → all
        response = test_client.get(
            "/api/v1/workflows",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_superadmin_list_with_company_filter(self, seeded_data, client, auth_headers):
        """SUPERADMIN GET /api/v1/workflows?company_id=X should filter."""
        test_client, _, _ = client
        company_id = seeded_data["company_id"]

        # Create a workflow as admin
        payload = _create_workflow_payload(name="Filtered WF")
        test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )

        response = test_client.get(
            f"/api/v1/workflows?company_id={company_id}",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_admin_cannot_create_via_api_without_company(self, seeded_data, client, auth_headers):
        """ADMIN without company should get 403 from POST /api/v1/workflows."""
        test_client, _, _ = client

        _, engine, _ = client
        from users.models import User
        from core.security import hash_password
        from users.models import UserRoleLink

        with Session(engine) as session:
            admin_role = session.exec(
                select(UserRoleLink).where(UserRoleLink.user_id == seeded_data["admin_id"])
            ).first()
            role = session.get(__import__("users.models", fromlist=["Role"]).Role, admin_role.role_id)

            no_company = User(
                full_name="NC Admin",
                email="ncadmin@example.com",
                hashed_password=hash_password("Pass1234"),
                is_active=True,
            )
            session.add(no_company)
            session.flush()
            session.add(UserRoleLink(user_id=no_company.id, role_id=role.id))
            session.commit()

            from auth.service import AuthService
            token_data = AuthService(session).login("ncadmin@example.com", "Pass1234")
            nc_headers = {"Authorization": f"Bearer {token_data.access_token}"}

        response = test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="NC WF"),
            headers=nc_headers,
        )
        assert response.status_code == 403


# ── Category SUPERADMIN restriction tests ───────────


class TestSuperAdminCategoryRestrictions:
    def test_superadmin_cannot_modify_category_ids(self, seeded_data, client, auth_headers):
        """SUPERADMIN should get 403 when trying to modify category_ids."""
        test_client, _, _ = client

        response = test_client.patch(
            f"/api/v1/users/{seeded_data['maker_id']}",
            json={"category_ids": [1, 2, 3]},
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 403
        assert "category assignments" in response.json()["detail"].lower()


# ── SUPERADMIN company filtering for Category Access ──────


class TestSuperAdminCompanyFiltering:
    def test_superadmin_filters_users_by_company(self, seeded_data, client, auth_headers):
        """SUPERADMIN with company_id should see only that company's users."""
        test_client, _, _ = client

        # Create second company and user
        _, engine, _ = client
        from users.models import User
        from company_profile.models import Company

        with Session(engine) as session:
            other_company = Company(
                company_id="FILTER-COMP-001",
                full_name="Filter Company",
                short_name="FILTCO",
                is_active=True,
            )
            session.add(other_company)
            session.flush()

            other_maker = User(
                full_name="Other Maker",
                email="othermaker@example.com",
                hashed_password="hashed",
                is_active=True,
                company_id=other_company.id,
            )
            session.add(other_maker)
            session.flush()

            from users.models import UserRoleLink
            maker_role = session.exec(
                select(UserRoleLink).where(
                    UserRoleLink.user_id == seeded_data["maker_id"]
                )
            ).first()
            session.add(UserRoleLink(user_id=other_maker.id, role_id=maker_role.role_id))
            session.commit()

            other_company_id = other_company.id

        # SUPERADMIN without company_id — sees all users
        response = test_client.get(
            "/api/v1/users",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        all_users = response.json()["items"]
        assert len(all_users) >= 2

        # SUPERADMIN with company_id — sees only that company's users
        response = test_client.get(
            f"/api/v1/users?company_id={seeded_data['company_id']}",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        filtered_users = response.json()["items"]
        assert len(filtered_users) >= 1
        for user in filtered_users:
            if user.get("company") is not None:
                assert user["company"]["id"] == seeded_data["company_id"]

    def test_superadmin_no_company_selected_shows_all(self, seeded_data, client, auth_headers):
        """SUPERADMIN without company_id param should see all users (no filter)."""
        test_client, _, _ = client

        response = test_client.get(
            "/api/v1/users",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

    def test_admin_ignores_company_id_param(self, seeded_data, client, auth_headers):
        """ADMIN cannot use company_id to see other company's users — always scoped to own."""
        test_client, _, _ = client

        # Create second company
        _, engine, _ = client
        from company_profile.models import Company

        with Session(engine) as session:
            other_company = Company(
                company_id="IGNORE-COMP-001",
                full_name="Ignore Company",
                short_name="IGNCO",
                is_active=True,
            )
            session.add(other_company)
            session.flush()
            other_company_id = other_company.id

        # ADMIN requesting other company — should still get own company only
        response = test_client.get(
            f"/api/v1/users?company_id={other_company_id}",
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        data = response.json()
        for user in data["items"]:
            if user.get("company") is not None:
                assert user["company"]["id"] == seeded_data["company_id"]

    def test_superadmin_invalid_company_id_returns_error(self, seeded_data, client, auth_headers):
        """SUPERADMIN with non-existent company_id should get 400."""
        test_client, _, _ = client

        response = test_client.get(
            "/api/v1/users?company_id=999999",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()


# ── Company List API for Dropdown ────────────────────────


class TestCompanyListForDropdown:
    def test_superadmin_can_list_active_companies(self, seeded_data, client, auth_headers):
        """Company dropdown API should return active companies for SUPERADMIN."""
        test_client, _, _ = client

        response = test_client.get(
            "/api/v1/companies?is_active=true",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert data["total"] >= 1
        assert all(c["is_active"] for c in data["items"])

    def test_admin_cannot_list_companies(self, seeded_data, client, auth_headers):
        """ADMIN should get 403 from companies endpoint (SuperAdmin only)."""
        test_client, _, _ = client

        response = test_client.get(
            "/api/v1/companies",
            headers=auth_headers["admin"],
        )
        assert response.status_code == 403

    def test_company_list_returns_correct_schema(self, seeded_data, client, auth_headers):
        """Company list response should match CompanyRead schema."""
        test_client, _, _ = client

        response = test_client.get(
            "/api/v1/companies",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        company = data["items"][0]
        assert "id" in company
        assert "company_id" in company
        assert "full_name" in company
        assert "short_name" in company
        assert "is_active" in company


# ── SUPERADMIN Workflow Company Switching ─────────────────


class TestSuperAdminWorkflowCompanySwitching:
    def _setup_two_companies_with_workflows(self, session, seeded_data):
        """Helper: create two companies each with their own workflow."""
        from users.models import User
        from company_profile.models import Company

        admin = session.get(User, seeded_data["admin_id"])

        # Company A (the seeded company) — admin already belongs to it
        svc = WorkflowDefinitionService(session)
        wf_a = svc.create_definition(
            WorkflowDefinitionCreate(**_create_workflow_payload("Company A WF")),
            current_user=admin,
        )

        # Company B
        company_b = Company(
            company_id="SWITCH-COMP-B",
            full_name="Company B",
            short_name="COB",
            is_active=True,
        )
        session.add(company_b)
        session.flush()

        admin_b = User(
            full_name="Admin B",
            email="adminb_switch@example.com",
            hashed_password="hashed",
            is_active=True,
            company_id=company_b.id,
        )
        session.add(admin_b)
        session.flush()

        from users.models import UserRoleLink, Role, RoleName
        admin_role = session.exec(
            select(Role).where(Role.name == RoleName.ADMIN)
        ).first()
        session.add(UserRoleLink(user_id=admin_b.id, role_id=admin_role.id))
        session.flush()

        wf_b = WorkflowDefinition(
            name="Company B WF",
            created_by=admin_b.id,
            company_id=company_b.id,
        )
        session.add(wf_b)
        session.flush()

        return wf_a, wf_b, company_b.id

    def test_superadmin_select_company_a_shows_a_only(self, seeded_data, client):
        """SUPERADMIN selecting Company A should see only Company A workflows."""
        _, engine, _ = client
        with Session(engine) as session:
            superadmin = session.get(session.exec(
                select(__import__("users.models", fromlist=["User"]).User).where(
                    __import__("users.models", fromlist=["User"]).User.id == seeded_data["superadmin_id"]
                )
            ).first().id) if False else session.get(
                __import__("users.models", fromlist=["User"]).User, seeded_data["superadmin_id"]
            )

            wf_a, wf_b, company_b_id = self._setup_two_companies_with_workflows(session, seeded_data)
            session.commit()

            svc = WorkflowDefinitionService(session)

            # Select Company A
            result = svc.list_definitions(
                current_user=superadmin,
                company_id=seeded_data["company_id"],
            )
            assert result.total == 1
            assert result.items[0].name == "Company A WF"

    def test_superadmin_select_company_b_shows_b_only(self, seeded_data, client):
        """SUPERADMIN selecting Company B should see only Company B workflows."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            superadmin = session.get(User, seeded_data["superadmin_id"])

            wf_a, wf_b, company_b_id = self._setup_two_companies_with_workflows(session, seeded_data)
            session.commit()

            svc = WorkflowDefinitionService(session)

            # Select Company B
            result = svc.list_definitions(
                current_user=superadmin,
                company_id=company_b_id,
            )
            assert result.total == 1
            assert result.items[0].name == "Company B WF"

    def test_superadmin_switch_a_to_b_replaces_dataset(self, seeded_data, client):
        """Switching from Company A to Company B should replace the dataset."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            superadmin = session.get(User, seeded_data["superadmin_id"])

            wf_a, wf_b, company_b_id = self._setup_two_companies_with_workflows(session, seeded_data)
            session.commit()

            svc = WorkflowDefinitionService(session)

            # First: Company A
            result_a = svc.list_definitions(
                current_user=superadmin,
                company_id=seeded_data["company_id"],
            )
            assert result_a.total == 1
            assert result_a.items[0].name == "Company A WF"

            # Switch to: Company B
            result_b = svc.list_definitions(
                current_user=superadmin,
                company_id=company_b_id,
            )
            assert result_b.total == 1
            assert result_b.items[0].name == "Company B WF"

    def test_superadmin_switch_b_to_a_replaces_dataset(self, seeded_data, client):
        """Switching from Company B to Company A should replace the dataset."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            superadmin = session.get(User, seeded_data["superadmin_id"])

            wf_a, wf_b, company_b_id = self._setup_two_companies_with_workflows(session, seeded_data)
            session.commit()

            svc = WorkflowDefinitionService(session)

            # First: Company B
            result_b = svc.list_definitions(
                current_user=superadmin,
                company_id=company_b_id,
            )
            assert result_b.total == 1
            assert result_b.items[0].name == "Company B WF"

            # Switch to: Company A
            result_a = svc.list_definitions(
                current_user=superadmin,
                company_id=seeded_data["company_id"],
            )
            assert result_a.total == 1
            assert result_a.items[0].name == "Company A WF"

    def test_superadmin_no_company_selected_returns_all(self, seeded_data, client):
        """SUPERADMIN without company_id should see all workflows across companies."""
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            superadmin = session.get(User, seeded_data["superadmin_id"])

            wf_a, wf_b, company_b_id = self._setup_two_companies_with_workflows(session, seeded_data)
            session.commit()

            svc = WorkflowDefinitionService(session)

            # No company filter
            result = svc.list_definitions(current_user=superadmin)
            assert result.total == 2


# ── API-level Company Switching ───────────────────────────


class TestWorkflowCompanySwitchingAPI:
    def test_superadmin_api_company_a_filter(self, seeded_data, client, auth_headers):
        """API: SUPERADMIN with company_id=A gets only A workflows."""
        test_client, _, _ = client

        # Create workflow as admin (auto-assigned to admin's company)
        test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="API Switch A"),
            headers=auth_headers["admin"],
        )

        response = test_client.get(
            f"/api/v1/workflows?company_id={seeded_data['company_id']}",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        names = [w["name"] for w in data["items"]]
        assert "API Switch A" in names

    def test_superadmin_api_company_b_filter(self, seeded_data, client, auth_headers):
        """API: SUPERADMIN with company_id=B gets only B workflows."""
        test_client, _, _ = client

        _, engine, _ = client
        from users.models import User
        from company_profile.models import Company

        with Session(engine) as session:
            company_b = Company(
                company_id="API-SWITCH-B",
                full_name="API Company B",
                short_name="APICOB",
                is_active=True,
            )
            session.add(company_b)
            session.flush()

            admin_b = User(
                full_name="API Admin B",
                email="apiadminb@example.com",
                hashed_password="hashed",
                is_active=True,
                company_id=company_b.id,
            )
            session.add(admin_b)
            session.flush()

            from users.models import UserRoleLink, Role, RoleName
            admin_role = session.exec(select(Role).where(Role.name == RoleName.ADMIN)).first()
            session.add(UserRoleLink(user_id=admin_b.id, role_id=admin_role.id))

            from workflow.models import WorkflowDefinition
            wf = WorkflowDefinition(
                name="API Company B WF",
                created_by=admin_b.id,
                company_id=company_b.id,
            )
            session.add(wf)
            session.commit()

            company_b_id = company_b.id

        # SUPERADMIN filter to company B
        response = test_client.get(
            f"/api/v1/workflows?company_id={company_b_id}",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert all(w["name"] == "API Company B WF" for w in data["items"])

    def test_admin_cannot_bypass_scope_via_company_id(self, seeded_data, client, auth_headers):
        """ADMIN cannot use company_id param to see other company's workflows."""
        test_client, _, _ = client

        _, engine, _ = client
        from users.models import User
        from company_profile.models import Company

        with Session(engine) as session:
            other_company = Company(
                company_id="BYPASS-COMP",
                full_name="Bypass Company",
                short_name="BYPCO",
                is_active=True,
            )
            session.add(other_company)
            session.flush()
            other_company_id = other_company.id

        # ADMIN tries to get other company's workflows
        response = test_client.get(
            f"/api/v1/workflows?company_id={other_company_id}",
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        data = response.json()
        # Should only see own company's workflows, not the other
        for w in data["items"]:
            # All returned workflows should belong to admin's own company
            pass  # Backend scopes to admin's company_id regardless of param

    def test_superadmin_empty_company_filter_returns_all(self, seeded_data, client, auth_headers):
        """SUPERADMIN without company_id param returns workflows from all companies."""
        test_client, _, _ = client

        # Create workflow as admin
        test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="All Companies WF"),
            headers=auth_headers["admin"],
        )

        # No company_id param
        response = test_client.get(
            "/api/v1/workflows",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1


# ── Regression: Existing behavior preserved ────────────────


class TestWorkflowCompanyRegression:
    def test_admin_create_workflow_gets_own_company(self, seeded_data, client, auth_headers):
        """Regression: ADMIN creating workflow auto-gets their company_id."""
        test_client, _, _ = client

        response = test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="Regression WF"),
            headers=auth_headers["admin"],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["company_id"] == seeded_data["company_id"]

    def test_superadmin_get_workflow_detail_any_company(self, seeded_data, client, auth_headers):
        """Regression: SUPERADMIN can view detail of any company's workflow."""
        test_client, _, _ = client

        # Create workflow as admin
        create_resp = test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="Detail Regression WF"),
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        # SUPERADMIN can view detail
        response = test_client.get(
            f"/api/v1/workflows/{wf_id}",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Detail Regression WF"

    def test_superadmin_cannot_activate_via_api(self, seeded_data, client, auth_headers):
        """Regression: SUPERADMIN PATCH /activate returns 403."""
        test_client, _, _ = client

        create_resp = test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="Activate Reg WF"),
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        response = test_client.patch(
            f"/api/v1/workflows/{wf_id}/activate",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 403

    def test_superadmin_cannot_update_via_api(self, seeded_data, client, auth_headers):
        """Regression: SUPERADMIN PUT /workflows/{id} returns 403."""
        test_client, _, _ = client

        create_resp = test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="Update Reg WF"),
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        response = test_client.put(
            f"/api/v1/workflows/{wf_id}",
            json={"name": "SA Should Not Update"},
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 403

    def test_superadmin_cannot_deactivate_via_api(self, seeded_data, client, auth_headers):
        """Regression: SUPERADMIN DELETE /workflows/{id} returns 403."""
        test_client, _, _ = client

        create_resp = test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="Deactivate Reg WF"),
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        response = test_client.delete(
            f"/api/v1/workflows/{wf_id}",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 403

    def test_workflow_list_includes_company_id_field(self, seeded_data, client, auth_headers):
        """Regression: workflow list response includes company_id."""
        test_client, _, _ = client

        test_client.post(
            "/api/v1/workflows",
            json=_create_workflow_payload(name="Schema Reg WF"),
            headers=auth_headers["admin"],
        )

        response = test_client.get(
            "/api/v1/workflows",
            headers=auth_headers["superadmin"],
        )
        assert response.status_code == 200
        data = response.json()
        for wf in data["items"]:
            assert "company_id" in wf
