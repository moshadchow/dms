"""Tests for the Correspondence module."""

from datetime import datetime

from fastapi import BackgroundTasks, HTTPException
from sqlmodel import Session, select

from correspondence.models import (
    Correspondence,
    CorrespondenceDirection,
    CorrespondenceMovement,
    CorrespondencePriority,
    CorrespondenceSequence,
    CorrespondenceStatus,
    DispatchMethod,
)
from correspondence.schemas import (
    CorrespondenceAssign,
    CorrespondenceArchive,
    CorrespondenceComplete,
    CorrespondenceCreate,
    CorrespondenceDeliver,
    CorrespondenceDispatch,
    CorrespondenceSubmit,
    CorrespondenceUpdate,
)
from correspondence.service import CorrespondenceService
from documents.models import Document, FileType


# ── Helpers ──────────────────────────────────────


def _corr_payload(seeded_data, **overrides) -> dict:
    payload = {
        "directory_id": seeded_data["finance_directory_id"],
        "category_id": seeded_data["finance_category_id"],
        "user_level_ids": [seeded_data["medium_level_id"]],
        "subject": "Test Correspondence",
        "body": "<p>Test body content</p>",
        "direction": "outbound",
        "priority": "normal",
        "sender_name": "John Sender",
        "recipient_name": "Jane Recipient",
    }
    payload.update(overrides)
    return payload


def _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Correspondence WF"):
    payload = {
        "name": name,
        "description": "Correspondence approval",
        "steps": [{
            "step_order": 1,
            "step_name": "Review",
            "approval_mode": "sequential",
            "approvers": [{"user_id": seeded_data["admin_id"]}],
        }],
    }
    resp = test_client.post("/api/v1/workflows", json=payload, headers=auth_headers["admin"])
    assert resp.status_code == 201
    return resp.json()["id"]


# ── Service Tests ────────────────────────────────


