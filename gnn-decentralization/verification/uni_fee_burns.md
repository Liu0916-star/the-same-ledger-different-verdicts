# UNI fee burns in the observation window (checked 2026-10-06)

v1 removed 1,498 UNI records as "burns". All 1,498 are transfers **to**
`0x000000000000000000000000000000000000dEaD` (none from the zero address), in
three amounts only: 2,000 UNI (971), 4,000 UNI (526), 0.0037 UNI (1); total
4,046,000.0037 UNI.

## They are the UNIfication fee mechanism operating

- Sample L1 transaction `0x7b8375366d1e6f3677fefb4e8e3b55e3df3935fe44629fc20a76a184c5fa9556`:
  a searcher contract (`0x331a5156…07be1bc`) flash-borrows WETH from Morpho,
  triggers Uniswap V2 protocol-fee minting of UNI-V2 LP tokens to
  `0xf38521f130fccf29db1961597bc5d2b60f995f85` (Etherscan verified source:
  `contract TokenJar is Owned, ITokenJar`, uniswap.org), and transfers UNI to
  `0xdEaD` in the same transaction — burn UNI to release accumulated fees.
- Other senders are L2 bridge withdrawals delivered straight to `0xdEaD`:
  Base (`0x49048044…74E97e`, Etherscan "Base: Base Portal"; L1 standard bridge
  `0x3154cf16…2c35`) and Arbitrum (`0xa3a7b6f8…0eec`, "Arbitrum One: L1 ERC20
  Gateway").

## Balance of 0xdEaD (on-chain `balanceOf`, chain_rpc.py)

| point | block | UNI |
|---|---|---|
| 2025-12-27 00:00 UTC (before UNIfication burn) | 24,100,246 | 49,577 |
| 2025-12-29 00:00 UTC (after 100M burn) | 24,114,578 | 100,049,577 |
| window start 2026-03-26 | 24,738,010 | 102,231,580 |
| snapshot (window end) | 25,390,910 | 106,277,580 |

Window increase 106,277,580 − 102,231,580 = 4,046,000, equal to the sum of the
1,498 records. The burn address's 10.63% of supply is 94% the one-off
100M UNIfication burn and 6% ongoing fee burns.

Sources for the governance event: The Block (2025-12-25), Cointelegraph
(2025-12-28), Uniswap protocol-fee documentation.

## Release thresholds (added 2026-10-07, after review)

- Mainnet: `TokenJar.releaser()` = `0x0d5cd355e2abeb8fb1552f56c965b867346d6721`
  (listed as the mainnet Firepit in Uniswap's protocol-fee deployments page);
  `releaser.threshold()` = 4,000 UNI at the first (24,738,010) and last
  (25,390,910) blocks of the window; `TokenJar.owner()` = UNI governance
  timelock `0x1a9c…35bc`, so governance can replace the releaser
  (results/fee_mechanism.json, v2_fee_mechanism.py).
- L2 releasers (updated 2026-10-12, `v2_fee_mechanism.py` → `verification/uni_l2_firepits.csv`):
  addresses taken from the deployments page (archived copy
  `verification/raw/uniswap_protocol_fee_deployments_2026-10-12.html`; it lists
  Base, Optimism, Arbitrum, Unichain and other chains), then checked on chain:
  each chain's `TokenJar.releaser()` equals the listed releaser, and
  `threshold()` = 2,000 UNI on Base, Optimism, Arbitrum and Unichain, all read at
  the L2 block closest to the end of the window (historical state was available
  on each chain's public RPC). This replaces the earlier note that Arbitrum and
  Optimism could only be read at `latest`.
- By lot in the window: 4,000 UNI × 526 from 14 senders (searcher contracts on
  Ethereum); 2,000 UNI × 971 from 5 senders, chiefly "Base: Base Bridge"
  `0x3154cf16…2c35` (671), "Arbitrum One: L1 ERC20 Gateway" (276) and
  "Optimism: Gateway" (18); one record of 0.0037 UNI.
