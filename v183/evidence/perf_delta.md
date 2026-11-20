# perf_delta.md — §6.2/§6.4: the gap explained, before vs after, what was kept

Machine: the build sandbox (2 vCPU, 4 GB RAM, Python 3.12.16). Real network.
Numbers: evidence/perf_before.txt / perf_after.txt (bench.py, one command).

## 6.2 The 78 s mystery (phase-5 handoff said ~15 s warm)
Two separate effects, both now measured and fixed/disclosed:
1. ATTRIBUTION BUG (fixed): v1.4.0 charged the WHOLE run's wall clock to
   every prefetch layer (starts[name] at t0, elapsed computed at the end).
   "macro 77.9s · quality 77.9s" was ONE 78 s wall, not two 78 s layers.
   v1.5.0 stamps each layer's OWN completion (done[name]) — macro now
   reports its real 0.2 s (offline snapshot) / 12-150 s (online public
   tier under load).
2. COLD vs WARM: a standard-mode run scores the whole quality universe
   (~614 names). Cold = network fetching (~1.3 s/name measured: 371 names
   in 480 s) -> 8-25 min. Warm = the engine still re-reads and re-parses
   ~614 cached companyfacts JSONs (~1.6 GB) + PIT availability math every
   run: ~73 s of pure ENGINE compute (measured in-thread profile:
   get_company 119.7 s of 183 s profiled, fact_available_date 4.96M calls
   25.5 s, normalize_companyfacts 26.5 s). H1 forbids touching quality.py,
   so that ~73 s is the warm floor for STANDARD depth.
   The fast tier: --mode quick (watchlist-only peers) + --offline = 5.8 s
   total on the default 22-name watchlist (measured).
3. meds online re-fetches the FRED public tier EVERY online run (its own
   tier ladder; cache is only a fallback): 12 s quiet, up to ~150 s while
   quality hammers the same pipe (GIL/network contention). Offline macro
   is 0.2 s from the materialised snapshot. Engine design, disclosed.

## 6.4 benchmark | before | after | change kept?
| benchmark                        | before      | after       | kept? |
|----------------------------------|-------------|-------------|-------|
| (a) import --version             | 17 ms       | 16 ms       | n/a — already lazy (no numpy/sklearn/pandas at import; verified by test) |
| (b) --selftest wall              | 11.4 s /186 | 18.8 s /256 | n/a — 70 more tests, not a regression |
| (c) stub run (default watchlist) | 0.3 s       | 0.4 s       | kept — provenance lines; 25x inside the 10 s guard (test-enforced) |
| (d) warm offline, standard depth | 77.9 s      | 75.2 s      | -3.5% (yfinance-bypass fix removed dead price attempts); floor = engine universe pass ~73 s (H1) |
| (d') warm offline, quick depth   | (recipe did not compose before: offline macro ERRORED) | 5.8 s | kept — the new fast tier |
| (e) cold online (MU NVDA AAPL)   | 148.3 s     | 156.2 s     | network-bound, +-5% run-to-run variance; not master code |
| per-layer timings                | wall clock charged to every layer | own completion stamps | kept — correctness fix |

Candidates examined and NOT kept (rule: >= 10% or revert; the warm path is
engine-bound, H1):
- lazy numpy/sklearn/joblib imports: already lazy (importtime shows none).
- build universe/peer refs once per run: already once (peek_refs, phase 3).
- cache sector/peer mappings module-level: engine-internal (H1).
- renderer sorting/formatting, skip render for --json: render already 0.0 s
  and --json never renders.
- vectorise the sizer: measured microseconds for a 22-name book.
- fetch each price series once: engine-internal (already memo+disk cached).
- overlap layer prefetch: already concurrent since phase 3; the remaining
  wall is engine compute + GIL contention (macro's pandas work waits for
  slices while quality parses JSON — visible as macro's inflated wall time
  in concurrent runs; its OWN work is 0.2 s offline).
- one JSON load per cached object: engine-internal (H1).
Conclusion: no master-side change clears the 10% bar on the warm standard
path; the honest speed story is mode choice (quick+offline 5.8 s) plus the
attribution fix, both shipped and test-covered.
