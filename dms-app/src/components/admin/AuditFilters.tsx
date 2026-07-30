import { useState } from 'react'
import type { AuditLogFilters } from '@/types/audit.types'

interface Props {
  filters: AuditLogFilters
  onChange: (filters: AuditLogFilters) => void
}

const MODULES = ['', 'auth', 'users', 'documents', 'directories', 'categories', 'user_levels', 'security']
const ACTIONS = [
  '', 'login', 'logout', 'failed_login', 'password_changed',
  'create_user', 'update_user', 'delete_user', 'deactivate_user',
  'upload_document', 'update_document', 'delete_document', 'download_document',
  'archive_document', 'restore_document',
  'create_directory', 'rename_directory', 'delete_directory',
  'create_category', 'update_category', 'delete_category',
  'create_user_level', 'update_user_level', 'delete_user_level',
  'unauthorized_access', 'permission_denied',
]

export default function AuditFilters({ filters, onChange }: Props) {
  const [expanded, setExpanded] = useState(false)

  const update = (patch: Partial<AuditLogFilters>) => {
    onChange({ ...filters, ...patch })
  }

  return (
    <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)' }}>
      {/* Main row */}
      <div style={{ display: 'flex', gap: '0.625rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <div style={{ flex: 1, minWidth: '200px', position: 'relative' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2"
            style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}>
            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            className="input"
            placeholder="Search audit logs..."
            value={filters.search || ''}
            onChange={(e) => update({ search: e.target.value || undefined })}
            style={{ paddingLeft: '32px', fontSize: '0.82rem' }}
          />
        </div>
        <select className="input" value={filters.module || ''} onChange={(e) => update({ module: e.target.value || undefined })}
          style={{ width: '140px', fontSize: '0.82rem' }}>
          <option value="">All modules</option>
          {MODULES.filter(Boolean).map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select className="input" value={filters.is_success === undefined ? '' : String(filters.is_success)}
          onChange={(e) => update({ is_success: e.target.value === '' ? undefined : e.target.value === 'true' })}
          style={{ width: '130px', fontSize: '0.82rem' }}>
          <option value="">All status</option>
          <option value="true">Success</option>
          <option value="false">Failed</option>
        </select>
        <button
          onClick={() => setExpanded(!expanded)}
          style={{
            padding: '7px 12px', borderRadius: '8px', border: '1px solid var(--border)',
            backgroundColor: expanded ? 'var(--primary-soft)' : 'var(--surface)',
            color: expanded ? 'var(--primary)' : 'var(--text-secondary)',
            cursor: 'pointer', fontSize: '0.82rem', fontFamily: 'inherit', fontWeight: 500,
          }}
        >
          {expanded ? 'Less filters' : 'More filters'}
        </button>
      </div>

      {/* Expanded filters */}
      {expanded && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '0.625rem', marginTop: '0.75rem' }}>
          <div>
            <label style={labelStyle}>Action</label>
            <select className="input" value={filters.action || ''} onChange={(e) => update({ action: e.target.value || undefined })}
              style={{ width: '100%', fontSize: '0.82rem' }}>
              <option value="">All actions</option>
              {ACTIONS.filter(Boolean).map(a => <option key={a} value={a}>{formatAction(a)}</option>)}
            </select>
          </div>
          <div>
            <label style={labelStyle}>Date From</label>
            <input type="datetime-local" className="input" value={filters.start_date || ''}
              onChange={(e) => update({ start_date: e.target.value || undefined })}
              style={{ width: '100%', fontSize: '0.82rem' }} />
          </div>
          <div>
            <label style={labelStyle}>Date To</label>
            <input type="datetime-local" className="input" value={filters.end_date || ''}
              onChange={(e) => update({ end_date: e.target.value || undefined })}
              style={{ width: '100%', fontSize: '0.82rem' }} />
          </div>
          <div>
            <label style={labelStyle}>IP Address</label>
            <input className="input" placeholder="Filter by IP" value={filters.ip_address || ''}
              onChange={(e) => update({ ip_address: e.target.value || undefined })}
              style={{ width: '100%', fontSize: '0.82rem' }} />
          </div>
          <div>
            <label style={labelStyle}>Entity</label>
            <select className="input" value={filters.entity_name || ''} onChange={(e) => update({ entity_name: e.target.value || undefined })}
              style={{ width: '100%', fontSize: '0.82rem' }}>
              <option value="">All entities</option>
              <option value="user">User</option>
              <option value="document">Document</option>
              <option value="directory">Directory</option>
              <option value="category">Category</option>
              <option value="user_level">User Level</option>
              <option value="role">Role</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Sort By</label>
            <select className="input" value={filters.sort_by || 'timestamp'}
              onChange={(e) => update({ sort_by: e.target.value })}
              style={{ width: '100%', fontSize: '0.82rem' }}>
              <option value="timestamp">Timestamp</option>
              <option value="user_id">User</option>
              <option value="module">Module</option>
              <option value="action">Action</option>
            </select>
          </div>
        </div>
      )}
    </div>
  )
}

function formatAction(action: string): string {
  return action.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-tertiary)',
  marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em',
}
