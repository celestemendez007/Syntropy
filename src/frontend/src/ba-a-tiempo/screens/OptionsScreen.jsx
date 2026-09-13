import React, { useState } from 'react';

export default function OptionsScreen({
  product = {
    name: 'Crédito Personal',
    type: '(cargo a cuenta)',
    amount: '125',
    cents: '00',
    dueDate: '20 sep 2026',
  },
  onBack,
  onSelectOption,
  onSubmitText,
}) {
  const [customText, setCustomText] = useState('');

  const options = [
    {
      id: 'pay_now',
      title: 'Puedo pagarlo ahora',
      subtitle: 'Quiero hacer el pago en este momento.',
      bgClass: 'ba-option-mint',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="2" y="5" width="20" height="14" rx="2" />
          <line x1="2" y1="10" x2="22" y2="10" />
        </svg>
      ),
    },
    {
      id: 'pay_later',
      title: 'Me pagan después',
      subtitle: 'Recibiré el dinero pronto.',
      bgClass: 'ba-option-yellow',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
      ),
    },
    {
      id: 'partial_pay',
      title: 'No puedo cubrirlo completo',
      subtitle: 'Quiero explorar opciones de pago parcial.',
      bgClass: 'ba-option-pink',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 2a10 10 0 0 1 10 10h-10z" />
        </svg>
      ),
    },
    {
      id: 'app_help',
      title: 'Necesito ayuda con la app',
      subtitle: 'Tengo un problema para realizar el pago.',
      bgClass: 'ba-option-blue',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
          <line x1="12" y1="18" x2="12.01" y2="18" />
        </svg>
      ),
    },
    {
      id: 'human_advisor',
      title: 'Quiero hablar con una persona',
      subtitle: 'Prefiero que un asesor me contacte.',
      bgClass: 'ba-option-purple',
      icon: (
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      ),
    },
  ];

  const handleTextKeyDown = (e) => {
    if (e.key === 'Enter' && customText.trim()) {
      if (onSubmitText) onSubmitText(customText);
      else alert(`Mensaje enviado: "${customText}"`);
    }
  };

  return (
    <div className="ba-options-screen-wrapper">
      {/* Top Header with Back Arrow and Title (Imagen 3) */}
      <div className="ba-options-top-header">
        <button type="button" className="ba-back-arrow-btn" onClick={onBack} title="Regresar">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#111827" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
        </button>
        <h2 className="ba-options-screen-title">BA A Tiempo</h2>
      </div>

      <div className="ba-screen-inner" style={{ padding: '0 16px 80px 16px' }}>
        {/* Product Summary Mini Card */}
        <div className="ba-product-summary-card">
          <div className="ba-summary-left">
            <div className="ba-summary-icon-circle">
              {/* Icon Hand with Coin */}
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#111827" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="8" r="4" />
                <path d="M12 6v4" />
                <path d="M10.5 7h3" />
                <path d="M4 17c0-2.5 4.5-3.5 8-3.5 1.8 0 3.8.3 5 1 .8.5 2 1.5 2 3.5v1H4v-2z" />
              </svg>
            </div>
            <div className="ba-summary-info">
              <div className="ba-summary-name">{product.name}</div>
              <div className="ba-summary-type">{product.type}</div>
            </div>
          </div>

          <div className="ba-summary-right">
            <div className="ba-summary-due-label">Próximo pago</div>
            <div className="ba-summary-amount">
              ${product.amount}<sup className="ba-sup-cents"> {product.cents}</sup>
            </div>
            <div className="ba-summary-due-date">Vence el {product.dueDate}</div>
          </div>
        </div>

        {/* Section Heading */}
        <div className="ba-options-heading-group">
          <h3>¿Qué sucede con este pago?</h3>
          <p>Cuéntanos para mostrarte la mejor opción.</p>
        </div>

        {/* List of Options (5 Cards) */}
        <div className="ba-options-list">
          {options.map((opt) => (
            <button
              key={opt.id}
              type="button"
              className="ba-option-card-row"
              onClick={() => onSelectOption ? onSelectOption(opt) : alert(`Seleccionaste: ${opt.title}`)}
            >
              <div className={`ba-option-icon-circle ${opt.bgClass}`}>
                {opt.icon}
              </div>
              <div className="ba-option-text-group">
                <div className="ba-option-title">{opt.title}</div>
                <div className="ba-option-subtitle">{opt.subtitle}</div>
              </div>
              <div className="ba-option-arrow">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 18 15 12 9 6" />
                </svg>
              </div>
            </button>
          ))}
        </div>

        {/* Custom Text Area Input */}
        <div className="ba-custom-input-section">
          <label className="ba-custom-input-label">
            También puedes escribir lo que sucede
          </label>
          <div className="ba-textarea-container">
            <textarea
              className="ba-custom-textarea"
              placeholder="Cuéntanos en tus palabras..."
              maxLength={300}
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              onKeyDown={handleTextKeyDown}
              rows={2}
            />
            <div className="ba-char-counter">
              {customText.length}/300
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
