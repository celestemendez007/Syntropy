// Continuous microphone, silence detection, interruption and mixed call recording.
export function encodeWav(parts, sampleRate) {
  const length=parts.reduce((n,p)=>n+p.length,0), buffer=new ArrayBuffer(44+length*2), v=new DataView(buffer)
  const write=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i))}
  write(0,'RIFF');v.setUint32(4,36+length*2,true);write(8,'WAVE');write(12,'fmt ');v.setUint32(16,16,true)
  v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,sampleRate,true);v.setUint32(28,sampleRate*2,true)
  v.setUint16(32,2,true);v.setUint16(34,16,true);write(36,'data');v.setUint32(40,length*2,true)
  let at=44
  for(const p of parts)for(const s of p){v.setInt16(at,Math.max(-1,Math.min(1,s))*32767,true);at+=2}
  return new Blob([buffer],{type:'audio/wav'})
}
// Every call request is bounded: a stalled fetch used to leave the microphone
// disabled for the rest of the call, which is what made calls look frozen.
async function checked(url,options={},timeout=25000){
  const abort=new AbortController(),timer=setTimeout(()=>abort.abort(),timeout)
  let r
  try{r=await fetch(url,{...options,signal:abort.signal})}
  catch(e){throw new Error(e.name==='AbortError'?'Eso tardó más de lo normal. Puedes intentarlo otra vez.':'No pudimos conectar. Intenta nuevamente.')}
  finally{clearTimeout(timer)}
  if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.detail||'No pudimos conectar. Intenta nuevamente.')}
  return r
}
const bounded=(promise,ms)=>Promise.race([promise,new Promise(resolve=>setTimeout(resolve,ms))])

