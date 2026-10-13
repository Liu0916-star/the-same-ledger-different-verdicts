# -*- coding: utf-8 -*-
"""
06_concentration.py -- ownership concentration and entity resolution

Produces the balance rows of Table 1. Each discretionary choice varies alone:
    population    all holders (main) / transfer-active / dust floor / value floor
    address type  all / excluding burn / excluding burn and issuer reserves
    entity        one address = one participant / labelled addresses merged
    statistics    Gini / top 1% / top 10 / HHI
and the flow side is entity-resolved as well.

The script checks and prints three facts:
  - on UNI the HHI rises when the burn address is excluded. This is
    renormalisation, not a bug: removing a holder with share s removes (100 s)^2
    points but scales every remaining squared share by 1 / (1 - s)^2;
  - excluding issuer reserves brings the two tokens close together, so most of
    the gap in the headline HHI comes from protocol-held supply;
  - merging labelled entities moves the HHI a lot (the seven LINK reserve wallets
    become one) while the Gini barely moves.

Entity resolution merges only labelled addresses (unlabelled ones stay separate),
so the entity-level figures are lower bounds.

Usage: python 06_concentration.py
"""
import json

import pandas as pd

import config as C
import common as cm

SCRIPT = "06_concentration"


def metrics(v):
    return {"n": len(v), "gini": cm.gini(v),
            "top1": cm.top_share(v, frac=0.01),
            "top10": cm.top_share(v, k=10), "hhi": cm.hhi(v)}


def _row(name, m):
    print(f"    {name:<28}{m['n']:>10,}{m['gini']:>9.4f}"
          f"{m['top1'] * 100:>7.1f}%{m['top10'] * 100:>7.1f}%{m['hhi']:>10.1f}")


