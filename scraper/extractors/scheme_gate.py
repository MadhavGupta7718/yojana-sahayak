"""Decide whether scraped text/payload is a real loan scheme vs policy/FAQ/noise."""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import urlparse

# URL / path cues that are almost never scheme pages
NON_SCHEME_URL_HINTS = (
    "privacy",
    "terms-of-use",
    "terms_of_use",
    "termsofuse",
    "copyright",
    "hyperlink",
    "accessibility",
    "security-policy",
    "security_policy",
    "monitoring",
    "contingency",
    "about-us",
    "aboutus",
    "/faq",
    "faqs",
    "dashboard",
    "sign-in",
    "signin",
    "login",
    "t-and-c",
    "tnc",
    "cookie",
    "disclaimer",
    "sitemap",
    "contact-us",
    "careers",
    "recruit",
)

# Title / scheme-name cues for policy and portal chrome pages
NON_SCHEME_NAME_HINTS = (
    "privacy policy",
    "terms of use",
    "terms & conditions",
    "terms and conditions",
    "copyright policy",
    "hyperlinking policy",
    "accessibility statement",
    "security policy",
    "monitoring policy",
    "contingency management",
    "about us",
    "frequently asked",
    "faq",
    "dashboard",
    "sign out",
    "something went wrong",
    "t&c for url",
    "conditions for hosting",
    "links to myscheme",
    "shared eligibility",
    "support-myscheme",
    "support myscheme",
    "unnamed scheme",
    "home page",
    "our mission is to streamline",
    "our vision",
    "powered by digital india",
    "department of social justice and empowerment - government of india",
    "schemes | department of social justice",
    "copyright policy",
    "material featured on this platform",
)

SCHEME_POSITIVE_NAME = re.compile(
    r"\b("
    r"scheme|yojana|term\s*loan|micro[\s\-]?finance|micro[\s\-]?credit|"
    r"educational\s*loan|vocational|udyam|aajeevika|mahila\s*samriddhi|"
    r"laghu\s*vyavasay|green\s*business|standup|stand[\-\s]?up"
    r")\b",
    re.I,
)

FINANCIAL_HINT = re.compile(
    r"(maximum\s*loan|max\.?\s*loan|loan\s*limit|interest\s*rate|rate\s*of\s*interest|"
    r"repayment\s*period|₹|rs\.?\s*[\d,]+\s*(?:lakh|lac|crore)?)",
    re.I,
)


def _blob(*parts: Optional[str]) -> str:
    return " ".join((p or "").lower() for p in parts)


def is_non_scheme_document(url: str = "", title: str = "", text: str = "") -> bool:
    """True when the page is policy / FAQ / portal chrome, not a loan scheme."""
    path = (urlparse(url).path or "").lower()
    host_path = f"{urlparse(url).netloc}{path}".lower()
    if any(h in path or h in host_path for h in NON_SCHEME_URL_HINTS):
        return True

    head = _blob(title, text[:800])
    if any(h in head for h in NON_SCHEME_NAME_HINTS):
        return True

    # myScheme SPA error chrome often leaks into extracted text
    if "something went wrong" in head and "sign out" in head:
        return True
    if "are you sure you want to sign out" in head:
        return True

    return False


def is_loan_scheme_payload(payload: dict[str, Any], *, url: str = "", text: str = "") -> bool:
    """
    Accept only payloads that look like real loan / assistance schemes.
    Requires: not a non-scheme page, and either financial facts or a strong scheme name
    plus at least one financial cue in text/description.
    """
    name = str(payload.get("name") or "")
    stype = str(payload.get("scheme_type") or "").lower()
    desc = str(payload.get("description") or "")
    source_url = str(payload.get("source_url") or url or "")

    if stype in {"eligibility_reference", "shared_eligibility", "navigation", "policy", "faq"}:
        return False

    if is_non_scheme_document(source_url, name, text or desc):
        return False

    name_l = name.lower().strip()
    if any(h in name_l for h in NON_SCHEME_NAME_HINTS):
        return False

    has_finance = any(
        payload.get(k) is not None for k in ("max_loan", "min_loan", "interest_rate", "tenure", "max_income")
    )
    strong_name = bool(SCHEME_POSITIVE_NAME.search(name))
    text_has_finance = bool(FINANCIAL_HINT.search(f"{name}\n{desc}\n{text[:2000]}"))

    # Hard require some loan/finance signal — policy pages must not pass
    if not has_finance and not (strong_name and text_has_finance):
        return False

    # Names without scheme/loan/yojana and without numbers in finance fields are weak
    if not strong_name and not has_finance:
        return False

    # Reject very short generic titles that are just site chrome
    if len(name_l) < 8:
        return False
    if name_l in {"myscheme", "schemes", "home", "dashboard", "faq", "about"}:
        return False

    return True


def is_loan_scheme_record(
    *,
    name: str = "",
    scheme_type: Optional[str] = None,
    max_loan: Any = None,
    min_loan: Any = None,
    interest_rate: Any = None,
    tenure: Any = None,
    max_income: Any = None,
    purpose: Optional[str] = None,
    description: Optional[str] = None,
    source_url: Optional[str] = None,
    canonical_key: Optional[str] = None,
) -> bool:
    """ORM / listing helper wrapping is_loan_scheme_payload."""
    return is_loan_scheme_payload(
        {
            "name": name,
            "scheme_type": scheme_type,
            "max_loan": max_loan,
            "min_loan": min_loan,
            "interest_rate": interest_rate,
            "tenure": tenure,
            "max_income": max_income,
            "purpose": purpose,
            "description": description,
            "source_url": source_url,
            "canonical_key": canonical_key,
        },
        url=source_url or "",
        text=description or "",
    )
