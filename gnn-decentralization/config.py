# -*- coding: utf-8 -*-
"""
config.py -- the single source of configuration for the repository

Every constant, path, hyperparameter and specification lives here; scripts hold
no hard-coded numbers or paths. To change a specification, change this file and
rerun.
"""
import os
from pathlib import Path

# ============================================================ specification switch
# The environment variable SPEC selects the data specification (Appendix B);
# default main.
#   main          zero-value and airdrop transfers removed
#   keep_zero     zero-value transfers kept (airdrop still removed)
#   keep_airdrop  airdrop transfers kept (zero-value still removed)
#   raw           both kept (the data of v1)
#   overwrite     main cleaning, but repeated ordered pairs are overwritten rather
#                 than summed (networkx DiGraph's default), to isolate this
#                 implementation choice
# Results of a non-main specification go to results_spec_<SPEC>/ and never
# overwrite the main results.
SPEC = os.environ.get("SPEC", "main")
assert SPEC in ("main", "keep_zero", "keep_airdrop", "raw", "overwrite"), SPEC
EDGE_AGG = "last" if SPEC == "overwrite" else "sum"

# ============================================================ paths
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
LABELS = ROOT / "labels"
RESULTS = ROOT / ("results" if SPEC == "main" else f"results_spec_{SPEC}")
FIGURES = ROOT / "figures"
LEGACY = ROOT / "results_v16_legacy"      # v16 results, read-only, for before/after comparisons
PRICES = ROOT / "results" / "prices_snapshot.json"   # snapshot prices (v2_prices.py), shared by every specification

for _d in (RESULTS, FIGURES, LABELS):
    _d.mkdir(exist_ok=True)

# ============================================================ data files
TOKENS = ("LINK", "UNI")

# v1 CSVs: used only by the regression test in v2_data_check.py
FILES = {
    "LINK": {"tx": DATA / "link_90d_transfers.csv",
             "bal": DATA / "link_balances.csv"},
    "UNI":  {"tx": DATA / "uni_90d_transfers.csv",
             "bal": DATA / "uni_balances.csv"},
}

# v2 data (sql/v2_transfers.sql, sql/v2_balances.sql; downloaded by sql/download_v2.py);
# both tokens are in one table, told apart by token_address
V2_TRANSFERS = DATA / "v2" / "v2_transfers.parquet"
V2_BALANCES = DATA / "v2" / "v2_balances.parquet"

# Balance snapshot: net flow over the whole history up to 2026-06-25 00:00:00 UTC
# (= end of the window). v1 balances had no cut-off (exported 26 June for LINK and
# 25 July for UNI); v2 uses one snapshot for both.
SNAPSHOT_TIME = "2026-06-25 00:00:00+00:00"
SNAPSHOT_BLOCK = 25_390_910       # last block before the cut-off (2026-06-24 23:59:59 UTC)

# Balance floors (Table 1): the dust floor equals the airdrop threshold; the value
# floor is USD 100 (attributed by Sai et al. 2021 to Srinivasan & Lee 2017, whose
# own threshold was >= 185 BTC / >= 2,477 ETH), priced with the Chainlink feeds at
# the snapshot block (v2_prices.py).
DUST_FLOOR = 0.01
VALUE_FLOOR_USD = 100
PRICE_FEEDS = {
    "LINK": ("0x2c1d072e956AFFC0D435Cb7AC38EF18d24d9127c", "LINK / USD"),
    "UNI": ("0x553303d460EE0afB37EdFf9bE42922D8FF63220e", "UNI / USD"),
}

# Genesis allocation without a Transfer event. The LINK constructor credits the
# whole supply to the deployer without emitting Transfer, so balances rebuilt from
# transfers are 1e9 LINK short. On-chain check: rebuilt + 1e9 ==
# balanceOf(deployer) @ SNAPSHOT_BLOCK == 12.768218868853097 LINK (v2_data_check.py)
GENESIS_ALLOCATION = {
    "LINK": {"0xf55037738604fddfc4043d12f25124e94d7d1780": 10**27},
}

# Expected values checked by 00_data_check.py (v2).
#   n_tx      raw transfers (identical to v1 record by record; v2_data_check.py)
#   n_holders addresses with positive balance at the snapshot (LINK: 885,011 + the deployer)
#   n_active  active addresses after main cleaning (zero and burn addresses excluded)
EXPECT = {
    "LINK": {"n_tx": 1_233_497, "n_active": 132_059, "n_holders": 885_012,
             "contract": "0x514910771af9ca656af840dff83e8264ecf986ca"},
    "UNI":  {"n_tx": 433_856, "n_active": 37_153, "n_holders": 382_972,
             "contract": "0x1f9840a85d5af5bf1d1762f925bdaddc4201f984"},
}

