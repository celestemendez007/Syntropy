# BA A Tiempo — Diseño del dataset sintético y feature engineering (v1)

Módulo: Data + ML + Explicabilidad · Entropy Hack 2026 · Reto Bancoagrícola
Estado: diseño, sin código. Todo dato es sintético. Toda regla financiera está marcada como **SUPUESTO DE DEMO**.

---

## 0. Correcciones conceptuales previas

| # | Lo que dice la guía | Problema | Corrección adoptada |
|---|---|---|---|
| 1 | IF detecta "alejamiento del patrón propio" | Un IF sobre una tabla cliente = anomalía vs. población. Un cliente crónicamente tardío pero estable sale anómalo siempre. | Las features del IF son desviaciones/ratios vs. la línea base del **mismo cliente**. Los estadísticos históricos descriptivos (delay promedio, puntualidad) se excluyen del IF. |
| 2 | Un CSV maestro | Sin panel por ciclo no hay línea base propia. | 4 tablas: `history_panel` (cliente × ciclo), `payments_log`, `contacts_log`, `customers_snapshot` (1 fila/cliente, historia agregada = entrada a modelos). |
| 3 | `situation_hint` en el JSON de `score_customer` | Ningún modelo produce S0–S4. | Se deriva con reglas deterministas sobre features. S4 es ortogonal a S1–S3 → `situation_hint ∈ {S0,S1,S2,S3}` + `low_digital_response ∈ {0,1}`. |
| 4 | `days_to_due` como feature | Hace que la anomalía dependa del día de scoring. | Variable temporal para NBA y compuertas. Fuera de IF y LR. |
| 5 | `synthetic_payment_difficulty` | Si se deriva de las features con una regla → LR 100 % (circular). "Dificultad" mezcla causa y resultado. | Etiqueta = resultado observable simulado `synthetic_late_payment_next_cycle`, generado desde variable latente oculta + ruido (§6). |
| 6 | Lista de features derivadas | Varias redundantes (§4). | Se fusionan o se eliminan con justificación. |
| 7 | `preferred_time` | No es observable, es inferencia. | Derivada de la moda de actividad en app con mínimo de 10 eventos; si no, `null`. |
| 8 | "Pago ya realizado" | No es feature. | Compuerta `current_cycle_paid = 1` → el cliente no se puntúa ni se contacta. |
| 9 | `risk_score` vs `anomaly_score` | No están definidos como distintos. | `anomaly_score` = IF normalizado (0–1). `risk_score` = combinación **SUPUESTO DE DEMO** (§7). Nunca se alimentan mutuamente como features. |

---

## 1. Estructura del dataset

```
history_panel.csv      1 fila por (customer_id, cycle_id)   → 6–12 ciclos por cliente. RAW histórico.
payments_log.csv       1 fila por pago/intento              → fuente de G (historial de pagos).
contacts_log.csv       1 fila por contacto enviado          → fuente de H, I, J.
customers_snapshot.csv 1 fila por cliente (ciclo actual + agregados) → CSV MAESTRO para ML, NBA, backend, dashboard.
golden_customers.csv   solo customer_id + expectativas       → nunca se une al snapshot en entrenamiento.
```

Convención: "ciclo" = período entre dos fechas de vencimiento de la cuota. "hist" = agregados sobre los últimos 6 ciclos completos (SUPUESTO DE DEMO: ventana de 6). "current" = ciclo en curso hasta `snapshot_date`.

### Leyenda de columnas de las tablas siguientes

- **Nat.** (naturaleza): RAW = observable actual · HIST = histórico · DER = derivada · UI = demo/interfaz · OUT = output de modelo · LBL = etiqueta sintética.
- **Modelos**: IF = Isolation Forest · LR = Logistic Regression · KM = K-Means · — = ninguno.
- **MVP**: P0 obligatoria · P1 útil · P2 opcional.
- **Sit.**: situación que ayuda a identificar.
- **Leak**: riesgo de data leakage (ninguno / bajo / medio / alto).
- **Prod**: existiría en producción (P) o solo en demo (D).
- **Generación**: distribución y dependencias para el generador sintético.

---

## 2. Tabla exhaustiva por categoría

### A. Identificación ficticia / demo

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `customer_id` | ID de cliente | string | `C104` | `C` + 3–5 dígitos, único | UI | — | P0 | ninguna | ninguno | P | Secuencial `C001…` | Llave primaria de todas las tablas. |
| `full_name_mock` | Nombre ficticio | string | `Cliente Demo 104` | texto | UI | — | P1 | ninguna | ninguno | D | Plantilla `Cliente Demo {n}` o lista de nombres inventados | Frontend/dashboard. Nunca feature. |
| `dui_mock` | DUI ficticio | string | `DUI-DEMO-000104` | patrón `DUI-DEMO-\d{6}` | UI | — | P1 | ninguna | ninguno | D | Derivado de `customer_id` | Inequívocamente falso; imposible coincidir con un DUI real. |
| `phone_mock` | Teléfono ficticio | string | `+503-0000-0104` | patrón demo | UI | — | P2 | ninguna | ninguno | D | Derivado de `customer_id` | Demo del canal SMS/llamada. |
| `account_id_mock` | Cuenta ficticia | string | `ACC-DEMO-000104` | patrón demo | UI | — | P2 | ninguna | ninguno | D | Derivado | Demo de "acceso rápido al pago". |
| `customer_since_date` | Cliente desde | date | `2022-03-15` | 2015-01-01 … `snapshot_date` | RAW | — | P1 | S0 (nuevo) | ninguno | P | Uniforme en fechas; ~8 % con < 6 meses (clientes nuevos) | Base de `tenure_months`; detecta cliente sin historial. |

### B. Datos financieros actuales (cuenta principal ficticia)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `current_balance` | Saldo disponible actual | float | `312.50` | ≥ 0 (USD) | RAW | vía DER | P0 | S1,S3 | ninguno | P | Lognormal condicionada a `income_hist_avg` × factor de latente de estrés (§6) | Insumo de `balance_ratio`, `balance_vs_historical`. |
| `balance_14d_ago` | Saldo hace 14 días | float | `540.00` | ≥ 0 | RAW | vía DER | P0 | S3 | ninguno | P | `current_balance` / (1 − drop), drop ~ Beta(2,8); en S3 Beta(5,4) | Insumo de `recent_balance_drop`. |
| `avg_balance_30d` | Saldo promedio 30 d | float | `420.10` | ≥ 0 | RAW | — | P1 | S3 | ninguno | P | Media de trayectoria simulada | Suaviza ruido de `current_balance` para dashboard. |
| `min_balance_30d` | Saldo mínimo 30 d | float | `88.00` | ≥ 0, ≤ `avg_balance_30d` | RAW | vía DER | P1 | S3 | ninguno | P | `avg_balance_30d` × U(0.1,0.9) | Insumo de `min_balance_ratio_30d`: captura si el cliente "toca fondo" dentro del mes. |

### C. Datos históricos financieros (agregados de `history_panel`)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `hist_cycles_available` | Ciclos con historia | int | `6` | 0–12 | HIST | — | P0 | S0 nuevo | ninguno | P | `min(6, tenure_months)` | Define confianza; si < 3, líneas base se marcan como no confiables. |
| `hist_avg_balance` | Saldo promedio histórico | float | `510.00` | ≥ 0; null si `hist_cycles_available`=0 | HIST | vía DER | P0 | S3 | ninguno | P | Media de `avg_balance` del panel | Línea base propia del saldo. |
| `hist_std_balance` | Desv. estándar saldo histórico | float | `95.00` | ≥ 0 | HIST | vía DER | P1 | S3 | ninguno | P | Std del panel | Permite z-score del saldo (alternativa a ratio). |
| `hist_avg_balance_at_due` | Saldo promedio el día de vencimiento | float | `260.00` | ≥ 0 | HIST | vía DER | P1 | S1,S2 | ninguno | P | Media del saldo en `due_date` en el panel | Diferencia "tiene dinero pero paga al límite" (S1) de "no llega" (S3). |

