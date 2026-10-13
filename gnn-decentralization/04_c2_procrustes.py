# -*- coding: utf-8 -*-
"""
04_c2_procrustes.py -- weekly retraining + Procrustes alignment

Each weekly window gets its own graph and its own embedding; common anchor nodes
then align every window to a reference window by orthogonal Procrustes, so that
embeddings of different windows are comparable. Outputs: alignment residuals,
number of common anchors, the persistent elite set, drift between windows.

Changes from v16:
  1. edge weights are summed (common.build_graph)
  2. the aligned weekly embeddings are saved as c2_embeddings_{TOKEN}.npz

Usage: python 04_c2_procrustes.py [TOKEN]
"""
import sys

import numpy as np
import pandas as pd

import config as C
import common as cm

SCRIPT = "04_c2_procrustes"
ELITE_PCT = 95          # elite = PageRank top 5%


def _embed_window(g, seed=None):
    """Graph, features and embedding for one window. Returns {address: vector}."""
    seed = C.SEED if seed is None else seed
    G = cm.build_graph(g, top_n=None, largest_wcc=True, verbose=False)
    if G.number_of_nodes() < 50:
        return None, None
    feat, nodes = cm.node_features(G, {}, C.BETWEENNESS_K["c2_window"], seed)
    x, _ = cm.prepare_gnn_input(feat)
    idx = {a: i for i, a in enumerate(nodes)}
    ei = np.array([[idx[u], idx[v]] for u, v in G.edges()], dtype=np.int64).T
    emb = cm.train_sage(x, ei, seed)

    pr_i = C.FEATURE_NAMES.index("pagerank")
    return dict(zip(nodes, emb)), dict(zip(nodes, feat[:, pr_i]))


def procrustes(A, B):
    """Orthogonal R minimising ||A R - B||; A and B are anchor matrices in the same order."""
    U, _, Vt = np.linalg.svd(A.T @ B)
    return U @ Vt


def run(token):
    cm.banner(f"04 · C2 Procrustes {token}")
    tx = cm.load_transfers(token)
    outliers = cm.find_outlier_windows(tx)
    print(f"  weekly windows {tx['week'].nunique()} | outlier windows {outliers if outliers else 'none'}")

    emb_by_w, pr_by_w = {}, {}
    for w, g in tx.groupby("week", sort=True):
        n_nodes = len(set(g["from"]) | set(g["to"]))
        # an outlier window (with raw data, LINK week 7 has 550k nodes) is very slow to
        # train and may run out of memory; it reflects a one-off airdrop rather than
        # routing structure, so it is skipped and recorded in the result.
        # After cleaning there is no outlier window.
        if int(w) in outliers and n_nodes > C.PROCRUSTES_MAX_NODES:
            print(f"    week {int(w) + 1}: outlier window with {n_nodes:,} nodes "
                  f"> {C.PROCRUSTES_MAX_NODES:,}, skipped")
            continue
        if n_nodes > C.PROCRUSTES_MAX_NODES:
            print(f"    week {int(w) + 1}: [!] {n_nodes:,} nodes, training will be slow")
        e, pr = _embed_window(g)
        if e is None:
            print(f"    week {int(w) + 1}: too few nodes, skipped")
            continue
        emb_by_w[int(w)], pr_by_w[int(w)] = e, pr
        print(f"    week {int(w) + 1}: {len(e):,} nodes embedded", flush=True)

    ws = sorted(emb_by_w)
    ref = ws[0]
    aligned = {ref: emb_by_w[ref]}
    diag = []
    for w in ws[1:]:
        common_a = sorted(set(emb_by_w[ref]) & set(emb_by_w[w]))
        if len(common_a) < 50:
            print(f"    [!] week {w + 1}: only {len(common_a)} common anchors, alignment skipped")
            continue
        A = np.stack([emb_by_w[w][a] for a in common_a])
        B = np.stack([emb_by_w[ref][a] for a in common_a])
        before = float(np.linalg.norm(A - B))
        R = procrustes(A, B)
        after = float(np.linalg.norm(A @ R - B))
        aligned[w] = {a: v @ R for a, v in emb_by_w[w].items()}
        diag.append({"window": w + 1, "anchors": len(common_a),
                     "resid_before": round(before, 2),
                     "resid_after": round(after, 2),
                     "improved": after < before})

    dd = pd.DataFrame(diag)
    if dd.empty:
        print("\n  [X] no window was aligned; check the data or thresholds")
        return
    ok = int(dd["improved"].sum())
    print(f"\n  [alignment] {ok}/{len(dd)} succeeded | fewest common anchors "
          f"{int(dd['anchors'].min()):,}")

    # ---------- persistent elite ----------
    elite = {}
    for w in ws:
        v = np.array(list(pr_by_w[w].values()))
        thr = np.percentile(v, ELITE_PCT)
        elite[w] = {a for a, p in pr_by_w[w].items() if p >= thr}
    persistent = set.intersection(*elite.values()) if elite else set()
    print(f"  [elite] persistent across all windows: {len(persistent):,}"
          f" (PageRank top {100 - ELITE_PCT}% in each window)")

    # ---------- drift between windows ----------
    drift = []
    for i in range(len(ws) - 1):
        a, b = ws[i], ws[i + 1]
        if a not in aligned or b not in aligned:
            continue
        shared = persistent & set(aligned[a]) & set(aligned[b])
        if not shared:
            continue
        d = np.mean([np.linalg.norm(aligned[b][x] - aligned[a][x])
                     for x in shared])
        drift.append({"from": a + 1, "to": b + 1, "drift": round(float(d), 4),
                      "is_outlier": a in outliers or b in outliers})
    dfd = pd.DataFrame(drift)
    normal = dfd[~dfd["is_outlier"]]["drift"].mean() if len(dfd) else np.nan
    print(f"  [drift] mean over normal windows {normal:.4f}")
    if len(dfd) and dfd["is_outlier"].any():
        print(f"          including outlier windows {dfd[dfd['is_outlier']]['drift'].mean():.4f}")

    # ---------- save ----------
    np.savez_compressed(
        C.RESULTS / f"c2_embeddings_{token}.npz",
        **{f"w{w}_addr": np.array(sorted(aligned[w]), dtype=object)
           for w in aligned},
        **{f"w{w}_emb": np.stack([aligned[w][a] for a in sorted(aligned[w])])
           for w in aligned})
    print(f"    → c2_embeddings_{token}.npz")

    print("\n  reproducibility: CPU training with deterministic algorithms (common.train_sage);")
    print("    a rerun reproduces the persistent elite set and drift byte for byte.")

    cm.save_json({"token": token, "n_windows": len(ws),
                  "skipped_outlier_windows": [w + 1 for w in outliers],
                  "anomaly_windows": outliers, "ref_window": ref + 1,
                  "alignment_diag": diag,
                  "alignment_ok": f"{ok}/{len(dd)}",
                  "min_anchors": int(dd["anchors"].min()) if len(dd) else None,
                  "n_persistent_elite": len(persistent),
                  "elite_drift": drift,
                  "normal_drift_mean": round(float(normal), 4)},
                 f"c2_procrustes_{token}.json")
    cm.log_metric(SCRIPT, token, "persistent_elite", len(persistent))
    cm.log_metric(SCRIPT, token, "normal_drift_mean", round(float(normal), 4))


def main():
    a = sys.argv[1:]
    for t in (a if a else C.TOKENS):
        run(t)
    cm.banner("Done. Next: python 05_c3_roles.py")


if __name__ == "__main__":
    main()
