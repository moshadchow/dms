"""add HTML to filetype enum

Revision ID: a1b2c3d4e5f8
Revises: f6a7b8c9d1e2
Create Date: 2026-08-13 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f8"
down_revision: Union[str, None] = "f6a7b8c9d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE filetype ADD VALUE IF NOT EXISTS 'HTML'")


def downgrade() -> None:
    pass
