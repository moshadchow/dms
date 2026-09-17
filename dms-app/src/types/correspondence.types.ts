import type { WorkflowStatus } from './workflow.types'

export type CorrespondenceDirection = 'inbound' | 'outbound' | 'internal'
export type CorrespondencePriority = 'low' | 'normal' | 'high' | 'urgent'
export type CorrespondenceStatus =
  | 'received' | 'registered' | 'assigned' | 'processing'
  | 'draft' | 'submitted' | 'pending_approval' | 'returned' | 'rejected'
  | 'approved' | 'ready_for_dispatch' | 'dispatched' | 'delivered'
  | 'acknowledged' | 'completed' | 'cancelled' | 'archived'
export type DispatchMethod = 'email' | 'courier' | 'post' | 'hand_delivery' | 'portal' | 'other'
export type AttachmentType = 'original' | 'supporting' | 'working'

export interface CorrespondenceAttachment {
  id: number
  correspondence_id: number
  document_id: number
  attachment_type: AttachmentType
  file_name: string | null
  file_type: string | null
  mime_type: string | null
  file_size: number | null
  created_by: number
  created_by_name: string | null
  created_at: string
}

export interface Correspondence {
  id: number
  document_id: number
  company_id: number
  created_by: number
  reference_number: string
  direction: CorrespondenceDirection
  status: CorrespondenceStatus
  subject: string
  body: string | null
  priority: CorrespondencePriority
  category_id: number | null
  sender_name: string | null
  sender_organization: string | null
  recipient_name: string | null
  recipient_organization: string | null
  date_sent: string | null
  date_received: string | null
  response_required: boolean
  response_deadline: string | null
  response_received: boolean
  responded_at: string | null
  parent_correspondence_id: number | null
  author_signature_id: number | null
  workflow_instance_id: number | null
  dispatch_method: DispatchMethod | null
  dispatch_reference: string | null
  dispatched_at: string | null
  delivered_at: string | null
  acknowledged_at: string | null
  created_by_name: string | null
  category_name: string | null
  created_at: string
  updated_at: string
}

export interface CorrespondenceMovement {
  id: number
  correspondence_id: number
  from_user_id: number | null
  from_user_name: string | null
  to_user_id: number | null
  to_user_name: string | null
  from_department: string | null
  to_department: string | null
  action: string
  remarks: string | null
  created_by: number
  created_by_name: string | null
  created_at: string
}

export interface CorrespondenceDetail extends Correspondence {
  sender_email: string | null
  sender_phone: string | null
  recipient_email: string | null
  recipient_phone: string | null
  document_title: string | null
  file_name: string | null
  file_type: string | null
  mime_type: string | null
  file_size: number | null
  movements: CorrespondenceMovement[]
  attachments: CorrespondenceAttachment[]
  user_level_ids: number[]
  parent_reference: string | null
  workflow_status: WorkflowStatus | null
}

export interface CorrespondenceListResponse {
  total: number
  items: Correspondence[]
}

export interface CorrespondenceCreate {
  direction: CorrespondenceDirection
  subject: string
  body?: string | null
  priority?: CorrespondencePriority
  category_id?: number | null
  sender_name?: string | null
  sender_organization?: string | null
  sender_email?: string | null
  sender_phone?: string | null
  recipient_name?: string | null
  recipient_organization?: string | null
  recipient_email?: string | null
  recipient_phone?: string | null
  date_received?: string | null
  response_required?: boolean
  response_deadline?: string | null
  parent_correspondence_id?: number | null
  user_level_ids?: number[]
  document_id?: number | null
  author_signature_id?: number | null
}

export interface CorrespondenceUpdate {
  subject?: string
  body?: string
  priority?: CorrespondencePriority
  category_id?: number | null
  sender_name?: string | null
  sender_organization?: string | null
  sender_email?: string | null
  sender_phone?: string | null
  recipient_name?: string | null
  recipient_organization?: string | null
  recipient_email?: string | null
  recipient_phone?: string | null
  response_required?: boolean
  response_deadline?: string | null
  user_level_ids?: number[]
  author_signature_id?: number | null
}

export interface CorrespondenceSubmit {
  workflow_definition_id: number
  signature_id?: number | null
}

export interface CorrespondenceAssign {
  to_user_id: number
  remarks?: string | null
}

export interface CorrespondenceDispatch {
  dispatch_method: DispatchMethod
  dispatch_reference?: string | null
  remarks?: string | null
}

export interface NextReferenceResponse {
  reference: string
}
