const API_VERSION_PREFIX = '/api/v1'

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, '')
}

function normalizeApiRoot(value: string | undefined): string {
  const raw = trimTrailingSlash(value?.trim() ?? '')

  if (!raw) {
    return API_VERSION_PREFIX
  }

  if (raw.endsWith(API_VERSION_PREFIX)) {
    return raw
  }

  if (raw.endsWith('/api')) {
    return `${raw}/v1`
  }

  return `${raw}${API_VERSION_PREFIX}`
}

export const apiRoot = normalizeApiRoot(import.meta.env.VITE_API_BASE_URL)
