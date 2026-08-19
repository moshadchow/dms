export type ApprovalMode = 'sequential' | 'parallel'

export interface WorkflowStepApprover {
  id: number
  workflow_step_id: number
  user_id: number | null
  role_id: number | null
  priority: number
  is_active: boolean
  user_name: string | null
  role_name: string | null
}

export interface WorkflowStep {
  id: number
  workflow_definition_id: number
  step_order: number
  step_name: string
  approval_mode: ApprovalMode
  is_active: boolean
  approvers: WorkflowStepApprover[]
}

export interface WorkflowDefinition {
  id: number
  name: string
  description: string | null
  document_category_id: number
  category_name: string | null
  is_active: boolean
  created_by: number
  created_at: string
  updated_at: string
}

export interface WorkflowDefinitionDetail extends WorkflowDefinition {
  steps: WorkflowStep[]
}

export interface WorkflowDefinitionListResponse {
  total: number
  page: number
  limit: number
  items: WorkflowDefinition[]
}

export interface WorkflowStepApproverCreate {
  user_id?: number | null
  role_id?: number | null
  priority?: number
}

export interface WorkflowStepCreate {
  step_order: number
  step_name: string
  approval_mode?: ApprovalMode
  approvers: WorkflowStepApproverCreate[]
}

export interface WorkflowDefinitionCreate {
  name: string
  description?: string
  document_category_id: number
  steps: WorkflowStepCreate[]
}

export interface WorkflowDefinitionUpdate {
  name?: string
  description?: string
  document_category_id?: number
  is_active?: boolean
  steps?: WorkflowStepCreate[]
}

// ── Workflow Instance Types ────────────────────────

export type WorkflowStatus =
  | 'draft'
  | 'submitted'
  | 'pending_approval'
  | 'returned'
  | 'rejected'
  | 'approved'
  | 'cancelled'
  | 'published'
  | 'archived'

export type ApprovalAction = 'approve' | 'reject' | 'return' | 'clarify' | 'forward'

export interface WorkflowInstance {
  id: number
  document_id: number
  document_title: string | null
  workflow_definition_id: number
  workflow_name: string | null
  current_step_order: number
  current_step_name: string | null
  status: WorkflowStatus
  submitted_by: number
  submitted_by_name: string | null
  submitted_at: string
  updated_at: string
}

export interface WorkflowAction {
  id: number
  workflow_instance_id: number
  workflow_step_id: number
  step_name: string | null
  acted_by: number
  acted_by_name: string | null
  action: ApprovalAction
  remarks: string | null
  signature_id: number | null
  acted_at: string
}

export interface WorkflowHistory {
  id: number
  workflow_instance_id: number
  event_type: string
  actor_id: number
  actor_name: string | null
  designation_snapshot: string | null
  remarks: string | null
  status_snapshot: WorkflowStatus
  occurred_at: string
}

export interface WorkflowInstanceDetail extends WorkflowInstance {
  actions: WorkflowAction[]
  history: WorkflowHistory[]
}

export interface WorkflowInstanceListResponse {
  total: number
  page: number
  limit: number
  items: WorkflowInstance[]
}

export interface WorkflowActionCreate {
  action: ApprovalAction
  remarks?: string
  signature_id?: number | null
}

// ── Signature Types ────────────────────────────────

export type SignatureType = 'e_signature' | 'wet_signature'

export interface Signature {
  id: number
  user_id: number
  file_name: string
  file_path: string
  mime_type: string
  file_size: number
  sig_type: SignatureType
  is_active: boolean
  created_at: string
  updated_at: string
}
