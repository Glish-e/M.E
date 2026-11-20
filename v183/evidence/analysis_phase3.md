# analysis_phase3.md — written BEFORE any phase-3 edit (evidence; no code dumps)

Carry-in: phase-2 output (master.py v1.2.0, 4,579 lines, 103 tests green
[1 LIVE SKIP: earnings_engine.py absent], CONFIG diff = +MACRO_SNAPSHOT_MAX_AGE_H
only). earnings_engine.py + both audit MDs STILL absent -> real-engine L3
points stay UNVERIFIED (H7). A15's text is taken from the phase-3 prompt
("a registered layer runs or fails loudly, never silently skipped").

Probes run before planning (grep/reads, no edits):
- LAYER_REGISTRY :1310 has all 3 layers, but build_layers :1316 iterates a
  HARDCODED order tuple ("macro","quality","earnings") and a stub maker dict
  (:1324) -> a 4th REGISTERED layer is silently never constructed/run = A15.
  _parse_layers :1619 already rejects unknown --only/--skip names (64).
- run_pipeline :1834: main loop special-cases `layer.name == "earnings"` for
  the funnel; no overlay/sizer phases exist. fuse :1540 hardcodes quality/
  earnings signal lookup; decisions sorted inside fuse :1560.
- render: _header :2142 (1-line box), _layers_block :2157 iterates
  out.results (already name-generic; extras special-cased per name), tilts
  line :2189 hardcodes SECTOR_ORDER; decisions table :2270 has NO reasons
  column, conv definition printed ABOVE the table (P2-11); footer :2335 has
  no score-not-probability line; no sector summary table exists.
- json_payload :2508 iterates out.results (name-generic) — good.
- _Progress :634 + [plan] banner :1780 + _note :1862 all write stderr;
  _cli_run :2855 writes results to stdout. make_style :2072: colour auto-off
  when stdout is not a TTY (piped == plain already holds); width clamp 40..110.
- Wizard/—-sectors/--cap/--discover: none exist. quality.TickerRef has
  (ticker, sector, status, note, evidence) ONLY — no market cap at universe
  scope (quality computes price x shares per name at scoring time) -> the
  cap step must honestly say "unavailable" until an engine exposes it.
  quality.get_universe() gives active refs by sector (probe source).
- Tests+fakes: §8 banner at :2913 through :4579 (1,667 lines) incl. imports
  at :2917-2918; test_master.py :1-25 is a thin runner; _run :3185 drives
  stubs via MASTER_STUBS env + build_layers' stub branch; Stub* classes
  :3202-3280; fake engines :3015-3147; _Mods :3153; _ns :3177.

ITEM 4 (move first — it is behavior-neutral): split master.py at the §8
banner; test_master.py gets the block + `from master import (auto-computed
name list)` + new _run/_stub_registry (tests swap master.LAYER_REGISTRY
entries under a context manager; MASTER_STUBS stays the banner flag).
master.py: build_layers loses the stub branch -> build_layers(only, skip,
registry=None) defaulting to LAYER_REGISTRY iterated IN INSERTION ORDER;
LAYERS :1313 becomes registry-driven; run_selftest imports test_master
lazily (no import cycle: function-level import; missing file -> 64).
Gate: the moved suite must still be 103 green BEFORE any phase-3 behaviour
change (move-neutrality evidence).

ITEM 1 (real registry / A15):
- build_layers iterates the registry (order = insertion), filtered by
  only/skip; unknown names already 64. Registered+selected => always
  constructed+run; a raising layer keeps today's loud isolation (salvage
  ERROR + stderr note + exit reason), never a skip.
- run_pipeline partitions by stage attr: gate/score run the main loop;
  funnel consumers generalise `== "earnings"` to class attr funnel_input
  (EarningsLayer sets it); NEW overlay phase after fusion (run receives the
  Decision list, registry order), then sizer phase (reads decisions, fills
  Decision.weight, may veto, appends portfolio footer lines via
  res.ctx_out["portfolio"]). Both write into the fusion snapshot so
  render/json/timings see them (snapshot semantics of P2-1 preserved).
