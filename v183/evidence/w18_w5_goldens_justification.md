# v1.8.0 W5 goldens regeneration — written justification

Command: `python3 scripts/make_goldens.py --regen` (C-4 discipline).

ONE change class: the risk footer's NEW cost-model line (W5 deliverable:
"a live cost model (shows gross and net)"):
  "costs: live plan is GROSS of costs — est round-trip 2 x 10 bps/side
   ~0.20% one-off on the deployed X% (the backtest nets the same
   10 bps/side; estimate, not a net-return claim)"
At 110/160 the diff is exactly 2 lines per golden (the line + its wrap);
at 40/70 it is 3-6 lines (the same line wrapped narrower) — the wrapped
continuation lines keep their indent (W3's separator-glued _wrap).
NO other line changes: decisions table, verdict, layers, data: cells,
summary card, ERRORS & WARNINGS, DATA SOURCES, disclaimer all
byte-identical (full diff: evidence/w18_w5_goldens_diff.txt).
Re-verified: generator gates (no dates, SYNTHETIC, colour==plain), the
466-test suite green, fuzz byte-identical, freeze/replay exit 0, frozen
decision hash unchanged (display-only change).
