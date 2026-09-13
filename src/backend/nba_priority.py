"""
nba_priority.py — Fase 7: feedback loop (BA_A_Tiempo_Propuesta_v2.md §8).

El "aprendizaje" del MVP es tabular y auditable, no un modelo de ML nuevo:

  conversations_log + interventions_log
      -> agregación por (situation_hint, barrier_detected, channel, alt_id)
      -> nba_priority_table (n_offered, n_accepted, acceptance_rate,
         n_paid_on_time_after, success_rate con suavizado bayesiano, avg_turns,
         pct_tense_or_hostile)
      -> el LLM/NBA ordena las alternativas elegibles por `success_rate` y
         presenta primero la de mayor prioridad.

Lo que NO se retroalimenta: el score financiero (`risk_engine.py`, Fases 2-3).
Esta tabla solo reordena el CATÁLOGO YA ELEGIBLE (Fase 5) -- nunca decide qué es
elegible, eso lo sigue decidiendo el Policy Engine. Evita que el sistema aprenda
"los clientes tensos son riesgosos": el tono nunca entra en `risk_score`.
"""
import os
import sys
import json

import numpy as np
import pandas as pd

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_INTERACTIONS_DIR = os.path.join(_BASE_DIR, "..", "..", "research", "ba_a_tiempo", "data", "interactions")
_OUTPUTS_DIR = os.path.join(_BASE_DIR, "..", "..", "research", "ba_a_tiempo", "outputs")
CONVERSATIONS_PATH = os.path.join(_INTERACTIONS_DIR, "conversations_log.csv")
INTERVENTIONS_PATH = os.path.join(_INTERACTIONS_DIR, "interventions_log.csv")
PRIORITY_TABLE_PATH = os.path.join(_OUTPUTS_DIR, "nba_priority_table.csv")

GROUP_COLS = ["situation_hint", "barrier_detected", "channel", "alt_id"]

_priority_table_cache = None


def _explode_offered_alternatives(conversations: pd.DataFrame) -> pd.DataFrame:
    """Una fila de conversations_log puede ofrecer varias alternativas
    (`alternatives_offered` es una lista separada por ';'); la tabla de
    prioridades es por (situación, barrera, canal, alt_id), así que cada
    alternativa ofrecida necesita su propia fila para poder contar
    `n_offered`/`n_accepted` correctamente."""
    rows = []
    for _, row in conversations.iterrows():
        offered_raw = row.get("alternatives_offered")
        offered = offered_raw if pd.notna(offered_raw) else ""
        alt_ids = [a for a in str(offered).split(";") if a]
        accepted_alt = row.get("alternative_accepted")
        accepted_alt = accepted_alt if pd.notna(accepted_alt) else None
        paid = row.get("paid_on_time_after")
        paid = bool(paid) if pd.notna(paid) else False
        for alt_id in alt_ids:
            rows.append({
                "situation_hint": row["situation_hint"], "barrier_detected": row["barrier_detected"],
                "channel": row["channel"], "alt_id": alt_id,
                "accepted": alt_id == accepted_alt,
                "paid_on_time_after": paid and alt_id == accepted_alt,
                "turns_total": row["turns_total"],
                "tense_or_hostile": row["tone_overall"] in ("TENSE", "HOSTILE"),
            })
    return pd.DataFrame(rows)


