"""HTTP and WebSocket transport for the integrated BA A Tiempo demo."""
import asyncio
import os
import io
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from app_service import BankingService, DemoError, SCENARIOS

class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str = Field(default="GOLD-G05", pattern=r"^(GOLD-G\d{2}|C\d{5})$")

class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["message", "select", "confirm", "cancel", "callback", "seen", "snooze", "reminder", "channel", "select_product", "greet"]
    version: int = Field(ge=0)
    text: str | None = Field(default=None, min_length=1, max_length=1500)
    offer_id: str | None = Field(default=None, max_length=80)
    token: str | None = Field(default=None, max_length=80)
    channel: Literal["WHATSAPP", "CALL", "APP_PUSH", "SMS"] | None = None
    product_id: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def required_fields(self):
        field = {"message": "text", "select": "offer_id", "confirm": "token", "channel": "channel",
                  "select_product": "product_id"}.get(self.action)
        if field and not getattr(self, field):
            raise ValueError(f"Falta {field}")
        if self.text is not None:
            self.text = self.text.strip()
            if not self.text:
                raise ValueError("El mensaje está vacío")
        return self

@asynccontextmanager
async def lifespan(app):
    app.state.service = BankingService()
    app.state.peers = defaultdict(set)
    yield

app = FastAPI(title="BA A Tiempo", version="1.0.0", lifespan=lifespan)

@app.exception_handler(DemoError)
async def demo_error(request, exc):
    return JSONResponse(status_code=exc.status, content={"detail": exc.message})

@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "synthetic-demo", "conversation": os.getenv('OLLAMA_MODEL', 'llama3.1:8b'), "websocket": True,
            'voice': os.getenv('BA_VOICE', 'es-SV-LorenaNeural'), 'transcription': 'faster-whisper/' + os.getenv('WHISPER_MODEL', 'base')}

class DemoLogin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    multiple: bool = False

@app.post('/api/demo/login', status_code=201)
def demo_login(request: DemoLogin):
    return app.state.service.random_session(request.multiple)

@app.get('/api/admin/overview')
def admin_overview():
    from admin_service import predictions, benchmarks
    data = predictions()
    conversations = app.state.service.conversations()
    timings = [e['latency_ms'] for c in conversations for e in c['events']
               if e.get('type') == 'MODEL_RESPONSE' and e.get('latency_ms')]
    return {'summary': data['summary'], 'distribution': data['distribution'], 'benchmarks': benchmarks(),
            'activity': {'conversations': len(conversations),
                         'calls': sum(len(c['calls']) for c in conversations),
                         'agreements': sum(e.get('type') == 'AGREEMENT_CONFIRMED' for c in conversations for e in c['events']),
                         'average_response_ms': round(sum(timings) / len(timings)) if timings else None}}

@app.get('/api/admin/predictions')
def admin_predictions(q: str = Query('', max_length=100), offset: int = Query(0, ge=0), limit: int = Query(25, ge=1, le=100)):
    from admin_service import predictions
    rows = [r for r in predictions()['rows'] if q.lower() in (r['customer_id'] + r['name'] + r['product']).lower()]
    return {'total': len(rows), 'rows': rows[offset:offset + limit]}

@app.get('/api/admin/conversations')
def admin_conversations():
    return app.state.service.conversations()

@app.post('/api/sessions/{sid}/calls', status_code=201)
async def start_call(sid: UUID):
    result = await run_in_threadpool(app.state.service.start_call, str(sid))
    await broadcast(str(sid), result['state'])
    return result

async def bounded_body(request, limit):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(413, 'El audio supera el tamaño permitido.')
    return bytes(data)

@app.post('/api/sessions/{sid}/transcribe')
async def transcribe_audio(sid: UUID, request: Request):
    from voice_service import transcribe
    await run_in_threadpool(app.state.service.get, str(sid))
    data = await bounded_body(request, 4 * 1024 * 1024)
    if not data:
        raise HTTPException(400, 'No recibimos audio.')
    try:
        return await run_in_threadpool(transcribe, data)
    except Exception:
        raise HTTPException(503, 'No pudimos transcribir este audio. Puedes continuar hablando o escribir.')

@app.get('/api/sessions/{sid}/speech/{message_id}')
async def speech(sid: UUID, message_id: UUID):
    from voice_service import synthesize
    state = await run_in_threadpool(app.state.service.get, str(sid))
    message = next((m for m in state['messages'] if m['id'] == str(message_id) and m['role'] == 'assistant'), None)
    if not message:
        raise HTTPException(404, 'Mensaje no disponible.')
    try:
        audio = await asyncio.wait_for(synthesize(message['content']), timeout=18)
        return Response(audio, media_type='audio/mpeg', headers={'Cache-Control': 'private, max-age=3600'})
    except Exception:
        raise HTTPException(503, 'La voz natural no está disponible. El texto sigue disponible.')

