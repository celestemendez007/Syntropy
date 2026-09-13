# Fase 7 — Feedback loop: tabla de prioridades del NBA

`nba_priority_table` agrega `conversations_log` por (situación, barrera, canal, alternativa) y ordena por `success_rate` con suavizado bayesiano `(n_paid_on_time_after + 1) / (n_offered + 2)`. El NBA usa esto SOLO para decidir en qué orden presentar alternativas ya elegibles (Fase 5) -- nunca para decidir elegibilidad ni para tocar `risk_score`.

**SUPUESTO DE DEMO importante**: no hay conversaciones reales todavía (Fase 6, sin LLM conectado); `conversations_log.csv` es sintético (`build_synthetic_conversations.py`), con una probabilidad de aceptación "verdadera" fija por alternativa para que haya señal real que aprender. Esta tabla demuestra el MECANISMO del feedback loop, no un resultado de negocio real.

## Demo de recálculo: 10 conversaciones (solo golden) vs. 244 (golden + sintéticas)

### Antes (solo golden conversations, poca evidencia)

| situation_hint   | barrier_detected   | channel   | alt_id               |   n_offered |   success_rate |   acceptance_rate |
|:-----------------|:-------------------|:----------|:---------------------|------------:|---------------:|------------------:|
| S0               | DATE_MISMATCH      | CALL      | ALT-NONE             |           1 |         0.3333 |                 0 |
| S0               | DATE_MISMATCH      | WHATSAPP  | ALT-NONE             |           1 |         0.3333 |                 0 |
| S1               | FORGOT             | APP_PUSH  | ALT-AUTOSAVE-PCT     |           1 |         0.3333 |                 0 |
| S1               | FORGOT             | APP_PUSH  | ALT-REMINDER-PAYLINK |           1 |         0.3333 |                 1 |
| S2               | DATE_MISMATCH      | WHATSAPP  | ALT-AUTOSAVE-PCT     |           1 |         0.3333 |                 0 |
| S2               | DATE_MISMATCH      | WHATSAPP  | ALT-DATE-SHIFT       |           1 |         0.3333 |                 1 |
| S3               | TECHNICAL          | APP_PUSH  | ALT-PARTIAL          |           1 |         0.3333 |                 0 |
| S3               | TECHNICAL          | APP_PUSH  | ALT-AUTOSAVE-PCT     |           1 |         0.3333 |                 0 |

### Después (con las conversaciones sintéticas agregadas)

| situation_hint   | barrier_detected   | channel   | alt_id               |   n_offered |   success_rate |   acceptance_rate |
|:-----------------|:-------------------|:----------|:---------------------|------------:|---------------:|------------------:|
| S1               | DATE_MISMATCH      | CALL      | ALT-REMINDER-PAYLINK |           3 |         0.8    |            1      |
| S1               | REFUSAL            | CALL      | ALT-REMINDER-PAYLINK |           9 |         0.7273 |            1      |
| S1               | DISPUTE            | CALL      | ALT-REMINDER-PAYLINK |           5 |         0.7143 |            1      |
| S1               | OTHER              | CALL      | ALT-REMINDER-PAYLINK |           8 |         0.7    |            1      |
| S1               | TECHNICAL          | CALL      | ALT-REMINDER-PAYLINK |           8 |         0.7    |            0.75   |
| S1               | FORGOT             | SMS       | ALT-REMINDER-PAYLINK |           7 |         0.6667 |            0.8571 |
| S1               | DATE_MISMATCH      | WHATSAPP  | ALT-REMINDER-PAYLINK |           1 |         0.6667 |            1      |
| S0               | DATE_MISMATCH      | CALL      | ALT-CHANNEL-SUPPORT  |           1 |         0.6667 |            1      |

**El orden cambió** entre las dos corridas: con poca evidencia (solo 10 golden conversations), el suavizado bayesiano empuja casi todo hacia el prior neutro (0.5) y el orden es sensible a 1-2 observaciones; con más datos, las combinaciones con `success_rate` genuinamente más alto se estabilizan arriba. Esto es exactamente el comportamiento esperado del suavizado: protege contra sobre-confiar en poca evidencia sin bloquear que el sistema aprenda cuando sí la hay.


Ciclo completo: conversación -> `conversations_log` + `interventions_log` -> `recompute_and_save()` (el botón 'recalcular' del dashboard, Fase 8) -> siguiente intervención usa `rank_alternatives()` con la tabla nueva.