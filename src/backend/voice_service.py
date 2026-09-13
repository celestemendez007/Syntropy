"""Neural speech and local transcription; call media is private runtime data."""
import io
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_model = None
_lock = threading.Lock()


def transcribe(data):
    global _model
    from faster_whisper import WhisperModel
    started = time.perf_counter()
    with _lock:
        if _model is None:
            _model = WhisperModel(os.getenv('WHISPER_MODEL', 'base'), device='cpu', compute_type='int8',
                                  cpu_threads=4, download_root=str(ROOT / '.runtime' / 'whisper'))
        segments, _ = _model.transcribe(io.BytesIO(data), language='es', beam_size=3,
                                       vad_filter=True, condition_on_previous_text=False)
        text = ' '.join(s.text.strip() for s in segments if s.no_speech_prob < .6).strip()
    return {'text': text, 'latency_ms': round((time.perf_counter() - started) * 1000)}


async def synthesize(text):
    import edge_tts
    voice = os.getenv('BA_VOICE', 'es-SV-LorenaNeural')
    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, voice, rate='+3%').stream():
        if chunk['type'] == 'audio':
            audio.extend(chunk['data'])
    if not audio:
        raise RuntimeError('No llegó audio del servicio de voz.')
    return bytes(audio)
