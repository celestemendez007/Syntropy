import { useEffect, useState } from 'react'
import './App.css'
import Simulator from './Simulator'

const STATUS_COLOR = {
  LOW: 'good', MEDIUM: 'warning', HIGH: 'critical',
  COOPERATIVE: 'good', NEUTRAL: 'warning', TENSE: 'serious', HOSTILE: 'critical',
}

function StatTile({ label, value, sub }) {
  return (
    <div className="stat-tile">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  )
}

function BarRow({ label, pct, status, count }) {
  const cls = status ? `bar-fill status-${status}` : 'bar-fill'
  return (
    <div className="bar-row">
      <span className="bar-label">{label}</span>
      <div className="bar-track">
        <div className={cls} style={{ width: `${Math.max(pct, 2)}%` }} />
      </div>
      <span className="bar-value">{count != null ? count : `${pct.toFixed(1)}%`}</span>
    </div>
  )
}

function DistributionCard({ title, distribution, statusMap, sortByValue = true }) {
  let entries = Object.entries(distribution || {})
  if (sortByValue) entries = entries.sort((a, b) => b[1] - a[1])
  return (
    <div className="card">
      <h3>{title}</h3>
      {entries.map(([key, val]) => (
        <BarRow key={key} label={key} pct={val * 100} status={statusMap?.[key]} />
      ))}
    </div>
  )
}

function CountsCard({ title, counts }) {
  const entries = Object.entries(counts || {}).sort((a, b) => b[1] - a[1])
  const max = Math.max(...entries.map(([, v]) => v), 1)
  return (
    <div className="card">
      <h3>{title}</h3>
      {entries.map(([key, val]) => (
        <BarRow key={key} label={key} pct={(val / max) * 100} count={val} />
      ))}
    </div>
  )
}

function ModelCard({ title, winner, competitors, why, metricsTable }) {
  return (
    <div className="card model-card">
      <h3>{title}</h3>
      <div className="model-winner">Ganador: <strong>{winner}</strong></div>
      {competitors && <div className="model-competitors" style={{ fontSize: '0.9rem', color: '#94a3b8', marginBottom: '10px' }}>Compitió contra: {competitors}</div>}
      <p className="model-why">{why}</p>
      {metricsTable}
    </div>
  )
}

function MiniTable({ rows, columns }) {
  if (!rows || rows.length === 0) return null
  return (
    <div className="table-scroll">
      <table className="mini-table">
        <thead>
          <tr>{columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {columns.map((c) => <td key={c.key}>{c.render ? c.render(row) : row[c.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function HistoryTable({ rows }) {
  return (
    <MiniTable
      rows={rows}
      columns={[
        { key: 'customer_id', label: 'ID Cliente' },
        {
          key: 'tone_overall', label: 'Emoción de la Persona',
          render: (r) => <span className={`pill pill-${STATUS_COLOR[r.tone_overall] || 'warning'}`}>{r.tone_overall}</span>,
        },
        { key: 'barrier_detected', label: 'Clasificación del Problema' },
        {
          key: 'llm_hallucination_flag', label: 'Alucinación de IA',
          render: (r) => (r.llm_hallucination_flag
            ? <span className="pill pill-critical">SÍ (Detectado)</span>
            : <span className="pill pill-good">No</span>),
        },
        { key: 'result', label: 'Resolución Final' },
      ]}
    />
  )
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')

  useEffect(() => {
    fetch('/data/dashboard_data.json')
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        return r.json()
      })
      .then(setData)
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="dashboard">
        <p className="error">
          No se pudo cargar data/dashboard_data.json ({error}). Corré{' '}
          <code>python src/backend/export_dashboard_data.py</code> (o <code>run_all.py</code>) primero.
        </p>
      </div>
    )
  }
  if (!data) return <div className="dashboard"><p>Cargando...</p></div>

  return (
    <div className="app-container">
      <nav className="top-nav">
        <button className={activeTab === 'dashboard' ? 'active' : ''} onClick={() => setActiveTab('dashboard')}>Dashboard Central</button>
        <button className={activeTab === 'simulator' ? 'active' : ''} onClick={() => setActiveTab('simulator')}>Simulador de Llamada (Fase 6)</button>
      </nav>
      
      {activeTab === 'simulator' ? (
        <Simulator />
      ) : (
      <div className="dashboard">
        <header className="dashboard-header">
          <h1>Panel de Resultados IA</h1>
          <p className="subtitle">
            Mostrando Modelos Activos y Registro de Conversaciones
          </p>
        </header>

      <section>
        <h2>Modelos Entrenados (Ganadores)</h2>
        <div className="card-grid">
          <ModelCard title="Detección de anomalías" winner={data.models.anomaly_detection.winner}
                     competitors="Z-score de Mahalanobis"
                     why={data.models.anomaly_detection.why} />
          <ModelCard title="Riesgo supervisado" winner={data.models.supervised_risk.winner}
                     competitors="Random Forest y LightGBM"
                     why={data.models.supervised_risk.why} />
          <ModelCard title="Preferencia de canal" winner="Nivel 1 + Nivel 2 + fallback CALL"
                     competitors="Enrutamiento de reglas fijas (Baseline)"
                     why={data.models.channel_preference.why} />
        </div>
      </section>

      <section>
        <h2>Historia de Llamadas y Mensajes</h2>
        <div className="stat-row" style={{ marginBottom: '20px' }}>
          <StatTile label="Llamadas y Mensajes Totales" value={data.conversation_metrics.n_conversations + data.golden_conversations.length} />
          <StatTile label="Tasa de Resolución Exitosa" value={`${(data.conversation_metrics.acceptance_rate * 100).toFixed(1)}%`} />
          <StatTile label="Tasa de Transferencia a Humano" value={`${(data.conversation_metrics.escalation_rate * 100).toFixed(1)}%`} />
        </div>
        <HistoryTable rows={data.golden_conversations} />
      </section>

      <footer className="dashboard-footer">
        Todos los datos son de prueba (simulación).
      </footer>
      </div>
      )}
    </div>
  )
}
