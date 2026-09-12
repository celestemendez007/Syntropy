# Fase 2 — Benchmark de detección de anomalías

Comparación sobre las mismas 10 features (`config.IF_FEATURES`), mismo train/test split, seed 42. AUC evaluado SOLO con `synthetic_situation_truth` (S0 vs S3), que nunca se usa para entrenar — es la variable oculta del generador, exclusiva para medir qué tan bien cada modelo separa lo normal de lo anómalo. S1/S2/S4 se excluyen del AUC por ser ambiguos por diseño (mezclan rasgos normales y anómalos).

## Resultados

| model              |   auc_s0_vs_s3 |   fit_time_s |   latency_p50_ms |   latency_p95_ms |   model_size_kb |   golden_g01_estable |   golden_g02_anomalia_benigna |   golden_g07_caida_ingreso |   golden_g07_pctil_anomalia |   golden_g12_cliente_nuevo | golden_check_pass   |
|:-------------------|---------------:|-------------:|-----------------:|-----------------:|----------------:|---------------------:|------------------------------:|---------------------------:|----------------------------:|---------------------------:|:--------------------|
| IsolationForest    |         0.9588 |        0.208 |           10.687 |           12.204 |          2259.6 |                0.246 |                         0.691 |                      0.512 |                        10.8 |                      0.209 | True                |
| LocalOutlierFactor |         0.6824 |        0.085 |            1.199 |            1.448 |          1113.4 |                0.049 |                         1     |                      0.1   |                         0.5 |                      0.027 | True                |
| OneClassSVM        |         0.8365 |        0.027 |            0.581 |            0.679 |            27.3 |                0.497 |                         1     |                      0.598 |                         3.2 |                      0.452 | True                |
| ZScore_Mahalanobis |         0.9736 |        0.71  |            0.691 |            0.784 |            27.4 |                0.008 |                         0.231 |                      0.034 |                        16.7 |                      0.005 | True                |

`golden_g07_pctil_anomalia`: percentil de anomalía del cliente G07 (caída real de ingreso) dentro de la población de test. 0 = el más anómalo de todos; 50 = mediana (nada anómalo).

## Lectura de los resultados (no solo el ranking)

- **Mejor AUC agregado (S0 vs S3):** `ZScore_Mahalanobis` (0.9736).
- **Menor latencia p95:** `OneClassSVM` (0.679 ms).
- **Modelo más pequeño:** `OneClassSVM` (27.3 KB).
- **Mejor detección del caso realista G07 (percentil más bajo = más anómalo):** `LocalOutlierFactor` (0.5 percentil).
- **Pasan el chequeo ordinal golden (G02 y G07 > G01):** IsolationForest, LocalOutlierFactor, OneClassSVM, ZScore_Mahalanobis.

**Discrepancia importante:** `ZScore_Mahalanobis` gana en AUC agregado, pero en el caso individual G07 (una caída de ingreso real, no un extremo) su percentil de anomalía es 16.7, mientras que `LocalOutlierFactor` lo ubica en el percentil 0.5. Un AUC alto sobre miles de clientes describe qué tan bien separa la *población* S0 de la S3 en promedio; no garantiza que un caso moderado e individual —el tipo de cliente que en producción sí quieres detectar— quede cerca de la cola anómala. Esto importa más para el producto que el AUC solo, porque el sistema puntúa un cliente a la vez, no una población.

### Notas de explicabilidad

- **IsolationForest:** Alta. Se puede calcular contribución por feature via ablación (reemplazar por mediana y medir el cambio en el score); árboles cortos, fácil de auditar manualmente un caso.
- **LocalOutlierFactor:** Media. El score depende de la densidad local (vecinos), más difícil de explicar en una frase a un jurado no técnico ('está lejos de sus 35 vecinos más cercanos').
- **OneClassSVM:** Baja. El hiperplano en espacio de kernel RBF no tiene traducción directa a 'esta variable causó la anomalía'; requiere SHAP con costo computacional alto.
- **ZScore_Mahalanobis:** Muy alta. Se puede descomponer exactamente cuánto aporta cada variable a la distancia (contribución = diferencia al cuadrado ponderada por la inversa de covarianza). Es una fórmula, no una aproximación.

### Veredicto (ponderando todos los criterios, no un solo número)
Un solo caso golden (G07) no debe decidir entre modelos por sí solo — es n=1. LocalOutlierFactor gana ahí, pero su AUC agregado (0.68) es mediocre: en la mitad de los casos no separa bien lo normal de lo anómalo, y su score depende de la densidad local (`n_neighbors=35`), un hiperparámetro al que es sensible; un resultado excelente en un caso y débil en el agregado es más señal de varianza del modelo que de superioridad real. Se descarta como elección principal por esa razón, aunque vale la pena revisar con más golden cases si el tiempo lo permite.

**Isolation Forest** es la recomendación para producción del MVP: AUC agregado alto (0.96, segundo lugar detrás del z-score por un margen pequeño), ubica el caso G07 en el percentil 10.8 (razonablemente cerca de la cola anómala, sin ser el mejor ni el peor), latencia p95 de ~13 ms por cliente —perfectamente aceptable para scoring uno-a-uno, aunque sea la más lenta de las cuatro—, y la mejor relación explicabilidad/costo: ablación por feature es barata de calcular con pocos árboles y se puede explicar en una frase ('se aisló rápido de los demás clientes').

**Z-score de Mahalanobis** es el hallazgo más útil de este benchmark: con el AUC agregado más alto (0.97), el modelo más chico (27 KB) y la explicabilidad más exacta de las cuatro (una fórmula, no una aproximación), es la elección correcta como **segunda opinión** — por ejemplo para monitorear drift poblacional en el dashboard ('¿la cartera completa se está alejando de su centro histórico?') — precisamente porque mide algo distinto a Isolation Forest: distancia al centro global de la población, no aislabilidad local. Que subestime a G07 (percentil 16.7, el peor de los cuatro en ese caso) muestra su límite: asume una distribución aproximadamente elíptica, y una caída de ingreso moderada sin otros síntomas no siempre genera suficiente distancia de Mahalanobis. Es una razón para no usarlo solo, no para descartarlo.

**One-Class SVM** queda tercero: AUC intermedio (0.84), el más barato en tamaño y de los más rápidos, pero su score en un hiperplano de kernel RBF no se explica ante un jurado sin recurrir a SHAP, que tiene costo computacional alto. Se recomienda solo si la latencia fuera el criterio dominante y hubiera presupuesto de ingeniería para explicabilidad post-hoc.

**Decisión para el MVP:** Isolation Forest como score principal (`anomaly_score`), z-score de Mahalanobis como chequeo secundario de drift poblacional en el dashboard. Ninguno se usa aislado; el JSON de contrato (Fase 5) puede exponer ambos.

Este veredicto es válido para **esta corrida con esta seed**; el detalle completo queda en `outputs/anomaly_benchmark.csv` para que el equipo lo revise.