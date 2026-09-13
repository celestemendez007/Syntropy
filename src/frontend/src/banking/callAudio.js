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
async function checked(url,options){const r=await fetch(url,options);if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.detail||'No pudimos conectar. Intenta nuevamente.')}return r}

export class CallAudio {
  constructor(sid,cb){Object.assign(this,{sid,cb,parts:[],recorded:[],preRoll:[],closed:false,muted:false,thinking:false,speaking:false,generation:0})}
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
    const result=await(await checked(`/api/sessions/${this.sid}/calls`,{method:'POST'})).json();this.callId=result.call_id
    if(this.closed){await this.end();return}
    this.cb.accept(result.state);this.cb.status('listening');await this.say(result.state.messages.at(-1),false)
  }
  frame(input){
    if(this.closed||this.muted||this.thinking||!this.callId)return
    const frame=new Float32Array(input),rms=Math.sqrt(frame.reduce((n,s)=>n+s*s,0)/frame.length),time=performance.now()
    this.preRoll.push(frame);if(this.preRoll.length>3)this.preRoll.shift()
    if(rms>(this.speaking?.045:.014)){
      if(!this.voicedAt)this.voicedAt=time
      if(this.speaking&&time-this.voicedAt>170)this.interrupt()
      this.lastSound=time
      if(!this.parts.length){this.parts=[...this.preRoll];this.began=time}else this.parts.push(frame)
    }else{this.voicedAt=null;if(this.parts.length)this.parts.push(frame)}
    if(this.parts.length&&(time-this.lastSound>850||time-this.began>22000)){
      const parts=this.parts;this.parts=[];this.preRoll=[]
      if(this.lastSound-this.began>170)this.hear(encodeWav(parts,this.context.sampleRate))
    }
  }
  async hear(audio){
    this.thinking=true;this.interrupt();this.cb.status('thinking')
    try{const result=await(await checked(`/api/sessions/${this.sid}/transcribe`,{method:'POST',headers:{'Content-Type':'audio/wav'},body:audio})).json()
      if(!this.closed&&result.text.trim()){this.cb.caption(result.text);await this.cb.message(result.text)}
    }catch(e){if(!this.closed)this.cb.error(e.message)}finally{this.thinking=false;if(!this.closed&&!this.speaking)this.cb.status(this.muted?'muted':'listening')}
  }
  interrupt(){this.generation++;if(this.source){this.source.onended=null;try{this.source.stop()}catch{/* stopped */}this.source=null}this.speaking=false}
  async say(message,closeAfter){
    if(this.closed||!message||this.lastMessage===message.id)return
    this.lastMessage=message.id;this.interrupt();const generation=this.generation
    this.cb.caption(message.content);this.cb.status('thinking')
    try{const r=await checked(`/api/sessions/${this.sid}/speech/${message.id}`),audio=await this.context.decodeAudioData(await r.arrayBuffer())
      if(this.closed||generation!==this.generation)return
      this.source=this.context.createBufferSource();this.source.buffer=audio;this.source.connect(this.context.destination);this.source.connect(this.destination)
      this.speaking=true;this.cb.status('speaking')
      this.source.onended=()=>{this.speaking=false;this.source=null;this.parts=[];this.preRoll=[];if(!this.closed){if(closeAfter)this.cb.finish();else this.cb.status(this.muted?'muted':'listening')}}
      await this.context.resume();this.source.start()
    }catch(e){if(!this.closed){this.cb.error(e.message+' Tu micrófono sigue disponible.');this.cb.status('listening')}}
  }
  toggleMute(){this.muted=!this.muted;this.parts=[];this.preRoll=[];this.stream?.getAudioTracks().forEach(t=>{t.enabled=!this.muted});if(!this.speaking)this.cb.status(this.muted?'muted':'listening');return this.muted}
  async end(){
    this.closed=true;this.interrupt();this.processor?.disconnect();this.input?.disconnect();this.stream?.getTracks().forEach(t=>t.stop())
    if(this.recorder&&this.recorder.state!=='inactive'){await new Promise(resolve=>{this.recorder.onstop=resolve;this.recorder.stop()});this.blob=new Blob(this.recorded,{type:this.recorder.mimeType})}
    if(this.context&&this.context.state!=='closed')await this.context.close()
    if(!this.callId)return
    await checked(`/api/sessions/${this.sid}/calls/${this.callId}/end`,{method:'POST'});return this.save()
  }
  async save(){if(!this.blob?.size||!this.callId)return;const r=await checked(`/api/sessions/${this.sid}/calls/${this.callId}/audio`,{method:'PUT',headers:{'Content-Type':this.blob.type},body:this.blob});return(await r.json()).audio_url}
}
