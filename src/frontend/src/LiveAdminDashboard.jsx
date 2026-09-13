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
    <div className="admin-tab">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <h2>Monitor de Interacciones en Vivo</h2>
        <button onClick={fetchCalls} className="btn">Actualizar Ahora</button>
      </div>

      <div className="table-scroll">
        <table className="mini-table">
          <thead>
            <tr>
              <th>ID Usuario</th>
              <th>Última Fase</th>
              <th>Emoción</th>
              <th>Hora de Actualización</th>
              <th>Acción</th>
            </tr>
          </thead>
          <tbody>
            {calls.length === 0 ? (
              <tr><td colSpan="5">No hay interacciones en vivo registradas aún. Inicia un chat en el simulador.</td></tr>
            ) : (
              calls.map((call, idx) => (
                <React.Fragment key={idx}>
                  <tr>
                    <td><strong>{call.customer_id}</strong></td>
                    <td><span className={`badge ${STATUS_COLOR[call.phase] || 'neutral'}`}>{call.phase}</span></td>
                    <td><span className={`badge ${STATUS_COLOR[call.emotion] || 'neutral'}`}>{call.emotion}</span></td>
                    <td>{new Date(call.timestamp).toLocaleString()}</td>
                    <td>
                      <button onClick={() => setExpandedRow(expandedRow === idx ? null : idx)}>
                        {expandedRow === idx ? 'Ocultar' : 'Ver Historial'}
                      </button>
                    </td>
                  </tr>
                  {expandedRow === idx && (
                    <tr>
                      <td colSpan="5">
                        <div style={{ backgroundColor: '#2d333b', padding: '15px', borderRadius: '5px', textAlign: 'left', fontSize: '13px' }}>
                          {call.history.map((msg, i) => (
                            <div key={i} style={{ marginBottom: '10px', color: msg.role === 'assistant' ? '#58a6ff' : '#fff' }}>
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
  );
}
