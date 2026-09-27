"""drop stale global unique index on categories.name

The initial schema migration created ``ix_categories_name`` as a UNIQUE index
on ``categories.name`` alone. Revision e3f4a5b6c7d8 later added
``uq_category_name_company`` (UNIQUE on name + company_id) but never dropped
the original global index, so both survived on the same table.

Result: a category name could only ever be used once across the whole
installation. A second company creating its own "Finance" category passed the
service-level per-company duplicate check and then hit the database
constraint, surfacing as HTTP 500 instead of 201.

This drops the global unique index and recreates it as a plain (non-unique)
index, matching ``Category.name = Field(index=True)``. Per-company uniqueness
remains enforced by ``uq_category_name_company``.

Revision ID: 7c8d9e0f1a2b
Revises: 9d48cbf08938
Create Date: 2026-09-27 15:53:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7c8d9e0f1a2b"
down_revision: Union[str, None] = "9d48cbf08938"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS/IF NOT EXISTS keep this safe on databases where the index was
    # already corrected by hand.
    op.execute("DROP INDEX IF EXISTS ix_categories_name")
    op.execute("CREATE INDEX IF NOT EXISTS ix_categories_name ON categories (name)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_categories_name")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_categories_name ON categories (name)")
