# -*- coding: utf-8 -*-
"""
05_c3_roles.py -- role typology and hidden brokers (Section 5, Appendix A)

Derived from cells 41 (brokers) and 42 (cluster naming) of v16. Cell 40 was
overwritten dead code and is dropped: hidden_brokers.csv has the column
core_score, a name used only in cell 41 (cell 40 used struct_score, a different
definition).

Five changes from v16:

  1. Ensemble over seeds (config.BROKER_CONSENSUS_SEEDS). The main set is the
     rank ensemble (percentile ranks averaged over seeds, then one top-1% cut);
     the vote consensus (>= 50% of seeds) is reported beside it as a stricter
     subset and a stability diagnostic.

  2. Degenerate brokers filtered (config.BROKER_MIN_COUNTERPARTIES). The v16
     definition admitted nodes with counterparties = 1 and betweenness = 0, two
     pairs of them vanity twins; zero betweenness contradicts "sitting on
     critical paths".

  3. The centrality baseline is a top-K of the same size. Comparing the
     ensemble-tightened set with a fixed-percentile betweenness set would compare
     sets of different sizes; now both come from the same pool with the same
     size, and only the overlap is reported.

  4. Clusters get flags instead of a composite name; the wealth-power relation is
     reported as Spearman correlations rather than a binary verdict. (v16 cell 42
     allowed several names per cluster, which could not go into a table.)

  5. node2vec runs through the same pipeline and ensemble, with the label
     composition of each top 1%, as a contrast.

core_score is an in-sample fit (no cross-validation), used only to select
descriptively; the predictive evidence is the cross-validated AUC of 02_c1.

Embedding caches carry a fingerprint (md5 of features and edge list). If
01_build_graph is rerun with other parameters, the fingerprint changes and the
embeddings are retrained instead of being read silently.

Usage:
    python 05_c3_roles.py            # LINK + UNI
    python 05_c3_roles.py LINK       # one token
    python 05_c3_roles.py --fresh    # ignore every embedding cache and retrain
"""
import sys

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import config as C
import common as cm

SCRIPT = "05_c3_roles"


def _fingerprint(d) -> str:
    """Fingerprint of the graph data (features + edge list), to check that a cached
    embedding still matches."""
    import hashlib
    h = hashlib.md5()
    h.update(np.ascontiguousarray(d["feat"]).tobytes())
    h.update(np.ascontiguousarray(d["edge_index"]).tobytes())
    return h.hexdigest()[:12]


def _cache_ok(cache_path, fp) -> bool:
    """A cache is valid only with a fingerprint matching the current graph.

    This is a hard requirement: if 01_build_graph were rerun with other parameters
    and 05 silently read old embeddings, results would disagree without any
    error -- the hardest kind of bug to find.
    """
    if "--fresh" in sys.argv:
        return False
    meta = cache_path.with_suffix(".fp")
    return (cache_path.exists() and meta.exists()
            and meta.read_text().strip() == fp)


def _write_cache(cache_path, arr, fp):
    np.save(cache_path, arr)
    cache_path.with_suffix(".fp").write_text(fp)


def _train_gnn(d, seed):
    """Train one GraphSAGE embedding (common.train_sage, the same code as 02)."""
    x, _ = cm.prepare_gnn_input(d["feat"])
    return cm.train_sage(x, d["edge_index"], seed)


def _multi_seed_embs(token, scale, d):
    """Train or reuse one embedding per seed in config.BROKER_CONSENSUS_SEEDS,
    with fingerprint check."""
    fp = _fingerprint(d)
    out = []
    for sd in C.BROKER_CONSENSUS_SEEDS:
        cache = C.RESULTS / f"emb_{token}_{scale}_s{sd}.npy"
        if _cache_ok(cache, fp):
            out.append(np.load(cache))
            continue
        print(f"    training seed {sd} ...", flush=True)
        e = _train_gnn(d, sd)
        _write_cache(cache, e, fp)
        out.append(e)
    return out


def _brokers_from_emb(embs, bal, cp, bet, cat):
    """Select hidden brokers from a (standardised) embedding, by the paper's definition.

    Definition: top 1% of the is_core classifier probability & balance <= median &
    unlabelled; plus the lower bounds counterparties >= BROKER_MIN_COUNTERPARTIES and
    betweenness > 0.

    core_score is an in-sample fit (no cross-validation), used only to select
    descriptively; the predictive evidence is the cross-validated AUC of 02_c1.
    Returns (base_mask, strict_mask, score).
    """
    y = cm.is_core_mask(cat).astype(int)
    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(embs, y)
    score = clf.predict_proba(embs)[:, 1]
    return _apply_broker_rules(score, bal, cp, bet, cat) + (score,)


