import React, { useEffect, useState } from 'react';

const STATUS_COLOR = {
  COOPERATIVE: 'good', NEUTRAL: 'warning', TENSE: 'serious', HOSTILE: 'critical', CONFUSED: 'warning',
  START: 'neutral', GREETING: 'neutral', INTRO: 'neutral', LISTENING: 'warning', OFFERING: 'serious', CONFIRMING: 'good',
  LLM_GENERATED: 'serious'
};

export default function LiveAdminDashboard() {
  const [calls, setCalls] = useState([]);
  const [error, setError] = useState(null);
  const [expandedRow, setExpandedRow] = useState(null);

  const fetchCalls = () => {
    fetch('http://localhost:8000/api/admin/live_calls')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data) => setCalls(data.reverse())) // Show newest first
      .catch((e) => setError(e.message));
  };

  useEffect(() => {
    fetchCalls();
    // Poll every 5 seconds for live updates
    const interval = setInterval(fetchCalls, 5000);
    return () => clearInterval(interval);
  }, []);

  if (error) {
    return <div className="card error">Error cargando llamadas en vivo: {error}</div>;
  }

  return (
    <div>
      <div style={{ backgroundColor: 'var(--ba-navy)', color: '#fff', padding: '15px 20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{ width: '32px', height: '32px', backgroundColor: 'var(--ba-yellow)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ba-navy)', fontWeight: 'bold' }}>BA</div>
          <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '600' }}>Monitor en Vivo (Admin)</h2>
        </div>
        <button onClick={fetchCalls} style={{ backgroundColor: 'var(--ba-yellow)', color: 'var(--ba-navy)', border: 'none', padding: '8px 15px', borderRadius: 'var(--ba-radius-sm)', fontWeight: 'bold', cursor: 'pointer' }}>Actualizar</button>
      </div>

      <div style={{ padding: '20px' }}>
        <div style={{ backgroundColor: 'var(--ba-card-bg)', borderRadius: 'var(--ba-radius-sm)', padding: '20px', boxShadow: '0 2px 8px rgba(0,0,0,0.05)' }}>
          <div className="table-scroll">
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--ba-border)' }}>
                  <th style={{ padding: '12px 8px', color: 'var(--ba-text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase' }}>ID Usuario</th>
                  <th style={{ padding: '12px 8px', color: 'var(--ba-text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Última Fase</th>
                  <th style={{ padding: '12px 8px', color: 'var(--ba-text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Emoción</th>
                  <th style={{ padding: '12px 8px', color: 'var(--ba-text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Hora</th>
                  <th style={{ padding: '12px 8px', color: 'var(--ba-text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase' }}>Acción</th>
                </tr>
              </thead>
              <tbody>
                {calls.length === 0 ? (
                  <tr><td colSpan="5" style={{ padding: '20px', textAlign: 'center', color: 'var(--ba-text-muted)' }}>No hay interacciones registradas aún.</td></tr>
                ) : (
                  calls.map((call, idx) => (
                    <React.Fragment key={idx}>
                      <tr style={{ borderBottom: '1px solid var(--ba-border-subtle)' }}>
                        <td style={{ padding: '15px 8px', color: 'var(--ba-navy)', fontWeight: '600' }}>{call.customer_id}</td>
                    <td style={{ padding: '15px 8px' }}><span className={`badge ${STATUS_COLOR[call.phase] || 'neutral'}`}>{call.phase}</span></td>
                    <td style={{ padding: '15px 8px' }}><span className={`badge ${STATUS_COLOR[call.emotion] || 'neutral'}`}>{call.emotion}</span></td>
                    <td style={{ padding: '15px 8px', color: 'var(--ba-text-secondary)', fontSize: '0.9rem' }}>{new Date(call.timestamp).toLocaleString()}</td>
                    <td style={{ padding: '15px 8px' }}>
                      <button 
                        onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}
                        style={{ backgroundColor: 'transparent', border: '1px solid var(--ba-border)', color: 'var(--ba-navy)', padding: '5px 10px', borderRadius: 'var(--ba-radius-sm)', cursor: 'pointer', fontWeight: 'bold' }}
                      >
                        {expandedRow === idx ? 'Ocultar' : 'Ver Historial'}
                      </button>
                    </td>
                  </tr>
                  {expandedRow === idx && (
                    <tr>
                      <td colSpan="5">
                        <div style={{ backgroundColor: 'var(--ba-bg)', padding: '20px', borderRadius: 'var(--ba-radius-sm)', textAlign: 'left', fontSize: '14px', border: '1px solid var(--ba-border)' }}>
                          {call.history.map((msg, i) => (
                            <div key={i} style={{ marginBottom: '12px', color: msg.role === 'assistant' ? 'var(--ba-navy)' : 'var(--ba-text-primary)' }}>
                              <strong>{msg.role === 'assistant' ? 'IA / Agente:' : 'Cliente:'}</strong> {msg.content}
                            </div>
                          ))}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))
            )}
          </tbody>
        </table>
      </div>
      </div>
      </div>
    </div>
  );
}
