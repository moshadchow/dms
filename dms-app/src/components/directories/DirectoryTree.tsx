import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { directoriesApi } from '@/api/directories.api'
import { useDirectoryStore } from '@/store/directoryStore'
import { usePermissions } from '@/hooks/usePermissions'
import { getErrorMessage } from '@/api/client'
import DirectoryFormModal from './DirectoryFormModal'
import ConfirmDialog from '@/components/ui/ConfirmDialog'
import type { DirectoryNode, Directory } from '@/types/directory.types'

interface Props {
  categoryId: number
  tree:       DirectoryNode[]
  onRefresh:  () => void
}

interface ContextMenu {
  node: DirectoryNode
  x:    number
  y:    number
}

export default function DirectoryTree({ categoryId, tree, onRefresh }: Props) {
  const { selectedDirectoryId, expandedIds, setSelectedDirectory, toggleExpanded } = useDirectoryStore()
  const { canCreate, canUpdate, canDelete } = usePermissions()
  const navigate = useNavigate()

  // ── Modal state ───────────────────────────────────────────────────
  const [formOpen, setFormOpen]           = useState(false)
  const [editingDir, setEditingDir]       = useState<Directory | null>(null)
  const [parentId, setParentId]           = useState<number | null>(null)
  const [contextMenu, setContextMenu]     = useState<ContextMenu | null>(null)
  const [deletingDir, setDeletingDir]     = useState<DirectoryNode | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)

  // ── Actions ───────────────────────────────────────────────────────
  const openCreate = (pid: number | null = null) => {
    setEditingDir(null)
    setParentId(pid)
    setContextMenu(null)
    setFormOpen(true)   // must come last so state is set before render
  }

  const openEdit = (node: DirectoryNode) => {
    setEditingDir(node)
    setParentId(null)
    setContextMenu(null)
    setFormOpen(true)
  }

  const handleSelect = (node: DirectoryNode) => {
    setSelectedDirectory(node.id)
    navigate(`/directory/${node.id}`)
  }

  const handleFormSuccess = (_dir: Directory) => {
    onRefresh()
  }

  const handleDeleteConfirm = async () => {
    if (!deletingDir) return
    setDeleteLoading(true)
    try {
      await directoriesApi.delete(deletingDir.id)
      toast.success('Directory deleted')
      if (selectedDirectoryId === deletingDir.id) {
        setSelectedDirectory(null)
        navigate('/dashboard')
      }
      onRefresh()
      setDeletingDir(null)
    } catch (err) {
      // Show the exact backend message — keep dialog closed so user sees toast
      const msg = getErrorMessage(err)
      toast.error(msg, { duration: 6000 })
      setDeletingDir(null)
    } finally {
      setDeleteLoading(false)
    }
  }

  // ── Render ────────────────────────────────────────────────────────
  // NOTE: modals are ALWAYS rendered at the bottom regardless of tree state.
  // The early-return pattern was the bug — it skipped the modal JSX.

  return (
    <>
      {/* ── Empty state ── */}
      {tree.length === 0 && (
        <div style={{ padding: '2rem 1rem', textAlign: 'center' }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#cbd5e1" strokeWidth="1.5" style={{ margin: '0 auto 0.75rem', display: 'block' }}>
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-tertiary)', margin: '0 0 0.75rem' }}>No directories yet</p>
          {canCreate && (
            <button
              onClick={() => openCreate(null)}
              style={{ padding: '7px 16px', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              Create first directory
            </button>
          )}
        </div>
      )}

      {/* ── Tree with nodes ── */}
      {tree.length > 0 && (
        <>
          {/* New root directory button */}
          {canCreate && (
            <div style={{ padding: '0.5rem 0.75rem 0.25rem' }}>
              <button
                onClick={() => openCreate(null)}
                style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 8px', backgroundColor: 'transparent', border: '1px dashed #e2e8f0', borderRadius: '7px', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text-tertiary)', cursor: 'pointer', fontFamily: 'inherit' }}
              >
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                New directory
              </button>
            </div>
          )}

          {/* Tree nodes */}
          <div style={{ padding: '0.25rem 0.5rem' }}>
            {tree.map((node) => (
              <TreeNode
                key={node.id}
                node={node}
                depth={0}
                selectedId={selectedDirectoryId}
                expandedIds={expandedIds}
                onSelect={handleSelect}
                onToggle={toggleExpanded}
                onContextMenu={(e, n) => {
                  e.preventDefault()
                  e.stopPropagation()
                  setContextMenu({ node: n, x: e.clientX, y: e.clientY })
                }}
              />
            ))}
          </div>
        </>
      )}

      {/* ── Context menu ── */}
      {contextMenu && (
        <>
          <div style={{ position: 'fixed', inset: 0, zIndex: 40 }} onClick={() => setContextMenu(null)} />
          <div style={{ position: 'fixed', top: contextMenu.y, left: contextMenu.x, zIndex: 50, backgroundColor: 'var(--surface)', borderRadius: '10px', border: '1px solid var(--border)', boxShadow: '0 8px 24px rgba(0,0,0,0.12)', minWidth: '180px', overflow: 'hidden', padding: '0.3rem' }}>
            <p style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-tertiary)', padding: '6px 10px 2px', margin: 0, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              {contextMenu.node.name}
            </p>
            {canCreate && (
              <button onClick={() => openCreate(contextMenu.node.id)} style={ctxItemStyle}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
                New subdirectory
              </button>
            )}
            {canUpdate && (
              <button onClick={() => openEdit(contextMenu.node)} style={ctxItemStyle}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                Rename
              </button>
            )}
            {canDelete && (
              <>
                <div style={{ height: '1px', backgroundColor: 'var(--bg)', margin: '0.2rem 0' }} />
                <button onClick={() => { setDeletingDir(contextMenu.node); setContextMenu(null) }} style={{ ...ctxItemStyle, color: '#dc2626' }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                  Delete
                </button>
              </>
            )}
          </div>
        </>
      )}

      {/* ── Modals — always rendered so they're in the DOM when opened ── */}
      <DirectoryFormModal
        isOpen={formOpen}
        categoryId={categoryId}
        parentId={editingDir ? null : parentId}
        editing={editingDir}
        onClose={() => { setFormOpen(false); setEditingDir(null) }}
        onSuccess={handleFormSuccess}
      />

      <ConfirmDialog
        isOpen={!!deletingDir}
        title="Delete directory"
        message={`Delete "${deletingDir?.name}"? This only works if the directory has no subdirectories and no documents. Remove those first, then delete.`}
        confirmLabel="Delete"
        danger
        loading={deleteLoading}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeletingDir(null)}
      />
    </>
  )
}

