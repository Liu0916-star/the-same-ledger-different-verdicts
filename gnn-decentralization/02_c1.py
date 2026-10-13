# -*- coding: utf-8 -*-
"""
02_c1.py -- evaluating the structural score (Table 4 and Appendix A)

Compares the inputs that can score "structural position", in one run:
  - predicting the top 5% of balances (internal target)
  - predicting is_core (external label, no leakage)   <- Table 4
  - neighbourhood purity and enrichment
  - GraphSAGE over several seeds (config.SEEDS_BY_SCALE): mean ± sd
  - ablation: GraphSAGE with constant input (structure only)
  - node2vec baseline over five seeds (10^4 scale only)

Reads results/graph_{TOKEN}_{SCALE}.npz from 01_build_graph.py.

Two methodological details:
  1. no leakage: balance is dropped first, then the remaining 7 features get
     log1p + z-score (common.prepare_gnn_input)
  2. cross-validation is shuffled: positives are clustered in the node order,
     and unshuffled folds push the AUC systematically below 0.5

Usage: python 02_c1.py [TOKEN] [SCALE]
"""
import sys

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

import config as C
import common as cm

SCRIPT = "02_c1"
DEV = torch.device(C.TRAIN_DEVICE)
CV = StratifiedKFold(n_splits=C.CV_FOLDS, shuffle=C.CV_SHUFFLE,
                     random_state=C.SEED)


def train_emb(x, ei, seed):
    return cm.train_sage(x, ei.cpu(), seed)


def auc(X, y):
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    Xs = StandardScaler().fit_transform(X)
    s = cross_val_score(LogisticRegression(max_iter=1000,
                                           class_weight="balanced"),
                        Xs, y, cv=CV, scoring="roc_auc")
    return float(s.mean()), float(s.std())


