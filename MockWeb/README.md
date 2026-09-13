# MockWeb (local corpus)

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
