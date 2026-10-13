# -*- coding: utf-8 -*-
"""v2_airdrop_case.py -- the case study of Section 7: the phishing airdrop in LINK week 7
(uses the raw, uncleaned transfers).

Reads the uncleaned transfers (common.load_transfers_raw) and the verification
records. Output: results/airdrop_case.json -- scale (transfers, senders, receivers,
amount, concentration in time), the 38 archived contracts vs the 42 added by the
rule, and the effect of the airdrop on weekly statistics (same week with / without).
"""
import json

import pandas as pd

import common as cm
import config as C

VD = C.ROOT / "verification"


def week_stats(g):
    outf = g.groupby("from")["amt"].sum().values
    inf = g.groupby("to")["amt"].sum().values
    nodes = len(set(g["from"]) | set(g["to"]))
    return {"n_tx": len(g), "n_addr": nodes,
            "gini_out": cm.gini(outf), "gini_in": cm.gini(inf),
            "hhi_out": cm.hhi(outf), "hhi_in": cm.hhi(inf)}


def main():
    raw = cm.load_transfers_raw("LINK")
    base = raw[~(raw["from"].isin(C.BURN_ADDRS) | raw["to"].isin(C.BURN_ADDRS))]
    senders = set(pd.read_csv(VD / "airdrop_senders_LINK.csv")["address"])
    arch = json.load(open(VD / "eventstudy_w7_phishing_addrs.json"))
    c38 = {a.lower() for a in arch["script_contracts_each_10000txns"]}
    m = base["from"].isin(senders) & (base["amt"] > 0) & (base["amt"] < C.AIRDROP_MAX_AMT)
    ad = base[m]
    rc = ad.groupby("to").size()
    per_week = base.groupby("week").size()
    w7 = int(ad["week"].mode().iloc[0])
    days = ad["ts"].dt.date.value_counts(normalize=True)
    chk = pd.read_csv(VD / "airdrop_senders_LINK_outside_archive_checked.csv")
    clean_tx = cm.load_transfers("LINK")
    keep_ad = cm.clean_transfers(raw, airdrop=False)[0]
    out = {
        "week_index": w7 + 1,
        "week_tx_raw": int(per_week.loc[w7]),
        "median_week_tx_raw": float(per_week.median()),
        "week_ratio_to_median": float(per_week.loc[w7] / per_week.median()),
        "n_senders": len(senders), "n_archived_38_hit": len(senders & c38),
        "n_transfers": int(len(ad)),
        "n_transfers_archived_38": int(ad["from"].isin(c38).sum()),
        "n_transfers_other": int((~ad["from"].isin(c38)).sum()),
        "archived_per_contract_min": int(base[base["from"].isin(c38)].groupby("from").size().min()),
        "archived_per_contract_max": int(base[base["from"].isin(c38)].groupby("from").size().max()),
        "n_recipients": int(rc.size),
        "recipients_single_pct": float((rc == 1).mean()),
        "amount_counts": {str(k): int(v) for k, v in ad["amt"].round(6).value_counts().head(3).items()},
        "total_link": float(ad["amt"].sum()),
        "top2_days_share": float(days.head(2).sum()),
        "top2_days": [str(d) for d in days.head(2).index],
        "share_in_week": float((ad["week"] == w7).mean()),
        "others_checked": int(len(chk)),
        "others_suspicious": int(chk["etherscan_tag"].str.startswith("Suspicious").sum()),
        "others_deployers": int(chk["contract_creator"].nunique()),
        # differ only in the airdrop: both sides drop mint/burn and zero-value transfers as in the main spec
        "with_airdrop": week_stats(keep_ad[keep_ad["week"] == w7]),
        "without_airdrop": week_stats(clean_tx[clean_tx["week"] == w7]),
    }
    print(json.dumps(out, indent=1, default=str))
    cm.save_json(out, "airdrop_case.json")


if __name__ == "__main__":
    main()
