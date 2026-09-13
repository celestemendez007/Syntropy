import React from 'react';

export default function HomeScreen({ onOpenBAOption, onOpenHelp, onPayNow, onGoToProducts }) {
  return (
    <div className="ba-screen-inner">
      {/* Mis Cuentas Header & Cards Row */}
      <section>
        <div className="ba-section-header-row">
          <div className="ba-section-title-bold">
            <span>Mis cuentas</span>
            {/* Ojo para ocultar saldos */}
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#111827" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={{ cursor: 'pointer' }}>
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
          <span className="ba-link-ver-todas" onClick={onGoToProducts}>Ver todas &gt;</span>
        </div>

        <div className="ba-accounts-scroll-row">
          {/* Cuenta 1 */}
          <div className="ba-account-card-small">
            <div className="ba-account-card-top">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#111827" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 11V9a7 7 0 0 0-7-7 7 7 0 0 0-7 7v2a4 4 0 0 0-3 3.87V17a4 4 0 0 0 4 4h12a4 4 0 0 0 4-4v-2.13A4 4 0 0 0 19 11z" />
                <circle cx="9" cy="9" r="1" />
                <path d="M16 16v4" />
                <path d="M8 16v4" />
              </svg>
              <span className="ba-account-card-name">Cuenta de ahorro</span>
            </div>
            <div className="ba-account-card-sub">CUENTA DIGITAL</div>
            <div className="ba-account-card-balance">
              <span>$47</span>
              <sup className="ba-cents-sup">24</sup>
            </div>
            <div className="ba-account-card-label">Saldo disponible</div>
          </div>

          {/* Cuenta 2 */}
          <div className="ba-account-card-small">
            <div className="ba-account-card-top">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#111827" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 11V9a7 7 0 0 0-7-7 7 7 0 0 0-7 7v2a4 4 0 0 0-3 3.87V17a4 4 0 0 0 4 4h12a4 4 0 0 0 4-4v-2.13A4 4 0 0 0 19 11z" />
                <circle cx="9" cy="9" r="1" />
                <path d="M16 16v4" />
                <path d="M8 16v4" />
              </svg>
              <span className="ba-account-card-name">Cuenta de ahorro</span>
            </div>
            <div className="ba-account-card-sub">CUENTA DIGITAL</div>
            <div className="ba-account-card-balance">
              <span>$0</span>
              <sup className="ba-cents-sup">00</sup>
            </div>
            <div className="ba-account-card-label">Saldo disponible</div>
          </div>
        </div>
      </section>

      {/* Tarjeta Preventiva BA A Tiempo (Exacta a Imagen 1 de Referencia) */}
      <section className="ba-tiempo-banner-card">
        <div className="ba-tiempo-pill-badge">
          Previene, te da tranquilidad
        </div>

        <div className="ba-tiempo-header-content">
          <div className="ba-tiempo-calendar-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#111827" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            <div className="ba-tiempo-exclamation-dot">!</div>
          </div>

          <div className="ba-tiempo-text-block">
            <h3>BA A Tiempo</h3>
            <h4>Tu próximo pago vence pronto</h4>
            <p>Revisarlo con anticipación puede ayudarte a mantenerlo al día.</p>
          </div>
        </div>

        <div className="ba-tiempo-button-group">
          <button type="button" className="ba-btn-yellow-pill" onClick={onPayNow}>
            Pagar ahora
          </button>
          <button type="button" className="ba-btn-white-pill" onClick={onGoToProducts}>
            Revisar opciones
          </button>
          <button type="button" className="ba-btn-white-pill" onClick={onOpenHelp || onGoToProducts}>
            Necesito ayuda
          </button>
        </div>
      </section>

      {/* ¿Qué necesitas hacer hoy? (4 Botones Circulares Pasteles) */}
      <section className="ba-quick-actions-section">
        <div className="ba-section-title-bold" style={{ fontSize: '1rem' }}>
          ¿Qué necesitas hacer hoy?
        </div>

        <div className="ba-quick-actions-grid">
          {/* Transferir */}
          <button type="button" className="ba-pastel-action-item">
            <div className="ba-pastel-circle ba-pastel-pink">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v10m0 0l-4-4m4 4l4-4" transform="rotate(180 12 7)" />
                <rect x="4" y="10" width="16" height="10" rx="2" />
              </svg>
            </div>
            <span className="ba-pastel-label">Transferir dinero</span>
          </button>

          {/* Recargar */}
          <button type="button" className="ba-pastel-action-item">
            <div className="ba-pastel-circle ba-pastel-mint">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
                <line x1="12" y1="18" x2="12.01" y2="18" />
              </svg>
            </div>
            <span className="ba-pastel-label">Recargar celular</span>
          </button>

          {/* Pagar Tarjeta */}
          <button type="button" className="ba-pastel-action-item">
            <div className="ba-pastel-circle ba-pastel-yellow">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <rect x="2" y="5" width="20" height="14" rx="2" />
                <line x1="2" y1="10" x2="22" y2="10" />
              </svg>
            </div>
            <span className="ba-pastel-label">Pagar tarjeta</span>
          </button>

          {/* Pagar Servicios */}
          <button type="button" className="ba-pastel-action-item">
            <div className="ba-pastel-circle ba-pastel-blue">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10 9 9 9 8 9" />
              </svg>
            </div>
            <span className="ba-pastel-label">Pagar servicios</span>
          </button>
        </div>
      </section>

      {/* Promociones y Descuentos */}
      <section className="ba-promos-banner-row">
        <div className="ba-promos-left">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="9" cy="21" r="1" />
            <circle cx="20" cy="21" r="1" />
            <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6" />
          </svg>
          <span>Promociones y descuentos</span>
        </div>
        <span style={{ fontSize: '1.1rem', color: '#64748b' }}>&gt;</span>
      </section>
    </div>
  );
}
