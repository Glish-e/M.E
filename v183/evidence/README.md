# evidence/ — what is proven, and HOW (read me before trusting a number)

## Real-network proofs are HISTORICAL (pre-v1.8)

The R1-R8 captures in `final_real_runs.txt` predate the v1.8.x hardening
passes (R5 shows "master v1.5.0 doctor"). They prove the v1.5.0 online
paths only. Every v1.8.x network-behaviour claim below is backed by
LOOPBACK or FAKE-module evidence, which is honest but not the same thing.

## v1.8.3 claims with NO real-network proof yet (loopback/fake only)

- netguard preflight total budget (`NET_PREFLIGHT_TOTAL_S`) — loopback
  servers + mocked resolvers only (F1's DNS watchdog: the permanent-hang,
  5 s-stall and mixed-host cases are unit-proven with mocked getaddrinfo;
  a REAL hung resolver on the owner's network is the missing evidence).
- the wrapped yfinance seams (`YfinancePriceClient._download`,
  `_detect_sector_yfinance`) and the capped earnings `wrap_fetch` (F11) —
  proven with FAKE yfinance / hung-provider fakes only; yfinance is
  absent from the build/test environment, and the real-yfinance behaviour
  (version, curl_cffi presence, hang shapes) is exactly what
  `scripts/owner_net_check.sh` captures on the owner's machine.
- `NET_BROWNOUT_S` brownout budgets and the breaker rate rule — loopback
  hang/refused servers only.
- F1's pre-fix DNS-hang bound: v1.8.2 docs CLAIMED a 10 s bound
  ("stops the pass at 10 s"); the stage-1 audit MEASURED the permanent
  resolver hang as UNBOUNDED pre-fix (evidence/net_bounds.md, updated
  v1.8.3). The bound is now enforced in flight by the watchdog.

## Owner verification path (the networked, pinned-stack machine)

1. `bash scripts/owner_net_check.sh` (PowerShell: `owner_net_check.ps1`)
   — prints the yfinance version, curl_cffi importability and one
   time-boxed real call per provider to `owner_results/net_check.txt`
   (key names only, no values).
2. `python3 master.py --mode quick --json` — one real online run
   (compare preflight lines, FETCH HEALTH, wall time vs the 600 s quick
   budget, exit code, decision rows).
3. See `../OWNER_RUN.md` and the stage-2 handoff (`stage2_out/`) for the
   full list, incl. the v2 backtest readout (F2) and the SPY series (gate 3).
