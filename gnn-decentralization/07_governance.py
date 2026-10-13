# -*- coding: utf-8 -*-
"""
07_governance.py -- the rule layer (UNI): who can change the rules

    ownership layer  who holds          Gini + balance HHI    (06_concentration.py)
    routing layer    who moves tokens   flow HHI + brokers    (03 / 05)
    rule layer       who sets the rules Nakamoto coefficient  <- this script

The main measure in v2 is delegated votes: Uniswap's proposal threshold (1M) and
quorum (40M votes in favour) both count getPriorVotes, and undelegated balances
carry no voting weight. Votes come from the on-chain state at the snapshot block
read by sql/fetch_uni_delegation.py (checked delegate by delegate: votes == summed
balance delegated to it). The balance-based measure of v1 is kept as comparison
rows; it is one more case of the specification deciding the verdict.

Output results/governance_UNI.json:
  1. specifications: balances (three variants) vs delegated votes
  2. rule layer x routing layer: proposal-eligible delegates (votes >= 1M) vs the
     top-N senders by mean weekly outflow
  3. revocable share (routing flow directly controlled by governance)
  4. fee burns in the window (the UNIfication mechanism, see
     verification/uni_fee_burns.md)

Usage: python 07_governance.py
"""
import numpy as np
import pandas as pd

import config as C
import common as cm

SCRIPT = "07_governance"
ZERO = "0x0000000000000000000000000000000000000000"


def is_custodial(entity: str) -> bool:
    e = str(entity).lower()
    return any(h in e for h in C.GOV_CUSTODIAL_HINTS)


def load_votes() -> pd.DataFrame:
    v = pd.read_parquet(C.DATA / "v2" / "uni_delegate_votes.parquet")
    if not v["match"].all():
        raise SystemExit("[X] delegated votes do not equal delegated balances; rerun fetch_uni_delegation.py")
    v["votes"] = v["votes_raw"].map(lambda x: int(x) / 1e18)
    return v[v["votes"] > 0].sort_values("votes", ascending=False).reset_index(drop=True)


def describe(values, tot_supply):
    v = np.sort(np.asarray(values, dtype=float))[::-1]
    return {"n": int(len(v)), "total": float(v.sum()),
            "share_of_supply": round(float(v.sum() / tot_supply), 4),
            "nakamoto_quorum": cm.nakamoto_absolute(v, C.GOV_QUORUM),
            "nakamoto_half": cm.nakamoto(v, 0.5),
            "n_each_above_threshold": int((v >= C.GOV_PROPOSAL_THRESHOLD).sum()),
            "share_above_threshold": round(float(v[v >= C.GOV_PROPOSAL_THRESHOLD].sum()
                                                 / max(v.sum(), 1e-12)), 4),
            "top1_share": round(float(v[0] / v.sum()), 4) if len(v) else None,
            "top10_share": round(float(v[:10].sum() / v.sum()), 4) if len(v) else None,
            "hhi": round(cm.hhi(v), 1), "gini": round(cm.gini(v), 4)}


