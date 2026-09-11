# AI-Driven Government Scheme Matching Platform

**YojanaSahayak / योजना सहायक**  
Problem Statement ID: **26092** — AI-Driven Scheme Matching for Marginalized Entrepreneurs

This platform helps eligible citizens discover suitable government-backed financial/educational loan schemes, understand eligibility and estimated obligations, and identify nearby authorized channel partners. **It does not submit loan applications.**

## Architecture

```text
Official Source → Scraper → raw_documents → Parser → staging_records
    → Change detection / Validation → Production DB → Recommendation API → Bilingual UI
```

Services (Docker Compose):

| Service   | Role                                      |
|-----------|-------------------------------------------|
| `db`      | PostgreSQL 16                             |
| `redis`   | Reserved for rate-limit / future queueing |
| `backend` | FastAPI + Alembic migrations + seed       |
| `scraper` | APScheduler periodic source checks        |
| `frontend`| Next.js bilingual citizen + admin UI      |

## Technology stack

- Frontend: Next.js, React, TypeScript, Tailwind-style CSS
- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL
- Scraping: httpx, BeautifulSoup, pdfplumber, PyMuPDF, OCR fallback (Tesseract)
- Scheduling: APScheduler
- NLP: local rule-based multilingual extractor (+ optional sentence-transformers)
- Auth: JWT admin roles (`viewer`, `reviewer`, `superadmin`)

**No OpenAI/Gemini/Claude, no Google Maps/Mapbox, no paid geocoding, no government API keys required.**

## Quick start

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start stack
docker compose up --build

# 3. Ingest NSFDC (also auto-runs via scheduler)
docker compose exec scraper python -m scraper.run --source NSFDC

# 4. Open
# Citizen UI: http://localhost:3000
# Admin UI:   http://localhost:3000/admin
# API docs:   http://localhost:8000/docs
```

Default admin credentials come from `.env` (`ADMIN_USERNAME` / `ADMIN_PASSWORD`).

## Manual scraper

```bash
python -m scraper.run
python -m scraper.run --source NSFDC
```

## Government sources

Seeded in `government_sources`:

1. **NSFDC** (`https://nsfdc.nic.in/`) — enabled by default
2. **MoSJE** — registered, disabled until robots/authority verification
3. **data.gov.in** — discovery candidate (`pending_review`)
4. **SCA placeholder** — disabled until a real official SCA URL is added in Admin

Admins can add sources from the dashboard without code changes.

### Source verification approach

1. Domain must be `.gov.in` / `.nic.in` for discovery candidates
2. Keyword relevance check (NSFDC, SC finance, channelizing agency, etc.)
3. `robots.txt` check before crawl
4. If disallowed/blocked → status `MANUAL/RESTRICTED` + admin PDF/HTML upload adapter
5. Never bypass CAPTCHA, auth, or anti-bot controls

## Change detection & versioning

- Content/ETag/Last-Modified hashing skips unchanged pages
- Sensitive fields (interest, loan limits, income, tenure, etc.) → `pending_review`
- Safe fields (phone, address formatting) → `auto_approved`
- Conflicts between official sources stay pending for human verification
- `scheme_versions` stores immutable snapshots

## Recommendation algorithm

1. Extract profile (form + optional local NLP)
2. Evaluate DB/JSON eligibility rules (hard filter)
3. Rank only eligible schemes with configurable weights:
   - Eligibility 40% · Purpose 25% · Loan amount 15% · Project cost 10% · Other 10%
4. Explain each ✓ / ⚠ reason with official source citations

## Partner routing

1. Filter authorized partners that support the scheme (when mapping exists)
2. Expand radius: 20 → 40 → 60 → 100 km (configurable)
3. Rank by scheme compatibility, distance (Haversine), freshness, status
4. If coordinates missing, fall back to state/district matching
5. Never invent NPA/fund utilization — show unavailable when not in source

## Location handling

- Optional browser Geolocation API
- Manual address / city / district / state / PIN always available
- Precise coordinates used ephemerally for search (privacy notice shown)

## Hindi / English

Translation files:

- `frontend/locales/en/common.json`
- `frontend/locales/hi/common.json`

Language toggle sets a `locale` cookie; all major citizen strings are translated.

## Local ML / NLP

`ml/inference/nlp.py`:

- Keyword / regex / synonym extraction for EN, HI, and Hinglish
- Amount normalization (₹ / lakh / crore)
- Optional embeddings only if `ENABLE_EMBEDDINGS=true` (offline model)

## Security

- Password hashing (bcrypt), JWT admin auth, RBAC
- Input validation (Pydantic), ORM parameterization
- Rate limiting, security headers
- Audit log for admin actions
- No unnecessary storage of precise location

## Testing

```bash
docker compose exec backend pytest -q
# or locally with PYTHONPATH
cd backend && PYTHONPATH=..:../backend pytest -q
```

Coverage includes EMI, rules, Haversine, NLP, HTML/PDF field extraction, hash change, discovery domain checks, eligibility boundaries.

## Limitations

- Government sites may change layout; extractors are heuristic and conservative
- Missing fields are shown as **Not available from official source** (never fabricated)
- Partner coordinates appear only when present in authoritative extracts or manual verified upload
- OCR quality depends on scanned PDF clarity
- Optional embedding model is large and disabled by default

## Legal / ethical scraping

- Respect `robots.txt` and crawl delay
- Identify crawler via User-Agent
- Do not overload government servers
- Prefer official documents/feeds when crawling is restricted
- Attribute every important data point to its official source URL

## Future improvements

- Authorized government data feeds / APIs when available
- Richer state channelizing agency coverage after admin review
- Stronger local multilingual NER models
- PostGIS for advanced geospatial queries

## Disclaimer

Information is compiled from official government sources and may change. The platform provides guidance and scheme matching based on the latest successfully verified information available to it. Final eligibility, sanction, interest rate, documentation requirements, and disbursement are subject to the applicable official rules and the authorized channel partner.