### D. Ingresos

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `income_type` | Tipo de ingreso | categorical | `SALARIED` | SALARIED, BIWEEKLY, INDEPENDENT, UNKNOWN | RAW | KM (one-hot) | P0 | S2 | ninguno | P | Categorical(0.55, 0.15, 0.22, 0.08) | Condiciona regularidad y fecha esperada. |
| `income_last_30d` | Ingreso últimos 30 d | float | `680.00` | ≥ 0 | RAW | vía DER | P0 | S3 | ninguno | P | `income_hist_avg` × (1 + shock), shock ~ N(0,0.08); S3: N(−0.35,0.15) | Ventana de 30 d siempre contiene un pago mensual → comparable con histórico. |
| `income_hist_avg` | Ingreso mensual promedio histórico | float | `750.00` | ≥ 0 | HIST | vía DER | P0 | S3 | ninguno | P | Lognormal(μ=6.6, σ=0.5) ≈ mediana 730 USD (SUPUESTO DE DEMO) | Línea base del ingreso. |
| `income_hist_std` | Desv. estándar ingreso histórico | float | `40.00` | ≥ 0 | HIST | vía DER | P1 | S2,S3 | ninguno | P | SALARIED: 0.03–0.08 × avg; INDEPENDENT: 0.2–0.5 × avg | Insumo de `income_amount_cv`. |
| `income_expected_day` | Día esperado de ingreso | int | `30` | 1–31; null si UNKNOWN o regularidad baja | HIST | vía DER | P0 | S2 | ninguno | P | Moda del día de depósito en el panel; null si `income_day_std` > 5 (SUPUESTO DE DEMO) | Núcleo de S2 (`income_due_gap`). |
| `income_day_std` | Variabilidad del día de ingreso | float | `1.2` | 0–15 | HIST | vía DER | P1 | S2 | ninguno | P | SALARIED: U(0,2); INDEPENDENT: U(3,12) | Regularidad de *timing* (distinta de monto). |
| `income_deposits_6m` | Depósitos de ingreso en 6 ciclos | int | `6` | 0–24 | HIST | — | P2 | S2 | ninguno | P | Poisson(6) SALARIED; Poisson(9) INDEPENDENT | Apoya `income_type` inferido. |
| `last_income_date` | Última fecha de ingreso | date | `2026-08-30` | ≤ `snapshot_date` | RAW | vía DER | P1 | S2,S3 | ninguno | P | Derivada de `income_expected_day` y ciclo | Insumo de `days_since_last_income`. |
| `next_expected_income_date` | Próxima fecha esperada de ingreso | date | `2026-09-30` | > `snapshot_date`; null si desconocida | DER | vía DER | P0 | S2 | ninguno | P | `income_expected_day` proyectado al siguiente mes | Insumo directo de `income_due_gap` y `projected_coverage`. |

### E. Gastos

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `expenses_last_30d` | Gasto últimos 30 d | float | `720.00` | ≥ 0 | RAW | vía DER | P0 | S3 | ninguno | P | `expenses_hist_avg` × (1 + shock), shock ~ N(0,0.10); S3: N(+0.30,0.15) | Nivel de gasto reciente vs. histórico. |
| `expenses_last_7d` | Gasto últimos 7 d | float | `260.00` | ≥ 0 | RAW | vía DER | P1 | S3 | ninguno | P | `expenses_last_30d`/4.3 × (1 + N(0,0.2)); S3 picos U(1.5,2.5) | Aceleración reciente (velocidad). |
| `expenses_hist_avg` | Gasto mensual promedio histórico | float | `600.00` | ≥ 0 | HIST | vía DER | P0 | S3 | ninguno | P | `income_hist_avg` × U(0.55,0.95) | Línea base del gasto. |
| `expenses_hist_std` | Desv. estándar gasto histórico | float | `70.00` | ≥ 0 | HIST | — | P2 | S3 | ninguno | P | 0.08–0.2 × avg | z-score de gasto (alternativa). |

Se excluye deliberadamente: categorización de gasto (ocio, salud…) → inferencia sobre estilo de vida, innecesaria para el MVP y cercana a etiquetado moral.

### F. Obligación / crédito

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `credit_id_mock` | ID de crédito ficticio | string | `CR-DEMO-000104` | patrón demo | UI | — | P1 | ninguna | ninguno | D | Derivado | Trazabilidad backend. |
| `product_type` | Tipo de producto | categorical | `PERSONAL_LOAN` | PERSONAL_LOAN, CREDIT_CARD, AUTO_LOAN | RAW | KM (one-hot) | P1 | ninguna | ninguno | P | Categorical(0.5,0.35,0.15) | Contexto de UI y Policy Engine; no cambia el score en el MVP. |
| `installment_amount` | Cuota mensual | float | `180.00` | > 0 (test: 0 solo como edge case) | RAW | vía DER | P0 | varias | ninguno | P | `income_hist_avg` × U(0.10,0.40) | Denominador de casi todos los ratios. |
| `due_day` | Día de vencimiento | int | `25` | 1–31 | RAW | vía DER | P0 | S2 | ninguno | P | Categorical sobre {5,10,15,20,25,30} | Insumo de `next_due_date` e `income_due_gap`. |
| `next_due_date` | Próximo vencimiento | date | `2026-09-25` | ≥ `snapshot_date` | DER | vía DER | P0 | varias | ninguno | P | `due_day` proyectado | Insumo de `days_to_due`. |
| `remaining_installments` | Cuotas restantes | int | `18` | 0–120 | RAW | — | P2 | ninguna | ninguno | P | Uniforme 1–60 | UI / Policy Engine (p.ej. si hay margen para reprogramar; SUPUESTO DE DEMO). |
| `loan_remaining_balance` | Saldo del crédito | float | `3240.00` | ≥ 0 | RAW | — | P2 | ninguna | ninguno | P | `installment_amount` × `remaining_installments` × U(0.8,1.0) | Solo UI. |

### G. Historial de pagos (agregado de `payments_log`, últimos 6 ciclos)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `payments_observed_n` | Pagos observados | int | `6` | 0–12 | HIST | — | P0 | ninguna | ninguno | P | = `hist_cycles_available` | Denominador de tasas; si 0 → sin historial. |
| `on_time_payments_n` | Pagos a tiempo | int | `4` | 0–`payments_observed_n` | HIST | vía DER | P0 | S1 | ninguno | P | Binomial(n, p), p por perfil: S0 0.95, S1 0.5, S2 0.4, S3 0.6 histórico | Insumo de `payment_punctuality`. |
| `payment_delay_avg` | Retraso promedio (días) | float | `2.3` | 0–60 | HIST | LR, KM | P0 | S1,S2 | bajo | P | Media de `max(0, pay_date − due_date)` del log; S1: Gamma(2,1.5); S2: Gamma(4,1.5); S0: ≈0 | Magnitud del retraso habitual. |
| `payment_delay_max` | Retraso máximo (días) | int | `9` | 0–90 | HIST | KM | P1 | S1,S2 | bajo | P | Máx del log | Peor caso histórico. |
| `payment_delay_std` | Variabilidad del retraso | float | `1.8` | ≥ 0 | HIST | KM | P1 | S1 | bajo | P | Std del log | Reemplaza `historical_payment_consistency`. |
| `days_before_due_avg` | Anticipación promedio (días) | float | `−1.5` | −30…+30 (negativo = paga después) | HIST | — | P2 | S1 | bajo | P | Media de `due_date − pay_date` | Redundante con delay salvo por pagos adelantados; opcional. |
| `last_payment_delay_days` | Retraso del último pago | int | `4` | 0–90 | HIST | vía DER | P0 | S1,S3 | bajo | P | Último registro del log | Insumo de `last_payment_delay_deviation`. |
| `partial_payments_n` | Pagos parciales | int | `1` | 0–12 | HIST | LR | P1 | S3 | bajo | P | Binomial(n, 0.05); S3: 0.3 | Señal de presión sostenida. |
| `failed_payment_attempts_30d` | Intentos fallidos 30 d | int | `2` | 0–20 | RAW | IF, LR | P0 | S3 | ninguno | P | Poisson(0.1); S3: Poisson(1.5) | Señal directa y explicable ("intentó y no pudo"). |
| `failed_attempts_hist_avg` | Intentos fallidos promedio/ciclo | float | `0.2` | ≥ 0 | HIST | vía DER | P1 | S3 | ninguno | P | Media del panel | Línea base para `failed_attempts_deviation`. |
| `max_days_in_arrears_12m` | Máx. días en mora 12 m | int | `12` | 0–365 | HIST | — | P2 | ninguna | **medio** | P | Correlacionado con `payment_delay_max` | Solo dashboard. Fuera de modelos: describe el pasado en términos de mora y empuja la narrativa "predice mora". |
| `current_cycle_paid` | Cuota actual ya pagada | boolean | `false` | true/false | RAW | — (compuerta) | P0 | ninguna | **alto** | P | Bernoulli(0.25) si `days_to_due` < 5; 0 si no | Si `true` → no se puntúa ni contacta. Nunca feature. |

