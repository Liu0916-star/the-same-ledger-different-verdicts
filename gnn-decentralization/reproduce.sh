#!/bin/zsh
# reproduce.sh -- rebuild every result, figure and number of the paper from the raw
# data in data/v2.
#
# Inputs (not produced here):
#   data/v2/*.parquet   BigQuery extraction (sql/) and on-chain delegation snapshot
#                       (sql/fetch_uni_delegation.py)
#   data/*.csv          v1 data, used only for the regression in v2_data_check.py
#   labels/, verification/, benchmarks/raw/, results_v1/, results_v16_legacy/   archives
# Network: v2_data_check / v2_prices / v2_fee_mechanism / v2_broker_deploy read
#   public Ethereum and L2 RPC endpoints (historical blocks, so results are fixed).
# 11_random_control.py runs only "score": the blind list
#   verification/control_blind_v2.csv holds manual results and must not be
#   overwritten by "sample".
# Time: about 3 hours on an Apple-silicon CPU. Logs: logs/reproduce_*.log
set -e
cd "$(dirname "$0")"
PY=${PY:-../.venv/bin/python}
mkdir -p logs
step(){ local log="logs/reproduce_${(j:_:)${@//[\/. ]/_}}.log"
        echo "=== $(date '+%F %T') ${SPEC:-main} $*"; $PY "$@" > "$log" 2>&1; }

# ---- 1. data checks and cleaning ----
step v2_data_check.py
step 00_data_check.py
step v2_cleaning.py
step v2_prices.py

# ---- 2. main specification ----
for a in "LINK 1w" "UNI 1w" "LINK 5w"; do step 01_build_graph.py ${=a}; done
for a in "LINK 1w" "UNI 1w" "LINK 5w"; do step 02_c1.py ${=a}; done
step 03_c2_weekly.py
step 04_c2_procrustes.py
step 05_c3_roles.py
step 06_concentration.py
step 01_build_graph.py LINK full
step 02_c1.py LINK full
step 07_governance.py

# ---- 3. cleaning and edge-weight specifications (results in results_spec_<SPEC>/) ----
for S in keep_zero keep_airdrop raw overwrite; do
  export SPEC=$S
  for a in "LINK 1w" "UNI 1w"; do step 01_build_graph.py ${=a}; done
  for a in "LINK 1w" "UNI 1w"; do step 02_c1.py ${=a}; done
  step 03_c2_weekly.py
  step 05_c3_roles.py
  step 06_concentration.py
done
unset SPEC

# ---- 4. comparisons, supplementary statistics, on-chain checks ----
step v2_vs_v1.py
step v2_spec_compare.py
step v2_extra_stats.py
step v2_airdrop_case.py
step v2_broker_balance_sens.py
step v2_broker_deploy.py
step v2_auc_ci.py
step v2_spec_combos.py
step v2_fee_mechanism.py
step 11_random_control.py score
step 11_random_control.py score --cex-as-named
step benchmarks/us_bank_hhi.py
step benchmarks/other_benchmarks.py

# ---- 5. figures and numbers ----
step 08_figures.py
cp figures/fig_specification.pdf figures/fig_hhi_benchmark.pdf figures/fig_random_control.pdf ../paper/figures/
step make_numbers.py
step paper_audit.py
echo "=== $(date '+%F %T') DONE"
