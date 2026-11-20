# evidence/net_bounds.md — v1.8.2 (W1) worst-case network bounds
              (v1.8.3, F1: DNS-hang case RE-MEASURED with the watchdog)

The written bound is `me/netguard.py::worst_case_bound(...)` — the single
source of truth the loopback tests (TestLoopbackWorstCaseV182,
TestNetGuardBrownoutV182, TestPreflightTotalBudgetV182) assert against.
This document explains each formula, cites the MEASURED loopback numbers
(scripts/w1_measure_bounds.py output below) and states plainly which
targets are met, revised or impossible.

## Knobs (all CONFIG keys, S7: runtime knobs listed in the CONFIG diff)

| key | value | role in the bound |
|---|---|---|
| NET_PREFLIGHT_S | 2.0 s | per-host probe budget (DNS+TCP), per attempt |
| NET_PREFLIGHT_RETRIES | 2 | 1 + 2 attempts per host |
| NET_PREFLIGHT_TOTAL_S | 10.0 s | NEW v1.8.2: cap on the WHOLE preflight pass |
| NET_CALL_CAP_S | 30.0 s | per-attempt timeout clamp |
| RETRY_MAX_ATTEMPTS | 3 | attempts per call |
| RETRY_BACKOFF_S | (0.5, 1.5) | sleeps between attempts (jittered) |
| NET_RETRY_BUDGET_S | 45.0 s | total sleep budget per run |
| NET_BREAKER_K | 5 | consecutive-failure trip (v1.8.1, unchanged) |
| NET_BREAKER_WINDOW_N | 20 | NEW v1.8.2: rate-rule rolling window |
| NET_BREAKER_RATE | 0.5 | NEW v1.8.2: weighted-failure rate threshold |
| NET_BREAKER_TIMEOUT_WEIGHT | 2.0 | NEW v1.8.2: timeouts count double |
| NET_BROWNOUT_S | 120.0 s | NEW v1.8.2: global failed-attempt wall budget |
| NET_DEFER_COOLDOWN_S | 1.5 s | deferred-retry cooldown (then breaker-gated) |
| RUN_BUDGET_BY_DEPTH | quick 600 / standard 1200 / deep 4500 | NEW v1.8.2: run budget by depth preset |

## Formulas (worst_case_bound)

    per_call            = attempts*cap + (attempts-1)*backoff_max
    calls_to_trip       = ceil(K / attempts)
    per_host_trip       = calls_to_trip * per_call
    outage_refused      = preflight_total + defer_cooldown + slack(1 s)
    outage_no_preflight = outage_refused + (calls_to_trip+1)*backoff_max
    brownout (with NET_BROWNOUT_S)
                        = preflight_total + brownout_s + cap + defer + slack
    brownout (budget disabled)
                        = preflight_total + 3*per_host_trip + defer + slack
    intermittent        = preflight_total + retry_budget + defer + slack
    slow_drip_ok        = cap  (per successful call; nothing trips)

Production values: outage_refused = 10+1.5+1 = 12.5 s;
brownout = 10+120+30+1.5+1 = 162.5 s; intermittent = 10+45+1.5+1 = 57.5 s.

## Case 1 — total outage (connect refused / DNS dead)

- MEASURED (loopback, 127.0.0.1 refused port): 10 refused connects =
  1.2 ms; preflight over 6 hosts x (1+2) attempts = 0.92 s, all marked
  dead, breakers force-opened before any layer runs.
- v1.8.3 (F1) CORRECTION OF THE RECORD: the v1.8.2 line claimed a
  DNS-hang "stops the pass at 10 s". The stage-1 audit MEASURED the
  opposite on v1.8.2: the budget was checked only BETWEEN hosts, so a
  PERMANENTLY hung resolver on host 1 stalled the pass UNBOUNDED (still
  running at the 8 s test watchdog), and a 5 s resolver stall completed
  in 5.00 s on a 2.0 s total budget. The fix runs every resolve in a
  daemon watchdog thread joined by min(per-host budget, remaining
  total); a stuck resolver is abandoned (at most _DNS_ABANDON_MAX=8 per
  pass — later hosts get the honest cap note), marked dead with the
  'dns timeout' note and never retried past the budget.
- MEASURED (v1.8.3, mocked resolvers, shipped knobs 2.0/2/10.0/6 hosts;
  evidence/v183_dns_bounds.txt): permanent resolver block = 10.00 s
  wall (exactly the total; 5 abandoned resolvers + 1 total-budget note);
  5 s stall x6 = 10.00 s; mixed fast/refused + one 30 s stall = 2.75 s;
  11 permanent blocks with no total = 0.40 s (cap-note hosts after 8
  abandons). Fast-resolver notes/latency/attempts are byte-identical
  (test_fast_resolver_output_identical_to_v182).
