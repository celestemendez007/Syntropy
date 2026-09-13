import { useState } from 'react'
import { useBank } from './BankContext'
import Icon from './Icon'

export default function Login() {
  const { create, busy, loading, error } = useBank()
  const [multiple, setMultiple] = useState(false)
  return <main className="demo-login"><div className="brand" aria-label="Bancoagrícola"><span/><span/><span/></div>
    <section className="login-card"><span className="round-icon yellow"><Icon name="calendar" size={38}/></span>
      <span className="badge">Tu tranquilidad, primero</span><h1>Bienvenido a<br/>BA A Tiempo</h1>
      <p>Un espacio para encontrar opciones, conversar y cuidar tu próximo pago.</p>
      <div className="login-choice"><label htmlFor="demo-credits">Perfil para esta sesión</label><select id="demo-credits" value={multiple ? 'multiple' : 'any'} onChange={e => setMultiple(e.target.value === 'multiple')}>
        <option value="any">Cliente aleatorio de la base</option><option value="multiple">Cliente con varios créditos</option>
      </select><small>Recibirás un perfil ficticio con sus datos, cuentas y créditos. Cada sesión es independiente.</small></div>
      {error && <p className="inline-error" role="alert">{error}</p>}
      <button className="button primary" disabled={busy || loading} onClick={() => create(null, multiple)}>{busy || loading ? 'Preparando tu espacio…' : 'Iniciar sesión de demostración'}<Icon name="arrow" size={20}/></button>
      <p className="login-foot"><Icon name="lock" size={14}/>Sin credenciales bancarias ni dinero real</p>
    </section><a className="login-admin" href="/admin.html">Panel de administración <Icon name="arrow" size={16}/></a>
  </main>
}
