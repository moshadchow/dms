"""add document_type to workflow_definitions table

Revision ID: d6e7f8a9b0c1
Revises: b3c4d5e6f7a8
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "d6e7f8a9b0c1"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_definitions",
        sa.Column("document_type", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_workflow_definitions_document_type",
        "workflow_definitions",
        ["document_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_definitions_document_type", table_name="workflow_definitions")
    op.drop_column("workflow_definitions", "document_type")
