# Contratos Técnicos (JSON)

Este documento define las estructuras JSON que actúan como interfaces entre los distintos módulos del proyecto (Data/ML, Backend/Policy Engine y Frontend).

## 1. risk_result
Salida del motor de riesgo (ej. Isolation Forest / LR). Provee las señales iniciales para un cliente.
```json
{
  "customer_id": "C104",
  "risk_score": 0.78,
  "risk_level": "HIGH",
  "anomaly_score": 0.81,
  "situation_hint": "LIQUIDITY_PRESSURE",
  "top_factors": [
    "balance_ratio_low",
    "income_variation"
  ]
}
```

## 2. next_best_action
Salida del motor determinista de reglas para la siguiente acción recomendada, basada en el perfil de riesgo.
```json
{
  "intervene": true,
  "channel": "APP",
  "time_window": "12:00-13:30",
  "action": "START_ASSISTANCE",
  "reason": "HIGH_RISK_AND_ANOMALY"
}
```

## 3. allowed_offers
Opciones generadas y permitidas por el *Policy Engine*. El LLM de chat **solamente** debe ofrecer opciones contenidas aquí.
```json
{
  "customer_id": "C104",
  "offers": [
    {
      "id": "O1",
      "type": "PAY_NOW"
    },
    {
      "id": "O2",
      "type": "PROMISE_TO_PAY",
      "date": "2026-09-20"
    },
    {
      "id": "O3",
      "type": "HUMAN_CALLBACK"
    }
  ]
}
```

## 4. conversation_result
El resultado de la negociación capturado tras la interacción del cliente con el agente.
```json
{
  "state": "CLOSE",
  "barrier": "TIMING_MISMATCH",
  "selected_offer": "O2",
  "policy_result": "AUTHORIZED",
  "result": "PROMISE_TO_PAY",
  "confirmed": true
}
```
