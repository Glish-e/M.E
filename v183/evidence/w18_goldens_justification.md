# v1.8.0 goldens regeneration — written justification (W1)

Command: `python3 scripts/make_goldens.py --regen` (C-4 discipline: the
regen flag is mandatory; goldens are fixtures).

Reason: W1 bumps master.__version__ "1.7.0-dev" -> "1.8.0-dev" (the
release identity; the split is a structural change). The version prints
in the report header line.

Diff, all 12 files (colour/plain/ASCII x 40/70/110/160): EXACTLY ONE
line each — the header "MASTER v1.7.0-dev ..." -> "MASTER v1.8.0-dev
..." — same columns, same width padding, same everything else
(byte-level diff in evidence/w18_goldens_diff.txt). No data line, table
row, warning, footer, disclaimer or exit-code-relevant text changed.

Re-verified after regen: the generator's own gates pass (no real dates,
SYNTHETIC banner present, strip_ansi(colour) == plain at every width).
