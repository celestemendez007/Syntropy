"""Genera docs/data_dictionary.md a partir de las columnas reales de dataset.csv,
para que el diccionario nunca se desalinee del dato real (ver Fase 2: un desajuste
así costó un bug de NaN en el benchmark de anomalía)."""
import pandas as pd

DESCRIPTIONS = {
    "customer_id": "Identificador único del cliente (ficticio).",
    "hist_avg_balance": "Saldo promedio histórico (línea base propia del cliente, 6 ciclos).",
    "hist_std_balance": "Desviación estándar del saldo histórico.",
    "hist_avg_balance_at_due": "Saldo promedio el día de vencimiento en ciclos pasados.",
    "income_hist_avg": "Ingreso mensual promedio histórico.",
    "expenses_hist_avg": "Gasto mensual promedio histórico.",
    "installment_amount": "Monto de la cuota mensual.",
    "on_time_payments_n": "Pagos a tiempo en la ventana histórica.",
    "payments_observed_n": "Pagos observados en la ventana histórica.",
    "payment_delay_avg": "Retraso promedio histórico (días).",
    "payment_delay_max": "Retraso máximo histórico (días).",
    "payment_delay_std": "Variabilidad del retraso histórico.",
    "failed_attempts_hist_avg": "Intentos de pago fallidos promedio por ciclo (histórico).",
    "income_type": "Tipo de ingreso: SALARIED, BIWEEKLY, INDEPENDENT, UNKNOWN.",
    "income_day_std": "Variabilidad del día de ingreso (días).",
    "income_expected_day": "Día esperado de ingreso; null si es muy variable.",
    "due_day": "Día de vencimiento de la cuota.",
    "nomina_en_banco_mock": "Si la nómina se deposita en el banco (dato duro de fecha si true). SUPUESTO DE DEMO.",
    "income_last_30d": "Ingreso de los últimos 30 días.",
    "expenses_last_30d": "Gasto de los últimos 30 días.",
    "expenses_last_7d": "Gasto de los últimos 7 días.",
    "current_balance": "Saldo disponible actual.",
    "balance_14d_ago": "Saldo hace 14 días.",
    "min_balance_30d": "Saldo mínimo observado en 30 días.",
    "avg_balance_30d": "Saldo promedio en 30 días.",
    "failed_payment_attempts_30d": "Intentos de pago fallidos en los últimos 30 días.",
    "partial_payments_n": "Pagos parciales en la ventana histórica.",
    "last_payment_delay_days": "Retraso del último pago (días).",
    "hist_cycles_available": "Cantidad de ciclos históricos disponibles (confianza de la línea base).",
    "tenure_months": "Antigüedad del cliente en meses.",
    "external_debt_ratio_mock": "Deuda externa / ingreso (buró ficticio). SUPUESTO DE DEMO.",
    "next_due_date": "Próxima fecha de vencimiento.",
    "next_expected_income_date": "Próxima fecha esperada de ingreso; null si es desconocida.",
    "days_to_due": "Días al vencimiento (negativo = ya vencido). NO es feature de ML, es timing.",
    "contacts_sent_90d": "Contactos enviados en 90 días.",
    "contacts_answered_90d": "Contactos respondidos en 90 días.",
    "opt_out_flag": "Cliente rechazó explícitamente ser contactado.",
    "current_cycle_paid": "La cuota actual ya fue pagada (compuerta: si true, no se puntúa).",
    "app_logins_30d": "Ingresos a la app en los últimos 30 días.",
    "app_logins_hist_avg": "Ingresos promedio a la app por mes (histórico).",
    "push_enabled": "Notificaciones push activas.",
    "activity_events_90d": "Eventos de actividad en la app en 90 días.",
    "days_since_last_login": "Días desde el último ingreso a la app.",
    "days_since_last_contact": "Días desde el último contacto.",
    "balance_ratio": "current_balance / installment_amount. Cuántas cuotas cubre el saldo hoy.",
    "min_balance_ratio_30d": "min_balance_30d / installment_amount. Si tocó fondo durante el mes.",
    "projected_coverage": "Cobertura proyectada incluyendo ingreso esperado antes del vencimiento.",
    "balance_vs_historical": "current_balance / hist_avg_balance. Saldo vs. su propia normalidad.",
    "recent_balance_drop": "Velocidad de caída del saldo en 14 días.",
    "income_variation": "Desviación del ingreso actual vs. su promedio histórico.",
    "income_amount_cv": "Coeficiente de variación del monto de ingreso (estabilidad).",
    "expense_variation_30d": "Desviación del gasto de 30 días vs. su promedio histórico.",
    "spending_velocity_7d": "Ritmo de gasto de la última semana vs. semana típica.",
    "payment_punctuality": "Fracción de pagos históricos a tiempo.",
    "last_payment_delay_deviation": "Retraso del último pago menos su retraso promedio (¿se salió de su propio patrón?).",
    "failed_attempts_deviation": "Intentos fallidos actuales menos su promedio histórico.",
    "income_due_gap": "Días que el ingreso esperado llega después del vencimiento (positivo = tarde).",
    "income_due_gap_pos": "max(0, income_due_gap). Usado como feature de LR (evita valores centinela negativos).",
    "income_date_unknown": "Flag: la fecha de ingreso no se pudo estimar con confianza.",
    "baseline_unreliable": "Flag: menos de 3 ciclos históricos, líneas base imputadas de forma neutra.",
    "contact_history_insufficient": "Flag: menos de 2 contactos en 90 días, tasa de respuesta no confiable.",
    "contact_response_rate": "contacts_answered_90d / contacts_sent_90d.",
    "app_engagement_ratio": "app_logins_30d / app_logins_hist_avg. Uso de la app vs. su norma.",
    "synthetic_late_payment_next_cycle": "ETIQUETA SINTÉTICA (0/1). Generada con variable latente oculta + ruido. "
                                          "Nunca es feature de entrada, solo target de validación del pipeline.",
    "has_missing_core": "Flag: faltan features P0 core, cliente no se puntúa.",
    "full_name_mock": "Nombre ficticio para demo/UI. Nunca es feature de ML.",
    "dui_mock": "DUI ficticio (patrón DUI-DEMO-######), inequívocamente falso. Nunca es feature de ML.",
    "dataset_version": "Versión del dataset sintético.",
    "generator_seed": "Seed usada para generar los datos (reproducibilidad).",
    "snapshot_date": "Fecha de corte de la generación.",
}

