from datetime import datetime
from pathlib import Path
from typing import List, Optional
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlmodel import Session, func, select

from audit.models import AuditAction, AuditModule
from audit.service import AuditService
from categories.models import Category
from core.access import ensure_document_access, ensure_document_user_level_access
from core.config import settings
from documents.models import Document, DocumentUserLevelLink
from users.models import Role, RoleName, User, UserRoleLink
from workflow.models import (
    ApprovalAction,
    ApprovalMode,
    Signature,
    SignatureRead,
    SignatureType,
    WorkflowAction,
    WorkflowActionRead,
    WorkflowDefinition,
    WorkflowDefinitionDetailRead,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionRead,
    WorkflowHistory,
    WorkflowHistoryRead,
    WorkflowInstance,
    WorkflowInstanceDetailRead,
    WorkflowInstanceListResponse,
    WorkflowInstanceRead,
    WorkflowStatus,
    WorkflowStep,
    WorkflowStepApprover,
    WorkflowStepRead,
)
from workflow.schemas import (
    WorkflowActionCreate,
    WorkflowDefinitionCreate,
    WorkflowDefinitionUpdate,
    WorkflowInstanceCreate,
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
        cat_name = wf.category.name if wf.category else None
        return WorkflowDefinitionRead(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            document_category_id=wf.document_category_id,
            category_name=cat_name,
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

        # Check unique name
        existing = self.session.exec(
            select(WorkflowDefinition).where(WorkflowDefinition.name == data.name)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Workflow '{data.name}' already exists",
            )

        # Validate category exists
        cat = self.session.get(Category, data.document_category_id)
        if not cat:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Category {data.document_category_id} not found",
            )

        # Create definition
        wf = WorkflowDefinition(
            name=data.name,
            description=data.description,
            document_category_id=data.document_category_id,
            created_by=current_user.id,
        )
        self.session.add(wf)
        self.session.flush()

        # Create steps and approvers
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

        # Reload with relationships
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

        # Reload with steps and approvers
        wf = self.session.exec(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.id == definition_id)
        ).first()

        cat_name = wf.category.name if wf.category else None
        steps_read = self._build_steps_read(wf.steps)

        return WorkflowDefinitionDetailRead(
            id=wf.id,
            name=wf.name,
            description=wf.description,
            document_category_id=wf.document_category_id,
            category_name=cat_name,
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
        category_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> WorkflowDefinitionListResponse:
        query = select(WorkflowDefinition)

        if category_id is not None:
            query = query.where(WorkflowDefinition.document_category_id == category_id)
        if is_active is not None:
            query = query.where(WorkflowDefinition.is_active == is_active)

        # Count total
        count_query = select(func.count(WorkflowDefinition.id))
        if category_id is not None:
            count_query = count_query.where(WorkflowDefinition.document_category_id == category_id)
        if is_active is not None:
            count_query = count_query.where(WorkflowDefinition.is_active == is_active)
        total = self.session.exec(count_query).one()

        # Fetch page
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
            "document_category_id": wf.document_category_id,
            "is_active": wf.is_active,
        }

        # Update scalar fields
        if data.name is not None:
            # Check unique name if changing
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

        if data.document_category_id is not None:
            cat = self.session.get(Category, data.document_category_id)
            if not cat:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Category {data.document_category_id} not found",
                )
            wf.document_category_id = data.document_category_id

        if data.is_active is not None:
            wf.is_active = data.is_active

        # Replace steps if provided
        if data.steps is not None:
            self._validate_step_approvers(data.steps)

            # Delete existing steps and approvers
            for step in wf.steps:
                for approver in step.approvers:
                    self.session.delete(approver)
                self.session.delete(step)
            self.session.flush()

            # Create new steps
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

        # Reload with relationships
        wf = self.session.exec(
            select(WorkflowDefinition)
            .where(WorkflowDefinition.id == wf.id)
        ).first()

        new_value = {
            "name": wf.name,
            "description": wf.description,
            "document_category_id": wf.document_category_id,
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


# ══════════════════════════════════════════════
# Workflow Instance Service
# ══════════════════════════════════════════════


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
        eligible_ids: set[int] = set()

        for approver in step.approvers:
            if approver.user_id is not None:
                eligible_ids.add(approver.user_id)
            elif approver.role_id is not None:
                # Find all users with this role
                role_links = self.session.exec(
                    select(UserRoleLink).where(UserRoleLink.role_id == approver.role_id)
                ).all()
                for link in role_links:
                    eligible_ids.add(link.user_id)

        if not eligible_ids:
            return []

        # Filter by user level visibility (admin bypasses)
        user_level_links = self.session.exec(
            select(DocumentUserLevelLink).where(
                DocumentUserLevelLink.document_id == document.id,
            )
        ).all()
        permitted_level_ids = {link.user_level_id for link in user_level_links}

        # If no level links, document is only visible to admins
        if not permitted_level_ids:
            return []

        result = []
        for uid in eligible_ids:
            user = self.session.get(User, uid)
            if not user or not user.is_active:
                continue
            if user.is_admin():
                result.append(uid)
                continue
            if user.user_level_id in permitted_level_ids:
                result.append(uid)

        return result

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
        # Validate document exists and user has access
        document = ensure_document_access(self.session, current_user, data.document_id)
        ensure_document_user_level_access(self.session, current_user, document)

        # Prevent re-submission of already-approved documents
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

        # Validate workflow definition exists and is active
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

        # Validate definition matches document's category
        from directories.models import Directory
        directory = self.session.get(Directory, document.directory_id)
        if not directory or directory.category_id != wf_def.document_category_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Workflow definition does not match the document's category",
            )

        # Validate definition has steps
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

        # Validate first step has eligible approvers
        first_step = steps[0]
        eligible = self._resolve_eligible_user_ids(first_step, document)
        if not eligible:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No eligible approvers found for step '{first_step.step_name}'",
            )

        # Create instance
        instance = WorkflowInstance(
            document_id=data.document_id,
            workflow_definition_id=data.workflow_definition_id,
            current_step_order=first_step.step_order,
            status=WorkflowStatus.SUBMITTED,
            submitted_by=current_user.id,
        )
        self.session.add(instance)
        self.session.flush()

        # Record history
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

        # Reload with relationships
        instance = self.session.get(WorkflowInstance, instance_id)

        read = self._to_instance_read(instance)

        actions_read = []
        for action in instance.actions:
            actions_read.append(WorkflowActionRead(
                id=action.id,
                workflow_instance_id=action.workflow_instance_id,
                workflow_step_id=action.workflow_step_id,
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
        # Get all active instances
        all_instances = self.session.exec(
            select(WorkflowInstance)
            .where(WorkflowInstance.status.in_([
                WorkflowStatus.SUBMITTED,
                WorkflowStatus.PENDING_APPROVAL,
                WorkflowStatus.RETURNED,
            ]))
        ).all()

        # Filter to instances where current user is eligible
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

        # Paginate manually (in-memory filter)
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

        # Only the original submitter can cancel
        if instance.submitted_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the original submitter can cancel this workflow instance",
            )

        # Cannot cancel terminal states
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

        # Record history
        self._record_history(
            instance,
            event_type="cancelled",
            actor_id=current_user.id,
            status_snapshot=WorkflowStatus.CANCELLED,
        )

        # Audit
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


# ══════════════════════════════════════════════
# Approval Action Service
# ══════════════════════════════════════════════


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
        # Get actor's role for designation snapshot
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
        eligible_ids = self._resolve_eligible_user_ids(step, instance.document)

        if step.approval_mode == ApprovalMode.PARALLEL:
            # Parallel: any one approval completes the step
            return len(approve_actions) >= 1
        else:
            # Sequential: all eligible approvers must approve
            approved_ids = {a.acted_by for a in approve_actions}
            return all(eid in approved_ids for eid in eligible_ids)

    def _resolve_eligible_user_ids(self, step: WorkflowStep, document) -> List[int]:
        """Resolve eligible user IDs for a step (same logic as WorkflowInstanceService)."""
        eligible_ids: set[int] = set()
        for approver in step.approvers:
            if approver.user_id is not None:
                eligible_ids.add(approver.user_id)
            elif approver.role_id is not None:
                role_links = self.session.exec(
                    select(UserRoleLink).where(UserRoleLink.role_id == approver.role_id)
                ).all()
                for link in role_links:
                    eligible_ids.add(link.user_id)

        if not eligible_ids:
            return []

        from documents.models import DocumentUserLevelLink
        user_level_links = self.session.exec(
            select(DocumentUserLevelLink).where(DocumentUserLevelLink.document_id == document.id)
        ).all()
        permitted_level_ids = {link.user_level_id for link in user_level_links}

        if not permitted_level_ids:
            return []

        result = []
        for uid in eligible_ids:
            user = self.session.get(User, uid)
            if not user or not user.is_active:
                continue
            if user.is_admin():
                result.append(uid)
                continue
            if user.user_level_id in permitted_level_ids:
                result.append(uid)
        return result

    def act_on_instance(
        self,
        instance_id: int,
        data: WorkflowActionCreate,
        current_user: User,
    ) -> WorkflowInstanceRead:
        instance_svc = WorkflowInstanceService(self.session)
        instance = instance_svc._get_instance_or_404(instance_id)

        # Validate instance is in an actionable state
        if instance.status not in (
            WorkflowStatus.SUBMITTED,
            WorkflowStatus.PENDING_APPROVAL,
            WorkflowStatus.RETURNED,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Instance is in '{instance.status.value}' state and cannot be acted upon",
            )

        # Get current step
        current_step = instance_svc._get_current_step(instance)
        if not current_step:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Current step not found for instance",
            )

        # Validate user is eligible to act on this step
        eligible_ids = instance_svc._resolve_eligible_user_ids(current_step, instance.document)
        if current_user.id not in eligible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not an eligible approver for this step",
            )

        # Self-approval check: submitter cannot approve their own instance
        if data.action == ApprovalAction.APPROVE and current_user.id == instance.submitted_by:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Submitter cannot approve their own workflow instance",
            )

        # Validate signature if provided
        if data.signature_id is not None:
            sig_svc = SignatureService(self.session)
            sig = sig_svc.validate_signature_exists(data.signature_id)
            if sig.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You can only use your own signatures",
                )

        # Record the action
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

        # Process action
        if data.action == ApprovalAction.APPROVE:
            # Check if step is now complete
            if self._check_step_completion(instance, current_step):
                # Advance to next step or complete
                self._advance_step(instance, current_step, current_user)
            else:
                # Step not yet complete, update status to pending_approval
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
            # Clarify is informational — no status change, just history
            self._record_history(
                instance, "clarification_requested", current_user.id,
                instance.status, remarks=data.remarks,
            )

        elif data.action == ApprovalAction.FORWARD:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Forward action is not yet implemented",
            )

        # Audit
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

        return instance_svc._to_instance_read(instance)

    def _advance_step(
        self,
        instance: WorkflowInstance,
        current_step: WorkflowStep,
        actor: User,
    ) -> None:
        """Advance instance to next step or mark as approved."""
        # Find next step
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
            # No more steps — approved
            instance.status = WorkflowStatus.APPROVED
            instance.updated_at = datetime.utcnow()
            self._record_history(
                instance, "approved", actor.id,
                WorkflowStatus.APPROVED,
            )


