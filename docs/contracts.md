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
  "risk_prob_lr": 0.74,
  "situation_hint": "S3",
  "low_digital_response": false,
  "top_factors": ["balance_ratio", "income_variation", "balance_vs_historical"]
}
```

**Estado real de cada campo (para que backend/frontend sepan qué es definitivo):**

| Campo | Estado | Fuente |
|---|---|---|
| `anomaly_score` | **Real** | Isolation Forest entrenado (`research/ba_a_tiempo/outputs/anomaly_benchmark_report.md`) |
| `risk_prob_lr` | **Real** | Logistic Regression entrenada sobre `synthetic_late_payment_next_cycle` (Fase 3: ganó a Random Forest y LightGBM en AUC, calibración, tamaño y latencia — ver `research/ba_a_tiempo/outputs/risk_benchmark_report.md`) |
| `risk_score` / `risk_level` | **Real** | `risk_score = 0.6·risk_prob_lr + 0.4·anomaly_score` (SUPUESTO DE DEMO), cortes 0.35/0.65 |
| `situation_hint` | **Real** | Reglas deterministas sobre features derivadas |
| `low_digital_response` | **Real** | Regla sobre `contact_response_rate` / `app_engagement_ratio` |
| `top_factors` | **Real** | Ablación por feature sobre el Isolation Forest |

`risk_score` ya no es un proxy de `anomaly_score`: combina la señal no supervisada (IF) con la
supervisada (LR) desde la Fase 3.

## 2. channel_and_timing
Salida del motor de canal y momento (`src/ml/channel_timing_engine.py`, Fase 4). Ortogonal al riesgo:
no combina con `risk_score`, solo decide *cómo* y *cuándo* contactar si NBA ya decidió que sí.

```json
{
  "channel_pref_model": "UNDETERMINED",
  "channel_pref_confidence": 0.0121,
  "channel_used": "CALL",
  "channel_source": "FALLBACK_CALL",
  "best_hour_window": "18:00-19:30",
  "best_days_before_due": 5,
  "timing_confidence": 0.3
}
```

| Campo | Estado | Fuente |
|---|---|---|
| `channel_pref_model` / `channel_pref_confidence` | **Real** | Nivel 1 (tasa de respuesta por canal del propio cliente, ≥3 envíos) con fallback a nivel 2 (Logistic Regression poblacional). Ver `research/ba_a_tiempo/outputs/channel_timing_report.md`. |
| `channel_used` | **Real** | SIEMPRE un canal real: si la confianza es < 0.5, cae a `CALL` (regla de producto, no del modelo) — nunca deja a un cliente sin canal. |
| `channel_source` | **Real** | `MODEL_LEVEL1`, `MODEL_LEVEL2` o `FALLBACK_CALL`. |
| `best_hour_window` / `best_days_before_due` / `timing_confidence` | **Real** | Estadístico (histograma de respuesta), no ML — franja poblacional por `income_type` si el cliente no tiene suficientes observaciones propias. |

## 3. next_best_action
Salida del motor determinista de reglas (`src/backend/nba_engine.py`, Fase 5). Combina `risk_result`
(compuertas + `situation_hint`) con `channel_and_timing` (canal/momento reales, ya no fijos).

```json
{
  "intervene": true,
  "channel": "APP_PUSH",
  "channel_source": "MODEL_LEVEL1",
  "time_window": "12:00-13:30",
  "scheduled_for": "2026-09-14T12:00",
  "action": "EMPATHETIC_CONVERSATION",
  "reason": "S3",
  "nba_reason": "Se observa que el saldo actual cubre poco de la cuota; y el ingreso reciente se desvía de su promedio histórico."
}
```

`action` es uno de `NO_CONTACT, SIMPLE_REMINDER, DATE_OPTIONS, EMPATHETIC_CONVERSATION, CHANNEL_SWITCH,
HUMAN_ESCALATION` (v1 §P). Antes de calcular la acción, `nba_engine.py` evalúa compuertas que pueden
bloquear el contacto sin importar el riesgo: `current_cycle_paid`, `opt_out_flag`, contacto reciente
(anti-insistencia, < 3 días), cap de 2 contactos/7 días, y la ventana de intervención (1-10 días antes
del vencimiento). Cuando una compuerta bloquea, `intervene=false` y `reason` indica cuál (p. ej.
`CONTACTED_TOO_RECENTLY`).

## 4. eligible_alternatives
Salida del catálogo de alternativas del *Policy Engine* (`src/backend/policy_engine.py` +
`src/backend/alternatives_catalog.json`, Fase 5). Reemplaza los `O1-O4` genéricos: cada alternativa
elegible ya trae sus parámetros resueltos (fechas y porcentajes concretos, no condiciones abstractas).
El LLM (Fase 6) nunca ve el catálogo completo, solo esta lista ya resuelta.

```json
[
  { "alt_id": "ALT-PARTIAL", "type": "PARTIAL_PAYMENT", "min_percentage": 20, "min_amount": 40.0 },
  { "alt_id": "ALT-AUTOSAVE-PCT", "type": "AUTOSAVE_PCT", "percentage": 0.0222, "assumed_remaining_installments": 12 }
]
```

`assumed_remaining_installments` es un valor fijo (**SUPUESTO DE DEMO**, ver
`ASSUMED_REMAINING_INSTALLMENTS` en `policy_engine.py`): el generador sintético
(`research/ba_a_tiempo/ba_a_tiempo/generator.py`) todavía no produce `remaining_installments` por
cliente (quedó como columna P2/opcional del diseño, nunca implementada).

## 5. score_customer (contrato v2 completo)
Función única que ensambla todo lo anterior (`src/backend/score_customer.py`, Fase 5) — es el
contrato real para frontend/dashboard y para el LLM. No vuelve a calcular nada, solo combina
`risk_result` + `channel_and_timing` + `next_best_action` + `eligible_alternatives`.

```json
{
  "customer_id": "C00104",
  "snapshot_date": "2026-09-12",
  "days_to_due": 7,
  "gates": { "current_cycle_paid": false, "opt_out_flag": false },
  "risk": { "risk_score": 0.78, "risk_level": "HIGH", "anomaly_score": 0.81, "anomaly_flag": true, "risk_prob_lr": 0.74 },
  "situation": { "situation_hint": "S3", "low_digital_response": false, "top_factors": ["balance_ratio", "income_variation"], "flags": [] },
  "profile": { "credit_product": "VEHICLE_LOAN", "digital_capability": "D1", "needs_guided_help": false, "human_support_recommended": false, "complex_case": false, "avoid_more_credit": false },
  "channel": { "channel_pref_model": "WHATSAPP", "channel_pref_confidence": 0.72, "channel_source": "MODEL_LEVEL1", "channel_used": "WHATSAPP" },
  "timing": { "best_hour_window": "12:00-13:30", "best_days_before_due": 5, "timing_confidence": 0.4 },
  "nba": { "should_contact": true, "recommended_action": "EMPATHETIC_CONVERSATION", "scheduled_for": "2026-09-14T12:00", "nba_reason": "...", "block_reason": null },
  "policy_context": { "balance_ratio": 0.4, "income_due_gap": null, "projected_coverage": 0.4, "remaining_installments_assumed": 12, "eligible_alternatives_hint": ["ALT-PARTIAL", "ALT-AUTOSAVE-PCT"] },
  "meta": { "model_version": "if_v1_lr_v1_ch_v1", "scored_at": "2026-09-12T08:00:00+00:00" }
}
```

`channel_pref_model` puede ser `"UNDETERMINED"` (confianza < 0.5); `channel_used` NUNCA lo es —
es el canal real que se va a usar (fallback a `CALL` incluido). Un consumidor del contrato que
necesite saber "a qué canal le escribo" debe leer `channel_used`, no `channel_pref_model`.

Latencia end-to-end medida en `research/ba_a_tiempo/outputs/score_customer_benchmark_report.md`
(p95 ≈ 60 ms sobre clientes reales, tras corregir un cuello de botella real encontrado al perfilar:
la ablación de `top_factors` hacía 11 llamadas individuales al Isolation Forest en vez de una sola
llamada por lotes).

### `profile`: arquetipo de 3 capas (mejora post-Fase 8)
Situación financiera (`situation`, arriba) + producto crediticio + capacidad digital, combinados
-- nunca una sola dimensión aislada (p. ej. "crédito de vehículo + desfase de fecha + capacidad
digital D1"). Ninguno de los dos campos nuevos es feature de IF/LR (ver `FORBIDDEN_FEATURES`
equivalente en `config.py`): son contexto de enrutamiento para NBA/Policy Engine/LLM, no señal de
riesgo o anomalía.

| Campo | Valores | Fuente |
|---|---|---|
| `credit_product` | 10 productos (`PERSONAL_LOAN_PAYROLL_DEDUCTION`, `..._ACCOUNT_DEBIT`, `..._MORTGAGE_BACKED`, `CREDICHEQUE`, `SALARY_ADVANCE`, `OVERDRAFT_ELITE`, `EXTRA_FINANCING`, `HOME_LOAN`, `VEHICLE_LOAN`, `STUDENT_LOAN`) | Generador sintético, sorteo independiente (SUPUESTO DE DEMO) |
| `digital_capability` | `D1` autónomo / `D2` necesita guía / `D3` no sabe usar bien la app | Generador sintético; SUPUESTO DE DEMO explícito: no hay dato de edad/alfabetización real, es un sorteo independiente (D1 65%, D2 25%, D3 10%) |
| `needs_guided_help` | `digital_capability == "D3"` | `nba_engine.py` |
| `complex_case` | `situation_hint == "S3"` y (producto sensible con severidad moderada, umbral bajo a propósito, **o** la regla genérica de escalamiento por baja respuesta digital + severidad alta) | `nba_engine.py` |
| `human_support_recommended` | `complex_case` **o** (`needs_guided_help` y `situation_hint == "S3"`) | `nba_engine.py` |
| `avoid_more_credit` | producto rotativo/liquidez-puente (`CREDICHEQUE`, `OVERDRAFT_ELITE`, `EXTRA_FINANCING`, `SALARY_ADVANCE`) y `situation_hint == "S3"` | `nba_engine.py` |

**Productos sensibles** (`PERSONAL_LOAN_MORTGAGE_BACKED`, `HOME_LOAN`, `VEHICLE_LOAN`): el umbral
de escalamiento a humano es más bajo (`balance_ratio < 0.5` o `failed_payment_attempts_30d >= 1`,
en vez de `< 0.3` / `>= 3`) — un error de negociación automática pesa más en garantía real.

**Productos rotativos** (`CREDICHEQUE`, `OVERDRAFT_ELITE`, `EXTRA_FINANCING`, `SALARY_ADVANCE`):
`ALT-AUTOSAVE-PCT` nunca es elegible en `S3` (no comprometer más ingreso futuro sobre un cliente
que ya usa liquidez-puente), y `ALT-PAYMENT-PLAN` (revisión humana) siempre lo es en su lugar.

**`recommended_action` nuevo**: `GUIDED_APP_HELP` (capacidad digital D3 — guía paso a paso dentro
de la app, con instrucciones explícitas de qué SÍ y qué NO puede hacer la IA inyectadas en el
prompt, ver `conversation_engine.py`). Tiene prioridad sobre `CHANNEL_SWITCH`: no responder por
el canal habitual y no saber usar la app son problemas distintos con soluciones distintas.

Golden customers nuevos: `G13` (D3, `HOME_LOAN`, prueba `GUIDED_APP_HELP`) y `G14`
(`PERSONAL_LOAN_MORTGAGE_BACKED`, severidad moderada, prueba el umbral de escalamiento más bajo
para productos sensibles) — 14 golden customers en total.

## 6. conversation_result
El resultado de la negociación capturado tras la interacción del cliente con el agente
(`src/backend/chat_state_machine.py`, Fase 6). `barrier` usa las categorías cerradas de
`conversation_engine.py` (ya no `TIMING_MISMATCH`, ver §7); `selected_offer` es un `alt_id`
del catálogo de Fase 5, no un `O1-O4` genérico.

```json
{
  "state": "CLOSE",
  "barrier": "LIQUIDITY",
  "tone_overall": "COOPERATIVE",
  "selected_offer": "ALT-PARTIAL",
  "policy_result": "AUTHORIZED",
  "result": "PARTIAL_PAYMENT",
  "confirmed": true,
  "escalation_triggered": false,
  "llm_hallucination_flag": false
}
```

`policy_result = "REJECTED_NOT_ELIGIBLE"` es el caso que prueba que el Policy Engine bloquea
de verdad: si `selected_offer` no está en la lista que `policy_engine.get_eligible_alternatives`
resolvió para ese cliente (LLM alucinando, o un intento adversarial de manipular la llamada),
la máquina de estados NO avanza a `CONFIRM` sin importar qué diga el LLM.

## 7. Capa conversacional (Fase 6): categorías, prompt y guardrail
Todo en `src/backend/conversation_engine.py`.

- **Barrera** (`barrier_detected`, lo que el cliente *dice*, distinto de `situation_hint` que
  es lo que el sistema *infiere*): `FORGOT, DATE_MISMATCH, LIQUIDITY, TECHNICAL, DISPUTE,
  REFUSAL, ALREADY_PAID, OTHER`.
- **Tono** (`tone_overall`, describe la conversación, nunca a la persona — no se guarda en
  `customers_snapshot` ni alimenta el riesgo): `COOPERATIVE, NEUTRAL, TENSE, HOSTILE`.
  `tone_trajectory`: `STABLE, IMPROVING, WORSENING`.
- **Escalamiento automático** (`should_escalate`): tono `HOSTILE`, barrera `DISPUTE`, o barrera
  `OTHER` con confianza baja — la IA no negocia sola en esos casos.
- **Prompt** (`build_system_prompt`): recibe `score_customer` + la lista YA resuelta de
  `policy_engine.get_eligible_alternatives` (montos/fechas concretos, nunca el catálogo
  completo ni sus condiciones). Parámetros recomendados: **`temperature=0`** — es una tarea
  de clasificación cerrada y parafraseo de cifras ya decididas, no de generación creativa;
  mayor temperatura solo aumenta el riesgo de que el modelo "redondee" un monto o invente una
  fecha plausible-pero-no-autorizada.
- **Guardrail anti-alucinación** (`check_hallucination`): escanea la respuesta del LLM buscando
  fechas (`YYYY-MM-DD`), montos (`$123.45`) y porcentajes (`20%`) que no estén en las
  alternativas autorizadas para ese cliente, más una lista de frases-bandera (`sin intereses`,
  `gratis`, `descuento especial`, ...). Alimenta `llm_hallucination_flag`.
- **`call_llm()`** es un mock determinista por palabras clave (no hay proveedor real conectado
  todavía — solo un placeholder en `.env.example`). Reemplazar por una llamada real no debería
  requerir tocar el resto del módulo.
- **Golden conversations** (`research/ba_a_tiempo/data/interactions/golden_conversations.csv`,
  generado por `src/backend/build_golden_conversations.py` a partir del sistema real, no valores
  tipeados a mano): 10 casos, incluyendo un caso adversarial a propósito (`CV-G10`) donde la
  respuesta simulada menciona "sin intereses" y una fecha no autorizada — es el único de los 10
  que debe salir con `llm_hallucination_flag = true`.

## 8. Feedback loop (Fase 7): nba_priority_table
`src/backend/nba_priority.py` agrega `conversations_log` (real cuando exista, hoy sintético —
ver más abajo) por `(situation_hint, barrier_detected, channel, alt_id)`:

```json
{"situation_hint": "S1", "barrier_detected": "FORGOT", "channel": "CALL", "alt_id": "ALT-REMINDER-PAYLINK",
 "n_offered": 105, "n_accepted": 86, "acceptance_rate": 0.819, "n_paid_on_time_after": 71, "success_rate": 0.6729}
