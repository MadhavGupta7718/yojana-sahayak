"""Local hybrid NLP: rule-based extraction + optional multilingual embeddings."""

from __future__ import annotations

import re
from functools import lru_cache
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
        "self-employment", "स्वरोजगार", "dukaan", "shop", "startup", "workshop", "factory",
        "नौकरी नहीं", "खुद का काम",
    ],
    "education": [
        "education", "educational", "study", "studies", "college", "university", "शिक्षा",
        "पढ़ाई", "padhai", "shiksha", "tuition", "mba", "btech", "degree",
    ],
    "agriculture": [
        "agriculture", "farming", "dairy", "डेयरी", "कृषि", "kheti", "poultry", "goatery",
        "animal husbandry", "पशुपालन", "मछली", "fishery",
    ],
}

PROJECT_KEYWORDS = {
    "dairy": ["dairy", "डेयरी", "milk", "दूध", "gaushala", "cattle", "buffalo"],
    "tailoring": ["tailoring", "silai", "सिलाई", "boutique", "garment"],
    "kirana": ["kirana", "grocery", "किराना", "general store"],
    "transport": ["transport", "vehicle", "auto", "taxi", "परिवहन", "truck"],
    "education_loan": ["education loan", "शैक्षणिक ऋण", "tuition fee", "hostel fee"],
    "micro_enterprise": ["micro", "microfinance", "सूक्ष्म", "small business", "chhote business"],
    "beauty_parlour": ["beauty", "parlour", "salon", "पार्लर"],
    "agriculture": ["agriculture", "farming", "kheti", "कृषि", "crop"],
    "poultry": ["poultry", "chicken", "मुर्गी"],
    "services": ["repair", "service", "services", "मरम्मत"],
}

CATEGORY_KEYWORDS = {
    "SC": ["sc", "scheduled caste", "अनुसूचित जाति", "anusuchit jati", "dalit"],
    "ST": ["st", "scheduled tribe", "अनुसूचित जनजाति", "adivasi"],
    "OBC": ["obc", "other backward", "अन्य पिछड़ा", "pichda"],
}

HINGLISH_MAP = {
    "mujhe": "",
    "chahiye": "",
    "ke liye": " for ",
    "loan": "loan",
    "vyavasay": "business",
    "udyam": "business",
}

# Exemplars for embedding-based fill when rules miss (EN + HI mixed)
PURPOSE_EXEMPLARS = [
    ("business", "I need a business loan for self employment shop or small enterprise व्यवसाय स्वरोजगार"),
    ("education", "I need an education loan for college university tuition studies शिक्षा पढ़ाई"),
    ("agriculture", "I need a loan for farming dairy poultry agriculture कृषि डेयरी खेती"),
]

PROJECT_EXEMPLARS = [
    ("dairy", "dairy milk cattle buffalo animal husbandry डेयरी दूध पशुपालन"),
    ("kirana", "kirana grocery general store retail shop किराना दुकान"),
    ("tailoring", "tailoring boutique garment stitching सिलाई बुटीक"),
    ("beauty_parlour", "beauty parlour salon spa ब्यूटी पार्लर सैलून"),
    ("transport", "transport vehicle auto taxi truck परिवहन वाहन"),
    ("agriculture", "agriculture farming crops irrigation कृषि खेती"),
    ("poultry", "poultry chicken farm मुर्गी पालन"),
    ("micro_enterprise", "micro enterprise small business workshop सूक्ष्म उद्यम"),
    ("education_loan", "education loan tuition hostel fee college शिक्षा ऋण ट्यूशन"),
    ("services", "repair services workshop service centre मरम्मत सेवा"),
    ("manufacturing", "manufacturing factory production unit विनिर्माण कारखाना"),
]

EMBEDDING_MIN_SCORE = 0.28


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


@lru_cache(maxsize=1)
def _load_embedding_model():
    from app.config import get_settings

    settings = get_settings()
    if not settings.enable_embeddings:
        return None
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model_name)


def embedding_similarity(query: str, documents: list[str]) -> Optional[list[float]]:
    """Local multilingual embeddings; returns None if disabled/unavailable."""
    try:
        model = _load_embedding_model()
        if model is None:
            return None
        q = model.encode([query], normalize_embeddings=True)
        d = model.encode(documents, normalize_embeddings=True)
        scores = (q @ d.T).flatten().tolist()
        return [float(s) for s in scores]
    except Exception:
        return None


