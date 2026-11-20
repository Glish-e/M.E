# w18_perf.md — W2 speed pass (v1.8.0)

R9 LABEL: every number below is a FIXTURE/STUB timing measured in this
sandbox on the shipped 12-date pilot dataset (1,080 rows) or stub
layers. None of it is real-data speed; real speed is measured by the
OWNER with scripts/owner_bench.sh (.ps1 twin) into owner_results/.

## Method

cProfile (cumulative) on: (a) the stub pipeline (MASTER_STUBS=1,
MASTER_NET=offline, 5 tickers), (b) `master.py --backtest` on the
shipped dataset+harvests, (c) `ml_train.py --heads q --out /tmp/mlprof`
(fixture dataset; wrote only to /tmp), (d) `ml_dataset.py --verify`
(fixture dataset). Raw tables: /tmp/prof/{stub,bt,mt,md}_profile.txt —
key lines pasted below.

## Before/after on fixtures (R9)

| path (fixture)            | before  | after   | delta | what changed |
| --- | --- | --- | --- | --- |
| master.py --backtest (whole process) | 0.83 s | 0.31-0.33 s (3 runs: 0.33/0.31/0.31) | -62% | ONE fix: me/backtest now hoists the three npz members (as_of/ret_63/tickers) before the row loop — NpzFile.__getitem__ re-read+re-decompressed each member on every subscript (3,170 __getitem__ calls, 0.50 s of the 0.74 s backtest); after: 3 reads. Output byte-identical apart from the config-hash line, which is now DETERMINISTIC (see below). |
| stub quick pipeline (in-proc) | 0.422 s | 0.42 s (unchanged by design) | 0% | dominated by importing test_master.py (0.333 s: the stub layers live there by contract since phase 3) + numpy (0.205 s). NOT optimizable without breaking the stub contract — left alone. |
| ml_train --heads q (fixture) | 3.82 s | 3.82 s (no change) | 0% | 3.03 s of it is the sklearn/joblib IMPORT chain (sklearn.base 2.4 s, compile 2.0 s) — engine-of-training owned, not our code; actual fit is 0.52 s. Nothing in ml_train's own code is hot on fixtures; on owner-scale data fit grows, imports stay fixed. |
| ml_dataset --verify (fixture) | 0.30 s | 0.30 s | 0% | import-dominated (0.29 s); the verify itself is trivial. |

The one code-owned hotspot found and fixed: the npz member hoist. All
other observed cost on fixtures is (i) first-run bytecode compile
(__pycache__ regenerates; the release zip ships no .pyc), (ii) module
imports (numpy/sklearn), (iii) the stub-harness import. None of those
are master-owned algorithmic costs.

## Behaviour gates re-run after the W2 changes

- suite: Ran 442 tests in ~21.6s OK (436 baseline + 6 v1.8.0 tests).
- fuzz_decisions.py: output byte-identical to the W0 baseline (22,000
  cases, seed 88117).
- freeze/replay: exit 0, "5 names identical"; frozen-ranking decision
  hash 2734886b...972595 UNCHANGED.
- backtest report diff before/after the hoist: identical except the
  'current' CONFIG hash line — see D-18-002 below (that line was
  never deterministic before; it is now).

## Defect found and fixed while profiling: D-18-002

The CONFIG identity hash (backtest report 'current' hash, ml_dataset
manifest config_hash_master, ml_train ds['_cfg_hash']) serialized
CONFIG with json.dumps(default=str): CONFIG carries EIGHT frozensets
(CYCLICAL_SECTORS, DEFENSIVE_SCENARIOS, DISCRETIONARY_SET,
ML_FORBIDDEN_FEATURES, QUALITY_SECTORS, SLEEVE_ETFS, STAPLES_SET,
VETO_FLAGS) whose str() order depends on PYTHONHASHSEED — the hash was
DIFFERENT IN EVERY PROCESS (observed: 5babb1dd/f900e1fc/dd3ca5c9/3038
2779/cd6a8336 across five runs of the same tree). Consequences: the
"build-time vs current" comparison in backtest reports was noise, and
'current' hashes were not reproducible. Fix (RED first —
TestConfigHashDeterministic failed on seeds 1 vs 2, then GREEN):
me.core._canonical_json (sets -> sorted lists, tuples -> lists) shared
by me/backtest._bt_config_hash, ml_dataset.py and ml_train.py; the
backtest report line now says the recipe changed and pre-v1.8.0 build
hashes are not comparable. NOTE: this also means part of the W0
D-18-001 story (the shipped report's 'current 04293ea1...' vs the wip
tree's 'e0b4df46...') was HASH NOISE, not code drift; the stale
file-hash part of D-18-001 stands (sha256 mismatches are objective).

## Declined with reasons (R3: no extra ideas in code)

- Persistent HTTP cache with TTL: master owns NO data fetch — its only
  network use is read-only probes (_net_probe, --check's _probe: DNS/
  TCP/tiny reads, no caching value). Every data fetch lives inside the
  READ-ONLY engines (R1: meds.py/quality.py/earnings_engine.py, each
  with its own cache layer — quality.py:593 CACHE_TTL_SECONDS for
  sec/finnhub). A second TTL cache would be engine work — out of scope,
  and the engine caches already exist.
- Parallelism: the pipeline already prefetches layers concurrently
  (ThreadPoolExecutor, §3.1 _Progress); per-name parallelism inside
  engines is engine-owned (read-only).
- The engines are the bottleneck in REAL online runs — provable only
  on the owner machine; owner_bench.sh cells 4 (online_standard) and 7
  (dataset_build6) measure exactly that. Nothing here claims it.

## Owner bench (R12/W2 DONE criterion)

scripts/owner_bench.sh (+ .ps1) exist, bash -n verified; cells: cli
floor, stub quick, offline standard, online standard, backtest, ml
_train, dataset build x6 dates. Owner timings land in owner_results/
as AWAITING OWNER DATA until returned.
