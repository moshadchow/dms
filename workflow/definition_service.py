"""
workflow/definition_service.py
──────────────────────────────
CRUD operations for workflow definitions (admin-configured templates).
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from users.models import User
from workflow.models import (
    WorkflowAction,
    WorkflowDefinition,
    WorkflowDefinitionDetailRead,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionRead,
    WorkflowStep,
    WorkflowStepApprover,
    WorkflowStepRead,
)
from workflow.schemas import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowStepApproverCreate,
    WorkflowStepCreate,
)


class WorkflowDefinitionService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _validate_step_approvers(steps: List[WorkflowStepCreate]) -> None:
        """Ensure every step has at least one approver and each approver has exactly one of user_id/role_id."""
        for step in steps:
            if not step.approvers:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Step '{step.step_name}' (order {step.step_order}) must have at least one approver",
                )
            for approver in step.approvers:
                if bool(approver.user_id) == bool(approver.role_id):
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=(
                            f"Approver in step '{step.step_name}' must specify exactly one of "
                            f"user_id or role_id"
                        ),
                    )

    def _get_or_404(self, definition_id: int) -> WorkflowDefinition:
        wf = self.session.get(WorkflowDefinition, definition_id)
        if not wf:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow definition {definition_id} not found",
            )
        return wf

    def _to_read(self, wf: WorkflowDefinition) -> WorkflowDefinitionRead:
        return WorkflowDefinitionRead(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            is_active=wf.is_active,
            created_by=wf.created_by,
            created_at=wf.created_at,
            updated_at=wf.updated_at,
        )

    def _build_steps_read(self, steps: List[WorkflowStep]) -> List[WorkflowStepRead]:
        """Build step read schemas with approver details."""
        result = []
        for step in steps:
            approvers_data = []
            for app in step.approvers:
                approvers_data.append(
                    {
                        "id": app.id,
                        "workflow_step_id": app.workflow_step_id,
                        "user_id": app.user_id,
                        "role_id": app.role_id,
                        "priority": app.priority,
                        "is_active": app.is_active,
                        "user_name": app.user.full_name if app.user else None,
                        "role_name": app.role.name.value if app.role else None,
                    }
                )
            result.append(
                WorkflowStepRead(
                    id=step.id,
                    workflow_definition_id=step.workflow_definition_id,
                    step_order=step.step_order,
                    step_name=step.step_name,
                    approval_mode=step.approval_mode,
                    is_active=step.is_active,
                    approvers=approvers_data,
                )
            )
        return result

    def _log_audit(
        self,
        action: AuditAction,
        definition: WorkflowDefinition,
        description: str,
        *,
        old_value: Optional[dict] = None,
        new_value: Optional[dict] = None,
    ) -> None:
        try:
            svc = AuditService(self.session)
            svc.log_event(
                action=action,
                module=AuditModule.WORKFLOW,
                entity_name="workflow_definition",
                entity_id=str(definition.id),
                old_value=old_value,
                new_value=new_value,
                description=description,
                is_success=True,
            )
        except Exception:
            pass

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def create_definition(
        self,
        data: WorkflowDefinitionCreate,
        current_user: User,
    ) -> WorkflowDefinitionRead:
        self._validate_step_approvers(data.steps)

        existing = self.session.exec(
            select(WorkflowDefinition).where(WorkflowDefinition.name == data.name)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workflow '{data.name}' already exists",
            )

        wf = WorkflowDefinition(
            name=data.name,
            description=data.description,
            created_by=current_user.id,
        )
        self.session.add(wf)
        self.session.flush()

        for step_data in data.steps:
            step = WorkflowStep(
                workflow_definition_id=wf.id,
                step_order=step_data.step_order,
                step_name=step_data.step_name,
                approval_mode=step_data.approval_mode,
            )
            self.session.add(step)
            self.session.flush()

            for approver_data in step_data.approvers:
                approver = WorkflowStepApprover(
                    workflow_step_id=step.id,
                    user_id=approver_data.user_id,
                    role_id=approver_data.role_id,
                    priority=approver_data.priority,
                )
                self.session.add(approver)

        self.session.commit()
        self.session.refresh(wf)

        wf = self.session.exec(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.id == wf.id)
        ).first()

        self._log_audit(
            AuditAction.CREATE_WORKFLOW,
            wf,
            f"Created workflow '{wf.name}' with {len(data.steps)} step(s)",
            new_value={"name": wf.name, "steps": len(data.steps)},
        )

        return self._to_read(wf)

    def get_definition(self, definition_id: int) -> WorkflowDefinitionDetailRead:
        wf = self._get_or_404(definition_id)

        wf = self.session.exec(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.id == definition_id)
        ).first()

        steps_read = self._build_steps_read(wf.steps)

        return WorkflowDefinitionDetailRead(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            is_active=wf.is_active,
            created_by=wf.created_by,
            created_at=wf.created_at,
            updated_at=wf.updated_at,
            steps=steps_read,
        )

    def list_definitions(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        is_active: Optional[bool] = None,
    ) -> WorkflowDefinitionListResponse:
        query = select(WorkflowDefinition)

        if is_active is not None:
            query = query.where(WorkflowDefinition.is_active == is_active)

        count_query = select(func.count(WorkflowDefinition.id))
        if is_active is not None:
            count_query = count_query.where(WorkflowDefinition.is_active == is_active)
        total = self.session.exec(count_query).one()

        wfs = self.session.exec(
            query.order_by(WorkflowDefinition.name).offset(skip).limit(limit)
        ).all()

        items = [self._to_read(wf) for wf in wfs]

        return WorkflowDefinitionListResponse(
            total=total,
            page=(skip // limit) + 1,
            limit=limit,
            items=items,
        )

    def update_definition(
        self,
        definition_id: int,
        data: WorkflowDefinitionUpdate,
    ) -> WorkflowDefinitionRead:
        wf = self._get_or_404(definition_id)

        old_value = {
            "name": wf.name,
            "description": wf.description,
            "is_active": wf.is_active,
        }

        if data.name is not None:
            existing = self.session.exec(
                select(WorkflowDefinition)
                .where(WorkflowDefinition.name == data.name, WorkflowDefinition.id != definition_id)
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Workflow '{data.name}' already exists",
                )
            wf.name = data.name

        if data.description is not None:
            wf.description = data.description

        if data.is_active is not None:
            wf.is_active = data.is_active

        if data.steps is not None:
            self._validate_step_approvers(data.steps)

            step_ids = [step.id for step in wf.steps]
            if step_ids:
                actions_exist = self.session.exec(
                    select(WorkflowAction.workflow_step_id).where(
                        WorkflowAction.workflow_step_id.in_(step_ids)
                    ).limit(1)
                ).first()
                if actions_exist is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot modify steps: this workflow has active instances with approval actions. "
                        "Deactivate or complete existing instances before updating steps.",
                    )

            for step in wf.steps:
                for approver in step.approvers:
                    self.session.delete(approver)
                self.session.delete(step)
            self.session.flush()

            for step_data in data.steps:
                step = WorkflowStep(
                    workflow_definition_id=wf.id,
                    step_order=step_data.step_order,
                    step_name=step_data.step_name,
                    approval_mode=step_data.approval_mode,
                )
                self.session.add(step)
                self.session.flush()

                for approver_data in step_data.approvers:
                    approver = WorkflowStepApprover(
                        workflow_step_id=step.id,
                        user_id=approver_data.user_id,
                        role_id=approver_data.role_id,
                        priority=approver_data.priority,
                    )
                    self.session.add(approver)

        wf.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(wf)

        wf = self.session.exec(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.id == wf.id)
        ).first()

        new_value = {
            "name": wf.name,
            "description": wf.description,
            "is_active": wf.is_active,
        }

        self._log_audit(
            AuditAction.UPDATE_WORKFLOW,
            wf,
            f"Updated workflow '{wf.name}'",
            old_value=old_value,
            new_value=new_value,
        )

        return self._to_read(wf)

    def deactivate_definition(self, definition_id: int) -> WorkflowDefinitionRead:
        wf = self._get_or_404(definition_id)

        old_value = {"is_active": wf.is_active}
        wf.is_active = False
        wf.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(wf)

        self._log_audit(
            AuditAction.DELETE_WORKFLOW,
            wf,
            f"Deactivated workflow '{wf.name}'",
            old_value=old_value,
            new_value={"is_active": False},
        )

        return self._to_read(wf)

    def activate_definition(self, definition_id: int) -> WorkflowDefinitionRead:
        wf = self._get_or_404(definition_id)

        old_value = {"is_active": wf.is_active}
        wf.is_active = True
        wf.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(wf)

        self._log_audit(
            AuditAction.ACTIVATE_WORKFLOW,
            wf,
            f"Activated workflow '{wf.name}'",
            old_value=old_value,
            new_value={"is_active": True},
        )

        return self._to_read(wf)
