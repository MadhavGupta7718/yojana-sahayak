from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.location.search import search_partners
from app.models import ApplicationGuidance, Scheme, SourceCitation, UserProfile
from app.recommendation.engine import recommend_schemes, _timeline_display
from app.schemas import EMIRequest, ForwardGeocodeRequest, NLPParseRequest, PartnerSearchRequest, ProfileInput, ReverseGeocodeRequest
from app.services.finance import calculate_emi
from app.services.freshness import freshness_state

router = APIRouter(prefix="/api/v1", tags=["public"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "YojanaSahayak"}


@router.get("/schemes")
def list_schemes(db: Session = Depends(get_db)):
    schemes = db.query(Scheme).filter(Scheme.status != "discontinued").order_by(Scheme.name).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "scheme_type": s.scheme_type,
            "purpose": s.purpose,
            "description": s.description,
            "min_loan": s.min_loan,
            "max_loan": s.max_loan,
            "interest_rate": s.interest_rate,
            "max_income": s.max_income,
            "tenure": s.tenure,
            "timeline": _timeline_display(s),
            "target_gender": getattr(s, "target_gender", None) or "any",
            "source_url": s.source_url,
            "last_verified": s.last_verified,
            "freshness": freshness_state(s.last_verified),
            "status": s.status,
        }
        for s in schemes
    ]


@router.get("/schemes/{scheme_id}")
def get_scheme(scheme_id: int, db: Session = Depends(get_db)):
    s = db.query(Scheme).filter(Scheme.id == scheme_id).first()
    if not s:
        raise HTTPException(404, "Scheme not found")
    citations = (
        db.query(SourceCitation)
        .filter(SourceCitation.entity_type == "scheme", SourceCitation.entity_id == s.id)
        .all()
    )
    guidance = db.query(ApplicationGuidance).filter(ApplicationGuidance.scheme_id == s.id).first()
    return {
        "id": s.id,
        "name": s.name,
        "scheme_type": s.scheme_type,
        "purpose": s.purpose,
        "description": s.description,
        "min_income": s.min_income,
        "max_income": s.max_income,
        "min_loan": s.min_loan,
        "max_loan": s.max_loan,
        "interest_rate": s.interest_rate,
        "interest_rate_type": s.interest_rate_type,
        "tenure": s.tenure,
        "moratorium": s.moratorium,
        "loan_percentage": s.loan_percentage,
        "beneficiary_requirements": s.beneficiary_requirements,
        "eligible_activities": s.eligible_activities,
        "required_documents": s.required_documents,
        "application_process": s.application_process,
        "timeline": _timeline_display(s),
        "target_gender": getattr(s, "target_gender", None) or "any",
        "source_url": s.source_url,
        "last_verified": s.last_verified,
        "freshness": freshness_state(s.last_verified),
        "status": s.status,
        "current_version": s.current_version,
        "citations": [
            {
                "field_name": c.field_name,
                "source_url": c.source_url,
                "source_title": c.source_title,
                "source_section": c.source_section,
                "last_verified": c.last_verified,
            }
            for c in citations
        ],
        "guidance": {
            "title": guidance.title,
            "steps": guidance.steps,
            "disclaimer": guidance.disclaimer,
            "source_url": guidance.source_url,
        }
        if guidance
        else {
            "title": "What to do next",
            "steps": [
                "Confirm your eligibility against the official scheme page.",
                "Identify the recommended channel partner.",
                "Contact or visit the partner.",
                "Carry the required documents listed from official sources.",
                "Ask the partner to confirm current scheme availability.",
                "Complete the official application process with the partner.",
            ],
            "disclaimer": (
                "Final sanction and disbursement are determined by the authorized channel partner "
                "and applicable government rules. This platform does not submit loan applications."
            ),
            "source_url": s.source_url,
        },
        "field_availability": {
            "interest_rate": s.interest_rate is not None,
            "max_loan": s.max_loan is not None,
            "tenure": s.tenure is not None,
            "required_documents": bool(s.required_documents),
        },
    }


@router.post("/assessments/recommend")
def recommend(body: ProfileInput, db: Session = Depends(get_db)):
    profile = body.model_dump()
    # Optionally persist anonymous profile without precise location coords
    user = UserProfile(**{k: v for k, v in profile.items() if k in UserProfile.__table__.columns.keys()})
    db.add(user)
    db.commit()
    result = recommend_schemes(db, profile)
    result["profile_id"] = user.id
    return result


