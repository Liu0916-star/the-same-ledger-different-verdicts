# -*- coding: utf-8 -*-
"""
01_build_graph.py -- graph, node features and labels, saved for every later script

Writes results/graph_{TOKEN}_{SCALE}.npz (feat / nodes / cat / edge_index) once;
02_c1 and 05_c3 read it instead of recomputing betweenness.

Also writes the summed-vs-overwritten edge-weight comparison (lost volume, PageRank
correlation, top-50 overlap) reported in Section 4.6 of the paper.

Usage:
    python 01_build_graph.py                  # LINK and UNI at 10^4
    python 01_build_graph.py LINK 5w
    python 01_build_graph.py LINK full        # full cleaned graph, betweenness k=5000
"""
import sys

import numpy as np
import pandas as pd

import config as C
import common as cm

SCRIPT = "01_build_graph"


TOKEN_CTX = ("LINK", "1w")   # set by run(); used to name output files


def legacy_compare(tx, G, nodes, pr_new, verbose=True):
    """Rebuild with the overwriting construction of v16 to quantify the difference.
    Same topology; only the edge weights differ."""
    import networkx as nx
    Gl = nx.from_pandas_edgelist(tx, "from", "to", edge_attr="amt",
                                 create_using=nx.DiGraph())
    Gl = Gl.subgraph(nodes).copy()
    nx.set_edge_attributes(
        Gl, {(u, v): d["amt"] for u, v, d in Gl.edges(data=True)}, "w")
    pr_old = cm.safe_pagerank(Gl)

    v_new = sum(dict(G.in_degree(weight="w")).values())
    v_old = sum(dict(Gl.in_degree(weight="w")).values())
    a = np.array([pr_new[n] for n in nodes])
    b = np.array([pr_old.get(n, 0.0) for n in nodes])
    rho = float(np.corrcoef(a, b)[0, 1])
    t50a = set(np.array(nodes)[np.argsort(-a)[:50]])
    t50b = set(np.array(nodes)[np.argsort(-b)[:50]])
    ov = len(t50a & t50b)
    loss = (1 - v_old / v_new) * 100 if v_new else 0.0
    # save both PageRank vectors and the node order (not the graphs); the file is small
    np.savez_compressed(
        C.RESULTS / f"edgeweight_compare_{TOKEN_CTX[0]}_{TOKEN_CTX[1]}.npz",
        pr_new=a, pr_old=b, nodes=np.array(nodes, dtype=object),
        value_new=np.array([v_new]), value_old=np.array([v_old]))
    if verbose:
        print("\n  [summed vs overwritten edge weights]")
        print(f"    volume in graph: overwritten {v_old:,.0f} → summed {v_new:,.0f}"
              f" (overwriting loses {loss:.1f}%)")
        print(f"    PageRank correlation {rho:.4f} | top-50 overlap {ov}/50")
        print("    (reported in Section 4.6)")
    return {"value_loss_pct": round(loss, 2), "pagerank_corr": round(rho, 4),
            "top50_overlap": ov}


def run(token: str, scale: str):
    global TOKEN_CTX
    TOKEN_CTX = (token, scale)
    cm.banner(f"01 · graph {token} / {scale}")
    top_n = C.SCALES[scale]

    tx = cm.load_transfers(token)
    bal = cm.load_balances(token)
    bmap = dict(zip(bal["address"], bal["balance"]))
    print(f"  transfers {len(tx):,} | holders {len(bal):,}")

    G = cm.build_graph(tx, top_n=top_n)
    k = C.BETWEENNESS_K[scale]
    print(f"  computing features (betweenness k={k:,}) ...")
    feat, nodes = cm.node_features(G, bmap, k_betweenness=k)

    pr_i = C.FEATURE_NAMES.index("pagerank")
    pr_new = dict(zip(nodes, feat[:, pr_i]))
    # the edge-weight comparison is made on the activity-ranked subgraphs only (Section 4.6)
    if scale == "full":
        print("\n  [edge-weight comparison] skipped on the full graph")
        cmp = {}
    else:
        nodeset = set(nodes)
        cmp = legacy_compare(
            tx[tx["from"].isin(nodeset) & tx["to"].isin(nodeset)],
            G, nodes, pr_new)

    lm = cm.load_labels()
    cat = cm.node_categories(nodes, lm)
    n_core = int(cm.is_core_mask(cat).sum())
    print(f"\n  [labels] matched {int((cat != 'Unlabeled').sum()):,} | "
          f"core anchors {n_core}")
    print(f"    categories {pd.Series(cat).value_counts().to_dict()}")

    idx = {a: i for i, a in enumerate(nodes)}
    edges = np.array([[idx[u], idx[v]] for u, v in G.edges()], dtype=np.int64).T

    out = C.RESULTS / f"graph_{token}_{scale}.npz"
    np.savez_compressed(out, feat=feat, nodes=np.array(nodes, dtype=object),
                        cat=cat, edge_index=edges,
                        feature_names=np.array(C.FEATURE_NAMES, dtype=object),
                        meta=np.array([token, scale, str(k),
                                       str(G.number_of_nodes()),
                                       str(G.number_of_edges())], dtype=object))
    print(f"\n  → {out.name}  feat{feat.shape} edges{edges.shape}")

    for k_, v_ in cmp.items():
        cm.log_metric(SCRIPT, token, f"{scale}_{k_}", v_)
    cm.log_metric(SCRIPT, token, f"{scale}_n_nodes", G.number_of_nodes())
    cm.log_metric(SCRIPT, token, f"{scale}_n_anchors", n_core)
    return feat, nodes, cat, edges


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        run(args[0], args[1] if len(args) > 1 else "1w")
    else:
        for t in C.TOKENS:
            run(t, "1w")
    cm.banner("Done. Next: python 02_c1.py")


if __name__ == "__main__":
    main()
