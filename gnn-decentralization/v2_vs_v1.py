# -*- coding: utf-8 -*-
"""v2_vs_v1.py -- key numbers of v1 (results_v1/) and v2 (results/) side by side.

Output: results/v2_vs_v1.md. Reads result files only; recomputes nothing.
"""
import json

import numpy as np
import pandas as pd

import config as C

V1, V2 = C.ROOT / "results_v1", C.RESULTS
L = []


def j(base, name):
    p = base / name
    return json.load(open(p)) if p.exists() else {}


def row(label, a, b, fmt="{:.3f}"):
    f = (lambda x: "—" if x is None or (isinstance(x, float) and np.isnan(x))
         else (fmt.format(x) if isinstance(x, (int, float)) else str(x)))
    L.append(f"| {label} | {f(a)} | {f(b)} |")


def head(t):
    L.extend(["", f"### {t}", "", "| statistic | v1 | v2 |", "|---|---|---|"])


def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def weekly(base, tok):
    p = base / f"c2_weekly_{tok}.csv"
    if not p.exists():
        return {}
    w = pd.read_csv(p)
    ok = w[~w["is_outlier"]] if "is_outlier" in w else w
    ret = w.loc[~w["retention_contaminated"].fillna(True).astype(bool), "top_k_retention"] \
        if "retention_contaminated" in w else w["top_k_retention"]
    return {"gini_out": ok["gini_out"].mean(), "top1_out": ok["top1_out"].mean(),
            "elite": ok["elite_share"].mean(), "hhi_mean": w["hhi_out"].mean(),
            "hhi_min": w["hhi_out"].min(), "hhi_max": w["hhi_out"].max(),
            "gini_bet": ok["gini_betweenness"].mean(), "retention": ret.mean(),
            "nodes_med": w["nodes"].median()}


def brokers(base, tok):
    p = base / f"hidden_brokers_{tok}.csv"
    return set(pd.read_csv(p)["address"].str.lower()) if p.exists() else set()


