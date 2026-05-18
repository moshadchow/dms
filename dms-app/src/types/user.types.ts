export type PermissionAction = 'view' | 'download' | 'create' | 'update' | 'delete'
export type RoleName = 'admin' | 'maker' | 'checker' | 'auditor'

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

export interface User {
  id: number
  full_name: string
  email: string
  is_active: boolean
  created_at: string
  updated_at: string
  roles: Role[]
  categories: AssignedCategory[]
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
}

export interface UserUpdateRequest {
  full_name?: string
  email?: string
  is_active?: boolean
  role_ids?: number[]
  category_ids?: number[]
}

export interface RoleCreateRequest {
  name: RoleName
  description?: string
  permission_ids: number[]
}
