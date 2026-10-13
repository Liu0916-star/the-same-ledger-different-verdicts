# -*- coding: utf-8 -*-
"""
08_figures.py -- the paper's three figures (Fig. 1 specifications, Fig. 2 HHI
reference points, Fig. 3 matched control), drawn from result files only

Unlike make_all_figures.py of v16, this script computes nothing: it only reads
result files. In v16 captions and images once disagreed (two figures left out
UNI) because the plotting script recomputed numbers itself. Every number has
one source.

Usage: python 08_figures.py
"""
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C
import common as cm

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 300, "savefig.bbox": "tight",
    "font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
    "axes.spines.top": False, "axes.spines.right": False,
})
CLR = {"LINK": "#2E86AB", "UNI": "#E63946"}


def _load(name):
    p = C.RESULTS / name
    if not p.exists():
        return None
    return (pd.read_csv(p) if p.suffix == ".csv"
            else json.load(open(p, encoding="utf-8")))


def _save(fig, name):
    p = C.FIGURES / name
    fig.savefig(p, metadata={"CreationDate": None})
    plt.close(fig)
    print(f"    → {name}")


def fig_hhi_benchmark():
    """Fig. 2: flow and balance HHI beside reference points from other industries.

    The log axis spans two orders of magnitude, and matplotlib's default minor
    tick labels pile up at the bottom and collide with the axis title, so only
    decades are labelled, minor labels are off and the bottom margin is fixed.
    """
    from matplotlib.ticker import LogLocator, NullFormatter, FuncFormatter
    recs = {t: _load(f"concentration_{t}.json") for t in C.TOKENS}
    recs = {k: v for k, v in recs.items() if v}
    if not recs:
        print("    [skipped] HHI benchmark figure: concentration_*.json missing")
        return
    # reference points: only checkable numbers (made by the scripts in benchmarks/), Section 4.5
    us = json.load(open(C.ROOT / "benchmarks" / "us_bank_hhi.json"))
    ob = json.load(open(C.ROOT / "benchmarks" / "other_benchmarks.json"))
    sw = ob["sweden_credit_institutions_assets_hhi"]
    bench = {"U.S. deposits, national (FDIC 2026)": us["2026"]["hhi"],
             f"Swedish banking assets (ECB {max(sw)})": sw[max(sw)],
             "Global card networks (Nilson 2022)": ob["global_card_networks"]["hhi_lower"]}
    items = [(f"{t} flow (address level)", v["flow_hhi_addr"], CLR[t])
             for t, v in recs.items()]
    items += [(f"{t} flow (entity-resolved)", v["flow_hhi_entity"], CLR[t])
              for t, v in recs.items()]
    items += [(f"{t} balance", v["grid"]["all_holders|all"]["hhi"], CLR[t])
              for t, v in recs.items()]
    items += [(k, v, "#BBB") for k, v in bench.items()]
    items.sort(key=lambda z: z[1])

    n = len(items)
    # height = 0.30 in per bar + fixed margins; too small a base squeezes the axis title
    fig, ax = plt.subplots(figsize=(7.2, 0.30 * n + 2.3))
    y = np.arange(n)
    b = ax.barh(y, [z[1] for z in items], color=[z[2] for z in items],
                alpha=0.9, height=0.66)
    ax.bar_label(b, fmt="%.0f", fontsize=7, padding=3)
    ax.set_yticks(y)
    ax.set_yticklabels([z[0] for z in items], fontsize=7.5)
    ax.set_ylim(-1.5, n - 0.2)

    ax.set_xscale("log")
    ax.set_xlim(80, 12000)
    # label decades only; no minor tick labels
    ax.xaxis.set_major_locator(LogLocator(base=10))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.xaxis.set_minor_locator(LogLocator(base=10, subs=tuple(range(2, 10))))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.tick_params(axis="x", which="major", labelsize=8, pad=2)
    ax.tick_params(axis="x", which="minor", length=2)

    # The labels of the threshold lines must be staggered: on a log axis 1,500 and
    # 2,500 are too close for two labels. Both sets of guidelines are drawn so the
    # reader can see whether the verdict depends on them: the 2023 guidelines
    # define only "highly concentrated" above 1,800; the 2010 guidelines used
    # 1,500 / 2,500.
    for xv, lab, ls, yy, ha in (
            (C.DOJ2023_HIGH,     "2023: 1,800",    "--", -0.95, "left"),
            (C.DOJ_UNCONCENTRATED,      "2010: 1,500", ":", -0.45, "right"),
            (C.DOJ_HIGHLY_CONCENTRATED, "2010: 2,500", ":", -0.45, "left")):
        ax.axvline(xv, ls=ls, c="darkred", lw=1.0 if ls == "--" else 0.8,
                   alpha=0.9 if ls == "--" else 0.55)
        ax.text(xv, yy, f"{lab} " if ha == "right" else f" {lab}",
                fontsize=6.3, color="darkred", va="bottom", ha=ha,
                alpha=1.0 if ls == "--" else 0.7)

    ax.set_xlabel("Herfindahl\u2013Hirschman Index (log scale)", fontsize=8.5,
                  labelpad=6)

    ax.grid(axis="x", which="major", alpha=0.25)
    ax.set_axisbelow(True)
    # fixed margins rather than tight_layout's estimate
    fig.subplots_adjust(left=0.30, right=0.97, top=1 - 0.5 / (0.30 * n + 2.3),
                        bottom=1.55 / (0.30 * n + 2.0))
    _save(fig, "fig_hhi_benchmark.pdf")


