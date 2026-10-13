# -*- coding: utf-8 -*-
"""
11_random_control.py -- matched control for the hidden-broker verification (Section 5.4)

Problem
-------
The share of hidden brokers that resolve to named routing protocols is measured
only on addresses the criterion selected. Acknowledging that circularity does
not rule it out: is the share higher than for comparable addresses it did not
select?

Design
------
Controls are drawn from the same eligibility pool as the brokers (unlabelled,
counterparties >= 5, betweenness > 0, balance <= median) but not selected by the
criterion; after manual verification the share of named routing protocols is
compared.

Two traps are avoided:

  1. Uniform sampling would make the test meaningless. The score is strongly
     correlated with counterparty count, so a uniform control has far lower
     degree than the brokers, and "brokers look like routers" would reduce to
     "high-degree nodes are routers". The main test therefore uses a control
     matched on counterparty count: each broker is paired with the non-broker
     whose count is closest. The uniform group is reported as well.

  2. Knowing which address is a broker could bias the verifier. The script
     writes a shuffled blind list without group labels; the groups are kept in a
     key file that must not be opened before verification is complete.

Usage
-----
    python 11_random_control.py sample          # draw the sample, write the blind list
    #  -> verify each address on Etherscan and fill in control_blind_v2.csv
    python 11_random_control.py score           # unblind, count, Fisher test

Output
------
    verification/control_blind_v2.csv   blind list (filled in by hand; v1's is in verification/v1/)
    verification/control_key_v2.csv     group key (do not open before verification)
    results/random_control.json         test results
"""
import sys

import importlib

import numpy as np
import pandas as pd

import config as C
import common as cm

SCRIPT = "11_random_control"
VDIR = C.ROOT / "verification"
# v2: the new sample goes to *_v2.csv; the v1 records (v1/control_blind.csv and
# broker_identities.csv) are read-only and reused as verified identities. The blind
# list holds only addresses without a record, plus calibration anchors.
BLIND = VDIR / "control_blind_v2.csv"
KEY = VDIR / "control_key_v2.csv"
KNOWN = VDIR / "known_identities_v2.csv"       # reused existing records (not in the blind list)
V1_RECORDS = (VDIR / "broker_identities.csv", VDIR / "v1" / "control_blind.csv")


def known_records() -> pd.DataFrame:
    """Addresses verified in v1 -> identity. The two files differ in columns; both
    become address / verified_identity / evidence."""
    out = []
    for p in V1_RECORDS:
        if not p.exists():          # a missing record file would silently change the known identities
            raise FileNotFoundError(p)
        d = pd.read_csv(p)
        d.columns = [c.strip().lstrip("\ufeff") for c in d.columns]
        d["address"] = d["address"].astype(str).str.strip().str.lower()
        d["source"] = p.name
        out.append(d[["address", "verified_identity", "evidence", "source"]])
    k = pd.concat(out).dropna(subset=["verified_identity"])
    return k.drop_duplicates("address", keep="first")

# ---------------------------------------------------------------- sample size
# Verification is manual, so the list size decides whether the experiment can be
# done at all. From the power calculation: a one-sided Fisher test detects 35% vs
# 5% at p < 0.05 with n = 20 per group (n = 15 is not enough); a control rate of
# 15% would need n = 40. n = 20 is fixed in advance and the result is reported as
# it is; no samples are added after looking at the result.
CONTROL_TOKENS = ("LINK",)     # main ledger; both would double the verification work
N_MATCHED = 20                 # degree-matched control -- the main test
N_UNIFORM = 10                 # uniform control -- shows the degree confound; not the main test
N_BROKER_ANCHOR = 8            # broker anchors mixed in -- checks the verifier's criterion in the blind
CONTROL_SEED = 20260827        # fixed, independent of the pipeline's SEEDS, for reproducibility

# must not contain "": str.startswith(("", ...)) is always True and would mark every
# identity as unidentified. Empty values are handled separately.
GENERIC = ("unlabelled", "unlabeled", "unknown", "suspected", "mev",
           "fake_phishing", "compromised", "nan")
# v2 (fixed before unblinding): deposit and hot wallets of centralised exchanges are
# not routing protocols. The verification instructions put them under "Unknown"
# (as the verifier did for HTX 48); a Gate.io deposit address was entered by name,
# so the rule makes the treatment uniform. The result scored as entered is also
# reported (--cex-as-named).
CEX_PREFIXES = ("gate dep", "htx", "binance", "coinbase", "kraken", "kucoin",
                "bybit", "bitfinex", "huobi")
