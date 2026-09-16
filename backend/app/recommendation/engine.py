"""Scheme recommendation: hard eligibility filter then transparent ranking."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import RankingWeights, Scheme, SchemeEligibilityRule, SourceCitation
from app.rules.engine import evaluate_rule, is_eligible, purpose_compatible
from app.services.finance import calculate_emi
from app.services.freshness import freshness_state
from app.services.scheme_dedupe import active_unique_schemes, retire_stale_duplicates
from app.recommendation import localize as L
from scraper.extractors.scheme_gate import is_loan_scheme_record


def _timeline_display(scheme: Scheme, lang: str = "en") -> dict[str, Any]:
    atype = getattr(scheme, "availability_type", None)
    vf = getattr(scheme, "valid_from", None)
    vt = getattr(scheme, "valid_to", None)
    if atype == "lifetime":
        return {
            "availability_type": "lifetime",
            "valid_from": None,
            "valid_to": None,
            "label": L.lifetime_label(lang),
        }
    if atype == "period" or vf or vt:
        def _fmt(d):
            if not d:
                return L.na_label(lang)
            try:
                return d.strftime("%d %b %Y")
            except Exception:
                return L.na_label(lang)

        start = _fmt(vf)
        end = _fmt(vt)
        if start == L.na_label(lang) and end == L.na_label(lang):
            label = L.na_label(lang)
        elif start == L.na_label(lang):
            label = f"तक {end}" if lang == "hi" else f"Until {end}"
        elif end == L.na_label(lang):
            label = f"{start} से" if lang == "hi" else f"From {start}"
        else:
            label = f"{start} से {end}" if lang == "hi" else f"{start} to {end}"
        return {
            "availability_type": "period",
            "valid_from": vf.isoformat() if vf else None,
            "valid_to": vt.isoformat() if vt else None,
            "label": label,
        }
    return {
        "availability_type": None,
        "valid_from": None,
        "valid_to": None,
        "label": L.na_label(lang),
    }


def _fmt_money(n: Any) -> str:
    try:
        return f"₹{int(float(n)):,}"
    except (TypeError, ValueError):
        return str(n)


def _fail_reason(rule_type: str, actual: Any, expected: Any, operator: str, lang: str = "en") -> str:
    """Human explanation of why the applicant cannot use this scheme."""
    return L.fail_reason(rule_type, actual, expected, operator, lang)


def _enrich_results(results: list[dict[str, Any]], lang: str = "en") -> list[dict[str, Any]]:
    enriched = []
    for r in results:
        item = dict(r)
        if item.get("passed") is False:
            item["reason"] = _fail_reason(
                item.get("rule_type") or "",
                item.get("actual"),
                item.get("expected"),
                item.get("operator") or "",
                lang,
            )
            item["gap"] = {
                "field": item.get("rule_type"),
                "your_value": item.get("actual"),
                "scheme_requires": item.get("expected"),
                "message": item["reason"],
            }
        elif item.get("passed") is True:
            item["reason"] = L.pass_reason(
                item.get("rule_type") or "",
                lang,
                operator=item.get("operator") or "",
            )
        elif item.get("passed") is None:
            item["reason"] = L.missing_reason(item.get("rule_type") or "", lang)
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

    target_gender = (getattr(scheme, "target_gender", None) or "any").strip().lower() or "any"
    if target_gender not in {"any", "both", "all"}:
        gender_label = "women" if target_gender == "female" else "men"
        rules.append(
            {
                "rule_type": "gender",
                "operator": "gender_match",
                "value": target_gender,
                "description": f"This scheme is published for {gender_label} beneficiaries and matches your gender.",
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

    # Prefer gender-specific schemes that match the applicant (skip when prefer_not_to_say)
    user_g = str(profile.get("gender") or "").strip().lower()
    scheme_g = (getattr(scheme, "target_gender", None) or "any").strip().lower() or "any"
    if user_g in {"male", "female"} and scheme_g == user_g:
        other_score += 25
    elif user_g in {"male", "female"} and scheme_g in {"any", "both", "all", ""}:
        other_score += 5

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


def _target_gender_label(scheme: Scheme, lang: str = "en") -> str:
    return L.gender_label(getattr(scheme, "target_gender", None), lang)


def _scheme_card(
    scheme: Scheme,
    score: float,
    breakdown: dict,
    results: list[dict],
    citations: list,
    *,
    eligible: bool,
    lang: str = "en",
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
        "timeline": _timeline_display(scheme, lang),
        "target_gender": getattr(scheme, "target_gender", None) or "any",
        "target_gender_label": _target_gender_label(scheme, lang),
        "source_url": scheme.source_url,
        "last_verified": scheme.last_verified.isoformat() if scheme.last_verified else None,
        "freshness": L.freshness_label(freshness_state(scheme.last_verified), lang),
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
        "disclaimer": L.card_disclaimer(eligible, lang),
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


def _is_recommendable_scheme(scheme: Scheme) -> bool:
    """Skip crawl artifacts / meta pages that are not real loan schemes."""
    return is_loan_scheme_record(
        name=scheme.name or "",
        scheme_type=scheme.scheme_type,
        max_loan=scheme.max_loan,
        min_loan=scheme.min_loan,
        interest_rate=scheme.interest_rate,
        tenure=scheme.tenure,
        max_income=scheme.max_income,
        purpose=scheme.purpose,
        description=scheme.description,
        source_url=scheme.source_url,
        canonical_key=scheme.canonical_key,
    )


def recommend_schemes(db: Session, profile: dict[str, Any]) -> dict[str, Any]:
    lang = L.lang_code(profile)
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

    retired = retire_stale_duplicates(db)
    if retired:
        db.commit()
    schemes = active_unique_schemes(db)
    recommendations = []
    near_misses = []

    for scheme in schemes:
        if not _is_recommendable_scheme(scheme):
            continue
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

        results = _enrich_results([evaluate_rule(r, profile) for r in rules], lang)
        eligible, _missing = is_eligible(results)
        score, breakdown = _score(profile, scheme, results, weights)
        citations = (
            db.query(SourceCitation)
            .filter(SourceCitation.entity_type == "scheme", SourceCitation.entity_id == scheme.id)
            .all()
        )
        card = _scheme_card(scheme, score, breakdown, results, citations, eligible=eligible, lang=lang)

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

    top = recommendations[:10]
    for idx, card in enumerate(top):
        card["rank"] = idx + 1
        card["detail_level"] = "full" if idx < 3 else "summary"
        if idx < 3:
            principal = float(profile.get("loan_required") or card.get("max_loan") or 0)
            if card.get("interest_rate") is not None and card.get("tenure"):
                try:
                    card["emi_estimate"] = calculate_emi(
                        principal=principal,
                        annual_rate_percent=card.get("interest_rate"),
                        tenure_months=int(card["tenure"]),
                        moratorium_months=int(card.get("moratorium") or 0),
                    )
                except ValueError as exc:
                    card["emi_estimate"] = {"error": str(exc), "emi": None}
            else:
                card["emi_estimate"] = {
                    "emi": None,
                    "warnings": [L.emi_unavailable_warning(lang)],
                }
        else:
            card["emi_estimate"] = None

    suggestion = None
    if top:
        best = top[0]
        timeline = (best.get("timeline") or {}).get("label") or L.na_label(lang)
        pass_reasons = [w["text"] for w in (best.get("why") or []) if w.get("status") == "pass"][:3]
        why_bit = (L.key_matches_prefix(lang) + "; ".join(pass_reasons) + ".") if pass_reasons else ""
        suggestion = L.matched_suggestion(best["name"], best["score"], why_bit, timeline, lang)
        best["suggestion"] = suggestion

    if recommendations:
        return {
            "match_status": "matched",
            "count": len(top),
            "total_eligible": len(recommendations),
            "recommendations": top,
            "top_detailed": top[:3],
            "more_matches": top[3:],
            "suggestion": suggestion,
            "near_misses": [],
            "ineligible_count": len(near_misses),
            "message": None,
            "disclaimer": L.disclaimer_matched(lang),
        }

    best = [m for m in near_misses if _is_recommendable_scheme_card(m)][:3] or near_misses[:3]
    return {
        "match_status": "no_match",
        "count": 0,
        "total_eligible": 0,
        "recommendations": [],
        "top_detailed": [],
        "more_matches": [],
        "suggestion": None,
        "near_misses": best,
        "ineligible_count": len(near_misses),
        "message": L.no_match_message(bool(best), lang),
        "disclaimer": L.disclaimer_no_match(lang),
    }


def _is_recommendable_scheme_card(card: dict[str, Any]) -> bool:
    name = str(card.get("name") or "").lower()
    junk = ("shared eligibility", "support-myscheme", "support myscheme", "eligibility criteria")
    if any(j in name for j in junk):
        return False
    return bool(card.get("max_loan") is not None or card.get("interest_rate") is not None)
