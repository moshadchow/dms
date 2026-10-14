"""
workflow/service.py
───────────────────
Backward-compatible re-exports. The actual implementations now live in:
  - workflow/definition_service.py  (WorkflowDefinitionService)
  - workflow/instance_service.py    (WorkflowInstanceService)
  - workflow/approval_service.py    (ApprovalActionService)
  - signatures/service.py           (SignatureService)
"""

from workflow.definition_service import WorkflowDefinitionService  # noqa: F401
from workflow.instance_service import WorkflowInstanceService  # noqa: F401
from workflow.approval_service import ApprovalActionService  # noqa: F401
from signatures.service import SignatureService  # noqa: F401

__all__ = [
    "WorkflowDefinitionService",
    "WorkflowInstanceService",
    "ApprovalActionService",
    "SignatureService",
]
