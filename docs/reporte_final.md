# BA A Tiempo — Reporte final (Fase 8)

Cobranza preventiva y empática con IA. Todo el pipeline (Fases 1-7) está implementado y
probado; este documento consolida qué se comparó en cada fase, qué ganó, por qué, y qué
limitaciones quedan explícitamente documentadas. Todos los datos son **sintéticos**.

Para reproducir todo desde cero: `python run_all.py` desde la raíz del repo (~3 minutos).
Regenera los datos, corre los tres benchmarks de modelos, sincroniza los ganadores a
producción, genera las conversaciones (golden + sintéticas), recalcula la tabla de
prioridades, mide la latencia end-to-end, exporta el dashboard y corre toda la suite de
tests (146 tests entre `research/ba_a_tiempo/tests/` y `tests/`).

---

## 1. Arquitectura: Detectar → Comprender → Intervenir → Negociar → Registrar → Aprender

| Fase | Qué hace | Estado | Módulo |
|---|---|---|---|
| 1 | Generador sintético (3,000 clientes, 6 ciclos, golden customers) | ✅ | `research/ba_a_tiempo/ba_a_tiempo/generator.py` |
| 2 | Detección de anomalías (IF vs LOF vs OCSVM vs Z-score) | ✅ | `anomaly_benchmark.py` |
| 3 | Riesgo supervisado (LR vs Random Forest vs LightGBM) | ✅ | `risk_benchmark.py` |
| 4 | Canal preferido + momento óptimo (2 niveles + fallback) | ✅ | `channel_timing.py` / `channel_timing_engine.py` |
| 5 | NBA + Policy Engine + catálogo + `score_customer` | ✅ | `nba_engine.py`, `policy_engine.py`, `score_customer.py` |
| 6 | Capa conversacional (categorías, prompt, guardrail, golden conversations) | ✅ | `conversation_engine.py`, `chat_state_machine.py` |
| 7 | Feedback loop (`nba_priority_table`, suavizado bayesiano) | ✅ | `nba_priority.py` |
| 8 | Reporte final + dashboard mínimo + script único | ✅ | este documento, `src/frontend/`, `run_all.py` |

Principio invariante: **la IA conversa; el banco decide.** El Policy Engine (Fase 5)
resuelve elegibilidad y parámetros concretos ANTES de que el LLM diga una palabra; el LLM
(Fase 6) nunca inventa un monto o fecha, y un guardrail automático lo verifica.

---

## 2. Comparativa de modelos: cuál es mejor y por qué

### 2.1 Detección de anomalías (Fase 2)

| Modelo | AUC (S0 vs S3) | Latencia p95 | Tamaño | Explicabilidad |
|---|---|---|---|---|
| **Isolation Forest** ✅ | 0.959 | ~8 ms | 2.3 MB | Alta (ablación por feature) |
| Local Outlier Factor | 0.682 | 0.7 ms | 1.1 MB | Media (densidad local) |
| One-Class SVM | 0.837 | 0.5 ms | 27 KB | Baja (requiere SHAP) |
| Z-score Mahalanobis | 0.974 | 0.6 ms | 27 KB | Muy alta (fórmula exacta) |

**Ganador: Isolation Forest**, con **Z-score de Mahalanobis como segunda opinión** para
monitoreo de drift poblacional. El Z-score tiene el AUC agregado más alto, pero subestima
el caso individual G07 (percentil 16.7, el peor de los cuatro) — un recordatorio de que el
AUC agregado no garantiza buen desempeño en un cliente puntual, que es como este sistema
puntúa en producción. Detalle completo: `research/ba_a_tiempo/outputs/anomaly_benchmark_report.md`.

### 2.2 Riesgo supervisado (Fase 3)

| Modelo | AUC | Brier score | Calibración (MAE) | Latencia p95 | Tamaño |
|---|---|---|---|---|---|
| **Logistic Regression** ✅ | **0.737** | **0.213** | 0.158 | **0.42 ms** | **1.4 KB** |
| Random Forest | 0.721 | 0.216 | 0.144 | 27.5 ms | 2.2 MB |
| LightGBM | 0.668 | 0.225 | **0.101** | 1.3 ms | 624 KB |

