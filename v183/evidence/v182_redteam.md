# evidence/v182_redteam.md — five ways the claims could be false, each
# with a check and its real result (run on the final tree, 2026-11-20).

## 1. "The wall-time bounds pass only because loopback is fast"

CLAIM UNDER TEST: outage/brownout/intermittent walls are knob-bounded,
not loopback-luck.
CHECK: the bounds come from me/netguard.py::worst_case_bound (pure knob
arithmetic: preflight_total + budget + cap + defer + slack) and the
tests assert wall <= bound. Loopback speed only makes the MEASURED wall
smaller; each attempt is capped by a SOCKET TIMEOUT (not by loopback
latency) — proven by test_brownout_trips_and_fails_everything_fast,
where a server that hangs 6 s is capped at 0.3 s (20x). A slower real
network cannot exceed the cap per attempt, and the trip rules count
attempts, not seconds (except the brownout budget, which counts exactly
the failed-attempt wall the caps bound).
RESULT: PASS — the bound is cap-derived; the 6s-hang-vs-0.3s-cap test
is the direct proof.

## 2. "The run budgets were justified on warm caches"

CLAIM UNDER TEST: RUN_BUDGET_BY_DEPTH quick=600 is not warm-cache luck.
CHECK: quick 600 s vs the COLD estimate: quality's own CONFIG
COLD_S_PER_NAME = 0.8-2.0 s/name; the largest quick pool (--sectors all)
is ~85 active names -> 68-170 s cold, under 600 s with 3-8x headroom;
the measured real quick runs (6.4/10.8/24.6 s, RUNBOOK §2, v1.8.1 real
terminal runs) bracket the warm side. standard 1200 = the v1.8.1 value
unchanged (its own rationale: cold standard ~minutes). deep 4500 = the
deep preset's own 3600 s layer budget + 900 s slack — a COLD deep run
is what the budget must admit (v1.8.1 clipped it at 1200: the bug W1
fixes).
RESULT: PASS — the quick number is cold-bounded by COLD_S_PER_NAME x
pool, not by warm measurements; deep now admits its own cold layer.

## 3. "The decision hash was taken before the last code edit"

CLAIM UNDER TEST: S7's hash proof covers the SHIPPED code.
CHECK: the first decision-hash run preceded the last me/render.py
classifier edit; the gate was RE-RUN after the final code edit (the
only later file changes are docs/evidence). Output (final run):
v1.8.1 hash a023714c15e78f6019d2d3d97de9c13d3f987c9d91188dcb87ae9d10878c35e8
v1.8.2 hash a023714c15e78f6019d2d3d97de9c13d3f987c9d91188dcb87ae9d10878c35e8
UNCHANGED (evidence/v182_decision_hash.txt). Additionally the manifest
is built AFTER that (hash-of-record discipline) and the suite re-ran
after the last *.py edit (3 x 605 OK).
RESULT: PASS — hash-after-last-edit proven; no code changed after.

## 4. "Zero W_UNUSUAL only for the exact scenarios tested"

CLAIM UNDER TEST: the W4 claim is scoped to stub/offline/outage runs.
CHECK: the claim IS scoped (that is what W4 asks). The classifier keeps
W_UNUSUAL as the honest fallback for genuinely unclassified text, and
the drift test forces every code-shaped token to be registered. The
pinned-date matrix cells (4 dates x the full suite) exercised the
old-cache warning paths and found two more producers — both fixed and
regression-tested (D-182-9), which is evidence the enumeration method
(matrix-driven, not hand-picked) converges.
RESULT: PASS with the scope stated — zero W_UNUSUAL is claimed for
stub/offline/outage runs only, and W_UNUSUAL remains by design for the
unknown.

## 5. "The goldens were regenerated to bake in broken output"

CLAIM UNDER TEST: golden bytes are corroborated independently.
CHECK: every semantic change visible in the goldens has a unit test that
asserts the SEMANTICS, not the bytes: TestStaleCadenceDisplayV182
(refresh-due vs STALE vs refresh-failed), TestNoRoutineWUnusualV182
(the exact code per message), TestGoldensC4 invariants (no dates,
SYNTHETIC present, strip_ansi(colour)==plain, locale/sklearn
independence — all still enforced post-regen). The justification file
(evidence/v182_goldens_justification.md) names exactly two byte causes
(W4 code column, version string), both display-only.
RESULT: PASS — a render bug would have to simultaneously fool the
semantic unit tests and the invariant checks.

## Bonus: S8 packaging check (runtime state / secrets)

CHECK: the tree is cleaned (rm data/fetch_ledger.jsonl
data/negative_cache.json) before the manifest; the manifest build
verifies 286/286; the zip listing is grepped for fetch_ledger /
negative_cache / owner_results / *.key / .env — no rows; scripts print
key NAMES only (owner_net_check.sh/.ps1 reviewed line by line).
RESULT: recorded in the delivery message with the zip listing command
output.
