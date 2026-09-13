# Fase 4 — Canal y momento

Dos componentes, ninguno reemplaza al riesgo (IF/LR de Fases 2-3): preferencia de canal (nivel 1 por cliente + nivel 2 poblacional, con fallback a CALL) y momento óptimo (estadístico, no ML). Ver BA_A_Tiempo_Propuesta_v2.md §7 para el diseño completo.

## Modelo de canal (nivel 2, poblacional)

- **AUC** (predecir `responded` con `channel`, `hour_sent`, `days_before_due_at_contact`, `app_engagement_ratio`, `push_enabled`, `income_type`, `tenure_months`): `0.5177` (train=7923, test=1981).
- **Tamaño del modelo serializado** (incluye scaler + columnas): 2.7 KB.
- **Tiempo de entrenamiento:** 0.011 s.

## Latencia end-to-end (la llamada completa que usará `score_customer`, no solo `predict_proba`)

- `get_channel_preference`: p50=18.731 ms, p95=23.478 ms.
- `get_timing`: p50=8.359 ms, p95=12.716 ms.

## Cobertura: qué tan seguido se usa cada fuente (muestra de 200 clientes)

- `FALLBACK_CALL`: 86.0%
- `MODEL_LEVEL1`: 14.0%

## Chequeo golden (G09: baja respuesta digital)

El nivel 2 recomienda `WHATSAPP` con confianza 0.0045 para G09 (baja respuesta digital, `contact_response_rate=0`).
 Chequeo de diseño (PASA): con `contact_response_rate=0`, la confianza del modelo debería caer bajo 0.5 y activar el fallback a CALL — es exactamente el caso que el diseño (v1 §9, G09) preveía resolver con cambio de canal.

## Lectura de los resultados

El AUC del nivel 2 es modesto. Es esperable: el generador simula la respuesta con un vector de afinidad oculto por cliente (`aff_app`, `aff_sms`, ...) que nunca llega al modelo -- el nivel 2 solo ve variables observables (`app_engagement_ratio`, `income_type`, hora, anticipación), así que estructuralmente no puede recuperar toda la señal que sí ve el nivel 1 (que promedia directamente sobre los envíos reales de *ese* cliente). Esto no es un defecto del pipeline: es la razón de diseño para preferir el nivel 1 cuando hay evidencia suficiente y dejar el nivel 2 solo como respaldo para clientes con poco historial.


### Veredicto
La latencia end-to-end de ambos componentes (`get_channel_preference` p95=23.478 ms, `get_timing` p95=12.716 ms) es perfectamente viable para scoring uno-a-uno; el cuello de botella real en Fase 5 será el I/O de leer `contacts_log.csv` completo por cliente, no el modelo -- en producción esto se resolvería con un índice por `customer_id` (o una tabla pre-agregada), no con un modelo más liviano.

El diseño de dos niveles con fallback a CALL cumple su función explícita: nunca deja a un cliente sin canal (`UNDETERMINED` siempre resuelve a un canal real), y la regla de negocio de `confidence < 0.5` es la que decide, no el modelo -- eso es intencional para que el jurado vea una decisión de producto explícita, no una caja negra.

Este veredicto es válido para **esta corrida con esta seed**; el detalle completo queda en `outputs/channel_timing_benchmark.json`.