import argparse
from pathlib import Path
from dotenv import load_dotenv
import os

from auth import ensure_login
from catalog import fetch_product_list
from detail import fetch_mspp_for_products
from export import export_results

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--brand", required=True, help="Hanwha|Axis|Avigilon|all")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--only-missing", action="store_true")
    return p.parse_args()

def main():
    load_dotenv()
    args = parse_args()
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    ctx = ensure_login(headless=args.headless)

    products = fetch_product_list(ctx, brand=args.brand)
    results  = fetch_mspp_for_products(ctx, products, only_missing=args.only_missing)

    export_results(results, brand=args.brand)

    print(f"Done. Items: {len(results)}")

if __name__ == "__main__":
    main()
