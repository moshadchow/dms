"""Remove document_category_id from workflow_definitions

Revision ID: e1f2a3b4c5d6
Revises: d5e6f7a8b9c0
Create Date: 2026-08-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_workflow_definitions_document_category_id", table_name="workflow_definitions")
    op.drop_column("workflow_definitions", "document_category_id")


def downgrade() -> None:
    op.add_column(
        "workflow_definitions",
        sa.Column("document_category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
    )
    op.create_index(
        "ix_workflow_definitions_document_category_id",
        "workflow_definitions",
        ["document_category_id"],
    )
