"""
Seed Script
───────────
Populates the database with the default:
  • Permissions (view, download, create, update, delete)
  • Roles (Admin, Maker, Checker, Auditor) with correct permission sets
  • Initial Admin user

Run once after `alembic upgrade head`:
    python seed.py
"""

import sys

from sqlmodel import Session, select

from core.config import settings
from core.database import engine
from core.security import hash_password

# Import all models to ensure SQLModel metadata is populated
from users.models import (
    Permission,
    PermissionAction,
    Role,
    RoleName,
    RolePermissionLink,
    User,
    UserRoleLink,
)


# ──────────────────────────────────────────────
# Default permission matrix
# ──────────────────────────────────────────────

ROLE_PERMISSIONS: dict[RoleName, list[PermissionAction]] = {
    RoleName.ADMIN:   [PermissionAction.VIEW, PermissionAction.DOWNLOAD,
                       PermissionAction.CREATE, PermissionAction.UPDATE,
                       PermissionAction.DELETE],
    RoleName.MAKER:   [PermissionAction.VIEW, PermissionAction.DOWNLOAD,
                       PermissionAction.CREATE, PermissionAction.UPDATE],
    RoleName.CHECKER: [PermissionAction.VIEW, PermissionAction.DOWNLOAD,
                       PermissionAction.UPDATE],
    RoleName.AUDITOR: [PermissionAction.VIEW, PermissionAction.DOWNLOAD],
}

ROLE_DESCRIPTIONS: dict[RoleName, str] = {
    RoleName.ADMIN:   "Full system access; manages users, roles, and categories",
    RoleName.MAKER:   "Creates and uploads documents and directories",
    RoleName.CHECKER: "Reviews and updates documents",
    RoleName.AUDITOR: "Read-only access for compliance and auditing",
}

DEFAULT_ADMIN = {
    "full_name": "System Administrator",
    "email":     "admin@dms.local",
    "password":  "Admin@1234",   # ← change before production
}


def seed() -> None:
    with Session(engine) as session:
        # ── 1. Permissions ────────────────────
        perm_map: dict[PermissionAction, Permission] = {}

        for action in PermissionAction:
            existing = session.exec(
                select(Permission).where(Permission.action == action)
            ).first()

            if existing:
                perm_map[action] = existing
            else:
                perm = Permission(action=action)
                session.add(perm)
                session.flush()
                perm_map[action] = perm
                print(f"  [+] Permission: {action.value}")

        # ── 2. Roles + Permission links ────────
        role_map: dict[RoleName, Role] = {}

        for role_name, actions in ROLE_PERMISSIONS.items():
            existing = session.exec(
                select(Role).where(Role.name == role_name)
            ).first()

            if existing:
                role_map[role_name] = existing
                print(f"  [=] Role already exists: {role_name.value}")
            else:
                role = Role(
                    name=role_name,
                    description=ROLE_DESCRIPTIONS[role_name],
                )
                session.add(role)
                session.flush()

                for action in actions:
                    session.add(
                        RolePermissionLink(
                            role_id=role.id,
                            permission_id=perm_map[action].id,
                        )
                    )

                role_map[role_name] = role
                print(f"  [+] Role: {role_name.value}  ({', '.join(a.value for a in actions)})")

        # ── 3. Default Admin user ─────────────
        admin_exists = session.exec(
            select(User).where(User.email == DEFAULT_ADMIN["email"])
        ).first()

        if not admin_exists:
            admin_user = User(
                full_name=DEFAULT_ADMIN["full_name"],
                email=DEFAULT_ADMIN["email"],
                hashed_password=hash_password(DEFAULT_ADMIN["password"]),
            )
            session.add(admin_user)
            session.flush()

            session.add(
                UserRoleLink(
                    user_id=admin_user.id,
                    role_id=role_map[RoleName.ADMIN].id,
                )
            )
            print(f"  [+] Admin user created: {DEFAULT_ADMIN['email']}")
        else:
            print(f"  [=] Admin user already exists: {DEFAULT_ADMIN['email']}")

        session.commit()
        print("\n✅  Seed complete.")


if __name__ == "__main__":
    print("🌱  Seeding database...\n")
    try:
        seed()
    except Exception as exc:
        print(f"\n❌  Seed failed: {exc}", file=sys.stderr)
        sys.exit(1)
