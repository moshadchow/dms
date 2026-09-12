from datetime import datetime
import secrets
import string
from typing import List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from categories.models import Category
from company_profile.models import Company, CompanyRead
from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.security import hash_password
from user_levels.models import UserLevel, UserLevelRead
from users.models import (
    AssignedCategoryRead,
    Permission,
    PermissionAction,
    PermissionRead,
    Role,
    RoleCreate,
    RoleName,
    RoleRead,
    RolePermissionLink,
    User,
    UserCategoryLink,
    UserCreate,
    UserRead,
    UserRoleLink,
    UserUpdate,
    get_user_with_roles,
)


def _role_to_read(role: Role) -> RoleRead:
    return RoleRead(
        id=role.id,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
        permissions=[
            PermissionRead(id=p.id, action=p.action, description=p.description)
            for p in role.permissions
        ],
    )


def _user_to_read(user: User) -> UserRead:
    level_read = None
    if user.user_level:
        level_read = UserLevelRead.model_validate(user.user_level)
    company_read = None
    if user.company:
        company_read = CompanyRead.model_validate(user.company)
    return UserRead(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
        roles=[_role_to_read(r) for r in user.roles],
        categories=[
            AssignedCategoryRead(
                id=category.id,
                name=category.name,
                description=category.description,
                is_active=category.is_active,
            )
            for category in user.categories
        ],
        user_level=level_read,
        company=company_read,
    )