### H. Historial de contactos (agregado de `contacts_log`, 90 d)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `contacts_sent_90d` | Contactos enviados 90 d | int | `5` | 0–30 | HIST | — | P0 | S4 | ninguno | P | Poisson(3); S4: Poisson(6) | Denominador de tasa de respuesta; input de cap de contacto. |
| `contacts_answered_90d` | Contactos respondidos 90 d | int | `1` | 0–`contacts_sent_90d` | HIST | vía DER | P0 | S4 | ninguno | P | Binomial(n, p): p ~ Beta(6,3); S4: Beta(1,6) | Insumo de `contact_response_rate`. |
| `app_push_sent_90d` / `app_push_opened_90d` | Push enviados / abiertos | int | `3 / 2` | 0–30 | HIST | vía DER | P1 | S4 | ninguno | P | Igual, por canal | Tasa por canal → `best_channel`. |
| `sms_sent_90d` / `sms_replied_90d` | SMS enviados / respondidos | int | `2 / 0` | 0–30 | HIST | vía DER | P1 | S4 | ninguno | P | Igual | Ídem. |
| `calls_attempted_90d` / `calls_answered_90d` | Llamadas intentadas / atendidas | int | `1 / 1` | 0–30 | HIST | vía DER | P1 | S4 | ninguno | P | Igual | Ídem. |
| `last_contact_date` | Último contacto | date | `2026-08-20` | ≤ `snapshot_date`; null | HIST | vía DER | P0 | S4 | ninguno | P | Uniforme en 90 d | Insumo de `days_since_last_contact` (anti-insistencia). |
| `last_contact_channel` | Canal del último contacto | categorical | `SMS` | APP_PUSH, SMS, CALL, NONE | HIST | — | P1 | S4 | ninguno | P | Categorical | UI y regla "cambiar canal". |
| `last_contact_outcome` | Resultado del último contacto | categorical | `IGNORED` | ANSWERED, IGNORED, REJECTED, NONE | HIST | — | P1 | S4 | ninguno | P | Categorical condicionada al perfil | Regla "reducir insistencia si REJECTED". |
| `opt_out_flag` | Rechazo explícito de contactos | boolean | `false` | true/false | RAW | — (compuerta) | P0 | S4 | ninguno | P | Bernoulli(0.03) | Ética: si `true`, NO_CONTACT sin importar el riesgo (salvo escalamiento humano). |

### I. Uso de canales digitales (90 d)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `app_logins_30d` | Ingresos a la app 30 d | int | `9` | 0–100 | RAW | vía DER | P0 | S4,S1 | ninguno | P | Poisson(8); S4: Poisson(1) | Nivel de engagement actual. |
| `app_logins_hist_avg` | Ingresos promedio/mes histórico | float | `10.5` | ≥ 0 | HIST | vía DER | P1 | S4 | ninguno | P | Media del panel | Insumo de `app_engagement_ratio`. |
| `last_app_login_date` | Último ingreso a la app | date | `2026-09-10` | ≤ `snapshot_date`; null | RAW | vía DER | P0 | S4 | ninguno | P | Exponencial según `app_logins_30d` | Insumo de `days_since_last_login`. |
| `push_enabled` | Notificaciones push activas | boolean | `true` | true/false | RAW | — | P0 | S4 | ninguno | P | Bernoulli(0.8) | Si `false`, el canal APP_PUSH no es elegible. |
| `activity_hour_mode` | Hora más frecuente de uso | int | `12` | 0–23; null si < 10 eventos | HIST | — | P1 | S4 | ninguno | P | Moda de N(hora_perfil, 1.5) | Insumo de `preferred_time_window`. |
| `activity_events_90d` | Eventos de actividad 90 d | int | `31` | ≥ 0 | HIST | — | P1 | S4 | ninguno | P | ≈ 3 × `app_logins_30d` | Mínimo de observaciones para confiar en la hora. |

### J. Intervenciones anteriores de BA A Tiempo

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `prior_interventions_n` | Intervenciones previas | int | `2` | 0–20 | HIST | — | P1 | varias | bajo | P | Poisson(1) | Historial del propio sistema (aprender). |
| `prior_interventions_accepted_n` | Intervenciones aceptadas | int | `1` | 0–n | HIST | — | P1 | varias | bajo | P | Binomial(n, 0.6) | Tasa de aceptación → NBA (qué ofrecer primero). |
| `last_intervention_type` | Tipo de última intervención | categorical | `DATE_SHIFT` | NONE, REMINDER, DATE_SHIFT, PARTIAL_PLAN, HUMAN_ESCALATION | HIST | — | P1 | varias | bajo | P | Categorical | NBA y dashboard. |
| `last_intervention_outcome` | Resultado | categorical | `ACCEPTED` | NONE, ACCEPTED, REJECTED, IGNORED, PAID_AFTER | HIST | — | P1 | varias | **medio** | P | Categorical | Fuera de modelos: incorpora decisiones del sistema → sesgo de retroalimentación. |
| `last_intervention_date` | Fecha | date | `2026-07-22` | ≤ snapshot; null | HIST | — | P2 | ninguna | ninguno | P | Uniforme | Trazabilidad. |

### K. Variables temporales

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `snapshot_date` | Fecha de corte | date | `2026-09-12` | fija por corrida | RAW | — | P0 | ninguna | ninguno | P | Constante por dataset | Ancla de todos los cálculos. |
| `cycle_id` | ID de ciclo | string | `2026-09` | `YYYY-MM` | RAW | — | P0 | ninguna | ninguno | P | Derivado | Llave del panel. |
| `days_to_due` | Días al vencimiento | int | `7` | −30…31 (negativo = ya vencido) | DER | — (NBA) | P0 | varias | bajo | P | `next_due_date − snapshot_date` | Timing de la intervención; excluido de modelos (§0). |
| `days_elapsed_in_cycle` | Días transcurridos del ciclo | int | `23` | 0–31 | DER | — | P1 | ninguna | ninguno | P | 30 − `days_to_due` aprox. | Normalizar gasto acumulado si se usa. |
| `tenure_months` | Antigüedad (meses) | int | `42` | 0–140 | DER | LR (P2), KM | P1 | S0 nuevo | ninguno | P | `(snapshot_date − customer_since_date)/30` | Confianza en líneas base. |
| `days_since_last_income` | Días desde último ingreso | int | `13` | 0–90; null | DER | — | P1 | S2,S3 | ninguno | P | Diferencia de fechas | Contexto S2/S3 para NBA. |
| `days_since_last_contact` | Días desde último contacto | int | `23` | 0–90; null | DER | — (NBA) | P0 | S4 | ninguno | P | Diferencia | Regla anti-insistencia. |
| `days_since_last_login` | Días desde último ingreso a la app | int | `2` | 0–90; null | DER | — (regla S4) | P0 | S4 | ninguno | P | Diferencia | Desconexión digital. |