// ── Recursive node ────────────────────────────────────────────────

interface NodeProps {
  node:          DirectoryNode
  depth:         number
  selectedId:    number | null
  expandedIds:   Set<number>
  onSelect:      (node: DirectoryNode) => void
  onToggle:      (id: number) => void
  onContextMenu: (e: React.MouseEvent, node: DirectoryNode) => void
}

function TreeNode({ node, depth, selectedId, expandedIds, onSelect, onToggle, onContextMenu }: NodeProps) {
  const isSel  = selectedId === node.id
  const isExp  = expandedIds.has(node.id)
  const hasCh  = node.children.length > 0

  return (
    <div>
      <div
        style={{ display: 'flex', alignItems: 'center', paddingLeft: `${depth * 14}px` }}
        onContextMenu={(e) => onContextMenu(e, node)}
      >
        {/* Expand chevron */}
        <button
          onClick={() => hasCh && onToggle(node.id)}
          style={{ width: '22px', height: '30px', flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', border: 'none', background: 'none', cursor: hasCh ? 'pointer' : 'default', color: 'var(--text-muted)', padding: 0 }}
        >
          {hasCh && (
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
              style={{ transform: isExp ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 150ms' }}>
              <polyline points="9 18 15 12 9 6"/>
            </svg>
          )}
        </button>

        {/* Directory button */}
        <button
          onClick={() => onSelect(node)}
          style={{ flex: 1, display: 'flex', alignItems: 'center', gap: '7px', padding: '5px 7px', borderRadius: '7px', border: 'none', backgroundColor: isSel ? '#eef2ff' : 'transparent', cursor: 'pointer', textAlign: 'left', fontFamily: 'inherit' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill={isSel ? '#4f46e5' : 'none'} stroke={isSel ? '#4f46e5' : 'var(--text-tertiary)'} strokeWidth="2">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          <span style={{ fontSize: '0.84rem', fontWeight: isSel ? 600 : 400, color: isSel ? '#4f46e5' : 'var(--text-secondary)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {node.name}
          </span>
          {node.document_count > 0 && (
            <span style={{ fontSize: '0.65rem', fontWeight: 600, backgroundColor: isSel ? '#e0e7ff' : 'var(--surface-2)', color: isSel ? '#4f46e5' : 'var(--text-tertiary)', padding: '1px 6px', borderRadius: '999px', flexShrink: 0 }}>
              {node.document_count}
            </span>
          )}
        </button>
      </div>

      {isExp && hasCh && node.children.map((ch) => (
        <TreeNode
          key={ch.id}
          node={ch}
          depth={depth + 1}
          selectedId={selectedId}
          expandedIds={expandedIds}
          onSelect={onSelect}
          onToggle={onToggle}
          onContextMenu={onContextMenu}
        />
      ))}
    </div>
  )
}

const ctxItemStyle: React.CSSProperties = {
  width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
  padding: '6px 10px', border: 'none', borderRadius: '7px',
  backgroundColor: 'transparent', cursor: 'pointer',
  fontSize: '0.84rem', fontWeight: 500, color: 'var(--text-secondary)',
  textAlign: 'left', fontFamily: 'inherit',
}
