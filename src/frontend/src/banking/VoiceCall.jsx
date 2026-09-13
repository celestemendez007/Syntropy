import { useEffect, useRef, useState } from 'react'
import { useBank } from './BankContext'
import Icon from './Icon'

export function useVoice(onText) {
  const [listening, setListening] = useState(false)
  const [voiceError, setVoiceError] = useState('')
  const recognition = useRef(null)
  const onTextRef = useRef(onText)
  onTextRef.current = onText
  const supported = typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition)
  const stop = () => { recognition.current?.abort(); setListening(false) }
  const start = () => {
    if (!supported) { setVoiceError('Este navegador no permite dictado. Puedes escribir tu respuesta o usar Chrome / Edge.'); return }
    if (recognition.current) recognition.current.abort()
    window.speechSynthesis?.cancel()
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const instance = new Recognition()
    instance.lang = 'es-SV'; instance.interimResults = false; instance.continuous = false
    instance.onstart = () => setListening(true)
    instance.onend = () => setListening(false)
    instance.onresult = e => { setListening(false); onTextRef.current(e.results[0][0].transcript) }
    instance.onerror = e => {
      setListening(false)
      if (e.error !== 'aborted' && e.error !== 'no-speech') setVoiceError(e.error === 'not-allowed' ? 'Permite el micrófono en tu navegador o continúa por texto.' : 'No pudimos escuchar. Intenta otra vez o escribe tu respuesta.')
    }
    recognition.current = instance; setVoiceError('')
    try { instance.start() } catch { setVoiceError('El micrófono está ocupado. Intenta nuevamente.') }
  }
  useEffect(() => () => recognition.current?.abort(), [])
  return { start, stop, listening, voiceError, supported }
}

export default function VoiceCall() {
  const { state, command, callOpen, setCallOpen, busy, navigate } = useBank()
  const [status, setStatus] = useState('connected')
  const [seconds, setSeconds] = useState(0)
  const [text, setText] = useState('')
  const [caption, setCaption] = useState('')
  const [ended, setEnded] = useState(false)
  const processed = useRef(null)
  const active = useRef(false)
  const voice = useVoice(transcript => { setCaption(transcript); command('message', { text: transcript }) })
  const latest = useRef({ voice, state })
  latest.current = { voice, state }
  function end() {
    active.current = false; voice.stop(); window.speechSynthesis?.cancel(); setStatus('ended'); setEnded(true)
  }
  function speak(textToSay, closeAfter = false) {
    if (!active.current) return
    setCaption(textToSay)
    latest.current.voice.stop()
    if (!window.speechSynthesis) { setStatus('connected'); return }
    window.speechSynthesis.cancel()
    const speech = new SpeechSynthesisUtterance(textToSay)
    speech.lang = 'es-SV'; speech.rate = 0.97
    const voices = window.speechSynthesis.getVoices()
    const spanish = voices.find(v => v.lang.startsWith('es'))
    if (spanish) speech.voice = spanish
    setStatus('speaking')
    speech.onend = () => {
      if (!active.current) return
      if (closeAfter) end()
      else { setStatus('connected'); latest.current.voice.start() }
    }
    speech.onerror = () => { if (active.current) setStatus('connected') }
    window.speechSynthesis.speak(speech)
  }
  useEffect(() => {
    if (!callOpen) return
    active.current = true; setEnded(false); setSeconds(0)
    processed.current = state.messages.filter(m => m.role === 'assistant').at(-1)?.id
    speak('Hola, soy tu asistente de BA A Tiempo. Estoy aquí para ayudarte con tu próximo pago. ¿Qué sucede con este pago?')
    const timer = setInterval(() => { if (active.current) setSeconds(s => s + 1) }, 1000)
    return () => { active.current = false; clearInterval(timer); latest.current.voice.stop(); window.speechSynthesis?.cancel() }
    // Conversation state is read via refs; opening a call starts one voice session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [callOpen])
  useEffect(() => {
    if (!callOpen || !active.current) return
    const last = state.messages.filter(m => m.role === 'assistant').at(-1)
    if (last && last.id !== processed.current) {
      processed.current = last.id
      let speech = last.content
      const offer = state.pending_offer || (state.barrier && !state.receipt ? state.offers[0] : null)
      if (offer) {
        speech += ` ${offer.title}.`
        if (offer.date) speech += ` Fecha: ${new Intl.DateTimeFormat('es-SV', { day: 'numeric', month: 'long' }).format(new Date(offer.date + 'T12:00:00'))}.`
        if (offer.min_amount || offer.amount) speech += ` Monto: ${offer.min_amount || offer.amount} dólares.`
        if (offer.percentage) speech += ` Porcentaje: ${Number((offer.percentage * 100).toFixed(2))} por ciento.`
        speech += state.pending_offer ? ' Si estás de acuerdo, di confirmo.' : ' Puedes decir acepto para revisar el resumen.'
      }
      speak(speech, state.call_end)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.version, callOpen])
  if (!callOpen) return null
  const submit = async e => { e.preventDefault(); if (!text.trim()) return; voice.stop(); await command('message', { text }); setText('') }
  return <section className="voice-call" aria-label="Llamada con BA A Tiempo">
    <div className="call-top"><div className={'round-icon yellow ' + (status === 'speaking' ? 'speaking' : '')}><Icon name="headset" size={30}/></div><div><strong>BA A Tiempo</strong><span>{ended ? 'Llamada finalizada' : status === 'speaking' ? 'Tu asistente está hablando' : voice.listening ? 'Te escucho…' : 'En llamada'} · {Math.floor(seconds / 60).toString().padStart(2, '0')}:{(seconds % 60).toString().padStart(2, '0')}</span></div><button className="icon-button" aria-label="Cerrar llamada" onClick={() => { end(); setCallOpen(false) }}><Icon name="close"/></button></div>
    <div className="voice-wave" aria-hidden="true">{Array.from({length: 15}, (_, i) => <i key={i} style={{ height: [12, 22, 36, 19, 29][i % 5], animationDelay: `${i * .08}s`, animationPlayState: status === 'speaking' || voice.listening ? 'running' : 'paused' }}/>)}</div>
    <p className="call-caption" aria-live="polite">{caption}</p>
    {voice.voiceError && <p className="voice-note">{voice.voiceError}</p>}
    {!ended ? <><div className="call-actions"><button className="button secondary" onClick={() => navigate(state.receipt ? 'receipt' : 'productos')}><Icon name="card"/>Ver mi producto</button><button className={'icon-button mic-toggle ' + (voice.listening ? 'active' : '')} aria-label={voice.listening ? 'Pausar micrófono' : 'Activar micrófono'} onClick={() => voice.listening ? voice.stop() : voice.start()}><Icon name="mic"/></button><button className="icon-button hangup" aria-label="Colgar llamada" onClick={end}><Icon name="call"/></button></div>
    <form className="call-text" onSubmit={submit}><input aria-label="Respuesta por texto durante la llamada" value={text} onChange={e => setText(e.target.value)} maxLength={1500} placeholder="También puedes responder por texto"/><button aria-label="Enviar respuesta a la llamada" disabled={busy || !text.trim()}><Icon name="send" size={20}/></button></form></> : <button className="button primary" onClick={() => setCallOpen(false)}>Continuar en la app</button>}
  </section>
}
