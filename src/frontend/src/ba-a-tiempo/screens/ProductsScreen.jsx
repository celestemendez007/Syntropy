import React, { useState } from 'react';

export default function ProductsScreen({ onOpenBAOption, onOpenHelp, onPayNow }) {
  const [activeCategory, setActiveCategory] = useState('creditos');

  return (
    <div className="ba-screen-inner">
      {/* Título y Subtítulo de Página */}
      <div className="ba-products-header-section">
        <h2>Mis productos</h2>
        <p>Aquí puedes ver y gestionar todos tus productos.</p>
      </div>

      {/* Tabs de Categorías */}
      <div className="ba-product-category-tabs">
        <button
          type="button"
          className={`ba-cat-tab-btn ${activeCategory === 'cuentas' ? 'active' : ''}`}
          onClick={() => setActiveCategory('cuentas')}
        >
          Cuentas
        </button>
        <button
          type="button"
          className={`ba-cat-tab-btn ${activeCategory === 'tarjetas' ? 'active' : ''}`}
          onClick={() => setActiveCategory('tarjetas')}
        >
          Tarjetas
        </button>
        <button
          type="button"
          className={`ba-cat-tab-btn ${activeCategory === 'creditos' ? 'active' : ''}`}
          onClick={() => setActiveCategory('creditos')}
        >
          Créditos
        </button>
      </div>

      {/* Tarjeta Principal de Crédito para Vehículo (Imagen 2) */}
      <div className="ba-credit-product-card">
        <div className="ba-credit-header-row">
          <div className="ba-credit-title-group">
            <div className="ba-car-icon-box">
              {/* SVG Auto Bancoagrícola */}
              <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#1e293b" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.5 2.8C2.1 11 2 11.5 2 12v4c0 .6.4 1 1 1h2" />
                <circle cx="7" cy="17" r="2" />
                <path d="M9 17h6" />
                <circle cx="17" cy="17" r="2" />
              </svg>
            </div>
            <div>
              <div className="ba-credit-name-text">Crédito para Vehículo</div>
              <div className="ba-credit-sub-text">CRÉDITO</div>
              <div className="ba-credit-num-text">N° 3012345678</div>
            </div>
          </div>

          <div className="ba-badge-warning-pill">
            <span className="ba-badge-warning-circle">!</span>
            <span>Próximo a vencer</span>
          </div>
        </div>

        {/* 3 Columnas Métricas */}
        <div className="ba-credit-data-3col">
          <div className="ba-3col-item">
            <span className="ba-3col-label">Saldo pendiente</span>
            <span className="ba-3col-value">
              $12,560<sup className="ba-sup-cents"> 00</sup>
            </span>
          </div>
          <div className="ba-3col-item ba-border-col">
            <span className="ba-3col-label">Cuota mensual</span>
            <span className="ba-3col-value">
              $350<sup className="ba-sup-cents"> 00</sup>
            </span>
          </div>
          <div className="ba-3col-item ba-border-col">
            <span className="ba-3col-label">Próxima fecha de pago</span>
            <span className="ba-3col-value ba-date-val">15 sep. 2025</span>
          </div>
        </div>
      </div>

      {/* Tarjeta BA A Tiempo Integrada en Producto */}
      <div className="ba-tiempo-product-subcard">
        <div className="ba-tiempo-header-content">
          <div className="ba-tiempo-calendar-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#1e293b" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            <div className="ba-tiempo-exclamation-dot">!</div>
          </div>

          <div className="ba-tiempo-text-block">
            <h3>BA A Tiempo</h3>
            <h4>Tu próximo pago</h4>
            <p>Pagar a tiempo te ayuda a mantener un buen historial crediticio y seguir cumpliendo tus metas.</p>
          </div>
        </div>

        {/* Recuadro Blanco Interno (Monto a pagar / Fecha de vencimiento) */}
        <div className="ba-inner-white-2col">
          <div className="ba-white-col">
            <span className="ba-3col-label">Monto a pagar</span>
            <span className="ba-3col-value">
              $350<sup className="ba-sup-cents"> 00</sup>
            </span>
          </div>
          <div className="ba-white-col">
            <span className="ba-3col-label">Fecha de vencimiento</span>
            <span className="ba-3col-value ba-date-val">15 sep. 2025</span>
          </div>
        </div>

        {/* Botones de Acción */}
        <div className="ba-tiempo-button-group">
          <button
            type="button"
            className="ba-btn-yellow-pill"
            onClick={onOpenHelp || onOpenBAOption}
          >
            Necesito ayuda con este pago
          </button>
          <button
            type="button"
            className="ba-btn-white-pill"
            onClick={onPayNow}
          >
            Pagar ahora
          </button>
        </div>
      </div>

      {/* Enlace Ver Historial */}
      <div className="ba-history-link-row" onClick={() => alert('Historial de pagos')}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#1e293b" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <circle cx="10" cy="14" r="3"></circle>
          <polyline points="10 13 10 14 11 15"></polyline>
        </svg>
        <span>Ver historial</span>
        <span style={{ fontSize: '0.9rem', color: '#64748b', marginLeft: 'auto' }}>&gt;</span>
      </div>
    </div>
  );
}
