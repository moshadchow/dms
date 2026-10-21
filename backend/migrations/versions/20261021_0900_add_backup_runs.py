"""add backup_runs table (spec 35)

Revision ID: 20261021_0900
Revises: 20261018_153000
Create Date: 2026-10-21 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261021_0900'
down_revision = '20261018_153000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'backup_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('trigger', sa.String(length=10), nullable=False, server_default='manual'),
        sa.Column('triggered_by', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('file_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('archive_path', sa.String(length=500), nullable=True),
        sa.Column('archive_size_bytes', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_backup_runs_company_id', 'backup_runs', ['company_id'], unique=False)
    op.create_index('ix_backup_runs_status', 'backup_runs', ['status'], unique=False)
    op.create_index('ix_backup_runs_created_at', 'backup_runs', ['created_at'], unique=False)
    op.create_index('ix_backup_runs_company_created', 'backup_runs', ['company_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_backup_runs_company_created', table_name='backup_runs')
    op.drop_index('ix_backup_runs_created_at', table_name='backup_runs')
    op.drop_index('ix_backup_runs_status', table_name='backup_runs')
    op.drop_index('ix_backup_runs_company_id', table_name='backup_runs')
    op.drop_table('backup_runs')
