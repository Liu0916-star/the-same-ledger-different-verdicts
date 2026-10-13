-- v2 balances: cumulative net flow over full history, cut at the window end
-- 2026-06-25 00:00:00 UTC (v1 had no cut-off: LINK pulled 2026-06-26,
-- UNI 2026-07-25). Non-zero balances kept; zero address keeps its negative
-- (mint) balance and is excluded downstream.
SELECT
  t.token_address,
  m.address,
  SUM(m.delta) AS balance_raw
FROM (
  SELECT token_address, from_address, to_address,
         SAFE_CAST(value AS BIGNUMERIC) AS v
  FROM `bigquery-public-data.crypto_ethereum.token_transfers`
  WHERE token_address IN ('0x514910771af9ca656af840dff83e8264ecf986ca',
                          '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984')
    AND block_timestamp < TIMESTAMP('2026-06-25 00:00:00 UTC')
) AS t,
UNNEST([
  STRUCT(t.to_address   AS address,  t.v AS delta),
  STRUCT(t.from_address AS address, -t.v AS delta)
]) AS m
GROUP BY t.token_address, m.address
HAVING SUM(m.delta) <> 0
