# -*- coding: utf-8 -*-
"""chain_rpc.py -- read-only Ethereum JSON-RPC calls (eth_call at historical blocks).

Used for governance parameters (proposal threshold, quorum), delegated votes
(getPriorVotes), totalSupply / balanceOf spot checks, prices and fee contracts.
Read-only: nothing is signed and no transaction is sent.
"""
import time
import requests

RPC_URL = "https://eth.drpc.org"      # public node with archive (historical) state


def _post(method, params, retries=5, url=RPC_URL):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    for i in range(retries):
        try:
            r = requests.post(url, json=body, timeout=60)
            j = r.json()
            if "error" in j:
                raise RuntimeError(j["error"])
            return j["result"]
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(2 ** i)


def eth_call(to: str, data: str, block, url=RPC_URL) -> str:
    """block is an int or "latest"; url selects another chain (L2)."""
    return _post("eth_call", [{"to": to, "data": data}, block if isinstance(block, str) else hex(block)], url=url)


def call_uint(to: str, data: str, block, url=RPC_URL) -> int:
    return int(eth_call(to, data, block, url), 16)


def block_timestamp(block: int, url=RPC_URL) -> int:
    return int(_post("eth_getBlockByNumber", [hex(block), False], url=url)["timestamp"], 16)


def block_at_time(ts: int, url=RPC_URL) -> int:
    """Last block with timestamp <= ts (binary search)."""
    lo, hi = 0, int(_post("eth_blockNumber", [], url=url), 16)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if block_timestamp(mid, url) <= ts:
            lo = mid
        else:
            hi = mid - 1
    return lo


def addr_arg(addr: str) -> str:
    return addr.lower().replace("0x", "").rjust(64, "0")


def uint_arg(n: int) -> str:
    return hex(n)[2:].rjust(64, "0")