export class CallAudio {
  constructor(sid,cb){Object.assign(this,{sid,cb,parts:[],recorded:[],preRoll:[],spoken:new Set(),closed:false,muted:false,thinking:false,speaking:false,generation:0,thinkingSince:0,noiseFloor:.012,voiced:0,done:false})}
  wait(on){this.thinking=on;this.thinkingSince=on?performance.now():0}
  // Last line of defence: whatever goes wrong, the call goes back to listening
  // instead of sitting on "Estoy revisando lo que me cuentas…" forever.
  check(){
    if(this.closed||!this.thinking||performance.now()-this.thinkingSince<30000)return
    this.wait(false);this.cb.error('Eso tardó demasiado. Ya puedes seguir hablando.')
    if(!this.speaking)this.cb.status(this.muted?'muted':'listening')
  }
  idle(){if(!this.closed&&!this.speaking&&!this.thinking)this.cb.status(this.muted?'muted':'listening')}
  async start(){
    this.cb.status('connecting');this.context=new AudioContext();await this.context.resume()
    const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true,channelCount:1}})
    if(this.closed){stream.getTracks().forEach(t=>t.stop());return}
    this.stream=stream;this.destination=this.context.createMediaStreamDestination();this.input=this.context.createMediaStreamSource(stream)
    this.input.connect(this.destination)
    this.processor=this.context.createScriptProcessor(4096,1,1);this.input.connect(this.processor);this.processor.connect(this.context.destination)
    this.processor.onaudioprocess=e=>this.frame(e.inputBuffer.getChannelData(0))
    const mime=['audio/webm;codecs=opus','audio/mp4','audio/ogg;codecs=opus'].find(t=>MediaRecorder.isTypeSupported(t))
    if(!mime)throw new Error('Este navegador no permite grabar llamadas. Usa Chrome o Edge, o continúa por chat.')
    this.recorder=new MediaRecorder(this.destination.stream,{mimeType:mime,audioBitsPerSecond:48000})
    this.recorder.ondataavailable=e=>{if(e.data.size)this.recorded.push(e.data)};this.recorder.start(1000)
    this.watchdog=setInterval(()=>this.check(),1000)
    const result=await(await checked(`/api/sessions/${this.sid}/calls`,{method:'POST'},15000)).json();this.callId=result.call_id
    if(this.closed){await this.end();return}
    this.cb.accept(result.state);this.cb.status('listening');await this.say(result.state.messages.at(-1),false)
  }
  frame(input){
    if(this.closed||this.done||this.muted||this.thinking||!this.callId)return
    const frame=new Float32Array(input),rms=Math.sqrt(frame.reduce((n,s)=>n+s*s,0)/frame.length),time=performance.now()
    this.preRoll.push(frame);if(this.preRoll.length>3)this.preRoll.shift()
    // The room sets the bar, not a fixed number. A fixed threshold opens the
    // microphone on its own wherever there is traffic, a fan or a television,
    // and the browser's automatic gain lifts that noise further during pauses.
    const gate=Math.max(this.speaking?.05:.022,this.noiseFloor*(this.speaking?6:3.2))
    const loud=rms>gate
    if(loud){
      this.voiced++
      if(!this.voicedAt)this.voicedAt=time
      if(this.speaking&&time-this.voicedAt>450)this.interrupt()
    }else{
      this.voiced=0;this.voicedAt=null
      // Learn the room only from quiet frames, and never mid-sentence.
      if(!this.parts.length)this.noiseFloor=this.noiseFloor*.97+rms*.03
    }
    // One loud frame is a door or a keystroke; speech sustains across frames.
    if(loud&&this.voiced>=3){
      if(!this.parts.length){this.parts=[...this.preRoll];this.began=this.voicedAt}else this.parts.push(frame)
      this.lastSound=time
    }else if(this.parts.length)this.parts.push(frame)
    if(this.parts.length&&(time-this.lastSound>750||time-this.began>22000)){
      const parts=this.parts;this.parts=[];this.preRoll=[]
      // Too brief to be a sentence. Sending a cough or a knock to the
      // transcriber is what makes it answer things nobody said.
      if(this.lastSound-this.began>450)this.hear(encodeWav(parts,this.context.sampleRate))
    }
  }
  async hear(audio){
    this.wait(true);this.interrupt();this.cb.status('thinking')
    try{const result=await(await checked(`/api/sessions/${this.sid}/transcribe`,{method:'POST',headers:{'Content-Type':'audio/wav'},body:audio})).json()
      // The reply itself is bounded too: a slow model must not hold the mic.
      if(!this.closed&&result.text.trim()){this.cb.caption(result.text);await bounded(this.cb.message(result.text),30000)}
    }catch(e){if(!this.closed)this.cb.error(e.message)}finally{this.wait(false);this.idle()}
  }
  interrupt(){this.generation++;if(this.source){this.source.onended=null;try{this.source.stop()}catch{/* stopped */}this.source=null}this.speaking=false}
  async say(message,closeAfter){
    if(this.closed||!message||this.spoken.has(message.id))return
    this.interrupt();const generation=this.generation
    this.cb.caption(message.content);this.cb.status('thinking')
    let playing=false
    try{const r=await checked(`/api/sessions/${this.sid}/speech/${message.id}`),audio=await this.context.decodeAudioData(await r.arrayBuffer())
      if(this.closed||generation!==this.generation)return
      this.spoken.add(message.id)
      this.source=this.context.createBufferSource();this.source.buffer=audio;this.source.connect(this.context.destination);this.source.connect(this.destination)
      this.speaking=true;playing=true;this.cb.status('speaking')
      // After a farewell the line stays open: the customer hangs up, not the app.
      this.source.onended=()=>{this.speaking=false;this.source=null;this.parts=[];this.preRoll=[];if(!this.closed){if(closeAfter){this.done=true;this.cb.finish()}else this.idle()}}
      await this.context.resume();this.source.start()
    }catch(e){
      // The reply is already on screen: losing the voice must not end the call,
      // and the turn must not be retried forever against a failing synthesizer.
      this.spoken.add(message.id)
      if(!this.closed){this.cb.error('No pudimos reproducir la voz esta vez. Puedes seguir leyendo y hablando.');if(closeAfter){this.done=true;this.cb.finish()}}
    }finally{if(!playing)this.idle()}
  }
  toggleMute(){this.muted=!this.muted;this.parts=[];this.preRoll=[];this.stream?.getAudioTracks().forEach(t=>{t.enabled=!this.muted});if(!this.speaking)this.cb.status(this.muted?'muted':'listening');return this.muted}
  async end(){
    if(this.ending)return this.ending
    this.ending=(async()=>{
      this.closed=true;clearInterval(this.watchdog);this.interrupt()
      this.processor?.disconnect();this.input?.disconnect();this.stream?.getTracks().forEach(t=>t.stop())
      if(this.recorder&&this.recorder.state!=='inactive'){
        // A recorder that never fires onstop used to hang hanging up entirely.
        await new Promise(resolve=>{const done=()=>resolve();this.recorder.onstop=done;setTimeout(done,4000);try{this.recorder.stop()}catch{done()}})
        this.blob=new Blob(this.recorded,{type:this.recorder.mimeType})
      }
      if(this.context&&this.context.state!=='closed')await this.context.close().catch(()=>{})
      if(!this.callId)return
      // Closing the call server-side is best effort; the recording still matters.
      await checked(`/api/sessions/${this.sid}/calls/${this.callId}/end`,{method:'POST'},15000).catch(()=>{})
      return this.save()
    })()
    return this.ending
  }
  async save(){if(!this.blob?.size||!this.callId)return;const r=await checked(`/api/sessions/${this.sid}/calls/${this.callId}/audio`,{method:'PUT',headers:{'Content-Type':this.blob.type},body:this.blob},60000);return(await r.json()).audio_url}
}
