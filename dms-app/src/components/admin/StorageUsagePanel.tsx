import { useState, useEffect, useCallback } from 'react'
import { toast } from 'react-hot-toast'
import { storageApi } from '@/api/storage.api'
import type { StorageUsageResponse } from '@/api/storage.api'

export default function StorageUsagePanel() {
  const [data, setData] = useState<StorageUsageResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [capacityInput, setCapacityInput] = useState('')
  const [savingCapacity, setSavingCapacity] = useState(false)

  const loadUsage = useCallback(async () => {
    setLoading(true)
    try {
      const result = await storageApi.getUsage()
      setData(result)
      setCapacityInput(String(Math.round(result.total_capacity / (1024 ** 3))))
    } catch {
      toast.error('Failed to load storage usage')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadUsage() }, [loadUsage])

  const handleSaveCapacity = async () => {
    const gb = parseFloat(capacityInput)
    if (isNaN(gb) || gb <= 0) {
      toast.error('Please enter a valid capacity in GB')
      return
    }
    setSavingCapacity(true)
    try {
      await storageApi.setCapacity(gb)
      toast.success('Capacity updated')
      loadUsage()
    } catch {
      toast.error('Failed to update capacity')
    } finally {
      setSavingCapacity(false)
    }
  }

  if (loading && !data) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
        Loading storage usage...
      </div>
    )
  }

  if (!data) {
    return (
      <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
        No data available
      </div>
    )
  }

  const usedPct = Math.min(data.usage_percentage, 100)

  return (
    <div>
      {/* Overall Usage */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
        padding: '1.5rem', marginBottom: '1rem',
      }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 1rem' }}>
          Overall Storage Usage
        </h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <StatCard label="Used (DB)" value={data.db_used_human} color="var(--primary)" />
          <StatCard label="Used (Disk)" value={data.disk_used_human} color="#6366f1" />
          <StatCard label="Available" value={data.available_storage_human} color="var(--success)" />
          <StatCard label="Total Capacity" value={data.total_capacity_human} color="var(--text-secondary)" />
        </div>
        {/* Progress bar */}
        <div style={{ marginBottom: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>
            <span>{data.usage_percentage}% used</span>
            <span>{data.db_used_human} / {data.total_capacity_human}</span>
          </div>
          <div style={{ width: '100%', height: '10px', backgroundColor: 'var(--border)', borderRadius: '999px', overflow: 'hidden' }}>
            <div style={{
              width: `${usedPct}%`, height: '100%',
              backgroundColor: usedPct > 80 ? '#ef4444' : usedPct > 60 ? '#f59e0b' : '#22c55e',
              borderRadius: '999px', transition: 'width 0.3s ease',
            }} />
          </div>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', margin: 0 }}>
          DB vs Disk difference: {Math.abs(data.db_used - data.disk_used) > 1024
            ? `${Math.abs(data.db_used - data.disk_used) > 1024 ** 2 ? ((data.disk_used - data.db_used) / 1024 ** 2).toFixed(1) + ' MB' : ((data.disk_used - data.db_used) / 1024).toFixed(1) + ' KB'} ${data.disk_used > data.db_used ? 'more on disk' : 'more in DB'}`
            : 'in sync'}
        </p>
      </div>

      {/* Capacity Settings */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
        padding: '1.5rem', marginBottom: '1rem',
      }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: '0 0 1rem' }}>
          Capacity Settings
        </h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            Total Capacity:
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              type="number"
              value={capacityInput}
              onChange={(e) => setCapacityInput(e.target.value)}
              min="1"
              max="10000"
              style={{
                width: '100px', padding: '6px 10px', borderRadius: '8px',
                border: '1px solid var(--border)', backgroundColor: 'var(--bg)',
                color: 'var(--text)', fontSize: '0.82rem', fontFamily: 'inherit',
              }}
            />
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>GB</span>
            <button
              onClick={handleSaveCapacity}
              disabled={savingCapacity}
              style={{
                padding: '6px 14px', borderRadius: '8px', border: 'none',
                backgroundColor: 'var(--text)', color: 'var(--surface)',
                fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
                fontFamily: 'inherit', opacity: savingCapacity ? 0.6 : 1,
              }}
            >
              {savingCapacity ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>

      {/* Usage by Category */}
      <div style={{
        backgroundColor: 'var(--surface)', borderRadius: '1rem', border: '1px solid var(--border)',
        overflow: 'hidden',
      }}>
        <div style={{ padding: '1.25rem 1.5rem', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: 'var(--text)', margin: 0 }}>
            Usage by Category
          </h3>
        </div>
        {data.categories.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            No categories with storage usage
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', backgroundColor: 'var(--bg)' }}>
                <th style={thStyle}>Category</th>
                <th style={thStyle}>DB Size</th>
                <th style={thStyle}>Disk Size</th>
                <th style={thStyle}>Files</th>
                <th style={{ ...thStyle, minWidth: '120px' }}>% of Total</th>
              </tr>
            </thead>
            <tbody>
              {data.categories.map((cat) => (
                <tr key={cat.category_id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={tdStyle}>{cat.category_name}</td>
                  <td style={tdStyle}>{cat.db_size_human}</td>
                  <td style={tdStyle}>{cat.disk_size_human}</td>
                  <td style={tdStyle}>{cat.document_count.toLocaleString()}</td>
                  <td style={tdStyle}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ flex: 1, height: '6px', backgroundColor: 'var(--border)', borderRadius: '999px', overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.min(cat.usage_percentage, 100)}%`, height: '100%',
                          backgroundColor: '#6366f1', borderRadius: '999px',
                        }} />
                      </div>
                      <span style={{ minWidth: '35px', textAlign: 'right' }}>{cat.usage_percentage}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Refresh */}
      <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={loadUsage}
          disabled={loading}
          style={{
            padding: '6px 14px', borderRadius: '8px', border: '1px solid var(--border)',
            backgroundColor: 'var(--surface)', color: 'var(--text)',
            fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer',
            fontFamily: 'inherit', opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>
    </div>
  )
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <p style={{ fontSize: '1.2rem', fontWeight: 700, color, margin: 0 }}>{value}</p>
      <p style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', margin: '2px 0 0', fontWeight: 500 }}>{label}</p>
    </div>
  )
}

const thStyle: React.CSSProperties = {
  padding: '0.75rem 1rem',
  textAlign: 'left',
  fontWeight: 600,
  color: 'var(--text-secondary)',
}

const tdStyle: React.CSSProperties = {
  padding: '0.75rem 1rem',
  color: 'var(--text)',
}
