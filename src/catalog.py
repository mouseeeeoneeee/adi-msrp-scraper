# catalog.py — Hanwha IP Cameras: load all tiles → extract product fields → dedupe
from typing import List, Dict, Optional
from playwright.sync_api import BrowserContext
from pathlib import Path
import re, time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from config import BRANDS

LOG_DIR = Path("data/logs"); LOG_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------
# Logging
# -------------------------
def _log(msg: str): 
    print("[CATALOG]", msg)

# -------------------------
# Navigation helpers
# -------------------------
def _ensure_param(url: str, key: str, value: str) -> str:
    pr = urlparse(url)
    q = parse_qs(pr.query)
    q[key] = [value]
    new_q = urlencode({k: v[0] for k, v in q.items()})
    return urlunparse(pr._replace(query=new_q))

def _safe_click(page, selector: str, timeout: int = 9000) -> bool:
    try:
        loc = page.locator(selector)
        if loc.count():
            el = loc.first
            el.wait_for(state="visible", timeout=timeout)
            if el.is_enabled():
                el.click()
                page.wait_for_load_state("networkidle")
                time.sleep(0.25)
                return True
    except Exception:
        pass
    return False

def _wait_for_grid(page, timeout_ms: int = 15000) -> None:
    sels = [
        "[data-product-card]",
        ".product-card",
        ".product-tile",
        ".search-result-item",
        "li.product",
        ".product-list-item",
        "a[href*='/Product/']:has(img)",
        "a[href*='/product/']:has(img)"
    ]
    end = time.time() + (timeout_ms / 1000.0)
    while time.time() < end:
        for s in sels:
            try:
                if page.locator(s).count() > 0:
                    return
            except Exception:
                pass
        time.sleep(0.2)

def _parse_total(page) -> int:
    try:
        txt = page.locator("text=Showing").first.inner_text(timeout=2500)
        m = re.search(r"of\s+(\d+)", txt)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0

def _load_all(page):
    """Click “Show/Load More” and scroll until counts stabilize."""
    _log("Loading all products…")
    prev = -1
    stable = 0
    for _ in range(500):  # generous cap
        cards = page.locator(
            "[data-product-card], .product-card, .product-tile, "
            ".search-result-item, li.product, .product-list-item, "
            "a[href*='/Product/']:has(img), a[href*='/product/']:has(img)"
        ).count()

        clicked = (
            _safe_click(page, "button:has-text('Show More Products')")
            or _safe_click(page, "a:has-text('Show More Products')")
            or _safe_click(page, "button:has-text('Load More')")
            or _safe_click(page, "a:has-text('Load More')")
        )

        # nudge lazy-load
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        except Exception:
            pass
        time.sleep(0.4)

        if cards == prev and not clicked:
            stable += 1
        else:
            stable = 0
        prev = cards

        if stable >= 3:
            break

    _log(f"Loaded total product cards (visible): {max(prev, 0)}")

# -------------------------
# Attribute parsing
# -------------------------
SERIES_RE = re.compile(r"\b([A-Z]-Series|[A-Z] Series|[A-Z]-?series)\b", re.I)
MP_RE     = re.compile(r"(\d+(?:\.\d+)?)\s*MP\b", re.I)

def _parse_attrs(title: str) -> Dict[str, Optional[str]]:
    t = (title or "").strip()
    lo = t.lower()

    # series
    series = None
    m = SERIES_RE.search(t)
    if m:
        series = m.group(1).upper().replace("SERIES", "Series")

    # mp
    mp = None
    mm = MP_RE.search(t)
    if mm:
        mp = mm.group(1)

    # form factor
    if "bullet" in lo:   form_factor = "Bullet"
    elif "dome" in lo:   form_factor = "Dome"
    elif "ptz" in lo:    form_factor = "PTZ"
    elif "box camera" in lo or "box-style" in lo: form_factor = "Box"
    else: form_factor = None

    vandal = "vandal" in lo
    ir     = "ir " in lo or "ir-" in lo or "ir," in lo or "infrared" in lo

    return {
        "series": series,
        "megapixels": mp,
        "form_factor": form_factor,
        "vandal": vandal,
        "ir": ir,
    }

