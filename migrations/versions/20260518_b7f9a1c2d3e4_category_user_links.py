"""add user category links

Revision ID: b7f9a1c2d3e4
Revises: 02d41f17a806
Create Date: 2026-05-18 23:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b7f9a1c2d3e4"
down_revision: Union[str, None] = "02d41f17a806"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_category_links",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id", "category_id"),
    )
    op.create_index(
        "ix_user_category_links_user_id",
        "user_category_links",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_category_links_category_id",
        "user_category_links",
        ["category_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_category_links_category_id", table_name="user_category_links")
    op.drop_index("ix_user_category_links_user_id", table_name="user_category_links")
    op.drop_table("user_category_links")
