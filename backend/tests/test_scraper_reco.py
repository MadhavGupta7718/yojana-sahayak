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


def test_education_purpose_blocked_for_business_scheme():
    from app.rules.engine import purpose_compatible

    assert purpose_compatible("business", "education") is False
    assert purpose_compatible("self-employment", "business") is True
    rules = _rules_from_scheme(DummyScheme())
    profile = {
        "annual_family_income": 200000,
        "loan_required": 100000,
        "category": "SC",
        "purpose": "education",
    }
    results = [evaluate_rule(r, profile) for r in rules]
    eligible, _ = is_eligible(results)
    assert eligible is False
    purpose_fail = next(r for r in results if r["rule_type"] == "purpose")
    assert purpose_fail["passed"] is False


def test_discovery_accepts_any_http_host():
    assert is_government_domain("https://random-loan-blog.com/nsfdc") is False
    prop = propose_source("https://example.com/loan", "NSFDC loans")
    assert prop["enabled"] is False
    assert prop["discovery_status"] == "pending_review"
    assert prop["authority_level"] > 0


def test_discovery_accepts_gov():
    assert is_government_domain("https://nsfdc.nic.in/schemes") is True


def test_timeline_and_partner_geo_extraction():
    from scraper.extractors.facts import extract_document_schemes

    text = """
    Scheme Name: Livelihood Retail shop Scheme 01
    Purpose: business
    Maximum loan upto Rs. 3.50 lakh
    Interest rate 5.5%
    Annual family income limit Rs. 3 lakh
    Repayment period 36 months
    Availability: Lifetime
    Channel Partner
    Channel Partner Name: Sangaria Channel Partner Centre 01
    Organization: Rajasthan State Channelizing Agency
    State: Rajasthan
    District: Hanumangarh
    Address: Near Bus Stand, Sangaria, Hanumangarh, Rajasthan - 335804
    Phone: +91-9123456789
    Email: partner1@channeldesk.in
    Latitude: 29.7902
    Longitude: 74.4661
    """
    schemes = extract_document_schemes(text, url="https://example.com/livelihood-finance/")
    assert len(schemes) == 1
    payload = schemes[0]["payload"]
    assert payload["availability_type"] == "lifetime"
    assert payload["target_gender"] == "any"
    assert schemes[0]["partners"]
    partner = schemes[0]["partners"][0]
    assert partner["latitude"] == 29.7902
    assert partner["longitude"] == 74.4661
    assert "335804" in (partner.get("address") or "")


def test_target_gender_extraction_and_hard_filter():
    from scraper.extractors.facts import extract_scheme_fields
    from app.rules.engine import evaluate_rule

    women = extract_scheme_fields(
        "Scheme Name: Mahila Udyam Scheme\nTarget gender: female\nFor women entrepreneurs only\nMaximum loan Rs. 2 lakh",
        url="https://example.com/women",
    )["payload"]
    assert women["target_gender"] == "female"

    men = extract_scheme_fields(
        "Scheme Name: Men Transport Scheme\nThis scheme is published for men beneficiaries only.\nMaximum loan Rs. 2 lakh",
        url="https://example.com/men",
    )["payload"]
    assert men["target_gender"] == "male"

    neutral = extract_scheme_fields(
        "Scheme Name: General Livelihood Scheme\nMaximum loan Rs. 2 lakh",
        url="https://example.com/any",
    )["payload"]
    assert neutral["target_gender"] == "any"

    rule = {
        "rule_type": "gender",
        "operator": "gender_match",
        "value": "female",
        "description": "women only",
        "is_hard": True,
    }
    assert evaluate_rule(rule, {"gender": "male"})["passed"] is False
    assert evaluate_rule(rule, {"gender": "female"})["passed"] is True
    assert evaluate_rule(rule, {"gender": "prefer_not_to_say"})["passed"] is True
