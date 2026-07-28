"""
tests/test_document_visibility.py
─────────────────────────────────
Tests for user-level-based document visibility (Feature 2).
"""

import io
import json

import pytest
from sqlmodel import Session

from core.security import create_access_token, hash_password
from documents.models import DocumentUserLevelLink
from users.models import (
    Permission,
    PermissionAction,
    Role,
    RoleName,
    RolePermissionLink,
    User,
    UserCategoryLink,
    UserRoleLink,
)
from user_levels.models import UserLevel


@pytest.fixture()
def seeded_visibility_data(client, seeded_data):
    """Extend seeded data with additional users and documents for visibility tests."""
    _, engine, _ = client

    with Session(engine) as session:
        high_level = session.get(UserLevel, seeded_data["high_level_id"])
        medium_level = session.get(UserLevel, seeded_data["medium_level_id"])
        low_level = session.get(UserLevel, seeded_data["low_level_id"])

        maker_role = session.exec(
            __import__("sqlmodel", fromlist=["select"]).select(Role).where(Role.name == RoleName.MAKER)
        ).first()

        checker_role = Role(name=RoleName.CHECKER, description="Checker")
        session.add(checker_role)
        session.flush()
        for action in (PermissionAction.VIEW, PermissionAction.DOWNLOAD):
            perm = session.exec(
                __import__("sqlmodel", fromlist=["select"]).select(Permission).where(Permission.action == action)
            ).first()
            session.add(RolePermissionLink(role_id=checker_role.id, permission_id=perm.id))

        maker_high = User(
            full_name="Maker High",
            email="maker_high@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            user_level_id=high_level.id,
        )
        maker_medium = User(
            full_name="Maker Medium",
            email="maker_medium@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            user_level_id=medium_level.id,
        )
        maker_low = User(
            full_name="Maker Low",
            email="maker_low@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            user_level_id=low_level.id,
        )
        checker_high = User(
            full_name="Checker High",
            email="checker_high@example.com",
            hashed_password=hash_password("Checker@1234"),
            is_active=True,
            user_level_id=high_level.id,
        )
        checker_medium = User(
            full_name="Checker Medium",
            email="checker_medium@example.com",
            hashed_password=hash_password("Checker@1234"),
            is_active=True,
            user_level_id=medium_level.id,
        )
        checker_low = User(
            full_name="Checker Low",
            email="checker_low@example.com",
            hashed_password=hash_password("Checker@1234"),
            is_active=True,
            user_level_id=low_level.id,
        )
        session.add_all([maker_high, maker_medium, maker_low, checker_high, checker_medium, checker_low])
        session.flush()

        session.add(UserRoleLink(user_id=maker_high.id, role_id=maker_role.id))
        session.add(UserRoleLink(user_id=maker_medium.id, role_id=maker_role.id))
        session.add(UserRoleLink(user_id=maker_low.id, role_id=maker_role.id))
        session.add(UserRoleLink(user_id=checker_high.id, role_id=checker_role.id))
        session.add(UserRoleLink(user_id=checker_medium.id, role_id=checker_role.id))
        session.add(UserRoleLink(user_id=checker_low.id, role_id=checker_role.id))

        finance_id = seeded_data["finance_category_id"]
        hr_id = seeded_data["hr_category_id"]
        for u in [maker_high, maker_medium, maker_low, checker_high, checker_medium, checker_low]:
            session.add(UserCategoryLink(user_id=u.id, category_id=finance_id))
            session.add(UserCategoryLink(user_id=u.id, category_id=hr_id))

        session.commit()

        return {
            **seeded_data,
            "maker_high_id": maker_high.id,
            "maker_medium_id": maker_medium.id,
            "maker_low_id": maker_low.id,
            "checker_high_id": checker_high.id,
            "checker_medium_id": checker_medium.id,
            "checker_low_id": checker_low.id,
        }


