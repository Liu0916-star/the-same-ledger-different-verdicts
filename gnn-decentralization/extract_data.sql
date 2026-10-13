-- =============================================================================
-- BigQuery extraction of the FIRST version (v1). v2 uses sql/v2_*.sql; this file is
-- kept because v2_data_check.py compares the v2 transfers with these v1 CSVs.
-- =============================================================================
-- Source: bigquery-public-data.crypto_ethereum.token_transfers
-- Window: [2026-03-26 00:00:00 UTC, 2026-06-25 00:00:00 UTC)
--         half-open, i.e. up to 2026-06-24 23:59:59 UTC
--         identical for both tokens, which the cross-token comparison requires
--
-- Expected counts (v1):
--   LINK transfers: 1,233,497 | active addresses 642,126
--   UNI  transfers:   433,856 | active addresses  38,667
--
-- Note: value is a STRING (to hold uint256) and is divided by 1e18 downstream.
--       The balance queries do not divide in SQL, so both tokens go through
--       exactly the same processing.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- 1. LINK transfers
-- -----------------------------------------------------------------------------
SELECT
  from_address     AS `from`,
  to_address       AS `to`,
  value,
  transaction_hash AS evt_tx_hash,
  block_timestamp
FROM `bigquery-public-data.crypto_ethereum.token_transfers`
WHERE token_address = '0x514910771af9ca656af840dff83e8264ecf986ca'
  AND block_timestamp >= TIMESTAMP('2026-03-26 00:00:00 UTC')
  AND block_timestamp <  TIMESTAMP('2026-06-25 00:00:00 UTC');


-- -----------------------------------------------------------------------------
-- 2. UNI transfers (identical to query 1 except for the contract address)
-- -----------------------------------------------------------------------------
SELECT
  from_address     AS `from`,
  to_address       AS `to`,
  value,
  transaction_hash AS evt_tx_hash,
  block_timestamp
FROM `bigquery-public-data.crypto_ethereum.token_transfers`
WHERE token_address = '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984'
  AND block_timestamp >= TIMESTAMP('2026-03-26 00:00:00 UTC')
  AND block_timestamp <  TIMESTAMP('2026-06-25 00:00:00 UTC');


-- -----------------------------------------------------------------------------
-- 3. LINK balances (net flow over the whole history, not limited to the window;
--    v1 had no cut-off time). One scan: UNNEST expands both sides, half the bytes
--    of a UNION ALL.
-- -----------------------------------------------------------------------------
SELECT
  addr AS address,
  SUM(delta) AS balance
FROM `bigquery-public-data.crypto_ethereum.token_transfers`,
UNNEST([
  STRUCT(to_address   AS addr,  CAST(value AS BIGNUMERIC) AS delta),
  STRUCT(from_address AS addr, -CAST(value AS BIGNUMERIC) AS delta)
])
WHERE token_address = '0x514910771af9ca656af840dff83e8264ecf986ca'
GROUP BY addr
HAVING balance > 0;


-- -----------------------------------------------------------------------------
-- 4. UNI balances (identical to query 3 except for the contract address)
-- -----------------------------------------------------------------------------
SELECT
  addr AS address,
  SUM(delta) AS balance
FROM `bigquery-public-data.crypto_ethereum.token_transfers`,
UNNEST([
  STRUCT(to_address   AS addr,  CAST(value AS BIGNUMERIC) AS delta),
  STRUCT(from_address AS addr, -CAST(value AS BIGNUMERIC) AS delta)
])
WHERE token_address = '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984'
GROUP BY addr
HAVING balance > 0;
