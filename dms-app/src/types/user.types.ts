export type PermissionAction = 'view' | 'download' | 'create' | 'update' | 'delete'
export type RoleName = 'admin' | 'maker' | 'checker' | 'auditor' | 'superadmin'

export interface Permission {
  id: number
  action: PermissionAction
  description: string | null
}

export interface Role {
  id: number
  name: RoleName
  description: string | null
  created_at: string
  permissions: Permission[]
}

export interface AssignedCategory {
  id: number
  name: string
  description: string | null
  is_active: boolean
}

export interface UserLevel {
  id: number
  name: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface CompanySummary {
  id: number
  company_id: string
  full_name: string
  short_name: string
  address: string | null
  contact_person: string | null
  contact_no: string | null
  email_address: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface User {
  id: number
  full_name: string
  email: string
  is_active: boolean
  auth_provider: string
  must_change_password: boolean
  created_at: string
  updated_at: string
  roles: Role[]
  categories: AssignedCategory[]
  user_level: UserLevel | null
  company: CompanySummary | null
}

export interface UserListResponse {
  total: number
  skip: number
  limit: number
  items: User[]
}

export interface UserCreateRequest {
  full_name: string
  email: string
  password: string
  is_active: boolean
  role_ids: number[]
  category_ids?: number[]
  user_level_id?: number | null
  company_id?: number | null
}

export interface UserUpdateRequest {
  full_name?: string
  email?: string
  is_active?: boolean
  role_ids?: number[]
  category_ids?: number[]
  user_level_id?: number | null
  company_id?: number | null
}

export interface RoleCreateRequest {
  name: RoleName
  description?: string
  permission_ids: number[]
}

export interface UserLevelCreateRequest {
  name: string
  description?: string
  is_active?: boolean
}

export interface UserLevelUpdateRequest {
  name?: string
  description?: string
  is_active?: boolean
}
