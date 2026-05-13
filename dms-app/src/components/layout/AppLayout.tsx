import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Topbar from './Topbar'
import Sidebar from './Sidebar'
import ChangePasswordModal from '@/components/auth/ChangePasswordModal'

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen]       = useState(true)
  const [changePassOpen, setChangePassOpen] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', backgroundColor: 'var(--bg)' }}>
      <Topbar
        onMenuToggle={() => setSidebarOpen((o) => !o)}
        sidebarOpen={sidebarOpen}
        onChangePassword={() => setChangePassOpen(true)}
      />
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <Sidebar isOpen={sidebarOpen} />
        <main style={{ flex: 1, overflowY: 'auto', backgroundColor: 'var(--bg)', padding: '1.5rem' }}>
          <Outlet />
        </main>
      </div>

      <ChangePasswordModal isOpen={changePassOpen} onClose={() => setChangePassOpen(false)} />
    </div>
  )
}
