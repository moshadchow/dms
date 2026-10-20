"""create companies table

Revision ID: d4e5f6a7b8c0
Revises: c3d4e5f6a7b9
Create Date: 2026-09-08 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c0"
down_revision: Union[str, None] = "c3d4e5f6a7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sqlmodel.SQLModel.metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("full_name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column("short_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("address", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True),
        sa.Column("contact_person", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("contact_no", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True),
        sa.Column("email_address", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_companies_company_id"), "companies", ["company_id"], unique=True)
    op.create_index(op.f("ix_companies_short_name"), "companies", ["short_name"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_companies_short_name"), table_name="companies")
    op.drop_index(op.f("ix_companies_company_id"), table_name="companies")
    op.drop_table("companies")
