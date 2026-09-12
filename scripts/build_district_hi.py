"""Build Hindi district label map from public EN/HI JSON + our district list."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCATIONS = ROOT / "frontend" / "src" / "data" / "indiaLocations.ts"
OUT = ROOT / "frontend" / "src" / "data" / "districtLabelsHi.ts"

DEFAULT_SOURCES = [
    "https://raw.githubusercontent.com/tanvir-dhanjal/india-state-district-en-hi-json/master/india_district.json",
]


def load_our_districts() -> list[str]:
    text = LOCATIONS.read_text(encoding="utf-8")
    start = text.index("export const DISTRICTS_BY_STATE")
    end = text.index("export function districtsForState")
    block = text[start:end]
    return sorted(set(re.findall(r'^\s{4}"([^"]+)",?\s*$', block, re.M)))


def normalize(name: str) -> str:
    n = name.lower().strip()
    n = n.replace("&", "and").replace("&amp;", "and")
    n = re.sub(r"\s*\(.*?\)\s*", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    aliases = {
        "faizabad": "ayodhya",
        "allahabad": "prayagraj",
        "bellary": "ballari",
        "tumkur": "tumakuru",
        "mysore": "mysuru",
        "belgaum": "belagavi",
        "gulbarga": "kalaburagi",
        "bijapur": "vijayapura",
        "gautam buddha nagar": "gautam budh nagar",
        "gautam budh nagar": "gautam buddha nagar",
        "bulandshahr": "bulandshahar",
        "bulandshahar": "bulandshahr",
        "badaun": "budaun",
        "sant ravidas nagar": "bhadohi",
        "rae bareli": "raebareli",
        "raebareli": "rae bareli",
        "lakhimpur kheri": "kheri",
        "kanshiram nagar": "kasganj",
        "kasganj": "kanshiram nagar",
        "shamali": "shamli",
        "siddharth nagar": "siddharthnagar",
        "siddharthnagar": "siddharth nagar",
        "gurgaon": "gurugram",
        "mewat": "nuh",
        "ysr kadapa": "kadapa",
        "kadapa": "ysr kadapa",
    }
    return aliases.get(n, n)


def flatten_source(data) -> dict[str, str]:
    out: dict[str, str] = {}

    def add(en: str, hi: str):
        en = (en or "").strip()
        hi = (hi or "").strip()
        if not en or not hi:
            return
        out[normalize(en)] = hi

    if isinstance(data, dict) and "data" in data:
        data = data["data"]

    if isinstance(data, list):
        for st in data:
            if not isinstance(st, dict):
                continue
            for d in st.get("districts", []):
                if isinstance(d, dict):
                    add(
                        d.get("district_en") or d.get("name") or d.get("en") or "",
                        d.get("district_hi") or d.get("name-hi") or d.get("hi") or "",
                    )
    elif isinstance(data, dict):
        for _state, val in data.items():
            if isinstance(val, dict):
                districts = val.get("districts", val)
                if isinstance(districts, dict):
                    for en, hi in districts.items():
                        if isinstance(hi, str):
                            add(en, hi)
                elif isinstance(districts, list):
                    for d in districts:
                        if isinstance(d, dict):
                            add(
                                d.get("district_en") or d.get("name") or "",
                                d.get("district_hi") or d.get("name-hi") or "",
                            )
    return out


# Exact labels for our UP/Delhi strings (including parenthetical forms)
MANUAL = {
    "Agra": "आगरा",
    "Aligarh": "अलीगढ़",
    "Allahabad": "इलाहाबाद",
    "Ambedkar Nagar": "अम्बेडकर नगर",
    "Amethi (Chatrapati Sahuji Mahraj Nagar)": "अमेठी",
    "Amroha (J.P. Nagar)": "अमरोहा",
    "Auraiya": "औरैया",
    "Azamgarh": "आज़मगढ़",
    "Baghpat": "बागपत",
    "Bahraich": "बहराइच",
    "Ballia": "बलिया",
    "Balrampur": "बलरामपुर",
    "Banda": "बाँदा",
    "Barabanki": "बाराबंकी",
    "Bareilly": "बरेली",
    "Basti": "बस्ती",
    "Bhadohi": "भदोही",
    "Bijnor": "बिजनौर",
    "Budaun": "बदायूँ",
    "Bulandshahr": "बुलंदशहर",
    "Chandauli": "चंदौली",
    "Chitrakoot": "चित्रकूट",
    "Deoria": "देवरिया",
    "Etah": "एटा",
    "Etawah": "इटावा",
    "Faizabad": "फ़ैज़ाबाद",
    "Farrukhabad": "फ़र्रूख़ाबाद",
    "Fatehpur": "फ़तेहपुर",
    "Firozabad": "फ़िरोज़ाबाद",
    "Gautam Buddha Nagar": "गौतम बुद्ध नगर",
    "Ghaziabad": "गाज़ियाबाद",
    "Ghazipur": "ग़ाज़ीपुर",
    "Gonda": "गोंडा",
    "Gorakhpur": "गोरखपुर",
    "Hamirpur": "हमीरपुर",
    "Hapur (Panchsheel Nagar)": "हापुड़",
    "Hardoi": "हरदोई",
    "Hathras": "हाथरस",
    "Jalaun": "जालौन",
    "Jaunpur": "जौनपुर",
    "Jhansi": "झांसी",
    "Kannauj": "कन्नौज",
    "Kanpur Dehat": "कानपुर देहात",
    "Kanpur Nagar": "कानपुर नगर",
    "Kanshiram Nagar (Kasganj)": "कासगंज",
    "Kaushambi": "कौशाम्बी",
    "Kushinagar (Padrauna)": "कुशीनगर",
    "Lakhimpur - Kheri": "लखीमपुर खीरी",
    "Lalitpur": "ललितपुर",
    "Lucknow": "लखनऊ",
    "Maharajganj": "महाराजगंज",
    "Mahoba": "महोबा",
    "Mainpuri": "मैनपुरी",
    "Mathura": "मथुरा",
    "Mau": "मऊ",
    "Meerut": "मेरठ",
    "Mirzapur": "मिर्ज़ापुर",
    "Moradabad": "मुरादाबाद",
    "Muzaffarnagar": "मुज़फ़्फ़रनगर",
    "Pilibhit": "पीलीभीत",
    "Pratapgarh": "प्रतापगढ़",
    "RaeBareli": "रायबरेली",
    "Rampur": "रामपुर",
    "Saharanpur": "सहारनपुर",
    "Sambhal (Bhim Nagar)": "सम्भल",
    "Sant Kabir Nagar": "संत कबीर नगर",
    "Shahjahanpur": "शाहजहाँपुर",
    "Shamali (Prabuddh Nagar)": "शामली",
    "Shravasti": "श्रावस्ती",
    "Siddharth Nagar": "सिद्धार्थनगर",
    "Sitapur": "सीतापुर",
    "Sonbhadra": "सोनभद्र",
    "Sultanpur": "सुल्तानपुर",
    "Unnao": "उन्नाव",
    "Varanasi": "वाराणसी",
    "New Delhi": "नई दिल्ली",
    "Central Delhi": "मध्य दिल्ली",
    "East Delhi": "पूर्वी दिल्ली",
    "North Delhi": "उत्तर दिल्ली",
    "North East  Delhi": "उत्तर पूर्व दिल्ली",
    "North West  Delhi": "उत्तर पश्चिम दिल्ली",
    "Shahdara": "शाहदरा",
    "South Delhi": "दक्षिण दिल्ली",
    "South East Delhi": "दक्षिण पूर्व दिल्ली",
    "South West  Delhi": "दक्षिण पश्चिम दिल्ली",
    "West Delhi": "पश्चिम दिल्ली",
}


def fetch_json(url: str):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print("fetch failed", url, e)
        return None


def load_json_path(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def lookup(merged: dict[str, str], district: str) -> str | None:
    keys = [
        normalize(district),
        normalize(re.sub(r"\s*\(.*?\)\s*", " ", district)),
        normalize(district.split("(")[0]),
        normalize(district.split("-")[0]),
    ]
    for k in keys:
        if k and k in merged:
            return merged[k]
    best = None
    best_score = 0
    tokens = set(normalize(district).split())
    if not tokens:
        return None
    for k, hi in merged.items():
        kt = set(k.split())
        score = len(tokens & kt)
        if score >= 2 and score > best_score and score >= max(2, len(tokens) - 1):
            best_score = score
            best = hi
    return best


def main():
    our = load_our_districts()
    print("our districts", len(our))
    merged: dict[str, str] = {}

    local_args = [Path(a) for a in sys.argv[1:] if Path(a).exists()]
    for path in local_args:
        data = load_json_path(path)
        flat = flatten_source(data)
        print("local", path, "keys", len(flat))
        merged.update(flat)

    if not merged:
        for url in DEFAULT_SOURCES:
            data = fetch_json(url)
            if data is None:
                continue
            flat = flatten_source(data)
            print(url, "keys", len(flat))
            merged.update(flat)

    result: dict[str, str] = {}
    missing = []
    for d in our:
        if d in MANUAL:
            result[d] = MANUAL[d]
            continue
        hi = lookup(merged, d)
        if hi:
            result[d] = hi
        else:
            missing.append(d)

    print("mapped", len(result), "missing", len(missing))
    if missing[:40]:
        print("sample missing:", missing[:40])

    lines = [
        "/** Hindi display labels for districts. Values stay English for form matching. */",
        "export const DISTRICT_LABEL_HI: Record<string, string> = {",
    ]
    for en in sorted(result):
        hi = result[en].replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'  "{en}": "{hi}",')
    lines.append("};")
    lines.append("")
    lines.append('export function districtLabel(district: string, locale: "en" | "hi") {')
    lines.append('  if (locale !== "hi") return district;')
    lines.append("  const hi = DISTRICT_LABEL_HI[district];")
    lines.append("  return hi ? `${hi} (${district})` : district;")
    lines.append("}")
    lines.append("")
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print("wrote", OUT, "entries", len(result))


if __name__ == "__main__":
    main()
