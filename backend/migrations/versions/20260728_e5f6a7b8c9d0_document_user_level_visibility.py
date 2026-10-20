"""document user level visibility

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-07-28 01:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_user_level_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "document_id",
            sa.Integer(),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_level_id",
            sa.Integer(),
            sa.ForeignKey("user_levels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        op.f("ix_document_user_level_links_document_id"),
        "document_user_level_links",
        ["document_id"],
    )
    op.create_index(
        op.f("ix_document_user_level_links_user_level_id"),
        "document_user_level_links",
        ["user_level_id"],
    )
    op.create_index(
        "uq_doc_user_level",
        "document_user_level_links",
        ["document_id", "user_level_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_doc_user_level", table_name="document_user_level_links")
    op.drop_index(op.f("ix_document_user_level_links_user_level_id"), table_name="document_user_level_links")
    op.drop_index(op.f("ix_document_user_level_links_document_id"), table_name="document_user_level_links")
    op.drop_table("document_user_level_links")
