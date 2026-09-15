import { useState, useEffect } from 'react'
import { toast } from 'react-hot-toast'
import { companiesApi } from '@/api/companies.api'
import type { Company, AzureConfig, AzureConfigUpdateRequest } from '@/types/company.types'

interface AzureConfigModalProps {
  isOpen: boolean
  company: Company | null
  onClose: () => void
  onSuccess: () => void
}

export default function AzureConfigModal({ isOpen, company, onClose, onSuccess }: AzureConfigModalProps) {
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [config, setConfig] = useState<AzureConfig | null>(null)

  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [tenantId, setTenantId] = useState('')
  const [enabled, setEnabled] = useState(false)
  const [defaultRole, setDefaultRole] = useState('auditor')

  useEffect(() => {
    if (isOpen && company) {
      loadConfig()
    }
  }, [isOpen, company])

  const loadConfig = async () => {
    if (!company) return
    setFetching(true)
    try {
      const data = await companiesApi.getAzureConfig(company.id)
      setConfig(data)
      setClientId(data.azure_client_id || '')
      setTenantId(data.azure_tenant_id || '')
      setEnabled(data.azure_enabled)
      setDefaultRole(data.azure_default_role_name || 'auditor')
      setClientSecret('') // Never pre-fill secret
    } catch {
      toast.error('Failed to load Azure AD config')
    } finally {
      setFetching(false)
    }
  }

  const handleSave = async () => {
    if (!company) return
    if (!clientId.trim() || !tenantId.trim()) {
      toast.error('Client ID and Tenant ID are required')
      return
    }

    setLoading(true)
    try {
      const payload: AzureConfigUpdateRequest = {
        azure_client_id: clientId.trim(),
        azure_tenant_id: tenantId.trim(),
        azure_enabled: enabled,
        azure_default_role_name: defaultRole || undefined,
      }
      // Only include secret if user typed a new one
      if (clientSecret.trim()) {
        payload.azure_client_secret = clientSecret.trim()
      }
      await companiesApi.updateAzureConfig(company.id, payload)
      toast.success('Azure AD config updated')
      onSuccess()
      onClose()
    } catch {
      toast.error('Failed to update Azure AD config')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (!company) return
    if (!confirm('Remove Azure AD configuration for this company?')) return

    setLoading(true)
    try {
      await companiesApi.deleteAzureConfig(company.id)
      toast.success('Azure AD config removed')
      onSuccess()
      onClose()
    } catch {
      toast.error('Failed to remove Azure AD config')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen || !company) return null

  return (
    <div style={{
      position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.4)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50,
      padding: '1rem',
    }} onClick={onClose}>
      <div
        style={{
          backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
          boxShadow: 'var(--shadow-lg)', width: '100%', maxWidth: '480px', maxHeight: '90vh',
          overflow: 'auto', padding: '1.5rem',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
          <div>
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
              Azure AD Configuration
            </h2>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', margin: '2px 0 0' }}>
              {company.short_name}
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)', padding: '4px' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>

        {fetching ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>Loading…</div>
        ) : (
          <>
            {/* Enable toggle */}
            <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ position: 'relative', display: 'inline-block', width: '40px', height: '22px' }}>
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                  style={{ opacity: 0, width: 0, height: 0 }}
                />
                <span style={{
                  position: 'absolute', cursor: 'pointer', inset: 0,
                  backgroundColor: enabled ? 'var(--primary)' : 'var(--border)',
                  borderRadius: '22px', transition: '0.2s',
                }}>
                  <span style={{
                    position: 'absolute', content: '""', height: '16px', width: '16px',
                    left: enabled ? '20px' : '3px', bottom: '3px',
                    backgroundColor: 'white', borderRadius: '50%', transition: '0.2s',
                  }} />
                </span>
              </label>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text)' }}>
                Enable Azure AD for this company
              </span>
            </div>

            {/* Client ID */}
            <div style={{ marginBottom: '0.875rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Client ID
              </label>
              <input
                className="input"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                disabled={loading}
                style={{ fontSize: '0.85rem' }}
              />
            </div>

            {/* Tenant ID */}
            <div style={{ marginBottom: '0.875rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Tenant ID
              </label>
              <input
                className="input"
                value={tenantId}
                onChange={(e) => setTenantId(e.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                disabled={loading}
                style={{ fontSize: '0.85rem' }}
              />
            </div>

            {/* Client Secret */}
            <div style={{ marginBottom: '0.875rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Client Secret {config?.configured && <span style={{ fontWeight: 400, color: 'var(--text-tertiary)' }}>(leave blank to keep current)</span>}
              </label>
              <input
                className="input"
                type="password"
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
                placeholder={config?.configured ? '••••••••' : 'Enter client secret'}
                disabled={loading}
                style={{ fontSize: '0.85rem' }}
              />
            </div>

            {/* Default Role */}
            <div style={{ marginBottom: '1.25rem' }}>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Default Role for JIT Users
              </label>
              <select
                className="input"
                value={defaultRole}
                onChange={(e) => setDefaultRole(e.target.value)}
                disabled={loading}
                style={{ fontSize: '0.85rem' }}
              >
                <option value="auditor">Auditor</option>
                <option value="maker">Maker</option>
                <option value="checker">Checker</option>
              </select>
            </div>

            {/* Actions */}
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'space-between' }}>
              {config?.configured ? (
                <button
                  onClick={handleDelete}
                  disabled={loading}
                  style={{
                    padding: '0.5rem 1rem', fontSize: '0.82rem', fontWeight: 600,
                    backgroundColor: 'rgba(239,68,68,0.1)', color: '#dc2626',
                    border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px',
                    cursor: 'pointer', fontFamily: 'inherit',
                  }}
                >
                  Remove Config
                </button>
              ) : <div />}
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button onClick={onClose} className="btn btn-secondary" style={{ padding: '0.5rem 1rem', fontSize: '0.82rem' }}>
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={loading}
                  className="btn btn-primary"
                  style={{ padding: '0.5rem 1rem', fontSize: '0.82rem' }}
                >
                  {loading ? 'Saving…' : 'Save'}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
