"""drop memo to_recipients and from_name columns

Revision ID: c4d5e6f7a8b9
Revises: a1b2c3d4e5f8
Create Date: 2026-08-13 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "a1b2c3d4e5f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("memos", "to_recipients")
    op.drop_column("memos", "from_name")


def downgrade() -> None:
    op.add_column("memos", sa.Column("to_recipients", sa.String(length=500), nullable=False))
    op.add_column("memos", sa.Column("from_name", sa.String(length=255), nullable=False))
