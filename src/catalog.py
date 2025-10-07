# catalog.py – find all product URLs for a brand
from typing import List, Dict
from playwright.sync_api import BrowserContext
from urllib.parse import urlencode

# Adjust this base/filters to the exact Hanwha camera listing you use
BASE = 'https://www.adiglobaldistribution.us/Search'  # placeholder

def _brand_query(brand: str) -> str:
    # TODO: refine brand/category query params as needed
    q = {'q': brand, 'category': 'Cameras'}
    return f"{BASE}?{urlencode(q)}"

def fetch_product_list(ctx: BrowserContext, brand: str) -> List[Dict]:
    page = ctx.new_page()
    url = _brand_query(brand)
    page.goto(url, wait_until='domcontentloaded')

    products = []
    while True:
        # Update selectors to match ADI search result cards
        items = page.locator('[data-product-card]').all()  # placeholder
        for it in items:
            name = it.locator('.product-title').inner_text(timeout=5000)
            sku  = it.locator('.product-sku').inner_text(timeout=5000)
            href = it.locator('a.product-link').get_attribute('href')
            products.append({'sku': sku.strip(), 'name': name.strip(), 'url': href})

        next_btn = page.locator('a[rel="next"]')
        if not (next_btn.count() and next_btn.is_enabled()):
            break
        next_btn.click()
        page.wait_for_load_state('networkidle')
    page.close()
    # de-dupe
    seen = set()
    out = []
    for p in products:
        if p['sku'] not in seen:
            seen.add(p['sku'])
            out.append(p)
    return out
