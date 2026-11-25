"""Tests for document move operations."""

import io
import json

from sqlmodel import Session, select

from core.security import create_access_token
from users.models import Role, RoleName


def _headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _maker_role_id(engine) -> int:
    with Session(engine) as session:
        return session.exec(select(Role.id).where(Role.name == RoleName.MAKER)).first()


def _create_user(test_client, engine, admin_headers, email: str, level_id: int, company_id: int) -> tuple[int, dict]:
    response = test_client.post(
        "/api/v1/users",
        json={
            "full_name": email.split("@")[0],
            "email": email,
            "password": "Maker@1234",
            "role_ids": [_maker_role_id(engine)],
            "category_ids": [],
            "user_level_id": level_id,
            "company_id": company_id,
        },
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    user_id = response.json()["id"]
    return user_id, _headers(user_id)


def _create_dir(test_client, admin_headers, name: str, category_id: int, parent_id=None) -> int:
    payload = {"name": name, "category_id": category_id}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = test_client.post("/api/v1/directories", json=payload, headers=admin_headers)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_doc(test_client, admin_headers, title: str, directory_id: int, level_ids: list) -> int:
    response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": title,
            "description": "",
            "directory_id": str(directory_id),
            "user_level_ids": json.dumps(level_ids),
        },
        files={"file": (f"{title}.pdf", io.BytesIO(b"pdf content"), "application/pdf")},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _upload_docx(test_client, admin_headers, title: str, directory_id: int, level_ids: list) -> int:
    """Upload a DOCX document for testing private variants (avoids PDF processing)."""
    response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": title,
            "description": "",
            "directory_id": str(directory_id),
            "user_level_ids": json.dumps(level_ids),
        },
        files={"file": (f"{title}.docx", io.BytesIO(b"docx content"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _grant(test_client, admin_headers, user_id: int, directory_ids: list) -> None:
    response = test_client.put(
        f"/api/v1/users/{user_id}/directory-access",
        json={"directory_ids": directory_ids},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


def _create_private_variant(test_client, user_headers, document_id: int) -> int:
    """Create a private annotation variant for a document."""
    response = test_client.post(
        f"/api/v1/documents/{document_id}/variants",
        json={"annotations": []},
        headers=user_headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["variant"]["id"]


def test_move_document_same_category(client, seeded_data, auth_headers):
    """Move a document between directories in the same category."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    finance_dir = seeded_data["finance_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    # Create another directory in same category
    other_dir = _create_dir(test_client, admin, "Other Dir", finance_cat)

    # Upload document
    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])

    # Move to other directory
    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": other_dir},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["directory_id"] == other_dir
    assert data["title"] == "Test Doc"


def test_move_document_cross_category_same_company(client, seeded_data, auth_headers):
    """Move a document to a directory in a different category within the same company."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_dir = seeded_data["finance_directory_id"]
    hr_dir = seeded_data["hr_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    # Upload document in Finance
    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])

    # Move to HR directory
    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": hr_dir},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["directory_id"] == hr_dir

    # Verify document's effective category is now HR (via directory relationship)
    detail = test_client.get(f"/api/v1/documents/{doc_id}", headers=admin)
    assert detail.status_code == 200
    assert detail.json()["directory_id"] == hr_dir


def test_move_document_access_denied_no_source_access(client, seeded_data, auth_headers):
    """User without source document access cannot move it."""
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    finance_dir = seeded_data["finance_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    # Upload document as admin
    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])

    # Create user with NO grants
    _, user_headers = _create_user(test_client, engine, admin, "nomove@example.com", medium_level, seeded_data["company_id"])

    # Try to move without access
    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": finance_dir},
        headers=user_headers,
    )
    assert response.status_code == 404, response.text


def test_move_document_access_denied_no_dest_access(client, seeded_data, auth_headers):
    """User with source access but no destination access cannot move."""
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    finance_dir = seeded_data["finance_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    # Create another directory
    other_dir = _create_dir(test_client, admin, "Other Dir", finance_cat)

    # Upload document
    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])

    # Create user with access ONLY to finance_dir
    user_id, user_headers = _create_user(test_client, engine, admin, "partial@example.com", medium_level, seeded_data["company_id"])
    _grant(test_client, admin, user_id, [finance_dir])

    # Try to move to other_dir (no access)
    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": other_dir},
        headers=user_headers,
    )
    assert response.status_code == 404, response.text


