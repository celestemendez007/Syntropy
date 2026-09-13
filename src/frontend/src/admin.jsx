import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import LiveAdminDashboard from './LiveAdminDashboard'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <div className="ba-bg" style={{ minHeight: '100vh', backgroundColor: 'var(--ba-bg)' }}>
      <LiveAdminDashboard />
    </div>
  </StrictMode>,
)
