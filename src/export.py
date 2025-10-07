# export.py – Excel/CSV + basic delta
import pandas as pd
from pathlib import Path
from datetime import datetime

def export_results(rows, brand: str):
    Path('data/exports').mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    df = pd.DataFrame(rows)
    csv_path = Path(f'data/exports/adi_{brand.lower()}_msrp_{ts}.csv')
    xls_path = Path(f'data/exports/adi_{brand.lower()}_msrp_{ts}.xlsx')
    df.to_csv(csv_path, index=False)
    df.to_excel(xls_path, index=False)
    print(f'Wrote: {csv_path}')
    print(f'Wrote: {xls_path}')
