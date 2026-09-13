import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import LiveAdminDashboard from './LiveAdminDashboard'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <div className="app-container" style={{ padding: '20px' }}>
      <LiveAdminDashboard />
    </div>
  </StrictMode>,
)
