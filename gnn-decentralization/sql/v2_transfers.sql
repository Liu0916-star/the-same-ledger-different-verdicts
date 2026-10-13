-- v2 transfers: LINK + UNI, window [2026-03-26, 2026-06-25) UTC.
-- Same filter as v1 extract_data.sql; adds log_index / block_number so every
-- record has a unique key (transaction_hash, log_index).
SELECT
  token_address, from_address, to_address, value,
  transaction_hash, log_index, block_number, block_timestamp
FROM `bigquery-public-data.crypto_ethereum.token_transfers`
WHERE token_address IN ('0x514910771af9ca656af840dff83e8264ecf986ca',
                        '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984')
  AND block_timestamp >= TIMESTAMP('2026-03-26 00:00:00 UTC')
  AND block_timestamp <  TIMESTAMP('2026-06-25 00:00:00 UTC')
