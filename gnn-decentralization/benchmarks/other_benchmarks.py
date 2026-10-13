# -*- coding: utf-8 -*-
"""other_benchmarks.py -- the other two benchmarks of Figure 2, with source and method.

1. Swedish banking: ECB Structural Financial Indicators, series
   SSI.A.SE.122C.H10.X.A1.Z0Z.Z (Herfindahl index of credit institutions' total
   assets, 0-1 scale), times 10,000 for the DOJ scale. Published value, not computed here.
2. Global card networks: 2022 purchase volume published in the Nilson Report,
   issue 1241 (May 2023): six global brands, USD 36.174 trillion in total, of which
   UnionPay 15.843, Visa 11.668, Mastercard 6.568, American Express 1.540 (USD tn).
   Lower bound of the HHI: the top four only; upper bound: the remaining share
   (JCB + Discover/Diners) treated as one firm.
The v1 figures for Canada 2,250, Sweden 2,400, LPMCL 3,500, Visa/Mastercard 5,150 and
FFIEC 935 had no checkable source and were removed or replaced by these computations.
"""
import json
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent


def sweden():
    """The raw CSV is archived in raw/ on first download and read from there afterwards
    (the API occasionally returns an empty table)."""
    import csv, io
    raw = HERE / "raw" / "ecb_ssi_SE_H10.csv"
    if not raw.exists():
        url = ("https://data-api.ecb.europa.eu/service/data/SSI/"
               "A.SE.122C.H10.X.A1.Z0Z.Z?format=csvdata&startPeriod=2020")
        text = requests.get(url, timeout=60).text
        raw.parent.mkdir(exist_ok=True)
        raw.write_text(text)
    out = {r["TIME_PERIOD"]: round(float(r["OBS_VALUE"]) * 10_000, 1)
           for r in csv.DictReader(io.StringIO(raw.read_text()))}
    if not out:
        raw.unlink()
        raise SystemExit("[X] ECB returned an empty table; nothing written, retry later")
    return out


def cards():
    total = 36.174
    top4 = {"UnionPay": 15.843, "Visa": 11.668, "Mastercard": 6.568, "American Express": 1.540}
    sh = {k: 100 * v / total for k, v in top4.items()}
    rest = 100 - sum(sh.values())
    lo = sum(s ** 2 for s in sh.values())
    return {"year": 2022, "source": "Nilson Report Issue 1241 (May 2023)",
            "shares_pct": {k: round(v, 2) for k, v in sh.items()},
            "residual_pct": round(rest, 2),
            "hhi_lower": round(lo, 1), "hhi_upper": round(lo + rest ** 2, 1),
            # denominator: the top four only (excluding JCB, Discover/Diners)
            "hhi_top4_only": round(sum((100 * v / sum(top4.values())) ** 2 for v in top4.values()), 1)}


if __name__ == "__main__":
    out = {"sweden_credit_institutions_assets_hhi": sweden(), "global_card_networks": cards()}
    (HERE / "other_benchmarks.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
