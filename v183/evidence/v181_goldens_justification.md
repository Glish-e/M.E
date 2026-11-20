# v1.8.1 goldens regeneration justification (R14/R15 disclosure)

Regenerated once for final_master_f with `python3
scripts/make_goldens.py --regen` (same harness, same masks: ISO dates ->
FROZEN-DATE, durations -> Xs; nothing else).

WHY the report bytes changed (all render/banner-only, R15: no decision
input changed; decision hashes unchanged, see
evidence/v181_decision_hash.txt):

1. N4: the report now ends with the FETCH HEALTH block (stub runs print
   the honest "stub layers — no fetches (MASTER_STUBS)" note line).
2. F4/F5: the [plan] "refresh plan:" line changed from presence counts
   ("90/90 cached") to TTL-freshness counts ("N/M fresh by TTL (7d) ·
   K due refresh") and the macro fragment gained cadence wording
   (fresh/refresh-due/stale-data/cold).
3. F3: classification codes changed ONLY for previously-W_UNUSUAL
   texts (W_ENGINE_NO_VERSION etc.) — the stub warnings themselves are
   unchanged, so the ERRORS & WARNINGS block bytes change only through
   items 1-2.

The engine inputs, layers, fusion, thresholds and stub data are
byte-identical; the goldens diff is exactly the block above.

(Second regeneration, same day: the version string v1.8.0-dev ->
v1.8.1 changed the header bytes AFTER the first regen; same harness,
same masks, same three render causes below.)
