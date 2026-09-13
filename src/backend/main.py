"""HTTP and WebSocket transport for the integrated BA A Tiempo demo."""
import asyncio
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from app_service import BankingService, DemoError, SCENARIOS

class SessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: str = Field(default="GOLD-G05", pattern=r"^(GOLD-G\d{2}|C\d{5})$")

class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["message", "select", "confirm", "cancel", "callback", "seen", "snooze", "reminder", "channel", "select_product"]
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
    return {"status": "ok", "mode": "synthetic-demo", "conversation": "groq-with-local-fallback" if os.getenv("GROQ_API_KEY") else "local", "websocket": True}

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
