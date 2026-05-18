export type FileType = 'pdf' | 'docx' | 'excel' | 'image'
export type DocumentStatus = 'active' | 'archived' | 'deleted'
export type AnnotationAnchorType = 'point' | 'text_range'
export type DocumentVariantStatus = 'active' | 'deleted'
export type DocumentVariantType = 'private_annotation'

export interface DocumentAnnotation {
  id: number
  variant_id: number
  page_number: number | null
  anchor_type: AnnotationAnchorType
  anchor_data: Record<string, unknown>
  note_text: string
  color: string
  created_at: string
  updated_at: string
}

export interface DocumentVariant {
  id: number
  source_document_id: number
  owner_user_id: number
  category_id: number
  directory_id: number
  variant_type: DocumentVariantType
  status: DocumentVariantStatus
  title: string
  source_file_name: string
  source_mime_type: string
  file_type: FileType
  file_size: number
  created_at: string
  updated_at: string
}

export interface Document {
  id: number
  title: string
  description: string | null
  directory_id: number
  uploaded_by: number
  file_name: string
  file_type: FileType
  mime_type: string
  file_size: number
  status: DocumentStatus
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  total: number
  page: number
  limit: number
  items: Document[]
}

export interface DocumentAnnotationRequest {
  page_number?: number | null
  anchor_type: AnnotationAnchorType
  anchor_data: Record<string, unknown>
  note_text: string
  color: string
}

export interface DocumentVariantSaveRequest {
  annotations: DocumentAnnotationRequest[]
}

export interface DocumentWorkspaceResponse {
  document: Document
  variant: DocumentVariant | null
  annotations: DocumentAnnotation[]
  preview_html: string | null
  preview_error: string | null
  has_private_variant: boolean
}

export interface DocumentUpdateRequest {
  title?: string
  description?: string
  status?: DocumentStatus
}

export interface DocumentListParams {
  directory_id?: number
  category_id?: number
  file_type?: FileType
  search?: string
  skip?: number
  limit?: number
}
