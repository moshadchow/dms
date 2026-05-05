import { create } from 'zustand'
import type { DirectoryNode } from '@/types/directory.types'

interface DirectoryState {
  selectedCategoryId:  number | null
  selectedDirectoryId: number | null
  tree:                DirectoryNode[]
  expandedIds:         Set<number>
  categoriesVersion:   number   // bump → sidebar reloads category list
  directoriesVersion:  number   // bump → sidebar busts treeMap cache

  setSelectedCategory:  (id: number | null) => void
  setSelectedDirectory: (id: number | null) => void
  setTree:              (tree: DirectoryNode[]) => void
  toggleExpanded:       (id: number) => void
  resetTree:            () => void
  refreshCategories:    () => void
  refreshDirectories:   () => void  // call after any directory create/rename/delete
}

export const useDirectoryStore = create<DirectoryState>((set, get) => ({
  selectedCategoryId:  null,
  selectedDirectoryId: null,
  tree:                [],
  expandedIds:         new Set(),
  categoriesVersion:   0,
  directoriesVersion:  0,

  setSelectedCategory:  (id) =>
    set({ selectedCategoryId: id, selectedDirectoryId: null, tree: [] }),

  setSelectedDirectory: (id) => set({ selectedDirectoryId: id }),

  setTree: (tree) => set({ tree }),

  toggleExpanded: (id) => {
    const next = new Set(get().expandedIds)
    next.has(id) ? next.delete(id) : next.add(id)
    set({ expandedIds: next })
  },

  resetTree: () =>
    set({ selectedCategoryId: null, selectedDirectoryId: null, tree: [], expandedIds: new Set() }),

  refreshCategories: () =>
    set((state) => ({ categoriesVersion: state.categoriesVersion + 1 })),

  refreshDirectories: () =>
    set((state) => ({ directoriesVersion: state.directoriesVersion + 1 })),
}))
