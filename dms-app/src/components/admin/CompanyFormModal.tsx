import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { companiesApi } from '@/api/companies.api'
import type { Company, CompanyCreateRequest, CompanyUpdateRequest } from '@/types/company.types'

interface Props {
  isOpen: boolean
  editing: Company | null
  onClose: () => void
  onSuccess: () => void
}

export default function CompanyFormModal({ isOpen, editing, onClose, onSuccess }: Props) {
  const [form, setForm] = useState({
    company_id: '',
    full_name: '',
    short_name: '',
    address: '',
    contact_person: '',
    contact_no: '',
    email_address: '',
    is_active: true,
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (editing) {
      setForm({
        company_id: editing.company_id,
        full_name: editing.full_name,
        short_name: editing.short_name,
        address: editing.address || '',
        contact_person: editing.contact_person || '',
        contact_no: editing.contact_no || '',
        email_address: editing.email_address || '',
        is_active: editing.is_active,
      })
    } else {
      setForm({
        company_id: '',
        full_name: '',
        short_name: '',
        address: '',
        contact_person: '',
        contact_no: '',
        email_address: '',
        is_active: true,
      })
    }
  }, [editing, isOpen])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    try {
      if (editing) {
        const payload: CompanyUpdateRequest = {
          company_id: form.company_id || undefined,
          full_name: form.full_name || undefined,
          short_name: form.short_name || undefined,
          address: form.address || undefined,
          contact_person: form.contact_person || undefined,
          contact_no: form.contact_no || undefined,
          email_address: form.email_address || undefined,
          is_active: form.is_active,
        }
        await companiesApi.update(editing.id, payload)
        toast.success('Company updated')
      } else {
        const payload: CompanyCreateRequest = {
          company_id: form.company_id,
          full_name: form.full_name,
          short_name: form.short_name,
          address: form.address || undefined,
          contact_person: form.contact_person || undefined,
          contact_no: form.contact_no || undefined,
          email_address: form.email_address || undefined,
          is_active: form.is_active,
        }
        await companiesApi.create(payload)
        toast.success('Company created')
      }
      onSuccess()
      onClose()
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Operation failed'
      toast.error(msg)
    } finally {
      setSaving(false)
    }
  }

  if (!isOpen) return null

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)' }} onClick={onClose} />
      <div style={{ position: 'relative', backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)', width: '90%', maxWidth: '520px', maxHeight: '90vh', overflow: 'auto', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)' }}>
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            {editing ? 'Edit Company' : 'New Company'}
          </h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: '4px' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ padding: '1.25rem 1.5rem' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Company ID *</label>
              <input
                className="input"
                value={form.company_id}
                onChange={(e) => setForm({ ...form, company_id: e.target.value })}
                required
                disabled={!!editing}
                style={{ width: '100%', fontSize: '0.82rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Full Name *</label>
              <input
                className="input"
                value={form.full_name}
                onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                required
                style={{ width: '100%', fontSize: '0.82rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Short Name *</label>
              <input
                className="input"
                value={form.short_name}
                onChange={(e) => setForm({ ...form, short_name: e.target.value })}
                required
                style={{ width: '100%', fontSize: '0.82rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Address</label>
              <input
                className="input"
                value={form.address}
                onChange={(e) => setForm({ ...form, address: e.target.value })}
                style={{ width: '100%', fontSize: '0.82rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Contact Person</label>
              <input
                className="input"
                value={form.contact_person}
                onChange={(e) => setForm({ ...form, contact_person: e.target.value })}
                style={{ width: '100%', fontSize: '0.82rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Contact No</label>
              <input
                className="input"
                value={form.contact_no}
                onChange={(e) => setForm({ ...form, contact_no: e.target.value })}
                style={{ width: '100%', fontSize: '0.82rem' }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>Email Address</label>
              <input
                className="input"
                type="email"
                value={form.email_address}
                onChange={(e) => setForm({ ...form, email_address: e.target.value })}
                style={{ width: '100%', fontSize: '0.82rem' }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.625rem', marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
            <button
              type="button"
              onClick={onClose}
              style={{ padding: '7px 14px', borderRadius: '8px', border: '1px solid var(--border)', backgroundColor: 'var(--surface)', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 500, cursor: 'pointer', fontFamily: 'inherit' }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              style={{ padding: '7px 14px', borderRadius: '8px', border: 'none', backgroundColor: 'var(--text)', color: 'var(--surface)', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit', opacity: saving ? 0.6 : 1 }}
            >
              {saving ? 'Saving…' : editing ? 'Update' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
