"""add company_id to workflow_definitions table

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
Create Date: 2026-09-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflow_definitions",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflow_definitions_company_id",
        "workflow_definitions",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index(
        "ix_workflow_definitions_company_id",
        "workflow_definitions",
        ["company_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_workflow_definitions_company_id", table_name="workflow_definitions")
    op.drop_constraint("fk_workflow_definitions_company_id", "workflow_definitions", type_="foreignkey")
    op.drop_column("workflow_definitions", "company_id")
