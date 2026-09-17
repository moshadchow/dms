"""add correspondence attachments table

Revision ID: b3c4d5e6f7a8
Revises: f8a9b0c1d2e3
Create Date: 2026-09-17 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'f8a9b0c1d2e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'correspondence_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('correspondence_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('attachment_type', sa.String(length=30), nullable=False, server_default='supporting'),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['correspondence_id'], ['correspondences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('correspondence_id', 'document_id', name='uq_corr_attachment_doc'),
    )
    op.create_index(op.f('ix_correspondence_attachments_correspondence_id'), 'correspondence_attachments', ['correspondence_id'], unique=False)
    op.create_index(op.f('ix_correspondence_attachments_document_id'), 'correspondence_attachments', ['document_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_correspondence_attachments_document_id'), table_name='correspondence_attachments')
    op.drop_index(op.f('ix_correspondence_attachments_correspondence_id'), table_name='correspondence_attachments')
    op.drop_table('correspondence_attachments')
