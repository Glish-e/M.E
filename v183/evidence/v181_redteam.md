# v1.8.1 red-team — five ways the core assertions could be false,
# each with the check that was actually run (2026-11-19)

1. "The breaker makes host calls fail instantly" could be false if some
   wrapper CAUGHT BreakerOpenError and retried anyway. CHECK: grep — the
   ONLY catch of BreakerOpenError is me/netguard.deferred_pass, where it
   marks the item SKIPPED (never a retry); the 50-checks loop in
   TestNetGuardBreaker.test_opens_and_fails_fast ran in < 0.5 s.
   [VERIFIED: grep -n "BreakerOpenError" me/netguard.py master.py ->
   deferred_pass skip path only; suite green.]

2. "The process exits within seconds despite stuck non-daemon workers"
   could be false if _exit_sweep's grace loop itself hung. CHECK: the
   subprocess test with a 60 s sleeper + master._exit_sweep(0) returned
   in < 5 s (wall measured) and never printed UNREACHABLE; the hanging
   stub-layer run_pipeline completed at ~1.5 s under RUN_BUDGET_S=1.5.
   [VERIFIED: test_exit_sweep_prompt_despite_stuck_threads +
   test_pipeline_budget_ends_hanging_layer, suite green.]

3. "The new tests only pass because the net guard is OFF (stubs/
   fakes)" could be false. CHECK: (a) TestNetGuardWiringInPipeline
   installs the guard for online fake runs and asserts the ledger dump;
   (b) the decision-hash gate ran the PRISTINE v1.8.0 tree vs this tree
   with the guard INSTALLED and a HEALTHY loopback server behind every
   quality fetch — hash a023714c...c35e8 IDENTICAL, 5 ok / 0 failed /
   0 skipped recorded by the guard (evidence/v181_decision_hash.txt).
   [VERIFIED.]

4. "FETCH HEALTH numbers could be fabricated counters" — CHECK: an
   inline run made 7 guarded urlopen calls to a real loopback HTTP
   server; server hits == 7 == ledger ok == 7, and the docs/CLI.md
   sample is the byte capture of exactly such a run.
   [VERIFIED: "server hits: 7 ledger ok: 7 PASS".]

5. "The suite is not really hermetic (real network touched)" — CHECK:
   the full-suite log contains ZERO 'preflight: api|fred|sec|yahoo|
   finnhub' real-host lines (grep -c 'preflight: api' == 0); the
   suite pins MASTER_NET_PREFLIGHT_HOSTS="" and master treats a SET env
   (even empty) as the override; MASTER_NET=online|offline pins skip
   preflight entirely. The decision-hash + capture drivers pin
   loopback-only hosts. [VERIFIED: suite4 log grep = 0 matches; env
   matrix all cells green.]

Bonus (hash-luck): the CONFIG diff canonicalises sets through
me.core._canonical_json in isolated per-tree processes, so frozenset
iteration order can never fake an addition/change
(evidence/v181_config_diff_v180.txt: 13 additions + 1 value change
only).
