export interface Directory {
  id: number
  name: string
  description: string | null
  category_id: number
  parent_id: number | null
  created_by: number
  created_at: string
  updated_at: string
}

export interface DirectoryNode extends Directory {
  children: DirectoryNode[]
  document_count: number
}

export interface DirectoryCreateRequest {
  name: string
  description?: string
  category_id: number
  parent_id?: number | null
}

export interface DirectoryUpdateRequest {
  name?: string
  description?: string
}
