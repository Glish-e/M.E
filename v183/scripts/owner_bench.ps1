# owner_bench.ps1 — W2 (v1.8.0): REAL-data benchmark, Windows PowerShell
# twin of scripts/owner_bench.sh. Run by the OWNER on the machine with
# network + API keys (R11: the agent never runs this). Writes
# owner_results\bench_*.txt with wall times and last lines.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force -Path owner_results | Out-Null

function Run-Bench($name, $cmdEnv, $exe, $argsArr) {
  $out = "owner_results\bench_$name.txt"
  $t0 = Get-Date
  "[{0}] bench: $name" | Tee-Object -FilePath $out -Append
  if ($cmdEnv) {
    foreach ($k in $cmdEnv.Keys) { Set-Item ("Env:" + $k) $cmdEnv[$k] }
  }
  & $exe @argsArr *>> $out
  $rc = $LASTEXITCODE
  $wall = "{0:N2}" -f ((Get-Date) -t0).TotalSeconds
  $last = (Get-Content $out | Select-Object -Last 1)
  "[exit $rc · ${wall}s] $last" | Tee-Object -FilePath $out -Append
  "" | Out-File $out -Append -Encoding utf8
}

"[{0}] owner_bench · host Windows · python {1}" -f (Get-Date -AsUTC),
  (python3 -V 2>&1) | Tee-Object -FilePath owner_results\bench_header.txt

Run-Bench "cli_floor" $null "python3" @("master.py", "--version")
Run-Bench "stub_quick" @{MASTER_STUBS="1"; MASTER_NET="offline"} "python3" `
  @("master.py", "--mode", "quick", "--quiet")
Run-Bench "offline_standard" $null "python3" `
  @("master.py", "--mode", "standard", "--offline", "--quiet")
Run-Bench "online_standard" $null "python3" `
  @("master.py", "--mode", "standard", "--quiet")
Run-Bench "backtest" $null "python3" @("master.py", "--backtest", "--quiet")
Run-Bench "ml_train" $null "python3" @("ml_train.py")
Run-Bench "dataset_build6" $null "python3" `
  @("ml_dataset.py", "--max-dates", "6")

"[{0}] owner_bench done — files in owner_results\" -f (Get-Date -AsUTC) |
  Tee-Object -FilePath owner_results\bench_header.txt -Append