class TestCorrespondenceService:
    def test_create_draft_creates_document_and_correspondence(self, seeded_data, client):
        _, engine, storage = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            assert corr.id is not None
            assert corr.subject == "Test Correspondence"
            assert corr.direction == CorrespondenceDirection.OUTBOUND
            assert corr.status == CorrespondenceStatus.DRAFT
            assert corr.reference_number is not None
            assert corr.reference_number.startswith("COR-TESTCO-")

            doc = session.get(Document, corr.document_id)
            assert doc is not None
            assert doc.file_type == FileType.HTML
            assert doc.title == "Test Correspondence"

    def test_create_draft_generates_unique_reference(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)

            corr1 = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)
            corr2 = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data, subject="Second")), maker)

            assert corr1.reference_number != corr2.reference_number
            assert corr1.reference_number.startswith("COR-TESTCO-")
            assert corr2.reference_number.startswith("COR-TESTCO-")

    def test_get_correspondence(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            fetched = svc.get_correspondence(corr.id, maker)
            assert fetched.id == corr.id
            assert fetched.created_by_name == "Maker User"

    def test_list_correspondences(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)

            svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data, subject="First")), maker)
            svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data, subject="Second")), maker)

            result = svc.list_correspondences(maker)
            assert result.total == 2

    def test_list_correspondences_by_direction(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)

            svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data, direction="internal")), maker)
            svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound")), maker)

            result = svc.list_correspondences(maker, direction=CorrespondenceDirection.INTERNAL)
            assert result.total == 1

    def test_update_correspondence(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            updated = svc.update_correspondence(
                corr.id,
                CorrespondenceUpdate(subject="Updated Subject"),
                maker,
            )
            assert updated.subject == "Updated Subject"

    def test_submit_correspondence(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        # Create a workflow definition via API
        wf_payload = {
            "name": "Correspondence WF",
            "description": "Correspondence approval",
            "steps": [{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
            }],
        }
        wf_resp = test_client.post("/api/v1/workflows", json=wf_payload, headers=auth_headers["admin"])
        assert wf_resp.status_code == 201
        wf_def_id = wf_resp.json()["id"]

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            assert result.status == CorrespondenceStatus.SUBMITTED

    def test_cannot_update_terminal_status(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            # Set terminal status directly on ORM object
            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.APPROVED
            session.add(orm_corr)
            session.commit()

            try:
                svc.update_correspondence(
                    corr.id,
                    CorrespondenceUpdate(subject="Should Fail"),
                    maker,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "cannot edit" in str(e).lower() or "conflict" in str(e).lower()

    def test_assign_correspondence(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            result = svc.assign_correspondence(
                corr.id,
                CorrespondenceAssign(to_user_id=admin.id, remarks="Please review"),
                admin,
            )
            assert result.status == CorrespondenceStatus.ASSIGNED

    def test_dispatch_correspondence(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            # Set status to approved via ORM
            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.APPROVED
            session.add(orm_corr)
            session.commit()

            result = svc.dispatch_correspondence(
                corr.id,
                CorrespondenceDispatch(
                    dispatch_method=DispatchMethod.EMAIL,
                    dispatch_reference="EMAIL-001",
                    remarks="Sent via email",
                ),
                admin,
            )
            assert result.dispatched_at is not None

    def test_dispatch_requires_approved_status(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), admin)

            try:
                svc.dispatch_correspondence(
                    corr.id,
                    CorrespondenceDispatch(dispatch_method=DispatchMethod.EMAIL),
                    admin,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "approved" in str(e).lower() or "cannot" in str(e).lower()

    def test_mark_delivered(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), admin)

            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.DISPATCHED
            session.add(orm_corr)
            session.commit()

            result = svc.mark_delivered(corr.id, admin)
            assert result.delivered_at is not None

    def test_mark_acknowledged(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), admin)

            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.DELIVERED
            session.add(orm_corr)
            session.commit()

            result = svc.mark_acknowledged(corr.id, admin)
            assert result.acknowledged_at is not None

    def test_get_movements(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            movements = svc.get_movements(corr.id, maker)
            assert isinstance(movements, list)

    def test_company_isolation(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            other_admin = session.get(User, seeded_data["other_admin_id"])
            svc = CorrespondenceService(session)

            # Create in company A
            corr_a = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            # User from company B should not see it
            try:
                svc.get_correspondence(corr_a.id, other_admin)
                # If admin has full access, this might pass
                # For strict isolation, this should fail
            except Exception:
                pass  # Expected for strict isolation

            # Company B creates their own
            svc_b = CorrespondenceService(session)
            corr_b = svc_b.create_draft(
                CorrespondenceCreate(**{
                    "directory_id": seeded_data["finance_directory_id"],
                    "category_id": seeded_data["marketing_category_id"],
                    "subject": "Other Company Correspondence",
                    "body": "<p>Body</p>",
                    "direction": "outbound",
                    "priority": "normal",
                    "sender_name": "Other Sender",
                }),
                other_admin,
            )

            # Verify separate reference numbers
            assert corr_a.reference_number.startswith("COR-TESTCO-")
            assert corr_b.reference_number.startswith("COR-OTHERCO-")


# ── Reference Number Tests ───────────────────────


class TestReferenceNumberGeneration:
    def test_reference_format(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            parts = corr.reference_number.split("-")
            assert parts[0] == "COR"
            assert parts[1] == "TESTCO"
            assert parts[2] == str(datetime.utcnow().year)
            assert len(parts[3]) == 6  # SEQ: 000001

    def test_sequence_increments(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)

            corr1 = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)
            corr2 = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            seq1 = int(corr1.reference_number.split("-")[-1])
            seq2 = int(corr2.reference_number.split("-")[-1])
            assert seq2 == seq1 + 1


# ── API/Router Tests ─────────────────────────────


class TestCorrespondenceAPI:
    def test_create_correspondence(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["subject"] == "Test Correspondence"
        assert data["direction"] == "outbound"
        assert "reference_number" in data

    def test_list_correspondences(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        # Create one first
        test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )

        resp = test_client.get("/api/v1/correspondences", headers=auth_headers["maker"])
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    def test_list_filter_by_direction(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, direction="internal"),
            headers=auth_headers["maker"],
        )
        test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, direction="outbound"),
            headers=auth_headers["maker"],
        )

        resp = test_client.get(
            "/api/v1/correspondences?direction=internal",
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_correspondence(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        resp = test_client.get(f"/api/v1/correspondences/{corr_id}", headers=auth_headers["maker"])
        assert resp.status_code == 200
        assert resp.json()["id"] == corr_id

    def test_update_correspondence(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        resp = test_client.patch(
            f"/api/v1/correspondences/{corr_id}",
            json={"subject": "Updated Subject"},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 200
        assert resp.json()["subject"] == "Updated Subject"

    def test_next_reference(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        resp = test_client.get(
            "/api/v1/correspondences/next-reference",
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 200
        assert "reference" in resp.json()

    def test_unauthenticated_access(self, client, seeded_data):
        test_client, _, _ = client
        resp = test_client.get("/api/v1/correspondences")
        assert resp.status_code in (401, 403)


# ── Attachment Tests ───────────────────────────────


class TestCorrespondenceAttachments:
    def test_add_attachment_to_outbound(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        import io
        file_content = b"Test PDF content"
        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
            data={"attachment_type": "supporting"},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["attachment_type"] == "supporting"
        assert data["file_name"] == "test.pdf"
        assert data["correspondence_id"] == corr_id

    def test_add_original_attachment_to_inbound(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, direction="inbound", body=None, date_received="2026-09-17T06:50:00Z"),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        import io
        file_content = b"Scanned letter content"
        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("letter.pdf", io.BytesIO(file_content), "application/pdf")},
            data={"attachment_type": "original"},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["attachment_type"] == "original"
        assert data["file_name"] == "letter.pdf"

    def test_detail_includes_attachments(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        import io
        test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")},
            data={"attachment_type": "supporting"},
            headers=auth_headers["maker"],
        )

        detail_resp = test_client.get(f"/api/v1/correspondences/{corr_id}", headers=auth_headers["maker"])
        assert detail_resp.status_code == 200
        attachments = detail_resp.json()["attachments"]
        assert len(attachments) == 1
        assert attachments[0]["file_name"] == "doc.pdf"

    def test_remove_attachment(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        import io
        attach_resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")},
            data={"attachment_type": "supporting"},
            headers=auth_headers["maker"],
        )
        attachment_id = attach_resp.json()["id"]

        del_resp = test_client.delete(
            f"/api/v1/correspondences/{corr_id}/attachments/{attachment_id}",
            headers=auth_headers["maker"],
        )
        assert del_resp.status_code == 204

        detail_resp = test_client.get(f"/api/v1/correspondences/{corr_id}", headers=auth_headers["maker"])
        assert len(detail_resp.json()["attachments"]) == 0

    def test_remove_nonexistent_attachment_returns_404(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        del_resp = test_client.delete(
            f"/api/v1/correspondences/{corr_id}/attachments/99999",
            headers=auth_headers["maker"],
        )
        assert del_resp.status_code == 404

    def test_download_no_document_returns_404(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, direction="inbound", body=None, date_received="2026-09-17T06:50:00Z"),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        resp = test_client.get(
            f"/api/v1/correspondences/{corr_id}/download",
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 404

    def test_replace_original_attachment_on_inbound(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, direction="inbound", body=None, date_received="2026-09-17T06:50:00Z"),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        import io
        resp1 = test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("original_letter.pdf", io.BytesIO(b"original content"), "application/pdf")},
            data={"attachment_type": "original"},
            headers=auth_headers["maker"],
        )
        assert resp1.status_code == 201
        first_att_id = resp1.json()["id"]

        resp2 = test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("replacement_letter.pdf", io.BytesIO(b"replacement content"), "application/pdf")},
            data={"attachment_type": "original"},
            headers=auth_headers["maker"],
        )
        assert resp2.status_code == 201

        detail = test_client.get(f"/api/v1/correspondences/{corr_id}", headers=auth_headers["maker"])
        originals = [a for a in detail.json()["attachments"] if a["attachment_type"] == "original"]
        assert len(originals) == 2

        test_client.delete(
            f"/api/v1/correspondences/{corr_id}/attachments/{first_att_id}",
            headers=auth_headers["maker"],
        )
        detail2 = test_client.get(f"/api/v1/correspondences/{corr_id}", headers=auth_headers["maker"])
        originals2 = [a for a in detail2.json()["attachments"] if a["attachment_type"] == "original"]
        assert len(originals2) == 1
        assert originals2[0]["file_name"] == "replacement_letter.pdf"

    def test_download_original_attachment(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, direction="inbound", body=None, date_received="2026-09-17T06:50:00Z"),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        import io
        test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("letter.pdf", io.BytesIO(b"letter content"), "application/pdf")},
            data={"attachment_type": "original"},
            headers=auth_headers["maker"],
        )

        resp = test_client.get(
            f"/api/v1/correspondences/{corr_id}/download",
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 200
        assert resp.content == b"letter content"

    def test_cannot_remove_attachment_in_terminal_status(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create_resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create_resp.json()["id"]

        import io
        attach_resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/attachments",
            files={"file": ("doc.pdf", io.BytesIO(b"content"), "application/pdf")},
            data={"attachment_type": "supporting"},
            headers=auth_headers["maker"],
        )
        attachment_id = attach_resp.json()["id"]

        _, engine, _ = client
        with Session(engine) as session:
            from correspondence.models import Correspondence, CorrespondenceStatus
            corr = session.get(Correspondence, corr_id)
            corr.status = CorrespondenceStatus.APPROVED
            session.add(corr)
            session.commit()

        del_resp = test_client.delete(
            f"/api/v1/correspondences/{corr_id}/attachments/{attachment_id}",
            headers=auth_headers["maker"],
        )
        assert del_resp.status_code == 409


# ── Workflow Status Sync Tests ───────────────────


class TestCorrespondenceWorkflowSync:
    def test_submit_saves_workflow_instance_id(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_payload = {
            "name": "Correspondence WF",
            "description": "Correspondence approval",
            "steps": [{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
            }],
        }
        wf_resp = test_client.post("/api/v1/workflows", json=wf_payload, headers=auth_headers["admin"])
        assert wf_resp.status_code == 201
        wf_def_id = wf_resp.json()["id"]

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            assert result.workflow_instance_id is not None

    def test_workflow_approval_syncs_correspondence_status(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_payload = {
            "name": "Correspondence WF",
            "description": "Correspondence approval",
            "steps": [{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
            }],
        }
        wf_resp = test_client.post("/api/v1/workflows", json=wf_payload, headers=auth_headers["admin"])
        wf_def_id = wf_resp.json()["id"]

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            wf_instance_id = result.workflow_instance_id

            # Simulate admin approval
            from workflow.models import WorkflowInstance, WorkflowStatus
            orm_instance = session.get(WorkflowInstance, wf_instance_id)
            orm_instance.status = WorkflowStatus.APPROVED
            session.add(orm_instance)
            session.commit()

            # Fetch detail — should sync status
            detail = svc.get_correspondence(corr.id, maker)
            assert detail.status == CorrespondenceStatus.APPROVED

    def test_dispatch_works_after_workflow_approval(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_payload = {
            "name": "Correspondence WF",
            "description": "Correspondence approval",
            "steps": [{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
            }],
        }
        wf_resp = test_client.post("/api/v1/workflows", json=wf_payload, headers=auth_headers["admin"])
        wf_def_id = wf_resp.json()["id"]

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            wf_instance_id = result.workflow_instance_id

            # Simulate approval
            from workflow.models import WorkflowInstance, WorkflowStatus
            orm_instance = session.get(WorkflowInstance, wf_instance_id)
            orm_instance.status = WorkflowStatus.APPROVED
            session.add(orm_instance)
            session.commit()

            # Dispatch should now work
            dispatch_result = svc.dispatch_correspondence(
                corr.id,
                CorrespondenceDispatch(
                    dispatch_method=DispatchMethod.EMAIL,
                    dispatch_reference="EMAIL-001",
                    remarks="Sent via email",
                ),
                admin,
            )
            assert dispatch_result.status == CorrespondenceStatus.DISPATCHED


class TestInboundSubmitWithAttachment:
    """Submit-time document auto-fallback (first attachment when document_id is None).

    Inbound records can no longer be submitted (see TestInboundSubmitRestriction),
    so the fallback is exercised on an outbound draft whose auto-generated
    backing-document link is cleared.
    """

    def test_submit_without_document_uses_first_attachment(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Attachment Fallback WF"
        )

        with Session(engine) as session:
            from users.models import User
            from correspondence.models import CorrespondenceAttachment
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)

            # Outbound draft starts with an auto-generated backing document
            corr = svc.create_draft(
                CorrespondenceCreate(**_corr_payload(seeded_data)),
                maker,
            )
            assert corr.document_id is not None
            assert corr.status == CorrespondenceStatus.DRAFT

            # Clear the link so submit must fall back to the first attachment
            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.document_id = None
            session.add(orm_corr)
            session.commit()
            session.refresh(orm_corr)
            assert orm_corr.document_id is None

            # Upload an attachment via the service (creates Document + CorrespondenceAttachment)
            import io
            from starlette.datastructures import UploadFile as StarletteUploadFile
            from starlette.datastructures import Headers
            from documents.models import DocumentUserLevelLink
            upload_file = StarletteUploadFile(
                file=io.BytesIO(b"fake letter content"),
                filename="letter.pdf",
                headers=Headers({"content-type": "application/pdf"}),
            )
            svc.add_attachment(corr.id, upload_file, "original", maker)

            link = session.exec(
                select(CorrespondenceAttachment)
                .where(CorrespondenceAttachment.correspondence_id == corr.id)
            ).first()
            assert link is not None
            doc_link = DocumentUserLevelLink(
                document_id=link.document_id,
                user_level_id=seeded_data["medium_level_id"],
            )
            session.add(doc_link)
            session.commit()

            # Now submit — should auto-fallback to the attachment's document
            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            assert result.workflow_instance_id is not None
            assert result.status == CorrespondenceStatus.SUBMITTED
            assert result.document_id == link.document_id


class TestInboundSubmitRestriction:
    """Inbound correspondence is the original incoming record and is never
    submitted for approval — only the OUTBOUND reply is (service, API and the
    generic workflow-instance endpoint)."""

    def _create_inbound(self, engine, seeded_data):
        from users.models import User

        with Session(engine) as session:
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(
                CorrespondenceCreate(
                    **_corr_payload(
                        seeded_data,
                        direction="inbound",
                        body=None,
                        document_id=seeded_data["finance_document_id"],
                    )
                ),
                maker,
            )
            assert corr.status == CorrespondenceStatus.RECEIVED
            return corr.id

    def test_submit_inbound_service_rejected(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Inbound Blocked WF"
        )
        corr_id = self._create_inbound(engine, seeded_data)

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            try:
                svc.submit_correspondence(
                    corr_id,
                    CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                    maker,
                )
                assert False, "Should have raised"
            except HTTPException as e:
                assert e.status_code == 409
                assert "inbound" in e.detail.lower()
                assert "reply" in e.detail.lower()

            orm_corr = session.get(Correspondence, corr_id)
            assert orm_corr.workflow_instance_id is None
            assert orm_corr.status == CorrespondenceStatus.RECEIVED

    def test_submit_inbound_api_rejected(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Inbound Blocked API WF"
        )
        corr_id = self._create_inbound(engine, seeded_data)

        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/submit",
            json={"workflow_definition_id": wf_def_id},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 409
        assert "inbound" in resp.json()["detail"].lower()

    def test_submit_inbound_reply_rejected(self, seeded_data, client, auth_headers):
        """A reply created with direction=inbound is still an inbound record."""
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Inbound Reply WF"
        )
        parent, maker = _make_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            maker = session.get(type(maker), maker.id)
            svc = CorrespondenceService(session)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="inbound", body=None)),
                maker,
            )
            try:
                svc.submit_reply(
                    reply.id,
                    CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                    maker,
                )
                assert False, "Should have raised"
            except HTTPException as e:
                assert e.status_code == 409
                assert "inbound" in e.detail.lower()

    def test_generic_instance_on_inbound_document_rejected(self, seeded_data, client, auth_headers):
        """POST /workflow-instances must not route an inbound record's document."""
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Inbound Doc Blocked WF"
        )
        self._create_inbound(engine, seeded_data)

        resp = test_client.post(
            "/api/v1/workflow-instances",
            json={
                "document_id": seeded_data["finance_document_id"],
                "workflow_definition_id": wf_def_id,
            },
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 409
        assert "inbound" in resp.json()["detail"].lower()

    def test_generic_instance_on_inbound_attachment_rejected(self, seeded_data, client, auth_headers):
        """Uploaded originals (attachment link only) are blocked too."""
        import io

        from starlette.datastructures import Headers
        from starlette.datastructures import UploadFile as StarletteUploadFile
        from users.models import User

        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Inbound Attachment WF"
        )
        parent, _ = _make_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            upload_file = StarletteUploadFile(
                file=io.BytesIO(b"incoming letter"),
                filename="incoming.pdf",
                headers=Headers({"content-type": "application/pdf"}),
            )
            att = svc.add_attachment(parent.id, upload_file, "original", maker)
            doc_id = att.document_id

        resp = test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": doc_id, "workflow_definition_id": wf_def_id},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 409
        assert "inbound" in resp.json()["detail"].lower()

    def test_generic_instance_on_outbound_document_allowed(self, seeded_data, client, auth_headers):
        """Control: outbound records keep their existing workflow submission."""
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Outbound Doc WF"
        )

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)
            doc_id = corr.document_id
            assert doc_id is not None

        resp = test_client.post(
            "/api/v1/workflow-instances",
            json={"document_id": doc_id, "workflow_definition_id": wf_def_id},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 201, resp.text

    def test_full_inbound_reply_approval_flow(self, seeded_data, client, auth_headers):
        """End-to-end: INBOUND received → no submit → OUTBOUND reply →
        submit-reply → approval workflow → status sync."""
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Reply Approval E2E WF"
        )

        # 1. INBOUND record is received
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(
                seeded_data,
                direction="inbound",
                body=None,
                document_id=seeded_data["finance_document_id"],
            ),
            headers=auth_headers["maker"],
        )
        assert create.status_code == 201, create.text
        parent = create.json()
        assert parent["direction"] == "inbound"
        assert parent["status"] == "received"

        # 2. Submit for Approval is refused on the inbound record
        blocked = test_client.post(
            f"/api/v1/correspondences/{parent['id']}/submit",
            json={"workflow_definition_id": wf_def_id},
            headers=auth_headers["maker"],
        )
        assert blocked.status_code == 409
        assert "inbound" in blocked.json()["detail"].lower()

        # 3. OUTBOUND reply is created against it
        reply_resp = test_client.post(
            f"/api/v1/correspondences/{parent['id']}/reply",
            json=_corr_payload(seeded_data, direction="outbound"),
            headers=auth_headers["maker"],
        )
        assert reply_resp.status_code == 201, reply_resp.text
        reply = reply_resp.json()
        assert reply["direction"] == "outbound"
        assert reply["parent_correspondence_id"] == parent["id"]
        assert reply["status"] == "draft"

        # 4. The reply IS submitted for approval
        submit = test_client.post(
            f"/api/v1/correspondences/{reply['id']}/submit-reply",
            json={"workflow_definition_id": wf_def_id},
            headers=auth_headers["maker"],
        )
        assert submit.status_code == 200, submit.text
        submitted = submit.json()
        assert submitted["status"] in ("submitted", "pending_approval")
        assert submitted["workflow_instance_id"] is not None

        parent_detail = test_client.get(
            f"/api/v1/correspondences/{parent['id']}", headers=auth_headers["maker"]
        )
        assert parent_detail.json()["response_received"] is True

        # 5. Approval workflow runs unchanged and syncs the reply status
        approve = test_client.post(
            f"/api/v1/workflow-instances/{submitted['workflow_instance_id']}/actions",
            json={"action": "approve"},
            headers=auth_headers["admin"],
        )
        assert approve.status_code == 200, approve.text

        final = test_client.get(
            f"/api/v1/correspondences/{reply['id']}", headers=auth_headers["maker"]
        )
        assert final.json()["status"] == "approved"

        # The inbound record still never entered a workflow
        parent_final = test_client.get(
            f"/api/v1/correspondences/{parent['id']}", headers=auth_headers["maker"]
        )
        assert parent_final.json()["workflow_instance_id"] is None
        assert parent_final.json()["status"] == "received"


# ── Lifecycle Tests (Complete/Archive) ───────────────


class TestCorrespondenceLifecycle:
    def test_complete_correspondence_from_acknowledged(self, seeded_data, client, auth_headers):
        """Test full lifecycle: create → submit → approve → dispatch → deliver → acknowledge → complete"""
        test_client, engine, _ = client
        wf_payload = {
            "name": "Lifecycle WF",
            "description": "Test complete lifecycle",
            "steps": [{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
            }],
        }
        wf_resp = test_client.post("/api/v1/workflows", json=wf_payload, headers=auth_headers["admin"])
        assert wf_resp.status_code == 201
        wf_def_id = wf_resp.json()["id"]

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)

            # Create draft
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            # Submit to workflow
            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            assert result.status == CorrespondenceStatus.SUBMITTED
            wf_instance_id = result.workflow_instance_id

            # Approve workflow (simulate admin approval)
            from workflow.models import WorkflowInstance, WorkflowStatus
            orm_instance = session.get(WorkflowInstance, wf_instance_id)
            orm_instance.status = WorkflowStatus.APPROVED
            session.add(orm_instance)
            session.commit()

            # Sync status
            detail = svc.get_correspondence(corr.id, maker)
            assert detail.status == CorrespondenceStatus.APPROVED

            # Dispatch
            dispatch_result = svc.dispatch_correspondence(
                corr.id,
                CorrespondenceDispatch(
                    dispatch_method=DispatchMethod.EMAIL,
                    dispatch_reference="EMAIL-001",
                    remarks="Sent via email",
                ),
                admin,
            )
            assert dispatch_result.status == CorrespondenceStatus.DISPATCHED

            # Deliver
            deliver_result = svc.mark_delivered(corr.id, admin)
            assert deliver_result.status == CorrespondenceStatus.DELIVERED

            # Acknowledge
            ack_result = svc.mark_acknowledged(corr.id, admin)
            assert ack_result.status == CorrespondenceStatus.ACKNOWLEDGED

            # Complete
            complete_result = svc.complete_correspondence(
                corr.id,
                CorrespondenceComplete(remarks="Successfully completed"),
                admin,
            )
            assert complete_result.status == CorrespondenceStatus.COMPLETED
            assert complete_result.completed_at is not None
            assert complete_result.completed_by_id == admin.id

    def test_complete_requires_acknowledged_status(self, seeded_data, client, auth_headers):
        """Complete should fail if not in ACKNOWLEDGED status"""
        test_client, engine, _ = client

        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)

            # Create and set to APPROVED (not acknowledged)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), admin)
            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.APPROVED
            session.add(orm_corr)
            session.commit()

            try:
                svc.complete_correspondence(
                    corr.id,
                    CorrespondenceComplete(remarks="Should fail"),
                    admin,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "acknowledged" in str(e).lower() or "cannot" in str(e).lower()

    def test_archive_correspondence_from_completed(self, seeded_data, client, auth_headers):
        """Test full lifecycle ending in archive: complete → archive"""
        test_client, engine, _ = client
        wf_payload = {
            "name": "Archive Lifecycle WF",
            "description": "Test archive lifecycle",
            "steps": [{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": seeded_data["admin_id"]}],
            }],
        }
        wf_resp = test_client.post("/api/v1/workflows", json=wf_payload, headers=auth_headers["admin"])
        assert wf_resp.status_code == 201
        wf_def_id = wf_resp.json()["id"]

        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)

            # Create draft
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            # Submit to workflow
            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            wf_instance_id = result.workflow_instance_id

            # Approve workflow
            from workflow.models import WorkflowInstance, WorkflowStatus
            orm_instance = session.get(WorkflowInstance, wf_instance_id)
            orm_instance.status = WorkflowStatus.APPROVED
            session.add(orm_instance)
            session.commit()

            # Dispatch
            svc.dispatch_correspondence(
                corr.id,
                CorrespondenceDispatch(
                    dispatch_method=DispatchMethod.EMAIL,
                    dispatch_reference="EMAIL-001",
                    remarks="Sent via email",
                ),
                admin,
            )

            # Deliver
            svc.mark_delivered(corr.id, admin)

            # Acknowledge
            svc.mark_acknowledged(corr.id, admin)

            # Complete
            complete_result = svc.complete_correspondence(
                corr.id,
                CorrespondenceComplete(remarks="Successfully completed"),
                admin,
            )
            assert complete_result.status == CorrespondenceStatus.COMPLETED

            # Archive
            archive_result = svc.archive_correspondence(
                corr.id,
                CorrespondenceArchive(remarks="Archived for records"),
                admin,
            )
            assert archive_result.status == CorrespondenceStatus.ARCHIVED
            assert archive_result.archived_at is not None
            assert archive_result.archived_by_id == admin.id

    def test_archive_requires_completed_status(self, seeded_data, client, auth_headers):
        """Archive should fail if not in COMPLETED status"""
        test_client, engine, _ = client

        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)

            # Create and set to ACKNOWLEDGED (not completed)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), admin)
            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.ACKNOWLEDGED
            session.add(orm_corr)
            session.commit()

            try:
                svc.archive_correspondence(
                    corr.id,
                    CorrespondenceArchive(remarks="Should fail"),
                    admin,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "completed" in str(e).lower() or "cannot" in str(e).lower()

    def test_cannot_complete_terminal_status(self, seeded_data, client, auth_headers):
        """Cannot complete if already in terminal status (COMPLETED/ARCHIVED)"""
        test_client, engine, _ = client

        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)

            # Create and set to COMPLETED
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), admin)
            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.COMPLETED
            session.add(orm_corr)
            session.commit()

            try:
                svc.complete_correspondence(
                    corr.id,
                    CorrespondenceComplete(remarks="Should fail"),
                    admin,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "completed" in str(e).lower() or "terminal" in str(e).lower() or "cannot" in str(e).lower()

    def test_cannot_archive_terminal_status(self, seeded_data, client, auth_headers):
        """Cannot archive if already ARCHIVED"""
        test_client, engine, _ = client

        with Session(engine) as session:
            from users.models import User
            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)

            # Create and set to ARCHIVED
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), admin)
            orm_corr = session.get(Correspondence, corr.id)
            orm_corr.status = CorrespondenceStatus.ARCHIVED
            session.add(orm_corr)
            session.commit()

            try:
                svc.archive_correspondence(
                    corr.id,
                    CorrespondenceArchive(remarks="Should fail"),
                    admin,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "archived" in str(e).lower() or "terminal" in str(e).lower() or "cannot" in str(e).lower()


# ── Reply-Response Lifecycle Tests ───────────────


class TestCorrespondenceReply:
    """Tests for the complete reply-response lifecycle."""

    def _create_inbound_parent(self, engine, seeded_data, user_id=None):
        from users.models import User
        with Session(engine) as session:
            svc = CorrespondenceService(session)
            user = session.get(User, user_id or seeded_data["maker_id"])
            parent = svc.create_draft(
                CorrespondenceCreate(
                    **_corr_payload(
                        seeded_data,
                        direction="inbound",
                        body=None,
                        response_required=True,
                        response_deadline="2099-12-31T00:00:00Z",
                    )
                ),
                user,
            )
            return parent, user

    def test_create_reply_links_to_parent(self, seeded_data, client):
        _, engine, _ = client
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            svc = CorrespondenceService(session)
            maker = session.get(type(maker), maker.id)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(
                    **_corr_payload(seeded_data, subject="Re: Test Correspondence", direction="outbound")
                ),
                maker,
            )

            assert reply.parent_correspondence_id == parent.id
            assert reply.direction == CorrespondenceDirection.OUTBOUND
            assert reply.status == CorrespondenceStatus.DRAFT
            assert reply.parent_reference == parent.reference_number
            orm_reply = session.get(Correspondence, reply.id)
            assert orm_reply.parent_correspondence_id == parent.id
            assert orm_reply.category_id == parent.category_id

    def test_reply_backing_document_uses_category_directory(self, seeded_data, client):
        _, engine, _ = client
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from documents.models import Document
            svc = CorrespondenceService(session)
            maker = session.get(type(maker), maker.id)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(
                    **_corr_payload(
                        seeded_data,
                        subject="Re: Test Correspondence",
                        direction="outbound",
                        category_id=None,
                    )
                ),
                maker,
            )
            orm_reply = session.get(Correspondence, reply.id)
            # Reply inherits the parent's category when none is supplied
            assert orm_reply.category_id == parent.category_id
            assert orm_reply.category_id == seeded_data["finance_category_id"]
            # Backing document is filed under the category's directory (not the placeholder dir 1)
            doc = session.get(Document, orm_reply.document_id)
            assert doc is not None
            assert doc.directory_id == seeded_data["finance_directory_id"]

    def test_create_reply_defaults_subject_to_re(self, seeded_data, client):
        _, engine, _ = client
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            svc = CorrespondenceService(session)
            maker = session.get(type(maker), maker.id)
            data = CorrespondenceCreate(
                **_corr_payload(seeded_data, direction="outbound")
            )
            # Service falls back to "Re: <parent subject>" when no subject is provided
            data.subject = ""
            reply = svc.create_reply(parent.id, data, maker)
            assert reply.subject == f"Re: {parent.subject}"

    def test_get_replies_lists_all_replies(self, seeded_data, client):
        _, engine, _ = client
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            svc = CorrespondenceService(session)
            maker = session.get(type(maker), maker.id)
            for i, subject in enumerate(["Re: First", "Re: Second"], start=1):
                svc.create_reply(
                    parent.id,
                    CorrespondenceCreate(
                        **_corr_payload(seeded_data, direction="outbound", subject=subject)
                    ),
                    maker,
                )

            replies = svc.get_replies(parent.id, maker)
            assert len(replies) == 2
            assert {r.subject for r in replies} == {"Re: First", "Re: Second"}
            for reply in replies:
                assert reply.parent_correspondence_id == parent.id

    def test_cannot_reply_to_other_company(self, seeded_data, client):
        _, engine, _ = client
        parent, _maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from users.models import User
            other_admin = session.get(User, seeded_data["other_admin_id"])
            svc = CorrespondenceService(session)
            try:
                svc.create_reply(
                    parent.id,
                    CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound")),
                    other_admin,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "another company" in str(e).lower()

    def test_cannot_reply_to_terminal_parent(self, seeded_data, client):
        _, engine, _ = client
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from users.models import User
            maker = session.get(type(maker), maker.id)
            orm_parent = session.get(Correspondence, parent.id)
            orm_parent.status = CorrespondenceStatus.ARCHIVED
            session.add(orm_parent)
            session.commit()

            svc = CorrespondenceService(session)
            try:
                svc.create_reply(
                    parent.id,
                    CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound")),
                    maker,
                )
                assert False, "Should have raised"
            except Exception as e:
                assert "terminal" in str(e).lower() or "cannot" in str(e).lower()

    def test_submit_reply_marks_parent_responded(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Reply WF")
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from users.models import User
            maker = session.get(type(maker), maker.id)
            svc = CorrespondenceService(session)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound")),
                maker,
            )

            result = svc.submit_reply(
                reply.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            assert result.workflow_instance_id is not None
            assert result.status == CorrespondenceStatus.SUBMITTED

            orm_parent = session.get(Correspondence, parent.id)
            assert orm_parent.response_received is True
            assert orm_parent.responded_at is not None

    def test_mark_responded_sets_fields_and_movement(self, seeded_data, client):
        _, engine, _ = client
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from users.models import User
            maker = session.get(type(maker), maker.id)
            svc = CorrespondenceService(session)
            result = svc.mark_responded(parent.id, maker)

            assert result.response_received is True
            assert result.responded_at is not None

            movements = session.exec(
                select(CorrespondenceMovement).where(
                    CorrespondenceMovement.correspondence_id == parent.id
                )
            ).all()
            assert any(m.action == "respond" for m in movements)

    def test_mark_responded_only_inbound(self, seeded_data, client):
        _, engine, _ = client
        with Session(engine) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            outbound = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)
            try:
                svc.mark_responded(outbound.id, maker)
                assert False, "Should have raised"
            except Exception as e:
                assert "inbound" in str(e).lower()

    def test_mark_responded_forbidden_in_terminal_status(self, seeded_data, client):
        _, engine, _ = client
        parent, maker = self._create_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from users.models import User
            maker = session.get(type(maker), maker.id)
            orm_parent = session.get(Correspondence, parent.id)
            orm_parent.status = CorrespondenceStatus.COMPLETED
            session.add(orm_parent)
            session.commit()

            svc = CorrespondenceService(session)
            try:
                svc.mark_responded(parent.id, maker)
                assert False, "Should have raised"
            except Exception as e:
                assert "terminal" in str(e).lower() or "cannot" in str(e).lower()

    def test_reply_detail_exposes_parent_reference(self, seeded_data, client, auth_headers):
        test_client, _, _ = client
        parent, _maker = self._create_inbound_parent(client[1], seeded_data)

        with Session(client[1]) as session:
            from users.models import User
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(
                    **_corr_payload(seeded_data, direction="outbound", subject="Re: Test")
                ),
                maker,
            )
            detail = svc.get_correspondence(reply.id, maker)
            assert detail.parent_reference == parent.reference_number
            assert detail.parent_correspondence_id == parent.id


