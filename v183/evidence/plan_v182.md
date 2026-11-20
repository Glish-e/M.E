# evidence/plan_v182.md — W0 ENTRY FACTS (v1.8.2 hardening pass)

Entry: final_master_f.zip (v1.8.1) unzipped to v181/, worked on in a copy
(v182/). Every fact below was RE-VERIFIED on this build (not trusted from
the prompt). Format: fact -> CONFIRMED/DIFFERS -> [VERIFIED: command +
file:line].

## Entry integrity

- ENGINES.sha256 at entry [VERIFIED: `sha256sum meds.py quality.py
  earnings_engine.py` inside v181/ == ENGINES.sha256]:
  - meds.py 5e64b60da86d2e759f1f506e8c9dfdc5acfed32ce6958a204f172242cefc437b
  - quality.py f123fb4e36ad298d0c662d0b36d71bb98ea80ef42760714d3b7133bac1b31215
  - earnings_engine.py 8e31e53248531584898ebfd266347775874b93d3440d12830cdb7f5a4545b0e0
- MANIFEST: 272 entries, 0 mismatches, 0 missing [VERIFIED: python3
  re-hash of every MANIFEST.txt line against the tree].
- Runtime state (data/fetch_ledger.jsonl, data/negative_cache.json) is NOT
  in the zip [VERIFIED: `unzip -l final_master_f.zip | rg fetch_ledger`
  -> no rows]. NOTE: running the suite in-place CREATES both (my entry
  runs did); they are deleted before packaging and the release gate must
  fail if present (W7 re-check).
- User: `z` (non-root) [VERIFIED: `whoami` -> z]. The root-only
  read-only-cache test caveat does not apply here.

## Baseline suite (user z, three environments)

| env | command | result |
|---|---|---|
| unset | `python3 test_master.py` | Ran 544 tests in 47.584s — OK |
| MASTER_NET=offline | `MASTER_NET=offline python3 test_master.py` | Ran 544 tests in 45.767s — OK |
| MASTER_STUBS=1 | `MASTER_STUBS=1 python3 test_master.py` | Ran 544 tests in 46.339s — OK |

RUNBOOK.md = 120 lines [VERIFIED: `wc -l RUNBOOK.md`]. HANDOFF.txt =
3,117 chars [VERIFIED: `wc -c HANDOFF.txt`].

## Facts a-h

### a. RUN_BUDGET_S 1200 / quick 300 / standard 900 — CONFIRMED
[VERIFIED: me/core.py:409 `_cfg("RUN_BUDGET_S", 1200.0, ...)`; quick
preset timeout 300.0 at me/core.py:227 (`MODES["quick"]`); standard =
`LAYER_TIMEOUT_S` 900 at me/core.py:221-222 and me/core.py:228-230.]

### b. CircuitBreaker consecutive-K; caps — CONFIRMED
[VERIFIED: me/netguard.py:149 `class CircuitBreaker`; `record()` at
me/netguard.py:192-205 counts CONSECUTIVE failures per host
(`self._fails[host] += 1; if >= self.k: open`) and a success resets
(me/netguard.py:194-197). NET_BREAKER_K=5 at me/core.py:430;
NET_CALL_CAP_S=30.0 at me/core.py:437; NET_RETRY_BUDGET_S=45.0 at
me/core.py:441.]

