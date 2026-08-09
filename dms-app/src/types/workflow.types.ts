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