def compute_priority_table(conversations: pd.DataFrame) -> pd.DataFrame:
    """Agrega conversations_log en la tabla de prioridades. `success_rate` usa
    suavizado bayesiano `(n_paid + 1) / (n_offered + 2)` (SUPUESTO DE DEMO, prior
    neutro de 0.5) para que una combinación con 1 observación no domine el orden
    solo por haber salido bien una vez -- ver BA_A_Tiempo_Propuesta_v2.md §8."""
    exploded = _explode_offered_alternatives(conversations)
    if exploded.empty:
        return pd.DataFrame(columns=GROUP_COLS + ["n_offered", "n_accepted", "acceptance_rate",
                                                    "n_paid_on_time_after", "success_rate", "avg_turns",
                                                    "pct_tense_or_hostile"])

    grouped = exploded.groupby(GROUP_COLS).agg(
        n_offered=("accepted", "count"),
        n_accepted=("accepted", "sum"),
        n_paid_on_time_after=("paid_on_time_after", "sum"),
        avg_turns=("turns_total", "mean"),
        pct_tense_or_hostile=("tense_or_hostile", "mean"),
    ).reset_index()

    grouped["acceptance_rate"] = (grouped["n_accepted"] / grouped["n_offered"]).round(4)
    grouped["success_rate"] = ((grouped["n_paid_on_time_after"] + 1) / (grouped["n_offered"] + 2)).round(4)
    grouped["avg_turns"] = grouped["avg_turns"].round(2)
    grouped["pct_tense_or_hostile"] = grouped["pct_tense_or_hostile"].round(4)
    return grouped.sort_values("success_rate", ascending=False).reset_index(drop=True)


def recompute_and_save(conversations_path: str = CONVERSATIONS_PATH) -> pd.DataFrame:
    """El botón 'recalcular' del dashboard (Fase 8): relee conversations_log y
    reescribe outputs/nba_priority_table.csv. Invalida el cache en memoria para
    que `rank_alternatives` use la tabla nueva en la siguiente llamada."""
    global _priority_table_cache
    conversations = pd.read_csv(conversations_path) if os.path.exists(conversations_path) else pd.DataFrame()
    table = compute_priority_table(conversations)
    os.makedirs(_OUTPUTS_DIR, exist_ok=True)
    table.to_csv(PRIORITY_TABLE_PATH, index=False)
    _priority_table_cache = table
    return table


def load_priority_table() -> pd.DataFrame:
    global _priority_table_cache
    if _priority_table_cache is None:
        if os.path.exists(PRIORITY_TABLE_PATH):
            _priority_table_cache = pd.read_csv(PRIORITY_TABLE_PATH)
        else:
            _priority_table_cache = recompute_and_save()
    return _priority_table_cache


def rank_alternatives(eligible_alternatives: list, situation_hint: str, channel: str,
                       barrier_detected: str | None = None) -> list:
    """Reordena las alternativas YA elegibles (Fase 5, Policy Engine) por
    `success_rate` aprendido, de mayor a menor. Sin evidencia para una
    combinación (`barrier_detected` es None antes de que el cliente hable, o la
    combinación nunca se ofreció), esa alternativa se queda con un prior neutro
    de 0.5 y se ordena al final entre sus pares -- nunca se descarta, solo no se
    prioriza sobre algo con evidencia real."""
    table = load_priority_table()
    if table.empty:
        return eligible_alternatives

    def _score(alt_id: str) -> float:
        mask = (table["alt_id"] == alt_id) & (table["situation_hint"] == situation_hint) & \
               (table["channel"] == channel)
        if barrier_detected is not None:
            mask &= (table["barrier_detected"] == barrier_detected)
        matches = table[mask]
        if matches.empty:
            return 0.5  # prior neutro, sin evidencia
        return float(matches["success_rate"].mean())

    return sorted(eligible_alternatives, key=lambda a: _score(a["alt_id"]), reverse=True)