# -------------------------
# Extraction
# -------------------------

def _extract_on_page_fast(page) -> List[Dict]:
    """
    Extract tiles using ADI data-test-selector hooks.
    Only accept PDP links under /Product/* to avoid brand-link collisions.
    """
    js = r"""
    () => {
      const toAbs = (h) => {
        if (!h) return "";
        return h.startsWith("http") ? h : "https://www.adiglobaldistribution.us" + h;
      };

      const cards = Array.from(document.querySelectorAll(
        "[data-test-selector='productListProductImage']"
      )).map(n => n.closest("div.sc-bczRLJ") || n.closest("div"));

      const rows = [];
      for (const card of cards) {
        // PDP URL: prefer description link, else image link
        const aDesc = card.querySelector("a[data-test-selector='productDescriptionLink']");
        const aImg  = card.querySelector("a[data-test-selector='productImage']");
        const href  = aDesc?.getAttribute("href") || aImg?.getAttribute("href") || "";
        if (!/^\/Product\//i.test(href)) {
          // Not a product detail link → skip this tile
          continue;
        }
        const url = toAbs(href);

        // Brand and Title
        const brand = (card.querySelector("[data-test-selector='brandLink'] span")?.textContent || "Hanwha Vision").trim();
        const title = (aDesc?.textContent || "").trim();

        // Models (e.g., ANV-L7012R | SQ-ANVL7012R)
        const partGrid = card.querySelector("[data-test-selector='plpPartNumberGrid']");
        const parts = partGrid ? Array.from(partGrid.querySelectorAll("span")).map(s => (s.textContent||"").trim()).filter(Boolean) : [];
        // Plp prints "ANV-L7012R | SQ-ANVL7012R" as three spans: [ANV-L7012R, |, SQ-ANVL7012R]
        const codes = parts.filter(x => /^[A-Z0-9]{2,}[-_A-Z0-9]+$/.test(x));
        const model = codes[0] || "";
        let alt_model = "";
        if (codes.length > 1) {
          const pref = codes.slice(1).find(c => c.toUpperCase().startsWith("SQ-"));
          alt_model = pref || codes[1];
        }

        // Lightweight attribute parsing from title
        const lo = title.toLowerCase();
        let form = null;
        if (lo.includes("bullet")) form = "Bullet";
        else if (lo.includes("dome")) form = "Dome";
        else if (lo.includes("ptz")) form = "PTZ";
        else if (lo.includes("box camera") || lo.includes("box-style")) form = "Box";
        const vandal = /vandal/i.test(title);
        const ir = /\bIR\b|infrared/i.test(title);
        const mpMatch = title.match(/(\d+(?:\.\d+)?)\s*MP\b/i);
        const megapixels = mpMatch ? mpMatch[1] : null;
        const seriesMatch = title.match(/\b([A-Z]-Series|[A-Z]\s*Series)\b/i);
        const series = seriesMatch ? seriesMatch[1].toUpperCase().replace("SERIES","Series") : null;

        rows.push({
          brand, title, model, alt_model, url,
          series, megapixels, form_factor: form, vandal, ir
        });
      }
      return rows;
    }
    """
    return page.evaluate(js)



