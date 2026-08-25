import { useState, useEffect, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { workflowApi } from '@/api/workflow.api'
import Button from '@/components/ui/Button'
import WorkflowFormModal from '@/components/admin/WorkflowFormModal'
import type {
  WorkflowDefinition,
  WorkflowDefinitionDetail,
} from '@/types/workflow.types'

const LIMIT = 20

export default function WorkflowConfigPanel() {
  const [definitions, setDefinitions] = useState<WorkflowDefinition[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<boolean | ''>('')
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<WorkflowDefinitionDetail | null>(null)

  const loadDefinitions = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {
        skip: (page - 1) * LIMIT,
        limit: LIMIT,
      }
      if (statusFilter !== '') params.is_active = statusFilter
      const data = await workflowApi.list(params as { skip?: number; limit?: number; is_active?: boolean })
      setDefinitions(data.items)
      setTotal(data.total)
    } catch {
      toast.error('Failed to load workflow definitions')
    } finally {
      setLoading(false)
    }
  }, [page, statusFilter])

  useEffect(() => { loadDefinitions() }, [loadDefinitions])
  useEffect(() => { setPage(1) }, [statusFilter])

  const totalPages = Math.ceil(total / LIMIT) || 1

  const handleToggleActive = async (def: WorkflowDefinition) => {
    try {
      if (def.is_active) {
        await workflowApi.deactivate(def.id)
        toast.success('Workflow deactivated')
      } else {
        await workflowApi.activate(def.id)
        toast.success('Workflow activated')
      }
      loadDefinitions()
    } catch {
      toast.error('Failed to update workflow status')
    }
  }

  const handleCreate = () => {
    setEditing(null)
    setModalOpen(true)
  }

  const handleEdit = async (def: WorkflowDefinition) => {
    try {
      const detail = await workflowApi.get(def.id)
      setEditing(detail)
      setModalOpen(true)
    } catch {
      toast.error('Failed to load workflow details')
    }
  }

  const handleModalSuccess = () => {
    setModalOpen(false)
    setEditing(null)
    loadDefinitions()
  }

  return (
    <div>
      {/* Header */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
        padding: '1.25rem 1.5rem', marginBottom: '1.25rem',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem',
      }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            Workflow Definitions
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '3px 0 0' }}>
            Configure approval workflows for document categories
          </p>
        </div>
        <Button onClick={handleCreate} size="md">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Create Workflow
        </Button>
      </div>

      {/* Main card */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem',
        border: '1px solid var(--border)', overflow: 'hidden',
      }}>
        {/* Filters */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem 1.25rem',
          borderBottom: '1px solid var(--border)', flexWrap: 'wrap',
        }}>
          <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Status
          </label>
          <select
            value={statusFilter === '' ? '' : String(statusFilter)}
            onChange={(e) => {
              if (e.target.value === '') setStatusFilter('')
              else setStatusFilter(e.target.value === 'true')
            }}
            style={{
              padding: '6px 10px', borderRadius: '8px', border: '1px solid var(--border)',
              backgroundColor: 'var(--bg)', color: 'var(--text)', fontSize: '0.82rem',
              fontFamily: 'inherit', minWidth: '130px',
            }}
          >
            <option value="">All Statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>

          {statusFilter !== '' && (
            <button
              onClick={() => setStatusFilter('')}
              style={{
                padding: '5px 10px', borderRadius: '7px', border: '1px solid var(--border)',
                backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.78rem',
                cursor: 'pointer', fontFamily: 'inherit', marginLeft: 'auto',
              }}
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Table */}
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '3rem' }}>
            <div style={{
              width: '28px', height: '28px',
              border: '3px solid #e2e8f0', borderTopColor: '#4f46e5',
              borderRadius: '50%', animation: 'spin 0.7s linear infinite',
            }} />
            <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
          </div>
        ) : definitions.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center' }}>
            <p style={{ color: 'var(--text-tertiary)', fontSize: '0.875rem' }}>No workflow definitions found</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={thStyle}>Name</th>
                  <th style={{ ...thStyle, textAlign: 'center' }}>Steps</th>
                  <th style={thStyle}>Status</th>
                  <th style={thStyle}>Created</th>
                  <th style={{ ...thStyle, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {definitions.map((def) => (
                  <tr key={def.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={tdStyle}>
                      <div>
                        <span style={{ fontWeight: 600 }}>{def.name}</span>
                        {def.description && (
                          <span style={{ display: 'block', fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                            {def.description}
                          </span>
                        )}
                      </div>
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'center' }}>
                      <span style={{ color: 'var(--text-tertiary)' }}>--</span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        display: 'inline-block', padding: '2px 10px', borderRadius: '999px',
                        fontSize: '0.72rem', fontWeight: 600,
                        backgroundColor: def.is_active ? '#dcfce7' : '#f1f5f9',
                        color: def.is_active ? '#166534' : '#64748b',
                      }}>
                        {def.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ color: 'var(--text-tertiary)', fontSize: '0.8rem' }}>
                        {new Date(def.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <button
                          onClick={() => handleEdit(def)}
                          style={{
                            padding: '4px 10px', borderRadius: '6px', border: '1px solid var(--border)',
                            backgroundColor: 'var(--surface)', cursor: 'pointer', fontSize: '0.75rem',
                            color: 'var(--text-secondary)', fontFamily: 'inherit',
                          }}
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => handleToggleActive(def)}
                          style={{
                            padding: '4px 10px', borderRadius: '6px', border: '1px solid var(--border)',
                            backgroundColor: def.is_active ? 'transparent' : 'transparent',
                            cursor: 'pointer', fontSize: '0.75rem', fontFamily: 'inherit',
                            color: def.is_active ? '#b91c1c' : '#15803d',
                          }}
                        >
                          {def.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: '0.5rem', padding: '1rem', borderTop: '1px solid var(--border)',
          }}>
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              style={pageBtn}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              style={pageBtn}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* Modal */}
      <WorkflowFormModal
        isOpen={modalOpen}
        editing={editing}
        onClose={() => { setModalOpen(false); setEditing(null) }}
        onSuccess={handleModalSuccess}
      />
    </div>
  )
}

const thStyle: React.CSSProperties = {
  padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 600,
  color: 'var(--text-secondary)', fontSize: '0.75rem', textTransform: 'uppercase',
  letterSpacing: '0.05em', whiteSpace: 'nowrap',
}

const tdStyle: React.CSSProperties = {
  padding: '0.75rem 1rem', color: 'var(--text)', verticalAlign: 'middle',
}

const pageBtn: React.CSSProperties = {
  padding: '5px 12px', borderRadius: '7px', border: '1px solid var(--border)',
  backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem',
  cursor: 'pointer', fontFamily: 'inherit', display: 'inline-flex', alignItems: 'center',
}
