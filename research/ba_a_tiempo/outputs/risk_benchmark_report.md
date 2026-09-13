# Fase 3 — Benchmark de riesgo supervisado

Comparación sobre las mismas 10 features (`config.LR_FEATURES`), mismo train/test split (80/20, seed 42), etiqueta `synthetic_late_payment_next_cycle` (ver BA_A_Tiempo_Diseno_Dataset_v1.md §6 para el proceso generativo sin circularidad: la etiqueta depende de la variable latente `z` con ruido, no de una regla sobre las features). Golden customers excluidos siempre — su etiqueta es fija por construcción y no mide desempeño real.

Nota de calibración de la demo: el diseño esperaba AUC ~0.75–0.85 (`synthetic_late_payment_next_cycle` generado con ruido suficiente para que ningún modelo lo resuelva trivialmente). Un AUC ≈1.0 aquí sería síntoma de leakage; un AUC ≈0.5, de que el ruido añadido ahogó la señal.

## Resultados

| model              |    auc |   brier_score |   calibration_mae |   fit_time_s |   latency_p50_ms |   latency_p95_ms |   model_size_kb |   positive_rate_train |   positive_rate_test |
|:-------------------|-------:|--------------:|------------------:|-------------:|-----------------:|-----------------:|----------------:|----------------------:|---------------------:|
| LogisticRegression | 0.7369 |        0.213  |            0.1575 |        0.011 |            1.196 |            1.523 |             1.4 |                  0.35 |                0.345 |
| RandomForest       | 0.7214 |        0.216  |            0.1444 |        0.898 |           73.165 |           94.032 |          2224   |                  0.35 |                0.345 |
| LightGBM           | 0.6681 |        0.2248 |            0.1009 |        4.766 |            1.462 |            1.653 |           623.9 |                  0.35 |                0.345 |

`calibration_mae`: error absoluto medio entre la probabilidad predicha y la frecuencia observada por bin (10 bins por cuantiles) — mide si `risk_prob_lr` se puede leer como una probabilidad real ('de cada 10 clientes con 0.7, ¿pagan tarde 7?'), no solo si ordena bien a los clientes (eso lo mide el AUC).

## Lectura de los resultados (no solo el ranking)

- **Mejor AUC:** `LogisticRegression` (0.7369).
- **Mejor calibración (menor `calibration_mae`):** `LightGBM` (0.1009).
- **Menor Brier score:** `LogisticRegression` (0.213).
- **Menor latencia p95:** `LogisticRegression` (1.523 ms).
- **Modelo más pequeño:** `LogisticRegression` (1.4 KB).

**AUC vs. calibración no coinciden:** `LogisticRegression` separa mejor a los clientes que sí pagarán tarde de los que no (AUC), pero `LightGBM` es más confiable si el negocio necesita leer `risk_prob_lr` como una probabilidad literal (p. ej. para decidir un umbral de descuento proporcional al riesgo, no solo un ranking). Para el contrato v2, donde `risk_score` combina `risk_prob_lr` con `anomaly_score` en una fórmula lineal (§7 del diseño), la calibración importa tanto como el AUC: una probabilidad mal calibrada distorsiona esa combinación.

### Notas de explicabilidad

- **LogisticRegression:** Alta. `top_factors` = coeficiente × valor estandarizado del cliente; es una fórmula exacta, no una aproximación, y se puede mostrar en una frase ('balance_ratio bajo pesó 3x más que income_variation en este caso'). Es el modelo que el diseño (§8 de BA_A_Tiempo_Diseno_Dataset_v1.md) asume para `top_factors` de riesgo.
- **RandomForest:** Media. `feature_importances_` (basada en impureza) es global, no explica un cliente individual ni la dirección del efecto (solo 'cuánto importa', no 'sube o baja el riesgo'). Para explicación por cliente se necesita SHAP TreeExplainer; con ~300 árboles poco profundos (`max_depth=6`) el costo es aceptable pero ya no es una fórmula cerrada.
- **LightGBM:** Media-baja. Igual que Random Forest (importances globales, requiere SHAP para explicar un cliente), y con el añadido de que el boosting secuencial hace más difícil razonar manualmente por qué un árbol corrigió a otro. El costo de SHAP con boosting suele ser mayor que con bosques por el número de iteraciones.

### Veredicto (ponderando todos los criterios, no un solo número)

Con AUC de 0.7369 (Logistic Regression), 0.7214 (Random Forest) y 0.6681 (LightGBM), Logistic Regression no solo empata sino que **gana** en AUC pese a ser el modelo más simple — consistente con que la señal está en variables lineales-ish (`balance_ratio`, `income_variation`) más ruido bernoulli explícito (§6): con solo 3,000 clientes y 10 features, 300 árboles (`max_depth=6`) tienen capacidad de sobra para ajustar ruido en vez de señal real, mientras que la regularización L2 de LR actúa de barrera contra ese sobreajuste.

**Logistic Regression** es la recomendación para producción del MVP (`risk_prob_lr` en el contrato v2): mejor AUC de los tres pese a ser el más simple, mejor Brier score, la mejor explicabilidad (coeficiente × valor estandarizado es una fórmula exacta, no una aproximación — necesaria para que `top_factors` se pueda decir en una frase ante un jurado o un cliente), el modelo más chico (1.4 KB vs. más de 600 KB de LightGBM) y la latencia p95 más baja. Gana en casi todos los criterios sin ningún trade-off que justifique un modelo más caro y menos explicable.

**LightGBM** es el hallazgo más interesante de este benchmark pese a tener el peor AUC: gana en `calibration_mae`, es decir, sus probabilidades son las más honestas para leerse literalmente ('de los clientes con 0.7, ¿cuántos realmente pagan tarde?'), aunque ordene peor a los clientes en general. Es una razón para no descartarlo de plano si en el futuro `risk_score` necesitara una probabilidad calibrada más que un buen ranking (p. ej. para dimensionar una provisión contable), pero no alcanza para reemplazar a LR en el MVP: su AUC más bajo (0.6681) sugiere sobreajuste al ruido de la etiqueta con solo 3,000 filas, y su explicabilidad requeriría SHAP.

**Random Forest** queda en el medio en casi todo y no gana ningún criterio: ni el AUC de LR ni la calibración de LightGBM, con el modelo más pesado (2.2 MB) y la latencia p95 más alta con margen (los árboles sin boosting evalúan más nodos por predicción individual que un boosting bien podado). Se descarta como elección principal.

**Decisión para el MVP:** `risk_prob_lr` = salida de **Logistic Regression**. `risk_score = 0.6·risk_prob_lr + 0.4·anomaly_score` (SUPUESTO DE DEMO, §7 del diseño), cortes de `risk_level` en 0.35/0.65. Reemplaza el proxy interino (`risk_score = anomaly_score`) usado antes de esta fase.

Este veredicto es válido para **esta corrida con esta seed**; el detalle completo queda en `outputs/risk_benchmark.csv` para que el equipo lo revise.