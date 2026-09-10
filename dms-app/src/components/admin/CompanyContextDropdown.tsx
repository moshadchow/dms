import { useCallback, useEffect, useState } from 'react'
import { toast } from 'react-hot-toast'
import { companiesApi } from '@/api/companies.api'
import { getErrorMessage } from '@/api/client'
import type { Company } from '@/types/company.types'
import Spinner from '@/components/ui/Spinner'

interface Props {
  value: number | null
  onChange: (companyId: number | null) => void
}

export default function CompanyContextDropdown({ value, onChange }: Props) {
  const [companies, setCompanies] = useState<Company[]>([])
  const [loading, setLoading] = useState(true)

  const loadCompanies = useCallback(async () => {
    setLoading(true)
    try {
      const data = await companiesApi.list({ is_active: true })
      setCompanies(data.items)
    } catch (error) {
      toast.error(getErrorMessage(error))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadCompanies()
  }, [loadCompanies])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
        <Spinner size="sm" />
        Loading companies...
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
      <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
        Company
      </label>
      <select
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}
        style={{
          padding: '6px 10px',
          borderRadius: '8px',
          border: '1px solid var(--border)',
          backgroundColor: 'var(--bg)',
          color: 'var(--text)',
          fontSize: '0.82rem',
          fontFamily: 'inherit',
          minWidth: '180px',
        }}
      >
        <option value="">Select Company</option>
        {companies.map((company) => (
          <option key={company.id} value={company.id}>
            {company.short_name} ({company.company_id})
          </option>
        ))}
      </select>
    </div>
  )
}
