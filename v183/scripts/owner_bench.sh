#!/usr/bin/env bash
# owner_bench.sh — W2 (v1.8.0): REAL-data benchmark, run by the OWNER on
# the machine that has network + API keys (R11: the agent never runs
# this; sandbox timings are fixture-labelled and never real speed).
# Writes owner_results/bench_*.txt with wall times and last lines.
# Safe: --backtest and ml_train write only reports/models you point
# them at; nothing here places trades or needs the sandbox.
set -u
cd "$(dirname "$0")/.."           # repo root (scripts/ is one level down)
mkdir -p owner_results
T() { date -u +%Y-%m-%dT%H:%M:%SZ; }

run() {  # run <name> <cmd...>
  name="$1"; shift
  out="owner_results/bench_${name}.txt"
  echo "[$(T)] bench: $name" | tee -a "$out"
  t0=$(date +%s.%N)
  "$@" >> "$out" 2>&1
  rc=$?
  t1=$(date +%s.%N)
  wall=$(awk -v a="$t0" -v b="$t1" 'BEGIN{printf "%.2f", b-a}')
  echo "[exit $rc · ${wall}s] $(tail -n 1 "$out")" | tee -a "$out"
  echo >> "$out"
}

echo "owner_bench — $(T) · host $(uname -s) · python $(python3 -V 2>&1)" \
     | tee owner_results/bench_header.txt

# 1. import + CLI floor (no engines, no network)
run cli_floor python3 master.py --version

# 2. stub quick run (regression guard; MASTER_STUBS, no network)
run stub_quick env MASTER_STUBS=1 MASTER_NET=offline \
  python3 master.py --mode quick --quiet

# 3. offline standard run from the disk caches (no sockets)
run offline_standard python3 master.py --mode standard --offline --quiet

# 4. ONLINE standard run (network + keys; the engine-fetch profile)
run online_standard python3 master.py --mode standard --quiet

# 5. integration backtest on the CURRENT dataset (real harvests)
run backtest python3 master.py --backtest --quiet

# 6. ml_train retrain (real dataset; writes under ml_data/models by
#    default — pass --out to a scratch dir first if you prefer)
run ml_train python3 ml_train.py

# 7. the long-history dataset build (free-tier; see OWNER_RUN for the
#    resumable flags) — timed build of 6 new month-ends as a sample
run dataset_build6 python3 ml_dataset.py --max-dates 6

echo "[$(T)] owner_bench done — files in owner_results/" | tee -a owner_results/bench_header.txt
echo "Compare stub_quick/offline_* against the v1.8.0 fixture numbers in"
echo "evidence/w18_perf.md (those are R9-labelled fixture timings, NOT"
echo "real speed); real speed lives only in owner_results/."
