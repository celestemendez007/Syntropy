import React, { useState } from 'react';
import AppShell from './components/AppShell';
import HomeScreen from './screens/HomeScreen';
import ProductsScreen from './screens/ProductsScreen';
import OptionsScreen from './screens/OptionsScreen';
import GestionesScreen from './screens/GestionesScreen';
import ParaTiScreen from './screens/ParaTiScreen';
import './styles/bancoagricola.css';

export default function BaATiempoApp() {
  const [currentTab, setCurrentTab] = useState('inicio');
  const [viewMode, setViewMode] = useState('tabs'); // 'tabs' | 'options'

  // Selected product data for BA A Tiempo flow (Image 3)
  const [selectedProduct, setSelectedProduct] = useState({
    name: 'Crédito Personal',
    type: '(cargo a cuenta)',
    amount: '125',
    cents: '00',
    dueDate: '20 sep 2026',
  });

  const handleOpenHelp = () => {
    setViewMode('options');
  };

  const handleOpenBAOption = () => {
    setViewMode('options');
  };

  const handleBackToTabs = () => {
    setViewMode('tabs');
  };

  const handleSelectOption = (option) => {
    alert(`Opción seleccionada: "${option.title}"\n\nEn la siguiente fase conectaremos el flujo de resolución conversacional.`);
  };

  const handleSubmitText = (text) => {
    alert(`Mensaje personalizado enviado:\n"${text}"`);
  };

  const handlePayNow = () => {
    alert('Acción: Redirigiendo a pasarela de pago de Bancoagrícola...');
  };

  const handleTabChange = (tabId) => {
    setCurrentTab(tabId);
    setViewMode('tabs');
  };

  return (
    <AppShell
      activeTab={currentTab}
      onSelectTab={handleTabChange}
      showHeader={viewMode === 'tabs'}
    >
      {viewMode === 'options' ? (
        <OptionsScreen
          product={selectedProduct}
          onBack={handleBackToTabs}
          onSelectOption={handleSelectOption}
          onSubmitText={handleSubmitText}
        />
      ) : (
        <>
          {currentTab === 'inicio' && (
            <HomeScreen
              onOpenBAOption={handleOpenBAOption}
              onOpenHelp={handleOpenHelp}
              onPayNow={handlePayNow}
              onGoToProducts={() => handleTabChange('productos')}
            />
          )}

          {currentTab === 'productos' && (
            <ProductsScreen
              onOpenBAOption={handleOpenBAOption}
              onOpenHelp={handleOpenHelp}
              onPayNow={handlePayNow}
            />
          )}

          {currentTab === 'gestiones' && <GestionesScreen />}

          {currentTab === 'parati' && <ParaTiScreen />}
        </>
      )}
    </AppShell>
  );
}