WINDOW_START = "2026-03-26 00:00:00+00:00"
WINDOW_END = "2026-06-25 00:00:00+00:00"      # half-open interval
WINDOW_DAYS = 7
N_WINDOWS = 13

# ============================================================ label snapshot
# Local file only; common.load_labels() refuses to go online.
# Source: combinedAllLabels.json of brianleect/etherscan-labels, retrieved 2026-08-26
# (Ethereum labels last scraped upstream on 2023-06-18). 29,945 entries; 173
# addresses appear twice, in two letter cases, with different content (v1 wrongly
# described 29,945 -> 29,772 as upstream drift; it is our case normalisation).
# v2 rule (fixed): labels = union; name = from the all-lowercase key, otherwise from
# the lexicographically smallest key.
LABEL_SNAPSHOT = LABELS / "etherscan_labels_2026-08-26.json"
LABEL_SNAPSHOT_URL = ("https://raw.githubusercontent.com/brianleect/"
                      "etherscan-labels/main/data/etherscan/combined/"
                      "combinedAllLabels.json")

LABEL_CATEGORIES = {
    "CEX": {"exchange", "binance", "coinbase", "kraken", "okx", "huobi",
            "bitfinex", "gate.io", "kucoin", "crypto-com", "bybit"},
    "DEX": {"uniswap", "sushiswap", "balancer", "curve", "dex", "1inch",
            "0x-protocol", "bancor", "kyber"},
    "Bridge": {"bridge", "arbitrum", "optimism", "polygon", "wormhole",
               "multichain"},
    "MEV": {"mev-bot", "mev", "flashbots"},
    "DeFi": {"defi", "lending", "aave", "compound", "maker"},
    "Malicious": {"phish-hack", "phishing", "scam", "exploit", "heist"},
}
CORE_CATS = ("CEX", "DEX", "Bridge", "DeFi")      # positive class of is_core

# ============================================================ graphs
# Three graphs: the 10^4 and 5x10^4 most active addresses, and the full cleaned
# graph. v1's third graph had 6.4x10^5 nodes, about 510k of them single receipts of
# the week-7 airdrop; the full cleaned graph has about 1.3x10^5 nodes, so the paper
# calls it the full graph rather than a scale-up.
SCALES = {"1w": 10_000, "5w": 50_000, "full": None}

# betweenness sample size by scale (weekly windows separately)
BETWEENNESS_K = {"1w": 500, "5w": 500, "full": 5_000, "c2_window": 200}

FEATURE_NAMES = ["balance", "in_deg", "out_deg", "in_deg_w", "out_deg_w",
                 "counterparties", "pagerank", "betweenness"]
# No leakage: balance is both a feature and a target, so it is dropped from the raw
# features first and the remaining 7 get log1p + z-score; the other order would let
# balance contaminate the standardisation.
LEAKY_FEATURE = "balance"

# ============================================================ model hyperparameters
SEED = 42
SEEDS = tuple(range(42, 52))      # GraphSAGE over ten seeds
# training at larger scales is expensive, so fewer seeds there; ten at 10^4
SEEDS_BY_SCALE = {"1w": tuple(range(42, 52)), "5w": (42, 43, 44, 45, 46),
                  "full": (42, 43, 44)}
# node2vec over five seeds (slower than GraphSAGE). With workers=1 and a stable hash
# (common.stable_hash) each run is deterministic; the seeds give the spread.
SEEDS_N2V = (42, 43, 44, 45, 46)
EMB_DIM = 16
HIDDEN_DIM = 32
EPOCHS = 200
# Training runs on CPU with deterministic algorithms: the same seed gives
# bit-identical results. v1 blamed GPU scatter order for irreproducibility; the main
# cause was that PyG's negative_sampling uses Python's random.sample, which
# torch.manual_seed does not reach. With all three RNGs seeded, MPS differs by ~1e-6
# and CPU by 0.
TRAIN_DEVICE = "cpu"
LR = 0.01
CV_FOLDS = 5
CV_SHUFFLE = True                 # positives are clustered; unshuffled folds push the AUC below 0.5
BOOTSTRAP_B = 1_000
PURITY_K = 10
N_CLUSTERS = 8

# ============================================================ specifications (main choices)
# population
POP_ALL_HOLDERS = "all_holders"       # every address with a positive balance <- main
POP_ACTIVE = "active"                 # addresses with a transfer in the window <- sensitivity
MAIN_POPULATION = POP_ALL_HOLDERS

# direction: flow statistics use the sender side; the receiver side is a sensitivity row
MAIN_DIRECTION = "out"

# time: computed weekly, then averaged; the pooled window is a sensitivity row
# (they differ a lot: LINK 421 vs 230, a factor of 1.83)
MAIN_AGGREGATION = "weekly"

