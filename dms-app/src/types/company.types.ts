export interface Company {
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

export interface CompanyCreateRequest {
  company_id: string
  full_name: string
  short_name: string
  address?: string
  contact_person?: string
  contact_no?: string
  email_address?: string
  is_active?: boolean
}

export interface CompanyUpdateRequest {
  company_id?: string
  full_name?: string
  short_name?: string
  address?: string
  contact_person?: string
  contact_no?: string
  email_address?: string
  is_active?: boolean
}
