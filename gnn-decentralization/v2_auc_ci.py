# -*- coding: utf-8 -*-
"""v2_auc_ci.py -- node-bootstrap confidence intervals for the core-label AUC.

With only a few dozen positives, the standard deviation across seeds is not the
right uncertainty. This script:
  1. builds out-of-fold predictions with the same StratifiedKFold as 02_c1.py
     (5 folds, shuffled, seed=C.SEED); GraphSAGE uses the mean of ten seeds;
  2. resamples nodes B times and reports 95% percentile intervals for each AUC and
     for paired differences: GraphSAGE - seven structural features;
     centrality (summed edges) - centrality (overwritten edges, same node set);
  3. since the ten-seed mean is an ensemble of ten models while the hand-crafted
     features are one model, also reports the pooled AUC of each single-seed
     GraphSAGE and the interval of "single seed - structural features", plus the
     fold-averaged AUC of each input, to reconcile with Table 4 (02_c1.py).
Output: results/auc_ci.json.
"""

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

import common as cm
import config as C

B = 2_000
CV = StratifiedKFold(n_splits=C.CV_FOLDS, shuffle=C.CV_SHUFFLE, random_state=C.SEED)


def oof(X, y):
    X = StandardScaler().fit_transform(X.reshape(len(y), -1))
    p = np.zeros(len(y))
    for tr, te in CV.split(X, y):
        clf = LogisticRegression(max_iter=1000, class_weight="balanced").fit(X[tr], y[tr])
        p[te] = clf.predict_proba(X[te])[:, 1]
    return p


def fold_mean(X, y):
    """As in 02_c1.py: the mean of the fold AUCs."""
    X = StandardScaler().fit_transform(X.reshape(len(y), -1))
    a = []
    for tr, te in CV.split(X, y):
        clf = LogisticRegression(max_iter=1000, class_weight="balanced").fit(X[tr], y[tr])
        a.append(roc_auc_score(y[te], clf.predict_proba(X[te])[:, 1]))
    return float(np.mean(a))


def inputs(d):
    x, names = cm.prepare_gnn_input(d["feat"])
    return x, x[:, [names.index("betweenness"), names.index("pagerank")]]


def boot(y, preds: dict, pairs, seed=C.SEED):
    rng = np.random.default_rng(seed)
    n = len(y)
    res = {k: [] for k in preds}
    dif = {f"{a}-{b}": [] for a, b in pairs}
    for _ in range(B):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        a_ = {k: roc_auc_score(y[i], p[i]) for k, p in preds.items()}
        for k in preds:
            res[k].append(a_[k])
        for a, b in pairs:
            dif[f"{a}-{b}"].append(a_[a] - a_[b])
    q = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    return ({k: {"auc": round(float(roc_auc_score(y, p)), 4), "ci95": q(res[k])} for k, p in preds.items()},
            {f"{a}-{b}": {"diff": round(float(roc_auc_score(y, preds[a]) - roc_auc_score(y, preds[b])), 4),
                          "ci95": q(dif[f"{a}-{b}"])} for a, b in pairs})   # point estimate = full-sample difference, as in the tables


def main():
    out = {}
    for t in C.TOKENS:
        d = np.load(C.RESULTS / f"graph_{t}_1w.npz", allow_pickle=True)
        y = cm.is_core_mask(d["cat"]).astype(int)
        x, cent = inputs(d)
        embs = {s: np.load(C.RESULTS / f"emb_{t}_1w_s{s}.npy") for s in C.BROKER_CONSENSUS_SEEDS}
        single = {f"graphsage_s{s}": oof(e, y) for s, e in embs.items()}
        gnn = np.mean(list(single.values()), axis=0)
        preds = {"centrality": oof(cent, y), "structural": oof(x, y), "graphsage": gnn, **single}
        pairs = [("graphsage", "structural"), ("structural", "centrality")] + \
                [(k, "structural") for k in single]
        fm = {"centrality": fold_mean(cent, y), "structural": fold_mean(x, y),
              "graphsage_single_mean": float(np.mean([fold_mean(e, y) for e in embs.values()]))}
        dov = np.load(C.ROOT / "results_spec_overwrite" / f"graph_{t}_1w.npz", allow_pickle=True)
        assert list(dov["nodes"]) == list(d["nodes"]), "overwrite spec has a different node set; cannot pair"
        preds["centrality_overwrite"] = oof(inputs(dov)[1], y)
        pairs.append(("centrality", "centrality_overwrite"))
        aucs, diffs = boot(y, preds, pairs)
        sd = {k: diffs.pop(f"{k}-structural") for k in single}
        sa = {k: aucs.pop(k) for k in single}
        d_ = np.array([v["diff"] for v in sd.values()])
        out[t] = {"n_pos": int(y.sum()), "n": int(len(y)), "auc": aucs, "diff": diffs, "B": B,
                  "fold_mean_auc": {k: round(v, 4) for k, v in fm.items()},
                  "single_seed": {"auc": sa, "diff_vs_structural": sd,
                                  "auc_median": round(float(np.median([v["auc"] for v in sa.values()])), 4),
                                  "diff_median": round(float(np.median(d_)), 4),
                                  "diff_min": round(float(d_.min()), 4), "diff_max": round(float(d_.max()), 4),
                                  "n_ci_excludes_zero": int(sum(v["ci95"][0] > 0 for v in sd.values())),
                                  "n_seeds": len(sd)}}
        print(t, {k: v for k, v in out[t].items() if k != "single_seed"})
        print("   single seed", {k: v for k, v in out[t]["single_seed"].items() if k not in ("auc", "diff_vs_structural")})
    cm.save_json(out, "auc_ci.json")


if __name__ == "__main__":
    main()
