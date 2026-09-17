"""add correspondence tables

Revision ID: c7e8f9a0b1c2
Revises: f1a2b3c4d5e6
Create Date: 2026-09-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c7e8f9a0b1c2'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── correspondence_sequences ──────────────────
    op.create_table(
        'correspondence_sequences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('last_value', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('company_id', 'year', name='uq_correspondence_sequences_company_year'),
    )
    op.create_index(op.f('ix_correspondence_sequences_company_id'), 'correspondence_sequences', ['company_id'], unique=False)

    # ── correspondences ───────────────────────────
    op.create_table(
        'correspondences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('reference_number', sa.String(length=50), nullable=False),
        sa.Column('direction', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='draft'),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=False, server_default='normal'),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('sender_name', sa.String(length=255), nullable=True),
        sa.Column('sender_organization', sa.String(length=255), nullable=True),
        sa.Column('sender_email', sa.String(length=255), nullable=True),
        sa.Column('sender_phone', sa.String(length=50), nullable=True),
        sa.Column('recipient_name', sa.String(length=255), nullable=True),
        sa.Column('recipient_organization', sa.String(length=255), nullable=True),
        sa.Column('recipient_email', sa.String(length=255), nullable=True),
        sa.Column('recipient_phone', sa.String(length=50), nullable=True),
        sa.Column('date_sent', sa.DateTime(), nullable=True),
        sa.Column('date_received', sa.DateTime(), nullable=True),
        sa.Column('response_required', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('response_deadline', sa.DateTime(), nullable=True),
        sa.Column('response_received', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('parent_correspondence_id', sa.Integer(), nullable=True),
        sa.Column('author_signature_id', sa.Integer(), nullable=True),
        sa.Column('workflow_instance_id', sa.Integer(), nullable=True),
        sa.Column('dispatch_method', sa.String(length=20), nullable=True),
        sa.Column('dispatch_reference', sa.String(length=255), nullable=True),
        sa.Column('dispatched_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_correspondence_id'], ['correspondences.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['author_signature_id'], ['signatures.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['workflow_instance_id'], ['workflow_instances.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id'),
        sa.UniqueConstraint('reference_number'),
    )
    op.create_index(op.f('ix_correspondences_category_id'), 'correspondences', ['category_id'], unique=False)
    op.create_index(op.f('ix_correspondences_company_id'), 'correspondences', ['company_id'], unique=False)
    op.create_index(op.f('ix_correspondences_created_by'), 'correspondences', ['created_by'], unique=False)
    op.create_index(op.f('ix_correspondences_date_received'), 'correspondences', ['date_received'], unique=False)
    op.create_index(op.f('ix_correspondences_date_sent'), 'correspondences', ['date_sent'], unique=False)
    op.create_index(op.f('ix_correspondences_direction'), 'correspondences', ['direction'], unique=False)
    op.create_index(op.f('ix_correspondences_parent_correspondence_id'), 'correspondences', ['parent_correspondence_id'], unique=False)
    op.create_index(op.f('ix_correspondences_priority'), 'correspondences', ['priority'], unique=False)
    op.create_index(op.f('ix_correspondences_reference_number'), 'correspondences', ['reference_number'], unique=False)
    op.create_index(op.f('ix_correspondences_response_deadline'), 'correspondences', ['response_deadline'], unique=False)
    op.create_index(op.f('ix_correspondences_status'), 'correspondences', ['status'], unique=False)
    op.create_index(op.f('ix_correspondences_subject'), 'correspondences', ['subject'], unique=False)
    op.create_index(op.f('ix_correspondences_workflow_instance_id'), 'correspondences', ['workflow_instance_id'], unique=False)

    # Composite indexes
    op.create_index('ix_corr_company_status', 'correspondences', ['company_id', 'status'], unique=False)
    op.create_index('ix_corr_company_direction', 'correspondences', ['company_id', 'direction'], unique=False)
    op.create_index('ix_corr_company_created', 'correspondences', ['company_id', 'created_at'], unique=False)

    # ── correspondence_movements ──────────────────
    op.create_table(
        'correspondence_movements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('correspondence_id', sa.Integer(), nullable=False),
        sa.Column('from_user_id', sa.Integer(), nullable=True),
        sa.Column('to_user_id', sa.Integer(), nullable=True),
        sa.Column('from_department', sa.String(length=255), nullable=True),
        sa.Column('to_department', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('remarks', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['correspondence_id'], ['correspondences.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['from_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['to_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_correspondence_movements_correspondence_id'), 'correspondence_movements', ['correspondence_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_correspondence_movements_correspondence_id'), table_name='correspondence_movements')
    op.drop_table('correspondence_movements')

    op.drop_index('ix_corr_company_created', table_name='correspondences')
    op.drop_index('ix_corr_company_direction', table_name='correspondences')
    op.drop_index('ix_corr_company_status', table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_workflow_instance_id'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_subject'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_status'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_response_deadline'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_reference_number'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_priority'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_parent_correspondence_id'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_direction'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_date_sent'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_date_received'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_created_by'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_company_id'), table_name='correspondences')
    op.drop_index(op.f('ix_correspondences_category_id'), table_name='correspondences')
    op.drop_table('correspondences')

    op.drop_index(op.f('ix_correspondence_sequences_company_id'), table_name='correspondence_sequences')
    op.drop_table('correspondence_sequences')