def _apply_broker_rules(score, bal, cp, bet, cat, bal_rule="median"):
    """Apply the broker definition to any score vector. Returns (base, strict).

    bal_rule: main "median" (balance <= subgraph median); sensitivity "zero"
    (exactly zero) and "dust" (balance < config.DUST_FLOOR, the 0.01-token floor).
    """
    thr = np.percentile(score, C.BROKER_PROB_PCT)
    bal_ok = {"median": bal <= np.median(bal), "zero": bal == 0,
              "dust": bal < C.DUST_FLOOR}[bal_rule]
    base = (score >= thr) & bal_ok & (cat == "Unlabeled")
    strict = base.copy()
    if C.BROKER_MIN_COUNTERPARTIES:
        strict &= cp >= C.BROKER_MIN_COUNTERPARTIES
    if C.BROKER_REQUIRE_POSITIVE_BETWEENNESS:
        strict &= bet > 0
    return base, strict


def _rank_ensemble(scores_all):
    """Average the percentile ranks of each seed's scores -- a scale-free standard ensemble."""
    from scipy.stats import rankdata
    n = len(scores_all[0])
    return np.mean([rankdata(s) / n for s in scores_all], axis=0)


def _node2vec_emb(token, scale, d, n_nodes, seed=None):
    """node2vec embedding (unweighted topology only), cached with fingerprint;
    runs only if node2vec is installed."""
    seed = C.SEED if seed is None else seed
    cache = C.RESULTS / f"emb_n2v_{token}_{scale}_s{seed}.npy"
    fp = _fingerprint(d)
    if _cache_ok(cache, fp):
        print(f"  [cache] reusing {cache.name} (fingerprint {fp} matches)")
        return np.load(cache)
    try:
        from node2vec import Node2Vec
        import networkx as nx
    except ImportError:
        return None
    print(f"    [node2vec] training seed {seed} ...", flush=True)
    Gx = nx.DiGraph()
    Gx.add_edges_from(d["edge_index"].T.tolist())
    cm.seed_everything(seed)
    n2v = Node2Vec(Gx, dimensions=C.EMB_DIM, walk_length=80, num_walks=10,
                   workers=1, quiet=True, seed=seed)
    mdl = n2v.fit(window=10, min_count=1, seed=seed, workers=1,
                  hashfxn=cm.stable_hash)
    e = np.array([mdl.wv[str(i)] if str(i) in mdl.wv else np.zeros(C.EMB_DIM)
                  for i in range(n_nodes)])
    _write_cache(cache, e, fp)
    return e


