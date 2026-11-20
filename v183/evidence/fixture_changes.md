# evidence/fixture_changes.md — PHASE 2 (v1.7.0-dev)

Every fixture / invariant-value change touching existing tests in this
phase, each with the justification the phase-2 prompt demands: what
changed, why the old value was wrong, and proof the assertion is not
weaker. No assertion was weakened. Items that could NOT be justified on
this tree are left untouched and marked DEFERRED with their owner
defect (the prompt's explicit fallback).

--------------------------------------------------------------------------------
1. fuzz_decisions.py I3 invariant — UPDATED (ported with the script)
--------------------------------------------------------------------------------
WHAT CHANGED: the overlay-fuzz invariant block now asserts the v1.4.1
HARDENED B5 contract: a blocked row must END as AVOID with conviction
capped below WATCH, and only the sanctioned WATCH-1 re-assert cap may
change a blocked row's conviction (`I3-overlay-blocked`,
`I3-overlay-blocked-uncapped`, `I3-overlay-adjusted-blocked` replace the
pre-v1.4.1 "blocked rows pass through untouched" reading).

WHY THE OLD VALUE WAS WRONG: the old invariant would flag the B5 FIX
itself — it preserved hand-built inconsistent states (blocked but
LONG/WATCH, or uncapped) instead of correcting them, which is exactly
the defect B5 exists to remove. v1.4.1's HANDOFF documents the same
change on its own base ("the old invariant flagged the fix itself").

PROOF NOT WEAKER: the new invariant is strictly STRONGER — it still
catches any adjustment arithmetic touching a blocked row (the
`I3-overlay-adjusted-blocked` check is unchanged in spirit and stricter
in wording), AND it additionally catches the two states the old one
never examined (blocked-not-AVOID, blocked-uncapped). RED->GREEN record:
the ported fuzz on the unported tree reported
I3-overlay-blocked 2984 / I3-overlay-blocked-uncapped 2861
(evidence/phase2_fuzz_red.txt); after the B5 port, both suites are 0
(evidence/phase2_fuzz_green.txt) and the only remaining suite is the
pre-existing DISCLOSED I1-ml-scaled-range (1231 — byte-identical count
to v1.4.1's post-fix run: out-of-contract DIRECT calls of _ml_scaled,
whose production consumers are guarded and tested).

--------------------------------------------------------------------------------
2. v1.4.1 fixture update #1 (_mk_ml_model report hash-binding) — DEFERRED
3. v1.4.1 fixture update #2 (test_activate_refused negative cases) — DEFERRED
--------------------------------------------------------------------------------
WHAT v1.4.1 DID: (1) the _mk_ml_model test helper's validation report
gained model_sha256 (computed from the npz it just wrote) +
dataset_sha256, because M5 made a real "passing" report hash-bound; (2)
test_activate_refused_without_passing_report gained two NEW negative
cases (wrong model hash -> rc 2, wrong dataset hash -> rc 2) on the same
fixture.

