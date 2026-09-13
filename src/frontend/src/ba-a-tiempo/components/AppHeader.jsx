import React from 'react';

export default function AppHeader({ userName = "Keylen", showGreeting = true }) {
  return (
    <>
      <header className="ba-top-header">
        {/* Bancoagrícola Official 3-Bar Logo */}
        <div className="ba-logo-svg-group" title="Bancoagrícola">
          <svg width="28" height="24" viewBox="0 0 28 24">
            <rect x="0" y="2" width="20" height="4.2" rx="2.1" fill="#1e293b" transform="skewX(-20)" />
            <rect x="3" y="9.5" width="20" height="4.2" rx="2.1" fill="#1e293b" transform="skewX(-20)" />
            <rect x="6" y="17" width="20" height="4.2" rx="2.1" fill="#1e293b" transform="skewX(-20)" />
          </svg>
        </div>

        {/* Top Actions Icons */}
        <div className="ba-top-nav-actions">
          <button className="ba-top-action-btn" title="Mensajería">
            <span className="ba-top-action-icon">🔔</span>
            <span className="ba-top-action-label">Mensajería</span>
            <span className="ba-badge-count">136</span>
          </button>

          <button className="ba-top-action-btn" title="Perfil">
            <span className="ba-top-action-icon">👤</span>
            <span className="ba-top-action-label">Perfil</span>
          </button>

          <button className="ba-top-action-btn" title="Mi QR">
            <span className="ba-top-action-icon">📷</span>
            <span className="ba-top-action-label">Mi QR</span>
          </button>
        </div>
      </header>

      {/* User Greeting (Inicio) */}
      {showGreeting && (
        <div className="ba-user-greeting-row">
          <div className="ba-user-greeting-title">
            <div className="ba-user-avatar-purple">
              👤
            </div>
            <span>Hola {userName} &gt;</span>
          </div>
          <div className="ba-user-last-visit">
            Última visita: 12/09/2026 | 07:47
          </div>
        </div>
      )}
    </>
  );
}
