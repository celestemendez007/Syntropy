# BA A Tiempo: aplicación integrada

La app está en `src/frontend/src/banking/`; la API HTTP/WebSocket en `src/backend/main.py` y la lógica de sesiones en `app_service.py`.

## Ejecución en Windows

Desde la raíz: `powershell -ExecutionPolicy Bypass -File .\start_local.ps1`.
Compila React y sirve frontend, API y WebSockets en una sola dirección: http://127.0.0.1:8000. El proceso permanece oculto en segundo plano. Los logs y el PID quedan en `.runtime/`. No instala dependencias.

Para desarrollo: ejecutar `python -m uvicorn main:app --app-dir src/backend --host 127.0.0.1 --port 8000` desde la raíz y `npm run dev` desde `src/frontend`. Vite proxifica `/api` y WebSockets al backend. El servidor debe reiniciarse tras cambios Python.

## Flujos y persistencia

- Inicio y Mis Productos consumen el resultado real de Isolation Forest, regresión logística, canal/timing y NBA. Los indicadores técnicos no se muestran al cliente.
- No hay sesión por defecto: la pantalla de Login (`banking/Login.jsx`) pide iniciar una demostración. `POST /api/demo/login` elige un perfil sintético al azar (nombre, documento, correo e ingreso realistas, generados una vez en la tabla `demo_profiles`); "Cliente con varios créditos" restringe la elección a clientes con más de un crédito activo.
- Un cliente puede tener más de un crédito activo (`state.products`, ver GOLD-G15: un vehicular al día y un personal en mora). El selector en Mis Productos (`CreditSwitcher`) cambia cuál crédito está "enfocado" (`state.product`) sin perder los pagos/acuerdos ya hechos sobre el otro.
- Perfil → Explorar la demostración permite cambiar entre nueve casos golden (A1–A9) además del login aleatorio. A5 usa C00252, un cliente sintético rotativo realmente clasificado en S3. A1 respeta NO_CONTACT.
- Las cuentas, cuotas y fechas vienen del backend. Los snapshots históricos se trasladan al día de la demo conservando los días hasta el vencimiento y la extensión autorizada por Policy Engine.
- Revisar opciones → explicar barrera → seleccionar alternativa → revisar resumen → confirmar. La selección no ejecuta la operación.
- Confirmaciones y pagos usan transacciones SQLite, token de oferta y revisión de sesión para impedir repeticiones o confirmaciones desde pantallas desactualizadas. Los comandos del cliente (`BankContext.jsx`) se encolan en orden; dos acciones casi simultáneas nunca se pisan ni se pierden.
- App, chat, WhatsApp simulado y llamada comparten la sesión. WebSockets publican cambios inmediatamente. Reconexión y polling permiten recuperar el estado.
- El historial, los comprobantes y las grabaciones de llamada se conservan en `.runtime/banking.sqlite3` y `.runtime/recordings/`, separado de datos de entrenamiento y de los CSV/JSON existentes.
- La llamada combina reconocimiento de voz en el navegador con transcripción de respaldo en el servidor (`faster-whisper`, local, sin clave) y síntesis de voz neuronal (`edge-tts`, gratuita) en vez de solo la Web Speech API del navegador; si el servidor de voz no responde, la llamada sigue por texto. Cada llamada se graba (`POST /api/sessions/{id}/calls`, subida a `.../calls/{id}/audio`) y queda disponible para reproducir desde el panel de administración. La detección de silencio/habla ocurre en el cliente (`banking/callAudio.js`, cubierto por `tests/test_call_audio.mjs`).
- La comprensión conversacional (`src/backend/dialogue.py`) usa un modelo local vía Ollama (`OLLAMA_URL`/`OLLAMA_MODEL`, por defecto `llama3.1:8b`) solo para interpretar intención y proponer una frase de apertura corta; nunca genera montos, fechas ni confirma operaciones -- eso siempre sale de las plantillas deterministas en `app_service.py`. Si Ollama no está disponible, cae automáticamente a la clasificación local por reglas (`classify()`), sin bloquear la conversación.
- Solicitar llamada registra una solicitud ficticia con identificador. WhatsApp externo utiliza `wa.me` sin destinatario ni información financiera. No envía automáticamente mensajes a terceros.
- Transferencias, recargas, QR y pagos de servicios explican su alcance de simulación; no son integraciones con el core bancario.
- El panel de administración (`/admin.html`) tiene cuatro pestañas: Resumen (KPIs de cartera y distribución de riesgo), Predicciones (tabla completa de los 3000 clientes con probabilidad de atraso, buscable y paginada), Conversaciones y llamadas (transcripciones reales con reproducción de audio) y Modelos (números de los benchmarks ya validados). Todo se sirve desde `GET /api/admin/overview|predictions|conversations` y `admin_service.py`, que corre inferencia real por lotes -- no reentrena ni toca los artefactos de benchmark.

## Pruebas sin alterar investigación

`python -B -m pytest tests/ -q` corre toda la suite del backend (incluye `test_conversation_experience.py`, con los flujos de comprensión/llamada/multi-crédito). `node --test tests/test_call_audio.mjs` cubre la detección de silencio/habla del cliente de llamada.

Las pruebas aíslan SQLite en carpetas temporales y cubren los perfiles golden, bloqueo de ofertas inventadas, revisión/confirmación, débito parcial, concurrencia, persistencia, opt-out, escalamiento, créditos múltiples y sincronización entre dos WebSockets. Las pruebas de `research/ba_a_tiempo/tests/` escriben artefactos (modelos, reportes de benchmark) al correr: no ejecutar esa suite ni `run_all.py` para simplemente abrir esta app.

La app es una demo local, sin autenticación bancaria ni movimientos reales. Un UUID aleatorio identifica cada sesión; no debe publicarse como servicio bancario de producción.