def main():
    token = "UNI"
    cm.banner("07 · rule layer, UNI")
    bal = cm.load_balances(token)
    tx = cm.load_transfers(token)
    lm = cm.load_labels()
    emap = cm.build_entity_map(token, lm, verbose=False)
    tot = 1e9                                   # UNI totalSupply (checked in v2_data_check)
    votes = load_votes()

    # ---------- 1. specifications ----------
    cm.banner("1. specifications: balances vs delegated votes", "-")
    ent = bal.assign(k=cm.entity_key(bal["address"], emap))
    cust = ent["k"].map(is_custodial).fillna(False)
    specs = {
        "balance: all holders": bal["balance"].values,
        "balance: excl. non-voting": bal.loc[~bal["address"].isin(C.GOV_NON_VOTING), "balance"].values,
        "balance: excl. non-voting & custodial":
            ent.loc[~ent["address"].isin(C.GOV_NON_VOTING) & ~cust, "balance"].values,
        "delegated votes (main)": votes["votes"].values,
    }
    # balance rows: which addresses reach the quorum (named row by row in Table 6)
    spec_frames = {
        "balance: all holders": bal,
        "balance: excl. non-voting": bal[~bal["address"].isin(C.GOV_NON_VOTING)],
        "balance: excl. non-voting & custodial": ent[~ent["address"].isin(C.GOV_NON_VOTING) & ~cust],
    }
    rec = {"proposal_threshold": C.GOV_PROPOSAL_THRESHOLD, "quorum": C.GOV_QUORUM,
           "snapshot_block": C.SNAPSHOT_BLOCK, "specs": {}}
    print(f"  threshold {C.GOV_PROPOSAL_THRESHOLD:,} | quorum {C.GOV_QUORUM:,} (both in delegated votes)")
    print(f"  {'specification':<40}{'n':>9}{'supply':>8}{'N(40M)':>8}{'N(50%)':>8}{'≥1M':>6}{'HHI':>8}")
    for nm, v in specs.items():
        d = describe(v, tot)
        rec["specs"][nm] = d
        print(f"  {nm:<40}{d['n']:>9,}{d['share_of_supply'] * 100:>7.1f}%"
              f"{d['nakamoto_quorum']:>8}{d['nakamoto_half']:>8}"
              f"{d['n_each_above_threshold']:>6}{d['hhi']:>8.0f}")

    # top 10 delegates: identity and votes
    def ident(a):
        if a in C.MANUAL_ENTITIES:
            return C.MANUAL_ENTITIES[a]
        return lm.get(a, {}).get("name", "") or emap.get(a, "")
    vmap0 = dict(zip(votes["delegate"], votes["votes"]))
    for nm, fr in spec_frames.items():
        top_ = fr.sort_values("balance", ascending=False).head(rec["specs"][nm]["nakamoto_quorum"])
        rec["specs"][nm]["quorum_members"] = [
            {"address": a, "balance": round(b), "identity": ident(a), "own_votes": round(vmap0.get(a, 0.0))}
            for a, b in zip(top_["address"], top_["balance"])]
        print(f"  {nm} quorum members", [(m["address"][:10], m["identity"] or "?") for m in rec["specs"][nm]["quorum_members"]])
    top = votes.head(10).assign(identity=lambda d: d["delegate"].map(ident),
                                share_of_votes=lambda d: d["votes"] / votes["votes"].sum())
    rec["top_delegates"] = [{"delegate": r.delegate, "votes": round(r.votes),
                             "share_of_delegated": round(r.share_of_votes, 4),
                             "label_snapshot_name": r.identity} for r in top.itertuples()]
    print("\n  top 10 delegates")
    for r in top.itertuples():
        print(f"    {r.delegate}  {r.votes:>14,.0f}  {r.share_of_votes * 100:5.2f}%  {r.identity}")

    # who are the two addresses behind v1's balance-based "Nakamoto = 2"
    nv = bal[~bal["address"].isin(C.GOV_NON_VOTING)].sort_values("balance", ascending=False).head(2)
    vmap = dict(zip(votes["delegate"], votes["votes"]))
    deleg = pd.read_parquet(C.DATA / "v2" / "uni_delegation_snapshot.parquet")
    dmap = dict(zip(deleg["holder"], deleg["delegate"]))
    rec["balance_spec_top2"] = [{"address": a, "balance": round(b), "identity": ident(a),
                                 "delegates_to": dmap.get(a, ZERO),
                                 "own_votes": round(vmap.get(a, 0.0))}
                                for a, b in zip(nv["address"], nv["balance"])]
    print("\n  two largest balances (non-voting addresses excluded)")
    for r in rec["balance_spec_top2"]:
        print(f"    {r['address']}  {r['balance']:>14,}  {r['identity'] or '?'}"
              f"  delegates to {r['delegates_to']}  own votes {r['own_votes']:,}")

    # ---------- 2. rule layer x routing layer ----------
    cm.banner("2. rule layer x routing layer", "-")
    elig = set(votes.loc[votes["votes"] >= C.GOV_PROPOSAL_THRESHOLD, "delegate"])
    movers = set(tx["from"]) | set(tx["to"])
    inactive = len(elig - movers)
    wk = tx.groupby("week")["amt"].sum()
    g = tx.groupby(["week", "from"])["amt"].sum().reset_index()
    g["sh"] = g["amt"] / g["week"].map(wk)
    outflow = (g.groupby("from")["sh"].sum() / tx["week"].nunique()).sort_values(ascending=False)
    strat = {"n_eligible": len(elig), "eligible_inactive": inactive,
             "eligible_inactive_share": round(inactive / max(len(elig), 1), 4)}
    print(f"  proposal-eligible (votes >= 1M): {len(elig)}, of which {inactive} sent or received no UNI in the window")
    for N in (10, 50, 100):
        topN = list(outflow.head(N).index)
        ov = [a for a in topN if a in elig]
        sub = bal[bal["address"].isin(topN)]
        delegated = sub["address"].map(dmap).fillna(ZERO) != ZERO
        strat[f"top{N}"] = {
            "overlap": len(ov), "outflow_share": round(float(outflow.head(N).sum()), 4),
            "median_votes": float(np.median([vmap.get(a, 0.0) for a in topN])),
            "own_balance_delegated_share": round(float(
                sub.loc[delegated, "balance"].sum() / max(sub["balance"].sum(), 1e-12)), 4)}
        print(f"    top{N:<4} senders: eligible {len(ov):>3} | median votes "
              f"{strat[f'top{N}']['median_votes']:,.0f} | own balance delegated "
              f"{strat[f'top{N}']['own_balance_delegated_share'] * 100:.1f}%")
    bp = C.RESULTS / f"hidden_brokers_{token}.csv"
    if bp.exists():
        br = set(pd.read_csv(bp)["address"].str.lower())
        strat["brokers_overlap_circular"] = len(br & elig)
    rec["stratification"] = strat

    # ---------- 3. revocable share ----------
    cm.banner("3. revocable share", "-")
    gov_direct = set(C.ISSUER_RESERVES.get(token, ()))
    l1 = float(outflow[outflow.index.isin(gov_direct)].sum())
    l2 = float(outflow[[str(emap.get(a, "")).lower().startswith("uniswap") and a not in gov_direct
                        for a in outflow.index]].sum())
    l3 = float(outflow[~outflow.index.isin(emap)].sum())
    rec["revocable_share"] = {"L1_governance_direct": round(l1, 4), "L2_protocol_owned": round(l2, 4),
                              "L3_unidentified": round(l3, 4)}
    print(f"    governance-controlled {l1 * 100:.2f}% | other Uniswap contracts {l2 * 100:.2f}% | unidentified {l3 * 100:.1f}%")

    # ---------- 4. fee burns ----------
    raw = cm.load_transfers_raw(token)
    b = raw[raw["to"] == C.DEAD_ADDR]
    by_lot = b.assign(lot=b["amt"].round(4)).groupby("lot")["from"].agg(["size", "nunique"])
    rec["fee_burns_window"] = {"n": int(len(b)), "total_uni": round(float(b["amt"].sum()), 4),
                               "lots": {str(k): {"n": int(r["size"]), "senders": int(r["nunique"]),
                                                 "via_bridges": int(b.loc[b["amt"].round(4) == k, "from"]
                                                                    .isin(C.UNI_FEE_BRIDGES).sum())}
                                        for k, r in by_lot.iterrows()},
                               "amount_counts": {str(k): int(v) for k, v in
                                                 b["amt"].round(4).value_counts().items()},
                               "dead_balance_share": round(float(
                                   bal.loc[bal["address"] == C.DEAD_ADDR, "balance"].sum() / tot), 4),
                               "note": "verification/uni_fee_burns.md"}
    print(f"\n  burns in the window: {len(b):,} records, {b['amt'].sum():,.0f} UNI; "
          f"the burn address holds {rec['fee_burns_window']['dead_balance_share'] * 100:.2f}%")

    cm.save_json({"token": token, **rec}, f"governance_{token}.json")
    cm.save_json({"token": "LINK", "applicable": False,
                  "reason": "no token-weighted governance"}, "governance_LINK.json")
    d = rec["specs"]["delegated votes (main)"]
    cm.log_metric(SCRIPT, token, "nakamoto_quorum_delegated", d["nakamoto_quorum"])
    cm.log_metric(SCRIPT, token, "n_delegates_above_threshold", d["n_each_above_threshold"])


if __name__ == "__main__":
    main()
