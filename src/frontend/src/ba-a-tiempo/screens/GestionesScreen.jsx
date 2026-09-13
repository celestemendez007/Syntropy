import React from 'react';

export default function GestionesScreen() {
  return (
    <div className="screen-content" style={{ padding: '24px 20px', textAlign: 'center' }}>
      <div className="section-title-wrap">
        <h1 className="main-title">Gestiones</h1>
        <p className="main-subtitle">Realiza solicitudes, bloqueos y trámites digitales.</p>
      </div>

      <div style={{ marginTop: 40, padding: 30, background: '#fff', borderRadius: 16, border: '1px solid #e2e8f0' }}>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" style={{ margin: '0 auto 16px' }}>
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
        </svg>
        <p style={{ fontSize: 15, color: '#64748b', fontWeight: 500 }}>
          Centro de Gestiones Bancoagrícola disponible.
        </p>
      </div>
    </div>
  );
}