### L. Variables derivadas → §4 (tabla propia).

### M. Variables objetivo sintéticas

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Sit. | Leak | Prod | Generación | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `synthetic_late_payment_next_cycle` | Etiqueta sintética: pago tardío/parcial simulado en el siguiente ciclo | int | `1` | 0/1 | LBL | LR (target) | P0 | — | **alto** (es la etiqueta) | D (en prod sería el outcome real observado después) | Simulación §6 | Target de la LR. Nunca feature. Nombre deja claro que es un resultado, no un juicio. |
| `latent_stress_index` | Índice latente de presión (generador) | float | `0.71` | 0–1 | LBL | — | P0 en `generator_state`, **no en el snapshot** | — | **alto** | D | Beta por perfil §6 | Motor oculto que correlaciona features y etiqueta con ruido. Vive en un archivo aparte. |
| `synthetic_situation_truth` | Situación verdadera del generador | categorical | `S3` | S0–S4 | LBL | — | P0 en `generator_state` | — | **alto** | D | Asignada por perfil | Para medir si las reglas de `situation_hint` recuperan la verdad. Nunca en el snapshot. |

### N. Validación / golden cases (archivo `golden_customers.csv`)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | Nat. | Modelos | MVP | Leak | Prod | Por qué |
|---|---|---|---|---|---|---|---|---|---|---|
| `is_golden` | Es golden customer | boolean | `true` | | UI | — | P0 | alto | D | Filtrarlos del entrenamiento del IF/LR (o al menos del test). |
| `golden_scenario` | Escenario | string | `S3_INCOME_DROP` | texto | UI | — | P0 | alto | D | Nombre legible para el jurado. |
| `golden_expected_situation` | Situación esperada | categorical | `S3` | S0–S4 | UI | — | P0 | alto | D | Assert en tests. |
| `golden_expected_intervene` | ¿Debe intervenirse? | boolean | `true` | | UI | — | P0 | alto | D | Assert. |
| `golden_expected_top_factors` | Factores esperados | string (lista) | `balance_ratio_low;income_variation_neg` | | UI | — | P1 | alto | D | Assert de explicabilidad. |
| `golden_expected_channel` | Canal esperado | categorical | `CALL` | | UI | — | P1 | alto | D | Assert NBA. |
| `edge_case_type` | Tipo de caso extremo | categorical | `ZERO_INCOME` | ver §9; NONE | UI | — | P0 | alto | D | Robustez. |
| `golden_notes` | Nota explicativa | string | | | UI | — | P1 | ninguno | D | Narrativa demo. |

### O. Outputs de ML (los produce `score_customer`; nunca entran como inputs)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | MVP | Leak | Cómo se produce |
|---|---|---|---|---|---|---|---|
| `anomaly_score_raw` | Score IF crudo | float | `−0.12` | ℝ | P1 | alto | `IsolationForest.decision_function` (negativo = más anómalo). |
| `anomaly_score` | Score de anomalía | float | `0.81` | 0–1 | P0 | alto | Min-max sobre train de `−decision_function`, clip [0,1]. Alto = atípico. |
| `anomaly_flag` | Es anómalo | boolean | `true` | | P0 | alto | `anomaly_score ≥ umbral` (contamination 0.1, SUPUESTO DE DEMO). |
| `risk_prob_lr` | Probabilidad LR | float | `0.74` | 0–1 | P0 | alto | `predict_proba` del baseline. |
| `risk_score` | Score de riesgo combinado | float | `0.78` | 0–1 | P0 | alto | §7. |
| `risk_level` | Nivel | categorical | `HIGH` | LOW, MEDIUM, HIGH | P0 | alto | Cortes 0.35/0.65 (SUPUESTO DE DEMO). |
| `situation_hint` | Situación sugerida | categorical | `S3` | S0–S3 | P0 | alto | Reglas §7 sobre features; **no** modelo. |
| `low_digital_response` | Baja respuesta digital | boolean | `true` | | P0 | alto | Regla S4 §7. |
| `top_factors` | Factores explicativos | string (lista) | `balance_ratio_low;income_variation_neg` | 2–4 ítems | P0 | alto | §8. |
| `cluster_id` | Cluster K-Means | int | `2` | 0–k; null si se excluye | P2 | alto | Solo exploratorio. |
| `model_version` / `scored_at` | Versión / timestamp | string / datetime | `if_v1_lr_v1` | | P0 | ninguno | Trazabilidad. |

### P. Variables para Next Best Action (reglas, no ML)

| Variable | Nombre ES | Tipo | Ejemplo | Rango | MVP | Fuente |
|---|---|---|---|---|---|---|
| `should_contact` | Intervenir | boolean | `true` | | P0 | Regla: `not current_cycle_paid and not opt_out and days_since_last_contact ≥ 3 and (risk_level ≠ LOW or anomaly_flag) and 1 ≤ days_to_due ≤ 10` (SUPUESTO DE DEMO). |
| `contacts_last_7d` | Contactos últimos 7 d | int | `0` | 0–7 | P0 | `contacts_log`. Cap: máx. 2 (SUPUESTO DE DEMO). |
| `best_channel` | Mejor canal observado | categorical | `CALL` | APP_PUSH, SMS, CALL, UNKNOWN | P0 | `channel_effectiveness` §4. |
| `preferred_time_window` | Franja horaria preferida | string | `12:00-13:30` | franjas de 90 min; null | P0 | Desde `activity_hour_mode` si `activity_events_90d ≥ 10`. |
| `recommended_channel` | Canal recomendado | categorical | `CALL` | | P0 | `best_channel`, con fallback APP_PUSH si `push_enabled`. Si `low_digital_response` → cambiar a un canal no probado recientemente. |
| `recommended_action` | Acción inicial | categorical | `EMPATHETIC_CONVERSATION` | NO_CONTACT, SIMPLE_REMINDER, DATE_OPTIONS, EMPATHETIC_CONVERSATION, CHANNEL_SWITCH, HUMAN_ESCALATION | P0 | Mapeo de `situation_hint` + `low_digital_response`. |
| `nba_reason` | Razón legible | string | `"Saldo 40% de la cuota e ingreso −35% vs histórico"` | | P0 | Plantilla desde `top_factors`. |

### Q. Trazabilidad / dashboard

| Variable | Tipo | Ejemplo | MVP | Por qué |
|---|---|---|---|---|
| `scoring_run_id` | string | `run_2026-09-12_01` | P0 | Reproducibilidad. |
| `dataset_version` / `generator_seed` | string / int | `synth_v1` / `42` | P0 | Reproducibilidad. |
| `intervention_status` | categorical: NOT_STARTED, SENT, IN_CONVERSATION, RESOLVED, ESCALATED | P0 | Embudo del dashboard. |
| `intervention_outcome` | categorical: NONE, ACCEPTED, REJECTED, IGNORED, PAID | P0 | Cierre del ciclo "REGISTRAR". |
| `conversation_id_mock` | string | P1 | Enlace al log del LLM. |
| `policy_decision_id` | string | P1 | Qué alternativas autorizó el Policy Engine. |
| `escalated_to_human` | boolean | P0 | KPI de escalamiento. |
| `human_review_flag` | boolean | P1 | Para revisión manual de casos anómalos sin explicación clara. |

---

## 3. VARIABLES PROHIBIDAS COMO FEATURES

