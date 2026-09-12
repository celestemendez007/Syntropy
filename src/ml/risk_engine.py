import pandas as pd
import json

def load_dataset():
    # En un entorno real se usaría pd.read_csv('../data/synthetic/dataset.csv')
    # Mockeamos los datos de prueba
    return [
        {"customer_id": "C000", "risk_level": "LOW", "anomaly_score": 0.1, "situation_hint": "NONE", "top_factors": []},
        {"customer_id": "C101", "risk_level": "MEDIUM", "anomaly_score": 0.4, "situation_hint": "FORGETFULNESS", "top_factors": ["payment_delay_avg"]},
        {"customer_id": "C102", "risk_level": "HIGH", "anomaly_score": 0.8, "situation_hint": "TIMING_MISMATCH", "top_factors": ["income_variation", "payment_delay_avg"]},
        {"customer_id": "C104", "risk_level": "HIGH", "anomaly_score": 0.9, "situation_hint": "LIQUIDITY_PRESSURE", "top_factors": ["balance_ratio", "spending_velocity", "failed_attempts"]},
    ]

def get_risk_profile(customer_id: str):
    """
    Mock del motor de ML.
    Debería ejecutar: Isolation Forest -> Logistic Regression -> Top Factors
    """
    dataset = load_dataset()
    for profile in dataset:
        if profile["customer_id"] == customer_id:
            return profile
    
    # Default fallback
    return {"customer_id": customer_id, "risk_level": "MEDIUM", "anomaly_score": 0.5, "situation_hint": "UNKNOWN", "top_factors": []}

if __name__ == "__main__":
    print(json.dumps(get_risk_profile("C104"), indent=2))
