import { create } from 'zustand'
import { workflowApi } from '@/api/workflow.api'

interface WorkflowState {
  pendingCount: number
  refreshPendingCount: () => Promise<void>
}

export const useWorkflowStore = create<WorkflowState>()((set) => ({
  pendingCount: 0,

  refreshPendingCount: async () => {
    try {
      const res = await workflowApi.getPendingInstances({ limit: 1 })
      set({ pendingCount: res.total })
    } catch {
      // silently ignore — badge is non-critical
    }
  },
}))