def fig_specification():
    """Fig. 1: the same snapshot under six specifications.

    (a) the HHI moves by an order of magnitude on UNI; (b) relative to the
    all-holder specification the Gini stays near 1 while the HHI does not.
    """
    recs = {t: _load(f"concentration_{t}.json") for t in C.TOKENS}
    recs = {k: v for k, v in recs.items() if v}
    if not recs:
        print("    [skipped] specification figure: concentration_*.json missing")
        return
    # the active population with the airdrop transfers kept (results_spec_keep_airdrop) as one more row
    for t in recs:
        rp = C.ROOT / "results_spec_keep_airdrop" / f"concentration_{t}.json"
        recs[t]["grid"]["active_raw|all"] = json.load(open(rp))["grid"]["active|all"]
    # (label, grid key, entity-resolved?)
    specs = [("All holders",              "all_holders|all",              False),
             ("Excl. burn",               "all_holders|excl_burn",        False),
             ("Excl. burn + issuer",      "all_holders|excl_burn_issuer", False),
             ("Active, airdrop kept",     "active_raw|all",               False),
             ("Active, cleaned",          "active|all",                   False),
             ("Entity-resolved",          "all_holders|entity_merged",    True)]
    fig, axes = plt.subplots(1, 2, figsize=(10.8, 3.7),
                             gridspec_kw={"width_ratios": [1.45, 1]})

    # --- (a) HHI under each specification, log axis ---
    ax = axes[0]
    xs = np.arange(len(specs))
    w = 0.38
    for i, (t, r) in enumerate(recs.items()):
        vals = []
        for _, key, is_ent in specs:
            g = r["grid"].get(key, {})
            vals.append(g.get("hhi_entity" if is_ent else "hhi", np.nan))
        b = ax.bar(xs + (i - 0.5) * w, vals, w, label=t, color=CLR[t],
                   alpha=0.88)
        ax.bar_label(b, fmt="%.0f", fontsize=7, padding=2)
    # threshold labels go outside the axes on the right (inside they cover the bar
    # values); 1,500 and 1,800 are only 0.08 decades apart, so one label sits
    # above its line and the other below
    for yv, lab, ls, al, va in (
            (C.DOJ2023_HIGH, "2023 high (1,800)", "--", 0.9, "bottom"),
            (C.DOJ_UNCONCENTRATED, "2010 (1,500)", ":", 0.6, "top")):
        ax.axhline(yv, ls=ls, c="darkred", lw=1.0, alpha=al)
        ax.text(1.01, yv, lab, ha="left", va=va, fontsize=6,
                color="darkred", alpha=al,
                transform=ax.get_yaxis_transform(), clip_on=False)
    ax.set_yscale("log")
    ax.set_xticks(xs)
    # rotation_mode="anchor" rotates labels about the tick; otherwise they drift left
    ax.set_xticklabels([x[0] for x in specs], fontsize=7.5, rotation=18,
                       ha="right", rotation_mode="anchor")
    ax.set_ylabel("Balance HHI (log scale)")
    ax.set_title("(a) The same ledger, six specifications", fontsize=9)
    # the 1,800 line crosses the upper left corner, so this goes below the axes
    ax.legend(frameon=False, fontsize=7.5, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.30))
    # print the range
    for t, r in recs.items():
        v = [r["grid"].get(k, {}).get("hhi_entity" if e else "hhi", np.nan)
             for _, k, e in specs]
        v = [x for x in v if np.isfinite(x)]
        if len(v) > 1:
            print(f"      {t} HHI range {min(v):.0f}–{max(v):.0f} "
                  f"({max(v)/min(v):.0f}x)")

    # --- (b) relative movement of HHI and Gini over the same specifications ---
    # A bar chart of the Gini cannot show "barely moves": all values lie in
    # 0.98-1.00 and a zoomed axis exaggerates differences. Plotting the ratio to
    # the all-holder specification on a log axis shows the HHI spread over the
    # axis while the Gini stays on the 1.0 line.
    ax = axes[1]
    ratio_specs = [("All\nholders",        "all_holders|all",              False),
                   ("Excl.\nburn",          "all_holders|excl_burn",        False),
                   ("Excl. burn\n+ issuer", "all_holders|excl_burn_issuer", False),
                   ("Active,\nairdrop kept", "active_raw|all",              False),
                   ("Active,\ncleaned",     "active|all",                   False),
                   ("Entity-\nresolved",    "all_holders|entity_merged",    True)]
    xs2 = np.arange(len(ratio_specs))
    for t, r in recs.items():
        hh, gg = [], []
        base_h = r["grid"].get("all_holders|all", {}).get("hhi", np.nan)
        base_g = r["grid"].get("all_holders|all", {}).get("gini", np.nan)
        for _, key, is_ent in ratio_specs:
            g = r["grid"].get(key, {})
            hh.append(g.get("hhi_entity" if is_ent else "hhi", np.nan) / base_h)
            gg.append(g.get("gini_entity" if is_ent else "gini", np.nan) / base_g)
        ax.plot(xs2, hh, "o-", color=CLR[t], ms=6, lw=1.6,
                label=f"{t} — HHI")
        ax.plot(xs2, gg, "s--", color=CLR[t], ms=5, lw=1.2, alpha=0.55,
                markerfacecolor="white", label=f"{t} — Gini")
    ax.axhline(1.0, c="k", lw=0.8, ls=":")
    ax.set_yscale("log")
    from matplotlib.ticker import FixedLocator, NullFormatter, FuncFormatter
    ax.yaxis.set_major_locator(FixedLocator([0.1, 0.2, 0.5, 1, 2, 5]))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xticks(xs2)
    ax.set_xticklabels([x[0] for x in ratio_specs], fontsize=7.5)
    ax.set_ylabel("Relative to all holders")
    ax.set_title("(b) Change relative to all holders", fontsize=9)
    ax.legend(frameon=False, fontsize=7, ncol=2)
    ax.grid(axis="y", alpha=0.25)
    ax.set_axisbelow(True)
    fig.tight_layout()
    _save(fig, "fig_specification.pdf")