def _extract_on_page(page) -> List[Dict]:
    """Extract fields from each tile: brand, title, model(s), url, parsed attrs."""
    products: List[Dict] = []

    cards = page.locator(
        "[data-product-card], .product-card, .product-tile, "
        ".search-result-item, li.product, .product-list-item"
    )
    count = cards.count()
    if count == 0:
        cards = page.locator("a[href*='/Product/'], a[href*='/product/'], a[href*='/Catalog/product']")
        count = cards.count()

    for i in range(count):
        card = cards.nth(i)

        # URL
        href = None
        for sel in ["a.product-link", "a[href*='/Product/']", "a[href*='/product/']", "a[href*='/Catalog/product']", "a[href]"]:
            try:
                if card.locator(sel).count():
                    href = card.locator(sel).first.get_attribute("href")
                    if href: break
            except Exception:
                pass
        if not href:
            try:
                href = card.get_attribute("href")
            except Exception:
                href = None
        if not href:
            continue
        if not href.startswith("http"):
            href = f"https://www.adiglobaldistribution.us{href}"

        # Brand (e.g., "Hanwha Vision")
        brand = ""
        for sel in ["[class*='brand']", "span:has-text('Hanwha')", "div:has-text('Hanwha Vision')"]:
            try:
                if card.locator(sel).count():
                    txt = card.locator(sel).first.inner_text().strip()
                    if "hanwha" in txt.lower():
                        brand = txt
                        break
            except Exception:
                pass
        if not brand:
            # fallback: first small element above title
            try:
                brand = card.locator("text=/Hanwha/i").first.inner_text().strip()
            except Exception:
                brand = "Hanwha Vision"

        # Title (marketing name)
        title = ""
        for sel in [".product-title", "h2", "[itemprop='name']", "a"]:
            if card.locator(sel).count():
                try:
                    title = card.locator(sel).first.inner_text().strip()
                    if title: break
                except Exception:
                    pass

        # Models (two usually appear separated by '|', e.g., "QNV-8080R | SQ-QNV8080R")
        model = ""
        alt_model = ""
        try:
            sku_line = card.locator("text=/\\b[A-Z0-9]{2,}[-_A-Z0-9]+\\b/").all_inner_texts()
            joined = " | ".join(sku_line)
            # pick first two distinct codes
            codes = re.findall(r"\b[A-Z0-9]{2,}[-_A-Z0-9]+\b", joined)
            if codes:
                model = codes[0]
                if len(codes) > 1:
                    # prefer the one starting with SQ- for alt_model if present
                    sq = [c for c in codes[1:] if c.upper().startswith("SQ-")]
                    alt_model = sq[0] if sq else codes[1]
        except Exception:
            pass

        # Parsed attributes from title
        attrs = _parse_attrs(title)

        products.append({
            "brand": brand,
            "title": title,
            "model": model,
            "alt_model": alt_model,
            "url": href,
            **attrs
        })

    return products

# -------------------------
# Entry point
# -------------------------
def fetch_product_list(ctx: BrowserContext, brand: str) -> List[Dict]:
    cfg = BRANDS[brand]
    page = ctx.new_page()
    page.set_default_timeout(90000)

    # 1) open pre-filtered IP Cameras URL
    url = cfg["list_url"]
    url = _ensure_param(url, "perPage", "140")           # reduce pagination
    url = _ensure_param(url, "sortCriteria", "relevance")
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")
    _log("IP Cameras page loaded")

    # 2) wait for grid & exhaust “Show/Load More”
    _wait_for_grid(page, timeout_ms=15000)
    total = _parse_total(page)
    _log(f"Total reported: {total} (ok if 0)")
    _load_all(page)

    # 3) extract tiles (robust, no MSRP here)
    try:
        ## items = _extract_on_page(page) ##
        items = _extract_on_page_fast(page)
        
    except Exception as e:
        _log(f"Extraction error: {e}")
        page.screenshot(path=str(LOG_DIR / "extract_error.png"), full_page=True)
        with open(LOG_DIR / "extract_error.html", "w", encoding="utf-8") as f:
            f.write(page.content())
        items = []

    _log(f"Extracted tiles (pre-dedupe): {len(items)}")

    if not items:
        page.screenshot(path=str(LOG_DIR / "catalog_zero_items.png"), full_page=True)
        with open(LOG_DIR / "catalog_zero_items.html", "w", encoding="utf-8") as f:
            f.write(page.content())

    page.close()

    # 4) de-dupe by URL
    seen = set(); uniq = []
    for it in items:
        key = it.get("url") or it.get("model")
        if not key:
            continue
        if key not in seen:
            seen.add(key)
            uniq.append(it)

    _log(f"Final unique products: {len(uniq)}")
    return uniq  # ← this line must be indented exactly like _log(...)
# ← no code at all after this