CEX_AS_NAMED = "--cex-as-named" in sys.argv


def ensemble_score(token, scale="1w"):
    """Rank-ensemble score, using the same functions as 05_c3_roles (cached
    embeddings -> standardise -> logistic regression -> mean rank)."""
    from sklearn.preprocessing import StandardScaler
    R5 = importlib.import_module("05_c3_roles")
    d = np.load(C.RESULTS / f"graph_{token}_{scale}.npz", allow_pickle=True)
    F = C.FEATURE_NAMES
    bal, cp, bet = (d["feat"][:, F.index(x)] for x in ("balance", "counterparties", "betweenness"))
    scores = [R5._brokers_from_emb(StandardScaler().fit_transform(e), bal, cp, bet, d["cat"])[2]
              for e in R5._multi_seed_embs(token, scale, d)]
    return R5._rank_ensemble(scores), d, len(scores)


def eligibility(d):
    """Eligibility pool: the broker definition of config without the score condition."""
    F = C.FEATURE_NAMES
    bal = d["feat"][:, F.index("balance")]
    cp = d["feat"][:, F.index("counterparties")]
    bet = d["feat"][:, F.index("betweenness")]
    cat = d["cat"]
    m = (cat == "Unlabeled") & (bal <= np.median(bal))
    if C.BROKER_MIN_COUNTERPARTIES:
        m &= cp >= C.BROKER_MIN_COUNTERPARTIES
    if C.BROKER_REQUIRE_POSITIVE_BETWEENNESS:
        m &= bet > 0
    return m, bal, cp, bet


def matched_sample(broker_cp, pool_idx, pool_cp, n, rng):
    """Pair each broker with the non-broker of closest counterparty count (without
    replacement). This is the control of the main test: with degree aligned, a
    difference between groups cannot be explained by degree."""
    avail = list(pool_idx)
    avail_cp = {i: pool_cp[k] for k, i in enumerate(pool_idx)}
    targets = rng.permutation(broker_cp)[:n]
    picked = []
    for t in targets:
        if not avail:
            break
        j = min(avail, key=lambda i: abs(avail_cp[i] - t))
        picked.append(j)
        avail.remove(j)
    return np.array(picked, dtype=int)