def fig_random_control():
    """Fig. 3: the matched control experiment, a negative result."""
    r = _load("random_control.json")
    if not r or not r.get("results"):
        print("    [skipped] control figure: random_control.json missing")
        return
    from scipy.stats import beta
    def ci(h, n):
        lo = beta.ppf(0.025, h, n - h + 1) if h > 0 else 0.0
        hi = beta.ppf(0.975, h + 1, n - h) if h < n else 1.0
        return lo, hi

    tok = list(r["results"])[0]
    res = r["results"][tok]
    groups = [("Hidden brokers\n(GNN-selected)", res.get("broker_all"),
               CLR.get(tok, "#2E86AB")),
              ("Control,\ndegree-matched", res.get("matched"), "#8D99AE"),
              ("Control,\nunmatched", res.get("uniform"), "#D9D9D9")]
    groups = [(a, b, c) for a, b, c in groups if b]
    fig, ax = plt.subplots(figsize=(5.4, 3.1))
    xs = np.arange(len(groups))
    props, los, his = [], [], []
    for _, (h, n), _ in groups:
        p = h / n
        lo, hi = ci(h, n)
        props.append(p); los.append(p - lo); his.append(hi - p)
    ax.bar(xs, props, 0.55, yerr=[los, his], capsize=5,
               color=[g[2] for g in groups], alpha=0.9,
               edgecolor="k", linewidth=0.5)
    for i, (nm, (h, n), _) in enumerate(groups):
        ax.text(i, props[i] + his[i] + 0.03, f"{h}/{n}", ha="center",
                fontsize=8.5)
    ax.set_xticks(xs)
    ax.set_xticklabels([g[0] for g in groups], fontsize=8.5)
    ax.set_ylim(0, 1.0)
    ax.set_ylabel("Share resolving to a named protocol")
    pv = res.get("p_value")
    # a real newline is needed here: a literal backslash-n would be printed on the figure
    ax.set_title("Matched control on LINK\n"
                 f"Fisher one-sided $p$ = {pv:.2f} "
                 "(brokers vs degree-matched control)", fontsize=8.5)
    ax.annotate("", xy=(0, 0.93), xytext=(1, 0.93),
                arrowprops=dict(arrowstyle="<->", lw=0.9, color="grey"))
    ax.text(0.5, 0.95, "no detectable difference", ha="center", fontsize=8,
            color="grey")
    fig.tight_layout()
    _save(fig, "fig_random_control.pdf")


def main():
    cm.banner("08 · the paper's three figures (reads result files only)")
    for fn in (fig_specification, fig_hhi_benchmark, fig_random_control):
        fn()
    cm.banner(f"Done → {C.FIGURES}")


if __name__ == "__main__":
    main()
