from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import core.database
import middleware.rbac
from core.database import get_session
from core.security import create_access_token, hash_password
from documents.models import Document, DocumentStatus, FileType
from directories.models import Directory
from main import app
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
from categories.models import Category


@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    SQLModel.metadata.create_all(engine)

    monkeypatch.setattr(core.database, "engine", engine)
    monkeypatch.setattr(middleware.rbac, "engine", engine)
    monkeypatch.setattr(core.database.settings, "DEBUG", False)
    monkeypatch.setattr(core.database.settings, "STORAGE_ROOT", str(tmp_path / "storage"))

    def override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as test_client:
        yield test_client, engine, Path(core.database.settings.STORAGE_ROOT)

    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_data(client):
    _, engine, _ = client

    with Session(engine) as session:
        permissions = {}
        for action in PermissionAction:
            permission = Permission(action=action, description=f"{action.value} permission")
            session.add(permission)
            session.flush()
            permissions[action] = permission

        admin_role = Role(name=RoleName.ADMIN, description="Admin")
        maker_role = Role(name=RoleName.MAKER, description="Maker")
        session.add(admin_role)
        session.add(maker_role)
        session.flush()

        for permission in permissions.values():
            session.add(
                RolePermissionLink(role_id=admin_role.id, permission_id=permission.id)
            )

        for action in (
            PermissionAction.VIEW,
            PermissionAction.DOWNLOAD,
            PermissionAction.CREATE,
            PermissionAction.UPDATE,
        ):
            session.add(
                RolePermissionLink(role_id=maker_role.id, permission_id=permissions[action].id)
            )

        admin = User(
            full_name="Admin User",
            email="admin@example.com",
            hashed_password=hash_password("Admin@1234"),
            is_active=True,
        )
        maker = User(
            full_name="Maker User",
            email="maker@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
        )
        session.add(admin)
        session.add(maker)
        session.flush()

        session.add(UserRoleLink(user_id=admin.id, role_id=admin_role.id))
        session.add(UserRoleLink(user_id=maker.id, role_id=maker_role.id))

        finance = Category(name="Finance", description="Finance docs", is_active=True)
        hr = Category(name="HR", description="HR docs", is_active=True)
        legal = Category(name="Legal", description="Legal docs", is_active=False)
        session.add(finance)
        session.add(hr)
        session.add(legal)
        session.flush()

        session.add(UserCategoryLink(user_id=maker.id, category_id=finance.id))
        session.add(UserCategoryLink(user_id=maker.id, category_id=legal.id))

        finance_dir = Directory(
            name="Finance Root",
            description="",
            category_id=finance.id,
            parent_id=None,
            created_by=admin.id,
        )
        hr_dir = Directory(
            name="HR Root",
            description="",
            category_id=hr.id,
            parent_id=None,
            created_by=admin.id,
        )
        session.add(finance_dir)
        session.add(hr_dir)
        session.flush()

        finance_doc = Document(
            title="Finance Report",
            description="Visible document",
            directory_id=finance_dir.id,
            uploaded_by=admin.id,
            file_name="finance.pdf",
            file_type=FileType.PDF,
            mime_type="application/pdf",
            file_size=128,
            storage_path="finance/finance.pdf",
            status=DocumentStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        hr_doc = Document(
            title="HR Policy",
            description="Hidden document",
            directory_id=hr_dir.id,
            uploaded_by=admin.id,
            file_name="hr.pdf",
            file_type=FileType.PDF,
            mime_type="application/pdf",
            file_size=128,
            storage_path="hr/hr.pdf",
            status=DocumentStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(finance_doc)
        session.add(hr_doc)
        session.commit()

        return {
            "admin_id": admin.id,
            "maker_id": maker.id,
            "finance_category_id": finance.id,
            "hr_category_id": hr.id,
            "legal_category_id": legal.id,
            "finance_directory_id": finance_dir.id,
            "hr_directory_id": hr_dir.id,
            "finance_document_id": finance_doc.id,
            "hr_document_id": hr_doc.id,
        }


@pytest.fixture()
def auth_headers(seeded_data):
    return {
        "admin": {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"},
        "maker": {"Authorization": f"Bearer {create_access_token(seeded_data['maker_id'])}"},
    }
