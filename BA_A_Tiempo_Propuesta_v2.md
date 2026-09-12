# BA A Tiempo — Propuesta v2: motor de intervención preventiva con aprendizaje

Módulo: Data + ML + Explicabilidad · Entropy Hack 2026 · Reto Bancoagrícola
Estado: diseño, sin código. Todo dato es sintético. Toda regla financiera está marcada como **SUPUESTO DE DEMO**.
Esta v2 **extiende** la v1 (`BA_A_Tiempo_Diseno_Dataset_v1.md`): el núcleo de datos, features, Isolation Forest, baseline, etiqueta sintética y golden customers se mantiene. Aquí se agrega lo que el objetivo ampliado requiere y se listan los cambios.

---

## 0. Objetivo (versión ampliada)

Motor de intervención preventiva integrado conceptualmente en la Banca Móvil que:

1. detecta señales financieras tempranas antes del vencimiento;
2. determina la **situación** del cliente en este ciclo (no un "tipo de persona");
3. aprende de patrones observados **por qué canal** y **cuándo** intervenir; sin evidencia suficiente, el canal por defecto es llamada;
4. conversa para entender la barrera real;
5. presenta únicamente alternativas autorizadas por el Policy Engine, con demos funcionales (calendario de fechas, ahorro gradual por porcentaje);
6. registra cada conversación con métricas de interacción (barrera, tono, turnos, resultado);
7. expone un dashboard de administración con historial de conversaciones, métricas por conversación, desempeño de los modelos y **retroalimentación** hacia el motor de decisión.

Principio invariante: **la IA conversa; el banco decide.**
Principio nuevo explícito: **el tono de una conversación describe la conversación, no a la persona.** Nunca se convierte en atributo del cliente ni alimenta el score financiero.

---

## 1. Mapa de componentes: qué es modelo, qué es regla, qué es LLM

| # | Pregunta que responde | Componente | Tipo | Datos que necesita | Estado en v1 |
|---|---|---|---|---|---|
| 1 | ¿Se está alejando de su patrón? | Isolation Forest | ML no supervisado | `customers_snapshot` (10 features) | Cubierto |
| 2 | ¿Hay señal de riesgo? (validación de pipeline) | Regresión logística | ML supervisado (etiqueta sintética) | snapshot + etiqueta | Cubierto |
| 3 | ¿En qué situación está este ciclo? | Reglas `situation_hint` | Determinista | features derivadas | Cubierto |
| 4 | ¿Por qué canal? | **Modelo de preferencia de canal** | ML supervisado ligero + fallback | `contacts_log` | **Nuevo** |
| 5 | ¿Cuándo? (hora y días antes del vencimiento) | **Modelo de momento** | Estadístico por cliente + poblacional | `contacts_log`, actividad app | **Nuevo** |
| 6 | ¿Intervenir? ¿Con qué acción inicial? | Next Best Action | Reglas + **tabla de prioridades aprendida** | outputs 1–5 + `outcomes` | Ampliado |
| 7 | ¿Cuál es la barrera real? | LLM con categorías cerradas | LLM (sin entrenar) | conversación | **Nuevo (definido)** |
| 8 | ¿Qué alternativas se pueden ofrecer? | Policy Engine | Determinista | `alternatives_catalog`, situación, contexto | Ampliado |
| 9 | ¿Cómo fue la conversación? | Métricas de conversación (tono, turnos, resultado) | LLM como anotador + reglas | `conversations_log` | **Nuevo** |
| 10 | ¿Qué funciona mejor? | Feedback loop | Agregación tabular → tabla de prioridades NBA | `conversations_log` + `interventions_log` | **Nuevo** |
| 11 | ¿Cómo van los modelos? | Panel de desempeño | Métricas de validación | outputs + golden | **Nuevo** |

