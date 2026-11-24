export interface CompanyOption {
  id: number
  name: string
}

export interface LoginResponse {
  access_token?: string
  refresh_token?: string
  token_type: string
  requires_company_selection?: boolean
  selection_token?: string
  companies?: CompanyOption[]
}

export interface LoginRequest {
  email: string
  password: string
  company_id?: number
}

export interface RefreshRequest {
  refresh_token: string
}

export interface SelectCompanyRequest {
  selection_token: string
  company_id: number
}
