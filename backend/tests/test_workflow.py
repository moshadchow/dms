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
    steps: list | None = None,
) -> dict:
    if steps is None:
        steps = [
            {
                "step_order": 1,
                "step_name": "Manager Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": 1}],
            }
        ]
    return {
        "name": name,
        "description": "Test workflow",
        "steps": steps,
    }


# ── Service Tests ────────────────────────────────


class TestWorkflowDefinitionService:
    def test_create_definition(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            payload = _create_workflow_payload()
            # We need to pass current_user; use admin from seeded_data
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            result = svc.create_definition(
                __import__("workflow.schemas", fromlist=["WorkflowDefinitionCreate"]).WorkflowDefinitionCreate(**payload),
                current_user=admin,
            )
            assert result.name == "Invoice Approval"
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
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)
            result = svc.get_definition(created.id, admin)
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
                )
                svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)

            result = svc.list_definitions(current_user=admin)
            assert result.total == 3
            assert len(result.items) == 3

    def test_update_definition(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            svc = WorkflowDefinitionService(session)
            from users.models import User
            from workflow.schemas import WorkflowDefinitionCreate, WorkflowDefinitionUpdate
            admin = session.get(User, seeded_data["admin_id"])

            payload = _create_workflow_payload(
                name="Update WF",
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)

            update = WorkflowDefinitionUpdate(name="Updated WF Name")
            result = svc.update_definition(created.id, update, admin)
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
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)
            result = svc.deactivate_definition(created.id, admin)
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
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)
            svc.deactivate_definition(created.id, admin)
            result = svc.activate_definition(created.id, admin)
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
                steps=[
                    {
                        "step_order": 1,
                        "step_name": "Step 1",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": 1}],
                    }
                ],
            )
            created = svc.create_definition(WorkflowDefinitionCreate(**payload), current_user=admin)

            new_steps = [
                WorkflowStepCreate(
                    step_order=1,
                    step_name="New Step A",
                    approval_mode="parallel",
                    approvers=[WorkflowStepApproverCreate(user_id=1)],
                ),
                WorkflowStepCreate(
                    step_order=2,
                    step_name="New Step B",
                    approval_mode="sequential",
                    approvers=[WorkflowStepApproverCreate(role_id=2)],
                ),
            ]
            update = WorkflowDefinitionUpdate(steps=new_steps)
            result = svc.update_definition(created.id, update, admin)

            detail = svc.get_definition(created.id, admin)
            assert len(detail.steps) == 2
            assert detail.steps[0].step_name == "New Step A"
            assert detail.steps[1].step_name == "New Step B"


