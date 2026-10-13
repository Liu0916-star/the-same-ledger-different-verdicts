# -*- coding: utf-8 -*-
"""
03_c2_weekly.py -- weekly flow-concentration series

Replaces cell 18 and Hhi_calculation of v16, with three corrections:

  1. edge weights are summed (common.build_graph); repeated edges no longer overwrite
  2. one basis for every statistic: Gini, top-1% share and HHI are all computed
     weekly, on the sender side, with summed edge weights. In v16 the three numbers
     came from two scripts and three combinations:
        Gini 0.976    cell 18          receiver, 12 weeks (W7 dropped), overwritten edges
        top1% 82.3%   cell 18          same, with zeros in the denominator
        Flow HHI 421  Hhi_calculation  sender, all 13 weeks, summed edges
     The receiver side, the pooled window, dropping outlier weeks and the v16
     top-1% implementation are printed side by side as sensitivity rows.
  3. writes results/c2_weekly_{TOKEN}.csv and c2_summary_{TOKEN}.json

Usage: python 03_c2_weekly.py
"""
import numpy as np
import pandas as pd

import config as C
import common as cm

SCRIPT = "03_c2_weekly"


def run(token):
    cm.banner(f"03 · weekly series {token}")
    tx = cm.load_transfers(token)
    outliers = cm.find_outlier_windows(tx)
    print(f"  transfers {len(tx):,} | weeks {tx['week'].nunique()} | "
          f"outlier weeks {outliers if outliers else 'none'}")

    rows = []
    elite_sets = {}          # week -> that week's top-K addresses by outflow
    for w, g in tx.groupby("week", sort=True):
        G = cm.build_graph(g, top_n=None, largest_wcc=False, verbose=False)
        outf = np.array(list(dict(G.out_degree(weight="w")).values()))
        inf = np.array(list(dict(G.in_degree(weight="w")).values()))
        import networkx as nx
        nb = G.number_of_nodes()
        if nb > 100_000:
            print(f"    week {int(w) + 1}: {nb:,} nodes, sampled betweenness is slow"
                  " (5-20 minutes); do not interrupt ...", flush=True)
        bet = nx.betweenness_centrality(
            G, k=min(C.BETWEENNESS_K["c2_window"], nb), seed=C.SEED)
        bv = np.array(list(bet.values()))
        # degenerate sampling: with k=200 on 550k nodes almost every node has zero
        # betweenness and the Gini collapses to 0; that cell is invalid, not "equal"
        zero_frac = float((bv == 0).mean())
        g_bet = cm.gini(bv) if zero_frac < 0.99 else np.nan
        if zero_frac >= 0.99:
            print(f"    [!] week {int(w) + 1}: betweenness is zero for {zero_frac * 100:.1f}%"
                  f" (k={min(C.BETWEENNESS_K['c2_window'], nb)} too small)"
                  " -> recorded as NaN")
        # ---- elite set: the week's top-K addresses by outflow ----
        # v16 reported "top-50 weekly retention 53% / 48%" and "mean elite flow
        # share 0.748" from a superseded script; recomputed here on one basis.
        ow = g.groupby("from")["amt"].sum().sort_values(ascending=False)
        topk = list(ow.head(C.ELITE_TOP_K).index)
        elite_sets[int(w)] = set(topk)
        elite_share = float(ow.head(C.ELITE_TOP_K).sum() / max(ow.sum(), 1e-12))

        rows.append({
            "window": int(w) + 1,
            "elite_share": elite_share,
            "start": (tx["ts"].min().normalize()
                      + pd.Timedelta(days=int(w) * C.WINDOW_DAYS)).date(),
            "txns": len(g), "nodes": G.number_of_nodes(),
            "edges": G.number_of_edges(), "volume": float(g["amt"].sum()),
            "gini_out": cm.gini(outf), "gini_in": cm.gini(inf),
            "top1_out": cm.top_share(outf, frac=0.01),
            "top1_in": cm.top_share(inf, frac=0.01),
            "top1_in_v16": cm.top_share_v16(inf),      # for the comparison with v16 only
            "hhi_out": cm.hhi(outf), "hhi_in": cm.hhi(inf),
            "gini_betweenness": g_bet, "betweenness_zero_frac": round(zero_frac, 4),
            "is_outlier": int(w) in outliers,
        })
        r = rows[-1]
        print(f"    week {r['window']:2d} {r['start']}  transfers {r['txns']:>7,} "
              f"nodes {r['nodes']:>7,} | Gini={r['gini_out']:.4f} "
              f"top1%={r['top1_out'] * 100:5.1f}% HHI={r['hhi_out']:7.1f}")

    df = pd.DataFrame(rows)
    # ---- weekly retention: overlap of the top-K sets of consecutive weeks ----
    # Retention belongs to a pair of weeks, so an outlier week contaminates two
    # values: its own (W7 vs W6) and the next week's (W8 vs W7). Dropping only the
    # outlier row would keep the second; retention_contaminated marks both.
    ws_ = sorted(elite_sets)
    ret = [np.nan]
    contam = [True]                      # the first week has no predecessor, hence no retention
    for i in range(1, len(ws_)):
        a_, b_ = elite_sets[ws_[i - 1]], elite_sets[ws_[i]]
        ret.append(len(a_ & b_) / max(len(b_), 1))
        contam.append(ws_[i - 1] in outliers or ws_[i] in outliers)
    df["top_k_retention"] = ret
    df["retention_contaminated"] = contam
    clean = df[~df["is_outlier"]]
    ret_clean = df.loc[~df["retention_contaminated"], "top_k_retention"]
    cm.save_csv(df, f"c2_weekly_{token}.csv")

    # ---------- main specification ----------
    cm.banner(f"{token} main (weekly · sender · summed edges · outlier weeks "
              f"{'dropped' if C.EXCLUDE_OUTLIER_WINDOWS else 'kept'})", "-")
    use = clean if C.EXCLUDE_OUTLIER_WINDOWS else df
    main = {"gini_flow": use["gini_out"].mean(),
            "top1pct_flow": use["top1_out"].mean(),
            "flow_hhi": use["hhi_out"].mean()}
    print(f"    flow Gini    {main['gini_flow']:.4f}")
    print(f"    top-1% share {main['top1pct_flow'] * 100:.1f}%")
    print(f"    Flow HHI    {main['flow_hhi']:.1f}   "
          f"{'unconcentrated' if main['flow_hhi'] < C.DOJ_UNCONCENTRATED else '>= DOJ line'}")
    n_bg = int(use["gini_betweenness"].notna().sum())
    print(f"    structural Gini {use['gini_betweenness'].mean():.4f}"
          f"   <- {n_bg}/{len(use)} weeks"
          f"{' (degenerate outlier weeks are NaN; different denominator)' if n_bg < len(use) else ''}")
    print(f"    elite (top{C.ELITE_TOP_K}) flow share  "
          f"{use['elite_share'].mean():.4f}")
    n_contam = int(df["retention_contaminated"].sum()) - 1   # minus the first week
    print(f"    elite weekly retention    "
          f"{df['top_k_retention'].mean():.4f}"
          f" ({ret_clean.mean():.4f} without {n_contam} contaminated pairs)")
    if n_contam:
        print(f"      an outlier week contaminates two retention values: W{outliers[0] + 1}"
              " and the week after it")
    main["elite_share"] = use["elite_share"].mean()
    main["top_k_retention"] = float(ret_clean.mean())

    # ---------- sensitivity ----------
    cm.banner("sensitivity (each row changes one choice)", "-")
    print(f"    {'choice':<26}{'Gini':>10}{'top1%':>9}{'HHI':>10}")

    def line(nm, d, gk, tk, hk):
        print(f"    {nm:<26}{d[gk].mean():>10.4f}"
              f"{d[tk].mean() * 100:>8.1f}%{d[hk].mean():>10.1f}")

    line("main (sender, all weeks)", df, "gini_out", "top1_out", "hhi_out")
    line("direction -> receiver", df, "gini_in", "top1_in", "hhi_in")
    line("weeks -> drop outliers", clean, "gini_out", "top1_out", "hhi_out")
    full_out = tx.groupby("from")["amt"].sum().values
    full_in = tx.groupby("to")["amt"].sum().values
    print(f"    {'time -> pooled window':<26}{cm.gini(full_out):>10.4f}"
          f"{cm.top_share(full_out, frac=0.01) * 100:>8.1f}%"
          f"{cm.hhi(full_out):>10.1f}")
    print(f"    {'  (same, receiver)':<26}{cm.gini(full_in):>10.4f}"
          f"{cm.top_share(full_in, frac=0.01) * 100:>8.1f}%"
          f"{cm.hhi(full_in):>10.1f}")
    ratio = df["hhi_out"].mean() / max(cm.hhi(full_out), 1e-9)
    print(f"    weekly / pooled = {ratio:.2f}x (the paper reports the weekly mean"
          " and says why)")

    # ---------- comparison with v16 ----------
    cm.banner("comparison with v16 (effect of the corrections)", "-")
    print(f"    {'statistic':<30}{'v16':>10}{'now':>10}")
    print(f"    {'flow Gini (receiver, clean)':<30}"
          f"{'0.976' if token == 'LINK' else '0.961':>10}"
          f"{clean['gini_in'].mean():>10.4f}")
    print(f"    {'top1% (v16 impl., receiver)':<30}"
          f"{'82.3%' if token == 'LINK' else '72.1%':>10}"
          f"{clean['top1_in_v16'].mean() * 100:>9.1f}%")
    print(f"    {'top1% (this repository)':<30}{'—':>10}"
          f"{clean['top1_in'].mean() * 100:>9.1f}%")
    print(f"    {'flow HHI (sender, all weeks)':<30}"
          f"{'421' if token == 'LINK' else '382':>10}"
          f"{df['hhi_out'].mean():>10.1f}")
    print(f"    {f'elite (top{C.ELITE_TOP_K}) flow share':<30}"
          f"{'0.748' if token == 'LINK' else '—':>10}"
          f"{clean['elite_share'].mean():>10.4f}")
    print(f"    {f'top{C.ELITE_TOP_K} retention (clean)':<30}"
          f"{'0.53' if token == 'LINK' else '0.48':>10}"
          f"{ret_clean.mean():>10.4f}")
    print("    the v16 elite figures came from a superseded script with overwritten"
          " edges; this table supersedes them")

    for k, v in main.items():
        cm.log_metric(SCRIPT, token, k, round(float(v), 4),
                      f"weekly, sender, summed edges (elite K={C.ELITE_TOP_K})")
    cm.save_json({
        "token": token, "main": {k: float(v) for k, v in main.items()},
        "weekly_out": {"gini": df["gini_out"].mean(), "top1": df["top1_out"].mean(),
                       "hhi": df["hhi_out"].mean(), "hhi_min": df["hhi_out"].min(),
                       "hhi_max": df["hhi_out"].max(),
                       "hhi_argmax_window": int(df.loc[df["hhi_out"].idxmax(), "window"])},
        "weekly_in": {"gini": df["gini_in"].mean(), "top1": df["top1_in"].mean(),
                      "hhi": df["hhi_in"].mean()},
        "pooled_out": {"gini": cm.gini(full_out), "top1": cm.top_share(full_out, frac=0.01),
                       "hhi": cm.hhi(full_out)},
        "pooled_in": {"gini": cm.gini(full_in), "top1": cm.top_share(full_in, frac=0.01),
                      "hhi": cm.hhi(full_in)},
        "weekly_over_pooled": float(ratio),
        "betweenness_gini": float(df["gini_betweenness"].mean()),
        "retention": float(ret_clean.mean()), "elite_share": float(use["elite_share"].mean()),
        "outlier_windows": [int(w) for w in outliers],
    }, f"c2_summary_{token}.json")
    return df


def main():
    for t in C.TOKENS:
        run(t)
    cm.banner("Done. Next: python 06_concentration.py")


if __name__ == "__main__":
    main()