@pytest.fixture()
def visibility_auth_headers(seeded_visibility_data):
    return {
        "admin": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['admin_id'])}"},
        "maker": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['maker_id'])}"},
        "maker_high": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['maker_high_id'])}"},
        "maker_medium": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['maker_medium_id'])}"},
        "maker_low": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['maker_low_id'])}"},
        "checker_high": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['checker_high_id'])}"},
        "checker_medium": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['checker_medium_id'])}"},
        "checker_low": {"Authorization": f"Bearer {create_access_token(seeded_visibility_data['checker_low_id'])}"},
    }


def _upload_doc(test_client, headers, directory_id, title, user_level_ids, file_content=b"test content"):
    """Helper to upload a document with user level IDs."""
    return test_client.post(
        "/api/v1/documents/upload",
        headers=headers,
        data={
            "title": title,
            "directory_id": str(directory_id),
            "user_level_ids": json.dumps(user_level_ids),
        },
        files={"file": (f"{title}.pdf", io.BytesIO(file_content), "application/pdf")},
    )


class TestUploadUserLevels:
    """Tests 1-4: Upload behaviour with user levels."""

    def test_maker_can_upload_document(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 1: Maker can upload documents with user level selection."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker"],
            data["finance_directory_id"],
            "Test Upload",
            [data["high_level_id"], data["medium_level_id"]],
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == "Test Upload"
        assert sorted(body["user_level_ids"]) == sorted([data["high_level_id"], data["medium_level_id"]])

    def test_upload_fails_without_user_levels(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 2: Upload fails if no user level is selected."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker"],
            data["finance_directory_id"],
            "No Levels",
            [],
        )
        assert resp.status_code == 422

    def test_upload_succeeds_with_one_user_level(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 3: Upload succeeds with exactly one user level."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker"],
            data["finance_directory_id"],
            "One Level",
            [data["low_level_id"]],
        )
        assert resp.status_code == 201
        assert resp.json()["user_level_ids"] == [data["low_level_id"]]

    def test_upload_succeeds_with_multiple_user_levels(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 4: Upload succeeds with multiple user levels."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker"],
            data["finance_directory_id"],
            "Multi Level",
            [data["high_level_id"], data["medium_level_id"], data["low_level_id"]],
        )
        assert resp.status_code == 201
        assert sorted(resp.json()["user_level_ids"]) == sorted([
            data["high_level_id"], data["medium_level_id"], data["low_level_id"]
        ])