- TARGET outage <= 15 s: **MET (by design since v1.8.3, by claim-only
  before)**. Knob-bound 12.5 s (with preflight, the default for
  auto/online terminal runs); measured ~3 s end to end (0.92 s
  preflight + fail-fast layers + deferred-retry skip) on the refused
  shape; the hung-resolver shape is bounded at the 10 s total + slack.
- RESIDUAL LIMIT (stated plainly): with preflight disabled
  (MASTER_NET=online, the documented hermeticity valve) the knob-bound is
  outage_no_preflight = 12.5 + 3*1.5 = 17 s — marginally OVER the 15 s
  target. The DNS component of an ENGINE call (urllib's internal
  getaddrinfo) still has no watchdog — only the preflight resolve and
  the wrap_fetch provider calls are capped (F11); a hung resolver inside
  a raw urlopen remains the known unbounded path (owner_net_check.sh is
  the verification tool).

## Case 2 — brownout (connect OK, no answer)

- MEASURED (loopback hang server, cap 30 s, K 5, 3 attempts): per-call
  wall 92.3 s and 92.1 s; the per-host breaker opened after 184.4 s —
  the K=5th failure lands mid-call-2 and that call still completes its
  attempts. Script: scripts/w1_measure_bounds.py, section 3.
- v1.8.1 shape: per_host_trip = 186 s (formula) / 184.4 s (measured),
  and the three host families (macro FRED, quality SEC, earnings
  finnhub/yahoo) trip SEQUENTIALLY (stages run one after another):
  3 x 184.4 = 553 s — far over both targets. This is what justified the
  new global knob.
- NET_BROWNOUT_S=120: the cumulative FAILED-attempt wall (successful
  attempts never count) force-opens EVERY breaker at ~120 s + one
  in-flight attempt (30 s) + deferred-retry skip (1.5 s).
- TARGET brownout <= 300 s (standard): **MET** — bound 162.5 s.
- TARGET brownout <= 180 s (quick): **MET** — bound 162.5 s (the guard
  is depth-independent; the quick run budget 600 s never clips first).
- A slow-but-WORKING network does NOT trip the guard: only failed
  attempts accumulate (test_slow_drip_successes_do_not_trip;
  test_slow_drip_within_bound).

## Case 3 — intermittent (alternating ok/fail)

- MEASURED (loopback, "cycle:500,200" alternating server, 1 attempt per
  call): the v1.8.1 consecutive rule NEVER trips (every success resets
  the count) — 30 alternating calls left the breaker closed. This is the
  gap the second trip rule closes.
- NEW rate rule: weighted failures in the last NET_BREAKER_WINDOW_N=20
  calls >= NET_BREAKER_RATE*20 = 10 (timeouts count 2x, so 5 timeouts
  suffice). Fast failures trip within the window at ~0 s each; the sleeps
  are bounded by NET_RETRY_BUDGET_S.
- TARGET (intermittant <= brownout targets): **MET** — bound 57.5 s
  (fast failures); intermittent-with-timeouts degrades to the brownout
  case (162.5 s) because each timeout failure also feeds fail-wall time.

## Run budget by depth (RUN_BUDGET_BY_DEPTH)

- quick 600 s = 2x its 300 s per-layer preset; measured real quick runs
  6.4-24.6 s (RUNBOOK §2), stub 0.3 s — 24x+ headroom.
- standard 1200 s = the unchanged v1.8.1 RUN_BUDGET_S value.
- deep 4500 s = the deep preset's own 3600 s layer timeout + 900 s
  slack. HONEST DISCLOSURE: v1.8.1's flat 1200 s budget silently CLIPPED
  a legitimate deep layer at 1200 s (budgets = min(start+timeout,
  run_deadline) with run_deadline = t0+1200 < t0+3600); the depth-derived
  budget fixes that. Same for --warm (WARM_TIMEOUT_S 3600 > 1200).
- MASTER_RUN_BUDGET_S env still wins (the CI/test valve); RUN_BUDGET_S
  stays the fallback for unknown depths.

## Prompt process exit with a stuck worker

Unchanged from v1.8.1 and re-proven by the suite: after the (now
depth-derived) budget the run salvages, renders and the process exits
within seconds even with stuck non-daemon workers —
TestRunBudgetHangs.test_pipeline_budget_ends_hanging_layer (now pins BOTH
budget keys) and test_exit_sweep_prompt_despite_stuck_threads.

## Measured loopback numbers (scripts/w1_measure_bounds.py, this build)

    10 refused connects: 1.2 ms total
    preflight 6 refused hosts x (1+2) attempts: 0.92 s (all dead)
    brownout per-call: 92.3 s / 92.1 s; breaker open after 184.4 s
    30 alternating 500/200 calls (3 attempts): 29 ok / 1 failed, breaker
    closed (the retry masks it; with 1 attempt the rate rule trips —
    TestLoopbackWorstCaseV182.test_intermittent_trips_within_bound)
