import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { companiesApi } from '@/api/companies.api'
import { useAuthStore } from '@/store/authStore'
import CompanyFormModal from '@/components/admin/CompanyFormModal'
import type { Company } from '@/types/company.types'

export default function CompanyProfilePage() {
  const navigate = useNavigate()
  const { isSuperAdmin } = useAuthStore()

  useEffect(() => {
    if (!isSuperAdmin()) { navigate('/dashboard', { replace: true }) }
  }, [])

  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterActive, setFilterActive] = useState<string>('')
  const [formOpen, setFormOpen] = useState(false)
  const [editingCompany, setEditingCompany] = useState<Company | null>(null)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const LIMIT = 20

  const loadCompanies = useCallback(async () => {
    setLoading(true)
    try {
      const data = await companiesApi.list({
        skip: (page - 1) * LIMIT,
        limit: LIMIT,
        search: search.trim() || undefined,
        is_active: filterActive === '' ? undefined : filterActive === 'true',
      })
      setCompanies(data.items)
      setTotal(data.total)
    } catch {
      toast.error('Failed to load companies')
    } finally {
      setLoading(false)
    }
  }, [page, search, filterActive])

  useEffect(() => { loadCompanies() }, [loadCompanies])
  useEffect(() => { setPage(1) }, [search, filterActive])

  const totalPages = Math.ceil(total / LIMIT) || 1

  const handleToggleActive = async (company: Company) => {
    try {
      if (company.is_active) {
        await companiesApi.deactivate(company.id)
        toast.success(`Deactivated ${company.short_name}`)
      } else {
        await companiesApi.activate(company.id)
        toast.success(`Activated ${company.short_name}`)
      }
      loadCompanies()
    } catch {
      toast.error('Failed to update company status')
    }
  }

  return (
    <div>
      {/* Page header */}
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', padding: '1.25rem 1.5rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>Company Profile</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.82rem', margin: '3px 0 0' }}>
            Manage company information
          </p>
        </div>
        <button
          onClick={() => { setEditingCompany(null); setFormOpen(true) }}
          style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '7px 14px', backgroundColor: 'var(--text)', color: 'var(--surface)', border: 'none', borderRadius: '8px', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New company
        </button>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem', marginBottom: '1.25rem' }}>
        {[
          { label: 'Total companies', value: total, color: 'var(--primary)', icon: '🏢' },
          { label: 'Active companies', value: companies.filter((c) => c.is_active).length, color: 'var(--success)', icon: '✅' },
        ].map((s) => (
          <div key={s.label} style={{ backgroundColor: 'var(--surface)', borderRadius: '0.875rem', border: '1px solid var(--border)', padding: '1rem 1.125rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <p style={{ fontSize: '1.4rem', fontWeight: 700, color: s.color, margin: 0 }}>{s.value}</p>
              <span style={{ fontSize: '1.25rem' }}>{s.icon}</span>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: '2px 0 0', fontWeight: 500 }}>{s.label}</p>
          </div>
        ))}
      </div>

      {/* Main card */}
      <div style={{ backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', overflow: 'hidden' }}>
        {/* Toolbar */}
        <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid var(--border)', display: 'flex', gap: '0.625rem', flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: '200px', position: 'relative' }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" style={{ position: 'absolute', left: '10px', top: '50%', transform: 'translateY(-50%)' }}>
              <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
            </svg>
            <input className="input" placeholder="Search by name or ID…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ paddingLeft: '32px', fontSize: '0.82rem' }} />
          </div>
          <select className="input" value={filterActive} onChange={(e) => setFilterActive(e.target.value)} style={{ width: '140px', fontSize: '0.82rem' }}>
            <option value="">All status</option>
            <option value="true">Active only</option>
            <option value="false">Inactive only</option>
          </select>
        </div>

        {/* Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Company ID', 'Full Name', 'Short Name', 'Contact Person', 'Email', 'Status', 'Actions'].map((h) => (
                  <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 600, color: 'var(--text-secondary)', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading…</td></tr>
              ) : companies.length === 0 ? (
                <tr><td colSpan={7} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>No companies found</td></tr>
              ) : companies.map((company) => (
                <tr key={company.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--text)' }}>{company.company_id}</td>
                  <td style={{ padding: '0.75rem 1rem', color: 'var(--text)' }}>{company.full_name}</td>
                  <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>{company.short_name}</td>
                  <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>{company.contact_person || '—'}</td>
                  <td style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)' }}>{company.email_address || '—'}</td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <span style={{ fontSize: '0.72rem', fontWeight: 600, padding: '3px 8px', borderRadius: '999px', backgroundColor: company.is_active ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)', color: company.is_active ? '#16a34a' : '#dc2626' }}>
                      {company.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem 1rem' }}>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        onClick={() => { setEditingCompany(company); setFormOpen(true) }}
                        style={{ padding: '4px 8px', fontSize: '0.75rem', borderRadius: '6px', border: '1px solid var(--border)', backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleToggleActive(company)}
                        style={{ padding: '4px 8px', fontSize: '0.75rem', borderRadius: '6px', border: '1px solid var(--border)', backgroundColor: company.is_active ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)', color: company.is_active ? '#dc2626' : '#16a34a', cursor: 'pointer', fontFamily: 'inherit' }}
                      >
                        {company.is_active ? 'Deactivate' : 'Activate'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', padding: '1rem', borderTop: '1px solid var(--border)' }}>
            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} style={pageBtn}>←</button>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Page {page} of {totalPages}</span>
            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages} style={pageBtn}>→</button>
          </div>
        )}
      </div>

      {/* Form modal */}
      <CompanyFormModal
        isOpen={formOpen}
        editing={editingCompany}
        onClose={() => { setFormOpen(false); setEditingCompany(null) }}
        onSuccess={loadCompanies}
      />
    </div>
  )
}

const pageBtn: React.CSSProperties = {
  padding: '5px 12px', borderRadius: '7px', border: '1px solid var(--border-soft)',
  backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.82rem',
  cursor: 'pointer', fontFamily: 'inherit',
}
