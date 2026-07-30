export interface AuditLog {
  id: number
  timestamp: string
  user_id: number | null
  username: string | null
  full_name: string | null
  auth_provider: string | null
  role: string | null
  user_level: string | null
  module: string
  entity_name: string | null
  entity_id: string | null
  action: string
  old_value: string | null
  new_value: string | null
  description: string | null
  ip_address: string | null
  browser: string | null
  operating_system: string | null
  device: string | null
  request_url: string | null
  http_method: string | null
  http_status: number | null
  session_id: string | null
  correlation_id: string | null
  is_success: boolean
  failure_reason: string | null
  created_at: string
}

export interface AuditLogListResponse {
  total: number
  page: number
  limit: number
  items: AuditLog[]
}

export interface AuditLogFilters {
  start_date?: string
  end_date?: string
  user_id?: number
  module?: string
  action?: string
  entity_name?: string
  entity_id?: string
  role?: string
  user_level?: string
  auth_provider?: string
  ip_address?: string
  is_success?: boolean
  search?: string
  sort_by?: string
  sort_order?: 'asc' | 'desc'
  skip?: number
  limit?: number
}
