import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import App from './App'
import './index.css'
import { applyTheme } from './store/themeStore'

// Apply saved theme immediately before first render to prevent flash
const saved = localStorage.getItem('dms-theme')
try {
  const parsed = saved ? JSON.parse(saved) : null
  if (parsed?.state?.theme) applyTheme(parsed.state.theme)
} catch { /* ignore */ }

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <App />
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3500,
          style: {
            fontFamily: 'DM Sans, sans-serif',
            fontSize: '14px',
            borderRadius: '12px',
            backgroundColor: 'var(--surface)',
            color: 'var(--text)',
            border: '1px solid var(--border-soft)',
            boxShadow: 'var(--shadow-md)',
          },
        }}
      />
    </BrowserRouter>
  </React.StrictMode>
)
