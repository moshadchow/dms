"""workflow instances

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f7
Create Date: 2026-08-09 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── workflow_instances ─────────────────────
    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("workflow_definition_id", sa.Integer(), sa.ForeignKey("workflow_definitions.id"), nullable=False),
        sa.Column("current_step_order", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
        sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_instances_document_id", "workflow_instances", ["document_id"])
    op.create_index("ix_workflow_instances_workflow_definition_id", "workflow_instances", ["workflow_definition_id"])
    op.create_index("ix_workflow_instances_status", "workflow_instances", ["status"])

    # ── workflow_actions ───────────────────────
    op.create_table(
        "workflow_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_instance_id", sa.Integer(), sa.ForeignKey("workflow_instances.id"), nullable=False),
        sa.Column("workflow_step_id", sa.Integer(), sa.ForeignKey("workflow_steps.id"), nullable=False),
        sa.Column("acted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("remarks", sa.String(length=2000), nullable=True),
        sa.Column("signature_id", sa.Integer(), nullable=True),
        sa.Column("acted_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_actions_workflow_instance_id", "workflow_actions", ["workflow_instance_id"])
    op.create_index("ix_workflow_actions_workflow_step_id", "workflow_actions", ["workflow_step_id"])

    # ── workflow_history ───────────────────────
    op.create_table(
        "workflow_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_instance_id", sa.Integer(), sa.ForeignKey("workflow_instances.id"), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("designation_snapshot", sa.String(length=100), nullable=True),
        sa.Column("remarks", sa.String(length=2000), nullable=True),
        sa.Column("status_snapshot", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_history_workflow_instance_id", "workflow_history", ["workflow_instance_id"])


def downgrade() -> None:
    op.drop_index("ix_workflow_history_workflow_instance_id", table_name="workflow_history")
    op.drop_table("workflow_history")

    op.drop_index("ix_workflow_actions_workflow_step_id", table_name="workflow_actions")
    op.drop_index("ix_workflow_actions_workflow_instance_id", table_name="workflow_actions")
    op.drop_table("workflow_actions")

    op.drop_index("ix_workflow_instances_status", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_workflow_definition_id", table_name="workflow_instances")
    op.drop_index("ix_workflow_instances_document_id", table_name="workflow_instances")
    op.drop_table("workflow_instances")
