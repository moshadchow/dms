"""scope user email uniqueness to company

Revision ID: b7c8d9e0f1a2
Revises: da9d9e3a15d9
Create Date: 2026-11-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, None] = "da9d9e3a15d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The original index made email addresses globally unique.  Keep a regular
    # lookup index for authentication while enforcing uniqueness only inside a
    # company, which is the tenancy boundary for users.
    op.drop_index("ix_users_email", table_name="users")
    op.create_unique_constraint(
        "uq_users_company_email", "users", ["company_id", "email"]
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_constraint("uq_users_company_email", "users", type_="unique")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
