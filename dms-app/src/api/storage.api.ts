import { apiClient } from './client'

export interface CategoryStorageUsage {
  category_id: number
  category_name: string
  db_size: number
  db_size_human: string
  disk_size: number
  disk_size_human: string
  document_count: number
  usage_percentage: number
}

export interface StorageUsageResponse {
  total_capacity: number
  total_capacity_human: string
  db_used: number
  db_used_human: string
  disk_used: number
  disk_used_human: string
  available_storage: number
  available_storage_human: string
  usage_percentage: number
  categories: CategoryStorageUsage[]
}

export interface CapacityResponse {
  capacity_gb: number
}

export const storageApi = {
  getUsage: () => apiClient.get<StorageUsageResponse>('/storage/usage').then((r) => r.data),
  getCapacity: () => apiClient.get<CapacityResponse>('/storage/capacity').then((r) => r.data),
  setCapacity: (capacityGb: number) =>
    apiClient.put<CapacityResponse>('/storage/capacity', { capacity_gb: capacityGb }).then((r) => r.data),
}
