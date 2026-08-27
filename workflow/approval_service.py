"""
workflow/approval_service.py
────────────────────────────
Approval actions: approve, reject, return, clarify on workflow instances.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel import Session, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from users.models import Role, RoleName, User
from workflow.approval_policy import resolve_eligible_user_ids
from workflow.models import (
    ApprovalAction,
    ApprovalMode,
    WorkflowAction,
    WorkflowHistory,
    WorkflowInstance,
    WorkflowInstanceRead,
    WorkflowStatus,
    WorkflowStep,
)
from workflow.schemas import WorkflowActionCreate


class ApprovalActionService:
    def __init__(self, session: Session):
        self.session = session

    def _log_audit_action(
        self,
        audit_action: AuditAction,
        instance: WorkflowInstance,
        action: ApprovalAction,
        description: str,
    ) -> None:
        try:
            svc = AuditService(self.session)
            svc.log_event(
                action=audit_action,
                module=AuditModule.WORKFLOW,
                entity_name="workflow_instance",
                entity_id=str(instance.id),
                new_value={"action": action.value, "status": instance.status.value},
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
    ) -> None:
        user = self.session.get(User, actor_id)
        designation = None
        if user and user.roles:
            designation = ",".join(r.name.value for r in user.roles)

        history = WorkflowHistory(
            workflow_instance_id=instance.id,
            event_type=event_type,
            actor_id=actor_id,
            designation_snapshot=designation,
            remarks=remarks,
            status_snapshot=status_snapshot,
        )
        self.session.add(history)

    def _check_step_completion(self, instance: WorkflowInstance, step: WorkflowStep) -> bool:
        """Check if the current step is complete based on approval mode."""
        actions = self.session.exec(
            select(WorkflowAction).where(
                WorkflowAction.workflow_instance_id == instance.id,
                WorkflowAction.workflow_step_id == step.id,
            )
        ).all()

        approve_actions = [a for a in actions if a.action == ApprovalAction.APPROVE]
        eligible_ids = resolve_eligible_user_ids(self.session, step, instance.document)

        if step.approval_mode == ApprovalMode.PARALLEL:
            return len(approve_actions) >= 1
        else:
            approved_ids = {a.acted_by for a in approve_actions}
            return all(eid in approved_ids for eid in eligible_ids)

    def _resolve_eligible_user_ids(self, step: WorkflowStep, document) -> List[int]:
        """Resolve eligible user IDs for a step (delegates to shared policy)."""
        return resolve_eligible_user_ids(self.session, step, document)

    def _get_instance_or_404(self, instance_id: int) -> WorkflowInstance:
        instance = self.session.get(WorkflowInstance, instance_id)
        if not instance:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workflow instance {instance_id} not found",
            )
        return instance

    def _get_current_step(self, instance: WorkflowInstance) -> Optional[WorkflowStep]:
        return self.session.exec(
            select(WorkflowStep)
            .where(
                WorkflowStep.workflow_definition_id == instance.workflow_definition_id,
                WorkflowStep.step_order == instance.current_step_order,
            )
        ).first()

    def _to_instance_read(self, instance: WorkflowInstance) -> WorkflowInstanceRead:
        from workflow.instance_service import WorkflowInstanceService
        return WorkflowInstanceService(self.session)._to_instance_read(instance)

    def act_on_instance(
        self,
        instance_id: int,
        data: WorkflowActionCreate,
        current_user: User,
    ) -> WorkflowInstanceRead:
        instance = self._get_instance_or_404(instance_id)

        if any(r.name == RoleName.MAKER for r in current_user.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Makers cannot perform approval actions",
            )

        if instance.status not in (
            WorkflowStatus.SUBMITTED,
            WorkflowStatus.PENDING_APPROVAL,
            WorkflowStatus.RETURNED,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Instance is in '{instance.status.value}' state and cannot be acted upon",
            )

        current_step = self._get_current_step(instance)
        if not current_step:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Current step not found for instance",
            )

        eligible_ids = self._resolve_eligible_user_ids(current_step, instance.document)
        if current_user.id not in eligible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not an eligible approver for this step",
            )

        if data.action == ApprovalAction.APPROVE and current_user.id == instance.submitted_by:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Submitter cannot approve their own workflow instance",
            )

        if data.signature_id is not None:
            from signatures.service import SignatureService
            sig_svc = SignatureService(self.session)
            sig = sig_svc.validate_signature_exists(data.signature_id)
            if sig.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only use your own signatures",
                )

        action_record = WorkflowAction(
            workflow_instance_id=instance.id,
            workflow_step_id=current_step.id,
            acted_by=current_user.id,
            action=data.action,
            remarks=data.remarks,
            signature_id=data.signature_id,
        )
        self.session.add(action_record)
        self.session.flush()

        old_status = instance.status

        if data.action == ApprovalAction.APPROVE:
            if self._check_step_completion(instance, current_step):
                self._advance_step(instance, current_step, current_user)
            else:
                if instance.status == WorkflowStatus.SUBMITTED:
                    instance.status = WorkflowStatus.PENDING_APPROVAL
                    self._record_history(
                        instance, "step_in_progress", current_user.id,
                        WorkflowStatus.PENDING_APPROVAL, remarks=data.remarks,
                    )

        elif data.action == ApprovalAction.REJECT:
            instance.status = WorkflowStatus.REJECTED
            instance.updated_at = datetime.utcnow()
            self._record_history(
                instance, "rejected", current_user.id,
                WorkflowStatus.REJECTED, remarks=data.remarks,
            )

        elif data.action == ApprovalAction.RETURN:
            instance.status = WorkflowStatus.RETURNED
            instance.updated_at = datetime.utcnow()
            self._record_history(
                instance, "returned", current_user.id,
                WorkflowStatus.RETURNED, remarks=data.remarks,
            )

        elif data.action == ApprovalAction.CLARIFY:
            self._record_history(
                instance, "clarification_requested", current_user.id,
                instance.status, remarks=data.remarks,
            )

        elif data.action == ApprovalAction.FORWARD:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Forward action is not yet implemented",
            )

        audit_map = {
            ApprovalAction.APPROVE: AuditAction.APPROVE_WORKFLOW,
            ApprovalAction.REJECT: AuditAction.REJECT_WORKFLOW,
            ApprovalAction.RETURN: AuditAction.RETURN_WORKFLOW,
            ApprovalAction.CLARIFY: AuditAction.RETURN_WORKFLOW,
        }
        self._log_audit_action(
            audit_map[data.action],
            instance,
            data.action,
            f"User {current_user.id} performed '{data.action.value}' on instance {instance.id}",
        )

        self.session.commit()
        self.session.refresh(instance)

        return self._to_instance_read(instance)

    def _advance_step(
        self,
        instance: WorkflowInstance,
        current_step: WorkflowStep,
        actor: User,
    ) -> None:
        """Advance instance to next step or mark as approved."""
        next_step = self.session.exec(
            select(WorkflowStep)
            .where(
                WorkflowStep.workflow_definition_id == instance.workflow_definition_id,
                WorkflowStep.step_order > instance.current_step_order,
            )
            .order_by(WorkflowStep.step_order)
        ).first()

        if next_step:
            instance.current_step_order = next_step.step_order
            instance.status = WorkflowStatus.PENDING_APPROVAL
            instance.updated_at = datetime.utcnow()
            self._record_history(
                instance, "step_advanced", actor.id,
                WorkflowStatus.PENDING_APPROVAL,
                remarks=f"Advanced to step '{next_step.step_name}'",
            )
        else:
            instance.status = WorkflowStatus.APPROVED
            instance.updated_at = datetime.utcnow()
            self._record_history(
                instance, "approved", actor.id,
                WorkflowStatus.APPROVED,
            )
