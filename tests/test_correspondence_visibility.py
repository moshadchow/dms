"""List/detail visibility consistency for correspondence (WP8).

``list_correspondences`` filters must stay a subset of ``_check_view_access``:
anything hidden from the list must also be rejected on detail, and admin
bypasses must match on both paths.

``TestApproverViewGrant`` covers the approver read-grant: eligible
current-step approvers may read an in-flight document their User Level
doesn't cover (mirrors memos' ``_is_eligible_approver``), while
non-approvers and mutations keep the strict level guard.
"""

from sqlmodel import Session

from correspondence.models import Correspondence
from correspondence.schemas import CorrespondenceCreate
from correspondence.service import CorrespondenceService


def _payload(seeded_data, **overrides) -> dict:
    payload = {
        "directory_id": seeded_data["finance_directory_id"],
        "category_id": seeded_data["finance_category_id"],
        "user_level_ids": [seeded_data["medium_level_id"]],
        "subject": "Visibility Test",
        "body": "<p>Body</p>",
        "direction": "outbound",
        "priority": "normal",
    }
    payload.update(overrides)
    return payload


def _ids(resp_json) -> set:
    return {item["id"] for item in resp_json["items"]}


class TestCategoryVisibility:
    def test_list_hides_unassigned_category_and_detail_rejects(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        with Session(engine) as session:
            from users.models import User

            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            finance = svc.create_draft(
                CorrespondenceCreate(**_payload(seeded_data, subject="Finance visible")),
                admin,
            )
            hr = svc.create_draft(
                CorrespondenceCreate(
                    **_payload(
                        seeded_data,
                        subject="HR hidden",
                        category_id=seeded_data["hr_category_id"],
                    )
                ),
                admin,
            )

        # Admin bypass sees both
        admin_list = test_client.get("/api/v1/correspondences", headers=auth_headers["admin"])
        assert admin_list.status_code == 200
        admin_ids = _ids(admin_list.json())
        assert finance.id in admin_ids
        assert hr.id in admin_ids

        # Maker is linked to finance only: HR is absent from the list
        maker_list = test_client.get("/api/v1/correspondences", headers=auth_headers["maker"])
        assert maker_list.status_code == 200
        maker_ids = _ids(maker_list.json())
        assert finance.id in maker_ids
        assert hr.id not in maker_ids

        # Detail matches the list: visible stays visible, hidden 404s
        visible = test_client.get(
            f"/api/v1/correspondences/{finance.id}",
            headers=auth_headers["maker"],
        )
        assert visible.status_code == 200

        hidden = test_client.get(
            f"/api/v1/correspondences/{hr.id}",
            headers=auth_headers["maker"],
        )
        assert hidden.status_code == 404

    def test_list_and_detail_hide_document_above_user_level(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        with Session(engine) as session:
            from users.models import User

            admin = session.get(User, seeded_data["admin_id"])
            svc = CorrespondenceService(session)
            # Same (maker-accessible) category, but the document is only
            # linked to the High user level — maker is Medium.
            normal = svc.create_draft(
                CorrespondenceCreate(**_payload(seeded_data, subject="Medium visible")),
                admin,
            )
            elevated = svc.create_draft(
                CorrespondenceCreate(
                    **_payload(
                        seeded_data,
                        subject="High only",
                        user_level_ids=[seeded_data["high_level_id"]],
                    )
                ),
                admin,
            )

        maker_list = test_client.get("/api/v1/correspondences", headers=auth_headers["maker"])
        assert maker_list.status_code == 200
        maker_ids = _ids(maker_list.json())
        assert normal.id in maker_ids
        assert elevated.id not in maker_ids

        visible = test_client.get(
            f"/api/v1/correspondences/{normal.id}",
            headers=auth_headers["maker"],
        )
        assert visible.status_code == 200

        hidden = test_client.get(
            f"/api/v1/correspondences/{elevated.id}",
            headers=auth_headers["maker"],
        )
        assert hidden.status_code == 403

        # Admin bypass sees both regardless of level
        admin_list = test_client.get("/api/v1/correspondences", headers=auth_headers["admin"])
        admin_ids = _ids(admin_list.json())
        assert normal.id in admin_ids
        assert elevated.id in admin_ids


class TestCrossCompanyVisibility:
    def test_superadmin_sees_all_companies_admin_scoped_to_own(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        with Session(engine) as session:
            from users.models import User

            admin = session.get(User, seeded_data["admin_id"])
            other_admin = session.get(User, seeded_data["other_admin_id"])
            svc = CorrespondenceService(session)
            own = svc.create_draft(
                CorrespondenceCreate(**_payload(seeded_data, subject="Test Company note")),
                admin,
            )
            other = svc.create_draft(
                CorrespondenceCreate(
                    **_payload(
                        seeded_data,
                        subject="Other Company note",
                        category_id=seeded_data["marketing_category_id"],
                    )
                ),
                other_admin,
            )

        superadmin_list = test_client.get("/api/v1/correspondences", headers=auth_headers["superadmin"])
        assert superadmin_list.status_code == 200
        superadmin_ids = _ids(superadmin_list.json())
        assert own.id in superadmin_ids
        assert other.id in superadmin_ids

        admin_list = test_client.get("/api/v1/correspondences", headers=auth_headers["admin"])
        assert admin_list.status_code == 200
        admin_ids = _ids(admin_list.json())
        assert own.id in admin_ids
        assert other.id not in admin_ids

        # Detail mirrors the list on both sides
        assert test_client.get(
            f"/api/v1/correspondences/{other.id}",
            headers=auth_headers["superadmin"],
        ).status_code == 200
        assert test_client.get(
            f"/api/v1/correspondences/{other.id}",
            headers=auth_headers["admin"],
        ).status_code == 404
        assert test_client.get(
            f"/api/v1/correspondences/{own.id}",
            headers=auth_headers["other_admin"],
        ).status_code == 404


class TestApproverViewGrant:
    """Eligible current-step approvers can read in-flight documents that their
    User Level does not cover; everyone else keeps the strict level guard."""

    def _make_user(
        self,
        engine,
        seeded_data,
        *,
        email,
        level_key,
        category_id=None,
        company_key="company_id",
        role_name=None,
    ):
        from core.security import create_access_token, hash_password
        from sqlmodel import select
        from users.models import Role, RoleName, User, UserCategoryLink, UserRoleLink

        role_name = role_name or RoleName.MAKER
        with Session(engine) as session:
            role = session.exec(select(Role).where(Role.name == role_name)).first()
            assert role, f"seeded {role_name} role missing"
            user = User(
                full_name=email.split("@")[0].replace(".", " ").title(),
                email=email,
                hashed_password=hash_password("Test@1234"),
                is_active=True,
                user_level_id=seeded_data[level_key],
                company_id=seeded_data[company_key],
            )
            session.add(user)
            session.flush()
            session.add(UserRoleLink(user_id=user.id, role_id=role.id))
            if category_id is not None:
                session.add(UserCategoryLink(user_id=user.id, category_id=category_id))
            session.commit()
            user_id = user.id
        headers = {"Authorization": f"Bearer {create_access_token(user_id)}"}
        return user_id, headers

    def _make_checker(self, engine, seeded_data, email):
        """A Medium-level CHECKER in the test company with finance access.

        CHECKER (not MAKER) matters: approval_service refuses act() for
        MAKER-role users, so only a checker can complete the workflow in the
        expiry test — mirroring the real 'Checker Review' approvers.
        """
        from users.models import RoleName

        return self._make_user(
            engine,
            seeded_data,
            email=email,
            level_key="medium_level_id",
            category_id=seeded_data["finance_category_id"],
            role_name=RoleName.CHECKER,
        )

    def _seed_submitted(self, test_client, auth_headers, seeded_data, approver_ids, name):
        """Admin creates a High-level-only draft and submits it to a one-step
        workflow whose approvers are ``approver_ids`` (mismatched levels)."""
        corr_resp = test_client.post(
            "/api/v1/correspondences",
            json=_payload(
                seeded_data,
                subject=name,
                user_level_ids=[seeded_data["high_level_id"]],
            ),
            headers=auth_headers["admin"],
        )
        assert corr_resp.status_code == 201, corr_resp.text
        corr = corr_resp.json()

        wf_resp = test_client.post(
            "/api/v1/workflows",
            json={
                "name": name,
                "description": "Approver view grant test",
                "steps": [{
                    "step_order": 1,
                    "step_name": "Review",
                    "approval_mode": "sequential",
                    "approvers": [{"user_id": uid} for uid in approver_ids],
                }],
            },
            headers=auth_headers["admin"],
        )
        assert wf_resp.status_code == 201, wf_resp.text

        sub = test_client.post(
            f"/api/v1/correspondences/{corr['id']}/submit",
            json={"workflow_definition_id": wf_resp.json()["id"]},
            headers=auth_headers["admin"],
        )
        assert sub.status_code == 200, sub.text
        assert sub.json()["status"] in ("submitted", "pending_approval")
        assert corr["document_id"] is not None
        return corr

    def test_eligible_approver_can_read_document_above_their_level(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(
            engine, seeded_data, "approver.read@example.com"
        )
        corr = self._seed_submitted(
            test_client, auth_headers, seeded_data, [checker_id], "Approver Read"
        )
        doc_id = corr["document_id"]

        detail = test_client.get(
            f"/api/v1/correspondences/{corr['id']}", headers=checker_headers
        )
        assert detail.status_code == 200

        by_doc = test_client.get(
            f"/api/v1/correspondences/by-document/{doc_id}", headers=checker_headers
        )
        assert by_doc.status_code == 200, by_doc.text
        assert by_doc.json()["id"] == corr["id"]

        movements = test_client.get(
            f"/api/v1/correspondences/{corr['id']}/movements", headers=checker_headers
        )
        assert movements.status_code == 200

        download = test_client.get(
            f"/api/v1/correspondences/{corr['id']}/download", headers=checker_headers
        )
        assert download.status_code == 200

        # The list filter is intentionally unchanged: the High-only document
        # stays hidden from the approver's list even though detail now opens
        # (list ⊆ detail-accessible still holds).
        listing = test_client.get("/api/v1/correspondences", headers=checker_headers)
        assert listing.status_code == 200
        assert corr["id"] not in {item["id"] for item in listing.json()["items"]}

    def test_non_approver_same_level_still_403(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        checker_id, _ = self._make_checker(engine, seeded_data, "approver.only@example.com")
        corr = self._seed_submitted(
            test_client, auth_headers, seeded_data, [checker_id], "Non Approver"
        )
        # maker: same Medium level and finance category access, but is NOT an
        # approver on this workflow -> the grant must not apply.
        by_doc = test_client.get(
            f"/api/v1/correspondences/by-document/{corr['document_id']}",
            headers=auth_headers["maker"],
        )
        assert by_doc.status_code == 403
        assert by_doc.json()["detail"] == "You do not have access to this document"

        detail = test_client.get(
            f"/api/v1/correspondences/{corr['id']}", headers=auth_headers["maker"]
        )
        assert detail.status_code == 403

    def test_approver_grant_does_not_unlock_mutations(
        self, client, auth_headers, seeded_data
    ):
        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(
            engine, seeded_data, "approver.mutate@example.com"
        )
        corr = self._seed_submitted(
            test_client, auth_headers, seeded_data, [checker_id], "Approver Mutate"
        )

        # Read side of the grant works...
        assert test_client.get(
            f"/api/v1/correspondences/{corr['id']}", headers=checker_headers
        ).status_code == 200

        # ...but mutations keep the strict User Level guard (checker even has
        # the UPDATE permission, so the RBAC dependency passes).
        patched = test_client.patch(
            f"/api/v1/correspondences/{corr['id']}",
            json={"subject": "Approver should not edit this"},
            headers=checker_headers,
        )
        assert patched.status_code == 403

        responded = test_client.post(
            f"/api/v1/correspondences/{corr['id']}/mark-responded",
            headers=checker_headers,
        )
        assert responded.status_code == 403

    def test_grant_expires_when_instance_completes(
        self, client, auth_headers, seeded_data
    ):
        from sqlmodel import select
        from workflow.models import WorkflowInstance

        test_client, engine, _ = client
        checker_id, checker_headers = self._make_checker(
            engine, seeded_data, "approver.expire@example.com"
        )
        corr = self._seed_submitted(
            test_client, auth_headers, seeded_data, [checker_id], "Grant Expires"
        )

        with Session(engine) as session:
            instance = session.exec(
                select(WorkflowInstance).where(
                    WorkflowInstance.document_id == corr["document_id"]
                )
            ).first()
            assert instance
            instance_id = instance.id

        act = test_client.post(
            f"/api/v1/workflow-instances/{instance_id}/actions",
            json={"action": "approve", "remarks": "ok"},
            headers=checker_headers,
        )
        assert act.status_code == 200, act.text
        assert act.json()["status"] == "approved"

        # Instance is no longer in flight -> the read grant lapses and the
        # strict User Level guard applies again.
        by_doc = test_client.get(
            f"/api/v1/correspondences/by-document/{corr['document_id']}",
            headers=checker_headers,
        )
        assert by_doc.status_code == 403
        assert test_client.get(
            f"/api/v1/correspondences/{corr['id']}", headers=checker_headers
        ).status_code == 403

    def test_cross_company_approver_still_404(self, client, auth_headers, seeded_data):
        test_client, engine, _ = client
        cross_id, cross_headers = self._make_user(
            engine,
            seeded_data,
            email="cross.approver@example.com",
            level_key="medium_level_id",
            company_key="other_company_id",
        )
        corr = self._seed_submitted(
            test_client,
            auth_headers,
            seeded_data,
            [seeded_data["maker_id"], cross_id],
            "Cross Company Approver",
        )

        # Tenancy is checked before anything else: an approver from another
        # company gets 404, never the grant.
        by_doc = test_client.get(
            f"/api/v1/correspondences/by-document/{corr['document_id']}",
            headers=cross_headers,
        )
        assert by_doc.status_code == 404
        assert test_client.get(
            f"/api/v1/correspondences/{corr['id']}", headers=cross_headers
        ).status_code == 404
