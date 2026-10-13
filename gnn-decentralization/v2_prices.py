# -*- coding: utf-8 -*-
"""v2_prices.py -- Chainlink prices at the snapshot block (for the USD value floor).

Reads latestRoundData() of each feed in config.PRICE_FEEDS at SNAPSHOT_BLOCK and
checks description(). Output: results/prices_snapshot.json.
"""
from eth_abi import decode

import chain_rpc as R
import common as cm
import config as C


def main():
    out = {}
    for t, (addr, desc_expect) in C.PRICE_FEEDS.items():
        desc = decode(["string"], bytes.fromhex(R.eth_call(addr, "0x7284e416", C.SNAPSHOT_BLOCK)[2:]))[0]
        assert desc == desc_expect, (t, desc)
        dec = R.call_uint(addr, "0x313ce567", C.SNAPSHOT_BLOCK)
        rd = decode(["uint80", "int256", "uint256", "uint256", "uint80"],
                    bytes.fromhex(R.eth_call(addr, "0xfeaf968c", C.SNAPSHOT_BLOCK)[2:]))
        out[t] = {"feed": addr, "description": desc, "round_id": str(rd[0]), "answer_raw": str(rd[1]), "decimals": dec,
                  "price_usd": rd[1] / 10 ** dec,
                  "updated_at": int(rd[3]), "block": C.SNAPSHOT_BLOCK}
        print(t, out[t])
    cm.save_json(out, "prices_snapshot.json")


if __name__ == "__main__":
    main()
