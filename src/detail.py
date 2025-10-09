# src/detail.py — PDP HTML parser (title + Key Features) + MSRP

import os
import re
import time
from typing import List, Dict, Optional, Tuple
from playwright.sync_api import BrowserContext, Page, TimeoutError
from config import BRANDS

# ---------- Regexes ----------
MODEL_RE    = re.compile(r"\b([A-Z]{2,4}-[A-Z0-9]+)\b")       # e.g., ANV-L7082R
ADISKU_RE   = re.compile(r"\bSQ-[A-Z0-9]+\b", re.I)            # e.g., SQ-ANVL7082R
MP_RE       = re.compile(r"\b(\d+(?:\.\d+)?)\s*MP\b", re.I)    # 4MP, 2.0 MP
IK_RE       = re.compile(r"\bIK[-\s]?(10|9|09|8|08)\b", re.I)  # IK10, IK09, IK8
MM_RANGE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*[-~–]\s*(\d+(?:\.\d+)?)\s*mm\b", re.I)
MM_SINGLE_RE= re.compile(r"\b(\d+(?:\.\d+)?)\s*mm\b", re.I)

# ---------- Helpers ----------
def _dismiss_banners(page: Page):
    for sel in [
        "#onetrust-accept-btn-handler",
        "#onetrust-banner-sdk #onetrust-accept-btn-handler",
        "button:has-text('Agree')",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "[aria-label='Close']",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click()
                page.wait_for_timeout(120)
        except Exception:
            pass

def _pdp_title(page: Page) -> str:
    """Main product title from the left product column only."""
    for sel in [
        "div[data-test-selector='productDetails_leftColumn'] h1",
        "main div[data-test-selector='productDetails_leftColumn'] h1",
        "main h1",
    ]:
        try:
            loc = page.locator(sel).first
            if loc.count():
                txt = loc.inner_text().strip()
                if txt:
                    return txt
        except Exception:
            pass
    return ""

def _key_features(page: Page) -> List[str]:
    """Key Features bullets from the left column area."""
    roots = [
        "div[data-test-selector='productDetails_leftColumn']",
        "main",
    ]
    for root in roots:
        loc = page.locator(f"{root} ul.mainfeatureslist li")
        if loc.count():
            try:
                items = [t.strip() for t in loc.all_inner_texts() if t and t.strip()]
                if items:
                    return items
            except Exception:
                pass
    # Fallback near a "Key Features" heading
    try:
        hf = page.locator("div[data-test-selector='productDetails_leftColumn'] :text('Key Features')").first
        if hf.count():
            parent = hf.locator("xpath=ancestor::*[1]")
            lis = parent.locator("li")
            return [t.strip() for t in lis.all_inner_texts() if t.strip()]
    except Exception:
        pass
    return []

def _pdp_codes(page: Page) -> Tuple[str, str]:
    """
    Read model + ADI SKU from the header area under the H1.
    Example: 'ANV-L7082R | SQ-ANVL7082R'
    """
    containers = [
        "div[data-test-selector='productDetails_leftColumn']",
        "main div[data-test-selector='productDetails_leftColumn']",
    ]
    for root in containers:
        c = page.locator(root).first
        if not c.count():
            continue
        try:
            txt = c.inner_text()
        except Exception:
            continue
        m = MODEL_RE.search(txt)
        s = ADISKU_RE.search(txt)
        model   = m.group(1) if m else ""
        alt_mod = s.group(0) if s else ""
        if model or alt_mod:
            return model, alt_mod
    return "", ""

def _derive_from_title_and_model(title: str, model: str) -> Dict[str, Optional[str]]:
    """Series from model, MP + form_factor best-effort from title."""
    series = None
    if model and re.match(r"^[A-Z]", model):
        series = f"{model[0]}-Series"

    mp = None
    m_mp = MP_RE.search(title or "")
    if m_mp:
        mp = m_mp.group(1)

    lo = (title or "").lower()
    form = None
    if "bullet" in lo: form = "Bullet"
    elif "dome" in lo: form = "Dome"
    elif "turret" in lo: form = "Turret"
    elif "ptz" in lo: form = "PTZ"
    elif "box camera" in lo or "box-style" in lo: form = "Box"

    return {"series": series, "megapixels": mp, "form_factor": form}

def _parse_features(features: List[str]) -> Dict[str, Optional[str]]:
    """IK rating, IR, lens type/info from Key Features."""
    text = " | ".join(features)

    ik = None
    m_ik = IK_RE.search(text)
    if m_ik:
        ik = f"IK{m_ik.group(1).zfill(2)}"

    ir = bool(re.search(r"\bIR\b|infrared", text, re.I))

    lens_type = None
    if re.search(r"\bmotorized\b", text, re.I): lens_type = "Motorized"
    if re.search(r"\bvarifocal\b", text, re.I):
        lens_type = (lens_type + " Varifocal") if lens_type else "Varifocal"
    if re.search(r"\bMFZ\b", text, re.I): lens_type = "MFZ"
    if re.search(r"\bmanual\b", text, re.I) and not lens_type: lens_type = "Manual"
    if re.search(r"\bfixed\b", text, re.I) and not lens_type: lens_type = "Fixed"

    lens_info = None
    mrange = MM_RANGE_RE.search(text)
    if mrange:
        lens_info = f"{mrange.group(1)}-{mrange.group(2)}mm"
    else:
        msingle = MM_SINGLE_RE.search(text)
        if msingle:
            lens_info = f"{msingle.group(1)}mm"

    return {
        "ik_rating": ik,
        "ir": ir,
        "lens_type": lens_type,
        "lens_info": lens_info,
    }

def _msrp_text_from_page(page: Page, brand: str = "Hanwha") -> Optional[str]:
    """Find MSRP value in the right column or whole page."""
    labels = BRANDS.get(brand, {}).get("msrp_labels", ["MSRP"])
    scopes = [
        "div[data-test-selector='productDetails_rightColumn']",
        "body",
    ]
    for scope in scopes:
        try:
            txt = page.locator(scope).first.inner_text()
        except Exception:
            continue
        for label in labels:
            # Use compiled regex to avoid f-string brace issues
            pat = re.compile(re.escape(label) + r"\s*\$?\s*([0-9][0-9,]*(?:\.\d{2})?)", re.I)
            m = pat.search(txt)
            if m:
                return m.group(1)
    return None

def fetch_mspp_for_products(ctx: BrowserContext, products: List[Dict], only_missing: bool = False) -> List[Dict]:
    """
    Visit each PDP and extract MSRP + structured attributes directly
    from the HTML (title + Key Features + header codes).
    """
    out: List[Dict] = []
    page = ctx.new_page()
    page.set_default_timeout(60000)

    for i, prod in enumerate(products, 1):
        url = prod.get("url") or ""
        brand = prod.get("brand", "Hanwha")
        print(f"[PDP] {i}/{len(products)} → {url}")
        try:
            if only_missing and str(prod.get("msrp") or "").strip():
                out.append(prod)
                continue

            page.goto(url, wait_until="domcontentloaded")
            _dismiss_banners(page)
            # Light settle; DOM is server-rendered for these bits
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except TimeoutError:
                pass

            title = _pdp_title(page)
            features = _key_features(page)
            model, alt_model = _pdp_codes(page)
            basics = _derive_from_title_and_model(title, model)
            more = _parse_features(features)
            msrp_val = _msrp_text_from_page(page, brand=brand)

            rec = {**prod}
            rec.update({
                "title": title or prod.get("title"),
                "model": model or prod.get("model"),
                "alt_model": alt_model or prod.get("alt_model"),
                "series": basics["series"] or prod.get("series"),
                "megapixels": basics["megapixels"] or prod.get("megapixels"),
                "form_factor": basics["form_factor"] or prod.get("form_factor"),
                "ik_rating": more["ik_rating"] or prod.get("ik_rating"),
                "ir": True if more["ir"] else (prod.get("ir") or False),
                "lens_type": more["lens_type"] or prod.get("lens_type"),
                "lens_info": more["lens_info"] or prod.get("lens_info"),
                "msrp_raw": None,
                "msrp": None,
            })

            if msrp_val:
                rec["msrp_raw"] = f"MSRP ${msrp_val}"
                rec["msrp"] = msrp_val.replace(",", "")

            out.append(rec)

        except TimeoutError:
            print("[PDP][TIMEOUT]")
            out.append({**prod, "msrp_raw": "TIMEOUT", "msrp": None})
        except Exception as e:
            print(f"[PDP][ERROR] {e}")
            out.append({**prod, "msrp_raw": f"ERROR: {e}", "msrp": None})

        page.wait_for_timeout(120)

    page.close()
    return out
# ---------- EOF ----------