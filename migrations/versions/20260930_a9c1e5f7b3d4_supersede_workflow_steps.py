"""version workflow step edits instead of deleting steps

update_definition used to delete + re-create workflow_steps rows, which is
unsafe: workflow_actions.workflow_step_id is a non-null FK and action rows are
append-only audit history. Step edits now supersede rows (is_active=False)
instead of deleting them, guarded by "no active instances". The old unique
constraint on (workflow_definition_id, step_order) would reject the replacement
row, so it becomes a partial index over active steps only.

Revision ID: a9c1e5f7b3d4
Revises: d2f4a6b8c1e3
Create Date: 2026-09-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "a9c1e5f7b3d4"
down_revision: Union[str, None] = "d2f4a6b8c1e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    constraints = {c["name"] for c in inspector.get_unique_constraints("workflow_steps")}
    if "uq_workflow_step_order" in constraints:
        op.drop_constraint("uq_workflow_step_order", "workflow_steps", type_="unique")

    indexes = {i["name"] for i in inspector.get_indexes("workflow_steps")}
    if "uq_workflow_step_order_active" not in indexes:
        op.create_index(
            "uq_workflow_step_order_active",
            "workflow_steps",
            ["workflow_definition_id", "step_order"],
            unique=True,
            postgresql_where=sa.text("is_active"),
            sqlite_where=sa.text("is_active"),
        )


def downgrade() -> None:
    # Recreating the original constraint fails if any definition has superseded
    # step rows sharing a step_order — restore manually after cleaning those up.
    inspector = sa.inspect(op.get_bind())
    indexes = {i["name"] for i in inspector.get_indexes("workflow_steps")}
    if "uq_workflow_step_order_active" in indexes:
        op.drop_index("uq_workflow_step_order_active", table_name="workflow_steps")
    op.create_unique_constraint(
        "uq_workflow_step_order",
        "workflow_steps",
        ["workflow_definition_id", "step_order"],
    )
