"""Subdirectory-level access control: grants, inheritance, enforcement, audit."""

import json

from sqlmodel import Session, select

from core.security import create_access_token
from users.models import Role, RoleName


def _headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _maker_role_id(engine) -> int:
    with Session(engine) as session:
        return session.exec(select(Role.id).where(Role.name == RoleName.MAKER)).first()


def _create_user(test_client, engine, admin_headers, email: str, level_id: int) -> tuple[int, dict]:
    response = test_client.post(
        "/api/v1/users",
        json={
            "full_name": email.split("@")[0],
            "email": email,
            "password": "Maker@1234",
            "role_ids": [_maker_role_id(engine)],
            "category_ids": [],
            "user_level_id": level_id,
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


def _upload(test_client, admin_headers, title: str, directory_id: int, level_ids: list) -> int:
    response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": title,
            "description": "",
            "directory_id": str(directory_id),
            "user_level_ids": json.dumps(level_ids),
        },
        files={"file": (f"{title}.pdf", b"pdf-bytes", "application/pdf")},
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _tree(client, seeded_data, auth_headers, medium_id: int):
    """Finance category with two sibling subtrees + a nested child; docs in each."""
    _, engine, _ = client
    fin = seeded_data["finance_category_id"]
    admin = auth_headers["admin"]
    sub_a = _create_dir(client[0], admin, "Sub A", fin)
    sub_b = _create_dir(client[0], admin, "Sub B", fin)
    child_a1 = _create_dir(client[0], admin, "Child A1", fin, parent_id=sub_a)
    doc_a = _upload(client[0], admin, "Doc A", sub_a, [medium_id])
    doc_b = _upload(client[0], admin, "Doc B", sub_b, [medium_id])
    doc_a1 = _upload(client[0], admin, "Doc A1", child_a1, [medium_id])
    user_id, user_headers = _create_user(
        client[0], engine, admin, "diraccess@example.com", medium_id
    )
    return {
        "sub_a": sub_a,
        "sub_b": sub_b,
        "child_a1": child_a1,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "doc_a1": doc_a1,
        "user_id": user_id,
        "user_headers": user_headers,
    }


def test_admin_can_grant_single_subdirectory(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    sub = _create_dir(
        test_client, admin, "Grants Me", seeded_data["finance_category_id"]
    )
    target = seeded_data["maker_id"]

    response = test_client.put(
        f"/api/v1/users/{target}/directory-access",
        json={"directory_ids": [sub]},
        headers=admin,
    )
    assert response.status_code == 200, response.text
    assert response.json()["directory_ids"] == [sub]

    # Grant persists on reopen.
    reread = test_client.get(f"/api/v1/users/{target}/directory-access", headers=admin)
    assert reread.status_code == 200
    assert reread.json()["directory_ids"] == [sub]

    profile = test_client.get(f"/api/v1/users/{target}", headers=admin)
    assert profile.status_code == 200
    assert [d["id"] for d in profile.json()["directories"]] == [sub]


def test_admin_can_grant_multiple_subdirectories(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    fin = seeded_data["finance_category_id"]
    sub1 = _create_dir(test_client, admin, "Multi 1", fin)
    sub2 = _create_dir(test_client, admin, "Multi 2", fin)

    response = test_client.put(
        f"/api/v1/users/{seeded_data['maker_id']}/directory-access",
        json={"directory_ids": [sub1, sub2]},
        headers=admin,
    )
    assert response.status_code == 200
    assert sorted(response.json()["directory_ids"]) == sorted([sub1, sub2])


def test_add_grant_is_idempotent(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    sub = _create_dir(test_client, admin, "Idem", seeded_data["finance_category_id"])
    target = seeded_data["maker_id"]

    for _ in range(2):
        response = test_client.post(
            f"/api/v1/users/{target}/directory-access",
            json={"directory_id": sub},
            headers=admin,
        )
        assert response.status_code == 200, response.text
    assert response.json()["directory_ids"] == [sub]

    # PUT with duplicated ids dedupes as well.
    dup = test_client.put(
        f"/api/v1/users/{target}/directory-access",
        json={"directory_ids": [sub, sub]},
        headers=admin,
    )
    assert dup.status_code == 200
    assert dup.json()["directory_ids"] == [sub]


def test_user_with_subdirectory_grant_accesses_authorized_documents(
    client, seeded_data, auth_headers
):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)

    grant = test_client.put(
        f"/api/v1/users/{t['user_id']}/directory-access",
        json={"directory_ids": [t["sub_a"]]},
        headers=admin,
    )
    assert grant.status_code == 200

    listing = test_client.get("/api/v1/documents", headers=t["user_headers"])
    assert listing.status_code == 200
    assert sorted(item["id"] for item in listing.json()["items"]) == sorted(
        [t["doc_a"], t["doc_a1"]]
    )

    detail = test_client.get(f"/api/v1/documents/{t['doc_a']}", headers=t["user_headers"])
    assert detail.status_code == 200

    download = test_client.get(
        f"/api/v1/documents/{t['doc_a']}/download", headers=t["user_headers"]
    )
    assert download.status_code == 200

    directory = test_client.get(
        f"/api/v1/directories/{t['sub_a']}", headers=t["user_headers"]
    )
    assert directory.status_code == 200


def test_sibling_directory_stays_denied(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)
    test_client.put(
        f"/api/v1/users/{t['user_id']}/directory-access",
        json={"directory_ids": [t["sub_a"]]},
        headers=admin,
    )
    uh = t["user_headers"]

    assert test_client.get(f"/api/v1/directories/{t['sub_b']}", headers=uh).status_code == 404
    assert test_client.get(f"/api/v1/documents/{t['doc_b']}", headers=uh).status_code == 404
    assert (
        test_client.get(f"/api/v1/documents/{t['doc_b']}/download", headers=uh).status_code
        == 404
    )
    assert (
        test_client.get(
            f"/api/v1/documents/{t['doc_b']}/view", headers=uh
        ).status_code
        == 404
    )

    tree = test_client.get(
        f"/api/v1/directories/category/{seeded_data['finance_category_id']}/tree",
        headers=uh,
    )
    assert tree.status_code == 200

    def _ids(nodes):
        out = []
        for node in nodes:
            out.append(node["id"])
            out.extend(_ids(node.get("children", [])))
        return out

    visible = _ids(tree.json())
    assert t["sub_a"] in visible
    assert t["sub_b"] not in visible


def test_mutation_guards_enforced_on_sibling_documents(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)
    test_client.put(
        f"/api/v1/users/{t['user_id']}/directory-access",
        json={"directory_ids": [t["sub_a"]]},
        headers=admin,
    )
    uh = t["user_headers"]

    # Upload into sibling denied; into granted dir allowed.
    denied_upload = test_client.post(
        "/api/v1/documents/upload",
        data={"title": "Nope", "directory_id": str(t["sub_b"])},
        files={"file": ("nope.pdf", b"pdf-bytes", "application/pdf")},
        headers=uh,
    )
    assert denied_upload.status_code == 404

    allowed_upload = test_client.post(
        "/api/v1/documents/upload",
        data={"title": "Yep", "directory_id": str(t["sub_a"])},
        files={"file": ("yep.pdf", b"pdf-bytes", "application/pdf")},
        headers=uh,
    )
    assert allowed_upload.status_code == 201, allowed_upload.text

    assert (
        test_client.patch(
            f"/api/v1/documents/{t['doc_b']}", json={"title": "Hijack"}, headers=uh
        ).status_code
        == 404
    )
    # DELETE: makers hold no `delete` permission, so the role layer denies
    # first (403) before the directory guard is reached — still denied.
    assert (
        test_client.delete(f"/api/v1/documents/{t['doc_b']}", headers=uh).status_code
        == 403
    )


def test_master_category_grant_still_covers_whole_tree(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)

    # Seeded maker holds the Finance category grant: sees both subtrees.
    listing = test_client.get("/api/v1/documents", headers=auth_headers["maker"])
    ids = [item["id"] for item in listing.json()["items"]]
    assert t["doc_a"] in ids
    assert t["doc_b"] in ids
    assert t["doc_a1"] in ids


def test_revoke_keeps_overlapping_grant_until_last_removed(
    client, seeded_data, auth_headers
):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)
    test_client.put(
        f"/api/v1/users/{t['user_id']}/directory-access",
        json={"directory_ids": [t["sub_a"], t["child_a1"]]},
        headers=admin,
    )

    # Revoking the child grant keeps access via the parent grant.
    revoked = test_client.delete(
        f"/api/v1/users/{t['user_id']}/directory-access/{t['child_a1']}",
        headers=admin,
    )
    assert revoked.status_code == 204
    assert (
        test_client.get(f"/api/v1/documents/{t['doc_a1']}", headers=t["user_headers"]).status_code
        == 200
    )

    # Revoking the last covering grant removes access.
    revoked = test_client.delete(
        f"/api/v1/users/{t['user_id']}/directory-access/{t['sub_a']}",
        headers=admin,
    )
    assert revoked.status_code == 204
    assert (
        test_client.get(f"/api/v1/documents/{t['doc_a1']}", headers=t["user_headers"]).status_code
        == 404
    )

    # Revoking a non-existent grant is a 404, not a silent success.
    missing = test_client.delete(
        f"/api/v1/users/{t['user_id']}/directory-access/{t['sub_a']}",
        headers=admin,
    )
    assert missing.status_code == 404


def test_nested_grant_covers_descendants_only(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)
    test_client.put(
        f"/api/v1/users/{t['user_id']}/directory-access",
        json={"directory_ids": [t["sub_a"]]},
        headers=admin,
    )
    uh = t["user_headers"]

    # Descendant covered...
    assert test_client.get(f"/api/v1/documents/{t['doc_a1']}", headers=uh).status_code == 200
    assert test_client.get(f"/api/v1/directories/{t['child_a1']}", headers=uh).status_code == 200
    # ...but the parent root directory itself is not (only granted subtree).
    assert (
        test_client.get(
            f"/api/v1/directories/{seeded_data['finance_directory_id']}", headers=uh
        ).status_code
        == 404
    )


def test_user_level_restrictions_still_apply(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    high = seeded_data["high_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)
    secret = _upload(client[0], admin, "Secret", t["sub_a"], [high])
    test_client.put(
        f"/api/v1/users/{t['user_id']}/directory-access",
        json={"directory_ids": [t["sub_a"]]},
        headers=admin,
    )

    listing = test_client.get("/api/v1/documents", headers=t["user_headers"])
    assert secret not in [item["id"] for item in listing.json()["items"]]
    assert test_client.get(f"/api/v1/documents/{secret}", headers=t["user_headers"]).status_code == 403


def test_non_admin_cannot_modify_grants(client, seeded_data, auth_headers):
    test_client, _, _ = client
    maker = auth_headers["maker"]
    target = seeded_data["maker_id"]
    sub = seeded_data["finance_directory_id"]

    assert (
        test_client.put(
            f"/api/v1/users/{target}/directory-access",
            json={"directory_ids": [sub]},
            headers=maker,
        ).status_code
        == 403
    )
    assert (
        test_client.post(
            f"/api/v1/users/{target}/directory-access",
            json={"directory_id": sub},
            headers=maker,
        ).status_code
        == 403
    )
    assert (
        test_client.delete(
            f"/api/v1/users/{target}/directory-access/{sub}", headers=maker
        ).status_code
        == 403
    )
    assert test_client.get(f"/api/v1/users/{target}/directory-access", headers=maker).status_code == 403


def test_unknown_directory_grant_rejected(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    response = test_client.put(
        f"/api/v1/users/{seeded_data['maker_id']}/directory-access",
        json={"directory_ids": [999999]},
        headers=admin,
    )
    assert response.status_code == 404


def test_grant_and_revoke_recorded_in_audit_trail(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    sub = _create_dir(test_client, admin, "Audited", seeded_data["finance_category_id"])
    target = seeded_data["maker_id"]

    test_client.put(
        f"/api/v1/users/{target}/directory-access",
        json={"directory_ids": [sub]},
        headers=admin,
    )
    test_client.delete(f"/api/v1/users/{target}/directory-access/{sub}", headers=admin)

    grants = test_client.get(
        "/api/v1/audit-logs?action=grant_directory_access", headers=admin
    )
    assert grants.status_code == 200
    assert any(item["entity_id"] == str(target) for item in grants.json()["items"])

    revokes = test_client.get(
        "/api/v1/audit-logs?action=revoke_directory_access", headers=admin
    )
    assert revokes.status_code == 200
    assert any(item["entity_id"] == str(target) for item in revokes.json()["items"])


def test_partial_category_visible_as_container(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    t = _tree(client, seeded_data, auth_headers, medium)
    test_client.put(
        f"/api/v1/users/{t['user_id']}/directory-access",
        json={"directory_ids": [t["sub_a"]]},
        headers=admin,
    )

    categories = test_client.get("/api/v1/categories", headers=t["user_headers"])
    assert categories.status_code == 200
    finance = next(
        c for c in categories.json() if c["id"] == seeded_data["finance_category_id"]
    )
    assert finance["access_type"] == "partial"
    assert t["sub_a"] in finance["granted_directory_ids"]