**Ganador: Logistic Regression**, y gana en casi todo pese a ser el modelo más simple: con
3,000 filas y 11 features, los árboles no encuentran no-linealidad real que explotar y solo
agregan costo de explicabilidad. **Hallazgo interesante**: LightGBM tiene el peor AUC pero
la mejor calibración — sus probabilidades son las más "honestas" para leerse literalmente,
aunque ordene peor a los clientes. No alcanza para reemplazar a LR en el MVP, pero es una
pista real de para cuándo valdría la pena reconsiderar (si `risk_score` necesitara una
probabilidad calibrada más que un buen ranking). Detalle: `risk_benchmark_report.md`.

### 2.3 Canal y momento (Fase 4)

No es una comparación de algoritmos sino de **diseño**: nivel 1 (tasa de respuesta por
canal del propio cliente) + nivel 2 (Logistic Regression poblacional, AUC 0.53 — modesto
porque no ve la afinidad oculta del generador) + fallback determinista a `CALL` cuando la
confianza es baja. En la práctica, con solo ~3 contactos por cliente en 90 días, el 88% de
las decisiones cae al fallback — un hallazgo honesto, no maquillado: el nivel 2 hace lo que
puede sin la señal oculta, y el fallback existe precisamente para eso. Detalle:
`channel_timing_report.md`.

### 2.4 Veredicto general

No hay "un modelo ganador" para todo el sistema — hay una arquitectura de tres capas
independientes que se combinan con fórmulas explícitas y auditables:

```
risk_score = 0.6 · risk_prob_lr (Logistic Regression) + 0.4 · anomaly_score (Isolation Forest)
```

Ninguna capa depende de que la otra sea "la mejor" en abstracto — el Z-score de Mahalanobis
sigue siendo útil aunque no gane como score principal, y LightGBM sigue siendo la pista
correcta si algún día se necesita calibración sobre ranking. Esa es la razón real para
preferir modelos simples y explicables en cada capa: el sistema completo ya es complejo
(5 componentes que se combinan), y cada componente individual necesita poder explicarse en
una frase ante un cliente o un jurado.

---

## 3. NBA + Policy Engine + `score_customer` (Fase 5)

- **12/12 golden customers** validados correctamente contra `situation_hint` (incluyendo
  dos excepciones documentadas por diseño: G09 usa `low_digital_response` en vez de un S4
  que ya no existe en el enum, y G06 cae a S0 porque `income_date_unknown=1` desactiva la
  regla S2 a propósito — ver `BA_A_Tiempo_Diseno_Dataset_v1.md` §10).
- **Catálogo de alternativas** (`alternatives_catalog.json`) resuelve parámetros concretos
  (fechas, montos, porcentajes) antes de que exista una sola palabra de conversación.
- **Guardrail real, no solo de prompt**: `chat_state_machine.py` rechaza (`policy_result =
  REJECTED_NOT_ELIGIBLE`) cualquier intento de seleccionar una alternativa que el Policy
  Engine no autorizó para ese cliente — la prueba adversarial explícita del criterio de
  éxito #2 del README.
- **Latencia end-to-end**: se encontró y corrigió un cuello de botella real durante esta
  fase (perfilado con `cProfile`, no adivinado): `top_factors` hacía 11 llamadas
  individuales al Isolation Forest en vez de una por lotes. p95 bajó de ~139 ms a **~60 ms**
  sin tocar ningún modelo. Detalle: `score_customer_benchmark_report.md`.

---

## 4. Capa conversacional (Fase 6)

- Categorías cerradas de barrera (8) y tono (4), con `temperature=0` recomendado
  explícitamente (tarea de clasificación + parafraseo de cifras ya resueltas, no
  generación creativa).
- Guardrail anti-alucinación: escanea fechas/montos/porcentajes no autorizados + una lista
  de frases-bandera ("sin intereses", "gratis", ...).
