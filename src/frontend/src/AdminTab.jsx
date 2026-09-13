import { useState, useEffect } from 'react'

export default function AdminTab() {
  const [archetypes, setArchetypes] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saveStatus, setSaveStatus] = useState(null)

  useEffect(() => {
    fetch('http://localhost:8000/api/archetypes')
      .then(r => r.json())
      .then(data => {
        setArchetypes(data)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  const handleSave = () => {
    setSaveStatus('Guardando...')
    fetch('http://localhost:8000/api/archetypes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(archetypes)
    })
      .then(r => r.json())
      .then(() => {
        setSaveStatus('¡Guardado exitosamente!')
        setTimeout(() => setSaveStatus(null), 3000)
      })
      .catch(err => {
        setSaveStatus(`Error al guardar: ${err.message}`)
      })
  }

  const handleChange = (index, field, value) => {
    const newArchetypes = [...archetypes]
    // split by newline for arrays
    newArchetypes[index][field] = value.split('\n')
    setArchetypes(newArchetypes)
  }
  
  const handleTextChange = (index, field, value) => {
    const newArchetypes = [...archetypes]
    newArchetypes[index][field] = value
    setArchetypes(newArchetypes)
  }

  if (loading) return <div className="dashboard"><p>Cargando configuración...</p></div>
  if (error) return <div className="dashboard"><p className="error">Error: {error}</p></div>

  return (
    <div className="dashboard admin-dashboard">
      <header className="dashboard-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>Configuración de Arquetipos (Admin)</h1>
          <p className="subtitle">Edita las instrucciones y permisos de la IA en tiempo real.</p>
        </div>
        <button 
          onClick={handleSave} 
          style={{ padding: '10px 20px', background: '#3b82f6', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer', fontWeight: 'bold' }}>
          Guardar Cambios
        </button>
      </header>
      
      {saveStatus && <div style={{ padding: '10px', background: saveStatus.includes('Error') ? '#fee2e2' : '#dcfce7', color: saveStatus.includes('Error') ? '#dc2626' : '#16a34a', borderRadius: '4px', marginBottom: '20px' }}>{saveStatus}</div>}

      <div className="card-grid" style={{ gridTemplateColumns: '1fr' }}>
        {archetypes.map((arch, index) => (
          <div key={arch.id} className="card" style={{ marginBottom: '20px' }}>
            <h3 style={{ borderBottom: '1px solid #334155', paddingBottom: '10px', color: '#818cf8' }}>{arch.id}: {arch.name}</h3>
            
            <div style={{ marginTop: '15px' }}>
              <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '5px', color: '#94a3b8' }}>Descripción (Perfil)</label>
              <textarea 
                style={{ width: '100%', padding: '10px', background: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '4px', minHeight: '60px' }}
                value={arch.description}
                onChange={(e) => handleTextChange(index, 'description', e.target.value)}
              />
            </div>

            <div style={{ marginTop: '15px' }}>
              <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '5px', color: '#94a3b8' }}>Qué puede hacer la IA (1 por línea)</label>
              <textarea 
                style={{ width: '100%', padding: '10px', background: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '4px', minHeight: '100px' }}
                value={arch.ai_can_do.join('\n')}
                onChange={(e) => handleChange(index, 'ai_can_do', e.target.value)}
              />
            </div>

            <div style={{ marginTop: '15px' }}>
              <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '5px', color: '#94a3b8' }}>Recomendaciones útiles / Alternativas (1 por línea)</label>
              <textarea 
                style={{ width: '100%', padding: '10px', background: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '4px', minHeight: '100px' }}
                value={arch.useful_alternatives.join('\n')}
                onChange={(e) => handleChange(index, 'useful_alternatives', e.target.value)}
              />
            </div>

            <div style={{ marginTop: '15px' }}>
              <label style={{ display: 'block', fontWeight: 'bold', marginBottom: '5px', color: '#94a3b8' }}>Reglas de Escalamiento / Cuándo detenerse (1 por línea)</label>
              <textarea 
                style={{ width: '100%', padding: '10px', background: '#1e293b', color: 'white', border: '1px solid #334155', borderRadius: '4px', minHeight: '100px' }}
                value={arch.escalation_rules.join('\n')}
                onChange={(e) => handleChange(index, 'escalation_rules', e.target.value)}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
