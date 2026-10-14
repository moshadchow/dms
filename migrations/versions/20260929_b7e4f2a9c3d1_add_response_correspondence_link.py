"""Add response_correspondence_id link to correspondences

Records which reply answered an inbound correspondence. Set on reply
submission; cleared when that reply is rejected/returned/cancelled.

Revision ID: b7e4f2a9c3d1
Revises: 7c8d9e0f1a2b
Create Date: 2026-09-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e4f2a9c3d1'
down_revision: Union[str, None] = '7c8d9e0f1a2b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'correspondences',
        sa.Column('response_correspondence_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_correspondences_response_correspondence_id',
        'correspondences', 'correspondences',
        ['response_correspondence_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_correspondences_response_correspondence_id',
        'correspondences', type_='foreignkey',
    )
    op.drop_column('correspondences', 'response_correspondence_id')
