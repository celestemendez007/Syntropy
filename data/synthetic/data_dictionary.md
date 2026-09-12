# Diccionario de Datos (Dataset Sintético)

> **Nota:** Todos estos datos son generados artificialmente y no reflejan información real de Bancoagrícola. Se utilizan exclusivamente para simular las entradas a los modelos de riesgo.

| Variable | Tipo | Descripción |
| :--- | :--- | :--- |
| `customer_id` | String | Identificador único del cliente. |
| `days_to_due` | Integer | Días restantes para el vencimiento de la cuota actual. |
| `balance_ratio` | Float | Proporción del saldo en cuenta respecto al monto de la cuota esperada. |
| `income_variation` | Float | Porcentaje de variación de los ingresos de este mes respecto al promedio de los últimos 3 meses. |
| `spending_velocity` | Float | Velocidad de gasto en los últimos 7 días. Valores altos indican estrés de liquidez. |
| `payment_delay_avg` | Float | Promedio histórico de días de atraso. |
| `reminder_response` | Float | Tasa de respuesta o apertura de notificaciones en la app (0.0 a 1.0). |
| `failed_attempts` | Integer | Número de intentos fallidos de cobro automático recientes. |
| `risk_level` | Categorical | Etiqueta sintética asignada para validación del baseline (`LOW`, `MEDIUM`, `HIGH`). |
