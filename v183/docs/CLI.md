# docs/CLI.md — the command line, with REAL captured output

Everything below was captured on this build (2026-11-14, sandbox:
python 3.12.16, NO_COLOR unset for the colour run). Reproduce with the
exact commands shown. Screenshot-free by design: the colour sample is
the literal byte stream with each ANSI SGR sequence spelled out as
`<ESC>[...m` so it can be read in any medium.

## The colour sample (real bytes)

Command:
```
python3 master.py MU NVDA --mode quick --offline --color always --quiet
```
Literal output (first 10 non-empty lines; every `\x1b[..m` is shown as
`<ESC>[..m`; `1m`=bold, `4m`=underline, `32m`=green, `33m`=yellow,
`90m`=dim, `91..97m`=bright, `0m`=reset):

```
╭──────────────────────────────────────────────────────────────────────────────────────────────╮
<ESC[96m>│ MASTER v1.7.0-dev · mode quick · net offline (MASTER_NET=offline (override)) · as of         │<ESC[0m>
<ESC[96m>│ 2026-11-14 (live) · stubs no                                                                 │<ESC[0m>
<ESC[96m>│ engines: meds v14.7.0 · quality v3.4.1 · earnings v3 · ml_train v1.0.0 · master v1.7.0-dev   │<ESC[0m>
<ESC[96m>│ chain: macro→quality→earnings→ml→risk                                                        │<ESC[0m>
<ESC[96m>│ RULESET legacy - missing-E advantage ACTIVE (UNVALIDATED)                                    │<ESC[0m>
<ESC[96m>│ data: macro cache 2026-10-31 STALE 14d  |  quality cache 2026-11-14 OK 0d                    │<ESC[0m>
<ESC[96m>│ data: earnings mixed n/a ERROR n/a  |  ml cache 2026-11-13 OK 1d  |  risk none n/a OK n/a    │<ESC[0m>
╰──────────────────────────────────────────────────────────────────────────────────────────────╯
<ESC[91m>VERDICT 1 LONG / 1 WATCH / 0 AVOID — earnings failed: earnings engine exposes no __version__; r…<ESC[0m>
```

The same run WITHOUT colour:

```
python3 master.py MU NVDA --mode quick --offline --plain --quiet
```

```
╭──────────────────────────────────────────────────────────────────────────────────────────────╮
│ MASTER v1.7.0-dev · mode quick · net offline (MASTER_NET=offline (override)) · as of         │
│ 2026-11-14 (live) · stubs no                                                                 │
│ engines: meds v14.7.0 · quality v3.4.1 · earnings v3 · ml_train v1.0.0 · master v1.7.0-dev   │
│ chain: macro→quality→earnings→ml→risk                                                        │
│ RULESET legacy - missing-E advantage ACTIVE (UNVALIDATED)                                    │
│ data: macro cache 2026-10-31 STALE 14d  |  quality cache 2026-11-14 OK 0d                    │
│ data: earnings mixed n/a ERROR n/a  |  ml cache 2026-11-13 OK 1d  |  risk none n/a OK n/a    │
╰──────────────────────────────────────────────────────────────────────────────────────────────╯
VERDICT 1 LONG / 1 WATCH / 0 AVOID — earnings failed: earnings engine exposes no __version__; r…
```

## Where colour comes from

`--color auto|always|never` (+ `--no-color`, `--plain`): auto = TTY +
env precedence (NO_COLOR beats FORCE_COLOR, which beats TERM=dumb;
capable markers WT_SESSION/TERM_PROGRAM/ConEmuANSI count); `always`
beats NO_COLOR and works through pipes; AUTO-off prints ONE dim reason
line with the fix. Depth detection truecolor/256/16 — the same bright
16-colour palette at every depth. Windows VT enable via ctypes with an
honest fallback reason. `python3 master.py --doctor` prints the colour
diagnostic (isatty, TERM, COLORTERM, NO_COLOR, FORCE_COLOR,
CLICOLOR_FORCE, platform, depth, decision + reason).

## Exit codes

0 clean · 1 degraded (result produced + warnings) · 2 usage/config ·
3 network · 4 no result / NO-GO · 65 replay mismatch · 70 unexpected ·
130 Ctrl-C. `--doctor` health failure = 1.

## Every run ends with

ERRORS & WARNINGS: layer · stable code · what · why · the exact fix
command (clean = "0 errors, 0 warnings"); errors also mirror to STDERR;
tracebacks only with `--debug`. DATA SOURCES: per layer live/cache/
SYNTHETIC + age (STALE) and the macro path (FRED key -> API; no key ->
public fredgraph.csv; a missing key is NOT an error).

## The main flags (day to day)

