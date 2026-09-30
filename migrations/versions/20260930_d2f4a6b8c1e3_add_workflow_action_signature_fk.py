"""add FK for workflow_actions.signature_id

The column was created as a plain nullable Integer in c3d4e5f6a7b8 while the
SQLModel relationship declares a foreign key. Add the constraint so an approval
can never reference a missing signature (orphan-null first for safety).

Revision ID: d2f4a6b8c1e3
Revises: b7e4f2a9c3d1
Create Date: 2026-09-30 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "d2f4a6b8c1e3"
down_revision: Union[str, None] = "b7e4f2a9c3d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "UPDATE workflow_actions SET signature_id = NULL "
        "WHERE signature_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM signatures WHERE signatures.id = workflow_actions.signature_id)"
    )
    op.create_foreign_key(
        "fk_workflow_actions_signature_id",
        "workflow_actions",
        "signatures",
        ["signature_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_workflow_actions_signature_id",
        "workflow_actions",
        type_="foreignkey",
    )
