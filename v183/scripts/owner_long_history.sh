#!/usr/bin/env bash
# owner_long_history.sh — W6 (v1.8.0): resumable LONG-HISTORY dataset
# build under FREE-TIER limits. OWNER-RUN ONLY (R11/R12): the build
# needs network + API keys; the agent never runs it.
#
# How it resumes: ml_dataset caches each finished month-end in
# ml_data/cache/dates/<date>.json — re-running the SAME command skips
# them and builds the next batch (--max-dates per invocation, a free-
# tier-friendly cadence). Quota exhaustion surfaces as ml_dataset's own
# non-zero exit + message; this script STOPS (does not loop into a wall),
# says how to resume, and exits with ml_dataset's code.
#
# Usage: bash scripts/owner_long_history.sh [DATES] [SECTORS]
#   DATES   total month-ends wanted (default 120 = ~10 years)
#   SECTORS default 'all'
set -u
cd "$(dirname "$0")/.."
DATES="${1:-120}"
SECTORS="${2:-all}"
mkdir -p owner_results
rc=0
built=0
for pass in 1 2 3 4 5 6 7 8 9 10; do
  echo "[owner_long_history] pass $pass — building the next batch"
  MASTER_NET=${MASTER_NET:-online} python3 ml_dataset.py \
    --dates "$DATES" --sectors "$SECTORS" --max-dates 6 \
    2>&1 | tee -a owner_results/long_history_log.txt
  rc=${PIPESTATUS[0]}
  if [ $rc -ne 0 ]; then
    echo "[owner_long_history] ml_dataset exit $rc — quota exhausted or"
    echo "  a fetch failed. NOTHING is lost: finished dates stay cached."
    echo "  resume later: re-run this script (same arguments); or tighten"
    echo "  the cadence: --max-dates 3; check the message above for the"
    echo "  exact provider (FRED / SEC EDGAR / Finnhub / Yahoo)."
    exit $rc
  fi
  # coverage report from the manifest after each pass
  python3 - "$pass" << 'PY'
import json, sys
try:
    m = json.load(open("ml_data/manifest.json"))
    b = m.get("build", {})
    print(f"[coverage] pass {sys.argv[1]}: dates {b.get('dates_built')} built"
          f" / {b.get('dates_cached')} cached / {b.get('dates_failed')} failed"
          f" · rows {m.get('rows', {}).get('total', '?')} · labels "
          f"{m.get('label_coverage', {}).get('usable', '?')} usable · nan_rate "
          f"{sum(m.get('nan_rate_per_feature', {}).values()) / max(1, len(m.get('nan_rate_per_feature', {}))):.1%} mean"
          + (" · SYNTHETIC!" if (m.get("data_provenance") or {}).get("class") != "REAL-API" else ""))
except Exception as e:
    print(f"[coverage] manifest unreadable ({e}) — nothing built yet")
PY
  done_n=$(python3 -c "import json;print(json.load(open('ml_data/manifest.json'))['build']['dates_built'])" 2>/dev/null || echo 0)
  if [ "${done_n:-0}" -ge "$DATES" ]; then
    echo "[owner_long_history] target reached ($done_n/$DATES month-ends)."
    echo "  next: python3 ml_train.py   (retrain; then master.py --backtest)"
    exit 0
  fi
done
echo "[owner_long_history] 10 passes done, ${done_n:-?}/$DATES month-ends — re-run to continue"