- fuse(): after fuse_candidate per ticker, attach every registered layer's
  signal to d.layers[name]; overlay signals carry facts["conviction_adj"]
  bounded by NEW CONFIG OVERLAY_MAX_ADJ=10.0 (rationale string; the only
  CONFIG diff this phase — H2 values byte-identical); veto/gate AVOIDs are
  never adjusted (overlay reason says skipped); adjusted rows re-gate with
  the SAME H2 thresholds and re-sort by _rank_key. Core conviction math
  (0.65/0.35/haircuts) untouched (H2/H5).
- _layers_block/_header/json: drop per-name special cases where possible
  (extras from res.ctx_out; chain from results order) so a dummy layer
  appears end-to-end (panel, header chain, JSON layers array, reasons).

ITEM 2 (wizard + flags):
- New flags: --sectors g1,g2|all (candidates = active quality-universe names
  in those groups; lazy quality import; import failure -> 64 with reason);
  --cap mega|large|mid|small (only if universe refs expose market_cap:
  today they do not -> flag parses, then refuses loudly 64 "unavailable:
  <reason>"; names with no mcap are excluded WITH a warning, never silent);
  --discover N (sets --top; pools/percentiles NEVER truncated; when fewer
  names qualify an explicit "M of N shown" warning fires).
- run_wizard(stdin, stdout): scope t/s/m -> sectors multi-select (numbers,
  names, 'all'; per-group counts from the universe probe) -> cap step (only
  if data exists, else one "unavailable — <reason>" line) -> discover N ->
  layers (registry keys, default all) -> depth quick/standard/deep ->
  confirm printing the EXACT composed command; Y builds the SAME Namespace
  via build_parser().parse_args(argv) (equivalence by construction); n/EOF
  aborts with the command to rerun (exit 0, nothing ran). 3 invalid answers
  per step -> 64. main(): no argv + stdin&stdout TTY -> wizard; no argv +
  non-TTY -> today's default run (scripts unaffected).
- Universe probe helper backs wizard, --sectors and --cap from ONE place:
  quality.get_universe() (refs) else GROUPS attr; no invented data (H3).

ITEM 3 (output):
- Manifest header: box rows mode / as-of / offline / stubs / engines
  (per-layer version vs tested; missing engine printed MISSING) + chain.
- NEW sector table after the macro card when quality ran: per sector —
  tilt, scored count, median Q (medians of OK scores; honest "–" when 0).
- Company table: + REASONS column (joined, ellipsised); flags cell shows
  flags only (veto/gate text moves to reasons); three width tiers
  (>=96 full; 70-95 drop/shorten reasons+flags; 40-69 core columns only:
  rank, ticker, action, conv, Q, E, short flags) — every line _fit-ed to
  the requested width, colour==plain at every width (P1-8 invariant kept).
- ONE footer line "conviction ... a score, not probability" (the P2-11
  table-top definition moves there); JSON definitions + --explain lines
  unchanged (separate views, not the report footer).
- Streams: results stdout, [plan]/progress/notes stderr (already true —
  pinned by new tests); piped stdout => no ANSI (already true — pinned).

CONFIG diff plan: exactly ONE new entry (OVERLAY_MAX_ADJ=10.0 + rationale);
no H2 value changes. New tests (red first): TestWizard (scripted stdin,
EOF, 3-strikes, non-TTY fallthrough, argv equivalence), TestRegistryReal
(dummy overlay e2e + dummy sizer + A15 no-silent-skip + unknown 64 +
registry order), TestWidths (40/70/110), TestSectorTable, TestManifest,
TestFooter, TestStreams, TestPipedPlain, TestCapAndSectors.

RUNBOOK.md gets a v1.3.0 section; master.py -> v1.3.0 + changelog block.
