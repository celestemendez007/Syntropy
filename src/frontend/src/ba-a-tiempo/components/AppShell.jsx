import React from 'react';
import AppHeader from './AppHeader';
import BottomNav from './BottomNav';

export default function AppShell({
  activeTab,
  onSelectTab,
  userName = "Keylen",
  showHeader = true,
  children,
}) {
  return (
    <div className="ba-app-wrapper">
      <div className="ba-phone-container">
        {/* Status Bar */}
        <div className="ba-phone-status-bar">
          <span>9:41</span>
          <div className="ba-status-notch-pill"></div>
          <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
            <span>5G</span>
            <span>100%</span>
          </div>
        </div>

        {/* Top Header */}
        {showHeader && <AppHeader userName={userName} showGreeting={activeTab === 'inicio'} />}

        {/* Scrollable Screen Content */}
        <div className={`ba-screen-content ${!showHeader ? 'no-header' : ''}`}>
          {children}
        </div>

        {/* Floating QR Action Button (Visible on Inicio) */}
        {activeTab === 'inicio' && (
          <button className="ba-floating-qr-btn" title="Escanear QR">
            📷
          </button>
        )}

        {/* Bottom Fixed Navigation Bar */}
        <BottomNav activeTab={activeTab} onSelectTab={onSelectTab} />
      </div>
    </div>
  );
}
