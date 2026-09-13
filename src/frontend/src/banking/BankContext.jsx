import { createContext, useContext, useEffect, useReducer, useRef, useCallback, useState } from 'react'

const BankContext = createContext(null)
const STORAGE = 'ba-a-tiempo-session-v1'
function reducer(current, next) {
  if (!next) return null
  if (!current || current.id !== next.id || next.version >= current.version) return next
  return current
}
async function api(path, body) {
  const response = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {})
  let result
  try { result = await response.json() } catch { throw new Error('No pudimos conectar. Intenta nuevamente en un momento.') }
  if (!response.ok) {
    const error = new Error(typeof result.detail === 'string' ? result.detail : 'Revisa los datos e intenta nuevamente.')
    error.status = response.status
    throw error
  }
  return result
}
export function BankingProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [live, setLive] = useState(false)
  const [page, setPage] = useState(location.hash.slice(2) || 'inicio')
  const [callOpen, setCallOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const current = useRef(null)
  const queue = useRef(Promise.resolve())
  const initializing = useRef(null)
  const navigate = useCallback((next) => { location.hash = '/' + next; setPage(next); window.scrollTo({ top: 0, behavior: 'smooth' }) }, [])
  const accept = useCallback((next, follow = true) => {
    if (current.current && current.current.id === next.id && next.version < current.current.version) return
    const changed = !current.current || current.current.id !== next.id || next.version > current.current.version
    current.current = next
    dispatch(next)
    if (follow && changed && next.view_hint) navigate(next.view_hint)
  }, [navigate])
  const create = useCallback(async (customer_id = null, multiple = false) => {
    setBusy(true); setError(null)
    try {
      const next = await api(customer_id ? '/api/sessions' : '/api/demo/login', customer_id ? { customer_id } : { multiple })
      localStorage.setItem(STORAGE, next.id)
      accept(next, false); navigate('inicio'); setCallOpen(false)
    } catch (e) { setError(e.message) } finally { setBusy(false); setLoading(false) }
  }, [accept, navigate])
  useEffect(() => {
    const hash = () => setPage(location.hash.slice(2) || 'inicio')
    window.addEventListener('hashchange', hash)
    if (!initializing.current) initializing.current = (async () => {
      const id = localStorage.getItem(STORAGE)
      if (id) {
        try { accept(await api('/api/sessions/' + id), false); setLoading(false); return }
        catch (e) { if (e.status !== 404) setError(e.message) }
      }
      setLoading(false)
    })()
    return () => window.removeEventListener('hashchange', hash)
  }, [accept, create])
  useEffect(() => {
    if (!state?.id) return
    let stopped = false, socket, timer, heartbeat
    const id = state.id
    function connect() {
      socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/sessions/${id}/live`)
      socket.onopen = () => { setLive(true); heartbeat = setInterval(() => socket.readyState === 1 && socket.send(JSON.stringify({ type: 'ping' })), 20000) }
      socket.onmessage = e => { const data = JSON.parse(e.data); if (!stopped && data.type === 'state' && current.current?.id === id) accept(data.state) }
      socket.onclose = () => { clearInterval(heartbeat); setLive(false); if (!stopped) timer = setTimeout(connect, 2000) }
      socket.onerror = () => socket.close()
    }
    connect()
    // HTTP refresh also keeps the UI current while a WebSocket reconnects.
    const poll = setInterval(() => {
      if (socket.readyState !== 1) api('/api/sessions/' + id).then(s => !stopped && accept(s)).catch(() => {})
    }, 5000)
    return () => { stopped = true; clearInterval(poll); clearInterval(heartbeat); clearTimeout(timer); socket.close() }
  }, [state?.id, accept])
  const command = useCallback((action, payload = {}) => {
    const sessionId = current.current?.id
    const execute = async () => {
    if (!current.current || current.current.id !== sessionId) return null
    setBusy(true); setError(null)
    const id = sessionId
    try {
      const next = await api(`/api/sessions/${id}/commands`, { action, version: current.current.version, ...payload })
      accept(next)
      return next
    } catch (e) {
      setError(e.message)
      if (e.status === 409) { try { accept(await api('/api/sessions/' + id), false) } catch { /* retain current state */ } }
      return null
    } finally { setBusy(false) }
    }
    const result = queue.current.then(execute, execute)
    queue.current = result.catch(() => {})
    return result
  }, [accept])
  const logout = () => { localStorage.removeItem(STORAGE); current.current = null; dispatch(null); setCallOpen(false); setError(null) }
  return <BankContext.Provider value={{ state, error, setError, busy, loading, live, page, navigate, command, create, logout, accept, callOpen, setCallOpen }}>{children}</BankContext.Provider>
}
export const useBank = () => useContext(BankContext)
