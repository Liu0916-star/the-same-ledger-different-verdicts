# -*- coding: utf-8 -*-
"""fetch_uni_delegation.py -- UNI delegation state at the snapshot (end of block B = SNAPSHOT_BLOCK).

Instead of replaying historical events (public RPCs do not serve historical
eth_getLogs; a BigQuery logs scan is about 2.85 TB), it reads the state directly,
which is complete and free:
  1. delegates(holder) @ B for every address with a positive balance -> delegation
  2. getPriorVotes(d, B) @ B+1 for every delegate that appears        -> votes
  3. check: each delegate's votes == summed balance of its delegators (exact integers)
     (the Compound/UNI invariant: votes come only from delegators' balances and
     move with every transfer)
Calls are batched through Multicall3 (0xcA11...CA11).
Output: data/v2/uni_delegation_snapshot.parquet (holder, balance_raw, delegate)
     data/v2/uni_delegate_votes.parquet（delegate, votes_raw, sum_delegated_raw, match）
"""
import sys
from pathlib import Path

import pandas as pd
from eth_abi import decode, encode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import chain_rpc as R          # noqa: E402
import config as C             # noqa: E402

UNI = C.EXPECT["UNI"]["contract"]
MC3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
B = C.SNAPSHOT_BLOCK
ZERO = "0x0000000000000000000000000000000000000000"
BATCH = 1_000
OUT = C.DATA / "v2"


def multicall(calls, block):
    data = "0x82ad56cb" + encode(["(address,bool,bytes)[]"], [calls]).hex()
    res = decode(["(bool,bytes)[]"], bytes.fromhex(R.eth_call(MC3, data, block)[2:]))[0]
    if not all(ok for ok, _ in res):
        raise RuntimeError("multicall sub-call failed")
    return [r for _, r in res]


def main():
    raw = pd.read_parquet(C.V2_BALANCES)
    raw = raw[(raw["token_address"] == UNI)]
    hold = pd.DataFrame({"holder": raw["address"].str.lower(),
                         "balance_raw": raw["balance_raw"].map(lambda x: int(str(x).split(".")[0]))})
    hold = hold[(hold["balance_raw"] > 0)].reset_index(drop=True)
    print(f"holders {len(hold):,}, block {B:,}")

    sel = bytes.fromhex("587cde1e")                     # delegates(address)
    dl = []
    for i in range(0, len(hold), BATCH):
        addrs = list(hold["holder"].iloc[i:i + BATCH])
        out = multicall([(UNI, True, sel + encode(["address"], [a])) for a in addrs], B)
        dl += [decode(["address"], r)[0].lower() for r in out]
        if (i // BATCH) % 50 == 0:
            print(f"  delegates {i + len(addrs):,}/{len(hold):,}", flush=True)
    hold["delegate"] = dl
    hold.assign(balance_raw=hold["balance_raw"].astype(str)) \
        .to_parquet(OUT / "uni_delegation_snapshot.parquet", index=False)

    dd = hold[hold["delegate"] != ZERO].groupby("delegate")["balance_raw"] \
        .apply(lambda s: sum(int(x) for x in s)).rename("sum_delegated_raw").reset_index()
    sel = bytes.fromhex("782d6fe1")                     # getPriorVotes(address,uint256)
    votes = []
    for i in range(0, len(dd), BATCH):
        addrs = list(dd["delegate"].iloc[i:i + BATCH])
        out = multicall([(UNI, True, sel + encode(["address", "uint256"], [a, B])) for a in addrs], B + 1)
        votes += [decode(["uint96"], r)[0] for r in out]
    dd["votes_raw"] = votes
    dd["match"] = [int(a) == int(b) for a, b in zip(dd["votes_raw"], dd["sum_delegated_raw"])]
    n_bad = int((~dd["match"]).sum())
    print(f"delegates {len(dd):,}; votes != delegated balance for {n_bad}")
    tot_supply = 10 ** 27
    deleg = sum(int(x) for x in dd["sum_delegated_raw"])
    print(f"delegated balance as share of supply {deleg / tot_supply * 100:.2f}%")
    dd.assign(votes_raw=dd["votes_raw"].astype(str),
              sum_delegated_raw=dd["sum_delegated_raw"].astype(str)) \
        .to_parquet(OUT / "uni_delegate_votes.parquet", index=False)
    if n_bad:
        raise SystemExit("[X] invariant violated; check the snapshot block and balances")


if __name__ == "__main__":
    main()
