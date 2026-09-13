# BA A Tiempo: aplicación integrada

La app está en `src/frontend/src/banking/`; la API HTTP/WebSocket en `src/backend/main.py` y la lógica de sesiones en `app_service.py`.

## Ejecución en Windows

Desde la raíz: `powershell -ExecutionPolicy Bypass -File .\start_local.ps1`.
Compila React y sirve frontend, API y WebSockets en una sola dirección: http://127.0.0.1:8000. El proceso permanece oculto en segundo plano. Los logs y el PID quedan en `.runtime/`. No instala dependencias.

Para desarrollo: ejecutar `python -m uvicorn main:app --app-dir src/backend --host 127.0.0.1 --port 8000` desde la raíz y `npm run dev` desde `src/frontend`. Vite proxifica `/api` y WebSockets al backend. El servidor debe reiniciarse tras cambios Python.

## Flujos y persistencia

- Inicio y Mis Productos consumen el resultado real de Isolation Forest, regresión logística, canal/timing y NBA. Los indicadores técnicos no se muestran al cliente.
- Perfil → Explorar la demostración permite cambiar entre ocho casos. A5 usa C00252, un cliente sintético rotativo realmente clasificado en S3. A1 respeta NO_CONTACT.
- Las cuentas, cuotas y fechas vienen del backend. Los snapshots históricos se trasladan al día de la demo conservando los días hasta el vencimiento y la extensión autorizada por Policy Engine.
- Revisar opciones → explicar barrera → seleccionar alternativa → revisar resumen → confirmar. La selección no ejecuta la operación.
- Confirmaciones y pagos usan transacciones SQLite, token de oferta y revisión de sesión para impedir repeticiones o confirmaciones desde pantallas desactualizadas.
- App, chat, WhatsApp simulado y llamada comparten la sesión. WebSockets publican cambios inmediatamente. Reconexión y polling permiten recuperar el estado.
- El historial y los comprobantes se conservan en `.runtime/banking.sqlite3`, separado de datos de entrenamiento y de los CSV/JSON existentes.
- La llamada usa Web Speech API. Requiere un navegador compatible y permiso de micrófono. Ofrece texto si el reconocimiento no está disponible. Se despide y finaliza después de que el usuario confirma que ve el cambio.
- Sin clave externa, un motor conversacional local maneja barreras, negativa, confirmación, guía, desvíos y escalamiento. Con `GROQ_API_KEY`, Groq clasifica lenguaje adicional con categorías cerradas y fallback local. Nunca se usa texto financiero libre del LLM para ejecutar acuerdos.
- Solicitar llamada registra una solicitud ficticia con identificador. WhatsApp externo utiliza `wa.me` sin destinatario ni información financiera. No envía automáticamente mensajes a terceros.
- Transferencias, recargas, QR y pagos de servicios explican su alcance de simulación; no son integraciones con el core bancario.

## Pruebas sin alterar investigación

`python -B -m pytest tests/test_banking_app.py tests/test_score_customer.py tests/test_risk_engine.py tests/test_policy_engine.py tests/test_nba_engine.py tests/test_nba_priority.py tests/test_channel_timing_engine.py tests/test_conversation_engine.py tests/test_chat_state_machine.py -q`

Las nuevas pruebas aíslan SQLite en carpetas temporales y cubren ocho perfiles, bloqueo de ofertas inventadas, revisión/confirmación, débito parcial, concurrencia, persistencia, opt-out, escalamiento y sincronización entre dos WebSockets. Las pruebas históricas de exportación/generación escriben artefactos: no ejecutar `run_all.py` para simplemente abrir esta app.

La app es una demo local, sin autenticación bancaria ni movimientos reales. Un UUID aleatorio identifica cada sesión; no debe publicarse como servicio bancario de producción.
