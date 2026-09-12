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