def do_sample():
    cm.banner("11 · drawing the control sample")
    rng = np.random.default_rng(CONTROL_SEED)
    rows = []
    for token in CONTROL_TOKENS:
        gp = C.RESULTS / f"graph_{token}_1w.npz"
        bp = C.RESULTS / f"hidden_brokers_{token}.csv"
        if not (gp.exists() and bp.exists()):
            print(f"  [X] {gp.name} or {bp.name} missing; run 01 and 05 first")
            return
        sc, d, n_emb = ensemble_score(token)
        if sc is None:
            print(f"  [X] {token}: emb_*_s*.npy missing; run 05_c3_roles.py first")
            return
        nodes = [str(x).lower() for x in d["nodes"]]
        elig, bal, cp, bet = eligibility(d)
        brokers = set(pd.read_csv(bp)["address"].astype(str).str.lower())
        is_broker = np.array([a in brokers for a in nodes])

        pool = np.flatnonzero(elig & ~is_broker)
        bidx = np.flatnonzero(is_broker)
        print(f"\n  {token}: ensemble score recomputed from {n_emb} embeddings")
        print(f"    pool {int(elig.sum()):,} | brokers {len(bidx)} | "
              f"available controls {len(pool):,}")
        print(f"    broker counterparties median {np.median(cp[bidx]):.0f} "
              f"[{cp[bidx].min():.0f}, {cp[bidx].max():.0f}]")
        print(f"    pool counterparties median {np.median(cp[pool]):.0f} "
              f"[{cp[pool].min():.0f}, {cp[pool].max():.0f}]")
        if np.median(cp[pool]) < np.median(cp[bidx]) / 2:
            print("    the degree distributions differ a lot -- which is why the control is matched")

        m_idx = matched_sample(cp[bidx], pool, cp[pool],
                               min(N_MATCHED, len(pool)), rng)
        remain = np.setdiff1d(pool, m_idx)
        u_idx = rng.choice(remain, size=min(N_UNIFORM, len(remain)),
                           replace=False)
        # Only some brokers are mixed into the blind list. Their identities are
        # already known; they calibrate the verifier: if the blind hit rate on them
        # is close to the known rate, the criterion did not tighten because the
        # verifier expected a list of controls.
        a_idx = rng.choice(bidx, size=min(N_BROKER_ANCHOR, len(bidx)),
                           replace=False)

        print(f"    matched controls {len(m_idx)}, counterparties median "
              f"{np.median(cp[m_idx]):.0f}  <- aligned with the brokers")
        print(f"    uniform controls {len(u_idx)}, counterparties median "
              f"{np.median(cp[u_idx]):.0f}")
        print(f"    broker anchors {len(a_idx)} (calibration)")

        for grp, idx in (("broker_anchor", a_idx), ("matched", m_idx),
                         ("uniform", u_idx)):
            for i in idx:
                rows.append({"token": token, "group": grp,
                             "address": nodes[i],
                             "counterparties": int(cp[i]),
                             "betweenness": round(float(bet[i]), 6),
                             "score_pct": round(float(sc[i]), 4)})

    # brokers of either token without a verification record also go into the blind list (group broker_new)
    known = known_records()
    kset = set(known["address"])
    for token in C.TOKENS:
        bp = C.RESULTS / f"hidden_brokers_{token}.csv"
        bdf = pd.read_csv(bp)
        for r in bdf.itertuples():
            a = str(r.address).lower()
            if a not in kset:
                rows.append({"token": token, "group": "broker_new", "address": a,
                             "counterparties": int(r.counterparties),
                             "betweenness": round(float(r.betweenness), 6),
                             "score_pct": round(float(r.ensemble_score), 4)})

    key = pd.DataFrame(rows).drop_duplicates(subset=["token", "address"])
    key["has_v1_record"] = key["address"].isin(kset)
    key.to_csv(KEY, index=False)
    # anchors must be in the blind list (calibration); other groups only where no record exists
    need = key[(key["group"] == "broker_anchor") | ~key["has_v1_record"]]
    need = need.drop_duplicates("address")
    blind = need.sample(frac=1.0, random_state=CONTROL_SEED)[
        ["address", "counterparties"]].copy()
    blind["verified_identity"] = ""
    blind["evidence"] = ""
    blind.to_csv(BLIND, index=False)
    known[known["address"].isin(set(key["address"]))].to_csv(KNOWN, index=False)
    print(f"  existing records reused: {int(key['has_v1_record'].sum())} (not in the blind list, except anchors)"
          f" → {KNOWN.name}")

    cm.banner("sample drawn", "-")
    print(f"  → {BLIND.name}  {len(blind)} addresses (shuffled, no groups)")
    print(f"  → {KEY.name}    do not open before verification is complete")
    print("\n  How to verify: on the Etherscan address page check the name tag, then the")
    print("  ERC-20 Token Transfers tab, then the Contract tab. Fill in verified_identity:")
    print("    · belongs to a protocol -> protocol name (e.g. '1inch: Router V6')")
    print("    · no tag but counterparties are DEX pools / aggregators -> 'Unlabelled routing contract'")
    print("    · high-frequency arbitrage pattern -> 'MEV Bot'")
    print("    · anything else -> 'Unknown'")
    print("\n  Then run: python 11_random_control.py score")
    cm.log_metric(SCRIPT, "BOTH", "n_blind", len(blind))


def _design_stats(token, bset):
    """Median counterparties of the pool and of the brokers (reads the graph file; no resampling)."""
    d = np.load(C.RESULTS / f"graph_{token}_1w.npz", allow_pickle=True)
    nodes = np.array([str(x).lower() for x in d["nodes"]])
    elig, _, cp, _ = eligibility(d)
    isb = np.isin(nodes, list(bset))
    return {"pool_size": int(elig.sum()), "pool_median_cp": float(np.median(cp[elig & ~isb])),
            "broker_median_cp": float(np.median(cp[isb]))}


def _min_detectable(n1, n2, p0, alpha=0.05, power=0.8, sims=2000, seed=CONTROL_SEED):
    """One-sided Fisher test: smallest difference in proportions detectable with the
    given power when the control proportion is p0 (by simulation)."""
    from scipy.stats import fisher_exact
    rng = np.random.default_rng(seed)
    for d in np.arange(0.05, 1 - p0 + 1e-9, 0.01):
        p1 = p0 + d
        hits = 0
        for _ in range(sims):
            a, c = rng.binomial(n1, p1), rng.binomial(n2, p0)
            hits += fisher_exact([[a, n1 - a], [c, n2 - c]], alternative="greater")[1] < alpha
        if hits / sims >= power:
            return round(float(d), 2)
    return None


