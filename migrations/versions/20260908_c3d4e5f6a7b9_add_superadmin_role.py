"""add SUPERADMIN to rolename enum

Revision ID: c3d4e5f6a7b9
Revises: b2c3d4e5f6a8
Create Date: 2026-09-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b9"
down_revision: Union[str, None] = "b2c3d4e5f6a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("ALTER TYPE rolename ADD VALUE 'SUPERADMIN'")
    # SQLite stores enums as VARCHAR — no schema change needed.


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        # PostgreSQL doesn't support DROP VALUE for enums directly.
        # Recreate the enum type without SUPERADMIN.
        op.execute("ALTER TABLE roles ALTER COLUMN name TYPE VARCHAR(255)")
        op.execute("DROP TYPE IF EXISTS rolename")
        op.execute(
            "CREATE TYPE rolename AS ENUM ('ADMIN', 'MAKER', 'CHECKER', 'AUDITOR')"
        )
        op.execute(
            "ALTER TABLE roles ALTER COLUMN name TYPE rolename USING name::rolename"
        )
    # SQLite: no-op.