| Variable | Por qué |
|---|---|
| `synthetic_late_payment_next_cycle` | Es la etiqueta. |
| `latent_stress_index`, `synthetic_situation_truth` | Son el generador de la etiqueta: leakage total, LR daría 100 %. No viven en el snapshot. |
| `is_golden`, `golden_*`, `edge_case_type` | Codifican la respuesta esperada. Además los golden deben salir del train del IF/LR (o del test como mínimo) para que la demo no sea "memorización". |
| `anomaly_score*`, `risk_*`, `situation_hint`, `top_factors`, `cluster_id` | Outputs. Meterlos como inputs crea dependencia circular entre corridas y hace inexplicable el resultado. Stacking LR(anomaly_score) es legítimo pero **no** para este MVP: complica la explicación ante jurado. |
| `current_cycle_paid`, `max_days_in_arrears_12m`, cualquier "resultado futuro del pago", `future_days_in_arrears` | Revelan el outcome o describen el pasado en términos de mora; contradicen "anomalía ≠ mora". |
| `last_intervention_outcome`, `prior_interventions_accepted_n` | Contienen decisiones del propio sistema → bucle de retroalimentación (el modelo aprende lo que el sistema hizo, no lo que el cliente es). Van a NBA, no a ML. |
| `days_to_due`, `snapshot_date`, `cycle_id` | Timing de scoring, no comportamiento. |
| `customer_id`, `*_mock`, `full_name_mock` | Identidad. |
| `income_type`, `product_type` en IF | Categóricas one-hot en IF distorsionan la aislabilidad (categorías raras = "anómalas"). Solo K-Means/LR con cuidado. |

---

## 4. Feature engineering (variables derivadas)

Notación: `eps = 1e-6`; `safe_div(a,b) = a/b si b>eps, si no NaN`; `clip(x,lo,hi)`.

Regla de faltantes general: si una línea base histórica no existe (`hist_cycles_available < 3`), la feature de desviación se imputa al **valor neutro** (ratio = 1, variación = 0) y se enciende `baseline_unreliable = 1`. Así un cliente nuevo no sale "anómalo" por falta de datos. Se documenta como SUPUESTO DE DEMO.

| Feature | Fórmula | Interpretación | Normal | Alto | Bajo | ÷0 | Faltantes | Modelo |
|---|---|---|---|---|---|---|---|---|
| `balance_ratio` | `clip(safe_div(current_balance, installment_amount), 0, 10)` | Cuántas cuotas cubre el saldo hoy | 1.5–4 | Holgura | < 1: no cubre la cuota | cuota 0 → NaN + excluir de scoring | saldo null → NaN → excluir | IF, LR, KM |
| `min_balance_ratio_30d` | `clip(safe_div(min_balance_30d, installment_amount), 0, 10)` | Si "tocó fondo" durante el mes | ≥ 0.8 | Nunca se quedó sin margen | Cerca de 0: momentos sin liquidez | igual | igual | IF |
| `projected_coverage` | `clip(safe_div(current_balance + income_before_due, installment_amount), 0, 10)` con `income_before_due = income_last_30d si next_expected_income_date ≤ next_due_date, si no 0` | Cobertura esperada al vencimiento | ≥ 1.5 | Cubre aun sin ingreso extra | < 1 con `balance_ratio` < 1 y gap > 0 → S2; < 1 con gap ≤ 0 → S3 | igual | fecha de ingreso null → usa solo saldo y `income_date_unknown=1` | LR |
| `balance_vs_historical` | `clip(safe_div(current_balance, hist_avg_balance), 0, 5)` | Saldo vs. su propia normalidad | 0.7–1.3 | Más liquidez que de costumbre | < 0.5: caída fuerte | hist 0 → neutro 1 + flag | hist null → 1 + flag | IF |
| `recent_balance_drop` | `clip(safe_div(balance_14d_ago − current_balance, balance_14d_ago), −1, 1)` | Velocidad de caída en 2 semanas | −0.2…0.3 | > 0.5: se vació rápido | negativo: recuperó | b14 = 0 → 0 | null → 0 | IF |
| `income_variation` | `clip(safe_div(income_last_30d − income_hist_avg, income_hist_avg), −1, 3)` | Desviación del ingreso vs. histórico | ±0.15 | Ingreso extraordinario (anómalo pero benigno; ver top_factors) | < −0.25: caída de ingreso (S3) | hist 0 → 0 + flag | 0 + flag | IF, LR, KM |
| `income_amount_cv` | `safe_div(income_hist_std, income_hist_avg)` | Estabilidad del monto (reemplaza `income_stability`) | SALARIED < 0.1; INDEP 0.2–0.5 | Ingreso impredecible | Muy regular | 0 | null → mediana por `income_type` | LR, KM |
| `income_timing_regularity` | `income_day_std` (renombra `income_regularity`) | Estabilidad de la fecha (no del monto) | < 2 | > 5: fecha impredecible → `income_expected_day = null` | Fecha fija | — | null → 15 (máximo) | KM; regla S2 |
| `income_due_gap` | `d = (next_expected_income_date − next_due_date).days`; envolver a `[−15, 15]` con módulo 30 | Días que el ingreso llega **después** del vencimiento | ≤ 0 | +3…+15: desfase (S2) | Ingreso antes del vencimiento | — | fecha null → NaN + `income_date_unknown=1` | LR (parte positiva `max(0,gap)`); regla S2 |
| `expense_variation_30d` | `clip(safe_div(expenses_last_30d − expenses_hist_avg, expenses_hist_avg), −1, 3)` | Desviación del gasto mensual (absorbe `spending_velocity` mensual) | ±0.15 | > 0.3: gasto elevado | Redujo gasto | 0 + flag | 0 + flag | IF, LR |
| `spending_velocity_7d` | `clip(safe_div(expenses_last_7d, expenses_hist_avg / 4.3), 0, 5)` | Ritmo de la última semana vs. semana típica | 0.7–1.3 | > 2: aceleración reciente | Frenó gasto | 0 → 1 | 1 | IF (P1) |
| `payment_punctuality` | `safe_div(on_time_payments_n, payments_observed_n)` | Fracción de pagos a tiempo | > 0.8 | Puntual | < 0.5: retrasos recurrentes (S1/S2) | 0 pagos → NaN → 0.8 (prior) + flag | igual | LR, KM |
| `payment_delay_avg` | (raw, §G) | Magnitud típica del retraso | 0–1 | > 5 | 0 | — | 0 + flag | LR o KM (elegir una entre esta y punctuality en LR si `|corr| > 0.85`) |
| `last_payment_delay_deviation` | `last_payment_delay_days − payment_delay_avg` | El último pago se retrasó **más de lo habitual para él** | ±2 | > 5: cambio de comportamiento | Pagó antes que de costumbre | — | 0 + flag | IF |
| `failed_attempts_deviation` | `failed_payment_attempts_30d − failed_attempts_hist_avg` | Intentos fallidos por encima de su norma | 0 | ≥ 2 | — | — | usa el raw | IF (P1; el raw es P0) |
| `contact_response_rate` | `safe_div(contacts_answered_90d, contacts_sent_90d)` (fusiona `reminder_response_rate`) | Responde al banco | > 0.5 | Receptivo | < 0.25 con ≥ 3 enviados → S4 | 0 enviados → NaN + `contact_history_insufficient=1` | igual | Regla S4; KM |
| `channel_response_rate_{app,sms,call}` | por canal, mismo patrón | Qué canal funciona | — | — | — | NaN si < 2 enviados | — | NBA |
| `channel_effectiveness` → `best_channel` | `argmax` de las tasas con ≥ 2 envíos; empate → orden APP_PUSH > SMS > CALL; ninguno elegible → UNKNOWN | Canal con mejor evidencia | — | — | — | — | UNKNOWN | NBA |
| `app_engagement_ratio` | `clip(safe_div(app_logins_30d, app_logins_hist_avg), 0, 5)` | Uso de la app vs. su norma | 0.7–1.3 | Más activo | < 0.3: desconexión (S4) | 0 → 1 + flag | 1 + flag | Regla S4; KM |
| `days_to_due` | ver §K | timing | — | — | — | — | — | NBA |

**Eliminadas / fusionadas**

