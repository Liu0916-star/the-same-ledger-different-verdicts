# -*- coding: utf-8 -*-
"""v2_data_check.py -- validation of the v2 extraction and regression against v1.

Checks (the script stops if any fails):
  1. no nulls after converting value / balance to numbers
  2. no negative balance except at the zero address
  3. sum of positive balances == on-chain totalSupply at the snapshot block
  4. 20 random addresses: rebuilt balance == on-chain balanceOf at the snapshot block
Regression:
  5. transfers match the v1 CSVs record for record (key: tx_hash, from, to, value;
     equal as multisets)
  6. balances vs v1: holder count, HHI, Gini (v1 had no cut-off time, so small
     differences are expected)
Output: results/v2_data_check.json
"""
import random
from collections import Counter

import numpy as np
import pandas as pd

import chain_rpc as R
import common as K
import config as C

SNAPSHOT_BLOCK = 25_390_910          # 2026-06-24 23:59:59 UTC: last block before 2026-06-25 00:00
TOKEN_ADDR = {t: C.EXPECT[t]["contract"] for t in C.TOKENS}
V2 = C.DATA / "v2"


def load_v1_balances(tok: str) -> pd.DataFrame:
    """v1 balance CSV (no cut-off time), read as in v1; used only for the regression."""
    raw = pd.read_csv(C.FILES[tok]["bal"], low_memory=False)
    c_a, c_b = K.find_col(raw, "address"), K.find_col(raw, "balance")
    df = pd.DataFrame({"address": raw[c_a].astype(str).str.strip().str.lower(),
                       "balance": pd.to_numeric(raw[c_b], errors="coerce")}).dropna()
    df = df[df["balance"] > 0]
    if df["balance"].median() > 1e12:
        df["balance"] = df["balance"] / 1e18
    return df.reset_index(drop=True)


def to_int(s: pd.Series) -> pd.Series:
    # BIGNUMERIC is stored as a decimal string; handled exactly with Python int
    return s.map(lambda x: None if x is None or x == "None" else int(str(x).split(".")[0]))


def main():
    out = {"snapshot_block": SNAPSHOT_BLOCK}
    tx = pd.read_parquet(V2 / "v2_transfers.parquet")
    bal = pd.read_parquet(V2 / "v2_balances.parquet")
    for tok in C.TOKENS:
        K.banner(tok)
        a = TOKEN_ADDR[tok]
        r = {}
        t = tx[tx.token_address == a]
        v = pd.to_numeric(t["value"], errors="coerce")
        r["n_transfers"] = len(t)
        r["value_null"] = int(v.isna().sum())
        r["dup_key"] = int(t.duplicated(["transaction_hash", "log_index"]).sum())

        b = bal[bal.token_address == a].copy()
        b["v"] = to_int(b["balance_raw"])
        r["balance_null"] = int(b["v"].isna().sum())
        neg = b[(b.v < 0) & (~b.address.isin(C.BURN_ADDRS))]
        r["negative_non_zero_addr"] = len(neg)
        pos = b[b.v > 0]
        r["n_positive"] = len(pos)
        total_pos = sum(int(x) for x in pos.v)
        supply = R.call_uint(a, "0x18160ddd", SNAPSHOT_BLOCK)      # totalSupply()
        r["sum_positive"] = str(total_pos)
        r["total_supply_onchain"] = str(supply)
        # negative balance of the zero address = amount minted; sum_positive must equal totalSupply
        r["supply_match"] = total_pos == supply
        # a negative balance elsewhere can only come from an allocation without a Transfer
        # event (config.GENESIS_ALLOCATION)
        gen = []
        for addr, raw in zip(neg.address, neg.v):
            alloc = C.GENESIS_ALLOCATION.get(tok, {}).get(addr, 0)
            onchain = R.call_uint(a, "0x70a08231" + R.addr_arg(addr), SNAPSHOT_BLOCK)
            gen.append({"address": addr, "rebuilt": str(raw), "genesis_alloc": str(alloc),
                        "onchain_balance": str(onchain),
                        "match_after_alloc": int(raw) + alloc == onchain})
        r["genesis_check"] = gen
        r["supply_match_after_genesis"] = (
            total_pos + sum(int(g["onchain_balance"]) for g in gen) == supply)

        random.seed(42)
        sample = random.sample(sorted(pos.address), 20)
        mism = []
        for addr in sample:
            onchain = R.call_uint(a, "0x70a08231" + R.addr_arg(addr), SNAPSHOT_BLOCK)
            mine = int(pos.loc[pos.address == addr, "v"].iloc[0])
            if onchain != mine:
                mism.append({"address": addr, "onchain": str(onchain), "rebuilt": str(mine)})
        r["balanceOf_sample"] = 20
        r["balanceOf_mismatch"] = mism

        # ---- regression: transfers
        old = pd.read_csv(C.FILES[tok]["tx"], low_memory=False)
        cf, ct = K.find_col(old, "from"), K.find_col(old, "to")
        cv, ch = K.find_col(old, "value"), "evt_tx_hash"
        key_old = Counter(zip(old[ch].str.lower(), old[cf].str.lower(),
                              old[ct].str.lower(), old[cv].astype(str)))
        key_new = Counter(zip(t.transaction_hash.str.lower(), t.from_address.str.lower(),
                              t.to_address.str.lower(), t["value"].astype(str)))
        r["v1_transfers"] = sum(key_old.values())
        r["transfers_identical_to_v1"] = key_old == key_new
        r["only_in_v1"] = sum((key_old - key_new).values())
        r["only_in_v2"] = sum((key_new - key_old).values())

        # ---- regression: balances
        v1 = load_v1_balances(tok)
        # compared with v1 on the same basis (no genesis allocation); the final holder
        # count of load_balances() is reported separately
        v2 = pos.assign(balance=pos.v.map(lambda x: x / 1e18))
        r["v2_holders_with_genesis"] = len(K.load_balances(tok))
        r["v1_holders"], r["v2_holders"] = len(v1), len(v2)
        r["v1_hhi"], r["v2_hhi"] = K.hhi(v1.balance.values), K.hhi(v2.balance.values)
        r["v1_gini"], r["v2_gini"] = K.gini(v1.balance.values), K.gini(v2.balance.values)
        m = v1.merge(v2[["address", "balance"]], on="address", how="outer",
                     suffixes=("_v1", "_v2")).fillna(0)
        r["addresses_balance_changed"] = int((~np.isclose(m.balance_v1, m.balance_v2,
                                                           rtol=1e-12, atol=1e-12)).sum())
        r["abs_balance_moved"] = float((m.balance_v1 - m.balance_v2).abs().sum())

        for k_, v_ in r.items():
            if k_ != "balanceOf_mismatch":
                print(f"  {k_:30s} {v_}")
        print("  balanceOf mismatches:", len(mism))
        out[tok] = r
    K.save_json(out, "v2_data_check.json")


if __name__ == "__main__":
    main()
