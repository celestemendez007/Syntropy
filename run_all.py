"""
run_all.py — Fase 8: script único para correr todo el pipeline, de punta a punta.

Orden (cada paso depende del anterior -- no se pueden reordenar):
  1. Generador sintético (Fase 1)                  -> research/ba_a_tiempo/data/
  2. Benchmark de anomalías (Fase 2)                -> anomaly_benchmark_report.md
  3. Benchmark de riesgo supervisado (Fase 3)        -> risk_benchmark_report.md
  4. Benchmark de canal y momento (Fase 4)           -> channel_timing_report.md
  5. Sincroniza los modelos ganadores + datos a src/ml/models y data/synthetic
     (producción lee de ahí, no de research/)
  6. Golden conversations (Fase 6)                   -> golden_conversations.csv
  7. Conversaciones/intervenciones sintéticas (Fase 7) -> conversations_log.csv, interventions_log.csv
  8. Recalcula la tabla de prioridades NBA (Fase 7)  -> nba_priority_table.csv
  9. Benchmark end-to-end de score_customer (Fase 5) -> score_customer_benchmark_report.md
  10. Exporta dashboard_data.json (Fase 8)           -> src/frontend/public/data/
  11. Corre toda la suite de tests (research + backend/ml)

Uso: `python run_all.py` desde la raíz del repo. Tarda unos minutos (el benchmark
de riesgo entrena LightGBM, el más lento de los tres).
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT / "research" / "ba_a_tiempo"
SRC_ML = ROOT / "src" / "ml"
SRC_BACKEND = ROOT / "src" / "backend"
DATA_SYNTHETIC = ROOT / "data" / "synthetic"

PYTHON = sys.executable


def _step(title: str):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def _run(code: str, cwd: Path):
    t0 = time.perf_counter()
    result = subprocess.run([PYTHON, "-c", code], cwd=str(cwd))
    if result.returncode != 0:
        print(f"FALLÓ (código {result.returncode}) -- abortando run_all.py", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"OK ({time.perf_counter() - t0:.1f}s)")


def _run_script(args: list, cwd: Path):
    t0 = time.perf_counter()
    result = subprocess.run([PYTHON] + args, cwd=str(cwd))
    if result.returncode != 0:
        print(f"FALLÓ (código {result.returncode}) -- abortando run_all.py", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"OK ({time.perf_counter() - t0:.1f}s)")


def _run_pytest(cwd: Path):
    t0 = time.perf_counter()
    result = subprocess.run([PYTHON, "-m", "pytest", "tests/", "-q"], cwd=str(cwd))
    if result.returncode != 0:
        print(f"Tests fallaron en {cwd} (código {result.returncode}) -- abortando run_all.py", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"OK ({time.perf_counter() - t0:.1f}s)")


def sync_production_artifacts():
    """Copia lo que Fases 1-4 decidieron como ganador hacia donde src/ lee en
    producción. No hay automatización de "cuál ganó" -- eso lo dice cada
    *_report.md; esta función asume que la decisión (Isolation Forest,
    Logistic Regression, el modelo de canal) no ha cambiado desde que se
    escribieron esos reportes."""
    pairs = [
        (RESEARCH / "data" / "processed" / "customers_snapshot.csv", DATA_SYNTHETIC / "dataset.csv"),
        (RESEARCH / "data" / "golden" / "golden_customers.csv", DATA_SYNTHETIC / "golden_customers.csv"),
        (RESEARCH / "data" / "raw_synthetic" / "contacts_log.csv", DATA_SYNTHETIC / "contacts_log.csv"),
        (RESEARCH / "models" / "anomaly_IsolationForest.joblib", SRC_ML / "models" / "anomaly_IsolationForest.joblib"),
        (RESEARCH / "models" / "anomaly_ZScore_Mahalanobis.joblib", SRC_ML / "models" / "anomaly_ZScore_Mahalanobis.joblib"),
        (RESEARCH / "models" / "anomaly_scaler.joblib", SRC_ML / "models" / "anomaly_scaler.joblib"),
        (RESEARCH / "models" / "risk_LogisticRegression.joblib", SRC_ML / "models" / "risk_LogisticRegression.joblib"),
        (RESEARCH / "models" / "risk_scaler.joblib", SRC_ML / "models" / "risk_scaler.joblib"),
        (RESEARCH / "models" / "risk_feature_order.json", SRC_ML / "models" / "risk_feature_order.json"),
        (RESEARCH / "models" / "channel_pref_v1.joblib", SRC_ML / "models" / "channel_pref_v1.joblib"),
        (RESEARCH / "models" / "timing_stats_v1.json", SRC_ML / "models" / "timing_stats_v1.json"),
    ]
    for src, dst in pairs:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
        print(f"  {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")


def main():
    t_start = time.perf_counter()

    _step("1-2. Generador sintético + benchmark de anomalías (Fases 1-2)")
    _run(
        "from ba_a_tiempo import generator as G; G.run_all(); "
        "from ba_a_tiempo import anomaly_benchmark as AB; r, s = AB.run_benchmark(); AB.build_report(r, s)",
        cwd=RESEARCH,
    )

    _step("3. Benchmark de riesgo supervisado: LR vs Random Forest vs LightGBM (Fase 3)")
    _run(
        "from ba_a_tiempo import risk_benchmark as RB; r, s = RB.run_benchmark(); RB.build_report(r, s)",
        cwd=RESEARCH,
    )

    _step("4. Benchmark de canal y momento (Fase 4)")
    _run(
        "from ba_a_tiempo import channel_timing as CT; r = CT.run_benchmark(); CT.build_report(r)",
        cwd=RESEARCH,
    )

    _step("5. Sincronizando modelos ganadores y datos hacia src/ (producción)")
    sync_production_artifacts()

    _step("6. Golden conversations (Fase 6)")
    _run_script(["build_golden_conversations.py"], cwd=SRC_BACKEND)

    _step("7. Conversaciones e intervenciones sintéticas (Fase 6-7, ~1,800 clientes)")
    _run_script(["build_synthetic_conversations.py"], cwd=SRC_BACKEND)

    _step("8. Recalculando la tabla de prioridades del NBA (Fase 7, 'botón recalcular')")
    _run_script(["nba_priority.py"], cwd=SRC_BACKEND)

    _step("9. Benchmark end-to-end de score_customer (Fase 5)")
    _run_script(["score_customer.py", "--benchmark"], cwd=SRC_BACKEND)

    _step("10. Exportando dashboard_data.json para el frontend (Fase 8)")
    _run_script(["export_dashboard_data.py"], cwd=SRC_BACKEND)

    _step("11. Suite de tests (research/ba_a_tiempo + backend/ml)")
    _run_pytest(RESEARCH)
    _run_pytest(ROOT)

    print(f"\nListo en {time.perf_counter() - t_start:.1f}s. "
          f"Dashboard: cd src/frontend && npm run dev (o npm run build).")


if __name__ == "__main__":
    main()
