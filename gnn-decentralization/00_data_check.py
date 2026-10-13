# -*- coding: utf-8 -*-
"""
00_data_check.py -- gate before running the pipeline (v2 data)

Confirms that the label snapshot is present, that transfers and balances match the
expected counts, that no record falls outside the window and that no outlier week
remains after cleaning. Resolve every [X] first. On-chain checks of the data and
the regression against v1 are in v2_data_check.py; the full cleaning report is in
v2_cleaning.py.

Usage: python 00_data_check.py
"""
import pandas as pd

import config as C
import common as cm

SCRIPT = "00_data_check"


def main():
    cm.banner("00 · data check (v2)")
    all_ok = True

    print("\n[label snapshot]")
    lm = cm.load_labels()
    md5 = cm.file_md5(C.LABEL_SNAPSHOT)
    print(f"    [OK] {C.LABEL_SNAPSHOT.name} · {len(lm):,} entries after normalisation · md5 {md5}")

    for p in (C.V2_TRANSFERS, C.V2_BALANCES):
        print(f"    {p.name}  {p.stat().st_size / 1e6:8.1f} MB  md5 {cm.file_md5(p)}")

    for token in C.TOKENS:
        cm.banner(token, "-")
        exp = C.EXPECT[token]
        raw = cm.load_transfers_raw(token)
        all_ok &= cm.check("raw transfers", len(raw), exp["n_tx"])
        t0, t1 = pd.Timestamp(C.WINDOW_START), pd.Timestamp(C.WINDOW_END)
        oob = int(((raw["ts"] < t0) | (raw["ts"] >= t1)).sum())
        all_ok &= cm.check("outside window", oob, 0)
        all_ok &= cm.check("weekly windows", int(raw["week"].nunique()), C.N_WINDOWS)

        tx, st = cm.clean_transfers(raw)
        print(f"    cleaning: mint/burn {st['n_mint_burn']:,} | zero-value {st['n_zero_value']:,} | "
              f"airdrop {st['n_airdrop_transfers']:,} transfers / {st['n_airdrop_senders']} senders")
        all_ok &= cm.check("active addresses after cleaning", st["active_clean"], exp["n_active"])
        out = cm.find_outlier_windows(tx)
        all_ok &= cm.check("outlier weeks after cleaning", len(out), 0)

        bal = cm.load_balances(token)
        all_ok &= cm.check("addresses with positive balance", len(bal), exp["n_holders"])
        tot = bal["balance"].sum()
        burned = bal.loc[bal["address"].isin(C.BURN_ADDRS), "balance"].sum()
        iss = C.ISSUER_RESERVES.get(token, frozenset())
        reserve = bal.loc[bal["address"].isin(iss), "balance"].sum()
        print(f"    total {tot:,.2f} | burn address {burned / tot * 100:.2f}% | "
              f"issuer reserves {reserve / tot * 100:.2f}% ({len(iss)} addresses)")

        # repeated ordered pairs (why edge weights must be summed)
        agg = tx.groupby(["from", "to"], as_index=False)["amt"].sum()
        dup_rows = len(tx) - len(agg)
        print(f"    repeated ordered pairs {dup_rows:,} rows ({dup_rows / len(tx) * 100:.1f}%)")

        cm.log_metric(SCRIPT, token, "n_transfers_raw", len(raw))
        cm.log_metric(SCRIPT, token, "n_transfers_clean", len(tx))
        cm.log_metric(SCRIPT, token, "n_active_clean", st["active_clean"])
        cm.log_metric(SCRIPT, token, "n_holders", len(bal))

    cm.banner("[OK] all checks passed" if all_ok
              else "[X] some checks failed; resolve them before continuing")


if __name__ == "__main__":
    main()
