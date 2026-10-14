"""Company isolation for subdirectory-level grants."""

from sqlmodel import Session, select

from core.security import create_access_token, hash_password
from users.models import Role, RoleName, User, UserRoleLink


def _headers(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _admin_role_id(engine) -> int:
    with Session(engine) as session:
        return session.exec(select(Role.id).where(Role.name == RoleName.ADMIN)).first()


def test_cross_company_directory_grant_rejected(client, seeded_data, auth_headers):
    test_client, _, _ = client
    # Marketing dir belongs to OTHERCO; TESTCO admin must get 404 (no oracle).
    response = test_client.put(
        f"/api/v1/users/{seeded_data['maker_id']}/directory-access",
        json={"directory_ids": [seeded_data["marketing_directory_id"]]},
        headers=auth_headers["admin"],
    )
    assert response.status_code == 404

    single = test_client.post(
        f"/api/v1/users/{seeded_data['maker_id']}/directory-access",
        json={"directory_id": seeded_data["marketing_directory_id"]},
        headers=auth_headers["admin"],
    )
    assert single.status_code == 404


def test_cross_company_user_target_not_found(client, seeded_data, auth_headers):
    test_client, _, _ = client
    # other_admin belongs to OTHERCO: invisible to TESTCO admin.
    response = test_client.get(
        f"/api/v1/users/{seeded_data['other_admin_id']}/directory-access",
        headers=auth_headers["admin"],
    )
    assert response.status_code == 404

    response = test_client.put(
        f"/api/v1/users/{seeded_data['other_admin_id']}/directory-access",
        json={"directory_ids": [seeded_data["finance_directory_id"]]},
        headers=auth_headers["admin"],
    )
    assert response.status_code == 404


def test_other_admin_manages_only_own_company(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    with Session(engine) as session:
        maker_role_id = session.exec(
            select(Role.id).where(Role.name == RoleName.MAKER)
        ).first()
        other_user = User(
            full_name="Other Maker",
            email="other_maker@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            company_id=seeded_data["other_company_id"],
        )
        session.add(other_user)
        session.flush()
        other_user_id = other_user.id
        session.add(UserRoleLink(user_id=other_user_id, role_id=maker_role_id))
        session.commit()

    other_admin = auth_headers["other_admin"]
    ok = test_client.put(
        f"/api/v1/users/{other_user_id}/directory-access",
        json={"directory_ids": [seeded_data["marketing_directory_id"]]},
        headers=other_admin,
    )
    assert ok.status_code == 200

    # TESTCO directory rejected for OTHERCO admin.
    denied = test_client.put(
        f"/api/v1/users/{other_user_id}/directory-access",
        json={"directory_ids": [seeded_data["finance_directory_id"]]},
        headers=other_admin,
    )
    assert denied.status_code == 404


def test_superadmin_reads_but_cannot_write_grants(client, seeded_data, auth_headers):
    test_client, _, _ = client
    superadmin = auth_headers["superadmin"]
    target = seeded_data["maker_id"]

    reads = test_client.get(f"/api/v1/users/{target}/directory-access", headers=superadmin)
    assert reads.status_code == 200

    writes = test_client.put(
        f"/api/v1/users/{target}/directory-access",
        json={"directory_ids": [seeded_data["finance_directory_id"]]},
        headers=superadmin,
    )
    assert writes.status_code == 403


def test_company_less_admin_rejected_on_write(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    role_id = _admin_role_id(engine)
    with Session(engine) as session:
        lonely = User(
            full_name="Lonely Admin",
            email="lonely_admin@example.com",
            hashed_password=hash_password("Admin@1234"),
            is_active=True,
            company_id=None,
        )
        session.add(lonely)
        session.flush()
        lonely_id = lonely.id
        session.add(UserRoleLink(user_id=lonely_id, role_id=role_id))
        session.commit()
    lonely_headers = _headers(lonely_id)

    response = test_client.put(
        f"/api/v1/users/{seeded_data['maker_id']}/directory-access",
        json={"directory_ids": [seeded_data["finance_directory_id"]]},
        headers=lonely_headers,
    )
    assert response.status_code == 400


def test_null_company_user_invisible_to_admin(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    with Session(engine) as session:
        orphan = User(
            full_name="Orphan User",
            email="orphan_dir@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            company_id=None,
        )
        session.add(orphan)
        session.flush()
        orphan_id = orphan.id
        session.commit()

    response = test_client.get(
        f"/api/v1/users/{orphan_id}/directory-access",
        headers=auth_headers["admin"],
    )
    assert response.status_code == 404


def test_directory_grant_does_not_leak_across_companies(
    client, seeded_data, auth_headers
):
    test_client, engine, _ = client
    # Grant within TESTCO; a non-admin from OTHERCO must not see TESTCO content.
    # (Admins bypass grants by design within their own scope; the grant-time
    # company check plus non-admin enforcement is what prevents leakage.)
    with Session(engine) as session:
        maker_role_id = session.exec(
            select(Role.id).where(Role.name == RoleName.MAKER)
        ).first()
        stranger = User(
            full_name="Stranger Maker",
            email="stranger_maker@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            company_id=seeded_data["other_company_id"],
        )
        session.add(stranger)
        session.flush()
        stranger_id = stranger.id
        session.add(UserRoleLink(user_id=stranger_id, role_id=maker_role_id))
        session.commit()
    stranger_headers = _headers(stranger_id)

    test_client.put(
        f"/api/v1/users/{seeded_data['maker_id']}/directory-access",
        json={"directory_ids": [seeded_data["finance_directory_id"]]},
        headers=auth_headers["admin"],
    )

    listing = test_client.get(
        f"/api/v1/documents?directory_id={seeded_data['finance_directory_id']}",
        headers=stranger_headers,
    )
    assert listing.status_code == 404
    assert (
        test_client.get(
            f"/api/v1/documents/{seeded_data['finance_document_id']}",
            headers=stranger_headers,
        ).status_code
        == 404
    )