# outlier weeks: from v2 cleaning works on transfers (airdrop rule + zero-value),
# not whole weeks. The detector is kept to show that no outlier week remains.
EXCLUDE_OUTLIER_WINDOWS = False
OUTLIER_NODE_MULTIPLIER = 3           # a week with more than 3x the median number of addresses is an outlier

# ============================================================ data cleaning (v2)
# The rules were fixed before the v2 results were seen. The airdrop rule was written
# after the week-7 event of v1 had been seen, which the paper states. Main =
# zero-value and airdrop transfers removed.
# Zero-value transfers: removed in main (a common address-poisoning technique; they
# carry no value but add counterparties)
DROP_ZERO_VALUE = SPEC in ("main", "keep_airdrop", "overwrite")
DROP_AIRDROP = SPEC in ("main", "keep_zero", "overwrite")

# Dust airdrop: if a sender, within some sliding AIRDROP_WINDOW, sends one transfer
# with 0 < amount < AIRDROP_MAX_AMT (in tokens) to each of more than AIRDROP_N
# distinct receivers, all of its transfers with 0 < amount < AIRDROP_MAX_AMT in the
# 90 days are removed; its transfers of normal size are kept.
AIRDROP_WINDOW = "48h"
AIRDROP_MAX_AMT = 0.01
AIRDROP_N = 1_000
# sensitivity (Appendix B): N and the threshold vary one at a time
AIRDROP_N_GRID = (100, 500, 1_000)
AIRDROP_AMT_GRID = (0.01, 0.1)

# zero address: removed on both sides (mint/burn is not market activity)
ZERO_ADDR = "0x0000000000000000000000000000000000000000"
DEAD_ADDR = "0x000000000000000000000000000000000000dead"
BURN_ADDRS = frozenset({ZERO_ADDR, DEAD_ADDR})

# Active addresses come from the cleaned transfers and exclude the zero and burn
# addresses (v1 counted them: LINK 642,126 = 642,124 + 2, UNI 38,667 = 38,666 + 1).

# ============================================================ verified entities
# non-circulating reserves held by the issuer / protocol (public Etherscan tags)
ISSUER_RESERVES = {
    "LINK": frozenset({          # Chainlink: Noncirculating Supply, 7 x 30,000,000
        "0x0dffd343c2d3460a7ead2797a687304beb394ce0",
        "0x5a8e77bc30948cc9a51ae4e042d96e145648bb4c",
        "0xe0b66bfc7344a80152bfec954942e2926a6fca80",
        "0x9bbb46637a1df7cadec2afca19c2920cddcc8db8",
        "0x8652fb672253607c0061677bdcafb77a324de081",
        "0x7594eb0ca0a7f313befd59afe9e95c2201a443e4",
        "0x76287e0f7b107d1c9f8f01d5afac314ea8461a04",
    }),
    "UNI": frozenset({
        "0x1a9c8182c09f50c8318d769245bea52c32be35bc",   # UNI Timelock
        "0x090d4613473dee047c3f2706764f49e0821d256e",   # UNI Token Distributor
    }),
}

# verified one by one on Etherscan / Arkham (highest priority, overrides the compilation)
MANUAL_ENTITIES = {
    "0x28c6c06298d514db089934071355e5743bf21d60": "Binance",     # Binance 14
    "0xf977814e90da44bfa03b6295a0616a897441acec": "Binance",     # Hot Wallet 20
    "0x5a52e96bacdabb82fd05763e25335261b270efcb": "Binance",     # Binance 28
    "0x51c72848c68a965f66fa7a88855f9f7784502a7f": "Wintermute",  # Arkham; Arbiscan: Market Maker
    "0xbc10f2e862ed4502144c7d632a3459f49dfcdb5e": "Chainlink Staking Pool",
    ZERO_ADDR: "Burn",
    DEAD_ADDR: "Burn",
}

# names too generic to be an entity when merging (two MEV bots are not one firm)
GENERIC_LABELS = frozenset({
    "mev bot", "mev", "bot", "deployer", "contract deployer", "null address",
    "fake_phishing", "phishing", "unlabelled contract", "unlabelled",
    "unlabelled routing contract", "compromised contract", "eoa", "wallet",
    "token", "contract", "unknown", "suspected",
})
# alert labels sit on victim addresses (Multichain Hack Alert covers 2,923); merging
# them would create a giant participant out of nothing
ALERT_KEYWORDS = ("hack alert", "alert", "phish", "exploit", "scam",
                  "victim", "hunter", "blocked", "heist")