- `payment_coverage` → renombrada `projected_coverage` (proyectado; `balance_ratio` es actual).
- `spending_velocity` → `spending_velocity_7d` (7 d) y `expense_variation_30d` (30 d); una mide nivel, otra aceleración.
- `reminder_response_rate` → `contact_response_rate`.
- `income_stability` → `income_amount_cv`; `income_regularity` → `income_timing_regularity`.
- `historical_payment_consistency` → eliminada, es `payment_delay_std`.
- `income_variation` vs `income_stability`: no redundantes (desviación actual vs. dispersión histórica).

**Flags de calidad (int 0/1, no features, sí `top_factors`/UI):** `baseline_unreliable`, `income_date_unknown`, `contact_history_insufficient`, `has_missing_core`.

---

## 5. Diseño para Isolation Forest

Objetivo: "el ciclo actual se aleja de su patrón". Solo desviaciones y estados actuales; nada descriptivo del pasado.

| # | Feature | Qué detecta | Por qué se defiende | Transform. |
|---|---|---|---|---|
| 1 | `balance_vs_historical` | Saldo muy por debajo de su norma | Es literalmente "vs. histórico". | log1p tras clip |
| 2 | `recent_balance_drop` | Caída rápida | Señal de shock reciente. | ninguna |
| 3 | `balance_ratio` | Saldo insuficiente vs. cuota | Estado actual crítico aunque el histórico sea bajo. | log1p |
| 4 | `min_balance_ratio_30d` | Tocó fondo en el mes | Captura estrés intra-mes invisible en el snapshot. | log1p |
| 5 | `income_variation` | Cambio de ingreso | S3 por caída; ingresos extraordinarios también salen anómalos → se explica en top_factors con signo. | ninguna |
| 6 | `expense_variation_30d` | Cambio de gasto | Directo. | ninguna |
| 7 | `spending_velocity_7d` | Aceleración reciente | P1; ruidosa. | log1p |
| 8 | `failed_payment_attempts_30d` | Intentos fallidos | Evento raro y muy explicable. | ninguna (Poisson, entero) |
| 9 | `last_payment_delay_deviation` | Pagó más tarde de lo habitual **para él** | Comportamiento de pago inusual sin castigar al crónico. | ninguna |
| 10 | `failed_attempts_deviation` | Fallos por encima de su norma | P1; refuerza 8. | ninguna |

10 features (8 P0 + 2 P1). Excluidas a propósito: `payment_punctuality`, `payment_delay_avg`, `income_amount_cv`, `contact_response_rate`, `days_to_due`, categóricas.

**Scaling.** IF es de árboles: no necesita estandarización para funcionar. Lo que sí necesita es **clipping y log1p en colas pesadas** (ratios y montos): sin eso, el IF solo aísla valores absurdos (saldo ×50) y se pierde el cliente "moderadamente raro". Los conteos Poisson y las variaciones acotadas se dejan crudos. Si aplicas StandardScaler no daña, pero no es la parte importante. Parámetros de arranque (SUPUESTO DE DEMO): `n_estimators=200, contamination=0.10, random_state=seed`; entrenar sin golden ni edge cases.

**Chequeo de sanidad obligatorio**: el S0 "no molestar" debe tener `anomaly_score < 0.4`; el cliente nuevo con imputación neutra debe tener `anomaly_score` cercano a la mediana.

---

## 6. Logistic Regression: features y etiqueta

### Features (10)

`balance_ratio`, `projected_coverage`, `balance_vs_historical`, `income_variation`, `expense_variation_30d`, `payment_punctuality` (o `payment_delay_avg`, la de menor colinealidad), `partial_payments_n`, `failed_payment_attempts_30d`, `income_due_gap_pos = max(0, income_due_gap)`, `income_amount_cv`. Opcional P2: `tenure_months`.

Transformaciones: log1p en ratios, StandardScaler en todo (LR sí lo necesita para que los coeficientes sean comparables y `top_factors` tenga sentido). Regularización L2, `class_weight='balanced'`. Métrica: AUC y curva de calibración, presentadas como **validación del pipeline, no desempeño real**.

### Etiqueta: `synthetic_late_payment_next_cycle`

Se rechaza `synthetic_payment_difficulty` porque (a) "dificultad" es una causa inferida, no un resultado; (b) invita a definirla con las mismas features → circularidad.

Definición: `1` si en el ciclo **siguiente** simulado el pago ocurrió con ≥ 3 días de retraso **o** fue parcial; `0` en otro caso (SUPUESTO DE DEMO para el umbral).

Generación sin circularidad (proceso generativo con variable latente):

1. Para cada cliente, muestrear un perfil `synthetic_situation_truth` y un `latent_stress_index z ~ Beta(a,b)` por perfil: S0 Beta(1.5,8); S1 Beta(2,6); S2 Beta(3,5); S3 Beta(6,2.5); S4 Beta(2,5).
2. Generar las variables RAW **condicionadas a z con ruido** (las distribuciones de §2 usan z como desplazamiento: p.ej. `income shock ~ N(−0.5·z, 0.12)`, `expense shock ~ N(0.4·z, 0.12)`, `failed attempts ~ Poisson(2·z)`).
3. Generar el outcome del ciclo siguiente: `p_late = sigmoid(−2.2 + 3.0·z + 0.8·[income_due_gap>0] + 1.5·(1 − payment_punctuality) + 0.6·[S1] + ε)`, `ε ~ N(0, 0.5)`; `label ~ Bernoulli(p_late)`; luego invertir el 4 % de las etiquetas (ruido de etiqueta).
4. Guardar `z` y `synthetic_situation_truth` **solo** en `generator_state.parquet`. El snapshot no los contiene.

Por qué no es trivial: las features observan z con ruido, el outcome depende de z con más ruido, y S1 tiene retrasos con dinero (el modelo no puede resolverlo con `balance_ratio`). AUC esperada ~0.75–0.85. Si sale > 0.95, sube el ruido; si sale < 0.65, baja. Documenta el valor final como calibración de demo.

---

## 7. `risk_score`, `risk_level`, `situation_hint` (reglas)

- `risk_score = 0.6·risk_prob_lr + 0.4·anomaly_score` (SUPUESTO DE DEMO; comunicar como "combinación demostrativa").
- `risk_level`: LOW < 0.35 ≤ MEDIUM < 0.65 ≤ HIGH.
- `situation_hint` (evaluar en orden; la primera que aplica):
  1. **S3** si `balance_ratio < 1` y (`income_variation < −0.2` o `expense_variation_30d > 0.25` o `failed_payment_attempts_30d ≥ 2` o `min_balance_ratio_30d < 0.3`).
  2. **S2** si `balance_ratio < 1` y `income_due_gap > 0` y `projected_coverage ≥ 1` (ingreso llega después pero alcanza).
  3. **S1** si `balance_ratio ≥ 1` y (`payment_punctuality < 0.6` o `payment_delay_avg > 1`) y sin señales S3.
  4. **S0** en otro caso, o si `baseline_unreliable = 1` y `balance_ratio ≥ 1`.
- `low_digital_response = 1` si `contacts_sent_90d ≥ 3` y `contact_response_rate < 0.25`, o `app_engagement_ratio < 0.3` con `days_since_last_login > 21`.
- Casos "sin señal pero anómalo" (anomalía benigna, p.ej. ingreso extraordinario): `situation_hint = S0`, `human_review_flag = 1`, NO_CONTACT.

Validación: matriz de confusión de `situation_hint` vs `synthetic_situation_truth` (solo para reportar que las reglas funcionan sobre el generador; no es desempeño real).

## 8. `top_factors`

Para IF: contribución por feature = cuánto cae `anomaly_score` al reemplazar esa feature por su mediana (ablación simple, 10 features → barato). Para LR: `coef × valor_estandarizado`. Se toman los 2–4 mayores y se mapean a etiquetas con signo, p.ej. `balance_ratio_low`, `balance_vs_historical_low`, `income_variation_neg`, `income_variation_pos`, `expense_variation_high`, `failed_attempts_high`, `payment_delay_unusual`, `income_due_gap_positive`, `low_contact_response`. Las flags de calidad se añaden si aplican (`baseline_unreliable`).

