"""workflow definitions

Revision ID: a1b2c3d4e5f7
Revises: f7a8b9c0d1e2
Create Date: 2026-08-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── workflow_definitions ──────────────────
    op.create_table(
        "workflow_definitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("document_category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_definitions_name", "workflow_definitions", ["name"], unique=True)
    op.create_index("ix_workflow_definitions_document_category_id", "workflow_definitions", ["document_category_id"])
    op.create_index("ix_workflow_definitions_is_active", "workflow_definitions", ["is_active"])

    # ── workflow_steps ────────────────────────
    op.create_table(
        "workflow_steps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_definition_id", sa.Integer(), sa.ForeignKey("workflow_definitions.id"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(length=255), nullable=False),
        sa.Column("approval_mode", sa.String(length=20), nullable=False, server_default="sequential"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_workflow_steps_workflow_definition_id", "workflow_steps", ["workflow_definition_id"])
    op.create_unique_constraint("uq_workflow_step_order", "workflow_steps", ["workflow_definition_id", "step_order"])

    # ── workflow_step_approvers ───────────────
    op.create_table(
        "workflow_step_approvers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_step_id", sa.Integer(), sa.ForeignKey("workflow_steps.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id"), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_index("ix_workflow_step_approvers_workflow_step_id", "workflow_step_approvers", ["workflow_step_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_step_approvers_workflow_step_id", table_name="workflow_step_approvers")
    op.drop_table("workflow_step_approvers")

    op.drop_constraint("uq_workflow_step_order", "workflow_steps", type_="unique")
    op.drop_index("ix_workflow_steps_workflow_definition_id", table_name="workflow_steps")
    op.drop_table("workflow_steps")

    op.drop_index("ix_workflow_definitions_is_active", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_document_category_id", table_name="workflow_definitions")
    op.drop_index("ix_workflow_definitions_name", table_name="workflow_definitions")
    op.drop_table("workflow_definitions")
