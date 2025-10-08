# export.py – Excel/CSV + optional suffix for catalog-only snapshots
import pandas as pd
from pathlib import Path
from datetime import datetime

def export_results(rows, brand: str, suffix: str = None):
    """
    Export scraped rows to CSV and XLSX in data/exports.
    suffix='catalog' will produce e.g. adi_hanwha_catalog_20251007_1605.*
    """
    Path('data/exports').mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    suf = f"_{suffix}" if suffix else "_msrp"

    csv_path = Path(f"data/exports/adi_{brand.lower()}{suf}_{ts}.csv")
    xls_path = Path(f"data/exports/adi_{brand.lower()}{suf}_{ts}.xlsx")

    df = pd.DataFrame(rows)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    df.to_excel(xls_path, index=False)

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {xls_path}")
