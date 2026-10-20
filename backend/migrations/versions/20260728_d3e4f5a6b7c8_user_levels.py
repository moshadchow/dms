"""user_levels

Revision ID: d3e4f5a6b7c8
Revises: c1d2e3f4a5b6
Create Date: 2026-07-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_levels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(op.f("ix_user_levels_name"), "user_levels", ["name"], unique=True)

    op.add_column(
        "users",
        sa.Column(
            "user_level_id",
            sa.Integer(),
            sa.ForeignKey("user_levels.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(op.f("ix_users_user_level_id"), "users", ["user_level_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_users_user_level_id"), table_name="users")
    op.drop_column("users", "user_level_id")
    op.drop_index(op.f("ix_user_levels_name"), table_name="user_levels")
    op.drop_table("user_levels")
