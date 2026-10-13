# -*- coding: utf-8 -*-
"""v2_broker_deploy.py -- deployment block of each broker contract, against the date
the label compilation was last scraped.

The Ethereum labels of brianleect/etherscan-labels were last scraped on 2023-06-18
(repository README), so "not in the compilation" may only mean "deployed after the
scrape". For each broker address we binary-search the first block at which
eth_getCode is non-empty; externally owned accounts (no code) are listed separately.
Output: results/broker_deploy.json.
"""

import pandas as pd

import chain_rpc as R
import common as cm
import config as C

LABEL_LAST_SCRAPE = "2023-06-18"


def block_at(ts: int) -> int:
    lo, hi = 1, C.SNAPSHOT_BLOCK
    while lo < hi:
        m = (lo + hi) // 2
        if R.block_timestamp(m) < ts:
            lo = m + 1
        else:
            hi = m
    return lo


def has_code(a, b):
    return len(R._post("eth_getCode", [a, hex(b)])) > 2


def deploy_block(a):
    if not has_code(a, C.SNAPSHOT_BLOCK):
        return None
    lo, hi = 1, C.SNAPSHOT_BLOCK
    while lo < hi:
        m = (lo + hi) // 2
        if has_code(a, m):
            hi = m
        else:
            lo = m + 1
    return lo


def main():
    cut = block_at(int(pd.Timestamp(LABEL_LAST_SCRAPE, tz="UTC").timestamp()))
    addrs = sorted(set(pd.read_csv(C.RESULTS / "hidden_brokers_LINK.csv")["address"])
                   | set(pd.read_csv(C.RESULTS / "hidden_brokers_UNI.csv")["address"]))
    rows = []
    for a in addrs:
        b = deploy_block(a)
        rows.append({"address": a, "deploy_block": b,
                     "deploy_time": None if b is None else
                     str(pd.Timestamp(R.block_timestamp(b), unit="s", tz="UTC")),
                     "after_label_scrape": None if b is None else b >= cut})
        print(rows[-1], flush=True)
    df = pd.DataFrame(rows)
    out = {"label_last_scrape": LABEL_LAST_SCRAPE, "cut_block": cut, "n": len(df),
           "n_contracts": int(df["deploy_block"].notna().sum()),
           "n_after": int((df["after_label_scrape"] == True).sum()),
           "rows": rows}
    cm.save_json(out, "broker_deploy.json")
    print({k: v for k, v in out.items() if k != "rows"})


if __name__ == "__main__":
    main()
