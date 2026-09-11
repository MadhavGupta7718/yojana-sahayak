"""Tests for finance calculator, rules, location, NLP, normalize."""

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.rules.engine import evaluate_rule, is_eligible
from app.services.finance import calculate_emi
from app.location.search import haversine_km
from ml.inference.nlp import normalize_amount, parse_intent
from scraper.extractors.normalize import content_hash, parse_indian_amount, parse_percent


def test_emi_basic():
    result = calculate_emi(100000, 6.5, 36, 0)
    assert result["estimated"] is True
    assert result["emi"] > 0
    assert result["total_repayment"] > 100000


def test_emi_missing_rate():
    result = calculate_emi(100000, None, 36)
    assert result["emi"] is None
    assert "not available" in result["warnings"][0].lower()


def test_emi_moratorium_warning():
    result = calculate_emi(100000, 6.5, 36, moratorium_months=6, moratorium_interest_known=False)
    assert any("moratorium" in w.lower() for w in result["warnings"])


def test_haversine_delhi_noida():
    # Approx Delhi -> Noida
    d = haversine_km(28.6139, 77.2090, 28.5355, 77.3910)
    assert 15 < d < 35


def test_haversine_same_point():
    assert haversine_km(28.6, 77.2, 28.6, 77.2) == 0


def test_rule_income_pass():
    rule = {"rule_type": "income", "operator": "lte", "value": 500000, "is_hard": True}
    r = evaluate_rule(rule, {"annual_family_income": 300000})
    assert r["passed"] is True


def test_rule_income_fail():
    rule = {"rule_type": "income", "operator": "lte", "value": 500000, "is_hard": True}
    r = evaluate_rule(rule, {"annual_family_income": 800000})
    assert r["passed"] is False


def test_rule_missing():
    rule = {"rule_type": "category", "operator": "in", "value": ["SC"], "is_hard": True}
    r = evaluate_rule(rule, {})
    assert r["passed"] is None
    eligible, missing = is_eligible([r])
    assert eligible is True
    assert missing is True


def test_boundary_loan():
    rule = {"rule_type": "loan_amount", "operator": "lte", "value": 125000, "is_hard": True}
    assert evaluate_rule(rule, {"loan_required": 125000})["passed"] is True
    assert evaluate_rule(rule, {"loan_required": 125001})["passed"] is False


def test_nlp_english():
    out = parse_intent("I want a loan for a dairy business of 1 lakh")
    assert out["extracted"].get("purpose") in {"business", "agriculture"}
    assert out["extracted"].get("project_type") == "dairy"
    assert out["extracted"].get("loan_required") == 100000


def test_nlp_hindi():
    out = parse_intent("मुझे डेयरी व्यवसाय शुरू करने के लिए ऋण चाहिए।")
    assert out["extracted"].get("project_type") == "dairy"


def test_nlp_hinglish():
    out = parse_intent("Mujhe dairy business ke liye loan chahiye")
    assert out["extracted"].get("project_type") == "dairy"


def test_normalize_amount_lakh():
    val, _ = parse_indian_amount("₹5 lakh")
    assert val == 500000


def test_normalize_percent():
    val, _ = parse_percent("6.5%")
    assert val == 6.5


def test_content_hash_stable():
    assert content_hash("abc") == content_hash("abc")
    assert content_hash("abc") != content_hash("abd")


def test_normalize_amount_helper():
    assert normalize_amount("Rs. 5,00,000") == 500000