```

`success_rate = (n_paid_on_time_after + 1) / (n_offered + 2)` (suavizado bayesiano, prior neutro
0.5) — evita que una combinación con 1 observación domine el orden solo por haber salido bien una
vez. `nba_priority.rank_alternatives()` reordena (nunca filtra) las alternativas que
`policy_engine.get_eligible_alternatives` ya marcó como elegibles, y `score_customer.py` la usa
antes de exponer `eligible_alternatives_hint` — la primera de la lista es la que el LLM debería
presentar primero. `recompute_and_save()` es el "botón recalcular" del dashboard (Fase 8).

**SUPUESTO DE DEMO explícito**: no hay conversaciones reales todavía (Fase 6 sin LLM conectado),
así que `conversations_log.csv` (215 filas) y `interventions_log.csv` (1,800 filas, 88% `NO_CONTACT`
— la métrica "sabe cuándo no molestar") son sintéticos, generados por
`src/backend/build_synthetic_conversations.py` sobre el sistema real (risk_engine + nba_engine +
policy_engine) con una probabilidad de aceptación "verdadera" fija por alternativa. Esto demuestra
el MECANISMO del feedback loop con datos plausibles, no un resultado de negocio real. Ver
`research/ba_a_tiempo/outputs/nba_priority_table_report.md` para la demo de recálculo (antes/después
de sumar evidencia) y el detalle completo.