# ============================================================ hidden brokers
# definition: top 1% of the is_core score & balance <= median & unlabelled
BROKER_PROB_PCT = 99          # top 1%
# Lower bounds added: the v16 definition admitted degenerate nodes with
# counterparties = 1 and betweenness = 0 (5 of 29 on UNI, including two pairs of
# vanity twins); zero betweenness contradicts "sitting on critical paths".
BROKER_MIN_COUNTERPARTIES = 5
BROKER_REQUIRE_POSITIVE_BETWEENNESS = True

# Ensemble over seeds. Introduced in v1, when runs were not reproducible (the cause
# was later traced to unseeded Python random, see TRAIN_DEVICE above). A single seed
# is still one draw of the representation, so the brokers come from an ensemble
# over ten seeds; how often a node is selected doubles as a stability measure.
BROKER_CONSENSUS_SEEDS = tuple(range(42, 52))   # the same seeds as 02_c1
BROKER_CONSENSUS_MIN_FRAC = 0.5                 # vote: selected under at least half of the seeds
BROKER_CORE_SET_FRAC = 0.9                      # threshold of the "high confidence" subset
N2V_CONSENSUS_N = 5                             # node2vec seeds for its ensemble (slower)

# ensemble used for the main set:
#   "rank"  average the percentile ranks across seeds, then cut the top 1% once
#           (standard; insensitive to each seed's probability scale; least
#           boundary jitter) -- main
#   "vote"  cut the top 1% per seed, then vote (sensitive to the hard threshold;
#           a stability diagnostic only)
BROKER_ENSEMBLE = "rank"

# The betweenness baseline must be the same size as the GNN set: the GNN side is
# tightened by the ensemble, so a fixed percentile on the betweenness side would not
# be comparable. True = take a top-K of the same size.
BROKER_SIZE_MATCHED_BASELINE = True

# 04_c2_procrustes: node cap per weekly window. With raw data LINK week 7 (the
# phishing airdrop) has 550k nodes, too slow and memory-hungry to train, and not
# representative of routing.
PROCRUSTES_MAX_NODES = 100_000

# 03_c2_weekly: size of the elite set. v16 used top-50 (retention 53% / 48%, mean
# flow share 0.748) from a superseded script with overwritten edges; recomputed here.
ELITE_TOP_K = 50

# ============================================================ rule layer (UNI)
# Three layers: ownership / routing / rules.
# proposalThreshold() / quorumVotes() of GovernorBravo 0x408E...24C3 read on chain at
# the first and last block of the window (24,738,010 and 25,390,910): 1M / 40M at
# both. v1's 2.5M was wrong. Both count delegated votes (getPriorVotes), not balances.
GOV_PROPOSAL_THRESHOLD = 1_000_000        # 1M UNI = 0.1%
GOV_QUORUM = 40_000_000                   # 40M UNI votes in favour
GOV_GOVERNOR = "0x408ed6354d4973f66138c91495f2f2fcbd8724c3"
# L1 bridges that deliver UNI burned on L2s to 0xdEaD on Ethereum (public Etherscan tags, checked 2026-10-07)
UNI_FEE_BRIDGES = {
    "0x3154cf16ccdb4c6d922629664174b904d80f2c35": "Base: Base Bridge",
    "0xa3a7b6f88361f48403514059f1f16c8e78d60eec": "Arbitrum One: L1 ERC20 Gateway",
    "0x99c9fc46f92e8a1c0dec1b1747d010903e884be1": "Optimism: Gateway",
    "0x81014f44b0a345033bb2b3b21c7a1a308b35feea": "Unichain: Unichain L1 Standard Bridge",
}
# addresses that cannot vote (governance contracts, burn addresses)
GOV_NON_VOTING = frozenset(ISSUER_RESERVES["UNI"]) | BURN_ADDRS
# custodial addresses: the tokens belong to customers and exchanges usually do not
# vote them; a separate sensitivity row
GOV_CUSTODIAL_HINTS = ("binance", "coinbase", "kraken", "okx", "huobi",
                       "bitfinex", "kucoin", "bybit", "gate.io", "crypto-com")

# ============================================================ reference points
# Industry benchmarks are not hard-coded here: see benchmarks/ (FDIC SOD, ECB SSI,
# Nilson 1241); every number is computed from public data or taken from an official
# release. v1's Canada / Sweden 2,400 / LPMCL / Visa-Mastercard 5,150 / FFIEC 935
# and the Lorenz benchmarks had no checkable source and were removed.

# DOJ/FTC thresholds. The Merger Guidelines of 18 Dec 2023 replaced the 2010
# Horizontal Merger Guidelines and lowered the structural presumption from 2,500 to
# 1,800. Both are reported in the text and drawn in the figures. The 2023 guidelines
# define only "highly concentrated" (> 1,800).
DOJ2023_HIGH = 1_800

DOJ_UNCONCENTRATED = 1_500
DOJ_HIGHLY_CONCENTRATED = 2_500
