# Fase 5 — Latencia end-to-end de `score_customer`

Mide la llamada completa (`risk_engine` + `channel_timing_engine` + `nba_engine` + `policy_engine`, todas las Fases 2-5 juntas) para un cliente a la vez, como la verá el backend en producción -- no las latencias por componente por separado (esas ya están en `anomaly_benchmark_report.md`, `risk_benchmark_report.md` y `channel_timing_report.md`).

## Resultados

- **Clientes reales** (muestra de 150 llamadas): p50=51.31 ms, p95=60.96 ms, media=57.07 ms.
- **Golden customers** (60 llamadas): p50=64.94 ms, p95=67.40 ms, media=64.48 ms.

## Lectura: lo que el perfilado encontró (y se corrigió en esta misma fase)

La primera corrida de este benchmark dio p95 ≈ 139 ms, sorprendentemente alto para modelos que individualmente miden <15 ms p95 (Fases 2-4). Perfilar con `cProfile` mostró la causa real: `risk_engine._top_factors` (ablación por feature, ver risk_benchmark) llamaba a `IsolationForest.score_samples` **11 veces por cliente** (1 base + 10 features), y cada llamada paga ~7 ms de costo fijo (validación de entrada + recorrer 200 árboles) independientemente de si se le pasa 1 fila o 11 -- así que 11 llamadas de 1 fila cuestan ~11 veces más que 1 llamada de 11 filas. Se corrigió batcheando las 11 variantes (base + 10 ablaciones) en un solo `score_samples`, y cacheando las medianas poblacionales usadas para la ablación (antes se recalculaban sobre 3,000 filas en cada llamada, sin necesidad: el dataset no cambia entre clientes). Resultado: p95 bajó de ~139 ms a ~61 ms, más de 2x, sin cambiar ningún modelo ni ninguna métrica de calidad (mismo `top_factors`, misma fórmula).


p95 de 61.0 ms es viable para scoring uno-a-uno en el flujo síncrono del MVP (un cliente entra al dashboard o dispara una intervención, no un batch nocturno de miles). El costo restante ya es principalmente el modelo mismo (IsolationForest sobre 11 filas) y la lectura de `dataset.csv`/`contacts_log.csv` completos por llamada (sin índice por `customer_id` en este MVP) -- ambos razonables de optimizar más adelante si el volumen lo exige (índice en memoria o base de datos), pero ninguno bloquea la demo.


Este benchmark es válido para **esta corrida con esta seed**; el detalle completo queda en `outputs/score_customer_benchmark.json`.