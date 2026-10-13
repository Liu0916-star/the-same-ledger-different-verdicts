# -*- coding: utf-8 -*-
"""us_bank_hhi.py -- national deposit HHI of U.S. commercial banking (replaces the
unsourced 935 of v1).

Data: FDIC Summary of Deposits (SOD), YEAR=2026 (as of 2026-06-30, the same date as
the balance snapshot). https://api.fdic.gov/banks/sod
Method: branch deposits DEPSUMBR summed by top holding company RSSDHCR (by
institution RSSDID where there is none); share = summed deposits / national total;
HHI = sum (100 s)^2. The national figure is an order-of-magnitude reference only:
merger review uses local banking markets, not the national one.
Output: benchmarks/us_bank_hhi.json and the raw download
benchmarks/raw/fdic_sod_<year>.csv.gz
"""
import json
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
YEARS = (2026, 2025, 2024, 2023)


def fetch(year: int) -> pd.DataFrame:
    raw = HERE / "raw" / f"fdic_sod_{year}.csv.gz"
    if raw.exists():
        return pd.read_csv(raw)
    rows, off = [], 0
    while True:
        r = requests.get("https://api.fdic.gov/banks/sod", timeout=120, params={
            "filters": f"YEAR:{year}", "fields": "YEAR,RSSDHCR,NAMEHCR,RSSDID,NAMEFULL,DEPSUMBR",
            "limit": 10000, "offset": off}).json()
        rows += [d["data"] for d in r["data"]]
        off += 10000
        if off >= r["meta"]["total"]:
            break
    df = pd.DataFrame(rows)
    raw.parent.mkdir(exist_ok=True)
    df.to_csv(raw, index=False, compression="gzip")
    return df


def main():
    out = {}
    for y in YEARS:
        df = fetch(y)
        key = df["RSSDHCR"].where(df["RSSDHCR"].fillna(0) > 0, df["RSSDID"])
        name = df["NAMEHCR"].where(df["RSSDHCR"].fillna(0) > 0, df["NAMEFULL"])
        g = df.assign(k=key, n=name).groupby("k").agg(dep=("DEPSUMBR", "sum"), name=("n", "first"))
        s = g["dep"] / g["dep"].sum()
        hhi = float(((100 * s) ** 2).sum())
        top = g.assign(s=s).sort_values("s", ascending=False).head(5)
        out[y] = {"hhi": round(hhi, 1), "n_branches": len(df), "n_holders": len(g),
                  "total_deposits_thousand_usd": int(g["dep"].sum()),
                  "top5": [(r_name, round(float(r_s) * 100, 2))
                           for r_name, r_s in zip(top["name"], top["s"])]}
        print(y, out[y]["hhi"], out[y]["n_holders"], out[y]["top5"][:3])
    (HERE / "us_bank_hhi.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
