"""Regression coverage for company-scoped user email addresses."""

from sqlmodel import Session, select

from auth.azure_service import resolve_azure_user
from company_profile.models import Company
from core.security import hash_password
from users.models import Role, RoleName, User


SHARED_EMAIL = "shared.user@example.com"
PASSWORD = "Shared@1234"


def _create_company(session: Session, company_id: str, short_name: str) -> Company:
    company = Company(
        company_id=company_id,
        full_name=f"{short_name} Company",
        short_name=short_name,
        is_active=True,
    )
    session.add(company)
    session.commit()
    session.refresh(company)
    return company


def _create_user(session: Session, company_id: int, email: str = SHARED_EMAIL) -> User:
    user = User(
        full_name="Shared User",
        email=email,
        hashed_password=hash_password(PASSWORD),
        company_id=company_id,
        is_active=True,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _admin_role_id(session: Session) -> int:
    return session.exec(select(Role).where(Role.name == RoleName.ADMIN)).one().id


def test_same_email_can_be_created_in_different_companies(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    with Session(engine) as session:
        company_b = _create_company(session, "EMAIL-B", "EMAILB")
        admin_role = _admin_role_id(session)

    first = test_client.post(
        "/api/v1/users",
        json={
            "full_name": "Shared Admin A",
            "email": SHARED_EMAIL,
            "password": PASSWORD,
            "role_ids": [admin_role],
            "company_id": seeded_data["company_id"],
        },
        headers=auth_headers["superadmin"],
    )
    second = test_client.post(
        "/api/v1/users",
        json={
            "full_name": "Shared Admin B",
            "email": SHARED_EMAIL,
            "password": PASSWORD,
            "role_ids": [admin_role],
            "company_id": company_b.id,
        },
        headers=auth_headers["superadmin"],
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["company"]["id"] == seeded_data["company_id"]
    assert second.json()["company"]["id"] == company_b.id


def test_same_email_is_rejected_within_one_company(client, seeded_data, auth_headers):
    test_client, engine, _ = client
    with Session(engine) as session:
        admin_role = _admin_role_id(session)
    payload = {
        "full_name": "First Shared Admin",
        "email": SHARED_EMAIL,
        "password": PASSWORD,
        "role_ids": [admin_role],
        "company_id": seeded_data["company_id"],
    }

    assert test_client.post(
        "/api/v1/users", json=payload, headers=auth_headers["superadmin"]
    ).status_code == 201

    payload["full_name"] = "Duplicate Shared Admin"
    duplicate = test_client.post(
        "/api/v1/users", json=payload, headers=auth_headers["superadmin"]
    )
    assert duplicate.status_code == 409


def test_login_requires_company_when_email_exists_in_multiple_companies(client):
    test_client, engine, _ = client
    with Session(engine) as session:
        company_a = _create_company(session, "LOGIN-A", "LOGINA")
        company_b = _create_company(session, "LOGIN-B", "LOGINB")
        user_a = _create_user(session, company_a.id)
        user_b = _create_user(session, company_b.id)
        company_a_id, company_b_id = company_a.id, company_b.id
        user_a_id, user_b_id = user_a.id, user_b.id

    ambiguous = test_client.post(
        "/api/v1/auth/login", json={"email": SHARED_EMAIL, "password": PASSWORD}
    )
    assert ambiguous.status_code == 200
    body = ambiguous.json()
    assert body["requires_company_selection"] is True
    assert len(body["companies"]) == 2

    for company_id, user_id in ((company_a_id, user_a_id), (company_b_id, user_b_id)):
        response = test_client.post(
            "/api/v1/auth/login",
            json={
                "email": SHARED_EMAIL,
                "password": PASSWORD,
                "company_id": company_id,
            },
        )
        assert response.status_code == 200, response.text
        me = test_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {response.json()['access_token']}"},
        )
        assert me.status_code == 200
        assert me.json()["id"] == user_id


def test_azure_email_match_is_limited_to_selected_company(client, seeded_data):
    _, engine, _ = client
    with Session(engine) as session:
        company_a = seeded_data["company_id"]
        company_b = seeded_data["other_company_id"]
        user_b = _create_user(session, company_b)

        resolved = resolve_azure_user(
            session,
            {"oid": "azure-shared-a", "email": SHARED_EMAIL, "name": "Shared A"},
            company_a,
        )

        assert resolved.id != user_b.id
        assert resolved.company_id == company_a
        session.expire_all()
        assert session.get(User, user_b.id).azure_object_id is None
        assert len(session.exec(select(User).where(User.email == SHARED_EMAIL)).all()) == 2
