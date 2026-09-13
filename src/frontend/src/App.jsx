import { useEffect, useState } from 'react'
import './App.css'

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

function ModelCard({ title, winner, why, metricsTable }) {
  return (
    <div className="card model-card">
      <h3>{title}</h3>
      <div className="model-winner">Ganador: <strong>{winner}</strong></div>
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

function GoldenCustomersTable({ rows }) {
  return (
    <MiniTable
      rows={rows}
      columns={[
        { key: 'customer_id', label: 'Cliente' },
        { key: 'scenario', label: 'Escenario' },
        { key: 'expected_situation', label: 'Esperado' },
        { key: 'actual_situation', label: 'Obtenido' },
        {
          key: 'passed', label: 'Resultado',
          render: (r) => <span className={r.passed ? 'pill pill-good' : 'pill pill-critical'}>{r.passed ? 'PASA' : 'FALLA'}</span>,
        },
      ]}
    />
  )
}

function GoldenConversationsTable({ rows }) {
  return (
    <MiniTable
      rows={rows}
      columns={[
        { key: 'conversation_id', label: 'ID' },
        { key: 'customer_id', label: 'Cliente' },
        { key: 'barrier_detected', label: 'Barrera' },
        {
          key: 'tone_overall', label: 'Tono',
          render: (r) => <span className={`pill pill-${STATUS_COLOR[r.tone_overall] || 'warning'}`}>{r.tone_overall}</span>,
        },
        {
          key: 'llm_hallucination_flag', label: 'Alucinación',
          render: (r) => (r.llm_hallucination_flag
            ? <span className="pill pill-critical">SÍ (caso adversarial)</span>
            : <span className="pill pill-good">no</span>),
        },
        { key: 'result', label: 'Resultado' },
      ]}
    />
  )
}

function PriorityTable({ rows }) {
  return (
    <MiniTable
      rows={rows}
      columns={[
        { key: 'situation_hint', label: 'Situación' },
        { key: 'barrier_detected', label: 'Barrera' },
        { key: 'channel', label: 'Canal' },
        { key: 'alt_id', label: 'Alternativa' },
        { key: 'n_offered', label: 'N ofrecidas' },
        { key: 'success_rate', label: 'Success rate', render: (r) => r.success_rate.toFixed(3) },
      ]}
    />
  )
}

function ScoredCustomersTable({ rows }) {
  return (
    <MiniTable
      rows={rows}
      columns={[
        { key: 'customer_id', label: 'Cliente' },
        { key: 'situation', label: 'Situación', render: (r) => r.situation.situation_hint },
        { key: 'risk_level', label: 'Riesgo', render: (r) => <span className={`pill pill-${STATUS_COLOR[r.risk.risk_level] || 'warning'}`}>{r.risk.risk_level}</span> },
        { key: 'risk_score', label: 'risk_score', render: (r) => r.risk.risk_score.toFixed(2) },
        { key: 'should_contact', label: '¿Contactar?', render: (r) => (r.nba.should_contact ? 'Sí' : 'No') },
        { key: 'action', label: 'Acción', render: (r) => r.nba.recommended_action },
        { key: 'channel', label: 'Canal', render: (r) => r.channel.channel_used },
      ]}
    />
  )
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

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

  const golden = data.golden_customers
  const goldenPassCount = golden.filter((g) => g.passed).length

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>BA A Tiempo — Panel de administración (mínimo)</h1>
        <p className="subtitle">
          Datos sintéticos. Generado {new Date(data.generated_at).toLocaleString('es-SV')}.
        </p>
      </header>

      <section>
        <h2>Vista 1 — Cartera</h2>
        <div className="stat-row">
          <StatTile label="Clientes muestreados" value={data.portfolio.n_sampled} />
          <StatTile label="% no contactar (S0/riesgo bajo)" value={`${data.portfolio.pct_no_contact}%`}
                    sub="Sabe cuándo no molestar" />
          <StatTile label="Golden customers OK" value={`${goldenPassCount}/${golden.length}`} />
          <StatTile label="Conversaciones (golden + sintéticas)"
                    value={data.conversation_metrics.n_conversations + data.golden_conversations.length} />
        </div>
        <div className="card-grid">
          <DistributionCard title="Distribución de situation_hint" distribution={data.portfolio.situation_hint_distribution} />
          <DistributionCard title="Distribución de risk_level" distribution={data.portfolio.risk_level_distribution} statusMap={STATUS_COLOR} />
          <CountsCard title="Acción recomendada (NBA)" counts={data.portfolio.recommended_action_distribution} />
          <DistributionCard title="Origen del canal elegido" distribution={data.portfolio.channel_source_distribution} />
        </div>
      </section>

      <section>
        <h2>Vista 2 — Modelos (Fases 2-4)</h2>
        <div className="card-grid">
          <ModelCard title="Detección de anomalías" winner={data.models.anomaly_detection.winner}
                     why={data.models.anomaly_detection.why} />
          <ModelCard title="Riesgo supervisado" winner={data.models.supervised_risk.winner}
                     why={data.models.supervised_risk.why} />
          <ModelCard title="Preferencia de canal" winner="Nivel 1 + Nivel 2 + fallback CALL"
                     why={data.models.channel_preference.why} />
          <div className="card">
            <h3>Latencia end-to-end (score_customer)</h3>
            <p className="model-why">
              p95 real ≈ {data.models.score_customer_latency?.real_customers?.p95_ms?.toFixed(1)} ms por cliente
              (tras corregir el cuello de botella de `top_factors`, ver Fase 5).
            </p>
          </div>
        </div>
      </section>

      <section>
        <h2>Vista 3 — Métricas de interacción (Fase 6, conversaciones sintéticas)</h2>
        <div className="stat-row">
          <StatTile label="Barrera coincide con situación inferida" value={`${(data.conversation_metrics.barrier_vs_situation_match_rate * 100).toFixed(1)}%`} />
          <StatTile label="Tasa de escalamiento" value={`${(data.conversation_metrics.escalation_rate * 100).toFixed(1)}%`} />
          <StatTile label="Tasa de aceptación de alternativas" value={`${(data.conversation_metrics.acceptance_rate * 100).toFixed(1)}%`} />
        </div>
        <div className="card-grid">
          <DistributionCard title="Tono de la conversación" distribution={data.conversation_metrics.tone_distribution} statusMap={STATUS_COLOR} />
          <DistributionCard title="Barrera detectada" distribution={data.conversation_metrics.barrier_distribution} />
        </div>
      </section>

      <section>
        <h2>Vista 4 — Feedback loop (Fase 7): top de la tabla de prioridades</h2>
        <p className="section-note">
          Ordenado por <code>success_rate</code> (suavizado bayesiano). Datos sintéticos — ver
          <code> research/ba_a_tiempo/outputs/nba_priority_table_report.md</code> para la demo de recálculo.
        </p>
        <PriorityTable rows={data.nba_priority_table_top} />
      </section>

      <section>
        <h2>Golden customers (validación, 12 casos)</h2>
        <GoldenCustomersTable rows={golden} />
      </section>

      <section>
        <h2>Golden conversations (10 casos, incluye 1 adversarial)</h2>
        <GoldenConversationsTable rows={data.golden_conversations} />
      </section>

      <section>
        <h2>Muestra de clientes puntuados (score_customer en vivo)</h2>
        <ScoredCustomersTable rows={data.sample_scored_customers} />
      </section>

      <footer className="dashboard-footer">
        Todos los datos son sintéticos (SUPUESTO DE DEMO). Ver <code>README.md</code> y <code>docs/contracts.md</code>.
      </footer>
    </div>
  )
}