class TestStepEditActiveInstanceGuard:
    """ADMIN may modify steps only while no instance is still active.

    Step edits supersede rows (is_active=False) instead of deleting them, so
    completed instances keep their historical workflow snapshot — the
    workflow_actions rows continue to reference the rows they acted on.
    """

    @staticmethod
    def _create(session, admin, name: str, steps: list | None = None):
        from workflow.schemas import WorkflowDefinitionCreate
        return WorkflowDefinitionService(session).create_definition(
            WorkflowDefinitionCreate(**_create_workflow_payload(name=name, steps=steps)),
            current_user=admin,
        )

    @staticmethod
    def _submit(session, document_id, definition_id, maker):
        return WorkflowInstanceService(session).submit_instance(
            WorkflowInstanceCreate(
                document_id=document_id,
                workflow_definition_id=definition_id,
            ),
            current_user=maker,
        )

    @staticmethod
    def _approve(session, instance_id, admin):
        return ApprovalActionService(session).act_on_instance(
            instance_id,
            WorkflowActionCreate(action=ApprovalAction.APPROVE),
            current_user=admin,
        )

    @staticmethod
    def _steps_of(session, definition_id):
        return session.exec(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_definition_id == definition_id)
            .order_by(WorkflowStep.step_order, WorkflowStep.id)
        ).all()

    @staticmethod
    def _steps_payload(*names, approver_id):
        from workflow.schemas import WorkflowStepCreate, WorkflowStepApproverCreate
        return [
            WorkflowStepCreate(
                step_order=i,
                step_name=name,
                approval_mode="sequential",
                approvers=[WorkflowStepApproverCreate(user_id=approver_id)],
            )
            for i, name in enumerate(names, start=1)
        ]

    def test_step_edit_blocked_while_instance_active(self, seeded_data, client):
        from fastapi import HTTPException
        from users.models import User
        from workflow.schemas import WorkflowDefinitionUpdate

        _, engine, _ = client
        with Session(engine) as session:
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])
            created = self._create(
                session, admin, "Blocked Edit WF",
                steps=[{
                    "step_order": 1,
                    "step_name": "Checker Step",
                    "approval_mode": "sequential",
                    "approvers": [{"user_id": admin.id}],
                }],
            )
            original = self._steps_of(session, created.id)
            instance = self._submit(
                session, seeded_data["finance_document_id"], created.id, maker
            )

            update = WorkflowDefinitionUpdate(
                steps=self._steps_payload("Changed Step", approver_id=admin.id)
            )
            with pytest.raises(HTTPException) as exc_info:
                WorkflowDefinitionService(session).update_definition(created.id, update, admin)
            assert exc_info.value.status_code == 409
            assert "active workflow instances" in exc_info.value.detail

            steps_after = self._steps_of(session, created.id)
            assert [s.id for s in steps_after] == [s.id for s in original]
            assert steps_after[0].step_name == "Checker Step"
            assert instance.status == WorkflowStatus.SUBMITTED

    def test_step_edit_allowed_once_instances_terminal(self, seeded_data, client):
        from users.models import User
        from workflow.schemas import WorkflowDefinitionUpdate

        _, engine, _ = client
        with Session(engine) as session:
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])
            created = self._create(
                session, admin, "Completed Instance WF",
                steps=[{
                    "step_order": 1,
                    "step_name": "Original Step",
                    "approval_mode": "sequential",
                    "approvers": [{"user_id": admin.id}],
                }],
            )
            old_steps = self._steps_of(session, created.id)
            instance = self._submit(
                session, seeded_data["finance_document_id"], created.id, maker
            )
            approved = self._approve(session, instance.id, admin)
            assert approved.status == WorkflowStatus.APPROVED

            actions = session.exec(
                select(WorkflowAction).where(WorkflowAction.workflow_instance_id == instance.id)
            ).all()
            assert len(actions) == 1
            assert actions[0].workflow_step_id == old_steps[0].id

            update = WorkflowDefinitionUpdate(
                steps=self._steps_payload("Renamed Step", approver_id=admin.id)
            )
            WorkflowDefinitionService(session).update_definition(created.id, update, admin)

            # Superseded, never deleted: the historical action's FK still resolves.
            assert old_steps[0].is_active is False
            assert session.get(WorkflowStep, old_steps[0].id) is not None
            assert actions[0].workflow_step_id == old_steps[0].id

            new_steps = [s for s in self._steps_of(session, created.id) if s.is_active]
            assert len(new_steps) == 1
            assert new_steps[0].id != old_steps[0].id
            assert new_steps[0].step_name == "Renamed Step"

            detail = WorkflowDefinitionService(session).get_definition(created.id, admin)
            assert [s.step_name for s in detail.steps] == ["Renamed Step"]

    def test_unchanged_step_payload_allowed_while_active(self, seeded_data, client):
        from users.models import User
        from workflow.schemas import WorkflowDefinitionUpdate

        _, engine, _ = client
        with Session(engine) as session:
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])
            steps = [{
                "step_order": 1,
                "step_name": "Same Step",
                "approval_mode": "sequential",
                "approvers": [{"user_id": admin.id}],
            }]
            created = self._create(session, admin, "Noop Edit WF", steps=steps)
            original = self._steps_of(session, created.id)
            self._submit(session, seeded_data["finance_document_id"], created.id, maker)

            # The edit form always sends the full step list; an unchanged
            # payload must not trip the in-flight guard nor version rows.
            update = WorkflowDefinitionUpdate(
                steps=self._steps_payload("Same Step", approver_id=admin.id)
            )
            WorkflowDefinitionService(session).update_definition(created.id, update, admin)

            after = self._steps_of(session, created.id)
            assert [s.id for s in after] == [s.id for s in original]
            assert all(s.is_active for s in after)

    def test_new_instance_resolves_new_steps_after_supersede(self, seeded_data, client):
        from users.models import User
        from workflow.schemas import WorkflowDefinitionUpdate

        _, engine, _ = client
        with Session(engine) as session:
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])
            created = self._create(
                session, admin, "Versioned Steps WF",
                steps=[
                    {
                        "step_order": 1,
                        "step_name": "First Review",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": admin.id}],
                    },
                    {
                        "step_order": 2,
                        "step_name": "Second Review",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": admin.id}],
                    },
                ],
            )
            old_steps = self._steps_of(session, created.id)
            assert len(old_steps) == 2

            # Complete one instance on the original chain.
            inst1 = self._submit(
                session, seeded_data["finance_document_id"], created.id, maker
            )
            self._approve(session, inst1.id, admin)
            approved1 = self._approve(session, inst1.id, admin)
            assert approved1.status == WorkflowStatus.APPROVED

            # All instances terminal → step edit goes through.
            update = WorkflowDefinitionUpdate(
                steps=self._steps_payload("New First", "New Second", approver_id=admin.id)
            )
            WorkflowDefinitionService(session).update_definition(created.id, update, admin)
            active = [s for s in self._steps_of(session, created.id) if s.is_active]
            assert [s.step_name for s in active] == ["New First", "New Second"]

            # A fresh instance runs entirely on the new chain. The seeded
            # maker is only linked to finance/legal and lacks this document's
            # user level, so grant both accesses first.
            from users.models import UserCategoryLink
            from documents.models import DocumentUserLevelLink
            session.add(
                UserCategoryLink(
                    user_id=maker.id, category_id=seeded_data["hr_category_id"]
                )
            )
            session.add(
                DocumentUserLevelLink(
                    document_id=seeded_data["hr_document_id"],
                    user_level_id=seeded_data["medium_level_id"],
                )
            )
            session.flush()
            inst2 = self._submit(
                session, seeded_data["hr_document_id"], created.id, maker
            )
            assert inst2.current_step_order == 1

            after_first = self._approve(session, inst2.id, admin)
            assert after_first.current_step_order == 2
            assert after_first.status == WorkflowStatus.PENDING_APPROVAL
            actions2 = session.exec(
                select(WorkflowAction).where(WorkflowAction.workflow_instance_id == inst2.id)
            ).all()
            # The action landed on the NEW step 1 (id 3), not the superseded
            # twin that shares its step_order.
            assert actions2[-1].workflow_step_id == active[0].id

            final = self._approve(session, inst2.id, admin)
            assert final.status == WorkflowStatus.APPROVED
            # The second action resolved the NEW step 2 by step_order.
            actions2 = session.exec(
                select(WorkflowAction).where(WorkflowAction.workflow_instance_id == inst2.id)
            ).all()
            assert actions2[-1].workflow_step_id == active[1].id

            # The completed historical instance still points at the old chain.
            actions1 = session.exec(
                select(WorkflowAction).where(WorkflowAction.workflow_instance_id == inst1.id)
            ).all()
            old_ids = {s.id for s in old_steps}
            assert {a.workflow_step_id for a in actions1} <= old_ids


