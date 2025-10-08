from pathlib import Path
import time
from playwright.sync_api import sync_playwright

HOME = "https://www.adiglobaldistribution.us/"
SIGNIN = "https://www.adiglobaldistribution.us/MyAccount/signin"
STATE_FILE = "storage_state.json"

COOKIE_KILL = [
    "#onetrust-accept-btn-handler",
    "#onetrust-banner-sdk #onetrust-accept-btn-handler",
    "button:has-text('Agree')",
    "button:has-text('Accept All')",
    "button:has-text('Accept Cookies')",
    "[aria-label='Close']",
]

def _kill_banners(page):
    for sel in COOKIE_KILL:
        try:
            btn = page.locator(sel).first
            if btn.count() and btn.is_visible():
                btn.click()
                page.wait_for_timeout(150)
        except Exception:
            pass

def _is_logged_in(page) -> bool:
    try:
        if page.locator("[data-test-selector='userMenu']").count():
            return True
        if page.locator("text=/Sign Out/i").count():
            return True
        if page.locator("text=/Hi,\\s*[A-Za-z]+/i").count():
            return True
    except Exception:
        pass
    return False

def _poll_until_logged_in(page, seconds: int) -> bool:
    end = time.time() + seconds
    while time.time() < end:
        _kill_banners(page)
        if _is_logged_in(page):
            return True
        page.wait_for_timeout(300)
    return False

def ensure_login(headless=False):
    """
    First run: opens a visible window, you log in once, we reuse THAT SAME context
    for the run and persist storage_state.json. Later runs reuse storage_state.json.
    """
    p = sync_playwright().start()

    # Fast path: try to reuse saved state (headless or headed per flag)
    if Path(STATE_FILE).exists():
        browser = p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(storage_state=STATE_FILE, viewport={"width":1400,"height":900})
        page = ctx.new_page()
        page.goto(HOME, wait_until="domcontentloaded")
        _kill_banners(page)
        if _is_logged_in(page):
            page.close()
            print("[AUTH] Reusing storage_state.json")
            return p, ctx
        # stale → drop state and fall through to manual
        try: Path(STATE_FILE).unlink()
        except Exception: pass
        try: page.close()
        except Exception: pass
        browser.close()

    # No valid state → force a VISIBLE manual login once
    print("[AUTH] First-time login required. A browser window will open. Log in within 2 minutes.")
    vis_browser = p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
    vis_ctx = vis_browser.new_context(viewport={"width":1400,"height":900})
    vis_page = vis_ctx.new_page()
    vis_page.set_default_timeout(60000)

    vis_page.goto(SIGNIN, wait_until="domcontentloaded")
    _kill_banners(vis_page)
    vis_page.evaluate("window.scrollBy(0, 240)")
    print("[AUTH] Please complete login in the visible window...")

    ok = _poll_until_logged_in(vis_page, seconds=120)
    if not ok:
        vis_page.goto(HOME, wait_until="domcontentloaded")
        _kill_banners(vis_page)
        ok = _poll_until_logged_in(vis_page, seconds=20)

    if not ok:
        print("[AUTH][ERROR] Login not detected. Leave window open to inspect. Aborting.")
        raise RuntimeError("Manual login not detected")

    # Persist for future and reuse THIS context for the run
    vis_ctx.storage_state(path=STATE_FILE)
    print("[AUTH] storage_state.json written.")
    return p, vis_ctx
