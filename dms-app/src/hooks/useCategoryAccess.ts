import { useAuthStore } from '@/store/authStore'

export function useCategoryAccess() {
  const user = useAuthStore((state) => state.user)
  const isAdmin = useAuthStore((state) => state.isAdmin)
  const canAccessCategory = useAuthStore((state) => state.canAccessCategory)

  return {
    isAdmin: isAdmin(),
    assignedCategoryIds: user?.categories.map((category) => category.id) ?? [],
    canAccessCategory,
  }
}