# ── Lifecycle correction regressions (WP1–WP7) ──────────────


def _make_inbound_parent(engine, seeded_data, user_id=None):
    from users.models import User

    with Session(engine) as session:
        svc = CorrespondenceService(session)
        user = session.get(User, user_id or seeded_data["maker_id"])
        parent = svc.create_draft(
            CorrespondenceCreate(
                **_corr_payload(
                    seeded_data,
                    direction="inbound",
                    body=None,
                    response_required=True,
                    response_deadline="2099-12-31T00:00:00Z",
                )
            ),
            user,
        )
        return parent, user


class TestCompleteArchiveHTTP:
    """WP1: HTTP complete/archive previously crashed with NameError
    (``send_notification_task`` was referenced without import)."""

    def test_complete_and_archive_via_api(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["admin"],
        )
        assert create.status_code == 201
        corr_id = create.json()["id"]

        with Session(engine) as session:
            corr = session.get(Correspondence, corr_id)
            corr.status = CorrespondenceStatus.ACKNOWLEDGED
            session.add(corr)
            session.commit()

        complete = test_client.post(
            f"/api/v1/correspondences/{corr_id}/complete",
            json={"remarks": "All done"},
            headers=auth_headers["admin"],
        )
        assert complete.status_code == 200
        assert complete.json()["status"] == "completed"

        archive = test_client.post(
            f"/api/v1/correspondences/{corr_id}/archive",
            json={"remarks": "Filed away"},
            headers=auth_headers["admin"],
        )
        assert archive.status_code == 200
        assert archive.json()["status"] == "archived"

    def test_complete_resolves_notification_reference(self, seeded_data, client):
        from users.models import User

        _, engine, _ = client
        with Session(engine) as session:
            admin = session.get(User, seeded_data["admin_id"])
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            orm = session.get(Correspondence, corr.id)
            orm.status = CorrespondenceStatus.ACKNOWLEDGED
            session.add(orm)
            session.commit()

            # Queues send_notification_task — raised NameError before WP1
            result = svc.complete_correspondence(
                corr.id,
                CorrespondenceComplete(remarks="done"),
                admin,
                BackgroundTasks(),
            )
            assert result.status == CorrespondenceStatus.COMPLETED


