# auth.py – Playwright login + storage state
from playwright.sync_api import sync_playwright
from pathlib import Path
import os

AUTH_PATH = Path('.auth/adi.json')

def ensure_login(headless: bool = True):
    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    user = os.getenv('ADI_USER')
    pw   = os.getenv('ADI_PASS')
    if not user or not pw:
        raise RuntimeError("Missing ADI_USER/ADI_PASS in .env")

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=headless)
    ctx = browser.new_context(storage_state=str(AUTH_PATH)) if AUTH_PATH.exists() else browser.new_context()

    page = ctx.new_page()
    # TODO: update login URL if different at your site
    page.goto('https://www.adiglobaldistribution.us/Account/Login', wait_until='domcontentloaded')

    if 'Login' in page.title() or 'Sign' in page.title():
        # Update selectors if site differs
        page.fill('input[name="Email"]', user)
        page.fill('input[name="Password"]', pw)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
        ctx.storage_state(path=str(AUTH_PATH))
    return ctx
