import { useEffect, useRef, useState } from 'react'

// Demo de canal Llamada: SOLO audio, nada escrito en pantalla -- se escucha y
// se habla, como una llamada real. El backend sigue siendo el mismo motor de
// conversación (/api/chat); acá solo cambia la interfaz: voz en vez de texto.
// Pensado para conectarse más adelante a la app bancaria simulada.

const CLOSING_MARKERS = ['que tenga un excelente día', 'muchas gracias por su tiempo']

export default function CallDemo() {
  const [customers, setCustomers] = useState([])
  const [customerId, setCustomerId] = useState('')
  const [status, setStatus] = useState('idle') // idle | ringing | connected | speaking | listening | ended
  const [seconds, setSeconds] = useState(0)
  const [error, setError] = useState(null)

  const historyRef = useRef([])
  const recognitionRef = useRef(null)
  const timerRef = useRef(null)
  const statusRef = useRef('idle')

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
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return
    const recognition = new SpeechRecognition()
    recognition.lang = 'es-SV'
    recognition.continuous = false
    recognition.interimResults = false
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      handleClientSpeech(transcript)
    }
    recognition.onerror = () => setStatus((s) => (s === 'ended' ? s : 'connected'))
    recognitionRef.current = recognition
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    statusRef.current = status
  }, [status])

  const setStatusSafe = (s) => { if (statusRef.current !== 'ended' || s === 'ended') setStatus(s) }

  const speak = (text, onDone) => {
    if (!('speechSynthesis' in window)) { onDone?.(); return }
    setStatusSafe('speaking')
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = 'es-SV'
    const voices = window.speechSynthesis.getVoices()
    const esVoice = voices.find((v) => v.lang.startsWith('es'))
    if (esVoice) utterance.voice = esVoice
    utterance.onend = () => onDone?.()
    window.speechSynthesis.speak(utterance)
  }

  const isClosingLine = (text) => CLOSING_MARKERS.some((m) => text.toLowerCase().includes(m))

  const askBackend = async (userText) => {
    const newHistory = [...historyRef.current, { role: 'user', content: userText }]
    historyRef.current = newHistory
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
      historyRef.current = [...historyRef.current, { role: 'assistant', content: data.reply }]

      speak(data.reply, () => {
        if (isClosingLine(data.reply) || statusRef.current === 'ended') {
          endCall()
        } else {
          startListening()
        }
      })
    } catch (err) {
      setError(err.message)
      setStatusSafe('connected')
    }
  }

  const startListening = () => {
    if (statusRef.current === 'ended') return
    setStatusSafe('listening')
    try { recognitionRef.current?.start() } catch { /* ya estaba escuchando */ }
  }

  const handleClientSpeech = (transcript) => {
    if (statusRef.current === 'ended') return
    setStatusSafe('connected')
    askBackend(transcript)
  }

  const startCall = () => {
    if (!customerId) return
    setError(null)
    historyRef.current = []
    setSeconds(0)
    setStatusSafe('ringing')
    setTimeout(() => {
      setStatusSafe('connected')
      timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000)
      askBackend('(inicio de llamada, el cliente contesta)')
    }, 1800)
  }

  const endCall = () => {
    window.speechSynthesis.cancel()
    try { recognitionRef.current?.stop() } catch { /* noop */ }
    clearInterval(timerRef.current)
    setStatusSafe('ended')
  }

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const statusLabel = {
    idle: 'Listo para llamar', ringing: 'Timbrando...', connected: 'En llamada',
    speaking: 'Bancoagrícola está hablando...', listening: 'Te escucho...', ended: 'Llamada finalizada',
  }[status]

  return (
    <div className="call-page">
      <div className="call-controls">
        <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} disabled={status !== 'idle' && status !== 'ended'}>
          {customers.map((c) => (
            <option key={c.customer_id} value={c.customer_id}>{c.customer_id} - {c.scenario}</option>
          ))}
        </select>
      </div>

      <div className="call-screen">
        <div className={`call-avatar ${status === 'speaking' ? 'pulse-speak' : ''} ${status === 'listening' ? 'pulse-listen' : ''}`}>
          🏦
        </div>
        <div className="call-name">Bancoagrícola</div>
        <div className="call-status">{statusLabel}</div>
        {(status === 'connected' || status === 'speaking' || status === 'listening') && (
          <div className="call-timer">{formatTime(seconds)}</div>
        )}
        {error && <div className="call-error">{error}</div>}

        <div className="call-actions">
          {status === 'idle' || status === 'ended' ? (
            <button className="call-btn call-btn-answer" onClick={startCall} disabled={!customerId}>📞 Llamar</button>
          ) : (
            <button className="call-btn call-btn-hangup" onClick={endCall}>🔴 Colgar</button>
          )}
        </div>
        {!recognitionRef.current && (
          <p className="call-warning">Tu navegador no soporta reconocimiento de voz -- probá en Chrome de escritorio.</p>
        )}
      </div>
    </div>
  )
}
