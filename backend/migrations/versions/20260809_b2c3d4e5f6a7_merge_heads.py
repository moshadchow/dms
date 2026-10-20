"""merge audit and azure_ad heads

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6, f7a8b9c0d1e2
Create Date: 2026-08-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = ("a1b2c3d4e5f6", "f7a8b9c0d1e2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
