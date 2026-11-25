"""Tests for directory move operations."""


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


def _grant(test_client, admin_headers, user_id: int, directory_ids: list) -> None:
    response = test_client.put(
        f"/api/v1/users/{user_id}/directory-access",
        json={"directory_ids": directory_ids},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


def test_move_directory_same_category_subdir_to_root(client, seeded_data, auth_headers):
    """Move a subdirectory to root level within the same category."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]

    # Create parent and child
    parent = _create_dir(test_client, admin, "Parent Dir", finance_cat)
    child = _create_dir(test_client, admin, "Child Dir", finance_cat, parent_id=parent)

    # Move child to root
    response = test_client.patch(
        f"/api/v1/directories/{child}/move",
        json={"new_parent_id": None},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["parent_id"] is None
    assert data["category_id"] == finance_cat
    assert data["name"] == "Child Dir"


def test_move_directory_same_category_root_to_subdir(client, seeded_data, auth_headers):
    """Move a root directory under another directory."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]

    parent = _create_dir(test_client, admin, "New Parent", finance_cat)
    root_dir = _create_dir(test_client, admin, "Root Dir", finance_cat)

    response = test_client.patch(
        f"/api/v1/directories/{root_dir}/move",
        json={"new_parent_id": parent},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["parent_id"] == parent
    assert data["category_id"] == finance_cat


def test_move_directory_cross_category(client, seeded_data, auth_headers):
    """Move a directory (and its subtree) to a different category within the same company."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    hr_cat = seeded_data["hr_category_id"]

    # Create source directory with child
    source = _create_dir(test_client, admin, "Source Dir", finance_cat)
    child = _create_dir(test_client, admin, "Child Dir", finance_cat, parent_id=source)

    # Create destination parent in HR category
    dest_parent = _create_dir(test_client, admin, "HR Parent", hr_cat)

    # Move source under HR parent
    response = test_client.patch(
        f"/api/v1/directories/{source}/move",
        json={"new_parent_id": dest_parent},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["parent_id"] == dest_parent
    assert data["category_id"] == hr_cat

    # Verify child also moved category
    child_check = test_client.get(f"/api/v1/directories/{child}", headers=admin)
    assert child_check.status_code == 200
    assert child_check.json()["category_id"] == hr_cat
    assert child_check.json()["parent_id"] == source


def test_move_directory_cycle_prevention(client, seeded_data, auth_headers):
    """Moving a directory into its own subtree should be rejected."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]

    parent = _create_dir(test_client, admin, "Parent", finance_cat)
    child = _create_dir(test_client, admin, "Child", finance_cat, parent_id=parent)
    grandchild = _create_dir(test_client, admin, "Grandchild", finance_cat, parent_id=child)

    # Try to move parent into grandchild (cycle)
    response = test_client.patch(
        f"/api/v1/directories/{parent}/move",
        json={"new_parent_id": grandchild},
        headers=admin,
    )
    assert response.status_code == 400, response.text
    assert "subtree" in response.json()["detail"].lower()


def test_move_directory_sibling_name_conflict(client, seeded_data, auth_headers):
    """Moving a directory to a parent that already has a sibling with the same name should fail."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]

    parent = _create_dir(test_client, admin, "Parent", finance_cat)
    # Create a directory "Child" under parent
    _ = _create_dir(test_client, admin, "Child", finance_cat, parent_id=parent)

    # Create another directory "Child" under a different parent
    other_parent = _create_dir(test_client, admin, "Other Parent", finance_cat)
    source = _create_dir(test_client, admin, "Child", finance_cat, parent_id=other_parent)

    # Try to move source under parent where "Child" already exists
    response = test_client.patch(
        f"/api/v1/directories/{source}/move",
        json={"new_parent_id": parent},
        headers=admin,
    )
    assert response.status_code == 409, response.text
    assert "already exists" in response.json()["detail"]


def test_move_directory_access_denied_no_source_access(client, seeded_data, auth_headers):
    """User without source directory access cannot move it."""
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    medium_level = seeded_data["medium_level_id"]

    # Create directory as admin
    source = _create_dir(test_client, admin, "Source", finance_cat)

    # Create user with NO grants
    _, user_headers = _create_user(test_client, engine, admin, "nomove@example.com", medium_level, seeded_data["company_id"])

    # Try to move without access
    response = test_client.patch(
        f"/api/v1/directories/{source}/move",
        json={"new_parent_id": None},
        headers=user_headers,
    )
    assert response.status_code == 404, response.text


def test_move_directory_access_denied_no_dest_access(client, seeded_data, auth_headers):
    """User with source access but no destination access cannot move."""
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    medium_level = seeded_data["medium_level_id"]

    # Create source and dest
    source = _create_dir(test_client, admin, "Source", finance_cat)
    dest = _create_dir(test_client, admin, "Dest", finance_cat)

    # Create user with access ONLY to source
    user_id, user_headers = _create_user(test_client, engine, admin, "partial@example.com", medium_level, seeded_data["company_id"])
    _grant(test_client, admin, user_id, [source])

    # Try to move to dest (no access)
    response = test_client.patch(
        f"/api/v1/directories/{source}/move",
        json={"new_parent_id": dest},
        headers=user_headers,
    )
    assert response.status_code == 404, response.text


def test_move_directory_navigation_only_insufficient(client, seeded_data, auth_headers):
    """Navigation-only access (parent of granted dir) is insufficient for move."""
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    medium_level = seeded_data["medium_level_id"]

    parent = _create_dir(test_client, admin, "Parent", finance_cat)
    child = _create_dir(test_client, admin, "Child", finance_cat, parent_id=parent)

    # Grant access to child only (parent becomes navigation-only)
    user_id, user_headers = _create_user(test_client, engine, admin, "navonly@example.com", medium_level, seeded_data["company_id"])
    _grant(test_client, admin, user_id, [child])

    # Try to move parent (navigation-only)
    response = test_client.patch(
        f"/api/v1/directories/{parent}/move",
        json={"new_parent_id": None},
        headers=user_headers,
    )
    assert response.status_code == 404, response.text


def test_move_directory_superadmin_blocked(client, seeded_data, auth_headers):
    """SuperAdmin cannot mutate directories."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    superadmin = auth_headers["superadmin"]
    finance_cat = seeded_data["finance_category_id"]

    # Create directories as admin (superadmin cannot access categories)
    source = _create_dir(test_client, admin, "Source", finance_cat)
    dest = _create_dir(test_client, admin, "Dest", finance_cat)

    # Try to move as superadmin
    response = test_client.patch(
        f"/api/v1/directories/{source}/move",
        json={"new_parent_id": dest},
        headers=superadmin,
    )
    assert response.status_code == 403, response.text
    assert "Super Admin cannot modify" in response.json()["detail"]


def test_move_directory_updates_updated_at(client, seeded_data, auth_headers):
    """Move operation should update the updated_at timestamp."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]

    parent = _create_dir(test_client, admin, "Parent", finance_cat)
    child = _create_dir(test_client, admin, "Child", finance_cat, parent_id=parent)

    before = test_client.get(f"/api/v1/directories/{child}", headers=admin).json()["updated_at"]

    # Small delay to ensure timestamp changes
    import time
    time.sleep(0.01)

    response = test_client.patch(
        f"/api/v1/directories/{child}/move",
        json={"new_parent_id": None},
        headers=admin,
    )
    assert response.status_code == 200
    after = response.json()["updated_at"]
    assert after != before


def test_move_directory_audit_logged(client, seeded_data, auth_headers):
    """Move operation should create MOVE_DIRECTORY audit event."""
    test_client, _, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]

    parent = _create_dir(test_client, admin, "Parent", finance_cat)
    child = _create_dir(test_client, admin, "Child", finance_cat, parent_id=parent)

    response = test_client.patch(
        f"/api/v1/directories/{child}/move",
        json={"new_parent_id": None},
        headers=admin,
    )
    assert response.status_code == 200

    # Check audit log
    audit = test_client.get(
        "/api/v1/audit-logs?action=move_directory&entity_id=" + str(child),
        headers=admin,
    )
    assert audit.status_code == 200
    items = audit.json()["items"]
    assert len(items) >= 1
    assert items[0]["action"] == "move_directory"
    assert items[0]["entity_id"] == str(child)
    assert "parent_id" in items[0]["old_value"]
    assert "parent_id" in items[0]["new_value"]


def test_move_directory_grants_preserved(client, seeded_data, auth_headers):
    """Directory grants should remain valid after move."""
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    finance_cat = seeded_data["finance_category_id"]
    hr_cat = seeded_data["hr_category_id"]
    medium_level = seeded_data["medium_level_id"]

    # Create source with child
    source = _create_dir(test_client, admin, "Source", finance_cat)
    child = _create_dir(test_client, admin, "Child", finance_cat, parent_id=source)

    # Grant user access to source
    user_id, user_headers = _create_user(test_client, engine, admin, "grantuser@example.com", medium_level, seeded_data["company_id"])
    _grant(test_client, admin, user_id, [source])

    # Create dest in HR
    dest = _create_dir(test_client, admin, "HR Dest", hr_cat)

    # Move source under HR dest
    response = test_client.patch(
        f"/api/v1/directories/{source}/move",
        json={"new_parent_id": dest},
        headers=admin,
    )
    assert response.status_code == 200

    # User should still have access to source and child
    assert test_client.get(f"/api/v1/directories/{source}", headers=user_headers).status_code == 200
    assert test_client.get(f"/api/v1/directories/{child}", headers=user_headers).status_code == 200