def run(token, scale="1w"):
    cm.banner(f"05 · roles and brokers {token} / {scale}")
    gp = C.RESULTS / f"graph_{token}_{scale}.npz"
    if not gp.exists():
        print(f"  [X] {gp.name} missing; run 01_build_graph.py first")
        return
    d = np.load(gp, allow_pickle=True)
    print(f"  [seeds] {len(C.BROKER_CONSENSUS_SEEDS)} seeds"
          " (cached embeddings are reused)")
    embs_all = _multi_seed_embs(token, scale, d)
    emb = embs_all[0]                       # main seed, used for clustering and display
    feat, nodes, cat = d["feat"], list(d["nodes"]), d["cat"]
    F_ = C.FEATURE_NAMES
    bal = feat[:, F_.index("balance")]
    cp = feat[:, F_.index("counterparties")]
    bet = feat[:, F_.index("betweenness")]
    deg = feat[:, F_.index("in_deg")] + feat[:, F_.index("out_deg")]
    y_core = cm.is_core_mask(cat).astype(int)
    print(f"  nodes {len(nodes):,} | core anchors {y_core.sum()}")

    # ---------- clustering ----------
    embs = StandardScaler().fit_transform(emb)
    km = KMeans(n_clusters=C.N_CLUSTERS, random_state=C.SEED, n_init=10)
    lab = km.fit_predict(embs)

    typ = {}
    core_rates = {c: y_core[lab == c].mean() for c in range(C.N_CLUSTERS)}
    med_bals = {c: float(np.median(bal[lab == c])) for c in range(C.N_CLUSTERS)}
    top_core = max(core_rates, key=core_rates.get)
    top_bal = max(med_bals, key=med_bals.get)

    print(f"\n  {'cl':>3}{'size':>7}{'core %':>9}{'med. bal.':>12}"
          f"{'med. cp':>10}{'med. betw.':>11}  flags")
    for c in range(C.N_CLUSTERS):
        m = lab == c
        flags = []
        if c == top_core:
            flags.append("core_infrastructure")
        if c == top_bal:
            flags.append("whale_hoarding")
        cats, cnt = np.unique(cat[m & (cat != "Unlabeled")], return_counts=True)
        typ[f"cluster_{c}"] = {
            "size": int(m.sum()),
            "core_rate": round(float(core_rates[c]), 4),
            "core_n": int(y_core[m].sum()),
            "med_balance": round(med_bals[c], 2),
            "med_counterparties": float(np.median(cp[m])),
            "med_betweenness": float(np.median(bet[m])),
            "med_deg": float(np.median(deg[m])),
            "flags": flags,          # no longer joined into one composite string
            "top_labels": dict(zip(cats.tolist(), cnt.tolist())),
        }
        print(f"  {c:>3}{int(m.sum()):>7,}{core_rates[c] * 100:>8.2f}%"
              f"{med_bals[c]:>12.2f}{np.median(cp[m]):>10.0f}"
              f"{np.median(bet[m]):>11.5f}  {','.join(flags) or '-'}")

    # ---------- wealth vs structural position: correlations, not a binary verdict ----------
    # v16 decided "core cluster == richest cluster" as a binary verdict, which flips
    # whenever two clusters have similar median balances. Here both cluster-level and
    # node-level correlations are given.
    from scipy.stats import spearmanr
    cr = np.array([core_rates[c] for c in range(C.N_CLUSTERS)])
    mb = np.array([med_bals[c] for c in range(C.N_CLUSTERS)])
    rho_c = float(spearmanr(cr, mb).statistic) if C.N_CLUSTERS > 2 else np.nan
    zero_frac = float((bal <= 0).mean())
    nz = bal > 0                      # on holders only; many tied zeros would dilute the correlation
    rho_n = float(spearmanr(bal, cp).statistic)
    rho_nb = float(spearmanr(bal, bet).statistic)
    rho_n_nz = float(spearmanr(bal[nz], cp[nz]).statistic) if nz.sum() > 10 else np.nan
    rho_nb_nz = float(spearmanr(bal[nz], bet[nz]).statistic) if nz.sum() > 10 else np.nan
    print("\n  [wealth vs structural position]")
    print(f"    zero-balance nodes {zero_frac * 100:.1f}%"
          f" ({int((~nz).sum()):,}/{len(bal):,}) -- ties dilute the all-node Spearman")
    print(f"    cluster-level Spearman(core rate, median balance) = {rho_c:+.3f}"
          f" ({C.N_CLUSTERS} clusters)")
    print(f"    {'':<4}{'all nodes':>12}{'holders only':>14}")
    print(f"    balance vs cp  {rho_n:>+11.3f}{rho_n_nz:>+14.3f}")
    print(f"    balance vs bet {rho_nb:>+11.3f}{rho_nb_nz:>+14.3f}"
          f"   (n={int(nz.sum()):,})")
    if max(abs(rho_n_nz), abs(rho_nb_nz)) < 0.15:
        print("    both near 0 -> at node level, wealth and structural position are")
        print("      nearly unrelated; this is how a Gini of 0.99 can coexist with")
        print("      unconcentrated routing.")
    if top_core == top_bal:
        print(f"    the highest core-rate and richest cluster are both {top_core} -> fused")
    else:
        print(f"    core cluster {top_core} differs from richest cluster {top_bal} -> separated"
              f" (core rate of the richest: {core_rates[top_bal] * 100:.1f}%)")
    print("    (v16 reported LINK separated and UNI fused; the v2 paper does not"
          " use this contrast,")
    print("      see Section 4.6 on why the v1 attribution was retracted)")
    wp = {"spearman_cluster_core_vs_balance": round(rho_c, 4),
          "spearman_node_balance_vs_counterparties": round(rho_n, 4),
          "spearman_node_balance_vs_betweenness": round(rho_nb, 4),
          "spearman_nonzero_balance_vs_counterparties": round(rho_n_nz, 4),
          "spearman_nonzero_balance_vs_betweenness": round(rho_nb_nz, 4),
          "zero_balance_frac": round(zero_frac, 4),
          "n_nonzero": int(nz.sum()),
          "top_core_cluster": int(top_core), "top_balance_cluster": int(top_bal),
          "verdict": "fused" if top_core == top_bal else "separated"}

    # ---------- hidden brokers (ensemble over seeds) ----------
    # One seed is one draw of the representation, so brokers come from an ensemble
    # over seeds; selection frequency is reported as a stability measure.
    n_seed = len(embs_all)
    votes = np.zeros(len(nodes), dtype=int)
    votes_base = np.zeros(len(nodes), dtype=int)
    scores_all = []
    for e in embs_all:
        es = StandardScaler().fit_transform(e)
        b_, s_, sc_ = _brokers_from_emb(es, bal, cp, bet, cat)
        votes += s_.astype(int)
        votes_base += b_.astype(int)
        scores_all.append(sc_)
    score_sd = np.std(scores_all, axis=0)
    freq = votes / n_seed

    # ---- main: rank ensemble (average percentile ranks, then one top-1% cut) ----
    # The vote cuts the top 1% per seed and then counts, so nodes at the hard
    # threshold flip in and out; the rank ensemble averages the underlying signal
    # and jitters far less -- the standard ensemble.
    rank_score = _rank_ensemble(scores_all)
    base_r, strict_r = _apply_broker_rules(rank_score, bal, cp, bet, cat)
    vote_strict = freq >= C.BROKER_CONSENSUS_MIN_FRAC

    if C.BROKER_ENSEMBLE == "rank":
        base, strict, score = base_r, strict_r, rank_score
    else:
        base = (votes_base / n_seed) >= C.BROKER_CONSENSUS_MIN_FRAC
        strict, score = vote_strict, np.mean(scores_all, axis=0)
    core_set = freq >= C.BROKER_CORE_SET_FRAC
    dropped = int(base.sum() - (base & strict).sum())

    print(f"\n  [hidden brokers · ensemble over {n_seed} seeds]")
    print(f"    main = {C.BROKER_ENSEMBLE}"
          f" ({'rank ensemble' if C.BROKER_ENSEMBLE == 'rank' else 'vote consensus'})")
    print(f"    {'specification':<30}{'nodes':>8}")
    print(f"    {'rank ensemble (one top-1% cut)':<30}"
          f"{int(strict_r.sum()):>8}")
    print(f"    {'vote >=50% of seeds':<30}{int(vote_strict.sum()):>8}")
    print(f"    {'both':<30}"
          f"{int((strict_r & vote_strict).sum()):>8}")
    print(f"    {'mean per seed':<30}{votes.sum() / n_seed:>8.1f}")
    print(f"\n    [stability] selection frequency"
          f" ({int((votes > 0).sum())} nodes ever selected)")
    print(f"    {'threshold':<26}{'nodes':>8}")
    for thr, nm in ((1.0, f"all {n_seed}/{n_seed} seeds"),
                    (C.BROKER_CORE_SET_FRAC,
                     f">={C.BROKER_CORE_SET_FRAC:.0%} seeds (high confidence)"),
                    (C.BROKER_CONSENSUS_MIN_FRAC,
                     f">={C.BROKER_CONSENSUS_MIN_FRAC:.0%} seeds"),
                    (0.1, ">=10% seeds (incl. occasional)")):
        print(f"    {nm:<26}{int((freq >= thr).sum()):>8}")
    hist = {k: int((votes == k).sum()) for k in range(1, n_seed + 1)}
    print("    histogram: " +
          " ".join(f"{k}:{v}" for k, v in hist.items() if v))
    churn = int(((votes >= 1) & (votes <= 2)).sum())
    print(f"    selected by only 1-2 seeds: {churn}"
          f" ({churn / max(int((votes > 0).sum()), 1):.0%} of those ever selected)")
    print("    a hard top-1% cut makes boundary nodes flip; this is inherent to the")
    print("      definition, so the ensemble set and this distribution are reported.")
    print(f"    reproducibility: the ensemble is deterministic given the {n_seed} embeddings,")
    print("      and training is deterministic on CPU; the embeddings and their .fp")
    print("      fingerprints are archived in results/.")

    # degenerate nodes removed by the lower bounds
    deg_mask = base & ~strict
    if deg_mask.sum():
        print(f"    degenerate nodes removed by the lower bounds: {int(deg_mask.sum())}"
              f" (counterparties < {C.BROKER_MIN_COUNTERPARTIES} or betweenness = 0):")
        for i in np.flatnonzero(deg_mask)[:6]:
            print(f"      {nodes[i]}  cp={int(cp[i])} betweenness={bet[i]:.6f} "
                  f"frequency={freq[i]:.0%}")

    bidx = np.flatnonzero(strict)
    brokers = pd.DataFrame({
        "rank": range(1, len(bidx) + 1),
        "address": [nodes[i] for i in bidx],
        "ensemble_score": np.round(score[bidx], 4),
        "seed_frequency": np.round(freq[bidx], 2),
        "score_sd_across_seeds": np.round(score_sd[bidx], 4),
        "in_vote_consensus": vote_strict[bidx],
        "high_confidence": core_set[bidx],
        "balance": bal[bidx], "counterparties": cp[bidx].astype(int),
        "betweenness": np.round(bet[bidx], 6), "cluster": lab[bidx],
    }).sort_values(["ensemble_score", "seed_frequency"],
                   ascending=[False, False])
    brokers["rank"] = range(1, len(brokers) + 1)

    # ---- betweenness baseline (top-K of the same size) ----
    # The GNN set is tightened by the ensemble; a fixed betweenness percentile would
    # give a set of a different size, so a top-K of the same size is taken.
    elig = (bal <= np.median(bal)) & (cat == "Unlabeled")
    if C.BROKER_MIN_COUNTERPARTIES:
        elig &= cp >= C.BROKER_MIN_COUNTERPARTIES
    if C.BROKER_REQUIRE_POSITIVE_BETWEENNESS:
        elig &= bet > 0
    K = int(strict.sum())
    ei_ = np.flatnonzero(elig)
    topk = ei_[np.argsort(-bet[ei_])[:K]] if len(ei_) else np.array([], int)
    bet_def = np.zeros(len(nodes), bool)
    bet_def[topk] = True
    overlap = int((strict & bet_def).sum())
    print(f"\n    [centrality baseline · same size K={K}]")
    print(f"    GNN {K} | betweenness top-{K} (same pool) | overlap {overlap}")
    print(f"    → overlap {overlap / max(K, 1):.0%}"
          f" (with equal sizes each side has {K - overlap} the other lacks,"
          " so 'GNN finds N more' is meaningless)")
    if C.BROKER_SIZE_MATCHED_BASELINE:
        bthr = np.percentile(bet, C.BROKER_PROB_PCT)
        bet_pct = elig & (bet >= bthr)
        print(f"    [reference] a fixed-percentile betweenness set has "
              f"{int(bet_pct.sum())} nodes, a different size; not used")

    # ---------- node2vec contrast: what does GraphSAGE add? ----------
    # If node2vec, which classifies about as well, finds the same brokers, GraphSAGE
    # is not needed for the selection.
    n2e = _node2vec_emb(token, scale, d, len(nodes))
    n2v_stats = None
    if n2e is not None:
        # node2vec uses the same ensemble, otherwise the comparison is not like for like
        sc2 = []
        for sd in C.BROKER_CONSENSUS_SEEDS[:C.N2V_CONSENSUS_N]:
            e2 = _node2vec_emb(token, scale, d, len(nodes), seed=sd)
            if e2 is None:
                break
            _, _, s2 = _brokers_from_emb(StandardScaler().fit_transform(e2),
                                         bal, cp, bet, cat)
            sc2.append(s2)
        if not sc2:
            sc2 = [np.zeros(len(nodes))]
        r2 = _rank_ensemble(sc2)
        _, s_n2v = _apply_broker_rules(r2, bal, cp, bet, cat)
        print(f"    (node2vec uses the same ensemble: mean rank over {len(sc2)} seeds)")
        gset = set(np.flatnonzero(strict))
        nset = set(np.flatnonzero(s_n2v))
        inter = gset & nset
        jac = len(inter) / max(len(gset | nset), 1)
        print("\n  [GNN vs node2vec broker sets]")
        print(f"    GNN {len(gset)} | node2vec {len(nset)} | "
              f"both {len(inter)} | Jaccard {jac:.3f}")

        def prof(idx):
            idx = list(idx)
            if not idx:
                return (0, 0, 0)
            return (float(np.median(cp[idx])), float(np.median(bet[idx])),
                    float(np.median(deg[idx])))

        print(f"    {'set':<22}{'med. cp':>10}{'med. betw.':>12}{'med. deg':>9}")
        for nm, ix in (("GNN only", gset - nset), ("both", inter),
                       ("node2vec only", nset - gset)):
            a, b_, c_ = prof(ix)
            print(f"    {nm:<22}{a:>10.0f}{b_:>12.6f}{c_:>9.0f}  (n={len(ix)})")

        # ---- against verified identities (circular; see the note printed below) ----
        vp = C.ROOT / "verification" / "broker_identities.csv"
        if vp.exists():
            vb = pd.read_csv(vp)
            acol_ = [c for c in vb.columns if "addr" in c.lower()][0]
            icol_ = next((c for c in vb.columns
                          if c.lower() in ("verified_identity", "identity",
                                           "name", "label")), None)
            # only rows with an identity count as verified, or the hit rate is inflated to 100%
            vset = set()
            for i_, a_ in enumerate(vb[acol_]):
                v_ = vb[icol_].iloc[i_] if icol_ else "verified"
                if pd.isna(v_) or not str(v_).strip() \
                        or str(v_).strip().lower() == "nan":
                    continue
                vset.add(str(a_).strip().lower())
            # After verification every address of our set is in the table, so the
            # "hit rate" is 100% by construction and says nothing. What matters is the
            # share with a specific identity (a protocol), not a generic entry such as
            # Unlabelled or MEV Bot.
            GEN = ("unlabelled", "unlabeled", "unknown", "suspected", "mev",
                   "fake_phishing", "compromised")
            # run() has no ident (it is local to cross_token), so the set of specific
            # identities is rebuilt from the table here.
            spec = set()
            for _i2, _a2 in enumerate(vb[acol_]):
                _v2 = vb[icol_].iloc[_i2] if icol_ else ""
                if pd.isna(_v2) or not str(_v2).strip():
                    continue
                if str(_v2).strip().lower().startswith(GEN):
                    continue
                spec.add(str(_a2).strip().lower())
            ident = vset          # for the counts printed below

            def _hit(mask):
                ix = np.flatnonzero(mask)
                h = sum(1 for i in ix if nodes[i] in vset)
                sp = sum(1 for i in ix if nodes[i] in spec)
                n_ = len(ix)
                return h, sp, n_

            print("\n    [verification] the sets side by side")
            print(f"    {'set':<26}{'in table':>9}{'specific':>10}{'share':>8}")
            layers = [("GNN rank ensemble (main)", strict_r),
                      ("GNN vote >=50%", vote_strict),
                      ("GNN both (strictest)", strict_r & vote_strict),
                      ("node2vec rank ensemble", s_n2v)]
            hits = {}
            for nm, mk in layers:
                h, sp, n_ = _hit(mk)
                r_ = sp / n_ if n_ else float("nan")
                hits[nm] = {"in_table": h, "specific_identity": sp, "n": n_,
                            "specific_share": round(r_, 3)}
                print(f"    {nm:<26}{f'{h}/{n_}':>9}{sp:>10}{r_:>7.0%}")
            print("    'in table' is complete by construction after verification and"
                  " is not a quality measure;")
            print("      what matters is the share resolved to a protocol rather than "
                  "Unlabelled / MEV.")
            print(f"    [!] the table has {len(ident)} entries, {len(spec)} with a specific identity."
                  " They were verified after selection by the GNN definition,")
            print("      so the comparison is circular; the node2vec figures are indicative only.")
            n2v_stats = {"verification_by_layer": hits,
                         "n_verified_total": len(ident),
                         "n_specific_identity": len(spec)}

        # ---- label composition of each top 1% ----
        # If node2vec ranks labelled infrastructure first while GraphSAGE ranks
        # unlabelled high-throughput nodes first, the "unlabelled" filter leaves
        # fewer brokers on the node2vec side.
        def _top1_profile(sc):
            thr = np.percentile(sc, C.BROKER_PROB_PCT)
            m = sc >= thr
            n_ = int(m.sum())
            lab_frac = float((cat[m] != "Unlabeled").mean()) if n_ else np.nan
            core_frac = float(cm.is_core_mask(cat[m]).mean()) if n_ else np.nan
            return n_, lab_frac, core_frac

        g_n, g_lab, g_core = _top1_profile(score)
        n_n, n_lab, n_core = _top1_profile(r2)
        print("\n    [label composition of the top 1%]")
        print(f"    {'method':<20}{'top1%':>8}{'labelled':>12}{'core anchors':>14}")
        print(f"    {'GNN':<20}{g_n:>8}{g_lab:>11.0%}{g_core:>13.0%}")
        print(f"    {'node2vec':<20}{n_n:>8}{n_lab:>11.0%}{n_core:>13.0%}")
        if n_lab > g_lab:
            print(f"    → more labelled nodes in node2vec's top 1%"
                  f" ({n_lab:.0%} vs {g_lab:.0%}): it ranks known infrastructure first,")
            print("      so the 'unlabelled' filter leaves it fewer brokers;")
            print("      GraphSAGE ranks unknown high-throughput nodes higher.")
        n2v_stats = (n2v_stats or {}) | {
            "n_gnn": len(gset), "n_node2vec": len(nset),
            "overlap": len(inter), "jaccard": round(jac, 4),
            "top1_labeled_frac_gnn": round(g_lab, 4),
            "top1_labeled_frac_node2vec": round(n_lab, 4),
            "top1_core_frac_gnn": round(g_core, 4),
            "top1_core_frac_node2vec": round(n_core, 4)}
        if jac > 0.7:
            print("    → large overlap: GraphSAGE is not needed for the selection")
        else:
            print("    → clear difference: the two embeddings capture different"
                  " structural roles")

    cm.save_csv(brokers, f"hidden_brokers_{token}.csv")
    cm.save_json({"token": token, "scale": scale, "n_nodes": len(nodes),
                  "n_clusters": C.N_CLUSTERS, "typology": typ,
                  "wealth_power": wp,
                  "hidden_brokers": {
                      "consensus_seeds": list(C.BROKER_CONSENSUS_SEEDS),
                      "consensus_min_frac": C.BROKER_CONSENSUS_MIN_FRAC,
                      "per_seed_mean": round(float(votes.sum() / n_seed), 1),
                      "consensus_set": int(strict.sum()),
                      "high_confidence_set": int(core_set.sum()),
                      "unanimous_set": int((freq >= 1.0).sum()),
                      "freq_histogram": {f"{k}/{n_seed}":
                                         int((votes == k).sum())
                                         for k in range(1, n_seed + 1)},
                      "gnn_def_v16": int(base.sum()),
                      "gnn_def_filtered": int(strict.sum()),
                      "n_degenerate_dropped": dropped,
                      "betweenness_def_topk": int(bet_def.sum()),
                      "overlap_size_matched": overlap,
                      "ensemble": C.BROKER_ENSEMBLE,
                      "rank_ensemble_set": int(strict_r.sum()),
                      "vote_consensus_set": int(vote_strict.sum()),
                      "rank_vote_overlap": int((strict_r & vote_strict).sum()),
                      "churn_1_2_seeds": churn,
                      "definition": f"[{C.BROKER_ENSEMBLE} ensemble over "
                                    f"{len(C.BROKER_CONSENSUS_SEEDS)} seeds] "
                                    f"top{100 - C.BROKER_PROB_PCT}% & "
                                    "balance<=median & unlabeled & "
                                    "counterparties>="
                                    f"{C.BROKER_MIN_COUNTERPARTIES} & "
                                    "betweenness>0",
                      "caveat": "core_score is an in-sample fit, used only to select "
                                "descriptively; predictive evidence is the cross-validated AUC"},
                  "node2vec_contrast": n2v_stats},
                 f"c3_typology_{token}.json")
    cm.log_metric(SCRIPT, token, "n_brokers", int(strict.sum()),
                  f"v16={int(base.sum())}, dropped={dropped}")
    return brokers