def main():
    L.append("# v1 → v2: key numbers side by side\n")
    L.append("v1 = arXiv 2609.24176v1 (results_v1/); v2 = end-of-window balance snapshot + "
             "zero-value and airdrop cleaning (results/). Seeds and hyperparameters unchanged. "
             "Third scale: v1 = 6.4×10^5-node graph, v2 = full cleaned graph.\n")

    for tok in C.TOKENS:
        cl = j(V2, f"cleaning_{tok}.json")
        dc = j(V2, "v2_data_check.json").get(tok, {})
        head(f"{tok} · data")
        row("raw transfers", dc.get("v1_transfers"), dc.get("n_transfers"), "{:,}")
        row("active addresses", C.EXPECT[tok]["n_active"] and (642_126 if tok == "LINK" else 38_667),
            cl.get("active_clean"), "{:,}")
        row("zero-value / airdrop transfers removed", "—", f"{cl.get('n_zero_value'):,} / {cl.get('n_airdrop_transfers'):,}")
        row("holders with positive balance", dc.get("v1_holders"), dc.get("v2_holders_with_genesis"), "{:,}")

    scales = [("1w", "1w"), ("5w", "5w"), ("64w", "full")]
    for tok in C.TOKENS:
        for s1, s2 in scales:
            a, b = j(V1, f"c1_{tok}_{s1}.json"), j(V2, f"c1_{tok}_{s2}.json")
            if not a and not b:
                continue
            head(f"{tok} · C1 · {s1} → {s2}")
            row("nodes", a.get("n_nodes"), b.get("n_nodes"), "{:,}")
            row("is_core anchors", a.get("n_anchors"), b.get("n_anchors"), "{:,}")
            row("AUC centrality", g(a, "is_core_centrality", "auc"), g(b, "is_core_centrality", "auc"))
            row("AUC structural (7)", g(a, "is_core_raw_struct", "auc"), g(b, "is_core_raw_struct", "auc"))
            row("AUC GNN mean", g(a, "gnn_is_core", "mean"), g(b, "gnn_is_core", "mean"))
            row("AUC GNN seed sd", g(a, "gnn_is_core", "sd_seed"), g(b, "gnn_is_core", "sd_seed"))
            row("AUC GNN constant input", g(a, "gnn_nofeat_is_core", "mean"), g(b, "gnn_nofeat_is_core", "mean"))
            row("AUC node2vec", g(a, "node2vec_is_core", "mean"), g(b, "node2vec_is_core", "mean"))
            row("AUC top-5% balance, centrality", g(a, "balance_top5pct_centrality", "auc"),
                g(b, "balance_top5pct_centrality", "auc"))
            row("AUC top-5% balance, structural", g(a, "balance_top5pct_raw_struct", "auc"),
                g(b, "balance_top5pct_raw_struct", "auc"))
            row("AUC top-5% balance, GNN", g(a, "gnn_balance", "mean"), g(b, "gnn_balance", "mean"))
            row("purity centrality", a.get("purity_centrality"), b.get("purity_centrality"), "{:.4f}")
            row("purity structural", a.get("purity_raw_struct"), b.get("purity_raw_struct"), "{:.4f}")
            row("purity GNN", g(a, "purity", "mean"), g(b, "purity", "mean"), "{:.4f}")
            row("random baseline", a.get("random_baseline_purity"), b.get("random_baseline_purity"), "{:.5f}")
            r1 = (g(a, "purity", "mean") / a["purity_raw_struct"]) if a else None
            r2 = (g(b, "purity", "mean") / b["purity_raw_struct"]) if b else None
            row("purity ratio GNN/structural", r1, r2, "{:.2f}")

    for tok in C.TOKENS:
        a, b = weekly(V1, tok), weekly(V2, tok)
        head(f"{tok} · weekly flows (sender side; v1 mean without outlier week)")
        for k, lab, f in [("gini_out", "flow Gini mean", "{:.3f}"), ("top1_out", "top-1% share", "{:.3f}"),
                          ("elite", "top-50 share", "{:.3f}"), ("retention", "top-50 weekly retention", "{:.2f}"),
                          ("hhi_mean", "flow HHI mean", "{:.0f}"), ("hhi_min", "flow HHI min", "{:.0f}"),
                          ("hhi_max", "flow HHI max", "{:.0f}"), ("gini_bet", "betweenness Gini", "{:.3f}"),
                          ("nodes_med", "median weekly nodes", "{:,.0f}")]:
            row(lab, a.get(k), b.get(k), f)
        pa, pb = j(V1, f"c2_procrustes_{tok}.json"), j(V2, f"c2_procrustes_{tok}.json")
        row("Procrustes aligned", pa.get("alignment_ok"), pb.get("alignment_ok"), "{}")
        row("fewest anchors", pa.get("min_anchors"), pb.get("min_anchors"), "{:,}")
        row("persistent elite", pa.get("n_persistent_elite"), pb.get("n_persistent_elite"), "{:,}")
        row("elite drift mean", pa.get("normal_drift_mean"), pb.get("normal_drift_mean"), "{:.3f}")

    for tok in C.TOKENS:
        a, b = j(V1, f"c3_typology_{tok}.json"), j(V2, f"c3_typology_{tok}.json")
        head(f"{tok} · roles and brokers")

        def core(d):
            t = d.get("typology", {})
            if not t:
                return {}
            k = max(t, key=lambda c: (t[c]["core_rate"], t[c]["size"]))
            return t[k]
        ca, cb = core(a), core(b)
        row("core cluster size", ca.get("size"), cb.get("size"), "{:,}")
        row("core cluster core rate", ca.get("core_rate"), cb.get("core_rate"), "{:.4f}")
        row("core cluster median counterparties", ca.get("med_counterparties"), cb.get("med_counterparties"), "{:.0f}")
        row("core cluster median balance", ca.get("med_balance"), cb.get("med_balance"), "{:,.2f}")
        for k, lab in [("spearman_nonzero_balance_vs_counterparties", "ρ balance-counterparties (positive)"),
                       ("spearman_nonzero_balance_vs_betweenness", "ρ balance-betweenness (positive)"),
                       ("n_nonzero", "nodes with positive balance"), ("verdict", "core vs richest cluster")]:
            row(lab, g(a, "wealth_power", k), g(b, "wealth_power", k),
                "{:.4f}" if "ρ" in lab else "{}")
        hb_a, hb_b = g(a, "hidden_brokers") or {}, g(b, "hidden_brokers") or {}
        for k, lab in [("rank_ensemble_set", "brokers (rank ensemble)"), ("vote_consensus_set", "vote >=50%"),
                       ("rank_vote_overlap", "both"), ("overlap_size_matched", "overlap with same-size betweenness set")]:
            row(lab, hb_a.get(k), hb_b.get(k), "{}")
        ba, bb = brokers(V1, tok), brokers(V2, tok)
        row("overlap v1 / v2", "—", f"{len(ba & bb)} / v1 {len(ba)} / v2 {len(bb)}")

    a, b = j(V1, "c3_cross_token.json"), j(V2, "c3_cross_token.json")
    head("brokers shared by LINK and UNI")
    row("shared", a.get("n_shared"), b.get("n_shared"), "{}")
    row("of which identified", a.get("n_identified"), b.get("n_identified"), "{}")

    for tok in C.TOKENS:
        a, b = j(V1, f"concentration_{tok}.json"), j(V2, f"concentration_{tok}.json")
        head(f"{tok} · concentration grid")
        for k in ["all_holders|all", "all_holders|excl_burn", "all_holders|excl_burn_issuer",
                  "active|all", "active|excl_burn_issuer"]:
            row(f"balance HHI {k}", g(a, "grid", k, "hhi"), g(b, "grid", k, "hhi"), "{:.1f}")
            row(f"balance Gini {k}", g(a, "grid", k, "gini"), g(b, "grid", k, "gini"), "{:.4f}")
        for k, lab in [("hhi_entity", "balance HHI entity-merged"), ("gini_entity", "balance Gini entity-merged")]:
            row(lab, g(a, "grid", "all_holders|entity_merged", k), g(b, "grid", "all_holders|entity_merged", k),
                "{:.4f}" if "Gini" in lab else "{:.1f}")
        row("flow HHI address", a.get("flow_hhi_addr"), b.get("flow_hhi_addr"), "{:.1f}")
        row("flow HHI entity", a.get("flow_hhi_entity"), b.get("flow_hhi_entity"), "{:.1f}")
        row("largest entity-level week", a.get("flow_hhi_entity_max"), b.get("flow_hhi_entity_max"), "{:.1f}")
        row("burned %", a.get("burned_pct"), b.get("burned_pct"), "{:.2f}")
        row("issuer %", a.get("reserve_pct"), b.get("reserve_pct"), "{:.2f}")
        row("label coverage of outflow", a.get("entity_coverage_outflow"), b.get("entity_coverage_outflow"), "{:.3f}")
        row("largest entity outflow share", a.get("top_entity_outflow_share"), b.get("top_entity_outflow_share"), "{:.3f}")

    out = C.RESULTS / "v2_vs_v1.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
