"""Tests for the Workflow module — Phase 1: Foundation + Phase 2: Submission."""

import pytest
from sqlmodel import Session, select

from workflow.models import (
    ApprovalAction,
    WorkflowAction,
    WorkflowDefinition,
    WorkflowHistory,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepApprover,
)
from workflow.schemas import WorkflowActionCreate, WorkflowInstanceCreate
from workflow.service import ApprovalActionService, WorkflowDefinitionService, WorkflowInstanceService


# ── Helpers ──────────────────────────────────────


def _create_workflow_payload(
    name: str = "Invoice Approval",
    category_id: int = 1,
    steps: list | None = None,
) -> dict:
    if steps is None:
        steps = [
            {
                "step_order": 1,
                "step_name": "Manager Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": 1, "priority": 0}],
            }
        ]
    return {
        "name": name,
        "description": "Test workflow",
        "document_category_id": category_id,
        "steps": steps,
    }


# ── Service Tests ────────────────────────────────


class TestWorkflowDefinitionService:
    def test_create_definition(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            payload = _create_workflow_payload(
                category_id=seeded_data["finance_category_id"],
            )
            # We need to pass current_user; use admin from seeded_data
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            result = svc.create_definition(
                __import__("workflow.schemas", fromlist=["WorkflowDefinitionCreate"]).WorkflowDefinitionCreate(**payload),
                current_user=admin,
            )
            assert result.name == "Invoice Approval"
            assert result.document_category_id == seeded_data["finance_category_id"]
            assert result.is_active is True

    def test_create_definition_rejects_duplicate_name(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate
            admin = session.get(User, seeded_data["admin_id"])

            payload = _create_workflow_payload(
                name="Unique Workflow",
                category_id=seeded_data["finance_category_id"],
            )
            svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)

            with pytest.raises(Exception) as exc_info:
                svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)
            assert "already exists" in str(exc_info.value.detail)

    def test_get_definition(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate
            admin = session.get(User, seeded_data["admin_id"])

            payload = _create_workflow_payload(
                name="Get Test WF",
                category_id=seeded_data["finance_category_id"],
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)
            result = svc.get_definition(created.id)
            assert result.name == "Get Test WF"
            assert len(result.steps) == 1
            assert result.steps[0].step_name == "Manager Review"

    def test_list_definitions(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate
            admin = session.get(User, seeded_data["admin_id"])

            for i in range(3):
                payload = _create_workflow_payload(
                    name=f"List WF {i}",
                    category_id=seeded_data["finance_category_id"],
                )
                svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)

            result = svc.list_definitions()
            assert result.total == 3
            assert len(result.items) == 3

    def test_list_definitions_filter_by_category(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate
            admin = session.get(User, seeded_data["admin_id"])

            payload_finance = _create_workflow_payload(
                name="Finance WF",
                category_id=seeded_data["finance_category_id"],
            )
            payload_hr = _create_workflow_payload(
                name="HR WF",
                category_id=seeded_data["hr_category_id"],
            )
            svc.create_definition(WorkflowDefinitionCreate(**payload_finance), current_user=admin)
            svc.create_definition(WorkflowDefinitionCreate(**payload_hr), current_user=admin)

            result = svc.list_definitions(category_id=seeded_data["finance_category_id"])
            assert result.total == 1
            assert result.items[0].name == "Finance WF"

    def test_update_definition(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate, WorkflowDefinitionUpdate
            admin = session.get(User, seeded_data["admin_id"])

            payload = _create_workflow_payload(
                name="Update WF",
                category_id=seeded_data["finance_category_id"],
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)

            update = WorkflowDefinitionUpdate(name="Updated WF Name")
            result = svc.update_definition(created.id, update)
            assert result.name == "Updated WF Name"

    def test_deactivate_definition(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate
            admin = session.get(User, seeded_data["admin_id"])

            payload = _create_workflow_payload(
                name="Deactivate WF",
                category_id=seeded_data["finance_category_id"],
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)
            result = svc.deactivate_definition(created.id)
            assert result.is_active is False

    def test_activate_definition(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate
            admin = session.get(User, seeded_data["admin_id"])

            payload = _create_workflow_payload(
                name="Activate WF",
                category_id=seeded_data["finance_category_id"],
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)
            svc.deactivate_definition(created.id)
            result = svc.activate_definition(created.id)
            assert result.is_active is True

    def test_validate_step_requires_approvers(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from workflow.schemas import WorkflowDefinitionCreate
            from fastapi import HTTPException

            steps = [
                {
                    "step_order": 1,
                    "step_name": "Empty Step",
                    "approval_mode": "sequential",
                    "approvers": [],
                }
            ]
            with pytest.raises(HTTPException) as exc_info:
                WorkflowDefinitionService._validate_step_approvers(
                    [__import__("workflow.schemas", fromlist=["WorkflowStepCreate"]).WorkflowStepCreate(**s) for s in steps]
                )
            assert "at least one approver" in str(exc_info.value.detail)

    def test_validate_approver_exactly_one_of_user_or_role(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from workflow.schemas import WorkflowStepCreate, WorkflowStepApproverCreate
            from fastapi import HTTPException

            step = WorkflowStepCreate(
                step_order=1,
                step_name="Bad Approver",
                approvers=[WorkflowStepApproverCreate(user_id=1, role_id=1)],
            )
            with pytest.raises(HTTPException) as exc_info:
                WorkflowDefinitionService._validate_step_approvers([step])
            assert "exactly one" in str(exc_info.value.detail)

    def test_update_replaces_steps(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate, WorkflowDefinitionUpdate, WorkflowStepCreate, WorkflowStepApproverCreate
            admin = session.get(User, seeded_data["admin_id"])

            payload = _create_workflow_payload(
                name="Replace Steps WF",
                category_id=seeded_data["finance_category_id"],
                steps=[
                    {
                        "step_order": 1,
                        "step_name": "Step 1",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": 1, "priority": 0}],
                    }
                ],
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)

            new_steps = [
                WorkflowStepCreate(
                    step_order=1,
                    step_name="New Step A",
                    approval_mode="parallel",
                    approvers=[WorkflowStepApproverCreate(user_id=1, priority=0)],
                ),
                WorkflowStepCreate(
                    step_order=2,
                    step_name="New Step B",
                    approval_mode="sequential",
                    approvers=[WorkflowStepApproverCreate(role_id=2, priority=1)],
                ),
            ]
            update = WorkflowDefinitionUpdate(steps=new_steps)
            result = svc.update_definition(created.id, update)

            detail = svc.get_definition(created.id)
            assert len(detail.steps) == 2
            assert detail.steps[0].step_name == "New Step A"
            assert detail.steps[1].step_name == "New Step B"


# ── API Tests ────────────────────────────────────


class TestWorkflowAPI:
    def test_admin_can_create_workflow(self, seeded_data, client):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            category_id=seeded_data["finance_category_id"],
        )
        response = test_client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 401  # No auth headers

    def test_admin_create_workflow(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="API Create WF",
            category_id=seeded_data["finance_category_id"],
        )
        response = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "API Create WF"
        assert data["is_active"] is True

    def test_maker_cannot_create_workflow(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Maker WF",
            category_id=seeded_data["finance_category_id"],
        )
        response = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["maker"],
        )
        assert response.status_code == 403

    def test_list_workflows(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        # Create one first
        payload = _create_workflow_payload(
            name="List WF",
            category_id=seeded_data["finance_category_id"],
        )
        test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )

        response = test_client.get("/api/v1/workflows", headers=auth_headers["admin"])
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_get_workflow_detail(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Detail WF",
            category_id=seeded_data["finance_category_id"],
        )
        create_resp = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        response = test_client.get(f"/api/v1/workflows/{wf_id}", headers=auth_headers["admin"])
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Detail WF"
        assert len(data["steps"]) == 1

    def test_update_workflow(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Update API WF",
            category_id=seeded_data["finance_category_id"],
        )
        create_resp = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        response = test_client.put(
            f"/api/v1/workflows/{wf_id}",
            json={"name": "Updated API WF"},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated API WF"

    def test_deactivate_workflow(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Deactivate API WF",
            category_id=seeded_data["finance_category_id"],
        )
        create_resp = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        response = test_client.delete(
            f"/api/v1/workflows/{wf_id}",
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_activate_workflow(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Activate API WF",
            category_id=seeded_data["finance_category_id"],
        )
        create_resp = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )
        wf_id = create_resp.json()["id"]

        # Deactivate first
        test_client.delete(f"/api/v1/workflows/{wf_id}", headers=auth_headers["admin"])

        response = test_client.patch(
            f"/api/v1/workflows/{wf_id}/activate",
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is True

    def test_get_nonexistent_workflow_returns_404(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        response = test_client.get("/api/v1/workflows/99999", headers=auth_headers["admin"])
        assert response.status_code == 404

    def test_duplicate_name_returns_409(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Duplicate WF",
            category_id=seeded_data["finance_category_id"],
        )
        test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )
        response = test_client.post(
            "/api/v1/workflows",
            json=payload,
            headers=auth_headers["admin"],
        )
        assert response.status_code == 409


# ══════════════════════════════════════════════
# Phase 2: Workflow Instance & Approval Tests
# ══════════════════════════════════════════════


def _create_workflow_with_step(
    session: Session,
    seeded_data: dict,
    *,
    wf_name: str = "Test Approval WF",
    approver_user_id: int | None = None,
) -> WorkflowDefinition:
    from users.models import User
    from workflow.schemas import WorkflowDefinitionCreate

    admin = session.get(User, seeded_data["admin_id"])
    svc = WorkflowDefinitionService(session)
    if approver_user_id is None:
        approver_user_id = seeded_data["admin_id"]

    payload = WorkflowDefinitionCreate(
        name=wf_name,
        description="Test workflow for Phase 2",
        document_category_id=seeded_data["finance_category_id"],
        steps=[{
            "step_order": 1,
            "step_name": "Manager Review",
            "approval_mode": "sequential",
            "approvers": [{"user_id": approver_user_id, "priority": 0}],
        }],
    )
    return svc.create_definition(payload, current_user=admin)


class TestWorkflowInstanceService:
    def test_submit_instance(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(session, seeded_data)
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            result = svc.submit_instance(payload, current_user=maker)
            assert result.document_id == seeded_data["finance_document_id"]
            assert result.workflow_definition_id == wf.id
            assert result.status == WorkflowStatus.SUBMITTED
            assert result.submitted_by == seeded_data["maker_id"]

    def test_submit_instance_records_history(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(session, seeded_data)
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            result = svc.submit_instance(payload, current_user=maker)

            history = session.exec(
                select(WorkflowHistory).where(WorkflowHistory.workflow_instance_id == result.id)
            ).all()
            assert len(history) == 1
            assert history[0].event_type == "submitted"

    def test_submit_instance_nonexistent_doc_raises(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(session, seeded_data)
            from users.models import User
            from fastapi import HTTPException
            maker = session.get(User, seeded_data["maker_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(document_id=99999, workflow_definition_id=wf.id)
            with pytest.raises(HTTPException) as exc_info:
                svc.submit_instance(payload, current_user=maker)
            assert exc_info.value.status_code == 404

    def test_submit_instance_inactive_wf_raises(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(session, seeded_data)
            from users.models import User
            from workflow.service import WorkflowDefinitionService as WDS
            from fastapi import HTTPException
            maker = session.get(User, seeded_data["maker_id"])

            WDS(session).deactivate_definition(wf.id)

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            with pytest.raises(HTTPException) as exc_info:
                svc.submit_instance(payload, current_user=maker)
            assert exc_info.value.status_code == 422

    def test_submit_instance_category_mismatch_raises(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate
            from fastapi import HTTPException

            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])
            wfs = WorkflowDefinitionService(session)

            payload = WorkflowDefinitionCreate(
                name="HR Only WF",
                document_category_id=seeded_data["hr_category_id"],
                steps=[{
                    "step_order": 1,
                    "step_name": "Review",
                    "approval_mode": "sequential",
                    "approvers": [{"user_id": seeded_data["maker_id"], "priority": 0}],
                }],
            )
            hr_wf = wfs.create_definition(payload, current_user=admin)

            svc = WorkflowInstanceService(session)
            instance_payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=hr_wf.id,
            )
            with pytest.raises(HTTPException) as exc_info:
                svc.submit_instance(instance_payload, current_user=maker)
            assert exc_info.value.status_code == 422

    def test_get_instance(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(session, seeded_data)
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            created = svc.submit_instance(payload, current_user=maker)
            detail = svc.get_instance(created.id)
            assert detail.id == created.id
            assert len(detail.history) == 1

    def test_list_my_instances(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(session, seeded_data)
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            svc.submit_instance(payload, current_user=maker)

            result = svc.list_my_instances(maker)
            assert result.total == 1
            assert result.items[0].submitted_by == seeded_data["maker_id"]

    def test_list_pending_includes_submitted(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(session, seeded_data, approver_user_id=seeded_data["admin_id"])
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            admin = session.get(User, seeded_data["admin_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            svc.submit_instance(payload, current_user=maker)

            pending = svc.list_pending(admin)
            assert pending.total == 1
            assert pending.items[0].status == WorkflowStatus.SUBMITTED


# ── Approval Action Service Tests ─────────────


class TestApprovalActionService:
    def _setup_instance(self, session, seeded_data, *, approver_user_id=None):
        if approver_user_id is None:
            approver_user_id = seeded_data["admin_id"]
        wf = _create_workflow_with_step(
            session, seeded_data, approver_user_id=approver_user_id,
        )
        from users.models import User
        maker = session.get(User, seeded_data["maker_id"])
        svc = WorkflowInstanceService(session)
        payload = WorkflowInstanceCreate(
            document_id=seeded_data["finance_document_id"],
            workflow_definition_id=wf.id,
        )
        instance = svc.submit_instance(payload, current_user=maker)
        return wf, instance

    def test_approve_advances_to_approved(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.APPROVE, remarks="Looks good")
            result = svc.act_on_instance(instance.id, action, current_user=admin)
            assert result.status == WorkflowStatus.APPROVED

    def test_approve_records_action(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.APPROVE, remarks="Approved")
            svc.act_on_instance(instance.id, action, current_user=admin)

            actions = session.exec(
                select(WorkflowAction).where(WorkflowAction.workflow_instance_id == instance.id)
            ).all()
            assert len(actions) == 1
            assert actions[0].action == ApprovalAction.APPROVE
            assert actions[0].remarks == "Approved"

    def test_approve_records_history(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.APPROVE)
            svc.act_on_instance(instance.id, action, current_user=admin)

            history = session.exec(
                select(WorkflowHistory).where(WorkflowHistory.workflow_instance_id == instance.id)
            ).all()
            assert len(history) == 2
            assert history[1].event_type == "approved"

    def test_reject_sets_rejected(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.REJECT, remarks="Nope")
            result = svc.act_on_instance(instance.id, action, current_user=admin)
            assert result.status == WorkflowStatus.REJECTED

    def test_return_sets_returned(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.RETURN, remarks="Fix please")
            result = svc.act_on_instance(instance.id, action, current_user=admin)
            assert result.status == WorkflowStatus.RETURNED

    def test_clarify_does_not_change_status(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.CLARIFY, remarks="What about page 3?")
            result = svc.act_on_instance(instance.id, action, current_user=admin)
            assert result.status == WorkflowStatus.SUBMITTED

    def test_forward_returns_501(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.FORWARD)
            with pytest.raises(HTTPException) as exc_info:
                svc.act_on_instance(instance.id, action, current_user=admin)
            assert exc_info.value.status_code == 501

    def test_self_approval_blocked(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(
                session, seeded_data, approver_user_id=seeded_data["maker_id"],
            )
            from users.models import User
            from fastapi import HTTPException
            maker = session.get(User, seeded_data["maker_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            instance = svc.submit_instance(payload, current_user=maker)

            action_svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.APPROVE)
            with pytest.raises(HTTPException) as exc_info:
                action_svc.act_on_instance(instance.id, action, current_user=maker)
            assert exc_info.value.status_code == 403
            assert "Makers cannot perform approval actions" in str(exc_info.value.detail)

    def test_ineligible_user_blocked(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf = _create_workflow_with_step(
                session, seeded_data, approver_user_id=seeded_data["admin_id"],
            )
            from users.models import User
            from fastapi import HTTPException
            maker = session.get(User, seeded_data["maker_id"])

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            instance = svc.submit_instance(payload, current_user=maker)

            action_svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.APPROVE)
            with pytest.raises(HTTPException) as exc_info:
                action_svc.act_on_instance(instance.id, action, current_user=maker)
            assert exc_info.value.status_code == 403

    def test_cannot_act_on_approved_instance(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            wf, instance = self._setup_instance(session, seeded_data)
            from users.models import User
            from fastapi import HTTPException
            admin = session.get(User, seeded_data["admin_id"])

            svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.APPROVE)
            svc.act_on_instance(instance.id, action, current_user=admin)

            action2 = WorkflowActionCreate(action=ApprovalAction.REJECT)
            with pytest.raises(HTTPException) as exc_info:
                svc.act_on_instance(instance.id, action2, current_user=admin)
            assert exc_info.value.status_code == 422

    def test_multi_step_advances_through_steps(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate

            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])

            wfs = WorkflowDefinitionService(session)
            payload = WorkflowDefinitionCreate(
                name="Multi-Step WF",
                document_category_id=seeded_data["finance_category_id"],
                steps=[
                    {
                        "step_order": 1,
                        "step_name": "Step 1",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": seeded_data["admin_id"], "priority": 0}],
                    },
                    {
                        "step_order": 2,
                        "step_name": "Step 2",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": seeded_data["admin_id"], "priority": 0}],
                    },
                ],
            )
            wf = wfs.create_definition(payload, current_user=admin)

            instance_svc = WorkflowInstanceService(session)
            instance_payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            instance = instance_svc.submit_instance(instance_payload, current_user=maker)
            assert instance.current_step_order == 1

            action_svc = ApprovalActionService(session)
            action1 = WorkflowActionCreate(action=ApprovalAction.APPROVE)
            result = action_svc.act_on_instance(instance.id, action1, current_user=admin)
            assert result.current_step_order == 2
            assert result.status == WorkflowStatus.PENDING_APPROVAL

            action2 = WorkflowActionCreate(action=ApprovalAction.APPROVE)
            result2 = action_svc.act_on_instance(instance.id, action2, current_user=admin)
            assert result2.status == WorkflowStatus.APPROVED

    def test_parallel_step_any_approve_completes(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User, Role, UserRoleLink
            from workflow.schemas import WorkflowDefinitionCreate

            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])

            from users.models import RoleName, RolePermissionLink, Permission, PermissionAction
            checker_role = Role(name=RoleName.CHECKER, description="Checker")
            session.add(checker_role)
            session.flush()
            for pa in (PermissionAction.VIEW, PermissionAction.DOWNLOAD, PermissionAction.UPDATE):
                perm = session.exec(select(Permission).where(Permission.action == pa)).first()
                if perm:
                    session.add(RolePermissionLink(role_id=checker_role.id, permission_id=perm.id))

            checker = User(
                full_name="Checker User", email="checker@example.com",
                hashed_password="checker", is_active=True,
                user_level_id=seeded_data["high_level_id"],
            )
            session.add(checker)
            session.flush()
            session.add(UserRoleLink(user_id=checker.id, role_id=checker_role.id))
            session.flush()

            wfs = WorkflowDefinitionService(session)
            payload = WorkflowDefinitionCreate(
                name="Parallel WF",
                document_category_id=seeded_data["finance_category_id"],
                steps=[{
                    "step_order": 1,
                    "step_name": "Parallel Review",
                    "approval_mode": "parallel",
                    "approvers": [
                        {"user_id": seeded_data["admin_id"], "priority": 0},
                        {"user_id": checker.id, "priority": 1},
                    ],
                }],
            )
            wf = wfs.create_definition(payload, current_user=admin)

            instance_svc = WorkflowInstanceService(session)
            instance_payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            instance = instance_svc.submit_instance(instance_payload, current_user=maker)

            action_svc = ApprovalActionService(session)
            action = WorkflowActionCreate(action=ApprovalAction.APPROVE)
            result = action_svc.act_on_instance(instance.id, action, current_user=admin)
            assert result.status == WorkflowStatus.APPROVED


# ── API Tests: Workflow Instances ──────────────


class TestWorkflowInstanceAPI:
    def test_submit_instance_api(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="API Instance WF",
            category_id=seeded_data["finance_category_id"],
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"], "priority": 0}],
            }],
        )
        wf_resp = test_client.post(
            "/api/v1/workflows", json=payload, headers=auth_headers["admin"],
        )
        wf_id = wf_resp.json()["id"]

        response = test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": seeded_data["finance_document_id"], "workflow_definition_id": wf_id},
            headers=auth_headers["maker"],
        )
        assert response.status_code == 201
        assert response.json()["status"] == "submitted"

    def test_submit_instance_requires_auth(self, seeded_data, client):
        test_client, _, _ = client
        response = test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": seeded_data["finance_document_id"], "workflow_definition_id": 1},
        )
        assert response.status_code == 401

    def test_pending_list_api(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Pending List WF",
            category_id=seeded_data["finance_category_id"],
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"], "priority": 0}],
            }],
        )
        wf_resp = test_client.post(
            "/api/v1/workflows", json=payload, headers=auth_headers["admin"],
        )
        wf_id = wf_resp.json()["id"]
        test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": seeded_data["finance_document_id"], "workflow_definition_id": wf_id},
            headers=auth_headers["maker"],
        )

        response = test_client.get(
            "/api/v1/workflow-instances/pending", headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_mine_list_api(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Mine List WF",
            category_id=seeded_data["finance_category_id"],
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"], "priority": 0}],
            }],
        )
        wf_resp = test_client.post(
            "/api/v1/workflows", json=payload, headers=auth_headers["admin"],
        )
        wf_id = wf_resp.json()["id"]
        test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": seeded_data["finance_document_id"], "workflow_definition_id": wf_id},
            headers=auth_headers["maker"],
        )

        response = test_client.get(
            "/api/v1/workflow-instances/mine", headers=auth_headers["maker"],
        )
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    def test_get_instance_detail_api(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Detail Instance WF",
            category_id=seeded_data["finance_category_id"],
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"], "priority": 0}],
            }],
        )
        wf_resp = test_client.post(
            "/api/v1/workflows", json=payload, headers=auth_headers["admin"],
        )
        wf_id = wf_resp.json()["id"]
        inst_resp = test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": seeded_data["finance_document_id"], "workflow_definition_id": wf_id},
            headers=auth_headers["maker"],
        )
        inst_id = inst_resp.json()["id"]

        response = test_client.get(
            f"/api/v1/workflow-instances/{inst_id}", headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        assert response.json()["id"] == inst_id
        assert "history" in response.json()

    def test_approve_instance_api(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="Approve Instance WF",
            category_id=seeded_data["finance_category_id"],
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"], "priority": 0}],
            }],
        )
        wf_resp = test_client.post(
            "/api/v1/workflows", json=payload, headers=auth_headers["admin"],
        )
        wf_id = wf_resp.json()["id"]
        inst_resp = test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": seeded_data["finance_document_id"], "workflow_definition_id": wf_id},
            headers=auth_headers["maker"],
        )
        inst_id = inst_resp.json()["id"]

        response = test_client.post(
            f"/api/v1/workflow-instances/{inst_id}/actions",
            json={"action": "approve", "remarks": "Looks good"},
            headers=auth_headers["admin"],
        )
        assert response.status_code == 200
        assert response.json()["status"] == "approved"