# ── API Tests ────────────────────────────────────


class TestWorkflowAPI:
    def test_admin_can_create_workflow(self, seeded_data, client):
        test_client, _, _ = client
        payload = _create_workflow_payload(
        )
        response = test_client.post("/api/v1/workflows", json=payload)
        assert response.status_code == 401  # No auth headers

    def test_admin_create_workflow(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="API Create WF",
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
        steps=[{
            "step_order": 1,
            "step_name": "Manager Review",
            "approval_mode": "sequential",
            "approvers": [{"user_id": approver_user_id}],
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
            admin = session.get(User, seeded_data["admin_id"])

            WDS(session).deactivate_definition(wf.id, admin)

            svc = WorkflowInstanceService(session)
            payload = WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            )
            with pytest.raises(HTTPException) as exc_info:
                svc.submit_instance(payload, current_user=maker)
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
                steps=[
                    {
                        "step_order": 1,
                        "step_name": "Step 1",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": seeded_data["admin_id"]}],
                    },
                    {
                        "step_order": 2,
                        "step_name": "Step 2",
                        "approval_mode": "sequential",
                        "approvers": [{"user_id": seeded_data["admin_id"]}],
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
                steps=[{
                    "step_order": 1,
                    "step_name": "Parallel Review",
                    "approval_mode": "parallel",
                    "approvers": [
                        {"user_id": seeded_data["admin_id"]},
                        {"user_id": checker.id},
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


# ── Duplicate action guard ─────────────────────


class TestDuplicateApprovalGuard:
    """Same approver, same step, same action → 409 and no second row."""

    def _setup(self, session, seeded_data, *, wf_name="Duplicate Guard WF"):
        from users.models import Role, RoleName, User, UserRoleLink
        from workflow.schemas import WorkflowDefinitionCreate

        admin = session.get(User, seeded_data["admin_id"])
        maker = session.get(User, seeded_data["maker_id"])

        role = session.exec(select(Role).where(Role.name == RoleName.CHECKER)).first()
        assert role, "seeded CHECKER role missing"
        checker = User(
            full_name="Duplicate Guard Checker",
            email="dup.guard@example.com",
            hashed_password="x",
            is_active=True,
            user_level_id=seeded_data["high_level_id"],
            company_id=seeded_data["company_id"],
        )
        session.add(checker)
        session.flush()
        session.add(UserRoleLink(user_id=checker.id, role_id=role.id))
        session.commit()

        wfs = WorkflowDefinitionService(session)
        payload = WorkflowDefinitionCreate(
            name=wf_name,
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [
                    {"user_id": seeded_data["admin_id"]},
                    {"user_id": checker.id},
                ],
            }],
        )
        wf = wfs.create_definition(payload, current_user=admin)

        instance_svc = WorkflowInstanceService(session)
        instance = instance_svc.submit_instance(
            WorkflowInstanceCreate(
                document_id=seeded_data["finance_document_id"],
                workflow_definition_id=wf.id,
            ),
            current_user=maker,
        )
        return instance, admin, checker

    @staticmethod
    def _count(session, model, instance_id):
        return len(session.exec(
            select(model).where(model.workflow_instance_id == instance_id)
        ).all())

    def test_first_approve_succeeds_with_single_row(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)

            result = svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            # Step stays open: the second sequential approver has not acted.
            assert result.status == WorkflowStatus.PENDING_APPROVAL
            assert self._count(session, WorkflowAction, instance.id) == 1

    def test_duplicate_approve_rejected_no_new_row(self, seeded_data, client):
        from fastapi import HTTPException

        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)
            svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            history_before = self._count(session, WorkflowHistory, instance.id)

            with pytest.raises(HTTPException) as exc_info:
                svc.act_on_instance(
                    instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                    current_user=admin,
                )
            assert exc_info.value.status_code == 409
            assert exc_info.value.detail == (
                "This record is already approved by the first approver."
            )
            assert self._count(session, WorkflowAction, instance.id) == 1
            assert self._count(session, WorkflowHistory, instance.id) == history_before

    def test_duplicate_rejected_after_page_reload(self, seeded_data, client):
        """Server-side state only: a fresh session (page refresh) cannot approve again."""
        from fastapi import HTTPException

        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            ApprovalActionService(session).act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            instance_id = instance.id
            admin_id = admin.id

        with Session(engine) as session2:
            from users.models import User
            admin2 = session2.get(User, admin_id)
            with pytest.raises(HTTPException) as exc_info:
                ApprovalActionService(session2).act_on_instance(
                    instance_id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                    current_user=admin2,
                )
            assert exc_info.value.status_code == 409
            assert self._count(session2, WorkflowAction, instance_id) == 1

    def test_next_sequential_approver_can_approve(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)

            svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            result = svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=checker,
            )
            assert result.status == WorkflowStatus.APPROVED
            assert self._count(session, WorkflowAction, instance.id) == 2

    def test_race_backstop_unique_constraint_maps_to_409(
        self, seeded_data, client, monkeypatch
    ):
        """Simulates two requests passing the pre-check concurrently: the DB
        unique constraint rejects the second insert and it maps to 409."""
        from fastapi import HTTPException

        _, engine, _ = client
        monkeypatch.setattr(
            ApprovalActionService,
            "_ensure_no_duplicate_action",
            lambda self, instance, step, user_id, action: None,
        )
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)
            svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )

            with pytest.raises(HTTPException) as exc_info:
                svc.act_on_instance(
                    instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                    current_user=admin,
                )
            assert exc_info.value.status_code == 409
            assert exc_info.value.detail == (
                "This record is already approved by the first approver."
            )
            assert self._count(session, WorkflowAction, instance.id) == 1

    def test_clarify_then_approve_allowed(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)

            svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.CLARIFY),
                current_user=admin,
            )
            result = svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            assert result.status == WorkflowStatus.PENDING_APPROVAL
            assert self._count(session, WorkflowAction, instance.id) == 2

    def test_duplicate_clarify_rejected(self, seeded_data, client):
        from fastapi import HTTPException

        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)
            svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.CLARIFY),
                current_user=admin,
            )
            with pytest.raises(HTTPException) as exc_info:
                svc.act_on_instance(
                    instance.id, WorkflowActionCreate(action=ApprovalAction.CLARIFY),
                    current_user=admin,
                )
            assert exc_info.value.status_code == 409
            assert exc_info.value.detail == (
                "You have already performed 'clarify' on this step."
            )
            assert self._count(session, WorkflowAction, instance.id) == 1

    def test_reject_by_second_approver_still_works(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)
            svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            result = svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.REJECT),
                current_user=checker,
            )
            assert result.status == WorkflowStatus.REJECTED
            assert self._count(session, WorkflowAction, instance.id) == 2

    def test_return_then_duplicate_return_rejected(self, seeded_data, client):
        from fastapi import HTTPException

        _, engine, _ = client
        with Session(engine) as session:
            instance, admin, checker = self._setup(session, seeded_data)
            svc = ApprovalActionService(session)
            svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.RETURN),
                current_user=admin,
            )
            with pytest.raises(HTTPException) as exc_info:
                svc.act_on_instance(
                    instance.id, WorkflowActionCreate(action=ApprovalAction.RETURN),
                    current_user=admin,
                )
            assert exc_info.value.status_code == 409
            assert self._count(session, WorkflowAction, instance.id) == 1

    def test_parallel_multi_step_same_approver_unaffected(self, seeded_data, client):
        """Parallel steps advance on first approve — the same approver acting on
        the next step is a different step and must not be blocked."""
        from users.models import User
        from workflow.schemas import WorkflowDefinitionCreate

        _, engine, _ = client
        with Session(engine) as session:
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])

            wfs = WorkflowDefinitionService(session)
            payload = WorkflowDefinitionCreate(
                name="Parallel Multi-Step WF",
                steps=[{
                    "step_order": order,
                    "step_name": f"Parallel {order}",
                    "approval_mode": "parallel",
                    "approvers": [{"user_id": seeded_data["admin_id"]}],
                } for order in (1, 2)],
            )
            wf = wfs.create_definition(payload, current_user=admin)

            instance = WorkflowInstanceService(session).submit_instance(
                WorkflowInstanceCreate(
                    document_id=seeded_data["finance_document_id"],
                    workflow_definition_id=wf.id,
                ),
                current_user=maker,
            )
            svc = ApprovalActionService(session)
            first = svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            assert first.current_step_order == 2
            second = svc.act_on_instance(
                instance.id, WorkflowActionCreate(action=ApprovalAction.APPROVE),
                current_user=admin,
            )
            assert second.status == WorkflowStatus.APPROVED
            assert self._count(session, WorkflowAction, instance.id) == 2