def purity(emb, y, k=None):
    """Neighbourhood purity: share of positives among each positive's k nearest
    neighbours. Computed in blocks to bound memory."""
    k = k or C.PURITY_K
    z = torch.tensor(emb, dtype=torch.float, device=DEV)
    z = z / (z.norm(dim=1, keepdim=True) + 1e-9)
    yt = torch.tensor(y, dtype=torch.float, device=DEV)
    idx = np.flatnonzero(y)
    # the similarity block is B x N; at 6.4e5 nodes B=512 needs ~1.3 GB, so B adapts to N
    B = max(16, min(512, int(2e7 // max(z.shape[0], 1))))
    tot = 0.0
    for i in range(0, len(idx), B):
        sub = torch.tensor(idx[i:i + B], device=DEV)
        sim = z[sub] @ z.T
        sim[torch.arange(len(sub), device=DEV), sub] = -2
        nb = sim.topk(k, dim=1).indices
        tot += yt[nb].mean(1).sum().item()
    return tot / max(len(idx), 1)


def run(token, scale):
    cm.banner(f"02 · C1 {token} / {scale}")
    p = C.RESULTS / f"graph_{token}_{scale}.npz"
    if not p.exists():
        print(f"  [X] missing {p.name}; run 01_build_graph.py {token} {scale} first")
        return
    d = np.load(p, allow_pickle=True)
    feat, cat = d["feat"], d["cat"]
    ei = torch.tensor(d["edge_index"], dtype=torch.long).to(DEV)

    x, names = cm.prepare_gnn_input(feat)
    y_core = cm.is_core_mask(cat).astype(int)
    bi = C.FEATURE_NAMES.index("balance")
    y_bal = (feat[:, bi] >= np.percentile(feat[:, bi], 95)).astype(int)
    ci = [names.index("betweenness"), names.index("pagerank")]
    X_cent = x[:, ci]

    print(f"  nodes {len(y_core):,} | core anchors {y_core.sum()} | "
          f"GNN input {len(names)} dims | device={DEV}")
    print(f"  CV = StratifiedKFold({C.CV_FOLDS}, shuffle={C.CV_SHUFFLE}, "
          f"rs={C.SEED})")

    rec = {"token": token, "scale": scale, "n_nodes": int(len(y_core)),
           "seeds": list(C.SEEDS_BY_SCALE.get(scale, C.SEEDS)),
           "n_anchors": int(y_core.sum()), "gnn_input": names,
           "cv": f"StratifiedKFold({C.CV_FOLDS},shuffle={C.CV_SHUFFLE},"
                 f"seed={C.SEED})",
           "preprocessing": "drop balance from raw, THEN log1p+zscore on 7"}

    # ---------- baselines (no seed involved) ----------
    print("\n  [baselines] (no seed involved)")
    for tag, y in (("is_core", y_core), ("balance_top5pct", y_bal)):
        a_c, s_c = auc(X_cent, y)
        a_r, s_r = auc(x, y)
        rec[f"{tag}_centrality"] = {"auc": round(a_c, 4), "sd_fold": round(s_c, 4)}
        rec[f"{tag}_raw_struct"] = {"auc": round(a_r, 4), "sd_fold": round(s_r, 4)}
        print(f"    {tag:16} centrality {a_c:.4f}  raw-struct {a_r:.4f}")

    # ---------- GraphSAGE over seeds + ablation ----------
    seeds = C.SEEDS_BY_SCALE.get(scale, C.SEEDS)
    print(f"\n  [seeds] {list(seeds)}"
          + (f"   <- training at {scale} is expensive; config.SEEDS_BY_SCALE uses "
             f"{len(seeds)}" if len(seeds) < len(C.SEEDS) else ""))
    print(f"    {'seed':>6}{'GNN is_core':>13}{'GNN balance':>13}"
          f"{'no feat.':>10}{'enrich.':>9}")
    x_nofeat = np.ones((x.shape[0], 1))
    rows = []
    rnd = y_core.mean()
    for sd in seeds:
        emb = train_emb(x, ei, sd)
        if sd == C.SEED:
            # Save the main-seed embedding with a fingerprint (md5 of features and
            # edge list). Later scripts reuse a cached embedding only if the
            # fingerprint still matches the graph; if 01 is rerun with other
            # parameters they retrain instead of silently reading a stale file.
            import hashlib
            _h = hashlib.md5()
            _h.update(np.ascontiguousarray(d["feat"]).tobytes())
            _h.update(np.ascontiguousarray(d["edge_index"]).tobytes())
            _fp = _h.hexdigest()[:12]
            np.save(C.RESULTS / f"emb_{token}_{scale}.npy", emb)
            (C.RESULTS / f"emb_{token}_{scale}.fp").write_text(_fp)
        a_core, _ = auc(emb, y_core)
        a_bal, _ = auc(emb, y_bal)
        pu = purity(emb, y_core)
        enr = pu / rnd if rnd else np.nan
        a_nof, _ = auc(train_emb(x_nofeat, ei, sd), y_core)
        rows.append((sd, a_core, a_bal, a_nof, pu, enr))
        print(f"    {sd:>6}{a_core:>13.4f}{a_bal:>13.4f}"
              f"{a_nof:>10.4f}{enr:>8.1f}x")

    arr = np.array([[r[1], r[2], r[3], r[4], r[5]] for r in rows])
    keys = ["gnn_is_core", "gnn_balance", "gnn_nofeat_is_core",
            "purity", "enrichment"]
    for j, kk in enumerate(keys):
        rec[kk] = {"mean": round(float(arr[:, j].mean()), 4),
                   "sd_seed": round(float(arr[:, j].std(ddof=1)), 4),
                   "min": round(float(arr[:, j].min()), 4),
                   "max": round(float(arr[:, j].max()), 4)}

    # ---------- enrichment of the centrality baseline ----------
    pu_c = purity(X_cent, y_core)
    pu_r = purity(x, y_core)
    rec["enrichment_centrality"] = round(pu_c / rnd, 1) if rnd else None
    rec["enrichment_raw_struct"] = round(pu_r / rnd, 1) if rnd else None
    rec["purity_centrality"] = round(float(pu_c), 4)
    rec["purity_raw_struct"] = round(float(pu_r), 4)
    rec["random_baseline_purity"] = round(float(rnd), 5)

    # ---------- node2vec baseline over seeds ----------
    # Several seeds, as for GraphSAGE. With workers=1, a seeded run and a stable
    # hash function (common.stable_hash) node2vec is deterministic; the spread
    # across seeds is the uncertainty that matters.
    try:
        from node2vec import Node2Vec
        import networkx as nx
        if scale != "1w":
            raise ImportError    # node2vec is skipped at larger scales (random walks are slow)
        print(f"\n  [node2vec baseline] seeds {list(C.SEEDS_N2V)}")
        Gx = nx.DiGraph()
        Gx.add_edges_from(d["edge_index"].T.tolist())
        n2 = []
        for sd in C.SEEDS_N2V:
            cm.seed_everything(sd)
            n2v = Node2Vec(Gx, dimensions=C.EMB_DIM, walk_length=80,
                           num_walks=10, workers=1, quiet=True, seed=sd)
            mdl = n2v.fit(window=10, min_count=1, seed=sd, workers=1,
                          hashfxn=cm.stable_hash)
            e2 = np.array([mdl.wv[str(i)] if str(i) in mdl.wv
                           else np.zeros(C.EMB_DIM)
                           for i in range(len(y_core))])
            a2, _ = auc(e2, y_core)
            p2 = purity(e2, y_core)
            n2.append((a2, p2 / rnd if rnd else np.nan))
            print(f"    seed {sd}: AUC {a2:.4f}  enrichment {n2[-1][1]:.1f}x")
        n2a = np.array(n2)
        rec["node2vec_is_core"] = {
            "mean": round(float(n2a[:, 0].mean()), 4),
            "sd_seed": round(float(n2a[:, 0].std(ddof=1)), 4),
            "min": round(float(n2a[:, 0].min()), 4),
            "max": round(float(n2a[:, 0].max()), 4)}
        rec["node2vec_enrichment"] = {
            "mean": round(float(n2a[:, 1].mean()), 2),
            "sd_seed": round(float(n2a[:, 1].std(ddof=1)), 2)}
        print(f"    node2vec AUC {n2a[:, 0].mean():.4f} "
              f"± {n2a[:, 0].std(ddof=1):.4f}  |  enrichment "
              f"{n2a[:, 1].mean():.1f}x ± {n2a[:, 1].std(ddof=1):.1f}")

        # ---------- compared with GraphSAGE ----------
        g = arr[:, 0]
        d_mean = g.mean() - n2a[:, 0].mean()
        pooled = np.sqrt(g.var(ddof=1) / len(g)
                         + n2a[:, 0].var(ddof=1) / len(n2a))
        print(f"\n    [GNN vs node2vec] difference {d_mean:+.4f}  "
              f"(pooled s.e. {pooled:.4f} → {d_mean / pooled:+.2f})")
        verdict = ("GNN significantly better" if d_mean / pooled > 2 else
                   "node2vec significantly better" if d_mean / pooled < -2 else
                   "no significant difference")
        print(f"    → {verdict}")
        print("    node2vec uses topology only; GraphSAGE also uses node features."
              " Both are learned representations;")
        print(f"      the contrast that matters is with hand-crafted centrality"
              f" ({rec['is_core_centrality']['auc']:.3f}).")
        rec["gnn_vs_node2vec"] = {"diff": round(float(d_mean), 4),
                                  "pooled_se": round(float(pooled), 4),
                                  "z": round(float(d_mean / pooled), 2),
                                  "verdict": verdict}
    except ImportError:
        msg = ("skipped at this scale (random walks are slow; compared at 10^4)" if scale != "1w"
               else "not installed, skipped (pip install node2vec)")
        print(f"\n  [node2vec] {msg}")

    # ---------- summary ----------
    cm.banner(f"{token}-{scale} summary", "-")
    print(f"  centrality            {rec['is_core_centrality']['auc']:.3f}")
    print(f"  raw structural        {rec['is_core_raw_struct']['auc']:.3f}")
    print(f"  GNN                   {rec['gnn_is_core']['mean']:.3f} "
          f"± {rec['gnn_is_core']['sd_seed']:.3f}  (across seeds)")
    print(f"  GNN (no features)     {rec['gnn_nofeat_is_core']['mean']:.3f} "
          f"± {rec['gnn_nofeat_is_core']['sd_seed']:.3f}")
    if isinstance(rec.get("node2vec_is_core"), dict):
        print(f"  node2vec              "
              f"{rec['node2vec_is_core']['mean']:.3f} "
              f"± {rec['node2vec_is_core']['sd_seed']:.3f}  (across seeds)")
    # enrichment = purity / random baseline, and the baseline shrinks with scale;
    # reporting enrichment alone would suggest that larger graphs do better while
    # absolute purity actually falls, so both are reported.
    print(f"\n  {'method':<14}{'purity':>10}{'enrichment':>11}")
    print(f"  {'random':<14}{rec['random_baseline_purity']:>10.5f}"
          f"{'1.0x':>11}")
    print(f"  {'centrality':<14}{rec['purity_centrality']:>10.4f}"
          f"{rec['enrichment_centrality']:>10.1f}x")
    print(f"  {'raw structural':<14}{rec['purity_raw_struct']:>10.4f}"
          f"{rec['enrichment_raw_struct']:>10.1f}x")
    print(f"  {'GNN':<14}{rec['purity']['mean']:>10.4f}"
          f"{rec['enrichment']['mean']:>10.1f}x")
    if "node2vec_enrichment" in rec:
        n2p = rec["node2vec_enrichment"]["mean"] * rec["random_baseline_purity"]
        print(f"  {'node2vec':<14}{n2p:>10.4f}"
              f"{rec['node2vec_enrichment']['mean']:>10.1f}x")
    ratio = rec["enrichment"]["mean"] / max(rec["enrichment_raw_struct"], 1e-9)
    print(f"  → GNN / structural purity ratio {ratio:.2f}x"
          " (independent of the random baseline, comparable across scales)")
    print("\n  the ± here is the standard deviation across seeds, not across"
          " folds")

    cm.save_json(rec, f"c1_{token}_{scale}.json")
    for kk in keys:
        cm.log_metric(SCRIPT, token, f"{scale}_{kk}", rec[kk]["mean"],
                      f"sd_seed={rec[kk]['sd_seed']}")
    return rec


def main():
    a = sys.argv[1:]
    if a:
        run(a[0], a[1] if len(a) > 1 else "1w")
    else:
        for t in C.TOKENS:
            run(t, "1w")
    cm.banner("Done. Next: python 03_c2_weekly.py")


if __name__ == "__main__":
    main()
