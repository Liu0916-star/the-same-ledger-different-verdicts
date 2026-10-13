# -*- coding: utf-8 -*-
"""v2_broker_balance_sens.py -- sensitivity of the broker criterion to its balance
condition (computation only; no new verification).

Recomputes the rank-ensemble score from the ten embeddings cached by 05 and varies
only the balance condition:
  median (main; must reproduce hidden_brokers_*.csv) / zero / dust (< 0.01 tokens)
Output: results/broker_balance_sens.json -- set size and overlap with the main set
for each condition, plus the subgraph's median balance and zero / dust shares.
"""
import importlib
import json

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

import common as cm
import config as C

R5 = importlib.import_module("05_c3_roles")


def main():
    out = {}
    for t in C.TOKENS:
        d = np.load(C.RESULTS / f"graph_{t}_1w.npz", allow_pickle=True)
        F = C.FEATURE_NAMES
        bal, cp, bet = (d["feat"][:, F.index(x)] for x in ("balance", "counterparties", "betweenness"))
        cat, nodes = d["cat"], np.array([str(x) for x in d["nodes"]])
        scores = []
        for e in R5._multi_seed_embs(t, "1w", d):
            scores.append(R5._brokers_from_emb(StandardScaler().fit_transform(e), bal, cp, bet, cat)[2])
        rank = R5._rank_ensemble(scores)
        main_set = set(pd.read_csv(C.RESULTS / f"hidden_brokers_{t}.csv")["address"])
        r = {"median_balance": float(np.median(bal)), "zero_share": float(np.mean(bal == 0)),
             "dust_share": float(np.mean(bal < C.DUST_FLOOR))}
        for rule in ("median", "zero", "dust"):
            _, strict = R5._apply_broker_rules(rank, bal, cp, bet, cat, bal_rule=rule)
            sel = set(nodes[strict])
            r[rule] = {"size": len(sel), "overlap_main": len(sel & main_set)}
        assert r["median"]["size"] == len(main_set) == r["median"]["overlap_main"], "main specification not reproduced"
        main_bal = bal[np.isin(nodes, list(main_set))]
        r["main_brokers_zero_balance"] = int((main_bal == 0).sum())
        out[t] = r
        print(t, json.dumps(r))
    cm.save_json(out, "broker_balance_sens.json")


if __name__ == "__main__":
    main()
