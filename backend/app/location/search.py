"""Haversine distance and partner radius search."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Partner, PartnerSchemeMapping, PartnerStatus
from app.services.freshness import freshness_state


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def search_partners(
    db: Session,
    scheme_id: int,
    user_lat: float,
    user_lon: float,
    max_radius_km: Optional[int] = None,
) -> dict[str, Any]:
    if not (-90 <= user_lat <= 90 and -180 <= user_lon <= 180):
        raise ValueError("Invalid coordinates")

    settings = get_settings()
    steps = settings.partner_radius_steps or [20, 40, 60, 100]
    max_r = max_radius_km or settings.max_partner_radius_km
    steps = [s for s in steps if s <= max_r]
    if not steps:
        steps = [max_r]

    mappings = (
        db.query(PartnerSchemeMapping)
        .filter(
            PartnerSchemeMapping.scheme_id == scheme_id,
            PartnerSchemeMapping.eligibility_status.in_(["eligible", "authorized", "active"]),
        )
        .all()
    )
    partner_ids = [m.partner_id for m in mappings]
    if not partner_ids:
        # If no mapping yet, allow partners marked active but explain limited confidence
        partners = db.query(Partner).filter(Partner.status == "active").all()
        mapping_required = False
    else:
        partners = (
            db.query(Partner)
            .filter(Partner.id.in_(partner_ids), Partner.status.in_(["active", "authorized"]))
            .all()
        )
        mapping_required = True

    status_map = {
        s.partner_id: s
        for s in db.query(PartnerStatus).filter(PartnerStatus.partner_id.in_([p.id for p in partners])).all()
    }

    eligible: list[dict[str, Any]] = []
    for p in partners:
        if p.latitude is None or p.longitude is None:
            continue
        pst = status_map.get(p.id)
        # Do not invent NPA/fund; filter only if explicitly bad
        if pst and pst.status and pst.status.lower() in {"suspended", "ineligible", "blacklisted"}:
            continue
        dist = haversine_km(user_lat, user_lon, p.latitude, p.longitude)
        reasons = []
        if mapping_required:
            reasons.append("Supports recommended scheme")
        else:
            reasons.append("Scheme-specific partner mapping not available from official source; listed as active partner")
        reasons.append("Verified partner" if p.last_verified else "Partner record present")
        if p.last_verified:
            reasons.append(f"Data freshness: {freshness_state(p.last_verified)}")
        score = 0.0
        score += 40 if mapping_required else 20
        score += max(0, 30 - dist)  # closer is better within 30km contribution
        if p.last_verified:
            fs = freshness_state(p.last_verified)
            score += {"Fresh": 20, "Aging": 10, "Stale": 2, "Unknown": 0}.get(fs, 0)
        if pst and pst.status == "active":
            score += 10
        eligible.append(
            {
                "id": p.id,
                "name": p.name,
                "partner_type": p.partner_type,
                "organization": p.organization,
                "state": p.state,
                "district": p.district,
                "address": p.address,
                "phone": p.phone,
                "email": p.email,
                "website": p.website,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "distance_km": round(dist, 2),
                "source_url": p.source_url,
                "last_verified": p.last_verified.isoformat() if p.last_verified else None,
                "freshness": freshness_state(p.last_verified),
                "status": p.status,
                "partner_operational_status": {
                    "fund_utilization": pst.fund_utilization if pst else None,
                    "npa_status": pst.npa_status if pst else None,
                    "overdue_status": pst.overdue_status if pst else None,
                    "status": pst.status if pst else "Current status unavailable / Last verified status",
                    "last_verified": pst.last_verified.isoformat() if pst and pst.last_verified else None,
                    "note": (
                        None
                        if pst and (pst.npa_status or pst.fund_utilization or pst.overdue_status)
                        else "Current fund utilization / NPA / overdue data is not available from an authoritative source."
                    ),
                },
                "score": round(score, 2),
                "reasons": reasons,
            }
        )

    used_radius = None
    results: list[dict[str, Any]] = []
    for radius in steps:
        results = [e for e in eligible if e["distance_km"] <= radius]
        if results:
            used_radius = radius
            break

    results.sort(key=lambda x: (-x["score"], x["distance_km"]))
    return {
        "scheme_id": scheme_id,
        "searched_radii_km": steps,
        "matched_radius_km": used_radius,
        "max_radius_km": max_r,
        "count": len(results),
        "partners": results,
        "message": (
            None
            if results
            else f"No suitable authorized partners found within {max_r} km based on available official data."
        ),
    }
