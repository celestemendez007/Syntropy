import json
import os
from datetime import datetime, timedelta

def load_policies():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    policy_path = os.path.join(base_dir, 'policies.json')
    with open(policy_path, 'r') as f:
        return json.load(f)

def get_allowed_offers(customer_id: str, risk_profile: dict) -> list:
    """
    Retorna las opciones válidas basadas en el riesgo.
    """
    offers = [{"id": "O1", "type": "PAY_NOW"}]
    
    if risk_profile.get("risk_level") in ["MEDIUM", "HIGH"]:
        # Permite extensión de acuerdo a policies.json (ej: 15 días max)
        policies = load_policies()
        max_days = policies.get("extension_max_days", 15)
        new_date = (datetime.now() + timedelta(days=max_days)).strftime("%Y-%m-%d")
        
        offers.append({
            "id": "O2",
            "type": "PROMISE_TO_PAY",
            "date": new_date
        })
        
        offers.append({
            "id": "O3",
            "type": "PARTIAL_PAYMENT",
            "min_percentage": policies.get("min_partial_payment_percentage", 20)
        })
    
    offers.append({"id": "O4", "type": "HUMAN_CALLBACK"})
    return offers

def validate_offer(offer_type: str, params: dict) -> bool:
    """
    Asegura que el agente no prometa cosas fuera de política.
    """
    policies = load_policies()
    
    if offer_type == "PROMISE_TO_PAY":
        requested_days = params.get("requested_days", 0)
        if requested_days > policies.get("extension_max_days", 15):
            return False
            
    if offer_type == "PARTIAL_PAYMENT":
        percentage = params.get("percentage", 0)
        if percentage < policies.get("min_partial_payment_percentage", 20):
            return False
            
    if offer_type == "WAIVER" and not policies.get("allow_interest_waiver", False):
        return False
        
    return True

def register_simulated_commitment(customer_id: str, offer_id: str) -> dict:
    return {
        "status": "SUCCESS",
        "customer_id": customer_id,
        "selected_offer": offer_id,
        "policy_result": "AUTHORIZED"
    }
