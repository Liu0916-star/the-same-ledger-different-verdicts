# -*- coding: utf-8 -*-
"""v2_cleaning.py -- cleaning report (airdrop rule + zero-value transfers), same rule for both tokens.

Output results/cleaning_<TOKEN>.json:
  - what the main specification removes (mint/burn, zero-value, airdrop: senders,
    transfers, amount, addresses)
  - sensitivity: N in AIRDROP_N_GRID (main threshold), threshold in
    AIRDROP_AMT_GRID (main N)
  - weekly transfers / addresses before and after cleaning; outlier-week detection
  - holders that are active only because they received the airdrop
  - LINK: flagged senders vs the 38 archived contracts + 13 funders of v1
Output verification/airdrop_senders_<TOKEN>.csv: flagged senders (for manual checking)
"""
import json

import pandas as pd

import common as K
import config as C


def weekly(tx):
    a = pd.concat([tx[["week", "from"]].rename(columns={"from": "a"}),
                   tx[["week", "to"]].rename(columns={"to": "a"})])
    return pd.DataFrame({"n_tx": tx.groupby("week").size(),
                         "n_addr": a.groupby("week")["a"].nunique()})


def main():
    for tok in C.TOKENS:
        K.banner(f"{tok} cleaning")
        raw = K.load_transfers_raw(tok)
        clean, st = K.clean_transfers(raw)
        out = {k: v for k, v in st.items() if k != "airdrop_senders"}

        # two contrasts: without the airdrop rule, without the zero-value rule (one switch each)
        _, st_noair = K.clean_transfers(raw, airdrop=False)
        _, st_nozero = K.clean_transfers(raw, drop_zero=False)
        out["active_without_airdrop_rule"] = st_noair["active_clean"]
        out["active_without_zero_rule"] = st_nozero["active_clean"]

        sens = []
        for n in C.AIRDROP_N_GRID:
            _, s = K.clean_transfers(raw, n=n)
            sens.append({"N": n, "max_amt": C.AIRDROP_MAX_AMT,
                         "senders": s["n_airdrop_senders"],
                         "transfers": s["n_airdrop_transfers"],
                         "active_clean": s["active_clean"]})
        for amt in C.AIRDROP_AMT_GRID:
            if amt == C.AIRDROP_MAX_AMT:
                continue
            _, s = K.clean_transfers(raw, max_amt=amt)
            sens.append({"N": C.AIRDROP_N, "max_amt": amt,
                         "senders": s["n_airdrop_senders"],
                         "transfers": s["n_airdrop_transfers"],
                         "active_clean": s["active_clean"]})
        out["sensitivity"] = sens
        # senders added at N=100 relative to the main N: how many weeks their small transfers span
        main_s = set(st["airdrop_senders"])
        s100 = set(K.clean_transfers(raw, n=min(C.AIRDROP_N_GRID))[1]["airdrop_senders"])
        extra = s100 - main_s
        base_ = K.clean_transfers(raw, airdrop=False)[0]
        ex = base_[base_["from"].isin(extra) & (base_["amt"] > 0) & (base_["amt"] < C.AIRDROP_MAX_AMT)]
        out["extra_senders_lowest_N"] = {"n": len(extra), "n_weeks": int(ex["week"].nunique()),
                                         "n_transfers": int(len(ex)),
                                         "max_week_share": float(ex["week"].value_counts(normalize=True).max()) if len(ex) else None}
        for r in sens:
            print(f"    N>{r['N']:>5} amt<{r['max_amt']:<5} senders {r['senders']:>3} "
                  f"transfers {r['transfers']:>8,} active {r['active_clean']:,}")

        before = weekly(raw[~(raw["from"].isin(C.BURN_ADDRS) | raw["to"].isin(C.BURN_ADDRS))])
        after = weekly(clean)
        wk = before.join(after, lsuffix="_raw", rsuffix="_clean")
        out["weekly"] = wk.reset_index().to_dict(orient="records")
        out["outlier_windows_raw"] = K.find_outlier_windows(
            raw[~(raw["from"].isin(C.BURN_ADDRS) | raw["to"].isin(C.BURN_ADDRS))])
        out["outlier_windows_clean"] = K.find_outlier_windows(clean)
        print(wk.to_string())
        print("    outlier weeks before cleaning", out["outlier_windows_raw"],
              "after", out["outlier_windows_clean"])

        # list of flagged senders
        senders = st["airdrop_senders"]
        sm = raw[raw["from"].isin(senders) & (raw["amt"] > 0)
                 & (raw["amt"] < C.AIRDROP_MAX_AMT)]
        lst = sm.groupby("from").agg(
            n_small=("to", "size"), n_receivers=("to", "nunique"),
            first=("ts", "min"), last=("ts", "max"),
            median_amt=("amt", "median")).reset_index().rename(columns={"from": "address"})
        # holders active only because they received the airdrop: how many, how large
        # their balances, how many hold only dust
        bal = K.load_balances(tok)
        only = set(K.active_addresses(base_)) - set(K.active_addresses(clean))
        h = bal[bal["address"].isin(only)]
        out["airdrop_only_holders"] = {"n_addresses": len(only), "n_holders": int(len(h)),
                                       "median_balance": float(h["balance"].median()) if len(h) else None,
                                       "n_below_dust_floor": int((h["balance"] < C.DUST_FLOOR).sum())}
        print("    holders active only through the airdrop", out["airdrop_only_holders"])
        if tok == "LINK":
            arch = json.load(open(C.ROOT / "verification" / "eventstudy_w7_phishing_addrs.json"))
            c38 = {a.lower() for a in arch["script_contracts_each_10000txns"]}
            f13 = {a.lower() for a in arch["upstream_funders"]}
            lst["in_appendix_C_38"] = lst["address"].isin(c38)
            lst["in_appendix_C_funders"] = lst["address"].isin(f13)
            out["archived_38_hit"] = int(lst["in_appendix_C_38"].sum())
            out["archived_38_missed"] = sorted(c38 - set(senders))
            out["archived_funders_hit"] = int(lst["in_appendix_C_funders"].sum())
            out["senders_not_in_archive"] = int((~lst["in_appendix_C_38"]
                                                 & ~lst["in_appendix_C_funders"]).sum())
            # exact number of transfers by the 38 archived contracts in the window
            # (v1 Appendix C said "at least 380,000")
            out["archived_38_exact_transfers"] = int(raw["from"].isin(c38).sum())
            out["archived_38_exact_small_transfers"] = int(
                (raw["from"].isin(c38) & (raw["amt"] > 0)
                 & (raw["amt"] < C.AIRDROP_MAX_AMT)).sum())
            print(f"    archived 38 contracts: hit {out['archived_38_hit']}, missed "
                  f"{len(out['archived_38_missed'])}; senders not in the archive "
                  f"{out['senders_not_in_archive']}")
            print(f"    exact transfers by the 38 contracts {out['archived_38_exact_transfers']:,}")
        lst = lst.sort_values("n_receivers", ascending=False)
        lst.to_csv(C.ROOT / "verification" / f"airdrop_senders_{tok}.csv", index=False)
        print(f"    flagged senders → verification/airdrop_senders_{tok}.csv ({len(lst)})")
        K.save_json(out, f"cleaning_{tok}.json")


if __name__ == "__main__":
    main()