def run(token, emap):
    cm.banner(f"06 · concentration {token}")
    tx = cm.load_transfers(token)
    bal = cm.load_balances(token)
    active = cm.active_addresses(tx)
    iss = C.ISSUER_RESERVES.get(token, frozenset())
    tot = bal["balance"].sum()

    burned = bal.loc[bal["address"].isin(C.BURN_ADDRS), "balance"].sum()
    reserve = bal.loc[bal["address"].isin(iss), "balance"].sum()
    print(f"  holders {len(bal):,} | active {len(active):,}")
    print(f"  burned {burned:,.0f} ({burned / tot * 100:.2f}%) | "
          f"issuer reserves {reserve:,.0f} ({reserve / tot * 100:.2f}%) · {len(iss)} addresses")

    price = json.load(open(C.PRICES))[token]["price_usd"]
    vfloor = C.VALUE_FLOOR_USD / price
    pops = {"all_holders": bal,
            "active": bal[bal["address"].isin(active)],
            "dust_floor": bal[bal["balance"] >= C.DUST_FLOOR],
            "value_floor": bal[bal["balance"] >= vfloor]}
    print(f"  value floor {C.VALUE_FLOOR_USD} USD = {vfloor:,.4f} {token} (price {price:.4f})")
    excls = {"all": lambda d: d,
             "excl_burn": lambda d: d[~d["address"].isin(C.BURN_ADDRS)],
             "excl_burn_issuer": lambda d: d[~d["address"].isin(
                 set(C.BURN_ADDRS) | set(iss))]}

    print(f"\n  [population x address type]  main = {C.MAIN_POPULATION} x all")
    print(f"    {'population / excluded':<28}{'n':>10}{'Gini':>9}{'top1%':>8}"
          f"{'top10':>8}{'HHI':>10}")
    grid = {}
    for pn, pdf in pops.items():
        for en, fn in excls.items():
            m = metrics(fn(pdf)["balance"].values)
            grid[f"{pn}|{en}"] = m
            _row(f"{pn} / {en}", m)

    # ---------- check of the renormalisation effect ----------
    if burned > 0:
        base = grid["all_holders|all"]["hhi"]
        after = grid["all_holders|excl_burn"]["hhi"]
        sh = burned / tot
        pred = (base - (sh * 100) ** 2) / (1 - sh) ** 2
        print(f"\n  [check] excluding burn {base:.1f} → {after:.1f}")
        print(f"    burn share {sh * 100:.2f}%, contributes {(sh * 100) ** 2:.1f} points; "
              f"removing it scales remaining squared shares by {1 / (1 - sh) ** 2:.4f}")
        print(f"    predicted ({base:.1f}−{(sh * 100) ** 2:.1f})×"
              f"{1 / (1 - sh) ** 2:.4f} = {pred:.1f}  observed {after:.1f}  "
              f"{'[OK] renormalisation, not a bug' if abs(pred - after) < 1 else '[X]'}")

    # ---------- entity resolution ----------
    print("\n  [entity resolution] (unlabelled addresses stay separate -> lower bound)")
    be = bal.assign(k=cm.entity_key(bal["address"], emap))
    for pn, pdf in pops.items():
        sub = be[be["address"].isin(pdf["address"])]
        a = cm.hhi(sub["balance"].values)
        b = cm.hhi(sub.groupby("k")["balance"].sum().values)
        g_a, g_b = cm.gini(sub["balance"].values), cm.gini(
            sub.groupby("k")["balance"].sum().values)
        print(f"    {pn:<16} HHI {a:>8.1f} → {b:>8.1f} ({b / a:.2f}x) | "
              f"Gini {g_a:.4f} → {g_b:.4f}")
        grid[f"{pn}|entity_merged"] = {"hhi_addr": a, "hhi_entity": b,
                                  "gini_addr": g_a, "gini_entity": g_b}

    # ---------- flows ----------
    print("\n  [flow, entity-resolved]")
    txn = cm.load_transfers(token)
    ha = cm.weekly_metric(txn, "from", cm.hhi)
    te = txn.assign(k=cm.entity_key(txn["from"], emap))
    he = pd.Series({int(w): cm.hhi(g.groupby("k")["amt"].sum().values)
                    for w, g in te.groupby("week")})
    print(f"    flow HHI address {ha.mean():.1f} → entity {he.mean():.1f}"
          f" ({he.mean() / ha.mean():.2f}x)")
    print(f"    largest entity-level week {he.max():.1f}  "
          f"{'below' if he.max() < C.DOJ_UNCONCENTRATED else '[!] above'} "
          f"the DOJ {C.DOJ_UNCONCENTRATED:,} line")
    print("    entity-level by week: " + " ".join(f"{x:.0f}" for x in he.sort_index()))

    # sensitivity: also drop outflows from issuer reserves (not market activity)
    if iss:
        t2 = txn[~txn["from"].isin(iss)]
        h2 = pd.Series({int(w): cm.hhi(
            g.assign(k=cm.entity_key(g["from"], emap))
             .groupby("k")["amt"].sum().values)
            for w, g in t2.groupby("week")})
        print(f"    also without issuer outflows: {h2.mean():.1f}"
              f" ({'below' if h2.max() < C.DOJ_UNCONCENTRATED else '[!] above'}"
              f" the DOJ line, max {h2.max():.1f})")

    wk = txn.groupby("week")["amt"].sum()
    g = txn.groupby(["week", "from"])["amt"].sum().reset_index()
    g["sh"] = g["amt"] / g["week"].map(wk)
    osh = (g.groupby("from")["sh"].sum() / txn["week"].nunique()
           ).sort_values(ascending=False)
    cov = osh[osh.index.isin(emap)].sum()
    print(f"    labels cover {cov * 100:.1f}% of mean weekly outflow"
          f"{'  [!] low; the merge says little' if cov < 0.30 else ''}")

    print("\n  [top-15 senders by outflow]")
    for i, (a, sh_) in enumerate(osh.head(15).items(), 1):
        print(f"    {i:>3} {a}  {sh_ * 100:>6.2f}%  {emap.get(a, '???')}")

    # entity shares after merging: how large is the largest entity?
    ent_sh = (osh.groupby(cm.entity_key(pd.Series(osh.index, index=osh.index),
                                        emap)).sum().sort_values(ascending=False))
    named = ent_sh[[not str(k).startswith("0x") for k in ent_sh.index]]
    print("\n  [top-10 entities by outflow] (unlabelled stay separate, so lower bounds)")
    for i, (e, sh_) in enumerate(named.head(10).items(), 1):
        n_addr = sum(1 for a in osh.index if emap.get(a) == e)
        print(f"    {i:>3} {str(e):<28}{sh_ * 100:>6.2f}%  "
              f"({n_addr} addresses)")
    top_ent = float(named.iloc[0]) if len(named) else float("nan")
    print(f"    → largest entity: {top_ent * 100:.2f}% of mean weekly outflow"
          f", {(top_ent * 100) ** 2:.0f} HHI points on its own")

    cm.save_json({"token": token, "grid": grid,
                  "value_floor_tokens": vfloor, "price_usd": price,
                  "burned_pct": round(burned / tot * 100, 2),
                  "reserve_pct": round(reserve / tot * 100, 2),
                  "flow_hhi_addr": round(float(ha.mean()), 1),
                  "flow_hhi_entity": round(float(he.mean()), 1),
                  "entity_coverage_outflow": round(float(cov), 4),
                  "flow_hhi_entity_max": round(float(he.max()), 1),
                  "top_entity_outflow_share": round(top_ent, 4),
                  "top_entities": {str(k): round(float(v), 4)
                                   for k, v in named.head(10).items()},
                  "caveat": "entity resolution merges labelled addresses only; lower bound"},
                 f"concentration_{token}.json")
    cm.log_metric(SCRIPT, token, "balance_hhi_main",
                  round(grid["all_holders|all"]["hhi"], 1),
                  "main = all holders")
    cm.log_metric(SCRIPT, token, "flow_hhi_entity",
                  round(float(he.mean()), 1))
    return grid


def main():
    lm = cm.load_labels()
    grids = {}
    for t in C.TOKENS:
        grids[t] = run(t, cm.build_entity_map(t, lm))

    cm.banner("both tokens (balance HHI)")
    print(f"  {'specification':<30}{'LINK':>10}{'UNI':>10}")
    for key in ("all_holders|all", "all_holders|excl_burn",
                "all_holders|excl_burn_issuer", "active|all"):
        a = grids.get("LINK", {}).get(key, {}).get("hhi", float("nan"))
        b = grids.get("UNI", {}).get(key, {}).get("hhi", float("nan"))
        print(f"  {key:<30}{a:>10.1f}{b:>10.1f}")
    ka = "all_holders|excl_burn_issuer"
    if "LINK" not in grids or "UNI" not in grids:
        return
    la, ua = grids["LINK"][ka]["hhi"], grids["UNI"][ka]["hhi"]
    print(f"\n  without issuer reserves the tokens converge: {la:.1f} vs {ua:.1f}"
          f" ({abs(la - ua) / max(la, ua) * 100:.0f}% apart)")
    print("    → most of the gap in the headline HHI is protocol-held supply")
    cm.banner("Done. Next: python 07_governance.py")


if __name__ == "__main__":
    main()
