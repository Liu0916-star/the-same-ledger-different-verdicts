# -*- coding: utf-8 -*-
"""v2_spec_compare.py -- comparison of the cleaning and edge-weight specifications (Appendix B).

Reads results/ (main) and results_spec_<SPEC>/; writes results/spec_compare.json and .md.
Reads result files only; recomputes nothing.
"""
import json

import pandas as pd

import config as C

SPECS = {"main": C.ROOT / "results", "keep_zero": C.ROOT / "results_spec_keep_zero",
         "keep_airdrop": C.ROOT / "results_spec_keep_airdrop", "raw": C.ROOT / "results_spec_raw",
         "overwrite": C.ROOT / "results_spec_overwrite"}


def j(d, name):
    p = d / name
    return json.load(open(p)) if p.exists() else {}


def main():
    out, lines = {}, ["# Cleaning and edge-weight specifications (10^4 subgraphs)", ""]
    for tok in C.TOKENS:
        main_br = set(pd.read_csv(SPECS["main"] / f"hidden_brokers_{tok}.csv")["address"].str.lower())
        rows = {}
        for s, d in SPECS.items():
            c1, conc, ty = j(d, f"c1_{tok}_1w.json"), j(d, f"concentration_{tok}.json"), \
                j(d, f"c3_typology_{tok}.json")
            bp = d / f"hidden_brokers_{tok}.csv"
            br = set(pd.read_csv(bp)["address"].str.lower()) if bp.exists() else set()
            g = conc.get("grid", {})
            core = max(ty.get("typology", {}).values(), key=lambda c: (c["core_rate"], c["size"]),
                       default={})
            rows[s] = {
                "graph_nodes": c1.get("n_nodes"), "anchors": c1.get("n_anchors"),
                "active_n": g.get("active|all", {}).get("n"),
                "active_balance_hhi": g.get("active|all", {}).get("hhi"),
                "auc_centrality": c1.get("is_core_centrality", {}).get("auc"),
                "auc_struct": c1.get("is_core_raw_struct", {}).get("auc"),
                "auc_gnn": c1.get("gnn_is_core", {}).get("mean"),
                "auc_balance_struct": c1.get("balance_top5pct_raw_struct", {}).get("auc"),
                "auc_balance_gnn": c1.get("gnn_balance", {}).get("mean"),
                "purity_ratio": (c1["purity"]["mean"] / c1["purity_raw_struct"]) if c1 else None,
                "core_cluster_med_balance": core.get("med_balance"),
                "rho_bal_cp": ty.get("wealth_power", {}).get("spearman_nonzero_balance_vs_counterparties"),
                "n_brokers": len(br), "brokers_overlap_main": len(br & main_br),
            }
        out[tok] = rows
        keys = list(next(iter(rows.values())).keys())
        lines += [f"## {tok}", "", "| statistic | " + " | ".join(SPECS) + " |",
                  "|---|" + "---|" * len(SPECS)]
        for k in keys:
            vals = []
            for s in SPECS:
                v = rows[s][k]
                vals.append("—" if v is None else (f"{v:,.3f}" if isinstance(v, float) else f"{v:,}"))
            lines.append(f"| {k} | " + " | ".join(vals) + " |")
        lines.append("")
    shared = {}
    for s, d in SPECS.items():
        try:
            a = set(pd.read_csv(d / "hidden_brokers_LINK.csv")["address"].str.lower())
            b = set(pd.read_csv(d / "hidden_brokers_UNI.csv")["address"].str.lower())
            shared[s] = len(a & b)
        except FileNotFoundError:
            shared[s] = None
    out["shared_brokers"] = shared
    lines += ["## Brokers shared by LINK and UNI", "", " | ".join(f"{s}: {v}" for s, v in shared.items()), ""]
    (C.ROOT / "results" / "spec_compare.json").write_text(json.dumps(out, indent=2, default=str))
    (C.ROOT / "results" / "spec_compare.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
