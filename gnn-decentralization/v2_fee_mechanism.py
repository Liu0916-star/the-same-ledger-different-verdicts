# -*- coding: utf-8 -*-
"""v2_fee_mechanism.py -- on-chain state of the UNIfication fee mechanism.

Ethereum: owner() and releaser() of the TokenJar (0xf385...f85) and the releaser's
threshold(), at the first and last block of the window.
L2s: the TokenJar and releaser listed on Uniswap's deployment page (archived copy in
verification/raw/uniswap_protocol_fee_deployments_2026-10-12.html). Identification =
address on the page + on-chain check that TokenJar.releaser() equals the listed
releaser; then threshold() is read. Reads use the L2 block closest to the end of the
window; if a public node has no historical state, the script falls back to "latest"
and records that.
Output: results/fee_mechanism.json and verification/uni_l2_firepits.csv.
"""
from eth_hash.auto import keccak

import pandas as pd

import chain_rpc as R
import common as cm
import config as C

TOKEN_JAR = "0xf38521f130fccf29db1961597bc5d2b60f995f85"
WINDOW_FIRST_BLOCK = 24_738_010
# Addresses listed on the deployment page (read 2026-10-12):
# chain -> (public RPC, TokenJar, releaser, releaser type shown on the page)
L2 = {
    "Base": ("https://mainnet.base.org", "0x9bD25e67bF390437C8fAF480AC735a27BcF6168c",
             "0xFf77c0ED0B6b13A20446969107E5867abc46f53a", "OptimismBridgedResourceFirepit"),
    "Optimism": ("https://mainnet.optimism.io", "0xb13285DF724ea75f3f1E9912010B7e491dCd5EE3",
                 "0x94460443Ca27FFC1baeCa61165fde18346C91AbD", "OptimismBridgedResourceFirepit"),
    "Arbitrum": ("https://arb1.arbitrum.io/rpc", "0x95E337C5B155385945D407f5396387D0c2a3A263",
                 "0xB8018422bcE25D82E70cB98FdA96a4f502D89427", "Releaser (type not stated)"),
    "Unichain": ("https://mainnet.unichain.org", "0xD576BDF6b560079a4c204f7644e556DbB19140b5",
                 "0xe0A780E9105aC10Ee304448224Eb4A2b11A77eeB", "OptimismBridgedResourceFirepit"),
}


def sel(sig):
    return "0x" + keccak(sig.encode()).hex()[:8]


def main():
    out = {"token_jar": TOKEN_JAR}
    for name, b in (("window_start", WINDOW_FIRST_BLOCK), ("window_end", C.SNAPSHOT_BLOCK)):
        rel = "0x" + R.eth_call(TOKEN_JAR, sel("releaser()"), b)[-40:]
        owner = "0x" + R.eth_call(TOKEN_JAR, sel("owner()"), b)[-40:]
        out[name] = {"block": b, "releaser": rel, "owner": owner,
                     "threshold_uni": R.call_uint(rel, sel("threshold()"), b) / 1e18}
        print(name, out[name])
    ts_end = R.block_timestamp(C.SNAPSHOT_BLOCK)
    rows = []
    for chain, (url, jar, rel_listed, typ) in L2.items():
        b = R.block_at_time(ts_end, url)
        row = {"chain": chain, "token_jar": jar.lower(), "releaser_listed": rel_listed.lower(),
               "releaser_type_on_page": typ, "rpc": url, "window_end_block": b}
        for at in (b, "latest"):
            try:
                rel = "0x" + R.eth_call(jar, sel("releaser()"), at, url)[-40:]
                thr = R.call_uint(rel, sel("threshold()"), at, url) / 1e18
            except Exception as e:      # public node without historical state
                row[f"error_{'end' if at == b else 'latest'}"] = str(e)[:120]
                continue
            row.update({"read_at": "window_end" if at == b else "latest", "releaser_onchain": rel,
                        "releaser_matches_page": rel == rel_listed.lower(), "threshold_uni": thr})
            break
        print(row)
        rows.append(row)
    out["l2"] = rows
    pd.DataFrame(rows).to_csv(C.ROOT / "verification" / "uni_l2_firepits.csv", index=False)
    cm.save_json(out, "fee_mechanism.json")


if __name__ == "__main__":
    main()
