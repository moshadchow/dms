"""Remove orphaned directories pointing to deleted categories

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a3b4c5d6e7f8"
down_revision: Union[str, None] = "f2a3b4c5d6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM documents WHERE directory_id IN "
        "(SELECT id FROM directories WHERE category_id NOT IN (SELECT id FROM categories))"
    )
    op.execute(
        "DELETE FROM directories WHERE category_id NOT IN (SELECT id FROM categories)"
    )


def downgrade() -> None:
    pass  # Cannot recover deleted orphaned rows
