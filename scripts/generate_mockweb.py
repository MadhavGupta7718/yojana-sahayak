"""Generate MockWeb HTML sites (150 schemes) and 2 manual-upload PDFs."""

from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "MockWeb"

# Sample partner outlets near the requested pincodes (presented as channel partners).
PIN_PARTNERS = [
    {
        "pin": "335804",
        "state": "Rajasthan",
        "district": "Hanumangarh",
        "city": "Sangaria",
        "lat": 29.7902,
        "lng": 74.4661,
        "street": "Near Bus Stand, Main Market Road",
        "org": "Rajasthan State Channelizing Agency",
    },
    {
        "pin": "201310",
        "state": "Uttar Pradesh",
        "district": "Gautam Buddha Nagar",
        "city": "Greater Noida",
        "lat": 28.4744,
        "lng": 77.5040,
        "street": "Alpha-1 Commercial Complex, Knowledge Park",
        "org": "Uttar Pradesh Development Finance Desk",
    },
    {
        "pin": "201001",
        "state": "Uttar Pradesh",
        "district": "Ghaziabad",
        "city": "Ghaziabad",
        "lat": 28.6692,
        "lng": 77.4538,
        "street": "Ambedkar Road, Near Railway Station",
        "org": "NCR Beneficiary Support Agency",
    },
    {
        "pin": "854105",
        "state": "Bihar",
        "district": "Purnia",
        "city": "Purnia",
        "lat": 25.7771,
        "lng": 87.4753,
        "street": "Line Bazar, Madhubani Road",
        "org": "Bihar Scheduled Caste Finance Corporation",
    },
]

SITES = [
    {
        "slug": "site-01-livelihood-finance",
        "title": "National Livelihood Finance Desk",
        "org": "Ministry of Social Justice Linked Livelihood Desk",
        "theme": "livelihood",
        "purpose": "business",
        "scheme_type": "term_loan",
        "prefix": "Livelihood",
        "accent": "#0f5c4c",
    },
    {
        "slug": "site-02-social-justice-loans",
        "title": "Social Justice Loan Assistance Portal",
        "org": "Social Justice Credit Facilitation Unit",
        "theme": "social_justice",
        "purpose": "business",
        "scheme_type": "term_loan",
        "prefix": "Samajik Nyay",
        "accent": "#1a3a6b",
    },
    {
        "slug": "site-03-women-enterprise",
        "title": "Women Enterprise Credit Portal",
        "org": "Women Entrepreneurship Support Cell",
        "theme": "women",
        "purpose": "business",
        "scheme_type": "micro_finance",
        "prefix": "Mahila Udyam",
        "accent": "#7a2e4a",
    },
    {
        "slug": "site-04-education-vocational",
        "title": "Education & Vocational Finance Hub",
        "org": "Skill and Higher Education Credit Cell",
        "theme": "education",
        "purpose": "education",
        "scheme_type": "educational_loan",
        "prefix": "Shiksha",
        "accent": "#2c4a7c",
    },
    {
        "slug": "site-05-green-enterprise",
        "title": "Green Enterprise Support Desk",
        "org": "Sustainable Livelihood Finance Unit",
        "theme": "green",
        "purpose": "business",
        "scheme_type": "term_loan",
        "prefix": "Harit Udyam",
        "accent": "#2f6b3a",
    },
]

CATEGORIES = ["SC", "OBC", "General", "ST", "EWS"]
ACTIVITIES = [
    "Retail shop",
    "Tailoring unit",
    "Dairy farming",
    "Food processing",
    "Automobile service",
    "Handicraft production",
    "IT services",
    "Beauty and wellness",
    "Agriculture allied",
    "Transport service",
]
EDU_ACTIVITIES = [
    "Professional degree",
    "Vocational certificate",
    "Diploma course",
    "Skill development programme",
    "Higher studies abroad",
]


def _money_lakh(n: float) -> str:
    if n >= 100000:
        return f"Rs. {n/100000:.2f} lakh".replace(".00", "")
    return f"Rs. {int(n):,}"


