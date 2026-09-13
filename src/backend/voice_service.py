"""Neural speech and local transcription; call media is private runtime data."""
import io
import os
import re
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_model = None
_lock = threading.Lock()
# Primes the transcriber for short conversational Spanish. Whisper also tends to
# echo this text back when it is handed noise, so heard() below drops that echo.
PROMPT = 'Bueno, dime. Sí, claro. Asistencia de Bancoagrícola.'
_PROMPT_WORDS = set(re.findall(r'\w+', PROMPT.lower()))


def heard(segments):
    """What the customer actually said, or nothing.

    Noise that slips through still reaches the transcriber, and a transcriber
    given noise does not stay quiet: it invents a plausible phrase, often the
    priming text itself. Answering those is what makes the assistant look like
    it is listening to the whole room.
    """
    kept = [s.text.strip() for s in segments
            if s.no_speech_prob < .6 and getattr(s, 'avg_logprob', 0) > -1.0]
    text = ' '.join(kept).strip()
    words = re.findall(r'\w+', text.lower())
    if not words:
        return ''
    return '' if set(words) <= _PROMPT_WORDS else text


def transcribe(data):
    global _model
    from faster_whisper import WhisperModel
    started = time.perf_counter()
    with _lock:
        if _model is None:
            _model = WhisperModel(os.getenv('WHISPER_MODEL', 'base'), device='cpu', compute_type='int8',
                                  cpu_threads=4, download_root=str(ROOT / '.runtime' / 'whisper'))
        segments, _ = _model.transcribe(io.BytesIO(data), language='es', beam_size=3,
                                       vad_filter=True, condition_on_previous_text=False,
                                       initial_prompt=PROMPT)
        text = heard(segments)
    return {'text': text, 'latency_ms': round((time.perf_counter() - started) * 1000)}


def _money(match):
    units, cents = match.group(1).replace(',', ''), match.group(2)
    spoken = f'{units} dólares' if units != '1' else 'un dólar'
    return spoken if not cents or int(cents) == 0 else f'{spoken} con {int(cents)} centavos'


def speakable(text):
    """Símbolos y espacios en blanco leídos como los diría una persona.

    edge-tts deletrea '$44.00' y hace una pausa larga en cada salto de línea:
    eso es lo que suena robótico. El texto mostrado en pantalla no cambia,
    solo lo que se envía a la voz, y los números siguen siendo los mismos.
    """
    text = re.sub(r'\$\s*(\d[\d,]*)(?:\.(\d{2}))?', _money, text)
    text = re.sub(r'(\d+(?:[.,]\d+)?)\s*%', r'\1 por ciento', text)
    text = re.sub(r'N\.?°\s*', 'número ', text)
    return re.sub(r'\s+', ' ', text).strip()


async def synthesize(text):
    import edge_tts
    voice = os.getenv('BA_VOICE', 'es-SV-LorenaNeural')
    audio = bytearray()
    async for chunk in edge_tts.Communicate(speakable(text), voice, rate=os.getenv('BA_VOICE_RATE', '+15%')).stream():
        if chunk['type'] == 'audio':
            audio.extend(chunk['data'])
    if not audio:
        raise RuntimeError('No llegó audio del servicio de voz.')
    return bytes(audio)
