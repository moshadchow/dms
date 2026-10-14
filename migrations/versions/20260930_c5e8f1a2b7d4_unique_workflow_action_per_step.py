"""one action per (instance, step, user, action)

act_on_instance inserted workflow_actions rows unconditionally, so the same
approver could approve the same step twice while the instance stayed in
'pending_approval'. Guard the invariant in the database: dedupe existing
rows (keep the earliest — that is the one _check_step_completion counts)
then add a unique constraint. The service pre-checks and maps IntegrityError
to HTTP 409, this is the race backstop.

Revision ID: c5e8f1a2b7d4
Revises: a9c1e5f7b3d4
Create Date: 2026-09-30 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c5e8f1a2b7d4"
down_revision: Union[str, None] = "a9c1e5f7b3d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM workflow_actions WHERE id NOT IN ("
        "SELECT MIN(id) FROM workflow_actions "
        "GROUP BY workflow_instance_id, workflow_step_id, acted_by, action"
        ")"
    )
    inspector = sa.inspect(op.get_bind())
    constraints = {c["name"] for c in inspector.get_unique_constraints("workflow_actions")}
    if "uq_workflow_actions_instance_step_user_action" not in constraints:
        op.create_unique_constraint(
            "uq_workflow_actions_instance_step_user_action",
            "workflow_actions",
            ["workflow_instance_id", "workflow_step_id", "acted_by", "action"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    constraints = {c["name"] for c in inspector.get_unique_constraints("workflow_actions")}
    if "uq_workflow_actions_instance_step_user_action" in constraints:
        op.drop_constraint(
            "uq_workflow_actions_instance_step_user_action",
            "workflow_actions",
            type_="unique",
        )
    # Rows deleted by the upgrade dedupe cannot be restored.
