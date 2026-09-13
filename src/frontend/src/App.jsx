import { useEffect, useState } from 'react'
import './App.css'
import AdminTab from './AdminTab'
import WhatsAppDemo from './WhatsAppDemo'
import CallDemo from './CallDemo'
import BaATiempoApp from './ba-a-tiempo/BaATiempoApp'

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

function HistoryTab({ data }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [toneFilter, setToneFilter] = useState('')
  const [barrierFilter, setBarrierFilter] = useState('')
  const [hallucinationFilter, setHallucinationFilter] = useState('')
  const [resultFilter, setResultFilter] = useState('')

  const allRows = data.golden_conversations || []
  
  const filteredRows = allRows.filter(r => {
    if (searchTerm && !r.customer_id.toLowerCase().includes(searchTerm.toLowerCase())) return false
    if (toneFilter && r.tone_overall !== toneFilter) return false
    if (barrierFilter && r.barrier_detected !== barrierFilter) return false
    if (hallucinationFilter === 'yes' && !r.llm_hallucination_flag) return false
    if (hallucinationFilter === 'no' && r.llm_hallucination_flag) return false
    if (resultFilter && r.result !== resultFilter) return false
    return true
  })

  // Get unique values for filters
  const uniqueTones = [...new Set(allRows.map(r => r.tone_overall))]
  const uniqueBarriers = [...new Set(allRows.map(r => r.barrier_detected))]
  const uniqueResults = [...new Set(allRows.map(r => r.result))]

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Historia de Llamadas y Mensajes</h1>
        <p className="subtitle">Registro histórico con filtros interactivos.</p>
      </header>

      <div className="stat-row" style={{ marginBottom: '20px' }}>
        <StatTile label="Llamadas y Mensajes Totales" value={data.conversation_metrics.n_conversations + data.golden_conversations.length} />
        <StatTile label="Tasa de Resolución Exitosa" value={`${(data.conversation_metrics.acceptance_rate * 100).toFixed(1)}%`} />
        <StatTile label="Tasa de Transferencia a Humano" value={`${(data.conversation_metrics.escalation_rate * 100).toFixed(1)}%`} />
      </div>

      <div className="card" style={{ marginBottom: '20px' }}>
        <h3 style={{ marginBottom: '15px' }}>Filtros</h3>
        <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
          <input 
            type="text" 
            placeholder="Buscar ID Cliente..." 
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            style={{ padding: '8px', background: '#0f172a', color: 'white', border: '1px solid #334155', borderRadius: '4px' }}
          />
          <select value={toneFilter} onChange={e => setToneFilter(e.target.value)} style={{ padding: '8px', background: '#0f172a', color: 'white', border: '1px solid #334155', borderRadius: '4px' }}>
            <option value="">Cualquier Emoción</option>
            {uniqueTones.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={barrierFilter} onChange={e => setBarrierFilter(e.target.value)} style={{ padding: '8px', background: '#0f172a', color: 'white', border: '1px solid #334155', borderRadius: '4px' }}>
            <option value="">Cualquier Barrera</option>
            {uniqueBarriers.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
          <select value={hallucinationFilter} onChange={e => setHallucinationFilter(e.target.value)} style={{ padding: '8px', background: '#0f172a', color: 'white', border: '1px solid #334155', borderRadius: '4px' }}>
            <option value="">Alucinación: Todas</option>
            <option value="yes">Sí (Detectado)</option>
            <option value="no">No</option>
          </select>
          <select value={resultFilter} onChange={e => setResultFilter(e.target.value)} style={{ padding: '8px', background: '#0f172a', color: 'white', border: '1px solid #334155', borderRadius: '4px' }}>
            <option value="">Cualquier Resolución</option>
            {uniqueResults.map(r => <option key={r} value={r}>{r}</option>)}
          </select>
          <button onClick={() => {
            setSearchTerm(''); setToneFilter(''); setBarrierFilter(''); setHallucinationFilter(''); setResultFilter('');
          }} className="btn-secondary">Limpiar Filtros</button>
        </div>
      </div>

      <MiniTable
        rows={filteredRows}
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
              ? <span className="pill pill-critical">Sí (Detectado)</span>
              : <span className="pill pill-good">No</span>),
          },
          { key: 'result', label: 'Resolución Final' },
        ]}
      />
    </div>
  )
}

