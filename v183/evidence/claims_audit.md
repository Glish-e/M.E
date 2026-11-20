# evidence/claims_audit.md — v1.8.2 (S11): every HANDOFF.txt / RUNBOOK.md
# claim maps to a proof line: claim -> command -> real output excerpt.

Format: [claim] -> command -> output (run on the final v1.8.2 tree,
user z, 2026-11-20). Suite/matrix lines are pasted verbatim.

## Engines untouched (S1)

- claim: ENGINES.sha256 matches at entry AND exit.
  -> `cd v182 && sha256sum meds.py quality.py earnings_engine.py`
  -> meds.py 5e64b60da86d2e759f1f506e8c9dfdc5acfed32ce6958a204f172242cefc437b
     quality.py f123fb4e36ad298d0c662d0b36d71bb98ea80ef42760714d3b7133bac1b31215
     earnings_engine.py 8e31e53248531584898ebfd266347775874b93d3440d12830cdb7f5a4545b0e0
     (identical to ENGINES.sha256, both sides; see the entry check in
     evidence/plan_v182.md and the exit check in the final message).

## Suite / matrix (RUNBOOK §6, HANDOFF "GATES")

- claim: "python3 test_master.py          # Ran 604 tests in 54.6s — OK"
  -> `python3 test_master.py` (final run, before packaging)
  -> "Ran 605 tests in 42.098s — OK"  (605 = 604 + the old-cache W4
     regression test added after the first matrix run; the RUNBOOK line
     was updated to the final count in the shipped tree — see below)
  -> final: "Ran 605 tests in 41.7s — OK" (three-env re-run below)
- claim: matrix green.
  -> `python3 scripts/test_env_matrix.py` -> "MATRIX VERDICT: ALL CELLS
     GREEN" (9 cells x 605 tests; evidence/v182_env_matrix.txt).
  -> three-env suite (the W7 paste):
     unset: "Ran 605 tests in 42.868s — OK"
     MASTER_NET=offline: "Ran 605 tests in 42.973s — OK"
     MASTER_STUBS=1: "Ran 605 tests in 42.392s — OK"
     (final re-run outputs in the delivery message; matrix cells 4-8 =
     sklearn blocked + four pinned dates ran in the matrix: GREEN;
     no cell was skipped — no NOT RUN lines for the matrix.)
- claim: goldens byte-exact + justified.
  -> `python3 -m unittest test_master.TestGoldensC4` -> "Ran 9 tests ...
     OK"; evidence/v182_goldens_justification.md (two causes: W4 code
     column, version string).

## W1 bounds (RUNBOOK §2/§8, HANDOFF)

- claim: per-host brownout trip measured 184.4 s.
  -> `python3 scripts/w1_measure_bounds.py` -> "call 1: 92.3 s ... call
     2: 92.1 s -> breaker open / TRIPPED after 184.4 s" (loopback).
- claim: outage/brownout/intermittent bounds are test-enforced.
  -> `python3 -m unittest test_master.TestLoopbackWorstCaseV182
     test_master.TestNetGuardBrownoutV182 test_master.TestPreflightTotalBudgetV182
     test_master.TestNetGuardRateRuleV182 test_master.TestRunBudgetByDepthV182`
  -> "Ran 20 tests in 4.1s — OK" (walls asserted against
     me/netguard.py::worst_case_bound, the same function
     evidence/net_bounds.md documents).
- claim: depth budgets quick 600 / standard 1200 / deep 4500.
  -> `python3 -m unittest test_master.TestRunBudgetByDepthV182` -> OK
     (values pinned in the test; env override + fallback pinned too).

## W2 yfinance (HANDOFF "KNOWN LIMITS" replacement)

- claim: the yfinance wrappers cap/ledger/classify with a FAKE module.
  -> `python3 -m unittest test_master.TestYfinanceGuardV182` -> "Ran 6
     tests ... OK" (hang capped < 1.5 s, raise -> (None, "RuntimeError"),
     success passthrough, sector detection None-on-failure, pipeline
     installs+restores, offline swap unchanged).
