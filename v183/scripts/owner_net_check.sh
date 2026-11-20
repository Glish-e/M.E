#!/usr/bin/env bash
# owner_net_check.sh — v1.8.2 (N2 owner pack + W2): per-host
# reachability, latency, key-presence check AND the yfinance/transport
# census (version, curl_cffi importability, one timed capped call).
# RUN THIS FIRST when a run is slow — it tells you which of the six
# engine hosts is dead in seconds. Writes owner_results/net_check.txt
# (NEVER any key values — names only). Loopback-safe: add extra hosts
# with OWNER_NET_CHECK_EXTRA="h1,h2". The capped call (10 s max) is the
# ONLY piece that touches a real provider, and it is capped.
set -u
cd "$(dirname "$0")/.."
mkdir -p owner_results
OUT=owner_results/net_check.txt

python3 - <<'PY' >> "$OUT" 2>&1
import socket, time, os, sys
from datetime import datetime, timezone

HOSTS = [
    ("api.stlouisfed.org", 443, "FRED keyed API (meds)"),
    ("fred.stlouisfed.org", 443, "FRED public CSV (meds, no key)"),
    ("www.sec.gov", 443, "SEC ticker map (quality; SEC_USER_AGENT recommended)"),
    ("data.sec.gov", 443, "SEC submissions/companyfacts (quality)"),
    ("query1.finance.yahoo.com", 443, "Yahoo chart (quality/earnings)"),
    ("finnhub.io", 443, "Finnhub earnings (needs FINNHUB_API_KEY, optional)"),
]
extra = os.environ.get("OWNER_NET_CHECK_EXTRA", "")
for h in extra.split(","):
    if h.strip():
        HOSTS.append((h.strip(), 443, "extra (owner-added)"))

print("OWNER NET CHECK —", datetime.now(timezone.utc).isoformat(timespec="seconds"), "UTC")
print("keys (NAMES only, never values):")
for v in ("FREDAPI", "FRED_API_KEY", "SEC_USER_AGENT", "FINNHUB_API_KEY"):
    print(f"  {v}: {'set' if os.environ.get(v) else 'absent'}")
print("hosts (DNS + TCP connect, 2 s budget, no payload, no request):")
ok_all = True
for host, port, why in HOSTS:
    t0 = time.monotonic()
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        if not infos:
            raise OSError("no address resolved")
        with socket.create_connection(infos[0][4], timeout=2.0):
            pass
        ms = (time.monotonic() - t0) * 1000.0
        print(f"  {host:<28} OK   {ms:7.0f} ms   {why}")
    except Exception as e:
        ok_all = False
        print(f"  {host:<28} DEAD ({type(e).__name__})      {why}")

# v1.8.2 (W2): the yfinance/transport census. Real yfinance is ABSENT
# in the agent environment — these lines are the OWNER-side proof of the
# paths master wraps (YfinancePriceClient._download + _detect_sector).
print("yfinance / transports (v1.8.2, W2 — master wraps the engine seams;")
print("  real yfinance cannot be tested in the agent sandbox: UNVERIFIED there)")
try:
    import yfinance
    print(f"  yfinance: importable, version "
          f"{getattr(yfinance, '__version__', 'unknown')}")
except Exception as e:
    print(f"  yfinance: NOT importable ({type(e).__name__}) — quality uses "
          "its built-in urllib chart client; the wrappers stay dormant")
try:
    import curl_cffi
    print(f"  curl_cffi: importable, version "
          f"{getattr(curl_cffi, '__version__', 'unknown')} "
          "(a non-requests transport yfinance may use; master's yfinance "
          "wrappers still cover the call because they wrap the engine "
          "seam, not the socket)")
except Exception as e:
    print(f"  curl_cffi: NOT importable ({type(e).__name__}) — yfinance "
          "(if present) uses requests, covered by the requests-level "
          "process guard as well")

# ONE timed, capped (10 s) provider call — proves the end-to-end path.
# No keys, one public chart endpoint, capped and timed.
import urllib.request
url = ("https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
       "?period1=1704067200&period2=1704153600&interval=1d&events=div,split")
t0 = time.monotonic()
try:
    req = urllib.request.Request(
        url, headers={"User-Agent": "owner-net-check/1.8.2"})
    with urllib.request.urlopen(req, timeout=10.0) as r:
        body = r.read(256)
    ms = (time.monotonic() - t0) * 1000.0
    print(f"  capped call (10 s): HTTP {r.status}, {len(body)} bytes "
          f"read, {ms:.0f} ms — path OK")
except Exception as e:
    print(f"  capped call (10 s): FAILED after {time.monotonic()-t0:.1f}s "
          f"({type(e).__name__}) — the breaker will fail fast on this "
          "host; offline-from-cache still works")

print("verdict:", "all reachable" if ok_all else
      "SOME HOSTS DEAD — master's per-host breaker will fail fast on them; "
      "an auto run falls back to offline-from-cache")
sys.exit(0 if ok_all else 1)
PY
rc=$?
echo "owner_net_check: wrote $OUT (exit $rc; key NAMES only, never values)"
exit $rc