function TechnicalTab() {
  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Documentación Técnica de Algoritmos</h1>
        <p className="subtitle">Desglose de cada modelo matemático, parámetros y cómo el sistema toma decisiones.</p>
      </header>
      
      <section>
        <h2>Fase 1: Detección de Anomalías (Aislamiento de Casos Raros)</h2>
        <div className="card">
          <p><strong>Algoritmo:</strong> <code>Isolation Forest</code> (Machine Learning No Supervisado).</p>
          <p><strong>Parámetros Evaluados:</strong> 10 variables financieras, incluyendo <code>balance_vs_historical</code> (saldo vs su histórico), <code>recent_balance_drop</code>, <code>spending_velocity_7d</code> (velocidad de gasto en los últimos 7 días), y <code>failed_payment_attempts_30d</code>.</p>
          <p><strong>¿Cómo toma la decisión?:</strong> Entrena 200 árboles de aislamiento sobre 3,000 clientes históricos. Genera un "Score de Anomalía". Si un cliente empieza a actuar muy diferente a su propio pasado, el score se dispara. Usa "Ablación por feature" para calcular matemáticamente exactamente qué variable causó la anomalía (ej. <em>"Tus gastos subieron 40%"</em>) y se lo pasa a la IA.</p>
        </div>
      </section>

      <section>
        <h2>Fase 2: Predicción de Mora (Riesgo Supervisado)</h2>
        <div className="card">
          <p><strong>Algoritmo:</strong> <code>Regresión Logística (Logistic Regression)</code>. Ganó contra Random Forest y LightGBM por su interpretabilidad matemática directa (no es caja negra).</p>
          <p><strong>Parámetros Evaluados:</strong> 11 features fuertemente correlacionados, como <code>balance_ratio</code> (saldo disponible vs límite), <code>projected_coverage</code>, <code>income_due_gap_pos</code> (distancia en días entre el día que recibe su sueldo y el día que le toca pagar), y <code>payment_punctuality</code>.</p>
          <p><strong>¿Cómo toma la decisión?:</strong> Calcula estadísticamente la probabilidad (0% a 100%) de que el cliente cometa un "Late Payment" (retraso) en el próximo ciclo (<code>synthetic_late_payment_next_cycle</code>). Esta probabilidad se cruza con el Score de Anomalía (Fase 1) para dar el <strong>Nivel de Riesgo Final</strong>.</p>
        </div>
      </section>

      <section>
        <h2>Fase 3: Preferencia de Canal y Timing (Cuándo y Dónde)</h2>
        <div className="card">
          <p><strong>Algoritmo de Canal:</strong> Modelo Híbrido. Nivel 1 evalúa la tasa de respuesta histórica del propio cliente. Nivel 2 es una Regresión Logística poblacional basada en <code>income_type</code>, <code>app_engagement</code>, y edad en la plataforma. Si ninguno da confianza alta (&gt;0.5), hace <em>Fallback</em> a <strong>Llamada Telefónica</strong> obligatoria.</p>
          <p><strong>Algoritmo de Momento (Hora):</strong> Agrupa (bucketiza) el historial de mensajes del cliente en rangos de 1.5 horas. Calcula promedios históricos. <em>No usa K-Means</em>, usa frecuencias estadísticas puras. Si no hay historial suficiente (menos de 5 mensajes previos), usa promedios poblacionales, por ejemplo, asignando la hora de almuerzo (12:00-13:30) para asalariados (<code>SALARIED</code>), ya que matemáticamente tienen mayor tasa de respuesta en ese horario.</p>
          <p><strong>Algoritmo de Momento (Días Antes):</strong> Es un <strong>Modelo Heurístico Basado en Frecuencias Estadísticas</strong>. El sistema utiliza "Buckets" (Cestas) que analizan a cada cliente de manera individual:</p>
          <ul style={{ paddingLeft: '20px', marginTop: '5px' }}>
            <li>Revisa todo el historial del usuario y agrupa los mensajes enviados en cuatro cestas: <em>1-2 días antes, 3-5 días, 6-8 días, y 9-15 días</em>.</li>
            <li>Calcula matemáticamente en qué "cesta" ese usuario en particular suele responder más.</li>
            <li><strong>Depende del usuario:</strong> Si Carlos siempre contesta y paga cuando se le avisa con 15 días de anticipación (apenas le depositan), el sistema automáticamente le asignará su alerta en el bloque de 9-15 días. Si María suele pagar sobre la raya y contesta mejor faltando 2 días, el modelo la mueve a ese bloque.</li>
            <li>Si un cliente es completamente nuevo y no hay historial suficiente, el sistema usa el promedio poblacional: la alerta estándar <strong>5 días antes</strong> del vencimiento.</li>
          </ul>
        </div>
      </section>

      <section>
        <h2>Fase 4: Motor de Políticas y Alternativas de Usuario (Cero Azar)</h2>
        <div className="card">
          <p><strong>Algoritmo:</strong> Determinista (Árbol de Decisión / Reglas If-Else Fijas). Aquí no interviene Machine Learning, son las reglas inamovibles del banco.</p>
          <p><strong>Parámetros Evaluados:</strong> <code>risk_level</code>, <code>digital_capability</code> (D1 a D3) y tipo de crédito (ej. Credicheque, Hipoteca).</p>
          <p><strong>¿Cómo toma la decisión?:</strong> Asigna un <strong>Arquetipo (A1-A8)</strong> y una <strong>Situación (S0-S6)</strong>. Luego, consulta la base de datos (JSON) armada por el usuario/banco para extraer exactamente qué "Alternativas de Pago" o Recomendaciones están pre-autorizadas para ese Producto y ese Perfil en específico. No se inventa nada.</p>
        </div>
      </section>

      <section>
        <h2>Fase 5: IA Conversacional Generativa (El Chat)</h2>
        <div className="card">
          <p><strong>Algoritmo:</strong> LLM (Large Language Model) <code>Llama-3.1-8b-instant</code> a través de Groq Cloud.</p>
          <p><strong>Responsabilidad:</strong> Ninguna decisión financiera. Su única misión es ingerir todo el contexto calculado (Fases 1 a 4) y transformarlo en una conversación empática y natural. Clasifica en vivo las respuestas del usuario (Tono Emocional y Barrera).</p>
          <p><strong>Guardrails de Seguridad (Regex):</strong> Analiza la salida de la IA milisegundos antes de enviarla. Si el modelo Generativo se "equivoca" (alucina) e intenta ofrecer una recomendación que la Fase 4 no le autorizó, el sistema interrumpe el chat, reporta "Alucinación: Sí" y transfiere a un humano.</p>
        </div>
      </section>
    </div>
  )
}

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('ba_a_tiempo')

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
        <button className={activeTab === 'ba_a_tiempo' ? 'active' : ''} onClick={() => setActiveTab('ba_a_tiempo')}>📱 App Bancoagrícola (BA A Tiempo)</button>
        <button className={activeTab === 'whatsapp' ? 'active' : ''} onClick={() => setActiveTab('whatsapp')}>WhatsApp</button>
        <button className={activeTab === 'call' ? 'active' : ''} onClick={() => setActiveTab('call')}>Llamada</button>
        <button className={activeTab === 'history' ? 'active' : ''} onClick={() => setActiveTab('history')}>Registro Histórico</button>
        <button className={activeTab === 'technical' ? 'active' : ''} onClick={() => setActiveTab('technical')}>Algoritmos IA (Docs)</button>
        <button className={activeTab === 'admin' ? 'active' : ''} onClick={() => setActiveTab('admin')}>Arquetipos (Admin)</button>
      </nav>

      {activeTab === 'ba_a_tiempo' ? (
        <BaATiempoApp />
      ) : activeTab === 'whatsapp' ? (
        <WhatsAppDemo />
      ) : activeTab === 'call' ? (
        <CallDemo />
      ) : activeTab === 'admin' ? (
        <AdminTab />
      ) : activeTab === 'technical' ? (
        <TechnicalTab />
      ) : activeTab === 'history' ? (
        <HistoryTab data={data} />
      ) : null}
    </div>
  )
}