class UserService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Users
    # ──────────────────────────────────────────

    def list_users(
        self,
        skip:      int = 0,
        limit:     int = 50,
        search:    Optional[str]  = None,
        is_active: Optional[bool] = None,
        user_level_id: Optional[int] = None,
        current_user:  Optional[User] = None,
        company_id:    Optional[int] = None,
    ) -> Tuple[List[UserRead], int]:
        query = select(User).options(
            selectinload(User.roles).selectinload(Role.permissions),  # type: ignore[arg-type]
            selectinload(User.categories),  # type: ignore[arg-type]
            selectinload(User.user_level),  # type: ignore[arg-type]
            selectinload(User.company),  # type: ignore[arg-type]
        )

        # Hide SUPERADMIN users from ADMIN list and scope to same company
        if current_user is not None:
            is_superadmin = any(r.name == RoleName.SUPERADMIN for r in current_user.roles)
            is_admin = any(r.name == RoleName.ADMIN for r in current_user.roles)
            if is_admin and not is_superadmin:
                superadmin_role_id = self.session.exec(
                    select(Role.id).where(Role.name == RoleName.SUPERADMIN)
                ).first()
                if superadmin_role_id is not None:
                    superadmin_user_ids = self.session.exec(
                        select(UserRoleLink.user_id).where(
                            UserRoleLink.role_id == superadmin_role_id
                        )
                    ).all()
                    if superadmin_user_ids:
                        query = query.where(User.id.notin_(superadmin_user_ids))

                # Scope to same company
                if current_user.company_id is not None:
                    query = query.where(User.company_id == current_user.company_id)
                else:
                    return [], 0

            # SUPERADMIN company filter: when company_id is provided, scope to that company
            if is_superadmin and company_id is not None:
                # Validate company exists
                company = self.session.get(Company, company_id)
                if not company:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Company {company_id} not found",
                    )
                query = query.where(User.company_id == company_id)

        if search:
            query = query.where(
                User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
            )
        if is_active is not None:
            query = query.where(User.is_active == is_active)
        if user_level_id is not None:
            query = query.where(User.user_level_id == user_level_id)

        all_users = self.session.exec(query).all()
        total     = len(all_users)
        page      = self.session.exec(query.offset(skip).limit(limit)).all()
        return [_user_to_read(u) for u in page], total

    def get_user(self, user_id: int) -> UserRead:
        user = get_user_with_roles(self.session, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        return _user_to_read(user)

    def create_user(self, data: UserCreate, current_user: User = None) -> UserRead:
        exists = self.session.exec(
            select(User).where(User.email == data.email)
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Email '{data.email}' is already registered",
            )

        # Enforce: SUPERADMIN can only assign ADMIN role
        is_superadmin = False
        if current_user is not None:
            is_superadmin = any(r.name == RoleName.SUPERADMIN for r in current_user.roles)
            if is_superadmin:
                allowed_ids = {
                    r.id for r in self.session.exec(select(Role)).all()
                    if r.name == RoleName.ADMIN
                }
                if not set(data.role_ids).issubset(allowed_ids):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Super Admin can only create Admin users",
                    )

        # Company assignment for SUPERADMIN-created ADMIN
        company_id = None
        if is_superadmin:
            if not data.company_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Company is required for Admin users created by Super Admin",
                )
            company = self.session.get(Company, data.company_id)
            if not company:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Company {data.company_id} not found",
                )
            if not company.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign an inactive company",
                )
            company_id = data.company_id

        # Company assignment for ADMIN-created users (MAKER, CHECKER, AUDITOR, ADMIN)
        # ADMIN must have a company assigned; new users inherit that company automatically
        is_admin = False
        if current_user is not None:
            is_admin = any(r.name == RoleName.ADMIN for r in current_user.roles)
            if is_admin and not is_superadmin:
                if not current_user.company_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Admin must be assigned to a Company Profile before creating users",
                    )
                company = self.session.get(Company, current_user.company_id)
                if not company:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Admin's company {current_user.company_id} not found",
                    )
                if not company.is_active:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot create users: Admin's company is inactive",
                    )
                company_id = current_user.company_id

        # Determine user_level_id: use provided value, or default to "Low"
        level_id = data.user_level_id
        if level_id is None:
            default_level = self.session.exec(
                select(UserLevel).where(UserLevel.name == "Low", UserLevel.is_active == True)
            ).first()
            if default_level:
                level_id = default_level.id

        # Validate: local users must have a password
        auth_provider = data.auth_provider or "local"
        hashed_pw = None
        if auth_provider == "local":
            if not data.password:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Password is required for local users",
                )
            hashed_pw = hash_password(data.password)
        elif data.azure_object_id:
            hashed_pw = None

        user = User(
            full_name=data.full_name,
            email=data.email,
            hashed_password=hashed_pw,
            is_active=data.is_active,
            user_level_id=level_id,
            company_id=company_id,
            auth_provider=auth_provider,
            azure_object_id=data.azure_object_id,
        )
        self.session.add(user)
        self.session.flush()
        self._assign_roles(user.id, data.role_ids)
        self._assign_categories(user.id, data.category_ids, current_user)
        self.session.commit()

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.CREATE_USER,
            module=AuditModule.USERS,
            company_id=user.company_id,
            entity_name="user",
            entity_id=str(user.id),
            new_value={"email": data.email, "full_name": data.full_name},
            description=f"Created user {data.email}",
            is_success=True,
        )

        # Re-fetch with eager load so roles are in memory
        return self.get_user(user.id)

    def update_user(self, user_id: int, data: UserUpdate, current_user: User = None) -> UserRead:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        # Capture old values for audit
        old_values = {
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
        }

        if data.full_name is not None:
            user.full_name = data.full_name
        if data.email is not None:
            dup = self.session.exec(
                select(User).where(User.email == data.email, User.id != user_id)
            ).first()
            if dup:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{data.email}' is already taken",
                )
            user.email = data.email
        if data.is_active is not None:
            user.is_active = data.is_active

        if data.role_ids is not None:
            # SUPERADMIN cannot change roles of any user — silently skip
            if current_user is not None:
                is_superadmin = any(r.name == RoleName.SUPERADMIN for r in current_user.roles)
                if is_superadmin:
                    pass  # ignore role_ids, allow other fields to update
                else:
                    for link in self.session.exec(
                        select(UserRoleLink).where(UserRoleLink.user_id == user_id)
                    ).all():
                        self.session.delete(link)
                    self.session.flush()
                    self._assign_roles(user_id, data.role_ids)
            else:
                for link in self.session.exec(
                    select(UserRoleLink).where(UserRoleLink.user_id == user_id)
                ).all():
                    self.session.delete(link)
                self.session.flush()
                self._assign_roles(user_id, data.role_ids)

        if data.category_ids is not None:
            # SUPERADMIN cannot change category assignments — silently skip
            if current_user is not None:
                is_superadmin = any(r.name == RoleName.SUPERADMIN for r in current_user.roles)
                if is_superadmin:
                    pass  # ignore category_ids, allow other fields to update
                else:
                    for link in self.session.exec(
                        select(UserCategoryLink).where(UserCategoryLink.user_id == user_id)
                    ).all():
                        self.session.delete(link)
                    self.session.flush()
                    self._assign_categories(user_id, data.category_ids, current_user)
            else:
                for link in self.session.exec(
                    select(UserCategoryLink).where(UserCategoryLink.user_id == user_id)
                ).all():
                    self.session.delete(link)
                self.session.flush()
                self._assign_categories(user_id, data.category_ids, current_user)

        if data.user_level_id is not None or (hasattr(data, 'user_level_id') and 'user_level_id' in data.model_fields_set):
            user.user_level_id = data.user_level_id

        # Company assignment — only for ADMIN users
        if 'company_id' in data.model_fields_set:
            # Defense-in-depth: admin cannot change their own company
            if current_user is not None and current_user.id == user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin cannot change their own company",
                )
            target_user_roles = [r.name for r in user.roles]
            if RoleName.ADMIN in target_user_roles:
                if data.company_id is not None:
                    company = self.session.get(Company, data.company_id)
                    if not company:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Company {data.company_id} not found",
                        )
                    if not company.is_active:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Cannot assign an inactive company",
                        )
                user.company_id = data.company_id

        user.updated_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()

        # Log audit event
        new_values = {
            "full_name": user.full_name,
            "email": user.email,
            "is_active": user.is_active,
        }
        AuditService(self.session).log_event(
            action=AuditAction.UPDATE_USER,
            module=AuditModule.USERS,
            company_id=user.company_id,
            entity_name="user",
            entity_id=str(user_id),
            old_value=old_values,
            new_value=new_values,
            description=f"Updated user {user.email}",
            is_success=True,
        )

        return self.get_user(user_id)

    def delete_user(self, user_id: int) -> None:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        email = user.email
        self.session.delete(user)
        self.session.commit()

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.DELETE_USER,
            module=AuditModule.USERS,
            company_id=user.company_id,
            entity_name="user",
            entity_id=str(user_id),
            old_value={"email": email},
            description=f"Deleted user {email}",
            is_success=True,
        )

    def deactivate_user(self, user_id: int) -> UserRead:
        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")
        user.is_active = False
        user.updated_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.DEACTIVATE_USER,
            module=AuditModule.USERS,
            company_id=user.company_id,
            entity_name="user",
            entity_id=str(user_id),
            old_value={"is_active": True},
            new_value={"is_active": False},
            description=f"Deactivated user {user.email}",
            is_success=True,
        )

        return self.get_user(user_id)

    def reset_password(self, user_id: int, current_admin_id: int) -> str:
        """Admin resets a user's password. Returns the plain-text temp password."""
        from notifications.service import EmailService
        from notifications.templates import build_password_reset_email

        user = self.session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail=f"User {user_id} not found")

        if user.auth_provider == "azure_ad":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot reset password for Azure AD users",
            )

        if user.id == current_admin_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin cannot reset their own password",
            )

        alphabet = string.ascii_letters + string.digits
        temp_password = "".join(secrets.choice(alphabet) for _ in range(12))

        user.hashed_password = hash_password(temp_password)
        user.must_change_password = True
        user.updated_at = datetime.utcnow()
        self.session.add(user)
        self.session.commit()

        AuditService(self.session).log_event(
            action=AuditAction.PASSWORD_RESET,
            module=AuditModule.USERS,
            company_id=user.company_id,
            entity_name="user",
            entity_id=str(user.id),
            description=f"Admin reset password for user {user.email}",
            is_success=True,
        )

        email_service = EmailService(self.session)
        subject, html_body, text_body = build_password_reset_email(
            user.full_name, temp_password
        )
        email_service._send_smtp(user.email, subject, html_body, text_body)

        return temp_password

    def _assign_roles(self, user_id: int, role_ids: List[int]) -> None:
        for role_id in role_ids:
            role = self.session.get(Role, role_id)
            if not role:
                raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
            self.session.add(UserRoleLink(user_id=user_id, role_id=role_id))

    def _assign_categories(self, user_id: int, category_ids: List[int], current_user: User = None) -> None:
        for category_id in category_ids:
            category = self.session.get(Category, category_id)
            if not category:
                raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
            # Admin can only assign categories from their own company — silently skip others
            if current_user is not None and current_user.is_admin():
                is_superadmin = any(r.name == RoleName.SUPERADMIN for r in current_user.roles)
                if not is_superadmin and category.company_id != current_user.company_id:
                    continue
            self.session.add(UserCategoryLink(user_id=user_id, category_id=category_id))

    # ──────────────────────────────────────────
    # Roles
    # ──────────────────────────────────────────

    def list_roles(self) -> List[RoleRead]:
        roles = self.session.exec(
            select(Role).options(selectinload(Role.permissions))  # type: ignore[arg-type]
        ).all()
        return [_role_to_read(r) for r in roles]

    def get_role(self, role_id: int) -> RoleRead:
        role = self.session.exec(
            select(Role)
            .where(Role.id == role_id)
            .options(selectinload(Role.permissions))  # type: ignore[arg-type]
        ).first()
        if not role:
            raise HTTPException(status_code=404, detail=f"Role {role_id} not found")
        return _role_to_read(role)

    def create_role(self, data: RoleCreate) -> RoleRead:
        # Prevent creation of protected system roles
        if data.name == RoleName.SUPERADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create Super Admin role via API",
            )
        exists = self.session.exec(
            select(Role).where(Role.name == data.name)
        ).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{data.name}' already exists",
            )
        role = Role(name=data.name, description=data.description)
        self.session.add(role)
        self.session.flush()
        for perm_id in data.permission_ids:
            perm = self.session.get(Permission, perm_id)
            if not perm:
                raise HTTPException(status_code=404, detail=f"Permission {perm_id} not found")
            self.session.add(RolePermissionLink(role_id=role.id, permission_id=perm_id))
        self.session.commit()

        # Log audit event
        AuditService(self.session).log_event(
            action=AuditAction.CREATE_ROLE,
            module=AuditModule.USERS,
            company_id=None,
            entity_name="role",
            entity_id=str(role.id),
            new_value={"name": data.name.value if hasattr(data.name, "value") else str(data.name)},
            description=f"Created role {data.name}",
            is_success=True,
        )

        return self.get_role(role.id)

    # ──────────────────────────────────────────
    # Permissions
    # ──────────────────────────────────────────

    def list_permissions(self) -> List[PermissionRead]:
        perms = self.session.exec(select(Permission)).all()
        return [PermissionRead(id=p.id, action=p.action, description=p.description) for p in perms]