# ══════════════════════════════════════════════
# Signature Service
# ══════════════════════════════════════════════

# Allowed MIME types for signature images
ALLOWED_SIGNATURE_MIME_TYPES = {"image/jpeg", "image/png"}


class SignatureService:
    def __init__(self, session: Session):
        self.session = session

    def _to_read(self, sig: Signature) -> SignatureRead:
        return SignatureRead(
            id=sig.id,
            user_id=sig.user_id,
            file_name=sig.file_name,
            file_path=sig.file_path,
            mime_type=sig.mime_type,
            file_size=sig.file_size,
            sig_type=sig.sig_type,
            is_active=sig.is_active,
            created_at=sig.created_at,
            updated_at=sig.updated_at,
        )

    def _log_audit(
        self,
        action: AuditAction,
        signature: Signature,
        description: str,
    ) -> None:
        try:
            svc = AuditService(self.session)
            svc.log_event(
                action=action,
                module=AuditModule.WORKFLOW,
                entity_name="signature",
                entity_id=str(signature.id),
                new_value={
                    "sig_type": signature.sig_type.value,
                    "file_name": signature.file_name,
                },
                description=description,
                is_success=True,
            )
        except Exception:
            pass

    def upload_signature(
        self,
        file: UploadFile,
        current_user: User,
        sig_type: SignatureType,
    ) -> SignatureRead:
        """Upload a signature image (e-signature or wet-signature capture)."""
        # Validate MIME type
        mime = file.content_type or ""
        if mime not in ALLOWED_SIGNATURE_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"File type '{mime}' is not supported. Allowed types: JPEG, PNG",
            )

        # Read file content
        content = file.file.read()
        file_size = len(content)

        # Validate file size (max 5MB for signatures)
        max_bytes = 5 * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Signature file size exceeds the 5 MB limit",
            )

        # Generate safe filename
        storage_root = Path(settings.STORAGE_ROOT)
        dest_dir = storage_root / "signatures" / str(current_user.id)
        dest_dir.mkdir(parents=True, exist_ok=True)

        safe_name = f"{uuid.uuid4().hex}_{Path(file.filename or 'signature').name}"
        dest_path = dest_dir / safe_name
        dest_path.write_bytes(content)

        relative_path = str(dest_path.relative_to(storage_root))

        # Create DB record
        sig = Signature(
            user_id=current_user.id,
            file_name=file.filename or safe_name,
            file_path=relative_path,
            mime_type=mime,
            file_size=file_size,
            sig_type=sig_type,
            is_active=True,
        )
        self.session.add(sig)
        self.session.commit()
        self.session.refresh(sig)

        self._log_audit(
            AuditAction.CREATE_WORKFLOW,
            sig,
            f"User {current_user.id} uploaded {sig_type.value}",
        )

        return self._to_read(sig)

    def get_signature(self, signature_id: int, current_user: User) -> SignatureRead:
        """Get signature metadata. Users can view their own; admins can view all."""
        sig = self.session.get(Signature, signature_id)
        if not sig:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        # Check ownership or admin
        if sig.user_id != current_user.id and not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own signatures",
            )
        return self._to_read(sig)

    def get_signature_file(self, signature_id: int, current_user: User) -> Path:
        """Get the file path for serving a signature image."""
        sig = self.session.get(Signature, signature_id)
        if not sig or not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        # Check ownership or admin
        if sig.user_id != current_user.id and not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only view your own signatures",
            )

        storage_root = Path(settings.STORAGE_ROOT).resolve()
        abs_path = (storage_root / sig.file_path).resolve()

        # Path-traversal guard
        if not str(abs_path).startswith(str(storage_root)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file path",
            )

        if not abs_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Signature file not found on disk",
            )

        return abs_path

    def soft_delete_signature(self, signature_id: int, current_user: User) -> SignatureRead:
        """Soft-delete a signature (set is_active=False). Users can delete their own; admins can delete all."""
        sig = self.session.get(Signature, signature_id)
        if not sig:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        if not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found",
            )
        # Check ownership or admin
        if sig.user_id != current_user.id and not current_user.is_admin():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own signatures",
            )

        sig.is_active = False
        sig.updated_at = datetime.utcnow()
        self.session.commit()
        self.session.refresh(sig)

        self._log_audit(
            AuditAction.DELETE_WORKFLOW,
            sig,
            f"User {current_user.id} deleted signature {signature_id}",
        )

        return self._to_read(sig)

    def validate_signature_exists(self, signature_id: int) -> Signature:
        """Validate that a signature exists and is active. Used by act_on_instance."""
        sig = self.session.get(Signature, signature_id)
        if not sig or not sig.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Signature {signature_id} not found or is inactive",
            )
        return sig
