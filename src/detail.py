# detail.py — fast PDP MSRP (request blocking + smart waits + minimal reloads)

import os, re, time
from typing import List, Dict, Tuple, Optional
from playwright.sync_api import BrowserContext, Page, TimeoutError
from config import BRANDS

# ---------- Tunables ----------
FAST = os.getenv("ADI_FAST", "1") != "0"
PRICE_WAIT_MS = 6000 if FAST else 15000
POST_RENDER_MS = 200 if FAST else 350

BLOCK_HOST_SUBSTR = [
    "googletagmanager", "google-analytics", "doubleclick",
    "facebook", "hotjar", "optimizely", "adobedtm", "tealium",
]
BLOCK_RES_TYPES = {"image", "media", "font"}  # stylesheet allowed (layout ok, cheap)
# --------------------------------

def _install_fast_routes(ctx: BrowserContext):
    if not FAST:
        return
    def handler(route):
        req = route.request
        url = req.url.lower()
        # Kill heavy/irrelevant
        if req.resource_type in BLOCK_RES_TYPES:
            return route.abort()
        if any(h in url for h in BLOCK_HOST_SUBSTR):
            return route.abort()
        return route.continue_()
    # Safe to call once; no-op if already installed
    try:
        ctx.route("**/*", handler)
    except Exception:
        pass

# --- UX noise killers (OneTrust + misc) ---
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
                page.wait_for_timeout(120 if FAST else 150)
        except Exception:
            pass

def _is_logged_in(page: Page) -> bool:
    try:
        if page.locator("[data-test-selector='userMenu']").count(): return True
        if page.locator("text=/Sign Out/i").count(): return True
        if page.locator("text=/Hi,\\s*[A-Za-z]+/i").count(): return True
    except Exception:
        pass
    return False

def _pdp_shows_signin(page: Page) -> bool:
    rc = "div[data-test-selector='productDetails_rightColumn']"
    if page.locator(f"{rc} h1:has-text('Sign In for Dealer Pricing')").first.count(): return True
    if page.locator(f"{rc} button:has-text('Sign In')").first.count(): return True
    if page.locator(f"{rc} >> text=/Sign In/i").first.count(): return True
    return False

def _open_signin_drawer(page: Page) -> bool:
    rc_btn = page.locator("div[data-test-selector='productDetails_rightColumn'] button:has-text('Sign In'):visible").first
    if rc_btn.count():
        rc_btn.click()
    else:
        hdr = page.locator("header a:has-text('Sign In'), header button:has-text('Sign In'), header [data-test-selector='signInLink'], header [aria-label='Sign In']").first
        if hdr.count():
            hdr.click()
        else:
            return False
    try:
        page.wait_for_selector("[role='alertdialog'] .signInDrawer, .signInDrawer", timeout=5000 if FAST else 10000)
        return True
    except TimeoutError:
        return False

def _login_via_drawer(page: Page, ctx: BrowserContext, user: str, pwd: str) -> bool:
    drawer = page.locator("[role='alertdialog'] .signInDrawer, .signInDrawer").first
    if not drawer.count(): return False

    user_in = drawer.locator("[data-test-selector='signIn_userName'], #userName, input[name='userName'], input[name='username'], input[type='email'], input[name='email'], #email").first
    pass_in = drawer.locator("[data-test-selector='signIn_password'], #password, input[name='password'], input[type='password']").first
    submit  = drawer.locator("[data-test-selector='signIn_submit'], button[type='submit'], button:has-text('Sign In'), button:has-text('Sign in')").first

    if not (user_in.count() and pass_in.count()): return False

    user_in.click(force=True); user_in.fill(user, force=True)
    pass_in.click(force=True); pass_in.fill(pwd,  force=True)
    if submit.count(): submit.click()
    else: drawer.locator("button:has-text('Sign In')").first.click()

    ok = False
    for _ in range(40 if FAST else 80):
        if page.locator("[role='alertdialog'] .signInDrawer, .signInDrawer").count() == 0: ok = True; break
        if _is_logged_in(page): ok = True; break
        time.sleep(0.2 if FAST else 0.25)

    if ok:
        try: ctx.storage_state(path="storage_state.json")
        except Exception: pass
    return ok

def _wait_pricing_loaded(page: Page, timeout_ms: int = PRICE_WAIT_MS):
    """
    Wait for either: (a) a pricing-like XHR=200, OR (b) an MSRP/List label shows up.
    Uses context-level event to support older Playwright.
    """
    ctx = page.context
    patterns = ("/pricing", "/price", "/getpricing")
    labels = ["MSRP", "List Price", "List"]

    # (b) label watcher as quick path
    label_locator = page.locator(
        "div[data-test-selector='productDetails_rightColumn'] >> " +
        ",".join([f":text('{lbl}')" for lbl in labels])
    )

    # Arm response waiter
    def _matcher(resp):
        try:
            url = resp.url.lower()
            rtype = getattr(getattr(resp, "request", None), "resource_type", None)
            is_xhr = (rtype == "xhr") if rtype is not None else True
            return is_xhr and any(p in url for p in patterns) and resp.status == 200
        except Exception:
            return False

    start = time.time()
    got = False
    try:
        # race-ish loop: poll label quickly, otherwise wait for one pricing XHR
        while (time.time() - start) * 1000 < timeout_ms:
            if label_locator.count() and label_locator.first.is_visible():
                got = True; break
            try:
                ctx.wait_for_event("response", predicate=_matcher, timeout=500)  # short slice
                got = True; break
            except TimeoutError:
                pass
    except Exception:
        pass

    page.wait_for_timeout(POST_RENDER_MS)
    return got

