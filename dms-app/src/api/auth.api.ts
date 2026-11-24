import { apiClient } from './client'
import type { TokenResponse, LoginRequest, ChangePasswordRequest, LoginResponse, SelectCompanyRequest, CompanyOption } from '@/types/auth.types'
import type { User } from '@/types/user.types'

export const authApi = {
  login: async (data: LoginRequest): Promise<LoginResponse> => {
    const res = await apiClient.post<LoginResponse>('/auth/login', data)
    return res.data
  },

  selectCompany: async (data: SelectCompanyRequest): Promise<LoginResponse> => {
    const res = await apiClient.post<LoginResponse>('/auth/select-company', data)
    return res.data
  },

  refresh: async (refreshToken: string): Promise<TokenResponse> => {
    const res = await apiClient.post<TokenResponse>('/auth/refresh', {
      refresh_token: refreshToken,
    })
    return res.data
  },

  companiesByEmail: async (email: string): Promise<CompanyOption[]> => {
    const res = await apiClient.get<CompanyOption[]>(`/auth/companies`, { params: { email } })
    return res.data
  },
  me: async (): Promise<User> => {
    const res = await apiClient.get<User>('/auth/me')
    return res.data
  },

  changePassword: async (data: ChangePasswordRequest): Promise<void> => {
    await apiClient.post('/auth/change-password', data)
  },
}
