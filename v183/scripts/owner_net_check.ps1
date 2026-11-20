# owner_net_check.ps1 — v1.8.2 (N2 owner pack + W2): per-host
# reachability, latency, key-presence check AND the yfinance/transport
# census (PowerShell twin of owner_net_check.sh).
# RUN THIS FIRST when a run is slow. Writes owner_results/net_check.txt
# (key NAMES only, never values). Exit 0 all reachable / 1 some dead.
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force -Path owner_results | Out-Null
$out = "owner_results/net_check.txt"

$hosts = @(
    @{h="api.stlouisfed.org"; why="FRED keyed API (meds)"},
    @{h="fred.stlouisfed.org"; why="FRED public CSV (meds, no key)"},
    @{h="www.sec.gov"; why="SEC ticker map (quality; SEC_USER_AGENT recommended)"},
    @{h="data.sec.gov"; why="SEC submissions/companyfacts (quality)"},
    @{h="query1.finance.yahoo.com"; why="Yahoo chart (quality/earnings)"},
    @{h="finnhub.io"; why="Finnhub earnings (needs FINNHUB_API_KEY, optional)"}
)
$extra = $env:OWNER_NET_CHECK_EXTRA
if ($extra) {
    foreach ($h in ($extra -split ",")) {
        if ($h.Trim()) { $hosts += @{h=$h.Trim(); why="extra (owner-added)"} }
    }
}

$lines = @()
$lines += "OWNER NET CHECK - $((Get-Date).ToUniversalTime().ToString('o'))"
$lines += "keys (NAMES only, never values):"
foreach ($v in @("FREDAPI", "FRED_API_KEY", "SEC_USER_AGENT", "FINNHUB_API_KEY")) {
    $set = [bool](Get-Item env:$v -ErrorAction SilentlyContinue)
    $lines += "  $v : $(if ($set) {'set'} else {'absent'})"
}
$lines += "hosts (DNS + TCP connect, 2 s budget, no payload, no request):"
$okAll = $true
foreach ($entry in $hosts) {
    $h = $entry.h
    $tcp = $null
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $t0 = Get-Date
        $task = $tcp.ConnectAsync($h, 443)
        if (-not $task.Wait(2000)) { throw [System.TimeoutException]::new("timeout") }
        $ms = ((Get-Date) - $t0).TotalMilliseconds
        $lines += "  $h OK   {0,7:0} ms   {1}" -f $ms, $entry.why
    } catch {
        $okAll = $false
        $lines += "  $h DEAD ($($_.Exception.InnerException.GetType().Name))  $($entry.why)"
    } finally {
        if ($tcp) { $tcp.Close() }
    }
}
$lines += "verdict: $(if ($okAll) {'all reachable'} else {'SOME HOSTS DEAD - master''s per-host breaker will fail fast on them; an auto run falls back to offline-from-cache'})"
$lines += ""
$lines += "yfinance / transports (v1.8.2, W2 - master wraps the engine seams; real yfinance cannot be tested in the agent sandbox: UNVERIFIED there)"
$py = @"
import sys
try:
    import yfinance
    print(f"  yfinance: importable, version {getattr(yfinance, '__version__', 'unknown')}")
except Exception as e:
    print(f"  yfinance: NOT importable ({type(e).__name__}) - quality uses its built-in urllib chart client; the wrappers stay dormant")
try:
    import curl_cffi
    print(f"  curl_cffi: importable, version {getattr(curl_cffi, '__version__', 'unknown')} (a non-requests transport yfinance may use; master's yfinance wrappers still cover the call because they wrap the engine seam, not the socket)")
except Exception as e:
    print(f"  curl_cffi: NOT importable ({type(e).__name__}) - yfinance (if present) uses requests, covered by the requests-level process guard as well")
import time, urllib.request
url = ("https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
       "?period1=1704067200&period2=1704153600&interval=1d&events=div,split")
t0 = time.monotonic()
try:
    req = urllib.request.Request(url, headers={"User-Agent": "owner-net-check/1.8.2"})
    with urllib.request.urlopen(req, timeout=10.0) as r:
        body = r.read(256)
    print(f"  capped call (10 s): HTTP {r.status}, {len(body)} bytes read, {(time.monotonic()-t0)*1000:.0f} ms - path OK")
except Exception as e:
    print(f"  capped call (10 s): FAILED after {time.monotonic()-t0:.1f}s ({type(e).__name__}) - the breaker will fail fast on this host; offline-from-cache still works")
"@
try {
    $pyout = $py | python3 - 2>&1
    if (-not $pyout) { $pyout = $py | python - 2>&1 }
    $lines += $pyout
} catch {
    $lines += "  python census failed: $($_.Exception.Message)"
}
$lines | Out-File -FilePath $out -Encoding utf8
$lines | Write-Output
Write-Host "owner_net_check: wrote $out (exit $(if ($okAll) {0} else {1}); key NAMES only)"
if ($okAll) { exit 0 } else { exit 1 }