def _extract_labeled_price(text: str, labels: List[str]) -> Optional[Tuple[str, str]]:
    for label in labels:
        m = re.search(rf"{re.escape(label)}\s*[:\-]?\s*\$?\s*([0-9][0-9,]*(?:\.\d{{2}})?)", text, re.I)
        if m: return m.group(1), label
    return None

def _msrp_text_from_page(page: Page, brand: str = "Hanwha") -> Optional[Tuple[str, str]]:
    labels = BRANDS.get(brand, {}).get("msrp_labels", ["MSRP", "List Price", "List"])
    scopes = [
        page.locator("div[data-test-selector='productDetails_rightColumn']").first,
        None,
    ]
    for scope in scopes:
        try:
            txt = scope.inner_text() if scope and scope.count() else page.inner_text()
        except Exception:
            txt = page.inner_text()
        hit = _extract_labeled_price(txt, labels)
        if hit: return hit
    return None

def fetch_mspp_for_products(ctx: BrowserContext, products: List[Dict], only_missing: bool = False) -> List[Dict]:
    _install_fast_routes(ctx)

    out: List[Dict] = []
    page = ctx.new_page()
    page.set_default_timeout(12000 if FAST else 20000)

    for i, prod in enumerate(products, 1):
        url = prod["url"]
        brand = prod.get("brand", "Hanwha")
        print(f"[PDP] {i}/{len(products)} → {url}")
        try:
            if only_missing and str(prod.get("msrp") or "").strip():
                out.append(prod); continue

            page.goto(url, wait_until="domcontentloaded")
            _dismiss_banners(page)

            # Make pricing area visible to trigger lazy logic
            right_col = page.locator("div[data-test-selector='productDetails_rightColumn']").first
            if right_col.count(): right_col.scroll_into_view_if_needed()
            else: page.evaluate("window.scrollBy(0, 600)")

            _wait_pricing_loaded(page)

            # First parse attempt
            hit = _msrp_text_from_page(page, brand=brand)

            # If missing, force one drawer-login and retry without reload (faster)
            if not hit:
                user = os.getenv("ADI_USER", "")
                pwd  = os.getenv("ADI_PASS", "")
                if not user or not pwd:
                    raise RuntimeError("Missing ADI_USER / ADI_PASS in environment/.env")

                need_login = _pdp_shows_signin(page) or not _is_logged_in(page)
                if need_login:
                    if not page.locator("[role='alertdialog'] .signInDrawer, .signInDrawer").first.count():
                        _open_signin_drawer(page)
                    if _login_via_drawer(page, ctx, user, pwd):
                        # try again without reload (DOM usually updates)
                        _wait_pricing_loaded(page, timeout_ms=PRICE_WAIT_MS+4000)
                        hit = _msrp_text_from_page(page, brand=brand)
                        # last resort: single reload
                        if not hit:
                            page.reload(wait_until="domcontentloaded")
                            _dismiss_banners(page)
                            if right_col.count(): right_col.scroll_into_view_if_needed()
                            _wait_pricing_loaded(page, timeout_ms=PRICE_WAIT_MS+6000)
                            hit = _msrp_text_from_page(page, brand=brand)

            # Backup: raw $ node scan
            if not hit:
                val_text = None
                candidates = [
                    "div[data-test-selector='productDetails_rightColumn'] :text('MSRP') >> xpath=following::*[contains(normalize-space(),'$')][1]",
                    "div[data-test-selector='productDetails_rightColumn'] .price",
                    "div[data-test-selector='productDetails_rightColumn'] [class*='price']",
                    "div[data-test-selector='productDetails_rightColumn'] :text(/^\\$\\s*\\d[\\d,]*(?:\\.\\d{2})?$/)"
                ]
                for sel in candidates:
                    try:
                        loc = page.locator(sel).first
                        if loc.count() and loc.is_visible():
                            t = loc.inner_text().strip()
                            m = re.search(r"\$?\s*([0-9][0-9,]*(?:\.\d{2})?)", t)
                            if m:
                                val_text = m.group(1); break
                    except Exception:
                        pass
                if val_text:
                    hit = (val_text, "MSRP")

            rec = {**prod, "msrp_raw": None, "msrp": None}
            if hit:
                value, label = hit
                rec["msrp_raw"] = f"{label} ${value}"
                rec["msrp"] = value.replace(",", "")
                print(f"[PDP] {label} ${value}")
            else:
                print("[PDP] MSRP not found.")
            out.append(rec)

        except TimeoutError:
            print("[PDP][TIMEOUT]")
            out.append({**prod, "msrp_raw": "TIMEOUT", "msrp": None})
        except Exception as e:
            print(f"[PDP][ERROR] {e}")
            out.append({**prod, "msrp_raw": f"ERROR: {e}", "msrp": None})

        page.wait_for_timeout(120 if FAST else 200)

    page.close()
    return out
