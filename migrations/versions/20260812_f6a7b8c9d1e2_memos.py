"""memos and memo attachments

Revision ID: f6a7b8c9d1e2
Revises: e5f6a7b8c9d1
Create Date: 2026-08-12 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f6a7b8c9d1e2"
down_revision: Union[str, None] = "e5f6a7b8c9d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── memos ──────────────────────────────────
    op.create_table(
        "memos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False, unique=True),
        sa.Column("to_recipients", sa.String(length=500), nullable=False),
        sa.Column("from_name", sa.String(length=255), nullable=False),
        sa.Column("memo_date", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("author_signature_id", sa.Integer(), sa.ForeignKey("signatures.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_memos_document_id", "memos", ["document_id"], unique=True)
    op.create_index("ix_memos_subject", "memos", ["subject"])

    # ── memo_attachments ───────────────────────
    op.create_table(
        "memo_attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("memo_id", sa.Integer(), sa.ForeignKey("memos.id"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_memo_attachments_memo_id", "memo_attachments", ["memo_id"])
    op.create_index("ix_memo_attachments_document_id", "memo_attachments", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_memo_attachments_document_id", table_name="memo_attachments")
    op.drop_index("ix_memo_attachments_memo_id", table_name="memo_attachments")
    op.drop_table("memo_attachments")

    op.drop_index("ix_memos_subject", table_name="memos")
    op.drop_index("ix_memos_document_id", table_name="memos")
    op.drop_table("memos")
