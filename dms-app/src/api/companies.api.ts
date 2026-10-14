import { apiClient } from './client'
import type { Company, CompanyCreateRequest, CompanyUpdateRequest, AzureConfig, AzureConfigUpdateRequest } from '@/types/company.types'

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

  getAzureConfig: async (id: number): Promise<AzureConfig> => {
    const { data } = await apiClient.get(`/companies/${id}/azure-config`)
    return data
  },

  updateAzureConfig: async (id: number, config: AzureConfigUpdateRequest): Promise<AzureConfig> => {
    const { data } = await apiClient.put(`/companies/${id}/azure-config`, config)
    return data
  },

  deleteAzureConfig: async (id: number): Promise<AzureConfig> => {
    const { data } = await apiClient.delete(`/companies/${id}/azure-config`)
    return data
  },
}