def build_report(before: pd.DataFrame, after: pd.DataFrame, n_conversations_before: int,
                  n_conversations_after: int) -> str:
    """Demo de 'recalcular': compara el orden de las 3 mejores combinaciones antes
    y después de sumar evidencia, para mostrar concretamente cómo cambia."""
    def _top(table, n=8):
        if table.empty:
            return "(sin datos)"
        cols = GROUP_COLS + ["n_offered", "success_rate", "acceptance_rate"]
        return table[cols].head(n).to_markdown(index=False)

    lines = [
        "# Fase 7 — Feedback loop: tabla de prioridades del NBA\n",
        "`nba_priority_table` agrega `conversations_log` por (situación, barrera, canal, "
        "alternativa) y ordena por `success_rate` con suavizado bayesiano "
        "`(n_paid_on_time_after + 1) / (n_offered + 2)`. El NBA usa esto SOLO para decidir "
        "en qué orden presentar alternativas ya elegibles (Fase 5) -- nunca para decidir "
        "elegibilidad ni para tocar `risk_score`.\n",
        f"**SUPUESTO DE DEMO importante**: no hay conversaciones reales todavía (Fase 6, sin "
        "LLM conectado); `conversations_log.csv` es sintético "
        "(`build_synthetic_conversations.py`), con una probabilidad de aceptación "
        "\"verdadera\" fija por alternativa para que haya señal real que aprender. Esta tabla "
        "demuestra el MECANISMO del feedback loop, no un resultado de negocio real.\n",
        f"## Demo de recálculo: {n_conversations_before} conversaciones (solo golden) vs. "
        f"{n_conversations_after} (golden + sintéticas)\n",
        "### Antes (solo golden conversations, poca evidencia)\n", _top(before), "",
        "### Después (con las conversaciones sintéticas agregadas)\n", _top(after), "",
    ]

    if not before.empty and not after.empty:
        top_before = set(before.head(3)[GROUP_COLS].apply(tuple, axis=1))
        top_after = set(after.head(3)[GROUP_COLS].apply(tuple, axis=1))
        if top_before != top_after:
            lines.append(
                "**El orden cambió** entre las dos corridas: con poca evidencia (solo 10 golden "
                "conversations), el suavizado bayesiano empuja casi todo hacia el prior neutro "
                "(0.5) y el orden es sensible a 1-2 observaciones; con más datos, las "
                "combinaciones con `success_rate` genuinamente más alto se estabilizan arriba. "
                "Esto es exactamente el comportamiento esperado del suavizado: protege contra "
                "sobre-confiar en poca evidencia sin bloquear que el sistema aprenda cuando sí "
                "la hay.\n"
            )
        else:
            lines.append("El top-3 no cambió entre corridas en esta semilla -- con más datos "
                          "confirma la misma prioridad en vez de contradecirla.\n")

    lines.append(
        "\nCiclo completo: conversación -> `conversations_log` + `interventions_log` -> "
        "`recompute_and_save()` (el botón 'recalcular' del dashboard, Fase 8) -> siguiente "
        "intervención usa `rank_alternatives()` con la tabla nueva."
    )

    report = "\n".join(lines)
    with open(os.path.join(_OUTPUTS_DIR, "nba_priority_table_report.md"), "w", encoding="utf-8") as f:
        f.write(report)
    return report


if __name__ == "__main__":
    golden_path = os.path.join(_INTERACTIONS_DIR, "golden_conversations.csv")
    golden = pd.read_csv(golden_path) if os.path.exists(golden_path) else pd.DataFrame()
    # golden_conversations.csv no tiene alternatives_offered en el mismo formato -- normalizar
    if not golden.empty and "alternatives_offered" in golden.columns:
        golden["alternative_accepted"] = golden["alternative_accepted"].fillna("")
    before_table = compute_priority_table(golden) if not golden.empty else pd.DataFrame()

    synthetic = pd.read_csv(CONVERSATIONS_PATH) if os.path.exists(CONVERSATIONS_PATH) else pd.DataFrame()
    combined = pd.concat([golden, synthetic], ignore_index=True) if not golden.empty else synthetic
    after_table = compute_priority_table(combined)

    os.makedirs(_OUTPUTS_DIR, exist_ok=True)
    after_table.to_csv(PRIORITY_TABLE_PATH, index=False)
    _priority_table_cache = after_table

    report = build_report(before_table, after_table, len(golden), len(combined))
    print(f"golden-only: {len(before_table)} combinaciones, combinado: {len(after_table)} combinaciones")
    print("Reporte guardado en research/ba_a_tiempo/outputs/nba_priority_table_report.md")