- **10 golden conversations**, incluyendo un caso adversarial a propósito (`CV-G10`) donde
  la respuesta simulada menciona "sin intereses" y una fecha no autorizada — es el único
  que sale marcado con `llm_hallucination_flag = true`.
- **No hay LLM real conectado** (`.env.example` solo tiene un placeholder de
  `OPENAI_API_KEY`). `call_llm()` usa un clasificador determinista por palabras clave para
  poder generar golden conversations y correr tests sin red ni API key; es el único punto
  de integración que habría que reemplazar.

---

## 5. Feedback loop (Fase 7)

`nba_priority_table` agrega conversaciones por `(situation_hint, barrier_detected, channel,
alt_id)` con suavizado bayesiano `(n_paid_on_time_after + 1) / (n_offered + 2)`, y
`rank_alternatives()` reordena (nunca filtra) lo que el Policy Engine ya autorizó.

**Demostración concreta del mecanismo** (no un resultado de negocio real, ver más abajo):
con solo 10 golden conversations el orden es inestable (todo cerca del prior neutro 0.5);
al sumar 215 conversaciones sintéticas, `ALT-REMINDER-PAYLINK` para S1/FORGOT se estabiliza
arriba con `success_rate = 0.67` sobre 105 observaciones — exactamente el comportamiento
esperado del suavizado bayesiano. Detalle: `nba_priority_table_report.md`.

---

## 6. Dashboard mínimo (Fase 8)

`src/frontend` (React + Vite) lee un snapshot estático (`public/data/dashboard_data.json`,
generado por `src/backend/export_dashboard_data.py`) — no hay servidor HTTP en este MVP.
Muestra: distribución de cartera (situación, riesgo, % `NO_CONTACT`), comparativa de
modelos, métricas de conversación, el top de la tabla de prioridades, validación de los 12
golden customers, las 10 golden conversations, y una muestra de clientes puntuados en vivo
con `score_customer`. `npm run dev` (o `npm run build`) en `src/frontend/`.

---

## 7. Limitaciones conocidas (dichas explícitamente, no escondidas)

- **`conversations_log`/`interventions_log` son sintéticos** (`build_synthetic_conversations.py`):
  no hay LLM real conectado todavía, así que la aceptación de alternativas se simula con una
  probabilidad "verdadera" fija por `alt_id`. El feedback loop (Fase 7) demuestra el
  mecanismo, no mide éxito real de negocio.
- **`remaining_installments`** no existe en el generador sintético (quedó como columna
  opcional del diseño, nunca implementada); `ALT-AUTOSAVE-PCT` usa un valor fijo asumido
  (`ASSUMED_REMAINING_INSTALLMENTS = 12`), documentado en `policy_engine.py`.
- **El catálogo de alternativas no se re-resuelve tras conocer la barrera real**: la
  elegibilidad (Fase 5) se calcula con `situation_hint` (inferido de datos, antes de
  hablar); cuando la barrera que el cliente revela no coincide (ver golden conversations
  `CV-G04`, `CV-G05`), el catálogo puede no tener una alternativa que calce y el sistema
  debe escalar. Documentado como mejora para Fase 7+.
- **Modelos de anomalía entrenados con una versión de scikit-learn distinta a la instalada**
  generan un `InconsistentVersionWarning` al cargar — no afecta los resultados numéricos
  en las corridas verificadas, pero es una razón real para fijar versiones en
  `requirements.txt` antes de cualquier despliegue.
- **Sin servidor HTTP**: el dashboard lee un JSON estático regenerado por script, no un
  backend vivo. Suficiente para la demo del hackathon; una API real (FastAPI/Flask
  exponiendo `score_customer`) sería el siguiente paso natural.

---

## 8. Cómo reproducir

```bash
python run_all.py          # todo el pipeline, ~3 min, termina corriendo 146 tests
cd src/frontend && npm run dev   # dashboard en http://localhost:5173
```

Ver `README.md` para el detalle por fase y `docs/contracts.md` para los contratos JSON
completos entre módulos.
