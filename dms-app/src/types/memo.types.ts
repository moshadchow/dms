import type { WorkflowStatus } from './workflow.types'

export interface MemoAttachment {
  id: number
  memo_id: number
  document_id: number
  document_title: string | null
  file_name: string | null
  file_type: string | null
  mime_type: string | null
  file_size: number | null
  created_at: string
}

export interface Memo {
  id: number
  document_id: number
  memo_date: string
  subject: string
  body: string
  author_signature_id: number | null
  created_by: number
  created_by_name: string | null
  created_at: string
  updated_at: string
  workflow_status: WorkflowStatus | null
}

export interface MemoDetail extends Memo {
  directory_id?: number | null
  document_title: string | null
  file_name: string | null
  file_type: string | null
  mime_type: string | null
  file_size: number | null
  attachments: MemoAttachment[]
  user_level_ids: number[]
}

export interface MemoListResponse {
  total: number
  page: number
  limit: number
  items: Memo[]
}

export interface MemoCreate {
  directory_id: number
  user_level_ids: number[]
  memo_date?: string | null
  subject: string
  body: string
  attachment_document_ids?: number[]
}

export interface MemoUpdate {
  memo_date?: string | null
  subject?: string
  body?: string
  user_level_ids?: number[]
  attachment_document_ids?: number[]
}

export interface MemoSubmit {
  workflow_definition_id: number
  signature_id?: number | null
}