@router.post("/finance/emi")
def emi(body: EMIRequest):
    try:
        return calculate_emi(
            principal=body.principal,
            annual_rate_percent=body.annual_rate_percent,
            tenure_months=body.tenure_months,
            moratorium_months=body.moratorium_months,
            repayment_frequency=body.repayment_frequency,
            moratorium_interest_known=body.moratorium_interest_known,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/partners/search")
def partners_search(body: PartnerSearchRequest, db: Session = Depends(get_db)):
    if body.latitude is None or body.longitude is None:
        # Manual location without coordinates: filter by state/district when available
        from sqlalchemy import or_

        from app.models import Partner, PartnerSchemeMapping

        mappings = (
            db.query(PartnerSchemeMapping)
            .filter(PartnerSchemeMapping.scheme_id == body.scheme_id)
            .all()
        )
        mapped_ids = {m.partner_id for m in mappings}

        q = db.query(Partner).filter(Partner.status.in_(["active", "authorized"]))
        if body.state:
            q = q.filter(Partner.state.ilike(f"%{body.state}%"))
        if body.district:
            q = q.filter(Partner.district.ilike(f"%{body.district}%"))
        partners = q.all()

        # If regional partners are not yet published with state metadata, show national listings
        fallback_note = None
        if not partners:
            national = (
                db.query(Partner)
                .filter(Partner.status.in_(["active", "authorized"]))
                .filter(or_(Partner.state.is_(None), Partner.state == ""))
                .all()
            )
            if mapped_ids:
                national = [p for p in national if p.id in mapped_ids] or national
            partners = national
            if partners:
                fallback_note = (
                    "No partners with matching state/district were found in the verified dataset. "
                    "Showing national channel-partner listings from the official source. "
                    "Use automatic location when partner coordinates are available for map search."
                )

        if mapped_ids and body.state:
            # Prefer mapped partners when regional filter returned results
            mapped_only = [p for p in partners if p.id in mapped_ids]
            if mapped_only:
                partners = mapped_only

        return {
            "scheme_id": body.scheme_id,
            "mode": "manual_region",
            "matched_radius_km": None,
            "count": len(partners),
            "partners": [
                {
                    "id": p.id,
                    "name": p.name,
                    "state": p.state,
                    "district": p.district,
                    "address": p.address,
                    "latitude": p.latitude,
                    "longitude": p.longitude,
                    "phone": p.phone,
                    "source_url": p.source_url,
                    "last_verified": p.last_verified,
                    "freshness": freshness_state(p.last_verified),
                    "distance_km": None,
                    "reasons": [
                        "Matched by state/district"
                        if (body.state and p.state)
                        else "National channel partner listing (state not published in source extract)",
                        "Supports recommended scheme" if p.id in mapped_ids or not mapped_ids else "Listed partner",
                    ],
                    "score": 50,
                    "partner_operational_status": {
                        "status": "Current status unavailable / Last verified status",
                        "note": "Fund/NPA data shown only when available from an authoritative source.",
                    },
                }
                for p in partners
            ],
            "message": fallback_note
            if partners
            else "No partners found for the given location details. Try another district/state or use current location if coordinates are available.",
            "privacy_note": "Location is used only to find nearby eligible channel partners.",
        }

    try:
        result = search_partners(db, body.scheme_id, body.latitude, body.longitude, body.max_radius_km)
        result["privacy_note"] = "Your location is used only to find nearby eligible channel partners."
        result["mode"] = "geocoordinate"
        return result
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/nlp/parse")
def nlp_parse(body: NLPParseRequest):
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from ml.inference.nlp import parse_intent

    return parse_intent(body.text)


@router.post("/geo/reverse")
def reverse_geocode(body: ReverseGeocodeRequest):
    """Resolve GPS coordinates to address / state / district via OpenStreetMap Nominatim."""
    import httpx

    lang = "hi,en" if body.language.lower().startswith("hi") else "en"
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "format": "jsonv2",
        "lat": body.latitude,
        "lon": body.longitude,
        "zoom": 14,
        "addressdetails": 1,
    }
    try:
        with httpx.Client(timeout=12.0) as client:
            res = client.get(
                url,
                params=params,
                headers={
                    "User-Agent": "YojanaSahayak/1.0 (local research; scheme guidance)",
                    "Accept-Language": lang,
                },
            )
            res.raise_for_status()
            data = res.json()
    except Exception as exc:
        raise HTTPException(502, f"Geocoding service unavailable: {exc}") from exc

    addr = data.get("address") or {}
    state = addr.get("state") or addr.get("region") or addr.get("state_district") or ""
    district = (
        addr.get("state_district")
        or addr.get("county")
        or addr.get("city_district")
        or addr.get("district")
        or addr.get("city")
        or addr.get("town")
        or addr.get("municipality")
        or ""
    )
    # Avoid duplicating state into district
    if district and state and district.strip().lower() == state.strip().lower():
        district = addr.get("city") or addr.get("town") or addr.get("suburb") or ""

    return {
        "latitude": body.latitude,
        "longitude": body.longitude,
        "display_name": data.get("display_name"),
        "state": state or None,
        "district": district or None,
        "address": addr,
    }


@router.post("/geo/forward")
def forward_geocode(body: ForwardGeocodeRequest):
    """Resolve state/district to map center via OpenStreetMap Nominatim."""
    import httpx

    lang = "hi,en" if body.language.lower().startswith("hi") else "en"
    q = ", ".join([p for p in [body.pin_code, body.district, body.state, "India"] if p])
    try:
        with httpx.Client(timeout=12.0) as client:
            res = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"format": "json", "limit": 1, "q": q},
                headers={
                    "User-Agent": "YojanaSahayak/1.0 (local research; scheme guidance)",
                    "Accept-Language": lang,
                },
            )
            res.raise_for_status()
            data = res.json()
    except Exception as exc:
        raise HTTPException(502, f"Geocoding service unavailable: {exc}") from exc

    if not data:
        return {"found": False, "latitude": None, "longitude": None, "label": q}
    hit = data[0]
    return {
        "found": True,
        "latitude": float(hit["lat"]),
        "longitude": float(hit["lon"]),
        "label": hit.get("display_name") or q,
    }
