# v1.8.2 goldens regeneration justification (R14/R15 disclosure)

Regenerated TWICE during the v1.8.2 hardening pass with
`python3 scripts/make_goldens.py --regen` (same harness, same masks:
ISO dates -> FROZEN-DATE, durations -> Xs; nothing else).

WHY the report bytes changed (all render/classification-only, R15: no
decision input changed; decision hashes unchanged, see
evidence/v182_decision_hash.txt):

1. W4 (first regen): warnings that previously classified as W_UNUSUAL
   now carry their stable codes — the stub run's "credit OFF — not
   trade-grade" renders as W_CREDIT_OFF, "earnings accuracy: SIGNAL"
   as W_EARNINGS_ACCURACY, "N ticker(s) no earnings history" as
   W_EARNINGS_MISSING, the bare quality flag words as W_QUALITY_FLAG.
   The stub warnings THEMSELVES are unchanged; only the ERRORS &
   WARNINGS code column changed.
2. Version string (second regen): me/core.py __version__ 1.8.1 ->
   1.8.2 changed the header bytes ("MASTER v1.8.2 · ...") after the
   W-code regen; same harness, same masks.

The engine inputs, layers, fusion, thresholds, stub data and every
warning TEXT are byte-identical to v1.8.1; the goldens diff is exactly
the two causes above.
