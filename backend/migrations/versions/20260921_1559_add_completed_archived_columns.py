"""Add completed_at, completed_by_id, archived_at, archived_by_id to correspondences

Revision ID: 9d48cbf08938
Revises: d6e7f8a9b0c1
Create Date: 2026-09-21 15:59:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d48cbf08938'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('correspondences', sa.Column('completed_at', sa.DateTime(), nullable=True))
    op.add_column('correspondences', sa.Column('completed_by_id', sa.Integer(), nullable=True))
    op.add_column('correspondences', sa.Column('archived_at', sa.DateTime(), nullable=True))
    op.add_column('correspondences', sa.Column('archived_by_id', sa.Integer(), nullable=True))

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_correspondences_completed_by_id_users',
        'correspondences', 'users',
        ['completed_by_id'], ['id']
    )
    op.create_foreign_key(
        'fk_correspondences_archived_by_id_users',
        'correspondences', 'users',
        ['archived_by_id'], ['id']
    )


def downgrade() -> None:
    op.drop_constraint('fk_correspondences_completed_by_id_users', 'correspondences', type_='foreignkey')
    op.drop_constraint('fk_correspondences_archived_by_id_users', 'correspondences', type_='foreignkey')
    op.drop_column('correspondences', 'archived_by_id')
    op.drop_column('correspondences', 'archived_at')
    op.drop_column('correspondences', 'completed_by_id')
    op.drop_column('correspondences', 'completed_at')