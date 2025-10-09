# 🧾 ADI MSRP Scraper

A Python scraper that extracts **Hanwha camera product data** from **ADI Global (US)**, retrieves **MSRP and product details**, and exports structured results to Excel or CSV.

---

## 📦 Overview

The scraper performs the following steps:

1. **Authenticates** to ADI and saves session data → `storage_state.json`  
2. **Loads all products** from the ADI listing page  
3. **Optionally visits each Product Detail Page (PDP)** to extract MSRP and technical specs  
4. **Exports results** to `data/exports/` with timestamped filenames  

---

## 📁 Folder Structure

```
adi-msrp-scraper/
├─ data/
│  ├─ exports/              # Auto-created output (Excel / CSV)
│  └─ logs/                 # Optional: saved HTML/screenshot logs
├─ src/
│  ├─ auth.py               # Login + session handling
│  ├─ catalog.py            # Listing-page scraper
│  ├─ config.py             # Brand and site configuration
│  ├─ detail.py             # PDP parser for MSRP + attributes
│  ├─ export.py             # Excel/CSV export logic
│  ├─ main.py               # CLI entry point
│  └─ debug_login.py        # Manual login helper (optional)
├─ requirements.txt
├─ refresh_hanwha.bat       # Example Windows batch file
└─ storage_state.json       # Saved login session (auto-created)
```

---

## ⚙️ Installation

**Requirements**

- Python **3.10+**
- Playwright
- Chrome/Chromium

**Install dependencies**

```bash
pip install -r requirements.txt
python -m playwright install
```

---

## 🚀 How to Run

> All commands should be executed from the **repo root** (where `src/` is located).

---

### 🟩 1. Run the Full Scraper (Catalog + PDP + MSRP)

Fetch all products, visit each PDP, and export MSRP + product details.

```bash
python src/main.py --brand Hanwha
```

**Optional flags:**

```bash
--headless       # Run without browser window
--keep-open      # Keep browser open for debugging
--limit 10       # Process only the first 10 products
```

**Example:**

```bash
python src/main.py --brand Hanwha --headless
```

---

### 🟦 2. Catalog-Only (No PDP/MSRP)

Create a product list (URLs only), skipping PDP scraping.

```bash
python src/main.py --brand Hanwha --catalog-only
```

**Output:**  
`data/exports/adi_hanwha_catalog_YYYYMMDD_HHMM.xlsx`

---

### 🟨 3. Use an Existing Catalog File (Fetch MSRP Only)

If you already have a file with product URLs (Excel or CSV), reuse it to scrape MSRP and details only.

```bash
python src/main.py --brand Hanwha --from-file "data/exports/adi_hanwha_catalog_20251008_1530.xlsx"
```

**Helpful flags:**

```bash
--only-missing   # Only update rows missing MSRP
--pdp-only       # Skip catalog scrape phase
--headless       # Hide browser window
```

**Example:**

```bash
python src/main.py --brand Hanwha --from-file "data/exports/adi_hanwha_catalog_20251008_1530.xlsx" --only-missing --headless
```

**Output:**  
`data/exports/adi_hanwha_msrp_YYYYMMDD_HHMM.xlsx`

---

### 🟥 4. Refresh Login (If MSRP Disappears)

If MSRP values stop appearing, your session likely expired. Re-login manually.

**macOS / Linux:**

```bash
rm -f storage_state.json
python src/main.py --brand Hanwha
```

**Windows:**

```bat
del storage_state.json
python src\main.py --brand Hanwha
```

Or use environment variables (`ADI_USER`, `ADI_PASS`) for automated login:

```bash
python src/debug_login.py
```

---

### 🟪 5. Recommended Two-Phase Workflow (For Large Runs)

**Phase 1 – Catalog Snapshot**

```bash
python src/main.py --brand Hanwha --catalog-only --headless
```

**Phase 2 – PDP/MSRP Enrichment**

```bash
python src/main.py --brand Hanwha --from-file "data/exports/adi_hanwha_catalog_YYYYMMDD_HHMM.xlsx" --only-missing --headless
```

---

## 📤 Exported Files

| Type | Example Filename | Description |
|------|------------------|-------------|
| Catalog Snapshot | `adi_hanwha_catalog_YYYYMMDD_HHMM.xlsx` | Product list + URLs |
| MSRP Results | `adi_hanwha_msrp_YYYYMMDD_HHMM.xlsx` | Combined catalog + MSRP results |

**Common columns:**

```
brand, title, model, alt_model, url,
series, megapixels, form_factor, ir, ik_rating,
lens_type, lens_info, msrp_raw, msrp
```

---

## 🧠 How It Works

- **`catalog.py`** — Scrapes listing pages for product tiles (brand, title, SKU, URL)  
- **`detail.py`** — Extracts MSRP, lens info, IK rating, etc. from each PDP  
- **`config.py`** — Holds brand URLs and label patterns  
- **`export.py`** — Merges and exports Excel/CSV output  
- **`auth.py`** — Manages login + reuses `storage_state.json` session  

---

## 🧹 Troubleshooting

| Issue | Solution |
|--------|-----------|
| MSRP missing | Delete `storage_state.json` and re-login |
| Only update rows missing MSRP | Use `--only-missing` |
| Watch browser actions | Use `--keep-open` |
| Scraper slow or stuck | Use `--limit` to test fewer products |
| `.adi_profile` files showing in git | Add `.adi_profile/` to `.gitignore` |

---

## 🪟 Example Windows Batch File

```bat
@echo off
REM Phase 1: Catalog snapshot
python src\main.py --brand Hanwha --catalog-only --headless

REM Phase 2: MSRP enrichment
python src\main.py --brand Hanwha --from-file "data\exports\adi_hanwha_catalog_YYYYMMDD_HHMM.xlsx" --only-missing --headless
```

---

## 📜 License / Notes

Internal tool for **IDIS Americas** — used for product benchmarking and MSRP validation.  
ADI website structure may change; adjust selectors or patterns as needed.

---
