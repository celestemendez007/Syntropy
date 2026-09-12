# Diccionario de Datos (Dataset Sintético) — v2

> **Nota:** Todos estos datos son generados artificialmente y no reflejan información real de Bancoagrícola. Se usan exclusivamente para simular las entradas a los modelos de riesgo.

> Generado automáticamente desde `data/synthetic/dataset.csv` (3000 clientes, 70 columnas) por `docs/generate_data_dictionary.py`, para que nunca se desalinee del dato real. No editar a mano — editar el script y volver a correr.

Reemplaza la versión anterior (9 columnas: `days_to_due, balance_ratio, income_variation, spending_velocity, payment_delay_avg, reminder_response, failed_attempts, risk_level`), que era el esquema del mock. Ver `docs/contracts.md` para el JSON de salida del motor de riesgo.

| Variable | Tipo | Usada en | Descripción |
| :--- | :--- | :--- | :--- |
| `customer_id` | str | **PROHIBIDA como feature** | Identificador único del cliente (ficticio). |
| `hist_avg_balance` | float64 | — | Saldo promedio histórico (línea base propia del cliente, 6 ciclos). |
| `hist_std_balance` | float64 | — | Desviación estándar del saldo histórico. |
| `hist_avg_balance_at_due` | float64 | — | Saldo promedio el día de vencimiento en ciclos pasados. |
| `income_hist_avg` | float64 | — | Ingreso mensual promedio histórico. |
| `expenses_hist_avg` | float64 | — | Gasto mensual promedio histórico. |
| `installment_amount` | float64 | — | Monto de la cuota mensual. |
| `on_time_payments_n` | int64 | — | Pagos a tiempo en la ventana histórica. |
| `payments_observed_n` | int64 | — | Pagos observados en la ventana histórica. |
| `payment_delay_avg` | float64 | — | Retraso promedio histórico (días). |
| `payment_delay_max` | int64 | — | Retraso máximo histórico (días). |
| `payment_delay_std` | float64 | — | Variabilidad del retraso histórico. |
| `failed_attempts_hist_avg` | float64 | — | Intentos de pago fallidos promedio por ciclo (histórico). |
| `income_type` | str | — | Tipo de ingreso: SALARIED, BIWEEKLY, INDEPENDENT, UNKNOWN. |
| `income_day_std` | float64 | — | Variabilidad del día de ingreso (días). |
| `income_expected_day` | float64 | — | Día esperado de ingreso; null si es muy variable. |
| `due_day` | int64 | — | Día de vencimiento de la cuota. |
| `nomina_en_banco_mock` | bool | — | Si la nómina se deposita en el banco (dato duro de fecha si true). SUPUESTO DE DEMO. |
| `income_last_30d` | float64 | — | Ingreso de los últimos 30 días. |
| `expenses_last_30d` | float64 | — | Gasto de los últimos 30 días. |
| `expenses_last_7d` | float64 | — | Gasto de los últimos 7 días. |
| `current_balance` | float64 | — | Saldo disponible actual. |
| `balance_14d_ago` | float64 | — | Saldo hace 14 días. |
| `min_balance_30d` | float64 | — | Saldo mínimo observado en 30 días. |
| `avg_balance_30d` | float64 | — | Saldo promedio en 30 días. |
| `failed_payment_attempts_30d` | int64 | Isolation Forest, LR (pendiente Fase 3) | Intentos de pago fallidos en los últimos 30 días. |
| `partial_payments_n` | int64 | LR (pendiente Fase 3) | Pagos parciales en la ventana histórica. |
| `last_payment_delay_days` | int64 | — | Retraso del último pago (días). |
| `hist_cycles_available` | int64 | — | Cantidad de ciclos históricos disponibles (confianza de la línea base). |
| `tenure_months` | int64 | — | Antigüedad del cliente en meses. |
| `external_debt_ratio_mock` | float64 | LR (pendiente Fase 3) | Deuda externa / ingreso (buró ficticio). SUPUESTO DE DEMO. |
| `next_due_date` | str | — | Próxima fecha de vencimiento. |
| `next_expected_income_date` | str | — | Próxima fecha esperada de ingreso; null si es desconocida. |
| `days_to_due` | int64 | **PROHIBIDA como feature** | Días al vencimiento (negativo = ya vencido). NO es feature de ML, es timing. |
| `contacts_sent_90d` | int64 | — | Contactos enviados en 90 días. |
| `contacts_answered_90d` | int64 | — | Contactos respondidos en 90 días. |
| `opt_out_flag` | bool | — | Cliente rechazó explícitamente ser contactado. |
| `current_cycle_paid` | bool | **PROHIBIDA como feature** | La cuota actual ya fue pagada (compuerta: si true, no se puntúa). |
| `app_logins_30d` | int64 | — | Ingresos a la app en los últimos 30 días. |
| `app_logins_hist_avg` | float64 | — | Ingresos promedio a la app por mes (histórico). |
| `push_enabled` | bool | — | Notificaciones push activas. |
| `activity_events_90d` | int64 | — | Eventos de actividad en la app en 90 días. |
| `days_since_last_login` | int64 | — | Días desde el último ingreso a la app. |
| `days_since_last_contact` | int64 | — | Días desde el último contacto. |
| `balance_ratio` | float64 | Isolation Forest, LR (pendiente Fase 3) | current_balance / installment_amount. Cuántas cuotas cubre el saldo hoy. |
| `min_balance_ratio_30d` | float64 | Isolation Forest | min_balance_30d / installment_amount. Si tocó fondo durante el mes. |
| `projected_coverage` | float64 | LR (pendiente Fase 3) | Cobertura proyectada incluyendo ingreso esperado antes del vencimiento. |
| `balance_vs_historical` | float64 | Isolation Forest, LR (pendiente Fase 3) | current_balance / hist_avg_balance. Saldo vs. su propia normalidad. |
| `recent_balance_drop` | float64 | Isolation Forest | Velocidad de caída del saldo en 14 días. |
| `income_variation` | float64 | Isolation Forest, LR (pendiente Fase 3) | Desviación del ingreso actual vs. su promedio histórico. |
| `income_amount_cv` | float64 | LR (pendiente Fase 3) | Coeficiente de variación del monto de ingreso (estabilidad). |
| `expense_variation_30d` | float64 | Isolation Forest, LR (pendiente Fase 3) | Desviación del gasto de 30 días vs. su promedio histórico. |
| `spending_velocity_7d` | float64 | Isolation Forest | Ritmo de gasto de la última semana vs. semana típica. |
| `payment_punctuality` | float64 | LR (pendiente Fase 3) | Fracción de pagos históricos a tiempo. |
| `last_payment_delay_deviation` | float64 | Isolation Forest | Retraso del último pago menos su retraso promedio (¿se salió de su propio patrón?). |
| `failed_attempts_deviation` | float64 | Isolation Forest | Intentos fallidos actuales menos su promedio histórico. |
| `income_due_gap` | float64 | — | Días que el ingreso esperado llega después del vencimiento (positivo = tarde). |
| `income_due_gap_pos` | float64 | LR (pendiente Fase 3) | max(0, income_due_gap). Usado como feature de LR (evita valores centinela negativos). |
| `income_date_unknown` | int64 | — | Flag: la fecha de ingreso no se pudo estimar con confianza. |
| `baseline_unreliable` | int64 | — | Flag: menos de 3 ciclos históricos, líneas base imputadas de forma neutra. |
| `contact_history_insufficient` | int64 | — | Flag: menos de 2 contactos en 90 días, tasa de respuesta no confiable. |
| `contact_response_rate` | float64 | — | contacts_answered_90d / contacts_sent_90d. |
| `app_engagement_ratio` | float64 | — | app_logins_30d / app_logins_hist_avg. Uso de la app vs. su norma. |
| `synthetic_late_payment_next_cycle` | int64 | **PROHIBIDA como feature** | ETIQUETA SINTÉTICA (0/1). Generada con variable latente oculta + ruido. Nunca es feature de entrada, solo target de validación del pipeline. |
| `has_missing_core` | int64 | — | Flag: faltan features P0 core, cliente no se puntúa. |
| `full_name_mock` | str | **PROHIBIDA como feature** | Nombre ficticio para demo/UI. Nunca es feature de ML. |
| `dui_mock` | str | **PROHIBIDA como feature** | DUI ficticio (patrón DUI-DEMO-######), inequívocamente falso. Nunca es feature de ML. |
| `dataset_version` | str | — | Versión del dataset sintético. |
| `generator_seed` | int64 | — | Seed usada para generar los datos (reproducibilidad). |
| `snapshot_date` | str | — | Fecha de corte de la generación. |

## Variables prohibidas como features (data leakage)

`synthetic_late_payment_next_cycle` (es la etiqueta), `customer_id`/`full_name_mock`/`dui_mock` (identidad), `current_cycle_paid` (compuerta, no feature), `days_to_due` (timing de scoring, no comportamiento). Ver `research/ba_a_tiempo/BA_A_Tiempo_Diseno_Dataset_v1.md` §3 para la lista completa y el razonamiento.

## Estado de los modelos

- **Isolation Forest:** real, entrenado sobre 3,000 clientes sintéticos. Ver `research/ba_a_tiempo/outputs/anomaly_benchmark_report.md`.
- **Logistic Regression / LightGBM (riesgo supervisado):** diseñadas, **no integradas aún** (Fase 3 pendiente). `src/ml/risk_engine.py` usa `anomaly_score` como proxy interino de `risk_score`, marcado explícitamente en el código y en el JSON de salida (`_pending`).
- **`situation_hint`:** reglas deterministas, reales, ya integradas.