**Eliminado:** K-Means. Con datos generados por perfiles, "descubriría" los perfiles del generador (circular). Se sustituye por el modelo de canal (#4), que sí tiene una pregunta concreta.

---

## 2. Cambios respecto a v1

| Cambio | Detalle |
|---|---|
| Nueva tabla `conversations_log` | Una fila por conversación; fuente del dashboard y del feedback loop. §4 |
| Nueva tabla `interventions_log` | Una fila por intervención decidida por NBA (haya o no conversación). §4 |
| Nueva tabla `alternatives_catalog` | Catálogo de alternativas del Policy Engine con condiciones de elegibilidad (SUPUESTO DE DEMO). §6 |
| Nueva tabla `accounts_mock` | Cuentas ficticias del cliente para la demo de ahorro gradual. §7 |
| `contacts_log` ampliado | Se agregan `days_before_due_at_contact`, `hour_sent`, `responded_within_hours`. §3 |
| Nuevas columnas en `customers_snapshot` | `channel_pref_model`, `channel_pref_confidence`, `best_days_before_due`, `best_hour_window`, `nomina_en_banco_mock`, `external_debt_ratio_mock`. §3 |
| Categorías cerradas de barrera y tono | §5 |
| Tabla de prioridades NBA | §8 |
| Contrato `score_customer` v2 | §10 |
| Golden **conversations** (además de golden customers) | §9 |
| K-Means | Eliminado |

Sin cambios: features de IF y LR, etiqueta `synthetic_late_payment_next_cycle`, variables prohibidas, golden customers G01–G12, casos extremos.

---

## 3. Datos nuevos en tablas existentes

### 3.1 `contacts_log` (una fila por contacto enviado)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|
| `contact_id` | ID de contacto | string | `CT-000481` | único | UI | — | P0 | secuencial | Llave. |
| `customer_id` | Cliente | string | `C104` | | UI | — | P0 | | FK. |
| `cycle_id` | Ciclo | string | `2026-07` | | RAW | — | P0 | | Contexto. |
| `channel` | Canal | categorical | `WHATSAPP` | APP_PUSH, SMS, WHATSAPP, CALL | RAW | canal | P0 | Categorical por perfil | Variable de decisión. |
| `sent_at` | Enviado | datetime | `2026-07-19 12:10` | | RAW | momento | P0 | Hora ~ N(hora_perfil, 3) | Base de `hour_sent`. |
| `hour_sent` | Hora de envío | int | `12` | 0–23 | DER | momento | P0 | de `sent_at` | Patrón horario. |
| `days_before_due_at_contact` | Días antes del vencimiento | int | `6` | −5…15 | DER | momento | P0 | `due_date − sent_at` | Patrón "cuántos días antes responde mejor". |
| `responded` | Respondió | boolean | `true` | | RAW | canal, momento | P0 | Bernoulli(p_canal × p_hora × p_días) | Target de los modelos 4 y 5. |
| `responded_within_hours` | Horas hasta la respuesta | float | `1.5` | ≥ 0; null | RAW | momento (P1) | P1 | Exponencial | Mide "le hace caso rápido". |
| `outcome` | Resultado | categorical | `ANSWERED` | ANSWERED, IGNORED, REJECTED, BOUNCED | RAW | — | P0 | Categorical | BOUNCED = canal no disponible. |
| `intervention_id` | Intervención asociada | string | `IV-000120`; null | | UI | — | P1 | | Enlace a `interventions_log`. |

Generación del target `responded` (SUPUESTO DE DEMO): cada cliente tiene un vector oculto de afinidad por canal `a_c ~ Dirichlet(1,1,1,1)` con un canal dominante, una hora preferida `h* ~ U(7,21)` y un óptimo de anticipación `d* ~ U(2,8)`. `p = sigmoid(−1 + 2·a_canal − 0.15·|hour − h*| − 0.2·|days − d*|)`. Los tres parámetros ocultos van a `generator_state`, nunca al snapshot. Un 30 % de clientes tiene afinidad plana (sin canal claro) → el modelo debe decir "sin evidencia" y el fallback es CALL.

### 3.2 `customers_snapshot` (columnas añadidas)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|
| `nomina_en_banco_mock` | Nómina depositada en el banco | boolean | `true` | | RAW | regla S2 | P1 | Bernoulli(0.6) | Si `true`, `income_expected_day` es dato duro (no inferido) → `income_date_unknown = 0` siempre. SUPUESTO DE DEMO. |
| `external_debt_ratio_mock` | Deuda externa / ingreso (buró ficticio) | float | `0.35` | 0–3 | RAW | LR (P1) | P1 | Beta(2,5)×1.5; S3: Beta(4,3)×2 | Refuerza S3 con la señal más usada en riesgo real. Marcado como ficticio. |
| `channel_pref_model` | Canal preferido (modelo) | categorical | `WHATSAPP` | APP_PUSH, SMS, WHATSAPP, CALL, UNDETERMINED | OUT | — | P0 | modelo #4 | Salida del modelo de canal. |
| `channel_pref_confidence` | Confianza | float | `0.72` | 0–1 | OUT | — | P0 | modelo #4 | < 0.5 → UNDETERMINED → CALL. |
| `best_hour_window` | Mejor franja horaria | string | `12:00-13:30`; null | | OUT | — | P0 | modelo #5 | Reemplaza `preferred_time_window` de v1. |
| `best_days_before_due` | Mejor anticipación (días) | int | `5`; null | 1–10 | OUT | — | P0 | modelo #5 | Cuándo disparar el nudge. |
| `timing_confidence` | Confianza del momento | float | `0.4` | 0–1 | OUT | — | P1 | modelo #5 | Baja → usar valores poblacionales. |

---

## 4. Tablas nuevas

### 4.1 `interventions_log` (una fila por decisión de NBA)

| Variable | Nombre ES | Tipo | Ejemplo | Rango / valores | MVP | Por qué |
|---|---|---|---|---|---|---|
| `intervention_id` | ID | string | `IV-000120` | único | P0 | Llave. |
| `customer_id`, `cycle_id`, `scoring_run_id` | | string | | | P0 | Trazabilidad al score que la originó. |
| `decided_at` | Fecha de decisión | datetime | | | P0 | |
| `situation_hint_at_decision` | Situación | categorical | `S3` | S0–S3 | P0 | Snapshot de la situación en ese momento. |
| `low_digital_response_at_decision` | | boolean | | | P0 | |
| `risk_level_at_decision` | | categorical | `HIGH` | | P0 | |
| `decision` | Decisión | categorical | `INTERVENE` | NO_CONTACT, INTERVENE, WAIT, HUMAN_ESCALATION | P0 | NO_CONTACT también se registra: es la métrica "sabe cuándo no molestar". |
| `channel_used` | Canal | categorical | `WHATSAPP` | + NONE | P0 | |
| `channel_source` | Origen del canal | categorical | `MODEL` | MODEL, FALLBACK_CALL, RULE_SWITCH | P0 | Para medir cuánto aporta el modelo vs. el fallback. |
| `scheduled_for` | Programado para | datetime | | | P0 | Hora y día decididos. |
| `initial_action` | Acción inicial | categorical | `EMPATHETIC_CONVERSATION` | ver v1 §P | P0 | |
| `conversation_id` | Conversación | string; null | | | P0 | null si no hubo respuesta. |
| `final_outcome` | Resultado final | categorical | `ACCEPTED` | NO_RESPONSE, ACCEPTED, REJECTED, PAID_WITHOUT_ALT, ESCALATED, OPT_OUT | P0 | Target del feedback loop. |
| `paid_on_time_after` | Pagó a tiempo después | boolean; null | | | P0 | El resultado que realmente importa. Sintético en demo. |
| `days_late_after` | Días de retraso después | int; null | 0–60 | P1 | |

### 4.2 `conversations_log` (una fila por conversación)

| Variable | Nombre ES | Tipo | Ejemplo | Rango / valores | MVP | Por qué |
|---|---|---|---|---|---|---|
| `conversation_id` | ID | string | `CV-000077` | único | P0 | Llave. |
| `intervention_id`, `customer_id` | | string | | | P0 | |
| `channel` | Canal | categorical | `WHATSAPP` | | P0 | |
| `started_at`, `ended_at` | | datetime | | | P0 | Duración. |
| `turns_total` | Turnos totales | int | `6` | 1–40 | P0 | Eficiencia. |
| `turn_of_resolution` | Turno de resolución | int; null | `4` | | P1 | Cuánto costó llegar. |
| `barrier_detected` | Barrera detectada por el LLM | categorical | `LIQUIDITY` | ver §5.1 | P0 | El "por qué" real. |
| `barrier_confidence` | Confianza | float | `0.85` | 0–1 | P1 | |
| `barrier_vs_situation_match` | ¿Coincide con `situation_hint`? | boolean | `true` | | P0 | Métrica clave: ¿el modelo adivinó bien la situación antes de hablar? |
| `tone_overall` | Tono de la conversación | categorical | `TENSE` | ver §5.2 | P0 | Describe la conversación, no al cliente. |
| `tone_trajectory` | Trayectoria del tono | categorical | `TENSE_TO_COOPERATIVE` | ver §5.2 | P1 | ¿La conversación mejoró o empeoró? |
| `escalation_triggered` | Escalamiento | boolean | `false` | | P0 | Regla: tono HOSTILE o barrera OTHER con confianza < 0.5 o petición explícita. |
| `alternatives_offered` | Alternativas ofrecidas | string (lista de `alt_id`) | `ALT-DATE-SHIFT;ALT-PARTIAL` | | P0 | Del Policy Engine. |
| `alternative_accepted` | Alternativa aceptada | string; null | `ALT-DATE-SHIFT` | | P0 | Target del feedback. |
| `policy_decision_id` | Decisión de política | string | | | P0 | Auditoría: qué autorizó el banco. |
| `llm_hallucination_flag` | Alerta de contenido no autorizado | boolean | `false` | | P0 | Verificación automática: si el LLM mencionó una fecha/monto fuera del `policy_decision_id`. Métrica de seguridad para el jurado. |
| `customer_feedback_mock` | Valoración del cliente (👍/👎) | int; null | `1` | −1, 0, 1 | P1 | Demo de "¿te sirvió?". |
| `transcript_mock` | Transcripción ficticia | string | | | P1 | Para el historial del admin. Generada por plantilla. |
| `summary_llm` | Resumen | string | | | P1 | 1–2 líneas para el dashboard. |

**Prohibido en esta tabla**: cualquier etiqueta sobre la persona (estado emocional del cliente, rasgos, "nivel de estrés"). El campo es `tone_*` de la conversación.
**Prohibido como feature de IF/LR**: todo `conversations_log`. Solo alimenta NBA vía §8.

### 4.3 `accounts_mock` (cuentas ficticias para la demo de ahorro)

| Variable | Tipo | Ejemplo | MVP | Por qué |
|---|---|---|---|---|
| `account_id_mock` | string | `ACC-DEMO-000104-S` | P1 | Llave. |
| `customer_id` | string | | P1 | |
| `account_type` | categorical: CHECKING, SAVINGS | `SAVINGS` | P1 | De cuál se propone apartar. |
| `balance` | float | `210.00` | P1 | |
| `is_payroll_account` | boolean | | P1 | Coherente con `nomina_en_banco_mock`. |
| `savings_rule_active` | boolean | `false` | P1 | Si ya tiene una regla de ahorro BA A Tiempo activa. |
| `savings_rule_pct` | float; null | `0.05` | P1 | Porcentaje configurado. |

---

## 5. Categorías cerradas para el LLM

### 5.1 Barrera (`barrier_detected`)

| Código | Significado | Situación que suele corresponder | Ejemplo de frase |
|---|---|---|---|
| `FORGOT` | Olvido / no tenía presente la fecha | S1 | "no me acordaba" |
| `DATE_MISMATCH` | El ingreso llega después | S2 | "me pagan hasta el 30" |
| `LIQUIDITY` | No alcanza el dinero este mes | S3 | "este mes no puedo completar" |
| `TECHNICAL` | Intentó pagar y falló | S3 (intentos fallidos) / soporte | "la app no me deja" |
| `DISPUTE` | No reconoce el cargo / desacuerdo | escalar | "eso no es lo que me cobraron" |
| `REFUSAL` | No quiere ser contactado | opt-out | "no me escriban" |
| `ALREADY_PAID` | Dice que ya pagó | verificar | "ya pagué ayer" |
| `OTHER` | No clasificable | escalar si confianza baja | |

Es intencional que las barreras no sean idénticas a S0–S4: la situación es lo que el sistema *infiere* de datos; la barrera es lo que el cliente *dice*. La comparación entre ambas (`barrier_vs_situation_match`) es una de las métricas más valiosas del dashboard.

### 5.2 Tono de la conversación (`tone_overall`, `tone_trajectory`)

`tone_overall ∈ {COOPERATIVE, NEUTRAL, TENSE, HOSTILE}`
`tone_trajectory ∈ {STABLE, IMPROVING, WORSENING}` (P1: forma `X_TO_Y`)

Reglas de uso:
- Lo anota el LLM al cierre de la conversación, sobre el texto de la conversación completa.
- HOSTILE → escalamiento a humano y fin de negociación automática.
- Se agrega por canal, situación y alternativa en el dashboard.
- **No** se guarda en `customers_snapshot`, **no** entra al score, **no** condiciona el trato del siguiente ciclo. Sí puede condicionar el *canal* del siguiente ciclo solo si el cliente lo pidió (REFUSAL de un canal → registrar preferencia negativa).

---

## 6. Catálogo de alternativas (`alternatives_catalog`) — todo SUPUESTO DE DEMO

| `alt_id` | Alternativa | Situaciones elegibles | Condiciones de elegibilidad (Policy Engine) | Demo asociada |
|---|---|---|---|---|
| `ALT-REMINDER-PAYLINK` | Recordatorio + enlace de pago directo | S1 | `balance_ratio ≥ 1` | Botón "pagar ahora" en la app |
| `ALT-DATE-SHIFT` | Mover la fecha de pago dentro de un rango | S2 | `income_due_gap ∈ [1,10]`, `remaining_installments ≥ 3`, no usado en últimos 3 ciclos | **Calendario** con fechas permitidas resaltadas |
| `ALT-GRACE-DAYS` | Días de gracia sin recargo | S1, S2 | `payment_punctuality ≥ 0.6`, máx. 1 vez por 6 ciclos | Calendario |
| `ALT-PARTIAL` | Pago parcial + saldo diferido | S3 | `balance_ratio ∈ [0.3, 1)`, `partial_payments_n ≤ 2` | Slider de monto (mínimo autorizado) |
| `ALT-AUTOSAVE-PCT` | Ahorro gradual: apartar % de ingresos hacia la cuota | S1, S2, S3 leve | `income_hist_avg − expenses_hist_avg > 0` | **Ahorro por porcentaje**: propone `pct = min(0.15, cuota / (ingreso_hist × meses_restantes))`, muestra proyección |
| `ALT-PAYMENT-PLAN` | Reestructuración (solo humano) | S3 severo | `balance_ratio < 0.3` o `income_variation < −0.4` | Escalamiento |
| `ALT-CHANNEL-SUPPORT` | Derivar a soporte técnico | TECHNICAL | `failed_payment_attempts_30d ≥ 2` y `balance_ratio ≥ 1` | Ticket |
| `ALT-NONE` | No ofrecer nada | S0 / REFUSAL | | |

El LLM recibe la lista de `alt_id` elegibles con sus parámetros ya resueltos (fechas concretas, porcentaje concreto, monto mínimo concreto). Nunca recibe la tabla completa ni las condiciones: si no está en la lista, no existe.

---

## 7. Modelos nuevos

### 7.1 Modelo de preferencia de canal (#4)

- **Pregunta**: dado el cliente, ¿qué canal maximiza la probabilidad de respuesta?
- **Datos**: `contacts_log` (target `responded`).
- **Nivel 1 — por cliente**: tasa de respuesta por canal con ≥ 3 envíos en 180 d. Si el mejor canal supera al segundo por ≥ 0.2 y tiene ≥ 3 envíos → `channel_pref_model` = ese canal, `confidence` = tasa.
- **Nivel 2 — poblacional (el "modelo" propiamente)**: regresión logística o árbol pequeño con features `channel` (one-hot), `app_engagement_ratio`, `push_enabled`, `income_type`, `tenure_months`, `hour_sent`, `days_before_due_at_contact` → `P(responded)`. Para un cliente con poco historial, se evalúa cada canal y se toma el argmax; `confidence` = P(mejor) − P(segundo).
- **Fallback**: `confidence < 0.5` → `UNDETERMINED` → canal CALL (regla de producto explícita).
- **Regla de exploración** (SUPUESTO DE DEMO): 10 % de las intervenciones usan el segundo mejor canal, para que el log siga aprendiendo. En demo, mostrar el porcentaje en el dashboard.
- **Por qué no K-Means**: la pregunta tiene target; un clasificador es directo y explicable.

### 7.2 Modelo de momento (#5)

- **Hora**: histograma de respuesta por franja de 90 min combinando `contacts_log.responded` y actividad en app. Franja con mayor tasa y ≥ 5 observaciones → `best_hour_window`; si no, franja poblacional por `income_type` (SUPUESTO DE DEMO: asalariado 12:00–13:30; independiente 18:00–19:30).
- **Anticipación**: tasa de respuesta por `days_before_due_at_contact` agrupado en {1–2, 3–5, 6–8, 9+}. Mejor bucket con ≥ 3 observaciones → `best_days_before_due` (centro del bucket); si no, 5 días (poblacional).
- `timing_confidence` = número de observaciones del cliente / 10, clip 1.

Ambos son modelos estadísticos simples y explicables ("le escribimos a las 12 porque 4 de 5 veces respondió a esa hora"). Es más honesto que un modelo grande sobre logs sintéticos.

---

## 8. Feedback loop: tabla de prioridades del NBA

El "aprendizaje" del MVP es tabular y auditable:

`nba_priority_table`: por cada combinación (`situation_hint`, `barrier_detected`, `channel`, `alt_id`) →
`n_offered`, `n_accepted`, `acceptance_rate`, `n_paid_on_time_after`, `success_rate`, `avg_turns`, `pct_tense_or_hostile`.

Uso por el NBA: entre las alternativas **elegibles** (Policy Engine manda), ordenar por `success_rate` con suavizado bayesiano `(n_paid + 1)/(n_offered + 2)` para que combinaciones con poca evidencia no dominen. El LLM presenta primero la de mayor prioridad.

Ciclo: conversación → `conversations_log` + `interventions_log` → recálculo nocturno de `nba_priority_table` → siguiente intervención. En demo: botón "recalcular" en el dashboard que muestra cómo cambia el orden.

Lo que **no** se retroalimenta: el score financiero (IF/LR). Solo el orden de alternativas y el canal/momento. Esto evita que el sistema aprenda "los clientes tensos son riesgosos".

---

## 9. Golden conversations (además de los golden customers de v1)

| ID | Cliente | Canal | Barrera | Tono | Alternativas ofrecidas | Aceptada | Resultado | Qué demuestra |
|---|---|---|---|---|---|---|---|---|
| CV-G01 | G03 (S1) | APP_PUSH | FORGOT | COOPERATIVE | PAYLINK | PAYLINK | PAID, 2 turnos | Fricción mínima. |
| CV-G02 | G05 (S2) | WHATSAPP | DATE_MISMATCH | NEUTRAL | DATE-SHIFT (calendario 28/30) | DATE-SHIFT 30 | ACCEPTED, paid on time | Demo calendario; `barrier_vs_situation_match = true`. |
| CV-G03 | G07 (S3) | WHATSAPP | LIQUIDITY | TENSE → COOPERATIVE | PARTIAL, AUTOSAVE-PCT | PARTIAL | ACCEPTED | Empatía + trayectoria de tono. |
| CV-G04 | G08 (S3) | APP_PUSH | TECHNICAL | NEUTRAL | CHANNEL-SUPPORT | — | ESCALATED soporte | Situación inferida S3, barrera real técnica: el sistema corrige. |
| CV-G05 | G09 (S4) | CALL 17:30 | DATE_MISMATCH | COOPERATIVE | DATE-SHIFT | DATE-SHIFT | ACCEPTED | Fallback/cambio de canal funciona. |
| CV-G06 | G11 (S3+S4) | CALL | LIQUIDITY | HOSTILE | (ninguna) | — | ESCALATED humano | Regla de escalamiento por tono. |
| CV-G07 | G04 (S1) | SMS | ALREADY_PAID | NEUTRAL | — | — | PAID_WITHOUT_ALT | Verificación antes de insistir. |
| CV-G08 | G06 (S2 fecha desconocida) | WHATSAPP | DATE_MISMATCH | NEUTRAL | LLM pregunta fecha → DATE-SHIFT | DATE-SHIFT | ACCEPTED | `income_date_unknown` → preguntar, no asumir. |
| CV-G09 | G10 | WHATSAPP | REFUSAL | TENSE | — | — | OPT_OUT | Respeto al rechazo; `opt_out_flag = 1`. |
| CV-G10 | G07 | WHATSAPP | LIQUIDITY | NEUTRAL | PARTIAL | — | `llm_hallucination_flag = true` (mencionó "sin intereses") | Métrica de seguridad: el guardrail detecta contenido no autorizado. Caso adversarial. |

Además, para que el dashboard tenga volumen: 150–200 conversaciones sintéticas generadas por plantilla con proporciones realistas (SUPUESTO DE DEMO: 55 % COOPERATIVE, 30 % NEUTRAL, 12 % TENSE, 3 % HOSTILE; aceptación ~60 %).

---

## 10. Contrato `score_customer` v2 (JSON)

```json
{
  "customer_id": "C104",
  "snapshot_date": "2026-09-12",
  "days_to_due": 7,
  "gates": { "current_cycle_paid": false, "opt_out_flag": false, "contacts_last_7d": 0 },
  "risk": { "risk_score": 0.78, "risk_level": "HIGH", "anomaly_score": 0.81, "anomaly_flag": true, "risk_prob_lr": 0.74 },
  "situation": { "situation_hint": "S3", "low_digital_response": false, "top_factors": ["balance_ratio_low", "income_variation_neg"], "flags": ["income_date_unknown"] },
  "channel": { "channel_pref_model": "WHATSAPP", "channel_pref_confidence": 0.72, "channel_source": "MODEL" },
  "timing": { "best_hour_window": "12:00-13:30", "best_days_before_due": 5, "timing_confidence": 0.4 },
  "nba": { "should_contact": true, "recommended_action": "EMPATHETIC_CONVERSATION", "scheduled_for": "2026-09-14T12:00", "nba_reason": "Saldo cubre 40% de la cuota e ingreso 35% por debajo de su promedio" },
  "policy_context": { "balance_ratio": 0.4, "income_due_gap": null, "projected_coverage": 0.4, "remaining_installments": 18, "eligible_alternatives_hint": ["ALT-PARTIAL", "ALT-AUTOSAVE-PCT"] },
  "meta": { "model_version": "if_v1_lr_v1_ch_v1", "scored_at": "2026-09-12T08:00:00" }
}
```

`eligible_alternatives_hint` es solo una sugerencia: la elegibilidad final la resuelve el Policy Engine en backend con `alternatives_catalog`.

---

## 11. Dashboard de administración (contrato para Camila)

**Vista 1 — Cartera**: distribución de `situation_hint`; % `NO_CONTACT` ("sabe cuándo no molestar"); `risk_level` por situación; lista de clientes con score, situación, canal y momento programado.

**Vista 2 — Conversaciones**: historial (`conversations_log` + `transcript_mock` + `summary_llm`); filtros por canal, barrera, tono, resultado; detalle de una conversación con alternativas ofrecidas vs. aceptada y `policy_decision_id`.

**Vista 3 — Métricas de interacción**: tasa de aceptación por (situación × canal × alternativa); tono por canal; `turns_total` promedio; `barrier_vs_situation_match` (precisión de la inferencia antes de hablar); `escalation_triggered` %; `llm_hallucination_flag` % (idealmente 0 en demo, con el caso adversarial CV-G10 visible).

**Vista 4 — Modelos**: IF: distribución de `anomaly_score`, golden asserts pasados/fallados; LR: AUC y calibración **rotulados como validación sintética**; canal: `channel_source` MODEL vs FALLBACK_CALL, tasa de respuesta por canal; momento: tasa de respuesta por franja y por anticipación; `nba_priority_table` con botón "recalcular".

**Vista 5 — Aprendizaje**: cómo cambió el orden de alternativas tras las últimas N conversaciones; % de exploración de canal.

---

## 12. Estructura de carpetas (delta sobre v1)

```
data/raw_synthetic/        + contacts_log.csv (ampliado), accounts_mock.csv
data/interactions/         + interventions_log.csv, conversations_log.csv, golden_conversations.csv
config/                    + alternatives_catalog.yaml, barrier_categories.yaml
models/                    + channel_pref_v1.joblib, timing_stats_v1.json
outputs/                   + nba_priority_table.csv, conversation_metrics.csv
```

---

## 13. Priorización y orden de construcción

**P0 (sin esto no hay demo):** todo el P0 de v1 · `contacts_log` ampliado · `interventions_log` · `conversations_log` (campos P0) · categorías de barrera y tono · `alternatives_catalog` · modelo de canal nivel 1 + fallback CALL · momento poblacional · `nba_priority_table` · contrato JSON v2 · 10 golden conversations · Vistas 1–3 del dashboard.

**P1:** modelo de canal nivel 2 (poblacional) · momento por cliente · `accounts_mock` + demo de ahorro · `nomina_en_banco_mock`, `external_debt_ratio_mock` · `tone_trajectory`, `turn_of_resolution` · Vista 4 · regla de exploración.

**P2:** `responded_within_hours` · `customer_feedback_mock` · Vista 5 · `days_late_after`.

Orden sugerido: (1) generador de snapshot + IF + LR (v1) → (2) `contacts_log` ampliado + canal nivel 1 + momento poblacional → (3) catálogo + conversaciones sintéticas + golden conversations → (4) `nba_priority_table` → (5) contrato JSON v2 → (6) dashboard.

---

## 14. SUPUESTOS DE DEMO añadidos en v2
Canal por defecto CALL cuando `confidence < 0.5` · 10 % de exploración de canal · franjas poblacionales por tipo de ingreso · anticipación poblacional de 5 días · condiciones de elegibilidad del catálogo · porcentaje de ahorro `min(0.15, cuota/(ingreso × meses))` · proporciones de tono y aceptación del generador de conversaciones · suavizado bayesiano `(n+1)/(N+2)` en la tabla de prioridades · escalamiento por tono HOSTILE.
