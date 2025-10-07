# detail.py – open product page and extract MSRP
from typing import List, Dict
from playwright.sync_api import BrowserContext

def _parse_price(txt: str) -> float:
    digits = ''.join(ch for ch in txt if ch.isdigit() or ch in '.')
    if digits.count('.') > 1:
        # fix formats like 6,27399 seen as 6273.99
        digits = digits.replace('.', '', digits.count('.')-1)
    return float(digits)

def fetch_mspp_for_products(ctx: BrowserContext, products: List[Dict], only_missing: bool=False) -> List[Dict]:
    page = ctx.new_page()
    results = []
    for p in products:
        page.goto(p['url'], wait_until='domcontentloaded')
        # Update selector to the MSRP element on the product page
        msrp_el = page.locator('text=MSRP').locator('..').locator('.price')  # placeholder chain
        if msrp_el.count() == 0:
            # fallback selector example
            msrp_el = page.locator('.msrp, .list-price, [data-msrp]')
        price_txt = msrp_el.first.inner_text(timeout=10000)
        msrp = _parse_price(price_txt)
        results.append({**p, 'msrp': msrp})
    page.close()
    return results
