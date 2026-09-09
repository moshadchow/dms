import { apiClient } from './client'
import type { Company, CompanyCreateRequest, CompanyUpdateRequest } from '@/types/company.types'

export const companiesApi = {
  list: async (params?: {
    skip?: number
    limit?: number
    search?: string
    is_active?: boolean
  }): Promise<{ total: number; skip: number; limit: number; items: Company[] }> => {
    const { data } = await apiClient.get('/companies', { params })
    return data
  },

  get: async (id: number): Promise<Company> => {
    const { data } = await apiClient.get(`/companies/${id}`)
    return data
  },

  create: async (companyData: CompanyCreateRequest): Promise<Company> => {
    const { data } = await apiClient.post('/companies', companyData)
    return data
  },

  update: async (id: number, companyData: CompanyUpdateRequest): Promise<Company> => {
    const { data } = await apiClient.patch(`/companies/${id}`, companyData)
    return data
  },

  activate: async (id: number): Promise<Company> => {
    const { data } = await apiClient.patch(`/companies/${id}/activate`)
    return data
  },

  deactivate: async (id: number): Promise<Company> => {
    const { data } = await apiClient.patch(`/companies/${id}/deactivate`)
    return data
  },
}
