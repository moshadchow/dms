"""add cancelled to workflowstatus enum

Revision ID: e5f6a7b8c9d1
Revises: d4e5f6a7b8c9
Create Date: 2026-08-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e5f6a7b8c9d1"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a transaction block in PG.
    # Switch to AUTOCOMMIT for this statement.
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(
        sa.text("ALTER TYPE workflowstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")
    )


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an enum type.
    # A full downgrade would require recreating the enum type.
    pass