def cross_token():
    """Brokers shared by the two ledgers."""
    ps = {t: C.RESULTS / f"hidden_brokers_{t}.csv" for t in C.TOKENS}
    if not all(p.exists() for p in ps.values()):
        return
    cm.banner("brokers shared by LINK and UNI")
    dfs = {t: pd.read_csv(p) for t, p in ps.items()}
    sets = {t: set(d["address"].str.lower()) for t, d in dfs.items()}
    a, b = C.TOKENS
    inter = sets[a] & sets[b]
    print(f"  {a} {len(sets[a])} | {b} {len(sets[b])} | shared {len(inter)}")
    for t, o in ((a, b), (b, a)):
        top10 = set(dfs[t].nlargest(10, "counterparties")["address"].str.lower())
        print(f"  of the 10 {t} brokers with most counterparties, {len(top10 & sets[o])} are also in {o}")

    # Look up manually verified identities, not the label snapshot: the broker
    # definition already requires cat == "Unlabeled", so the snapshot would find
    # nothing by construction. Known aggregators were recognised only through
    # manual verification on Etherscan.
    vp = C.ROOT / "verification" / "broker_identities.csv"
    ident, n_id = {}, 0
    if vp.exists():
        vb = pd.read_csv(vp)
        vb.columns = [c.strip().lstrip("\ufeff") for c in vb.columns]
        acol = next(c for c in vb.columns if "addr" in c.lower())
        icol = next((c for c in vb.columns
                     if c.lower() in ("verified_identity", "identity",
                                      "name", "label")), None)
        # empty or nan does not count as verified: unfilled template rows would
        # otherwise inflate the hit rate to 100%
        ident = {}
        # the loop variables must not be a / b / v: a, b = C.TOKENS outside, and
        # shadowing would turn sets[a] into sets[<address>] and raise KeyError
        for _i, _addr in enumerate(vb[acol]):
            _v = vb[icol].iloc[_i] if icol else "verified"
            if pd.isna(_v) or not str(_v).strip() \
                    or str(_v).strip().lower() == "nan":
                continue
            ident[str(_addr).strip().lower()] = str(_v).strip()
        n_blank = len(vb) - len(ident)
        if n_blank:
            print(f"\n  [!] {n_blank} of {len(vb)} rows in the verification table have no identity"
                  " and are excluded")
        n_id = len(ident)
        print(f"\n  [verification table] {n_id} entries")
    else:
        print("\n  [!] verification/broker_identities.csv not found;"
              " identities skipped")

    GENERIC = ("unlabelled", "unlabeled", "unknown", "suspected", "mev",
               "fake_phishing", "compromised")
    named = {x: ident[x] for x in sorted(inter)
             if x in ident and not str(ident[x]).lower().startswith(GENERIC)}
    unnamed = sorted(inter - set(named))
    print(f"\n  of {len(inter)} shared brokers, {len(named)} have a specific verified identity, "
          f"{len(unnamed)} have none")
    if ident:
        print(f"    → {len(unnamed)} shared brokers have no verifiable identity;")
        print(f"      the other {len(named)} are verified, known aggregators")
        print("      (which ones: see the status of named aggregators below)")
    for x, nm in list(named.items())[:15]:
        print(f"      {x}  {nm}")

    # Locate each aggregator named in the text: after the lower bounds some may drop
    # out or remain on one ledger only, and the text must match the result files.
    # "0x protocol" rather than "0x": the latter matches any string with an address
    CLAIMED = {"1inch": "1inch", "uniswap x": "Uniswap X",
               "universal router": "Uniswap V4 Universal Router",
               "0x protocol": "0x Protocol", "0x proto": "0x Protocol",
               "bitget": "Bitget", "mayan": "Mayan", "metamask": "MetaMask",
               "li.fi": "LI.FI", "lifi": "LI.FI", "velora": "Velora",
               "augustus": "Velora", "okx": "OKX", "rizzolver": "Uniswap X"}
    loc = {}
    if ident:
        print("\n  [status of named aggregators]")
        print(f"    {'aggregator':<34}{'status':<12}address")
        loc = {}
        for addr, nm in ident.items():
            low = str(nm).lower()
            key = next((v for k, v in CLAIMED.items() if k in low), None)
            if not key:
                continue
            in_a, in_b = addr in sets[a], addr in sets[b]
            st = ("both" if in_a and in_b else f"{a} only" if in_a
                  else f"{b} only" if in_b else "neither")
            loc.setdefault(key, []).append((st, addr, nm))
        for key in sorted(loc):
            for st, addr, nm in loc[key]:
                print(f"    {nm[:32]:<34}{st:<12}{addr}")
        dropped_claims = [k for k, v in loc.items()
                          if all(x[0] == "neither" for x in v)]
        if dropped_claims:
            print(f"    [!] {dropped_claims} are in neither broker set under this specification;")
            print("        the list of named aggregators in the text must be revised")

    cm.save_json({"tokens": list(C.TOKENS), "n_shared": len(inter),
                  "shared": sorted(inter),
                  "claimed_aggregator_status": {
                      k: [{"status": x[0], "address": x[1], "identity": x[2]}
                          for x in v] for k, v in
                      loc.items()},
                  "shared_identified": named,
                  "n_identified": len(named),
                  "n_unidentified": len(unnamed),
                  "verification_table_size": n_id},
                 "c3_cross_token.json")


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    if "--fresh" in sys.argv:
        print("[--fresh] ignoring every embedding cache; retraining")
    for t in (a if a else C.TOKENS):
        run(t)
    cross_token()
    cm.banner("Done. Next: python 06_concentration.py")


if __name__ == "__main__":
    main()
