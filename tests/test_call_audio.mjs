import test from 'node:test'
import assert from 'node:assert/strict'
import { CallAudio, encodeWav } from '../src/frontend/src/banking/callAudio.js'

test('WAV preserves the actual microphone sample rate and mono samples',async()=>{
 const b=encodeWav([new Float32Array([0,.5,-.5])],48000),v=new DataView(await b.arrayBuffer())
 assert.equal(v.getUint32(24,true),48000);assert.equal(v.getUint32(40,true),6);assert.equal(v.getInt16(46,true),16383)
})
test('silence segments two utterances automatically without restarting the microphone',()=>{
 let time=0;const original=globalThis.performance
 Object.defineProperty(globalThis,'performance',{value:{now:()=>time},configurable:true})
 try{
  const a=new CallAudio('test',{});a.callId='test';a.context={sampleRate:16000};const audio=[];a.hear=b=>audio.push(b)
  const speech=new Float32Array(1600).fill(.1),silence=new Float32Array(1600)
  for(let turn=0;turn<2;turn++){for(let i=0;i<6;i++){time+=100;a.frame(speech)}for(let i=0;i<12;i++){time+=100;a.frame(silence)}}
  assert.equal(audio.length,2);assert.equal(a.closed,false)
 }finally{Object.defineProperty(globalThis,'performance',{value:original,configurable:true})}
})
test('sustained user speech interrupts playback but a transient click does not',()=>{
 let time=100;const original=globalThis.performance
 Object.defineProperty(globalThis,'performance',{value:{now:()=>time},configurable:true})
 try{const a=new CallAudio('test',{});a.callId='test';a.context={sampleRate:16000};let stopped=0
  // Barge-in needs sustained speech: short bursts are background noise, and
  // reacting to them used to cut the assistant off mid-sentence.
  a.speaking=true;a.source={stop:()=>stopped++};a.frame(new Float32Array(1600).fill(.1));assert.equal(stopped,0)
  time+=200;a.frame(new Float32Array(1600).fill(.1));assert.equal(stopped,0,'a brief noise must not interrupt')
  time+=400;a.frame(new Float32Array(1600).fill(.1));assert.equal(stopped,1,'sustained speech interrupts')
 }finally{Object.defineProperty(globalThis,'performance',{value:original,configurable:true})}
})
test('muted microphone cannot dispatch audio for transcription',()=>{
 const a=new CallAudio('test',{});a.callId='test';a.muted=true;a.frame(new Float32Array(4096).fill(.8));assert.equal(a.parts.length,0)
})
const withClock=run=>{let time=0;const original=globalThis.performance
 Object.defineProperty(globalThis,'performance',{value:{now:()=>time},configurable:true})
 try{return run(()=>{time+=100})}finally{Object.defineProperty(globalThis,'performance',{value:original,configurable:true})}}
const listening=()=>{const a=new CallAudio('test',{});a.callId='test';a.context={sampleRate:16000}
 const heard=[];a.hear=b=>heard.push(b);return[a,heard]}

test('steady background noise never opens the microphone on its own',()=>{
 withClock(tick=>{const [a,heard]=listening()
  // Loud enough to trip the old fixed threshold, but it is the room, not a voice.
  const room=new Float32Array(1600).fill(.03)
  for(let i=0;i<80;i++){tick();a.frame(room)}
  assert.equal(heard.length,0)
  assert.ok(a.noiseFloor>.02,'the room should have been learned')
 })
})
test('a voice still gets through once the room is noisy',()=>{
 withClock(tick=>{const [a,heard]=listening()
  const room=new Float32Array(1600).fill(.03),voice=new Float32Array(1600).fill(.25),quiet=new Float32Array(1600).fill(.03)
  for(let i=0;i<40;i++){tick();a.frame(room)}
  for(let i=0;i<8;i++){tick();a.frame(voice)}
  for(let i=0;i<12;i++){tick();a.frame(quiet)}
  assert.equal(heard.length,1)
 })
})
test('a knock or a cough is too short to be sent for transcription',()=>{
 withClock(tick=>{const [a,heard]=listening()
  const knock=new Float32Array(1600).fill(.4),silence=new Float32Array(1600)
  for(let i=0;i<4;i++){tick();a.frame(knock)}      // ~300ms, below the 450ms floor
  for(let i=0;i<12;i++){tick();a.frame(silence)}
  assert.equal(heard.length,0)
 })
})

test('a turn that never comes back releases the call instead of freezing it',()=>{
 let time=0;const original=globalThis.performance
 Object.defineProperty(globalThis,'performance',{value:{now:()=>time},configurable:true})
 try{const status=[],errors=[]
  const a=new CallAudio('test',{status:v=>status.push(v),error:e=>errors.push(e)})
  a.wait(true);time+=10000;a.check()
  assert.equal(a.thinking,true,'still within the grace period')
  time+=25000;a.check()
  assert.equal(a.thinking,false);assert.equal(status.at(-1),'listening');assert.equal(errors.length,1)
 }finally{Object.defineProperty(globalThis,'performance',{value:original,configurable:true})}
})
test('a reply interrupted while its audio loads returns to listening',async()=>{
 const status=[],a=new CallAudio('test',{status:v=>status.push(v),caption:()=>{},error:()=>{}})
 a.context={decodeAudioData:async()=>({})}
 const original=globalThis.fetch
 globalThis.fetch=async()=>{a.interrupt();return{ok:true,arrayBuffer:async()=>new ArrayBuffer(8)}}
 try{await a.say({id:'m1',content:'hola'},false)
  assert.equal(a.speaking,false);assert.equal(status.at(-1),'listening')
 }finally{globalThis.fetch=original}
})
test('hanging up finishes even if the recorder never reports that it stopped',async()=>{
 const a=new CallAudio('test',{})
 a.recorder={state:'recording',mimeType:'audio/webm',stop(){/* silently never fires onstop */}}
 await a.end()
 assert.equal(a.closed,true)
})