- claim: real yfinance UNVERIFIED; owner script extended.
  -> `bash -n scripts/owner_net_check.sh` -> OK; the embedded python
     compiles (py_compile). NOT RUN on a real network (S2: loopback-only
     in the sandbox) — the owner runs it; output lands in
     owner_results/net_check.txt (key names only).

## W3 stale labels (RUNBOOK §3/§9, HANDOFF)

- claim: macro 19 d + no failed refresh = refresh-due, no W_STALE_CACHE;
  failed refresh or over-cadence = STALE.
  -> `python3 -m unittest test_master.TestStaleCadenceDisplayV182
     test_master.TestCadenceAwareStale test_master.TestFreshness` ->
     "Ran 24 tests ... OK".
- claim: the doctor is unchanged.
  -> `git diff v181 v182 --` N/A (no git); instead:
     `diff ../v181/master.py master.py | rg doctor` -> no doctor hunks
     (the doctor block is byte-identical; verified by
     `rg -n "cache     " master.py` -> same lines both trees).

## W4 codes (RUNBOOK registry pointer, HANDOFF)

- claim: stub/offline/outage runs produce zero W_UNUSUAL.
  -> `python3 -m unittest test_master.TestNoRoutineWUnusualV182` ->
     "Ran 8 tests ... OK" (stub, offline, outage, --earnings-backtest,
     pinned-date old-cache, plus per-message classification pins).
- claim: codes/docs drift test passes (docs/ADVANCED.md carries every
  code + fix).
  -> part of the suite: TestCodesRegistry (7 tests) OK.

## W5 --net (RUNBOOK §2, docs/CLI.md)

- claim: --net works, --mode unchanged, conflicts exit 2, --net online
  keeps exit 3.
  -> `python3 -m unittest test_master.TestExplicitNetFlagV182
     test_master.TestNetModes test_master.TestCli` -> "Ran 41 tests ...
     OK" (all --net x depth combinations, conflict matrix, exit 3,
     offline cached-truth run, --help surface).

## W6 dead tickers (RUNBOOK §9, OWNER_RUN.md)

- claim: OWNER_RUN uses the engine's real groups; the tool warns;
  the CSV is header-only.
  -> `python3 -m unittest test_master.TestUniverseOverrideV182
     test_master.TestUniverseOverrides` -> "Ran 10 tests ... OK".
  -> `python3 -c "import quality; print([g for g,m in
     quality.GROUPS.items() if 'CFLT' in m])"` -> "['tech']".

## S7 decision hashes (HANDOFF "GATES")

- claim: decisions unchanged vs v1.8.1 with a healthy network.
  -> `python3 scripts/decision_hash_v182.py` -> "v1.8.1 ... hash
     a023714c15e78f6019d2d3d97de9c13d3f987c9d91188dcb87ae9d10878c35e8 ·
     5 decisions / v1.8.2 ... hash a023714c... (same) · UNCHANGED"
     (evidence/v182_decision_hash.txt). Stub/offline fixture identity:
     the byte-exact goldens + the in-suite guard-off/guard-healthy hash
     test (both in the 605).

## S8 no secrets / no runtime state

- claim: the zip ships no secrets and no runtime state.
  -> packaging runs `rm -f data/fetch_ledger.jsonl data/negative_cache.json`
     and the release gate + a zip listing check (see defects/plan);
     `unzip -l final_master_g.zip | rg fetch_ledger|negative_cache|owner_results`
     -> no rows. Key NAMES only in scripts (grep for values: none).

## CONFIG disclosure (S7)

- claim: every new key is a disclosed runtime knob.
  -> `python3 scripts/config_diff_v182.py` -> "6 value change(s), 7
     rationale change(s)" — exactly RUN_BUDGET_BY_DEPTH,
     NET_BREAKER_WINDOW_N, NET_BREAKER_RATE, NET_BREAKER_TIMEOUT_WEIGHT,
     NET_BROWNOUT_S, NET_PREFLIGHT_TOTAL_S (+ RUN_BUDGET_S rationale)
     (evidence/v182_config_diff_vs_v181.txt).
