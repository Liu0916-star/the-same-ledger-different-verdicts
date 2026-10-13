# -*- coding: utf-8 -*-
"""v2_extra_stats.py -- supplementary statistics (reads graph files in results/, no retraining).

1. Spearman correlation of balance with structural position: n, rho, 95% CI
   (Fisher z and bootstrap), p; once for positive balances and once including zeros.
2. Size of the core cluster as a share of the 10^4 nodes.
3. Repeated ordered pairs (share of records).
Output: results/extra_stats.json
"""
import json

import numpy as np
from scipy import stats

import common as cm
import config as C

B = 2_000


def spearman_ci(x, y, seed=C.SEED):
    n = len(x)
    rho, p = stats.spearmanr(x, y)
    z, se = np.arctanh(rho), 1 / np.sqrt(n - 3)
    fisher = (float(np.tanh(z - 1.96 * se)), float(np.tanh(z + 1.96 * se)))
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(B):
        i = rng.integers(0, n, n)
        bs.append(stats.spearmanr(x[i], y[i])[0])
    boot = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
    return {"n": int(n), "rho": round(float(rho), 4), "p": float(p),
            "ci95_fisher": [round(v, 4) for v in fisher],
            "ci95_bootstrap": [round(v, 4) for v in boot]}


def main():
    out = {}
    names = C.FEATURE_NAMES
    for tok in C.TOKENS:
        d = np.load(C.RESULTS / f"graph_{tok}_1w.npz", allow_pickle=True)
        f = d["feat"]
        bal = f[:, names.index("balance")]
        cp = f[:, names.index("counterparties")]
        bet = f[:, names.index("betweenness")]
        pos = bal > 0
        r = {}
        for sub, m in (("positive_balance", pos), ("all_nodes", np.ones_like(pos))):
            r[sub] = {"balance_vs_counterparties": spearman_ci(bal[m], cp[m]),
                      "balance_vs_betweenness": spearman_ci(bal[m], bet[m])}
        ty = json.load(open(C.RESULTS / f"c3_typology_{tok}.json"))["typology"]
        core = max(ty.values(), key=lambda c: (c["core_rate"], c["size"]))
        r["core_cluster_share_of_graph"] = round(core["size"] / len(bal), 4)
        r["n_graph_nodes"] = int(len(bal))
        # repeated ordered pairs: all cleaned records, and records between nodes of the 10^4 subgraph
        tx = cm.load_transfers(tok)
        n_pairs = len(tx.groupby(["from", "to"]).size())
        nodes = set(str(x) for x in d["nodes"])
        sub = tx[tx["from"].isin(nodes) & tx["to"].isin(nodes)]
        r["repeat_share_full"] = 1 - n_pairs / len(tx)
        r["repeat_share_1w"] = 1 - len(sub.groupby(["from", "to"]).size()) / len(sub)
        out[tok] = r
        print(tok, json.dumps(r, indent=1))
    (C.RESULTS / "extra_stats.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