def do_score():
    cm.banner("11 · unblinding and tests")
    if not (BLIND.exists() and KEY.exists()):
        print(f"  [X] {BLIND.name} or {KEY.name} missing; run the sample mode first")
        return
    b = pd.read_csv(BLIND)
    k = pd.read_csv(KEY)
    for df in (b, k):
        df["address"] = df["address"].astype(str).str.strip().str.lower()
    n_blank = b["verified_identity"].isna().sum() + \
        (b["verified_identity"].astype(str).str.strip() == "").sum()
    if n_blank:
        print(f"  [!] {n_blank} rows have an empty identity and count as unidentified.")
        print("      If verification is not finished, complete it first or both shares are understated.")
    kn = pd.read_csv(KNOWN) if KNOWN.exists() else pd.DataFrame(
        columns=["address", "verified_identity", "evidence"])
    kn["address"] = kn["address"].astype(str).str.lower()
    ident = pd.concat([b[["address", "verified_identity", "evidence"]],
                       kn[~kn["address"].isin(set(b["address"]))][
                           ["address", "verified_identity", "evidence"]]])
    m = k.merge(ident, on="address", how="left")

    def is_named(v):
        t = str(v).strip().lower()
        if not CEX_AS_NAMED and t.startswith(CEX_PREFIXES):
            return False
        return bool(t) and not t.startswith(GENERIC)

    m["named"] = m["verified_identity"].map(is_named)
    globals()["is_named"] = is_named

    from scipy.stats import fisher_exact
    out = {}
    for token in CONTROL_TOKENS:
        sub = m[m["token"] == token]
        cm.banner(f"{token}", "-")
        print(f"    {'group':<16}{'n':>5}{'named':>10}{'share':>9}"
              f"{'median cp':>12}")
        stat = {}
        for g in ("broker_anchor", "matched", "uniform"):
            d = sub[sub["group"] == g]
            if not len(d):
                continue
            hit = int(d["named"].sum())
            stat[g] = (hit, len(d))
            print(f"    {g:<16}{len(d):>5}{hit:>10}{hit / len(d):>8.0%}"
                  f"{d['counterparties'].median():>12.0f}")

        # ---- the main test uses all verified brokers, not the 8 blind anchors ----
        # broker identities: the v2 blind result first, then the v1 records
        bp = C.RESULTS / f"hidden_brokers_{token}.csv"
        bset = set(pd.read_csv(bp)["address"].astype(str).str.lower())
        # all v1 records + v2 blind results (blind first); known_identities_v2.csv holds only sampled addresses
        allk = known_records()
        imap = dict(zip(allk["address"], allk["verified_identity"]))
        imap.update(dict(zip(b["address"], b["verified_identity"])))
        missing = [a for a in bset if a not in imap]
        if missing:
            print(f"    [!] {len(missing)} brokers have no identity record; counted as unidentified")
        nh = int(sum(is_named(imap.get(a, "")) for a in bset))
        bfull = (nh, len(bset))
        print(f"    {'broker (all)':<16}{len(bset):>5}{nh:>10}"
              f"{nh / max(len(bset), 1):>8.0%}{'':>12}")
        if "broker_anchor" in stat:
            ah, an = stat["broker_anchor"]
            d_ = abs(ah / max(an, 1) - nh / max(len(bset), 1))
            print(f"\n    [calibration] blind anchors {ah / max(an,1):.0%} vs "
                  f"all known brokers {nh / max(len(bset),1):.0%}, difference {d_:.0%}")
            print(f"      {'criterion stable ✓' if d_ <= 0.15 else '[!] large difference: the criterion may have tightened in the blind'}")

        if bfull and "matched" in stat:
            bh, bn = bfull
            mh, mn = stat["matched"]
            tab = [[bh, bn - bh], [mh, mn - mh]]
            odds, p = fisher_exact(tab, alternative="greater")
            print("\n    [main test] brokers vs degree-matched control")
            print(f"      Fisher exact test (one-sided): OR = "
                  f"{odds if np.isfinite(odds) else float('inf'):.2f}, "
                  f"p = {p:.4f}")
            verdict = ("circularity ruled out: among degree-matched addresses the "
                       "criterion selects significantly more named routing protocols"
                       if p < 0.05 else
                       "not significant: among degree-matched addresses the criterion "
                       "adds no detectable discrimination")
            print(f"      → {verdict}")
            if p >= 0.05 and min(bn, mn) < 30:
                print(f"      [i] small sample (n={min(bn, mn)}): a non-significant result"
                      " may reflect low power rather than no effect")
            from scipy.stats import beta as _beta

            def cp_ci(k, n):
                lo = 0.0 if k == 0 else float(_beta.ppf(0.025, k, n - k + 1))
                hi = 1.0 if k == n else float(_beta.ppf(0.975, k + 1, n - k))
                return [round(lo, 4), round(hi, 4)]
            import math

            def _wilson(k, n, z=1.959964):
                q = k / n
                d = 1 + z * z / n
                c = q + z * z / (2 * n)
                r = z * math.sqrt(q * (1 - q) / n + z * z / (4 * n * n))
                return (c - r) / d, (c + r) / d
            # Newcombe (hybrid Wilson) interval for the difference in proportions
            q1, q2 = bh / bn, mh / mn
            l1, u1 = _wilson(bh, bn)
            l2, u2 = _wilson(mh, mn)
            diff_ci = [round(q1 - q2 - math.sqrt((q1 - l1) ** 2 + (u2 - q2) ** 2), 4),
                       round(q1 - q2 + math.sqrt((u1 - q1) ** 2 + (q2 - l2) ** 2), 4)]
            print(f"    [difference] broker − matched = {q1 - q2:+.3f}, 95% CI {diff_ci}")
            uh, un = stat.get("uniform", (0, 0))
            p_mu = float(fisher_exact([[mh, mn - mh], [uh, un - uh]],
                                      alternative="greater")[1]) if un else None
            anc = sub[sub["group"] == "broker_anchor"]
            allk = known_records()
            v1map = dict(zip(allk["address"], allk["verified_identity"]))
            agree = int(sum(is_named(r.verified_identity) == is_named(v1map.get(r.address, ""))
                            for r in anc.itertuples()))
            print(f"    [matched vs uniform] one-sided p = {p_mu:.4f}" if p_mu is not None else "")
            print(f"    [anchor agreement] blind result agrees with the record {agree}/{len(anc)}")
            out[token] = {"broker_all": bfull,
                          "ci95_clopper_pearson": {
                              "broker_all": cp_ci(*bfull),
                              "matched": cp_ci(*stat["matched"]),
                              "uniform": cp_ci(*stat["uniform"]) if "uniform" in stat else None,
                              "broker_anchor_blind": cp_ci(*stat["broker_anchor"])
                              if "broker_anchor" in stat else None},
                          "p_matched_gt_uniform": None if p_mu is None else round(p_mu, 5),
                          "anchor_agreement": [agree, int(len(anc))],
                          "diff_broker_minus_matched": round(q1 - q2, 4),
                          "min_detectable_diff_80pct_power": _min_detectable(bn, mn, mh / mn),
                          "design": _design_stats(token, bset),
                          "diff_ci95_newcombe": diff_ci,
                          "broker_anchor_blind": stat.get("broker_anchor"),
                          "matched": stat.get("matched"),
                          "uniform": stat.get("uniform"),
                          "odds_ratio": None if not np.isfinite(odds)
                          else round(float(odds), 3),
                          "p_value": round(float(p), 5),
                          "verdict": verdict}

    cm.save_json({"control_seed": CONTROL_SEED,
                  "cex_as_named": CEX_AS_NAMED,
                  "n_matched": N_MATCHED, "n_uniform": N_UNIFORM,
                  "n_broker_anchor": N_BROKER_ANCHOR,
                  "tokens": list(CONTROL_TOKENS),
                  "design": "counterparty-matched control from the same "
                            "eligibility pool; blind manual verification",
                  "results": out},
                 "random_control_cex_as_named.json" if CEX_AS_NAMED else "random_control.json")
    cm.banner("Done → results/random_control.json")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "sample"
    if mode == "sample":
        do_sample()
    elif mode == "score":
        do_score()
    else:
        print("usage: python 11_random_control.py [sample|score]")


if __name__ == "__main__":
    main()