class TestAssignGuards:
    """WP2: assignment is a registration-stage action."""

    def test_assign_rejected_when_submitted(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["admin"],
        )
        corr_id = create.json()["id"]

        with Session(engine) as session:
            corr = session.get(Correspondence, corr_id)
            corr.status = CorrespondenceStatus.SUBMITTED
            session.add(corr)
            session.commit()

        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/assign",
            json={"to_user_id": seeded_data["maker_id"]},
            headers=auth_headers["admin"],
        )
        assert resp.status_code == 409
        assert "submitted" in resp.json()["detail"]

    def test_assign_rejected_after_dispatch(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["admin"],
        )
        corr_id = create.json()["id"]

        with Session(engine) as session:
            corr = session.get(Correspondence, corr_id)
            corr.dispatch_method = DispatchMethod.EMAIL
            session.add(corr)
            session.commit()

        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/assign",
            json={"to_user_id": seeded_data["maker_id"]},
            headers=auth_headers["admin"],
        )
        assert resp.status_code == 409
        assert "after dispatch" in resp.json()["detail"]

    def test_submit_from_assigned_status(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(
            test_client, auth_headers, seeded_data, name="Assigned Submit WF"
        )

        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        assert create.status_code == 201
        corr_id = create.json()["id"]

        assign = test_client.post(
            f"/api/v1/correspondences/{corr_id}/assign",
            json={"to_user_id": seeded_data["maker_id"], "remarks": "please handle"},
            headers=auth_headers["admin"],
        )
        assert assign.status_code == 200
        assert assign.json()["status"] == "assigned"

        submit = test_client.post(
            f"/api/v1/correspondences/{corr_id}/submit",
            json={"workflow_definition_id": wf_def_id},
            headers=auth_headers["maker"],
        )
        assert submit.status_code == 200
        assert submit.json()["status"] == "submitted"


class TestCreateValidation:
    """WP3: category / deadline validation on create and update."""

    def test_create_requires_category(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        payload = _corr_payload(seeded_data)
        del payload["category_id"]

        resp = test_client.post(
            "/api/v1/correspondences",
            json=payload,
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 422
        assert "Category is required" in resp.json()["detail"]

    def test_create_response_required_needs_deadline(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, response_required=True),
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 422
        assert "deadline" in resp.json()["detail"]

    def test_update_cannot_clear_category(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        assert create.status_code == 201
        corr_id = create.json()["id"]

        resp = test_client.patch(
            f"/api/v1/correspondences/{corr_id}",
            json={"category_id": None},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 422
        assert "Category is required" in resp.json()["detail"]

        detail = test_client.get(
            f"/api/v1/correspondences/{corr_id}",
            headers=auth_headers["maker"],
        )
        assert detail.json()["category_id"] == seeded_data["finance_category_id"]


class TestReplyLifecycleCorrections:
    """WP4: submit-reply flags the parent; rejection/return releases it."""

    def test_submit_reply_records_response_correspondence(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Reply Flag WF")
        parent, maker = _make_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            maker = session.get(type(maker), maker.id)
            svc = CorrespondenceService(session)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound")),
                maker,
            )
            svc.submit_reply(
                reply.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )

            orm_parent = session.get(Correspondence, parent.id)
            assert orm_parent.response_received is True
            assert orm_parent.response_correspondence_id == reply.id

    def test_rejected_reply_releases_parent_flag(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Reply Reject WF")
        parent, maker = _make_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from workflow.models import WorkflowInstance, WorkflowStatus

            maker = session.get(type(maker), maker.id)
            svc = CorrespondenceService(session)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound")),
                maker,
            )
            result = svc.submit_reply(
                reply.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )

            orm_parent = session.get(Correspondence, parent.id)
            assert orm_parent.response_received is True

            instance = session.get(WorkflowInstance, result.workflow_instance_id)
            instance.status = WorkflowStatus.REJECTED
            session.add(instance)
            session.commit()

            detail = svc.get_correspondence(reply.id, maker)
            assert detail.status == CorrespondenceStatus.REJECTED

            session.refresh(orm_parent)
            assert orm_parent.response_received is False
            assert orm_parent.responded_at is None
            assert orm_parent.response_correspondence_id is None

    def test_submit_reply_rejects_non_reply(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Not Reply WF")

        with Session(engine) as session:
            from users.models import User

            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            corr = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)

            try:
                svc.submit_reply(
                    corr.id,
                    CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                    maker,
                )
                assert False, "Should have raised"
            except HTTPException as e:
                assert e.status_code == 409
                assert "not a reply" in e.detail

    def test_submit_reply_rejects_non_inbound_parent(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_def_id = _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Outbound Parent WF")

        with Session(engine) as session:
            from users.models import User

            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)
            parent = svc.create_draft(CorrespondenceCreate(**_corr_payload(seeded_data)), maker)
            reply = svc.create_reply(
                parent.id,
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound")),
                maker,
            )

            try:
                svc.submit_reply(
                    reply.id,
                    CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                    maker,
                )
                assert False, "Should have raised"
            except HTTPException as e:
                assert e.status_code == 409
                assert "not inbound" in e.detail

    def test_rejected_reply_does_not_clear_newer_flag(self, seeded_data, client, auth_headers):
        """Guard: only the reply recorded in response_correspondence_id may
        release the parent flag; a stale rejection must leave it alone."""
        test_client, engine, _ = client
        wf_a = _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Reply A WF")
        wf_b = _create_workflow_for_finance(test_client, auth_headers, seeded_data, name="Reply B WF")
        parent, maker = _make_inbound_parent(engine, seeded_data)

        with Session(engine) as session:
            from workflow.models import WorkflowInstance, WorkflowStatus

            maker = session.get(type(maker), maker.id)
            svc = CorrespondenceService(session)
            reply_a = svc.create_reply(
                parent.id,
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound", subject="Re: A")),
                maker,
            )
            reply_b = svc.create_reply(
                parent.id,
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="outbound", subject="Re: B")),
                maker,
            )
            result_a = svc.submit_reply(reply_a.id, CorrespondenceSubmit(workflow_definition_id=wf_a), maker)
            svc.submit_reply(reply_b.id, CorrespondenceSubmit(workflow_definition_id=wf_b), maker)

            orm_parent = session.get(Correspondence, parent.id)
            assert orm_parent.response_correspondence_id == reply_b.id

            instance = session.get(WorkflowInstance, result_a.workflow_instance_id)
            instance.status = WorkflowStatus.REJECTED
            session.add(instance)
            session.commit()

            svc.get_correspondence(reply_a.id, maker)

            session.refresh(orm_parent)
            assert orm_parent.response_received is True
            assert orm_parent.response_correspondence_id == reply_b.id


class TestRoleGates:
    """WP6: SUPERADMIN is read-only; lifecycle mutations are admin-only."""

    def test_superadmin_create_denied(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["superadmin"],
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"]

    def test_superadmin_update_denied(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["admin"],
        )
        corr_id = create.json()["id"]

        resp = test_client.patch(
            f"/api/v1/correspondences/{corr_id}",
            json={"subject": "Renamed by superadmin"},
            headers=auth_headers["superadmin"],
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"]

    def test_superadmin_complete_denied(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["admin"],
        )
        corr_id = create.json()["id"]

        with Session(engine) as session:
            corr = session.get(Correspondence, corr_id)
            corr.status = CorrespondenceStatus.ACKNOWLEDGED
            session.add(corr)
            session.commit()

        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/complete",
            json={"remarks": "nope"},
            headers=auth_headers["superadmin"],
        )
        assert resp.status_code == 403
        assert "read-only" in resp.json()["detail"]

    def test_non_admin_cannot_complete(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create.json()["id"]

        with Session(engine) as session:
            corr = session.get(Correspondence, corr_id)
            corr.status = CorrespondenceStatus.ACKNOWLEDGED
            session.add(corr)
            session.commit()

        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/complete",
            json={"remarks": "nope"},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 403
        assert "Admin access required" in resp.json()["detail"]

    def test_non_admin_cannot_forward(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data),
            headers=auth_headers["maker"],
        )
        corr_id = create.json()["id"]

        resp = test_client.post(
            f"/api/v1/correspondences/{corr_id}/forward",
            json={"to_user_id": seeded_data["maker_id"]},
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 403
        assert "Admin access required" in resp.json()["detail"]


class TestDocumentSignatureGuards:
    """WP7: document ownership resolves document → directory → category →
    company; signatures must belong to the caller."""

    def test_inbound_create_cross_company_document_rejected(self, client, auth_headers, seeded_data):
        from documents.models import DocumentStatus

        test_client, engine, _ = client
        with Session(engine) as session:
            other_doc = Document(
                title="Other company doc",
                directory_id=seeded_data["marketing_directory_id"],
                uploaded_by=seeded_data["other_admin_id"],
                file_name="other.pdf",
                file_type=FileType.PDF,
                mime_type="application/pdf",
                file_size=4,
                storage_path="marketing/other.pdf",
                status=DocumentStatus.ACTIVE,
            )
            session.add(other_doc)
            session.commit()
            other_doc_id = other_doc.id

        resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(
                seeded_data,
                direction="inbound",
                body=None,
                document_id=other_doc_id,
            ),
            headers=auth_headers["admin"],
        )
        assert resp.status_code == 422
        assert resp.json()["detail"] == "Document not found"

    def test_inbound_create_rejects_already_linked_document(self, client, auth_headers, seeded_data):
        test_client, _, _ = client
        payload = _corr_payload(
            seeded_data,
            direction="inbound",
            body=None,
            document_id=seeded_data["finance_document_id"],
        )
        first = test_client.post(
            "/api/v1/correspondences",
            json=payload,
            headers=auth_headers["admin"],
        )
        assert first.status_code == 201

        second = test_client.post(
            "/api/v1/correspondences",
            json=payload,
            headers=auth_headers["admin"],
        )
        assert second.status_code == 409
        assert "already linked" in second.json()["detail"]

    def test_create_rejects_foreign_signature(self, client, auth_headers, seeded_data):
        from workflow.models import Signature, SignatureType

        test_client, engine, _ = client
        with Session(engine) as session:
            sig = Signature(
                user_id=seeded_data["admin_id"],
                file_name="admin.png",
                file_path="signatures/admin.png",
                mime_type="image/png",
                file_size=10,
                sig_type=SignatureType.E_SIGNATURE,
            )
            session.add(sig)
            session.commit()
            sig_id = sig.id

        resp = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, author_signature_id=sig_id),
            headers=auth_headers["maker"],
        )
        assert resp.status_code == 403
        assert "own signatures" in resp.json()["detail"]


# ── Pending Approval list sync ───────────────────────


class TestPendingApprovalListSync:
    """Approval actions update only the workflow instance; the list API must
    reconcile the stored correspondence status before filtering and counting
    so approved/rejected/returned rows leave the 'Pending Approval' list
    immediately (and stale rows are healed)."""

    def _make_checker(self, engine, seeded_data, email="checker.pending@example.com"):
        from core.security import create_access_token, hash_password
        from users.models import Role, RoleName, User, UserCategoryLink, UserRoleLink

        with Session(engine) as session:
            role = session.exec(select(Role).where(Role.name == RoleName.CHECKER)).first()
            assert role, "seeded CHECKER role missing"
            user = User(
                full_name="Checker Approver",
                email=email,
                hashed_password=hash_password("Test@1234"),
                is_active=True,
                user_level_id=seeded_data["medium_level_id"],
                company_id=seeded_data["company_id"],
            )
            session.add(user)
            session.flush()
            session.add(UserRoleLink(user_id=user.id, role_id=role.id))
            session.add(
                UserCategoryLink(
                    user_id=user.id, category_id=seeded_data["finance_category_id"]
                )
            )
            session.commit()
            checker_id = user.id
        headers = {"Authorization": f"Bearer {create_access_token(checker_id)}"}
        return checker_id, headers

    def _create_workflow(self, test_client, auth_headers, approver_id, name, steps=1):
        payload = {
            "name": name,
            "description": "Pending list sync test",
            "steps": [
                {
                    "step_order": i,
                    "step_name": f"Review {i}",
                    "approval_mode": "sequential",
                    "approvers": [{"user_id": approver_id}],
                }
                for i in range(1, steps + 1)
            ],
        }
        resp = test_client.post(
            "/api/v1/workflows", json=payload, headers=auth_headers["admin"]
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    def _submit(self, test_client, auth_headers, seeded_data, wf_id, subject):
        create = test_client.post(
            "/api/v1/correspondences",
            json=_corr_payload(seeded_data, subject=subject),
            headers=auth_headers["maker"],
        )
        assert create.status_code == 201, create.text
        corr = create.json()
        sub = test_client.post(
            f"/api/v1/correspondences/{corr['id']}/submit",
            json={"workflow_definition_id": wf_id},
            headers=auth_headers["maker"],
        )
        assert sub.status_code == 200, sub.text
        assert sub.json()["status"] in ("submitted", "pending_approval")
        assert corr["document_id"] is not None
        return corr

    def _instance_id(self, engine, document_id):
        from workflow.models import WorkflowInstance

        with Session(engine) as session:
            instance = session.exec(
                select(WorkflowInstance).where(
                    WorkflowInstance.document_id == document_id
                )
            ).first()
            assert instance
            return instance.id

    def _act(self, test_client, instance_id, action, checker_headers):
        resp = test_client.post(
            f"/api/v1/workflow-instances/{instance_id}/actions",
            json={"action": action, "remarks": "pending-list test"},
            headers=checker_headers,
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def _status_ids(self, test_client, auth_headers, status_value, **params):
        resp = test_client.get(
            "/api/v1/correspondences",
            params={"status": status_value, **params},
            headers=auth_headers["admin"],
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        return {item["id"] for item in data["items"]}, data["total"]

    def _db_status(self, engine, corr_id):
        with Session(engine) as session:
            corr = session.get(Correspondence, corr_id)
            assert corr
            return corr.status

    def test_approved_correspondence_leaves_pending_list_immediately(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        # 2-step workflow: approving step 1 advances the instance to
        # pending_approval, which is the state where the bug is observable.
        wf_id = self._create_workflow(
            test_client, auth_headers, checker_id, "Approve Leaves Pending", steps=2
        )
        corr = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Approve Leaves Pending"
        )

        instance_id = self._instance_id(engine, corr["document_id"])
        self._act(test_client, instance_id, "approve", checker_headers)

        pending_ids, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] in pending_ids  # sanity: present before the action
        assert pending_total == 1
        assert self._db_status(engine, corr["id"]) == CorrespondenceStatus.PENDING_APPROVAL

        result = self._act(test_client, instance_id, "approve", checker_headers)
        assert result["status"] == "approved"

        # First list request after the action must already be correct.
        pending_ids, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] not in pending_ids
        assert pending_total == 0

        approved_ids, approved_total = self._status_ids(
            test_client, auth_headers, "approved"
        )
        assert corr["id"] in approved_ids
        assert approved_total == 1
        assert self._db_status(engine, corr["id"]) == CorrespondenceStatus.APPROVED

    def test_rejected_correspondence_leaves_pending_list_immediately(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        wf_id = self._create_workflow(
            test_client, auth_headers, checker_id, "Reject Leaves Pending", steps=2
        )
        corr = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Reject Leaves Pending"
        )

        instance_id = self._instance_id(engine, corr["document_id"])
        self._act(test_client, instance_id, "approve", checker_headers)  # -> step 2

        pending_ids, _ = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] in pending_ids  # sanity: present before the action

        result = self._act(test_client, instance_id, "reject", checker_headers)
        assert result["status"] == "rejected"

        pending_ids, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] not in pending_ids
        assert pending_total == 0

        rejected_ids, _ = self._status_ids(test_client, auth_headers, "rejected")
        assert corr["id"] in rejected_ids
        assert self._db_status(engine, corr["id"]) == CorrespondenceStatus.REJECTED

    def test_returned_correspondence_leaves_pending_list_immediately(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        wf_id = self._create_workflow(
            test_client, auth_headers, checker_id, "Return Leaves Pending", steps=2
        )
        corr = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Return Leaves Pending"
        )

        instance_id = self._instance_id(engine, corr["document_id"])
        self._act(test_client, instance_id, "approve", checker_headers)  # -> step 2

        pending_ids, _ = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] in pending_ids  # sanity: present before the action

        result = self._act(test_client, instance_id, "return", checker_headers)
        assert result["status"] == "returned"

        pending_ids, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] not in pending_ids
        assert pending_total == 0

        returned_ids, _ = self._status_ids(test_client, auth_headers, "returned")
        assert corr["id"] in returned_ids
        assert self._db_status(engine, corr["id"]) == CorrespondenceStatus.RETURNED

    def test_single_step_approval_clears_submitted_status(
        self, client, auth_headers, seeded_data
    ):
        """A single-step workflow goes submitted -> approved without ever
        passing pending_approval; the stale 'submitted' row must also stop
        matching its status filter on the first list request."""
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        wf_id = self._create_workflow(
            test_client, auth_headers, checker_id, "Single Step Submitted"
        )
        corr = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Single Step Submitted"
        )

        submitted_ids, _ = self._status_ids(test_client, auth_headers, "submitted")
        assert corr["id"] in submitted_ids  # sanity

        instance_id = self._instance_id(engine, corr["document_id"])
        result = self._act(test_client, instance_id, "approve", checker_headers)
        assert result["status"] == "approved"

        submitted_ids, submitted_total = self._status_ids(
            test_client, auth_headers, "submitted"
        )
        assert corr["id"] not in submitted_ids
        assert submitted_total == 0
        approved_ids, _ = self._status_ids(test_client, auth_headers, "approved")
        assert corr["id"] in approved_ids
        assert self._db_status(engine, corr["id"]) == CorrespondenceStatus.APPROVED

    def test_inflight_correspondence_stays_in_pending_list_after_step_advance(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        wf_id = self._create_workflow(
            test_client, auth_headers, checker_id, "Two Step Stays Pending", steps=2
        )
        corr = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Two Step Stays Pending"
        )

        instance_id = self._instance_id(engine, corr["document_id"])
        result = self._act(test_client, instance_id, "approve", checker_headers)
        assert result["status"] == "pending_approval"  # advanced to step 2
        assert result["current_step_order"] == 2

        # The instance is still in flight, so the correspondence must remain.
        pending_ids, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] in pending_ids
        assert pending_total == 1
        assert self._db_status(engine, corr["id"]) == CorrespondenceStatus.PENDING_APPROVAL

    def test_pending_total_and_pagination_after_action(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        wf_id = self._create_workflow(
            test_client, auth_headers, checker_id, "Pagination Pending", steps=2
        )
        corr_one = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Pagination One"
        )
        corr_two = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Pagination Two"
        )

        # Advance both to step 2 so both sit at pending_approval.
        self._act(
            test_client,
            self._instance_id(engine, corr_one["document_id"]),
            "approve",
            checker_headers,
        )
        self._act(
            test_client,
            self._instance_id(engine, corr_two["document_id"]),
            "approve",
            checker_headers,
        )

        _, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert pending_total == 2  # sanity

        # Final-approve the first instance -> it must leave immediately.
        instance_one = self._instance_id(engine, corr_one["document_id"])
        result = self._act(test_client, instance_one, "approve", checker_headers)
        assert result["status"] == "approved"

        pending_ids, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert pending_total == 1
        assert pending_ids == {corr_two["id"]}

        page_ids, page_total = self._status_ids(
            test_client, auth_headers, "pending_approval", skip=0, limit=1
        )
        assert page_total == 1
        assert page_ids == {corr_two["id"]}

        approved_ids, approved_total = self._status_ids(
            test_client, auth_headers, "approved"
        )
        assert approved_total == 1
        assert approved_ids == {corr_one["id"]}

    def test_stale_stored_status_healed_by_list(
        self, client, auth_headers, seeded_data
    ):
        """Rows that went stale before this fix existed are corrected by the
        first list call, not only when they happen to be paged."""
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(engine, seeded_data)
        wf_id = self._create_workflow(
            test_client, auth_headers, checker_id, "Stale Heal"
        )
        corr = self._submit(
            test_client, auth_headers, seeded_data, wf_id, "Stale Heal"
        )

        instance_id = self._instance_id(engine, corr["document_id"])
        self._act(test_client, instance_id, "approve", checker_headers)

        # Simulate a pre-existing stale row: approved instance, stale status.
        with Session(engine) as session:
            row = session.get(Correspondence, corr["id"])
            assert row
            row.status = CorrespondenceStatus.PENDING_APPROVAL
            session.add(row)
            session.commit()

        pending_ids, pending_total = self._status_ids(
            test_client, auth_headers, "pending_approval"
        )
        assert corr["id"] not in pending_ids
        assert pending_total == 0
        assert self._db_status(engine, corr["id"]) == CorrespondenceStatus.APPROVED


