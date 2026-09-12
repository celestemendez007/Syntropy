def get_next_best_action(risk_profile: dict) -> dict:
    """
    Decide la intervención según el riesgo y las anomalías.
    """
    level = risk_profile.get("risk_level", "LOW")
    anomaly = risk_profile.get("anomaly_score", 0.0)
    
    if level == "LOW" and anomaly < 0.2:
        return {
            "intervene": False,
            "channel": "NONE",
            "action": "NO_CONTACT",
            "reason": "S0_STABLE"
        }
        
    if level == "MEDIUM":
        return {
            "intervene": True,
            "channel": "APP_PUSH",
            "action": "SEND_REMINDER",
            "reason": "S1_FRICTION"
        }
        
    # Riesgo alto o anomalías significativas (S2, S3)
    return {
        "intervene": True,
        "channel": "APP_IN_APP_MESSAGE",
        "action": "START_ASSISTANCE",
        "reason": "HIGH_RISK_OR_ANOMALY"
    }

if __name__ == "__main__":
    mock_risk = {"risk_level": "HIGH", "anomaly_score": 0.8}
    print(get_next_best_action(mock_risk))
