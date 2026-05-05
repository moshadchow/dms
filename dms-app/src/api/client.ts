import axios from 'axios'
import type { InternalAxiosRequestConfig } from 'axios'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export const apiClient = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request: inject Bearer token ──────────────────────────────────
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response: handle 401 (token refresh) only ─────────────────────
apiClient.interceptors.response.use(
  (response) => response,
  async (error: unknown) => {
    if (!axios.isAxiosError(error)) return Promise.reject(error)

    const status = error.response?.status

    // Only attempt refresh for 401 — all other errors pass through as-is
    if (status !== 401) {
      return Promise.reject(error)
    }

    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Avoid infinite retry loop
    if (originalRequest._retry) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    originalRequest._retry = true
    const refreshToken = localStorage.getItem('refresh_token')

    if (!refreshToken) {
      window.location.href = '/login'
      return Promise.reject(error)
    }

    try {
      const { data } = await axios.post(`${BASE_URL}/api/v1/auth/refresh`, {
        refresh_token: refreshToken,
      })
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('refresh_token', data.refresh_token)
      if (originalRequest.headers) {
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`
      }
      return apiClient(originalRequest)
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
      return Promise.reject(error)
    }
  }
)

// ── Extract readable error message from backend response ──────────
export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    const httpStatus = error.response?.status

    // FastAPI detail — string (most common)
    if (typeof data?.detail === 'string' && data.detail.trim()) {
      return data.detail
    }

    // FastAPI validation errors — array of {msg, loc, type}
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      return data.detail.map((e: { msg: string }) => e.msg).join(', ')
    }

    // Plain message field (some APIs)
    if (typeof data?.message === 'string' && data.message.trim()) {
      return data.message
    }

    // Meaningful HTTP status fallbacks
    switch (httpStatus) {
      case 400: return 'Bad request — please check your input'
      case 401: return 'Session expired — please log in again'
      case 403: return 'You do not have permission to perform this action'
      case 404: return 'Resource not found'
      case 409: return 'Conflict: this operation cannot be completed'
      case 413: return 'File is too large (max 50 MB)'
      case 422: return 'Validation error — please check your input'
      case 500: return 'Server error — please try again later'
    }
  }

  if (error instanceof Error && error.message) {
    return error.message
  }

  return 'An unexpected error occurred'
}
