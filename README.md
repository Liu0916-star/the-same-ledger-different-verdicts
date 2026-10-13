# The Same Ledger, Different Verdicts

**How Measurement Specification Determines On-Chain Concentration**

Jintao Liu\*, Zhimo Ji\* (School of Computing and Information Systems, The University of Melbourne) and Xuzhe Lin (School of Mathematics and Statistics, The University of Sydney)

\* Equal contribution · [中文说明](README_zh.md)

[![arXiv](https://img.shields.io/badge/arXiv-2609.24176-b31b1b.svg)](https://arxiv.org/abs/2609.24176)
[![Data DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23329575.svg)](https://doi.org/10.5281/zenodo.23329575)

---

People often settle whether a public blockchain is "decentralized" by quoting a
single concentration statistic. This repository contains the data pipeline,
results and manuscript for a paper that tests this on two ERC-20 ledgers,
Chainlink (LINK) and Uniswap (UNI), over the same 90-day window. On these
ledgers, the verdict depends on how the statistic is specified as much as on
the ledger itself.

This is the code and data for **arXiv v2** (release `v2.0`). Appendix E of the
paper lists every change from the first version.

## Main results

- **Specification choices move the statistics.** Over 18 combinations of
  holder population, address type and entity resolution:
  - the balance HHI of UNI runs from **108 to 3,281** (LINK: 115 to 562);
  - the balance Gini moves by at most 0.0063 (UNI) and 0.0129 (LINK).
- **Each choice acts on one end of the distribution.**
  - Address type and entity resolution act on the top. They move the HHI.
  - A balance floor acts on the tail. A USD 100 floor raises 1 − Gini 4.7-fold
    (UNI) and 2.6-fold (LINK), yet changes the HHI by at most 0.5%.
  - Restricting to transfer-active addresses acts on both ends.
- **Implementation details matter as much.**
  - LINK had a coordinated dust airdrop: 549,598 transfers from 80 senders.
    Removing it by rule changes the HHI of active LINK holdings from 135 to 375.
  - If repeated transfers between an address pair are overwritten instead of
    summed, the graph loses 85.9% of transferred volume.
- **Ownership and routing tell different stories.**
  - Ownership is extremely unequal: Gini 0.990 (LINK), 0.998 (UNI).
  - Routing is unconcentrated: weekly flow HHI 421 (LINK), 386 (UNI).
- **The learned model adds little to hidden-broker selection.** The
  hidden-broker criterion selects 22 LINK and 9 UNI addresses. In a blind,
  degree-matched control, the learned representation adds no detectable power
  beyond counterparty count: 50% vs 45% of addresses resolve to named routing
  services, one-sided Fisher *p* = 0.49.
- **Governance looks different in votes than in balances.** Measured in
  delegated votes, 4 UNI delegates reach the 40M quorum. None of the 49
  delegates able to propose routes the token.

| | LINK (oracle) | UNI (governance) |
|---|---|---|
| Transfers in window (raw) | 1,233,497 | 433,856 |
| Holders at snapshot block 25,390,910 | 885,012 | 382,972 |
| Transfer-active addresses after cleaning | 132,059 | 37,153 |
| Balance HHI over 18 specifications | 115 – 562 | 108 – 3,281 |
| Balance Gini (all holders) | 0.9898 | 0.9977 |
| Weekly flow HHI (address / entity-resolved) | 421 / 654 | 386 / 667 |
| Hidden brokers (shared across ledgers) | 22 (4) | 9 (4) |

Observation window: 2026-03-26 00:00 to 2026-06-25 00:00 UTC. Balances are
taken at the last block of the window.

## Repository layout

```
.
├── paper/
│   ├── main.tex, sections/, bib_v2.tex   manuscript (arXiv v2)
│   ├── numbers.tex                       every number in the text, generated
│   └── figures/                          the three figures
├── requirements.txt, requirements-lock.txt
└── gnn-decentralization/
    ├── config.py              every path, threshold, seed and hyperparameter
    ├── common.py              loading, cleaning, metrics, graph construction, GraphSAGE
    ├── 00_data_check.py … 07_governance.py   main pipeline
    ├── 08_figures.py          the three figures (reads results only)
    ├── 11_random_control.py   blind, degree-matched control
    ├── v2_*.py                cleaning report, sensitivity analyses, bootstrap
    │                          intervals, on-chain checks (prices, fee contracts)
    ├── benchmarks/            public-data HHI benchmarks, with raw downloads
    ├── make_numbers.py        writes paper/numbers.tex and checks every
    │                          qualitative claim against its numbers
    ├── paper_audit.py         flags numbers typed by hand in the manuscript
    ├── reproduce.sh           runs everything, in order
    ├── sql/                   BigQuery extraction (v2) and delegation snapshot
    ├── extract_data.sql       first-version extraction (kept for the v1 comparison)
    ├── labels/                archived Etherscan label snapshot
    ├── verification/          manual and blind verification records
    ├── results/               derived artefacts of the main specification
    ├── results_spec_*/        alternative cleaning and edge-weight specifications
    ├── results_v1/            first-version results (for the v1 → v2 comparison)
    └── results_v16_legacy/    one file from the superseded construction
```

## Data

Raw data are not in this repository, because one file is larger than GitHub
allows. They are archived on Zenodo (DOI: [10.5281/zenodo.23329575](https://doi.org/10.5281/zenodo.23329575)) as `data.zip`, with
`SHA256SUMS.txt`. Unzip it inside `gnn-decentralization/`, which creates `data/`:

| File | Content | How to rebuild |
|---|---|---|
| `data/v2/v2_transfers.parquet` | every LINK and UNI transfer in the window | `sql/v2_transfers.sql` |
| `data/v2/v2_balances.parquet` | balances at block 25,390,910 | `sql/v2_balances.sql` |
| `data/v2/uni_delegation_snapshot.parquet`, `uni_delegate_votes.parquet` | UNI delegation and votes at the same block | `sql/fetch_uni_delegation.py` (public RPC) |
| `data/*.csv` | first-version extraction | `extract_data.sql`; used only by `v2_data_check.py` |

The queries read `bigquery-public-data.crypto_ethereum.token_transfers`.
`sql/download_v2.py` runs them and writes the parquet files.

## Reproducing the results

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
cd gnn-decentralization
unzip /path/to/data.zip    # from Zenodo
./reproduce.sh
```

`reproduce.sh` runs every script in dependency order:

1. cleaning;
2. graphs and embeddings at three scales;
3. the four alternative specifications;
4. bootstrap intervals and on-chain checks;
5. figures and `paper/numbers.tex`.

It takes about three hours on an Apple-silicon CPU. A few steps read
historical state from public Ethereum and L2 RPC endpoints, so the machine
needs network access.

Training runs on CPU with deterministic algorithms. A full rerun of
`reproduce.sh` reproduces every result file byte for byte, apart from the
timestamps in `manifest.csv`. To rebuild only the
paper's numbers and figures from the archived `results/`, run
`make_numbers.py` and `08_figures.py`. To compile the paper, run `latexmk -pdf
main.tex` in `paper/`.

## What is archived, and where

| Artefact | Location |
|---|---|
| Label snapshot (retrieved 26 Aug 2026, MD5 `16792aac5afd369e6b847c3f0aad1df4`) | `labels/etherscan_labels_2026-08-26.json` |
| Graphs with node features | `results/graph_*_1w.npz`, `graph_*_5w.npz` |
| Embeddings behind every reported ensemble, with fingerprints | `results/emb_*_1w_s*.npy` and `.fp` |
| Hidden-broker sets and cluster assignments | `results/hidden_brokers_*.csv`, `c3_typology_*.json` |
| Dust-airdrop senders flagged by the rule | `verification/airdrop_senders_*.csv` |
| Blind control: list, key, known identities, result | `verification/control_*_v2.csv`, `known_identities_v2.csv`, `results/random_control.json` |
| Live Etherscan tags of the brokers (6 Oct 2026) | `verification/broker_live_labels_2026-10-06.csv` |
| UNI fee mechanism: burns, releasers on Ethereum and four L2s | `verification/uni_fee_burns.md`, `uni_l2_firepits.csv`, `raw/` |
| Chainlink prices at the snapshot (feed, round, answer) | `results/prices_snapshot.json` |
| First-version verification records | `verification/broker_identities.csv`, `verification/v1/` |

## Four details that decide whether the numbers reproduce

- **Edge weights are summed.** `networkx.from_pandas_edgelist` with a
  `DiGraph` keeps only the last record of each ordered address pair, and it
  does so without warning. `common.build_graph()` sums repeated pairs
  explicitly. Section 4.6 of the paper shows what overwriting changes.
- **Labels come from the archived snapshot.** The upstream compilation was
  last scraped for Ethereum in June 2023. `common.load_labels()` reads only the
  archived file and merges 173 entries that differ only in letter case.
- **Every source of randomness is seeded.**
  - PyTorch Geometric's `negative_sampling` draws from Python's `random`
    module, so we seed Python, NumPy and PyTorch.
  - We train on CPU with deterministic algorithms.
  - We give gensim a stable hash function.
  - We break ties in the activity ranking by address, and insert nodes into
    the graph in address order.
- **Manual verification uses Etherscan's token-transfer view.** A routing
  contract that other contracts call shows few transactions of its own.

## Citation

```bibtex
@article{liu2026sameledger,
  title   = {The Same Ledger, Different Verdicts: How Measurement Specification
             Determines On-Chain Concentration},
  author  = {Liu, Jintao and Ji, Zhimo and Lin, Xuzhe},
  journal = {arXiv preprint arXiv:2609.24176},
  year    = {2026}
}
```

## Licence

Code: MIT (see `LICENSE`). Manuscript: CC BY-NC-ND 4.0, as deposited on arXiv.
