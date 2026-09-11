"""Local rule-based multilingual NLP with optional embeddings fallback."""

from __future__ import annotations

import re
from typing import Any, Optional

# Amount patterns: ₹1 lakh, Rs. 5,00,000, 100000, 1.25 लाख
AMOUNT_PATTERNS = [
    (re.compile(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d+)?)\s*(lakh|lac|lakhs|लाख)?", re.I), "currency"),
    (re.compile(r"([\d,]+(?:\.\d+)?)\s*(lakh|lac|lakhs|लाख)", re.I), "lakh"),
    (re.compile(r"([\d,]+(?:\.\d+)?)\s*(crore|करोड़)", re.I), "crore"),
    (re.compile(r"\b(\d{4,9})\b"), "raw"),
]

PURPOSE_KEYWORDS = {
    "business": [
        "business", "vyapar", "vyapaar", "व्यवसाय", "उद्यम", "enterprise", "self employment",
        "self-employment", "स्वरोजगार", "dukaan", "shop",
    ],
    "education": [
        "education", "educational", "study", "studies", "college", "university", "शिक्षा",
        "पढ़ाई", "padhai", "shiksha", "tuition",
    ],
    "agriculture": [
        "agriculture", "farming", "dairy", "डेयरी", "कृषि", "kheti", "poultry", "goatery",
        "animal husbandry", "पशुपालन",
    ],
}

PROJECT_KEYWORDS = {
    "dairy": ["dairy", "डेयरी", "milk", "दूध", "gaushala"],
    "tailoring": ["tailoring", "silai", "सिलाई", "boutique"],
    "kirana": ["kirana", "grocery", "किराना"],
    "transport": ["transport", "vehicle", "auto", "taxi", "परिवहन"],
    "education_loan": ["education loan", "शैक्षणिक ऋण", "tuition fee"],
    "micro_enterprise": ["micro", "microfinance", "सूक्ष्म", "small business"],
}

CATEGORY_KEYWORDS = {
    "SC": ["sc", "scheduled caste", "अनुसूचित जाति", "anusuchit jati", "dalit"],
    "ST": ["st", "scheduled tribe", "अनुसूचित जनजाति"],
    "OBC": ["obc", "other backward", "अन्य पिछड़ा"],
}

HINGLISH_MAP = {
    "mujhe": "",
    "chahiye": "",
    "ke liye": " for ",
    "loan": "loan",
    "vyavasay": "business",
    "udyam": "business",
}


def normalize_amount(text: str) -> Optional[float]:
    t = text.replace(",", "")
    for pattern, kind in AMOUNT_PATTERNS:
        m = pattern.search(t)
        if not m:
            continue
        num = float(m.group(1).replace(",", ""))
        unit = (m.group(2) if m.lastindex and m.lastindex >= 2 else None) or ""
        unit = unit.lower()
        if kind == "lakh" or unit in {"lakh", "lac", "lakhs", "लाख"}:
            return num * 100_000
        if kind == "crore" or unit in {"crore", "करोड़"}:
            return num * 10_000_000
        if kind == "currency" and unit in {"lakh", "lac", "lakhs", "लाख"}:
            return num * 100_000
        if kind in {"currency", "raw"} and num >= 1000:
            return num
    return None


def parse_intent(text: str) -> dict[str, Any]:
    original = text.strip()
    lower = original.lower()
    for k, v in HINGLISH_MAP.items():
        lower = lower.replace(k, v)

    purpose = None
    for p, kws in PURPOSE_KEYWORDS.items():
        if any(kw in lower or kw in original for kw in kws):
            purpose = p
            break

    project_type = None
    for p, kws in PROJECT_KEYWORDS.items():
        if any(kw in lower or kw in original for kw in kws):
            project_type = p
            if purpose is None:
                purpose = "business" if p != "education_loan" else "education"
            break

    category = None
    for c, kws in CATEGORY_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            category = c
            break

    loan_required = normalize_amount(original)

    age = None
    age_m = re.search(r"(?:age|उम्र|vayu|umra)\D{0,6}(\d{1,2})", lower)
    if age_m:
        age = int(age_m.group(1))

    income = None
    income_m = re.search(
        r"(?:income|आय|aay|salary|वेतन)[^\d₹rs]{0,20}((?:₹|rs\.?)?\s*[\d,]+(?:\.\d+)?\s*(?:lakh|lac|लाख|crore)?)",
        lower,
        re.I,
    )
    if income_m:
        income = normalize_amount(income_m.group(1))

    fields = {
        "loan_required": loan_required,
        "project_type": project_type,
        "purpose": purpose,
        "category": category,
        "age": age,
        "annual_family_income": income,
    }
    extracted = {k: v for k, v in fields.items() if v is not None}

    return {
        "original_text": original,
        "extracted": extracted,
        "method": "rule_based",
        "confidence": 0.55 + 0.1 * len(extracted),
        "notes": "Local rule-based NLP. Values are suggestions; user should confirm in the form.",
    }


def embedding_similarity(query: str, documents: list[str]) -> Optional[list[float]]:
    """Optional local embeddings; returns None if unavailable."""
    try:
        from app.config import get_settings

        settings = get_settings()
        if not settings.enable_embeddings:
            return None
        from sentence_transformers import SentenceTransformer
        import numpy as np

        model = SentenceTransformer(settings.embedding_model_name)
        q = model.encode([query], normalize_embeddings=True)
        d = model.encode(documents, normalize_embeddings=True)
        scores = (q @ d.T).flatten().tolist()
        return scores
    except Exception:
        return None
