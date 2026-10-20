"""add antivirus scan tables and document av_scan_id

Revision ID: 20261018_153000
Revises: e8f1a2b3c4d5
Create Date: 2026-10-18 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20261018_153000'
down_revision = 'e8f1a2b3c4d5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create antivirus_scans table
    op.create_table(
        'antivirus_scans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(length=512), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('scan_engine', sa.String(length=100), nullable=False),
        sa.Column('scan_status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('threat_name', sa.String(length=255), nullable=True),
        sa.Column('scan_duration_ms', sa.Integer(), nullable=True),
        sa.Column('scanned_at', sa.DateTime(), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_antivirus_scans_company_id', 'antivirus_scans', ['company_id'], unique=False)
    op.create_index('ix_antivirus_scans_file_hash', 'antivirus_scans', ['file_hash'], unique=False)
    op.create_index('ix_antivirus_scans_scan_status', 'antivirus_scans', ['scan_status'], unique=False)
    op.create_index('ix_antivirus_scans_storage_path', 'antivirus_scans', ['storage_path'], unique=False)

    # Add av_scan_id column to documents table
    op.add_column('documents', sa.Column('av_scan_id', sa.Integer(), nullable=True))
    op.create_index('ix_documents_av_scan_id', 'documents', ['av_scan_id'], unique=False)
    op.create_foreign_key(
        'fk_documents_av_scan_id_antivirus_scans',
        'documents', 'antivirus_scans',
        ['av_scan_id'], ['id']
    )


def downgrade() -> None:
    # Remove av_scan_id from documents
    op.drop_constraint('fk_documents_av_scan_id_antivirus_scans', 'documents', type_='foreignkey')
    op.drop_index('ix_documents_av_scan_id', table_name='documents')
    op.drop_column('documents', 'av_scan_id')

    # Drop antivirus_scans table
    op.drop_index('ix_antivirus_scans_storage_path', table_name='antivirus_scans')
    op.drop_index('ix_antivirus_scans_scan_status', table_name='antivirus_scans')
    op.drop_index('ix_antivirus_scans_file_hash', table_name='antivirus_scans')
    op.drop_index('ix_antivirus_scans_company_id', table_name='antivirus_scans')
    op.drop_table('antivirus_scans')