import os, time, re
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError

HOME   = "https://www.adiglobaldistribution.us/"
SIGNIN = "https://www.adiglobaldistribution.us/MyAccount/signin"
LOGDIR = Path("data/logs"); LOGDIR.mkdir(parents=True, exist_ok=True)

def shot(page, name):
    try:
        page.screenshot(path=str(LOGDIR/f"{name}.png"), full_page=True)
    except Exception:
        pass
    try:
        with open(LOGDIR/f"{name}.html","w",encoding="utf-8") as f:
            f.write(page.content())
    except Exception:
        pass

def dismiss_banners(page):
    # OneTrust cookie banner (the big “Agree” button)
    for sel in [
        "#onetrust-accept-btn-handler",
        "#onetrust-banner-sdk #onetrust-accept-btn-handler",
        "button:has-text('Agree')",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "[aria-label='Close']",
    ]:
        try:
            b = page.locator(sel).first
            if b.count() and b.is_visible():
                b.click()
                page.wait_for_timeout(150)
        except Exception:
            pass

def is_logged_in(page) -> bool:
    try:
        if page.locator("[data-test-selector='userMenu']").count(): return True
        if page.locator("text=/Sign Out/i").count(): return True
        if page.locator("text=/Hi,\\s*Sam/i").count(): return True
    except Exception:
        pass
    return False

def main():
    load_dotenv()
    user = os.getenv("ADI_USER","")
    pwd  = os.getenv("ADI_PASS","")
    if not user or not pwd:
        raise RuntimeError("Missing ADI_USER / ADI_PASS")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, slow_mo=150,
            args=["--disable-blink-features=AutomationControlled"]
        )
        ctx = browser.new_context(viewport={"width":1400,"height":900})
        page = ctx.new_page()
        page.set_default_timeout(60000)

        # 1) Home
        page.goto(HOME, wait_until="domcontentloaded")
        dismiss_banners(page)
        shot(page, "00_home")

        # Already logged in?
        if is_logged_in(page):
            print("[DEBUG] Already logged in on HOME.")
            ctx.storage_state(path="storage_state.json")
            print("[DEBUG] storage_state.json written.")
            browser.close(); return

        # 2) Sign-in page (left form)
        page.goto(SIGNIN, wait_until="domcontentloaded")
        dismiss_banners(page)
        page.evaluate("window.scrollBy(0, 240)")
        shot(page, "01_signin_landing")

        # Scope to the LEFT sign-in form explicitly
        form = page.locator(
            "form:has(input[type='email']), form:has(input[name='emailAddress'])"
        ).first
        # Fallback if site uses username variant
        if not form.count():
            form = page.locator(
                "form:has([data-test-selector='signIn_userName']), form:has(#userName), form:has(input[name='userName'])"
            ).first

        if not form.count():
            print("[DEBUG] Sign-in form not found.")
            shot(page, "02_no_form")
            browser.close(); return

        # Inputs
        email_in = form.locator("input[type='email'], input[name='email'], #email, input[name='emailAddress']").first
        user_in  = form.locator("[data-test-selector='signIn_userName'], #userName, input[name='userName'], input[name='username']").first
        pass_in  = form.locator("[data-test-selector='signIn_password'], #password, input[name='password'], input[type='password']").first

        # Fill either email or username form
        if email_in.count() and pass_in.count():
            email_in.click(force=True); email_in.fill(user, force=True)
            pass_in.click(force=True);  pass_in.fill(pwd,  force=True)
        elif user_in.count() and pass_in.count():
            user_in.click(force=True); user_in.fill(user, force=True)
            pass_in.click(force=True); pass_in.fill(pwd,  force=True)
        else:
            print("[DEBUG] Inputs not found inside form.")
            shot(page, "03_inputs_missing")
            browser.close(); return

        # Submit (button within the same form)
        submit = form.locator("[data-test-selector='signIn_submit'], button[type='submit'], button:has-text('Sign In'), button:has-text('Sign in')").first
        if submit.count():
            submit.click()
        else:
            page.keyboard.press("Enter")

        # 3) Normalize: go Home and verify
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except TimeoutError:
            pass
        page.goto(HOME, wait_until="domcontentloaded")
        dismiss_banners(page)
        shot(page, "04_home_after_login")

        # Poll a bit for the header to update
        ok = False
        end = time.time() + 20
        while time.time() < end:
            if is_logged_in(page):
                ok = True
                break
            page.wait_for_timeout(300)

        print("[DEBUG] Logged-in header present:", ok)
        if not ok:
            print("[DEBUG] Login still not detected. See data/logs/ for HTML/PNG.")
        else:
            ctx.storage_state(path="storage_state.json")
            print("[DEBUG] storage_state.json written.")

        browser.close()

if __name__ == "__main__":
    main()
