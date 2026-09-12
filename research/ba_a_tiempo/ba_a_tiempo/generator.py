"""
Generador sintético reproducible para BA A Tiempo.

Produce:
  - generator_state.parquet   (variable latente z, situación verdadera, afinidades) -> NUNCA a modelos
  - history_panel.csv         (cliente x ciclo, 6 ciclos)
  - payments_log.csv          (agregados por cliente derivados del panel)
  - contacts_log.csv          (contactos con canal/hora/anticipación/respuesta)
  - customers_snapshot.csv    (1 fila/cliente, CSV MAESTRO para ML)
  - golden_customers.csv      (12 casos fijos, fuera del entrenamiento)

Todo con --seed fijo: misma seed -> mismo output (verificado en tests).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from . import config as C

RNG_GLOBAL_NOTE = "Todas las distribuciones son SUPUESTO DE DEMO, ver docs/assumptions_demo.md"


def _situation_params(sit: str) -> dict:
    """Parámetros del generador por situación (beta de z, shocks). SUPUESTO DE DEMO."""
    return {
        "S0": dict(z_a=1.5, z_b=8.0, income_shift=0.0, expense_shift=0.0, delay_p=0.05, fail_lambda=0.05),
        "S1": dict(z_a=2.0, z_b=6.0, income_shift=0.0, expense_shift=0.05, delay_p=0.5, fail_lambda=0.15),
        "S2": dict(z_a=3.0, z_b=5.0, income_shift=-0.05, expense_shift=0.05, delay_p=0.4, fail_lambda=0.2),
        "S3": dict(z_a=6.0, z_b=2.5, income_shift=-0.30, expense_shift=0.30, delay_p=0.6, fail_lambda=1.2),
        "S4": dict(z_a=2.0, z_b=5.0, income_shift=-0.05, expense_shift=0.05, delay_p=0.3, fail_lambda=0.2),
    }[sit]


def _draw_income_type(rng):
    return rng.choice(["SALARIED", "BIWEEKLY", "INDEPENDENT", "UNKNOWN"], p=[0.55, 0.15, 0.22, 0.08])


def generate_generator_state(n: int, rng: np.random.Generator) -> pd.DataFrame:
    """Variables ocultas: situación verdadera, z (presión), afinidades de canal/hora/anticipación."""
    situations = rng.choice(list(C.SITUATION_MIX), size=n, p=list(C.SITUATION_MIX.values()))
    rows = []
    for i, sit in enumerate(situations):
        p = _situation_params(sit)
        z = rng.beta(p["z_a"], p["z_b"])
        # afinidad de canal: Dirichlet con un canal dominante aleatorio
        dirichlet_alpha = np.ones(4)
        dom = rng.integers(0, 4)
        dirichlet_alpha[dom] += rng.uniform(2, 6)
        # 30% de clientes con afinidad plana (sin canal claro)
        if rng.random() < 0.30:
            dirichlet_alpha = np.ones(4) * 3
        affinity = rng.dirichlet(dirichlet_alpha)
        hour_star = rng.uniform(7, 21)
        days_star = rng.uniform(2, 8)
        rows.append(dict(
            customer_id=f"C{i+1:05d}", synthetic_situation_truth=sit, latent_stress_index=z,
            income_shift=p["income_shift"], expense_shift=p["expense_shift"],
            delay_p=p["delay_p"], fail_lambda=p["fail_lambda"],
            aff_app=affinity[0], aff_sms=affinity[1], aff_whatsapp=affinity[2], aff_call=affinity[3],
            hour_star=hour_star, days_star=days_star,
        ))
    return pd.DataFrame(rows)


def generate_history_panel(state: pd.DataFrame, rng: np.random.Generator, n_cycles: int = C.HIST_CYCLES) -> pd.DataFrame:
    """Panel cliente x ciclo: la línea base propia de cada cliente."""
    rows = []
    for _, r in state.iterrows():
        income_hist_avg = rng.lognormal(mean=6.6, sigma=0.5)
        cv = rng.uniform(0.03, 0.08) if r["fail_lambda"] < 0.5 else rng.uniform(0.15, 0.35)
        expenses_hist_avg = income_hist_avg * rng.uniform(0.55, 0.95)
        installment = income_hist_avg * rng.uniform(0.10, 0.40)
        for c in range(n_cycles):
            balance_at_due = max(0.0, rng.normal(installment * rng.uniform(1.0, 3.0), installment * 0.3))
            on_time = rng.random() > r["delay_p"]
            delay = 0 if on_time else max(1, int(rng.gamma(2.5, 2.0)))
            rows.append(dict(
                customer_id=r["customer_id"], cycle=c,
                income=max(0.0, rng.normal(income_hist_avg, income_hist_avg * cv)),
                expenses=max(0.0, rng.normal(expenses_hist_avg, expenses_hist_avg * 0.12)),
                avg_balance=max(0.0, rng.normal(income_hist_avg * 0.7, income_hist_avg * 0.25)),
                balance_at_due=balance_at_due, installment_amount=installment,
                on_time=on_time, payment_delay=delay,
                failed_attempts=rng.poisson(0.1),
                income_hist_avg=income_hist_avg, expenses_hist_avg=expenses_hist_avg,
            ))
    return pd.DataFrame(rows)


def _safe_div(a, b, default=np.nan):
    return np.where(np.abs(b) > 1e-6, a / np.where(np.abs(b) > 1e-6, b, 1), default)


def build_customers_snapshot(state: pd.DataFrame, panel: pd.DataFrame, rng: np.random.Generator,
                              snapshot_date: str = C.SNAPSHOT_DATE) -> pd.DataFrame:
    snap_date = datetime.strptime(snapshot_date, "%Y-%m-%d")
    agg = panel.groupby("customer_id").agg(
        hist_avg_balance=("avg_balance", "mean"), hist_std_balance=("avg_balance", "std"),
        hist_avg_balance_at_due=("balance_at_due", "mean"),
        income_hist_avg=("income_hist_avg", "first"), expenses_hist_avg=("expenses_hist_avg", "first"),
        installment_amount=("installment_amount", "first"),
        on_time_payments_n=("on_time", "sum"), payments_observed_n=("on_time", "count"),
        payment_delay_avg=("payment_delay", "mean"), payment_delay_max=("payment_delay", "max"),
        payment_delay_std=("payment_delay", "std"), failed_attempts_hist_avg=("failed_attempts", "mean"),
    ).reset_index()
    agg["payment_delay_std"] = agg["payment_delay_std"].fillna(0.0)
    agg["hist_std_balance"] = agg["hist_std_balance"].fillna(0.0)

    df = state.merge(agg, on="customer_id", how="left")
    n = len(df)

    df["income_type"] = [_draw_income_type(rng) for _ in range(n)]
    df["income_day_std"] = np.where(df["income_type"] == "INDEPENDENT", rng.uniform(3, 12, n), rng.uniform(0, 2, n))
    df["income_expected_day"] = np.where(df["income_day_std"] > 5, np.nan, rng.integers(1, 29, n))
    df["due_day"] = rng.choice([5, 10, 15, 20, 25, 30], size=n)
    df["nomina_en_banco_mock"] = rng.random(n) < 0.6
    df.loc[df["nomina_en_banco_mock"], "income_expected_day"] = rng.integers(1, 29, df["nomina_en_banco_mock"].sum())

    # ingreso/gasto actuales (shock por z)
    income_shock = rng.normal(df["income_shift"], 0.10)
    expense_shock = rng.normal(df["expense_shift"], 0.10)
    df["income_last_30d"] = np.clip(df["income_hist_avg"] * (1 + income_shock), 0, None)
    df["expenses_last_30d"] = np.clip(df["expenses_hist_avg"] * (1 + expense_shock), 0, None)
    df["expenses_last_7d"] = df["expenses_last_30d"] / 4.3 * (1 + rng.normal(0, 0.15, n))

    df["current_balance"] = np.clip(df["hist_avg_balance"].fillna(df["income_hist_avg"] * 0.5) *
                                     (1 - rng.beta(2 + df["latent_stress_index"] * 6, 8, n)), 0, None)
    drop = rng.beta(2, 8, n) + df["latent_stress_index"] * 0.3
    df["balance_14d_ago"] = df["current_balance"] / np.clip(1 - drop, 0.05, 0.95)
    df["min_balance_30d"] = df["avg_balance_30d"] = df["current_balance"] * rng.uniform(0.5, 1.0, n)

    df["failed_payment_attempts_30d"] = rng.poisson(df["fail_lambda"])
    df["partial_payments_n"] = rng.binomial(C.HIST_CYCLES, np.clip(df["latent_stress_index"] * 0.3, 0, 1))
    df["last_payment_delay_days"] = np.clip(rng.normal(df["payment_delay_avg"], 1.5), 0, None).round().astype(int)
    df["hist_cycles_available"] = C.HIST_CYCLES
    df["tenure_months"] = rng.integers(1, 120, n)
    new_mask = rng.random(n) < 0.05
    df.loc[new_mask, "tenure_months"] = rng.integers(1, 5, int(new_mask.sum()))

    df["external_debt_ratio_mock"] = np.where(
        df["synthetic_situation_truth"] == "S3", rng.beta(4, 3, n) * 2.0, rng.beta(2, 5, n) * 1.5)

    # fechas de ingreso
    df["next_due_date"] = [snap_date.replace(day=min(int(d), 28)) if snap_date.day <= d
                            else (snap_date.replace(day=1) + timedelta(days=32)).replace(day=min(int(d), 28))
                            for d in df["due_day"]]
    df["next_expected_income_date"] = [
        (snap_date.replace(day=min(int(d), 28)) if not np.isnan(d) else pd.NaT)
        for d in df["income_expected_day"]]
    df["days_to_due"] = (df["next_due_date"] - snap_date).dt.days

    # contacto/digital (agregados 90d, simplificado a partir de afinidades)
    contacts_sent = rng.poisson(np.where(df["synthetic_situation_truth"] == "S4", 6, 3))
    resp_p = np.clip(df[["aff_app", "aff_sms", "aff_whatsapp", "aff_call"]].max(axis=1) * 0.9, 0.02, 0.95)
    resp_p = np.where(df["synthetic_situation_truth"] == "S4", resp_p * 0.2, resp_p)
    df["contacts_sent_90d"] = contacts_sent
    df["contacts_answered_90d"] = rng.binomial(np.maximum(contacts_sent, 0), resp_p)
    df["opt_out_flag"] = rng.random(n) < 0.03
    df["current_cycle_paid"] = rng.random(n) < np.where(df["days_to_due"] < 5, 0.25, 0.0)

    df["app_logins_30d"] = rng.poisson(np.where(df["synthetic_situation_truth"] == "S4", 1, 8))
    df["app_logins_hist_avg"] = np.clip(rng.normal(df["app_logins_30d"], 2), 0.1, None)
    df["push_enabled"] = rng.random(n) < 0.8
    df["activity_events_90d"] = df["app_logins_30d"] * 3
    df["days_since_last_login"] = rng.integers(0, 30, n)
    df["days_since_last_contact"] = rng.integers(0, 90, n)

    # ---- features derivadas ----
    inst = df["installment_amount"].replace(0, np.nan)
    df["balance_ratio"] = np.clip(_safe_div(df["current_balance"], inst), 0, 10)
    df["min_balance_ratio_30d"] = np.clip(_safe_div(df["min_balance_30d"], inst), 0, 10)
    income_before_due = np.where(df["next_expected_income_date"].notna() &
                                  (df["next_expected_income_date"] <= df["next_due_date"]),
                                  df["income_last_30d"], 0)
    df["projected_coverage"] = np.clip(_safe_div(df["current_balance"] + income_before_due, inst), 0, 10)
    hist_bal = df["hist_avg_balance"].replace(0, np.nan)
    df["balance_vs_historical"] = np.clip(_safe_div(df["current_balance"], hist_bal, default=1.0), 0, 5)
    df["recent_balance_drop"] = np.clip(
        _safe_div(df["balance_14d_ago"] - df["current_balance"], df["balance_14d_ago"], default=0.0), -1, 1)
    hist_inc = df["income_hist_avg"].replace(0, np.nan)
    df["income_variation"] = np.clip(_safe_div(df["income_last_30d"] - df["income_hist_avg"], hist_inc, 0.0), -1, 3)
    df["income_amount_cv"] = (df["income_hist_avg"] * 0 + df["income_day_std"] * 0)  # placeholder overwritten below
    hist_exp = df["expenses_hist_avg"].replace(0, np.nan)
    df["expense_variation_30d"] = np.clip(
        _safe_div(df["expenses_last_30d"] - df["expenses_hist_avg"], hist_exp, 0.0), -1, 3)
    df["spending_velocity_7d"] = np.clip(_safe_div(df["expenses_last_7d"], df["expenses_hist_avg"] / 4.3, 1.0), 0, 5)
    df["payment_punctuality"] = _safe_div(df["on_time_payments_n"], df["payments_observed_n"], 0.8)
    df["last_payment_delay_deviation"] = df["last_payment_delay_days"] - df["payment_delay_avg"].fillna(0)
    df["failed_attempts_deviation"] = df["failed_payment_attempts_30d"] - df["failed_attempts_hist_avg"].fillna(0)
    df["income_due_gap"] = np.clip(
        (df["next_expected_income_date"] - df["next_due_date"]).dt.days.fillna(-99), -15, 15)
    df["income_due_gap_pos"] = np.where(df["income_due_gap"] == -99, 0, np.maximum(0, df["income_due_gap"]))
    df["income_date_unknown"] = df["next_expected_income_date"].isna().astype(int)
    df["baseline_unreliable"] = (df["hist_cycles_available"] < 3).astype(int)
    df["contact_history_insufficient"] = (df["contacts_sent_90d"] < 2).astype(int)
    df["contact_response_rate"] = _safe_div(df["contacts_answered_90d"], df["contacts_sent_90d"], np.nan)
    df["app_engagement_ratio"] = np.clip(_safe_div(df["app_logins_30d"], df["app_logins_hist_avg"], 1.0), 0, 5)

    # income_amount_cv real: dispersión mensual simulada (SUPUESTO DE DEMO, ligado a income_type)
    cv_map = {"SALARIED": 0.06, "BIWEEKLY": 0.06, "INDEPENDENT": 0.30, "UNKNOWN": 0.20}
    df["income_amount_cv"] = df["income_type"].map(cv_map) * rng.uniform(0.7, 1.3, n)

    # ---- etiqueta sintética (no circular): depende de z + señales, con ruido ----
    z = df["latent_stress_index"]
    logit = (-2.2 + 3.0 * z + 0.8 * (df["income_due_gap_pos"] > 0).astype(float)
             + 1.5 * (1 - df["payment_punctuality"]) + 0.6 * (df["synthetic_situation_truth"] == "S1").astype(float)
             + rng.normal(0, 0.5, n))
    p_late = 1 / (1 + np.exp(-logit))
    label = rng.binomial(1, p_late)
    flip = rng.random(n) < 0.04
    df[C.LABEL] = np.where(flip, 1 - label, label)

    # flags de calidad y demográficos ficticios
    df["has_missing_core"] = 0
    df["full_name_mock"] = "Cliente Demo " + df["customer_id"].str.replace("C", "")
    df["dui_mock"] = "DUI-DEMO-" + df["customer_id"].str.replace("C", "")
    df["dataset_version"] = "synth_v1"
    df["generator_seed"] = C.SEED
    df["snapshot_date"] = snapshot_date
    df.rename(columns={"synthetic_situation_truth": "_truth_situation"}, inplace=True)  # se separa en generator_state

    keep_state_cols = ["customer_id", "_truth_situation", "latent_stress_index",
                        "aff_app", "aff_sms", "aff_whatsapp", "aff_call", "hour_star", "days_star"]
    gen_state = df[keep_state_cols].rename(columns={"_truth_situation": "synthetic_situation_truth"})

    drop_cols = ["income_shift", "expense_shift", "delay_p", "fail_lambda",
                 "aff_app", "aff_sms", "aff_whatsapp", "aff_call", "hour_star", "days_star",
                 "latent_stress_index", "_truth_situation"]
    snapshot = df.drop(columns=[c for c in drop_cols if c in df.columns])
    return snapshot, gen_state


def generate_contacts_log(snapshot: pd.DataFrame, gen_state: pd.DataFrame, rng: np.random.Generator,
                           snapshot_date: str = C.SNAPSHOT_DATE, lookback_days: int = 90) -> pd.DataFrame:
    """Log de contactos individuales usando la afinidad oculta -> target `responded`."""
    snap_date = datetime.strptime(snapshot_date, "%Y-%m-%d")
    merged = snapshot[["customer_id", "contacts_sent_90d"]].merge(gen_state, on="customer_id", how="left")
    rows, cid = [], 0
    channel_names = ["APP_PUSH", "SMS", "WHATSAPP", "CALL"]
    for _, r in merged.iterrows():
        n_sent = int(r["contacts_sent_90d"])
        affinities = np.array([r["aff_app"], r["aff_sms"], r["aff_whatsapp"], r["aff_call"]])
        for _ in range(n_sent):
            ch_idx = rng.choice(4, p=affinities)
            channel = channel_names[ch_idx]
            days_before = int(np.clip(rng.normal(r["days_star"], 2), -5, 15))
            hour = int(np.clip(rng.normal(r["hour_star"], 3), 0, 23))
            sent_at = snap_date - timedelta(days=int(rng.integers(0, lookback_days)))
            sent_at = sent_at.replace(hour=hour)
            p = 1 / (1 + np.exp(-(-1 + 2 * affinities[ch_idx]
                                   - 0.15 * abs(hour - r["hour_star"]) - 0.2 * abs(days_before - r["days_star"]))))
            responded = rng.random() < p
            outcome = "ANSWERED" if responded else rng.choice(["IGNORED", "REJECTED", "BOUNCED"], p=[0.8, 0.15, 0.05])
            rows.append(dict(
                contact_id=f"CT-{cid:06d}", customer_id=r["customer_id"], channel=channel,
                sent_at=sent_at, hour_sent=hour, days_before_due_at_contact=days_before,
                responded=responded, responded_within_hours=(round(float(rng.exponential(2)), 2) if responded else None),
                outcome=outcome,
            ))
            cid += 1
    return pd.DataFrame(rows)


GOLDEN_SPECS = [
    dict(id="G01", scenario="S0_estable", situation="S0", overrides=dict(
        balance_ratio=3.2, balance_vs_historical=1.05, income_variation=0.02, payment_punctuality=1.0,
        contact_response_rate=0.8, expected_intervene=False)),
    dict(id="G02", scenario="S0_no_molestar_anomalia_benigna", situation="S0", overrides=dict(
        balance_ratio=6.0, income_variation=1.8, expense_variation_30d=0.4, payment_punctuality=1.0,
        expected_intervene=False, expected_anomalous=True)),
    dict(id="G03", scenario="S1_friccion_cronica", situation="S1", overrides=dict(
        balance_ratio=2.5, payment_punctuality=0.33, payment_delay_avg=3, last_payment_delay_deviation=0,
        expected_intervene=True)),
    dict(id="G04", scenario="S1_paga_al_limite", situation="S1", overrides=dict(
        balance_ratio=1.4, payment_punctuality=0.5, expected_intervene=True)),
    dict(id="G05", scenario="S2_asalariado_dia30", situation="S2", overrides=dict(
        balance_ratio=0.5, projected_coverage=3.5, income_due_gap=5, income_due_gap_pos=5,
        payment_punctuality=0.4, expected_intervene=True)),
    dict(id="G06", scenario="S2_independiente_fecha_incierta", situation="S2", overrides=dict(
        income_type="INDEPENDENT", income_day_std=7, balance_ratio=0.7, income_amount_cv=0.4,
        income_date_unknown=1, expected_intervene=True)),
    dict(id="G07", scenario="S3_caida_ingreso", situation="S3", overrides=dict(
        income_variation=-0.4, balance_ratio=0.4, balance_vs_historical=0.35, recent_balance_drop=0.5,
        payment_punctuality=0.85, expected_intervene=True)),
    dict(id="G08", scenario="S3_gasto_mas_intentos_fallidos", situation="S3", overrides=dict(
        expense_variation_30d=0.5, spending_velocity_7d=2.4, failed_payment_attempts_30d=3,
        min_balance_ratio_30d=0.05, balance_ratio=0.6, expected_intervene=True)),
    dict(id="G09", scenario="S4_baja_respuesta_digital", situation="S4", overrides=dict(
        contacts_sent_90d=6, contact_response_rate=0.0, balance_ratio=0.9, payment_punctuality=0.5,
        app_engagement_ratio=0.2, expected_intervene=True)),
    dict(id="G10", scenario="S2_S4_hibrido", situation="S2", overrides=dict(
        balance_ratio=0.6, income_due_gap=7, income_due_gap_pos=7, projected_coverage=2, contact_response_rate=0.1,
        days_since_last_contact=2, expected_intervene=False)),
    dict(id="G11", scenario="S3_S4_escalar_humano", situation="S3", overrides=dict(
        income_variation=-0.5, balance_ratio=0.2, failed_payment_attempts_30d=4, contact_response_rate=0.0,
        partial_payments_n=2, expected_intervene=True, expected_escalation=True)),
    dict(id="G12", scenario="cliente_nuevo_sin_historial", situation="S0", overrides=dict(
        tenure_months=1, hist_cycles_available=0, balance_ratio=2.0, baseline_unreliable=1,
        expected_intervene=False)),
]


def build_golden_customers(snapshot_columns: list[str]) -> pd.DataFrame:
    """Construye los 12 golden customers con valores fijos (no muestreados)."""
    base_defaults = dict(
        income_type="SALARIED", installment_amount=200.0, income_hist_avg=750.0, expenses_hist_avg=550.0,
        current_balance=500.0, balance_14d_ago=520.0, min_balance_30d=400.0, avg_balance_30d=450.0,
        hist_avg_balance=500.0, hist_std_balance=50.0, hist_avg_balance_at_due=300.0,
        income_last_30d=750.0, expenses_last_30d=550.0, expenses_last_7d=128.0,
        payment_delay_avg=0.5, payment_delay_max=2, payment_delay_std=0.5,
        last_payment_delay_days=0, failed_payment_attempts_30d=0, failed_attempts_hist_avg=0.1,
        partial_payments_n=0, on_time_payments_n=5, payments_observed_n=6, hist_cycles_available=6,
        income_due_gap=-5, income_due_gap_pos=0, income_amount_cv=0.06, income_date_unknown=0,
        balance_ratio=2.0, projected_coverage=2.5, balance_vs_historical=1.0, recent_balance_drop=0.0,
        min_balance_ratio_30d=1.5, income_variation=0.0, expense_variation_30d=0.0, spending_velocity_7d=1.0,
        payment_punctuality=0.9,
        last_payment_delay_deviation=0, failed_attempts_deviation=0, baseline_unreliable=0,
        contact_history_insufficient=0, contact_response_rate=0.6, app_engagement_ratio=1.0,
        contacts_sent_90d=3, contacts_answered_90d=2, opt_out_flag=False, current_cycle_paid=False,
        app_logins_30d=8, app_logins_hist_avg=8.0, push_enabled=True, activity_events_90d=24,
        days_since_last_login=2, days_since_last_contact=10, external_debt_ratio_mock=0.3,
        nomina_en_banco_mock=True, has_missing_core=0, tenure_months=36, due_day=25,
        income_expected_day=25.0, days_to_due=7, dataset_version="synth_v1", generator_seed=C.SEED,
        snapshot_date=C.SNAPSHOT_DATE, next_due_date=pd.NaT, next_expected_income_date=pd.NaT,
    )
    rows = []
    for spec in GOLDEN_SPECS:
        row = dict(base_defaults)
        row["customer_id"] = f"GOLD-{spec['id']}"
        row["full_name_mock"] = f"Golden {spec['id']}"
        row["dui_mock"] = f"DUI-DEMO-GOLD-{spec['id']}"
        row[C.LABEL] = 0
        for k, v in spec["overrides"].items():
            row[k] = v
        row["is_golden"] = True
        row["golden_scenario"] = spec["scenario"]
        row["golden_expected_situation"] = spec["situation"]
        row["golden_expected_intervene"] = spec["overrides"].get("expected_intervene", None)
        row["golden_expected_escalation"] = spec["overrides"].get("expected_escalation", False)
        row["golden_expected_anomalous"] = spec["overrides"].get("expected_anomalous", False)
        rows.append(row)
    gdf = pd.DataFrame(rows)
    for col in snapshot_columns:
        if col not in gdf.columns:
            gdf[col] = np.nan
    return gdf


def run_all(seed: int = C.SEED, n: int = C.N_CUSTOMERS, out_dir: Path | None = None) -> dict:
    """Corre el generador completo y escribe todos los CSV. Retorna dict de DataFrames."""
    rng = np.random.default_rng(seed)
    C.RAW.mkdir(parents=True, exist_ok=True)
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    C.GOLDEN.mkdir(parents=True, exist_ok=True)
    C.GENSTATE.mkdir(parents=True, exist_ok=True)

    state = generate_generator_state(n, rng)
    panel = generate_history_panel(state, rng)
    snapshot, gen_state = build_customers_snapshot(state, panel, rng)
    contacts = generate_contacts_log(snapshot, gen_state, rng)
    golden = build_golden_customers(snapshot.columns.tolist())

    panel.to_csv(C.RAW / "history_panel.csv", index=False)
    contacts.to_csv(C.RAW / "contacts_log.csv", index=False)
    snapshot.to_csv(C.PROCESSED / "customers_snapshot.csv", index=False)
    golden.to_csv(C.GOLDEN / "golden_customers.csv", index=False)
    gen_state.to_csv(C.GENSTATE / "generator_state.csv", index=False)

    return dict(snapshot=snapshot, panel=panel, contacts=contacts, golden=golden, gen_state=gen_state)


if __name__ == "__main__":
    result = run_all()
    print("snapshot:", result["snapshot"].shape)
    print("panel:", result["panel"].shape)
    print("contacts:", result["contacts"].shape)
    print("golden:", result["golden"].shape)
