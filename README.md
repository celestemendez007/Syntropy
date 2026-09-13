# BA A Tiempo (Prototipo MVP)

**Cobranza preventiva y empática con Inteligencia Artificial**

## 🎯 Objetivo
Construir un MVP funcional, seguro y demostrable. El objetivo de *BA A Tiempo* no es cobrar más agresivamente, sino intervenir antes, comprender la barrera real del cliente y ofrecer únicamente acciones válidas que le ayuden a proteger su historial crediticio.

**Principio:** Detectar → Comprender → Intervenir → Negociar → Registrar → Aprender.

## 🚀 Promesa del Producto
> "Hoy una gran parte de la cobranza ocurre cuando el problema ya existe. BA A Tiempo cambia ese momento: detecta señales tempranas, identifica quién realmente necesita una intervención y conversa para entender qué está impidiendo el pago. En lugar de que un chatbot improvise condiciones, todas las alternativas vienen autorizadas por Bancoagrícola."

## 📦 Alcance del MVP (Definición de "Terminado")
Para considerar este MVP como exitoso durante el hackathon, debe cumplirse lo siguiente:
1. Un cliente ficticio puede recorrer el flujo completo desde la señal de riesgo hasta el resultado registrado.
2. El *Policy Engine* bloquea condiciones inválidas aunque el usuario intente manipular al LLM (pruebas adversariales).
3. El frontend muestra **solo** alternativas devueltas y autorizadas por el backend.
4. Existe al menos un caso donde el sistema decide **"no contactar"** (S0).
5. Se utilizan datos completamente **sintéticos** (supuestos de demo).

## ⚠️ Supuestos Obligatorios (Disclaimer)
* Todos los datos utilizados en esta demostración son ficticios/sintéticos.
* Las opciones de negociación mostradas son ejemplos para demostrar arquitectura, **no** representan políticas reales.
* No hay integración con el core bancario real; las operaciones se simulan.
* Las métricas de ML son sobre etiquetas sintéticas y validan el pipeline, no el rendimiento productivo.

## 👥 Equipo
* **Celeste:** Backend, Policy Engine y Agente Conversacional (Owner rama `main` y `develop`).
* **Elena:** Data, Machine Learning y Explicabilidad.
* **Camila:** Frontend, Experiencia de Cliente (UX), QA y Demo.

## 📊 Estado del motor de ML (actualizado)

`src/ml/risk_engine.py` ya no es un mock. Estado real por componente:

| Componente | Estado | Detalle |
|---|---|---|
| Generador de datos sintéticos | ✅ Real | 3,000 clientes, 6 ciclos históricos, reproducible (seed fija). `research/ba_a_tiempo/` |
| `anomaly_score` | ✅ Real | Isolation Forest, comparado contra LOF/One-Class SVM/z-score Mahalanobis. Ver `research/ba_a_tiempo/outputs/anomaly_benchmark_report.md` |
| `situation_hint` (S0-S3) | ✅ Real | Reglas deterministas, no ML |
| `low_digital_response` | ✅ Real | Regla sobre tasa de respuesta y uso de app |
| `top_factors` | ✅ Real | Ablación por feature sobre Isolation Forest |
| `risk_score` / `risk_level` | ✅ Real | Combina `risk_prob_lr` (0.6) + `anomaly_score` (0.4), cortes 0.35/0.65 |
| Riesgo supervisado (LR vs. Random Forest vs. LightGBM) | ✅ Real | Logistic Regression ganó en AUC, calibración, tamaño y latencia. Ver `research/ba_a_tiempo/outputs/risk_benchmark_report.md` |
| Canal preferido (nivel 1 por cliente + nivel 2 poblacional, fallback CALL) | ✅ Real | `src/ml/channel_timing_engine.py`. Ver `research/ba_a_tiempo/outputs/channel_timing_report.md` |
| Momento óptimo (hora + anticipación) | ✅ Real | Estadístico, no ML. Mismo módulo/reporte que canal |
| NBA (compuertas + acción + escalamiento a humano) | ✅ Real | `src/backend/nba_engine.py`. Sin feedback loop todavía (Fase 7) |
| Catálogo de alternativas (Policy Engine) | ✅ Real | `src/backend/policy_engine.py` + `alternatives_catalog.json`, parámetros resueltos (fechas, montos, porcentajes) |
| `score_customer` (contrato v2 único) | ✅ Real | `src/backend/score_customer.py`. Latencia end-to-end p95 ≈ 60 ms, ver `research/ba_a_tiempo/outputs/score_customer_benchmark_report.md` |
| Capa conversacional (categorías, prompt, guardrail) | ✅ Real | `src/backend/conversation_engine.py` + `chat_state_machine.py`. `call_llm()` usa un mock determinista (sin proveedor real conectado, solo placeholder en `.env.example`) |
| Golden conversations (10, con caso adversarial) | ✅ Real | `research/ba_a_tiempo/data/interactions/golden_conversations.csv`, generado por `src/backend/build_golden_conversations.py` |
| Feedback loop (`nba_priority_table`, suavizado bayesiano, recálculo) | ✅ Real | `src/backend/nba_priority.py`, wireado en `score_customer.py`. `conversations_log`/`interventions_log` son sintéticos (sin LLM real conectado), ver `research/ba_a_tiempo/outputs/nba_priority_table_report.md` |
| Reporte final consolidado | ✅ Real | `docs/reporte_final.md` — comparativa de qué modelo ganó en cada fase y por qué, limitaciones conocidas |
| Dashboard mínimo | ✅ Real | `src/frontend` (React + Vite), lee `public/data/dashboard_data.json` (estático, sin backend HTTP) |
| Script único para correr todo | ✅ Real | `python run_all.py` desde la raíz — regenera todo, sincroniza producción, corre 146 tests, ~3 min |

**Todas las 8 fases del proyecto están completas.** Ver `docs/reporte_final.md` para el
resumen consolidado y las limitaciones conocidas.

Documentación completa del diseño (dataset, feature engineering, golden customers, casos extremos,
benchmark de modelos con veredicto razonado) en `research/ba_a_tiempo/`. `docs/contracts.md` y
`docs/data_dictionary.md` reflejan el esquema real (v2), no el mock original.

### Cómo correr todo

```bash
python run_all.py
```

Un único script (`run_all.py`, raíz del repo) regenera los datos sintéticos, corre los
tres benchmarks de modelos (anomalía, riesgo supervisado, canal/momento), sincroniza los
modelos ganadores hacia `src/ml/models/` y `data/synthetic/` (producción no lee de
`research/`), genera las golden conversations y las conversaciones/intervenciones
sintéticas, recalcula la tabla de prioridades del NBA, mide la latencia end-to-end de
`score_customer`, exporta `dashboard_data.json` para el frontend, y corre toda la suite de
tests (146 tests). Tarda ~3 minutos.

Para ver el dashboard después: `cd src/frontend && npm install && npm run dev`.

Para correr un solo paso (útil mientras se itera), cada módulo se puede invocar
directamente -- ver los comandos dentro de cada función de `run_all.py` o los `if __name__
== "__main__":` de `research/ba_a_tiempo/ba_a_tiempo/*.py` y `src/backend/*.py`.
