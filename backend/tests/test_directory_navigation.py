"""Permission-aware navigation of parent directories (spec 28 follow-up).

A user granted only a subdirectory must be able to traverse its ancestor
chain (read-only) without hitting ForbiddenPage, while every write path and
all unauthorized siblings stay denied.
"""

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


def _grant(test_client, admin_headers, user_id: int, directory_ids: list) -> None:
    response = test_client.put(
        f"/api/v1/users/{user_id}/directory-access",
        json={"directory_ids": directory_ids},
        headers=admin_headers,
    )
    assert response.status_code == 200, response.text


def _scenario(client, seeded_data, auth_headers, medium_id: int):
    """finance: parent > assigned (+ sibling); docs in parent and assigned."""
    _, engine, _ = client
    fin = seeded_data["finance_category_id"]
    admin = auth_headers["admin"]
    parent = _create_dir(client[0], admin, "Dept Folder", fin)
    assigned = _create_dir(client[0], admin, "Assigned Sub", fin, parent_id=parent)
    sibling = _create_dir(client[0], admin, "Sibling Sub", fin, parent_id=parent)
    doc_parent = _upload(client[0], admin, "Parent Doc", parent, [medium_id])
    doc_assigned = _upload(client[0], admin, "Assigned Doc", assigned, [medium_id])
    doc_sibling = _upload(client[0], admin, "Sibling Doc", sibling, [medium_id])
    user_id, user_headers = _create_user(
        client[0], engine, admin, "navigator@example.com", medium_id
    )
    _grant(client[0], admin, user_id, [assigned])
    return {
        "parent": parent,
        "assigned": assigned,
        "sibling": sibling,
        "doc_parent": doc_parent,
        "doc_assigned": doc_assigned,
        "doc_sibling": doc_sibling,
        "user_id": user_id,
        "user_headers": user_headers,
    }


def test_parent_folder_navigable_for_descendant_grant(client, seeded_data, auth_headers):
    test_client, _, _ = client
    medium = seeded_data["medium_level_id"]
    t = _scenario(client, seeded_data, auth_headers, medium)
    uh = t["user_headers"]

    parent = test_client.get(f"/api/v1/directories/{t['parent']}", headers=uh)
    assert parent.status_code == 200, parent.text
    assert parent.json()["navigation_only"] is True

    assigned = test_client.get(f"/api/v1/directories/{t['assigned']}", headers=uh)
    assert assigned.status_code == 200
    assert assigned.json()["navigation_only"] is False

    # Category metadata readable for the page header.
    cat = test_client.get(
        f"/api/v1/categories/{seeded_data['finance_category_id']}", headers=uh
    )
    assert cat.status_code == 200

    # Tree keeps the ancestor path, drops the unauthorized sibling.
    tree = test_client.get(
        f"/api/v1/directories/category/{seeded_data['finance_category_id']}/tree",
        headers=uh,
    )
    assert tree.status_code == 200
    roots = tree.json()
    assert len(roots) == 1
    root_node = roots[0]
    assert root_node["id"] == t["parent"]
    assert root_node["navigation_only"] is True
    child_ids = [c["id"] for c in root_node["children"]]
    assert child_ids == [t["assigned"]]
    assert root_node["children"][0]["navigation_only"] is False


def test_parent_document_listing_returns_only_authorized_content(
    client, seeded_data, auth_headers
):
    test_client, _, _ = client
    medium = seeded_data["medium_level_id"]
    t = _scenario(client, seeded_data, auth_headers, medium)
    uh = t["user_headers"]

    parent_listing = test_client.get(
        f"/api/v1/documents?directory_id={t['parent']}", headers=uh
    )
    assert parent_listing.status_code == 200, parent_listing.text
    assert parent_listing.json()["total"] == 0

    assigned_listing = test_client.get(
        f"/api/v1/documents?directory_id={t['assigned']}", headers=uh
    )
    assert assigned_listing.status_code == 200
    assert [d["id"] for d in assigned_listing.json()["items"]] == [t["doc_assigned"]]

    # No leakage through the unscoped list either.
    all_docs = test_client.get("/api/v1/documents", headers=uh).json()
    ids = [d["id"] for d in all_docs["items"]]
    assert t["doc_assigned"] in ids
    assert t["doc_parent"] not in ids
    assert t["doc_sibling"] not in ids


