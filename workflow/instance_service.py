"""
workflow/instance_service.py
────────────────────────────
Workflow instance lifecycle: submit, list, cancel.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from core.access import ensure_document_access, ensure_document_user_level_access
from documents.models import Document
from users.models import User
from workflow.approval_policy import resolve_eligible_user_ids
from workflow.models import (
    WorkflowDefinition,
    WorkflowHistory,
    WorkflowHistoryRead,
    WorkflowInstance,
    WorkflowInstanceDetailRead,
    WorkflowInstanceListResponse,
    WorkflowInstanceRead,
    WorkflowActionRead,
    WorkflowStatus,
    WorkflowStep,
)
from workflow.schemas import WorkflowInstanceCreate


class WorkflowInstanceService:
    def __init__(self, session: Session):
        self.session = session

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _get_instance_or_404(self, instance_id: int) -> WorkflowInstance:
        instance = self.session.get(WorkflowInstance, instance_id)
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow instance {instance_id} not found",
            )
        return instance

    def _get_current_step(self, instance: WorkflowInstance) -> Optional[WorkflowStep]:
        """Return the current step for an instance."""
        return self.session.exec(
            select(WorkflowStep)
            .where(
                WorkflowStep.workflow_definition_id == instance.workflow_definition_id,
                WorkflowStep.step_order == instance.current_step_order,
            )
        ).first()

    def _resolve_eligible_user_ids(self, step: WorkflowStep, document: Document) -> List[int]:
        """Return user IDs eligible to act at this step, filtered by user level visibility."""
        return resolve_eligible_user_ids(self.session, step, document)

    def _to_instance_read(self, instance: WorkflowInstance) -> WorkflowInstanceRead:
        doc_title = instance.document.title if instance.document else None
        wf_name = instance.workflow_definition.name if instance.workflow_definition else None
        submitter_name = instance.submitted_by_user.full_name if instance.submitted_by_user else None

        current_step = self._get_current_step(instance)
        step_name = current_step.step_name if current_step else None

        return WorkflowInstanceRead(
            id=instance.id,
            document_id=instance.document_id,
            document_title=doc_title,
            workflow_definition_id=instance.workflow_definition_id,
            workflow_name=wf_name,
            current_step_order=instance.current_step_order,
            current_step_name=step_name,
            status=instance.status,
            submitted_by=instance.submitted_by,
            submitted_by_name=submitter_name,
            submitted_at=instance.submitted_at,
            updated_at=instance.updated_at,
        )

    def _to_instance_detail(self, instance: WorkflowInstance) -> WorkflowInstanceDetailRead:
        """Build a detailed read (instance + actions + history)."""
        instance = self.session.get(WorkflowInstance, instance.id)
        read = self._to_instance_read(instance)

        actions_read = []
        for action in instance.actions:
            step_name = action.workflow_step.step_name if action.workflow_step else None
            actions_read.append(WorkflowActionRead(
                id=action.id,
                workflow_instance_id=action.workflow_instance_id,
                workflow_step_id=action.workflow_step_id,
                step_name=step_name,
                acted_by=action.acted_by,
                acted_by_name=action.acted_by_user.full_name if action.acted_by_user else None,
                action=action.action,
                remarks=action.remarks,
                signature_id=action.signature_id,
                acted_at=action.acted_at,
            ))

        history_read = []
        for h in instance.history:
            history_read.append(WorkflowHistoryRead(
                id=h.id,
                workflow_instance_id=h.workflow_instance_id,
                event_type=h.event_type,
                actor_id=h.actor_id,
                actor_name=h.actor.full_name if h.actor else None,
                designation_snapshot=h.designation_snapshot,
                remarks=h.remarks,
                status_snapshot=h.status_snapshot,
                occurred_at=h.occurred_at,
            ))

        return WorkflowInstanceDetailRead(
            **read.model_dump(),
            actions=actions_read,
            history=history_read,
        )

    def _log_audit_instance(
        self,
        action: AuditAction,
        instance: WorkflowInstance,
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
                entity_name="workflow_instance",
                entity_id=str(instance.id),
                old_value=old_value,
                new_value=new_value,
                description=description,
                is_success=True,
            )
        except Exception:
            pass

    def _record_history(
        self,
        instance: WorkflowInstance,
        event_type: str,
        actor_id: int,
        status_snapshot: WorkflowStatus,
        *,
        remarks: Optional[str] = None,
        designation_snapshot: Optional[str] = None,
    ) -> None:
        history = WorkflowHistory(
            workflow_instance_id=instance.id,
            event_type=event_type,
            actor_id=actor_id,
            designation_snapshot=designation_snapshot,
            remarks=remarks,
            status_snapshot=status_snapshot,
        )
        self.session.add(history)

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def submit_instance(
        self,
        data: WorkflowInstanceCreate,
        current_user: User,
    ) -> WorkflowInstanceRead:
        document = ensure_document_access(self.session, current_user, data.document_id)
        ensure_document_user_level_access(self.session, current_user, document)

        approved_instance = self.session.exec(
            select(WorkflowInstance).where(
                WorkflowInstance.document_id == data.document_id,
                WorkflowInstance.status == WorkflowStatus.APPROVED,
            )
        ).first()
        if approved_instance:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document is already approved and cannot be resubmitted",
            )

        wf_def = self.session.get(WorkflowDefinition, data.workflow_definition_id)
        if not wf_def:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow definition {data.workflow_definition_id} not found",
            )
        if not wf_def.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Workflow definition is not active",
            )

        steps = self.session.exec(
            select(WorkflowStep)
            .where(WorkflowStep.workflow_definition_id == wf_def.id)
            .order_by(WorkflowStep.step_order)
        ).all()
        if not steps:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Workflow definition has no steps configured",
            )

        first_step = steps[0]
        eligible = self._resolve_eligible_user_ids(first_step, document)
        if not eligible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No eligible approvers found for step '{first_step.step_name}'",
            )

        instance = WorkflowInstance(
            document_id=data.document_id,
            workflow_definition_id=data.workflow_definition_id,
            current_step_order=first_step.step_order,
            status=WorkflowStatus.SUBMITTED,
            submitted_by=current_user.id,
        )
        self.session.add(instance)
        self.session.flush()

        self._record_history(
            instance,
            event_type="submitted",
            actor_id=current_user.id,
            status_snapshot=WorkflowStatus.SUBMITTED,
        )

        self.session.commit()
        self.session.refresh(instance)

        self._log_audit_instance(
            AuditAction.SUBMIT_WORKFLOW,
            instance,
            f"Submitted document {data.document_id} for approval via workflow '{wf_def.name}'",
            new_value={"document_id": data.document_id, "workflow_name": wf_def.name},
        )

        return self._to_instance_read(instance)

    def get_instance(self, instance_id: int) -> WorkflowInstanceDetailRead:
        instance = self._get_instance_or_404(instance_id)
        return self._to_instance_detail(instance)

    def get_by_document(
        self,
        document_id: int,
        current_user: User,
    ) -> WorkflowInstanceDetailRead:
        """Return the most recent workflow instance for a document (with access check)."""
        document = ensure_document_access(self.session, current_user, document_id)
        ensure_document_user_level_access(self.session, current_user, document)

        instance = self.session.exec(
            select(WorkflowInstance)
            .where(WorkflowInstance.document_id == document_id)
            .order_by(WorkflowInstance.submitted_at.desc())
        ).first()
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No workflow instance found for document {document_id}",
            )

        return self._to_instance_detail(instance)

    def list_my_instances(
        self,
        current_user: User,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> WorkflowInstanceListResponse:
        query = select(WorkflowInstance).where(WorkflowInstance.submitted_by == current_user.id)

        count = self.session.exec(
            select(func.count(WorkflowInstance.id)).where(WorkflowInstance.submitted_by == current_user.id)
        ).one()

        instances = self.session.exec(
            query.order_by(WorkflowInstance.submitted_at.desc()).offset(skip).limit(limit)
        ).all()

        return WorkflowInstanceListResponse(
            total=count,
            page=(skip // limit) + 1,
            limit=limit,
            items=[self._to_instance_read(i) for i in instances],
        )

    def list_pending(
        self,
        current_user: User,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> WorkflowInstanceListResponse:
        """Return instances where the current user is an eligible approver at the current step."""
        all_instances = self.session.exec(
            select(WorkflowInstance)
            .where(WorkflowInstance.status.in_([
                WorkflowStatus.SUBMITTED,
                WorkflowStatus.PENDING_APPROVAL,
                WorkflowStatus.RETURNED,
            ]))
        ).all()

        eligible_instances = []
        for instance in all_instances:
            step = self._get_current_step(instance)
            if not step:
                continue
            doc = instance.document
            if not doc:
                continue
            eligible_ids = self._resolve_eligible_user_ids(step, doc)
            if current_user.id in eligible_ids:
                eligible_instances.append(instance)

        total = len(eligible_instances)
        page_instances = eligible_instances[skip:skip + limit]

        return WorkflowInstanceListResponse(
            total=total,
            page=(skip // limit) + 1,
            limit=limit,
            items=[self._to_instance_read(i) for i in page_instances],
        )

    def cancel_instance(
        self,
        instance_id: int,
        current_user: User,
    ) -> WorkflowInstanceRead:
        instance = self._get_instance_or_404(instance_id)

        if instance.submitted_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the original submitter can cancel this workflow instance",
            )

        if instance.status in (
            WorkflowStatus.APPROVED,
            WorkflowStatus.REJECTED,
            WorkflowStatus.CANCELLED,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Instance is in '{instance.status.value}' state and cannot be cancelled",
            )

        instance.status = WorkflowStatus.CANCELLED
        instance.updated_at = datetime.utcnow()
        self.session.add(instance)

        self._record_history(
            instance,
            event_type="cancelled",
            actor_id=current_user.id,
            status_snapshot=WorkflowStatus.CANCELLED,
        )

        try:
            svc = AuditService(self.session)
            svc.log_event(
                action=AuditAction.CANCEL_WORKFLOW,
                module=AuditModule.WORKFLOW,
                entity_name="workflow_instance",
                entity_id=str(instance.id),
                new_value={"status": "cancelled"},
                description=f"User {current_user.id} cancelled workflow instance {instance.id}",
                is_success=True,
            )
        except Exception:
            pass

        self.session.commit()
        self.session.refresh(instance)

        return self._to_instance_read(instance)
