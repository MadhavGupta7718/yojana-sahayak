"""Additional scraper/recommendation/security tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from app.recommendation.engine import _rules_from_scheme
from app.rules.engine import evaluate_rule, is_eligible
from scraper.discovery import is_government_domain, propose_source
from scraper.extractors.facts import extract_scheme_fields
from scraper.parsers.content import html_to_text


class DummyScheme:
    max_income = 500000
    min_income = None
    max_loan = 125000
    min_loan = None
    beneficiary_requirements = {"categories": ["SC"]}
    eligible_activities = ["dairy", "micro enterprise"]
    purpose = "business"
    name = "Micro Finance Scheme"


def test_html_extraction():
    html = "<html><head><title>T</title></head><body><script>x</script><h1>Scheme</h1><p>Interest rate 6.5%</p></body></html>"
    text = html_to_text(html)
    assert "Interest rate 6.5%" in text
    assert "x" not in text or "script" not in text.lower()


def test_scheme_field_extraction():
    text = """
    Micro Finance Scheme
    Maximum loan upto Rs. 1.25 lakh
    Interest rate 6.5% per annum
    Annual family income limit Rs. 3 lakh
    Repayment period 36 months
    Scheduled Caste beneficiaries
    Required: identity proof, caste certificate, project report
    """
    data = extract_scheme_fields(text, "Micro Finance Scheme", "https://nsfdc.nic.in/schemes")
    payload = data["payload"]
    assert payload["max_loan"] == 125000
    assert payload["interest_rate"] == 6.5
    assert payload["max_income"] == 300000
    assert payload["tenure"] == 36
    assert "Caste Certificate" in payload["required_documents"] or "caste certificate" in [
        d.lower() for d in payload["required_documents"]
    ]


def test_hash_change_detection():
    from scraper.extractors.normalize import content_hash

    a = content_hash("Maximum Loan = ₹1.25 lakh")
    b = content_hash("Maximum Loan = ₹1.40 lakh")
    assert a != b


def test_ineligible_hard_filter():
    rules = _rules_from_scheme(DummyScheme())
    profile = {"annual_family_income": 900000, "loan_required": 50000, "category": "SC"}
    results = [evaluate_rule(r, profile) for r in rules]
    eligible, _ = is_eligible(results)
    assert eligible is False


def test_eligible_user():
    rules = _rules_from_scheme(DummyScheme())
    profile = {
        "annual_family_income": 200000,
        "loan_required": 100000,
        "category": "SC",
        "project_type": "dairy",
        "purpose": "business",
    }
    results = [evaluate_rule(r, profile) for r in rules]
    eligible, missing = is_eligible(results)
    assert eligible is True


def test_discovery_rejects_blog():
    assert is_government_domain("https://random-loan-blog.com/nsfdc") is False
    prop = propose_source("https://example.com/loan", "NSFDC loans")
    assert prop["enabled"] is False
    assert prop["discovery_status"] == "pending_review"


def test_discovery_accepts_gov():
    assert is_government_domain("https://nsfdc.nic.in/schemes") is True
