# 同一本账，不同结论（The Same Ledger, Different Verdicts）

**测量规格如何决定链上集中度**

Jintao Liu\*、Zhimo Ji\*（墨尔本大学计算与信息系统学院）、Xuzhe Lin（悉尼大学数学与统计学院）

\* 共同第一作者 · [English](README.md)

[![arXiv](https://img.shields.io/badge/arXiv-2609.24176-b31b1b.svg)](https://arxiv.org/abs/2609.24176)
[![Data DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23329575.svg)](https://doi.org/10.5281/zenodo.23329575)

---

一条公链是否"去中心化"，常常只凭引用一个集中度指标就下了结论。本仓库包含论文的
数据流程、结果和稿件。论文在同一个 90 天窗口里研究了两个 ERC-20 账本：Chainlink
（LINK）和 Uniswap（UNI）。在这两本账上，结论既取决于账本本身，也取决于指标怎么
设定。

本仓库对应 **arXiv v2**（release `v2.0`）。相对第一版的全部改动列在论文附录 E。

## 主要结论

- **规格选择会改变指标。** 在持有者人群、地址类型、实体合并三项选择的 18 种组合下：
  - UNI 的余额 HHI 从 **108 到 3,281**（LINK：115 到 562）；
  - 余额 Gini 最多只变 0.0063（UNI）和 0.0129（LINK）。
- **不同的选择作用在分布的不同一端。**
  - 地址类型和实体合并作用在顶端，改变的是 HHI。
  - 余额下限作用在尾部。加 100 美元下限后，1 − Gini 变为原来的 4.7 倍（UNI）和
    2.6 倍（LINK），HHI 最多只变 0.5%。
  - 只算转账活跃地址，两端都会变。
- **实现细节同样关键。**
  - LINK 上有一次协同的粉尘空投：80 个发送方共 549,598 笔转账。按规则剔除后，
    活跃 LINK 持有者的余额 HHI 从 135 变为 375。
  - 同一对地址之间的重复转账，如果被覆盖而不是累加，图中会丢掉 85.9% 的转账量。
- **所有权和路由是两回事。**
  - 所有权极度不均：Gini 0.990（LINK）、0.998（UNI）。
  - 路由并不集中：周度流量 HHI 421（LINK）、386（UNI）。
- **学习得到的表示对选出隐藏经纪人帮助不大。** 隐藏经纪人判据在 LINK 上选出
  22 个地址，在 UNI 上选出 9 个。在盲评、按度数匹配的对照实验中，学习得到的
  表示在对手方数量之外没有可检测的额外作用：能核实为具名路由服务的比例是
  50% 对 45%，单侧 Fisher 检验 *p* = 0.49。
- **按委托票数看，治理的结论和按余额看不同。** 按委托票数计，4 个 UNI 委托人
  就能达到 4,000 万票的法定人数；49 个有提案资格的委托人中，没有一个参与该代币
  的路由。

| | LINK（预言机） | UNI（治理） |
|---|---|---|
| 窗口内转账（原始） | 1,233,497 | 433,856 |
| 快照区块 25,390,910 的持有者 | 885,012 | 382,972 |
| 清洗后的转账活跃地址 | 132,059 | 37,153 |
| 18 种规格下的余额 HHI | 115 – 562 | 108 – 3,281 |
| 余额 Gini（全部持有者） | 0.9898 | 0.9977 |
| 周度流量 HHI（地址 / 实体合并） | 421 / 654 | 386 / 667 |
| 隐藏经纪人（两币共有） | 22（4） | 9（4） |

观测窗口：2026-03-26 00:00 至 2026-06-25 00:00 UTC。余额取窗口最后一个区块。

## 目录结构

```
.
├── paper/
│   ├── main.tex、sections/、bib_v2.tex   稿件（arXiv v2）
│   ├── numbers.tex                       正文中的全部数字，由脚本生成
│   └── figures/                          三张图
├── requirements.txt、requirements-lock.txt
└── gnn-decentralization/
    ├── config.py              所有路径、阈值、随机种子、超参数
    ├── common.py              读数、清洗、指标、建图、GraphSAGE
    ├── 00_data_check.py … 07_governance.py   主流程
    ├── 08_figures.py          三张图（只读结果文件）
    ├── 11_random_control.py   盲评、按度数匹配的对照实验
    ├── v2_*.py                清洗报告、敏感性分析、自助法区间、链上核对（价格、费用合约）
    ├── benchmarks/            用公开数据计算的 HHI 基准，附原始下载
    ├── make_numbers.py        生成 paper/numbers.tex，并逐条用数字核对正文的定性表述
    ├── paper_audit.py         找出稿件中手写的数字
    ├── reproduce.sh           按顺序运行全部脚本
    ├── sql/                   BigQuery 抽取（v2）与委托快照
    ├── extract_data.sql       第一版的抽取脚本（v1 对照用）
    ├── labels/                存档的 Etherscan 标签快照
    ├── verification/          人工核验与盲评记录
    ├── results/               主规格的派生结果
    ├── results_spec_*/        其他清洗与边权规格
    ├── results_v1/            第一版结果（v1 → v2 对照用）
    └── results_v16_legacy/    旧构造保留的一个文件
```

## 数据

原始数据不放在本仓库，因为其中一个文件超过了 GitHub 的单文件上限。数据存档在
Zenodo（DOI：[10.5281/zenodo.23329575](https://doi.org/10.5281/zenodo.23329575)），文件为 `data.zip` 和校验文件 `SHA256SUMS.txt`。
在 `gnn-decentralization/` 下解压，会生成 `data/`：

| 文件 | 内容 | 如何重建 |
|---|---|---|
| `data/v2/v2_transfers.parquet` | 窗口内全部 LINK 与 UNI 转账 | `sql/v2_transfers.sql` |
| `data/v2/v2_balances.parquet` | 区块 25,390,910 的余额 | `sql/v2_balances.sql` |
| `data/v2/uni_delegation_snapshot.parquet`、`uni_delegate_votes.parquet` | 同一区块的 UNI 委托关系与票数 | `sql/fetch_uni_delegation.py`（公开 RPC） |
| `data/*.csv` | 第一版抽取的数据 | `extract_data.sql`；只有 `v2_data_check.py` 用到 |

查询读取 `bigquery-public-data.crypto_ethereum.token_transfers`，
`sql/download_v2.py` 负责运行查询并写出 parquet 文件。

## 复现

```bash
python3.13 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
cd gnn-decentralization
unzip /path/to/data.zip    # 从 Zenodo 下载
./reproduce.sh
```

`reproduce.sh` 按依赖顺序运行全部脚本：

1. 清洗；
2. 三个规模的建图与嵌入；
3. 四种替代规格；
4. 自助法区间与链上核对；
5. 出图并生成 `paper/numbers.tex`。

在 Apple 芯片的 CPU 上约需三小时。有几步要从以太坊和 L2 的公开 RPC 读取历史状态，
需要联网。

训练在 CPU 上以确定性算法运行；完整重跑一遍 `reproduce.sh`，除 `manifest.csv`
里的时间戳外，所有结果文件逐字节相同。如果只想用存档的 `results/` 重建论文的数字和图，运行 `make_numbers.py` 和
`08_figures.py` 即可。编译论文：在 `paper/` 下运行 `latexmk -pdf main.tex`。

## 存档内容与位置

| 内容 | 位置 |
|---|---|
| 标签快照（2026-08-26 获取，MD5 `16792aac5afd369e6b847c3f0aad1df4`） | `labels/etherscan_labels_2026-08-26.json` |
| 含节点特征的图 | `results/graph_*_1w.npz`、`graph_*_5w.npz` |
| 每个集成结果背后的嵌入及指纹 | `results/emb_*_1w_s*.npy` 与 `.fp` |
| 隐藏经纪人集合与聚类结果 | `results/hidden_brokers_*.csv`、`c3_typology_*.json` |
| 被空投规则标记的发送方 | `verification/airdrop_senders_*.csv` |
| 盲评对照：清单、答案、已知身份、结果 | `verification/control_*_v2.csv`、`known_identities_v2.csv`、`results/random_control.json` |
| 经纪人的 Etherscan 实时标签（2026-10-06） | `verification/broker_live_labels_2026-10-06.csv` |
| UNI 费用机制：销毁记录，以太坊与四条 L2 的 releaser | `verification/uni_fee_burns.md`、`uni_l2_firepits.csv`、`raw/` |
| 快照时的 Chainlink 价格（喂价合约、轮次、报价） | `results/prices_snapshot.json` |
| 第一版的核验记录 | `verification/broker_identities.csv`、`verification/v1/` |

## 决定能否复现的四个细节

- **边权必须累加。** `networkx.from_pandas_edgelist` 建 `DiGraph` 时，同一有序
  地址对只保留最后一条记录，而且不给任何提示。`common.build_graph()` 显式累加
  重复的地址对。覆盖边权会改变什么，见论文第 4.6 节。
- **标签只用存档快照。** 上游标签库对以太坊的最后一次抓取是 2023 年 6 月。
  `common.load_labels()` 只读存档文件，并把 173 条仅大小写不同的条目合并。
- **所有随机源都设了种子。**
  - PyTorch Geometric 的 `negative_sampling` 从 Python 的 `random` 模块取随机数，
    所以 Python、NumPy、PyTorch 三者都要设种子。
  - 在 CPU 上用确定性算法训练。
  - 给 gensim 一个稳定的哈希函数。
  - 活跃度排名的并列按地址打破，图中节点按地址顺序插入。
- **人工核验用 Etherscan 的代币转账视图。** 被其他合约调用的路由合约，自身的
  交易记录很少。

## 引用

```bibtex
@article{liu2026sameledger,
  title   = {The Same Ledger, Different Verdicts: How Measurement Specification
             Determines On-Chain Concentration},
  author  = {Liu, Jintao and Ji, Zhimo and Lin, Xuzhe},
  journal = {arXiv preprint arXiv:2609.24176},
  year    = {2026}
}
```

## 许可

代码：MIT（见 `LICENSE`）。稿件：CC BY-NC-ND 4.0，以 arXiv 上的版本为准。
