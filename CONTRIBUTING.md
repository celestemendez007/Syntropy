# Reglas de Trabajo y Uso de Herramientas AI - Hackathon "BA A Tiempo"

Este documento establece las reglas estrictas de control de versiones y el uso de herramientas de Inteligencia Artificial para el hackathon.

## 1. Flujo de Trabajo en Git (Git Workflow)

Para evitar conflictos y asegurar que siempre tengamos una versión lista para presentar, seguiremos este modelo:

- **Ramas Principales:**
  - `main`: **EXCLUSIVA DE CELESTE**. Esta rama contiene siempre la versión estable ("demo-ready"). **Nadie más hace push ni merge a esta rama**.
  - `develop`: Rama de integración de todo el equipo. Todo el trabajo nuevo debe llegar aquí primero.

- **Ramas Individuales (Feature Branches):**
  Cada integrante debe crear ramas desde `develop` con el siguiente prefijo según su especialidad:
  - **Elena (Data/ML):** `feat/ml-[nombre-tarea]` (ej. `feat/ml-risk-baseline`)
  - **Celeste (Backend/Core):** `feat/core-[nombre-tarea]` (ej. `feat/core-policy-engine`)
  - **Camila (Frontend/UX):** `feat/ui-[nombre-tarea]` (ej. `feat/ui-chat-component`)

- **Reglas para subir código (Push & Merge):**
  1. Haz *commits* pequeños y descriptivos.
  2. Haz *push* **únicamente** a tu rama de feature.
  3. Crea un *Pull Request (PR)* hacia `develop`. **NUNCA directo a `main`**.
  4. **Revisión obligatoria:** Ningún módulo crítico se une a `develop` sin la revisión rápida de otra integrante del equipo (ej. Frontend revisa Backend).

## 2. Asignación y Uso de Herramientas de IA

Para maximizar nuestra velocidad en las 24 horas, usaremos herramientas específicas para tareas concretas:

### 🚀 Antigravity (Scaffolding, Código Estructural y Setup)
Herramienta principal para generar bases de código y conectar piezas.
- **Elena:** Generación del esqueleto (scaffold) de notebooks de datos, módulos de ML (`risk_engine`) y tests.
- **Celeste:** Generación de la estructura base de FastAPI, clientes de conexión API, definición de contratos (`policies.json`) y pruebas unitarias.
- **Camila:** Scaffolding de componentes visuales (UI) y escritura del código de conexión con los endpoints (APIs).

### 🛡️ Claude (Análisis Crítico, Red-Teaming y UX)
Herramienta principal para asegurar la calidad lógica, tono y casos límite (edge cases).
- **Elena:** Segunda revisión de *features*, chequeos para evitar "data leakage" (fugas de información), validaciones lógicas y redacción del *Model Card*.
- **Celeste:** "Red-Teaming" sobre los prompts del Agente (intentar romper los guardrails), revisión de la máquina de estados y búsqueda de vulnerabilidades lógicas.
- **Camila:** Revisión experta de *microcopy* (tono de empatía), validación de casos de experiencia de usuario (UX) y generación de la matriz de pruebas adversariales.

### 🧠 ChatGPT (Generación de Datos, Ideación y Apoyo Rápido)
Herramienta principal para crear contenido, casos ficticios y resolver dudas puntuales.
- **Elena:** Generación acelerada del dataset sintético reproducible, perfiles "golden customers" (S0-S4) y lluvia de ideas para variables de riesgo (`top_factors`).
- **Celeste:** Redacción de borradores para reglas de negocio, flujos conversacionales, y debugging rápido de errores en terminal.
- **Camila:** Ideación de flujos de navegación, alternativas de diseño de pantalla, y solución de bloqueos rápidos de estilos o CSS.

## 3. Reglas de Oro del Proyecto
1. **Verificación Humana:** Ningún código generado por IA (sin importar la herramienta) se hace merge sin haberlo ejecutado y entendido al 100%.
2. **Code Freeze:** Durante las últimas 2-3 horas **NO HAY FEATURES NUEVOS**. Sólo se permiten *bug fixes* (arreglos de errores), sacar screenshots de backup, afinar el pitch y ensayar la demo. Priorizar siempre la estabilidad de la demo sobre agregar funciones incompletas.
