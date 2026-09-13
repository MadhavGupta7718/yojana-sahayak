"""Configurable eligibility rule engine — rules are authoritative."""

from __future__ import annotations

from typing import Any, Optional

PURPOSE_FAMILIES = {
    "business": {
        "business",
        "self-employment",
        "self employment",
        "selfemployment",
        "agriculture",
        "enterprise",
        "micro",
        "term_loan",
        "micro_finance",
    },
    "education": {
        "education",
        "educational",
        "educational_loan",
        "study",
        "studies",
    },
}


def normalize_purpose(value: Any) -> str:
    text = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    compact = text.replace(" ", "")
    for family, aliases in PURPOSE_FAMILIES.items():
        normalized_aliases = {a.replace("_", " ").replace("-", " ") for a in aliases}
        compact_aliases = {a.replace(" ", "").replace("_", "").replace("-", "") for a in aliases}
        if text in normalized_aliases or compact in compact_aliases:
            return family
    if any(a in text for a in ("education", "educational", "study")):
        return "education"
    if any(a in text for a in ("business", "self employment", "agriculture", "enterprise", "micro", "term loan")):
        return "business"
    return text


def purpose_compatible(user_purpose: Any, scheme_purpose: Any) -> bool:
    u = normalize_purpose(user_purpose)
    s = normalize_purpose(scheme_purpose)
    if not u or not s:
        return False
    return u == s


def _get_profile_value(profile: dict[str, Any], rule_type: str) -> Any:
    mapping = {
        "income": "annual_family_income",
        "annual_family_income": "annual_family_income",
        "category": "category",
        "age": "age",
        "gender": "gender",
        "project_type": "project_type",
        "project_cost": "project_cost",
        "loan_amount": "loan_required",
        "loan_required": "loan_required",
        "education": "education_status",
        "education_status": "education_status",
        "location": "location",
        "state": "state",
        "district": "district",
        "purpose": "purpose",
        "occupation": "occupation",
    }
    key = mapping.get(rule_type, rule_type)
    return profile.get(key)


def evaluate_rule(rule: Any, profile: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a single SchemeEligibilityRule-like object."""
    rule_type = rule.rule_type if hasattr(rule, "rule_type") else rule["rule_type"]
    operator = rule.operator if hasattr(rule, "operator") else rule["operator"]
    value = rule.value if hasattr(rule, "value") else rule["value"]
    description = rule.description if hasattr(rule, "description") else rule.get("description")
    is_hard = rule.is_hard if hasattr(rule, "is_hard") else rule.get("is_hard", True)

    actual = _get_profile_value(profile, rule_type)
    missing = actual is None or actual == ""
    passed: Optional[bool]

    if missing:
        passed = None
        reason = f"This information ({rule_type}) is required to confirm eligibility."
        symbol = "warning"
    else:
        passed = _compare(actual, operator, value)
        if passed:
            reason = description or f"Your {rule_type} matches the published condition."
            symbol = "pass"
        else:
            reason = f"Your {rule_type} does not meet the published condition."
            symbol = "fail"

    return {
        "rule_type": rule_type,
        "operator": operator,
        "expected": value,
        "actual": actual,
        "passed": passed,
        "is_hard": is_hard,
        "reason": reason,
        "symbol": symbol,
    }


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    op = operator.lower()
    if op in {"eq", "==", "equals"}:
        return str(actual).strip().lower() == str(expected).strip().lower()
    if op in {"neq", "!="}:
        return str(actual).strip().lower() != str(expected).strip().lower()
    if op in {"gte", ">="}:
        return float(actual) >= float(expected)
    if op in {"lte", "<="}:
        return float(actual) <= float(expected)
    if op in {"gt", ">"}:
        return float(actual) > float(expected)
    if op in {"lt", "<"}:
        return float(actual) < float(expected)
    if op == "in":
        values = expected if isinstance(expected, list) else [expected]
        return str(actual).strip().lower() in {str(v).strip().lower() for v in values}
    if op == "contains":
        return str(expected).strip().lower() in str(actual).strip().lower()
    if op == "purpose_match":
        return purpose_compatible(actual, expected)
    if op == "between":
        low, high = expected[0], expected[1]
        return float(low) <= float(actual) <= float(high)
    if op == "intersects":
        actual_set = {str(actual).lower()} if not isinstance(actual, list) else {str(a).lower() for a in actual}
        expected_set = {str(e).lower() for e in (expected if isinstance(expected, list) else [expected])}
        return bool(actual_set & expected_set)
    if op == "gender_match":
        user_g = str(actual or "").strip().lower()
        target = str(expected or "any").strip().lower() or "any"
        if target in {"any", "both", "all", ""}:
            return True
        if user_g in {"prefer_not_to_say", "prefer-not-to-say", "na", ""}:
            return True
        return user_g == target
    return False


def is_eligible(rule_results: list[dict[str, Any]]) -> tuple[bool, bool]:
    """Return (eligible_enough_to_recommend, has_missing_required).

    Hard failures block. Missing hard fields do not auto-pass; scheme may still
    be shown with warnings if no hard failure occurred, but marked incomplete.
    """
    hard = [r for r in rule_results if r.get("is_hard", True)]
    has_fail = any(r["passed"] is False for r in hard)
    has_missing = any(r["passed"] is None for r in hard)
    return (not has_fail), has_missing
