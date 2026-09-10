from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

import core.database
import middleware.rbac
import middleware.audit
from core.database import get_session
from core.security import create_access_token, hash_password
from documents.models import Document, DocumentStatus, DocumentUserLevelLink, FileType
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
from user_levels.models import UserLevel
from company_profile.models import Company


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
    monkeypatch.setattr(middleware.audit, "engine", engine)
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
        checker_role = Role(name=RoleName.CHECKER, description="Checker")
        auditor_role = Role(name=RoleName.AUDITOR, description="Auditor")
        superadmin_role = Role(name=RoleName.SUPERADMIN, description="Full system access; manages admins & companies")
        session.add(admin_role)
        session.add(maker_role)
        session.add(checker_role)
        session.add(auditor_role)
        session.add(superadmin_role)
        session.flush()

        for permission in permissions.values():
            session.add(
                RolePermissionLink(role_id=admin_role.id, permission_id=permission.id)
            )
            session.add(
                RolePermissionLink(role_id=superadmin_role.id, permission_id=permission.id)
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

        for action in (
            PermissionAction.VIEW,
            PermissionAction.DOWNLOAD,
            PermissionAction.UPDATE,
        ):
            session.add(
                RolePermissionLink(role_id=checker_role.id, permission_id=permissions[action].id)
            )

        for action in (
            PermissionAction.VIEW,
            PermissionAction.DOWNLOAD,
        ):
            session.add(
                RolePermissionLink(role_id=auditor_role.id, permission_id=permissions[action].id)
            )

        # User levels
        high_level = UserLevel(name="High", description="High access", is_active=True)
        medium_level = UserLevel(name="Medium", description="Medium access", is_active=True)
        low_level = UserLevel(name="Low", description="Low access", is_active=True)
        session.add(high_level)
        session.add(medium_level)
        session.add(low_level)
        session.flush()

        admin = User(
            full_name="Admin User",
            email="admin@example.com",
            hashed_password=hash_password("Admin@1234"),
            is_active=True,
            user_level_id=high_level.id,
        )
        maker = User(
            full_name="Maker User",
            email="maker@example.com",
            hashed_password=hash_password("Maker@1234"),
            is_active=True,
            user_level_id=medium_level.id,
        )
        superadmin = User(
            full_name="Super Administrator",
            email="superadmin@dms.local",
            hashed_password=hash_password("SuperAdmin@1234"),
            is_active=True,
            user_level_id=high_level.id,
        )
        session.add(admin)
        session.add(maker)
        session.add(superadmin)
        session.flush()

        session.add(UserRoleLink(user_id=admin.id, role_id=admin_role.id))
        session.add(UserRoleLink(user_id=maker.id, role_id=maker_role.id))
        session.add(UserRoleLink(user_id=superadmin.id, role_id=superadmin_role.id))

        # Create a test company for admin
        test_company = Company(
            company_id="TEST-COMP-001",
            full_name="Test Company",
            short_name="TESTCO",
            is_active=True,
        )
        session.add(test_company)
        session.flush()

        # Create a second company for cross-company testing
        other_company = Company(
            company_id="OTHER-CO-002",
            full_name="Other Company",
            short_name="OTHERCO",
            is_active=True,
        )
        session.add(other_company)
        session.flush()

        # Assign company to admin user
        admin.company_id = test_company.id
        session.add(admin)
        # Assign company to maker user (same company as admin)
        maker.company_id = test_company.id
        session.add(maker)
        session.flush()

        # Create second admin for cross-company testing
        other_admin = User(
            full_name="Other Admin",
            email="other_admin@example.com",
            hashed_password=hash_password("OtherAdmin@1234"),
            is_active=True,
            user_level_id=high_level.id,
            company_id=other_company.id,
        )
        session.add(other_admin)
        session.flush()
        session.add(UserRoleLink(user_id=other_admin.id, role_id=admin_role.id))

        finance = Category(
            name="Finance",
            description="Finance docs",
            is_active=True,
            company_id=test_company.id,
            created_by=admin.id,
        )
        hr = Category(
            name="HR",
            description="HR docs",
            is_active=True,
            company_id=test_company.id,
            created_by=admin.id,
        )
        legal = Category(
            name="Legal",
            description="Legal docs",
            is_active=False,
            company_id=test_company.id,
            created_by=admin.id,
        )
        # Categories for the other company
        marketing = Category(
            name="Marketing",
            description="Marketing docs",
            is_active=True,
            company_id=other_company.id,
            created_by=other_admin.id,
        )
        operations = Category(
            name="Operations",
            description="Operations docs",
            is_active=True,
            company_id=other_company.id,
            created_by=other_admin.id,
        )
        session.add(finance)
        session.add(hr)
        session.add(legal)
        session.add(marketing)
        session.add(operations)
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
        session.flush()

        # Link documents to user levels for visibility
        # finance_doc: visible to High and Medium
        session.add(DocumentUserLevelLink(document_id=finance_doc.id, user_level_id=high_level.id))
        session.add(DocumentUserLevelLink(document_id=finance_doc.id, user_level_id=medium_level.id))
        # hr_doc: visible to High only
        session.add(DocumentUserLevelLink(document_id=hr_doc.id, user_level_id=high_level.id))

        session.commit()

        return {
            "admin_id": admin.id,
            "maker_id": maker.id,
            "superadmin_id": superadmin.id,
            "other_admin_id": other_admin.id,
            "finance_category_id": finance.id,
            "hr_category_id": hr.id,
            "legal_category_id": legal.id,
            "marketing_category_id": marketing.id,
            "operations_category_id": operations.id,
            "finance_directory_id": finance_dir.id,
            "hr_directory_id": hr_dir.id,
            "finance_document_id": finance_doc.id,
            "hr_document_id": hr_doc.id,
            "high_level_id": high_level.id,
            "medium_level_id": medium_level.id,
            "low_level_id": low_level.id,
            "company_id": test_company.id,
            "other_company_id": other_company.id,
        }


@pytest.fixture()
def auth_headers(seeded_data):
    return {
        "admin": {"Authorization": f"Bearer {create_access_token(seeded_data['admin_id'])}"},
        "maker": {"Authorization": f"Bearer {create_access_token(seeded_data['maker_id'])}"},
        "superadmin": {"Authorization": f"Bearer {create_access_token(seeded_data['superadmin_id'])}"},
        "other_admin": {"Authorization": f"Bearer {create_access_token(seeded_data['other_admin_id'])}"},
    }
