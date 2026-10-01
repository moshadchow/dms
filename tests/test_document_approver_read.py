"""Approver read-grant for documents/ read paths (detail, view, download).

Eligible current-step approvers may read an in-flight document past the
User Level guard — mirroring memos ``_is_eligible_approver`` and
correspondence ``_check_view_access(approver_view=True)``. The reported bug
was a 403 on ``GET /documents/{id}/download`` for a checker who was an
eligible approver of the memo whose *attachment* the document is: the
workflow instance lives on the memo's backing document, so the grant must
traverse ``memo_attachments`` / ``correspondence_attachments``.

Non-approvers, pre-submission, workspace/variants, and expired instances
keep the strict level guard (``You do not have access to this document``).
"""

import json

from sqlmodel import Session, select

from core.security import create_access_token, hash_password
from users.models import Role, RoleName, User, UserCategoryLink, UserRoleLink

LEVEL_DETAIL = "You do not have access to this document"


def _make_checker(engine, seeded_data, email):
    """High-level CHECKER in the test company with finance category access.

    High level vs the Medium-only document under test mirrors the reported
    bug. CHECKER role (not MAKER): approval_service.act refuses MAKER users.
    Role rows come from the seeded roles — never create Role objects here.
    """
    with Session(engine) as session:
        role = session.exec(select(Role).where(Role.name == RoleName.CHECKER)).first()
        assert role, "seeded CHECKER role missing"
        user = User(
            full_name=email.split("@")[0].replace(".", " ").title(),
            email=email,
            hashed_password=hash_password("Test@1234"),
            is_active=True,
            user_level_id=seeded_data["high_level_id"],
            company_id=seeded_data["company_id"],
        )
        session.add(user)
        session.flush()
        session.add(UserRoleLink(user_id=user.id, role_id=role.id))
        session.add(
            UserCategoryLink(user_id=user.id, category_id=seeded_data["finance_category_id"])
        )
        session.commit()
        user_id = user.id
    return user_id, {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _upload_medium_doc(test_client, auth_headers, seeded_data):
    """A document linked only to the Medium level (High users are denied)."""
    resp = test_client.post(
        "/api/v1/documents/upload",
        files={"file": ("secret.pdf", b"%PDF-1.4 secret", "application/pdf")},
        data={
            "title": "Medium Only Doc",
            "directory_id": str(seeded_data["finance_directory_id"]),
            "user_level_ids": json.dumps([seeded_data["medium_level_id"]]),
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _create_workflow(test_client, auth_headers, name, approver_ids):
    resp = test_client.post(
        "/api/v1/workflows",
        json={
            "name": name,
            "description": "Approver read-grant test",
            "steps": [{
                "step_order": 1,
                "step_name": "Review",
                "approval_mode": "sequential",
                "approvers": [{"user_id": uid} for uid in approver_ids],
            }],
        },
        headers=auth_headers["admin"],
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _seed_submitted_memo(
    test_client, auth_headers, seeded_data, wf_id, attachment_doc_id, name
):
    """Maker creates a memo carrying ``attachment_doc_id`` and submits it.

    The workflow instance lands on the memo's backing document — the
    attachment itself never gets an instance (the traversal under test).
    """
    memo_resp = test_client.post(
        "/api/v1/memos",
        json={
            "directory_id": seeded_data["finance_directory_id"],
            "user_level_ids": [seeded_data["medium_level_id"]],
            "subject": name,
            "body": "# Memo\n\nAttachment under review.",
            "attachment_document_ids": [attachment_doc_id],
        },
        headers=auth_headers["maker"],
    )
    assert memo_resp.status_code == 201, memo_resp.text
    memo = memo_resp.json()
    assert memo["attachments"], memo

    sub = test_client.post(
        f"/api/v1/memos/{memo['id']}/submit",
        json={"workflow_definition_id": wf_id},
        headers=auth_headers["maker"],
    )
    assert sub.status_code == 200, sub.text

    inst = test_client.get(
        f"/api/v1/workflow-instances/by-document/{memo['document_id']}",
        headers=auth_headers["admin"],
    )
    assert inst.status_code == 200, inst.text
    return {
        "memo_id": memo["id"],
        "memo_document_id": memo["document_id"],
        "instance_id": inst.json()["id"],
    }


class TestApproverReadGrant:
    def test_approver_reads_and_downloads_memo_attachment(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = _make_checker(
            engine, seeded_data, "approver.read@example.com"
        )
        doc_id = _upload_medium_doc(test_client, auth_headers, seeded_data)

        # Designated approver, but no in-flight instance yet -> strict guard.
        before = test_client.get(f"/api/v1/documents/{doc_id}", headers=checker_headers)
        assert before.status_code == 403
        assert before.json()["detail"] == LEVEL_DETAIL

        wf_id = _create_workflow(test_client, auth_headers, "Att Read WF", [checker_id])
        seeded = _seed_submitted_memo(
            test_client, auth_headers, seeded_data, wf_id, doc_id, "Approver Read"
        )

        detail = test_client.get(f"/api/v1/documents/{doc_id}", headers=checker_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == doc_id

        download = test_client.get(
            f"/api/v1/documents/{doc_id}/download", headers=checker_headers
        )
        assert download.status_code == 200, download.text
        assert download.content.startswith(b"%PDF")

        # The memo's backing document carries the instance itself (direct
        # branch of the grant), even though its level links exclude High.
        backing = test_client.get(
            f"/api/v1/documents/{seeded['memo_document_id']}", headers=checker_headers
        )
        assert backing.status_code == 200, backing.text

    def test_non_approver_still_denied_on_attachment(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        approver_id, _ = _make_checker(engine, seeded_data, "approver.only@example.com")
        other_id, other_headers = _make_checker(
            engine, seeded_data, "non.approver@example.com"
        )
        doc_id = _upload_medium_doc(test_client, auth_headers, seeded_data)

        wf_id = _create_workflow(test_client, auth_headers, "Att Deny WF", [approver_id])
        seeded = _seed_submitted_memo(
            test_client, auth_headers, seeded_data, wf_id, doc_id, "Non Approver"
        )

        detail = test_client.get(f"/api/v1/documents/{doc_id}", headers=other_headers)
        assert detail.status_code == 403
        assert detail.json()["detail"] == LEVEL_DETAIL

        download = test_client.get(
            f"/api/v1/documents/{doc_id}/download", headers=other_headers
        )
        assert download.status_code == 403
        assert download.json()["detail"] == LEVEL_DETAIL

        backing = test_client.get(
            f"/api/v1/documents/{seeded['memo_document_id']}", headers=other_headers
        )
        assert backing.status_code == 403

    def test_grant_does_not_cover_workspace(
        self, client, auth_headers, seeded_data
    ):
        """The grant is limited to detail/view/download — workspace
        (and variants) keep the strict User Level guard."""
        test_client, engine, _ = client
        checker_id, checker_headers = _make_checker(
            engine, seeded_data, "approver.workspace@example.com"
        )
        doc_id = _upload_medium_doc(test_client, auth_headers, seeded_data)
        wf_id = _create_workflow(test_client, auth_headers, "Att WS WF", [checker_id])
        _seed_submitted_memo(
            test_client, auth_headers, seeded_data, wf_id, doc_id, "Approver Workspace"
        )

        assert test_client.get(
            f"/api/v1/documents/{doc_id}", headers=checker_headers
        ).status_code == 200

        workspace = test_client.get(
            f"/api/v1/documents/{doc_id}/workspace", headers=checker_headers
        )
        assert workspace.status_code == 403
        assert workspace.json()["detail"] == LEVEL_DETAIL

    def test_grant_expires_when_instance_completes(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = _make_checker(
            engine, seeded_data, "approver.expire@example.com"
        )
        doc_id = _upload_medium_doc(test_client, auth_headers, seeded_data)
        wf_id = _create_workflow(test_client, auth_headers, "Att Expire WF", [checker_id])
        seeded = _seed_submitted_memo(
            test_client, auth_headers, seeded_data, wf_id, doc_id, "Grant Expires"
        )

        assert test_client.get(
            f"/api/v1/documents/{doc_id}", headers=checker_headers
        ).status_code == 200

        act = test_client.post(
            f"/api/v1/workflow-instances/{seeded['instance_id']}/actions",
            json={"action": "approve", "remarks": "ok"},
            headers=checker_headers,
        )
        assert act.status_code == 200, act.text
        assert act.json()["status"] == "approved"

        detail = test_client.get(f"/api/v1/documents/{doc_id}", headers=checker_headers)
        assert detail.status_code == 403
        assert detail.json()["detail"] == LEVEL_DETAIL

        download = test_client.get(
            f"/api/v1/documents/{doc_id}/download", headers=checker_headers
        )
        assert download.status_code == 403

    def test_correspondence_attachment_branch(
        self, client, auth_headers, seeded_data
    ):
        """Same grant for a document attached to a correspondence whose
        backing document carries the in-flight instance."""
        from correspondence.models import AttachmentType, CorrespondenceAttachment

        test_client, engine, _ = client
        checker_id, checker_headers = _make_checker(
            engine, seeded_data, "approver.corr@example.com"
        )
        doc_id = _upload_medium_doc(test_client, auth_headers, seeded_data)

        corr_resp = test_client.post(
            "/api/v1/correspondences",
            json={
                "directory_id": seeded_data["finance_directory_id"],
                "category_id": seeded_data["finance_category_id"],
                "user_level_ids": [seeded_data["medium_level_id"]],
                "subject": "Attachment Grant",
                "body": "<p>Body</p>",
                "direction": "outbound",
                "priority": "normal",
            },
            headers=auth_headers["admin"],
        )
        assert corr_resp.status_code == 201, corr_resp.text
        corr = corr_resp.json()

        # The API only creates attachments from uploaded files; link the
        # Medium-only document directly to exercise the traversal.
        with Session(engine) as session:
            session.add(
                CorrespondenceAttachment(
                    correspondence_id=corr["id"],
                    document_id=doc_id,
                    attachment_type=AttachmentType.SUPPORTING,
                    created_by=seeded_data["admin_id"],
                )
            )
            session.commit()

        wf_id = _create_workflow(test_client, auth_headers, "Corr Att WF", [checker_id])
        sub = test_client.post(
            f"/api/v1/correspondences/{corr['id']}/submit",
            json={"workflow_definition_id": wf_id},
            headers=auth_headers["admin"],
        )
        assert sub.status_code == 200, sub.text
        assert sub.json()["document_id"] is not None

        detail = test_client.get(f"/api/v1/documents/{doc_id}", headers=checker_headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["id"] == doc_id

        download = test_client.get(
            f"/api/v1/documents/{doc_id}/download", headers=checker_headers
        )
        assert download.status_code == 200, download.text
        assert download.content.startswith(b"%PDF")