def test_move_document_navigation_only_insufficient(client, seeded_data, auth_headers):
    """Navigation-only access (parent of granted dir) is insufficient for document move."""
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    medium_level = seeded_data["medium_level_id"]

    parent = _create_dir(test_client, admin, "Parent", finance_cat)
    child = _create_dir(test_client, admin, "Child", finance_cat, parent_id=parent)

    # Upload document in child
    doc_id = _upload_doc(test_client, admin, "Test Doc", child, [medium_level])

    # Grant user access to child only (parent becomes navigation-only)
    user_id, user_headers = _create_user(test_client, engine, admin, "navonly@example.com", medium_level, seeded_data["company_id"])
    _grant(test_client, admin, user_id, [child])

    # Try to move document from child to parent (navigation-only)
    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": parent},
        headers=user_headers,
    )
    assert response.status_code == 404, response.text


def test_move_document_superadmin_blocked(client, seeded_data, auth_headers):
    """SuperAdmin cannot mutate documents."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    superadmin = auth_headers["superadmin"]
    finance_dir = seeded_data["finance_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    # Create document as admin (superadmin cannot access categories)
    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])
    other_dir = _create_dir(test_client, admin, "Other", seeded_data["finance_category_id"])

    # Try to move as superadmin
    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": other_dir},
        headers=superadmin,
    )
    assert response.status_code == 403, response.text
    assert "Super Admin cannot modify" in response.json()["detail"]


def test_move_document_updates_updated_at(client, seeded_data, auth_headers):
    """Move operation should update the updated_at timestamp."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    finance_dir = seeded_data["finance_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    other_dir = _create_dir(test_client, admin, "Other Dir", finance_cat)
    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])

    before = test_client.get(f"/api/v1/documents/{doc_id}", headers=admin).json()["updated_at"]

    import time
    time.sleep(0.01)

    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": other_dir},
        headers=admin,
    )
    assert response.status_code == 200
    after = response.json()["updated_at"]
    assert after != before


def test_move_document_audit_logged(client, seeded_data, auth_headers):
    """Move operation should create MOVE_DOCUMENT audit event."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    finance_dir = seeded_data["finance_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    other_dir = _create_dir(test_client, admin, "Other Dir", finance_cat)
    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])

    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": other_dir},
        headers=admin,
    )
    assert response.status_code == 200

    # Check audit log
    audit = test_client.get(
        "/api/v1/audit-logs?action=move_document&entity_id=" + str(doc_id),
        headers=admin,
    )
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert len(items) >= 1
    assert items[0]["action"] == "move_document"
    assert items[0]["entity_id"] == str(doc_id)
    assert "directory_id" in items[0]["old_value"]
    assert "directory_id" in items[0]["new_value"]


def test_move_document_updates_private_variants(client, seeded_data, auth_headers):
    """Private variants should have their directory_id and category_id updated on document move."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    hr_cat = seeded_data["hr_category_id"]
    finance_dir = seeded_data["finance_directory_id"]
    hr_dir = seeded_data["hr_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    # Upload a DOCX document in Finance (non-PDF so variant creation doesn't need PDF processing)
    doc_id = _upload_docx(test_client, admin, "Test Doc", finance_dir, [medium_level])

    # Create private variant (as admin user)
    variant_id = _create_private_variant(test_client, admin, doc_id)

    # Verify variant has correct initial directory/category
    variant_detail = test_client.get(f"/api/v1/documents/variants/{variant_id}", headers=admin)
    assert variant_detail.status_code == 200
    assert variant_detail.json()["directory_id"] == finance_dir
    assert variant_detail.json()["category_id"] == finance_cat

    # Move document to HR
    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": hr_dir},
        headers=admin,
    )
    assert response.status_code == 200

    # Verify variant updated
    variant_detail = test_client.get(f"/api/v1/documents/variants/{variant_id}", headers=admin)
    assert variant_detail.status_code == 200
    assert variant_detail.json()["directory_id"] == hr_dir
    assert variant_detail.json()["category_id"] == hr_cat


def test_move_document_invalid_destination(client, seeded_data, auth_headers):
    """Moving to a non-existent directory should return 404."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_dir = seeded_data["finance_directory_id"]
    medium_level = seeded_data["medium_level_id"]

    doc_id = _upload_doc(test_client, admin, "Test Doc", finance_dir, [medium_level])

    response = test_client.patch(
        f"/api/v1/documents/{doc_id}/move",
        json={"new_directory_id": 999999},
        headers=admin,
    )
    assert response.status_code == 404, response.text