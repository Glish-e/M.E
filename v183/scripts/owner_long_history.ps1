# owner_long_history.ps1 — W6 (v1.8.0): resumable long-history build
# (PowerShell twin of owner_long_history.sh). OWNER-RUN ONLY.
# Resumes via ml_data/cache/dates/*.json; stops on quota exhaustion with
# the resume command; prints the coverage report after each pass.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
$dates = if ($args[0]) { $args[0] } else { 120 }
$sectors = if ($args[1]) { $args[1] } else { "all" }
New-Item -ItemType Directory -Force -Path owner_results | Out-Null
for ($pass = 1; $pass -le 10; $pass++) {
  "[owner_long_history] pass $pass — building the next batch"
  & python3 ml_dataset.py --dates $dates --sectors $sectors `
      --max-dates 6 *>> owner_results\long_history_log.txt
  $rc = $LASTEXITCODE
  if ($rc -ne 0) {
    "[owner_long_history] ml_dataset exit $rc — quota exhausted or a"
    "fetch failed. NOTHING lost: finished dates stay cached. Resume:"
    "re-run this script (same arguments); tighten --max-dates 3."
    exit $rc
  }
  "[coverage] pass ${pass}: see ml_data\manifest.json (build.dates_*," +
  " rows, label_coverage, nan_rate_per_feature)"
  $done = 0
  try {
    $m = Get-Content ml_data\manifest.json | ConvertFrom-Json
    $done = [int]$m.build.dates_built
  } catch {}
  if ($done -ge $dates) {
    "[owner_long_history] target reached ($done/$dates month-ends)."
    "next: python3 ml_train.py  (retrain; then master.py --backtest)"
    exit 0
  }
}
"[owner_long_history] 10 passes done — re-run to continue"
