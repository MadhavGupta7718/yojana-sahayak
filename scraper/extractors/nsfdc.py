"""NSFDC-specific structured extraction from official scheme pages."""

from __future__ import annotations

import re
from typing import Any

from scraper.extractors.normalize import canonical_key, normalize_whitespace, parse_indian_amount, parse_months, parse_percent

SCHEME_SPLIT = re.compile(
    r"(?:^|\n)\s*\d+\s*\n\s*(Micro Finance Scheme(?:\s*\(MFS\))?|Term Loan|Aajeevika Micro-Finance Yojana|"
    r"Udyam Nidhi Yojana(?:\s*\(UNY\))?|Educational Loan Scheme(?:\s*\(ELS\))?|"
    r"Mahila Samriddhi Yojana|Laghu Vyavasay Yojana|Green Business Scheme|"
    r"Vocational Education(?:\s*&?\s*Training)?(?:\s*Loan)?|"
    r"[A-Z][A-Za-z0-9 &/\-()]{5,80}(?:Scheme|Yojana)(?:\s*\([A-Z]+\))?)\s*(?:\n|$)",
    re.I,
)


def _beneficiary_rate(section: str) -> float | None:
    # Prefer beneficiary rate when SCA/CA rate and beneficiary rate both present
    m = re.search(
        r"(?:shall charge|charge[sd]?)\s*(?:interest\s*)?(?:@\s*)?([\d.]+)\s*%\s*from the (?:SCAs|CAs).*?"
        r"(?:shall charge|charge)\s*([\d.]+)\s*%\s*from the [Bb]eneficiar",
        section,
        re.I | re.S,
    )
    if m:
        return float(m.group(2))
    m = re.search(r"Beneficiary[^\d%]{0,40}([\d.]+)\s*%", section, re.I)
    if m:
        return float(m.group(1))
    # Table style: 2.5% then 6.5% after CAs / Beneficiary headers
    rates = re.findall(r"([\d.]+)\s*%", section)
    # Avoid ISO 9001 etc by requiring rates typically <= 20
    rates = [float(r) for r in rates if float(r) <= 20]
    if len(rates) >= 2:
        return rates[1]
    if rates:
        return rates[0]
    return None


def _max_loan(section: str) -> float | None:
    # Prefer explicit maximum loan limit block
    block = section
    mblock = re.search(r"Maximum Loan Limit(.{0,500})", section, re.I | re.S)
    if mblock:
        block = mblock.group(1)
    patterns = [
        r"maximum(?:\s*amount)?(?:\s*of)?(?:\s*up to)?\s*(?:₹|Rs\.?)?\s*([\d.,]+)\s*(lakh|lac|crore)?",
        r"(?:i\.e\.\s*)?up to\s*(?:₹|Rs\.?)?\s*([\d.,]+)\s*(lakh|lac|Lakh|crore)",
        r"upto\s*(?:₹|Rs\.?)?\s*([\d.,]+)\s*(lakh|lac|Lakh|crore)",
        r"and up to\s*(?:₹|Rs\.?)?\s*([\d.,]+)\s*(lakh|lac|crore)",
    ]
    for p in patterns:
        m = re.search(p, block, re.I)
        if m:
            raw = m.group(0)
            val, _ = parse_indian_amount(raw)
            if val and val >= 1000:
                return val
    return None


def extract_nsfdc_schemes(text: str, url: str = "") -> list[dict[str, Any]]:
    clean = text.replace("\xa0", " ").replace("\r", "")
    # Only run on pages that look like NSFDC scheme listing
    if not re.search(r"Micro Finance Scheme|Educational Loan Scheme|Term Loan", clean, re.I):
        return []

    parts = SCHEME_SPLIT.split(clean)
    # split keeps delimiters: [preamble, name1, body1, name2, body2, ...]
    schemes: list[dict[str, Any]] = []
    i = 1
    while i + 1 < len(parts):
        name = normalize_whitespace(parts[i])
        body = parts[i + 1]
        i += 2
        if len(name) < 4:
            continue
        section = name + "\n" + body[:4000]
        originals: dict[str, str] = {}

        max_loan = _max_loan(section)
        if max_loan:
            originals["max_loan"] = f"extracted from NSFDC scheme section for {name}"

        rate = _beneficiary_rate(section)
        if rate is not None:
            originals["interest_rate"] = f"beneficiary rate from NSFDC scheme section for {name}"

        tenure = None
        tm = re.search(
            r"(?:repayment period|repaid|within(?:\s*a)?(?:\s*maximum)?(?:\s*period)?(?:\s*of)?|"
            r"installments?(?:\s*of)?(?:\s*up to)?)\s*"
            r"([^\n.]{0,100}?(?:\d+\s*(?:years?|months?)|(?:one|two|three|four|five|six|seven|eight|nine|ten|twelve)\s*years?))",
            section,
            re.I,
        )
        if tm:
            tenure, originals["tenure"] = parse_months(tm.group(1))

        moratorium = None
        mm = re.search(r"(\d+\s*[- ]?month(?:s)?)\s*moratorium", section, re.I)
        if mm:
            moratorium, originals["moratorium"] = parse_months(mm.group(1))

        loan_pct = None
        pm = re.search(r"up to\s*([\d.]+)\s*%\s*of the\s*project\s*cost", section, re.I)
        if pm:
            loan_pct = float(pm.group(1))

        purpose = "education" if re.search(r"education", name, re.I) else "business"
        scheme_type = "educational_loan" if purpose == "education" else "term_loan"
        if re.search(r"micro", name, re.I):
            scheme_type = "micro_finance"

        # Project cost ceiling sometimes stated separately
        project_cost_max = None
        pcm = re.search(
            r"(?:units? costing|projects? costing).*?(?:up to|more than).*?(?:₹|Rs\.?)?\s*([\d.,]+)\s*(lakh|lac|crore)",
            section,
            re.I,
        )
        if pcm:
            project_cost_max, _ = parse_indian_amount(pcm.group(0))

        payload = {
            "name": name,
            "canonical_key": canonical_key(f"nsfdc-{name}"),
            "scheme_type": scheme_type,
            "purpose": purpose,
            "description": normalize_whitespace(body)[:1500],
            "max_loan": max_loan,
            "interest_rate": rate,
            "interest_rate_type": "beneficiary_pa" if rate is not None else None,
            "tenure": tenure,
            "moratorium": moratorium,
            "loan_percentage": loan_pct,
            "beneficiary_requirements": {"categories": ["SC"]},
            "source_url": url,
            "status": "active",
        }
        if project_cost_max:
            payload["raw_fields"] = {"project_cost_context": project_cost_max}

        schemes.append({"payload": payload, "original_text": originals})

    return schemes


def extract_nsfdc_eligibility(text: str, url: str = "") -> dict[str, Any] | None:
    if not re.search(r"eligibility|Scheduled Caste|annual family income", text, re.I):
        return None
    max_income = None
    m = re.search(r"annual family income.*?not exceed\s*(?:₹|Rs\.?)?\s*([\d.,]+)\s*(lakh|lac)?", text, re.I | re.S)
    if m:
        max_income, orig = parse_indian_amount(m.group(0))
    else:
        orig = None
    return {
        "max_income": max_income,
        "beneficiary_requirements": {"categories": ["SC"]},
        "source_url": url,
        "original_text": {"max_income": orig} if orig else {},
        "application_process": (
            "Apply through the concerned State Channelizing Agencies (SCAs) or Channelizing Agencies (CAs). "
            "NSFDC does not entertain direct applications from beneficiaries."
        )
        if re.search(r"State Channelizing Agencies", text, re.I)
        else None,
    }
