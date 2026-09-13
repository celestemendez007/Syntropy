import { useEffect, useRef, useState } from 'react'
import { useBank } from './BankContext'
import { CallAudio } from './callAudio'
import Icon from './Icon'

export function useVoice(onText) {
  const [listening,setListening]=useState(false),[voiceError,setVoiceError]=useState('')
  const ref=useRef(null),callback=useRef(onText);callback.current=onText
  const stop=()=>{ref.current?.abort();setListening(false)}
  const start=()=>{
    const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition
    if(!Recognition){setVoiceError('Para conversar por voz sin pulsar el micrófono, usa el botón de llamada.');return}
    stop();const r=new Recognition();ref.current=r;r.lang='es-SV'
    r.onstart=()=>setListening(true);r.onend=()=>setListening(false);r.onresult=e=>callback.current(e.results[0][0].transcript)
    r.onerror=e=>{if(!['aborted','no-speech'].includes(e.error))setVoiceError('No pudimos escuchar. Puedes escribir o iniciar una llamada.')}
    setVoiceError('');r.start()
  }
  useEffect(()=>()=>ref.current?.abort(),[])
  return {start,stop,listening,voiceError}
}
const labels={connecting:'Conectando tu llamada…',speaking:'Tu asistente está hablando',listening:'Te escucho, habla con confianza',thinking:'Estoy revisando lo que me cuentas…',muted:'Micrófono silenciado',ended:'Llamada finalizada'}
export default function VoiceCall(){
  const {state,command,callOpen,setCallOpen,busy,navigate,accept}=useBank()
  const [status,setStatus]=useState('connecting'),[seconds,setSeconds]=useState(0),[text,setText]=useState(''),[caption,setCaption]=useState(''),[error,setError]=useState('')
  const [muted,setMuted]=useState(false),[saving,setSaving]=useState(false),[audioUrl,setAudioUrl]=useState(null)
  const engine=useRef(null),latest=useRef(null),ending=useRef(false)
  latest.current={command,accept,state}
  const ended=status==='ended'
  async function end(close=false){
    if(ending.current)return
    ending.current=true;setStatus('ended');setSaving(true)
    try{const url=await engine.current?.end();setAudioUrl(url);if(close)setCallOpen(false)}
    catch(e){setError('La llamada terminó, pero la grabación no se guardó: '+e.message)}
    finally{setSaving(false);ending.current=false}
  }
  useEffect(()=>{
    if(!callOpen)return
    let disposed=false
    setError('');setAudioUrl(null);setStatus('connecting');setSeconds(0);setMuted(false)
    latest.current.command('clear_chat')
    const instance=new CallAudio(latest.current.state.id,{
      status:v=>!disposed&&setStatus(v),caption:v=>!disposed&&setCaption(v),error:v=>!disposed&&setError(v),
      accept:s=>!disposed&&latest.current.accept(s,false),message:t=>latest.current.command('message',{text:t}),finish:()=>!disposed&&end(),
    })
    engine.current=instance
    instance.start().catch(async e=>{if(!disposed){setError(e.name==='NotAllowedError'?'Permite el micrófono para conversar. También puedes continuar por texto.':e.message);setStatus('ended')}await instance.end().catch(()=>{})})
    const timer=setInterval(()=>{if(!instance.closed)setSeconds(s=>s+1)},1000)
    return()=>{disposed=true;clearInterval(timer);if(!instance.closed)instance.end().catch(()=>{})}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[callOpen])
  useEffect(()=>{
    const instance=engine.current
    if(callOpen&&instance?.callId&&!instance.closed)instance.say(state.messages.filter(m=>m.role==='assistant').at(-1),state.call_end)
  },[state.version,callOpen,state.messages,state.call_end])
  if(!callOpen)return null
  const submit=async e=>{e.preventDefault();if(!text.trim())return;engine.current?.interrupt();const value=text;setText('');await command('message',{text:value})}
  return <section className="voice-call" aria-label="Llamada con BA A Tiempo">
    <div className="call-top"><span className={'round-icon yellow '+(status==='speaking'?'speaking':'')}><Icon name="headset" size={30}/></span><div><strong>BA A Tiempo</strong><span>{labels[status]} · {Math.floor(seconds/60).toString().padStart(2,'0')}:{(seconds%60).toString().padStart(2,'0')}</span></div><button className="icon-button" disabled={saving} aria-label="Cerrar llamada" onClick={()=>end(true)}><Icon name="close"/></button></div>
    <div className="voice-wave" aria-hidden="true">{Array.from({length:15},(_,i)=><i key={i} style={{height:[12,22,36,19,29][i%5],animationDelay:i*.08+'s',animationPlayState:['speaking','listening'].includes(status)?'running':'paused'}}/>)}</div>
    <p className="recording-status">{saving?'Guardando tu grabación…':ended?(audioUrl?'Grabación y conversación guardadas':'Conversación guardada'):'● Grabando · Puedes hablar sin tocar el micrófono e interrumpirme'}</p>
    <p className="call-caption" aria-live="polite">{caption}</p>
    {error&&<p className="voice-note" role="alert">{error}</p>}
    {state.pending_offer&&!ended&&<div className="call-offer"><strong>{state.pending_offer.title}</strong><p>El resumen está en tu pantalla. Puedes decir «confirmo» o «no acepto».</p></div>}
    {!ended?<><div className="call-actions"><button className="button secondary" onClick={()=>navigate(state.receipt?'receipt':'productos')}><Icon name="card"/>Ver mi producto</button><button className={'icon-button mic-toggle '+(muted?'muted':'active')} aria-label={muted?'Reactivar micrófono':'Silenciar micrófono'} aria-pressed={muted} onClick={()=>setMuted(engine.current.toggleMute())}><Icon name="mic"/></button><button className="icon-button hangup" aria-label="Colgar llamada" onClick={()=>end()}><Icon name="call"/></button></div>
      <form className="call-text" onSubmit={submit}><input aria-label="Respuesta por texto durante la llamada" value={text} onChange={e=>setText(e.target.value)} maxLength={1500} placeholder="También puedes responder por texto"/><button aria-label="Enviar respuesta a la llamada" disabled={busy||!text.trim()}><Icon name="send" size={20}/></button></form></>:<>
      {audioUrl&&<audio className="call-audio" controls src={audioUrl}/>}
      {!audioUrl&&engine.current?.blob&&!saving&&<button className="button secondary" onClick={async()=>{setSaving(true);try{setAudioUrl(await engine.current.save());setError('')}catch(e){setError(e.message)}finally{setSaving(false)}}}>Reintentar guardar grabación</button>}
      <button className="button primary" disabled={saving} onClick={()=>setCallOpen(false)}>Continuar en la app</button></>}
  </section>
}