class TestDocumentVisibility:
    """Tests 5-9: Document visibility based on user levels."""

    def test_high_level_user_can_access_high_documents(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 5: High-level users can view documents shared with High."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = test_client.get(
            f"/api/v1/documents/{data['finance_document_id']}",
            headers=visibility_auth_headers["checker_high"],
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == data["finance_document_id"]

    def test_medium_level_user_can_access_medium_documents(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 6: Medium-level users can view documents shared with Medium."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = test_client.get(
            f"/api/v1/documents/{data['finance_document_id']}",
            headers=visibility_auth_headers["checker_medium"],
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == data["finance_document_id"]

    def test_user_cannot_access_document_outside_their_level(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 7: Users cannot access documents outside their permitted user levels."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = test_client.get(
            f"/api/v1/documents/{data['hr_document_id']}",
            headers=visibility_auth_headers["checker_low"],
        )
        assert resp.status_code == 403

    def test_multi_level_document_visible_to_all_selected_levels(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 8: Documents shared with multiple levels are visible to all selected levels."""
        test_client, _, _ = client
        data = seeded_visibility_data
        for role in ["checker_high", "checker_medium"]:
            resp = test_client.get(
                f"/api/v1/documents/{data['finance_document_id']}",
                headers=visibility_auth_headers[role],
            )
            assert resp.status_code == 200, f"{role} should see finance_doc"

        resp = test_client.get(
            f"/api/v1/documents/{data['finance_document_id']}",
            headers=visibility_auth_headers["checker_low"],
        )
        assert resp.status_code == 403

    def test_admin_can_access_every_document(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 9: Administrators can access every document regardless of user level."""
        test_client, _, _ = client
        data = seeded_visibility_data
        for doc_id in [data["finance_document_id"], data["hr_document_id"]]:
            resp = test_client.get(
                f"/api/v1/documents/{doc_id}",
                headers=visibility_auth_headers["admin"],
            )
            assert resp.status_code == 200, f"Admin should see document {doc_id}"


class TestSearchAndDownloadVisibility:
    """Tests 10-12: Search, download, and preview respect visibility."""

    def test_search_respects_visibility(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 10: Search results only include documents the user can access."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = test_client.get(
            "/api/v1/documents",
            headers=visibility_auth_headers["checker_low"],
            params={"search": "Finance Report"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        visible_ids = [item["id"] for item in items]
        assert data["finance_document_id"] not in visible_ids

        resp = test_client.get(
            "/api/v1/documents",
            headers=visibility_auth_headers["checker_high"],
            params={"search": "Finance Report"},
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        visible_ids = [item["id"] for item in items]
        assert data["finance_document_id"] in visible_ids

    def test_download_respects_visibility(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 11: Download requires user level access."""
        test_client, _, _ = client
        data = seeded_visibility_data

        # Upload a real file (High only) via maker_high
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker_high"],
            data["hr_directory_id"],
            "Download Test",
            [data["high_level_id"]],
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        # Low user cannot download
        resp = test_client.get(
            f"/api/v1/documents/{doc_id}/download",
            headers=visibility_auth_headers["checker_low"],
        )
        assert resp.status_code == 403

        # High user can download
        resp = test_client.get(
            f"/api/v1/documents/{doc_id}/download",
            headers=visibility_auth_headers["checker_high"],
        )
        assert resp.status_code == 200

    def test_preview_respects_visibility(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 12: Preview requires user level access."""
        test_client, _, _ = client
        data = seeded_visibility_data

        # Upload a real file (High only) via maker_high
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker_high"],
            data["hr_directory_id"],
            "Preview Test",
            [data["high_level_id"]],
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        # Low user cannot preview
        resp = test_client.get(
            f"/api/v1/documents/{doc_id}/view",
            headers=visibility_auth_headers["checker_low"],
        )
        assert resp.status_code == 403

        # High user can preview
        resp = test_client.get(
            f"/api/v1/documents/{doc_id}/view",
            headers=visibility_auth_headers["checker_high"],
        )
        assert resp.status_code == 200


class TestExistingRBAC:
    """Tests 13-14: Existing RBAC and document functionality remain intact."""

    def test_existing_rbac_permissions_work(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 13: Existing RBAC permissions continue to function correctly."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker"],
            data["finance_directory_id"],
            "RBAC Test",
            [data["high_level_id"]],
        )
        assert resp.status_code == 201

        resp = _upload_doc(
            test_client,
            visibility_auth_headers["checker_high"],
            data["finance_directory_id"],
            "RBAC Fail",
            [data["high_level_id"]],
        )
        assert resp.status_code == 403

    def test_existing_upload_management_unaffected(self, client, seeded_visibility_data, visibility_auth_headers):
        """Test 14: Existing document upload and management functionality remains unaffected."""
        test_client, _, _ = client
        data = seeded_visibility_data
        resp = _upload_doc(
            test_client,
            visibility_auth_headers["maker"],
            data["finance_directory_id"],
            "Management Test",
            [data["high_level_id"], data["medium_level_id"]],
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        resp = test_client.patch(
            f"/api/v1/documents/{doc_id}",
            headers=visibility_auth_headers["maker"],
            json={"title": "Updated Title"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"

        resp = test_client.post(
            f"/api/v1/documents/{doc_id}/archive",
            headers=visibility_auth_headers["maker"],
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

        resp = test_client.post(
            f"/api/v1/documents/{doc_id}/restore",
            headers=visibility_auth_headers["admin"],
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

        # Delete requires DELETE permission (admin only per seeded RBAC)
        resp = test_client.delete(
            f"/api/v1/documents/{doc_id}",
            headers=visibility_auth_headers["admin"],
        )
        assert resp.status_code == 204