---

## 9. Golden customers (12)

| ID | Escenario | Variables clave | IF | Baseline | Intervenir | top_factors | Canal | Explicación |
|---|---|---|---|---|---|---|---|---|
| G01 | S0 estable | balance_ratio 3.2, vs_hist 1.05, income_var 0.02, punct 1.0, resp_rate 0.8 | score ~0.2 | p ~0.05 | **No** | (ninguno) | — | Cliente asalariado normal. Referencia. |
| G02 | **S0 "no molestar"** (anomalía benigna) | balance_ratio 6.0, income_var **+1.8** (bono), expense_var 0.4, punct 1.0 | **anómalo** (~0.7) | p ~0.08 | **No** | income_variation_pos | — | Demuestra: anomalía ≠ riesgo. Reglas → S0, human_review_flag, NO_CONTACT. |
| G03 | S1 fricción crónica | balance_ratio 2.5, hist_balance_at_due alto, punct 0.33, delay_avg 3, delay_dev 0, app_logins 12 | score bajo (~0.3): es su patrón | p ~0.45 | Sí, suave | payment_delay_unusual? no → `low_punctuality`, `balance_ok` | APP_PUSH | Tiene dinero, olvida. Recordatorio + pago rápido. |
| G04 | S1 paga al límite | balance_ratio 1.4, days_before_due_avg −0.5, punct 0.5, resp_rate 0.9 push | ~0.3 | p ~0.35 | Sí, suave | low_punctuality | APP_PUSH | Responde a push; recordatorio 3 días antes. |
| G05 | S2 asalariado día 30, cuota día 25 | balance_ratio 0.5, projected_cov 3.5, income_due_gap +5, punct 0.4, income_var 0 | ~0.4 | p ~0.55 | Sí | income_due_gap_positive, balance_ratio_low | APP_PUSH | El dinero llega 5 días tarde. Policy Engine → fechas permitidas. |
| G06 | S2 independiente, fecha incierta | income_type INDEPENDENT, income_day_std 7, expected_day null, balance_ratio 0.7, cv 0.4 | ~0.45 | p ~0.5 | Sí | balance_ratio_low, income_date_unknown | APP_PUSH | Prueba `income_date_unknown`: el LLM debe preguntar cuándo cobra, no asumir. |
| G07 | S3 caída de ingreso | income_var −0.4, balance_ratio 0.4, vs_hist 0.35, recent_drop 0.5, punct 0.85 hist | **~0.85** | p ~0.8 | Sí, empática | income_variation_neg, balance_vs_historical_low, balance_ratio_low | APP_PUSH → escalable | Buen pagador histórico con shock. Alternativas autorizadas. |
| G08 | S3 gasto + intentos fallidos | expense_var +0.5, velocity_7d 2.4, failed_30d 3, min_ratio 0.05, balance_ratio 0.6 | **~0.9** | p ~0.75 | Sí | failed_attempts_high, expense_variation_high, min_balance_low | APP_PUSH | "Intentó pagar y no pudo": señal más explicable. |
| G09 | S4 baja respuesta digital | contacts 6, answered 0 push/sms, calls 2/2 (tardes), balance_ratio 0.9, punct 0.5, app_engagement 0.2 | ~0.4 | p ~0.45 | Sí, **cambiar canal** | low_contact_response, balance_ratio_low | **CALL** 17:00-18:30 | El canal habitual falla; NBA cambia canal y hora, reduce insistencia. |
| G10 | S2 + S4 híbrido | gap +7, projected_cov 2, resp_rate 0.1, last_outcome IGNORED, days_since_contact 2 | ~0.4 | p ~0.55 | **Todavía no** (cap de contacto) | income_due_gap_positive, low_contact_response | SMS (siguiente no probado) | Prueba regla anti-insistencia: esperar 3 días y cambiar canal. |
| G11 | S3 + S4 → humano | income_var −0.5, balance_ratio 0.2, failed 4, resp_rate 0.0, partial_payments 2 | **~0.95** | p ~0.9 | Sí → **HUMAN_ESCALATION** | balance_ratio_low, income_variation_neg, failed_attempts_high, low_contact_response | CALL humano | Riesgo alto y sin respuesta digital: la IA no negocia sola. |
| G12 | Cliente nuevo sin historial | tenure 1, hist_cycles 0, balance_ratio 2.0, todas las desviaciones imputadas neutras, baseline_unreliable 1 | ~mediana | p ~0.2 | **No** | baseline_unreliable | — | Prueba que la imputación neutra no genera falsos positivos. |

Los golden se generan con valores fijos (no muestreados) y se excluyen del train.

---

## 10. Casos extremos / adversariales

| Caso | Tratamiento |
|---|---|
| `income_last_30d = 0` | Válido. `income_variation = −1` (clip). Si `income_hist_avg` también 0 → variación 0 + `baseline_unreliable`. Marca S3 solo si `balance_ratio < 1`. |
| `current_balance = 0` | Válido. `balance_ratio = 0`, `recent_balance_drop` con `balance_14d_ago` normal. Caso S3 claro. |
| `installment_amount = 0` | Solo en test. Ratios → NaN; `has_missing_core=1`; `score_customer` retorna `risk_level = "N/A"`, `should_contact = false`, `nba_reason = "sin obligación activa"`. Nunca dividir. |
| Faltantes en features core | Imputación según §4 + flag; si faltan > 3 features P0 → `has_missing_core`, no se puntúa, `human_review_flag`. |
| Ingreso extremadamente alto (×20) | Clip en `income_variation` (máx 3) y log1p. IF lo marcará anómalo → reglas → S0 + `income_variation_pos` → NO_CONTACT (mismo mecanismo que G02). |
| Gasto extremadamente alto | Clip a 3 / 5. Si `balance_ratio ≥ 1` → S0 con review; si < 1 → S3. |
| Cliente nuevo | G12. `hist_cycles_available = 0` → líneas base neutras, `baseline_unreliable`, K-Means lo excluye. |
| Pocos contactos históricos (< 3) | `contact_response_rate = NaN`, `contact_history_insufficient=1`, nunca S4; `best_channel = UNKNOWN` → fallback APP_PUSH si `push_enabled`. |
| Fecha de ingreso desconocida | `income_due_gap = NaN`, `income_date_unknown=1`; regla S2 no aplica; LR usa `income_due_gap_pos = 0`; NBA instruye al LLM a preguntar. |
| Valores fuera de rango (saldo negativo, tasa > 1, delay −5) | Validación previa con esquema (pandera/pydantic): rechazar fila o clip con registro en `data_quality_log`. En demo: clip + flag `out_of_range`. |
| Pago ya realizado | `current_cycle_paid = 1` → compuerta; no se puntúa; dashboard muestra "resuelto". |
| Varios intentos fallidos (≥ 5) | Clip a 10 en features; `failed_attempts_high` en top_factors; prioridad alta en NBA; si `balance_ratio ≥ 1` (fallo técnico, no de fondos) → `recommended_action = CHANNEL_SWITCH` a soporte, no cobranza. |

---

## 11. Listas definitivas

### 11.1 Columnas del CSV maestro (`customers_snapshot.csv`)

