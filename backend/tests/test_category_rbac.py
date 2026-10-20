def test_admin_can_assign_and_unassign_categories(client, seeded_data, auth_headers):
    test_client, _, _ = client

    response = test_client.patch(
        f"/api/v1/users/{seeded_data['maker_id']}",
        json={"category_ids": [seeded_data["hr_category_id"]]},
        headers=auth_headers["admin"],
    )

    assert response.status_code == 200
    payload = response.json()
    assert [category["id"] for category in payload["categories"]] == [seeded_data["hr_category_id"]]

    response = test_client.patch(
        f"/api/v1/users/{seeded_data['maker_id']}",
        json={"category_ids": []},
        headers=auth_headers["admin"],
    )

    assert response.status_code == 200
    assert response.json()["categories"] == []


def test_regular_user_only_lists_assigned_active_categories(client, auth_headers):
    test_client, _, _ = client

    response = test_client.get("/api/v1/categories", headers=auth_headers["maker"])

    assert response.status_code == 200
    payload = response.json()
    assert [category["name"] for category in payload] == ["Finance"]


def test_regular_user_cannot_fetch_unassigned_category_by_id(client, seeded_data, auth_headers):
    test_client, _, _ = client

    response = test_client.get(
        f"/api/v1/categories/{seeded_data['hr_category_id']}",
        headers=auth_headers["maker"],
    )

    assert response.status_code == 404


def test_regular_user_cannot_access_directory_or_document_outside_assigned_category(
    client,
    seeded_data,
    auth_headers,
):
    test_client, _, _ = client

    directory_response = test_client.get(
        f"/api/v1/directories/{seeded_data['hr_directory_id']}",
        headers=auth_headers["maker"],
    )
    document_response = test_client.get(
        f"/api/v1/documents/{seeded_data['hr_document_id']}",
        headers=auth_headers["maker"],
    )

    assert directory_response.status_code == 404
    assert document_response.status_code == 404


def test_regular_user_document_list_is_scoped_to_assigned_categories(
    client,
    seeded_data,
    auth_headers,
):
    test_client, _, _ = client

    response = test_client.get("/api/v1/documents", headers=auth_headers["maker"])

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert [item["id"] for item in payload["items"]] == [seeded_data["finance_document_id"]]

    filtered_response = test_client.get(
        f"/api/v1/documents?category_id={seeded_data['hr_category_id']}",
        headers=auth_headers["maker"],
    )
    assert filtered_response.status_code == 404


def test_regular_user_cannot_upload_to_unassigned_category_directory(
    client,
    seeded_data,
    auth_headers,
):
    test_client, _, _ = client

    response = test_client.post(
        "/api/v1/documents/upload",
        data={
            "title": "Blocked Upload",
            "description": "Should not be allowed",
            "directory_id": str(seeded_data["hr_directory_id"]),
        },
        files={"file": ("blocked.pdf", b"pdf-bytes", "application/pdf")},
        headers=auth_headers["maker"],
    )

    assert response.status_code == 404
