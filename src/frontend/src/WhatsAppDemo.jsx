import { useEffect, useRef, useState } from 'react'

// Demo de canal WhatsApp: SOLO texto, sin audio. Incluye un botón de "Pagar
// ahora" fijo -- el objetivo del canal es que el cliente pueda resolver (pagar
// o negociar) sin salir del chat. Pensado para conectarse más adelante a la
// app bancaria simulada (misma API /api/chat, mismo historial).
export default function WhatsAppDemo() {
  const [customers, setCustomers] = useState([])
  const [customerId, setCustomerId] = useState('')
  const [history, setHistory] = useState([])
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const scrollRef = useRef(null)

  useEffect(() => {
    fetch('http://localhost:8000/api/customers')
      .then((r) => r.json())
      .then((data) => {
        setCustomers(data)
        if (data.length > 0) setCustomerId(data[0].customer_id)
      })
      .catch((e) => console.error('Error fetching customers:', e))
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [history, loading])

  const send = async (text) => {
    if (!text.trim() || !customerId) return
    const userMsg = { role: 'user', content: text.trim() }
    const newHistory = [...history, userMsg]
    setHistory(newHistory)
    setInputText('')
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ customer_id: customerId, history: newHistory }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.detail || 'Error en el servidor')
      }
      const data = await res.json()
      setHistory((prev) => [...prev, {
        role: 'assistant', content: data.reply,
        hallucination_flagged: data.hallucination_flagged,
        unauthorized_mentions: data.unauthorized_mentions,
      }])
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  const handlePayNow = () => send('Quiero pagar ahora mismo, ¿cómo lo hago?')
  const handleReset = () => { setHistory([]); setError(null) }

  return (
    <div className="wa-page">
      <div className="wa-controls">
        <select value={customerId} onChange={(e) => { setCustomerId(e.target.value); handleReset() }}>
          {customers.map((c) => (
            <option key={c.customer_id} value={c.customer_id}>{c.customer_id} - {c.scenario}</option>
          ))}
        </select>
        <button className="btn-secondary" onClick={handleReset}>Reiniciar chat</button>
      </div>

      <div className="wa-phone">
        <div className="wa-header">
          <div className="wa-avatar">BA</div>
          <div className="wa-header-text">
            <div className="wa-header-name">Bancoagrícola</div>
            <div className="wa-header-status">en línea</div>
          </div>
        </div>

        <div className="wa-body" ref={scrollRef}>
          {history.length === 0 && (
            <div className="wa-empty">El banco te va a escribir por acá. También podés escribir vos primero.</div>
          )}
          {history.map((msg, i) => (
            <div key={i} className={`wa-bubble-row ${msg.role}`}>
              <div className={`wa-bubble ${msg.role}`}>
                {msg.content}
                {msg.hallucination_flagged && (
                  <div className="wa-flag">⚠️ mencionó algo no autorizado: {JSON.stringify(msg.unauthorized_mentions)}</div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="wa-bubble-row assistant">
              <div className="wa-bubble assistant wa-typing"><span></span><span></span><span></span></div>
            </div>
          )}
        </div>

        {error && <div className="wa-error">{error}</div>}

        <div className="wa-quick-actions">
          <button className="wa-quick-pay" onClick={handlePayNow} disabled={loading}>💳 Pagar ahora</button>
        </div>

        <div className="wa-input-row">
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send(inputText)}
            placeholder="Escribí un mensaje"
          />
          <button className="wa-send" onClick={() => send(inputText)} disabled={loading || !inputText.trim()}>➤</button>
        </div>
      </div>
    </div>
  )
}
