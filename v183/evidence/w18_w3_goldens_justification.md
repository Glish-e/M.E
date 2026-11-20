# v1.8.0 W3 goldens regeneration — written justification

Command: `python3 scripts/make_goldens.py --regen` (C-4 discipline).

Why goldens change in W3 (the workstream's PURPOSE is fixing the render):
1. Header `data:` provenance cells relabelled — OLD: 'macro stub n/a OK
   n/a' (five unlabeled values, the owner-reported noise); NEW:
   'macro: stub . as-of n/a . OK . age n/a' (labelled, packed as units,
   field-dropping below width 96/64). All 12 goldens, the data: lines
   only.
2. NEW `SUMMARY` card line(s) after the header box (verdict counts ·
   risk class · warnings · top picks) — the W3 addition; tiered and
   width-bounded (progressive field append).
3. Layer rows re-assembled with drop-by-priority — OLD could glue the
   truncated engine name to the elapsed column
   ('ml_train SYNTHETI.Xs' in ascii goldens = the reported
   'ml_train SYNTHETI...' bug); NEW keeps whole-word names
   ('ml_train SYNTHETIC-stub 0.0s') and one+ space between cells.
4. DATA SOURCES now packs whole per-layer cells between ' · ' — the OLD
   line hard-truncated mid-name at narrow widths ('risk SYNTHET…').
5. Header wraps no longer leave a dangling ' ·' at end-of-line
   (separator glued to the FOLLOWING word).

Scope of change (evidence/w18_w3_goldens_diff.txt, 300 diff lines over
12 files): the render surfaces above ONLY. The decisions table, footer
disclaimer, LEGEND, ERRORS & WARNINGS block, exit codes, JSON/CSV
schemas: byte-identical (the diff contains no table/footer/legend line).
Re-verified by the generator's own gates: no real dates, SYNTHETIC
banner present, strip_ansi(colour) == plain at every width; plus
TestUiFixesV18 (9 tests) and the full 451-test suite green; fuzz
byte-identical; freeze/replay exit 0; the frozen ranking decision hash
2734886b...972595 UNCHANGED (render-only change, R15).