**Identificación/demo:** `customer_id, full_name_mock, dui_mock, phone_mock, account_id_mock, credit_id_mock, customer_since_date`
**Temporales:** `snapshot_date, cycle_id, next_due_date, days_to_due, days_elapsed_in_cycle, tenure_months`
**Financieras actuales:** `current_balance, balance_14d_ago, avg_balance_30d, min_balance_30d`
**Históricas:** `hist_cycles_available, hist_avg_balance, hist_std_balance, hist_avg_balance_at_due`
**Ingresos:** `income_type, income_last_30d, income_hist_avg, income_hist_std, income_expected_day, income_day_std, last_income_date, next_expected_income_date, days_since_last_income`
**Gastos:** `expenses_last_30d, expenses_last_7d, expenses_hist_avg`
**Obligación:** `product_type, installment_amount, due_day, remaining_installments, loan_remaining_balance, current_cycle_paid`
**Pagos:** `payments_observed_n, on_time_payments_n, payment_delay_avg, payment_delay_max, payment_delay_std, last_payment_delay_days, partial_payments_n, failed_payment_attempts_30d, failed_attempts_hist_avg, max_days_in_arrears_12m`
**Contactos:** `contacts_sent_90d, contacts_answered_90d, app_push_sent_90d, app_push_opened_90d, sms_sent_90d, sms_replied_90d, calls_attempted_90d, calls_answered_90d, contacts_last_7d, last_contact_date, last_contact_channel, last_contact_outcome, days_since_last_contact, opt_out_flag`
**Digital:** `app_logins_30d, app_logins_hist_avg, last_app_login_date, days_since_last_login, push_enabled, activity_hour_mode, activity_events_90d`
**Intervenciones:** `prior_interventions_n, prior_interventions_accepted_n, last_intervention_type, last_intervention_outcome, last_intervention_date`
**Derivadas:** `balance_ratio, min_balance_ratio_30d, projected_coverage, balance_vs_historical, recent_balance_drop, income_variation, income_amount_cv, income_timing_regularity, income_due_gap, expense_variation_30d, spending_velocity_7d, payment_punctuality, last_payment_delay_deviation, failed_attempts_deviation, contact_response_rate, channel_response_rate_app, channel_response_rate_sms, channel_response_rate_call, best_channel, app_engagement_ratio, preferred_time_window`
**Flags:** `baseline_unreliable, income_date_unknown, contact_history_insufficient, has_missing_core, out_of_range`
**Etiqueta:** `synthetic_late_payment_next_cycle`
**Trazabilidad:** `dataset_version, generator_seed`

(Outputs de ML y NBA van en `model_outputs/scores.csv`, no en el maestro. Golden/generador en archivos aparte.)

### 11.2 Features de Isolation Forest (10)
`balance_vs_historical, recent_balance_drop, balance_ratio, min_balance_ratio_30d, income_variation, expense_variation_30d, spending_velocity_7d, failed_payment_attempts_30d, last_payment_delay_deviation, failed_attempts_deviation`

### 11.3 Features de Logistic Regression (10 + 1 opcional)
`balance_ratio, projected_coverage, balance_vs_historical, income_variation, expense_variation_30d, payment_punctuality, partial_payments_n, failed_payment_attempts_30d, income_due_gap_pos, income_amount_cv` (+ `tenure_months`)

### 11.4 Excluidas del ML
Todo §3, más: `avg_balance_30d, hist_std_balance, hist_avg_balance_at_due, income_day_std/income_timing_regularity (solo regla), days_since_*, contacts_*, app_*, push_enabled, activity_*, best_channel, preferred_time_window, product_type, income_type (salvo K-Means), remaining_installments, loan_remaining_balance, prior_interventions_*, last_intervention_*, flags de calidad` (las flags sí van a top_factors).

### 11.5 Estructura de carpetas
```
ba_a_tiempo_data/
├── config/
│   ├── generator_config.yaml       # seed, N clientes, proporciones S0–S4, ventanas (6 ciclos, 90 d)
│   └── feature_definitions.yaml    # fórmulas, clips, imputaciones, versión
├── data/
│   ├── raw_synthetic/              # history_panel.csv, payments_log.csv, contacts_log.csv
│   ├── processed/                  # customers_snapshot.csv, if_features.parquet, lr_features.parquet
│   ├── golden/                     # golden_customers.csv, edge_cases.csv
│   └── generator_state/            # latent_stress_index, synthetic_situation_truth  (NUNCA a modelos)
├── docs/
│   ├── data_dictionary.md          # este documento §2–§4
│   └── assumptions_demo.md         # lista de SUPUESTOS DE DEMO
├── models/
│   ├── isolation_forest_v1.joblib
│   ├── logreg_v1.joblib
│   └── scaler_lr_v1.joblib
├── outputs/
│   ├── scores.csv                  # customer_id + §O + §P
│   ├── validation_report.md        # AUC, matriz situation_hint vs truth, golden asserts
│   └── data_quality_log.csv
└── tests/
    ├── test_golden.py
    └── test_edge_cases.py
```

### 11.6 Contrato para Celeste (backend) — `score_customer` → JSON
`customer_id, snapshot_date, days_to_due, next_due_date, installment_amount, current_cycle_paid, opt_out_flag, risk_score, risk_level, anomaly_score, anomaly_flag, situation_hint, low_digital_response, top_factors[], nba_reason, should_contact, recommended_action, recommended_channel, preferred_time_window, best_channel, contacts_last_7d, days_since_last_contact, income_date_unknown, baseline_unreliable, human_review_flag, model_version, scored_at`
Más, para el Policy Engine (contexto, no decisión): `income_due_gap, projected_coverage, next_expected_income_date, balance_ratio, remaining_installments, prior_interventions_accepted_n, last_intervention_type`.

### 11.7 Contrato para Camila (dashboard)
Todo 11.6 menos ratios internos, más: `full_name_mock, dui_mock, product_type, current_balance, income_last_30d, expenses_last_30d, payment_punctuality, contact_response_rate, last_contact_channel, last_contact_outcome, intervention_status, intervention_outcome, escalated_to_human, conversation_id_mock, policy_decision_id, is_golden, golden_scenario, scoring_run_id, dataset_version`.
Agregados sugeridos: distribución de `situation_hint`, % NO_CONTACT (la métrica "sabe cuándo no molestar"), embudo `intervention_status`, tasa de aceptación por `recommended_action`, canal más efectivo.

### 11.8 Priorización

**P0 (imprescindibles):** `customer_id, snapshot_date, next_due_date, days_to_due, current_balance, balance_14d_ago, min_balance_30d, hist_cycles_available, hist_avg_balance, income_type, income_last_30d, income_hist_avg, income_expected_day, next_expected_income_date, expenses_last_30d, expenses_hist_avg, installment_amount, due_day, current_cycle_paid, payments_observed_n, on_time_payments_n, payment_delay_avg, last_payment_delay_days, failed_payment_attempts_30d, contacts_sent_90d, contacts_answered_90d, contacts_last_7d, last_contact_date, opt_out_flag, app_logins_30d, last_app_login_date, push_enabled`, las 10 features IF y 10 LR, la etiqueta, los flags, `generator_seed`, y todo §O/§P marcado P0.

**P1 (útiles):** `full_name_mock, dui_mock, credit_id_mock, customer_since_date/tenure_months, avg_balance_30d, hist_std_balance, hist_avg_balance_at_due, income_hist_std, income_day_std, last_income_date, expenses_last_7d, product_type, payment_delay_max, payment_delay_std, partial_payments_n, failed_attempts_hist_avg`, contadores por canal, `last_contact_channel/outcome, app_logins_hist_avg, activity_hour_mode, activity_events_90d, preferred_time_window`, intervenciones previas, `human_review_flag, conversation_id_mock, policy_decision_id`.

**P2 (opcionales):** `phone_mock, account_id_mock, income_deposits_6m, expenses_hist_std, remaining_installments, loan_remaining_balance, days_before_due_avg, max_days_in_arrears_12m, last_intervention_date, cluster_id, anomaly_score_raw, tenure_months en LR`.

---

## 12. Lista de SUPUESTOS DE DEMO (para decirlos explícitamente ante el jurado)
Ventana histórica de 6 ciclos y 90 d de contactos · umbral de etiqueta ≥ 3 días o parcial · `income_expected_day = null` si `income_day_std > 5` · contamination 0.10 · cortes de `risk_level` 0.35/0.65 · pesos 0.6/0.4 de `risk_score` · cap de 2 contactos/7 d y 3 días entre contactos · ventana de intervención 1–10 días antes del vencimiento · umbrales de las reglas S1–S4 · distribuciones y parámetros del generador · imputación neutra para clientes nuevos.
