"""Scheme recommendation: hard eligibility filter then transparent ranking."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RankingWeights, Scheme, SchemeEligibilityRule, SourceCitation
from app.rules.engine import evaluate_rule, is_eligible, purpose_compatible
from app.services.freshness import freshness_state


def _fmt_money(n: Any) -> str:
    try:
        return f"₹{int(float(n)):,}"
    except (TypeError, ValueError):
        return str(n)


def _fail_reason(rule_type: str, actual: Any, expected: Any, operator: str) -> str:
    """Human explanation of why the applicant cannot use this scheme."""
    op = (operator or "").lower()
    if rule_type in {"income", "annual_family_income"}:
        if op in {"lte", "<="}:
            return (
                f"Your annual family income ({_fmt_money(actual)}) is above the scheme limit "
                f"({_fmt_money(expected)}). You currently do not meet this income criterion."
            )
        if op in {"gte", ">="}:
            return (
                f"Your annual family income ({_fmt_money(actual)}) is below the minimum required "
                f"({_fmt_money(expected)})."
            )
        return f"Your income ({_fmt_money(actual)}) does not meet the published income condition ({expected})."
    if rule_type in {"loan_amount", "loan_required"}:
        if op in {"lte", "<="}:
            return (
                f"Your requested loan ({_fmt_money(actual)}) is higher than the maximum allowed "
                f"({_fmt_money(expected)}) for this scheme."
            )
        if op in {"gte", ">="}:
            return (
                f"Your requested loan ({_fmt_money(actual)}) is below the minimum published amount "
                f"({_fmt_money(expected)})."
            )
        return f"Your loan amount ({_fmt_money(actual)}) does not fit this scheme's loan limits."
    if rule_type == "purpose":
        return (
            f"This scheme is for '{expected}' purposes, but you asked for '{actual}'. "
            "Purpose does not match, so this scheme is not suitable."
        )
    if rule_type == "category":
        allowed = ", ".join(str(v) for v in (expected if isinstance(expected, list) else [expected]))
        return f"Your category ({actual}) is not in the allowed beneficiary categories ({allowed})."
    if rule_type == "age":
        return f"Your age ({actual}) does not meet the published age condition for this scheme."
    if rule_type == "project_type":
        return f"Your project type ({actual}) does not match the activities covered by this scheme."
    return f"You do not meet the published '{rule_type}' condition for this scheme."


def _enrich_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for r in results:
        item = dict(r)
        if item.get("passed") is False:
            item["reason"] = _fail_reason(
                item.get("rule_type") or "",
                item.get("actual"),
                item.get("expected"),
                item.get("operator") or "",
            )
            item["gap"] = {
                "field": item.get("rule_type"),
                "your_value": item.get("actual"),
                "scheme_requires": item.get("expected"),
                "message": item["reason"],
            }
        enriched.append(item)
    return enriched


def _rules_from_scheme(scheme: Scheme) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if scheme.max_income is not None:
        rules.append(
            {
                "rule_type": "income",
                "operator": "lte",
                "value": scheme.max_income,
                "description": "Your family income is within the required limit.",
                "is_hard": True,
            }
        )
    if scheme.min_income is not None:
        rules.append(
            {
                "rule_type": "income",
                "operator": "gte",
                "value": scheme.min_income,
                "description": "Your family income meets the minimum published threshold.",
                "is_hard": True,
            }
        )
    if scheme.max_loan is not None:
        rules.append(
            {
                "rule_type": "loan_amount",
                "operator": "lte",
                "value": scheme.max_loan,
                "description": "Your requested loan is within the applicable limit.",
                "is_hard": True,
            }
        )
    if scheme.min_loan is not None:
        rules.append(
            {
                "rule_type": "loan_amount",
                "operator": "gte",
                "value": scheme.min_loan,
                "description": "Your requested loan meets the minimum published amount.",
                "is_hard": True,
            }
        )
    if scheme.beneficiary_requirements and isinstance(scheme.beneficiary_requirements, dict):
        cats = scheme.beneficiary_requirements.get("categories") or scheme.beneficiary_requirements.get("category")
        if cats:
            rules.append(
                {
                    "rule_type": "category",
                    "operator": "in",
                    "value": cats if isinstance(cats, list) else [cats],
                    "description": "Your category matches the published beneficiary requirement.",
                    "is_hard": True,
                }
            )
    if scheme.eligible_activities:
        acts = scheme.eligible_activities if isinstance(scheme.eligible_activities, list) else [scheme.eligible_activities]
        rules.append(
            {
                "rule_type": "project_type",
                "operator": "intersects",
                "value": [str(a).lower() for a in acts],
                "description": "Your project type matches the scheme.",
                "is_hard": False,
            }
        )
    if scheme.purpose:
        rules.append(
            {
                "rule_type": "purpose",
                "operator": "purpose_match",
                "value": scheme.purpose,
                "description": "Your purpose aligns with the scheme purpose.",
                "is_hard": True,
            }
        )
    elif scheme.scheme_type:
        st = (scheme.scheme_type or "").lower()
        if "education" in st:
            rules.append(
                {
                    "rule_type": "purpose",
                    "operator": "purpose_match",
                    "value": "education",
                    "description": "Your purpose aligns with the scheme purpose.",
                    "is_hard": True,
                }
            )
        elif any(k in st for k in ("micro", "term_loan", "business", "enterprise")):
            rules.append(
                {
                    "rule_type": "purpose",
                    "operator": "purpose_match",
                    "value": "business",
                    "description": "Your purpose aligns with the scheme purpose.",
                    "is_hard": True,
                }
            )
    return rules


def _score(
    profile: dict[str, Any],
    scheme: Scheme,
    rule_results: list[dict[str, Any]],
    weights: RankingWeights,
) -> tuple[float, dict[str, float]]:
    hard_pass = [r for r in rule_results if r.get("is_hard") and r["passed"] is True]
    hard_total = [r for r in rule_results if r.get("is_hard")]
    eligibility = (len(hard_pass) / len(hard_total) * 100) if hard_total else 50.0

    purpose_score = 0.0
    user_purpose = (profile.get("purpose") or "").lower()
    user_project = (profile.get("project_type") or "").lower()
    if purpose_compatible(user_purpose, scheme.purpose or scheme.scheme_type or ""):
        purpose_score = 100.0
    elif user_project and scheme.eligible_activities:
        acts = " ".join(
            str(a).lower()
            for a in (
                scheme.eligible_activities
                if isinstance(scheme.eligible_activities, list)
                else [scheme.eligible_activities]
            )
        )
        if user_project in acts or any(tok in acts for tok in user_project.split()):
            purpose_score = 90.0
        else:
            purpose_score = 20.0
    else:
        purpose_score = 20.0

    loan_score = 50.0
    loan = profile.get("loan_required")
    if loan is not None and scheme.max_loan:
        if scheme.min_loan and scheme.min_loan <= loan <= scheme.max_loan:
            loan_score = 100.0
        elif loan <= scheme.max_loan:
            loan_score = 80.0
        else:
            loan_score = 0.0

    cost_score = 50.0
    cost = profile.get("project_cost")
    if cost is not None and scheme.loan_percentage:
        cost_score = 70.0
    elif cost is not None:
        cost_score = 60.0

    other_score = 50.0
    if profile.get("state"):
        other_score += 10
    if scheme.last_verified:
        fs = freshness_state(scheme.last_verified)
        other_score += {"Fresh": 30, "Aging": 15, "Stale": 0, "Unknown": 0}.get(fs, 0)

    breakdown = {
        "eligibility": round(eligibility, 2),
        "purpose": round(purpose_score, 2),
        "loan_amount": round(loan_score, 2),
        "project_cost": round(cost_score, 2),
        "other": round(min(other_score, 100), 2),
    }
    total = (
        breakdown["eligibility"] * weights.eligibility
        + breakdown["purpose"] * weights.purpose
        + breakdown["loan_amount"] * weights.loan_amount
        + breakdown["project_cost"] * weights.project_cost
        + breakdown["other"] * weights.other
    ) / max(
        weights.eligibility + weights.purpose + weights.loan_amount + weights.project_cost + weights.other,
        1,
    )
    return round(total, 2), breakdown


def _scheme_card(
    scheme: Scheme,
    score: float,
    breakdown: dict,
    results: list[dict],
    citations: list,
    *,
    eligible: bool,
) -> dict[str, Any]:
    why = []
    gaps = []
    for r in results:
        if r["symbol"] == "pass":
            why.append({"status": "pass", "text": r["reason"]})
        elif r["symbol"] == "warning":
            why.append({"status": "warning", "text": r["reason"]})
        else:
            why.append({"status": "fail", "text": r["reason"]})
            if r.get("gap"):
                gaps.append(r["gap"])

    return {
        "scheme_id": scheme.id,
        "name": scheme.name,
        "scheme_type": scheme.scheme_type,
        "purpose": scheme.purpose,
        "description": scheme.description,
        "min_loan": scheme.min_loan,
        "max_loan": scheme.max_loan,
        "min_income": scheme.min_income,
        "max_income": scheme.max_income,
        "interest_rate": scheme.interest_rate,
        "interest_rate_type": scheme.interest_rate_type,
        "tenure": scheme.tenure,
        "moratorium": scheme.moratorium,
        "required_documents": scheme.required_documents,
        "application_process": scheme.application_process,
        "source_url": scheme.source_url,
        "last_verified": scheme.last_verified.isoformat() if scheme.last_verified else None,
        "freshness": freshness_state(scheme.last_verified),
        "status": scheme.status,
        "score": score,
        "score_breakdown": breakdown,
        "eligible": eligible,
        "eligibility_complete": eligible and not any(r["passed"] is None for r in results if r.get("is_hard")),
        "why": why,
        "gaps": gaps,
        "citations": [
            {
                "field_name": c.field_name,
                "source_url": c.source_url,
                "source_title": c.source_title,
                "source_section": c.source_section,
                "last_verified": c.last_verified.isoformat() if c.last_verified else None,
            }
            for c in citations
        ],
        "disclaimer": (
            "You appear to meet the published eligibility criteria based on the latest verified "
            "information available. Final approval is determined by the authorized channel partner."
            if eligible
            else (
                "This is the closest published scheme to your request, but you currently do not meet "
                "one or more eligibility conditions. It is shown only for guidance — not as an available option."
            )
        ),
        "unavailable_fields": [
            f
            for f, v in {
                "interest_rate": scheme.interest_rate,
                "max_loan": scheme.max_loan,
                "tenure": scheme.tenure,
                "required_documents": scheme.required_documents,
            }.items()
            if v is None
        ],
    }


def recommend_schemes(db: Session, profile: dict[str, Any]) -> dict[str, Any]:
    weights = db.query(RankingWeights).filter(RankingWeights.is_active.is_(True)).first()
    if not weights:
        settings = get_settings()
        weights = RankingWeights(
            name="default",
            eligibility=settings.weight_eligibility,
            purpose=settings.weight_purpose,
            loan_amount=settings.weight_loan_amount,
            project_cost=settings.weight_project_cost,
            other=settings.weight_other,
        )

    schemes = db.query(Scheme).filter(Scheme.status.in_(["active", "unavailable"])).all()
    recommendations = []
    near_misses = []

    for scheme in schemes:
        if not scheme.max_loan and not scheme.purpose and not scheme.scheme_type:
            continue

        db_rules = db.query(SchemeEligibilityRule).filter(SchemeEligibilityRule.scheme_id == scheme.id).all()
        derived = _rules_from_scheme(scheme)
        existing_types = {r.rule_type for r in db_rules}
        rules = list(db_rules) + [r for r in derived if r["rule_type"] not in existing_types]

        # Always enforce hard purpose match from scheme columns
        if scheme.purpose:
            rules = [
                r
                for r in rules
                if not (
                    (hasattr(r, "rule_type") and r.rule_type == "purpose")
                    or (isinstance(r, dict) and r.get("rule_type") == "purpose")
                )
            ]
            rules.append(
                {
                    "rule_type": "purpose",
                    "operator": "purpose_match",
                    "value": scheme.purpose,
                    "description": "Your purpose aligns with the scheme purpose.",
                    "is_hard": True,
                }
            )

        results = _enrich_results([evaluate_rule(r, profile) for r in rules])
        eligible, _missing = is_eligible(results)
        score, breakdown = _score(profile, scheme, results, weights)
        citations = (
            db.query(SourceCitation)
            .filter(SourceCitation.entity_type == "scheme", SourceCitation.entity_id == scheme.id)
            .all()
        )
        card = _scheme_card(scheme, score, breakdown, results, citations, eligible=eligible)

        if eligible:
            recommendations.append(card)
        else:
            hard_fails = [r for r in results if r.get("is_hard") and r.get("passed") is False]
            soft_fails = [r for r in results if not r.get("is_hard") and r.get("passed") is False]
            near_misses.append(
                {
                    **card,
                    "hard_fail_count": len(hard_fails),
                    "soft_fail_count": len(soft_fails),
                    "blocking_reasons": [r["reason"] for r in hard_fails],
                }
            )

    recommendations.sort(key=lambda x: x["score"], reverse=True)
    near_misses.sort(key=lambda x: (x["hard_fail_count"], -x["score"], x["soft_fail_count"]))

    if recommendations:
        return {
            "match_status": "matched",
            "count": len(recommendations),
            "recommendations": recommendations,
            "near_misses": [],
            "ineligible_count": len(near_misses),
            "message": None,
            "disclaimer": (
                "Information is compiled from official government sources and may change. "
                "The platform provides guidance and scheme matching based on the latest successfully "
                "verified information available to it. Final eligibility, sanction, interest rate, "
                "documentation requirements, and disbursement are subject to the applicable official "
                "rules and the authorized channel partner."
            ),
        }

    best = near_misses[:3]
    return {
        "match_status": "no_match",
        "count": 0,
        "recommendations": [],
        "near_misses": best,
        "ineligible_count": len(near_misses),
        "message": (
            "No scheme matches your need based on the published eligibility rules. "
            "Below is the closest scheme for reference, with clear reasons why you currently cannot avail it."
            if best
            else "No scheme matches your need based on the published eligibility rules available in the system."
        ),
        "disclaimer": (
            "Information is compiled from official government sources and may change. "
            "Closest-scheme suggestions are guidance only and do not mean you are eligible."
        ),
    }
