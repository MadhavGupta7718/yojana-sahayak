"""Normalize government document values while preserving originals."""

from __future__ import annotations

import hashlib
import re
from typing import Optional, Tuple


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def parse_indian_amount(text: str) -> Tuple[Optional[float], str]:
    original = normalize_whitespace(text)
    if not original:
        return None, original
    t = original.lower().replace(",", "").replace("₹", "").replace("rs.", "").replace("rs", "").replace("inr", "")
    t = t.strip()

    m = re.search(r"([\d.]+)\s*(lakh|lac|lakhs|लाख)", t, re.I)
    if m:
        return float(m.group(1)) * 100_000, original
    m = re.search(r"([\d.]+)\s*(crore|करोड़)", t, re.I)
    if m:
        return float(m.group(1)) * 10_000_000, original
    m = re.search(r"([\d.]+)", t)
    if m:
        val = float(m.group(1))
        # Heuristic: if looks like "1.25" near lakh context already handled; raw rupees otherwise
        return val, original
    return None, original


def parse_percent(text: str) -> Tuple[Optional[float], str]:
    original = normalize_whitespace(text)
    m = re.search(r"([\d.]+)\s*%", original)
    if m:
        return float(m.group(1)), original
    m = re.search(r"([\d.]+)\s*percent", original, re.I)
    if m:
        return float(m.group(1)), original
    return None, original


def parse_months(text: str) -> Tuple[Optional[int], str]:
    original = normalize_whitespace(text)
    t = original.lower()
    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "twelve": 12,
    }
    for word, num in words.items():
        if re.search(rf"\b{word}\s*years?\b", t):
            return num * 12, original
        if re.search(rf"\b{word}\s*months?\b", t):
            return num, original
    m = re.search(r"(\d+)\s*(years?|वर्ष|साल)", t)
    if m:
        return int(m.group(1)) * 12, original
    m = re.search(r"(\d+)\s*(months?|महीने|माह)", t)
    if m:
        return int(m.group(1)), original
    m = re.search(r"(\d+)", t)
    if m:
        return int(m.group(1)), original
    return None, original


def canonical_key(name: str) -> str:
    s = normalize_whitespace(name).lower()
    s = re.sub(r"[^a-z0-9\u0900-\u097f]+", "-", s)
    return s.strip("-")[:480]
