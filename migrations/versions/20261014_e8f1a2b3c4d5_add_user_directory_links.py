"""add user directory links for subdirectory-level access

Revision ID: e8f1a2b3c4d5
Revises: c5e8f1a2b7d4
Create Date: 2026-10-14 00:00:00.000000

Idempotent: a DEBUG=True boot auto-creates this table from SQLModel
metadata (see main.py lifespan) before the migration runs, so CREATE uses
IF NOT EXISTS guards, matching the 7c8d9e0f1a2b precedent.

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e8f1a2b3c4d5"
down_revision: Union[str, None] = "c5e8f1a2b7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS user_directory_links (
            user_id INTEGER NOT NULL,
            directory_id INTEGER NOT NULL,
            CONSTRAINT user_directory_links_pkey PRIMARY KEY (user_id, directory_id),
            CONSTRAINT fk_user_directory_links_user_id
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            CONSTRAINT fk_user_directory_links_directory_id
                FOREIGN KEY (directory_id) REFERENCES directories (id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_directory_links_user_id"
        " ON user_directory_links (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_user_directory_links_directory_id"
        " ON user_directory_links (directory_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS user_directory_links")