tickers (positional or `--tickers A,B` / `--watchlist FILE`) ·
`--mode quick|standard|deep` (depth presets) + `--mode offline|online|auto`
(data mode; offline = cached truth, zero sockets, ages labelled) ·
`--net auto|online|offline` (v1.8.2: the data mode as its OWN flag —
combines freely with the depth presets, e.g. `--mode quick --net offline`;
conflicts with `--mode auto/online/offline` and with `--offline` are a
clear exit-2 usage error; `--net online` keeps the exit-3 probe contract;
`--mode` keeps working exactly as before) ·
`--as-of YYYY-MM-DD` (point-in-time) · `--sectors tech,healthcare|all`
(quality-pool scan) · `--top N` / `--min-conviction X` (display filters) ·
`--explain TICKER` (per-layer breakdown) · `--json` / `--csv FILE`
(exports) · `--freeze DIR` / `--replay DIR` (reproducibility) ·
`--md FILE` / `--html FILE` (v1.8.0 exports; same filters as --csv) · `--backtest` (the preregistered integration backtest) · `--bt-start/--bt-end YYYY-MM-DD` (v1.8.0: evaluate a month-end sub-window of the DATASET, printed beside the full-span numbers and labelled descriptive — never a verdict; dates outside the dataset need `python3 ml_dataset.py --start/--end/--freq`, an owner network build) · `--doctor`
v1.8.0 notes: the report begins with a SUMMARY card (verdict,
top picks, risk, warnings); --help is grouped by task; the
layer/data lines never cut names mid-word; the risk footer shows
the live cost model (GROSS + the 2 x 10 bps estimate);
`--bt-breaker` is the opt-in drawdown circuit-breaker what-if;
`--bt-spy FILE` consumes the owner SPY series;
`--bt-ablate macro_cap|macro_mult|macro_all` (v1.8.3, F6) is the
opt-in macro ablation over the RECORDED decisions (reads
ml_data/cache/dates/*.json only; prints n + the one-episode
disclosure beside every number — a what-if, never a verdict);
evidence/backtest_runlog.jsonl logs every backtest run.
(one-screen health) · `--selftest` (the stubbed suite). Full surface:
`python3 master.py --help`.

## Reading the table

One row per name: rank, ticker, sector, ACTION (LONG/WATCH/AVOID,
colour-coded), a conviction bar (ASCII fallback `#####`), the letter
grade, quality/earnings cells, the NOW chip (next earnings), macro tilt,
plan take-profit, weight. The header labels the active ruleset (legacy
default; `--ruleset v2` opts in) and the sizer (`--sizing vol_target`
opts in). VERDICT line: how many LONG/WATCH/AVOID and what dominated.


## FETCH HEALTH (v1.8.1, N4 — every run ends with it)

Every run prints a FETCH HEALTH block: per host and per layer
ok/failed/skipped counts, the totals, the deferred-retry "recovered n of
m" line and the skipped items with (item, why, fix). The JSON payload
carries the same object under the additive `fetch_health` key; the
quality progress line shows it live ("net ok 41 | fail 3 | skip 2").

The sample below is a REAL capture from the LOOPBACK fault simulation
(SIMULATED — 127.0.0.1 fault servers, fake engines, never real provider
data; reproduce with `python3 scripts/capture_sim_fetch_health.py`):

```
=== FETCH HEALTH (captured from the LOOPBACK fault simulation — SIMULATED, never real provider data) ===
FETCH HEALTH
  127.0.0.1 10 ok / 2 failed / 0 skipped
  quality-engine 1 ok / 0 failed / 1 skipped
  totals 11 ok / 2 failed / 1 skipped
  recovered 1 of 1 (deferred retry pass)
  skipped: ZZ (PERMANENT: HTTP Error 404: Not Found — fix: add the ticker to data/universe_over…
[stderr] preflight: 127.0.0.1:41703 ok (probe ok 0 ms)
[stderr] quality QQ: recovered by the deferred retry pass
```

What the simulation exercised: preflight (N2) to the loopback host, a
200 item, a 404 (permanent — no retry, negative-cached, N5/F8), a
500-500-500-200 item (transient retries exhausted in-call, then ONE
deferred attempt after the cooldown recovered it — N9), and a 429 whose
Retry-After was honoured (N5).

v1.8.1 flags: `--strict` / `--lenient` (opt-in exit policies — default
contract unchanged; strict: degraded->2; lenient: degraded->0; NO-GO 4
and usage 2 never forgiven) · `--retry-failed` (N9: re-fetch ONLY the
last run's failed transient items from data/fetch_ledger.jsonl;
permanent 404s never retried; healthy items never rerun) ·
`--retry-failed-path JSONL`. The run budget (RUN_BUDGET_S) bounds every
run — after it the run renders what it has and the process exits within
seconds even if a worker is stuck (N1).
