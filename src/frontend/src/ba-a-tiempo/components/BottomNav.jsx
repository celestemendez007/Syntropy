import React from 'react';

export default function BottomNav({ activeTab, onSelectTab }) {
  return (
    <nav className="ba-app-bottom-navbar">
      {/* Inicio */}
      <button
        type="button"
        className={`ba-bottom-tab-item ${activeTab === 'inicio' ? 'active' : ''}`}
        onClick={() => onSelectTab('inicio')}
      >
        <svg className="ba-bottom-tab-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
        <span>Inicio</span>
      </button>

      {/* Mis Productos */}
      <button
        type="button"
        className={`ba-bottom-tab-item ${activeTab === 'productos' ? 'active' : ''}`}
        onClick={() => onSelectTab('productos')}
      >
        <svg className="ba-bottom-tab-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="5" width="20" height="14" rx="2" />
          <line x1="2" y1="10" x2="22" y2="10" />
        </svg>
        <span>Mis Productos</span>
      </button>

      {/* Gestiones */}
      <button
        type="button"
        className={`ba-bottom-tab-item ${activeTab === 'gestiones' ? 'active' : ''}`}
        onClick={() => onSelectTab('gestiones')}
      >
        <svg className="ba-bottom-tab-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
        </svg>
        <span>Gestiones</span>
      </button>

      {/* Para Ti */}
      <button
        type="button"
        className={`ba-bottom-tab-item ${activeTab === 'parati' ? 'active' : ''}`}
        onClick={() => onSelectTab('parati')}
      >
        <svg className="ba-bottom-tab-svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 12 20 22 4 22 4 12" />
          <rect x="2" y="7" width="20" height="5" />
          <line x1="12" y1="22" x2="12" y2="7" />
          <path d="M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z" />
          <path d="M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z" />
        </svg>
        <span>Para Ti</span>
      </button>
    </nav>
  );
}
