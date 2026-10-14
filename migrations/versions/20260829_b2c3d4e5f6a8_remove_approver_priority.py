"""remove priority column from workflow_step_approvers

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f9
Create Date: 2026-08-29 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a8"
down_revision: Union[str, None] = "a1b2c3d4e5f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("workflow_step_approvers", "priority")


def downgrade() -> None:
    op.add_column(
        "workflow_step_approvers",
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
