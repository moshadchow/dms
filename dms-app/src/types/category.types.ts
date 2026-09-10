export interface Category {
  id: number
  name: string
  description: string | null
  is_active: boolean
  company_id: number
  created_by: number | null
  created_at: string
  updated_at: string
  directory_count: number
  document_count: number
}

export interface CategoryCreateRequest {
  name: string
  description?: string
  is_active?: boolean
}

export interface CategoryUpdateRequest {
  name?: string
  description?: string
  is_active?: boolean
}
