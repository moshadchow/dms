"""add company_id to audit_logs table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-09-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_audit_logs_company_id",
        "audit_logs",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index(
        "ix_audit_logs_company_id",
        "audit_logs",
        ["company_id"],
    )

    # Backfill existing audit records from users.company_id
    op.execute(
        """
        UPDATE audit_logs
        SET company_id = (
            SELECT users.company_id
            FROM users
            WHERE users.id = audit_logs.user_id
            AND users.company_id IS NOT NULL
        )
        WHERE audit_logs.user_id IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM users
            WHERE users.id = audit_logs.user_id
            AND users.company_id IS NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_company_id", table_name="audit_logs")
    op.drop_constraint("fk_audit_logs_company_id", "audit_logs", type_="foreignkey")
    op.drop_column("audit_logs", "company_id")