### c. Macro STALE at 19d in header/SUMMARY path; refresh-due only in
the plan banner; HANDOFF claims F4 done — CONFIRMED
[VERIFIED:
- STALE_STATUS_DAYS=7 at me/core.py:493.
- me/render.py:441-450 `_prov_status`: any provenance with
  `age_days > 7` renders "STALE" — used by the header provenance cells
  (me/render.py:410), the layers block (me/render.py:526), the DATA
  SOURCES line (me/render.py:1045) and `_build_diags` (me/render.py:1000)
  which emits W_STALE_CACHE (me/render.py:1001-1005) — a monthly macro
  series at 19 days (within its 45d cadence, no failed refresh) shows
  STALE + a W_STALE_CACHE warning (which the SUMMARY warning count
  carries).
- "refresh-due" exists ONLY in the plan banner: master.py:2723 (text) and
  master.py:2709-2713 (docstring); grep over master.py/me/*.py shows no
  other site.
- layer_provenance (master.py:2554-2559) marks macro STALE only when the
  DATA age exceeds FRESHNESS_MACRO_MAX_AGE_D=45 — the 7d display rule in
  the renderer is what fires at 19d.
- HANDOFF.txt:34-35 claims "F4 cadence-aware STALE (18 d macro =
  refresh-due, not stale)" — PARTIAL: true only of the [plan] banner; the
  header/SUMMARY/warnings surfaces still say STALE. Corrected in W3/W7.]

### d. Stub/offline runs still emit W_UNUSUAL for the three messages —
CONFIRMED
[VERIFIED: `python3 -c` calling `me.render._classify_warning` on the
exact texts observed in a `MASTER_STUBS=1 python3 master.py MU --mode
quick --json` run:
- "empty shortlist: nothing passed the quality gate" (quality) ->
  W_UNUSUAL (emitted at master.py:1135)
- "scenario RISK_ON score renormalized: retained weight 60% of its terms
  (<70%)" (macro; meds.py:7989-7991 is the source) -> W_UNUSUAL
- "macro DEGRADED (...)" (master.py:3187) -> W_UNUSUAL
- also still W_UNUSUAL in a plain stub run: "credit OFF — not
  trade-grade (macro damped; ...)" (master.py:3183-3185) and "earnings
  accuracy: SIGNAL: ..." -> W_UNUSUAL. The stub MU run renders exactly
  one W_UNUSUAL line (the credit-OFF warning).
Fixed in W4.]

### e. Net guard patches urlopen + requests only; quality calls yfinance
directly; yfinance absent from the lock — CONFIRMED
[VERIFIED: me/netguard.py:946-947 patches urllib.request.urlopen,
me/netguard.py:955-956 patches requests.Session.request, nothing else
(`install()` me/netguard.py:939-957). quality.py:3157-3160 `available()`
imports yfinance; quality.py:3163-3192 `_download` calls
`yf.Ticker(ticker).history(...)` (quality.py:3179) directly — bypasses
quality.default_transport; quality.py:15661-15668
`_detect_sector_yfinance` calls `yfinance.Ticker(ticker).info`
(quality.py:15664-15665) directly. requirements-lock.txt:14 documents
"# yfinance: ABSENT (optional; see requirements.txt)". master.py:563-575
already swaps YfinancePriceClient.available ONLY for offline runs; in
online mode yfinance is entirely unwrapped (the W2 gap).]

### f. OWNER_RUN CFLT/PSTG sectors wrong; EXAMPLE1 row ships — CONFIRMED
[VERIFIED: OWNER_RUN.md:47-48 add CFLT with sector "energy" and PSTG
with "utilities"; quality.py's GROUPS place CFLT (quality.py:1052) and
PSTG (quality.py:1068) in the "tech" group (group starts quality.py:985)
— `python3 -c "import quality; print([g for g,m in quality.GROUPS.items()
if 'CFLT' in m])" -> ['tech']`. data/universe_overrides.csv ships
`EXAMPLE1,,,` after the header. Fixed in W6.]

### g. --mode mixes net modes and depth presets; no --net flag — CONFIRMED
[VERIFIED: me/cli.py:43 `--mode` choices =
NET_MODES(auto/online/offline) + MODES(quick/standard/deep); the split
happens in `_apply_mode` me/cli.py:243-250; `rg -n '"--net"' me/cli.py`
-> no matches. W5 adds the separate flag.]

### h. Exit 3 for --mode online with dead network; MASTER_NET=online
skips the probe — CONFIRMED
[VERIFIED: master.py:2481-2485 raises MasterError(..., 3) when
want == "online" and the probe failed; master.py:2468-2471 returns the
MASTER_NET env value with note "(override)" WITHOUT probing when
MASTER_NET in (online, offline).]

## Scope confirmation

- No preregistration amendment is needed for W0-W7: all changes are
  master-owned surfaces (netguard/CLI/render/codes/docs/scripts) or
  disclosed CONFIG additions (S7: decisions unchanged — decision-hash
  invariance re-proven in W7; new keys are runtime knobs listed in the
  CONFIG diff). The preregistration file evidence/preregistration.md is
  untouched this phase.
- Priority conflicts: none encountered (S14).
