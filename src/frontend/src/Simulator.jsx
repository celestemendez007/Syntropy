import { useEffect, useState, useRef } from 'react'

export default function Simulator() {
  const [customers, setCustomers] = useState([])
  const [selectedCustomer, setSelectedCustomer] = useState('')
  const [history, setHistory] = useState([])
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef(null)

  useEffect(() => {
    fetch('http://localhost:8000/api/customers')
      .then(r => r.json())
      .then(data => {
        setCustomers(data)
        if (data.length > 0) setSelectedCustomer(data[0].customer_id)
      })
      .catch(e => console.error("Error fetching customers:", e))
  }, [])

  // Setup Web Speech API for Speech to Text
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      const recognition = new SpeechRecognition()
      recognition.lang = 'es-SV' // El Salvador Spanish
      recognition.continuous = false
      recognition.interimResults = false

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript
        setInputText(prev => prev + " " + transcript)
      }
      recognition.onend = () => {
        setIsListening(false)
      }
      recognitionRef.current = recognition
    }
  }, [])

  const toggleListen = () => {
    if (isListening) {
      recognitionRef.current?.stop()
      setIsListening(false)
    } else {
      recognitionRef.current?.start()
      setIsListening(true)
    }
  }

  const speakText = (text) => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel() // Stop any current speech
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'es-SV'
      
      // Try to find a good Spanish voice
      const voices = window.speechSynthesis.getVoices()
      const esVoice = voices.find(v => v.lang.startsWith('es'))
      if (esVoice) utterance.voice = esVoice
      
      window.speechSynthesis.speak(utterance)
    }
  }

  const sendMessage = async () => {
    if (!inputText.trim()) return
    const userMsg = { role: 'user', content: inputText.trim() }
    const newHistory = [...history, userMsg]
    setHistory(newHistory)
    setInputText('')
    setLoading(true)
    setError(null)

    try {
      const res = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: selectedCustomer,
          history: newHistory
        })
      })

      if (!res.ok) {
        const errData = await res.json()
        throw new Error(errData.detail || 'Error en el servidor')
      }

      const data = await res.json()
      const asstMsg = { 
        role: 'assistant', 
        content: data.reply,
        hallucination_flagged: data.hallucination_flagged,
        unauthorized_mentions: data.unauthorized_mentions
      }
      setHistory(prev => [...prev, asstMsg])
      
      // Speak the assistant's reply
      speakText(data.reply)

    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="simulator-container">
      <h2>Simulador Interactivo de Cliente (Fase 6)</h2>
      <p>Selecciona un cliente para probar cómo negocia el modelo (Policy Engine + LLM).</p>
      
      <div className="sim-controls">
        <select 
          value={selectedCustomer} 
          onChange={e => {
            setSelectedCustomer(e.target.value)
            setHistory([]) // clear history on change
          }}
        >
          {customers.map(c => (
            <option key={c.customer_id} value={c.customer_id}>
              {c.customer_id} - {c.scenario}
            </option>
          ))}
        </select>
        <button onClick={() => setHistory([])} className="btn-secondary">Reiniciar Chat</button>
      </div>

      <div className="chat-window">
        {history.length === 0 && <div className="chat-empty">Escribe o habla para empezar la negociación...</div>}
        {history.map((msg, i) => (
          <div key={i} className={`chat-bubble-container ${msg.role}`}>
            <div className={`chat-bubble ${msg.role}`}>
              {msg.content}
            </div>
            {msg.hallucination_flagged && (
              <div className="hallucination-warning">
                ⚠️ Alucinación detectada: intentó ofrecer {JSON.stringify(msg.unauthorized_mentions)}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="chat-bubble-container assistant"><div className="chat-bubble assistant typing">Escribiendo...</div></div>}
      </div>

      {error && <div className="sim-error">{error}</div>}

      <div className="chat-input-area">
        {recognitionRef.current && (
          <button 
            className={`mic-btn ${isListening ? 'listening' : ''}`}
            onClick={toggleListen}
            title="Usar Voz"
          >
            {isListening ? '🛑' : '🎤'}
          </button>
        )}
        <input 
          type="text" 
          value={inputText}
          onChange={e => setInputText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && sendMessage()}
          placeholder="Escribe tu mensaje como cliente..."
        />
        <button onClick={sendMessage} disabled={loading || !inputText.trim()}>
          Enviar
        </button>
      </div>
    </div>
  )
}
