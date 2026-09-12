import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/backend')))
from policy_engine import validate_offer, load_policies

def test_load_policies():
    policies = load_policies()
    assert "extension_max_days" in policies

def test_validate_valid_extension():
    assert validate_offer("PROMISE_TO_PAY", {"requested_days": 10}) == True

def test_validate_invalid_extension():
    assert validate_offer("PROMISE_TO_PAY", {"requested_days": 100}) == False

def test_validate_invalid_partial_payment():
    assert validate_offer("PARTIAL_PAYMENT", {"percentage": 10}) == False

def test_validate_waiver_not_allowed():
    assert validate_offer("WAIVER", {}) == False
