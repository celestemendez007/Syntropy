# Contratos Técnicos (JSON) — v2

Este documento define las estructuras JSON que actúan como interfaces entre los distintos módulos
del proyecto (Data/ML, Backend/Policy Engine y Frontend).

> **Reemplaza la v1** (que usaba `situation_hint` con nombres semánticos como `LIQUIDITY_PRESSURE`,
> `TIMING_MISMATCH`, `FORGETFULNESS`). Ahora `situation_hint` usa códigos `S0-S3` (situación del
> *ciclo actual*, no un tipo de cliente fijo — ver `research/ba_a_tiempo/BA_A_Tiempo_Diseno_Dataset_v1.md`
> para el razonamiento). La respuesta digital baja (antes `TIMING_MISMATCH`-ish) es ahora un flag
> aparte, `low_digital_response`, porque es ortogonal a la situación financiera: un cliente puede
> estar en S3 y además no responder por su canal habitual.
>
> | Código | Significado |
> |---|---|
> | `S0` | Estable / no intervenir |
> | `S1` | Fricción / olvido (tiene liquidez, paga tarde) |
> | `S2` | Desfase de fecha (el ingreso llega después del vencimiento) |
> | `S3` | Presión de liquidez |
> | *(flag aparte)* | `low_digital_response`: baja respuesta por el canal habitual |

## 1. risk_result
Salida del motor de riesgo (`src/ml/risk_engine.py`).

```json
{
  "customer_id": "C00104",
  "risk_score": 0.78,
  "risk_level": "HIGH",
  "anomaly_score": 0.81,
  "situation_hint": "S3",
  "low_digital_response": false,
  "top_factors": ["balance_ratio", "income_variation", "balance_vs_historical"],
  "_pending": "risk_score es proxy de anomaly_score; falta integrar LR/LightGBM (Fase 3)"
}
```

**Estado real de cada campo (para que backend/frontend sepan qué es definitivo):**

| Campo | Estado | Fuente |
|---|---|---|
| `anomaly_score` | **Real** | Isolation Forest entrenado (`research/ba_a_tiempo/outputs/anomaly_benchmark_report.md`) |
| `situation_hint` | **Real** | Reglas deterministas sobre features derivadas |
| `low_digital_response` | **Real** | Regla sobre `contact_response_rate` / `app_engagement_ratio` |
| `top_factors` | **Real** | Ablación por feature sobre el Isolation Forest |
| `risk_score` / `risk_level` | **Proxy interino** | = `anomaly_score` hasta integrar el benchmark de riesgo supervisado (Fase 3: Logistic Regression vs. Random Forest vs. LightGBM sobre `synthetic_late_payment_next_cycle`) |

El campo `_pending` se incluye a propósito en el JSON real para que nadie consuma `risk_score` como
si fuera el diseño final sin leer esta nota.

## 2. next_best_action
Salida del motor determinista de reglas para la siguiente acción recomendada (`src/backend/nba_engine.py`).
Solo lee `risk_level` y `anomaly_score` de `risk_result`, así que es compatible con el proxy interino
sin cambios.

```json
{
  "intervene": true,
  "channel": "APP_PUSH",
  "time_window": "12:00-13:30",
  "action": "START_ASSISTANCE",
  "reason": "S3_LIQUIDITY_PRESSURE"
}
```

`channel` y `time_window` reales (modelo de preferencia de canal + momento) son diseño de Fase 4,
todavía no implementados; hoy `nba_engine.py` usa reglas fijas por nivel de riesgo.

## 3. allowed_offers
Opciones generadas y permitidas por el *Policy Engine* (`src/backend/policy_engine.py`, sin cambios
en esta actualización — solo lee `risk_level`).

```json
{
  "customer_id": "C00104",
  "offers": [
    { "id": "O1", "type": "PAY_NOW" },
    { "id": "O2", "type": "PROMISE_TO_PAY", "date": "2026-09-20" },
    { "id": "O3", "type": "PARTIAL_PAYMENT", "min_percentage": 20 },
    { "id": "O4", "type": "HUMAN_CALLBACK" }
  ]
}
```

## 4. conversation_result
El resultado de la negociación capturado tras la interacción del cliente con el agente
(`src/backend/chat_state_machine.py`). Sin cambios en esta actualización.

```json
{
  "state": "CLOSE",
  "barrier": "TIMING_MISMATCH",
  "selected_offer": "O2",
  "policy_result": "AUTHORIZED",
  "result": "PROMISE_TO_PAY",
  "confirmed": true
}
```