def test_sibling_and_writes_stay_denied(client, seeded_data, auth_headers):
    test_client, _, _ = client
    medium = seeded_data["medium_level_id"]
    t = _scenario(client, seeded_data, auth_headers, medium)
    uh = t["user_headers"]

    # Sibling directory / content unreachable.
    assert test_client.get(f"/api/v1/directories/{t['sibling']}", headers=uh).status_code == 404
    assert (
        test_client.get(f"/api/v1/documents?directory_id={t['sibling']}", headers=uh).status_code
        == 404
    )
    assert test_client.get(f"/api/v1/documents/{t['doc_sibling']}", headers=uh).status_code == 404
    assert (
        test_client.get(f"/api/v1/documents/{t['doc_sibling']}/download", headers=uh).status_code
        == 404
    )

    # Navigation never unlocks writes on the nav-only parent.
    upload = test_client.post(
        "/api/v1/documents/upload",
        data={"title": "Nope", "directory_id": str(t["parent"])},
        files={"file": ("nope.pdf", b"pdf-bytes", "application/pdf")},
        headers=uh,
    )
    assert upload.status_code == 404

    rename = test_client.patch(
        f"/api/v1/directories/{t['parent']}", json={"name": "Hijack"}, headers=uh
    )
    assert rename.status_code == 404

    # DELETE: makers hold no `delete` permission, so the role layer denies
    # before the directory guard is reached — still denied.
    delete = test_client.delete(f"/api/v1/directories/{t['parent']}", headers=uh)
    assert delete.status_code == 403

    # Writes into the granted directory still work.
    allowed = test_client.post(
        "/api/v1/documents/upload",
        data={"title": "Yep", "directory_id": str(t["assigned"])},
        files={"file": ("yep.pdf", b"pdf-bytes", "application/pdf")},
        headers=uh,
    )
    assert allowed.status_code == 201, allowed.text


