# Plan Maestro: Tareas, Productos y Flujo Final (MVP Hackathon)

A continuación se detalla el cronograma completo de tareas clasificadas de inicio a fin (según la Guía Definitiva), junto con los entregables exactos y el flujo de la experiencia final.

---

## 📅 1. Clasificación de Tareas (De Inicio a Fin)

Las tareas están organizadas cronológicamente para asegurar que ningún frente de trabajo (Data, Backend, Frontend) bloquee al otro.

### Fase 1: Setup y Contratos Base (Bloqueadores P0)
*Antes de programar lógica, se deben establecer las reglas y los datos.*
1. **T00:** Congelar alcance, supuestos, perfiles y definición de "terminado". (Todas)
2. **T01:** Crear repositorio, estructura de carpetas, ramas (`main`, `develop`) y archivo de contratos JSON. (Celeste)
3. **T02:** Cerrar matriz *State–Skills–Tools* y prompts por estado para el LLM. (Celeste + Camila)
4. **T03:** Generar dataset sintético, diccionario de variables y *golden customers*. (Elena)
5. **T04:** Crear *wireframes* base (M1–M4) y fixtures (mocks) para el frontend. (Camila)

### Fase 2: Desarrollo Independiente (Core y Modelos P0)
*Cada integrante desarrolla su módulo utilizando los datos y contratos congelados en la Fase 1.*
6. **T05:** Preprocesamiento compartido y entrenamiento del **Isolation Forest**. (Elena)
7. **T06:** Entrenamiento de la **Regresión Logística (Baseline)**. (Camila)
8. **T07:** Construcción del **Policy Engine** determinista (backend). (Celeste)
9. **T08:** Implementación del **Next Best Action (NBA)** por reglas. (Celeste)
10. **T09:** Creación de la **Máquina de Estados** (ConversationState) y schemas de validación para el LLM. (Celeste)
11. **T10:** Integración del LLM con *tool calling* (El Agente). (Celeste)
12. **T11:** Construcción de pantallas M1-M3 en código (Banca Móvil y Chat). (Camila)

### Fase 3: Integración y Pruebas (Ensamblaje P0/P1)
*Se conectan las piezas de Machine Learning, Backend y Frontend.*
13. **T12:** Unificar *Isolation Forest* y *Logistic Regression* en un único `risk_result`. (Elena + Camila)
14. **T13:** Construcción del **Dashboard Interno M4**. (Camila)
15. **T14 - T17:** Ejecución de Matrices de Pruebas:
    - *Datos/ML:* Fuga de datos, casos extremos. (Elena)
    - *Seguridad:* Inyección de prompts, intentar vulnerar el Policy Engine. (Celeste)
    - *UX/UI:* Casos ambiguos, errores de red. (Camila)
16. **T18:** *Cross-review*: Cada integrante revisa el código de otra. (Todas)

### Fase 4: Entrega y Cierre (P1 y P3)
*Preparación para la demostración al jurado.*
17. **T19:** Redactar el *Model Card* conjunto (limitaciones y métricas sintéticas). (Elena + Camila)
18. **T20:** Validar logs de auditoría (trazabilidad de decisiones). (Celeste + Camila)
19. **T21:** Prueba **End-to-End** completa (3 casos de uso + el caso "S0" de No Contactar). (Todas)
20. **T22:** Preparar el *Pitch* de negocio (speech + ensayo). (Todas)
21. **T23/T24:** (Opcional P3) K-Means exploratorio o añadir Voz (STT/TTS). (Camila / Celeste)
22. **T25:** **FREEZE (Congelamiento):** Backup, screenshots de emergencia y ensayo final. (Todas)

---

## 📦 2. Productos Esperados (Entregables del MVP)

Al finalizar las 24 horas, el equipo no entregará una aplicación real conectada al banco, sino un **MVP simulado, seguro y auditable** que consta de:

1. **Banca Móvil (Simulada):** Una interfaz web (React/Vite) que muestra una tarjeta de intervención preventiva ("Nudge") invitando al cliente a revisar su pago.
2. **Agente Conversacional Seguro:** Un chat integrado donde un LLM comprende al usuario, pero **NO** tiene poder financiero. Sus promesas están limitadas estrictamente por un código en Python (Policy Engine).
3. **Módulo de ML Híbrido:** Un motor doble que detecta anomalías en el comportamiento (*Isolation Forest*) y calcula el riesgo base (*Logistic Regression*) usando datos 100% ficticios.
4. **Dashboard Operativo:** Un panel de control (pantalla web) interno que demuestra cómo el banco audita todo: riesgo, anomalía, decisión (Next Best Action), resultado de la política y el acuerdo final de la conversación.
5. **Documentación de Defensa:** El *Model Card* explicando qué se hizo, por qué se usaron datos sintéticos y cómo esto se llevaría a producción.

---

## 🔄 3. El Flujo Final (Experiencia End-to-End)

El recorrido exacto que el jurado verá funcionar en vivo durante la demostración:

1. **Detección (Background):** El sistema lee los datos sintéticos de un cliente. Los modelos (Isolation Forest + Logistic Regression) detectan que el cliente tiene una alta *anomalía* y *riesgo medio*.
2. **Decisión (NBA):** El *Next Best Action* decide que el cliente no es un S0 (Estable), por lo que emite la orden de intervenir enviando una alerta (Nudge) a su Banca Móvil.
3. **Interacción (Frontend):** El cliente entra a su App del banco y ve una tarjeta preventiva. Decide hacer clic en "Revisar opciones".
4. **Comprensión (Agente LLM):** El cliente escribe su problema en lenguaje natural (ej. *"No me han pagado mi salario"*). El LLM clasifica el problema (Barrera identificada: Presión de Liquidez).
5. **Validación (Policy Engine):** El LLM pide al backend las opciones. El backend (Policy Engine determinista) revisa las reglas y le responde al LLM: *"Solo puedes ofrecerle pagar en 15 días o contactar a un humano"*.
6. **Negociación y Confirmación:** El LLM le presenta las opciones al cliente. El cliente selecciona los 15 días extra. El LLM pide confirmación explícita (*"¿Confirmas el cambio para el 20 de septiembre?"*). El cliente acepta.
7. **Registro y Cierre:** El acuerdo se guarda. El **Dashboard Interno** se actualiza automáticamente mostrando el caso cerrado, la barrera identificada, la oferta aplicada y todo el registro auditable.
