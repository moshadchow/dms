"""add azure config to companies

Revision ID: f1a2b3c4d5e6
Revises: e597bede3373
Create Date: 2026-09-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e597bede3373"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("azure_client_id", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column("companies", sa.Column("azure_client_secret", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=True))
    op.add_column("companies", sa.Column("azure_tenant_id", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column("companies", sa.Column("azure_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("companies", sa.Column("azure_default_role_name", sqlmodel.sql.sqltypes.AutoString(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "azure_default_role_name")
    op.drop_column("companies", "azure_enabled")
    op.drop_column("companies", "azure_tenant_id")
    op.drop_column("companies", "azure_client_secret")
    op.drop_column("companies", "azure_client_id")