@app.post('/api/sessions/{sid}/calls/{call_id}/end')
async def end_call(sid: UUID, call_id: UUID):
    state = await run_in_threadpool(app.state.service.finish_call, str(sid), str(call_id))
    await broadcast(str(sid), state)
    return state

@app.put('/api/sessions/{sid}/calls/{call_id}/audio')
async def save_audio(sid: UUID, call_id: UUID, request: Request):
    import av
    with app.state.service.connect() as db:
        if not db.execute('SELECT 1 FROM calls WHERE id=? AND session_id=?', (str(call_id), str(sid))).fetchone():
            raise HTTPException(404, 'Llamada no disponible.')
    data = await bounded_body(request, 40 * 1024 * 1024)
    mime = request.headers.get('content-type', '').split(';')[0]
    extensions = {'audio/webm': 'webm', 'audio/mp4': 'mp4', 'audio/ogg': 'ogg'}
    if mime not in extensions:
        raise HTTPException(415, 'Formato de grabación no compatible.')
    try:
        with av.open(io.BytesIO(data)) as media:
            if not media.streams.audio:
                raise ValueError('Missing audio')
    except Exception:
        raise HTTPException(400, 'La grabación no contiene audio válido.')
    folder = app.state.service.db_path.parent / 'recordings'
    folder.mkdir(exist_ok=True)
    path = folder / f'{call_id}.{extensions[mime]}'
    await run_in_threadpool(path.write_bytes, data)
    state = await run_in_threadpool(app.state.service.finish_call, str(sid), str(call_id), str(path), mime)
    await broadcast(str(sid), state)
    return {'saved': True, 'audio_url': f'/api/sessions/{sid}/calls/{call_id}/audio'}

@app.get('/api/sessions/{sid}/calls/{call_id}/audio')
def call_audio(sid: UUID, call_id: UUID):
    with app.state.service.connect() as db:
        row = db.execute('SELECT recording,mime FROM calls WHERE id=? AND session_id=?', (str(call_id), str(sid))).fetchone()
    if not row or not row[0] or not Path(row[0]).is_file():
        raise HTTPException(404, 'Esta llamada aún no tiene grabación disponible.')
    return FileResponse(row[0], media_type=row[1], headers={'Cache-Control': 'no-store'})

@app.get("/api/scenarios")
def scenarios():
    return [{"id": a, "label": label, "customer_id": cid} for a, label, cid in SCENARIOS]

@app.get("/api/customers")
def customers():
    return [{"customer_id": cid, "scenario": label} for _, label, cid in SCENARIOS]

@app.get("/api/admin/live_calls")
def live_calls():
    return app.state.service.list_live_calls()

@app.post("/api/sessions", status_code=201)
def create_session(request: SessionRequest):
    return app.state.service.create(request.customer_id)

@app.get("/api/sessions/{sid}")
def get_session(sid: UUID):
    return app.state.service.get(str(sid))

async def broadcast(sid, state):
    peers = list(app.state.peers.get(sid, ()))
    async def send(peer):
        try:
            await asyncio.wait_for(peer.send_json({"type": "state", "state": state}), timeout=3)
        except Exception:
            app.state.peers[sid].discard(peer)
    await asyncio.gather(*(send(peer) for peer in peers))

@app.post("/api/sessions/{sid}/commands")
async def command(sid: UUID, request: Command):
    state = await run_in_threadpool(app.state.service.command, str(sid), request.model_dump())
    await broadcast(str(sid), state)
    return state

@app.websocket("/api/sessions/{sid}/live")
async def live(websocket: WebSocket, sid: UUID):
    origin = websocket.headers.get("origin")
    host = websocket.headers.get("host")
    if origin and origin.split("://", 1)[-1] != host:
        await websocket.close(code=1008)
        return
    sid = str(sid)
    try:
        state = await run_in_threadpool(app.state.service.get, sid)
    except DemoError:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    app.state.peers[sid].add(websocket)
    try:
        await websocket.send_json({"type": "state", "state": state})
        while True:
            payload = await websocket.receive_json()
            if payload.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue
            try:
                request = Command.model_validate(payload)
                state = await run_in_threadpool(app.state.service.command, sid, request.model_dump())
                await broadcast(sid, state)
            except DemoError as exc:
                await websocket.send_json({"type": "error", "detail": exc.message})
            except ValueError:
                await websocket.send_json({"type": "error", "detail": "Solicitud inválida."})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        app.state.peers[sid].discard(websocket)
        if not app.state.peers[sid]:
            app.state.peers.pop(sid, None)

dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="app")
