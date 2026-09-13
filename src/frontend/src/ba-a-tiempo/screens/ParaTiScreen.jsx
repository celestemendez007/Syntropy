import React from 'react';

export default function ParaTiScreen() {
  return (
    <div className="screen-content" style={{ padding: '24px 20px', textAlign: 'center' }}>
      <div className="section-title-wrap">
        <h1 className="main-title">Para Ti</h1>
        <p className="main-subtitle">Beneficios, promociones exclusivas y recomendaciones personalizadas.</p>
      </div>

      <div style={{ marginTop: 40, padding: 30, background: '#fff', borderRadius: 16, border: '1px solid #e2e8f0' }}>
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5" style={{ margin: '0 auto 16px' }}>
          <polyline points="20 12 20 22 4 22 4 12"></polyline>
          <rect x="2" y="7" width="20" height="5"></rect>
          <line x1="12" y1="22" x2="12" y2="7"></line>
          <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z"></path>
          <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z"></path>
        </svg>
        <p style={{ fontSize: 15, color: '#64748b', fontWeight: 500 }}>
          Descubre tus beneficios y programas Puntos Bancoagrícola.
        </p>
      </div>
    </div>
  );
}