def partner_for(index: int) -> dict:
    base = PIN_PARTNERS[index % len(PIN_PARTNERS)]
    # Slight offset so map pins are distinct
    jitter = (index // len(PIN_PARTNERS)) * 0.0021
    return {
        **base,
        "lat": round(base["lat"] + math.sin(index) * 0.004 + jitter, 6),
        "lng": round(base["lng"] + math.cos(index) * 0.004 + jitter, 6),
        "name": f"{base['city']} Channel Partner Centre {((index % 7) + 1):02d}",
        "phone": f"+91-9{(index % 9) + 1}{20000000 + index * 137 % 10000000:07d}"[:14],
        "email": f"partner{(index % 40) + 1}@channeldesk.in",
    }


def build_scheme(site: dict, local_idx: int, global_idx: int) -> dict:
    purpose = site["purpose"]
    min_loan = 25000 + (local_idx % 8) * 25000
    max_loan = 200000 + (local_idx % 12) * 150000
    if purpose == "education":
        max_loan = 300000 + (local_idx % 10) * 200000
        min_loan = 50000 + (local_idx % 5) * 25000
    max_income = 150000 + (local_idx % 10) * 50000
    rate = round(4.0 + (local_idx % 9) * 0.5, 1)
    tenure_months = 24 + (local_idx % 8) * 12
    mora = 3 if local_idx % 3 == 0 else (6 if local_idx % 3 == 1 else 0)
    category = CATEGORIES[local_idx % len(CATEGORIES)]
    age_min, age_max = 18, 55 if purpose != "education" else 35
    activities = EDU_ACTIVITIES if purpose == "education" else ACTIVITIES
    activity = activities[local_idx % len(activities)]

    # Gender focus: women-enterprise site leans female; mix elsewhere
    if site["theme"] == "women":
        target_gender = "female" if local_idx % 4 != 0 else "any"
    elif local_idx % 10 == 7:
        target_gender = "male"
    elif local_idx % 10 == 3:
        target_gender = "female"
    else:
        target_gender = "any"

    # Timeline mix: lifetime / period / omit (NA)
    mode = global_idx % 5
    if mode in (0, 1):
        timeline = "Availability: Lifetime"
        availability_type = "lifetime"
        period = None
    elif mode in (2, 3):
        start_y = 2025 + (local_idx % 2)
        end_y = start_y + 2 + (local_idx % 3)
        day = 5 + (local_idx % 20)
        timeline = f"Scheme period: {day} May {start_y} to 31 March {end_y}"
        availability_type = "period"
        period = timeline
    else:
        timeline = None
        availability_type = None
        period = None

    p = partner_for(global_idx)
    name = f"{site['prefix']} {activity} Scheme {local_idx + 1:02d}"
    if purpose == "education":
        name = f"{site['prefix']} Educational Loan Scheme {local_idx + 1:02d}"
    if target_gender == "female":
        name = f"{site['prefix']} Women {activity} Scheme {local_idx + 1:02d}"
        if purpose == "education":
            name = f"{site['prefix']} Educational Loan for Women Scheme {local_idx + 1:02d}"
    elif target_gender == "male":
        name = f"{site['prefix']} Men {activity} Scheme {local_idx + 1:02d}"

    docs = [
        "Aadhaar",
        "Identity proof",
        "Address proof",
        "Income certificate",
        "Caste certificate",
        "Bank account",
        "Project report" if purpose == "business" else "Educational certificate",
        "Passport size photograph",
    ]

    gender_note = {
        "female": "This scheme is published for women beneficiaries only.",
        "male": "This scheme is published for men beneficiaries only.",
        "any": "This scheme is open to both male and female beneficiaries.",
    }[target_gender]

    return {
        "id": f"{site['slug']}-{local_idx + 1:02d}",
        "name": name,
        "scheme_type": site["scheme_type"],
        "purpose": purpose,
        "description": (
            f"{name} provides concessional finance for {activity.lower()} under "
            f"{site['org']}. Beneficiaries from category {category} meeting income "
            f"and age criteria may apply through the listed channel partner. {gender_note}"
        ),
        "min_loan": min_loan,
        "max_loan": max_loan,
        "max_income": max_income,
        "interest_rate": rate,
        "tenure_months": tenure_months,
        "moratorium": mora,
        "category": category,
        "age_min": age_min,
        "age_max": age_max,
        "activity": activity,
        "documents": docs,
        "timeline": timeline,
        "availability_type": availability_type,
        "period": period,
        "target_gender": target_gender,
        "partner": p,
        "application": (
            "Submit the application form with required documents at the authorised "
            "channel partner office. After verification, the sanction letter is issued "
            "as per applicable guidelines."
        ),
    }


def scheme_text_block(s: dict) -> str:
    p = s["partner"]
    address = f"{p['street']}, {p['city']}, {p['district']}, {p['state']} - {p['pin']}"
    lines = [
        f"Scheme Name: {s['name']}",
        f"Scheme Type: {s['scheme_type'].replace('_', ' ').title()}",
        f"Purpose: {s['purpose']}",
        f"Description: {s['description']}",
        f"Eligible activity: {s['activity']}",
        f"Beneficiary category: {s['category']}",
        f"Target gender: {s['target_gender']}",
        f"Age limit: {s['age_min']} to {s['age_max']} years",
        f"Annual family income limit: {_money_lakh(s['max_income'])}",
        f"Minimum loan: {_money_lakh(s['min_loan'])}",
        f"Maximum loan: {_money_lakh(s['max_loan'])}",
        f"Interest rate: {s['interest_rate']}%",
        f"Repayment period: {s['tenure_months']} months",
        f"Moratorium: {s['moratorium']} months",
        f"Required documents: {', '.join(s['documents'])}",
        f"Application process: {s['application']}",
    ]
    if s["timeline"]:
        lines.append(s["timeline"])
    lines.extend(
        [
            "Channel Partner",
            f"Channel Partner Name: {p['name']}",
            f"Organization: {p['org']}",
            f"Partner Type: Channelizing Agency",
            f"State: {p['state']}",
            f"District: {p['district']}",
            f"Address: {address}",
            f"Phone: {p['phone']}",
            f"Email: {p['email']}",
            f"Latitude: {p['lat']}",
            f"Longitude: {p['lng']}",
        ]
    )
    return "\n".join(lines)


def scheme_html_article(s: dict) -> str:
    p = s["partner"]
    address = f"{p['street']}, {p['city']}, {p['district']}, {p['state']} - {p['pin']}"
    timeline_html = f"<p>{s['timeline']}</p>" if s["timeline"] else ""
    docs = ", ".join(s["documents"])
    return f"""
<article class="scheme" id="{s['id']}" data-purpose="{s['purpose']}" data-category="{s['category']}">
  <h2>{s['name']}</h2>
  <p class="meta">{s['scheme_type'].replace('_', ' ').title()} · Purpose: {s['purpose']}</p>
  <p>Scheme Name: {s['name']}</p>
  <p>{s['description']}</p>
  {timeline_html}
  <p>Eligible activity: {s['activity']}</p>
  <p>Beneficiary category: {s['category']}</p>
  <p>Target gender: {s['target_gender']}</p>
  <p>Age limit: {s['age_min']} to {s['age_max']} years</p>
  <p>Annual family income: {_money_lakh(s['max_income'])}</p>
  <p>Minimum loan: {_money_lakh(s['min_loan'])}</p>
  <p>Maximum loan: {_money_lakh(s['max_loan'])}</p>
  <p>Interest rate: {s['interest_rate']}%</p>
  <p>Repayment period: {s['tenure_months']} months</p>
  <p>Moratorium: {s['moratorium']} months</p>
  <p>Required documents: {docs}</p>
  <p>Application process: {s['application']}</p>
  <section class="channel-partner">
    <h3>Channel Partner</h3>
    <p>Channel Partner Name: {p['name']}</p>
    <p>Organization: {p['org']}</p>
    <p>Partner Type: Channelizing Agency</p>
    <p>State: {p['state']}</p>
    <p>District: {p['district']}</p>
    <p>Address: {address}</p>
    <p>Phone: {p['phone']}</p>
    <p>Email: {p['email']}</p>
    <p>Latitude: {p['lat']}</p>
    <p>Longitude: {p['lng']}</p>
  </section>
</article>
"""


def render_site(site: dict, schemes: list[dict]) -> str:
    articles = "\n".join(scheme_html_article(s) for s in schemes)
    accent = site["accent"]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{site['title']}</title>
<style>
:root {{ --accent: {accent}; --ink:#122018; --bg:#f4f7f5; --card:#fff; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; font-family: Georgia, "Times New Roman", serif; color:var(--ink); background:var(--bg); line-height:1.55; }}
header {{ background:linear-gradient(120deg, var(--accent), #0a1f18); color:#fff; padding:2rem 1.25rem 2.5rem; }}
header h1 {{ margin:0 0 .4rem; font-size:clamp(1.6rem, 3vw, 2.4rem); }}
header p {{ margin:0; max-width:52rem; opacity:.92; }}
nav {{ display:flex; gap:1rem; flex-wrap:wrap; margin-top:1.25rem; }}
nav a {{ color:#fff; text-decoration:none; border-bottom:1px solid rgba(255,255,255,.5); }}
.wrap {{ max-width:960px; margin:0 auto; padding:1.5rem 1.25rem 3rem; }}
.toolbar {{ display:flex; gap:.75rem; flex-wrap:wrap; margin:1rem 0 1.5rem; }}
.toolbar input, .toolbar select {{ padding:.55rem .7rem; border:1px solid #c5d0c9; background:#fff; font:inherit; min-width:180px; }}
.scheme {{ background:var(--card); border:1px solid #d7e0db; padding:1.25rem 1.35rem; margin-bottom:1.25rem; }}
.scheme h2 {{ margin-top:0; color:var(--accent); font-size:1.25rem; }}
.scheme .meta {{ color:#4d5c55; font-size:.92rem; margin-top:-.4rem; }}
dl {{ display:grid; grid-template-columns: 12rem 1fr; gap:.35rem .75rem; }}
dt {{ font-weight:700; color:#355046; }}
dd {{ margin:0; }}
.channel-partner {{ margin-top:1rem; padding-top:1rem; border-top:1px dashed #c9d5ce; }}
.channel-partner h3 {{ margin:.2rem 0 .6rem; }}
footer {{ background:#101814; color:#d7e4dc; padding:1.5rem; text-align:center; font-size:.9rem; }}
.hidden {{ display:none !important; }}
@media (max-width:640px) {{ dl {{ grid-template-columns:1fr; }} }}
</style>
</head>
<body>
<header>
  <div class="wrap" style="padding-bottom:0">
    <h1>{site['title']}</h1>
    <p>{site['org']}. Browse published loan and assistance schemes, eligibility conditions, timelines, and authorised channel partners.</p>
    <nav>
      <a href="#schemes">Schemes</a>
      <a href="#about">About</a>
    </nav>
  </div>
</header>
<main class="wrap">
  <section id="about">
    <h2>About this portal</h2>
    <p>This portal publishes scheme summaries for citizen guidance. Applicants should verify final terms with the authorised channel partner before applying.</p>
  </section>
  <section id="schemes">
    <h2>Published schemes ({len(schemes)})</h2>
    <div class="toolbar">
      <input id="q" type="search" placeholder="Search scheme name or activity"/>
      <select id="cat">
        <option value="">All categories</option>
        <option>SC</option><option>ST</option><option>OBC</option><option>EWS</option><option>General</option>
      </select>
    </div>
    <div id="list">
{articles}
    </div>
  </section>
</main>
<footer>
  <p>{site['org']} · Scheme information subject to verification at the channel partner office.</p>
</footer>
<script>
(function() {{
  const q = document.getElementById('q');
  const cat = document.getElementById('cat');
  const items = [...document.querySelectorAll('.scheme')];
  function filter() {{
    const term = (q.value || '').toLowerCase();
    const c = cat.value;
    items.forEach(el => {{
      const text = el.innerText.toLowerCase();
      const okTerm = !term || text.includes(term);
      const okCat = !c || el.dataset.category === c;
      el.classList.toggle('hidden', !(okTerm && okCat));
    }});
  }}
  q.addEventListener('input', filter);
  cat.addEventListener('change', filter);
}})();
</script>
</body>
</html>
"""


def write_pdfs(all_schemes: list[dict]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    out_dir = MOCK / "manual-upload"
    batches = [
        ("schemes-batch-A.pdf", all_schemes[0:10]),
        ("schemes-batch-B.pdf", all_schemes[10:20]),
    ]
    for filename, schemes in batches:
        path = out_dir / filename
        c = canvas.Canvas(str(path), pagesize=A4)
        width, height = A4
        for s in schemes:
            y = height - 50
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, s["name"][:90])
            y -= 18
            c.setFont("Helvetica", 9)
            for line in scheme_text_block(s).splitlines():
                if y < 50:
                    c.showPage()
                    y = height - 50
                    c.setFont("Helvetica", 9)
                c.drawString(40, y, line[:110])
                y -= 12
            c.showPage()
        c.save()
        print(f"Wrote {path}")


def main() -> None:
    all_schemes: list[dict] = []
    global_idx = 0
    for site in SITES:
        schemes = []
        for i in range(30):
            s = build_scheme(site, i, global_idx)
            schemes.append(s)
            all_schemes.append(s)
            global_idx += 1
        folder = MOCK / site["slug"]
        folder.mkdir(parents=True, exist_ok=True)
        html_path = folder / "index.html"
        html_path.write_text(render_site(site, schemes), encoding="utf-8")
        print(f"Wrote {html_path} ({len(schemes)} schemes)")

    write_pdfs(all_schemes)

    readme = MOCK / "README.md"
    readme.write_text(
        """# MockWeb (local corpus)

Five self-contained scheme portals and two PDFs for manual-upload demos.

## Sites
- `site-01-livelihood-finance/`
- `site-02-social-justice-loans/`
- `site-03-women-enterprise/`
- `site-04-education-vocational/`
- `site-05-green-enterprise/`

Each folder has a single `index.html` (inline CSS/JS) with ~30 schemes.
Each scheme includes timeline text and a channel partner block with Latitude/Longitude.

## Manual upload PDFs
- `manual-upload/schemes-batch-A.pdf` (10 schemes)
- `manual-upload/schemes-batch-B.pdf` (10 schemes)

Deploy the HTML folders to any public host, then register the URLs as crawl sources in Admin.
Regenerate with: `python scripts/generate_mockweb.py`
""",
        encoding="utf-8",
    )
    print(f"Total schemes: {len(all_schemes)}")


if __name__ == "__main__":
    main()
