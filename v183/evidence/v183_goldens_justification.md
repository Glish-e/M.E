# v1.8.3 goldens regeneration — written justification (C-4 discipline)

Regenerated 2026-11-20 (`python3 scripts/make_goldens.py --regen`) after
the stage-2 fixes. The 12 v1.8.2 goldens were backed up first; the diff
v1.8.2 -> v1.8.3 contains EXACTLY three change classes, all intended,
none silent:

## 1. The version row (all 12 files)

    - │ MASTER v1.8.2 · mode standard · net ...
    + │ MASTER v1.8.3 · mode standard · net ...

The version bump is the release itself (me/core.py __version__ 1.8.2 ->
1.8.3; F8 made me/core.py the single source of truth for stamps).

## 2. The F2 header disclosure (all 12 files; wrapped at 40/70)

    + │ earnings prior: 1/3 names scored with E missing (x0.90 quality
    +   haircut; ruleset legacy) — NOT_SELECTED/MISSING_DATA
    +   indistinguishable here

The F2e display-only header line (owner APPROVED as part of the F2
read-out; the fill design itself stays DEFERRED). The stub fixture has
exactly 1 of 3 names on the missing-E prior (AAPL's E cell is n/a in
both the old and the new golden — unchanged), so the count is real.
Header lines do not feed the decision hash (S7 re-proven separately in
evidence/v183_decision_hash.txt).

## 3. The WT column width 6 -> 7 (110/160 widths only, where WT shows)

    -  #  TICKER   SECTOR    ACTION   CONV               Q       E           WT     MACRO
    +  #  TICKER   SECTOR    ACTION   CONV               Q       E           WT      MACRO

F9 reserves one character for the '*' ADV-unchecked marker. In the stub
run the marker itself never fires (StubRiskLayer assigns weights
directly; adv_checked stays None), so NO '*' and NO footnote appear in
any golden — the stub render is otherwise byte-identical.

## Explicitly unchanged

- Every decision row, conviction, action, weight value, grade, macro
  tilt, flag, reason, warning block, SUMMARY, FETCH HEALTH, DATA
  SOURCES line: byte-identical.
- The v1.8.2 goldens' warnings/SUMMARY counts did not change (no new
  warning fires in the stub fixture — W_CONSUMER_MERGED needs consumer
  names and the stub universe is MU/NVDA/AAPL, all tech).
- verify() passes: no dates, SYNTHETIC present, strip_ansi(colour) ==
  plain for all four widths.
