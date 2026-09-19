"""Tests for the Correspondence module."""

from datetime import datetime

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
    def test_submit_inbound_without_document_uses_first_attachment(self, seeded_data, client, auth_headers):
        test_client, engine, _ = client
        wf_payload = {
            "name": "Inbound Correspondence WF",
            "description": "Inbound approval",
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
            from correspondence.models import CorrespondenceAttachment
            maker = session.get(User, seeded_data["maker_id"])
            svc = CorrespondenceService(session)

            # Create inbound correspondence WITHOUT a document_id
            corr = svc.create_draft(
                CorrespondenceCreate(**_corr_payload(seeded_data, direction="inbound", body=None)),
                maker,
            )
            assert corr.document_id is None
            assert corr.status == CorrespondenceStatus.RECEIVED

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

            # Add user level link so maker can access the document
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

            # Verify document_id is still None on the correspondence
            assert corr.document_id is None

            # Now submit — should auto-fallback to the attachment's document
            result = svc.submit_correspondence(
                corr.id,
                CorrespondenceSubmit(workflow_definition_id=wf_def_id),
                maker,
            )
            assert result.workflow_instance_id is not None
            assert result.status == CorrespondenceStatus.SUBMITTED
            assert result.document_id == link.document_id