def _best_label(query: str, exemplars: list[tuple[str, str]], min_score: float = EMBEDDING_MIN_SCORE) -> Optional[tuple[str, float]]:
    docs = [text for _, text in exemplars]
    scores = embedding_similarity(query, docs)
    if not scores:
        return None
    best_i = max(range(len(scores)), key=lambda i: scores[i])
    if scores[best_i] < min_score:
        return None
    return exemplars[best_i][0], scores[best_i]


def _enrich_with_embeddings(text: str, extracted: dict[str, Any]) -> tuple[dict[str, Any], bool, float]:
    """Fill missing purpose/project via embeddings. Returns (extracted, used, best_score)."""
    used = False
    best = 0.0

    if "purpose" not in extracted:
        hit = _best_label(text, PURPOSE_EXEMPLARS)
        if hit:
            extracted["purpose"] = hit[0]
            best = max(best, hit[1])
            used = True

    if "project_type" not in extracted:
        hit = _best_label(text, PROJECT_EXEMPLARS)
        if hit:
            extracted["project_type"] = hit[0]
            best = max(best, hit[1])
            used = True
            if "purpose" not in extracted:
                extracted["purpose"] = "education" if hit[0] == "education_loan" else "business"

    return extracted, used, best


def _text_has_keyword(kw: str, lower: str, original: str) -> bool:
    """Avoid false hits like 'st' inside 'start' / 'something'."""
    if len(kw) <= 3 and kw.isascii():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", lower, re.I))
    return kw in lower or kw in original


def parse_intent(text: str) -> dict[str, Any]:
    original = text.strip()
    lower = original.lower()
    for k, v in HINGLISH_MAP.items():
        lower = lower.replace(k, v)

    purpose = None
    for p, kws in PURPOSE_KEYWORDS.items():
        if any(_text_has_keyword(kw, lower, original) for kw in kws):
            purpose = p
            break

    project_type = None
    for p, kws in PROJECT_KEYWORDS.items():
        if any(_text_has_keyword(kw, lower, original) for kw in kws):
            project_type = p
            if purpose is None:
                purpose = "business" if p != "education_loan" else "education"
            break

    category = None
    for c, kws in CATEGORY_KEYWORDS.items():
        if any(_text_has_keyword(kw, lower, original) for kw in kws):
            category = c
            break

    loan_required = normalize_amount(original)

    age = None
    age_m = re.search(
        r"(?:age|उम्र|vayu|umra|years?\s*old|साल\s*का|वर्षीय)\D{0,8}(\d{1,2})"
        r"|(?:i\s*am|i'm|mein|main|मेरी?\s*उम्र)\D{0,8}(\d{1,2})",
        lower,
    )
    if age_m:
        age = int(next(g for g in age_m.groups() if g))

    income = None
    income_m = re.search(
        r"(?:income|आय|aay|salary|वेतन)[^\d₹rs]{0,20}((?:₹|rs\.?)?\s*[\d,]+(?:\.\d+)?\s*(?:lakh|lac|लाख|crore)?)",
        lower,
        re.I,
    )
    if income_m:
        income = normalize_amount(income_m.group(1))

    # Map agriculture-related intents to business purpose for the citizen form options
    if purpose == "agriculture":
        purpose = "business"
        if project_type is None:
            project_type = "agriculture"

    fields = {
        "loan_required": loan_required,
        "project_type": project_type,
        "purpose": purpose,
        "category": category,
        "age": age,
        "annual_family_income": income,
    }
    extracted = {k: v for k, v in fields.items() if v is not None}

    extracted, used_embeddings, emb_score = _enrich_with_embeddings(original, extracted)

    # Re-map agriculture after embedding fill
    if extracted.get("purpose") == "agriculture":
        extracted["purpose"] = "business"
        extracted.setdefault("project_type", "agriculture")

    method = "hybrid" if used_embeddings else "rule_based"
    confidence = 0.55 + 0.1 * len(extracted)
    if used_embeddings:
        confidence = min(0.95, confidence + 0.15 * emb_score)

    notes = (
        "Hybrid NLP (rules + local multilingual embeddings). Confirm values in the form."
        if used_embeddings
        else "Local rule-based NLP. Values are suggestions; user should confirm in the form."
    )

    return {
        "original_text": original,
        "extracted": extracted,
        "method": method,
        "confidence": round(confidence, 3),
        "notes": notes,
    }
