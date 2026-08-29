"""Tests for the extracted approver resolution policy function."""

import pytest
from sqlmodel import Session

from documents.models import Document
from users.models import Role, RoleName, User, UserRoleLink
from workflow.approval_policy import resolve_eligible_user_ids
from workflow.models import WorkflowStepApprover


class TestResolveEligibleUserIds:
    """Unit tests for resolve_eligible_user_ids — the single source of truth."""

    def _make_step(self, session, *, user_id=None, role_id=None):
        """Create a persisted WorkflowStep with one approver."""
        from workflow.models import WorkflowStep, ApprovalMode
        step = WorkflowStep(
            workflow_definition_id=1,
            step_order=1,
            step_name="Test Step",
            approval_mode=ApprovalMode.SEQUENTIAL,
        )
        session.add(step)
        session.flush()
        approver = WorkflowStepApprover(
            workflow_step_id=step.id,
            user_id=user_id,
            role_id=role_id,
        )
        session.add(approver)
        session.flush()
        return step

    def test_direct_user_eligible(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            doc = session.get(Document, seeded_data["finance_document_id"])
            step = self._make_step(session, user_id=seeded_data["admin_id"])

            result = resolve_eligible_user_ids(session, step, doc)
            assert seeded_data["admin_id"] in result

    def test_direct_user_eligible_regardless_of_level(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # hr_doc is only visible to High level
            doc = session.get(Document, seeded_data["hr_document_id"])
            # maker has Medium level, not High — but approvers are trusted
            step = self._make_step(session, user_id=seeded_data["maker_id"])

            result = resolve_eligible_user_ids(session, step, doc)
            assert seeded_data["maker_id"] in result

    def test_role_based_expansion(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            doc = session.get(Document, seeded_data["finance_document_id"])

            # Create a checker role and user
            checker_role = Role(name=RoleName.CHECKER, description="Checker")
            session.add(checker_role)
            session.flush()

            checker = User(
                full_name="Checker User",
                email="checker@test.com",
                hashed_password="x",
                is_active=True,
                user_level_id=seeded_data["high_level_id"],
            )
            session.add(checker)
            session.flush()
            session.add(UserRoleLink(user_id=checker.id, role_id=checker_role.id))
            session.flush()

            step = self._make_step(session, role_id=checker_role.id)

            result = resolve_eligible_user_ids(session, step, doc)
            assert checker.id in result

    def test_admin_bypasses_level_restriction(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # hr_doc is only visible to High level
            doc = session.get(Document, seeded_data["hr_document_id"])
            # admin has High level AND is admin — should be included
            step = self._make_step(session, user_id=seeded_data["admin_id"])

            result = resolve_eligible_user_ids(session, step, doc)
            assert seeded_data["admin_id"] in result

    def test_inactive_user_excluded(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            doc = session.get(Document, seeded_data["finance_document_id"])

            inactive = User(
                full_name="Inactive",
                email="inactive@test.com",
                hashed_password="x",
                is_active=False,
                user_level_id=seeded_data["high_level_id"],
            )
            session.add(inactive)
            session.flush()

            step = self._make_step(session, user_id=inactive.id)

            result = resolve_eligible_user_ids(session, step, doc)
            assert inactive.id not in result

    def test_no_approvers_returns_empty(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from workflow.models import WorkflowStep, ApprovalMode
            doc = session.get(Document, seeded_data["finance_document_id"])

            step = WorkflowStep(
                workflow_definition_id=1,
                step_order=1,
                step_name="Empty Step",
                approval_mode=ApprovalMode.SEQUENTIAL,
            )
            session.add(step)
            session.flush()

            result = resolve_eligible_user_ids(session, step, doc)
            assert result == []

    def test_no_level_links_still_eligible(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            # Create a doc with no user level links
            doc = Document(
                title="No Levels",
                description="",
                directory_id=1,
                uploaded_by=seeded_data["admin_id"],
                file_name="nolevels.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                file_size=0,
                storage_path="x/x.pdf",
            )
            session.add(doc)
            session.flush()

            step = self._make_step(session, user_id=seeded_data["admin_id"])

            result = resolve_eligible_user_ids(session, step, doc)
            assert seeded_data["admin_id"] in result
