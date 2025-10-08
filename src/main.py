# src/main.py
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

from auth import ensure_login
from catalog import fetch_product_list
from detail import fetch_mspp_for_products


def _export_catalog_snapshot(rows, brand: str):
    """Always drop a catalog snapshot so you can validate counts/columns."""
    try:
        import pandas as pd
    except ImportError:
        raise RuntimeError("pandas is required. Run: pip install -r requirements.txt")

    Path("data/exports").mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    csv_path = Path(f"data/exports/adi_{brand.lower()}_catalog_{ts}.csv")
    xls_path = Path(f"data/exports/adi_{brand.lower()}_catalog_{ts}.xlsx")
    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False)
    df.to_excel(xls_path, index=False)
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {xls_path}")


def _export_results(rows, brand: str):
    """Prefer export.py; fall back to catalog-style writer if not available."""
    try:
        from export import export_results
        export_results(rows, brand=brand)
    except Exception as e:
        print(f"[WARN] export.py not used ({e}). Writing generic export.")
        _export_catalog_snapshot(rows, brand=brand)


def _load_products_from_file(path_str: str):
    """Load prior catalog (xlsx/csv) and return list[dict] for PDP pass."""
    import pandas as pd
    p = Path(path_str)
    if not p.exists():
        raise FileNotFoundError(f"--from-file not found: {p}")

    if p.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(p)
    elif p.suffix.lower() == ".csv":
        df = pd.read_csv(p)
    else:
        raise ValueError("Unsupported file type. Use .xlsx or .csv")

    if "url" not in df.columns:
        raise ValueError("Input file must contain a 'url' column.")

    expected = [
        "brand","title","model","alt_model","url","series","megapixels",
        "form_factor","vandal","ir","msrp","msrp_raw"
    ]
    for col in expected:
        if col not in df.columns:
            df[col] = None

    rows = df.to_dict(orient="records")
    print(f"[FROM-FILE] Loaded {len(rows)} rows from {p}")
    return rows


def _parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--brand", required=True, help="Hanwha | Axis | Avigilon | all")
    p.add_argument("--headless", action="store_true", help="Run browser headless")
    p.add_argument("--keep-open", action="store_true",
                   help="Keep browser open after run (useful for manual login)")
    p.add_argument("--only-missing", action="store_true",
                   help="Only fetch MSRP for rows where msrp is empty/None")
    p.add_argument("--catalog-only", action="store_true",
                   help="Skip MSRP; export the catalog list only")
    p.add_argument("--from-file", help="Path to existing catalog (xlsx/csv) instead of re-scraping")
    p.add_argument("--pdp-only", action="store_true",
                   help="When using --from-file, skip writing a new catalog snapshot")
    p.add_argument("--limit", type=int, default=0,
                   help="Process only the first N items (useful for quick tests)")
    return p.parse_args()


def main():
    load_dotenv()
    args = _parse_args()
    Path("data").mkdir(parents=True, exist_ok=True)

    # launch browser & authenticated session
    p, ctx = ensure_login(headless=args.headless)

    try:
        # Route A: fresh catalog scrape
        if not args.from_file:
            products = fetch_product_list(ctx, brand=args.brand)

            if args.limit > 0:
                products = products[: args.limit]
                print(f"[MAIN] Limiting to first {args.limit} products.")

            _export_catalog_snapshot(
                [{**row, "msrp": row.get("msrp", None)} for row in products],
                brand=args.brand,
            )

            if args.catalog_only:
                print("[MAIN] Catalog-only run complete. Skipping MSRP phase.")
                return

        # Route B: reuse existing file
        else:
            products = _load_products_from_file(args.from_file)

            if args.limit > 0:
                products = products[: args.limit]
                print(f"[MAIN] Limiting to first {args.limit} products from file.")

            if not args.pdp_only:
                _export_catalog_snapshot(
                    [{**row, "msrp": row.get("msrp", None)} for row in products],
                    brand=args.brand,
                )

        # MSRP phase
        results = fetch_mspp_for_products(
            ctx,
            products,
            only_missing=args.only_missing,
        )
        _export_results(results, brand=args.brand)
        print(f"[MAIN] Done. Items: {len(results)}")

        if args.keep_open:
            print("[MAIN] Browser left open as requested (--keep-open).")
            input("Press Enter to close browser...")

    finally:
        if not args.keep_open:
            try:
                ctx.close()
            finally:
                p.stop()


if __name__ == "__main__":
    main()
