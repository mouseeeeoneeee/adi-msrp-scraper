ADI MSRP Scraper — README

This repo scrapes Hanwha camera product data from ADI’s US site and (optionally) pulls MSRP from each product detail page (PDP). It writes both a catalog snapshot and a results export (CSV/XLSX) under data/exports/.

What it does

Authenticate once to ADI and reuse a saved session (storage_state.json) on later runs.

Load the Hanwha IP Cameras listing, auto-click “Show/Load More,” and extract product tiles (brand, marketing title, model, ADI’s SQ-code, URL, lightweight attributes).

(Optional) Visit each PDP to extract MSRP and richer attributes (title, model/SQ code under the H1, IK rating, IR, lens info/type) from the left column and “Key Features.”

Export files to data/exports/ with timestamped names.

Repo layout
adi-msrp-scraper/
├─ data/                     # exports/ and logs/ are created here at runtime
├─ src/
│  ├─ auth.py                # login + storage_state.json reuse :contentReference[oaicite:5]{index=5}
│  ├─ catalog.py             # listing-page extractor (tiles → rows) :contentReference[oaicite:6]{index=6}
│  ├─ config.py              # brand config (Hanwha URL + MSRP labels) :contentReference[oaicite:7]{index=7}
│  ├─ detail.py              # PDP parser: title/codes/features/MSRP → fields :contentReference[oaicite:8]{index=8}
│  ├─ export.py              # CSV/XLSX writer with suffix handling :contentReference[oaicite:9]{index=9}
│  ├─ main.py                # CLI entrypoint & orchestration :contentReference[oaicite:10]{index=10}
│  └─ debug_login.py         # optional: form-based login & screenshots :contentReference[oaicite:11]{index=11}
├─ requirements.txt
├─ refresh_hanwha.bat        # example Windows runner
└─ storage_state.json        # saved browser session (created on first run)

Prerequisites

Python 3.10+ recommended

Chrome/Chromium via Playwright

Install deps:

pip install -r requirements.txt
python -m playwright install


The code uses Playwright sync API, pandas, and python-dotenv.

First-time login

The scraper persists an authenticated browser state to storage_state.json and reuses it automatically. On first run, a visible window opens for manual login and is saved when the header shows you’re signed in.

If you prefer a credentialed, form-fill login for debugging, you can create a .env with ADI_USER and ADI_PASS and run:

python src/debug_login.py


This writes storage_state.json and drops HTML/PNG evidence in data/logs/.

Usage

Basic (headed browser, full flow):

python src/main.py --brand Hanwha


Headless:

python src/main.py --brand Hanwha --headless


Limit items (quick test):

python src/main.py --brand Hanwha --limit 10


Catalog-only (skip PDP/MSRP phase):

python src/main.py --brand Hanwha --catalog-only


Two-phase workflow (recommended for big runs):

Create a catalog snapshot (URLs, titles, models):

python src/main.py --brand Hanwha --catalog-only


Reuse that file to fetch only MSRP/attributes from PDPs:

python src/main.py --brand Hanwha --from-file "data/exports/adi_hanwha_catalog_YYYYMMDD_HHMM.xlsx"


Flags reference: --brand, --headless, --keep-open, --only-missing, --catalog-only, --from-file, --pdp-only, --limit.

When using --from-file, the loader ensures a url column exists and backfills any expected columns if missing. Expected columns include:
brand, title, model, alt_model, url, series, megapixels, form_factor, vandal, ir, msrp, msrp_raw.

What gets exported

Catalog snapshot (always written before the PDP phase unless --pdp-only):
data/exports/adi_hanwha_catalog_YYYYMMDD_HHMM.(csv|xlsx)

Results export (after PDP phase):
data/exports/adi_hanwha_msrp_YYYYMMDD_HHMM.(csv|xlsx) by default, or with a custom suffix from export.py.

Columns (combined across catalog + PDP):

brand, title, model, alt_model, url

Parsed/derived: series, megapixels, form_factor, ik_rating, ir, lens_type, lens_info (PDP features & title parsers).

Pricing: msrp_raw (e.g., MSRP $300), msrp (normalized numeric string).

How it parses things (at a glance)

Listing page: selects only links under /Product/* to avoid non-PDP collisions, reads the tile’s brand/title/codes, parses megapixels, series, form factor, IR, vandal keywords.

PDP page:

Title from the left column H1; Key Features bullets below it.

Model & ADI SKU (e.g., ANV-L7082R | SQ-ANVL7082R) read from the codes text under the H1.

MSRP discovered in the right column (or whole page) using label variants from config.py (e.g., MSRP, List Price).

Features regexes pull IK10/09/08, IR presence, lens type (Motorized Varifocal, Fixed, MFZ), and focal length (e.g., 3.3–10.3mm).

Brand configuration

Brands live in src/config.py. Hanwha is pre-wired with the IP Cameras listing URL and MSRP label variants. Add other brands by extending this dict.

Logs & diagnostics

Listing/PDP errors write screenshots/HTML under data/logs.

The code clicks away cookie/consent banners automatically.

Tips & troubleshooting

Not logged in / prices hidden: Delete storage_state.json and run again (headed) to refresh login.

Only update missing MSRP: add --only-missing when re-running a file with existing data.

Keep browser open (for manual inspection): add --keep-open. You’ll be prompted to press Enter when finished.

Tile count stuck: The catalog loader repeatedly scrolls/clicks “Load/Show More” and stops after counts stabilize; re-run if the site is slow.

Windows quick-run example

The included refresh_hanwha.bat can wrap a typical two-phase refresh (adjust paths as needed):

@echo off
REM Phase 1: Catalog snapshot
python src\main.py --brand Hanwha --catalog-only --headless

REM Phase 2: PDP/MSRP enrichment from latest catalog file (edit the filename)
python src\main.py --brand Hanwha --from-file "data\exports\adi_hanwha_catalog_YYYYMMDD_HHMM.xlsx" --only-missing --headless

License / Notes

Internal tooling for IDIS competitive pricing workflows. Site structure may change; selectors and regexes are written to be resilient but may need updates over time.