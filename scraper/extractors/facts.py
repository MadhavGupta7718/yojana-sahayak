"""Extract structured scheme/partner facts from official page text."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from scraper.extractors.normalize import (
    canonical_key,
    normalize_whitespace,
    parse_indian_amount,
    parse_months,
    parse_percent,
)
from scraper.extractors.scheme_gate import is_loan_scheme_payload, is_non_scheme_document

SCHEME_NAME_HINTS = [
    r"micro\s*credit\s*finance",
    r"micro\s*finance\s*scheme",
    r"term\s*loan",
    r"educational\s*loan",
    r"vocational\s*education",
    r"skill\s*development",
    r"stand[\-\s]*up",
    r"green\s*business",
    r"mahila\s*samriddhi",
    r"laghu\s*vyavasay",
    r"unit\s*cost",
    r"scheme",
]

FIELD_PATTERNS = {
    "max_loan": [
        r"(?:maximum|max\.?|upto|up to|ceiling)\s*(?:loan|finance|assistance)?[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
        r"(?:loan\s*limit|finance\s*limit)[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
    ],
    "min_loan": [
        r"(?:minimum|min\.?)\s*(?:loan|finance)[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
    ],
    "interest_rate": [
        r"(?:interest\s*rate|rate\s*of\s*interest|roi)[^\d%]{0,40}((?:[0-9]|1[0-9]|20)(?:\.\d+)?\s*%)",
        r"(?:charge[sd]?|beneficiary)[^\d%]{0,40}((?:[0-9]|1[0-9]|20)(?:\.\d+)?\s*%)",
    ],
    "max_income": [
        r"(?:annual\s*(?:family\s*)?income|income\s*limit|income\s*ceiling)[^\d₹rs]{0,40}((?:₹|rs\.?)?\s*[\d,.]+\s*(?:lakh|lac|crore)?)",
    ],
    "tenure": [
        r"(?:repayment|repayment\s*period|tenure|loan\s*period)[^\d]{0,30}(\d+\s*(?:years?|months?|वर्ष|महीने)?)",
    ],
    "moratorium": [
        r"(?:moratorium|gestation)[^\d]{0,30}(\d+\s*(?:years?|months)?)",
    ],
}


DOC_KEYWORDS = [
    "identity proof", "aadhaar", "aadhar", "pan", "address proof", "income certificate",
    "caste certificate", "project report", "bank account", "passport size", "educational",
    "ration card", "voter", "driving licence", "passport",
]

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _first_match(patterns: list[str], text: str) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1)
    return None


def _parse_date_token(raw: str) -> Optional[datetime]:
    raw = normalize_whitespace(raw)
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", raw)
    if not m:
        m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", raw)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return datetime(y, mo, d, tzinfo=timezone.utc)
            except ValueError:
                return None
        return None
    day = int(m.group(1))
    month = _MONTHS.get(m.group(2).lower())
    year = int(m.group(3))
    if not month:
        return None
    try:
        return datetime(year, month, day, tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_timeline(text: str) -> dict[str, Any]:
    """Parse lifetime / period timeline. Missing values stay unset (UI shows NA)."""
    out: dict[str, Any] = {}
    if re.search(r"availability\s*:\s*lifetime|\blifetime\s+available\b|\bavailable\s+lifetime\b", text, re.I):
        out["availability_type"] = "lifetime"
        out["valid_from"] = None
        out["valid_to"] = None
        return out
    m = re.search(
        r"(?:scheme\s*period|validity|valid\s*(?:from|period)|available\s*from)\s*:?\s*"
        r"(.+?)\s+(?:to|–|-|until|till)\s+(.+?)(?:\.|$|\n)",
        text,
        re.I,
    )
    if m:
        start = _parse_date_token(m.group(1))
        end = _parse_date_token(m.group(2))
        out["availability_type"] = "period"
        out["valid_from"] = start.isoformat() if start else None
        out["valid_to"] = end.isoformat() if end else None
        return out
    return out


def extract_scheme_fields(text: str, page_title: str | None = None, url: str = "") -> dict[str, Any]:
    clean = normalize_whitespace(text)
    title = page_title or ""
    named = re.search(r"scheme\s*name\s*:\s*([^\n]{5,200})", text, re.I)
    if named:
        name = normalize_whitespace(named.group(1))
    else:
        name = title
        if not any(re.search(h, name, re.I) for h in SCHEME_NAME_HINTS):
            for h in SCHEME_NAME_HINTS:
                m = re.search(rf"([A-Z][A-Za-z0-9 \-]{{5,80}}{h}[A-Za-z0-9 \-]{{0,40}})", text, re.I)
                if m:
                    name = normalize_whitespace(m.group(1))
                    break
    if not name:
        name = "Unnamed scheme from official page"

    payload: dict[str, Any] = {
        "name": name[:500],
        "canonical_key": canonical_key(name),
        "source_url": url,
        "description": clean[:2000] if clean else None,
    }
    originals: dict[str, str] = {}

    raw_max = _first_match(FIELD_PATTERNS["max_loan"], text)
    if raw_max:
        val, orig = parse_indian_amount(raw_max)
        payload["max_loan"] = val
        originals["max_loan"] = orig

    raw_min = _first_match(FIELD_PATTERNS["min_loan"], text)
    if raw_min:
        val, orig = parse_indian_amount(raw_min)
        payload["min_loan"] = val
        originals["min_loan"] = orig

    raw_rate = _first_match(FIELD_PATTERNS["interest_rate"], text)
    if raw_rate:
        val, orig = parse_percent(raw_rate)
        payload["interest_rate"] = val
        originals["interest_rate"] = orig

    raw_income = _first_match(FIELD_PATTERNS["max_income"], text)
    if raw_income:
        val, orig = parse_indian_amount(raw_income)
        payload["max_income"] = val
        originals["max_income"] = orig

    raw_tenure = _first_match(FIELD_PATTERNS["tenure"], text)
    if raw_tenure:
        val, orig = parse_months(raw_tenure)
        payload["tenure"] = val
        originals["tenure"] = orig

    raw_mora = _first_match(FIELD_PATTERNS["moratorium"], text)
    if raw_mora:
        val, orig = parse_months(raw_mora)
        payload["moratorium"] = val
        originals["moratorium"] = orig

    docs = []
    lower = text.lower()
    for dk in DOC_KEYWORDS:
        if dk in lower:
            docs.append(dk.title())
    if docs:
        payload["required_documents"] = sorted(set(docs))

    if re.search(r"scheduled\s*caste|\bSC\b|अनुसूचित\s*जाति", text, re.I):
        payload["beneficiary_requirements"] = {"categories": ["SC"]}
    cat = re.search(r"beneficiary\s*category\s*:\s*([A-Za-z]+)", text, re.I)
    if cat:
        payload["beneficiary_requirements"] = {"categories": [cat.group(1).upper()]}

    if re.search(r"education|educational|vocational", text, re.I):
        payload["purpose"] = "education"
        payload["scheme_type"] = "educational_loan"
    elif re.search(r"micro|self[\-\s]*employment|business|enterprise|livelihood", text, re.I):
        payload["purpose"] = "business"
        payload["scheme_type"] = "term_loan"

    purpose_line = re.search(r"purpose\s*:\s*([a-zA-Z_\- ]+)", text, re.I)
    if purpose_line:
        payload["purpose"] = purpose_line.group(1).strip().lower().split()[0]

    payload.update(extract_timeline(text))
    payload["target_gender"] = extract_target_gender(text)

    return {"payload": payload, "original_text": originals}


def extract_target_gender(text: str) -> str:
    """
    Detect gender focus from scheme text.
    If not mentioned, return 'any' (suitable for both male and female).
    """
    t = text or ""
    # Explicit field first
    labeled = re.search(
        r"(?:target\s*gender|beneficiary\s*gender|gender\s*(?:focus|eligibility)?)\s*:\s*"
        r"(male|female|women|woman|men|man|both|any|all)\b",
        t,
        re.I,
    )
    if labeled:
        val = labeled.group(1).lower()
        if val in {"female", "women", "woman"}:
            return "female"
        if val in {"male", "men", "man"}:
            return "male"
        return "any"

    female_cues = re.search(
        r"\b("
        r"women[\s\-]?only|only\s+for\s+women|female\s+beneficiar|"
        r"mahila|women\s+entrepreneur|women\s+enterprise|"
        r"for\s+women|girl\s+student|women\s+and\s+girls|"
        r"exclusively\s+for\s+(?:women|females)"
        r")\b",
        t,
        re.I,
    )
    male_cues = re.search(
        r"\b("
        r"men[\s\-]?only|only\s+for\s+men|male\s+beneficiar|"
        r"for\s+men\b|exclusively\s+for\s+(?:men|males)"
        r")\b",
        t,
        re.I,
    )
    if female_cues and not male_cues:
        return "female"
    if male_cues and not female_cues:
        return "male"
    return "any"


def split_scheme_blocks(text: str) -> list[str]:
    """Split multi-scheme documents on explicit Scheme Name markers."""
    if not text:
        return []
    matches = list(re.finditer(r"(?:^|\n)\s*Scheme\s*Name\s*:", text, re.I))
    if not matches:
        return [text]
    blocks = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[start:end].strip()
        if block:
            blocks.append(block)
    return blocks or [text]


def extract_document_schemes(text: str, page_title: str | None = None, url: str = "") -> list[dict[str, Any]]:
    """Extract one or many schemes from a page/PDF."""
    if is_non_scheme_document(url, page_title or "", text or ""):
        return []

    blocks = split_scheme_blocks(text)
    results = []
    for block in blocks:
        title = page_title if len(blocks) == 1 else None
        data = extract_scheme_fields(block, title, url)
        if not is_loan_scheme_payload(data["payload"], url=url, text=block):
            continue
        partners = extract_structured_partners(
            block, url, linked_scheme_key=data["payload"].get("canonical_key")
        )
        data["partners"] = partners
        results.append(data)
    seen = set()
    unique = []
    for item in results:
        key = item["payload"].get("canonical_key")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _field_after(label: str, text: str) -> Optional[str]:
    m = re.search(rf"{label}\s*:\s*([^\n]+)", text, re.I)
    if m:
        return normalize_whitespace(m.group(1))
    # html_to_text may put label and value on adjacent lines
    m = re.search(rf"{label}\s*\n\s*([^\n]+)", text, re.I)
    if m:
        return normalize_whitespace(m.group(1))
    return None


def extract_structured_partners(
    text: str,
    url: str = "",
    linked_scheme_key: str | None = None,
) -> list[dict[str, Any]]:
    """Parse Channel Partner blocks with address and Latitude/Longitude."""
    if not re.search(r"channel\s*partner", text, re.I):
        return []

    chunks = re.split(r"(?i)(?=Channel\s+Partner(?:\s+Name)?\s*:)", text)
    partners: list[dict[str, Any]] = []
    for chunk in chunks:
        if not re.search(r"channel\s*partner\s*name\s*:", chunk, re.I):
            continue
        name = _field_after(r"Channel\s+Partner\s+Name", chunk)
        if not name or len(name) < 4:
            continue
        if _looks_like_person_or_job(name):
            continue

        lat_raw = _field_after(r"Latitude", chunk)
        lng_raw = _field_after(r"Longitude", chunk)
        lat = lng = None
        try:
            if lat_raw:
                lat = float(re.search(r"-?\d+(?:\.\d+)?", lat_raw).group(0))  # type: ignore[union-attr]
            if lng_raw:
                lng = float(re.search(r"-?\d+(?:\.\d+)?", lng_raw).group(0))  # type: ignore[union-attr]
        except (AttributeError, ValueError, TypeError):
            lat = lng = None

        partners.append(
            {
                "name": name[:500],
                "canonical_key": canonical_key(name),
                "partner_type": "channelizing_agency",
                "organization": _field_after(r"Organization", chunk),
                "state": _field_after(r"State", chunk),
                "district": _field_after(r"District", chunk),
                "address": _field_after(r"Address", chunk),
                "phone": _field_after(r"Phone", chunk),
                "email": _field_after(r"Email", chunk),
                "website": _field_after(r"Website", chunk),
                "latitude": lat,
                "longitude": lng,
                "source_url": url,
                "status": "active",
                "linked_scheme_key": linked_scheme_key,
            }
        )

    seen = set()
    unique = []
    for p in partners:
        if p["canonical_key"] in seen:
            continue
        seen.add(p["canonical_key"])
        unique.append(p)
    return unique[:200]


def _is_partner_source_url(url: str) -> bool:
    u = (url or "").lower()
    blocked = ("career", "recruit", "interview", "vacancy", "hr/", "/hr", "tender", "pratibha", "upsc")
    if any(b in u for b in blocked):
        return False
    allowed = (
        "channel-partner",
        "channel_partner",
        "channelpartner",
        "our-channel-partners",
        "channelising",
        "channelizing",
        "/sca",
        "state-channel",
    )
    return any(a in u for a in allowed)


def _looks_like_person_or_job(name: str) -> bool:
    n = name or ""
    if re.match(r"^(Mr\.|Ms\.|Mrs\.|Shri|Smt\.?|Dr\.)\b", n, re.I):
        return True
    if re.search(r"\b(Manager|Deputy|Assistant|Officer|Director|Candidate|Selected|Interview)\b", n, re.I):
        return True
    if re.search(r"\b(Pay Scale|Level E-|IDA Pattern|UPSC)\b", n, re.I):
        return True
    return False


def extract_partners(text: str, url: str = "") -> list[dict[str, Any]]:
    """Extract channel partners from structured blocks or legacy agency name lists."""
    structured = extract_structured_partners(text, url)
    if structured:
        return structured

    if url and not _is_partner_source_url(url):
        if not re.search(r"\bchannel\s*partners?\b", text, re.I):
            return []

    partners = []
    for m in re.finditer(
        r"(?P<name>[A-Z][A-Za-z0-9 &.,\-()]{8,120}(?:Corporation|Corporation Ltd|Nigam|Board|Agency|Bank|Society))",
        text,
    ):
        name = normalize_whitespace(m.group("name"))
        if _looks_like_person_or_job(name):
            continue
        if re.search(r"national scheduled castes finance", name, re.I):
            continue
        partners.append(
            {
                "name": name,
                "canonical_key": canonical_key(name),
                "partner_type": "channelizing_agency",
                "source_url": url,
                "status": "active",
                "latitude": None,
                "longitude": None,
            }
        )
    seen = set()
    unique = []
    for p in partners:
        if p["canonical_key"] in seen:
            continue
        seen.add(p["canonical_key"])
        unique.append(p)
    return unique[:100]


def extract_partner_categories(text: str, url: str = "") -> list[dict[str, Any]]:
    """Extract channel partner category rows when individual agency lists are PDF-only."""
    u = (url or "").lower()
    if any(b in u for b in ("career", "recruit", "interview", "vacancy", "hr/")):
        return []

    categories = [
        ("State Channelizing Agencies (SCAs)", "state_channelizing_agency"),
        ("Public Sector Banks (PSBs)", "public_sector_bank"),
        ("Regional Rural Banks (RRBs)", "regional_rural_bank"),
        ("Non-Banking Financial Company (NBFC-MFI)", "nbfc_mfi"),
        ("Co-operative Banks", "cooperative_bank"),
        ("Small Finance Banks (SFBs)", "small_finance_bank"),
        ("Cooperative Societies", "cooperative_society"),
        ("SIDBI (Development Bank channel)", "development_bank"),
    ]
    found = []
    partner_cue = re.search(
        r"\b(channel\s*partners?|channelising|channelizing|state\s+channelizing|SCAs?)\b",
        f"{url}\n{text}",
        re.I,
    )
    if not partner_cue and "faq" not in u:
        return []

    for label, ptype in categories:
        needle = label.split("(")[0].strip()
        if re.search(re.escape(needle), text, re.I) or re.search(re.escape(label), text, re.I):
            found.append(
                {
                    "name": label,
                    "canonical_key": canonical_key(f"nsfdc-partner-category-{label}"),
                    "partner_type": ptype,
                    "organization": "NSFDC Channel Partner Category",
                    "source_url": url,
                    "status": "active",
                    "latitude": None,
                    "longitude": None,
                    "address": None,
                }
            )
    return found
