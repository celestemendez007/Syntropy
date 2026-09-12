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
| `risk_score` / `risk_level` | ⚠️ Proxy interino | = `anomaly_score` hasta integrar el modelo supervisado |
| Riesgo supervisado (LR/Random Forest/LightGBM) | ⏳ Pendiente | Fase 3, diseño listo, benchmark no corrido aún |
| Canal preferido / momento óptimo | ⏳ Pendiente | Fase 4 |
| NBA con feedback loop | ⏳ Pendiente | Fase 5 |

Documentación completa del diseño (dataset, feature engineering, golden customers, casos extremos,
benchmark de modelos con veredicto razonado) en `research/ba_a_tiempo/`. `docs/contracts.md` y
`docs/data_dictionary.md` reflejan el esquema real (v2), no el mock original.

Para regenerar los datos o el benchmark:
```bash
cd research/ba_a_tiempo
python3 -c "from ba_a_tiempo import generator; generator.run_all()"
python3 -c "from ba_a_tiempo import anomaly_benchmark as AB; r,s = AB.run_benchmark(); AB.build_report(r,s)"
python3 -m pytest tests/ -q
```
