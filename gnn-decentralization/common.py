# -*- coding: utf-8 -*-
"""
common.py -- the single source of truth

All loading, metrics, graph construction, label handling and GraphSAGE training
live here; scripts do not reimplement them.

Three hard rules, one for each known pitfall:
  1. build_graph() is the only way to build a graph, and it sums edge weights.
     v16 had 13 calls to from_pandas_edgelist; because a DiGraph keeps only the
     last edge of a pair, each of them lost 48.8% (LINK) / 59.6% (UNI) of the
     transferred amount.
  2. Columns are found by name, never by position (iloc).
     v16 was caught twice: the UNI balance file had 2 columns and LINK 4, so
     iloc[:, 1] read total_received on LINK and counted 3,918,660 addresses
     (true value then 885,011).
  3. load_labels() reads the local snapshot only and refuses to go online:
     the upstream compilation drifts, and the is_core anchors would change silently.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd

import config as C

# ============================================================ column lookup
_CANDIDATES = {
    "from": ["from", "from_address", "sender", "evt_from", "src", "from_addr"],
    "to": ["to", "to_address", "receiver", "recipient", "evt_to", "dst"],
    "value": ["value", "value_link", "value_uni", "amount", "raw_value",
              "quantity", "val"],
    "time": ["block_timestamp", "evt_block_time", "timestamp", "block_time",
             "evt_block_timestamp", "time", "date"],
    "address": ["address", "addr", "holder", "wallet", "account", "owner"],
    "balance": ["balance", "balance_link", "balance_uni", "token_balance"],
}


def find_col(df: pd.DataFrame, role: str) -> str:
    """Find a column by name. If none matches, raise and show the real column
    names -- never fall back to iloc silently."""
    norm = {str(c).strip().lower().lstrip("\ufeff"): c for c in df.columns}
    for cand in _CANDIDATES[role]:
        if cand in norm:
            return norm[cand]
    raise KeyError(
        f"no column for '{role}'. Columns: {list(df.columns)}\n"
        f"candidates: {_CANDIDATES[role]}\n"
        "(if this is a new spelling, add it to common._CANDIDATES; do not use iloc)"
    )


def _norm_addr(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower()


# ============================================================ loading
_TX_CACHE: dict = {}


def load_transfers_raw(token: str) -> pd.DataFrame:
    """All transfers of the v2 extraction, uncleaned. Returns from / to / amt / ts / week.

    Includes mint/burn records and zero-value transfers. Only the cleaning code,
    the case study of Section 7 and the raw-data rows of the appendix use it
    directly; every other analysis uses load_transfers().
    """
    if token not in _TX_CACHE:
        raw = pd.read_parquet(C.V2_TRANSFERS)
        raw = raw[raw["token_address"] == C.EXPECT[token]["contract"]]
        df = pd.DataFrame({
            "from": _norm_addr(raw["from_address"]),
            "to": _norm_addr(raw["to_address"]),
            "amt": pd.to_numeric(raw["value"], errors="raise") / 1e18,
            "ts": pd.to_datetime(raw["block_timestamp"], utc=True),
            "tx_hash": raw["transaction_hash"].str.lower(),
            "log_index": raw["log_index"].astype(int),
        })
        t0 = pd.Timestamp(C.WINDOW_START)
        df["week"] = ((df["ts"] - t0).dt.days // C.WINDOW_DAYS).astype(int)
        _TX_CACHE[token] = df.sort_values(["ts", "tx_hash", "log_index"]) \
                             .reset_index(drop=True)
    return _TX_CACHE[token].copy()


def airdrop_senders(tx: pd.DataFrame, n: int = None, max_amt: float = None,
                    window: str = None) -> set:
    """Airdrop rule: senders that, within some sliding window, send one transfer
    with 0 < amount < max_amt to each of more than n distinct receivers.
    tx needs from / to / amt / ts."""
    n = C.AIRDROP_N if n is None else n
    max_amt = C.AIRDROP_MAX_AMT if max_amt is None else max_amt
    win = pd.Timedelta(C.AIRDROP_WINDOW if window is None else window)
    small = tx[(tx["amt"] > 0) & (tx["amt"] < max_amt)]
    # a sender with at most n distinct receivers in the whole period cannot qualify
    cand = small.groupby("from")["to"].nunique()
    cand = cand[cand > n].index
    hit = set()
    for s, g in small[small["from"].isin(cand)].groupby("from", sort=True):
        ts = g["ts"].values
        rc = g["to"].values
        cnt: dict = {}
        lo = 0
        for hi in range(len(ts)):
            cnt[rc[hi]] = cnt.get(rc[hi], 0) + 1
            while ts[hi] - ts[lo] >= win:          # window strictly shorter than win
                c = cnt[rc[lo]] - 1
                if c:
                    cnt[rc[lo]] = c
                else:
                    del cnt[rc[lo]]
                lo += 1
            if len(cnt) > n:
                hit.add(s)
                break
    return hit


def clean_transfers(tx: pd.DataFrame, drop_zero: bool = None,
                    airdrop: bool = None, n: int = None,
                    max_amt: float = None) -> tuple[pd.DataFrame, dict]:
    """Clean under the current specification (defaults: config.DROP_ZERO_VALUE / DROP_AIRDROP).

    Order: mint/burn -> zero-value -> airdrop. For a sender flagged by the airdrop
    rule, every transfer with 0 < amount < max_amt in the whole period is removed;
    its transfers of normal size are kept.
    """
    drop_zero = C.DROP_ZERO_VALUE if drop_zero is None else drop_zero
    airdrop = C.DROP_AIRDROP if airdrop is None else airdrop
    max_amt = C.AIRDROP_MAX_AMT if max_amt is None else max_amt
    st = {"n_raw": len(tx), "active_raw": len(active_addresses(tx))}
    burn = tx["from"].isin(C.BURN_ADDRS) | tx["to"].isin(C.BURN_ADDRS)
    st["n_mint_burn"] = int(burn.sum())
    tx = tx[~burn]
    if drop_zero:
        z = tx["amt"] == 0
        st["n_zero_value"] = int(z.sum())
        tx = tx[~z]
    if airdrop:
        senders = airdrop_senders(tx, n=n, max_amt=max_amt)
        m = tx["from"].isin(senders) & (tx["amt"] > 0) & (tx["amt"] < max_amt)
        st["airdrop_senders"] = sorted(senders)
        st["n_airdrop_senders"] = len(senders)
        st["n_airdrop_transfers"] = int(m.sum())
        st["airdrop_volume"] = float(tx.loc[m, "amt"].sum())
        tx = tx[~m]
    st["n_clean"] = len(tx)
    st["active_clean"] = len(active_addresses(tx))
    return tx.reset_index(drop=True), st


def load_transfers(token: str, clean: bool = True) -> pd.DataFrame:
    """Transfers of the main specification: mint/burn, zero-value and airdrop removed
    (rules in config).

    clean=False removes mint/burn only -- equivalent to drop_burn=True in v1 --
    for the raw-data rows of the appendix and the case study of Section 7.
    """
    tx = load_transfers_raw(token)
    if clean:
        return clean_transfers(tx)[0]
    return clean_transfers(tx, drop_zero=False, airdrop=False)[0]


def load_balances(token: str) -> pd.DataFrame:
    """Returns address / balance (in tokens) at the snapshot, config.SNAPSHOT_TIME.

    Positive balances only. The zero address (negative through minting) is left
    out; the burn address 0x...dead is kept, since counting it or not is a row of
    the sensitivity table. Genesis allocations without a Transfer event are added
    （config.GENESIS_ALLOCATION）。
    Sums are exact integers until the final conversion to float.
    """
    raw = pd.read_parquet(C.V2_BALANCES)
    raw = raw[raw["token_address"] == C.EXPECT[token]["contract"]]
    v = {a: int(str(b).split(".")[0])
         for a, b in zip(_norm_addr(raw["address"]), raw["balance_raw"])}
    for a, amt in C.GENESIS_ALLOCATION.get(token, {}).items():
        v[a] = v.get(a, 0) + amt
    df = pd.DataFrame({"address": list(v), "raw": list(v.values())})
    df = df[(df["raw"] > 0) & ~df["address"].isin(C.BURN_ADDRS - {C.DEAD_ADDR})]
    df["balance"] = df["raw"].map(lambda x: x / 1e18)
    return df[["address", "balance"]].reset_index(drop=True)


def active_addresses(tx: pd.DataFrame) -> set:
    """Addresses that sent or received, excluding the zero and burn addresses."""
    return (set(tx["from"]) | set(tx["to"])) - C.BURN_ADDRS


# ============================================================ labels
def load_labels() -> dict:
    """Read the local snapshot only. If it is missing, raise with the command that
    fetches it; never go online."""
    snap = C.LABEL_SNAPSHOT
    if not snap.exists():
        # find any snapshot in labels/, so a file-name mismatch with config does not block
        found = sorted(C.LABELS.glob("etherscan_labels_*.json"))
        if len(found) == 1:
            snap = found[0]
            print(f"    [i] {C.LABEL_SNAPSHOT.name} named in config is missing; "
                  f"using {snap.name}")
        elif len(found) > 1:
            snap = found[-1]
            print(f"    [!] {len(found)} snapshots in labels/; "
                  f"using the newest, {snap.name}. For reproducibility keep one "
                  "and name it in config.LABEL_SNAPSHOT.")
    if not snap.exists():
        raise FileNotFoundError(
            f"label snapshot not found: {C.LABEL_SNAPSHOT}\n"
            "fetch it once and commit it (it is read locally from then on):\n"
            "  python -c \"import urllib.request,shutil;"
            f"shutil.copyfileobj(urllib.request.urlopen('{C.LABEL_SNAPSHOT_URL}'),"
            f"open('{C.LABEL_SNAPSHOT}','wb'))\"\n"
            "The compilation keeps changing and the is_core anchors drift with it; "
            "the snapshot must be committed and its date reported."
        )
    with open(snap, encoding="utf-8") as f:
        raw = json.load(f)
    # 173 addresses appear twice, in two letter cases, with different content. Rule
    # (see config): labels = union; name = from the all-lowercase key if there is
    # one, otherwise from the lexicographically smallest key.
    out: dict = {}
    for key in sorted(raw):
        a = key.lower()
        v = raw[key]
        if a not in out:
            out[a] = {"name": v.get("name", ""), "labels": list(v.get("labels", [])),
                      "_lower": key == a}
        else:
            prev = out[a]
            prev["labels"] = sorted(set(prev["labels"]) | set(v.get("labels", [])))
            if key == a and not prev["_lower"]:
                prev["name"], prev["_lower"] = v.get("name", ""), True
    for v in out.values():
        v.pop("_lower")
    return out


def categorize(labels) -> str:
    labs = {str(x).lower() for x in labels}
    for cat, keys in C.LABEL_CATEGORIES.items():
        if labs & keys:
            return cat
    return "Other-labeled"


def node_categories(nodes, label_map: dict) -> np.ndarray:
    return np.array([categorize(label_map[a]["labels"]) if a in label_map
                     else "Unlabeled" for a in nodes])


def is_core_mask(cat: np.ndarray) -> np.ndarray:
    return np.isin(cat, C.CORE_CATS)


# ============================================================ graph construction (only entry point)
def build_graph(tx: pd.DataFrame, top_n: int | None = None,
                largest_wcc: bool = True, verbose: bool = True):
    """The only way to build a graph. Edge weights are summed per (from, to) --
    the largest bug of v16 was here.

    tx needs from / to / amt. top_n=None means no activity filter (full graph).
    Returns a networkx.DiGraph with edge attribute 'w'.
    """
    import networkx as nx

    if top_n is not None:
        # ties broken by address -- otherwise who is in at the boundary depends on row order
        activity = pd.concat([tx["from"], tx["to"]]).value_counts()
        activity = activity.rename_axis("a").reset_index(name="n") \
                           .sort_values(["n", "a"], ascending=[False, True])
        core = set(activity["a"].head(top_n))
        tx = tx[tx["from"].isin(core) & tx["to"].isin(core)]
        if verbose:
            print(f"    activity top{top_n:,} → {len(core):,} nodes, "
                  f"{len(tx):,} transfers among them")

    if C.EDGE_AGG == "sum":
        agg = tx.groupby(["from", "to"], as_index=False)["amt"].sum()   # sorted by (from, to)
    else:   # SPEC=overwrite only: reproduce DiGraph's overwriting -- the last transfer in time
        agg = tx.groupby(["from", "to"], as_index=False)["amt"].last()
    agg = agg.rename(columns={"amt": "w"})
    if verbose and len(tx):
        dup = len(tx) - len(agg)
        print(f"    distinct edges {len(agg):,} ({dup:,} repeated rows, "
              f"{dup / len(tx) * 100:.1f}%)")

    # nodes are inserted in address order: sampled betweenness draws its sample by
    # node order, which must depend on the data only
    G = nx.DiGraph()
    G.add_nodes_from(sorted(set(agg["from"]) | set(agg["to"])))
    G.add_weighted_edges_from(agg[["from", "to", "w"]].itertuples(index=False), weight="w")

    if largest_wcc and G.number_of_nodes():
        keep = max(nx.weakly_connected_components(G), key=len)
        H = nx.DiGraph()
        H.add_nodes_from(n for n in G.nodes if n in keep)
        H.add_edges_from((u, v, d) for u, v, d in G.edges(data=True) if u in keep)
        G = H
    if verbose:
        print(f"    graph {G.number_of_nodes():,} nodes / "
              f"{G.number_of_edges():,} edges")
    return G


def safe_pagerank(G, weight="w"):
    """Summed weights are more extreme and max_iter=100 may not converge; relax step
    by step and report it."""
    import networkx as nx
    for mi, tol in ((100, 1e-6), (500, 1e-6), (2000, 1e-8)):
        try:
            pr = nx.pagerank(G, weight=weight, max_iter=mi, tol=tol)
            if mi > 100:
                print(f"    [!] PageRank converged only at max_iter={mi}"
                      " (the default is 100)")
            return pr
        except nx.PowerIterationFailedConvergence:
            continue
    raise RuntimeError("PageRank did not converge")


def node_features(G, balance_map: dict, k_betweenness: int, seed: int = None,
                  skip_betweenness: bool = False):
    """Returns (feat, nodes); feat columns in the order of config.FEATURE_NAMES.

    With skip_betweenness=True that column is 0 and the caller fills in a reused
    value. Betweenness depends on topology only, not on edge weights.
    """
    import networkx as nx
    seed = C.SEED if seed is None else seed
    nodes = list(G.nodes())
    ind, outd = dict(G.in_degree()), dict(G.out_degree())
    indw = dict(G.in_degree(weight="w"))
    outdw = dict(G.out_degree(weight="w"))
    pr = safe_pagerank(G)
    if skip_betweenness:
        bet = {n: 0.0 for n in nodes}
    else:
        k = min(k_betweenness, G.number_of_nodes())
        bet = nx.betweenness_centrality(G, k=k, seed=seed)
    cp = {n: len(set(G.predecessors(n)) | set(G.successors(n))) for n in nodes}

    feat = np.array([[balance_map.get(n, 0.0), ind[n], outd[n], indw[n],
                      outdw[n], cp[n], pr[n], bet[n]] for n in nodes],
                    dtype=np.float64)
    return feat, nodes


def prepare_gnn_input(feat: np.ndarray):
    """No leakage: drop balance first, then log1p + z-score on the remaining 7 features.

    The other order would let balance contaminate the standardisation. Returns
    (x, kept_names).
    """
    names = C.FEATURE_NAMES
    bi = names.index(C.LEAKY_FEATURE)
    keep = [i for i in range(len(names)) if i != bi]
    raw = feat[:, keep]
    lg = np.log1p(np.abs(raw)) * np.sign(raw)
    x = (lg - lg.mean(0)) / (lg.std(0) + 1e-8)
    return x, [names[i] for i in keep]


# ============================================================ embedding training (only entry point)
def seed_everything(seed: int) -> None:
    """Seed Python's random, NumPy and torch together.

    PyG's negative_sampling uses Python's random.sample, so seeding torch alone is not enough.
    """
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def stable_hash(s: str) -> int:
    """Hash for gensim's vector initialisation. Python's hash() is randomised per
    process, which makes node2vec irreproducible across runs; md5 is used instead."""
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


def train_sage(x: np.ndarray, edge_index, seed: int) -> np.ndarray:
    """Two-layer GraphSAGE with an unsupervised link-reconstruction objective;
    every hyperparameter comes from config.

    Used by 02, 04 and 05. CPU + deterministic algorithms: same input and seed give
    bit-identical output.
    """
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric.nn import SAGEConv
    from torch_geometric.utils import negative_sampling

    torch.use_deterministic_algorithms(True)
    dev = torch.device(C.TRAIN_DEVICE)
    ei = torch.as_tensor(edge_index, dtype=torch.long).to(dev)

    class SAGE(nn.Module):
        def __init__(s, i, h, o):
            super().__init__()
            s.c1, s.c2 = SAGEConv(i, h), SAGEConv(h, o)

        def forward(s, x, e):
            return s.c2(F.relu(s.c1(x, e)), e)

    seed_everything(seed)
    xt = torch.tensor(x, dtype=torch.float, device=dev)
    m = SAGE(xt.size(1), C.HIDDEN_DIM, C.EMB_DIM).to(dev)
    opt = torch.optim.Adam(m.parameters(), lr=C.LR)
    m.train()
    for _ in range(C.EPOCHS):
        opt.zero_grad()
        z = m(xt, ei)
        pos = (z[ei[0]] * z[ei[1]]).sum(1)
        ne = negative_sampling(ei, z.size(0), num_neg_samples=ei.size(1))
        neg = (z[ne[0]] * z[ne[1]]).sum(1)
        loss = (F.binary_cross_entropy_with_logits(pos, torch.ones_like(pos))
                + F.binary_cross_entropy_with_logits(neg, torch.zeros_like(neg)))
        loss.backward()
        opt.step()
    m.eval()
    with torch.no_grad():
        return m(xt, ei).cpu().numpy()


# ============================================================ metrics
def gini(values) -> float:
    x = np.sort(np.asarray(values, dtype=float))
    x = x[x > 0]
    n = len(x)
    if n == 0:
        return np.nan
    c = np.cumsum(x)
    return float((n + 1 - 2 * np.sum(c) / c[-1]) / n)


def hhi(values) -> float:
    """0-10,000 scale. DOJ 2010: < 1500 unconcentrated, 1500-2500 moderate, > 2500
    highly concentrated; DOJ 2023: > 1800 highly concentrated."""
    v = np.asarray(values, dtype=float)
    v = v[v > 0]
    if len(v) == 0 or v.sum() <= 0:
        return np.nan
    s = v / v.sum()
    return float(np.sum((s * 100) ** 2))


def top_share(values, frac: float = None, k: int = None,
              include_zeros: bool = False) -> float:
    """include_zeros decides the denominator of the "1%".

    Cell 18 of v16 took int(len * 0.01) over every value of in_degree() (including
    pure senders with zero inflow) and got 82.3% on LINK; ceil over positive values
    gives 79.4%. Both are defensible but must be stated. Main: include_zeros=False.
    """
    x = np.asarray(values, dtype=float)
    if not include_zeros:
        x = x[x > 0]
    if len(x) == 0:
        return np.nan
    x = np.sort(x)[::-1]
    n = k if k is not None else max(1, int(np.ceil(len(x) * frac)))
    return float(x[:n].sum() / max(x.sum(), 1e-12))


def top_share_v16(values, frac: float = 0.01) -> float:
    """Exact reimplementation of v16 cell 18, for the before/after comparison only.

    Two differences: zeros are not filtered (in_degree returns 0 for pure senders)
    and int truncates instead of ceil. On LINK together they raise 79.4% to 82.3%.
    """
    sv = np.sort(np.asarray(values, dtype=float))[::-1]
    if len(sv) == 0:
        return np.nan
    return float(sv[:max(1, int(len(sv) * frac))].sum() / max(sv.sum(), 1e-9))


def nakamoto(values, threshold_frac: float = 0.5) -> int:
    """Fewest participants needed to reach a share threshold_frac (rule layer)."""
    x = np.sort(np.asarray(values, dtype=float))[::-1]
    x = x[x > 0]
    if len(x) == 0:
        return 0
    return int(np.searchsorted(np.cumsum(x) / x.sum(), threshold_frac) + 1)


def nakamoto_absolute(values, threshold: float) -> int:
    """Fewest addresses needed to reach an absolute threshold (e.g. the 40M UNI quorum)."""
    x = np.sort(np.asarray(values, dtype=float))[::-1]
    x = x[x > 0]
    cum = np.cumsum(x)
    if len(cum) == 0 or cum[-1] < threshold:
        return -1                       # not reached even by all of them
    return int(np.searchsorted(cum, threshold) + 1)


def weekly_metric(tx: pd.DataFrame, side: str, fn) -> pd.Series:
    """Apply fn to the amounts aggregated by side ('from' / 'to') in each week."""
    out = {}
    for w, g in tx.groupby("week", sort=True):
        out[int(w)] = fn(g.groupby(side)["amt"].sum().values)
    return pd.Series(out, name=getattr(fn, "__name__", "metric"))


def find_outlier_windows(tx: pd.DataFrame) -> list:
    per = pd.concat([
        tx[["week", "from"]].rename(columns={"from": "a"}),
        tx[["week", "to"]].rename(columns={"to": "a"}),
    ]).groupby("week")["a"].nunique()
    med = per.median()
    return sorted(per[per > C.OUTLIER_NODE_MULTIPLIER * med].index.tolist())


# ============================================================ entity resolution
_TAIL = None


def _family(name: str):
    """Map an Etherscan name to its entity family: 'Binance 14' -> 'Binance'."""
    global _TAIL
    if _TAIL is None:
        import re
        _TAIL = re.compile(
            r"\s+(v\d+(\.\d+)?|\d+|#\d+|deposit|hot\s*wallet|cold\s*wallet)\s*$",
            re.I)
    if not name or not str(name).strip():
        return None
    head = str(name).split(":")[0].split("：")[0].strip()
    prev = None
    while prev != head:
        prev = head
        head = _TAIL.sub("", head).strip()
    low = head.lower()
    if len(head) < 2 or low in C.GENERIC_LABELS:
        return None
    if any(k in low for k in C.ALERT_KEYWORDS):
        return None
    return head


def build_entity_map(token: str, label_map: dict = None,
                     verbose: bool = True) -> dict:
    """Three sources, in increasing priority: label compilation -> issuer reserves
    -> manual verification."""
    if label_map is None:
        label_map = load_labels()
    emap = {}
    for a, info in label_map.items():
        fam = _family(info.get("name", ""))
        if fam:
            emap[a] = fam
    n_lib = len(emap)
    for a in C.ISSUER_RESERVES.get(token, ()):
        emap[a] = f"{token} Issuer Reserve"
    emap.update({k.lower(): v for k, v in C.MANUAL_ENTITIES.items()})
    if verbose:
        print(f"    entity map {len(emap):,} addresses → {len(set(emap.values())):,} "
              f"entities (compilation {n_lib:,} / manual {len(C.MANUAL_ENTITIES)})")
    return emap


def entity_key(addrs: pd.Series, emap: dict) -> pd.Series:
    """Unidentified addresses stay separate -- the merge is partial, so results are
    lower bounds, not upper bounds."""
    return addrs.map(emap).fillna(addrs)


# ============================================================ output / provenance
def file_md5(path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def log_metric(script: str, token: str, metric: str, value,
               note: str = "") -> None:
    """Append a key number to results/manifest.csv (one line of provenance per number)."""
    row = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "script": script, "token": token, "metric": metric,
        "value": value, "note": note,
    }
    path = C.RESULTS / "manifest.csv"
    pd.DataFrame([row]).to_csv(path, mode="a", header=not path.exists(),
                               index=False)


def save_json(obj, name: str) -> Path:
    path = C.RESULTS / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
    print(f"    → {path.name}")
    return path


def save_csv(df: pd.DataFrame, name: str) -> Path:
    path = C.RESULTS / name
    df.to_csv(path, index=False)
    print(f"    → {path.name} ({len(df)} rows)")
    return path


def banner(text: str, ch: str = "=") -> None:
    print("\n" + ch * 76)
    print(f"  {text}")
    print(ch * 76)


def check(label: str, got, expect, tol=0) -> bool:
    """Gate: flag a mismatch loudly but do not stop (let the batch finish first)."""
    ok = (abs(got - expect) <= tol) if isinstance(got, (int, float)) \
        else (got == expect)
    mark = "[OK]" if ok else "[X] "
    print(f"    {mark} {label}: {got:,} (expected {expect:,})" if
          isinstance(got, (int, float)) else
          f"    {mark} {label}: {got} (expected {expect})")
    return ok