WHY THEY CANNOT LAND IN PHASE 2 (the prompt's DEFERRED rule): these
fixtures exist to be FAITHFUL to M5's hash-bound-activation contract.
That contract is NOT ported yet: this tree's ml_train --activate performs
NO hash verification (defects.md B-4, "the v1.5.0 ml_train.py:687-707
does NO hash verification"), because the M5 port is scheduled with the
ML layer in phase 3 (the phase-2 port list scopes this phase to the
decision layer + scripts + atomic writes; the accounting in port_map.md
records M4/M5 — and the rest of the ML half — for phase 3). Adding
hash fields to fixtures no gate reads would be decoration asserting a
contract the code does not have, and "the assertion is not weaker" could
not be demonstrated without the gate itself.

NOT WEAKENED: nothing was weakened — the two wip fixtures are left
byte-identical to phase 1 (their assertions all still pass: 288/288).
The v1.4.1 updates are recorded here and in port_map.md as the phase-3
obligation: when M5 ports, the fixture update AND the two negative cases
must land in the same red->green step as the --activate hash checks.
Owner defect: B-4 (OPEN, target phase now recorded as 3).

--------------------------------------------------------------------------------
4. Phase-2 test-authoring correction (BEFORE first green) — disclosed
--------------------------------------------------------------------------------
WHAT: this phase's own NEW test test_b6_mode_keys_drive_the_standard_mode
was first drafted to ALSO assert that the import-built
CONFIG["MODES"]["standard"] dict tracks a LATER
mock.patch.dict(CONFIG, ...) mutation. That is an over-reach beyond the
ported v1.4.1 contract: MODES is built from the keys at import (a dict
literal cannot track later mutations — v1.4.1's own test asserts the
monkeypatch only through _apply_mode). The draft was corrected before
first green: the apply-time monkeypatch assertions (123.0/7) are kept
verbatim from v1.4.1, and the import-time half asserts the built preset
EQUALS the keys as loaded (no drift).

NOT WEAKER: the corrected test still proves exactly what B6 requires —
that EARNINGS_TOP_K / LAYER_TIMEOUT_S are LIVE inputs to the standard
preset (change the key -> the resolved preset changes; the built preset
agrees with the keys). No existing test was touched.

================================================================================
# PHASE 3 (v1.7.0-dev) — fixture / contract changes, each justified
================================================================================

5. TestFeatureCap contract move (pooled -> per-fold selection) — UPDATED
--------------------------------------------------------------------------------
WHAT CHANGED: the three §7.2 tests moved from the v1.5.0 pooled
select_features(X, y, groups, feats, splits) contract to the phase-3
per-fold select_features_fold(X, y, feats, train_idx) contract (cap 20
unchanged): selection now runs INSIDE each training fold on that fold's
own train window, and the final refit selects on all labeled rows
(disclosed in the report).

WHY THE OLD CONTRACT WAS WRONG: the pooled ranking averaged importances
over EVERY fold's train window — an early fold's train window contains
rows that are LATER folds' test-period data (the expanding window), so
the single fixed feature set the old code shipped was chosen with
knowledge of test periods (F16; the phase-3 prompt's "select features
INSIDE each training fold only"). v1.4.1 had no selection at all, so
this is the one place the port is a REWRITE of a v1.5.0 addition rather
than a v1.4.1 function.

PROOF NOT WEAKER: the new tests assert everything the old ones did (cap
enforced, the signal feature survives, "not needed" for small sets, the
shipped heads <= 20 features, the report records selection) AND add the
perturbation proof the old contract could not express (perturb rows
OUTSIDE the train window — labels AND values — the keep set is
bit-identical). RED->GREEN: the rewritten tests failed on the as-shipped
tree (evidence/phase3_red.txt: AttributeError select_features_fold /
missing per-fold records); they pass after the port.

6. The two DEFERRED v1.4.1 fixture updates (items 2-3 above) — LANDED
--------------------------------------------------------------------------------
WHAT CHANGED (exactly v1.4.1's updates, as promised "when M5 ports"):
(1) _mk_ml_model's validation report now carries model_sha256 (sha256
of the npz it just wrote) + dataset_sha256 (the npz's own pin), plus
new calib_a/calib_b/dataset_sha kwargs the B8 tests needed; (2)
test_activate_refused_without_passing_report gained the wrong-model-hash
(rc 2) and wrong-dataset-hash (rc 2) negative cases in BOTH its sklearn
and no-sklearn branches.

WHY NOW: M5's hash-bound contract did not exist in phase 2; adding hash
fields then would have decorated fixtures no gate reads. The gates now
exist and VERIFY (loader + --activate), so the fixtures must be faithful.

NOT WEAKENED: the old assertions all remain (no report -> 2, failing
verdict -> 2, passes -> 0 + ACTIVE). The positive-case fixture in the
sklearn branch forges the VERDICT ("beats") over the trainer's real
report while keeping the TRUE hashes — the hash binding is the surface
under test there (the no-sklearn branch writes both by hand). The
no-sklearn branch's minimal npz now carries dataset_sha256="0"*12, which
the phase-3 --activate REQUIRES (a pin-less npz is refused): recorded
below as the deliberate strengthening.

7. --activate dataset-pin strictness (a disclosed strengthening over v1.4.1)
--------------------------------------------------------------------------------
WHAT: v1.4.1's --activate compared report.dataset_sha256 to the npz's pin
and let empty==empty pass; phase 3 REFUSES an npz (or report) with no
dataset pin at all. The no-sklearn test fixture was updated to carry
real pins rather than rely on the empty==empty hole.

WHY: an npz without a dataset pin is a malformed/legacy artifact; the
spec's "verified at load and at --activate" is meaningless if "both
absent" can satisfy it. Not weaker in any direction: every case that
passed before still passes except the malformed one.

8. Verdict vocabulary: "insufficient evidence" (phase-3 prompt)
--------------------------------------------------------------------------------
WHAT: a failed sample gate (periods/rows/calibration) now yields verdict
"insufficient evidence" with verdict_why naming each failed condition;
"beats" and "fails" (the judged-negative case: gates pass, IC/Brier do
not) keep their v1.4.1 meanings. The v141-ported tests that asserted
"fails" for sample-gate failures were updated to the new vocabulary in
the same red->green step (test_m3_insufficient..., test_m4_gate_*).

WHY: the phase-3 prompt states it verbatim ("Otherwise the verdict is
'insufficient evidence' (state which condition failed)"). v1.4.1's own
tests could not foresee the wording; the CONDITIONS asserted are the
same or stronger (the gate tests now assert the named condition's text).

9. C-6 skip guard on the selection test — UPDATED
--------------------------------------------------------------------------------
WHAT: test_select_features_fold_cap_and_train_only skips cleanly where
sklearn is genuinely absent (B7's "ML tests skip cleanly with sklearn
blocked"), instead of failing on the unrankable-keep-all path.

WHY: the test needs a real pipeline fit; without sklearn the function's
honest "unrankable — kept all, disclosed" branch is the CORRECT
behaviour, and asserting a 20-feature selection there would assert an
impossibility. The blocked-deps matrix cell asserts the skip; the
refusal paths themselves stay asserted by TestMLTrain (no skip).
