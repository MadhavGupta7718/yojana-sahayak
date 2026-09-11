"""Scheme recommendation: hard eligibility filter then transparent ranking."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RankingWeights, Scheme, SchemeEligibilityRule, SourceCitation
from app.rules.engine import evaluate_rule, is_eligible
from app.services.freshness import freshness_state


SCHEME_FIELD_FALLBACK_RULES = [
    # Built from scheme columns when explicit rules are absent
]


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
                "operator": "contains",
                "value": scheme.purpose,
                "description": "Your purpose aligns with the scheme purpose.",
                "is_hard": False,
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
    scheme_purpose = (scheme.purpose or "").lower()
    scheme_name = (scheme.name or "").lower()
    if user_purpose and (user_purpose in scheme_purpose or user_purpose in scheme_name):
        purpose_score = 100.0
    elif user_project and scheme.eligible_activities:
        acts = " ".join(str(a).lower() for a in (scheme.eligible_activities if isinstance(scheme.eligible_activities, list) else [scheme.eligible_activities]))
        if user_project in acts or any(tok in acts for tok in user_project.split()):
            purpose_score = 90.0
        else:
            purpose_score = 30.0
    else:
        purpose_score = 40.0

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
        # soft signal only
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
    ineligible = []

    for scheme in schemes:
        db_rules = db.query(SchemeEligibilityRule).filter(SchemeEligibilityRule.scheme_id == scheme.id).all()
        # Merge DB rules with column-derived rules so later-filled fields (e.g. income) still apply
        derived = _rules_from_scheme(scheme)
        existing_types = {r.rule_type for r in db_rules}
        rules = list(db_rules) + [r for r in derived if r["rule_type"] not in existing_types]
        results = [evaluate_rule(r, profile) for r in rules]
        eligible, missing = is_eligible(results)

        # Hard filter: never recommend if hard fail
        if not eligible:
            ineligible.append({"scheme_id": scheme.id, "name": scheme.name, "reasons": results})
            continue

        score, breakdown = _score(profile, scheme, results, weights)
        citations = (
            db.query(SourceCitation)
            .filter(SourceCitation.entity_type == "scheme", SourceCitation.entity_id == scheme.id)
            .all()
        )
        why = []
        for r in results:
            if r["symbol"] == "pass":
                why.append({"status": "pass", "text": r["reason"]})
            elif r["symbol"] == "warning":
                why.append({"status": "warning", "text": r["reason"]})
            else:
                why.append({"status": "fail", "text": r["reason"]})

        recommendations.append(
            {
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
                "eligibility_complete": not missing,
                "why": why,
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
        )

    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return {
        "count": len(recommendations),
        "recommendations": recommendations,
        "ineligible_count": len(ineligible),
        "disclaimer": (
            "Information is compiled from official government sources and may change. "
            "The platform provides guidance and scheme matching based on the latest successfully "
            "verified information available to it. Final eligibility, sanction, interest rate, "
            "documentation requirements, and disbursement are subject to the applicable official "
            "rules and the authorized channel partner."
        ),
    }
