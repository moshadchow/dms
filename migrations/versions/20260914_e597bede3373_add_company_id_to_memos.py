"""add company_id to memos

Revision ID: e597bede3373
Revises: e3f4a5b6c7d8
Create Date: 2026-09-14 12:30:55.095320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e597bede3373'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add company_id column to memos table
    op.add_column('memos', sa.Column('company_id', sa.Integer(), nullable=True))
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_memos_company_id',
        'memos',
        'companies',
        ['company_id'],
        ['id'],
        ondelete='SET NULL'
    )
    # Add index for company_id
    op.create_index(op.f('ix_memos_company_id'), 'memos', ['company_id'], unique=False)

    # Backfill existing memos with company_id from their author
    op.execute("""
        UPDATE memos m
        SET company_id = u.company_id
        FROM users u
        WHERE m.created_by = u.id AND u.company_id IS NOT NULL
    """)


def downgrade() -> None:
    # Remove index
    op.drop_index(op.f('ix_memos_company_id'), table_name='memos')
    # Remove foreign key
    op.drop_constraint('fk_memos_company_id', 'memos', type_='foreignkey')
    # Remove column
    op.drop_column('memos', 'company_id')