IF_FEATURES = {
    "balance_vs_historical", "recent_balance_drop", "balance_ratio", "min_balance_ratio_30d",
    "income_variation", "expense_variation_30d", "spending_velocity_7d",
    "failed_payment_attempts_30d", "last_payment_delay_deviation", "failed_attempts_deviation",
}
LR_FEATURES_PENDING = {  # definidas en el diseño, LR aún no integrada (Fase 3 pendiente)
    "balance_ratio", "projected_coverage", "balance_vs_historical", "income_variation",
    "expense_variation_30d", "payment_punctuality", "partial_payments_n",
    "failed_payment_attempts_30d", "income_due_gap_pos", "income_amount_cv", "external_debt_ratio_mock",
}
FORBIDDEN = {
    "synthetic_late_payment_next_cycle", "customer_id", "full_name_mock", "dui_mock",
    "current_cycle_paid", "days_to_due",
}


def main():
    df = pd.read_csv("data/synthetic/dataset.csv")
    lines = [
        "# Diccionario de Datos (Dataset Sintético) — v2",
        "",
        "> **Nota:** Todos estos datos son generados artificialmente y no reflejan información real "
        "de Bancoagrícola. Se usan exclusivamente para simular las entradas a los modelos de riesgo.",
        "",
        f"> Generado automáticamente desde `data/synthetic/dataset.csv` ({len(df)} clientes, "
        f"{len(df.columns)} columnas) por `docs/generate_data_dictionary.py`, para que nunca se "
        "desalinee del dato real. No editar a mano — editar el script y volver a correr.",
        "",
        "Reemplaza la versión anterior (9 columnas: `days_to_due, balance_ratio, income_variation, "
        "spending_velocity, payment_delay_avg, reminder_response, failed_attempts, risk_level`), que "
        "era el esquema del mock. Ver `docs/contracts.md` para el JSON de salida del motor de riesgo.",
        "",
        "| Variable | Tipo | Usada en | Descripción |",
        "| :--- | :--- | :--- | :--- |",
    ]
    for col in df.columns:
        dtype = str(df[col].dtype)
        uso = []
        if col in IF_FEATURES:
            uso.append("Isolation Forest")
        if col in LR_FEATURES_PENDING:
            uso.append("LR (pendiente Fase 3)")
        if col in FORBIDDEN:
            uso.append("**PROHIBIDA como feature**")
        uso_str = ", ".join(uso) if uso else "—"
        desc = DESCRIPTIONS.get(col, "_(pendiente de documentar)_")
        lines.append(f"| `{col}` | {dtype} | {uso_str} | {desc} |")

    lines += [
        "",
        "## Variables prohibidas como features (data leakage)",
        "",
        "`synthetic_late_payment_next_cycle` (es la etiqueta), `customer_id`/`full_name_mock`/`dui_mock` "
        "(identidad), `current_cycle_paid` (compuerta, no feature), `days_to_due` (timing de scoring, no "
        "comportamiento). Ver `research/ba_a_tiempo/BA_A_Tiempo_Diseno_Dataset_v1.md` §3 para la lista "
        "completa y el razonamiento.",
        "",
        "## Estado de los modelos",
        "",
        "- **Isolation Forest:** real, entrenado sobre 3,000 clientes sintéticos. "
        "Ver `research/ba_a_tiempo/outputs/anomaly_benchmark_report.md`.",
        "- **Logistic Regression / LightGBM (riesgo supervisado):** diseñadas, **no integradas aún** "
        "(Fase 3 pendiente). `src/ml/risk_engine.py` usa `anomaly_score` como proxy interino de "
        "`risk_score`, marcado explícitamente en el código y en el JSON de salida (`_pending`).",
        "- **`situation_hint`:** reglas deterministas, reales, ya integradas.",
    ]
    with open("docs/data_dictionary.md", "w") as f:
        f.write("\n".join(lines))
    print(f"Escrito docs/data_dictionary.md con {len(df.columns)} columnas documentadas "
          f"({sum(1 for c in df.columns if c in DESCRIPTIONS)} con descripción real).")


if __name__ == "__main__":
    main()
