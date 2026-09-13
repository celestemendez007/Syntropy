import { useEffect, useState } from 'react'
import './App.css'
import Simulator from './Simulator'
import AdminTab from './AdminTab'

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
            ? <span className="pill pill-critical">Sí (Detectado)</span>
            : <span className="pill pill-good">No</span>),
        },
        { key: 'result', label: 'Resolución Final' },
      ]}
    />
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
          <p><strong>Algoritmo de Momento (Días Antes):</strong> Igual que la hora, agrupa envíos previos en buckets (1-2 días, 3-5 días, 6-8 días). Elige el rango donde el cliente tenga mejor tasa histórica de conversión. Por defecto: 5 días antes.</p>
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
        <button className={activeTab === 'technical' ? 'active' : ''} onClick={() => setActiveTab('technical')}>Algoritmos IA (Docs)</button>
        <button className={activeTab === 'simulator' ? 'active' : ''} onClick={() => setActiveTab('simulator')}>Simulador de Llamada (Fase 6)</button>
        <button className={activeTab === 'admin' ? 'active' : ''} onClick={() => setActiveTab('admin')}>Arquetipos (Admin)</button>
      </nav>
      
      {activeTab === 'simulator' ? (
        <Simulator />
      ) : activeTab === 'admin' ? (
        <AdminTab />
      ) : activeTab === 'technical' ? (
        <TechnicalTab />
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
        <h2>Arquitectura del Sistema (Cerebro Matemático vs IA Conversacional)</h2>
        <div className="card-grid">
          <div className="card">
            <h3 style={{ color: '#10b981', marginBottom: '10px' }}>1. Cerebro Matemático (Machine Learning Predictivo)</h3>
            <p style={{ color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              <strong>100% Matemático y determinista (Cero azar).</strong> Se ejecuta <em>antes</em> de que el cliente reciba cualquier mensaje. Lee la base de datos financiera para:
            </p>
            <ul style={{ paddingLeft: '20px', color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              <li>Detectar señales de incumplimiento (Riesgo).</li>
              <li>Medir la Capacidad Digital (¿Sabe usar la app?).</li>
              <li><strong>Decidir el canal y el Timing exacto:</strong> Elige entre WhatsApp o Llamada, calcula exactamente <em>cuántos días antes de la fecha de pago</em> es ideal enviar el mensaje, y en qué ventana de horas (por ejemplo, aprovechando los horarios de almuerzo que estadísticamente tienen mayor tasa de respuesta).</li>
            </ul>
          </div>
          <div className="card">
            <h3 style={{ color: '#3b82f6', marginBottom: '10px' }}>2. Motor de Políticas (Reglas del Banco)</h3>
            <p style={{ color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              Cruza los datos del modelo de ML con las reglas de negocio del banco para clasificar la situación.
            </p>
            <ul style={{ paddingLeft: '20px', color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              <li>Clasifica al cliente en un <strong>Arquetipo (A1-A8)</strong>.</li>
              <li>Extrae exactamente <strong>qué alternativas de pago</strong> están autorizadas para ese producto y perfil.</li>
            </ul>
          </div>
          <div className="card">
            <h3 style={{ color: '#a855f7', marginBottom: '10px' }}>3. IA Conversacional (LLM Groq) + Seguridad</h3>
            <p style={{ color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              Es la cara visible. Recibe el contexto estructurado y su única misión es negociar empáticamente.
            </p>
            <ul style={{ paddingLeft: '20px', color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              <li><strong>Comunica y Recomienda:</strong> Adapta su lenguaje, explica la deuda y ofrece solo las alternativas dictadas por el Motor de Políticas.</li>
              <li><strong>Guardrails (Escalamiento):</strong> Si detecta hostilidad, fraude, problemas técnicos en la app, o alucina una opción prohibida, bloquea el chat y escala a un humano.</li>
            </ul>
          </div>
        </div>
      </section>

      <section>
        <h2>Lógica de Decisión del Agente (Reglas de Negocio)</h2>
        <div className="card-grid">
          <div className="card">
            <h3 style={{ color: '#818cf8', marginBottom: '10px' }}>Tipos de Clasificaciones (Lo que la IA escucha)</h3>
            <ul style={{ paddingLeft: '20px', color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              <li><strong>Barreras del Cliente:</strong> Olvido de fecha (FORGOT), Desfase de quincena (DATE_MISMATCH), Falta de liquidez temporal (LIQUIDITY), Falla de la app bancaria (TECHNICAL), Fraude o queja (DISPUTE).</li>
              <li><strong>Tonos Emocionales:</strong> COOPERATIVE (Amable), NEUTRAL (Seco), TENSE (Preocupado), HOSTILE (Agresivo).</li>
            </ul>
          </div>
          <div className="card">
            <h3 style={{ color: '#818cf8', marginBottom: '10px' }}>Recomendaciones al Cliente (Soluciones)</h3>
            <ul style={{ paddingLeft: '20px', color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              <li><strong>Pago Parcial:</strong> Permite abonar una fracción sin manchar severamente el historial.</li>
              <li><strong>Plan de Pagos (Calendario):</strong> Ajusta la fecha de corte para coincidir con el día de pago de nómina del cliente.</li>
              <li><strong>Ahorro Automático:</strong> Domicilia micropagos diarios/semanales.</li>
            </ul>
          </div>
          <div className="card">
            <h3 style={{ color: '#818cf8', marginBottom: '10px' }}>Medidas que toma la IA (Guardrails)</h3>
            <ul style={{ paddingLeft: '20px', color: '#94a3b8', lineHeight: '1.6', fontSize: '0.95rem' }}>
              <li><strong>Negociación Autónoma:</strong> Si el tono es Cooperativo y el problema es netamente financiero, la IA cierra el trato sola.</li>
              <li><strong>Transferencia a Humano:</strong> Si detecta un tono <strong style={{color: '#ff6b6b'}}>HOSTILE</strong>, o problemas como <strong>DISPUTE/TECHNICAL</strong>, la IA finaliza amablemente y transfiere a un asesor real.</li>
            </ul>
          </div>
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
