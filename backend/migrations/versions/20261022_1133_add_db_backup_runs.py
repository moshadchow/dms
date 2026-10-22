"""add db_backup_runs table (spec 36)

Revision ID: 20261022_1133
Revises: 20261021_0900
Create Date: 2026-10-22 11:33:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20261022_1133'
down_revision = '20261021_0900'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'db_backup_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        # status/trigger are `str, Enum` members, so SQLAlchemy persists the
        # enum *NAME* (upper case), not .value — server_default must therefore
        # be 'PENDING'/'MANUAL'. A lower-case default here would be accepted
        # on write but raise LookupError on ORM read-back.
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('trigger', sa.String(length=10), nullable=False, server_default='MANUAL'),
        sa.Column('triggered_by', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('dump_path', sa.String(length=500), nullable=True),
        sa.Column('dump_size_bytes', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('pg_dump_version', sa.String(length=60), nullable=True),
        sa.Column('error_message', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['triggered_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_db_backup_runs_status', 'db_backup_runs', ['status'], unique=False)
    op.create_index('ix_db_backup_runs_created_at', 'db_backup_runs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_db_backup_runs_created_at', table_name='db_backup_runs')
    op.drop_index('ix_db_backup_runs_status', table_name='db_backup_runs')
    op.drop_table('db_backup_runs')