# ── API Tests: Workflow Instances ──────────────


class TestWorkflowInstanceAPI:
    def test_submit_instance_api(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        payload = _create_workflow_payload(
            name="API Instance WF",
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
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
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
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
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
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
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
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
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
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


class TestDuplicateApprovalAPI:
    """HTTP-level duplicate guard: 409 + exact message + no extra row."""

    DUPLICATE_MESSAGE = "This record is already approved by the first approver."

    def _make_checker(self, engine, seeded_data):
        from core.security import create_access_token, hash_password
        from users.models import Role, RoleName, User, UserRoleLink

        with Session(engine) as session:
            role = session.exec(select(Role).where(Role.name == RoleName.CHECKER)).first()
            assert role, "seeded CHECKER role missing"
            user = User(
                full_name="API Dup Checker",
                email="api.dup.checker@example.com",
                hashed_password=hash_password("Test@1234"),
                is_active=True,
                user_level_id=seeded_data["high_level_id"],
                company_id=seeded_data["company_id"],
            )
            session.add(user)
            session.flush()
            session.add(UserRoleLink(user_id=user.id, role_id=role.id))
            session.commit()
            checker_id = user.id
        headers = {"Authorization": f"Bearer {create_access_token(checker_id)}"}
        return checker_id, headers

    def _setup_instance(self, test_client, auth_headers, seeded_data, checker_id, name):
        payload = _create_workflow_payload(
            name=name,
            steps=[{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [
                    {"user_id": seeded_data["admin_id"]},
                    {"user_id": checker_id},
                ],
            }],
        )
        wf_resp = test_client.post(
            "/api/v1/workflows", json=payload, headers=auth_headers["admin"],
        )
        assert wf_resp.status_code == 201, wf_resp.text
        inst_resp = test_client.post(
            "/api/v1/workflow-instances",
            json={
                "document_id": seeded_data["finance_document_id"],
                "workflow_definition_id": wf_resp.json()["id"],
            },
            headers=auth_headers["maker"],
        )
        assert inst_resp.status_code == 201, inst_resp.text
        return inst_resp.json()["id"]

    def _action_rows(self, engine, instance_id):
        with Session(engine) as session:
            return session.exec(
                select(WorkflowAction).where(
                    WorkflowAction.workflow_instance_id == instance_id
                )
            ).all()

    def test_duplicate_approve_api_rejected_next_approver_works(
        self, seeded_data, client, auth_headers
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        inst_id = self._setup_instance(
            test_client, auth_headers, seeded_data, checker_id,
            "API Dup Guard WF",
        )

        # 1. First approver approves once → success, exactly one row.
        first = test_client.post(
            f"/api/v1/workflow-instances/{inst_id}/actions",
            json={"action": "approve"},
            headers=auth_headers["admin"],
        )
        assert first.status_code == 200, first.text
        assert first.json()["status"] == "pending_approval"
        assert len(self._action_rows(engine, inst_id)) == 1

        # 2./3. Same approver again → 409 with the required message, no new row.
        dup = test_client.post(
            f"/api/v1/workflow-instances/{inst_id}/actions",
            json={"action": "approve"},
            headers=auth_headers["admin"],
        )
        assert dup.status_code == 409
        assert dup.json()["detail"] == self.DUPLICATE_MESSAGE
        assert len(self._action_rows(engine, inst_id)) == 1

        # 5. Reopening the page (fresh GET) does not change server state.
        detail = test_client.get(
            f"/api/v1/workflow-instances/{inst_id}", headers=auth_headers["admin"],
        )
        assert detail.status_code == 200
        body = detail.json()
        assert body["current_step_id"] is not None
        assert len(body["actions"]) == 1
        assert body["actions"][0]["action"] == "approve"
        assert body["actions"][0]["acted_by"] == seeded_data["admin_id"]
        again = test_client.post(
            f"/api/v1/workflow-instances/{inst_id}/actions",
            json={"action": "approve"},
            headers=auth_headers["admin"],
        )
        assert again.status_code == 409

        # 4. Next sequential approver approves normally.
        second = test_client.post(
            f"/api/v1/workflow-instances/{inst_id}/actions",
            json={"action": "approve"},
            headers=checker_headers,
        )
        assert second.status_code == 200, second.text
        assert second.json()["status"] == "approved"
        assert len(self._action_rows(engine, inst_id)) == 2

    def test_duplicate_reject_api_rejected(
        self, seeded_data, client, auth_headers
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        inst_id = self._setup_instance(
            test_client, auth_headers, seeded_data, checker_id,
            "API Dup Reject WF",
        )
        first = test_client.post(
            f"/api/v1/workflow-instances/{inst_id}/actions",
            json={"action": "reject", "remarks": "no"},
            headers=auth_headers["admin"],
        )
        assert first.status_code == 200, first.text

        dup = test_client.post(
            f"/api/v1/workflow-instances/{inst_id}/actions",
            json={"action": "reject"},
            headers=auth_headers["admin"],
        )
        # Instance is already 'rejected' → status guard fires first (422), and
        # no duplicate row exists either way.
        assert dup.status_code in (409, 422)
        assert len(self._action_rows(engine, inst_id)) == 1
