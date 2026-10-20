"""azure_ad_authentication

Revision ID: a1b2c3d4e5f6
Revises: e5f6a7b8c9d0
Create Date: 2026-07-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # auth_provider: "local" or "azure_ad", defaults to "local" for existing rows
    op.add_column(
        "users",
        sa.Column(
            "auth_provider",
            sa.String(length=20),
            nullable=False,
            server_default="local",
        ),
    )
    op.create_index(
        "ix_users_auth_provider", "users", ["auth_provider"], unique=False,
    )

    # Azure AD identity columns (all nullable — only set for Azure-linked users)
    op.add_column(
        "users",
        sa.Column("azure_object_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_users_azure_object_id",
        "users",
        ["azure_object_id"],
        unique=True,
        postgresql_where=sa.text("azure_object_id IS NOT NULL"),
    )

    op.add_column(
        "users",
        sa.Column("azure_tenant_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("azure_display_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("azure_last_login_at", sa.DateTime(), nullable=True),
    )

    # Make hashed_password nullable so Azure AD users can exist without one
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=True,
        server_default=None,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(length=255),
        nullable=False,
        server_default="",
    )
    op.drop_index("ix_users_azure_object_id", table_name="users")
    op.drop_column("users", "azure_last_login_at")
    op.drop_column("users", "azure_display_name")
    op.drop_column("users", "azure_tenant_id")
    op.drop_column("users", "azure_object_id")
    op.drop_index("ix_users_auth_provider", table_name="users")
    op.drop_column("users", "auth_provider")
