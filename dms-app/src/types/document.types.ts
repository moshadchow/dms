export type FileType = 'pdf' | 'excel' | 'image'
export type DocumentStatus = 'active' | 'archived' | 'deleted'

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