def test_nested_ancestor_chain_navigable_recursively(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    fin = seeded_data["finance_category_id"]
    top = _create_dir(test_client, admin, "Top", fin)
    mid = _create_dir(test_client, admin, "Mid", fin, parent_id=top)
    leaf = _create_dir(test_client, admin, "Leaf", fin, parent_id=mid)
    other = _create_dir(test_client, admin, "Other Child", fin, parent_id=top)
    user_id, uh = _create_user(client[0], engine, admin, "deepnav@example.com", medium)
    _grant(test_client, admin, user_id, [leaf])

    for dir_id in (mid, top):
        r = test_client.get(f"/api/v1/directories/{dir_id}", headers=uh)
        assert r.status_code == 200, r.text
        assert r.json()["navigation_only"] is True

    leaf_r = test_client.get(f"/api/v1/directories/{leaf}", headers=uh)
    assert leaf_r.status_code == 200
    assert leaf_r.json()["navigation_only"] is False

    # Unrelated branch under the same root stays invisible.
    assert test_client.get(f"/api/v1/directories/{other}", headers=uh).status_code == 404

    tree = test_client.get(f"/api/v1/directories/category/{fin}/tree", headers=uh)
    assert tree.status_code == 200
    roots = tree.json()
    assert len(roots) == 1 and roots[0]["id"] == top
    mid_node = roots[0]["children"][0]
    assert mid_node["id"] == mid
    assert [c["id"] for c in mid_node["children"]] == [leaf]


def test_full_category_grant_has_no_navigation_flag(client, seeded_data, auth_headers):
    test_client, _, _ = client
    r = test_client.get(
        f"/api/v1/directories/{seeded_data['finance_directory_id']}",
        headers=auth_headers["maker"],
    )
    assert r.status_code == 200
    assert r.json()["navigation_only"] is False

    tree = test_client.get(
        f"/api/v1/directories/category/{seeded_data['finance_category_id']}/tree",
        headers=auth_headers["maker"],
    )
    assert tree.status_code == 200

    def _flags(nodes):
        out = [n.get("navigation_only", False) for n in nodes]
        for n in nodes:
            out.extend(_flags(n.get("children", [])))
        return out

    assert any(_flags(tree.json())) is False


def test_navigation_respects_user_level(client, seeded_data, auth_headers):
    test_client, _, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    high = seeded_data["high_level_id"]
    t = _scenario(client, seeded_data, auth_headers, medium)
    secret = _upload(client[0], admin, "Secret", t["assigned"], [high])
    uh = t["user_headers"]

    assigned_listing = test_client.get(
        f"/api/v1/documents?directory_id={t['assigned']}", headers=uh
    ).json()
    assert secret not in [d["id"] for d in assigned_listing["items"]]
    assert test_client.get(f"/api/v1/documents/{secret}", headers=uh).status_code == 403

    parent_listing = test_client.get(
        f"/api/v1/documents?directory_id={t['parent']}", headers=uh
    ).json()
    assert parent_listing["total"] == 0


def test_zero_grant_user_cannot_navigate(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    _, uh = _create_user(client[0], engine, admin, "nogrant@example.com", medium)

    assert (
        test_client.get(
            f"/api/v1/directories/{seeded_data['finance_directory_id']}", headers=uh
        ).status_code
        == 404
    )
    assert (
        test_client.get(
            f"/api/v1/categories/{seeded_data['finance_category_id']}", headers=uh
        ).status_code
        == 404
    )
    assert (
        test_client.get(
            f"/api/v1/documents?directory_id={seeded_data['finance_directory_id']}",
            headers=uh,
        ).status_code
        == 404
    )


def test_revoking_grant_removes_navigation(client, seeded_data, auth_headers):
    test_client, _, _ = client
    medium = seeded_data["medium_level_id"]
    t = _scenario(client, seeded_data, auth_headers, medium)
    admin = auth_headers["admin"]

    assert (
        test_client.get(f"/api/v1/directories/{t['parent']}", headers=t["user_headers"]).status_code
        == 200
    )

    revoke = test_client.delete(
        f"/api/v1/users/{t['user_id']}/directory-access/{t['assigned']}",
        headers=admin,
    )
    assert revoke.status_code == 204

    assert (
        test_client.get(f"/api/v1/directories/{t['parent']}", headers=t["user_headers"]).status_code
        == 404
    )


def test_partial_category_counts_scoped_to_granted_subtree(
    client, seeded_data, auth_headers
):
    test_client, _, _ = client
    medium = seeded_data["medium_level_id"]
    t = _scenario(client, seeded_data, auth_headers, medium)

    categories = test_client.get("/api/v1/categories", headers=t["user_headers"])
    assert categories.status_code == 200
    finance = next(
        c for c in categories.json() if c["id"] == seeded_data["finance_category_id"]
    )
    assert finance["access_type"] == "partial"
    # Only granted-subtree content counts — parent doc, sibling dir/doc and
    # the seeded Finance Root doc stay out of the stats.
    assert finance["directory_count"] == 1
    assert finance["document_count"] == 1


def test_auth_me_includes_directory_grants_for_frontend_gate(
    client, seeded_data, auth_headers
):
    """GET /auth/me must carry directory grants.

    The frontend's canAccessCategory gate reads user.directories; omitting
    them sent grant-only users to /forbidden before any API call.
    """
    test_client, _, _ = client
    medium = seeded_data["medium_level_id"]
    t = _scenario(client, seeded_data, auth_headers, medium)

    me = test_client.get("/api/v1/auth/me", headers=t["user_headers"])
    assert me.status_code == 200
    granted = {d["id"]: d for d in me.json()["directories"]}
    assert t["assigned"] in granted
    assert granted[t["assigned"]]["category_id"] == seeded_data["finance_category_id"]
    # Sibling/parent are not grants — only the granted directory is listed.
    assert t["sibling"] not in granted
    assert t["parent"] not in granted


def test_auth_me_directories_empty_without_grants(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    admin = auth_headers["admin"]
    medium = seeded_data["medium_level_id"]
    _, uh = _create_user(client[0], engine, admin, "nograntme@example.com", medium)

    me = test_client.get("/api/v1/auth/me", headers=uh)
    assert me.status_code == 200
    assert me.json()["directories"] == []
