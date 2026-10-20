"""add company_id and created_by to categories table

Revision ID: e3f4a5b6c7d8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-10 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Add columns as nullable initially (for production backfill)
    op.add_column(
        "categories",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "categories",
        sa.Column("created_by", sa.Integer(), nullable=True),
    )

    # Step 2: Add composite unique constraint
    op.create_unique_constraint(
        "uq_category_name_company",
        "categories",
        ["name", "company_id"],
    )

    # Step 3: Add foreign key constraints
    op.create_foreign_key(
        "fk_categories_company_id",
        "categories",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_categories_created_by",
        "categories",
        "users",
        ["created_by"],
        ["id"],
    )

    # Step 4: Add indexes
    op.create_index(
        "ix_categories_company_id",
        "categories",
        ["company_id"],
    )
    op.create_index(
        "ix_categories_created_by",
        "categories",
        ["created_by"],
    )

    # NOTE: Backfill of company_id and created_by for existing categories
    # should be done as a separate data migration step after this schema migration.
    # For new deployments, columns will be populated by application logic.


def downgrade() -> None:
    op.drop_index("ix_categories_created_by", table_name="categories")
    op.drop_index("ix_categories_company_id", table_name="categories")
    op.drop_constraint("fk_categories_created_by", "categories", type_="foreignkey")
    op.drop_constraint("fk_categories_company_id", "categories", type_="foreignkey")
    op.drop_constraint("uq_category_name_company", "categories", type_="unique")
    op.drop_column("categories", "created_by")
    op.drop_column("categories", "company_id")
