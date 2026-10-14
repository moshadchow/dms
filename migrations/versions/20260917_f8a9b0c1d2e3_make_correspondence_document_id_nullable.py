"""make correspondence document_id nullable

Revision ID: f8a9b0c1d2e3
Revises: c7e8f9a0b1c2
Create Date: 2026-09-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f8a9b0c1d2e3'
down_revision: Union[str, None] = 'c7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('correspondences', 'document_id',
                     existing_type=sa.Integer(),
                     nullable=True)


def downgrade() -> None:
    op.alter_column('correspondences', 'document_id',
                     existing_type=sa.Integer(),
                     nullable=False)
