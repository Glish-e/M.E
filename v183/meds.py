"""
meds.py — Macro Regime & L/S Scenario Engine v14.7 — single-file engine.

WHAT IT IS
  A macro-regime research backtester + signal generator for US ETFs. Once a
  month it reads 22 FRED macro series, scores 7 economic scenarios (plus a
  Neutral fallback), maps the winner to an ETF basket, sets gross leverage
  between 0.5x and 2.0x (conviction, trend cap, crash guard, defensive cap,
  drawdown throttle), and simulates next-month trades with costs, financing
  and an optional 3% VXX crisis hedge. It places NO orders and has NO broker
  code. Walk-forward validation, a frozen preregistration (PREREG C01-C13),
  a paper-trading record and a small Python API are included.

SETUP
  pip install pandas numpy yfinance          (scipy optional; yfinance is
  imported lazily, so --help / --check-config / import work without it)
  FREDAPI — read from the environment (FREDAPI, FRED_API_KEY, FRED_API,
  FRED_APIKEY, case-insensitive) or from a .env file next to this file, ONLY
  if that file already exists (it is never created). Without a key the
  engine falls back to FRED's public fredgraph.csv and, fully offline, to
  the verified meds_cache/ (MEDS_CACHE=1) or a frozen snapshot/ folder.
  BAML credit CSVs in data/ are read-only inputs.

RUN  (one command, no steps)
  python meds.py                 THIS month's prediction as a short card:
                                  regime, confidence, leverage, LONG/SHORT
                                  basket, data tier, credit state.  No
                                  backtest; cold run fetches 22 FRED series
                                  (one stderr line), later runs are warm
                                  (<=2s from the verified card cache).
  python meds.py --from 2024-01 [--to 2024-12]
                                  month-by-month regimes + baskets (one
                                  fetch, one classification pass; clamped
                                  to the predictable range with notices).
  python meds.py --audit          the FULL run: data -> walk-forward ->
                                  backtest -> prereg -> readiness report
                                  (the v14.6.2 plain run; --csv implies it).
  python meds.py --ticker SPY    score ONE ticker against the live regime.
  python meds.py --ticker SPY --json    machine-readable score (for a layer).
  python meds.py --check-endpoints     one tiny read-only request per source.

OUTPUT
  The bare run prints the prediction card (<=22 lines, colours; NO_COLOR or
  non-tty disables them); exit 0 = valid prediction (DEGRADED included),
  2 = no prediction / bad input (one line, no traceback).  The full report
  (--audit) ends with RESULT: OK | RESULT: NO-GO <reason> | RESULT:
  FAILED <real error>. A default run writes NOTHING to disk except the
  card cache meds_cache/ (the warm-card path; MEDS_CACHE=1 additionally
  caches full-run data); the only other opt-in writes are --csv FILE
  (monthly results), --paper (paper_record.csv) and --ml (macro_ml.npz).
  Every network/parse/cache failure prints the REAL upstream message via
  one formatter (_describe_failure), with the API key redacted.

LAYER
  from meds import (ticker_score, regime_now, mrs, mrs_at, mrs_ml, tpl,
                     now, span, render_card, render_span)
  now()                              -> dict (card: regime + status/quality)
  span("2024-01", "2024-12")         -> dict (rows[], status, notices[])
  regime_now()                       -> dict (scenario, confidence, basket)
  ticker_score("SPY")                -> dict (score 0-100 + components)
  ticker_score("SPY", as_of="2020-03-31")   -> point-in-time safe
  API functions never print, never raise on data problems (they return an
  {error, source, detail} dict), never mutate module globals, and share one
  in-RAM memo (1h TTL) so repeat calls do not refetch.

OTHER FLAGS
  --snapshot, --audit, --start/--end DATE, --fetch-start DATE,
  --output-start/--output-end DATE, --require-credit, --ml, --demo,
  --paper, --pit-manifest, --print-config, --check-config, --help.
  Exit codes: 0 ok | 1 failure | 2 NO-GO | 64 bad config | 130 Ctrl+C.

CHANGELOG v14.7 (speed + layer + card CLI, vs v14.6.2)
  SPEED   bit-identical hot-path rewrites (oracle: 2,307 real-data cases,
          0 mismatches): per-series SPY trend table, positional numpy
          overlay loop (label loop kept as fallback), vectorised month-end
          mask, fork-pool grid search with in-order trial merge, zip-based
          parse_signals.  Suite 132s -> 17s.
  LAYER   now()/span()/render_card()/render_span() + __all__; the card
          prefers a fresh verified meds_cache/fredcard/ (warm <=2s) and a
          cold card writes it back (H7).
  CLI     bare run = the prediction card (exit 0/2); the old full report
          moved to --audit (--csv/--prereg-full imply it); --from/--to
          spans with clamps/notices + --json; --start/--end keep their
          backtest meaning with --audit, alias --from/--to without it.
  RULES   skipped derived series recorded (4a); retained-weight warnings
          <70% (4b); backtest clamps at -100% and stops at ruin (4c);
          degenerate stats NaN+status, rendered n/a (4d); except-pass
          logged or justified (4e).  Default FRED UA + public-tier 429
          backoff (Step 8).  Tests: literal micro-tables or real
          snapshot/data files only (skip if absent, never fake).

CHANGELOG v14.6.2 (STEP A: credit mode, vs v14.6.1)
  A       USER-REQUESTED: FRED's free-tier ICE BofA OAS window is a rolling
          ~3y (was a hard NO-GO).  credit_mode "auto" (default) runs without
          the credit signal when the OAS pair misses the need date — series
          dropped, credit scenarios + kill-switch OFF, banner + credit_signal
          warnings, PREREG BLOCKED, DEGRADED; --require-credit = v14.6.1.

CHANGELOG v14.6.1 (BUG 6: strict-vintage API tier, vs v14.6)
  BUG 6   the API tier's realtime-RANGE requests sent units=pc1/chg and FRED
          now answers that with HTTP 400 ("If output_type is '1' and units is
          not 'lin', then realtime_start must equal realtime_end...") ->
          core series (CPIAUCSL/PCEPILFE/INDPRO/PAYEMS) never served, NO-GO.
          Fix: _build_fred_obs_url REFUSES non-lin units with a range (fail
          fast, offline); range fetches bring LEVELS and pc1/chg are applied
          LOCALLY per release date (new §13.2b _apply_fred_units_vintage,
          vectorised pivot+shift; k from the shared §13.2a _fred_units_k) —
          both terms of every ratio come from ONE information set, so a
          year-ago revision enters only from its own realtime_start (PIT
          safe); the pc1 cross-check now pins ONE vintage
          (realtime_start == realtime_end == output_end) for BOTH its
          requests (FRED's own pc1 + the lin levels, transformed with the
          same code); locally transformed specs fetch the same 14-month
          warmup as the public CSV tier so the served window is unchanged;
          lin / real-time / public-CSV / snapshot paths untouched.

CHANGELOG v14.6 (partial-frame trust pass, vs v14.5)
  A       a PARTIAL price frame can never produce a verdict: the shared
          frame is completeness-checked (§17.7 _frame_gaps — missing
          tickers, truncated date ranges vs measured listing floors) and
          the download retried up to 3 attempts through _safe_yf_download
          paced by _API_PACER; still-PARTIAL FAILS C13 (naming the gaps) so
          PREREG = BLOCKED; ticker_score refuses a truncated OWN series
          and flags other-ticker gaps price_frame PARTIAL (yellow card).
  B       data fingerprint (§17.8): per-ticker rows + first/last date and
          the 12-hex sha256 of the month-end close panel (the stable digest
          — Yahoo's daily adjusted closes jitter at the last bits between
          downloads) printed at the end of a full run and in --ticker
          (print-only, never a file).

CHANGELOG v14.5 (structure pass, vs v14.4)
  MAP     25 numbered sections (§ 1..§ 25) with a `§N.k` one-line banner above
          EVERY top-level symbol — any issue is locatable by grepping its
          §-address; comments only, behaviour is untouched.
  ENV     --check-config and the run header report the FACT when a .env
          exists next to meds.py but carries no FRED key variable (U2).

CHANGELOG v14.4 (final fix pass, vs v14.1)
  U1-U5   one-command run + --validate alias + short phase-timed report
          with a RESULT: verdict line; Ctrl+C exits 130 naming the phase.
  U4/U6   import meds is now side-effect free: no directory is created, no
          logger is silenced, yfinance is imported lazily at first use.
  U7-U11  layer contract: quiet API (notes returned, never printed),
          stable failure shape, regime_now(), ticker_score(as_of=...) PIT
          safe, in-RAM memo (1h TTL, lock), per-call diagnostics instead of
          module-global mutation.
  ERRORS  one _describe_failure formatter for every network/parse/cache/
          file failure: status+reason or exception class+message, the
          upstream body verbatim (<=300 chars), attempt counter, elapsed;
          API key redacted everywhere; yfinance per-ticker messages are
          captured (logger handler + shared._ERRORS), never silenced.
  D1-D4   zero writes on a default run; the object cache is now ONE
          gzip-compressed JSON file with its own SHA-256, 24h TTL, 50MB
          cap, written only under MEDS_CACHE=1; snapshot prices are rebuilt
          from hash-verified CSVs instead of loading executable object
          files.
  S1-S3   keyed FRED requests share one pacer capped at 100/min (below
          FRED's documented 120); ONE price download per run shared by the
          backtest, attribution and ticker_score; the classifier runs once
          per panel month (ticker_score reuses the first pass).
  R6      PREREG benchmarks corrected to the owner's specification:
          SPY buy-and-hold, 60/40 SPY/TLT, SMA10-only, cash (hash re-pinned).
  CLI     --ticker/--json, --validate, --check-endpoints, --csv FILE.

CHANGELOG v14.1 (audit release, vs v14.0)
  Publication-lag PIT for EVERY delayed-release series on the non-API
        tiers, each anchored to a dated release on the publisher's own
        schedule (PIT_LAG_EVIDENCE); a month-end row now consumes only
        values the publisher had actually released by that month end.
  PIT manifest generated from code (build_pit_manifest / --pit-manifest);
        CFNAI's publication lag corrected to end of the FOLLOWING month;
        DTWEXBGS corrected to the weekly Monday H.10 update.  PIT fetch
        floor: loaders fetch from fetch_start minus the max publication lag.
  pc1 is percent change from the YEAR-AGO observation (FRED's definition)
        on every tier; verified download cache with SHA-256 manifest;
        BAMLC0A0CM added to the mandatory guard; walk-forward state
        continuity; drifted-weight turnover accounting; true close-to-close
        SPY B&H benchmark; 9-state readiness framework; frozen PREREG with
        hash pin; trial ledger; paper mode.
"""
from __future__ import annotations

import asyncio
import base64
import concurrent.futures
import gzip
import io
import json
import math
import os
import re
import sys
import threading
import urllib.error
import urllib.request
import warnings
from contextlib import contextmanager
from collections import OrderedDict
from dataclasses import dataclass, field, asdict, replace
from datetime import datetime
from statistics import NormalDist
from typing import Any, Callable, Iterable, Sequence

try:
    import numpy as np
    import pandas as pd
except ImportError:              # reported cleanly by main_cli (exit 2)
    np = None
    pd = None

import hashlib
import logging
import multiprocessing
import time
import urllib.parse
from zoneinfo import ZoneInfo

# v14.4 U4: yfinance is imported LAZILY at first use (see _load_yf).  A
# missing yfinance must not break --help, --check-config, --pit-manifest or
# a plain `import meds`; the run degrades to the snapshot/cache price tiers
# and reports the real import error.
yf = None                      # set by _load_yf() on first successful import
_YF_IMPORT_ERROR: Exception | None = None
_YF_TRIED = False
_YF_CACHE_DIR: str | None = None

__version__ = "14.7.0"

#──────────────────────────────────────────────────────────────────────────────
#  SECTION MAP — every top-level symbol carries a `§N.k` banner; grep it
#  (rg "§ 12" meds.py).  Line numbers below are as shipped; they drift.
#    § 1  FRED key loading (U2) ..............................................   L275
#    § 2  Error contract — _describe_failure + redaction (R8) ................   L339
#    § 3  Per-call diagnostics sink & in-RAM memo (U7/U10/U11) ...............   L442
#    § 4  Rate limiter — shared pacer, 100 req/min (S1) ......................   L573
#    § 5  Terminal output — colours + phase clock (U3) .......................   L598
#    § 6  Verified cache — gzip JSON, SHA-256, TTL (D3) ......................   L652
#    § 7  PIT publication lags (v14.1 D1) ....................................   L821
#    § 8  Easy settings — dates & paths ......................................   L874
#    § 9  Configuration — Config dataclass ...................................   L964
#    § 10 Indicators & scoring ..............................................  L1116
#    § 11 Scenario taxonomy — 7 + Neutral ...................................  L1277
#    § 12 FRED client & feature engine ......................................  L1412
#    § 13 Offline tiers — public CSV & snapshot .............................  L2519
#    § 14 Regime classifier & hysteresis ....................................  L3230
#    § 15 Risk manager & VXX overlay ........................................  L3456
#    § 16 Statistics & trial ledger .........................................  L3855
#    § 17 Price data — lazy yfinance (U4/S2) ................................  L4117
#    § 18 Backtester & daily ledger .........................................  L4666
#    § 19 Walk-forward engine ...............................................  L5449
#    § 20 Diagnostic — classification path ..................................  L5682
#    § 21 Presentation & orchestration ......................................  L5739
#    § 22 Short API — mrs/mrs_at/mrs_ml/tpl .................................  L7453
#    § 23 Layer API — regime_now/ticker_score ...............................  L7857
#    § 24 ML dataset builder ................................................  L8777
#    § 25 CLI entrypoint ....................................................  L9008
#──────────────────────────────────────────────────────────────────────────────


# ── Output directory (READ-ONLY by default: v14.4 D1 — nothing is created ──
# on import or on a plain run; only the explicit opt-ins write anything).
DATA_DIR = os.environ.get("MACRO_ENGINE_DATA_DIR", "data")

# v13.3 M-3: force the frozen snapshot for every network dependency
# (FRED series AND Yahoo prices). Set by --snapshot or MEDS_FORCE_SNAPSHOT=1.
FORCE_SNAPSHOT = os.environ.get("MEDS_FORCE_SNAPSHOT", "") not in ("", "0", "false", "False")

# v14.4 U2: the environment-variable names that may carry the FRED key,
# in precedence order, matched case-insensitively.
_FRED_KEY_NAMES = ("FREDAPI", "FRED_API_KEY", "FRED_API", "FRED_APIKEY")


# ── § 1.1 · _clean_key
# ══════════════════════════════════════════════════════════════════════════════
#  § 1 · FRED KEY LOADING — env vars, then an existing .env (U2)
# ══════════════════════════════════════════════════════════════════════════════
def _clean_key(v: str) -> str:
    return v.strip().strip('"').strip("'")


# ── § 1.2 · _load_env_fredapi ── v14.4 U2: the FRED API key. Read in this order: os.environ
def _load_env_fredapi() -> str:
    """v14.4 U2: the FRED API key.  Read in this order: os.environ
    (FREDAPI, FRED_API_KEY, FRED_API, FRED_APIKEY — matched
    case-insensitively), then a .env file next to meds.py ONLY if it
    already exists (a .env is never created; BAML credit CSVs in data/ are
    separate read-only inputs).  The key is never printed (see _redact)."""
    for name in _FRED_KEY_NAMES:
        v = os.environ.get(name)
        if v:
            return _clean_key(v)
    for k, v in os.environ.items():          # case-insensitive fallback
        if v and k.upper() in _FRED_KEY_NAMES:
            return _clean_key(v)
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(env_path):             # ONLY if it already exists
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    if k.strip().upper() in _FRED_KEY_NAMES:
                        return _clean_key(v)
        except OSError as e:
            # v14.7 4e: recorded, not silent — an unreadable .env means "no
            # key from it", and the diagnostics sink carries the real cause.
            _diag().notes.append(f".env unreadable ({e!r}) — no key from it")
    return ""


# ── § 1.3 · _dotenv_status ── v14.5 U2: a FACT (never advice) about the .env next to meds.py.
def _dotenv_status() -> str:
    """v14.5 U2: a FACT (never advice) about the .env next to meds.py.
    Returns '' when there is nothing unusual — no .env, a key IS configured
    from any source, or an unreadable .env.  Variable NAMES only, never
    values (R8)."""
    if _load_env_fredapi():
        return ""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as fh:
                names = [ln.partition("=")[0].strip() for ln in fh
                         if ln.strip() and not ln.strip().startswith("#")
                         and "=" in ln and ln.partition("=")[0].strip()]
        except OSError:
            return ""
        if names:
            shown = ", ".join(names[:6]) + (" …" if len(names) > 6 else "")
            return (f".env next to meds.py has no FREDAPI/FRED_API_KEY/FRED_API/"
                    f"FRED_APIKEY variable (found only: {shown}) — no FRED API "
                    f"key configured; the keyless/offline tiers are in use")
    return ""


# ═══════════════════════════════════════════════════════════════════════════
#  § 2 · ERROR CONTRACT — one formatter, real messages only (R8)
#  Every network / parse / cache / file failure is routed through
#  _describe_failure(): status+reason or exception class+message, the
#  upstream body verbatim (<=300 chars), the attempt counter and elapsed
#  seconds — with the API key redacted.  Nothing generic is ever printed.
# ═══════════════════════════════════════════════════════════════════════════
# ── § 2.1 · _active_key_material ── Key values that must never appear in any message (env + Config…
def _active_key_material() -> list[str]:
    """Key values that must never appear in any message (env + Config)."""
    out = []
    for name in _FRED_KEY_NAMES:
        v = os.environ.get(name)
        if v:
            out.append(v.strip())
    try:
        v = getattr(CFG, "fred_api_key", "")
        if v:
            out.append(str(v))
    except (AttributeError, NameError):
        pass                         # Config not built yet / replaced
    return out


# ── § 2.2 · _redact ── R8: replace `api_key=<anything>` and the literal key value wherev…
def _redact(text: str) -> str:
    """R8: replace `api_key=<anything>` and the literal key value wherever
    they appear (URLs, exception text, repr).  Every message passes through
    this before it is printed or stored."""
    if not isinstance(text, str):
        text = str(text)
    text = re.sub(r"api_key=[^&\s'\"<>]+", "api_key=***", text)
    for key in _active_key_material():
        if key:
            text = text.replace(key, "***")
    return text


# ── § 2.3 · _body_summary ── The upstream body, verbatim, <=300 chars. FRED JSON bodies print
def _body_summary(body: str) -> str:
    """The upstream body, verbatim, <=300 chars.  FRED JSON bodies print
    their error_code and error_message exactly as returned; non-JSON bodies
    (HTML error pages, empty bodies) print their first 300 characters."""
    if body is None:
        return ""
    text = body if isinstance(body, str) else str(body)
    text = text.strip()
    if not text:
        return ""
    try:
        doc = json.loads(text)
        if isinstance(doc, dict) and ("error_code" in doc or "error_message" in doc):
            return (f"error_code={doc.get('error_code')} "
                    f"error_message={doc.get('error_message')}")[:300]
    except ValueError:
        pass   # v14.7 4e: body is not JSON — fall through to the plain-text view
    return " ".join(text.split())[:300]


# ── § 2.4 · _describe_failure ── v14.4 section 3: the ONE failure formatter. Fields, in order,
def _describe_failure(source: str, request: str, *, http=None, exc=None,
                       body=None, url: str | None = None,
                       attempt: int | None = None, attempts: int | None = None,
                       elapsed: float | None = None) -> str:
    """v14.4 section 3: the ONE failure formatter.  Fields, in order,
    skipping only the ones that do not apply:
      1. source   — FRED API | FRED public CSV | Yahoo (yfinance) | local file | cache
      2. request  — series id or ticker list, the date window, and the URL
                    (key replaced by ***); attempt counter when retried
      3. HTTP status AND reason phrase, or the exception class and message
                    (plus __cause__ when present)
      4. the upstream body verbatim, <=300 characters
      5. elapsed seconds
    The angle-bracket parts are always filled from the real response —
    never invented."""
    head = f"✗ {source}  {request}"
    if attempt is not None:
        head += f"  attempt {int(attempt)}/{int(attempts)}" if attempts else f"  attempt {int(attempt)}"
    lines = [head]
    if url:
        lines.append(f"  url: {url}")
    if http is not None:
        code = getattr(http, "code", None)
        reason = getattr(http, "reason", "") or ""
        lines.append(f"  HTTP {code} {str(reason).strip()}".rstrip())
    if exc is not None:
        name = type(exc).__name__
        msg = str(exc)
        line = f"  {name}: {msg}" if msg else f"  {name}"
        cause = getattr(exc, "__cause__", None)
        if cause is not None:
            cmsg = str(cause)
            line += (f"  (caused by {type(cause).__name__}: {cmsg})"
                     if cmsg else f"  (caused by {type(cause).__name__})")
        lines.append(line)
    summary = _body_summary(body)
    if summary:
        lines.append(f"  upstream: {summary}")
    if elapsed is not None:
        lines.append(f"  elapsed {elapsed:.2f}s")
    return _redact("\n".join(lines))


# ══════════════════════════════════════════════════════════════════════════════
#  § 3 · PER-CALL DIAGNOSTICS SINK & IN-RAM MEMO (U7/U10/U11)
# ══════════════════════════════════════════════════════════════════════════════
# Legacy module-global collections (kept as the DEFAULT sink so the CLI run
# and the tests keep one shared view).  While an API call holds
# _capture_diagnostics(), every helper records into that call's private
# sink instead — no module global is mutated (U11), nothing prints (U7),
# and the collected notes/warnings/errors are returned in the result dict.
SCORE_ERRORS: list[str] = []
YF_DOWNLOAD_ERRORS: list[str] = []
PRICE_SOURCE_NOTES: list[str] = []
# v14.1 S7 (audit H6): in-memory TRIAL LEDGER — every backtest trial (full
# runs and walk-forward folds) is recorded with a config fingerprint and
# headline stats so a validation claim can be audited against what was
# actually run.  In-memory only (never persisted), capped at TRIAL_LEDGER_MAX.
TRIAL_LEDGER: list[dict] = []
TRIAL_LEDGER_MAX: int = 2000


# ── § 3.1 · _Diagnostics ── Per-call collection of everything the CLI would print.
class _Diagnostics:
    """Per-call collection of everything the CLI would print."""
    __slots__ = ("score_errors", "yf_errors", "price_notes", "notes",
                 "trials", "quiet", "fetch_failures")

    def __init__(self, quiet: bool = True):
        self.score_errors: list[str] = []
        self.yf_errors: list[str] = []
        self.price_notes: list[str] = []
        self.notes: list[str] = []
        self.trials: list[dict] = []
        self.quiet = quiet
        self.fetch_failures: dict[str, str] = {}

    def warnings(self) -> list[str]:
        return list(self.yf_errors) + list(self.price_notes)

    def errors(self) -> list[str]:
        return (list(self.score_errors)
                + list(self.fetch_failures.values()) + list(self.yf_errors))


# The CLI/default sink: aliases the legacy module globals (appends land in
# the very lists main_async prints and the tests inspect).
_CLI_DIAG = _Diagnostics(quiet=False)
_CLI_DIAG.score_errors = SCORE_ERRORS
_CLI_DIAG.yf_errors = YF_DOWNLOAD_ERRORS
_CLI_DIAG.price_notes = PRICE_SOURCE_NOTES
_CLI_DIAG.trials = TRIAL_LEDGER

# A stack (module-global, lock-protected) rather than a ContextVar: the
# asyncio/executor machinery inside _run() executes the coroutine on worker
# threads, and context changes do not cross thread boundaries.
_DIAG_STACK: list[_Diagnostics] = []
_DIAG_LOCK = threading.RLock()


# ── § 3.2 · _capture_diagnostics
@contextmanager
def _capture_diagnostics(quiet: bool = True):
    d = _Diagnostics(quiet=quiet)
    with _DIAG_LOCK:
        _DIAG_STACK.append(d)
    try:
        yield d
    finally:
        with _DIAG_LOCK:
            if _DIAG_STACK and _DIAG_STACK[-1] is d:
                _DIAG_STACK.pop()
            else:
                try:
                    _DIAG_STACK.remove(d)
                except ValueError:
                    pass   # v14.7 4e: already popped by an unwound capture


# ── § 3.3 · _diag
def _diag() -> _Diagnostics:
    with _DIAG_LOCK:
        return _DIAG_STACK[-1] if _DIAG_STACK else _CLI_DIAG


# ── § 3.4 · _emit ── U7: on an API path a note is COLLECTED; on the CLI path it is pri…
def _emit(msg: str) -> None:
    """U7: on an API path a note is COLLECTED; on the CLI path it is printed."""
    d = _diag()
    if d.quiet:
        d.notes.append(msg)
    else:
        print(msg)


# ── v14.4 U10/S7: in-RAM memo (one-hour TTL, lock-protected) ─────────────────
_MEMO_LOCK = threading.RLock()
_MEMO: dict = {}
_MEMO_TTL_SECONDS = 3600.0


# ── § 3.5 · _memo_get
def _memo_get(key):
    with _MEMO_LOCK:
        e = _MEMO.get(key)
        if e is None:
            return None
        if time.monotonic() - e["ts"] > _MEMO_TTL_SECONDS:
            _MEMO.pop(key, None)
            return None
        return e["value"]


# ── § 3.6 · _memo_put
def _memo_put(key, value) -> None:
    with _MEMO_LOCK:
        _MEMO[key] = {"ts": time.monotonic(), "value": value}


# ── § 3.7 · _memo_clear
def _memo_clear() -> None:
    with _MEMO_LOCK:
        _MEMO.clear()
    # v14.6 STEP A: the per-process retry budget goes with the memo — a
    # cleared memo means a fresh acquisition context (hermetic tests too).
    _FRAME_RETRY_SPENT.clear()


# ── v14.4 S1: request pacer for the keyed FRED tier ────────────────────────────
# FRED documents 120 requests/minute per key (429 beyond it; see
# fred.stlouisfed.org/docs/api/fred/errors.html).  The keyed tier is capped
# at 100/min — a strict minimum-interval pacer shared by all worker threads,
# so no burst can ever exceed the budget.
# ── § 4.1 · _Pacer
# ══════════════════════════════════════════════════════════════════════════════
#  § 4 · RATE LIMITER — one shared pacer, 100 req/min cap (S1)
# ══════════════════════════════════════════════════════════════════════════════
class _Pacer:
    def __init__(self, per_minute: float):
        self._interval = 60.0 / float(per_minute)
        self._lock = threading.Lock()
        self._next_ok = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now < self._next_ok:
                delay = self._next_ok - now
                self._next_ok += self._interval
            else:
                delay = 0.0
                self._next_ok = now + self._interval
        if delay > 0:
            time.sleep(delay)


_API_PACER = _Pacer(100.0)


# ══════════════════════════════════════════════════════════════════════════════
#  § 5 · TERMINAL OUTPUT — colours (NO_COLOR-safe) + phase clock (U3)
# ══════════════════════════════════════════════════════════════════════════════
# ── § 5.1 · _use_color
def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return bool(sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


# ── § 5.2 · _c
def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _use_color() else text


_PHASE = "startup"
_PHASE_TIMES: list[tuple[str, float]] = []


# ── § 5.3 · _phase ── U3: one line per phase with elapsed seconds; also names the phase…
class _phase:
    """U3: one line per phase with elapsed seconds; also names the phase a
    Ctrl+C lands in (U5)."""

    def __init__(self, name: str):
        self.name = name
        self.secs = 0.0

    def __enter__(self):
        global _PHASE
        _PHASE = self.name
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb):
        global _PHASE_TIMES
        self.secs = time.monotonic() - self._t0
        _PHASE_TIMES.append((self.name, self.secs))
        mark = "✓" if exc_type is None else "✗"
        print(_c(f"  {mark} {self.name} ({self.secs:.1f}s)", "36"))
        return False


# ── v14 FIX-3 → v14.4 D3: verified cache (ONE gzip JSON file, SHA-256) ──────
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meds_cache")
CACHE_FILE_NAME = "cache.json.gz"
CACHE_TTL_HOURS = 24.0
CACHE_MAX_BYTES = 50 * 1024 * 1024


# ── § 6.1 · _sha256_file
# ══════════════════════════════════════════════════════════════════════════════
#  § 6 · VERIFIED CACHE — ONE gzip JSON, SHA-256, 24h TTL (D3)
# ══════════════════════════════════════════════════════════════════════════════
def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ── § 6.2 · _cache_enabled ── D1: the cache may only be written when MEDS_CACHE=1 is set.
def _cache_enabled() -> bool:
    """D1: the cache may only be written when MEDS_CACHE=1 is set."""
    return os.environ.get("MEDS_CACHE", "") not in ("", "0", "false", "False")


# ── § 6.3 · _payload_sha256
def _payload_sha256(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


# ── § 6.4 · VerifiedCache ── v14.4 D3: ONE gzip-compressed JSON file (meds_cache/cache.json.gz)
class VerifiedCache:
    """v14.4 D3: ONE gzip-compressed JSON file (meds_cache/cache.json.gz)
    carrying its own SHA-256 over the payload, verified before parsing, with
    a 24-hour TTL and a 50MB cap (oldest entries evicted first).  Nothing is
    written unless MEDS_CACHE=1 is set; a tampered or corrupt file is
    reported through _describe_failure (source 'cache') and ignored."""

    # · __init__
    def __init__(self, root: str | None = None):
        self.root = root or CACHE_DIR
        self.path = os.path.join(self.root, CACHE_FILE_NAME)

    # ── load / verify ────────────────────────────────────────────────────
    # · _load_all
    def _load_all(self) -> dict:
        if not os.path.isfile(self.path):
            return {}
        try:
            with gzip.open(self.path, "rb") as fh:
                raw = fh.read()
        except (OSError, EOFError, ValueError) as e:
            _emit("  " + _describe_failure("cache", f"file={self.path}", exc=e,
                                          body="unreadable gzip file — cache ignored"))
            return {}
        try:
            doc = json.loads(raw.decode("utf-8", errors="replace"))
            payload = doc.get("payload") if isinstance(doc, dict) else None
            digest = doc.get("sha256") if isinstance(doc, dict) else None
            if not isinstance(payload, dict) or not isinstance(digest, str):
                raise ValueError("cache file is not a {payload, sha256} document")
            if _payload_sha256(payload) != digest:
                _emit("  " + _describe_failure(
                    "cache", f"file={self.path}",
                    body="SHA-256 mismatch over the payload — the whole cache "
                         "file is discarded"))
                return {}
            return payload
        except ValueError as e:
            _emit("  " + _describe_failure("cache", f"file={self.path}", exc=e,
                                          body=raw.decode("utf-8", "replace")[:300]))
            return {}

    # · _entry_age_days
    def _entry_age_days(self, entry: dict) -> float:
        try:
            return ((datetime.now() - datetime.fromisoformat(str(entry.get("written"))))
                    .total_seconds() / 86400.0)
        except (TypeError, ValueError):
            return float("inf")

    # ── write (MEDS_CACHE=1 only) ────────────────────────────────────────
    # · _write_all
    def _write_all(self, payload: dict) -> None:
        os.makedirs(self.root, exist_ok=True)
        # 50MB cap on the compressed footprint: evict oldest entries first.
        def _serialized(p: dict) -> bytes:
            doc = {"payload": p, "sha256": _payload_sha256(p)}
            return json.dumps(doc, separators=(",", ":")).encode("utf-8")
        blob = _serialized(payload)
        while len(gzip.compress(blob)) > CACHE_MAX_BYTES and payload:
            oldest = min(payload, key=lambda k: str(payload[k].get("written", "")))
            payload.pop(oldest)
            blob = _serialized(payload)
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(gzip.compress(blob, 6))
        os.replace(tmp, self.path)

    # · put — Store `data` under `name`. D1: a no-op (returns "") unless
    def put(self, name: str, data: bytes, meta: dict | None = None) -> str:
        """Store `data` under `name`.  D1: a no-op (returns "") unless
        MEDS_CACHE=1 is set — or the v14.7 card/span layer is running (H7:
        meds_cache/ is an allowed write target; the WARM card of §3.1
        depends on the cold card persisting its data).  A default (non-card)
        run still writes nothing."""
        if not _cache_enabled() and not _CARD_MODE:
            return ""
        payload = self._load_all()
        payload[name] = {"data_b64": base64.b64encode(bytes(data)).decode("ascii"),
                         "written": datetime.now().isoformat(timespec="seconds"),
                         **(meta or {})}
        self._write_all(payload)
        return self.path

    # · get — (bytes, meta) for a fresh, hash-verified entry, else None.
    def get(self, name: str, max_age_days: float | None = CACHE_TTL_HOURS / 24.0):
        """(bytes, meta) for a fresh, hash-verified entry, else None."""
        payload = self._load_all()
        entry = payload.get(name)
        if not isinstance(entry, dict) or "data_b64" not in entry:
            return None
        if max_age_days is not None and self._entry_age_days(entry) > max_age_days:
            return None
        try:
            data = base64.b64decode(entry["data_b64"], validate=True)
        except (ValueError, TypeError) as e:
            _emit("  " + _describe_failure("cache", f"entry={name}", exc=e,
                                          body=str(entry.get("data_b64"))[:80]))
            return None
        meta = {k: v for k, v in entry.items() if k != "data_b64"}
        meta["sha256"] = hashlib.sha256(data).hexdigest()
        return data, meta

    # ── DataFrame entries (no object deserialization — plain JSON) ───────
    # · put_frame
    def put_frame(self, name: str, df: "pd.DataFrame", meta: dict | None = None) -> str:
        if not _cache_enabled():
            return ""
        doc = self._frame_to_doc(df)
        return self.put(name, json.dumps(doc, separators=(",", ":")).encode("utf-8"), meta)

    # · get_frame
    def get_frame(self, name: str, max_age_days: float | None = CACHE_TTL_HOURS / 24.0):
        got = self.get(name, max_age_days)
        if got is None:
            return None
        try:
            doc = json.loads(got[0].decode("utf-8"))
            return self._doc_to_frame(doc), got[1]
        except (ValueError, KeyError, TypeError) as e:
            _emit("  " + _describe_failure("cache", f"entry={name}", exc=e))
            return None

    # · _frame_to_doc
    @staticmethod
    def _frame_to_doc(df: "pd.DataFrame") -> dict:
        idx = [pd.Timestamp(t).isoformat() for t in df.index]
        cols = [list(c) if isinstance(c, tuple) else [c] for c in df.columns]
        data = [[None if (v is None or (isinstance(v, float) and np.isnan(v)))
                 else (v.item() if hasattr(v, "item") else v) for v in row]
                for row in df.values]
        return {"index": idx, "columns": cols, "data": data}

    # · _doc_to_frame
    @staticmethod
    def _doc_to_frame(doc: dict) -> "pd.DataFrame":
        idx = pd.DatetimeIndex(pd.to_datetime(doc["index"]))
        cols = [tuple(c) if len(c) > 1 else c[0] for c in doc["columns"]]
        df = pd.DataFrame(doc["data"], index=idx)
        df.columns = (pd.MultiIndex.from_tuples(cols, names=["Price", "Ticker"])
                      if all(len(c) > 1 for c in doc["columns"]) else pd.Index(cols))
        return df


# ── § 7.1 · _apply_pit_lags ── v14 FIX-5 / v14.1 S1 (audit D1): publication-lag PIT approximatio…
# ══════════════════════════════════════════════════════════════════════════════
#  § 7 · PIT PUBLICATION LAGS (v14.1 audit D1)
# ══════════════════════════════════════════════════════════════════════════════
def _apply_pit_lags(raw: dict[str, pd.Series],
                    cfg: Config) -> tuple[dict[str, pd.Series], list[str]]:
    """v14 FIX-5 / v14.1 S1 (audit D1): publication-lag PIT approximation for
    the non-API tiers.  Each configured series is re-indexed at observation
    date + lag (publisher-calendar lag, see PIT_LAG_EVIDENCE), so the
    month-end resample can only ever see values that were PUBLIC by that
    month end.  v14.0 lagged only WALCL; every delayed-release series (CPI,
    core PCE, payrolls, unemployment, CFNAI, IP, housing, JOLTS, GDP, claims,
    …) previously entered in its OBSERVATION month even though its publisher
    releases it in M+1/M+2 — a look-ahead that materially moved regimes
    (audit D1).  The API tier does not need this — it replays true realtime
    vintages."""
    notes: list[str] = []
    if not cfg.pit_lag_enabled or not cfg.pit_lag_days:
        return raw, notes
    applied: list[str] = []
    for sid, lag in cfg.pit_lag_days:
        s = raw.get(sid)
        if s is None or s.empty or int(lag) <= 0:
            continue
        shifted = s.copy()
        shifted.index = shifted.index + pd.Timedelta(days=int(lag))
        raw[sid] = shifted
        applied.append(f"{sid}+{lag}d")
    if applied:
        notes.append(
            f"PIT publication lags applied ({len(applied)} delayed-release "
            f"series re-indexed to first-publication dates: "
            + ", ".join(applied)
            + "). Month-end rows now consume only values their publisher had "
              "actually released by that month end (APPROXIMATE_PIT: first-print "
              "timing respected; realtime revisions NOT replayed — that needs "
              "a FREDAPI key).")
    return raw, notes


# ── § 7.2 · _pit_fetch_floor ── v14.1 S1: the earliest OBSERVATION date the loaders must fetch so…
def _pit_fetch_floor(cfg: Config) -> pd.Timestamp:
    """v14.1 S1: the earliest OBSERVATION date the loaders must fetch so the
    publication-lag shift cannot push a series' first visible value past
    fetch_start (the shift moves dates forward, so fetching must start earlier
    by at least the largest shift).  150% of the max lag + 10d margin."""
    base = pd.Timestamp(cfg.fetch_start)
    if not cfg.pit_lag_enabled:
        return base
    max_lag = _max_pit_lag_days(cfg)
    if max_lag <= 0:
        return base
    return base - pd.Timedelta(days=int(max_lag * 1.5) + 10)

# ═══════════════════════════════════════════════════════════════════════════
#  § 8 · EASY SETTINGS — dates & data-dir helpers
# ═══════════════════════════════════════════════════════════════════════════
FETCH_START  = "1998-01-01"   # earliest data downloaded (warmup for z-scores/SMA).
                              # Keep it >= ~10 years before OUTPUT_START.
OUTPUT_START = "2008-01-01"   # first backtest / signal month
OUTPUT_END   = None           # None = today, or e.g. "2026-09-30"


# ── v14.1 S1 (audit D1): publication-lag PIT table for the non-API tiers ────
# Each lag is anchored to a real, dated release from the publisher's own
# schedule (evidence below, verified 2026-11-01).  Mechanism: the series index
# is shifted observation-date + lag, so a month-end resample row can only see
# values whose PUBLICATION had happened by that month end.  A lag is PIT-safe
# when it moves an observation out of its observation month into the month in
# which the publisher actually released it (a larger lag is merely stale, never
# look-ahead).
PIT_LAG_DAYS: tuple[tuple[str, int], ...] = (
    # weekly / next-business-day operational releases
    ("WALCL", 8),      # H.4.1: released Thursday for the week ending the prior Wednesday
    ("DFF", 2),        # effective rate finalized the next business day
    ("ICSA", 7),       # DOL: Thursday release for the week ending the prior Saturday
    ("DTWEXBGS", 5),   # H.10 on FRED: updated weekly on Monday (data through prior Friday)
    # monthly releases published during M+1
    ("CPIAUCSL", 45),  # BLS CPI: Sep-2026 released 2026-10-14 (13th-ish of M+1)
    ("PAYEMS", 40),    # BLS Employment Situation: first Friday of M+1 (Sep-2026 -> 2026-10-02)
    ("UNRATE", 40),    # same release as PAYEMS
    ("INDPRO", 45),    # FRB G.17: mid M+1 (~14th-17th)
    ("HOUST", 50),     # Census NRC: 12th workday of M+1 (Sep-2026 -> 2026-10-20)
    ("CFNAI", 55),     # Chicago Fed: toward the END of M+1 (Sep-2026 -> late Oct)
    ("PCEPILFE", 60),  # BEA Personal Income & Outlays: end of M+1 (Sep-2026 -> 2026-10-29)
    # monthly release published during M+2
    ("JTSJOL", 75),    # BLS JOLTS: ~first Tuesday of M+2 (Dec-2024 -> 2025-02-04)
    # quarterly: advance estimate ~25-28 days after quarter END
    ("A191RL1Q225SBEA", 120),  # BEA: Q3-2026 advance released 2026-10-29
    # UMCSENT (final, within the observation month) and the same-evening
    # market/operational dailies (RRPONTSYD, T5YIE, T10YIE, DGS10, T10Y2Y,
    # BAMLH0A0HYM2, BAMLC0A0CM, BAMLH0A1HYBBEY) publish fast enough that no
    # shift is required (lag 0) — see PIT_LAG_EVIDENCE.
)

PIT_LAG_EVIDENCE: dict[str, str] = {
    "WALCL": "H.4.1 release schedule: Thursdays, week ending the prior Wednesday (~8d)",
    "DFF": "FRED series notes: daily effective rate finalized next business day (~09:00 ET)",
    "ICSA": "DOL UI claims: Thursday release for week ending prior Saturday (~5d)",
    "DTWEXBGS": "FRED series page (H.10): 'Updated Oct 26, 2026 … Next Release Date: Nov 2, 2026' — weekly Monday update, data through the prior Friday",
    "CPIAUCSL": "BLS schedule: September 2026 CPI released Wednesday, October 14, 2026",
    "PAYEMS": "BLS Schedule of Releases for the Employment Situation: October 2026 reference month -> Nov 06, 2026; September 2026 -> Oct 02, 2026 (first Friday of M+1)",
    "UNRATE": "BLS Employment Situation (same release as PAYEMS), first Friday of M+1",
    "INDPRO": "FRB G.17 industrial production: released mid-month (~14th-17th) for M-1",
    "HOUST": "Census New Residential Construction: preliminary data on the 12th workday of each month (September 2026 released October 20, 2026)",
    "CFNAI": "Chicago Fed: 'The CFNAI is released at 8:30 a.m. ET on scheduled days, normally toward the end of each calendar month' — i.e. the END of the month FOLLOWING the observation month (v14.0 manifest wrongly said end of observation month; D7)",
    "PCEPILFE": "BEA Personal Income and Outlays: September 2026 released October 29, 2026; next release November 25, 2026 (end of M+1)",
    "JTSJOL": "BLS JOLTS news release archive: December 2024 results released Tuesday, February 4, 2025 (first Tuesday of M+2)",
    "A191RL1Q225SBEA": "BEA advance estimate: Q3-2026 GDP (obs 2026-07-01) released October 29, 2026, ~25-28 days after quarter end",
    "UMCSENT": "U-M Surveys of Consumers: preliminary mid-month, FINAL within the observation month (~last two business days) — lag 0 is PIT-correct for the final print",
    "RRPONTSYD": "NY Fed: same-day operational figure (~13:30 ET), not revised",
    "T5YIE": "FRED/Treasury: daily market-implied breakeven, published same day (end of day)",
    "T10YIE": "FRED/Treasury: daily market-implied breakeven, published same day (end of day)",
    "DGS10": "Treasury daily par yield curve: same day ~17:00 ET",
    "T10Y2Y": "Treasury daily par yield curve: same day (end of day)",
    "BAMLH0A0HYM2": "ICE BofA end-of-day index via FRED: published the same evening",
    "BAMLC0A0CM": "ICE BofA end-of-day index via FRED: published the same evening",
    "BAMLH0A1HYBBEY": "ICE BofA end-of-day index via FRED: published the same evening",
}


# ── § 8.1 · _max_pit_lag_days
def _max_pit_lag_days(cfg: "Config") -> int:
    return max((int(lag) for _, lag in (cfg.pit_lag_days or ())), default=0)

# ── § 8.2 · _dp ── Join a filename onto DATA_DIR.
def _dp(fname: str) -> str:
    """Join a filename onto DATA_DIR."""
    return os.path.join(DATA_DIR, fname)


# ── § 8.3 · get_freq_me
def get_freq_me() -> str:
    try:
        major, minor = pd.__version__.split(".")[:2]
        if int(major) > 2 or (int(major) == 2 and int(minor) >= 1):
            return "ME"
    except (AttributeError, ValueError):
        return "M"
    return "M"

FREQ_ME: str = get_freq_me()


# ═══════════════════════════════════════════════════════════════════════════
#  § 9 · CONFIGURATION — Config dataclass (weights/thresholds frozen, R4)
# ═══════════════════════════════════════════════════════════════════════════
# ── § 9.1 · Config
@dataclass(frozen=True)
class Config:
    fred_api_key: str = field(default_factory=_load_env_fredapi)
    # 10y of warmup (B-3): keeps the expanding credit z-score, the 60m z-score
    # window and the 10m SMA valid from the first output month (2008-01).
    fetch_start: str = FETCH_START
    output_start: str = OUTPUT_START
    output_end: str = field(default_factory=lambda: OUTPUT_END or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"))

    zscore_window: int = 60
    zscore_min_periods: int = 12
    percentile_window: int = 60
    # v14.1 S5 (audit D6): 1 -> 12.  With min_periods=1 the first rows of a
    # short panel produced degenerate percentiles (1.0, 0.5, 0.33...) that
    # the scenario scores consumed as if they were meaningful; a percentile
    # of fewer than 12 observations is noise, so those rows are now NaN and
    # the affected score terms are excluded (renormalized) instead.
    percentile_min_periods: int = 12
    roc_3m: int = 3
    credit_expanding_min_periods: int = 36

    debounce_months: int = 2
    max_regime_life: int = 60
    credit_breaker: bool = True
    min_confidence: float = 0.25
    min_margin: float = 0.02
    dominance_saturation: float = 0.35
    # v14.5 FIX-3 (part B / C10): the credit-crunch kill-switch z threshold.
    # Identical to the hard-coded 1.5 it replaces (behaviour unchanged with
    # the default) — made addressable ONLY so the PREREG C10 suite can scale
    # it +/-20% via dataclasses.replace; the frozen PREREG text is untouched.
    killswitch_credit_z: float = 1.5

    min_leverage: float = 0.5
    max_leverage: float = 2.0
    trend_sma_window: int = 10
    trend_roc_window: int = 3
    bull_pullback_lev: float = 1.25
    v_recovery_lev: float = 1.25
    bear_market_lev: float = 0.5
    cycle_peak_lev_cap: float = 1.25

    vxx_allocation: float = 0.030
    vxx_profit_take_pct: float = 0.10
    vxx_max_hold_days: int = 15
    vxx_trailing_stop_pct: float = 0.15
    vix_trigger_level: float = 25.0
    vxx_spike_pct: float = 0.15
    vxx_extreme_vix: float = 30.0
    vxx_term_structure_ratio: float = 1.15   # DEPRECATED alias (see below)
    # H-4 (v13.2): accurate name for the stress gate — it compares spot VIX
    # with its own 20-day moving average, NOT the VIX futures term structure
    # (no futures data is used anywhere). vxx_term_structure_ratio above is
    # kept as a deprecated alias for backward compatibility. Precedence:
    # if vix_spot_ma20_ratio is not None it WINS; otherwise the deprecated
    # alias is used (with a one-time DeprecationWarning when it was changed
    # from its default).
    vix_spot_ma20_ratio: float | None = None
    vxx_allowed_regimes: tuple = ("HARD_LANDING", "CREDIT_CRUNCH")

    wf_train_window: int = 60
    wf_test_window: int = 12
    wf_roll_step: int = 12
    grid_min_confidence: tuple = (0.20, 0.25, 0.30)
    grid_dominance_saturation: tuple = (0.30, 0.35, 0.40)

    fred_concurrency: int = 6
    fred_timeout: float = 45.0
    core_columns: tuple = ("CPIAUCSL", "DFF", "UNRATE", "BAMLH0A0HYM2")

    # v13.1 H-1 history guard (FRED truncated the ICE BofA series to 3 years).
    # Each guard series must start on/before
    #   max(fetch_start, output_start - credit_expanding_min_periods months)
    #   + history_tolerance_days,
    # otherwise ensure_history() tries data/<SERIES>_full.csv, then stops.
    history_guard_series: tuple = ("BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLH0A1HYBBEY")
    # E-1 (v13.2): a MANDATORY guard series that is absent from the fetched
    # data, or too short without a CSV repair, aborts the run; an OPTIONAL
    # one is skipped with an explicit note. Both sets must be contained in
    # history_guard_series.
    history_guard_mandatory: tuple = ("BAMLH0A0HYM2", "BAMLC0A0CM")
    history_guard_optional: tuple = ("BAMLH0A1HYBBEY",)
    history_tolerance_days: int = 45
    history_csv_dir: str = field(default_factory=lambda: DATA_DIR)
    history_overlap_tol: float = 0.10      # max median |CSV - FRED| on overlap (percent)
    # v14.6.2 STEP A (USER-REQUESTED behaviour change): what to do when the
    # ICE BofA OAS history (BAMLH0A0HYM2 + BAMLC0A0CM) is NOT usable — FRED
    # serves only a rolling ~3y window of both on the free tier and no
    # data/<SID>_full.csv repair is present.
    #   "auto"     run WITHOUT the credit signal: both series dropped from
    #              the panel, CREDIT_CRUNCH + EARLY_CYCLE_RE_ACCELERATION
    #              excluded (never silently renormalised), credit kill-switch
    #              OFF, PREREG BLOCKED — loud yellow banner; results are
    #              explicitly NOT comparable to credit-ON runs.
    #   "required" v14.6.1 behaviour exactly: NO-GO (exit 2).
    # CLI: --require-credit sets "required".
    credit_mode: str = "auto"
    # per-run state, set ONLY by resolve_credit_mode via dataclasses.replace
    # (never a user default): "ON" | "OFF" for THIS run, and the scenario
    # keys that are not selectable in this run.
    credit_signal: str = "ON"
    excluded_scenarios: tuple = ()
    # v13.1 H-2 PIT sanity: if the PIT collapse keeps < this share of the
    # distinct observation dates, fall back to obs date + lag.
    pit_min_retained: float = 0.80
    pit_fallback_lag_days: int = 45        # monthly series; weekly uses 7, quarterly 90
    # v14 FIX-5 / v14.1 S1 (audit D1): publication-lag PIT approximation,
    # applied on the non-API tiers (the API tier replays true vintages).
    # Default ON, with a per-series lag for EVERY delayed-release series
    # (publisher-calendar evidence in PIT_LAG_EVIDENCE).
    pit_lag_enabled: bool = True
    pit_lag_days: tuple = PIT_LAG_DAYS

    cost_bps_per_trade: float = 10.0

    # ── v13 RISK OVERLAYS (each one can be switched off for A/B testing) ─────
    # R-1 crash guard: if SPY's last COMPLETED month returned below
    # crash_guard_1m_ret, next month's leverage cap is cut even when the
    # 10m SMA is still rising (fast-crash de-risking, one month earlier).
    crash_guard: bool = True
    crash_guard_1m_ret: float = -0.08
    # R-2 drawdown throttle on the STRATEGY equity curve (not SPY): leverage
    # scales linearly from 1.0x at dd_throttle_start down to dd_throttle_floor
    # at dd_throttle_full, and recovers as the equity curve recovers.
    dd_throttle: bool = True
    dd_throttle_start: float = 0.12
    dd_throttle_full: float = 0.30
    dd_throttle_floor: float = 0.50
    # R-3 defensive regimes never run gross leverage above this cap.
    defensive_lev_cap: float = 1.00
    defensive_regimes: tuple = ("HARD_LANDING", "CREDIT_CRUNCH", "STAGFLATIONARY_DRAG")
    # R-4 financing & borrow costs.
    charge_financing: bool = True
    financing_flat_annual: float = 0.043   # fallback when DFF is unavailable
    financing_spread: float = 0.006        # broker spread over the policy rate
    short_borrow_bps_annual: float = 100.0 # charged on short notional
    vxx_cost_bps: float = 20.0             # round-trip cost per VXX trade

CFG: Config = Config()


# ── § 9.2 · MedsValidationError ── v13.2 J-1: a refusal-to-run condition (data guard failed, valid…
class MedsValidationError(RuntimeError):
    """v13.2 J-1: a refusal-to-run condition (data guard failed, validation
    failed, NO-GO). Subclasses RuntimeError so every existing caller that
    catches RuntimeError keeps working; the CLI maps it to exit code 2."""


# ═══════════════════════════════════════════════════════════════════════════
#  § 10 · INDICATORS & SCORING
# ═══════════════════════════════════════════════════════════════════════════
# ── § 10.1 · IndicatorSpec
@dataclass(frozen=True)
class IndicatorSpec:
    series_id: str
    name: str
    units: str
    category: str
    is_real_time: bool = False

INDICATORS: list[IndicatorSpec] = [
    IndicatorSpec("RRPONTSYD", "Overnight Reverse Repo", "lin", "liquidity", is_real_time=True),
    IndicatorSpec("WALCL", "Fed Balance Sheet", "lin", "liquidity", is_real_time=True),
    IndicatorSpec("DFF", "Fed Funds Rate", "lin", "liquidity", is_real_time=True),
    IndicatorSpec("CPIAUCSL", "CPI (YoY)", "pc1", "inflation"),
    IndicatorSpec("PCEPILFE", "Core PCE (YoY)", "pc1", "inflation"),
    IndicatorSpec("T5YIE", "5Y Breakeven", "lin", "inflation", is_real_time=True),
    IndicatorSpec("T10YIE", "10Y Breakeven", "lin", "inflation", is_real_time=True),
    IndicatorSpec("A191RL1Q225SBEA", "Real GDP Growth", "lin", "growth"),
    IndicatorSpec("CFNAI", "Chicago Fed Nat'l Activity", "lin", "growth"),
    IndicatorSpec("INDPRO", "Industrial Production", "pc1", "growth"),
    IndicatorSpec("HOUST", "Housing Starts", "lin", "growth"),
    IndicatorSpec("UMCSENT", "Consumer Sentiment", "lin", "growth"),
    IndicatorSpec("PAYEMS", "Nonfarm Payrolls", "chg", "employment"),
    IndicatorSpec("UNRATE", "Unemployment Rate", "lin", "employment"),
    IndicatorSpec("ICSA", "Initial Jobless Claims", "lin", "employment"),
    IndicatorSpec("JTSJOL", "Job Openings", "lin", "employment"),
    IndicatorSpec("BAMLH0A0HYM2", "HY OAS Spread", "lin", "credit", is_real_time=True),
    IndicatorSpec("BAMLC0A0CM", "IG OAS Spread", "lin", "credit", is_real_time=True),
    IndicatorSpec("BAMLH0A1HYBBEY", "BB Bond Yield", "lin", "credit", is_real_time=True),
    IndicatorSpec("DGS10", "10Y Treasury Yield", "lin", "credit", is_real_time=True),
    IndicatorSpec("T10Y2Y", "10Y-2Y Yield Curve", "lin", "credit", is_real_time=True),
    IndicatorSpec("DTWEXBGS", "Trade-Weighted USD", "lin", "fx", is_real_time=True),
]

DERIVED_SERIES: dict[str, Callable[[pd.DataFrame], pd.Series]] = {
    "REAL10Y": lambda df: df["DGS10"] - df["T10YIE"],
}

# ── § 10.2 · _score_gt
def _score_gt(val: float, target: float, soft_target: float = 0.0) -> float:
    if pd.isna(val): return np.nan
    if val >= target: return 1.0
    if val <= soft_target: return 0.0
    return (val - soft_target) / (target - soft_target)

# ── § 10.3 · _score_lt
def _score_lt(val: float, target: float, soft_target: float = 1.0) -> float:
    if pd.isna(val): return np.nan
    if val <= target: return 1.0
    if val >= soft_target: return 0.0
    return (soft_target - val) / (soft_target - target)

# ── § 10.4 · _score_abs_lt
def _score_abs_lt(val: float, target: float, soft_target: float) -> float:
    if pd.isna(val): return np.nan
    abs_val = abs(val)
    if abs_val <= target: return 1.0
    if abs_val >= soft_target: return 0.0
    return (soft_target - abs_val) / (soft_target - target)

# ── § 10.5 · safe_weighted_score
def safe_weighted_score_detail(terms: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """v14.7 4b: safe_weighted_score PLUS the retained-weight fraction —
    the share of the ORIGINAL weight mass that actually scored (1.0 =
    nothing missing).  The score half is computed by the exact same
    renormalization safe_weighted_score always used, so delegating to this
    function changes NO score; the fraction is warning/display-only
    (§3.4: <70% retained → warnings entry, score unchanged)."""
    all_w = sum(w for w, _ in terms)
    valid = [(w, s) for w, s in terms if not pd.isna(s)]
    if not valid or all_w == 0:
        return np.nan, 0.0
    total_w = sum(w for w, _ in valid)
    if total_w == 0:
        return np.nan, (total_w / all_w)
    return sum(w * s for w, s in valid) / total_w, (total_w / all_w)


# v14.7 4b: when armed (a list), every safe_weighted_score call appends its
# retained fraction — the ONLY hook the layer needs to read a scenario's
# retained weight without touching the frozen SCENARIOS lambdas.  Disarmed
# (None) in all normal paths, so the cost is one None-check per call.
_SCORE_RETAINED_BUF: list | None = None


# ── § 10.5.2 · safe_weighted_score — the score half (recorder-observed).
def safe_weighted_score(terms: Sequence[tuple[float, float]]) -> float:
    score, retained = safe_weighted_score_detail(terms)
    if _SCORE_RETAINED_BUF is not None:
        _SCORE_RETAINED_BUF.append(retained)
    return score


# ── § 10.5.1 · _scenario_retained_weight — v14.7 4b: warning-path reader.
def _scenario_retained_weight(row: pd.Series, scenario_key: str,
                              cfg: Config = CFG) -> float | None:
    """v14.7 4b: the retained-weight fraction a scenario's score would
    renormalize over on THIS row (1.0 = every term scored, None = scenario
    unknown or its lambda raised).  Arms the safe_weighted_score recorder,
    re-evaluates the PURE score lambda once, disarms.  §3.4 contract: this
    feeds WARNINGS only — scores are never taken from here."""
    sc = next((s for s in _scenarios_for(cfg) if s.key == scenario_key), None)
    if sc is None or sc.score is None:
        return None
    buf: list[float] = []
    global _SCORE_RETAINED_BUF
    _SCORE_RETAINED_BUF = buf
    try:
        sc.score(row)
    except Exception:
        return None
    finally:
        _SCORE_RETAINED_BUF = None
    return buf[0] if buf else None

# ── § 10.6 · conviction_leverage_v2 ── v13.2 D-1: THE authoritative conviction-leverage formula (u…
def conviction_leverage_v2(dominance: float, regime_acc: float, regime_months: int, cfg: Config = CFG) -> float:
    """v13.2 D-1: THE authoritative conviction-leverage formula (unchanged
    from v13.1). NOTE the convention: the result is the GROSS exposure
    multiplier the backtester applies (sum of |weights|), which is what the
    financing charge (borrowed = conv_lev - 1) assumes."""
    if pd.isna(dominance): dominance = 0.0
    if pd.isna(regime_acc): regime_acc = 0.5
    margin_score = min(1.0, dominance / cfg.dominance_saturation) if cfg.dominance_saturation > 0 else 0.0
    blended = 0.6 * margin_score + 0.4 * regime_acc
    base_lev = cfg.min_leverage + (cfg.max_leverage - cfg.min_leverage) * blended
    stability_mult = 0.8 if regime_months < 2 else (0.9 if regime_months < 3 else 1.0)
    final_lev = base_lev * stability_mult
    return round(max(cfg.min_leverage, min(cfg.max_leverage, final_lev)), 3)


_DEFAULT_VXX_TERM_STRUCTURE_RATIO = 1.15   # default of the deprecated alias
_VIX_ALIAS_WARNED = False


# ── § 10.7 · resolve_vix_spot_ma20_ratio ── H-4 (v13.2): resolve the VIX-vs-its-20d-MA stress thre…
def resolve_vix_spot_ma20_ratio(cfg: Config = CFG) -> float:
    """H-4 (v13.2): resolve the VIX-vs-its-20d-MA stress threshold.

    Precedence: cfg.vix_spot_ma20_ratio (new, accurate name) wins whenever
    it is not None; otherwise the deprecated cfg.vxx_term_structure_ratio
    is honored (with a one-time DeprecationWarning if it was changed from
    its default, so existing configurations keep working).
    """
    global _VIX_ALIAS_WARNED
    if cfg.vix_spot_ma20_ratio is not None:
        return float(cfg.vix_spot_ma20_ratio)
    if cfg.vxx_term_structure_ratio != _DEFAULT_VXX_TERM_STRUCTURE_RATIO and not _VIX_ALIAS_WARNED:
        warnings.warn(
            "Config.vxx_term_structure_ratio is deprecated: the gate it feeds "
            "compares spot VIX with its own 20-day moving average, not the VIX "
            "futures term structure. Use Config.vix_spot_ma20_ratio (which wins "
            "when both are set).",
            DeprecationWarning, stacklevel=2)
        _VIX_ALIAS_WARNED = True
    return float(cfg.vxx_term_structure_ratio)


# ═══════════════════════════════════════════════════════════════════════════
#  § 11 · SCENARIO TAXONOMY — 7 scenarios + Neutral
# ═══════════════════════════════════════════════════════════════════════════
# ── § 11.1 · ScenarioSpec
@dataclass(frozen=True)
class ScenarioSpec:
    key: str
    name: str
    regime: str
    cycle_phase: str
    emoji: str
    diagnosis: str
    score: Callable[[pd.Series], float]
    long: list[str]
    short: list[str]
    priority: int

SCENARIOS: list[ScenarioSpec] = [
    ScenarioSpec(
        key="CREDIT_CRUNCH", name="Credit Crunch & Liquidity Squeeze", regime="RESTRICTIVE",
        cycle_phase="Crisis", emoji="🚨", priority=1,
        diagnosis="HY & IG spreads blowing out to historic highs; liquidity draining; yields spiking.",
        score=lambda r: safe_weighted_score([
            (0.4, _score_gt(r.get("BAMLH0A0HYM2_lvl_pct", np.nan), 0.70, 0.45)),
            (0.3, _score_gt(r.get("BAMLC0A0CM_lvl_pct", np.nan), 0.65, 0.45)),
            (0.3, _score_gt(r.get("BAMLH0A0HYM2_diff3m", np.nan), 0.8, 0.0)),
        ]),
        long=["Long Treasuries (TLT)", "T-Bills / Cash (BIL)", "Utilities (XLU)", "Consumer Staples (XLP)"],
        short=[],
    ),
    ScenarioSpec(
        key="INFLATION_SHOCK", name="Inflation Shock / Hawkish Pivot", regime="RESTRICTIVE",
        cycle_phase="Mid-Late Cycle", emoji="🔥", priority=2,
        diagnosis="Inflation accelerating rapidly; Fed actively hiking; RRP liquidity draining.",
        score=lambda r: safe_weighted_score([
            (0.35, _score_gt(r.get("CPIAUCSL_diff3m", np.nan), 0.5, 0.0)),
            (0.25, _score_gt(r.get("PCEPILFE_diff3m", np.nan), 0.3, 0.0)),
            (0.20, _score_gt(r.get("DFF_diff3m", np.nan), 0.5, 0.0)),
            (0.20, _score_lt(r.get("RRPONTSYD_lvl_z", np.nan), -0.5, 0.0)),
        ]),
        long=["Energy (XLE)", "Commodities (DBC)", "T-Bills (BIL)"],
        short=["Long Treasuries (TLT)"],
    ),
    ScenarioSpec(
        key="LATE_CYCLE_OVERHEATING", name="Late-Cycle Overheating", regime="RESTRICTIVE",
        cycle_phase="Late Cycle", emoji="🌡️", priority=3,
        diagnosis="High growth + sticky high inflation + tight labor + inverted yield curve.",
        score=lambda r: safe_weighted_score([
            (0.3, _score_gt(r.get("CFNAI", np.nan), 0.5, 0.0)),
            (0.3, _score_gt(r.get("CPIAUCSL_lvl_pct", np.nan), 0.65, 0.45)),
            (0.2, _score_lt(r.get("UNRATE_lvl_pct", np.nan), 0.35, 0.55)),
            (0.2, _score_lt(r.get("T10Y2Y_lvl_z", np.nan), -0.5, -0.2)),
        ]),
        long=["Energy (XLE)", "S&P 500 (SPY)", "T-Bills (BIL)"],
        short=["Long Treasuries (TLT)"],
    ),
    ScenarioSpec(
        key="STAGFLATIONARY_DRAG", name="Stagflationary Drag", regime="RESTRICTIVE",
        cycle_phase="Late Cycle", emoji="💀", priority=4,
        diagnosis="Growth decelerating + sticky high inflation + real yields rising.",
        score=lambda r: safe_weighted_score([
            (0.4, _score_lt(r.get("CFNAI", np.nan), -0.2, 0.0)),
            (0.3, _score_gt(r.get("CPIAUCSL_lvl_pct", np.nan), 0.65, 0.50)),
            (0.3, _score_gt(r.get("REAL10Y_diff3m", np.nan), 0.2, -0.3)),
        ]),
        long=["T-Bills (BIL)", "Long Treasuries (TLT)", "Energy (XLE)"],
        short=[],
    ),
    ScenarioSpec(
        key="HARD_LANDING", name="Hard Landing / Recessionary Contraction", regime="CONTRACTIONARY",
        cycle_phase="Recession", emoji="📉", priority=5,
        diagnosis="Negative growth momentum + unemployment surging + CPI cooling fast.",
        score=lambda r: safe_weighted_score([
            (0.4, _score_lt(r.get("CFNAI", np.nan), -0.3, 0.0)),
            (0.4, _score_gt(r.get("UNRATE_diff3m", np.nan), 0.15, 0.0)),
            (0.2, _score_lt(r.get("CPIAUCSL_diff3m", np.nan), -0.3, 0.0)),
        ]),
        long=["Long Treasuries (TLT)", "T-Bills (BIL)", "Utilities (XLU)", "Consumer Staples (XLP)"],
        short=[],
    ),
    ScenarioSpec(
        key="SOFT_LANDING_PIVOT", name="Soft Landing / Policy Pivot", regime="EXPANSIONARY",
        cycle_phase="Mid Cycle", emoji="🪂", priority=6,
        diagnosis="Growth stabilizing; inflation returning to target; Fed easing/pausing.",
        score=lambda r: safe_weighted_score([
            (0.3, _score_abs_lt(r.get("CFNAI", np.nan), 0.3, 1.0)),
            (0.3, _score_lt(r.get("CPIAUCSL_lvl_pct", np.nan), 0.60, 0.80)),
            (0.2, _score_lt(r.get("CPIAUCSL_diff3m", np.nan), 0.0, 0.6)),
            (0.2, _score_lt(r.get("DFF_diff3m", np.nan), 0.0, 0.6)),
        ]),
        long=["S&P 500 (SPY)", "Nasdaq (QQQ)", "Consumer Discretionary (XLY)"],
        short=[],
    ),
    ScenarioSpec(
        key="EARLY_CYCLE_RE_ACCELERATION", name="Early-Cycle Re-acceleration", regime="EXPANSIONARY",
        cycle_phase="Early Cycle", emoji="🌱", priority=7,
        diagnosis="Growth momentum turning positive from low levels; easy financial conditions.",
        score=lambda r: safe_weighted_score([
            (0.4, _score_gt(r.get("CFNAI_diff3m", np.nan), 0.0, -0.5)),
            (0.2, _score_lt(r.get("CFNAI_lvl_pct", np.nan), 0.50, 0.70)),
            (0.4, _score_lt(r.get("BAMLH0A0HYM2_diff3m", np.nan), 0.0, 0.5)),
        ]),
        long=["Nasdaq (QQQ)", "Industrials (XLI)", "Consumer Discretionary (XLY)", "S&P 500 (SPY)"],
        short=[],
    ),
    ScenarioSpec(
        key="NEUTRAL_WAIT_AND_SEE", name="Neutral / Wait-and-See (Market Gridlock)", regime="NEUTRAL",
        cycle_phase="Indeterminate", emoji="🟡", priority=99,
        diagnosis="Conflicting indicator momentum; flat rates-of-change across growth/inflation.",
        score=lambda r: 1.0,
        long=["S&P 500 (SPY)", "Nasdaq (QQQ)", "Ultra-Short T-Bills (SGOV/BIL)"],
        short=[],
    ),
]

_SCENARIO_LOOKUP: dict[str, ScenarioSpec] = {s.key: s for s in SCENARIOS}
_CLASSES: list[str] = [s.key for s in sorted(SCENARIOS, key=lambda x: x.priority)]
_CLASS_IDX: dict[str, int] = {k: i for i, k in enumerate(_CLASSES)}


# ── § 11.2 · _scenarios_for ── v14.6.2 STEP A: the scenarios selectable in THIS run.
def _scenarios_for(cfg: Config) -> list[ScenarioSpec]:
    """v14.6.2 STEP A: the scenarios selectable in THIS run.

    A credit-OFF run (cfg.excluded_scenarios, set by resolve_credit_mode via
    _credit_off_cfg) excludes CREDIT_CRUNCH (every score term is a credit
    feature) and EARLY_CYCLE_RE_ACCELERATION (40% of its weight sits on
    BAMLH0A0HYM2_diff3m): safe_weighted_score renormalises over the
    surviving terms, which would silently shift 0.4 of the weight onto the
    other two — excluded loudly instead, never silently renormalised.
    With credit ON (the default) this is exactly SCENARIOS."""
    ex = set(getattr(cfg, "excluded_scenarios", ()) or ())
    return [s for s in SCENARIOS if s.key not in ex]


# ═══════════════════════════════════════════════════════════════════════════
#  § 12 · FRED CLIENT & FEATURE ENGINE — pure URL builders (v14.4 §4)
# ═══════════════════════════════════════════════════════════════════════════
# ── § 12.1 · _build_fred_obs_url ── v14.4 section 4: PURE FRED API URL construction (no network in…
def _build_fred_obs_url(series_id: str, api_key: str, *,
                         observation_start: str, observation_end: str,
                         units: str = "lin",
                         realtime_start: str | None = None,
                         realtime_end: str | None = None,
                         base_url: str | None = None) -> str:
    """v14.4 section 4: PURE FRED API URL construction (no network inside).
    Parameter names and allowed `units` values verified against
    https://fred.stlouisfed.org/docs/api/fred/series_observations.html:
    series_id, api_key, file_type, observation_start, observation_end, units
    (lin|chg|ch1|pch|pc1|pca|cch|cca|log), realtime_start, realtime_end,
    limit (default/max 100000), offset, sort_order, output_type 1-4.
    v14.6.1 BUG 6: FRED answers a non-'lin' units value with HTTP 400
    ("If output_type is '1' and units is not 'lin', then realtime_start
    must equal realtime_end or vintage_dates may set only 1 date.") unless
    the request pins ONE vintage, so the builder REFUSES to construct such
    a URL — the bug class dies here, offline, before any network."""
    if units != "lin" and realtime_start != realtime_end:
        raise ValueError(
            f"_build_fred_obs_url: units={units!r} needs a SINGLE vintage — "
            f"FRED rejects non-'lin' units with a realtime range (HTTP 400: "
            f"\"If output_type is '1' and units is not 'lin', then "
            f"realtime_start must equal realtime_end or vintage_dates may "
            f"set only 1 date.\"). Fetch levels (units='lin') and apply the "
            f"transform locally per release date with "
            f"_apply_fred_units_vintage (§13.2b). "
            f"(realtime_start={realtime_start!r}, realtime_end={realtime_end!r})")
    params = {"series_id": series_id, "api_key": api_key,
              "observation_start": observation_start,
              "observation_end": observation_end,
              "units": units, "file_type": "json"}
    if realtime_start is not None:
        params["realtime_start"] = realtime_start
    if realtime_end is not None:
        params["realtime_end"] = realtime_end
    return (base_url or FREDClient.BASE_URL) + "?" + urllib.parse.urlencode(params)


# ── § 12.2 · _build_public_csv_url ── v14.4 section 4: PURE fredgraph.csv URL construction (no net…
def _build_public_csv_url(series_id: str, cosd: str, coed: str,
                          base_url: str | None = None) -> str:
    """v14.4 section 4: PURE fredgraph.csv URL construction (no network).
    This is a website export, not a documented API; the header the loader
    requires is `observation_date` (confirmed by the genuine dumps in
    snapshot/fred/*.csv). Multi-id batching was NOT verified, so the
    unkeyed tier keeps one request per series at the conservative pace."""
    return (f"{base_url or FREDClient.PUBLIC_CSV_URL}"
            f"?id={series_id}&cosd={cosd}&coed={coed}")


# ── § 12.3 · FREDClient
class FREDClient:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    PUBLIC_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"

    # · __init__
    def __init__(self, api_key: str, cfg: Config = CFG) -> None:
        self.api_key = api_key
        self.cfg = cfg
        self._sem = asyncio.Semaphore(cfg.fred_concurrency)
        self._timeout = cfg.fred_timeout
        self.last_failures: list[str] = []   # B-1: series that came back empty
        self.pit_fallbacks: list[str] = []   # H-2: series that needed the lag fallback
        # v13.3 M-1: which tier actually served the data ("api" | "public-csv"
        # | "snapshot") and a human-readable caveat for non-API tiers.
        self.source_mode: str = ""
        self.source_note: str = ""
        # v13.3 M-1: why a tier was skipped (printed by main_async so a bare
        # run never sits silently through a dead network).
        self.tier_failure_notes: list[str] = []
        self._public_errors: list[str] = []
        # v14 FIX-1: local-pc1 vs FRED-pc1 cross-check results (API tier).
        self.pc1_check_notes: list[str] = []
        # v14.4 section 3: per-series REAL failure texts (series_id ->
        # _describe_failure output) for everything that did not come back.
        self.fetch_failures: dict[str, str] = {}

    # · _collapse_vintage_pit — L-1 FIX: point-in-time collapse of FRED realtime obse…
    @staticmethod
    def _collapse_vintage_pit(obs: list[dict]) -> pd.Series:
        """L-1 FIX: point-in-time collapse of FRED realtime observations.

        Returns a Series indexed by the date each value became PUBLIC
        (realtime_start). At each index date the value is the reading of the
        latest observation (by observation date) released on or before that
        date; among equal observation dates the later release wins.

        Downstream, resample('ME').last().ffill() turns this into "the reading
        known at the end of each month" — exactly the information set available
        when the engine decides next month's trade. An observation for month M
        that is first released inside M+1 (CPI, UNRATE, CFNAI, core PCE) can
        therefore never appear in row M, and revisions only enter the panel in
        the month they were actually published.
        """
        rows = []
        for o in obs:
            v = o.get("value")
            if v in (".", None, ""): continue
            try:
                rows.append({"date": pd.Timestamp(o["date"]),
                             "rt": pd.Timestamp(o["realtime_start"]),
                             "value": float(v)})
            except (ValueError, KeyError): continue
        if not rows: return pd.Series(dtype=float, name="dummy")

        # Walk releases in publication order; track the current reading.
        df = pd.DataFrame(rows).sort_values(["rt", "date"], kind="stable")
        out_idx, out_val = [], []
        cur_date = None
        for rt, date, value in zip(df["rt"], df["date"], df["value"]):
            if cur_date is None or date >= cur_date:
                cur_date = date
                out_idx.append(rt)
                out_val.append(value)
            # releases for observations OLDER than the current reading cannot
            # change what the series' latest published value is -> ignored
        s = pd.Series(out_val, index=pd.DatetimeIndex(out_idx, name="date"))
        s = s[~s.index.duplicated(keep="last")]
        return s.sort_index()

    # · _pit_sanity — H-2: detect a degenerate PIT collapse (bulk-loaded vintages).
    def _pit_sanity(self, obs: list[dict], s: pd.Series, sid: str) -> pd.Series:
        """H-2: detect a degenerate PIT collapse (bulk-loaded vintages).

        Normally the collapse keeps ~1 row per observation date. If it keeps
        far fewer, many observations share one realtime_start (history loaded
        in bulk), so the series would silently lose its history. Fallback:
        index each observation (latest value) at obs date + a conservative
        publication lag. Revisions are not replayed in this mode, so it is a
        slightly leaky-on-revisions but never lookahead-on-first-print proxy.
        """
        dates = {o["date"] for o in obs if o.get("value") not in (".", None, "")}
        n = len(dates)
        if n < 24 or len(s) >= self.cfg.pit_min_retained * n:
            return s
        rows = []
        for o in obs:
            v = o.get("value")
            if v in (".", None, ""): continue
            try:
                rows.append((pd.Timestamp(o["date"]), pd.Timestamp(o["realtime_start"]), float(v)))
            except (ValueError, KeyError): continue
        if not rows: return s
        df = (pd.DataFrame(rows, columns=["date", "rt", "value"])
                .sort_values(["date", "rt"]).drop_duplicates("date", keep="last"))
        gap = df["date"].diff().dt.days.median()
        lag = 7 if gap <= 8 else (self.cfg.pit_fallback_lag_days if gap <= 35 else 90)
        out = pd.Series(df["value"].values,
                        index=pd.DatetimeIndex(df["date"] + pd.Timedelta(days=lag), name="date"),
                        name=sid).sort_index()
        out = out[~out.index.duplicated(keep="last")]
        self.pit_fallbacks.append(
            f"{sid}: PIT collapse kept {len(s)} of {n} observations (bulk-loaded vintages); "
            f"using observation date + {lag}d lag instead.")
        return out

    # · _fetch_obs_json_sync — v14.4 section 3: one FRED API GET via urllib (standard…
    def _fetch_obs_json_sync(self, url: str, series_id: str = "",
                             window: str = "",
                             pacer: "_Pacer | None" = None) -> tuple[list[dict], str | None]:
        """v14.4 section 3: one FRED API GET via urllib (standard library
        only).  Retries up to 4 times with Retry-After-aware backoff on 429
        and 5xx; every failure is described by _describe_failure with the
        REAL status+reason or exception, the verbatim upstream body (FRED's
        own error_code / error_message), the attempt counter and elapsed
        seconds.  The API key appears only inside the request URL and is
        redacted from every recorded message (R8).  Returns
        (observations, failure_text_or_None)."""
        attempts = 4
        req = urllib.request.Request(url)   # v14.7 Step 8: default UA (middlebox-safe)
        request_desc = f"series={series_id}  window={window}"
        last_failure: str | None = None
        for attempt in range(1, attempts + 1):
            if pacer is not None:
                pacer.wait()
            t0 = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as r:
                    raw = r.read().decode("utf-8", errors="replace")
                    elapsed = time.monotonic() - t0
                    try:
                        payload = json.loads(raw)
                    except ValueError as e:
                        failure = _describe_failure(
                            "FRED API", request_desc, url=url, exc=e, body=raw,
                            attempt=attempt, attempts=attempts, elapsed=elapsed)
                        _emit("  " + failure)
                        return [], failure
                    if not isinstance(payload, dict) or "observations" not in payload:
                        failure = _describe_failure(
                            "FRED API", request_desc, url=url, body=raw,
                            attempt=attempt, attempts=attempts, elapsed=elapsed)
                        _emit("  " + failure)
                        return [], failure
                    return payload.get("observations", []), None
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read().decode("utf-8", errors="replace")
                except (OSError, ValueError):
                    body = ""
                elapsed = time.monotonic() - t0
                failure = _describe_failure(
                    "FRED API", request_desc, url=url, http=e, body=body,
                    attempt=attempt, attempts=attempts, elapsed=elapsed)
                _emit("  " + failure)
                last_failure = failure
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    delay = float(retry_after) if retry_after else 2.0 ** (attempt - 1)
                except (TypeError, ValueError):
                    delay = 2.0 ** (attempt - 1)
                if e.code in (429, 500, 502, 503, 504) and attempt < attempts:
                    time.sleep(max(0.0, delay))
                    continue
                return [], failure
            except OSError as e:            # URLError, timeouts, connection resets
                elapsed = time.monotonic() - t0
                failure = _describe_failure(
                    "FRED API", request_desc, url=url, exc=e,
                    attempt=attempt, attempts=attempts, elapsed=elapsed)
                _emit("  " + failure)
                last_failure = failure
                if attempt < attempts:
                    time.sleep(2.0 ** (attempt - 1))
                    continue
                return [], failure
        if last_failure is None:            # unreachable, kept for honesty
            last_failure = _describe_failure(
                "FRED API", request_desc, url=url,
                body="all attempts exhausted without a response",
                attempt=attempts, attempts=attempts)
            _emit("  " + last_failure)
        return [], last_failure

    # · _vintage_warmup_start — v14.6.1 BUG 6: the earliest observation (and realtime) …
    def _vintage_warmup_start(self) -> str:
        """v14.6.1 BUG 6: the earliest observation (and realtime) date for a
        locally transformed (pc1/chg) vintage fetch — the SAME warmup the
        public CSV tier uses (_fetch_one_public): 14 months before
        fetch_start (one month of slack over the 12 the year-ago pc1 needs)
        or the PIT-lag floor, whichever is earlier.  Both tiers then cover
        the same window and the first in-window release has its year-ago
        level inside the fetched rows."""
        return min(pd.Timestamp(self.cfg.fetch_start) - pd.DateOffset(months=14),
                   _pit_fetch_floor(self.cfg)).strftime("%Y-%m-%d")

    # · _fetch_obs_json — v13.2 G-1: raw FRED observations (WITH realtime metadata) f…
    async def _fetch_obs_json(self, spec: IndicatorSpec,
                              units_override: str | None = None,
                              realtime_pin: str | None = None) -> list[dict]:
        """v13.2 G-1: raw FRED observations (WITH realtime metadata) for a
        series — shared by _fetch_one, the pc1 cross-check and the
        vintage-revision audit.
        v14.4 S1: the keyed tier shares ONE pacer capped at 100 requests per
        minute (FRED documents 120; see _Pacer).
        v14.6.1 BUG 6: a realtime RANGE can only ever ask for LEVELS — FRED
        answers non-'lin' units with HTTP 400 unless ONE vintage is pinned —
        so pc1/chg specs are fetched as lin and transformed locally per
        release date (§13.2b).  realtime_pin, when set, requests that ONE
        vintage (realtime_start == realtime_end == pin), the only mode in
        which FRED still serves its own units=pc1; the pc1 cross-check uses
        it for both of its requests.  Non-real-time specs that will be
        transformed locally also fetch the 14-month warmup
        (_vintage_warmup_start) so the year-ago level is in the rows.
        units_override is honoured only where non-lin units are legal
        (pinned / real-time requests); on a range it must be 'lin' or the
        URL builder fails fast."""
        warm = (not spec.is_real_time) and spec.units != "lin"
        if realtime_pin is not None:
            units = units_override or spec.units
            rt_start = rt_end = realtime_pin
            obs_start = self._vintage_warmup_start() if warm else self.cfg.fetch_start
        elif spec.is_real_time:
            units = units_override or spec.units
            rt_start = rt_end = None
            obs_start = self.cfg.fetch_start
        else:
            units = units_override or "lin"      # BUG 6: a range ⇒ levels only
            obs_start = rt_start = (self._vintage_warmup_start() if warm
                                    else self.cfg.fetch_start)
            rt_end = self.cfg.output_end
        url = _build_fred_obs_url(
            spec.series_id, self.api_key,
            observation_start=obs_start,
            observation_end=self.cfg.output_end,
            units=units,
            realtime_start=rt_start, realtime_end=rt_end)
        window = f"{obs_start}..{self.cfg.output_end}"
        async with self._sem:
            obs, failure = await asyncio.to_thread(
                self._fetch_obs_json_sync, url, spec.series_id, window, _API_PACER)
        if failure is not None and obs == []:
            self.fetch_failures[spec.series_id] = failure
        return obs

    # · _verify_pc1_replication — v14 FIX-1: with an API key, cross-check the local p…
    async def _verify_pc1_replication(self, specs: list[IndicatorSpec]) -> None:
        """v14 FIX-1: with an API key, cross-check the local pc1 replication
        (levels + _apply_fred_units) against FRED's own units=pc1 output on
        the overlap and record a warning when they differ.
        v14.6.1 BUG 6: FRED's own units=pc1 is only served for ONE vintage,
        so BOTH requests pin realtime_start == realtime_end ==
        cfg.output_end (the latest available date); the local pc1 is
        computed from the pinned lin levels with the same per-release code
        (_apply_fred_units_vintage, §13.2b) at that same single vintage —
        every lin row's release date is rewritten to the pin first, so the
        transform uses exactly the information set FRED served for the
        pin.  The one-line cross-check result is unchanged."""
        pin = self.cfg.output_end
        for spec in specs:
            if spec.units != "pc1":
                continue
            try:
                api = await self._fetch_obs_json(spec, units_override="pc1",
                                                 realtime_pin=pin)
                lin = await self._fetch_obs_json(spec, units_override="lin",
                                                 realtime_pin=pin)
            except OSError as e:
                # v14.4 section 3: a swallowed verification error is a bug —
                # record the real cause and skip THIS check only.
                self.pc1_check_notes.append(
                    f"pc1 replication check: {spec.series_id} skipped — "
                    + _describe_failure("FRED API", f"series={spec.series_id}", exc=e))
                continue
            if not api or not lin:
                continue
            # FRED's own pc1 at the pinned vintage: obs date -> value
            a = {}
            for o in api:
                if o.get("value") not in (".", None, ""):
                    try:
                        a[o["date"]] = float(o["value"])
                    except (ValueError, KeyError, TypeError):
                        continue
            # local pc1 at the SAME vintage: pin every lin row's release
            # date, then run the per-release transform (one information set)
            rows = [{"date": o.get("date"), "realtime_start": pin,
                     "value": o.get("value")}
                    for o in lin if o.get("value") not in (".", None, "")]
            local = {r["date"]: r["value"]
                     for r in _apply_fred_units_vintage(rows, "pc1")}
            common = sorted(set(a) & set(local))
            if len(common) < 6:
                continue
            diff = float(np.median([abs(a[d] - local[d]) for d in common]))
            if diff > 0.05:
                self.pc1_check_notes.append(
                    f"pc1 replication check: {spec.series_id} local YoY DIFFERS "
                    f"from FRED units=pc1 by median {diff:.3f} on "
                    f"{len(common)} overlapping dates")
            else:
                self.pc1_check_notes.append(
                    f"pc1 replication check: {spec.series_id} matches FRED "
                    f"units=pc1 (median abs diff {diff:.4f} over "
                    f"{len(common)} dates)")

    # · _fetch_one
    async def _fetch_one(self, spec: IndicatorSpec) -> pd.Series:
        obs = await self._fetch_obs_json(spec)
        if not obs:
            return pd.Series(dtype=float, name=spec.series_id)

        if not spec.is_real_time:
            # v14.6.1 BUG 6: the range fetch brought LEVELS; pc1/chg are
            # applied per RELEASE date (§13.2b) BEFORE the PIT collapse so
            # every vintage's reading is computed only from levels already
            # public at that release.  units='lin' series skip this and
            # behave exactly as before.
            if spec.units != "lin":
                obs = _apply_fred_units_vintage(obs, spec.units)
                if not obs:
                    return pd.Series(dtype=float, name=spec.series_id)
                pit = self._collapse_vintage_pit(obs).rename(spec.series_id)
                out = self._pit_sanity(obs, pit, spec.series_id)
                # the warmup rows (releases dated before fetch_start) are
                # only the pc1/chg look-back history — keep the served
                # window starting at fetch_start, exactly as
                # observation_start=fetch_start did before the fix
                out = out.loc[out.index >= pd.Timestamp(self.cfg.fetch_start)]
                return (out.rename(spec.series_id) if not out.empty
                        else pd.Series(dtype=float, name=spec.series_id))
            pit = self._collapse_vintage_pit(obs).rename(spec.series_id)
            return self._pit_sanity(obs, pit, spec.series_id)

        dates, vals = [], []
        for o in obs:
            v = o.get("value")
            if v in (".", None, ""): continue
            try:
                dates.append(pd.Timestamp(o["date"]))
                vals.append(float(v))
            except (ValueError, KeyError): continue
        if not dates:
            return pd.Series(dtype=float, name=spec.series_id)
        return pd.Series(vals, index=pd.DatetimeIndex(dates, name="date"),
                         name=spec.series_id, dtype=float)

    # · fetch_all — v13.3 M-1: three-tier data source, tried in order:
    async def fetch_all(self, specs: list[IndicatorSpec]) -> dict[str, pd.Series]:
        """v13.3 M-1: three-tier data source, tried in order:

          api         FREDAPI is set and the API answered — strict point-in-
                      time vintages (the only tier with realtime metadata);
          public-csv  FRED's public fredgraph.csv endpoint, no key needed —
                      genuine FRED data at the CURRENT vintage (revisions
                      applied; no realtime replay); pc1/chg replicated
                      locally per the FRED API docs;
          snapshot    the frozen genuine inputs in snapshot/fred/*.csv
                      (hashes in snapshot/hashes.json) — fully offline.

        The tier that served the run is recorded in self.source_mode and
        self.source_note so callers can print an honest caveat.
        """
        self.pit_fallbacks = []
        self.last_failures = []
        self.source_mode, self.source_note = "", ""
        self.tier_failure_notes, self._public_errors = [], []

        # ── Tier 3 (forced): --snapshot / MEDS_FORCE_SNAPSHOT=1 ────────────
        if FORCE_SNAPSHOT:
            raw = self._load_snapshot_series(specs)
            self.last_failures = [s.series_id for s in specs if s.series_id not in raw]
            if raw:
                self.source_mode = "snapshot"
                self.source_note = self._snapshot_note(raw)
            return raw

        # ── Tier 0 (card paths only): fresh verified card cache ──────────
        # v14.7 §3.1: now()/span() prefer the fredcard/ entries the cold
        # card wrote (final series, no unit re-transform).  Complete hit
        # only — a single missing series falls through to the live tiers.
        if _CARD_MODE:
            raw = self._load_card_series(specs)
            if raw and len(raw) == len(specs):
                self.source_mode = "cache"
                self.source_note = ("verified card cache meds_cache/fredcard/ "
                                    "(fresh, SHA-256 checked, written by an "
                                    "earlier card run) — no network call")
                self.last_failures = []
                return raw

        # ── Tier 1: FRED API (only meaningful with a key) ──────────────────
        if self.api_key:
            tasks = [self._fetch_one(s) for s in specs]
            results = await asyncio.gather(*tasks)
            raw = {s.series_id: r for s, r in zip(specs, results) if not r.empty}
            if raw:
                self.source_mode = "api"
                # B-1: remember what failed so callers can refuse to run on a
                # silently re-weighted score instead of discovering it later.
                self.last_failures = [s.series_id for s, r in zip(specs, results) if r.empty]
                await self._verify_pc1_replication(specs)
                if _CARD_MODE:
                    _card_cache_write_series(raw)   # v14.7: warm next card
                return raw
            # key set but nothing came back (bad key / network): fall through
            # v14.4 section 3: the tier note carries the REAL per-series
            # causes (formatter output), never generic advice.
            # v14.7 Step 8: the card layer gets a one-line, human-readable
            # warning too (the public tier is about to serve the data — the
            # run continues, but the user must know the key did not work).
            _diag().price_notes.append(
                "FRED API key present but the API tier returned no data "
                "(wrong key or rate limit) — continuing on the public tier; "
                "verify with --check-endpoints")
            causes = "; ".join(
                f"{sid}: {text.splitlines()[0]}"
                for sid, text in sorted(self.fetch_failures.items()))[:600]
            self.tier_failure_notes.append(
                "FRED API tier (key present) returned no data for any series; "
                f"per-series causes: {causes or 'no observations in the window'}; "
                "trying the public CSV tier")

        # ── Tier 2: public fredgraph.csv — no key needed ──────────────────
        if await self._public_tier_alive():
            raw = await self.fetch_all_public(specs)
            if raw:
                self.source_mode = "public-csv"
                self.source_note = ("FRED public fredgraph.csv (no API key) — "
                                    "genuine data at the CURRENT vintage; realtime "
                                    "revisions are not replayed (that needs a key)")
                self.last_failures = [s.series_id for s in specs if s.series_id not in raw]
                return raw
            first_err = self._public_errors[0] if self._public_errors else "no usable rows"
            self.tier_failure_notes.append(
                f"public fredgraph.csv reachable but returned no usable series "
                f"(first error: {first_err})")
        else:
            # FIX-4 (v14.5): the probe's real, already-redacted cause travels
            # with the tier note (main run, _mrs detail, ticker_score dict).
            probe_cause = (self._public_errors[0] if self._public_errors
                           else "no recorded cause")
            self.tier_failure_notes.append(
                "public fredgraph.csv unreachable (probe failed) — tier skipped"
                f" — cause: {' · '.join(probe_cause.splitlines())}")

        # ── Tier 2b: verified meds_cache/ (offline, SHA-256-checked) ─────
        raw = self._load_cache_series(specs)
        if raw:
            self.source_mode = "cache"
            self.source_note = (f"verified download cache {CACHE_DIR} (SHA-256 "
                                f"manifest; written by an earlier online run) - "
                                f"current vintage, offline")
            self.last_failures = [s.series_id for s in specs if s.series_id not in raw]
            return raw

        # ── Tier 3: frozen snapshot ──────────────────────────────────────
        raw = self._load_snapshot_series(specs)
        if raw:
            self.source_mode = "snapshot"
            self.source_note = self._snapshot_note(raw)
            self.last_failures = [s.series_id for s in specs if s.series_id not in raw]
            return raw

        self.last_failures = [s.series_id for s in specs]
        return {}

    # · _public_csv_sync — (body, error): one fredgraph.csv fetch via urllib. urllib…
    def _public_csv_sync(self, sid: str, cosd: str, coed: str,
                         timeout: float) -> tuple[str, str | None]:
        """(body, error): one fredgraph.csv fetch via urllib. urllib is used
        deliberately — some corporate/sandbox middleboxes stall httpx's
        connection pattern to fred.stlouisfed.org while passing urllib's.
        v14.4 section 3: the error text is the FULL _describe_failure output
        (status AND reason phrase, exception class and message, URL, body) —
        never just the status code."""
        url = _build_public_csv_url(sid, cosd, coed)
        # v14.7 Step 8: NO custom User-Agent — some egress proxies/middleboxes
        # stall any non-standard UA on fred.stlouisfed.org while passing
        # urllib's default.  FRED does not require an identifying UA.
        req = urllib.request.Request(url)
        request_desc = f"series={sid}  window={cosd}..{coed}"
        attempts = 2
        last_err: str | None = None
        for attempt in range(1, attempts + 1):
            t0 = time.monotonic()
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    body = r.read().decode("utf-8", errors="replace")
                    # v14.4 section 3: a 200 body that is NOT a fredgraph.csv
                    # (no observation_date header) is a FAILURE with its first
                    # 200 characters — never silently empty data.
                    if "observation_date" not in body:
                        return "", _describe_failure(
                            "FRED public CSV", request_desc, url=url,
                            body=f"status 200 but the body is not a fredgraph.csv "
                                 f"(no observation_date header): {body[:200]}",
                            attempt=attempt, attempts=attempts,
                            elapsed=time.monotonic() - t0)
                    return body, None
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8", errors="replace")
                except (OSError, ValueError):
                    err_body = ""
                last_err = _describe_failure(
                    "FRED public CSV", request_desc, url=url, http=e, body=err_body,
                    attempt=attempt, attempts=attempts,
                    elapsed=time.monotonic() - t0)
                # v14.7 Step 8: 429/5xx get a Retry-After-aware backoff before
                # the retry (the API tier has always done this).
                if e.code in (429, 500, 502, 503, 504) and attempt < attempts:
                    ra = e.headers.get("Retry-After") if e.headers else None
                    time.sleep(min(30.0, float(ra)) if ra and str(ra).isdigit()
                               else 1.5 * attempt)
            except OSError as e:            # URLError, timeouts, connection resets
                last_err = _describe_failure(
                    "FRED public CSV", request_desc, url=url, exc=e,
                    attempt=attempt, attempts=attempts,
                    elapsed=time.monotonic() - t0)
        return "", last_err

    # · _public_tier_alive — v13.3 M-1: 8-second reachability probe (one tiny DFF req…
    async def _public_tier_alive(self) -> bool:
        """v13.3 M-1: 8-second reachability probe (one tiny DFF request) so a
        dead network degrades to the snapshot tier in seconds instead of
        waiting for 22 series timeouts.  v14.4 section 3: a 200 reply whose
        body is not CSV (no observation_date header) is recorded with its
        first 200 characters instead of looking like empty data."""
        cosd = (datetime.now() - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        coed = datetime.now().strftime("%Y-%m-%d")
        body, err = await asyncio.to_thread(self._public_csv_sync, "DFF", cosd, coed, 8.0)
        if err is not None:
            self._public_errors.append(err)
            return False
        if "observation_date" not in body:
            self._public_errors.append(_describe_failure(
                "FRED public CSV", f"series=DFF  window={cosd}..{coed}",
                url=_build_public_csv_url("DFF", cosd, coed),
                body="status 200 but the body is not a fredgraph.csv "
                     f"(no observation_date header): {body[:200]}"))
            return False
        return True

    # · _fetch_one_public — v13.3 M-1 (tier 2): one series via FRED's public CSV endp…
    async def _fetch_one_public(self, spec: IndicatorSpec) -> pd.Series:
        """v13.3 M-1 (tier 2): one series via FRED's public CSV endpoint.

        fredgraph.csv serves LEVELS only, so the API's documented pc1/chg
        transformations are replicated locally. The request asks for two
        extra months before fetch_start so the first requested observation
        has a defined transformation; the result is then sliced to
        [fetch_start, output_end] exactly like the API's
        observation_start/observation_end parameters would have done.
        """
        empty = pd.Series(dtype=float, name=spec.series_id)
        # v14 FIX-1: >= 13 months of extra history so the year-ago pc1 is
        # defined at fetch_start (14 gives one month of slack).  v14.1 S1:
        # also cover the max publication lag so the PIT shift keeps the
        # window covered (14 months > 190d, so the existing warmup already
        # suffices for the default lag table — the min() keeps it explicit).
        cosd = min(pd.Timestamp(self.cfg.fetch_start) - pd.DateOffset(months=14),
                   _pit_fetch_floor(self.cfg)).strftime("%Y-%m-%d")
        url = _build_public_csv_url(spec.series_id, cosd, self.cfg.output_end)
        async with self._sem:
            await asyncio.sleep(0.15)     # stay polite to the public endpoint
            body, err = await asyncio.to_thread(
                self._public_csv_sync, spec.series_id, cosd, self.cfg.output_end,
                min(self._timeout, 30.0))
        if err is not None:
            self._public_errors.append(f"{spec.series_id}: {err}")
            self.fetch_failures[spec.series_id] = err
            return empty
        # v14.4 section 3: a 200 body that is not CSV is a FAILURE, not empty
        # data — print its first 200 characters.
        if "observation_date" not in body:
            failure = _describe_failure(
                "FRED public CSV", f"series={spec.series_id}", url=url,
                body="status 200 but the body is not a fredgraph.csv "
                     f"(no observation_date header): {body[:200]}")
            self._public_errors.append(f"{spec.series_id}: {failure}")
            self.fetch_failures[spec.series_id] = failure
            _emit("  " + failure)
            return empty
        try:
            s = _parse_fred_csv(pd.read_csv(io.StringIO(body)), spec.series_id)
        except (ValueError, OSError) as e:      # pandas parse errors
            failure = _describe_failure(
                "FRED public CSV", f"series={spec.series_id}", url=url, exc=e,
                body=body[:300])
            self._public_errors.append(f"{spec.series_id}: {failure}")
            self.fetch_failures[spec.series_id] = failure
            _emit("  " + failure)
            return empty
        if s.empty:
            failure = _describe_failure(
                "FRED public CSV", f"series={spec.series_id}", url=url,
                body="status 200, CSV header present, but zero usable rows")
            self._public_errors.append(f"{spec.series_id}: {failure}")
            self.fetch_failures[spec.series_id] = failure
            _emit("  " + failure)
            return empty
        # v14 FIX-3 → v14.4 D1: the verified cache is written ONLY when
        # MEDS_CACHE=1 is set; a write failure is recorded, never swallowed.
        try:
            VerifiedCache().put(f"fred/{spec.series_id}.csv", body.encode("utf-8"))
        except OSError as e:
            _emit("  " + _describe_failure("cache", f"entry=fred/{spec.series_id}.csv",
                                          exc=e))
        s = _apply_fred_units(s, spec.units)
        s = s.loc[(s.index >= pd.Timestamp(self.cfg.fetch_start)) &
                  (s.index <= pd.Timestamp(self.cfg.output_end))]
        return s.rename(spec.series_id) if not s.empty else empty

    # · fetch_all_public — v13.3 M-1 (tier 2): all series via the public fredgraph.cs…
    async def fetch_all_public(self, specs: list[IndicatorSpec]) -> dict[str, pd.Series]:
        """v13.3 M-1 (tier 2): all series via the public fredgraph.csv."""
        self._public_errors = []
        tasks = [self._fetch_one_public(s) for s in specs]
        results = await asyncio.gather(*tasks)
        raw = {s.series_id: r for s, r in zip(specs, results) if not r.empty}
        if _CARD_MODE and raw:
            _card_cache_write_series(raw)       # v14.7: warm next card
        return raw

    # · _load_card_series — v14.7 §3.1 (tier 0, card paths): final series
    def _load_card_series(self, specs: list[IndicatorSpec]) -> dict[str, pd.Series]:
        """v14.7 §3.1 (card tier 0): the FINAL series a previous card run
        served, from fredcard/<SID>.csv in the verified cache (fresh-only,
        hash-checked on load).  Unlike _load_cache_series these values are
        ALREADY pc1/chg-transformed, so no unit transform is applied —
        exactly what the card wrote.  Sliced to the caller's window."""
        out: dict[str, pd.Series] = {}
        lo = min(pd.Timestamp(self.cfg.fetch_start), _pit_fetch_floor(self.cfg))
        hi = pd.Timestamp(self.cfg.output_end)
        for spec in specs:
            got = VerifiedCache().get(f"fredcard/{spec.series_id}.csv")
            if got is None:
                continue
            body, _meta = got
            try:
                # dtype=str + Python float(): the value column mixes '.' and
                # repr-precision floats, so read_csv would parse the numeric
                # tokens with its (up to 1-ulp lossy) C parser — Python's
                # float() on the repr string is the ONLY bit-exact read.
                df = pd.read_csv(io.StringIO(
                    body.decode("utf-8", errors="replace")), dtype=str)
                if df.shape[1] < 2:
                    continue
                idx = pd.to_datetime(df[df.columns[0]], errors="coerce")
                col = df[df.columns[1]]
                vals = [np.nan if (v is None or v.strip() in (".", ""))
                        else float(v) for v in col]
                # NaN-PRESERVING parse (unlike _parse_fred_csv): the '.'
                # warmup rows keep their dates so positional rolling
                # windows match a fresh fetch exactly.
                s = pd.Series(vals, index=pd.DatetimeIndex(idx), dtype=float)
                s = s[s.index.notna()]
                s = s[~s.index.duplicated(keep="last")].sort_index().rename(spec.series_id)
            except (ValueError, OSError) as e:
                _emit("  " + _describe_failure(
                    "cache", f"entry=fredcard/{spec.series_id}.csv", exc=e))
                continue
            if s.empty:
                continue
            s = s.loc[(s.index >= lo) & (s.index <= hi)]
            if not s.empty:
                out[spec.series_id] = s.rename(spec.series_id)
        return out

    # · _load_snapshot_series — v13.3 M-1 (tier 3): frozen fredgraph.csv dumps at
    def _load_snapshot_series(self, specs: list[IndicatorSpec]) -> dict[str, pd.Series]:
        """v13.3 M-1 (tier 3): frozen fredgraph.csv dumps at
        <snapshot>/fred/<SID>.csv — same layout, same unit replication and
        same window slice as tier 2, but fully offline.  v14.1 S1: the slice
        starts at the PIT fetch floor (fetch_start minus the max publication
        lag) so the lag shift cannot push first visible values past the
        window."""
        d = _snapshot_dir()
        if not d:
            return {}
        out: dict[str, pd.Series] = {}
        lo = min(pd.Timestamp(self.cfg.fetch_start), _pit_fetch_floor(self.cfg))
        hi = pd.Timestamp(self.cfg.output_end)
        for spec in specs:
            path = os.path.join(d, "fred", f"{spec.series_id}.csv")
            if not os.path.isfile(path):
                continue
            try:
                s = _parse_fred_csv(pd.read_csv(path), spec.series_id)
            except (ValueError, OSError) as e:
                # v14.4 section 3: the real parse error, recorded not swallowed
                _emit("  " + _describe_failure("local file", f"file={path}", exc=e))
                continue
            if s.empty:
                continue
            s = _apply_fred_units(s, spec.units)
            s = s.loc[(s.index >= lo) & (s.index <= hi)]
            if not s.empty:
                out[spec.series_id] = s.rename(spec.series_id)
        return out

    # · _load_cache_series — v14 FIX-3 (tier 2b): series served from the verified med…
    def _load_cache_series(self, specs: list[IndicatorSpec]) -> dict[str, pd.Series]:
        """v14 FIX-3 (tier 2b): series served from the verified meds_cache/
        written by an earlier online run - same layout, same unit replication
        and same window slice as tier 2, but fully offline and hash-checked
        on every load."""
        out: dict[str, pd.Series] = {}
        lo = min(pd.Timestamp(self.cfg.fetch_start), _pit_fetch_floor(self.cfg))
        hi = pd.Timestamp(self.cfg.output_end)
        for spec in specs:
            got = VerifiedCache().get(f"fred/{spec.series_id}.csv")
            if got is None:
                continue
            body, _meta = got
            try:
                s = _parse_fred_csv(pd.read_csv(
                    io.StringIO(body.decode("utf-8", errors="replace"))),
                    spec.series_id)
            except (ValueError, OSError) as e:
                _emit("  " + _describe_failure("cache",
                                              f"entry=fred/{spec.series_id}.csv",
                                              exc=e))
                continue
            if s.empty:
                continue
            s = _apply_fred_units(s, spec.units)
            s = s.loc[(s.index >= lo) & (s.index <= hi)]
            if not s.empty:
                out[spec.series_id] = s.rename(spec.series_id)
        return out

    # · _snapshot_note
    @staticmethod
    def _snapshot_note(raw: dict[str, pd.Series]) -> str:
        d = _snapshot_dir() or "snapshot"
        starts = [pd.Timestamp(s.index.min()) for s in raw.values()]
        ends = [pd.Timestamp(s.index.max()) for s in raw.values()]
        cov = f"{min(starts).date()}..{max(ends).date()}" if starts else "?"
        return (f"frozen snapshot {d} (genuine FRED fredgraph.csv + yfinance "
                f"inputs; SHA-256 hashes in snapshot/hashes.json) — current "
                f"vintage, realtime revisions not replayed; coverage {cov}")


# ── § 12.4 · assert_core_series ── B-1: raise if any core series was not served (the scenario scor…
def assert_core_series(raw: dict[str, pd.Series], cfg: Config = CFG,
                       failures: dict[str, str] | None = None) -> None:
    """B-1: raise if any core series was not served (the scenario scores
    renormalize over whatever is present, so a missing core series silently
    changes the regime definition).

    v14.4 section 3: the message carries the REAL per-series cause from
    _describe_failure (passed by callers that own a FREDClient) — the facts,
    never generic advice."""
    # v14 FIX-4: BAMLC0A0CM is MANDATORY for the run as a whole (guard
    # series) even though only core_columns gate feature-row existence.
    # v14.6.2 STEP A: NOT mandatory in a credit-OFF run — both credit series
    # were dropped from the panel by resolve_credit_mode (and removed from
    # core_columns via the derived per-run Config), so demanding one here
    # would contradict the OFF decision.  CPIAUCSL / DFF / UNRATE and every
    # other core series stay mandatory in OFF runs exactly as before.
    _credit_off = getattr(cfg, "credit_signal", "ON") == "OFF"
    mandatory = tuple(cfg.core_columns) + (() if _credit_off else ("BAMLC0A0CM",))
    missing = [c for c in mandatory if c not in raw or raw[c].empty]
    if missing:
        parts = [f"core series not served by any tier: {missing}; "
                 f"refusing to score on a silently re-weighted panel."]
        for sid in missing:
            cause = (failures or {}).get(sid)
            if cause:
                parts.append(f"{sid} cause:\n{cause}")
            else:
                parts.append(f"{sid} cause: no observations in the requested "
                             f"window {cfg.fetch_start}..{cfg.output_end}")
        raise RuntimeError("\n".join(parts))


# ── § 12.5 · _load_history_csv ── Read data/<sid>_full.csv (or <sid>.csv): date in col 1, value in…
def _load_history_csv(sid: str, cfg: Config) -> tuple[pd.Series | None, str]:
    """Read data/<sid>_full.csv (or <sid>.csv): date in col 1, value in col 2."""
    for name in (f"{sid}_full.csv", f"{sid}.csv"):
        path = os.path.join(cfg.history_csv_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            df = pd.read_csv(path)
        except (ValueError, OSError) as e:
            raise RuntimeError(f"Could not read {path}: {e}")
        if df.shape[1] < 2:
            raise RuntimeError(f"{path} needs 2 columns (date, value); found {df.shape[1]}.")
        vcol = sid if sid in df.columns else df.columns[1]
        idx = pd.to_datetime(df[df.columns[0]], errors="coerce")
        vals = pd.to_numeric(df[vcol], errors="coerce")
        s = pd.Series(vals.values, index=pd.DatetimeIndex(idx)).dropna()
        s = s[s.index.notna()]
        s = s[~s.index.duplicated(keep="last")].sort_index().astype(float)
        s.name = sid
        if s.empty:
            raise RuntimeError(f"{path} contained no usable rows.")
        return s, path
    return None, ""


# ── § 12.6 · ensure_history ── H-1 / v13.2 E-1: make sure the guard series reach far enough back…
def ensure_history(raw: dict[str, pd.Series], cfg: Config = CFG) -> tuple[dict[str, pd.Series], list[str]]:
    """H-1 / v13.2 E-1: make sure the guard series reach far enough back, or
    stop loudly.

    Returns (possibly repaired raw dict, notes). Raises RuntimeError listing
    every MANDATORY series that is missing or still too short.

    v13.2 E-1: every guard series is classified explicitly —
      * mandatory (default BAMLH0A0HYM2, BAMLC0A0CM: the kill switch and the
        CREDIT_CRUNCH score consume them): absent or unrepaired -> error;
      * optional (default BAMLH0A1HYBBEY: not consumed by any scenario
        score): absent or unrepaired -> explicit note, never a silent skip.
    """
    mandatory = set(cfg.history_guard_mandatory)
    optional = set(cfg.history_guard_optional)
    unknown = (mandatory | optional) - set(cfg.history_guard_series)
    if unknown:
        raise MedsValidationError(
            f"history_guard_mandatory/optional contain series that are not in "
            f"history_guard_series: {sorted(unknown)}")

    need = max(pd.Timestamp(cfg.fetch_start),
               pd.Timestamp(cfg.output_start) - pd.DateOffset(months=cfg.credit_expanding_min_periods))
    need = need + pd.Timedelta(days=cfg.history_tolerance_days)
    out, notes, problems = dict(raw), [], []

    for sid in cfg.history_guard_series:
        is_mandatory = sid in mandatory
        s = out.get(sid)
        if s is None or s.empty:
            # E-1 (v13.2): v13.1 silently skipped absent guard series.
            if is_mandatory:
                problems.append(
                    f"{sid}: MANDATORY guard series is missing from the fetched data. "
                    f"Its absence would silently re-weight the credit signal; refusing to run. "
                    f"Check the FRED fetch, or supply history via "
                    f"{os.path.join(cfg.history_csv_dir, sid + '_full.csv')}.")
            else:
                notes.append(f"{sid}: optional guard series absent — skipped explicitly "
                             f"(not consumed by any scenario score).")
            continue
        # v14.6.2 STEP A: the per-series judgement (CSV repair, overlap
        # check, exact v14.6.1 wording) lives in ONE place so the
        # credit-mode resolver (§12.6b) runs the SAME dry-run decision.
        r = _repair_history_series(sid, s, need, cfg, is_mandatory)
        if r["note"] is not None:
            notes.append(r["note"])
        if r["problem"] is not None:
            problems.append(r["problem"])
        if r["repaired"]:
            out[sid] = r["series"]

    if problems:
        raise RuntimeError("History check failed (refusing to run on a truncated credit signal):\n  - "
                           + "\n  - ".join(problems))
    return out, notes


# ── § 12.6a · _repair_history_series ── v14.6.2 STEP A: the per-series guard judgement.
def _repair_history_series(sid: str, s: pd.Series, need: pd.Timestamp,
                           cfg: Config, is_mandatory: bool) -> dict:
    """v14.6.2 STEP A: the per-series body of the ensure_history loop (the
    data/<SID>_full.csv repair with the existing overlap check), factored
    out UNCHANGED so resolve_credit_mode (§12.6b) can run the exact same
    judgement as a dry run before deciding the run's credit mode.

    `s` must be non-empty.  Returns a dict:
      series    the Series to keep — the repaired/merged one on success,
                the ORIGINAL otherwise (only stored when repaired=True);
      repaired  True only when a CSV repair actually extended the series;
      note      the informational line for the run log (None when silent);
      problem   the error line when the series does NOT reach `need`
                (None when it does, or when it does not but is optional —
                for optional series the same fact is delivered via `note`).
    """
    first = s.index.min()
    if first <= need:
        return {"series": s, "repaired": False, "note": None, "problem": None}
    csv_path = os.path.join(cfg.history_csv_dir, f"{sid}_full.csv")
    csv, found = _load_history_csv(sid, cfg)
    if csv is None:
        if is_mandatory:
            return {"series": s, "repaired": False, "note": None, "problem":
                    f"{sid}: FRED history starts {first.date()} but must start on/before "
                    f"{need.date()}. Provide the full history as {csv_path} "
                    f"(date,value in percent; FRED CSV layout is fine)."}
        return {"series": s, "repaired": False, "note":
                f"{sid}: optional guard series starts {first.date()} (needs "
                f"{need.date()}) and no {csv_path} was found — left as-is, "
                f"skipped explicitly (not consumed by any scenario score).",
                "problem": None}
    ov = csv.index.intersection(s.index)
    csv_bad = False
    msg = ""
    if len(ov) >= 20:
        d = float((csv.loc[ov] - s.loc[ov]).abs().median())
        if d > cfg.history_overlap_tol:
            msg = (f"{sid}: {found} disagrees with FRED on {len(ov)} overlapping dates "
                   f"(median abs diff {d:.3f}). Wrong series or units (need percent, not bp)?")
            csv_bad = True
    else:
        m_csv, m_fred = float(csv.median()), float(s.median())
        if m_fred > 0 and not (0.2 <= m_csv / m_fred <= 5.0):
            msg = (f"{sid}: {found} has no usable overlap with FRED and its level "
                   f"(median {m_csv:.2f}) is far from FRED's ({m_fred:.2f}). Units?")
            csv_bad = True
    if csv_bad:
        if is_mandatory:
            return {"series": s, "repaired": False, "note": None, "problem": msg}
        return {"series": s, "repaired": False,
                "note": msg + " (optional series — not merged, run continues)",
                "problem": None}
    older = csv[csv.index < first]
    merged = pd.concat([older, s]).sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    merged.name = sid
    if merged.index.min() > need:
        if is_mandatory:
            return {"series": s, "repaired": False, "note": None, "problem":
                    f"{sid}: even with {found} history starts {merged.index.min().date()}; "
                    f"need on/before {need.date()}."}
        return {"series": s, "repaired": False, "note":
                f"{sid}: even with {found} history starts "
                f"{merged.index.min().date()} (need {need.date()}) — optional, "
                f"not merged.", "problem": None}
    note = (f"{sid}: FRED started {first.date()}; prepended {len(older)} obs from {found} "
            f"(now from {merged.index.min().date()}).")
    if len(older) and (first - older.index.max()).days > 100:
        note += f" WARNING: {(first - older.index.max()).days}-day gap between CSV end and FRED start."
    return {"series": merged, "repaired": True, "note": note, "problem": None}


# ── § 12.6b · credit-mode constants ── v14.6.2 STEP A: the both-or-neither credit decision.
CREDIT_MODE_SERIES: tuple = ("BAMLH0A0HYM2", "BAMLC0A0CM")   # both or neither
_CREDIT_OFF_DROPS: tuple = ("BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLH0A1HYBBEY")
_CREDIT_EXCLUDED_SCENARIOS: tuple = ("CREDIT_CRUNCH", "EARLY_CYCLE_RE_ACCELERATION")


# ── § 12.6c · _credit_need_date ── v14.6.2 STEP A: the `need` date, ONE definition.
def _credit_need_date(cfg: Config) -> pd.Timestamp:
    """v14.6.2 STEP A: the `need` date ensure_history computes — ONE
    definition, so the resolver and the guard can never drift apart."""
    need = max(pd.Timestamp(cfg.fetch_start),
               pd.Timestamp(cfg.output_start) - pd.DateOffset(months=cfg.credit_expanding_min_periods))
    return need + pd.Timedelta(days=cfg.history_tolerance_days)


# ── § 12.6d · resolve_credit_mode ── v14.6.2 STEP A: is the ICE BofA OAS credit signal usable?
def resolve_credit_mode(raw: dict[str, pd.Series], cfg: Config = CFG
                        ) -> tuple[dict[str, pd.Series], dict]:
    """v14.6.2 STEP A (user-requested): decide ONCE per run whether the ICE
    BofA OAS credit signal is USABLE, before assert_core_series /
    ensure_history get a say.

    USABLE = BOTH BAMLH0A0HYM2 and BAMLC0A0CM reach back to the `need` date
    ensure_history computes — straight from the FRED tiers, or repaired by
    data/<SID>_full.csv with the existing overlap check (the SAME
    _repair_history_series judgement, run as a dry run).

    Returns (raw, info):
      * USABLE, or credit_mode == "required": raw is returned UNCHANGED and
        info["credit"] == "ON" — the v14.6.1 path is byte-identical (the CSV
        repair, its notes and its NO-GO all still happen inside
        ensure_history; "required" + unusable raises there exactly as
        before).
      * NOT usable + credit_mode == "auto": info["credit"] == "OFF" and raw
        comes back with BOTH credit series (and BAMLH0A1HYBBEY if present)
        removed entirely, so a 3-year fragment can NEVER produce partial
        _lvl_pct/_diff3m/_lvl_z_expanding features.  Never decided
        per-series: both or neither.  The caller derives the per-run Config
        with _credit_off_cfg (mandatory sets without the credit series,
        CREDIT_CRUNCH + EARLY_CYCLE_RE_ACCELERATION excluded) and prints the
        loud banner from info["banner"].
    """
    need = _credit_need_date(cfg)
    starts: dict[str, str | None] = {}
    problems: list[str] = []
    usable = True
    for sid in CREDIT_MODE_SERIES:
        s = raw.get(sid)
        if s is None or s.empty:
            starts[sid] = None
            usable = False
            continue
        r = _repair_history_series(sid, s, need, cfg, is_mandatory=True)
        starts[sid] = str(pd.Timestamp(r["series"].index.min()).date())
        if r["problem"] is not None:
            usable = False
            problems.append(r["problem"])
    mode = getattr(cfg, "credit_mode", "auto")
    if usable or mode == "required":
        return raw, {"mode": mode, "credit": "ON", "usable": True,
                     "need": str(need.date()), "starts": starts,
                     "excluded": (), "dropped": (), "reason": None,
                     "banner": [], "warning": None, "problems": []}
    # OFF (auto mode only): both-or-neither — the LATER first-observation is
    # the binding one; an absent series is called out by name.
    present = [pd.Timestamp(starts[sid]) for sid in CREDIT_MODE_SERIES
               if starts[sid] is not None]
    start_label = (str(max(present).date()) if present
                   else "absent (neither series served)")
    if any(starts[sid] is None for sid in CREDIT_MODE_SERIES):
        start_label += (" — " + ", ".join(
            f"{sid} absent" for sid in CREDIT_MODE_SERIES if starts[sid] is None))
    dropped = tuple(sid for sid in _CREDIT_OFF_DROPS if sid in raw)
    reason = (f"ICE BofA OAS history not available on FRED free tier "
              f"(starts {start_label}, needs {need.date()})")
    banner = [
        f"⚠ CREDIT SIGNAL OFF - {reason}.",
        "Excluded: CREDIT_CRUNCH, EARLY_CYCLE_RE_ACCELERATION; credit "
        "kill-switch OFF. Results are NOT comparable to credit-ON runs.",
        "Why excluded: CREDIT_CRUNCH scores only on the two OAS series; "
        "EARLY_CYCLE_RE_ACCELERATION carries 40% of its weight on "
        "BAMLH0A0HYM2_diff3m — a silent renormalisation onto the remaining "
        "60% would shift the regime definition, so the scenario loses its "
        "seat instead. The soft-landing fallback also needs HY-OAS easing "
        "evidence (BAMLH0A0HYM2_diff3m < 0) and therefore cannot fire.",
    ]
    warning = (f"credit signal OFF: {reason} — CREDIT_CRUNCH, "
               f"EARLY_CYCLE_RE_ACCELERATION excluded, credit kill-switch "
               f"OFF; results are NOT comparable to credit-ON runs.")
    out = {k: v for k, v in raw.items() if k not in _CREDIT_OFF_DROPS}
    return out, {"mode": mode, "credit": "OFF", "usable": False,
                 "need": str(need.date()), "starts": starts,
                 "excluded": _CREDIT_EXCLUDED_SCENARIOS, "dropped": dropped,
                 "reason": reason, "banner": banner, "warning": warning,
                 "problems": problems}


# ── § 12.6e · _credit_off_cfg ── v14.6.2 STEP A: the per-run Config of a credit-OFF run.
def _credit_off_cfg(cfg: Config) -> Config:
    """v14.6.2 STEP A: the per-run Config for a credit-OFF run: the two
    credit series leave every mandatory set (core_columns, the history
    guards) and the two credit-dependent scenarios are excluded from
    selection.  NOTHING else moves — no weight, band, threshold, PREREG or
    default is retuned (R1)."""
    return replace(cfg,
                   core_columns=tuple(c for c in cfg.core_columns
                                      if c not in CREDIT_MODE_SERIES),
                   history_guard_series=(),
                   history_guard_mandatory=(),
                   history_guard_optional=(),
                   excluded_scenarios=_CREDIT_EXCLUDED_SCENARIOS,
                   credit_signal="OFF")


# ═══════════════════════════════════════════════════════════════════════════
#  § 13 · OFFLINE TIERS — public fredgraph.csv & frozen snapshot
# ═══════════════════════════════════════════════════════════════════════════
# ── § 13.1 · _snapshot_dir ── v13.3 M-1: locate the frozen snapshot directory.
def _snapshot_dir() -> str | None:
    """v13.3 M-1: locate the frozen snapshot directory.

    MACRO_ENGINE_SNAPSHOT is AUTHORITATIVE when set: if it names an existing
    directory it is used, if it names a missing one the snapshot tier is
    disabled (this is how the test suite stays hermetic). Without the env
    var, <script dir>/snapshot then ./snapshot are probed."""
    env = os.environ.get("MACRO_ENGINE_SNAPSHOT")
    if env is not None:
        return env if os.path.isdir(env) else None
    for cand in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot"),
                 os.path.join(os.getcwd(), "snapshot")):
        if os.path.isdir(cand):
            return cand
    return None


# ── § 13.2a · _fred_units_k ── v14.6.1 BUG 6: the ONE definition of the pc1 look-back …
def _fred_units_k(dates) -> int:
    """v14.6.1 BUG 6: the ONE definition of the pc1 look-back period k,
    inferred from the series' own observation spacing (median gap in days:
    52 weekly / 12 monthly / 4 quarterly).  Shared by _apply_fred_units
    (collapsed series, §13.2) and _apply_fred_units_vintage (per-release
    rows, §13.2b) so the two paths can never drift apart."""
    s = pd.Series(sorted(pd.DatetimeIndex(dates).unique()))
    gap = float(s.diff().dt.days.median()) if len(s) > 1 else float("nan")
    return 52 if gap <= 10 else (12 if gap <= 40 else 4)


# ── § 13.2 · _apply_fred_units ── v13.3 M-1: replicate FRED's documented `units` transformations f…
def _apply_fred_units(s: pd.Series, units: str) -> pd.Series:
    """v13.3 M-1: replicate FRED's documented `units` transformations for the
    public fredgraph.csv path, which serves LEVELS only (same replication the
    v13.2 replay adapter used and the baseline was validated against):
      pc1 = percent change from the YEAR-AGO observation (FRED definition)
      chg = change from the preceding period
    The transformation runs on the full fetched history BEFORE any window
    slice; callers fetch >= 13 months before fetch_start so the first
    in-window observation has a defined year-over-year value."""
    if units == "pc1":
        # v14 FIX-1 (CRITICAL): FRED pc1 = percent change from the YEAR-AGO
        # observation. k is inferred from the series' own observation
        # spacing: 52 weekly / 12 monthly / 4 quarterly.
        if len(s) < 3:
            return pd.Series(dtype=float, name=s.name)
        k = _fred_units_k(s.index)
        return 100.0 * (s / s.shift(k) - 1.0)
    if units == "chg":
        return s.diff()
    return s


# ── § 13.2b · _apply_fred_units_vintage ── v14.6.1 BUG 6: pc1/chg applied LOCALLY, per releas…
def _apply_fred_units_vintage(obs: list[dict], units: str) -> list[dict]:
    """v14.6.1 BUG 6: pc1/chg for REALTIME (vintage) rows, applied per
    RELEASE date — FRED serves its own non-'lin' units only at a single
    pinned vintage (HTTP 400 otherwise, see _build_fred_obs_url), so every
    realtime-RANGE download fetches LEVELS and the transform runs here:

        pc1(M, r) = 100 * (L(M, r) / L(M-k, r) - 1)
        chg(M, r) = L(M, r) - L(M-1, r)

    where L(X, r) = the level of observation X as KNOWN at release date r
    (the latest row with observation date X and realtime_start <= r) and k
    comes from _fred_units_k — the SAME rule the collapsed path
    (_apply_fred_units, §13.2) uses.  Both terms of every ratio/difference
    come from ONE information set: the year-ago level is the revised one
    when that revision was already public at r, the first-print one when it
    was not; no value is visible to the transform before its own
    realtime_start (no look-ahead).

    Vectorised: pivot (obs_date x realtime_start) -> ffill across vintages
    gives every L(X, r) at once; shifting the observation axis by k (or 1)
    gives the year-ago/previous level at the SAME vintage; a melt+merge
    reads the transformed value off each REAL release row.  No per-row
    Python loops.  Rows whose transform is undefined at that vintage
    (year-ago/previous level not yet public) are dropped — the vintage
    equivalent of _apply_fred_units' NaN head.  units='lin' returns the
    rows unchanged.  Output rows keep the exact {date, realtime_start,
    value} shape _collapse_vintage_pit consumes."""
    if units not in ("pc1", "chg"):
        return obs
    rows = []
    for o in obs:
        v = o.get("value")
        if v in (".", None, ""):
            continue
        try:
            rows.append((pd.Timestamp(o["date"]),
                         pd.Timestamp(o["realtime_start"]),
                         float(v)))
        except (ValueError, KeyError, TypeError):
            continue
    if not rows:
        return []
    df = (pd.DataFrame(rows, columns=["obs_date", "rt", "level"])
          .sort_values(["obs_date", "rt"], kind="stable")
          .drop_duplicates(["obs_date", "rt"], keep="last"))
    k = _fred_units_k(df["obs_date"])
    # levels as known at each vintage: NaN before an observation's first
    # release, then forward-filled across the vintage axis
    piv = (df.pivot(index="obs_date", columns="rt", values="level")
           .sort_index(axis=0).sort_index(axis=1).ffill(axis=1))
    base = piv.shift(k) if units == "pc1" else piv.shift(1)
    tmat = 100.0 * (piv / base - 1.0) if units == "pc1" else piv - base
    # keep only cells that ARE release events with a defined transform
    tvals = (tmat.rename_axis(index="obs_date", columns="rt").reset_index()
             .melt(id_vars="obs_date", var_name="rt", value_name="tval")
             .dropna(subset=["tval"]))
    tvals["rt"] = pd.to_datetime(tvals["rt"])   # melt yields object labels
    out = df.merge(tvals, on=["obs_date", "rt"], how="inner")
    out = out[np.isfinite(out["tval"])]
    return [{"date": d.strftime("%Y-%m-%d"),
             "realtime_start": r.strftime("%Y-%m-%d"),
             "value": float(v)}
            for d, r, v in zip(out["obs_date"], out["rt"], out["tval"])]


# ── § 13.3 · _parse_fred_csv ── v13.3 M-1: fredgraph.csv layout (observation_date,<SID>) -> clean…
def _parse_fred_csv(df: pd.DataFrame, sid: str) -> pd.Series:
    """v13.3 M-1: fredgraph.csv layout (observation_date,<SID>) -> clean daily-
    indexed float Series ('.' / blanks dropped, duplicates keep-last, sorted)."""
    if df.shape[1] < 2:
        return pd.Series(dtype=float, name=sid)
    idx = pd.to_datetime(df[df.columns[0]], errors="coerce")
    vals = pd.to_numeric(df[df.columns[1]].astype(str).str.strip(), errors="coerce")
    s = pd.Series(vals.values, index=pd.DatetimeIndex(idx), dtype=float)
    s = s[s.index.notna()].dropna()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.rename(sid)


_SNAPSHOT_DAILY_CACHE: pd.DataFrame | None = None
_SNAPSHOT_LOCK = threading.RLock()
_SNAPSHOT_YAHOO_FIELDS = ("Open", "High", "Low", "Close", "Volume")


# ── § 13.4 · _snapshot_daily ── v14.4 D3: the frozen Yahoo daily frame rebuilt from the hash-veri…
def _snapshot_daily() -> pd.DataFrame | None:
    """v14.4 D3: the frozen Yahoo daily frame rebuilt from the hash-verified
    snapshot/yahoo/*.csv dumps (MultiIndex (Price, Ticker) — exactly the
    shape yf.download(auto_adjust=True) returns; verified value-identical to
    the combined frame it replaces).  No executable object files are loaded.
    A file listed in snapshot/hashes.json is used ONLY when its SHA-256
    matches the manifest line; otherwise the formatter text is emitted and
    the file is ignored.  Only successful loads are cached; tests can reset
    meds._SNAPSHOT_DAILY_CACHE."""
    global _SNAPSHOT_DAILY_CACHE
    with _SNAPSHOT_LOCK:
        if _SNAPSHOT_DAILY_CACHE is not None:
            return _SNAPSHOT_DAILY_CACHE
    d = _snapshot_dir()
    if not d:
        return None
    ydir = os.path.join(d, "yahoo")
    if not os.path.isdir(ydir):
        return None
    hashes: dict[str, str] = {}
    try:
        with open(os.path.join(d, "hashes.json"), "r", encoding="utf-8") as fh:
            loaded = json.load(fh).get("files_sha256", {})
            hashes = loaded if isinstance(loaded, dict) else {}
    except (OSError, ValueError):
        hashes = {}
    frames: dict[str, pd.DataFrame] = {}
    for fn in sorted(os.listdir(ydir)):
        if not fn.endswith(".csv"):
            continue
        ticker = "^VIX" if fn[:-4] == "VIX" else fn[:-4]
        path = os.path.join(ydir, fn)
        rel = os.path.join("yahoo", fn)
        if rel in hashes:
            try:
                digest = _sha256_file(path)
            except OSError as e:
                _emit("  " + _describe_failure("local file", f"file={path}", exc=e))
                continue
            if digest != hashes[rel]:
                _emit("  " + _describe_failure(
                    "local file", f"file={path}",
                    body="SHA-256 mismatch vs snapshot/hashes.json — file ignored"))
                continue
        try:
            df = pd.read_csv(path)
        except (ValueError, OSError) as e:
            _emit("  " + _describe_failure("local file", f"file={path}", exc=e))
            continue
        if "Date" not in df.columns or not any(c in df.columns for c in ("Close", "Open")):
            _emit("  " + _describe_failure(
                "local file", f"file={path}",
                body=f"expected a Date column and OHLC columns, found {list(df.columns)}"))
            continue
        idx = pd.to_datetime(df["Date"], errors="coerce")
        df = df.assign(Date=idx).dropna(subset=["Date"]).set_index("Date").sort_index()
        frames[ticker] = df
    if not frames:
        return None
    tickers = sorted(frames)
    cols = {}
    for f in _SNAPSHOT_YAHOO_FIELDS:
        for t in tickers:
            cols[(f, t)] = frames[t][f] if f in frames[t].columns else pd.Series(dtype=float)
    out = pd.DataFrame(cols).sort_index()
    out.columns = pd.MultiIndex.from_product(
        [_SNAPSHOT_YAHOO_FIELDS, tickers], names=["Price", "Ticker"])
    out.index = pd.DatetimeIndex(out.index, name="Date")
    if out.empty:
        return None
    with _SNAPSHOT_LOCK:
        _SNAPSHOT_DAILY_CACHE = out
    return out


# ── § 13.5 · _auto_window ── v13.3 M-2: clip the window to what the actually-available data
def _auto_window(raw: dict[str, pd.Series], cfg: Config) -> tuple[Config, dict[str, pd.Series], list[str]]:
    """v13.3 M-2: clip the window to what the actually-available data
    supports — used ONLY on degraded source tiers (public CSV / snapshot)
    and only when the user did not pin dates explicitly.

    Rule (matches the window the v13.2 replay validated):
      fetch_start  = max(cfg.fetch_start, first month-start on/after the
                        earliest MANDATORY-guard observation, counting
                        data/<SID>_full.csv repairs)
      output_start = max(cfg.output_start, fetch_start + 2 months warmup)
    Raw series are re-sliced to the effective fetch_start so the panel is
    identical to what the FRED API (observation_start=fetch_start) would
    have returned. With full BAML history present (CSVs or API key) the
    window is NOT changed — the 1998/2008 defaults stand.
    """
    notes: list[str] = []
    guard_starts = []
    for sid in cfg.history_guard_mandatory:
        cands = []
        s = raw.get(sid)
        if s is not None and not s.empty:
            cands.append(pd.Timestamp(s.index.min()))
        try:
            csv, _ = _load_history_csv(sid, cfg)
        except RuntimeError:
            csv = None
        if csv is not None:
            cands.append(pd.Timestamp(csv.index.min()))
        if not cands:
            # Missing mandatory series: do not window around it — let
            # ensure_history() raise the actionable error.
            return cfg, raw, notes
        guard_starts.append(min(cands))
    guard_start = min(guard_starts)

    def _month_start_on_or_after(ts: pd.Timestamp) -> pd.Timestamp:
        ts = pd.Timestamp(ts).normalize()
        return ts if ts.day == 1 else ts + pd.offsets.MonthBegin(1)

    fetch_eff = max(pd.Timestamp(cfg.fetch_start),
                    _month_start_on_or_after(guard_start))
    output_eff = max(pd.Timestamp(cfg.output_start),
                     fetch_eff + pd.DateOffset(months=2))

    if fetch_eff == pd.Timestamp(cfg.fetch_start) and output_eff == pd.Timestamp(cfg.output_start):
        return cfg, raw, notes          # full history present — nothing to clip

    notes.append(
        f"auto-window: fetch_start {cfg.fetch_start} -> {fetch_eff.date()}, "
        f"output_start {cfg.output_start} -> {output_eff.date()} "
        f"(earliest mandatory credit-history observation: {guard_start.date()}; "
        f"FRED's public window for the ICE BofA series is rolling ~3 years).")
    notes.append(
        "to run the full 2008+ backtest: place percent-unit history CSVs at "
        + ", ".join(os.path.join(cfg.history_csv_dir, sid + "_full.csv")
                     for sid in cfg.history_guard_mandatory)
        + " (FRED's own CSV layout is fine), or set FREDAPI for vintage access.")

    lo, hi = min(fetch_eff, _pit_fetch_floor(replace(cfg, fetch_start=str(fetch_eff.date())))), \
        pd.Timestamp(cfg.output_end)
    sliced = {}
    for sid, s in raw.items():
        s2 = s.loc[(s.index >= lo) & (s.index <= hi)]
        if not s2.empty:
            sliced[sid] = s2
    if not sliced:
        return cfg, raw, notes
    new_cfg = replace(cfg, fetch_start=str(fetch_eff.date()),
                      output_start=str(output_eff.date()))
    return new_cfg, sliced, notes


# ── v13.2 C-1: point-in-time integrity manifest ─────────────────────────────
# Per-series audit of all 22 indicators. "strict_vintage_pit" = fetched with
# realtime_start/realtime_end and collapsed by publication date (a row for
# month M only contains readings PUBLIC by the end of M). "approximate_realtime"
# = is_real_time=True: indexed by observation date on the assumption that the
# value was public within ~1 day — see publication_lag / affected_observations
# for the residual edge risk at month boundaries.
_PIT_MANIFEST_DATA: dict[str, dict[str, str]] = {
    "RRPONTSYD": dict(
        pit_mode="approximate_realtime", revision_risk="none (operational daily figure, not revised)",
        publication_lag="same day (~13:30 ET)",
        evidence="FRED series notes: overnight reverse repurchase operations, published same day",
        affected_observations="last 1 daily obs of a month may publish on/just after the 1st of M+1",
        lookahead_risk="LOW (<=1 day)"),
    "WALCL": dict(
        pit_mode="approximate_realtime", revision_risk="none material (weekly level)",
        publication_lag="~8 days: released Thursday for the week ending the prior Wednesday",
        evidence="FRED H.4.1 release schedule (weekly, Thursday)",
        affected_observations="month-end rows whose last Wednesday observation is published AFTER month end (up to ~5 days)",
        lookahead_risk="MODERATE — flagged APPROXIMATE; consider an 8-day lag or dropping month-edge observations"),
    "DFF": dict(
        pit_mode="approximate_realtime", revision_risk="none (effective rate finalized next business day)",
        publication_lag="next business day ~09:00 ET (v14.1 S1: +2d shift applied on non-API tiers so the last 1-2 daily obs of a month are not consumed early)",
        evidence="FRED series notes: daily effective federal funds rate",
        affected_observations="final 1-2 daily obs of a month publish early in M+1, before the entry open",
        lookahead_risk="LOW (public before the next-month entry in most calendars)"),
    "CPIAUCSL": dict(
        pit_mode="strict_vintage_pit", revision_risk="HIGH (seasonal/benchmark revisions)",
        publication_lag="~2-3 weeks after the observation month",
        evidence="BLS release calendar; FRED realtime vintages used",
        affected_observations="none under vintage mode (first print lands in its publication month)",
        lookahead_risk="NONE under strict PIT; APPROXIMATE under the H-2 lag fallback"),
    "PCEPILFE": dict(
        pit_mode="strict_vintage_pit", revision_risk="HIGH (annual revisions)",
        publication_lag="~4 weeks (end of following month)",
        evidence="BEA release calendar; FRED realtime vintages used",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT; APPROXIMATE under the H-2 lag fallback"),
    "T5YIE": dict(
        pit_mode="approximate_realtime", revision_risk="none (daily market-implied breakeven)",
        publication_lag="same day (end of day)",
        evidence="FRED series notes: 5-year, 5-year forward breakeven derived from TIPS",
        affected_observations="last daily obs of a month may publish on/after the 1st of M+1",
        lookahead_risk="LOW (<=1 day)"),
    "T10YIE": dict(
        pit_mode="approximate_realtime", revision_risk="none (daily market-implied breakeven)",
        publication_lag="same day (end of day)",
        evidence="FRED series notes: 10-year breakeven from TIPS",
        affected_observations="last daily obs of a month may publish on/after the 1st of M+1",
        lookahead_risk="LOW (<=1 day)"),
    "A191RL1Q225SBEA": dict(
        pit_mode="strict_vintage_pit", revision_risk="VERY HIGH (advance -> second -> final + annual/benchmark)",
        publication_lag="~1 month (advance), revised for months afterwards",
        evidence="BEA GDP release schedule; FRED realtime vintages used",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT; APPROXIMATE under the H-2 lag fallback"),
    "CFNAI": dict(
        pit_mode="strict_vintage_pit", revision_risk="low (index generally final at release)",
        publication_lag="toward the END of the month FOLLOWING the observation month (~8 weeks after the observation month; v14.0 wrongly said end of observation month — audit D7)",
        evidence="Chicago Fed: 'The CFNAI is released at 8:30 a.m. ET on scheduled days, normally toward the end of each calendar month' — the September index is released in late October",
        affected_observations="none under vintage mode; on non-API tiers a +55d shift is applied",
        lookahead_risk="NONE under strict PIT; LOW on non-API tiers (publication-lag shift)"),
    "INDPRO": dict(
        pit_mode="strict_vintage_pit", revision_risk="MODERATE (preliminary -> final)",
        publication_lag="~2-2.5 weeks (mid following month)",
        evidence="FRB G.17 release schedule",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT; APPROXIMATE under the H-2 lag fallback"),
    "HOUST": dict(
        pit_mode="strict_vintage_pit", revision_risk="MODERATE (monthly revisions)",
        publication_lag="~2-3 weeks (mid following month)",
        evidence="Census new residential construction release schedule",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT; APPROXIMATE under the H-2 lag fallback"),
    "UMCSENT": dict(
        pit_mode="strict_vintage_pit", revision_risk="MODERATE (preliminary + final prints)",
        publication_lag="mid-month preliminary, end-month final",
        evidence="U-M Surveys of Consumers schedule",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT"),
    "PAYEMS": dict(
        pit_mode="strict_vintage_pit", revision_risk="VERY HIGH (2 monthly revisions + annual benchmark)",
        publication_lag="~3 weeks (first Friday after the observation month)",
        evidence="BLS Employment Situation schedule",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT; APPROXIMATE under the H-2 lag fallback"),
    "UNRATE": dict(
        pit_mode="strict_vintage_pit", revision_risk="MODERATE (monthly revisions)",
        publication_lag="~3 weeks (first Friday after the observation month)",
        evidence="BLS Employment Situation schedule",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT"),
    "ICSA": dict(
        pit_mode="strict_vintage_pit", revision_risk="MODERATE (revised in the following week's release)",
        publication_lag="~5 days (Thursday release for the week ending Saturday)",
        evidence="DOL unemployment insurance claims release schedule",
        affected_observations="none under vintage mode (weekly lag handled by the H-2 fallback too)",
        lookahead_risk="NONE under strict PIT"),
    "JTSJOL": dict(
        pit_mode="strict_vintage_pit", revision_risk="MODERATE (monthly revisions)",
        publication_lag="~6-7 weeks (early second month after)",
        evidence="BLS JOLTS release schedule",
        affected_observations="none under vintage mode",
        lookahead_risk="NONE under strict PIT"),
    "BAMLH0A0HYM2": dict(
        pit_mode="approximate_realtime", revision_risk="low (end-of-day index; restatements rare)",
        publication_lag="same evening (ICE BofA end-of-day indices)",
        evidence="ICE BofA US High Yield Index via FRED",
        affected_observations="last daily obs of a month publishes the same evening / next morning; ALSO: FRED serves only a rolling ~3y window since 2026-04 (H-1) — full history needs a user CSV",
        lookahead_risk="LOW (<=1 day) + DATA PROVISION RISK (history truncation)"),
    "BAMLC0A0CM": dict(
        pit_mode="approximate_realtime", revision_risk="low (end-of-day index; restatements rare)",
        publication_lag="same evening",
        evidence="ICE BofA US Corporate Index via FRED",
        affected_observations="same 1-day edge; rolling ~3y FRED window (H-1)",
        lookahead_risk="LOW (<=1 day) + DATA PROVISION RISK"),
    "BAMLH0A1HYBBEY": dict(
        pit_mode="approximate_realtime", revision_risk="low (end-of-day index)",
        publication_lag="same evening",
        evidence="ICE BofA BB US High Yield Index via FRED",
        affected_observations="same 1-day edge; rolling ~3y FRED window (H-1); optional guard series (not scored)",
        lookahead_risk="LOW (<=1 day) + DATA PROVISION RISK"),
    "DGS10": dict(
        pit_mode="approximate_realtime", revision_risk="none (daily CMT yield)",
        publication_lag="same day ~17:00 ET",
        evidence="Treasury daily par yield curve rates",
        affected_observations="last daily obs of a month may publish on/after the 1st of M+1",
        lookahead_risk="LOW (<=1 day)"),
    "T10Y2Y": dict(
        pit_mode="approximate_realtime", revision_risk="none (daily yield spread)",
        publication_lag="same day (end of day)",
        evidence="Treasury daily par yield curve rates",
        affected_observations="last daily obs of a month may publish on/after the 1st of M+1",
        lookahead_risk="LOW (<=1 day)"),
    "DTWEXBGS": dict(
        pit_mode="approximate_realtime", revision_risk="none (daily broad USD index)",
        publication_lag="weekly Monday FRED update for the H.10 release (data through the prior Friday); the last week of a month can publish the following Monday (v14.1 S1: +5d shift applied on non-API tiers)",
        evidence="FRED series page: 'Updated Oct 26, 2026 … Next Release Date: Nov 2, 2026' with last observation 2026-10-23",
        affected_observations="last 1-7 daily obs of a month may publish in M+1",
        lookahead_risk="LOW (<=1 week; covered by the +5d shift)"),
}


# ── § 13.6 · build_pit_manifest ── C-1 (v13.2) / v14.1 S1 (audit D7): PIT integrity manifest for a…
def build_pit_manifest() -> list[dict]:
    """C-1 (v13.2) / v14.1 S1 (audit D7): PIT integrity manifest for all 22
    indicators, GENERATED FROM CODE (the single source of truth — the shipped
    snapshot/PIT_MANIFEST.json was written by an older build and is stale:
    it claimed pc1 = month-over-month and CFNAI publishes at the end of the
    observation month; both claims are wrong).

    Validation statuses:
      VERIFIED      — designation supported by the series' documented
                      publication process (market/operational daily data,
                      not revised).
      APPROXIMATE   — real-time designation is a reasonable approximation but
                      a residual publication-lag edge exists at month
                      boundaries (WALCL is the notable case: ~8-day lag).
      UNVERIFIED_IN_THIS_ENV — strict vintage behavior could not be exercised
                      in the repair environment (no FRED API key), so the
                      strict-PIT path is verified by unit tests on synthetic
                      vintages, not on genuine vintages.
    Each entry also carries the publication lag actually APPLIED on non-API
    tiers (applied_pit_lag_days) and the dated release evidence behind it.
    Print it with:  python meds.py --pit-manifest
    """
    lag_map = dict(CFG.pit_lag_days) if CFG.pit_lag_enabled else {}
    manifest = []
    for spec in INDICATORS:
        extra = _PIT_MANIFEST_DATA.get(spec.series_id, {})
        if spec.series_id == "WALCL":
            status = "APPROXIMATE"
        elif spec.is_real_time:
            status = "VERIFIED"
        else:
            status = "UNVERIFIED_IN_THIS_ENV"
        manifest.append({
            "series_id": spec.series_id, "name": spec.name, "units": spec.units,
            "category": spec.category, "is_real_time": spec.is_real_time,
            "pit_mode": extra.get("pit_mode", "strict_vintage_pit" if not spec.is_real_time else "approximate_realtime"),
            "revision_risk": extra.get("revision_risk", ""),
            "publication_lag": extra.get("publication_lag", ""),
            "evidence": extra.get("evidence", ""),
            "affected_observations": extra.get("affected_observations", ""),
            "lookahead_risk": extra.get("lookahead_risk", ""),
            "validation_status": status,
            # v14 FIX-1: pc1 is now truly year-over-year on every tier, so
            # the "CPI (YoY)" style labels are accurate.
            "units_note": ("FRED units=pc1 = percent change from the year-ago "
                           "observation (year-over-year)" if spec.units == "pc1"
                           else "FRED units=chg = change from the preceding period" if spec.units == "chg"
                           else "FRED units=lin = level"),
            # v14.1 S1: the lag actually applied on non-API tiers + evidence.
            "applied_pit_lag_days": int(lag_map.get(spec.series_id, 0)),
            "applied_pit_lag_evidence": PIT_LAG_EVIDENCE.get(spec.series_id, ""),
        })
    return manifest


# ── § 13.7 · pit_observation_report ── v14.1 S1: per-observation PIT tracking. One row per fetched…
def pit_observation_report(raw: dict[str, pd.Series],
                           cfg: Config = CFG) -> pd.DataFrame:
    """v14.1 S1: per-observation PIT tracking.  One row per fetched series
    with the publication lag applied, the dated evidence, and the first/last
    month-end rows that can see its observations after the shift — the audit
    artifact proving WHEN each series' information becomes usable."""
    lag_map = dict(cfg.pit_lag_days) if cfg.pit_lag_enabled else {}
    rows = []
    for spec in INDICATORS:
        s = raw.get(spec.series_id)
        if s is None or s.empty:
            continue
        lag = int(lag_map.get(spec.series_id, 0))
        shifted = s if lag <= 0 else s.copy().set_axis(
            s.index + pd.Timedelta(days=lag))
        s_me = shifted.resample(FREQ_ME).last().dropna()
        pit_mode = ("STRICT_VINTAGE" if (not spec.is_real_time and cfg.fred_api_key)
                    else ("APPROXIMATE_LAG" if lag > 0 else "REALTIME"))
        rows.append({
            "series_id": spec.series_id,
            "lag_days": lag,
            "n_obs": int(len(s)),
            "first_obs": str(s.index.min().date()),
            "last_obs": str(s.index.max().date()),
            "first_visible_month_end": (str(s_me.index.min().date())
                                         if not s_me.empty else ""),
            "last_visible_month_end": (str(s_me.index.max().date())
                                        if not s_me.empty else ""),
            "pit_mode": pit_mode,
            "evidence": PIT_LAG_EVIDENCE.get(spec.series_id, ""),
        })
    return pd.DataFrame(rows)


# ── § 13.8 · credit_killswitch_coverage ── v14.1 S5 (audit D6): when is the CREDIT_CRUNCH kill-swi…
def credit_killswitch_coverage(raw: dict[str, pd.Series],
                              cfg: Config = CFG) -> dict:
    """v14.1 S5 (audit D6): when is the CREDIT_CRUNCH kill-switch
    structurally ABLE to fire?  It consumes BAMLH0A0HYM2_lvl_z_expanding,
    which needs credit_expanding_min_periods (36) months of HY-OAS history —
    on a clipped window (FRED's rolling ~3y ICE BofA coverage) the
    kill-switch is dead for most of the run and the regime layer silently
    loses one of its two kill-switches.  This measures the gap honestly."""
    s = (raw or {}).get("BAMLH0A0HYM2")
    empty = {"first_valid_month": None, "n_inactive": 0, "n_total": 0,
             "killswitch_active_share": 0.0,
             "note": "BAMLH0A0HYM2 not available"}
    if s is None or s.empty:
        return empty
    s_me = s.resample(FREQ_ME).last().ffill()
    lo = pd.Timestamp(cfg.output_start)
    hi = pd.Timestamp(cfg.output_end)
    out_rows = s_me.loc[(s_me.index >= lo) & (s_me.index <= hi)]
    if out_rows.empty:
        return empty
    hist = s_me.loc[:out_rows.index[-1]]
    n_min = int(cfg.credit_expanding_min_periods)
    valid = hist.index[n_min - 1:] if len(hist) >= n_min else []
    first_valid = (valid[0].strftime("%Y-%m") if len(valid) else None)
    if first_valid is None:
        n_inactive = len(out_rows)
    else:
        n_inactive = int((out_rows.index < pd.Timestamp(first_valid)).sum())
    n_total = len(out_rows)
    return {
        "first_valid_month": first_valid,
        "n_inactive": int(n_inactive),
        "n_total": int(n_total),
        "killswitch_active_share": (n_total - n_inactive) / n_total if n_total else 0.0,
        "note": (f"expanding z needs {n_min} months of HY-OAS history; "
                 f"FRED's public ICE BofA window is rolling ~3y"),
    }


# ── § 13.9 · universe_audit ── v13.2: each ticker's first trade date vs the backtest start. v13.…
def universe_audit(tickers: list[str], backtest_start: str) -> pd.DataFrame:
    """v13.2: each ticker's first trade date vs the backtest start. v13.3 M-1:
    yfinance is now OPTIONAL — when it is unreachable (or --snapshot is set)
    the first trade date comes from the frozen snapshot's price history and
    the `source` column says so. An UNKNOWN IPO date stays unknown — it must
    not silently count as "predates the backtest"."""
    info = None
    if not FORCE_SNAPSHOT:
        yf_mod = _load_yf()
        if yf_mod is None:
            _diag().yf_errors.append(_describe_failure(
                "Yahoo (yfinance)", f"tickers={tickers}", exc=_YF_IMPORT_ERROR,
                body="yfinance is not installed — first-trade dates fall back "
                     "to the snapshot price history"))
        else:
            try:
                info = yf_mod.Tickers(" ".join(tickers)).tickers
            except Exception as e:        # recorded verbatim, never silenced
                _diag().yf_errors.append(_describe_failure(
                    "Yahoo (yfinance)", f"tickers={tickers}", exc=e,
                    body="universe audit degraded to the snapshot price history"))
                info = None
    snap = _snapshot_daily()
    rows = []
    for t in tickers:
        ipo_date, source = None, "unknown"
        if info is not None:
            try:
                ipo = info[t].info.get("firstTradeDateEpochUtc")
                ipo_date = pd.Timestamp(ipo, unit="s").date() if ipo else None
                if ipo_date is not None:
                    source = "yfinance"
            except Exception as e:        # recorded verbatim, never silenced
                _diag().yf_errors.append(_describe_failure(
                    "Yahoo (yfinance)", f"ticker={t}", exc=e,
                    body="first-trade-date lookup failed; falling back to the "
                         "snapshot price history"))
                ipo_date = None
        if ipo_date is None and snap is not None and isinstance(snap.columns, pd.MultiIndex):
            try:
                close_t = snap["Close"][t]
            except (KeyError, IndexError, TypeError):
                close_t = None
            if close_t is not None:
                first = close_t.first_valid_index()
                if first is not None:
                    ipo_date = pd.Timestamp(first).date()
                    source = "snapshot"
        rows.append({
            "ticker": t,
            "first_trade_date": ipo_date,
            "source": source,
            "ipo_known": ipo_date is not None,
            "predates_backtest": (None if ipo_date is None
                                   else bool(pd.Timestamp(ipo_date) <= pd.Timestamp(backtest_start))),
        })
    return pd.DataFrame(rows)


# ── § 13.10 · FeatureEngine
class FeatureEngine:
    # · build_panel
    @staticmethod
    def build_panel(raw: dict[str, pd.Series], cfg: Config = CFG) -> pd.DataFrame:
        series_list = []
        for spec in INDICATORS:
            s = raw.get(spec.series_id)
            if s is None: continue
            s_me = s.resample(FREQ_ME).last().ffill()
            series_list.append(s_me.rename(spec.series_id))
        if not series_list: return pd.DataFrame()
        return pd.concat(series_list, axis=1, sort=False).sort_index()

    # · add_derived
    @staticmethod
    def add_derived(panel: pd.DataFrame) -> pd.DataFrame:
        derived_list = []
        for name, func in DERIVED_SERIES.items():
            try: derived_list.append(func(panel).rename(name))
            except KeyError as e:
                # v14.7 4a: the skip is RECORDED, naming the missing input
                # series — a REAL10Y-less panel used to vanish silently and
                # safe_weighted_score renormalized the remaining terms of
                # STAGFLATIONARY_DRAG with no trace.  (Score unchanged; on
                # a healthy panel both inputs exist and nothing fires.)
                missing = e.args[0] if e.args else "<unknown>"
                _diag().price_notes.append(
                    f"derived {name} skipped: missing {missing}")
        if derived_list:
            return pd.concat([panel, pd.concat(derived_list, axis=1, sort=False)], axis=1)
        return panel

    # · add_features
    @staticmethod
    def add_features(panel: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
        feature_frames = []
        for col in panel.columns:
            s = panel[col]
            mu = s.rolling(cfg.zscore_window, min_periods=cfg.zscore_min_periods).mean()
            std = s.rolling(cfg.zscore_window, min_periods=cfg.zscore_min_periods).std()
            lvl_z = ((s - mu) / std.replace(0, np.nan)).rename(f"{col}_lvl_z")
            lvl_pct = s.rolling(cfg.percentile_window, min_periods=cfg.percentile_min_periods).rank(pct=True).rename(f"{col}_lvl_pct")
            # v14 FIX-9: fill_method=None — the panel is already forward-
            # filled (line above), so this is value-identical to the old
            # deprecated default and kills the FutureWarning noise.
            roc3m = s.pct_change(cfg.roc_3m, fill_method=None).rename(f"{col}_roc3m")
            diff3m = s.diff(cfg.roc_3m).rename(f"{col}_diff3m")
            roc_mu = roc3m.rolling(cfg.zscore_window, min_periods=cfg.zscore_min_periods).mean()
            roc_std = roc3m.rolling(cfg.zscore_window, min_periods=cfg.zscore_min_periods).std()
            roc3m_z = ((roc3m - roc_mu) / roc_std.replace(0, np.nan)).rename(f"{col}_roc3m_z")
            feature_frames.extend([lvl_z, lvl_pct, roc3m, diff3m, roc3m_z])
        return pd.concat([panel, pd.concat(feature_frames, axis=1, sort=False)], axis=1)

    # · add_credit_expanding_zscore
    @staticmethod
    def add_credit_expanding_zscore(panel: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
        if "BAMLH0A0HYM2" not in panel.columns: return panel
        s = panel["BAMLH0A0HYM2"]
        exp_mean = s.expanding(min_periods=cfg.credit_expanding_min_periods).mean()
        exp_std = s.expanding(min_periods=cfg.credit_expanding_min_periods).std()
        exp_z = ((s - exp_mean) / exp_std.replace(0, np.nan)).rename("BAMLH0A0HYM2_lvl_z_expanding")
        return pd.concat([panel, exp_z], axis=1)

    # · build_full_panel
    @classmethod
    def build_full_panel(cls, raw: dict[str, pd.Series], cfg: Config = CFG) -> pd.DataFrame:
        panel = cls.build_panel(raw, cfg)
        if panel.empty: return panel
        panel = cls.add_derived(panel)
        panel = cls.add_features(panel, cfg)
        panel = cls.add_credit_expanding_zscore(panel, cfg)
        core_cols = [c for c in cfg.core_columns if c in panel.columns]
        if core_cols:
            panel = panel.dropna(subset=core_cols, how="all")
        return panel

    # · run
    @classmethod
    def run(cls, raw: dict[str, pd.Series], cfg: Config = CFG) -> pd.DataFrame:
        panel = cls.build_full_panel(raw, cfg)
        if panel.empty: return panel
        start_ts = pd.Timestamp(cfg.output_start)
        end_ts = pd.Timestamp(cfg.output_end)
        return panel.loc[(panel.index >= start_ts) & (panel.index <= end_ts)]


# ═══════════════════════════════════════════════════════════════════════════
#  § 14 · REGIME CLASSIFIER & HYSTERESIS
# ═══════════════════════════════════════════════════════════════════════════
# v13.2 audit: scenario score lambdas that RAISE are excluded from scoring
# (v13.1 behavior) but now RECORDED instead of being silently swallowed — a
# broken score would otherwise silently re-weight every regime.
# (v14.4 U11: the live collection is the ACTIVE diagnostics sink's
# score_errors list — see _Diagnostics; the module-global SCORE_ERRORS is
# the CLI default sink's backing list, defined once near the sink.)

# v14.7 S5: memo for RegimeClassifier._extract_input_features — the suffix
# key list depends ONLY on which columns a panel carries, so it is computed
# once per distinct column tuple (capped; cleared when full) instead of once
# per row.  Output is byte-identical to the per-row scan.
_FEATURE_KEYS_CACHE: dict[tuple, list] = {}


# ── § 14.1 · RegimeClassifier
class RegimeClassifier:
    # · __init__
    def __init__(self, scenarios: list[ScenarioSpec], cfg: Config = CFG) -> None:
        self.cfg = cfg
        self.scenarios = sorted(scenarios, key=lambda s: s.priority)
        self.neutral = next(s for s in self.scenarios if s.key == "NEUTRAL_WAIT_AND_SEE")
        # v14.6.2 STEP A: None in a credit-OFF run (CREDIT_CRUNCH is one of
        # the excluded scenarios) — the credit kill-switch branch below is
        # then structurally dead, which the run states explicitly.
        self.credit_crunch = next((s for s in self.scenarios
                                   if s.key == "CREDIT_CRUNCH"), None)
        self.hard_landing = next(s for s in self.scenarios if s.key == "HARD_LANDING")

    # · _extract_input_features
    def _extract_input_features(self, row: pd.Series) -> dict:
        # v14.7 S5: the suffix scan is per-PANEL work, not per-row — it is
        # memoised on the exact column tuple (output depends only on which
        # columns exist), so classify_panel stops re-scanning every row.
        cols = tuple(row.index)
        keys = _FEATURE_KEYS_CACHE.get(cols)
        if keys is None:
            keys = [k for k in row.index if any(k.endswith(s) for s in ["_lvl_z", "_lvl_pct", "_diff3m", "_roc3m"])]
            if len(_FEATURE_KEYS_CACHE) >= 256:
                _FEATURE_KEYS_CACHE.clear()
            _FEATURE_KEYS_CACHE[cols] = keys
        return {k: row[k] for k in keys}

    # · classify_panel
    def classify_panel(self, panel: pd.DataFrame) -> pd.DataFrame:
        records = []
        for date, row in panel.iterrows():
            sc, top_fit, runner_up_fit, dominance, all_scores, input_zs, path = self._classify_row_full(row)
            # v13.2 D-1: NO placeholder leverage here. The executable leverage
            # needs regime feedback (regime_acc) and the post-hysteresis
            # regime_months, neither of which exists at classification time.
            # apply_hysteresis() fills `conviction_leverage` with the
            # unadjusted (prior-based) value; the backtester computes the
            # executable value via executable_leverage().
            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "regime": sc.regime, "scenario_key": sc.key, "scenario": sc.name,
                "cycle_phase": sc.cycle_phase, "emoji": sc.emoji, "diagnosis": sc.diagnosis,
                "confidence": round(top_fit, 6), "runner_up_confidence": round(runner_up_fit, 6),
                "dominance": round(dominance, 6), "margin_passed": bool(dominance >= self.cfg.min_margin),
                "conviction_leverage": np.nan,
                "lev_basis": "pending_hysteresis",
                "long": list(sc.long), "short": list(sc.short),
                # v13 R-4: policy rate (DFF, percent) as known at the decision
                # date — used by the backtester to charge financing on leverage.
                "financing_rate": row.get("DFF", np.nan),
                "classification_path": path,
            })
        return pd.DataFrame(records)

    # · _classify_row_full
    def _classify_row_full(self, row: pd.Series):
        unrate_diff = row.get("UNRATE_diff3m", np.nan)
        if pd.notna(unrate_diff) and unrate_diff > 0.3:
            return (self.hard_landing, 1.0, 0.0, 1.0, {"HARD_LANDING": 1.0},
                    self._extract_input_features(row), "kill_switch_hard_landing")

        hy_oas_z = row.get("BAMLH0A0HYM2_lvl_z_expanding", np.nan)
        # v14.5 FIX-3 (part B): cfg.killswitch_credit_z (default 1.5, the
        # historical hard-coded value) so the C10 suite can perturb it.
        # v14.6.2 STEP A: dead branch in a credit-OFF run — the feature does
        # not exist (both OAS series were dropped from the panel), hy_oas_z
        # is NaN, AND the scenario is excluded (self.credit_crunch is None).
        if (self.credit_crunch is not None and pd.notna(hy_oas_z)
                and hy_oas_z > self.cfg.killswitch_credit_z):
            return (self.credit_crunch, 1.0, 0.0, 1.0, {"CREDIT_CRUNCH": 1.0},
                    self._extract_input_features(row), "kill_switch_credit_crunch")

        scores = []
        for sc in self.scenarios:
            if sc.key == "NEUTRAL_WAIT_AND_SEE": continue
            try:
                fit = sc.score(row)
            except Exception as e:
                # v13.2 audit: recorded, not swallowed (the score is still
                # excluded, exactly as in v13.1).  v14.4 U11: the record goes
                # to the ACTIVE diagnostics sink (the CLI sink aliases the
                # module-global SCORE_ERRORS; an API call collects privately).
                _diag().score_errors.append(f"{sc.key}: {type(e).__name__}: {e}")
                fit = np.nan
            if pd.isna(fit): continue
            scores.append((sc, fit))

        if not scores:
            return (self.neutral, 1.0, 0.0, 0.0, {}, self._extract_input_features(row), "neutral_no_scores")

        scores.sort(key=lambda x: (-x[1], x[0].priority))
        top_sc, top_fit = scores[0]
        runner_up_fit = scores[1][1] if len(scores) > 1 else 0.0
        dominance = max(0.0, top_fit - runner_up_fit)

        if top_fit < self.cfg.min_confidence:
            cfmai_val = row.get("CFNAI", np.nan)
            hy_diff = row.get("BAMLH0A0HYM2_diff3m", np.nan)
            spy_trend_up = (pd.notna(hy_diff) and hy_diff < 0 and pd.notna(cfmai_val) and cfmai_val > -0.3)
            if spy_trend_up:
                soft_landing = next(s for s in self.scenarios if s.key == "SOFT_LANDING_PIVOT")
                return (soft_landing, 0.5, top_fit, 0.5 - top_fit,
                        {s.key: f for s, f in scores}, self._extract_input_features(row), "soft_landing_fallback")
            return (self.neutral, 1.0 - top_fit, top_fit, dominance,
                    {s.key: f for s, f in scores}, self._extract_input_features(row), "neutral_low_confidence")

        return (top_sc, top_fit, runner_up_fit, dominance,
                {s.key: f for s, f in scores}, self._extract_input_features(row), "scored")


# ── § 14.2 · get_macro_regime
def get_macro_regime(panel: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    # v14.6.2 STEP A: credit-OFF runs classify on the reduced scenario set
    # (CREDIT_CRUNCH / EARLY_CYCLE_RE_ACCELERATION excluded); with credit
    # ON _scenarios_for(cfg) is exactly SCENARIOS (v14.6.1 behaviour).
    return RegimeClassifier(_scenarios_for(cfg), cfg).classify_panel(panel)


# ── § 14.3 · _patch_record
def _patch_record(record: dict[str, Any], target_key: str) -> dict[str, Any]:
    sc = _SCENARIO_LOOKUP.get(target_key, SCENARIOS[-1])
    record["raw_winner_key"] = record.get("scenario_key")
    record["scenario_key"] = sc.key
    record["scenario"] = sc.name
    record["regime"] = sc.regime
    record["cycle_phase"] = sc.cycle_phase
    record["emoji"] = sc.emoji
    record["diagnosis"] = sc.diagnosis
    record["long"] = list(sc.long)
    record["short"] = list(sc.short)
    record["hysteresis_patched"] = True
    return record


# ── § 14.4 · apply_hysteresis ── Debounce/regime-life smoothing.
def apply_hysteresis(predictions: pd.DataFrame, cfg: Config = CFG,
                     initial_state: dict | None = None) -> pd.DataFrame:
    """Debounce/regime-life smoothing.

    v13.2 additions:
    * `initial_state` lets a caller chain the hysteresis state across folds
      (walk-forward); the final state is exported on `out.attrs[
      "hysteresis_final_state"]`.
    * `conviction_leverage` is (re)computed here from the TRUE post-hysteresis
      regime_months (v13.1's classify_panel used placeholder months=1).
      regime_acc is still the 0.5 prior at this stage (it needs backtest
      feedback); `lev_basis` says so explicitly. The backtester's executable
      leverage is computed by executable_leverage().
    """
    if predictions.empty: return predictions
    records = predictions.to_dict("records")
    st = initial_state or {}
    active_key = st.get("active_key") or records[0]["scenario_key"]
    pending_key = st.get("pending_key")
    pending_ct = int(st.get("pending_ct", 0))
    regime_months = int(st.get("regime_months", 0))

    for i in range(len(records)):
        raw_key = records[i]["scenario_key"]
        records[i]["hysteresis_patched"] = False

        if cfg.credit_breaker and raw_key in ["CREDIT_CRUNCH", "HARD_LANDING"]:
            if raw_key == active_key:
                regime_months += 1
            else:
                active_key = raw_key
                pending_key, pending_ct, regime_months = None, 0, 1
            _patch_record(records[i], active_key)
            records[i]["regime_months"] = regime_months
            records[i]["conviction_leverage"] = conviction_leverage_v2(
                records[i].get("dominance", 0.0), 0.5, regime_months, cfg)
            records[i]["lev_basis"] = "unadjusted_prior"
            continue

        if raw_key == active_key:
            pending_key, pending_ct = None, 0
            regime_months += 1
            _patch_record(records[i], active_key)
            records[i]["regime_months"] = regime_months
            records[i]["conviction_leverage"] = conviction_leverage_v2(
                records[i].get("dominance", 0.0), 0.5, regime_months, cfg)
            records[i]["lev_basis"] = "unadjusted_prior"
            continue

        if pending_key == raw_key:
            pending_ct += 1
        else:
            pending_key, pending_ct = raw_key, 1

        if pending_ct >= cfg.debounce_months or regime_months >= cfg.max_regime_life:
            active_key = raw_key
            pending_key, pending_ct, regime_months = None, 0, 1
            _patch_record(records[i], active_key)
        else:
            _patch_record(records[i], active_key)
        records[i]["regime_months"] = regime_months
        records[i]["conviction_leverage"] = conviction_leverage_v2(
            records[i].get("dominance", 0.0), 0.5, regime_months, cfg)
        records[i]["lev_basis"] = "unadjusted_prior"

    out = pd.DataFrame(records)
    out.attrs["hysteresis_final_state"] = {
        "active_key": active_key, "pending_key": pending_key,
        "pending_ct": pending_ct, "regime_months": regime_months,
    }
    return out


# ═══════════════════════════════════════════════════════════════════════════
#  § 15 · RISK MANAGER & VXX OVERLAY
# ═══════════════════════════════════════════════════════════════════════════
# ── § 15.0 · SPY trend table cache — v14.7 S1: the rolling SMA/ROC table
# compute_leverage_cap rebuilt for EVERY call (4 rolling passes + 4 full-index
# strftime passes).  It is constant for a given (series, sma_window,
# roc_window); here it is built once and served from a small LRU keyed by
# series identity + length + last value + the two windows (the entry holds a
# STRONG reference to the series, so the id() stays valid while cached, and
# hits are re-verified with `is`).  Duplicate 'YYYY-MM' keys: later rows win,
# exactly like .loc[label].iloc[-1] on the string-indexed copies.
_SPY_TREND_CACHE: "OrderedDict[tuple, tuple]" = OrderedDict()
_SPY_TREND_CACHE_MAX = 8
_SPY_TREND_LOCK = threading.Lock()


# ── § 15.0.1 · _spy_trend_table — the ONE table compute_leverage_cap reads.
def _spy_trend_table(spy_monthly_close: pd.Series, sma_window: int,
                     roc_window: int) -> dict:
    """v14.7 S1: {'YYYY-MM': (close, sma, roc, roc1)} for a monthly-close
    series — the ONE table compute_leverage_cap reads.  Values follow
    RiskManager._scalar semantics (float, NaN stays NaN); later duplicates
    overwrite earlier ones, matching the old .loc[str].iloc[-1] reads."""
    n = len(spy_monthly_close)
    last = spy_monthly_close.iloc[-1] if n else None
    last_key = None if n == 0 or not (last == last) else float(last)
    key = (id(spy_monthly_close), n, last_key, int(sma_window), int(roc_window))
    with _SPY_TREND_LOCK:
        hit = _SPY_TREND_CACHE.get(key)
        if hit is not None:
            if hit[0] is spy_monthly_close:      # airtight identity re-check
                _SPY_TREND_CACHE.move_to_end(key)
                return hit[1]
            _SPY_TREND_CACHE.pop(key, None)     # stale id: drop and rebuild
    spy_sma = spy_monthly_close.rolling(sma_window).mean()
    spy_roc = spy_monthly_close.pct_change(roc_window)
    spy_roc1 = spy_monthly_close.pct_change(1)
    keys = spy_monthly_close.index.strftime("%Y-%m")
    table: dict[str, tuple] = {}
    for k, c, s, r, r1 in zip(keys, spy_monthly_close.to_numpy(),
                              spy_sma.to_numpy(), spy_roc.to_numpy(),
                              spy_roc1.to_numpy()):
        table[k] = tuple(RiskManager._scalar(v) for v in (c, s, r, r1))
    with _SPY_TREND_LOCK:
        _SPY_TREND_CACHE[key] = (spy_monthly_close, table)
        _SPY_TREND_CACHE.move_to_end(key)
        while len(_SPY_TREND_CACHE) > _SPY_TREND_CACHE_MAX:
            _SPY_TREND_CACHE.popitem(last=False)
    return table


# ── § 15.1 · RiskManager
class RiskManager:
    # · __init__
    def __init__(self, cfg: Config = CFG) -> None:
        self.cfg = cfg

    # · _scalar — Coerce a possibly-Series .loc result to a float.
    @staticmethod
    def _scalar(v) -> float:
        """Coerce a possibly-Series .loc result to a float."""
        if isinstance(v, (pd.Series, np.ndarray)):
            v = v.iloc[-1] if isinstance(v, pd.Series) else v[-1]
        return float(v) if pd.notna(v) else np.nan

    # · _build_vxx_context — L-1 (v13.2): everything simulate_vxx_overlay used to rec…
    def _build_vxx_context(self, daily_open: pd.DataFrame,
                           daily_close: pd.DataFrame) -> dict | None:
        """L-1 (v13.2): everything simulate_vxx_overlay used to recompute for
        EVERY month — the date-aligned VIX/VXX series, the 20-day VIX moving
        average and the SPY monthly-close trend — is constant for a given
        daily frame. Building it once per backtest is bit-identical (proven
        by tests) and removes an O(months x history) hotspot. Lives on
        RiskManager because simulate_vxx_overlay (also a RiskManager method)
        falls back to building it per call when no context is supplied.

        Returns None when ^VIX / VXX / SPY are not all available (the overlay
        then reports N/A, as before).
        """
        if not all(c in daily_close.columns for c in ("^VIX", "SPY")) \
                or "VXX" not in daily_open.columns or "VXX" not in daily_close.columns:
            return None
        vix_close = daily_close["^VIX"].dropna()
        vxx_open = daily_open["VXX"].dropna()
        vxx_close = daily_close["VXX"].dropna()
        common_idx = vix_close.index.intersection(vxx_close.index).intersection(vxx_open.index)
        vix_close = vix_close.loc[common_idx]
        vxx_open = vxx_open.loc[common_idx]
        vxx_close = vxx_close.loc[common_idx]
        vix_ma20 = vix_close.rolling(window=20, min_periods=5).mean()
        # L-2: monthly closes keyed by their ACTUAL last trading day.
        # v14.7 S3: on a sorted, duplicate-free daily index the last trading
        # day of each month is just `~per.duplicated(keep='last')` — one
        # vectorised mask instead of a per-month `.index[per == p]` scan.
        # Names are reset to None so the result is bit-identical to the
        # dict-built Series it replaces (oracle-proven); anything unsorted
        # or duplicated takes the legacy path.
        spy_daily = daily_close["SPY"].dropna()
        per = spy_daily.index.to_period("M")
        if spy_daily.index.is_monotonic_increasing and not spy_daily.index.has_duplicates:
            month_close = spy_daily[~per.duplicated(keep="last")]
            month_close.name = None
            month_close.index = month_close.index.rename(None)
        else:
            month_close = pd.Series(
                {spy_daily.index[per == p][-1]: spy_daily.loc[spy_daily.index[per == p][-1]]
                 for p in sorted(set(per))}
            )
        month_sma = month_close.rolling(self.cfg.trend_sma_window).mean()
        return {"vix_close": vix_close, "vxx_open": vxx_open, "vxx_close": vxx_close,
                "vix_ma20": vix_ma20, "month_close": month_close, "month_sma": month_sma}

    # · compute_leverage_cap — Trend-based leverage cap for the trade month, decided…
    def compute_leverage_cap(self, spy_monthly_close: pd.Series, month_str: str, is_short: bool = False) -> float:
        """Trend-based leverage cap for the trade month, decided from the last
        COMPLETED month (knowable at the entry open).

        v13 R-1 crash guard: a completed-month SPY return below
        cfg.crash_guard_1m_ret de-risks immediately even if the 10m SMA is
        still rising — the SMA alone reacts one month later in fast crashes.
        """
        cfg = self.cfg
        prev_month_str = (pd.Timestamp(month_str) - pd.DateOffset(months=1)).strftime("%Y-%m")

        # v14.7 S1: the rolling SMA/ROC/strftime table is served from the
        # small identity-keyed LRU (_spy_trend_table) instead of being
        # rebuilt on every call; row values are the _scalar floats the old
        # per-call .loc reads produced (oracle-proven identical).
        row = _spy_trend_table(spy_monthly_close, cfg.trend_sma_window,
                               cfg.trend_roc_window).get(prev_month_str)
        if row is None:
            return cfg.max_leverage

        close, sma_v, roc_v, roc1_v = row

        lt_up = pd.notna(sma_v) and pd.notna(close) and close > sma_v
        st_up = pd.notna(roc_v) and roc_v > 0
        crash = (cfg.crash_guard and pd.notna(roc1_v)
                 and roc1_v < cfg.crash_guard_1m_ret)

        if is_short:
            return cfg.max_leverage if (not lt_up and not st_up) else cfg.min_leverage

        if lt_up and st_up and not crash: return cfg.max_leverage
        if lt_up and not st_up:           return cfg.bull_pullback_lev
        if not lt_up and st_up:           return cfg.v_recovery_lev
        return cfg.bear_market_lev

    # · simulate_vxx_overlay — VXX crash-hedge sleeve for one trade month.
    def simulate_vxx_overlay(self, signal, daily_open, daily_close, spy_monthly_close,
                             vxx_ctx: dict | None = None):
        """VXX crash-hedge sleeve for one trade month.

        v13 fixes (audit L-2 + patch bug):
        * m_vxx_open / m_vxx_close are explicitly sliced from the common
          index — the 'm_vxx_open not defined' NameError from the hand-applied
          patch cannot occur here.
        * spy_trend_down uses ONLY months completed as of each decision day
          (last trading day <= decision day). The old calendar-month lookup
          read the current month's FINAL close, which does not exist yet at a
          mid-month decision.
        * per-trade returns are COMPOUNDED (not summed) and each round trip
          pays cfg.vxx_cost_bps.

        v13.2 L-1: the aligned VIX/VXX series, the 20-day VIX MA and the SPY
        monthly-close trend are constant for a given daily frame, so they can
        be computed ONCE per backtest and passed in as `vxx_ctx`
        (Backtester._build_vxx_context). When vxx_ctx is None the context is
        built per call — bit-identical, just slower (backward compatible).

        v14.7 S2: the day loop runs on POSITIONAL numpy reads over the shared
        aligned index (_vxx_overlay_fast) when the month slices are aligned
        and the month-close index is sorted and unique; anything else falls
        back to the verbatim legacy label-based loop (_vxx_overlay_loop).
        Both paths are oracle-proven bit-identical on real data.

        v13.2 H-4: the entry gate formerly labelled "term_structure_stress"
        compares spot VIX with its own 20-day moving average (see
        resolve_vix_spot_ma20_ratio; no VIX futures data is used anywhere).
        """
        cfg = self.cfg
        regime = signal.get("scenario_key", "")

        if vxx_ctx is None:
            vxx_ctx = self._build_vxx_context(daily_open, daily_close)
        if vxx_ctx is None:
            return False, 0.0, "N/A"
        vix_close = vxx_ctx["vix_close"]
        vxx_open = vxx_ctx["vxx_open"]
        vxx_close = vxx_ctx["vxx_close"]
        vix_ma20 = vxx_ctx["vix_ma20"]
        month_close = vxx_ctx["month_close"]
        month_sma = vxx_ctx["month_sma"]

        year, mon = map(int, signal["month"].split("-"))
        m_start = pd.Timestamp(year=year, month=mon, day=1)
        m_end = m_start + pd.offsets.MonthEnd(1)

        m_vix = vix_close.loc[m_start:m_end]
        m_vxx_open = vxx_open.loc[m_start:m_end]      # FIX: always defined
        m_vxx_close = vxx_close.loc[m_start:m_end]    # FIX: always defined

        if m_vix.empty or m_vxx_open.empty or m_vxx_close.empty or len(m_vix) < 2:
            return False, 0.0, "N/A"

        mc_idx = month_close.index
        if (m_vix.index.equals(m_vxx_open.index)
                and m_vix.index.equals(m_vxx_close.index)
                and mc_idx.is_monotonic_increasing and not mc_idx.has_duplicates):
            trade_active, comp_mult = self._vxx_overlay_fast(
                m_vix, m_vxx_open, m_vxx_close, vix_ma20, month_close,
                month_sma, regime, cfg)
        else:
            trade_active, comp_mult = self._vxx_overlay_loop(
                m_vix, m_vxx_open, m_vxx_close, vix_ma20, month_close,
                month_sma, regime, cfg)

        total_trade_ret = comp_mult - 1.0 if trade_active else 0.0

        # Diagnostic-only labels (hardcoded crisis calendar, not used in PnL).
        crisis_dates = ["2008-10-01", "2015-08-01", "2018-12-01", "2020-03-01", "2022-06-01"]
        is_crisis = any(abs((pd.Timestamp(signal["month"]) - pd.Timestamp(d)).days) < 45 for d in crisis_dates)
        regime_label = "CRISIS" if is_crisis else "CALM"

        return (trade_active, total_trade_ret, regime_label) if trade_active else (False, 0.0, regime_label)

    # · _vxx_overlay_fast — v14.7 S2: the day loop on positional numpy reads.
    def _vxx_overlay_fast(self, m_vix, m_vxx_open, m_vxx_close, vix_ma20,
                          month_close, month_sma, regime, cfg):
        """v14.7 S2: simulate_vxx_overlay's day loop on positional numpy
        reads.  Caller guarantees: the three month slices share one aligned
        index and month_close's index is sorted+unique.  The last completed
        month uses searchsorted(side='right'); arithmetic and float()
        conversion points mirror the legacy loop exactly (oracle-proven
        bit-identical)."""
        vix = m_vix.to_numpy()
        vxx_o = m_vxx_open.to_numpy()
        vxx_c = m_vxx_close.to_numpy()
        ma = vix_ma20.reindex(m_vix.index).to_numpy()
        mc_vals = month_close.to_numpy()
        ms_vals = month_sma.to_numpy()
        mc_idx = month_close.index.to_numpy()
        ma_ratio = resolve_vix_spot_ma20_ratio(cfg)
        regime_ok = regime in tuple(cfg.vxx_allowed_regimes)

        in_position, entry_price, entry_idx = False, 0.0, -1
        max_price = 0.0
        comp_mult = 1.0
        trade_active = False

        def _net_ret(entry: float, exit_: float) -> float:
            r = (exit_ - entry) / entry if entry > 0 else 0.0
            return r - cfg.vxx_cost_bps / 10000.0   # R-4: round-trip cost

        for i in range(1, len(m_vix)):
            if in_position:
                exit_signal = False
                current_price = float(vxx_c[i - 1])
                max_price = max(max_price, current_price)

                if current_price >= entry_price * (1 + cfg.vxx_profit_take_pct):
                    exit_signal = True
                if current_price <= max_price * (1 - cfg.vxx_trailing_stop_pct):
                    exit_signal = True
                if i - entry_idx >= cfg.vxx_max_hold_days:
                    exit_signal = True

                if exit_signal:
                    exit_price = float(vxx_o[i])
                    comp_mult *= (1.0 + _net_ret(entry_price, exit_price))
                    in_position = False

            if not in_position:
                vix_prev = float(vix[i - 1])
                vix_extreme = vix_prev > cfg.vix_trigger_level
                vix_spike = vix_prev > cfg.vxx_extreme_vix

                vix_ma_val = ma[i - 1]
                vix_spot_vs_ma20_stress = (
                    pd.notna(vix_ma_val) and vix_ma_val > 0
                    and (vix_prev / vix_ma_val) > ma_ratio
                )

                vix_jump = False
                if i >= 2:
                    vix_prev2 = float(vix[i - 2])
                    if vix_prev2 > 0:
                        vix_jump = (vix_prev / vix_prev2 - 1.0) > cfg.vxx_spike_pct

                # L-2 FIX: only months COMPLETED as of the decision day count.
                pos = mc_idx.searchsorted(m_vix.index[i - 1].to_datetime64(), side="right")
                spy_trend_down = False
                if pos:
                    ref_close = float(mc_vals[pos - 1])
                    ref_sma = float(ms_vals[pos - 1])
                    if pd.notna(ref_close) and pd.notna(ref_sma):
                        spy_trend_down = ref_close < ref_sma

                entry_trigger = (
                    (regime_ok and vix_spot_vs_ma20_stress and (vix_extreme or vix_jump) and spy_trend_down)
                    or (vix_spike and vix_spot_vs_ma20_stress and spy_trend_down)
                )

                if entry_trigger:
                    entry_price = float(vxx_o[i])
                    max_price = entry_price
                    entry_idx = i
                    in_position = True
                    trade_active = True

        if in_position:
            exit_price = float(vxx_c[-1])
            comp_mult *= (1.0 + _net_ret(entry_price, exit_price))
        return trade_active, comp_mult

    # · _vxx_overlay_loop — the verbatim v14.6.2 label-based day loop (fallback).
    def _vxx_overlay_loop(self, m_vix, m_vxx_open, m_vxx_close, vix_ma20,
                          month_close, month_sma, regime, cfg):
        """The verbatim v14.6.2 label-based day loop, kept as the fallback for
        inputs that fail the fast path's alignment guards (unaligned month
        slices, or an unsorted/duplicated month-close index).  Relocated
        unchanged from simulate_vxx_overlay; oracle-proven identical."""
        in_position, entry_price, entry_idx = False, 0.0, -1
        max_price = 0.0
        comp_mult = 1.0
        trade_active = False

        def _net_ret(entry: float, exit_: float) -> float:
            r = (exit_ - entry) / entry if entry > 0 else 0.0
            return r - cfg.vxx_cost_bps / 10000.0   # R-4: round-trip cost

        for i in range(1, len(m_vix)):
            idx = m_vix.index[i]
            prev_idx = m_vix.index[i - 1]

            if in_position:
                exit_signal = False
                current_price = float(m_vxx_close.loc[prev_idx])
                max_price = max(max_price, current_price)

                if current_price >= entry_price * (1 + cfg.vxx_profit_take_pct):
                    exit_signal = True
                if current_price <= max_price * (1 - cfg.vxx_trailing_stop_pct):
                    exit_signal = True
                if i - entry_idx >= cfg.vxx_max_hold_days:
                    exit_signal = True

                if exit_signal:
                    exit_price = float(m_vxx_open.loc[idx])
                    comp_mult *= (1.0 + _net_ret(entry_price, exit_price))
                    in_position = False

            if not in_position:
                vix_prev = float(m_vix.loc[prev_idx])
                vix_extreme = vix_prev > cfg.vix_trigger_level
                vix_spike = vix_prev > cfg.vxx_extreme_vix

                vix_ma_val = vix_ma20.loc[prev_idx] if prev_idx in vix_ma20.index else np.nan
                vix_spot_vs_ma20_stress = (
                    pd.notna(vix_ma_val) and vix_ma_val > 0
                    and (vix_prev / vix_ma_val) > resolve_vix_spot_ma20_ratio(cfg)
                )

                vix_jump = False
                if i >= 2:
                    vix_prev2 = float(m_vix.loc[m_vix.index[i - 2]])
                    if vix_prev2 > 0:
                        vix_jump = (vix_prev / vix_prev2 - 1.0) > cfg.vxx_spike_pct

                regime_ok = regime in tuple(cfg.vxx_allowed_regimes)

                # L-2 FIX: only months COMPLETED as of the decision day count.
                ends = month_close.index[month_close.index <= prev_idx]
                spy_trend_down = False
                if len(ends):
                    ref = ends[-1]
                    ref_close = self._scalar(month_close.loc[ref])
                    ref_sma = self._scalar(month_sma.loc[ref])
                    if pd.notna(ref_close) and pd.notna(ref_sma):
                        spy_trend_down = ref_close < ref_sma

                entry_trigger = (
                    (regime_ok and vix_spot_vs_ma20_stress and (vix_extreme or vix_jump) and spy_trend_down)
                    or (vix_spike and vix_spot_vs_ma20_stress and spy_trend_down)
                )

                if entry_trigger:
                    entry_price = float(m_vxx_open.loc[idx])
                    max_price = entry_price
                    entry_idx = i
                    in_position = True
                    trade_active = True

        if in_position:
            exit_price = float(m_vxx_close.iloc[-1])
            comp_mult *= (1.0 + _net_ret(entry_price, exit_price))
        return trade_active, comp_mult


# ═══════════════════════════════════════════════════════════════════════════
#  § 16 · STATISTICS & TRIAL LEDGER
# ═══════════════════════════════════════════════════════════════════════════
# ── § 16.1 · annualized_sharpe
def annualized_sharpe(monthly_returns: pd.Series, rf: float = 0.0) -> float:
    excess = monthly_returns - rf / 12
    if excess.std() == 0: return 0.0
    return float(np.sqrt(12) * excess.mean() / excess.std())
# ── § 16.2 · annualized_sortino
def annualized_sortino(monthly_returns: pd.Series, rf: float = 0.0) -> float:
    excess = monthly_returns - rf / 12
    downside = excess[excess < 0].std()
    if downside == 0: return float("inf")
    return float(np.sqrt(12) * excess.mean() / downside)

# ── § 16.3 · max_drawdown ── v13.2 reliability fix: a monotonically non-falling equity curve (…
def max_drawdown(monthly_returns: pd.Series) -> tuple[float, str, str]:
    """v13.2 reliability fix: a monotonically non-falling equity curve (no
    drawdown at all) made `wealth[:idx]` empty and crashed idxmax() with
    "attempt to get argmax of an empty sequence" (v13.1 crashed on any
    all-positive monthly history — e.g. short OOS windows)."""
    if monthly_returns.empty:
        # v14.7 4d: NaN, not 0.0 — "no drawdown" would look like a real
        # result on an empty history.
        return float("nan"), "", ""
    wealth = (1 + monthly_returns).cumprod()
    peak = wealth.cummax()
    dd = (wealth - peak) / peak
    idx = dd.idxmin()
    prior = wealth.loc[:idx]
    peak_date = str(prior.idxmax()) if len(prior) else str(wealth.index[0])
    return float(dd.min() * 100), str(idx), peak_date

# ── § 16.4 · calmar
def calmar(monthly_returns: pd.Series) -> float:
    # v14.7 4d: an empty history has no Calmar — NaN instead of crashing on
    # the 12/len exponent (or pretending via a number).
    if len(monthly_returns) == 0:
        return float("nan")
    mdd, _, _ = max_drawdown(monthly_returns)
    if mdd == 0: return float("inf")
    ann_ret = (1 + monthly_returns).prod() ** (12 / len(monthly_returns)) - 1
    return ann_ret / abs(mdd / 100)

# ── § 16.5 · alpha_beta
def alpha_beta(strategy_rets: pd.Series, spy_rets: pd.Series, rf: float = 0.0) -> dict:
    # v14.7 4d: degenerate/failed inputs return NaN + a status instead of a
    # plausible-looking {0, 0, 0} — callers render "n/a" when a value is
    # NaN or a status is present.  The happy path is unchanged.
    df = pd.concat([strategy_rets, spy_rets], axis=1).dropna()
    df.columns = ['strat', 'spy']
    if len(df) < 2:
        return {"alpha_annualized_pct": float("nan"), "beta": float("nan"),
                "r_squared": float("nan"), "status": "insufficient_overlap"}
    if df['spy'].std() == 0:
        return {"alpha_annualized_pct": float("nan"), "beta": float("nan"),
                "r_squared": float("nan"), "status": "degenerate_zero_variance"}
    y = df['strat'].values - rf / 12
    x = df['spy'].values - rf / 12
    x = np.vstack([np.ones(len(x)), x]).T
    try:
        coeffs = np.linalg.lstsq(x, y, rcond=None)[0]
        alpha_m = coeffs[0]
        beta = coeffs[1]
        y_pred = x @ coeffs
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        return {"alpha_annualized_pct": float(alpha_m * 12 * 100),
                "beta": float(beta), "r_squared": float(r_squared)}
    except (np.linalg.LinAlgError, ValueError):
        return {"alpha_annualized_pct": float("nan"), "beta": float("nan"),
                "r_squared": float("nan"), "status": "regression_failed"}

# ── § 16.6 · block_bootstrap_ci
def block_bootstrap_ci(monthly_returns: pd.Series, block_size: int = 3, n_resamples: int = 5000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    n = len(monthly_returns)
    if n == 0:
        # v14.7 4d: NaN + status instead of {0, 0, 0} — an empty input has
        # no confidence interval, and zeros looked like a real one.
        return {"median_cum_pct": float("nan"), "p5_cum_pct": float("nan"),
                "p95_cum_pct": float("nan"), "status": "empty_input"}
    r = monthly_returns.values
    cum_returns = np.empty(n_resamples)
    p = 1.0 / block_size
    for i in range(n_resamples):
        idx = []
        while len(idx) < n:
            start = rng.integers(0, n)
            block_len = rng.geometric(p)
            idx.extend([(start + k) % n for k in range(block_len)])
        sampled = r[idx[:n]]
        cum_returns[i] = np.prod(1 + sampled) - 1
    return {
        "median_cum_pct": float(np.median(cum_returns) * 100),
        "p5_cum_pct": float(np.percentile(cum_returns, 5) * 100),
        "p95_cum_pct": float(np.percentile(cum_returns, 95) * 100),
    }

# ── § 16.7 · extract_tickers
def extract_tickers(asset_list: Iterable[str]) -> list[str]:
    tickers = []
    for item in asset_list:
        match = re.search(r"\(([^)]+)\)", item)
        if match:
            for symbol in match.group(1).split("/"):
                clean = symbol.strip()
                if clean and re.match(r"^[A-Za-z0-9\.\-\^]+$", clean):
                    tickers.append(clean)
    return tickers

# ── § 16.8 · parse_signals
def parse_signals(df: pd.DataFrame) -> list[dict[str, Any]]:
    # v14.7 S6: iterrows -> per-column lists (zip); one vectorised date
    # parse + month shift instead of one per row.  Column access semantics
    # are preserved exactly: required columns raise KeyError, optional ones
    # default per-row exactly like Series.get(key, default).
    n = len(df)
    if n == 0:
        return []
    months = (pd.to_datetime(df["date"]) + pd.DateOffset(months=1)).dt.strftime("%Y-%m").tolist()

    def _col(name: str, default):
        return df[name].tolist() if name in df.columns else [default] * n

    signals = []
    for m, lo, sh, sk, rg, conf, ruc, dom, clv, rm, fin in zip(
            months,
            df["long"].tolist(), df["short"].tolist(),
            df["scenario_key"].tolist(), df["regime"].tolist(),
            _col("confidence", 1.0), _col("runner_up_confidence", 0.0),
            _col("dominance", 0.0), _col("conviction_leverage", 1.0),
            _col("regime_months", 1), _col("financing_rate", np.nan)):
        signals.append({
            "month": m,
            "longs": extract_tickers(lo),
            "shorts": extract_tickers(sh),
            "scenario_key": sk, "regime": rg,
            "confidence": float(conf),
            "runner_up_confidence": float(ruc),
            "dominance": float(dom),
            "conviction_leverage": float(clv),
            "regime_months": int(rm),
            # v13 R-4: point-in-time policy rate for the financing charge.
            "financing_rate": float(fin) if pd.notna(fin) else np.nan,
        })
    return signals

# v13.2 L-1 → v14.4 U11: download failures are recorded into the active
# diagnostics sink (the CLI sink aliases these module globals) instead of
# being swallowed; the final report prints them so an empty backtest is
# explainable.


# ── § 16.9 · _cfg_fingerprint
def _cfg_fingerprint(cfg: Config) -> str:
    d = asdict(cfg)
    d.pop("fred_api_key", None)
    return hashlib.sha256(json.dumps(d, sort_keys=True,
                                     default=str).encode()).hexdigest()


# ── § 16.10 · _record_trial
def _record_trial(kind: str, cfg: Config, results: pd.DataFrame) -> None:
    # v14.4 U11: trials go to the ACTIVE diagnostics sink — the CLI default
    # sink aliases the module-global TRIAL_LEDGER, while an API call's
    # private sink returns them in the result dict instead of mutating it.
    if results is None or results.empty:
        return
    r = results["Net Portfolio Return %"] / 100.0
    _ledger_append({
        "ts": datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"),
        "kind": kind,
        "cfg_sha256": _cfg_fingerprint(cfg),
        "n_months": int(len(results)),
        "first_month": str(results["Month"].iloc[0]),
        "last_month": str(results["Month"].iloc[-1]),
        "cum": round(float((1 + r).prod() - 1), 6),
        "sharpe": round(annualized_sharpe(r), 4),
    })


# ── § 16.10.1 · _ledger_append — ONE place for the ledger's cap semantics.
def _ledger_append(trial: dict) -> None:
    """Append one trial record to the ACTIVE sink's ledger with the cap
    semantics (v14.4 U11).  Shared by _record_trial and the grid-search
    merge so pooled worker trials land exactly like sequential ones."""
    ledger = _diag().trials
    if len(ledger) >= TRIAL_LEDGER_MAX:
        del ledger[:len(ledger) // 2]
    ledger.append(trial)


# ── § 16.11 · trial_ledger_summary ── H6: what has actually been TRIED in this process — the audit…
def trial_ledger_summary() -> dict:
    """H6: what has actually been TRIED in this process — the audit trail a
    validation claim has to reconcile against."""
    if not TRIAL_LEDGER:
        return {"n_trials": 0}
    by_kind: dict[str, int] = {}
    for t in TRIAL_LEDGER:
        by_kind[t["kind"]] = by_kind.get(t["kind"], 0) + 1
    return {
        "n_trials": len(TRIAL_LEDGER),
        "by_kind": by_kind,
        "distinct_configs": len({t["cfg_sha256"] for t in TRIAL_LEDGER}),
        "window": (TRIAL_LEDGER[0]["ts"], TRIAL_LEDGER[-1]["ts"]),
        "n_positive_sharpe": sum(1 for t in TRIAL_LEDGER if t["sharpe"] > 0),
    }


# ── § 16.12 · deflated_sharpe ── v14.5 FIX-3 (PREREG C03): Bailey–López de Prado DSR.
def deflated_sharpe(monthly_returns: pd.Series,
                    trial_sharpes: Sequence[float] | None = None) -> dict:
    """v14.5 FIX-3 (PREREG C03): Bailey & López de Prado deflated Sharpe
    ratio, per-period (monthly, NON-annualised) SR throughout:

        DSR = Φ((SR − SR0)·√(T−1) / √(1 − skew·SR + (kurt−1)/4·SR²))
        SR0 = √Var[SR_trials] · ((1−g)·Φ⁻¹(1−1/N) + g·Φ⁻¹(1−1/(N·e)))

    with g the Euler–Mascheroni constant, kurt the RAW kurtosis (pandas
    .kurt() is excess; raw = excess + 3) and T the number of months.
    `trial_sharpes` are the per-trial Sharpes the ledger really holds —
    _record_trial (§16.10) stores them ANNUALISED, so they are converted
    to the monthly unit here (÷√12) to match SR.  N = len(trial_sharpes);
    an empty ledger (or N=1) gives SR0 = 0 — no trial count is invented.
    Degenerate inputs (T < 2 or zero variance) return dsr = 0.0.

    Returns {"dsr", "sr", "sr0", "n_trials", "skew", "kurt_raw",
    "t_months", "degenerate"} — dsr is a probability in [0, 1]."""
    r = monthly_returns.dropna().astype(float)
    t_months = int(len(r))
    out = {"dsr": 0.0, "sr": 0.0, "sr0": 0.0, "n_trials": 1, "skew": 0.0,
           "kurt_raw": 0.0, "t_months": t_months, "degenerate": False}
    if t_months < 2 or float(r.std()) == 0.0:
        out["degenerate"] = True
        return out
    sr = float(r.mean() / r.std())               # per-period (monthly) SR
    skew = float(r.skew())
    kurt_raw = float(r.kurt() + 3.0)             # raw kurtosis (normal = 3)
    sharpes = [float(s) for s in (trial_sharpes or []) if pd.notna(s)]
    n = max(1, len(sharpes))
    out.update({"sr": sr, "skew": skew, "kurt_raw": kurt_raw, "n_trials": n})
    sr0 = 0.0
    if n >= 2:
        per_period = [s / math.sqrt(12.0) for s in sharpes]   # annualised -> monthly
        var_sr = float(np.var(per_period, ddof=1))
        if var_sr > 0.0:
            g = 0.5772156649015329               # Euler–Mascheroni
            nd = NormalDist()
            z1 = nd.inv_cdf(1.0 - 1.0 / n)
            z2 = nd.inv_cdf(1.0 - 1.0 / (n * math.e))
            sr0 = math.sqrt(var_sr) * ((1.0 - g) * z1 + g * z2)
    out["sr0"] = sr0
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr + (kurt_raw - 1.0) / 4.0 * sr * sr))
    z = (sr - sr0) * math.sqrt(t_months - 1.0) / denom
    out["dsr"] = float(NormalDist().cdf(z))
    return out


# ── § 17.1 · _snapshot_daily_slice ── v13.3 M-1: the frozen daily frame restricted to `tickers` and
# ══════════════════════════════════════════════════════════════════════════════
#  § 17 · PRICE DATA — lazy yfinance, ONE download per run (U4/S2)
# ══════════════════════════════════════════════════════════════════════════════
def _snapshot_daily_slice(tickers: Iterable[str], start_date: str,
                          end_date: str) -> pd.DataFrame | None:
    """v13.3 M-1: the frozen daily frame restricted to `tickers` and
    [start_date, end_date], preserving yf.download's (Price, Ticker)
    MultiIndex layout — or None when the snapshot cannot serve it."""
    daily = _snapshot_daily()
    if daily is None:
        return None
    wanted = set(tickers)
    try:
        mask = daily.columns.get_level_values(-1).isin(wanted)
        sel = daily.loc[:, mask]
        sel = sel.loc[pd.Timestamp(start_date):pd.Timestamp(end_date)]
        if not isinstance(sel.columns, pd.MultiIndex) or "Close" not in set(
                sel.columns.get_level_values(0)):
            return None
        if sel["Close"].dropna(how="all").empty:
            return None
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    return None if sel.empty else sel


# ── v14.4 U4/D2: lazy yfinance import + its cache directory ────────────────────
# ── § 17.2 · _load_yf ── Import yfinance on FIRST use only (U4). Returns the module or Non…
def _load_yf():
    """Import yfinance on FIRST use only (U4).  Returns the module or None;
    the real import error is kept in _YF_IMPORT_ERROR so the failure text is
    the actual upstream message.  D2: yfinance's own timezone cache is
    pointed at a per-process temporary directory (guarded with getattr — the
    setter name differs across versions) which atexit removes."""
    global yf, _YF_IMPORT_ERROR, _YF_TRIED, _YF_CACHE_DIR
    if _YF_TRIED:
        return yf
    _YF_TRIED = True
    try:
        import yfinance as _yf_mod
    except Exception as e:               # the real reason (ImportError et al.)
        _YF_IMPORT_ERROR = e
        yf = None
        return None
    yf = _yf_mod
    try:
        import atexit
        import shutil
        import tempfile
        _YF_CACHE_DIR = tempfile.mkdtemp(prefix="meds-yf-cache-")
        setter = getattr(_yf_mod, "set_tz_cache_location", None)
        if callable(setter):
            setter(_YF_CACHE_DIR)
        atexit.register(shutil.rmtree, _YF_CACHE_DIR, ignore_errors=True)
    except (OSError, TypeError, AttributeError):
        _YF_CACHE_DIR = None             # cache stays wherever yfinance puts it
    return yf


# ── § 17.3 · _YfLogCapture ── v14.4 section 3: capture yfinance's REAL logger output (rate limi…
class _YfLogCapture(logging.Handler):
    """v14.4 section 3: capture yfinance's REAL logger output (rate limit,
    delisted, timezone, JSON decode) during ONE download call instead of
    silencing the logger process-wide."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(record.getMessage())
        except Exception as e:            # formatting a bad record must not kill a run
            if not isinstance(e, (ValueError, TypeError, KeyError)):
                raise


# ── § 17.4 · _safe_yf_download ── v14.4: ONE price fetch with real-error capture.
def _safe_yf_download(tickers: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """v14.4: ONE price fetch with real-error capture.

    * yfinance is imported lazily; a missing package is reported with the
      real import error and degrades to the cache / snapshot tiers.
    * yf.download rarely raises — it returns an empty frame and records
      per-ticker reasons.  Those are captured from yfinance.shared._ERRORS
      (guarded getattr for version differences) AND by a temporary logging
      handler attached to the 'yfinance' logger for the duration of the call
      (propagation to stderr is suppressed only while the handler is
      attached, so the messages are REPORTED verbatim instead of lost).
    * The verified object cache is ONE gzip JSON file (D3, no executable
      object deserialization), written only under MEDS_CACHE=1.
    * The frozen snapshot remains the last offline fallback.
    """
    if not tickers:
        return pd.DataFrame()
    diag = _diag()
    tickers = list(tickers)
    request_desc = f"tickers={sorted(set(tickers))}  window={start_date}..{end_date}"
    raw_data = pd.DataFrame()
    # v14 FIX-3 → v14.4 D3: verified price cache - the key covers the tickers
    # AND the exact window, so a re-run tomorrow (new end date) refreshes.
    _cache = VerifiedCache()
    _pkey = ("yahoo/" + hashlib.sha256(
        ("|".join(sorted(set(tickers))) + f"|{start_date}|{end_date}")
        .encode("utf-8")).hexdigest()[:16] + ".json.gz")
    # v13.3 M-3: --snapshot / MEDS_FORCE_SNAPSHOT skips the live call so
    # offline runs are deterministic.
    if not FORCE_SNAPSHOT:
        yf_mod = _load_yf()
        if yf_mod is None:
            diag.yf_errors.append(_describe_failure(
                "Yahoo (yfinance)", request_desc, exc=_YF_IMPORT_ERROR,
                body="yfinance is not installed — degrading to the verified "
                     "cache / frozen snapshot price tiers"))
        else:
            shared = getattr(yf_mod, "shared", None)
            pre_errors = dict(getattr(shared, "_ERRORS", {}) or {})
            capture = _YfLogCapture()
            lg = logging.getLogger("yfinance")
            old_propagate = lg.propagate
            lg.addHandler(capture)
            lg.propagate = False          # scoped: only during THIS call
            try:
                raw_data = yf_mod.download(tickers, start=start_date, end=end_date,
                                           progress=False, auto_adjust=True)
            except Exception as e:         # reported verbatim, then degrade
                diag.yf_errors.append(_describe_failure(
                    "Yahoo (yfinance)", request_desc, exc=e))
                raw_data = pd.DataFrame()
            finally:
                lg.removeHandler(capture)
                lg.propagate = old_propagate
            # per-ticker messages from yfinance.shared._ERRORS (new ones only)
            post_errors = getattr(shared, "_ERRORS", {}) or {}
            if isinstance(post_errors, dict):
                for t, msg in list(post_errors.items()):
                    if t in tickers and post_errors.get(t) != pre_errors.get(t):
                        diag.yf_errors.append(_describe_failure(
                            "Yahoo (yfinance)",
                            f"ticker={t}  window={start_date}..{end_date}",
                            body=str(msg)))
            for msg in capture.records:
                diag.yf_errors.append(_describe_failure(
                    "Yahoo (yfinance)", request_desc, body=str(msg)))
            if (raw_data is None or raw_data.empty) and not diag.yf_errors:
                diag.yf_errors.append(_describe_failure(
                    "Yahoo (yfinance)", request_desc,
                    body="yf.download returned an empty frame with no recorded "
                         "per-ticker message"))
            if raw_data is None:
                raw_data = pd.DataFrame()
    if raw_data is None or raw_data.empty:
        # v14 FIX-3 → v14.4 D3: live Yahoo unavailable - try the verified
        # meds_cache (gzip JSON frame) before the frozen snapshot.
        got = None if FORCE_SNAPSHOT else _cache.get_frame(_pkey)
        if got is not None:
            cached = got[0]
            if cached is not None and not cached.empty:
                diag.price_notes.append(
                    f"Yahoo Finance unavailable for {sorted(set(tickers))} "
                    f"({start_date}..{end_date}) - serving the verified "
                    f"meds_cache copy ({cached.index.min().date()}.."
                    f"{cached.index.max().date()}).")
                return cached
        # v13.3 M-1: live Yahoo unavailable (or forced off) — fall back to
        # the frozen snapshot before giving up.
        snap = _snapshot_daily_slice(tickers, start_date, end_date)
        if snap is not None:
            diag.price_notes.append(
                f"Yahoo Finance unavailable for {sorted(set(tickers))} "
                f"({start_date}..{end_date}) — serving "
                f"{snap.index.min().date()}..{snap.index.max().date()} from the "
                f"frozen snapshot.")
            return snap
        return pd.DataFrame()
    if len(tickers) == 1 and not isinstance(raw_data.columns, pd.MultiIndex):
        # v14.4 B22: recent yfinance returns MultiIndex (Price, Ticker) even
        # for one ticker; older builds need the promotion.  FIX-2 (v14.5):
        # skip the promotion when yfinance ALREADY returned a MultiIndex —
        # `pd.Index` also matches MultiIndex, so the old guard re-wrapped it.
        raw_data.columns = pd.MultiIndex.from_product([raw_data.columns, tickers])
    if not FORCE_SNAPSHOT and not raw_data.empty:
        try:
            _cache.put_frame(_pkey, raw_data)
        except (OSError, ValueError, TypeError) as e:
            diag.yf_errors.append(_describe_failure(
                "cache", f"entry={_pkey}", exc=e))
    return raw_data


# ── v14.4 S2/U10: ONE shared price frame per run ─────────────────────────────
# The canonical ticker set every consumer of a full run needs (all scenario
# baskets plus the SPY/QQQ/TLT benchmarks, VIX and VXX).  The backtester,
# analyze_ticker_performance and ticker_score all slice THIS frame, so a full
# run performs exactly ONE price download and a second ticker_score call
# performs none.
_CANONICAL_PRICE_TICKERS: tuple[str, ...] = tuple(sorted(
    {t for sc in SCENARIOS for t in extract_tickers(sc.long + sc.short)}
    | {"^VIX", "VXX", "SPY", "QQQ", "TLT"}))


# ── § 17.5 · _get_prices ── S2/U10: price frame served from the in-RAM memo when a cached fra…
def _get_prices(tickers: Iterable[str], start_date: str, end_date: str) -> pd.DataFrame:
    """S2/U10: price frame served from the in-RAM memo when a cached frame
    already covers the requested tickers AND window; otherwise one download
    (which itself degrades to cache / snapshot tiers).  Memo: 1h TTL, lock."""
    want = frozenset(tickers)
    if not want:
        return pd.DataFrame()
    start_ts, end_ts = pd.Timestamp(start_date), pd.Timestamp(end_date)
    with _MEMO_LOCK:
        for key, entry in list(_MEMO.items()):
            if key[0] != "px" or time.monotonic() - entry["ts"] > _MEMO_TTL_SECONDS:
                continue
            v = entry["value"]
            if (want <= v["tickers"] and start_ts >= v["start"]
                    and end_ts <= v["end"]):
                frame = v["frame"]
                try:
                    mask = frame.columns.get_level_values(-1).isin(want)
                    sel = frame.loc[:, mask].loc[start_ts:end_ts]
                    return sel if not sel.empty else frame.loc[:, mask]
                except (KeyError, TypeError, ValueError):
                    break
    frame = _safe_yf_download(sorted(want), start_date, end_date)
    if not frame.empty:
        with _MEMO_LOCK:
            _MEMO[("px", tuple(sorted(want)), start_date, end_date)] = {
                "ts": time.monotonic(),
                "value": {"tickers": frozenset(want), "start": start_ts,
                          "end": end_ts, "frame": frame}}
    return frame


# ── § 17.6 · _engine_price_frame ── S2: the ONE daily frame a full run needs, on the backtester's…
def _engine_price_frame(cfg: Config) -> pd.DataFrame:
    """S2: the ONE daily frame a full run needs, on the backtester's own
    price window (B-8 warmup identical on every code path).
    v14.6 STEP A: the frame is COMPLETENESS-CHECKED (§17.7) and the
    download retried while it comes back PARTIAL (up to 3 attempts total,
    one per window per process) — a truncated Yahoo frame must never
    quietly produce a verdict."""
    start, end = Backtester._price_window(cfg)
    return _get_prices_retried(_CANONICAL_PRICE_TICKERS, start, end, cfg)


# ── § 17.7 · _frame_gaps & friends ── v14.6 STEP A: is the shared frame PARTIAL? ─
#  WHAT "PARTIAL" MEANS HERE (the engine's own judgement, lifted from the
#  month level to the whole frame — no new definition of "missing"):
#  the Backtester (§18.2 `missing_price`) has always flagged months whose
#  LISTED basket tickers had no prices, restricted weights to backed
#  positions and let the readiness report mark BACKTEST_VALIDITY PARTIAL.
#  §17.7 makes the SAME call on the frame BEFORE anything computes a
#  verdict, so a partial frame can be retried (and, if still partial,
#  must FAIL the C13 prerequisite gates instead of producing numbers):
#    missing   a requested ticker with no Close column at all (or all-NaN) —
#              exactly what §18.2 reports per month, aggregated over the run;
#    truncated a requested ticker whose served range fails to span the
#              window: it STARTS after its listing floor (+45d grace) or it
#              ENDS before the run's last needed date (-14d grace for
#              weekends/holidays).  The end side is judged only on frames
#              served LIVE: the verified cache / frozen snapshot end frozen
#              by design (their span is the tier's honest end, already
#              surfaced via price_notes and the M-2 window clip).
_PRICE_LISTING_FLOOR: dict[str, str] = {
    # Earliest date a HEALTHY source serves each canonical ticker.  All 13
    # measured on the live Yahoo frame of 2026-11-03 (window requested from
    # 1997-12-01; each ticker's first served bar = its listing/inception):
    #   SPY 1997-12-01   ^VIX 1997-12-01   XLE/XLI/XLP/XLU/XLY 1998-12-22
    #   QQQ 1999-03-10   TLT 2002-07-30    DBC 2006-02-06   BIL 2007-05-30
    #   VXX 2018-01-25   SGOV 2020-06-01
    # Floors are set ~1 month BEFORE each measured first bar; with the 45d
    # grace a healthy first bar carries ~75d of slack, while a frame
    # truncated to "the last N years" sits years past every floor and flags.
    "SPY": "1993-01-01", "^VIX": "1990-01-01",
    "XLE": "1998-12-01", "XLI": "1998-12-01", "XLP": "1998-12-01",
    "XLU": "1998-12-01", "XLY": "1998-12-01",
    "QQQ": "1999-03-01", "TLT": "2002-07-01", "DBC": "2006-02-01",
    "BIL": "2007-05-01", "VXX": "2018-01-01", "SGOV": "2020-06-01",
}
_FRAME_GRACE_START = 45       # days a first bar may trail its floor/window
_FRAME_GRACE_END = 14         # days the last bar may trail the needed end
_FRAME_RETRY_SPENT: set = set()   # windows whose retry budget is spent (per process)


# ── § 17.7.1 · _price_need_end ── v14.6 STEP A: the last date the run's prices must reach.
def _price_need_end(cfg: Config) -> pd.Timestamp:
    """v14.6 STEP A: the last date a full run's prices must reach — the
    month end of the last COMPLETE trade month at/before output_end (an
    output_end mid-month is a month still trading; the +2m request headroom
    in _price_window is NOT a need).  A frame ending before this is missing
    whole trade months."""
    oe = pd.Timestamp(cfg.output_end)
    me = oe + pd.offsets.MonthEnd(0)
    return me if oe == me else oe - pd.offsets.MonthEnd(1)


# ── § 17.7.2 · _frame_gaps ── v14.6 STEP A: the shared frame's completeness verdict (pure).
def _frame_gaps(frame: pd.DataFrame, requested: Iterable[str],
                start_date: str, end_date: str,
                end_anchor: "pd.Timestamp | None" = None,
                judge_end: bool = True) -> dict:
    """v14.6 STEP A: the completeness verdict for a price frame vs the
    window it was asked to cover.  Pure (no I/O, no printing) so the
    download-retry gate (§17.7 _get_prices_retried), the C13 prerequisite
    gate (§21.4b) and ticker_score (§23.5) all share ONE judgement.

    `end_anchor` overrides the date the data must reach (default: the
    requested end_date); callers pass _price_need_end(cfg) for a full run
    and the decision month end for a ticker_score.  `judge_end=False`
    (offline-served frame) skips the end side only.

    Returns {"partial", "missing": {t: reason}, "truncated": {t: reason},
    "checked", "window", "end_anchor"}.  A ticker with NO listing floor
    (any non-canonical symbol) gets no start-side judgement: its listing
    date is unknowable from here, so only the end side and the SMA window
    sufficiency check (§23.5) guard it — a documented blind spot, never a
    silent guess."""
    want = sorted(set(requested))
    anchor = (pd.Timestamp(end_anchor) if end_anchor is not None
              else pd.Timestamp(end_date))
    out: dict = {"partial": True, "missing": {}, "truncated": {},
                 "checked": want, "window": (str(start_date), str(end_date)),
                 "end_anchor": str(anchor.date())}
    if (frame is None or frame.empty or "Close" not in set(
            frame.columns.get_level_values(0))):
        out["missing"] = {t: "no data returned" for t in want}
        return out
    close = frame["Close"]
    for t in want:
        if t not in close.columns:
            out["missing"][t] = "no data returned"
            continue
        s = close[t].dropna()
        if s.empty:
            out["missing"][t] = "all prices NaN"
            continue
        first, last = pd.Timestamp(s.index.min()), pd.Timestamp(s.index.max())
        why: list[str] = []
        floor = _PRICE_LISTING_FLOOR.get(t)
        if floor is not None:
            exp_first = max(pd.Timestamp(floor), pd.Timestamp(start_date))
            if first > exp_first + pd.Timedelta(days=_FRAME_GRACE_START):
                why.append(f"starts {first.date()} (expected by "
                           f"{exp_first.date()})")
        if judge_end and last < anchor - pd.Timedelta(days=_FRAME_GRACE_END):
            why.append(f"ends {last.date()} (needs through {anchor.date()})")
        if why:
            out["truncated"][t] = "; ".join(why)
    out["partial"] = bool(out["missing"] or out["truncated"])
    return out


# ── § 17.7.3 · _frame_gaps_line ── v14.6 STEP A: one-line summary of a frame's gaps.
def _frame_gaps_line(gaps: dict) -> str:
    """v14.6 STEP A: the one-line summary of a frame's gaps — the missing
    tickers and the date ranges that failed — used by the retry prints and
    the C13 FAIL detail."""
    if not gaps or not gaps.get("partial"):
        return "complete"
    bits: list[str] = []
    if gaps.get("missing"):
        bits.append("missing: " + ", ".join(sorted(gaps["missing"])))
    if gaps.get("truncated"):
        bits.append("truncated: " + "; ".join(
            f"{t} {why}" for t, why in sorted(gaps["truncated"].items())))
    return " · ".join(bits)


# ── § 17.7.4 · _frame_served_live ── v14.6 STEP A: did the live tier serve the frame?
def _frame_served_live() -> bool:
    """v14.6 STEP A: True when nothing in this process has served prices
    from the verified cache / frozen snapshot (both append a price_note
    when they serve, and their frozen ends are by design — no end-side
    judgement for them) and snapshot mode is off."""
    if FORCE_SNAPSHOT:
        return False
    return not any(("meds_cache copy" in n) or ("frozen snapshot" in n)
                   for n in _diag().price_notes)


# ── § 17.7.5 · _memo_put_frame ── v14.6 STEP A: publish a frame to the §17.5 in-RAM memo.
def _memo_put_frame(frame: pd.DataFrame, want: Iterable[str],
                    start_date: str, end_date: str) -> None:
    """v14.6 STEP A: publish a frame to the §17.5 in-RAM memo under the
    exact key format _get_prices writes, so every later consumer in this
    process sees the retried/best frame instead of a PARTIAL first
    attempt (the 'one successful download per run' invariant)."""
    if frame is None or frame.empty:
        return
    tickers = frozenset(want)
    with _MEMO_LOCK:
        _MEMO[("px", tuple(sorted(tickers)), start_date, end_date)] = {
            "ts": time.monotonic(),
            "value": {"tickers": tickers, "start": pd.Timestamp(start_date),
                      "end": pd.Timestamp(end_date), "frame": frame}}


# ── § 17.7.6 · _get_prices_retried ── v14.6 STEP A: the shared frame with REAL bounded retries.
def _get_prices_retried(tickers: Iterable[str], start_date: str, end_date: str,
                        cfg: Config, max_attempts: int = 3,
                        emit: Callable[[str], None] = print) -> pd.DataFrame:
    """v14.6 STEP A: the shared frame (§17.5/§17.6 — ONE download per run)
    with REAL retries on a PARTIAL download.

    Evidence: 1 of 6 real full runs got a truncated Yahoo frame; the engine
    marked it PARTIAL (month-level missing prices), restricted weights —
    but the criterion statuses were still computed and the headline return
    moved.  Now the frame is completeness-checked with §17.7 _frame_gaps
    and the download retried up to `max_attempts` attempts total, paced by
    the existing _API_PACER (short backoff) and re-issued through the
    existing _safe_yf_download.  Real retries only — nothing fabricated,
    nothing patched — and the budget is spent ONCE per window per process
    (_FRAME_RETRY_SPENT), so a full run still performs at most 3 download
    attempts however many consumers slice the shared frame.

    One line is emitted per retry (which attempt was partial + exactly what
    was missing); a still-PARTIAL frame after the last attempt is kept (the
    best of the attempts) and reported, and the callers' verdicts treat it
    as partial: C13 FAILs with the gaps (§21.4b) and ticker_score refuses a
    truncated OWN series or flags price_frame PARTIAL (§23.5)."""
    want = sorted(set(tickers))
    anchor = _price_need_end(cfg)
    spent_key = (tuple(want), start_date, end_date)

    def _gaps(fr: pd.DataFrame, live: bool) -> dict:
        return _frame_gaps(fr, want, start_date, end_date,
                           end_anchor=anchor, judge_end=live)

    n_notes = len(_diag().price_notes)
    frame = _get_prices(want, start_date, end_date)
    live = (len(_diag().price_notes) == n_notes) and not FORCE_SNAPSHOT
    gaps = _gaps(frame, live)
    if (gaps["partial"] and not FORCE_SNAPSHOT
            and spent_key not in _FRAME_RETRY_SPENT):
        _FRAME_RETRY_SPENT.add(spent_key)
        best_frame, best_gaps = frame, gaps

        def _score(fr: pd.DataFrame, g: dict) -> tuple:
            rows = 0 if fr is None or fr.empty else len(fr)
            return (len(g["missing"]) + len(g["truncated"]), -rows)

        best_key = _score(best_frame, best_gaps)
        for attempt in range(2, max_attempts + 1):
            note = _frame_gaps_line(gaps)
            emit(_c(f"  ⚠  price frame PARTIAL on attempt {attempt - 1}/"
                    f"{max_attempts} — {note} — retrying ({attempt}/{max_attempts})",
                    "33"))
            _diag().price_notes.append(
                f"price frame PARTIAL on attempt {attempt - 1}/{max_attempts}: "
                f"{note} — retried")
            _API_PACER.wait()            # the existing pacing helper: short backoff
            n_notes = len(_diag().price_notes)
            frame = _safe_yf_download(want, start_date, end_date)
            live = (len(_diag().price_notes) == n_notes) and not FORCE_SNAPSHOT
            gaps = _gaps(frame, live)
            if not gaps["partial"]:
                best_frame, best_gaps = frame, gaps
                break
            if _score(frame, gaps) < best_key:
                best_frame, best_gaps, best_key = frame, gaps, _score(frame, gaps)
        if best_gaps["partial"]:
            emit(_c(f"  ⚠  price frame STILL PARTIAL after {max_attempts}/"
                    f"{max_attempts} attempts — {_frame_gaps_line(best_gaps)} — "
                    f"C13 prerequisite gates will FAIL and no criterion is "
                    f"counted on this frame", "33"))
            _diag().price_notes.append(
                f"price frame STILL PARTIAL after {max_attempts} attempts: "
                f"{_frame_gaps_line(best_gaps)}")
        frame, gaps = best_frame, best_gaps
        _memo_put_frame(frame, want, start_date, end_date)
    return frame


# ── § 17.8 · price_fingerprint ── v14.6 STEP B: the data fingerprint (print-only) ─
def price_fingerprint(frame: pd.DataFrame) -> dict:
    """v14.6 STEP B: the data fingerprint of a price frame — per ticker the
    row count + first/last date, plus a short hash (first 12 hex chars of
    sha256) of the close data — so two runs whose numbers differ can be
    compared at a glance.  PRINT-ONLY by design: nothing is ever written
    to any file.

    Hash recipe (measured for cross-run stability): sha256 of the frame's
    MONTH-END close panel (resample ME, last — exactly the data the
    engine's monthly decisions consume), restricted to COMPLETE months
    (everything before the current calendar month: the current month's
    last bar is intraday-live — ^VIX updates through the day and would
    drift the hash between two same-day runs), values rounded to 1dp,
    NaN->0, columns in the frame's own order.  Why not the raw daily
    panel: Yahoo serves float-jittery adjusted closes — measured on
    2026-11-03, two back-to-back downloads of the identical window differ
    in 50-85 of 94,601 daily cells at cent precision — while the month-end
    panel at 1dp was bit-identical across all 6 measured download pairs.
    The daily row counts + first/last dates below are exact and do the
    day-level comparison.  Returns {"tickers": {t: {"rows", "first",
    "last"}}, "close_sha256_12", "window": (first, last), "lines"} where
    lines is the aligned CLI block (2 tickers per line, header + hash <=
    12 lines for the 13-ticker canonical frame)."""
    out: dict = {"tickers": {}, "close_sha256_12": None,
                 "window": (None, None), "lines": [
                     "  price frame fingerprint: (no frame)"]}
    if (frame is None or frame.empty or "Close" not in set(
            frame.columns.get_level_values(0))):
        return out
    close = frame["Close"]
    for t in close.columns:
        s = close[t].dropna()
        out["tickers"][t] = {"rows": int(len(s)),
                             "first": str(s.index.min().date()),
                             "last": str(s.index.max().date())}
    out["window"] = (str(close.index.min().date()),
                     str(close.index.max().date()))
    monthly = close.resample(FREQ_ME).last().fillna(0.0).round(1)
    # keep only COMPLETE months: everything strictly before the current
    # calendar month (a frame entirely inside the current month keeps all
    # of its rows — a degenerate but honest digest of what is there).
    # NB: - MonthBegin(1) lands on THIS month's 1st (MonthBegin(0) would
    # roll FORWARD to next month and keep the partial month).
    month_start = (pd.Timestamp.now().normalize()
                   - pd.offsets.MonthBegin(1))
    complete = monthly.loc[monthly.index < month_start]
    if not complete.empty:
        monthly = complete
    out["close_sha256_12"] = hashlib.sha256(
        monthly.to_csv().encode("utf-8")).hexdigest()[:12]
    tk = sorted(out["tickers"])

    def _cell(t: str) -> str:
        c = out["tickers"][t]
        return (f"{t:<6} {c['rows']:>5} rows  {c['first']}..{c['last']}")

    lines = [f"  price frame fingerprint ({len(tk)} tickers, close panel "
             f"{out['window'][0]}..{out['window'][1]}):"]
    for i in range(0, len(tk), 2):
        lines.append("    " + "   ".join(_cell(t) for t in tk[i:i + 2]))
    lines.append(_c(f"    month-end close sha256[:12] {out['close_sha256_12']}  "
                    f"(ME last, round 1dp, NaN->0, csv)", "36"))
    out["lines"] = lines
    return out


# ── § 17.8.2 · print_price_fingerprint ── v14.6 STEP B: print the compact fingerprint block.
def print_price_fingerprint(fp: dict) -> None:
    """v14.6 STEP B: print the compact fingerprint block (print-only)."""
    for ln in (fp or {}).get("lines", []):
        print(ln)


# ── § 18.1 · executable_leverage ── v13.2 D-1: the ONE authoritative path from classifier outputs…
# ══════════════════════════════════════════════════════════════════════════════
#  § 18 · BACKTESTER & DAILY LEDGER
# ══════════════════════════════════════════════════════════════════════════════
def executable_leverage(scenario_key: str, dominance: float, regime_months: int,
                        regime_history: Sequence[float], spy_monthly_close: pd.Series,
                        month: str, wealth: float, peak: float, has_shorts: bool,
                        cfg: Config = CFG) -> tuple[float, dict]:
    """v13.2 D-1: the ONE authoritative path from classifier outputs to the
    leverage the backtester actually executes. Shared by Backtester.run(),
    mrs_at() and (through the backtest) the ML dataset builder.

    Uses ONLY past information: the caller supplies the regime return
    history and the strategy equity curve as of BEFORE the trade month.
    Order of overlays is exactly v13.1's: conviction formula -> trend cap
    (long or short side) -> cycle-peak cap -> defensive cap -> drawdown
    throttle -> min/max clamp.

    Returns (leverage, details).
    """
    hist = [r for r in (regime_history or [])]
    # NOTE: regime_acc deliberately keeps numpy's float64 (v13.1 passed
    # np.mean(...) straight through). Casting to a Python float changes
    # round() semantics on exact .xx5 boundaries (np.float64(0.885) -> 0.88,
    # float(0.885) -> 0.89) — a display-only difference, but bit-exact parity
    # with v13.1 is required by the replay comparison.
    regime_acc = np.mean([1 if r > 0 else 0 for r in hist[-12:]]) if hist else 0.5
    conv_lev = conviction_leverage_v2(
        float(dominance) if dominance is not None and pd.notna(dominance) else 0.0,
        regime_acc, int(regime_months), cfg)
    lev_cap = RiskManager(cfg).compute_leverage_cap(
        spy_monthly_close, month, is_short=bool(has_shorts))
    if scenario_key == "LATE_CYCLE_OVERHEATING":
        lev_cap = min(lev_cap, cfg.cycle_peak_lev_cap)
    if scenario_key in set(cfg.defensive_regimes):
        lev_cap = min(lev_cap, cfg.defensive_lev_cap)
    throttled = False
    if cfg.dd_throttle and peak > 0:
        dd_now = max(0.0, 1.0 - wealth / peak)
        if dd_now > cfg.dd_throttle_start:
            span = max(1e-9, cfg.dd_throttle_full - cfg.dd_throttle_start)
            t = min(1.0, (dd_now - cfg.dd_throttle_start) / span)
            throttle = 1.0 - t * (1.0 - cfg.dd_throttle_floor)
            conv_lev = max(cfg.min_leverage, conv_lev * throttle)
            throttled = True
    conv_lev = min(conv_lev, lev_cap)
    conv_lev = max(cfg.min_leverage, conv_lev)
    return conv_lev, {"regime_acc": regime_acc, "lev_cap": lev_cap,
                      "dd_throttled": throttled}


# ── § 18.2 · Backtester
class Backtester:
    # · __init__
    def __init__(self, cfg: Config = CFG) -> None:
        self.cfg = cfg
        self.risk_mgr = RiskManager(cfg)
        self._daily_data: pd.DataFrame | None = None
        # A-1 (v13.2): portable portfolio/regime state, exported after every
        # run() so walk-forward folds (or the API) can chain it.
        self.last_state: dict = self._fresh_state()
        # v14.1 S3: per-month executed TARGET weights and unrounded leverage
        # diagnostics — consumed by build_daily_ledger() (accounting audit).
        self.month_weights: dict[str, dict[str, float]] = {}
        self.month_diag: dict[str, dict[str, float]] = {}

    # · _fresh_state
    @staticmethod
    def _fresh_state() -> dict:
        return {"prev_weights": {}, "regime_history": {}, "wealth": 1.0, "peak": 1.0}

    # · _price_window — v13.3 M-2 (B-3/B-8 parity): the daily-price request window.
    @staticmethod
    def _price_window(cfg: Config) -> tuple[str, str]:
        """v13.3 M-2 (B-3/B-8 parity): the daily-price request window.

        The 10m SPY SMA trend filter must be live from the FIRST output month
        even when the macro fetch window was auto-clipped short (B-3 built a
        10-year warmup into fetch_start for exactly this; the auto-window
        cannot, because the ICE BofA history does not exist). Prices are
        independent of the macro constraint, so at least
        trend_sma_window + 2 months before output_start are always requested.
        With the stock 1998/2008 configuration the window is UNCHANGED from
        v13.1 (fetch_start - 1 month)."""
        sma_warmup = pd.Timestamp(cfg.output_start) - pd.DateOffset(
            months=cfg.trend_sma_window + 2)
        start = min(pd.Timestamp(cfg.fetch_start), sma_warmup) - pd.DateOffset(months=1)
        end = pd.Timestamp(cfg.output_end) + pd.DateOffset(months=2)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # · preload_prices
    def preload_prices(self, tickers: set[str], cfg: Config = None) -> None:
        cfg = cfg or self.cfg
        # v14.4 S2: one SHARED frame per run — the canonical ticker set plus
        # anything the caller explicitly adds; served through the in-RAM memo
        # so the backtest, the attribution and ticker_score reuse one download.
        all_tickers = sorted(tickers | {"^VIX", "VXX", "SPY", "QQQ", "TLT"})
        start, end = self._price_window(cfg)
        if set(all_tickers) <= set(_CANONICAL_PRICE_TICKERS):
            self._daily_data = _engine_price_frame(cfg)
        else:
            self._daily_data = _get_prices(all_tickers, start, end)

    # · run — v13.2 A-1: `state` (a previous run's self.last_state) chains
    def run(self, signals: list[dict[str, Any]], cfg: Config = None,
            state: dict | None = None) -> pd.DataFrame:
        """v13.2 A-1: `state` (a previous run's self.last_state) chains
        prev_weights / regime_history / wealth / peak across calls — the
        walk-forward engine uses it to keep OOS folds continuous."""
        cfg = cfg or self.cfg
        risk_mgr = RiskManager(cfg) if cfg != self.cfg else self.risk_mgr
        st = dict(state) if state else {}
        self.last_state = {"prev_weights": dict(st.get("prev_weights") or {}),
                           "regime_history": {k: list(v) for k, v in (st.get("regime_history") or {}).items()},
                           "wealth": float(st.get("wealth", 1.0)),
                           "peak": float(st.get("peak", 1.0))}

        all_tickers = set()
        for sig in signals:
            all_tickers.update(sig["longs"])
            all_tickers.update(sig["shorts"])
        all_tickers.update(["^VIX", "VXX", "SPY", "QQQ", "TLT"])

        if self._daily_data is not None:
            daily_data = self._daily_data
        else:
            # B-8: same warmup window as preload_prices (shared _price_window)
            # so the 10m SMA trend filter is identical on both code paths.
            # v14.4 S2: the frame comes from the shared in-RAM memo.
            start_date, end_date = self._price_window(cfg)
            if all_tickers <= set(_CANONICAL_PRICE_TICKERS):
                daily_data = _engine_price_frame(cfg)
            else:
                daily_data = _get_prices(sorted(all_tickers), start_date, end_date)
            # v14.1 S3: cache the frame actually used so downstream audits
            # (daily ledger) see exactly what the backtest saw.
            self._daily_data = daily_data

        if daily_data.empty:
            return pd.DataFrame()

        daily_open = daily_data["Open"]
        daily_close = daily_data["Close"]

        # B-1 (v13.2): SPY/QQQ are load-bearing (trend filter, benchmark, SPY
        # fallback). A missing column must abort with a clear error instead
        # of a KeyError deep inside the loop or a silently corrupted run.
        _missing_bench = [t for t in ("SPY", "QQQ") if t not in daily_close.columns]
        if _missing_bench:
            raise RuntimeError(
                f"Daily price data missing for {_missing_bench}: the SPY trend filter, "
                f"the benchmark and the SPY fallback are undefined. The Yahoo Finance "
                f"download is incomplete — refusing to run on misaligned data.")

        spy_monthly_close = daily_close["SPY"].resample(FREQ_ME).last()

        # L-1 (v13.2): build the VXX overlay context ONCE per run (identical
        # to the previous per-month computation, proven by tests).
        vxx_ctx = risk_mgr._build_vxx_context(daily_open, daily_close)
        vxx_overlay = {}
        for sig in signals:
            active, ret, label = risk_mgr.simulate_vxx_overlay(
                sig, daily_open, daily_close, spy_monthly_close, vxx_ctx=vxx_ctx)
            vxx_overlay[sig["month"]] = {"active": active, "ret": ret, "label": label}

        std_tickers = [t for t in all_tickers if t not in ("^VIX", "VXX") and t in daily_open.columns]
        monthly_open = daily_open[std_tickers].resample(FREQ_ME).first()
        monthly_close = daily_close[std_tickers].resample(FREQ_ME).last()
        monthly_open.index = monthly_open.index.strftime("%Y-%m")
        monthly_close.index = monthly_close.index.strftime("%Y-%m")

        bench_open = daily_open[["SPY", "QQQ"]].resample(FREQ_ME).first()
        bench_close = daily_close[["SPY", "QQQ"]].resample(FREQ_ME).last()
        bench_open.index = bench_open.index.strftime("%Y-%m")
        bench_close.index = bench_close.index.strftime("%Y-%m")

        SHORT_AMPLIFY_REGIMES = {"INFLATION_SHOCK", "LATE_CYCLE_OVERHEATING"}
        SHORT_MULT = 1.5
        LONG_MULT = 1.0

        results = []
        equity_tickers = {"SPY", "QQQ", "IWM", "XLY", "XLI", "XLB", "XLE", "XLU", "XLP", "HYG", "XLF"}
        defensive_regimes = set(cfg.defensive_regimes)

        # A-1 (v13.2): portfolio + regime state seeded from the chained
        # `state` argument (walk-forward folds) instead of resetting to flat.
        # v14.1 S3 (audit D3): prev_weights are the DRIFTED end-of-previous-
        # month weights (targets x that month's price moves), not the untouched
        # targets — rebalancing back to target is a real trade.
        prev_weights = dict(self.last_state["prev_weights"])
        regime_history = {k: list(v) for k, v in self.last_state["regime_history"].items()}
        wealth, peak = self.last_state["wealth"], self.last_state["peak"]
        self.month_weights = {}
        self.month_diag = {}

        # v14.1 S3 (audit D5) + v14.4 R6: benchmark monthly series.  SPY in
        # BOTH conventions; the balanced benchmark is the owner-specified
        # 60/40 = 0.6 SPY + 0.4 TLT (close-to-close, true B&H).
        #   O→C  first open -> last close (the strategy's own holding window)
        #   C→C  prior month-end close -> this month-end close (true B&H)
        spy_cc_s = daily_close["SPY"].resample(FREQ_ME).last()
        spy_cc_s.index = spy_cc_s.index.strftime("%Y-%m")
        tlt_cc_s = (daily_close["TLT"].resample(FREQ_ME).last()
                    if "TLT" in daily_close.columns else pd.Series(dtype=float))
        if not tlt_cc_s.empty:
            tlt_cc_s.index = tlt_cc_s.index.strftime("%Y-%m")

        for sig in signals:
            month = sig["month"]
            if month not in monthly_open.index:
                continue

            # B-1 (v13.2): compute per-ticker returns and remember WHICH
            # tickers actually have tradable prices this month — weights are
            # built over exactly these (v13.1 averaged returns over the
            # available set but spread weights over the LISTED set, leaving
            # weight on unpriced tickers: reported exposure without positions).
            def _m_ret(t: str):
                if t not in monthly_open.columns:
                    return None
                e, x = monthly_open.loc[month, t], monthly_close.loc[month, t]
                if pd.notna(e) and pd.notna(x) and e > 0:
                    return (x - e) / e
                return None

            # v14.1 S3: per-ticker returns for EVERY held ticker this month
            # (drift of the executed weights; unpriced -> no drift).
            month_ret = {}
            for t in set(prev_weights) | set(sig["longs"]) | set(sig["shorts"]):
                r = _m_ret(t)
                if r is not None:
                    month_ret[t] = r

            long_rets, avail_l = [], []
            for t in sig["longs"]:
                r = _m_ret(t)
                if r is not None:
                    long_rets.append(r)
                    avail_l.append(t)
            short_rets, avail_s = [], []
            for t in sig["shorts"]:
                r = _m_ret(t)
                if r is not None:
                    short_rets.append(-r)   # short P&L: positive when price falls
                    avail_s.append(t)
            missing_price = [t for t in list(sig["longs"]) + list(sig["shorts"])
                             if t not in avail_l and t not in avail_s]

            avg_l = float(np.mean(long_rets)) if long_rets else 0.0
            avg_s = float(np.mean(short_rets)) if short_rets else 0.0
            n_l = len(long_rets)
            n_s = len(short_rets)
            # B-1 (v13.2): the weight construction uses the SAME counts as the
            # return averaging (available positions, not listed baskets).
            n_longs = n_l
            n_shorts_w = n_s

            if sig["scenario_key"] in SHORT_AMPLIFY_REGIMES and n_s > 0 and n_l > 0:
                w_l = n_l * LONG_MULT
                w_s = n_s * SHORT_MULT
                w_total = w_l + w_s
                base_ret = ((w_l * avg_l) + (w_s * avg_s)) / w_total if w_total > 0 else 0.0
            else:
                n_total = n_l + n_s
                base_ret = ((n_l * avg_l) + (n_s * avg_s)) / n_total if n_total > 0 else 0.0

            # B-1 (v13.2): ONE condition for the 50% SPY fallback, applied to
            # returns AND weights. v13.1 halved the long weights and added a
            # 50% SPY weight whenever has_equity was False — including for
            # DEFENSIVE regimes, whose returns explicitly exclude SPY: an
            # unbacked exposure that inflated turnover and reported gross
            # exposure. has_equity also keys on AVAILABLE longs so weights
            # never reference positions that do not exist.
            spy_ret = None
            if "SPY" in monthly_open.columns:
                e_spy, x_spy = monthly_open.loc[month, "SPY"], monthly_close.loc[month, "SPY"]
                if pd.notna(e_spy) and pd.notna(x_spy) and e_spy > 0:
                    spy_ret = (x_spy - e_spy) / e_spy
            has_equity = any(t in equity_tickers for t in avail_l)
            spy_fallback = (spy_ret is not None and not has_equity and n_s == 0
                            and sig["scenario_key"] not in defensive_regimes)
            if spy_fallback:
                base_ret = (base_ret * 0.50) + (spy_ret * 0.50)

            hist_rets = regime_history.get(sig["scenario_key"], [])
            regime_months = int(sig.get("regime_months", 1))

            # D-1 (v13.2): the single authoritative leverage path (formula,
            # trend cap, cycle/defensive caps, drawdown throttle) — shared
            # with mrs_at() and the ML builder.
            conv_lev, lev_details = executable_leverage(
                scenario_key=sig["scenario_key"],
                dominance=float(sig.get("dominance", 0.0)),
                regime_months=regime_months,
                regime_history=hist_rets,
                spy_monthly_close=spy_monthly_close,
                month=month, wealth=wealth, peak=peak,
                has_shorts=(n_s > 0), cfg=cfg)
            lev_cap = lev_details["lev_cap"]

            vxx_data = vxx_overlay.get(month, {"active": False, "ret": 0.0, "label": "N/A"})
            vxx_active = bool(vxx_data["active"])
            vxx_ret = float(vxx_data["ret"])
            vxx_label = vxx_data["label"]
            vxx_alloc = cfg.vxx_allocation if vxx_active else 0.0

            # v13 R-5: the hedge sleeve sits OUTSIDE the equity leverage
            # multiplier (the old code levered the hedge itself). The VXX
            # returns are already net of per-trade costs (R-4).
            gross_ret = conv_lev * base_ret * (1.0 - vxx_alloc) + vxx_alloc * vxx_ret

            current_weights = {}

            if n_longs > 0:
                if sig["scenario_key"] in SHORT_AMPLIFY_REGIMES and n_shorts_w > 0:
                    total_units = (n_longs * LONG_MULT) + (n_shorts_w * SHORT_MULT)
                    base_weight = (conv_lev * LONG_MULT) / total_units
                else:
                    base_weight = conv_lev / n_longs
                for t in avail_l:
                    current_weights[t] = base_weight

            if n_shorts_w > 0:
                if sig["scenario_key"] in SHORT_AMPLIFY_REGIMES:
                    if n_longs > 0:
                        total_units = (n_longs * LONG_MULT) + (n_shorts_w * SHORT_MULT)
                    else:
                        total_units = n_shorts_w * SHORT_MULT
                    short_weight = (conv_lev * SHORT_MULT) / total_units
                else:
                    short_weight = conv_lev / n_shorts_w
                for t in avail_s:
                    current_weights[t] = -short_weight

            if spy_fallback:
                for t in list(current_weights.keys()):
                    current_weights[t] *= 0.50
                current_weights["SPY"] = current_weights.get("SPY", 0.0) + (conv_lev * 0.50)

            # v14.1 S3: record the executed targets + unrounded diagnostics
            # for the daily-ledger accounting audit.
            self.month_weights[month] = dict(current_weights)
            self.month_diag[month] = {
                "conv_lev": float(conv_lev), "base_ret": float(base_ret),
                "vxx_alloc": float(vxx_alloc),
            }

            # v14.1 S3 (audit D3): turnover against the DRIFTED entry weights.
            # v14.0 compared target vs previous TARGET, so holding the same
            # basket through any price move charged NOTHING — understating
            # costs on every drift month.
            turnover = 0.0
            all_t = set(prev_weights.keys()) | set(current_weights.keys())
            for t in all_t:
                turnover += abs(current_weights.get(t, 0.0) - prev_weights.get(t, 0.0))
            cost_pct = (cfg.cost_bps_per_trade / 10000.0) * turnover
            # drift the executed weights to the month-end marks: these (not
            # the targets) are next month's entry weights.
            drifted = {}
            for t, w in current_weights.items():
                r = month_ret.get(t)
                drifted[t] = w if r is None else w * (1.0 + (r if w >= 0 else -r))
            prev_weights = drifted

            # v13 R-4: financing on borrowed notional + borrow fee on shorts.
            fin_cost, borrow_cost = 0.0, 0.0
            if cfg.charge_financing:
                borrowed = max(0.0, conv_lev - 1.0)
                rate_pct = sig.get("financing_rate", np.nan)
                if pd.isna(rate_pct):
                    rate_pct = cfg.financing_flat_annual * 100.0
                fin_cost = borrowed * (float(rate_pct) / 100.0 + cfg.financing_spread) / 12.0
                short_notional = sum(w for w in current_weights.values() if w < 0)
                borrow_cost = abs(short_notional) * cfg.short_borrow_bps_annual / 10000.0 / 12.0
            financing_drag = fin_cost + borrow_cost

            total_ret = gross_ret - cost_pct - financing_drag
            # v14.7 4c: a month can never lose more than everything — the
            # ledger clamps at -100% instead of letting a -150% month flip
            # the equity curve NEGATIVE (nonsense compounding).  On real
            # baskets the clamp never binds (gross is diversified and
            # leverage-capped), so normal results are unchanged.
            total_ret = max(total_ret, -1.0)

            # v13 R-2: update the strategy equity curve AFTER the month is done.
            wealth *= (1.0 + total_ret)
            peak = max(peak, wealth)

            regime_history.setdefault(sig["scenario_key"], []).append(total_ret)

            # v14.1 S3 (audit D5): benchmarks in both conventions —
            #   'SPY O→C %'    same holding window as the strategy (apples-
            #                  to-apples: entry open -> last close)
            #   'SPY B&H %'    TRUE buy-and-hold: prior month-end close ->
            #                  this month-end close (v14.0 used O→C and
            #                  mislabelled it B&H, hiding the month-end gap)
            spy_oc_pct = spy_ret * 100 if spy_ret is not None else 0.0
            prev_close = spy_cc_s.shift(1).get(month, np.nan)
            this_close = spy_cc_s.get(month, np.nan)
            spy_cc = ((this_close / prev_close - 1.0)
                      if (pd.notna(prev_close) and pd.notna(this_close)
                          and prev_close > 0) else np.nan)
            if pd.isna(spy_cc):
                spy_cc = spy_ret if spy_ret is not None else 0.0
            spy_bh = spy_cc * 100

            # v14.4 R6: the 60/40 SPY/TLT benchmark (close-to-close when TLT
            # prices exist — degenerate to SPY only on synthetic frames that
            # carry no TLT column) and the cash benchmark (financing rate/12).
            tlt_oc = None
            if "TLT" in monthly_open.columns:
                e_t, x_t = monthly_open.loc[month, "TLT"], monthly_close.loc[month, "TLT"]
                if pd.notna(e_t) and pd.notna(x_t) and e_t > 0:
                    tlt_oc = (x_t - e_t) / e_t
            tlt_prev = tlt_cc_s.shift(1).get(month, np.nan) if not tlt_cc_s.empty else np.nan
            tlt_this = tlt_cc_s.get(month, np.nan) if not tlt_cc_s.empty else np.nan
            tlt_cc = ((tlt_this / tlt_prev - 1.0)
                      if (pd.notna(tlt_prev) and pd.notna(tlt_this) and tlt_prev > 0)
                      else np.nan)
            mix_6040 = 0.0
            if month in bench_open.index:
                spy_r = spy_ret if spy_ret is not None else 0.0
                t_r = tlt_oc if tlt_oc is not None else spy_ret if spy_ret is not None else 0.0
                if pd.notna(spy_cc):
                    spy_r = spy_cc
                if pd.notna(tlt_cc):
                    t_r = tlt_cc
                mix_6040 = (spy_r * 0.6 + t_r * 0.4) * 100

            # v14.4 R6: cash benchmark = the month's financing rate / 12
            # (DFF when known, the flat fallback otherwise).
            _fr = sig.get("financing_rate", np.nan)
            _fr = float(_fr) if pd.notna(_fr) else cfg.financing_flat_annual * 100.0
            cash_pct = _fr / 12.0

            gross_exposure = sum(abs(w) for w in current_weights.values())
            net_exposure = sum(current_weights.values())

            results.append({
                "Month": month,
                "Scenario": sig["scenario_key"],
                "Regime": sig.get("regime", ""),
                "Long Assets": ", ".join(sig["longs"]),
                "Short Assets": ", ".join(sig["shorts"]),
                "Regime Months": regime_months,
                "Dominance": round(float(sig.get("dominance", 0.0)), 3),
                "Conviction Lev": round(conv_lev, 2),
                "Trend Cap": round(lev_cap, 2),
                "VXX Active": "Yes" if vxx_active else "No",
                "VXX Return %": round(vxx_ret * 100, 2) if vxx_active else 0.0,
                "VXX Regime": vxx_label,
                "Base Return %": round(base_ret * 100, 2),
                "Gross Ret %": round(gross_ret * 100, 2),
                "Cost %": round(cost_pct * 100, 2),
                "Financing %": round(financing_drag * 100, 3),
                "Net Portfolio Return %": round(total_ret * 100, 2),
                "SPY O→C %": round(spy_oc_pct, 2),
                "SPY B&H %": round(spy_bh, 2),
                "60/40 SPY/TLT %": round(mix_6040, 2),
                "Cash %": round(cash_pct, 3),
                "Outcome": "Win 🟢" if total_ret > 0 else "Loss 🔴",
                # v13.2 B-1: accounting diagnostics (additive columns).
                "Turnover": round(turnover, 4),
                "Gross Exposure": round(gross_exposure, 3),
                "Net Exposure": round(net_exposure, 3),
                "Missing Price Tickers": ", ".join(missing_price),
            })

            # v14.7 4c: ruin stops the track — the ruin month itself is
            # recorded above, but no further month compounds a zero equity
            # curve (the strategy ceased to exist).
            if wealth <= 0:
                _diag().price_notes.append(
                    f"backtest stopped at {month}: wealth <= 0 (ruin) — "
                    f"later months are not simulated")
                break

        # v13 B-6 / v13.2 I-1: drop the in-progress month — its "close" is
        # just the latest available price — but judge completion by the final
        # ACTUAL trading session: a month whose CALENDAR end falls on a
        # weekend/holiday must not be rejected merely because the last price
        # date precedes that calendar end (v13.1 silently dropped such months
        # at the data edge). A month is complete when either
        #   (a) price data already exists beyond its calendar end, or
        #   (b) the month has fully elapsed as of the run date AND the last
        #       price observation lies inside it, within 5 calendar days of
        #       month end (US equity markets never leave the last 5 calendar
        #       days of a month without a session).
        if results and not daily_close.empty:
            spy_px = daily_close["SPY"].dropna() if "SPY" in daily_close.columns else pd.Series(dtype=float)
            if not spy_px.empty:
                last_price_date = spy_px.index.max()
                # v14 FIX-9: "today" for the month-complete rule is the New
                # York trading day, not the server's local clock.
                asof_ref = min(pd.Timestamp(cfg.output_end).normalize(),
                               pd.Timestamp.now(ZoneInfo("America/New_York"))
                               .tz_localize(None).normalize())
                kept = []
                for r in results:
                    cal_end = pd.Timestamp(r["Month"] + "-01") + pd.offsets.MonthEnd(0)
                    complete = cal_end <= last_price_date
                    if not complete:
                        m_start = cal_end.replace(day=1)
                        complete = (cal_end <= asof_ref
                                    and m_start <= last_price_date <= cal_end
                                    and (cal_end - last_price_date).days <= 5)
                    if complete:
                        kept.append(r)
                results = kept

        # A-1 (v13.2): export the state for chaining (walk-forward, API).
        self.last_state = {"prev_weights": dict(prev_weights),
                           "regime_history": {k: list(v) for k, v in regime_history.items()},
                           "wealth": wealth, "peak": peak}
        # v14.1 S7 (H6): record the trial for auditability.
        _record_trial("backtest", cfg, pd.DataFrame(results))
        return pd.DataFrame(results)


# ── § 18.3 · generate_performance_summary
def generate_performance_summary(df: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    if df.empty: return pd.DataFrame()
    r = df["Net Portfolio Return %"] / 100
    spy = df["SPY B&H %"] / 100
    # v14.1 S3 (audit D5): the same-period benchmark (first open -> last
    # close) is the apples-to-apples comparator for the strategy's own
    # holding window; 'SPY B&H %' is the true close-to-close buy-and-hold.
    spy_oc = (df["SPY O→C %"] / 100) if "SPY O→C %" in df.columns else spy
    mix = df["60/40 SPY/TLT %"] / 100
    cum = (1 + r).prod() - 1
    cum_spy = (1 + spy).prod() - 1
    cum_oc = (1 + spy_oc).prod() - 1
    cum_mix = (1 + mix).prod() - 1
    cum_cash = ((1 + df["Cash %"] / 100).prod() - 1) if "Cash %" in df.columns else None
    sharpe = annualized_sharpe(r)
    sortino = annualized_sortino(r)
    mdd, mdd_date, mdd_peak = max_drawdown(r)
    cal = calmar(r)
    ab = alpha_beta(r, spy_oc)
    ci = block_bootstrap_ci(r)

    # v14.7 4d: degenerate statistics render as "n/a", never as a
    # plausible 0.00 (a failed/empty input is not a zero result).
    def _f2(v):
        return f"{v:.2f}" if pd.notna(v) else "n/a"

    def _pm(v):
        return f"{v:+.2f}%" if pd.notna(v) else "n/a"

    ci_ok = "status" not in ci
    wins = r[r > 0]
    losses = r[r < 0]
    avg_win = float(wins.mean() * 100) if len(wins) else 0.0
    avg_loss = float(losses.mean() * 100) if len(losses) else 0.0
    beats = int((r > spy_oc).sum())
    rows = [
        ("Net Cumulative Return", f"{cum*100:+.2f}%",
         f"SPY B&H: {cum_spy*100:+.2f}% | SPY O→C: {cum_oc*100:+.2f}% | "
         f"60/40 SPY/TLT: {cum_mix*100:+.2f}%"
         + (f" | Cash: {cum_cash*100:+.2f}%" if cum_cash is not None else "")),
        ("Annualized Sharpe", _f2(sharpe), f"Sortino: {_f2(sortino)} | Calmar: {_f2(cal)}"),
        ("Max Drawdown", _pm(mdd),
         f"Peak: {mdd_peak} | Trough: {mdd_date}"),
        ("Alpha (Ann.) vs SPY", _pm(ab['alpha_annualized_pct']),
         f"Beta: {_f2(ab['beta'])} | R²: {_f2(ab['r_squared'])} (same-period O→C SPY)"),
        ("Bootstrap CI (5th-95th)",
         f"[{ci['p5_cum_pct']:+.2f}%, {ci['p95_cum_pct']:+.2f}%]" if ci_ok else "n/a",
         f"Median: {ci['median_cum_pct']:+.2f}%" if ci_ok else "insufficient months for a CI"),
        # v14.1 S3 (audit D5): honest labels — positive months are NOT
        # benchmark beats; the beat count is reported separately.
        ("Positive Months", f"{len(wins)}/{len(r)} ({len(wins)/len(r):.1%})",
         f"Avg Win: +{avg_win:.2f}% | Avg Loss: {avg_loss:.2f}%"),
        ("Beat SPY (same-period)", f"{beats}/{len(r)} ({beats/len(r):.1%})",
         "months with net > SPY O→C"),
        ("VXX Overlay Fires", f"{(df['VXX Active']=='Yes').sum()}/{len(df)}", f"Allowed regimes: {', '.join(cfg.vxx_allowed_regimes)}"),
    ]
    if "Cost %" in df.columns:
        rows.append(("Turnover Cost (total)", f"{df['Cost %'].sum():+.2f}%",
                     f"{cfg.cost_bps_per_trade:.0f} bps per unit turnover"))
    if "Financing %" in df.columns:
        rows.append(("Financing + Borrow (total)", f"{-df['Financing %'].sum():+.2f}%",
                     "DFF + spread on leverage > 1x; borrow fee on shorts"))
    # v13.2 B-1: accounting diagnostics now recorded by the backtester.
    if "Conviction Lev" in df.columns:
        rows.append(("Leverage (avg / max)",
                     f"{df['Conviction Lev'].mean():.2f}x / {df['Conviction Lev'].max():.2f}x",
                     "executable gross exposure per month"))
    if "Gross Exposure" in df.columns and "Net Exposure" in df.columns:
        rows.append(("Exposure gross / net (avg)",
                     f"{df['Gross Exposure'].mean():.2f} / {df['Net Exposure'].mean():.2f}",
                     "sum |weights| vs sum weights (long-minus-short)"))
    if "Turnover" in df.columns:
        rows.append(("Turnover (total / monthly avg)",
                     f"{df['Turnover'].sum():.1f} / {df['Turnover'].mean():.2f}",
                     "sum of |month-over-month weight changes|"))
    return pd.DataFrame(rows, columns=["Metric", "Result", "Breakdown / Context"])


# ── § 18.4 · vxx_ledger
def vxx_ledger(df: pd.DataFrame, cfg: Config = CFG) -> pd.DataFrame:
    active = df[df["VXX Active"] == "Yes"].copy()
    if active.empty: return pd.DataFrame()
    if "VXX Regime" in active.columns:
        active["regime_label"] = active["VXX Regime"]
    else:
        crisis_dates = ["2008-10-01", "2015-08-01", "2018-12-01", "2020-03-01", "2022-06-01"]
        active["regime_label"] = active["Month"].apply(
            lambda m: "CRISIS" if any(abs((pd.Timestamp(m) - pd.Timestamp(d)).days) < 45 for d in crisis_dates) else "CALM"
        )
    active["pnl_dollars_per_100k"] = active["VXX Return %"] / 100 * cfg.vxx_allocation * 100_000
    return active[["Month", "Scenario", "regime_label", "VXX Return %", "pnl_dollars_per_100k"]].copy().round(2)


# ── § 18.5 · print_vxx_coverage_note ── v14.1 S4 (audit D4): name the VXX coverage gap explicitly…
def print_vxx_coverage_note(df: pd.DataFrame) -> None:
    """v14.1 S4 (audit D4): name the VXX coverage gap explicitly instead of
    letting the overlay be silently inactive (as it is for the whole pre-2018
    segment of a 2008+ backtest)."""
    if df is None or df.empty or "VXX Regime" not in df.columns:
        return
    na = int((df["VXX Regime"].fillna("N/A") == "N/A").sum())
    if na:
        print(f"\n  ⚠️  VXX overlay price coverage MISSING in {na}/{len(df)} "
              f"months (VXX/VIX data absent — e.g. before VXX listed).  The "
              f"hedge was INACTIVE there; those months are counted in the "
              f"readiness report (audit D4).")


# ── § 18.6 · build_daily_ledger ── v14.1 S3 (audit claim 2, 'accounting is exact'): a position-lev…
def build_daily_ledger(signals: list[dict], daily_data: pd.DataFrame | None,
                       results_df: pd.DataFrame,
                       month_weights: dict | None,
                       cfg: Config = CFG) -> pd.DataFrame:
    """v14.1 S3 (audit claim 2, 'accounting is exact'): a position-level
    DAILY ledger proving the monthly arithmetic.

    For every trade month it rebuilds each held position's daily cumulative
    path from the month's FIRST OPEN (per-ticker telescoping: the path
    product equals (last close / first open) exactly) and marks the portfolio
    equity as 1 + sum(w_t * (path_t - 1)) — which is sign-correct for shorts
    (w<0 => contribution w*(path-1) = |w|*(1-path)).

    Two reconciliations per month:
      residual_abs   |daily-path end equity - independently recomputed
                     sum(w_t * R_t) from the monthly open/close bars| —
                     must be ~1e-15 (telescoping proof; catches any resample
                     or weight-construction divergence);
      vs_gross_abs   |end equity - (conv_lev * base_ret * (1 - vxx_alloc))|
                     from the backtester's own diagnostics — must be ~0
                     (uses UNROUNDED values recorded in Backtester.month_diag
                     when available, else the rounded results columns).

    Also yields intra-month diagnostics the monthly frame cannot show
    (worst daily equity point inside each month).
    """
    if (daily_data is None or getattr(daily_data, "empty", True)
            or results_df is None or results_df.empty or not month_weights):
        return pd.DataFrame()
    daily_open, daily_close = daily_data["Open"], daily_data["Close"]
    res_idx = results_df.set_index("Month")
    rows = []
    for sig in signals:
        month = sig["month"]
        w = month_weights.get(month)
        if not w or month not in res_idx.index:
            continue
        y, m = map(int, month.split("-"))
        m_start = pd.Timestamp(y, m, 1)
        m_end = m_start + pd.offsets.MonthEnd(0)
        # per-ticker cumulative path from the month's first open
        paths: dict[str, pd.Series] = {}
        monthly_bars: dict[str, float] = {}
        for t in w:
            if t not in daily_close.columns:
                continue
            closes = daily_close[t].loc[m_start:m_end].dropna()
            opens = daily_open[t].loc[m_start:m_end].dropna()
            if closes.empty or opens.empty:
                continue
            entry = float(opens.iloc[0])
            if not np.isfinite(entry) or entry <= 0:
                continue
            paths[t] = closes / entry
            monthly_bars[t] = float(closes.iloc[-1]) / entry - 1.0
        if not paths:
            continue
        all_days = sorted(set().union(*[set(p.index) for p in paths.values()]))
        expected_end = sum(w[t] * monthly_bars[t] for t in monthly_bars)
        for d in all_days:
            eq = 1.0
            for t, p in paths.items():
                v = p.loc[d] if d in p.index else float(p.asof(d))
                eq += w[t] * (float(v) - 1.0)
            rows.append({
                "Month": month, "Date": d, "equity": eq,
                "daily_ret": np.nan,   # filled after sorting
                "residual_abs": np.nan,
            })
        # fill daily returns and the end-of-month reconciliation
        # (this month's rows are the tail of `rows`, in date order)
        start_i = len(rows) - len(all_days)
        for i, d in enumerate(all_days):
            prev_eq = (rows[start_i + i - 1]["equity"]
                       if i > 0 else 1.0)
            rows[start_i + i]["daily_ret"] = rows[start_i + i]["equity"] / prev_eq - 1.0
        end_eq = rows[-1]["equity"]
        residual = abs(end_eq - (1.0 + expected_end))
        for i in range(start_i, len(rows)):
            rows[i]["residual_abs"] = residual
        rows[start_i]["month_end_equity"] = end_eq
        rows[start_i]["expected_month_end"] = 1.0 + expected_end
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # vs_gross: compare against the backtester's own gross basket component
    if "Gross Ret %" in res_idx.columns:
        vs = []
        for _, r in out.iterrows():
            m = r["Month"]
            g = float(res_idx.loc[m, "Gross Ret %"]) / 100.0
            vs.append(abs(r["month_end_equity"] - (1.0 + g))
                      if pd.notna(r.get("month_end_equity")) else np.nan)
        out["vs_gross_abs"] = vs
    return out


# ── § 18.7 · analyze_ticker_performance
def analyze_ticker_performance(signals, output_start, output_end, cfg: Config = CFG) -> pd.DataFrame:
    all_tickers = sorted({t for sig in signals for t in (sig["longs"] + sig["shorts"]) if t not in ("^VIX", "VXX")})
    if not all_tickers: return pd.DataFrame()
    start_date = (pd.Timestamp(output_start) - pd.DateOffset(months=1)).strftime("%Y-%m-%d")
    end_date = (pd.Timestamp(output_end) + pd.DateOffset(months=2)).strftime("%Y-%m-%d")
    raw_data = _safe_yf_download(all_tickers, start_date, end_date)
    if raw_data.empty: return pd.DataFrame()

    open_p = raw_data["Open"].resample(FREQ_ME).first()
    close_p = raw_data["Close"].resample(FREQ_ME).last()
    open_p.index = open_p.index.strftime("%Y-%m")
    close_p.index = close_p.index.strftime("%Y-%m")

    stats = {t: {"long_trades": 0, "long_pnl": 0.0, "long_wins": 0,
                 "short_trades": 0, "short_pnl": 0.0, "short_wins": 0} for t in all_tickers}
    for sig in signals:
        m = sig["month"]
        if m not in open_p.index: continue
        for t in sig["longs"]:
            if t in open_p.columns:
                e, x = open_p.loc[m, t], close_p.loc[m, t]
                if pd.notna(e) and pd.notna(x) and e > 0:
                    ret = (x - e) / e
                    stats[t]["long_trades"] += 1
                    stats[t]["long_pnl"] += ret
                    if ret > 0: stats[t]["long_wins"] += 1
        for t in sig["shorts"]:
            if t in open_p.columns:
                e, x = open_p.loc[m, t], close_p.loc[m, t]
                if pd.notna(e) and pd.notna(x) and e > 0:
                    ret = (e - x) / e
                    stats[t]["short_trades"] += 1
                    stats[t]["short_pnl"] += ret
                    if ret > 0: stats[t]["short_wins"] += 1

    records = []
    for t, s in stats.items():
        total_trades = s["long_trades"] + s["short_trades"]
        total_pnl = s["long_pnl"] + s["short_pnl"]
        long_win = (s["long_wins"] / s["long_trades"] * 100) if s["long_trades"] > 0 else None
        short_win = (s["short_wins"] / s["short_trades"] * 100) if s["short_trades"] > 0 else None
        records.append({
            "Ticker": t, "Net PnL %": f"{total_pnl*100:+.2f}%",
            "_pnl_num": total_pnl,
            "Longs": s["long_trades"], "Long Win %": f"{long_win:.1f}%" if long_win is not None else "N/A",
            "Shorts": s["short_trades"], "Short Win %": f"{short_win:.1f}%" if short_win is not None else "N/A",
            "Total Trades": total_trades, "Insufficient Sample": "⚠️" if total_trades < 20 else "",
        })
    # B-9: sort on the NUMERIC pnl, not the formatted string (a string sort
    # ranks '-5.00%' above '+10.00%').
    out = pd.DataFrame(records)
    if out.empty: return out
    return (out.sort_values(by="_pnl_num", ascending=False)
              .drop(columns=["_pnl_num"])
              .reset_index(drop=True))


# ═══════════════════════════════════════════════════════════════════════════
#  § 19 · WALK-FORWARD ENGINE
# ═══════════════════════════════════════════════════════════════════════════
# v14.7 S4: grid-search worker context.  _GRID_SHARED holds (engine, panel,
# backtester, cfg) and is read by _grid_eval_config — set immediately before
# the fork-based pool is created (fork children inherit it; no pickling of
# the shared objects) and cleared afterwards.  Single-threaded callers only;
# grid searches never nest.
_GRID_SHARED: tuple | None = None


# ── § 19.0 · _grid_eval_config — ONE grid configuration (pool or in-process).
def _grid_eval_config(task):
    """v14.7 S4: evaluate ONE grid-search configuration.  Mirrors the
    per-configuration body of the v14.6.2 sequential search exactly (same
    exception net, same 'insufficient train results' rule, same Sharpe
    computation) and returns (sharpe, n_results, error, trials): sharpe is
    None for an insufficient window, error is None when nothing raised, and
    trials are the TRIAL-LEDGER records the pipeline wrote (captured in a
    private sink so pooled workers can hand them back for an ordered merge
    — the C03 deflated-Sharpe N must not depend on where the pipeline ran).
    Runs inside a forked pool worker or in-process — same function, same
    result."""
    mc, ds = task
    engine, panel, backtester, base_cfg = _GRID_SHARED
    train_cfg = replace(base_cfg, min_confidence=mc, dominance_saturation=ds)
    try:
        with _capture_diagnostics() as d:
            results, _, _ = engine._run_pipeline(panel, train_cfg, backtester)
        trials = [dict(t) for t in d.trials]
        if results.empty or len(results) < 6:
            return (None, 0 if results.empty else len(results), None, trials)
        returns = results["Net Portfolio Return %"] / 100
        return (float(annualized_sharpe(returns)), len(results), None, trials)
    except Exception as e:
        return (None, 0, f"{type(e).__name__}: {e}", [])


# ── § 19.0.1 · _grid_fold — fold grid outcomes in ORIGINAL iteration order.
def _grid_fold(configs, outcomes, cfg):
    """v14.7 S4: fold the per-configuration outcomes in the ORIGINAL
    iteration order with the ORIGINAL comparison logic (strict >, first
    wins) and merge each pipeline's trial-ledger records in the same order
    — so the selected parameters, failures and C03's deflated-Sharpe N are
    identical with or without the pool."""
    best_sharpe = -float("inf")
    best_params = {"min_confidence": cfg.min_confidence,
                   "dominance_saturation": cfg.dominance_saturation}
    failures = []
    evaluated = 0
    for (mc, ds), (sharpe, n_results, err, trials) in zip(configs, outcomes):
        for t in trials:
            _ledger_append(t)
        if err is not None:
            failures.append({"min_confidence": mc, "dominance_saturation": ds,
                             "error": err})
        elif sharpe is None:
            failures.append({"min_confidence": mc, "dominance_saturation": ds,
                             "error": f"insufficient train results "
                                      f"({n_results} months; need >= 6)"})
        else:
            evaluated += 1
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = {"min_confidence": mc,
                               "dominance_saturation": ds,
                               "train_sharpe": round(sharpe, 3)}
    return best_sharpe, best_params, failures, evaluated


# ── § 19.1 · WalkForwardEngine
class WalkForwardEngine:
    # · __init__
    def __init__(self, cfg: Config = CFG) -> None:
        self.cfg = cfg
        self.train_window = cfg.wf_train_window
        self.test_window = cfg.wf_test_window
        self.roll_step = cfg.wf_roll_step
        # A-1 (v13.2): rolling by less than the test window would make the
        # OOS windows overlap and double-count months in the aggregate
        # metrics — refuse such a configuration.
        if self.roll_step < self.test_window:
            raise MedsValidationError(
                f"wf_roll_step ({self.roll_step}) < wf_test_window ({self.test_window}): "
                f"OOS windows would overlap and months would be double-counted. "
                f"Use roll_step >= test_window.")
        self.n_trials = len(cfg.grid_min_confidence) * len(cfg.grid_dominance_saturation)
        # K-1 (v13.2): log of the last grid search (failures + counts).
        self.last_grid_log: dict = {"failures": [], "n_evaluated": 0, "n_configs": self.n_trials}

    # · _run_pipeline — v13.2 A-1: hysteresis and backtester state can be chained in…
    def _run_pipeline(self, panel, cfg, backtester, bt_state=None, hyst_state=None):
        """v13.2 A-1: hysteresis and backtester state can be chained in and
        out, so consecutive OOS folds behave exactly like one continuous run.
        Returns (results, hysteresis_state, backtester_state)."""
        # v14.6.2 STEP A: same reduced scenario set as get_macro_regime —
        # an excluded scenario can never win an OOS fold either.
        classifier = RegimeClassifier(_scenarios_for(cfg), cfg)
        raw_preds = classifier.classify_panel(panel)
        final = apply_hysteresis(raw_preds, cfg, initial_state=hyst_state)
        hyst_out = final.attrs.get("hysteresis_final_state")
        signals = parse_signals(final)
        res = backtester.run(signals, cfg, state=bt_state)
        return res, hyst_out, backtester.last_state

    # · _grid_search — K-1 (v13.2): every failed configuration is logged with its
    def _grid_search(self, train_panel, backtester, cfg):
        """K-1 (v13.2): every failed configuration is logged with its
        exception; if ALL configurations fail, the search raises instead of
        returning the current defaults as if optimization had succeeded.
        Only min_confidence and dominance_saturation are ever tuned.

        v14.7 S4: the per-configuration pipelines run in a fork-based
        ProcessPoolExecutor (workers = min(4, cpu)) when available — the
        dominant sequential cost of a full run.  Outcomes are folded back
        in the ORIGINAL iteration order with the ORIGINAL comparison
        logic, so the selected parameters, failures and last_grid_log are
        identical to the sequential evaluation (oracle-proven).  Without
        fork (or on any pool failure) the same worker runs in-process."""
        configs = [(mc, ds) for mc in cfg.grid_min_confidence
                   for ds in cfg.grid_dominance_saturation]
        global _GRID_SHARED
        _GRID_SHARED = (self, train_panel, backtester, cfg)
        outcomes = None
        workers = min(4, os.cpu_count() or 1)
        try:
            if (workers >= 2 and len(configs) >= 4
                    and "fork" in multiprocessing.get_all_start_methods()):
                try:
                    ctx = multiprocessing.get_context("fork")
                    with concurrent.futures.ProcessPoolExecutor(
                            max_workers=workers, mp_context=ctx) as ex:
                        outcomes = list(ex.map(_grid_eval_config, configs,
                                               chunksize=1))
                except Exception:
                    outcomes = None         # any pool failure -> in-process
            if outcomes is None:
                outcomes = [_grid_eval_config(c) for c in configs]
        finally:
            _GRID_SHARED = None

        best_sharpe, best_params, failures, evaluated = _grid_fold(
            configs, outcomes, cfg)
        self.last_grid_log = {"failures": failures, "n_evaluated": evaluated,
                              "n_configs": self.n_trials}
        if evaluated == 0:
            raise RuntimeError(
                f"Grid search failed: all {self.n_trials} configurations failed on the "
                f"training window — refusing to return default parameters as if "
                f"optimization had succeeded. First errors: "
                + "; ".join(f"[mc={f['min_confidence']}, ds={f['dominance_saturation']}] {f['error']}"
                            for f in failures[:3]))
        return best_params

    # · run
    def run(self, raw, cfg: Config = CFG):
        panel = FeatureEngine.build_full_panel(raw, cfg)
        if panel.empty or len(panel) < self.train_window + self.test_window:
            # v14 FIX-8: a normal line, not an error.
            return pd.DataFrame(), pd.DataFrame(), {
                "error": f"WF skipped: need {self.train_window + self.test_window} "
                         f"months, have {len(panel)}"}

        all_tickers = set()
        for sc in SCENARIOS:
            all_tickers.update(extract_tickers(sc.long))
            all_tickers.update(extract_tickers(sc.short))
        all_tickers.update(["^VIX", "VXX", "SPY", "QQQ"])

        backtester = Backtester(cfg)
        backtester.preload_prices(all_tickers, cfg)

        all_oos, param_history = [], []
        start_idx = 0
        # A-1 (v13.2): portfolio + regime state chained across OOS folds so
        # the stitched OOS equity curve equals one continuous run under the
        # same parameter schedule.
        bt_state, hyst_state = None, None
        seen_months: list[str] = []

        while start_idx + self.train_window + self.test_window <= len(panel):
            train = panel.iloc[start_idx:start_idx + self.train_window]
            test = panel.iloc[start_idx + self.train_window: start_idx + self.train_window + self.test_window]

            train_start, train_end = str(train.index[0].date()), str(train.index[-1].date())
            test_start, test_end = str(test.index[0].date()), str(test.index[-1].date())

            best_params = self._grid_search(train, backtester, cfg)
            test_cfg = replace(cfg, **{k: v for k, v in best_params.items()
                                        if k in ("min_confidence", "dominance_saturation")})

            oos_results, hyst_state, bt_state = self._run_pipeline(
                test, test_cfg, backtester, bt_state, hyst_state)
            if not oos_results.empty:
                oos_results["WF Train Start"] = train_start
                oos_results["WF Train End"] = train_end
                oos_results["WF Test Start"] = test_start
                oos_results["WF Test End"] = test_end
                all_oos.append(oos_results)
                seen_months.extend(oos_results["Month"].tolist())

            param_history.append({"train_start": train_start, "train_end": train_end,
                                  "test_start": test_start, "test_end": test_end,
                                  "n_grid_failures": len(self.last_grid_log["failures"]),
                                  **best_params})
            start_idx += self.roll_step

        # A-1 (v13.2): each OOS month must appear exactly once.
        if len(seen_months) != len(set(seen_months)):
            dupes = sorted({m for m in seen_months if seen_months.count(m) > 1})
            raise RuntimeError(f"Walk-forward produced overlapping OOS months "
                               f"(duplicates: {dupes[:5]}); refusing to aggregate "
                               f"double-counted months.")

        oos_df = pd.concat(all_oos, ignore_index=True) if all_oos else pd.DataFrame()
        param_df = pd.DataFrame(param_history)
        metrics = {}

        if not oos_df.empty:
            r = oos_df["Net Portfolio Return %"] / 100
            spy = oos_df["SPY B&H %"] / 100
            metrics["oos_sharpe"] = annualized_sharpe(r)
            metrics["oos_cum_return_pct"] = float((1 + r).prod() - 1) * 100
            mdd, _, _ = max_drawdown(r)
            metrics["oos_max_drawdown_pct"] = mdd
            ab = alpha_beta(r, spy)
            metrics["oos_alpha_annualized_pct"] = ab["alpha_annualized_pct"]
            metrics["oos_beta"] = ab["beta"]
            metrics["n_oos_months"] = len(r)

        return oos_df, param_df, metrics


# ═══════════════════════════════════════════════════════════════════════════
#  § 20 · DIAGNOSTIC — classification path
# ═══════════════════════════════════════════════════════════════════════════
# ── § 20.1 · classification_path_diagnostic
def classification_path_diagnostic(classified_df: pd.DataFrame) -> dict[str, Any]:
    if classified_df.empty or "classification_path" not in classified_df.columns:
        return {}
    total = len(classified_df)
    path_counts = classified_df["classification_path"].value_counts()
    path_pct = (path_counts / total * 100).round(2)
    regime_by_path = (
        classified_df.groupby("classification_path")["scenario_key"]
        .value_counts().unstack(fill_value=0)
    )
    dates = pd.to_datetime(classified_df["date"])
    kill_switch_mask = classified_df["classification_path"].isin(
        ["kill_switch_hard_landing", "kill_switch_credit_crunch"]
    )
    kill_switch_years = dates[kill_switch_mask].dt.year.value_counts().sort_index()
    return {
        "total_months": total,
        "path_counts": path_counts.to_dict(),
        "path_pct": path_pct.to_dict(),
        "regime_by_path": regime_by_path,
        "kill_switch_months_by_year": kill_switch_years.to_dict(),
    }


# ── § 20.2 · print_classification_path_diagnostic
def print_classification_path_diagnostic(classified_df: pd.DataFrame) -> None:
    diag = classification_path_diagnostic(classified_df)
    if not diag:
        print("  (no classification_path data — panel empty or column missing)")
        return
    print(f"\n  Total months classified: {diag['total_months']}")
    print("\n  Path breakdown (which branch of _classify_row_full fired):")
    for path, pct in sorted(diag["path_pct"].items(), key=lambda x: -x[1]):
        ct = diag["path_counts"][path]
        bar = "█" * int(pct / 2)
        print(f"    {path:28s}  {ct:4d}  ({pct:5.1f}%)  {bar}")
    kill_switch_pct = sum(pct for path, pct in diag["path_pct"].items() if path.startswith("kill_switch"))
    fallback_pct = sum(pct for path, pct in diag["path_pct"].items()
                       if path in ("soft_landing_fallback", "neutral_low_confidence", "neutral_no_scores"))
    scored_pct = diag["path_pct"].get("scored", 0.0)
    print(f"\n  Kill-switch: {kill_switch_pct:.1f}%   Fallback: {fallback_pct:.1f}%   Scored: {scored_pct:.1f}%")
    if kill_switch_pct > 25:
        print("\n  ⚠️  Kill-switches firing on a large share of history.")
    print("\n  Kill-switch months by year:")
    if diag["kill_switch_months_by_year"]:
        for year, ct in diag["kill_switch_months_by_year"].items():
            print(f"    {year}: {ct}")
    else:
        print("    (none fired)")
    print("\n  Regime assigned (post-hysteresis) by raw path:")
    print(diag["regime_by_path"].to_string())


# ═══════════════════════════════════════════════════════════════════════════
#  § 21 · PRESENTATION & ORCHESTRATION — run_engine · PREREG · readiness
# ═══════════════════════════════════════════════════════════════════════════
# ── § 21.1 · _print_section
def _print_section(title: str, width: int = 80, char: str = "═") -> None:
    print(f"\n{char * width}\n{title}\n{char * width}")


# ── § 21.2 · _print_monthly_results
def _print_monthly_results(df: pd.DataFrame) -> None:
    if df.empty: return
    cols = ["Month", "Scenario", "Regime Months", "Conviction Lev", "Trend Cap",
            "Net Portfolio Return %", "SPY B&H %", "Outcome"]
    view = df[cols].copy()
    widths = {c: max(len(c), int(view[c].astype(str).str.len().max() if len(view) else 0)) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for _, row in view.iterrows():
        print("  ".join(str(row[c]).ljust(widths[c]) for c in cols))


# ── § 21.3 · run_engine
async def run_engine(raw, cfg: Config = CFG) -> pd.DataFrame:
    panel = FeatureEngine.run(raw, cfg)
    if panel.empty: return pd.DataFrame()
    raw_preds = get_macro_regime(panel, cfg)
    final = apply_hysteresis(raw_preds, cfg)
    return final


# ── v14.1 S7 (audit H6): frozen pre-registration, BEFORE any full-window ────
# validation is possible.  Its SHA-256 is pinned by a test: editing PREREG is
# a deliberate, visible act (change the pin too) and can never be done after
# the validation data has been seen.  All 13 criteria evaluate ONLY on the
# full 2008..latest window with strict-or-approximate PIT data; until then
# every strategy claim is PROVISIONAL.
PREREG: dict = {
    "version": "2026-11-01.1",
    "scope": ("Full-window validation, 2008-01..latest complete month, vs the "
              "benchmark set below.  STRATEGY conclusions are PROVISIONAL "
              "until a >= 12-month forward paper record exists (--paper)."),
    "benchmarks": ("SPY buy-and-hold (close-to-close), 60/40 SPY/TLT "
                   "(0.6 SPY + 0.4 TLT), SPY 10-month SMA trend rule "
                   "(SMA10-only, same costs and financing), cash "
                   "(financing rate)"),
    "criteria": {
        "C01_NET_SHARPE_BEATS_SMA10": {
            "rule": "net annualized Sharpe >= SMA10-only Sharpe + 0.15",
            "threshold": 0.15},
        "C02_BOOTSTRAP_CI_POSITIVE": {
            "rule": ("95% paired block-bootstrap CI lower bound of net cum "
                     "return (strategy minus SMA10-only) > 0"),
            "threshold": 0.0},
        "C03_DEFLATED_SHARPE": {
            "rule": "Deflated Sharpe Ratio >= 0.95",
            "threshold": 0.95},
        "C04_MAX_DRAWDOWN": {
            "rule": "net max drawdown <= 25%",
            "threshold": 0.25},
        "C05_AVG_LEVERAGE": {
            "rule": "average gross leverage <= 1.5x",
            "threshold": 1.5},
        "C06_COST_ROBUST_1X": {
            "rule": "net cumulative return > 0 at 1x current costs",
            "threshold": 0.0},
        "C07_COST_ROBUST_2X": {
            "rule": "net cumulative return > 0 at 2x current costs",
            "threshold": 0.0},
        "C08_COST_ROBUST_3X": {
            "rule": "net cumulative return > 0 at 3x current costs",
            "threshold": 0.0},
        "C09_PUB_LAG_PERTURBATION": {
            "rule": ("every publication lag scaled +/-50%: net Sharpe stays "
                     "> 0 and month-level regime agreement with the baseline "
                     "lags >= 70%"),
            "threshold": 0.70},
        "C10_THRESHOLD_SENSITIVITY": {
            "rule": ("decision thresholds (min_confidence, "
                     "dominance_saturation, kill-switch z, crash guard, VIX "
                     "trigger) each scaled +/-20%: net Sharpe > 0 in every "
                     "perturbation"),
            "threshold": 0.0},
        "C11_VARIANT_ROBUSTNESS": {
            "rule": (">= 80% of the 9-point parameter grid "
                     "(min_confidence x dominance_saturation) has positive "
                     "net Sharpe"),
            "threshold": 0.80},
        "C12_BENCHMARK_SET_REPORTED": {
            "rule": ("results reported vs SPY, 60/40 SPY/TLT, SMA10-only and "
                     "cash over the IDENTICAL months (reporting requirement)"),
            "threshold": None},
        "C13_PREREQUISITE_GATES": {
            "rule": ("audit gates S1 (PIT), S3 (accounting), S4 (VXX), S5 "
                     "(classifier) and S6 (coverage 2008..latest) all PASS "
                     "before any criterion above is counted"),
            "threshold": None},
    },
    # v14.1 S4 (audit D9): behaviours retained from the original strategy and
    # disclosed here so nobody mistakes them for newly-added logic.
    "documented_behaviours": {
        "VXX_SPIKE_REGIME_EXEMPTION": (
            "The VXX overlay's crisis entry has TWO branches: the normal "
            "gate requires an allowed regime (HARD_LANDING / CREDIT_CRUNCH) "
            "AND VIX-vs-MA20 stress AND (VIX>25 or a 15% 2-day jump) AND SPY "
            "below its 10m SMA; the SPIKE branch (VIX > 30 + VIX-vs-MA20 "
            "stress + SPY trend down) may enter WITHOUT an allowed regime. "
            "Original v13.1 behaviour, deliberately retained and covered by "
            "a dedicated test (TestS4Vxx.test_spike_entry_fires_without_"
            "allowed_regime_and_is_disclosed)."),
        "VXX_PRE_LISTING_INACTIVITY": (
            "The overlay can only trade where VXX/VIX price data exists; "
            "months without coverage are reported as N/A and COUNTED in the "
            "readiness report (audit D4) — a 2008+ window includes ~9 years "
            "without the overlay (VXX listed 2009-01-30; this snapshot's VXX "
            "history starts 2018-01-25)."),
    },
}


# ── § 21.4 · prereg_sha256 ── Canonical-content SHA-256 of the frozen PREREG (pinned by tests).
def prereg_sha256() -> str:
    """Canonical-content SHA-256 of the frozen PREREG (pinned by tests)."""
    return hashlib.sha256(
        json.dumps(PREREG, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=True).encode("utf-8")).hexdigest()


# ── § 21.4b · _prereg_prereq_state ── the C13 prerequisite gates, shared by run_prereg_eval and main_async.
def _prereg_prereq_state(df_results: pd.DataFrame, wf_metrics: dict,
                         cfg: Config, source_mode: str,
                         price_frame_gaps: dict | None = None) -> dict:
    """The C13 prerequisite-gate computation (single source of truth):
    span >= 15y including 2008 and 2020, the walk-forward actually ran, and
    PIT data (true API vintages, or lags applied on a non-API tier).  Used
    by run_prereg_eval (C13's status/detail) and by main_async (to decide
    whether --prereg-full should run the part-B suites at all).

    v14.6 STEP A: `price_frame_gaps` (§17.7 _frame_gaps on the shared frame
    the run actually used) adds the frame-completeness gate — a PARTIAL
    frame (missing tickers / truncated date ranges, still partial after the
    §17.7 retries) FAILS C13 so the overall verdict is BLOCKED and NO
    criterion is counted on that frame.  None = not judged here (older
    callers keep v14.5 behaviour)."""
    months = (pd.to_datetime(df_results["Month"], format="%Y-%m")
              if df_results is not None and not df_results.empty
              else pd.Series(dtype="datetime64[ns]"))
    span = ((months.max() - months.min()).days / 365.25
            if len(months) > 1 else 0.0)
    has08 = bool(((months >= "2008-01-01") & (months <= "2008-12-31")).any())
    has20 = bool(((months >= "2020-01-01") & (months <= "2020-12-31")).any())
    wf_ok = bool(wf_metrics) and "error" not in wf_metrics
    pit_ok = (source_mode == "api"
              or (source_mode != "api" and cfg.pit_lag_enabled))
    frame_ok = (price_frame_gaps is None
                or not price_frame_gaps.get("partial", True))
    # v14.6.2 STEP A: the frozen PREREG was pre-registered for the
    # credit-enabled engine — a credit-OFF run is DEGRADED and can never
    # PASS or FAIL a criterion.
    credit_ok = getattr(cfg, "credit_signal", "ON") == "ON"
    prereq_ok = (span >= 15.0 and has08 and has20 and wf_ok and pit_ok
                 and frame_ok and credit_ok)
    why = ("ok" if prereq_ok else
           f"span {span:.1f}y (2008={has08}, 2020={has20}), "
           f"walk-forward {'ran' if wf_ok else 'did not run'}, "
           f"PIT tier {source_mode or 'unknown'} "
           f"({'lags applied' if cfg.pit_lag_enabled else 'NO lags'})"
           + ("" if credit_ok else
              "; credit signal OFF: PREREG applies to the credit-enabled "
              "engine")
           + ("" if frame_ok else
              f", price frame PARTIAL — "
              f"{_frame_gaps_line(price_frame_gaps)}"))
    return {"ok": prereq_ok, "span": span, "has08": has08, "has20": has20,
            "wf_ok": wf_ok, "pit_ok": pit_ok, "frame_ok": frame_ok,
            "credit_ok": credit_ok, "why": why}


# ── § 21.5 · run_prereg_eval ── v14.1 S7 + v14.5 FIX-3: evaluate the frozen PREREG for real.
def run_prereg_eval(df_results: pd.DataFrame, wf_metrics: dict,
                    cfg: Config, source_mode: str = "",
                    prereg_inputs: dict | None = None,
                    part_b: dict | None = None,
                    price_frame_gaps: dict | None = None) -> dict:
    """v14.1 S7 + v14.5 FIX-3: evaluate the frozen PREREG against a
    full-window run.

    C13 (prerequisite gates) evaluates FIRST: the criteria C01-C12 are only
    COUNTED when the audit prerequisites hold — window >= 15y incl. 2008 &
    2020, walk-forward actually ran, and a non-api tier is explicitly
    flagged APPROXIMATE_PIT.  On a short/clipped window the evaluator
    refuses to produce a single PASS (even for a beautiful short-window
    result) and reports BLOCKED — that is the honest answer.

    v14.5 FIX-3 status semantics (was: C01-C12 hard-coded "NOT RUN" and
    every not-run criterion collapsed into overall FAIL):
      per-criterion status in {PASS, FAIL, BLOCKED, NOT_RUN}
      overall = BLOCKED     if C13 fails (nothing is counted)
              | FAIL        if any criterion is FAIL
              | INCOMPLETE  if any criterion is NOT_RUN
              | PASS        only when all 13 are PASS

    `prereg_inputs` (optional; built by build_prereg_inputs §21.5b in
    main_async from the base run and the ONE shared price frame §17.6 — no
    globals, no second download) carries the net monthly strategy returns
    plus the monthly returns of the four benchmarks (SPY B&H, 60/40
    SPY/TLT, SMA10-only, cash) over IDENTICAL months.  Without it the
    benchmark-dependent criteria honestly report NOT_RUN.  Part A computes
    C01-C06 and C12 from the base run.

    `part_b` (optional; built by run_prereg_part_b §21.5c, gated behind the
    --prereg-full CLI flag in main_async) carries the C07-C11 robustness
    suites' real results (cost 2x/3x re-runs, ±50% publication lags, ±20%
    decision thresholds, the 3x3 grid).  Without it C07-C11 honestly report
    NOT_RUN ("run with --prereg-full") and the overall stays INCOMPLETE; a
    suite that ran but failed FAILs its criterion with the real error.

    v14.6 STEP A: `price_frame_gaps` (§17.7) is the frame-completeness
    gate — a PARTIAL price frame FAILS C13 (detail names the missing
    tickers and date ranges) so the overall is BLOCKED and no criterion is
    PASS or FAIL on that frame.

    Returns {"overall": PASS|FAIL|BLOCKED|INCOMPLETE, "criteria": {id:
    {status, detail, ...}}, "prereg_sha256": ...}.
    """
    crit: dict[str, dict] = {}
    # v14.5 part B: the gate computation lives in ONE place (§21.4b) so
    # main_async's --prereg-full gate and C13 can never drift apart.
    pre = _prereg_prereq_state(df_results, wf_metrics, cfg, source_mode,
                               price_frame_gaps)
    prereq_ok = pre["ok"]
    crit["C13_PREREQUISITE_GATES"] = {
        "status": "PASS" if prereq_ok else "FAIL",
        "detail": (f"span {pre['span']:.1f}y (2008={pre['has08']}, "
                   f"2020={pre['has20']}); "
                   f"walk-forward {'ran' if pre['wf_ok'] else 'did not run'}; "
                   f"PIT tier: {source_mode or 'unknown'} "
                   f"({'lags applied' if cfg.pit_lag_enabled else 'NO lags'}); "
                   # v14.6.2 STEP A: the credit-OFF gate comes BEFORE the
                   # frame clause so it survives the 150-char print cut —
                   # a degraded run says WHY it can never be counted.
                   + ("" if pre.get("credit_ok", True) else
                      "credit signal OFF: PREREG applies to the "
                      "credit-enabled engine; ")
                   + ("price frame: "
                      + ("complete" if pre["frame_ok"] else
                         f"PARTIAL — {_frame_gaps_line(price_frame_gaps)}"))),
    }
    blocked_note = ("not counted: prerequisite gates failed — the frozen "
                    "PREREG evaluates ONLY on the full 2008..latest window "
                    "with PIT data and a walk-forward that ran")

    def _not_run(cid: str, why: str) -> None:
        crit[cid] = {"status": "NOT_RUN", "detail": why}

    if not prereq_ok:
        for cid in PREREG["criteria"]:
            if cid != "C13_PREREQUISITE_GATES":
                crit[cid] = {"status": "BLOCKED", "detail": blocked_note}
    else:
        # ── v14.5 FIX-3 part A: compute what the base run can answer ──
        inputs = prereg_inputs or {}
        strat = inputs.get("strategy_net")
        bench = inputs.get("benchmarks") or {}
        sma10 = bench.get("SMA10-only")
        n_months = int(len(strat)) if isinstance(strat, pd.Series) else 0
        no_inputs = ("base-run benchmark inputs not supplied to this "
                     "evaluator — the full CLI (phase 4) builds them from "
                     "the base run and the shared price frame")

        # C01 — net Sharpe >= SMA10-only Sharpe + 0.15 (§16.1)
        if (isinstance(strat, pd.Series) and isinstance(sma10, pd.Series)
                and len(strat) > 1 and len(sma10) > 1):
            sh_s, sh_b = annualized_sharpe(strat), annualized_sharpe(sma10)
            thr = float(PREREG["criteria"]["C01_NET_SHARPE_BEATS_SMA10"]["threshold"])
            crit["C01_NET_SHARPE_BEATS_SMA10"] = {
                "status": "PASS" if sh_s >= sh_b + thr else "FAIL",
                "detail": (f"net Sharpe {sh_s:.2f} vs SMA10-only {sh_b:.2f} "
                           f"+ {thr:.2f} over {n_months} identical months")}
        else:
            _not_run("C01_NET_SHARPE_BEATS_SMA10", no_inputs)

        # C02 — 95% paired block-bootstrap CI lower bound of cum return
        #        (strategy − SMA10-only) > 0 (§16.6, deterministic seed)
        if (isinstance(strat, pd.Series) and isinstance(sma10, pd.Series)
                and len(strat) > 1):
            diff = (strat - sma10).dropna()
            ci = block_bootstrap_ci(diff)
            lb = float(ci["p5_cum_pct"])
            crit["C02_BOOTSTRAP_CI_POSITIVE"] = {
                "status": "PASS" if len(diff) > 0 and lb > 0.0 else "FAIL",
                "detail": (f"paired block-bootstrap on strategy−SMA10-only "
                           f"({len(diff)} paired months): CI lower bound "
                           f"(p5 cum) {lb:+.2f}% vs 0 (block=3, 5000 "
                           f"resamples, seed 42 — §16.6)")}
        else:
            _not_run("C02_BOOTSTRAP_CI_POSITIVE", no_inputs)

        # C03 — deflated Sharpe >= 0.95 (§16.12); N and the trial Sharpes
        #        come from the trial ledger (§16.10-16.11) — nothing invented
        if isinstance(strat, pd.Series) and len(strat) > 1:
            trial_sharpes = [t["sharpe"] for t in TRIAL_LEDGER
                             if isinstance(t, dict) and pd.notna(t.get("sharpe"))]
            dsr = deflated_sharpe(strat, trial_sharpes)
            thr = float(PREREG["criteria"]["C03_DEFLATED_SHARPE"]["threshold"])
            kinds: dict[str, int] = {}
            for t in TRIAL_LEDGER:
                k = t.get("kind", "?") if isinstance(t, dict) else "?"
                kinds[k] = kinds.get(k, 0) + 1
            comp = (", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
                    if kinds else "empty")
            if dsr["degenerate"]:
                d_note = "degenerate return series (zero variance / <2 months): DSR undefined, reported 0.000"
            elif trial_sharpes:
                d_note = (f"N={dsr['n_trials']} trial Sharpe(s) from the ledger "
                          f"({comp}); the ledger stores ANNUALISED per-trial "
                          f"Sharpe (§16.10), converted to monthly ÷√12")
            else:
                d_note = ("ledger holds no per-trial Sharpes — N=1, SR0=0 "
                          f"(ledger: {comp}; no trial count invented)")
            crit["C03_DEFLATED_SHARPE"] = {
                "status": "PASS" if dsr["dsr"] >= thr else "FAIL",
                "detail": (f"DSR {dsr['dsr']:.3f} vs {thr:.2f} (monthly SR "
                           f"{dsr['sr']:.3f}, SR0 {dsr['sr0']:.3f}, "
                           f"T={dsr['t_months']}; {d_note})")}
        else:
            _not_run("C03_DEFLATED_SHARPE", no_inputs)

        # C04 — net max drawdown <= 25% (§16.3)
        if isinstance(strat, pd.Series) and len(strat) > 0:
            mdd, trough, peak = max_drawdown(strat)
            thr = float(PREREG["criteria"]["C04_MAX_DRAWDOWN"]["threshold"] * 100)
            crit["C04_MAX_DRAWDOWN"] = {
                "status": "PASS" if abs(mdd) <= thr else "FAIL",
                "detail": (f"net max drawdown {abs(mdd):.1f}% (peak {peak} → "
                           f"trough {trough}) vs {thr:.0f}% over {n_months} "
                           f"months")}
        else:
            _not_run("C04_MAX_DRAWDOWN", no_inputs)

        # C05 — average gross leverage <= 1.5x (executed, from the base run)
        if (df_results is not None and not df_results.empty
                and "Gross Exposure" in df_results.columns):
            avg_lev = float(df_results["Gross Exposure"].mean())
            thr = float(PREREG["criteria"]["C05_AVG_LEVERAGE"]["threshold"])
            crit["C05_AVG_LEVERAGE"] = {
                "status": "PASS" if avg_lev <= thr else "FAIL",
                "detail": (f"avg gross leverage {avg_lev:.2f}x vs {thr:.1f}x "
                           f"(mean of the executed Gross Exposure column "
                           f"over {len(df_results)} months)")}
        else:
            _not_run("C05_AVG_LEVERAGE",
                     "no executed Gross Exposure column in the base run")

        # C06 — net cumulative return > 0 at 1x (current, unscaled) costs
        if isinstance(strat, pd.Series) and len(strat) > 0:
            cum = float((1.0 + strat).prod() - 1.0)
            crit["C06_COST_ROBUST_1X"] = {
                "status": "PASS" if cum > 0.0 else "FAIL",
                "detail": (f"net cum return {cum * 100:+.2f}% at 1x current "
                           f"costs over {n_months} months vs 0")}
        else:
            _not_run("C06_COST_ROBUST_1X", no_inputs)

        # C07-C11 — part B suites (§21.5c): only --prereg-full produced them
        if part_b is None:
            for cid in ("C07_COST_ROBUST_2X", "C08_COST_ROBUST_3X",
                        "C09_PUB_LAG_PERTURBATION",
                        "C10_THRESHOLD_SENSITIVITY", "C11_VARIANT_ROBUSTNESS"):
                _not_run(cid, "run with --prereg-full")
        else:
            crit.update(evaluate_part_b_criteria(part_b))

        # C12 — the 4-benchmark comparison table was actually PRINTED over
        #        identical months in this process (reporting requirement)
        printed = bool(inputs.get("benchmarks_printed"))
        have_all = all(isinstance(bench.get(k), pd.Series) and len(bench[k]) > 0
                       for k in ("SPY B&H", "60/40 SPY/TLT", "SMA10-only", "cash"))
        if printed and have_all and isinstance(strat, pd.Series) and n_months > 0:
            crit["C12_BENCHMARK_SET_REPORTED"] = {
                "status": "PASS",
                "detail": (f"4-benchmark comparison table printed over "
                           f"{n_months} identical months (SPY B&H, 60/40 "
                           f"SPY/TLT, SMA10-only, cash)")}
        else:
            _not_run("C12_BENCHMARK_SET_REPORTED",
                     "the 4-benchmark comparison table was not printed over "
                     "identical months in this process")

    n_fail = sum(1 for c in crit.values() if c["status"] == "FAIL")
    n_not_run = sum(1 for c in crit.values() if c["status"] == "NOT_RUN")
    overall = ("BLOCKED" if not prereq_ok
               else "FAIL" if n_fail
               else "INCOMPLETE" if n_not_run
               else "PASS")
    return {"overall": overall, "criteria": crit,
            "prereg_sha256": prereg_sha256(),
            "trial_ledger": trial_ledger_summary()}


# ── § 21.5b · build_prereg_inputs ── v14.5 FIX-3 (part A): the real benchmark inputs for the PREREG.
def build_prereg_inputs(df_results: pd.DataFrame, bt: "Backtester",
                        cfg: Config) -> dict | None:
    """v14.5 FIX-3 (part A): build the real inputs run_prereg_eval (§21.5)
    needs — the net monthly strategy returns plus the monthly returns of
    the four PREREG benchmarks over IDENTICAL months — from the base run
    (df_results) and the ONE shared price frame (bt._daily_data, §17.6).
    No globals, no second download.

    Benchmarks: SPY buy-and-hold, 60/40 SPY/TLT and cash are the columns
    the base backtest already reports per month; SMA10-only is a REAL
    second Backtester run over the same daily frame — long SPY when the
    prior month-end close is above its own 10-month SMA, else cash — so it
    goes through the SAME cost and financing accounting as the strategy
    (no hand-rolled second cost model).  It runs unlevered (a benchmark
    copy of cfg with min=max_leverage=1.0 pins executable_leverage to
    exactly 1.0x on every overlay path) and without the VXX hedge sleeve
    (vxx_allocation=0); a defensive scenario_key keeps the 50% SPY
    fallback out of flat months so cash months stay flat.

    Returns {"months", "strategy_net", "benchmarks", "benchmarks_printed"
    (False — main_async flips it AFTER the table actually printed),
    "provenance"} or None when the base run cannot support the comparison.
    """
    if (df_results is None or df_results.empty
            or getattr(bt, "_daily_data", None) is None
            or bt._daily_data.empty):
        return None
    daily = bt._daily_data
    try:
        spy_close = daily["Close"]["SPY"]
    except (KeyError, TypeError, IndexError):
        return None
    if spy_close.dropna().empty:
        return None
    spy_m = spy_close.resample(FREQ_ME).last().dropna()
    sma_m = spy_m.rolling(cfg.trend_sma_window).mean()
    spy_by_m = spy_m.copy()
    spy_by_m.index = spy_by_m.index.strftime("%Y-%m")
    sma_by_m = sma_m.copy()
    sma_by_m.index = sma_by_m.index.strftime("%Y-%m")

    def _in_market(m: str) -> bool:
        """SMA10 rule for trade month m, decided ONLY from the prior
        completed month (PIT: known at m's entry open — the same
        information the engine's own trend cap keys on)."""
        prev = (pd.Timestamp(m + "-01") - pd.DateOffset(months=1)).strftime("%Y-%m")
        c, s = spy_by_m.get(prev, np.nan), sma_by_m.get(prev, np.nan)
        return bool(pd.notna(c) and pd.notna(s) and float(c) > float(s))

    bench_cfg = replace(cfg, min_leverage=1.0, max_leverage=1.0,
                        vxx_allocation=0.0)
    bench_signals = [
        {"month": m, "longs": ["SPY"] if _in_market(m) else [], "shorts": [],
         "scenario_key": "STAGFLATIONARY_DRAG",   # defensive: no SPY fallback
         "regime": "SMA10-only benchmark (PREREG C01/C02)",
         "confidence": 1.0, "runner_up_confidence": 0.0, "dominance": 0.0,
         "conviction_leverage": 1.0, "regime_months": 3,
         "financing_rate": np.nan}
        for m in df_results["Month"]]
    bench_bt = Backtester(bench_cfg)
    bench_bt._daily_data = daily            # the ONE shared frame — no refetch
    bench_df = bench_bt.run(bench_signals, bench_cfg)
    if bench_df is None or bench_df.empty:
        return None
    bench_months = set(bench_df["Month"])
    common = [m for m in df_results["Month"] if m in bench_months]
    if not common:
        return None
    strat_ix = df_results.set_index("Month")
    bench_ix = bench_df.set_index("Month")

    def _col(frame: pd.DataFrame, col: str) -> pd.Series:
        return (frame[col].astype(float) / 100.0).loc[common]

    benchmarks = {
        "SPY B&H": _col(strat_ix, "SPY B&H %"),
        "60/40 SPY/TLT": _col(strat_ix, "60/40 SPY/TLT %"),
        "SMA10-only": _col(bench_ix, "Net Portfolio Return %"),
        "cash": _col(strat_ix, "Cash %"),
    }
    return {
        "months": list(common),
        "strategy_net": _col(strat_ix, "Net Portfolio Return %"),
        "benchmarks": benchmarks,
        "benchmarks_printed": False,   # main_async flips this AFTER printing
        "provenance": {
            "window": f"{common[0]}..{common[-1]}",
            "n_months": len(common),
            "sma10_in_market_months": [m for m in common if _in_market(m)],
            "sma10_rule": (f"long SPY when prior month-end close > its "
                           f"{cfg.trend_sma_window}-month SMA, else cash"),
            "sma10_costs": ("engine cost model (§18.2): turnover bps + "
                            "financing; unlevered 1.0x, no VXX sleeve"),
        },
    }


# ── § 21.5c · PREREG part B (v14.5 FIX-3) — the C07-C11 re-run suites ────────
# The frozen rules (PREREG["criteria"], read-only):
#   C07  net cumulative return > 0 at 2x current costs
#   C08  net cumulative return > 0 at 3x current costs
#   C09  every publication lag scaled +/-50%: net Sharpe > 0 AND month-level
#        regime agreement with the baseline lags >= 70%
#   C10  decision thresholds (min_confidence, dominance_saturation, kill-switch
#        z, crash guard, VIX trigger) each scaled +/-20%: net Sharpe > 0 in
#        EVERY perturbation
#   C11  >= 80% of the 3x3 grid (min_confidence x dominance_saturation) has
#        positive net Sharpe
# Every variant re-runs the SAME engine path as the base run — run_engine
# (§21.3) then a Backtester (§18.2) seeded with the ONE shared daily price
# frame (bt._daily_data, §17.6) — on the ALREADY-FETCHED raw data: no refetch,
# no new data source, no mocks, and the WalkForwardEngine is NOT re-run.
# A variant that fails to run FAILs its criterion with the REAL error in the
# detail — nothing is skipped silently and no error is swallowed.

# · PREREG_COST_FIELDS — what "current costs" scales: every broker-charged
#   friction in the §18.2 cost model.  financing_flat_annual (the policy-rate
#   fallback) is the cost of money, not a trading friction, and is NOT scaled.
PREREG_COST_FIELDS: tuple = ("cost_bps_per_trade", "vxx_cost_bps",
                             "financing_spread", "short_borrow_bps_annual")


# ── § 21.5c.1 · build_cost_variant ── C07/C08: all cost frictions x scale.
def build_cost_variant(cfg: Config, scale: float) -> Config:
    """C07/C08: scale every cost friction in the engine's cost model by
    `scale` (2.0 for C07, 3.0 for C08).  Scaled fields (PREREG_COST_FIELDS):
    cost_bps_per_trade, vxx_cost_bps, financing_spread,
    short_borrow_bps_annual.  NOT scaled: financing_flat_annual (the
    policy-rate fallback — the cost of money itself, and the cash benchmark's
    basis — is not a trading friction)."""
    return replace(cfg, **{f: float(getattr(cfg, f)) * float(scale)
                           for f in PREREG_COST_FIELDS})


# ── § 21.5c.2 · scaled_lag_days ── C09: one lag, scaled, round-half-up.
def scaled_lag_days(lag: int, scale: float) -> int:
    """Scale one publication lag (days) by `scale`, round-half-up, floored at
    0.  Round-half-up (not banker's) so 7d at +50% and at -50% both move a
    full day (7*1.5=10.5->11, 7*0.5=3.5->4) — symmetric perturbations."""
    return max(0, int(float(lag) * float(scale) + 0.5))


# ── § 21.5c.3 · build_lag_variant_cfg ── C09: cfg with every lag scaled.
def build_lag_variant_cfg(cfg: Config, scale: float) -> Config:
    """C09: every publication lag in cfg.pit_lag_days scaled by `scale`
    (1.5 = +50%, 0.5 = -50%).  Series identity and order are preserved; a
    0-day (same-evening) lag stays 0."""
    if not cfg.pit_lag_days:
        return cfg
    return replace(cfg, pit_lag_days=tuple(
        (sid, scaled_lag_days(lag, scale)) for sid, lag in cfg.pit_lag_days))


# ── § 21.5c.4 · lagged_raw_copy ── C09: apply the (scaled) lags ONCE to the PRE-lag raw.
def lagged_raw_copy(raw_pre_pit: dict[str, pd.Series],
                    cfg_v: Config) -> dict[str, pd.Series]:
    """C09: a fresh raw dict with cfg_v's lags applied exactly ONCE to the
    PRE-lag series (raw_pre_pit — the observation-date-indexed dict captured
    in main_async BEFORE _apply_pit_lags ran on the base).  _apply_pit_lags
    REPLACES dict slots with re-indexed copies and never mutates the Series,
    so the input dict is left untouched; lags can never be applied twice."""
    shifted, _notes = _apply_pit_lags(dict(raw_pre_pit), cfg_v)
    return shifted


# ── § 21.5c.5 · build_threshold_variants ── C10: 5 thresholds x +/-20% = 10 cfgs.
def build_threshold_variants(cfg: Config) -> list[tuple[str, Config]]:
    """C10: the five decision thresholds named by the frozen rule, each
    scaled x0.8 and x1.2 (symmetric +/-20% of the value, sign preserved):
      min_confidence          (classification gate, §14.1)
      dominance_saturation    (conviction-leverage margin, §10.6)
      killswitch_credit_z     (credit kill-switch, §14.1)
      crash_guard_1m_ret      (crash guard, §15)
      vix_trigger_level       (VXX overlay gate, §15)
    Returns 10 (label, cfg) pairs; nothing else is perturbed."""
    fields = ("min_confidence", "dominance_saturation", "killswitch_credit_z",
              "crash_guard_1m_ret", "vix_trigger_level")
    out: list[tuple[str, Config]] = []
    for fname in fields:            # `fname`, not `field`: shadows dataclasses.field
        base_val = float(getattr(cfg, fname))
        for tag, scale in (("x0.8", 0.8), ("x1.2", 1.2)):
            val = base_val * scale
            out.append((f"{fname} {tag}={val:.4g}",
                        replace(cfg, **{fname: val})))
    return out


# ── § 21.5c.6 · build_grid_variants ── C11: the 3x3 min_confidence x dominance_saturation grid.
def build_grid_variants(cfg: Config) -> list[tuple[str, Config]]:
    """C11: the full 3x3 grid cfg.grid_min_confidence x
    cfg.grid_dominance_saturation (the same two parameters the walk-forward
    grid search tunes) -> 9 (label, cfg) pairs, including the base point."""
    out: list[tuple[str, Config]] = []
    for mc in cfg.grid_min_confidence:
        for ds in cfg.grid_dominance_saturation:
            out.append((f"min_confidence={mc:.2f}, dominance_saturation={ds:.2f}",
                        replace(cfg, min_confidence=float(mc),
                                dominance_saturation=float(ds))))
    return out


# ── § 21.5c.7 · regime_agreement ── C09: month-level agreement vs the baseline-lag run.
def regime_agreement(base_df: pd.DataFrame,
                     variant_df: pd.DataFrame) -> tuple[float, int]:
    """C09: share (0..1) of months with the SAME post-hysteresis scenario_key
    as the baseline run, over the common decision months.  Returns
    (agreement, n_common_months)."""
    if (base_df is None or variant_df is None or base_df.empty
            or variant_df.empty
            or not {"date", "scenario_key"} <= set(base_df.columns)
            or not {"date", "scenario_key"} <= set(variant_df.columns)):
        return (0.0, 0)
    b = base_df.set_index("date")["scenario_key"]
    v = variant_df.set_index("date")["scenario_key"]
    common = b.index.intersection(v.index)
    if len(common) == 0:
        return (0.0, 0)
    same = (b.loc[common] == v.loc[common]).sum()
    return (float(same) / float(len(common)), int(len(common)))


# ── § 21.5c.8 · _variant_metrics ── net cum / net Sharpe of one variant run.
def _variant_metrics(df_results: pd.DataFrame) -> dict:
    r = df_results["Net Portfolio Return %"].astype(float) / 100.0
    return {"n_months": int(len(r)),
            "cum": float((1.0 + r).prod() - 1.0),
            "sharpe": float(annualized_sharpe(r))}


# ── § 21.5c.9 · _run_full_window_variant ── ONE variant through the SAME engine path.
async def _run_full_window_variant(raw: dict[str, pd.Series], cfg_v: Config,
                                   daily_frame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run ONE part-B variant through exactly the base run's engine path:
    run_engine (§21.3: FeatureEngine -> get_macro_regime -> apply_hysteresis)
    -> parse_signals -> Backtester (§18.2) on the ONE shared daily price
    frame.  No refetch (a missing frame raises instead of downloading), no
    walk-forward.  Returns (df_results, final_df); raises with the real error
    otherwise."""
    if daily_frame is None or (hasattr(daily_frame, "empty") and daily_frame.empty):
        raise RuntimeError("shared daily price frame is empty — part B never "
                           "refetches (no new download, no new data source)")
    final_df = await run_engine(raw, cfg_v)
    if final_df is None or final_df.empty:
        raise RuntimeError("run_engine returned an empty panel for this variant")
    signals = parse_signals(final_df)
    vbt = Backtester(cfg_v)
    vbt._daily_data = daily_frame          # the ONE shared frame — no refetch
    df_v = vbt.run(signals, cfg_v)
    if df_v is None or df_v.empty:
        raise RuntimeError("backtest returned no rows for this variant")
    return df_v, final_df


# ── § 21.5c.10 · _live_counter ── progress UX: an in-place "k/N" line.
def _live_counter(label: str, n: int):
    """Progress UX for a suite: tick() rewrites one line in place as
    '  <label>: k/N — <note>'; the caller ends the line with print()."""
    state = {"k": 0}

    def tick(note: str = "") -> None:
        state["k"] += 1
        sys.stdout.write(f"\r  {label}: {state['k']}/{n}"
                         + (f" — {note}" if note else ""))
        sys.stdout.flush()
    return tick


# ── § 21.5c.11 · run_prereg_part_b ── run the four suites, return their real results.
async def run_prereg_part_b(raw: dict[str, pd.Series],
                            raw_pre_pit: dict[str, pd.Series] | None,
                            cfg: Config, bt: "Backtester",
                            base_final_df: pd.DataFrame,
                            base_df_results: pd.DataFrame,
                            source_mode: str = "",
                            emit=print) -> dict:
    """v14.5 FIX-3 (part B): the C07-C11 re-run suites on the already-fetched
    data (gated behind --prereg-full by main_async; the caller has already
    verified the prerequisite gates).  Four suites, each one _phase line with
    a live k/N counter:
      costs x3        1x (determinism/consistency check vs the base run),
                      2x (C07), 3x (C08)
      lags x2         every publication lag scaled +50% and -50% (C09)
      thresholds x10  the five decision thresholds each x0.8/x1.2 (C10)
      grid x9         the 3x3 min_confidence x dominance_saturation grid (C11)
    Returns the part_b dict consumed by run_prereg_eval / evaluate_part_b_
    criteria; per-variant failures are recorded with their REAL errors and
    never swallowed."""
    daily = getattr(bt, "_daily_data", None)
    out: dict = {"costs": {"variants": {}, "errors": {}},
                 "lags": {"variants": {}, "errors": {}, "skipped_reason": None},
                 "thresholds": {"variants": {}, "errors": {}},
                 "grid": {"variants": {}, "errors": {}},
                 "base_cum": None}

    async def _run_one(label: str, cfg_v: Config, raw_v: dict[str, pd.Series]):
        """One variant -> (metrics, agreement, final_df) or raises."""
        df_v, final_v = await _run_full_window_variant(raw_v, cfg_v, daily)
        m = _variant_metrics(df_v)
        agree, n_common = regime_agreement(base_final_df, final_v)
        return m, agree, n_common

    # ── suite 1: cost scaling x3 (1x consistency check + C07 2x + C08 3x) ──
    with _phase("PREREG part-B: cost scaling x3 (1x/2x/3x)"):
        tick = _live_counter("costs", 3)
        base_m = _variant_metrics(base_df_results)
        out["base_cum"] = base_m["cum"]
        for scale in (1.0, 2.0, 3.0):
            key = f"{scale:.0f}x"
            try:
                m, _agree, _n = await _run_one(key, build_cost_variant(cfg, scale), raw)
                out["costs"]["variants"][key] = m
                note = (f"cum {m['cum'] * 100:+.2f}%" if scale != 1.0 else
                        f"cum {m['cum'] * 100:+.2f}% (base {base_m['cum'] * 100:+.2f}%)")
                tick(note)
            except Exception as e:                      # record, never swallow
                out["costs"]["errors"][key] = f"{type(e).__name__}: {e}"
                tick(f"{key} FAILED")
        print()
        v1 = out["costs"]["variants"].get("1x")
        if v1 is not None:
            drift_pp = abs(v1["cum"] - base_m["cum"]) * 100.0
            out["costs"]["one_x_consistency_pp"] = drift_pp
            if drift_pp > 0.05:
                emit(_c(f"  ⚠  1x-cost re-run cum {v1['cum']*100:+.2f}% vs base "
                        f"{base_m['cum']*100:+.2f}% (drift {drift_pp:.3f}pp) — "
                        f"variant runs must be deterministic", "33"))
            else:
                emit(f"  i  1x-cost re-run reproduces the base net cum "
                     f"({v1['cum']*100:+.2f}%, drift {drift_pp:.3f}pp)")

    # ── suite 2: publication lags +/-50% (C09) ─────────────────────────────
    skip = None
    if source_mode == "api":
        skip = ("API tier replays true realtime vintages — the publication-"
                "lag perturbation is defined for the APPROXIMATE_PIT tiers "
                "whose cfg.pit_lag_days lags the engine actually applies")
    elif not cfg.pit_lag_enabled:
        skip = "pit_lag_enabled is False — no publication lags to perturb"
    elif not cfg.pit_lag_days:
        skip = "cfg.pit_lag_days is empty — no publication lags to perturb"
    elif raw_pre_pit is None:
        skip = "pre-lag raw was not captured — cannot re-apply scaled lags once"
    out["lags"]["skipped_reason"] = skip
    if skip is not None:
        emit(f"  i  lag suite skipped: {skip}")
    else:
        with _phase("PREREG part-B: publication lags +/-50% x2"):
            tick = _live_counter("lags", 2)
            for scale, key in ((1.5, "+50%"), (0.5, "-50%")):
                try:
                    cfg_v = build_lag_variant_cfg(cfg, scale)
                    raw_v = lagged_raw_copy(raw_pre_pit, cfg_v)
                    m, agree, n_common = await _run_one(key, cfg_v, raw_v)
                    out["lags"]["variants"][key] = {**m, "agreement": agree,
                                                    "n_common": n_common}
                    tick(f"Sharpe {m['sharpe']:.2f}, agreement {agree:.0%}")
                except Exception as e:
                    out["lags"]["errors"][key] = f"{type(e).__name__}: {e}"
                    tick(f"lags {key} FAILED")
            print()

    # ── suite 3: decision thresholds +/-20% (C10) ──────────────────────────
    with _phase("PREREG part-B: decision thresholds +/-20% x10"):
        pairs = build_threshold_variants(cfg)
        tick = _live_counter("thresholds", len(pairs))
        for label, cfg_v in pairs:
            try:
                m, _agree, _n = await _run_one(label, cfg_v, raw)
                out["thresholds"]["variants"][label] = m
                tick(f"Sharpe {m['sharpe']:.2f}")
            except Exception as e:
                out["thresholds"]["errors"][label] = f"{type(e).__name__}: {e}"
                tick(f"{label} FAILED")
        print()

    # ── suite 4: the 3x3 grid (C11) ────────────────────────────────────────
    with _phase("PREREG part-B: confidence x dominance grid x9"):
        pairs = build_grid_variants(cfg)
        tick = _live_counter("grid", len(pairs))
        for label, cfg_v in pairs:
            try:
                m, _agree, _n = await _run_one(label, cfg_v, raw)
                out["grid"]["variants"][label] = m
                tick(f"Sharpe {m['sharpe']:.2f}")
            except Exception as e:
                out["grid"]["errors"][label] = f"{type(e).__name__}: {e}"
                tick(f"{label} FAILED")
        print()

    # ── the compact part-B table: criterion | worst-case | threshold | status
    ev = evaluate_part_b_criteria(out)
    emit("  part-B robustness summary (worst case vs frozen threshold):")
    for cid, c in ev.items():
        emit(f"    {cid:30s} {c.get('worst', ''):22} vs {c.get('thr', ''):24}"
             f" {c['status']}")
    return out


# ── § 21.5c.12 · evaluate_part_b_criteria ── pure C07-C11 aggregation over a part_b dict.
def evaluate_part_b_criteria(part_b: dict) -> dict:
    """Pure aggregation of a part_b result dict (§21.5c.11) into the C07-C11
    criterion dicts {status, detail, worst, thr}.  Used by run_prereg_eval
    AND by run_prereg_part_b's compact table, so the printed table and the
    frozen verdict can never disagree.  A variant that failed to run FAILs
    its criterion with the real error; a skipped suite (e.g. the lag suite on
    the API tier) is NOT_RUN with the reason."""
    crit: dict[str, dict] = {}

    def _fmt_pct(x: float) -> str:
        return f"{x * 100:+.2f}%"

    # C07 / C08 — net cum return > 0 at 2x / 3x current costs
    for cid, key in (("C07_COST_ROBUST_2X", "2x"), ("C08_COST_ROBUST_3X", "3x")):
        suite = part_b.get("costs") or {}
        err = (suite.get("errors") or {}).get(key)
        m = (suite.get("variants") or {}).get(key)
        scale = 2.0 if cid.startswith("C07") else 3.0
        if err:
            crit[cid] = {"status": "FAIL",
                         "detail": f"{key}-cost rerun failed: {err}",
                         "worst": "error", "thr": "> 0"}
        elif m:
            ok = m["cum"] > 0.0
            drift = suite.get("one_x_consistency_pp")
            drift_note = ("" if drift is None or drift <= 0.05 else
                          f" | WARNING 1x re-run drift {drift:.2f}pp vs base")
            crit[cid] = {
                "status": "PASS" if ok else "FAIL",
                "detail": (f"net cum return {_fmt_pct(m['cum'])} at {key} "
                           f"current costs ({m['n_months']} months) vs > 0 — "
                           f"all cost frictions scaled x{scale:.0f} "
                           f"(trade bps, VXX bps, financing spread, short "
                           f"borrow; financing_flat_annual NOT scaled — it is "
                           f"the cost of money, not a friction)"
                           f"{drift_note}"),
                "worst": _fmt_pct(m["cum"]), "thr": "> 0"}
        else:
            crit[cid] = {"status": "NOT_RUN",
                         "detail": f"no {key}-cost result in the part-B suite",
                         "worst": "—", "thr": "> 0"}

    # C09 — every publication lag scaled +/-50%: net Sharpe > 0 AND
    #       month-level regime agreement with the baseline lags >= 70%
    suite = part_b.get("lags") or {}
    skip = suite.get("skipped_reason")
    errs = suite.get("errors") or {}
    variants = suite.get("variants") or {}
    if skip:
        crit["C09_PUB_LAG_PERTURBATION"] = {
            "status": "NOT_RUN", "detail": f"lag suite skipped: {skip}",
            "worst": "—", "thr": "Sharpe > 0, agree >= 70%"}
    elif errs:
        first = next(iter(errs.items()))
        crit["C09_PUB_LAG_PERTURBATION"] = {
            "status": "FAIL",
            "detail": (f"lag perturbation failed: {first[0]} -> {first[1]}"
                       + (f" (+{len(errs) - 1} more)" if len(errs) > 1 else "")),
            "worst": "error", "thr": "Sharpe > 0, agree >= 70%"}
    elif variants:
        thr = float(PREREG["criteria"]["C09_PUB_LAG_PERTURBATION"]["threshold"])
        worst_sharpe = min(v["sharpe"] for v in variants.values())
        min_agree = min(v["agreement"] for v in variants.values())
        n_common = min(v["n_common"] for v in variants.values())
        ok = worst_sharpe > 0.0 and min_agree >= thr
        per = "; ".join(f"{k}: Sharpe {v['sharpe']:.2f}, agreement "
                        f"{v['agreement']:.1%} ({v['n_common']} months)"
                        for k, v in sorted(variants.items()))
        crit["C09_PUB_LAG_PERTURBATION"] = {
            "status": "PASS" if ok else "FAIL",
            "detail": (f"every publication lag scaled +/-50% — worst net "
                       f"Sharpe {worst_sharpe:.2f} (> 0), min month-level "
                       f"regime agreement {min_agree:.1%} vs threshold "
                       f"{thr:.0%} over {n_common} common months | {per}"),
            "worst": f"Sharpe {worst_sharpe:.2f}, agree {min_agree:.0%}",
            "thr": "Sharpe > 0, agree >= 70%"}
    else:
        crit["C09_PUB_LAG_PERTURBATION"] = {
            "status": "NOT_RUN", "detail": "no lag-perturbation results",
            "worst": "—", "thr": "Sharpe > 0, agree >= 70%"}

    # C10 — each of the five decision thresholds scaled +/-20%: net Sharpe > 0
    #       in EVERY perturbation
    suite = part_b.get("thresholds") or {}
    errs = suite.get("errors") or {}
    variants = suite.get("variants") or {}
    if errs:
        first = next(iter(errs.items()))
        crit["C10_THRESHOLD_SENSITIVITY"] = {
            "status": "FAIL",
            "detail": (f"threshold perturbation failed: {first[0]} -> "
                       f"{first[1]}"
                       + (f" (+{len(errs) - 1} more)" if len(errs) > 1 else "")),
            "worst": "error", "thr": "Sharpe > 0"}
    elif variants:
        worst_label, worst = min(variants.items(), key=lambda kv: kv[1]["sharpe"])
        n_pos = sum(1 for v in variants.values() if v["sharpe"] > 0.0)
        ok = n_pos == len(variants) and len(variants) == 10
        crit["C10_THRESHOLD_SENSITIVITY"] = {
            "status": "PASS" if ok else "FAIL",
            "detail": (f"{n_pos}/{len(variants)} +/-20% threshold "
                       f"perturbations have net Sharpe > 0; worst "
                       f"{worst['sharpe']:.2f} ({worst_label}) vs > 0"),
            "worst": f"Sharpe {worst['sharpe']:.2f}", "thr": "Sharpe > 0"}
    else:
        crit["C10_THRESHOLD_SENSITIVITY"] = {
            "status": "NOT_RUN", "detail": "no threshold-perturbation results",
            "worst": "—", "thr": "Sharpe > 0"}

    # C11 — >= 80% of the 3x3 grid has positive net Sharpe
    suite = part_b.get("grid") or {}
    errs = suite.get("errors") or {}
    variants = suite.get("variants") or {}
    thr = float(PREREG["criteria"]["C11_VARIANT_ROBUSTNESS"]["threshold"])
    if errs:
        first = next(iter(errs.items()))
        crit["C11_VARIANT_ROBUSTNESS"] = {
            "status": "FAIL",
            "detail": (f"grid run failed: {first[0]} -> {first[1]}"
                       + (f" (+{len(errs) - 1} more)" if len(errs) > 1 else "")),
            "worst": "error", "thr": ">= 80% of 9"}
    elif variants:
        k = sum(1 for v in variants.values() if v["sharpe"] > 0.0)
        n = len(variants)
        share = k / n if n else 0.0
        worst_label, worst = min(variants.items(), key=lambda kv: kv[1]["sharpe"])
        crit["C11_VARIANT_ROBUSTNESS"] = {
            "status": "PASS" if share >= thr else "FAIL",
            "detail": (f"{k}/{n} grid points (min_confidence x "
                       f"dominance_saturation) have positive net Sharpe "
                       f"({share:.0%} vs >= {thr:.0%}); worst Sharpe "
                       f"{worst['sharpe']:.2f} ({worst_label})"),
            "worst": f"{k}/{n} ({share:.0%})", "thr": ">= 80% of 9"}
    else:
        crit["C11_VARIANT_ROBUSTNESS"] = {
            "status": "NOT_RUN", "detail": "no grid results",
            "worst": "—", "thr": ">= 80% of 9"}
    return crit


# ── v14.1 S8: PAPER MODE — the forward record that can earn a STRATEGY ──────
# verdict.  One row per decision month in paper_record.csv; NEVER a
# performance claim (no realized returns are recorded by the engine).
# ── § 21.6 · paper_record_path
def paper_record_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "paper_record.csv")


# ── § 21.7 · run_paper_mode ── --paper: record the CURRENT signal as a forward, timestamped row.
def run_paper_mode(cfg: Config = CFG) -> int:
    """--paper: record the CURRENT signal as a forward, timestamped row.

    This is the mechanism by which STRATEGY claims stop being PROVISIONAL:
    >= 12 consecutive decision-month records, reviewed against realized
    outcomes OUTSIDE this engine.  The row contains the decision and the
    intended basket/leverage only — never a return.  No backtest is run and
    no backtest_results.csv is written.
    """
    # live fetch ALWAYS: fetch_all() itself routes to the frozen snapshot
    # when FORCE_SNAPSHOT is set (or to public-csv/cache tiers offline), so
    # --paper works both online and against the shipped snapshot.
    out = mrs(live=True, cfg=cfg)
    if "error" in out:
        print(f"PAPER MODE ERROR: {out['error']}", file=sys.stderr)
        return 2
    final, sig = out["signals_df"], out["latest_signal"]
    row = final.iloc[-1]
    rec = {
        "recorded_utc": datetime.now(ZoneInfo("UTC")).isoformat(timespec="seconds"),
        "decision_month": str(row["date"]),
        "trade_month": sig["month"],
        "scenario_key": sig["scenario_key"],
        "regime": sig["regime"],
        "confidence": round(float(row.get("confidence", float("nan"))), 4),
        "dominance": round(float(row.get("dominance", float("nan"))), 4),
        "regime_months": int(row.get("regime_months", 1)),
        "longs": ";".join(sig["longs"]),
        "shorts": ";".join(sig["shorts"]),
        "conviction_leverage": float(row.get("conviction_leverage", float("nan"))),
        "lev_basis": row.get("lev_basis", "unadjusted_prior"),
        "source_mode": "snapshot" if FORCE_SNAPSHOT else "live",
    }
    path = paper_record_path()
    header = not os.path.isfile(path)
    with open(path, "a", encoding="utf-8") as fh:
        if header:
            fh.write(",".join(rec) + "\n")
        fh.write(",".join(str(rec[k]) for k in rec) + "\n")
    print("PAPER RECORD appended (forward record — NOT a performance claim):")
    for k, v in rec.items():
        print(f"  {k:22s} {v}")
    n_so_far = sum(1 for _ in open(path, encoding="utf-8")) - 1
    print(f"\n  paper_record.csv now holds {n_so_far} row(s); a STRATEGY "
          f"verdict needs >= 12 consecutive decision months reviewed against "
          f"realized outcomes.  Until then every strategy claim is PROVISIONAL.")
    return 0


# ── v14.1 S2 (audit D2): 9-state readiness framework ────────────────────────
READINESS_STATES: tuple = (
    "CODE_INTEGRITY", "DATA_INTEGRITY", "PIT_COMPLIANCE",
    "HISTORICAL_COVERAGE", "BACKTEST_VALIDITY", "WALK_FORWARD",
    "STRATEGY_VALIDATION", "OPERATIONAL", "LIVE_TRADING",
)


# ── § 21.8 · verify_snapshot_hashes ── v14.1 S2: verify every file listed in snapshot/hashes.json
def verify_snapshot_hashes(snapshot_dir: str) -> tuple[int, list[str], int]:
    """v14.1 S2: verify every file listed in snapshot/hashes.json
    (files_sha256).  Returns (n_ok, [failed relpaths], n_total); n_total == 0
    when no manifest exists."""
    try:
        with open(os.path.join(snapshot_dir, "hashes.json"),
                  "r", encoding="utf-8") as fh:
            files = json.load(fh).get("files_sha256", {})
    except (OSError, ValueError) as e:
        # v14.4 section 3: a missing/corrupt manifest is reported with the
        # real cause, not treated as an empty manifest.
        _emit("  " + _describe_failure("local file",
                                      f"file={os.path.join(snapshot_dir, 'hashes.json')}",
                                      exc=e))
        return 0, [], 0
    ok, bad = 0, []
    for rel, expect in sorted(files.items()):
        try:
            digest = _sha256_file(os.path.join(snapshot_dir, rel))
        except OSError:
            bad.append(rel)
            continue
        if digest == expect:
            ok += 1
        else:
            bad.append(rel)
    return ok, bad, len(files)


# ── § 21.9 · _crash_window_stats ── (spy_max_dd, strat_max_dd_during_crash, crash_present) using m…
def _crash_window_stats(df_results: pd.DataFrame) -> tuple[float, float, bool]:
    """(spy_max_dd, strat_max_dd_during_crash, crash_present) using monthly
    compounding; dd values are negative fractions."""
    spy = df_results["SPY B&H %"].astype(float) / 100.0
    strat = df_results["Net Portfolio Return %"].astype(float) / 100.0
    sc = (1 + spy).cumprod()
    spy_dd = (sc / sc.cummax() - 1.0)
    tc = (1 + strat).cumprod()
    strat_dd = (tc / tc.cummax() - 1.0)
    deep = spy_dd <= -0.20
    return (float(spy_dd.min()),
            float(strat_dd[deep].min()) if bool(deep.any()) else 0.0,
            bool(deep.any()))


# ── § 21.10 · build_readiness_report ── v14.1 S2 (audit D2): the 9-state readiness report. Every l…
def build_readiness_report(df_results: pd.DataFrame, cfg: Config,
                           wf_metrics: dict, source_mode: str,
                           credit_full_history: bool,
                           extra: dict | None = None) -> list[dict]:
    """v14.1 S2 (audit D2): the 9-state readiness report.  Every line is
    COMPUTED from the run's own artifacts — no hard-coded PASS lines, no
    benchmark comparison dressed up as validation.  Status vocabulary:
    PASS | FAIL | BLOCKED | PARTIAL | NOT RUN | INFO.
    Returns a list of {state, status, evidence} rows (a state may emit more
    than one row)."""
    ex = extra or {}
    raw: dict[str, pd.Series] | None = ex.get("raw")
    rep: list[dict] = []

    def add(state: str, status: str, evidence: str) -> None:
        rep.append({"state": state, "status": status, "evidence": evidence})

    # 1 ── CODE_INTEGRITY
    _score_errors = _diag().score_errors
    add("CODE_INTEGRITY",
        "PASS" if not _score_errors else "FAIL",
        f"meds v{__version__}; frozen PREREG sha256:{prereg_sha256()[:12]}… "
        f"({len(PREREG['criteria'])} criteria); {len(_score_errors)} scenario-"
        f"score evaluation error(s) this run; {len(SCENARIOS)} scenarios x "
        f"{len(INDICATORS)} FRED series wired")

    # 2 ── DATA_INTEGRITY
    snap = _snapshot_dir()
    if snap and os.path.isfile(os.path.join(snap, "hashes.json")):
        ok, bad, total = verify_snapshot_hashes(snap)
        add("DATA_INTEGRITY",
            "PASS" if (total > 0 and not bad) else "FAIL",
            (f"snapshot/hashes.json verified {ok}/{total} files"
             + (f"; MISMATCH: {bad[:5]}" if bad else "")))
    else:
        add("DATA_INTEGRITY", "NOT RUN",
            "no snapshot/hashes.json present to verify (offline cache/api tier)")
    if raw is not None:
        core_missing = [c for c in cfg.core_columns if c not in raw]
        add("DATA_INTEGRITY",
            "PASS" if not core_missing else "FAIL",
            "core series present" if not core_missing else
            f"core series MISSING: {core_missing}")
        # v14.6.2 STEP A: an OFF run says so in the readiness report too —
        # the banner already said it loudly above.
        if getattr(cfg, "credit_signal", "ON") == "OFF":
            add("DATA_INTEGRITY", "INFO",
                "credit signal OFF this run: BAMLH0A0HYM2/BAMLC0A0CM dropped "
                "from the panel, CREDIT_CRUNCH + "
                "EARLY_CYCLE_RE_ACCELERATION excluded, credit kill-switch "
                "OFF — results NOT comparable to credit-ON runs")

    # 3 ── PIT_COMPLIANCE
    if source_mode == "api":
        add("PIT_COMPLIANCE", "PASS",
            "strict point-in-time: FRED API realtime vintages replayed by "
            "publication date")
    elif cfg.pit_lag_enabled:
        n_lag = sum(1 for _, lag in cfg.pit_lag_days if int(lag) > 0)
        max_lag = _max_pit_lag_days(cfg)
        add("PIT_COMPLIANCE", "PARTIAL",
            f"APPROXIMATE_PIT: publication lags applied to {n_lag} delayed-"
            f"release series (max +{max_lag}d) so month-end rows only consume "
            f"publisher-released values; realtime REVISIONS NOT replayed "
            f"(needs a FREDAPI key)")
    else:
        add("PIT_COMPLIANCE", "FAIL",
            "current vintage with NO publication-lag approximation — "
            "delayed-release series leak their observation month")

    # 4 ── HISTORICAL_COVERAGE
    if df_results is None or df_results.empty:
        add("HISTORICAL_COVERAGE", "FAIL", "backtest produced no rows")
    else:
        months = pd.to_datetime(df_results["Month"], format="%Y-%m")
        span = ((months.max() - months.min()).days / 365.25
                if len(months) > 1 else 0.0)
        has08 = bool(((months >= "2008-01-01") & (months <= "2008-12-31")).any())
        has20 = bool(((months >= "2020-01-01") & (months <= "2020-12-31")).any())
        need = (pd.Timestamp(cfg.output_start)
                - pd.DateOffset(months=cfg.credit_expanding_min_periods))
        # v14.6.2 STEP A: a credit-OFF run has an empty history_guard set
        # (the series were dropped) — the unlock advice still names the two
        # CSVs that would turn the signal back ON.
        unlock = ("; ".join(
            os.path.join(cfg.history_csv_dir, sid + "_full.csv")
            for sid in (cfg.history_guard_mandatory or CREDIT_MODE_SERIES)))
        add("HISTORICAL_COVERAGE",
            "PASS" if (span >= 15.0 and has08 and has20 and credit_full_history)
            else "FAIL",
            f"window {months.min():%Y-%m}..{months.max():%Y-%m} ({span:.1f}y; "
            f"2008={has08}, 2020={has20}); ICE BofA history reaches "
            f"{'far enough' if credit_full_history else 'NOT far enough'} "
            f"(needs obs on/before {need.date()}).  Unlock the full 2008+ "
            f"backtest: {unlock} (percent units, from <=2006-12), or set "
            f"FREDAPI for vintage access")

    # 5 ── BACKTEST_VALIDITY
    if df_results is None or df_results.empty:
        add("BACKTEST_VALIDITY", "FAIL", "backtest produced no rows")
    else:
        add("BACKTEST_VALIDITY", "PASS",
            f"{len(df_results)} trade months simulated with costs, financing "
            f"and borrow fees")
        if all(c in df_results.columns for c in
               ("Net Portfolio Return %", "Gross Ret %", "Cost %", "Financing %")):
            resid = (df_results["Net Portfolio Return %"]
                     - (df_results["Gross Ret %"] - df_results["Cost %"]
                        - df_results["Financing %"])).abs().max()
            add("BACKTEST_VALIDITY",
                "PASS" if float(resid) <= 0.02 else "FAIL",
                f"accounting identity Net = Gross - Cost - Financing holds to "
                f"{float(resid):.4f}pp (rounding tolerance 0.02pp)")
        if all(c in df_results.columns for c in
               ("Net Portfolio Return %", "SPY B&H %", "60/40 SPY/TLT %")):
            r = df_results["Net Portfolio Return %"] / 100.0
            spy = df_results["SPY B&H %"] / 100.0
            mix = df_results["60/40 SPY/TLT %"] / 100.0
            gap = float(((1 + r).prod() - (1 + spy).prod()) * 100)
            add("BACKTEST_VALIDITY", "INFO",
                f"benchmark comparison over the identical {len(df_results)} "
                f"months: MEDS {((1+r).prod()-1)*100:+.2f}% vs SPY "
                f"{((1+spy).prod()-1)*100:+.2f}% (gap {gap:+.1f}pp), 60/40 "
                f"SPY/TLT {((1+mix).prod()-1)*100:+.2f}% — a computed "
                f"comparison, NOT a validation criterion")
        miss = (df_results["Missing Price Tickers"].fillna("").astype(str)
                .str.len() > 0).sum() if "Missing Price Tickers" in df_results.columns else 0
        add("BACKTEST_VALIDITY", "PASS" if miss == 0 else "PARTIAL",
            f"{int(miss)} month(s) listed assets without price data "
            f"(weights restricted to backed positions)"
            if miss else "every listed asset had prices every month")
        shorts = 0
        if "Short Assets" in df_results.columns:
            shorts = int((df_results["Short Assets"].fillna("").astype(str)
                          .str.len() > 0).sum())
        add("BACKTEST_VALIDITY", "PASS" if shorts > 0 else "PARTIAL",
            f"short leg fired in {shorts}/{len(df_results)} months"
            + ("" if shorts else
               " — the L/S short leg NEVER fired on this window: borrow-fee "
               "and short-P&L paths untested on genuine data"))
        vxx_na = int((df_results.get("VXX Regime", pd.Series(["CALM"] * len(df_results)))
                      .fillna("N/A") == "N/A").sum())
        add("BACKTEST_VALIDITY", "PASS" if vxx_na == 0 else "PARTIAL",
            f"VXX overlay price coverage missing in {vxx_na}/{len(df_results)} "
            f"months (overlay cannot trade without VXX/VIX data — e.g. before "
            f"VXX's 2018 listing in this snapshot)" if vxx_na else
            "VXX overlay price data covered every month")
        # v14.1 S5 (audit D6): credit kill-switch structural coverage
        if raw is not None:
            ks = credit_killswitch_coverage(raw, cfg)
            if ks["n_total"]:
                add("BACKTEST_VALIDITY",
                    "PASS" if ks["killswitch_active_share"] > 0.9 else "PARTIAL",
                    f"credit kill-switch (HY-OAS expanding z, "
                    f"{cfg.credit_expanding_min_periods}m min) structurally "
                    f"active only from {ks['first_valid_month'] or 'never'} — "
                    f"INACTIVE for {ks['n_inactive']}/{ks['n_total']} output "
                    f"months ({ks['note']})")
        spy_dd, strat_dd, crash = _crash_window_stats(df_results)
        if crash:
            add("BACKTEST_VALIDITY",
                "PASS" if strat_dd > spy_dd else "FAIL",
                f"crash behaviour: during SPY's >=20% drawdown (max "
                f"{spy_dd:.1%}) the strategy drew down {strat_dd:.1%}")
        else:
            add("BACKTEST_VALIDITY", "FAIL",
                "no SPY >= 20% drawdown in the window — crash behaviour "
                "untested")

    # 6 ── WALK_FORWARD
    if wf_metrics and "error" not in wf_metrics:
        add("WALK_FORWARD", "PASS",
            f"walk-forward ran on real data: {wf_metrics.get('n_oos_months', 0)} "
            f"OOS months, OOS Sharpe {wf_metrics.get('oos_sharpe', 0):.2f}")
    elif wf_metrics and wf_metrics.get("error", "").startswith("WF skipped"):
        add("WALK_FORWARD", "FAIL", wf_metrics["error"])
    else:
        add("WALK_FORWARD", "NOT RUN",
            "walk-forward produced no folds this run")

    # 7 ── STRATEGY_VALIDATION
    cov_pass = any(r["state"] == "HISTORICAL_COVERAGE" and r["status"] == "PASS"
                   for r in rep)
    wf_pass = any(r["state"] == "WALK_FORWARD" and r["status"] == "PASS"
                  for r in rep)
    if cov_pass and wf_pass:
        add("STRATEGY_VALIDATION", "NOT RUN",
            f"PREREG sha256:{prereg_sha256()[:12]}… — 13 frozen criteria; "
            f"phase 4 above evaluates part A (C01-C06, C12, C02, C03), "
            f"C07-C11 need the part-B suites")
    else:
        add("STRATEGY_VALIDATION", "BLOCKED",
            f"PREREG sha256:{prereg_sha256()[:12]}… — 13 frozen criteria, "
            f"0 evaluated; BLOCKED on HISTORICAL_COVERAGE "
            f"({'PASS' if cov_pass else 'FAIL'}) and WALK_FORWARD "
            f"({'PASS' if wf_pass else 'not PASS'}).  Strategy claims remain "
            f"PROVISIONAL")

    # 8 ── OPERATIONAL
    add("OPERATIONAL",
        "PARTIAL" if source_mode == "snapshot" else "PASS",
        "run completed; terminal report only — a default run writes no files"
        + ("; --snapshot forces offline mode: the verified-cache WRITE path "
           "was not exercised this run" if source_mode == "snapshot" else ""))

    # 9 ── LIVE_TRADING (can never pass inside the engine)
    add("LIVE_TRADING", "NOT RUN",
        "requires >= 12 months of forward paper records (--paper, one row "
        "per decision month); this engine can never mark LIVE_TRADING as "
        "PASS by itself")
    return rep


# ── § 21.11 · print_readiness_check ── v14 section 10 / v14.1 S2: the 9-state readiness report pri…
def print_readiness_check(df_results: pd.DataFrame, cfg: Config,
                          wf_metrics: dict, source_mode: str,
                          credit_full_history: bool,
                          extra: dict | None = None) -> None:
    """v14 section 10 / v14.1 S2: the 9-state readiness report printed at the
    end of every run.  Never prints advice to trade, and never claims
    validation the run did not earn."""
    rep = build_readiness_report(df_results, cfg, wf_metrics, source_mode,
                                 credit_full_history, extra)
    print("  READINESS REPORT (9 states; PASS|FAIL|BLOCKED|PARTIAL|NOT RUN|INFO)")
    for state in READINESS_STATES:
        rows = [r for r in rep if r["state"] == state]
        for r in rows:
            print(f"  [{r['status']:<8}] {state:<20s} {r['evidence']}")
    not_passed = [r for r in rep if r["status"] != "PASS" and r["status"] != "INFO"]
    if not_passed:
        print("\n  NOT VALIDATED FOR LIVE TRADING")
        for r in not_passed:
            print(f"    - {r['state']}: {r['evidence']}")


# ── § 21.12 · vintage_revision_table ── v13.2 G-1: compare the SAME observation date across data v…
def vintage_revision_table(obs_rows, probe_obs_dates) -> pd.DataFrame:
    """v13.2 G-1: compare the SAME observation date across data vintages.

    obs_rows: iterable of (observation_date, realtime_start, value) — exactly
    the (date, realtime_start, value) triplets FRED returns for a series with
    realtime metadata.

    For every probed OBSERVATION date the table reports the FIRST PRINT (the
    value with the earliest realtime_start) versus the LATEST vintage value —
    a true revision of the same economic period. Probe dates without
    observations are simply absent; nothing is fabricated by comparing two
    different observation periods (that was the v13.1 bug: it compared the
    PIT reading as-of date d — an OLDER observation — against the revised
    value AT d, i.e. a different period, and labelled the difference a
    revision).
    """
    rows = [{"obs_date": r[0], "realtime_start": r[1], "value": r[2]} for r in obs_rows]
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["obs_date"] = pd.to_datetime(df["obs_date"], errors="coerce")
    df["realtime_start"] = pd.to_datetime(df["realtime_start"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["obs_date", "realtime_start", "value"])
    out = []
    for d in probe_obs_dates:
        ts = pd.Timestamp(d)
        sub = df[df["obs_date"] == ts].sort_values("realtime_start")
        if sub.empty:
            continue
        first, last = sub.iloc[0], sub.iloc[-1]
        fp, lv = float(first["value"]), float(last["value"])
        out.append({
            "obs_date": ts.strftime("%Y-%m-%d"),
            "first_print_date": first["realtime_start"].strftime("%Y-%m-%d"),
            "first_print": round(fp, 4),
            "latest_vintage_date": last["realtime_start"].strftime("%Y-%m-%d"),
            "latest_value": round(lv, 4),
            "revision": round(lv - fp, 4),
            "abs_revision": round(abs(lv - fp), 4),
            "rel_revision_pct": round(100.0 * abs(lv - fp) / abs(fp), 4) if fp != 0 else None,
            "n_vintages": int(len(sub)),
        })
    return pd.DataFrame(out)


# ── § 21.13 · run_vintage_audit ── G-1 (v13.2): revision audit keyed strictly on OBSERVATION dates…
async def run_vintage_audit(client: FREDClient, cfg: Config) -> pd.DataFrame:
    """G-1 (v13.2): revision audit keyed strictly on OBSERVATION dates — the
    first print of each probed observation versus its latest revised vintage.
    (v13.1 compared an as-of PIT reading for an older period against the
    revised value of a different period and called the gap a revision.)

    v13.3 M-4: returns an empty table immediately when the run was NOT
    served by the FRED API tier — the public CSV and snapshot tiers carry
    no vintage/realtime metadata to audit.
    v14.6.1 BUG 6: the audit compares RAW observations, so its fetch now
    receives levels (units='lin' — see _fetch_obs_json) and needs no
    pc1/chg transform: first_print / latest_value / revision are level
    revisions, rel_revision_pct is well-defined on levels."""
    if getattr(client, "source_mode", "api") != "api":
        return pd.DataFrame()
    frames = []
    series_ids = ("CPIAUCSL", "PAYEMS", "A191RL1Q225SBEA")
    probes = ("2013-09-01", "2018-12-01", "2020-06-01", "2023-09-01", "2025-03-01")
    for sid in series_ids:
        spec = next(s for s in INDICATORS if s.series_id == sid)
        obs = await client._fetch_obs_json(spec)
        rows = [(o.get("date"), o.get("realtime_start"), o.get("value"))
                for o in obs if o.get("value") not in (".", None, "")]
        tbl = vintage_revision_table(rows, probes)
        if not tbl.empty:
            tbl.insert(0, "series", sid)
            frames.append(tbl)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ── § 21.14 · main_async ── v14.4 U3: ONE short report — a header, one line per phase with el…
async def main_async(cfg: Config = CFG,
                     explicit_dates: frozenset = frozenset(),
                     prereg_full: bool = False) -> pd.DataFrame:
    """v14.4 U3: ONE short report — a header, one line per phase with elapsed
    seconds, the verdict block (readiness), and the RESULT line printed by
    main_cli.  Returns the monthly results frame (used by --csv).
    v14.5 FIX-3 (part B): `prereg_full` (the --prereg-full flag) also runs
    the C07-C11 robustness suites (§21.5c) before the PREREG verdict."""
    global _PHASE_TIMES
    _PHASE_TIMES = []
    diag = _diag()                     # CLI sink: aliases the module globals
    print(_c("╔" + "═" * 78 + "╗", "36"))
    print(_c("║  " + f"MACRO REGIME & L/S SCENARIO ENGINE v{__version__}".ljust(76) + "║", "36"))
    print(_c("║  " + "one command · terminal only · no files written".ljust(76) + "║", "36"))
    print(_c("╚" + "═" * 78 + "╝", "36"))

    # ── phase 1: data ─────────────────────────────────────────────────────
    with _phase("data fetch (FRED tiers + guards)"):
        client = FREDClient(cfg.fred_api_key, cfg)
        raw = await client.fetch_all(INDICATORS)

        # J-1 (v13.2): NO-GO conditions raise (CLI maps them to exit code 2)
        # instead of printing an error and exiting 0.  v14.4 section 3: the
        # message carries the real per-series causes + tier facts, no advice.
        if not raw:
            causes = "\n".join(
                f"  {sid}: {text}" for sid, text in sorted(client.fetch_failures.items()))
            raise MedsValidationError(
                "No FRED data from ANY source tier (API, public fredgraph.csv, "
                "verified cache, snapshot).\n"
                + ("Per-series causes:\n" + causes if causes else
                   "No tier produced a usable series.")
                + ("\nTier notes: " + "; ".join(client.tier_failure_notes)
                   if client.tier_failure_notes else ""))

        for n in client.tier_failure_notes:
            print(_c(f"  ⚠  {n}", "33"))
        if client.source_mode != "api":
            print(_c(f"  ⚠  FRED source: {client.source_note}", "33"))
            # v13.3 M-2: clip the window to what the data supports — but NEVER
            # touch dates the user pinned explicitly on the command line.
            if not ({"fetch_start", "output_start", "output_end"} & set(explicit_dates)):
                cfg, raw, aw_notes = _auto_window(raw, cfg)
                for n in aw_notes:
                    print(_c(f"  ⚠  {n}", "33"))
            else:
                print("      explicit --fetch-start/--output-start/--output-end given: "
                      "the window is NOT auto-clipped; unsatisfiable credit "
                      "history then means credit-OFF (auto mode, loud banner) "
                      "or exit 2 (--require-credit).")

        # v14 FIX-5 / v14.1 S1: publication-lag PIT approximation on non-API
        # tiers, plus the one-line per-observation PIT audit.
        # v14.5 FIX-3 (part B): keep the PRE-lag series (observation-date
        # index) for the C09 ±50% lag re-runs — _apply_pit_lags REPLACES dict
        # slots with re-indexed COPIES and never mutates the Series, so this
        # shallow copy stays unlagged with no refetch.
        raw_pre_pit = dict(raw)
        if client.source_mode != "api" and cfg.pit_lag_enabled:
            raw, pit_notes = _apply_pit_lags(raw, cfg)
            for n in pit_notes:
                print(f"  i  {n}")
            pit_tbl = pit_observation_report(raw, cfg)
            if not pit_tbl.empty:
                delayed = pit_tbl[pit_tbl["lag_days"] > 0]
                realtime = int((pit_tbl["lag_days"] == 0).sum())
                print(f"  i  PIT audit: {len(pit_tbl)} series — {len(delayed)} "
                      f"delayed to first-publication month-end (max "
                      f"{int(pit_tbl['lag_days'].max())}d), {realtime} realtime (lag 0d)")
                _bad = delayed[(delayed["first_visible_month_end"] == "") |
                               (delayed["pit_mode"] != "APPROXIMATE_LAG")]
                if not _bad.empty:
                    print(_c(f"  ⚠  PIT audit anomalies: {', '.join(_bad['series_id'])}", "33"))

        vintage = ("strict point-in-time (FRED API vintages)"
                   if client.source_mode == "api"
                   else ("APPROXIMATE_PIT: publication lags applied, realtime "
                         "revisions NOT replayed (current vintage)"
                         if cfg.pit_lag_enabled
                         else "current vintage (revised data, NOT point-in-time)"))
        print(f"  data tier: {client.source_mode or 'none'} | window: "
              f"{cfg.fetch_start} -> {cfg.output_start} -> {cfg.output_end} | {vintage}")
        if client.source_mode != "api":
            _dn = _dotenv_status()
            if _dn:
                print(f"  i  {_dn}")
        for n in client.pc1_check_notes:
            print(f"  i  {n}")

        # v14.6.2 STEP A: decide ONCE, before the guards, whether the ICE
        # BofA OAS credit signal is usable (both BAMLH0A0HYM2 and
        # BAMLC0A0CM reaching the ensure_history `need` date, after the same
        # data/<SID>_full.csv repair).  Usable (or "required" mode): the
        # v14.6.1 path continues byte-identical.  Not usable + "auto": the
        # credit signal is OFF for the WHOLE run — both series leave the
        # panel and every mandatory set, the two credit-dependent scenarios
        # are excluded, and the guards below judge the remaining core
        # series exactly as before.
        raw, credit_info = resolve_credit_mode(raw, cfg)
        if credit_info["credit"] == "OFF":
            cfg = _credit_off_cfg(cfg)

        # B-1: refuse to run on a silently re-weighted score (real causes).
        assert_core_series(raw, cfg, failures=client.fetch_failures)
        raw, hist_notes = ensure_history(raw, cfg)       # v13.1 H-1 / v13.2 E-1
        if diag.score_errors:
            print(_c(f"  ⚠  {len(diag.score_errors)} scenario-score evaluation(s) "
                     f"raised and were excluded from scoring "
                     f"(first: {diag.score_errors[0]})", "33"))
        for note in list(client.pit_fallbacks) + hist_notes:  # v13.1 H-1 / H-2
            print(_c(f"  ⚠  {note}", "33"))
        if client.last_failures:
            print(_c("  ⚠  non-core series not served (excluded from scoring): "
                     f"{', '.join(client.last_failures)}", "33"))
        print(_c(f"  ✓ {len(raw)}/{len(INDICATORS)} FRED series served "
                 f"(tier: {client.source_mode})", "32"))

        if client.source_mode == "api":
            vint_audit = await run_vintage_audit(client, cfg)
            if vint_audit.empty:
                print("  i  vintage audit: no rows (no probed revisions)")
            else:
                print(f"  i  vintage audit: {len(vint_audit)} probed observation "
                      f"dates across {vint_audit['series'].nunique()} series; "
                      f"max |revision| "
                      f"{float(vint_audit['abs_revision'].max()):.2f}")
        else:
            # v13.3 M-4: the non-API tiers carry no vintage metadata.
            print(f"  i  vintage audit skipped — the '{client.source_mode}' tier "
                  f"has no vintage metadata (needs a FREDAPI key).")
        uni_audit = universe_audit(["SPY", "QQQ", "IWM", "VXX"], cfg.output_start)
        if not uni_audit.empty and "source" in uni_audit.columns:
            srcs = uni_audit["source"].value_counts().to_dict()
            print(f"  i  universe audit: {len(uni_audit)} tickers "
                  f"(first-trade-date sources: {srcs})")

    # v14.6.2 STEP A: the LOUD banner, right after the data phase — a
    # credit-OFF run must never be mistaken for a credit-ON result.
    if credit_info["credit"] == "OFF":
        for _b in credit_info["banner"]:
            print(_c(_b, "33"))
        for _p in credit_info["problems"]:
            print(_c(f"  cause: {_p}", "33"))

    # v14.6.2 STEP A: the backtest and walk-forward still run and print on a
    # credit-OFF window, but every line is labelled DEGRADED — never a
    # PASS/FAIL verdict from a degraded run.
    _degraded = (" — DEGRADED (credit signal OFF)"
                 if credit_info["credit"] == "OFF" else "")

    # ── phase 2: walk-forward ─────────────────────────────────────────────
    with _phase("walk-forward validation" + _degraded):
        if _degraded:
            print(_c("  ⚠  DEGRADED (credit signal OFF): the numbers below are "
                     "NOT comparable to credit-ON runs", "33"))
        wf_engine = WalkForwardEngine(cfg)
        oos_df, param_df, wf_metrics = wf_engine.run(raw, cfg)
        if wf_metrics and "error" not in wf_metrics:
            # v14.7 4d: degenerate OOS statistics render as n/a, not nan%.
            def _wf(v, spec="{:+.1f}%"):
                if v is None or (isinstance(v, float) and v != v):
                    return "n/a"
                return spec.format(v)

            print(f"  OOS: Sharpe {_wf(wf_metrics.get('oos_sharpe'), '{:.2f}')} | "
                  f"cum {_wf(wf_metrics.get('oos_cum_return_pct'))} | "
                  f"maxDD {_wf(wf_metrics.get('oos_max_drawdown_pct'), '{:.1f}%')} | "
                  f"alpha {_wf(wf_metrics.get('oos_alpha_annualized_pct'))} | "
                  f"{wf_metrics.get('n_oos_months', 0)} OOS months")
            if "n_grid_failures" in param_df.columns and int(param_df["n_grid_failures"].sum()) > 0:
                print(_c(f"  ⚠  grid search: {int(param_df['n_grid_failures'].sum())} "
                         f"failed configurations across folds (each logged with "
                         f"its exception)", "33"))
        else:
            _wf_msg = wf_metrics.get("error", "no folds produced results")
            print(f"  {_wf_msg}")              # v14 FIX-8: a normal line
        # v13.3 M-1: surface any price-tier fallback that happened so far.
        for n in dict.fromkeys(diag.price_notes):      # de-duplicated, order kept
            print(_c(f"  ⚠  {n}", "33"))

    # ── phase 3: backtest ─────────────────────────────────────────────────
    with _phase("full historical backtest" + _degraded):
        if _degraded:
            print(_c("  ⚠  DEGRADED (credit signal OFF): the numbers below are "
                     "NOT comparable to credit-ON runs", "33"))
        final_df = await run_engine(raw, cfg)
        if final_df.empty:
            raise MedsValidationError("Feature panel empty — not enough history / missing core series.")
        counts = final_df["scenario"].value_counts()
        top3 = ", ".join(f"{n} ({c / len(final_df):.0%})" for n, c in counts.head(3).items())
        print(f"  regime mix: {top3}")
        path_diag = classification_path_diagnostic(final_df)
        if path_diag:
            pp = path_diag["path_pct"]
            ks_pct = sum(v for k, v in pp.items() if str(k).startswith("kill_switch"))
            fb_pct = sum(v for k, v in pp.items()
                         if k in ("soft_landing_fallback", "neutral_low_confidence",
                                  "neutral_no_scores"))
            print(f"  classification: scored {pp.get('scored', 0):.0f}% | "
                  f"kill-switch {ks_pct:.0f}% | fallback {fb_pct:.0f}%")
        # v14.1 S5 (audit D6): credit kill-switch structural coverage
        ks = credit_killswitch_coverage(raw, cfg)
        if ks["n_total"]:
            print(_c(f"  ⚠  credit kill-switch structurally active only from "
                     f"{ks['first_valid_month'] or 'never'} "
                     f"(INACTIVE {ks['n_inactive']}/{ks['n_total']} output months)",
                     "33"))
        elif credit_info["credit"] == "OFF":
            # v14.6.2 STEP A: said explicitly, never left silent.
            print(_c("  i  credit kill-switch OFF: credit unavailable "
                     "(signal dropped this run)", "33"))

        signals = parse_signals(final_df)
        bt = Backtester(cfg)
        df_results = bt.run(signals, cfg)
        if df_results.empty:
            # J-1: an empty backtest is a NO-GO, not a silent empty report.
            # v14.4 section 3: the REAL yfinance messages, verbatim.
            for e in diag.yf_errors[-5:]:
                print(_c(f"  ⚠  {e}", "33"), file=sys.stderr)
            raise MedsValidationError(
                "Backtest returned no rows — no price data from any price tier "
                "(live Yahoo, verified cache, snapshot). Real per-ticker causes "
                "above / in YF_DOWNLOAD_ERRORS.")
        if "Missing Price Tickers" in df_results.columns:
            miss = int((df_results["Missing Price Tickers"].astype(str).str.len() > 0).sum())
            if miss:
                print(_c(f"  ⚠  {miss} month(s) had listed assets WITHOUT price data "
                         f"(weights restricted to backed positions)", "33"))
        # compact performance summary (the verdict numbers)
        print(generate_performance_summary(df_results, cfg).to_string(index=False))
        # the CURRENT signal — the one line the owner actually acts on
        last = final_df.iloc[-1]
        last_sig = signals[-1]
        print(_c(f"  ▶ NOW: {last['scenario_key']} ({last['scenario']}, "
                 f"{last['cycle_phase']}) confidence {last['confidence']:.2f} | "
                 f"next month {last_sig['month']}: L[{','.join(last_sig['longs'])}] "
                 f"S[{','.join(last_sig['shorts'])}] @ "
                 f"{last['conviction_leverage']:.2f}x", "1"))
        ledger = build_daily_ledger(signals, bt._daily_data, df_results,
                                    bt.month_weights, cfg)
        if ledger.empty:
            print("  i  daily ledger: not built (no preloaded daily frame)")
        else:
            max_res = float(ledger["residual_abs"].fillna(0).max())
            print(f"  i  daily ledger reconciles {ledger['Month'].nunique()} months "
                  f"to {max_res:.1e} (telescoping proof)")
        print_vxx_coverage_note(df_results)
        vxx_df = vxx_ledger(df_results, cfg)
        if vxx_df.empty:
            print("  i  VXX hedge: no trades activated")
        else:
            fires = len(vxx_df)
            pnl = float(vxx_df["pnl_dollars_per_100k"].sum())
            print(f"  i  VXX hedge: {fires} activation(s), "
                  f"{pnl:+.0f} USD per 100k notional")
        df_attr = analyze_ticker_performance(signals, cfg.output_start, cfg.output_end, cfg)
        if not df_attr.empty and "Net PnL %" in df_attr.columns:
            head = df_attr.head(3)["Ticker"].tolist()
            tail = df_attr.tail(3)["Ticker"].tolist()
            print(f"  i  attribution: best {head} · worst {tail}")

    # ── phase 4: preregistered evaluation ─────────────────────────────────
    with _phase("preregistered evaluation (PREREG C01-C13)"):
        # v14.5 FIX-3: build the REAL benchmark inputs from the base run and
        # the ONE shared price frame (no globals, no second download), print
        # the 4-benchmark comparison over identical months (C12 is a
        # reporting requirement — PASS only if the table actually printed),
        # then evaluate the criteria for real.
        pinputs = build_prereg_inputs(df_results, bt, cfg)
        if pinputs is not None:
            prov = pinputs["provenance"]
            rows = ([("strategy (net)", pinputs["strategy_net"])]
                    + list(pinputs["benchmarks"].items()))
            print(f"  benchmarks over {prov['n_months']} identical months "
                  f"({prov['window']}):")
            for name, s in rows:
                cum = float((1.0 + s).prod() - 1.0)
                sh = annualized_sharpe(s)
                mdd, _, _ = max_drawdown(s)
                print(f"    {name:<16} cum {cum * 100:+8.1f}% | Sharpe "
                      f"{sh:5.2f} | maxDD {abs(mdd):5.1f}%")
            pinputs["benchmarks_printed"] = True
        # v14.5 FIX-3 (part B): --prereg-full runs the C07-C11 robustness
        # suites (§21.5c) on the already-fetched data — but ONLY when the C13
        # prerequisite gates hold: the frozen PREREG evaluates on the full
        # 2008..latest window, and burning ~24 backtests on a window the
        # evaluator will refuse to count is not a result.
        # v14.6 STEP A: the shared frame the backtest ACTUALLY used is judged
        # with the SAME §17.7 logic the retry gate used — still PARTIAL (after
        # the bounded retries) FAILS C13 naming the missing tickers and date
        # ranges, so the overall verdict is BLOCKED and NO criterion is
        # counted on that frame.
        pgaps = _frame_gaps(bt._daily_data, _CANONICAL_PRICE_TICKERS,
                            *Backtester._price_window(cfg),
                            end_anchor=_price_need_end(cfg),
                            judge_end=_frame_served_live())
        part_b = None
        if prereg_full:
            pre = _prereg_prereq_state(df_results, wf_metrics, cfg,
                                       client.source_mode, pgaps)
            if pre["ok"]:
                part_b = await run_prereg_part_b(
                    raw, raw_pre_pit, cfg, bt, final_df, df_results,
                    client.source_mode)
            else:
                print(_c("  ⚠  --prereg-full: part-B suites skipped — "
                         f"prerequisite gates fail ({pre['why']}); the "
                         "frozen PREREG evaluates only on the full "
                         "2008..latest window (C07-C11 stay NOT_RUN)", "33"))
        ev = run_prereg_eval(df_results, wf_metrics, cfg, client.source_mode,
                             prereg_inputs=pinputs, part_b=part_b,
                             price_frame_gaps=pgaps)
        print(f"  PREREG {ev['overall']} (sha256 {ev['prereg_sha256'][:12]}…, "
              f"{len(PREREG['criteria'])} frozen criteria)")
        for cid, c in ev["criteria"].items():
            # v14.5 FIX-3 (3a): PASS green, FAIL red, BLOCKED/NOT_RUN yellow
            col = ("32" if c["status"] == "PASS"
                   else "31" if c["status"] == "FAIL" else "33")
            print(_c(f"    [{c['status']:<8}] {cid}: {c['detail'][:150]}", col))

    # ── phase 5: readiness verdict ────────────────────────────────────────
    with _phase("readiness report"):
        hy = raw.get("BAMLH0A0HYM2")
        credit_full = (hy is not None and not hy.empty
                       and pd.Timestamp(hy.index.min())
                       <= pd.Timestamp(cfg.output_start)
                       - pd.DateOffset(months=cfg.credit_expanding_min_periods))
        print_readiness_check(df_results, cfg, wf_metrics, client.source_mode,
                              credit_full, extra={"raw": raw, "uni_audit": uni_audit})

    # ── v14.6 STEP B: the data fingerprint (print-only, <= 12 lines) ────────
    # Per canonical ticker: rows + first/last date, plus the 12-hex sha256
    # of the whole Close panel — two runs whose numbers differ can be
    # compared at a glance.  Nothing is ever written to a file.
    print_price_fingerprint(price_fingerprint(bt._daily_data))
    return df_results


# ── § 21.15 · main
def main(cfg: Config = CFG, explicit_dates: frozenset = frozenset(),
         prereg_full: bool = False) -> pd.DataFrame:
    return asyncio.run(main_async(cfg, explicit_dates, prereg_full))



# ═══════════════════════════════════════════════════════════════════════════
#  § 22 · SHORT API — mrs / mrs_at / mrs_ml / tpl
# ═══════════════════════════════════════════════════════════════════════════
TPL_PATH = _dp("manual_inputs.txt")


# ── § 22.1 · tpl ── Write the manual-input template .txt. Returns the path.
def tpl(path: str = TPL_PATH) -> str:
    """Write the manual-input template .txt. Returns the path."""
    bar = "=" * 78
    L = [bar,
         " MANUAL MACRO INPUT TEMPLATE  —  meds.py",
         bar, "",
         "Supply monthly data as a pandas DataFrame (DatetimeIndex)",
         "OR a dict {'dates': [...], 'CPIAUCSL': [...], 'DFF': [...], ...}.",
         "Need >= 60 months of history.",
         "IMPORTANT: row M must contain the values KNOWN by the END of month M",
         "(point-in-time). Do not put a month-M release that was first",
         "published during month M+1 into row M.",
         "Column names MUST match the Series IDs below exactly.", "",
         f"{'#':>3}  {'Series ID':<22} {'Name':<34} {'Units':<6} {'Category':<12}",
         "-" * 78]
    for i, s in enumerate(INDICATORS, 1):
        L.append(f"{i:>3}  {s.series_id:<22} {s.name:<34} {s.units:<6} {s.category:<12}")
    L += ["", "Auto-derived: " + ", ".join(DERIVED_SERIES),
          "", "CSV header example:",
          "  " + ",".join(["date"] + [s.series_id for s in INDICATORS]), "",
          "Example usage:", "  import pandas as pd, meds as me",
          "  df = pd.read_csv('my_macro.csv', index_col='date', parse_dates=True)",
          "  out = me.mrs_at('2024-06-30', live=False, data=df)", bar]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


# ── § 22.2 · _coerce ── v13.2 F-1 rewrite: robust coercion of manual macro inputs.
def _coerce(data) -> dict[str, pd.Series]:
    """v13.2 F-1 rewrite: robust coercion of manual macro inputs.

    Accepts a pandas DataFrame (DatetimeIndex or date-like index), or a dict
    of {'dates': [...], SERIES_ID: values} where values may be a list, tuple,
    numpy array or pandas Series (a Series may carry its own DatetimeIndex).

    v13.1 bugs fixed here:
    * `data.get("dates") or data.get("date")` evaluated the truth value of
      numpy arrays / pandas Series -> "ambiguous truth value" ValueError.
      Now explicit None checks.
    * NaN cleanup happened BEFORE index alignment, so any series containing
      a NaN was either silently dropped (length mismatch after dropna) or
      crashed on `x.index = idx`. Alignment now happens FIRST.
    * duplicate/unsorted dates and invalid timestamps are handled
      explicitly (sorted, deduplicated keep-last, invalid rows dropped)
      instead of discarding the whole frame.
    """
    if data is None:
        return {}
    out: dict[str, pd.Series] = {}

    def _clean(x: pd.Series) -> pd.Series | None:
        """Align-then-clean: drop NaN values and NaT-indexed rows, sort,
        deduplicate (keep last). Returns None if nothing survives."""
        x = x[x.index.notna()]
        x = x.dropna()
        if x.empty:
            return None
        x = x[~x.index.duplicated(keep="last")].sort_index().astype(float)
        return x if not x.empty else None

    if isinstance(data, pd.DataFrame):
        df = data.copy()
        idx = pd.to_datetime(df.index, errors="coerce")
        if isinstance(df.index, pd.DatetimeIndex) and getattr(df.index, "tz", None) is not None:
            idx = df.index.tz_localize(None)
        df.index = pd.DatetimeIndex(idx)
        df = df[df.index.notna()]
        for s in INDICATORS:
            if s.series_id not in df.columns:
                continue
            v = pd.to_numeric(df[s.series_id], errors="coerce")
            ser = _clean(pd.Series(v.values, index=df.index))
            if ser is not None:
                ser.name = s.series_id
                out[s.series_id] = ser
        return out

    if isinstance(data, dict):
        dates = data.get("dates")
        if dates is None:                      # F-1: no ambiguous `or` on arrays
            dates = data.get("date")
        idx = None
        if dates is not None:
            try:
                dts = pd.to_datetime(dates, errors="coerce")
                idx = dts if isinstance(dts, pd.DatetimeIndex) else pd.DatetimeIndex(dts)
                if getattr(idx, "tz", None) is not None:
                    idx = idx.tz_localize(None)
            except (TypeError, ValueError):
                idx = None
        for s in INDICATORS:
            v = data.get(s.series_id)
            if v is None:
                continue
            if isinstance(v, pd.Series):
                x = pd.to_numeric(v, errors="coerce")   # length preserved
                if not isinstance(x.index, pd.DatetimeIndex):
                    if idx is None or len(idx) != len(x):
                        continue                          # mismatched: skip explicitly
                    x = pd.Series(x.values, index=idx)
                elif getattr(x.index, "tz", None) is not None:
                    x = x.tz_localize(None) if x.index.tz is not None else x
            elif isinstance(v, (list, tuple, np.ndarray)):
                vals = pd.to_numeric(pd.Series(list(v)), errors="coerce")  # length preserved
                if idx is None or len(idx) != len(vals):
                    continue                              # mismatched: skip explicitly
                x = pd.Series(vals.values, index=idx)
            else:
                continue
            ser = _clean(x)                              # align FIRST, then clean
            if ser is not None:
                ser.name = s.series_id
                out[s.series_id] = ser
    return out


# ── § 22.3 · _mrs ── v14.4 U7/U8/U10: the one regime pipeline behind mrs / mrs_at /
async def _mrs(live: bool, data, end: str | None, cfg: Config) -> dict:
    """v14.4 U7/U8/U10: the one regime pipeline behind mrs / mrs_at /
    mrs_ml / regime_now / ticker_score.

    * never prints (notes go to the active diagnostics sink);
    * failures return the stable shape {error, source, detail};
    * the LIVE fetch is memoized in RAM (1h TTL) keyed by (completed month,
      fetch window, tier), so repeat calls do not refetch anything.
    """
    if live:
        end_str = str(end) if end else str(pd.Timestamp(cfg.output_end).date())
        memo_key = ("fred_panel", end_str[:10], cfg.fetch_start,
                    cfg.output_start, cfg.output_end,
                    bool(FORCE_SNAPSHOT), bool(cfg.fred_api_key),
                    getattr(cfg, "credit_mode", "auto"))
        hit = _memo_get(memo_key)
        if hit is not None:
            return dict(hit)                 # shallow copy: callers add keys
        c = replace(cfg, output_end=end) if end else cfg
        client = FREDClient(c.fred_api_key, c)
        raw = await client.fetch_all(INDICATORS)
        if not raw:
            causes = "; ".join(
                f"{sid}: {text.splitlines()[0]}"
                for sid, text in sorted(client.fetch_failures.items()))[:800]
            return {
                "error": ("No FRED data from ANY source tier (API, public "
                          "fredgraph.csv, verified cache, snapshot). "
                          + (f"Per-series causes: {causes}" if causes else "")),
                "source": "FRED API; FRED public CSV; cache; local file",
                "detail": {"tier_notes": list(client.tier_failure_notes),
                           "fetch_failures": dict(client.fetch_failures)},
            }
        notes = list(client.pit_fallbacks)
        # v13.3 M-2: on degraded tiers clip the window to the data (the API
        # path pins dates only via cfg, which _auto_window respects).
        if client.source_mode != "api":
            c, raw, aw_notes = _auto_window(raw, c)
            notes = [f"source: {client.source_note}"] + aw_notes + notes
            # v14 FIX-5: same publication-lag PIT approximation as main_async
            if c.pit_lag_enabled:
                raw, pit_notes = _apply_pit_lags(raw, c)
                notes = notes + pit_notes
        # v14.6.2 STEP A: the SAME one-shot credit-mode decision main_async
        # makes (never a second implementation) — the layer API must report
        # the credit state, never silently re-weight.
        raw, credit_info = resolve_credit_mode(raw, c)
        if credit_info["credit"] == "OFF":
            c = _credit_off_cfg(c)
            notes = list(credit_info["banner"]) + notes
        # B-1: a missing core series silently re-weights every scenario score.
        try:
            assert_core_series(raw, c, failures=client.fetch_failures)
            raw, hist_notes = ensure_history(raw, c)       # v13.1 H-1
            notes = notes + hist_notes
        except RuntimeError as e:
            return {"error": str(e),
                    "source": (f"{client.source_mode or 'FRED tiers'}"),
                    "detail": {"fetch_failures": dict(client.fetch_failures),
                               "tier_notes": list(client.tier_failure_notes)},
                    "fetch_failures": client.last_failures}
        result = {"panel": None, "signals_df": None, "all_signals": None,
                  "notes": notes, "source_mode": client.source_mode,
                  "source_note": client.source_note,
                  "fetch_failures": dict(client.fetch_failures),
                  "last_failures": list(client.last_failures),
                  "pit_fallbacks": list(client.pit_fallbacks),
                  "credit_signal": credit_info["credit"],
                  "credit_warning": credit_info.get("warning")}
    else:
        c = cfg
        raw = _coerce(data)
        if not raw:
            return {
                "error": ("Manual mode: no usable data. Supply a pandas "
                          "DataFrame (DatetimeIndex) or a dict "
                          "{'dates': [...], SERIES_ID: [...]} with the column "
                          f"names in {TPL_PATH} (the template text is in "
                          "tpl()); row M must hold the values KNOWN by the end "
                          "of month M (point-in-time)."),
                "source": "local file",
                "detail": {"template_path": TPL_PATH,
                           "required_columns": [s.series_id for s in INDICATORS]},
            }
        notes: list[str] = []
        try:
            # v14.6.2 STEP A: manual data gets the same one-shot credit-mode
            # decision — a truncated credit history degrades the run loudly
            # instead of stopping it (auto) or silently re-weighting.
            raw, credit_info = resolve_credit_mode(raw, cfg)
            if credit_info["credit"] == "OFF":
                cfg = _credit_off_cfg(cfg)
                notes = list(credit_info["banner"])
            hist_raw, hist_notes2 = ensure_history(raw, cfg)  # v13.1 H-1
            raw = hist_raw
            notes = notes + hist_notes2
        except RuntimeError as e:
            return {"error": str(e), "source": "local file", "detail": {}}
        result = {"panel": None, "signals_df": None, "all_signals": None,
                  "notes": notes, "source_mode": "", "source_note": "",
                  "fetch_failures": {}, "last_failures": [],
                  "pit_fallbacks": [],
                  "credit_signal": credit_info["credit"],
                  "credit_warning": credit_info.get("warning")}
    for note in notes:
        _emit(f"[history] {note}")

    panel = FeatureEngine.build_full_panel(raw, cfg)
    if panel.empty:
        return {"error": "Feature panel empty — not enough history / missing core series.",
                "source": ("FRED API" if live else "local file"), "detail": {}}

    panel = panel.loc[(panel.index >= pd.Timestamp(c.output_start)) &
                      (panel.index <= pd.Timestamp(c.output_end))]
    if end:
        panel = panel.loc[:pd.Timestamp(end)]
    if panel.empty:
        return {"error": f"No data on or before {end}.",
                "source": ("FRED API" if live else "local file"), "detail": {}}

    preds = get_macro_regime(panel, cfg)
    final = apply_hysteresis(preds, cfg)
    sigs = parse_signals(final)
    result.update({"panel": panel, "signals_df": final, "all_signals": sigs,
                   "notes": notes})
    if live:
        _memo_put(memo_key, dict(result))
    return result


# ── § 22.4 · _run
def _run(coro) -> dict:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro)).result()


# ── § 22.5 · mrs ── v14.4 U7/U11: never prints, never mutates module globals; collect…
def mrs(live: bool = True, data=None, cfg: Config = CFG) -> dict:
    """v14.4 U7/U11: never prints, never mutates module globals; collected
    notes/warnings/errors come back in the dict."""
    with _capture_diagnostics() as d:
        r = _run(_mrs(live, data, None, cfg))
        r["notes"] = list(r.get("notes", [])) + d.notes
        r["warnings"] = d.warnings()
        r["errors"] = d.errors()
        if "error" in r:
            return r
        final, sigs = r["signals_df"], r["all_signals"]
        r["latest_regime"] = final.iloc[-1].to_dict() if not final.empty else {}
        r["latest_signal"] = sigs[-1] if sigs else {}
        return r


# ── § 22.6 · _decision_month_end ── v13: floor d to the last COMPLETED month end.
def _decision_month_end(d: str) -> pd.Timestamp:
    """v13: floor d to the last COMPLETED month end.

    Panel row M is only fully knowable at the END of month M, so an 'as of'
    date mid-month may only use the previous month's completed decision set.
    mrs_at('2020-03-15') therefore answers with the 2020-02-29 row (the data
    that would drive the March trade), not the 2020-03-31 row.
    """
    ts = pd.Timestamp(d)
    me = ts + pd.offsets.MonthEnd(0)
    return me if me <= ts else me - pd.offsets.MonthEnd(1)


# ── § 22.7 · mrs_at ── Regime + next-month basket as known on date d.
def mrs_at(d: str, live: bool = True, data=None, cfg: Config = CFG,
           backtest_state: dict | None = None) -> dict:
    """Regime + next-month basket as known on date d.

    d is floored to the last COMPLETED month end (see _decision_month_end):
    a mid-month d returns the previous month's row, because the current
    month's decision set only completes at month end. No future information
    can enter the result.

    v13.2 D-1: the returned `conviction_leverage` is the UNADJUSTED value
    (regime_months from hysteresis, regime_acc prior 0.5 — `lev_basis` says
    so). Pass `backtest_state` (a Backtester.last_state plus
    'spy_monthly_close') to also get `executable_leverage`, computed by the
    same authoritative function the backtester uses — for identical state
    and inputs the two are equal (see tests).

    v14.4 U7/U8: never prints; failures carry {error, source, detail} and
    `as_of`.
    """
    end = _decision_month_end(d)
    with _capture_diagnostics() as diag:
        r = _run(_mrs(live, data, end.strftime("%Y-%m-%d"), cfg))
        r["notes"] = list(r.get("notes", [])) + diag.notes
        r["warnings"] = diag.warnings()
        r["errors"] = diag.errors()
        if "error" in r:
            r.setdefault("as_of", str(end.date()))
            return r
        final = r["signals_df"]
        if final.empty:
            return {"as_of": str(end.date()),
                    "error": f"No regime computed on/before {end.date()}",
                    "source": r.get("source_mode") or "FRED API", "detail": {}}
        row = final.iloc[-1]
        sig = r["all_signals"][-1]
        out = {
            "date": row["date"], "regime": row["regime"], "scenario_key": row["scenario_key"],
            "scenario": row["scenario"], "cycle_phase": row["cycle_phase"],
            "confidence": float(row["confidence"]),
            "dominance": float(row["dominance"]),
            "conviction_leverage": float(row["conviction_leverage"]),
            "lev_basis": row.get("lev_basis", "unadjusted_prior"),
            "regime_months": int(row.get("regime_months", 1)),
            "longs": sig["longs"], "shorts": sig["shorts"],
            "raw": row.to_dict(),
        }
    if backtest_state is not None:
        lev, det = executable_leverage(
            scenario_key=sig["scenario_key"],
            dominance=sig["dominance"],
            regime_months=sig["regime_months"],
            regime_history=(backtest_state.get("regime_history", {})
                            .get(sig["scenario_key"], [])),
            spy_monthly_close=backtest_state["spy_monthly_close"],
            month=sig["month"],
            wealth=float(backtest_state.get("wealth", 1.0)),
            peak=float(backtest_state.get("peak", 1.0)),
            has_shorts=bool(sig["shorts"]),
            cfg=cfg)
        out["executable_leverage"] = round(lev, 3)
        out["executable_leverage_details"] = {
            k: (round(v, 3) if isinstance(v, float) else v) for k, v in det.items()}
    return out


# ── § 22.8 · mrs_ml ── v14.4 U7: quiet — collected diagnostics are returned in the error
def mrs_ml(live: bool = True, data=None, y: str = "regime",
           dropna: bool = True, cfg: Config = CFG):
    """v14.4 U7: quiet — collected diagnostics are returned in the error
    dict instead of being printed."""
    with _capture_diagnostics() as diag:
        r = _run(_mrs(live, data, None, cfg))
        if "error" in r:
            r["warnings"] = diag.warnings()
            r["errors"] = diag.errors()
            return None, None, r
        panel, final = r["panel"], r["signals_df"]
    final = final.copy()
    final["date"] = pd.to_datetime(final["date"])
    final = final.set_index("date")
    common = panel.index.intersection(final.index)
    X = panel.loc[common].copy()
    f = final.loc[common]

    if y == "regime":
        yv = f["scenario_key"].astype(str)
    elif y == "regime_id":
        yv = f["scenario_key"].map(_CLASS_IDX).astype("Int64")
    elif y == "lev":
        yv = f["conviction_leverage"].astype(float)
    else:
        return None, None, {"error": f"Unknown y='{y}' (use regime|regime_id|lev)"}

    if dropna:
        mask = X.notna().all(axis=1) & yv.notna()
        X, yv = X.loc[mask], yv.loc[mask]

    meta = {
        "feature_names": list(X.columns),
        "classes": _CLASSES if y in ("regime", "regime_id") else None,
        "n_samples": int(len(X)),
        "date_range": (str(X.index[0].date()), str(X.index[-1].date())) if len(X) else (None, None),
        "target": y,
    }
    return X, yv, meta


# ═══════════════════════════════════════════════════════════════════════════
#  § 23 · LAYER API — regime_now (U9) · ticker_score (U8)
# ═══════════════════════════════════════════════════════════════════════════
_TIER_LABELS = {"api": "api", "public-csv": "public", "cache": "cache",
                "snapshot": "snapshot"}

# ── § 23.0 · v14.7 card/layer support — display constants + card cache mode.
#  QUALITY_* are DISPLAY-ONLY module constants (§3.3): deliberately NOT
#  Config fields so the frozen config fingerprint is untouched.
#    HIGH = credit ON, confidence >= .50 AND margin >= .10
#    MED  = confidence >= cfg.min_confidence
#    LOW  = anything else; credit OFF caps the card at MED.
QUALITY_HIGH_MIN_CONFIDENCE = 0.50
QUALITY_HIGH_MIN_MARGIN = 0.10
QUALITY_RETAINED_MIN = 0.70        # <70% retained weight -> warnings entry

#  _CARD_MODE is set by now()/span() (the card CLI paths): it makes
#  FREDClient.fetch_all prefer a FRESH verified card cache (the warm card
#  of §3.1, <=2s) and permits VerifiedCache writes (the cold card's
#  write-back; H7 allows meds_cache/ writes).  Full runs / --audit never
#  set it, so their tier order and write gating are unchanged.
_CARD_MODE = False


# ── § 23.0.1 · _card_cache_write_series — the cold card's write-back.
def _card_cache_write_series(raw: dict) -> None:
    """v14.7 §3.1 (card write-back): serialize the FINAL series a tier
    served (post pc1/chg transform, post slice) as fredgraph-shaped CSV
    under fredcard/<SID>.csv in the verified cache, so the NEXT card run is
    warm.  Values round-trip exactly (Python float repr); the card reader
    never re-applies unit transforms.  Failures are recorded, never raised."""
    try:
        cache = VerifiedCache()
        for sid, s in raw.items():
            if s is None or s.empty:
                continue
            buf = io.StringIO()
            buf.write(f"observation_date,{sid}\n")
            for d, v in s.items():
                # fredgraph.csv's own missing-value convention: '.' rows keep
                # the row (and its DATE) so the round-trip stays lossless —
                # the pc1/chg warmup NaN head must survive to keep rolling
                # windows identical to a fresh fetch.
                val = "." if not (v == v) else repr(float(v))
                buf.write(f"{pd.Timestamp(d).date()},{val}\n")
            cache.put(f"fredcard/{sid}.csv", buf.getvalue().encode("utf-8"))
    except (OSError, ValueError, TypeError) as e:
        _emit("  " + _describe_failure(
            "cache", "entry=fredcard/<SID>.csv (card write-back)", exc=e))


# ── § 23.1 · _pit_mode_label
def _pit_mode_label(source_mode: str, cfg: Config, live: bool) -> str:
    if not live:
        return "as_supplied"
    if source_mode == "api":
        return "strict_vintage_pit"
    return "approximate_pit_lag" if cfg.pit_lag_enabled else "current_vintage"


# ── § 23.2 · regime_now ── v14.4 U9: the CURRENT (or as_of) macro regime as ONE dict — a thin
def regime_now(as_of=None, live: bool = True, data=None, cfg: Config = CFG) -> dict:
    """v14.4 U9: the CURRENT (or as_of) macro regime as ONE dict — a thin
    wrapper over the same _mrs pipeline mrs_at uses (no second
    implementation).  Fields: scenario_key, name, confidence, dominance,
    cycle_phase, conviction_leverage, as_of, data_tier
    (api|public|cache|snapshot, 'supplied' for manual data), pit_mode, plus
    basket {longs, shorts}.  as_of floors to the last COMPLETED month end
    (point-in-time safe).  Never prints; never raises on data problems
    (failures return {as_of, error, source, detail})."""
    if as_of is not None and not isinstance(as_of, str):
        raise TypeError("as_of must be a YYYY-MM-DD string or None")
    end = _decision_month_end(as_of) if as_of is not None else _decision_month_end(cfg.output_end)
    with _capture_diagnostics() as diag:
        r = _run(_mrs(live, data, end.strftime("%Y-%m-%d"), cfg))
        if "error" in r:
            return {"as_of": str(end.date()), "error": r["error"],
                    "source": r.get("source", "FRED API"),
                    "detail": r.get("detail", {}),
                    "notes": diag.notes, "warnings": diag.warnings(),
                    "errors": diag.errors()}
        final = r["signals_df"]
        if final is None or final.empty:
            return {"as_of": str(end.date()),
                    "error": f"No regime computed on/before {end.date()}",
                    "source": r.get("source_mode") or "FRED API", "detail": {}}
        # v14.7 §23.5: the row selection lives in ONE place (_decision_row),
        # shared with now()/span().
        row, sig, _i = _decision_row(r, end)
        if row is None:
            return {"as_of": str(end.date()),
                    "error": f"No regime computed on/before {end.date()}",
                    "source": r.get("source_mode") or "FRED API", "detail": {}}
        tier = _TIER_LABELS.get(r.get("source_mode", ""),
                                "supplied" if not live else "unknown")
        out = {
            "scenario_key": row["scenario_key"],
            "name": row["scenario"],
            "confidence": float(row["confidence"]),
            "dominance": float(row["dominance"]),
            "cycle_phase": row["cycle_phase"],
            "conviction_leverage": float(row["conviction_leverage"]),
            "as_of": str(end.date()),
            "data_tier": tier,
            "pit_mode": _pit_mode_label(r.get("source_mode", ""), cfg, live),
            "basket": {"longs": list(sig.get("longs", [])),
                       "shorts": list(sig.get("shorts", []))},
            "regime_months": int(row.get("regime_months", 1)),
            "next_trade_month": sig.get("month", ""),
            "regime": row["regime"],
            # v14.6.2 STEP A: the credit state of THIS run — ON changes
            # nothing; OFF carries the warning string.
            "credit_signal": r.get("credit_signal", "ON"),
            "notes": list(r.get("notes", [])) + diag.notes,
            "warnings": diag.warnings(),
            "errors": diag.errors(),
        }
        if r.get("credit_warning"):
            out["credit_warning"] = r["credit_warning"]
        # v14.7 4b / §3.4: if the WINNING scenario's score renormalized over
        # less than 70% of its weight (missing terms), that fact is reported
        # as a warnings entry — the score itself is unchanged.  On a healthy
        # panel every term scores and nothing fires.
        panel = r.get("panel")
        if panel is not None and not panel.empty:
            try:
                drow = panel.loc[pd.Timestamp(row["date"])]
            except (KeyError, TypeError, ValueError):
                drow = None
            if drow is not None:
                retained = _scenario_retained_weight(
                    drow, out["scenario_key"], cfg)
                if retained is not None and retained < 0.70:
                    out["warnings"].append(
                        f"scenario {out['scenario_key']} score renormalized: "
                        f"retained weight {retained:.0%} of its terms (<70%)")
        return out


# ── § 23.3 · _clip01
def _clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


# ── § 23.4 · ticker_score ── v14.4 U8/--ticker: score ONE ticker against the current (or as_of)
def ticker_score(ticker: str, as_of: str | None = None, live: bool = True,
                 data=None, cfg: Config = CFG) -> dict:
    """v14.4 U8/--ticker: score ONE ticker against the current (or as_of)
    macro regime — the exportable layer for an external trading system.
    Any valid exchange symbol works: basket symbols slice the shared
    canonical frame, anything else gets its own memoised download (FIX-2).

    Calibrated the way an institutional desk reads a rating — deliberately
    NOT strict: a neutral fact pattern scores ~50/100, not 0.
      score = 100 * (0.35*alignment + 0.30*edge + 0.20*trend + 0.15*risk)
        alignment  1.0 long side of the basket, 0.0 short side, 0.5 not held
        edge       mean O→C return of the month AFTER each in-regime
                   label (label t traded in t+1, §16.8), soft-clipped at
                   +/-4%/mo around a 0.5 centre (0.5 when < 6 pairs)
        trend      distance to the 10-month SMA, +/-20% band around 0.5,
                   inverted for short-side tickers
        risk       1 - annualized vol/50%, floored at 0
    `as_of` floors to the last COMPLETED month end and slices BOTH the
    regime row and the price history to <= as_of (point-in-time safe, B3).
    Never prints; never raises for data problems — failures return
    {ticker, as_of, error, source, detail}.  Programmer errors (bad types)
    raise TypeError.
    """
    if not isinstance(ticker, str) or not ticker.strip():
        raise TypeError("ticker must be a non-empty string")
    if as_of is not None and not isinstance(as_of, str):
        raise TypeError("as_of must be a YYYY-MM-DD string or None")
    ticker = ticker.strip().upper()
    end = _decision_month_end(as_of) if as_of is not None else _decision_month_end(cfg.output_end)
    if not _symbol_ok(ticker):          # FIX-2: gate BEFORE any fetch
        return {"ticker": ticker, "as_of": str(end.date()),
                "error": (f"invalid ticker symbol '{ticker}' — allowed: "
                          "A-Z, 0-9 and . - ^ =, 1-15 characters"),
                "source": "symbol validation",
                "detail": {"pattern": _SYMBOL_RE.pattern}}
    with _capture_diagnostics() as diag:
        r = _run(_mrs(live, data, end.strftime("%Y-%m-%d"), cfg))
        if "error" in r:
            return {"ticker": ticker, "as_of": str(end.date()),
                    "error": r["error"], "source": r.get("source", "FRED API"),
                    "detail": r.get("detail", {}),
                    "notes": diag.notes, "warnings": diag.warnings(),
                    "errors": diag.errors()}
        final = r["signals_df"]
        final_d = pd.to_datetime(final["date"])
        keep = final.index[final_d <= end]
        if len(keep) == 0:
            return {"ticker": ticker, "as_of": str(end.date()),
                    "error": f"No regime computed on/before {end.date()}",
                    "source": r.get("source_mode") or "FRED API", "detail": {}}
        row = final.loc[keep[-1]]
        sig = r["all_signals"][keep[-1]]
        regime_block = {
            "scenario_key": row["scenario_key"], "name": row["scenario"],
            "confidence": float(row["confidence"]),
            "dominance": float(row["dominance"]),
            "cycle_phase": row["cycle_phase"],
            "conviction_leverage": float(row["conviction_leverage"]),
            "as_of": str(end.date()),
            "data_tier": _TIER_LABELS.get(r.get("source_mode", ""),
                                          "supplied" if not live else "unknown"),
            "pit_mode": _pit_mode_label(r.get("source_mode", ""), cfg, live),
            "basket": {"longs": list(sig["longs"]), "shorts": list(sig["shorts"])},
            # v14.6.2 STEP A: the credit state of THIS run — shown on the
            # --ticker card and carried in --json.
            "credit_signal": r.get("credit_signal", "ON"),
        }
        if r.get("credit_warning"):
            regime_block["credit_warning"] = r["credit_warning"]

        # ── price history (FIX-2): basket symbols slice the ONE shared
        # frame to <= as_of (B3); any other valid symbol gets its own
        # memoised download.  The frozen snapshot never invents prices. ──
        if ticker not in _CANONICAL_PRICE_TICKERS and FORCE_SNAPSHOT:
            return {"ticker": ticker, "as_of": str(end.date()),
                    "error": ("snapshot serves only the basket symbols: "
                              + ", ".join(_CANONICAL_PRICE_TICKERS)),
                    "source": "local file", "detail": {"price_tier": "snapshot"},
                    "regime": regime_block,
                    "notes": diag.notes, "warnings": diag.warnings(),
                    "errors": diag.errors()}
        frame = _ticker_price_frame(ticker, cfg)
        has_px = (frame is not None and not frame.empty
                  and ticker in set(frame.columns.get_level_values(-1)))
        if not has_px:
            first_yf = next((e for e in diag.yf_errors if ticker in e), "")
            return {"ticker": ticker, "as_of": str(end.date()),
                    "error": (f"no price history for {ticker} in the served "
                              "price tier" + (f": {first_yf}" if first_yf else "")),
                    "source": ("local file" if FORCE_SNAPSHOT or r.get("source_mode") == "snapshot"
                               else "Yahoo (yfinance)"),
                    "detail": {"price_tier": ("snapshot" if FORCE_SNAPSHOT else "live")},
                    "regime": regime_block,
                    "notes": diag.notes, "warnings": diag.warnings(),
                    "errors": diag.errors()}
        # ── v14.6 STEP A.4: the OWN series must not be truncated, and (on
        # the shared basket frame) OTHER tickers' gaps make the frame
        # PARTIAL.  The SAME §17.7 judgement the engine's retry gate and C13
        # use — reused, not duplicated.  The end anchor is the decision
        # month end (an as_of in the past only needs data up to as_of).
        # Start-side floors exist only for the canonical tickers, so a
        # non-basket symbol gets no start judgement — its listing date is
        # unknowable from here (documented blind spot; the SMA-window
        # sufficiency check below still guards severe shortness). ──
        _uni = (_CANONICAL_PRICE_TICKERS if ticker in _CANONICAL_PRICE_TICKERS
                else (ticker,))
        _pgaps = _frame_gaps(frame, _uni, *Backtester._price_window(cfg),
                             end_anchor=end, judge_end=_frame_served_live())
        _own_gap = (_pgaps["missing"].get(ticker)
                    or _pgaps["truncated"].get(ticker))
        if _own_gap:
            return {"ticker": ticker, "as_of": str(end.date()),
                    "error": (f"price series for {ticker} is truncated — "
                              f"{_own_gap} — refusing to score on a partial "
                              f"price frame"),
                    "source": ("local file" if FORCE_SNAPSHOT else
                               "Yahoo (yfinance)"),
                    "detail": {"gaps": _own_gap,
                               "frame_window": list(_pgaps["window"]),
                               "end_anchor": _pgaps["end_anchor"]},
                    "regime": regime_block,
                    "notes": diag.notes, "warnings": diag.warnings(),
                    "errors": diag.errors()}
        _others = {**_pgaps["missing"], **_pgaps["truncated"]}
        _others.pop(ticker, None)
        close = frame["Close"][ticker].dropna().loc[:end]
        opens = frame["Open"][ticker].dropna().loc[:end]
        if close.empty or len(close) < 2:
            return {"ticker": ticker, "as_of": str(end.date()),
                    "error": f"insufficient price history for {ticker} on/before {end.date()}",
                    "source": "Yahoo (yfinance)", "detail": {"n_obs": int(len(close))},
                    "regime": regime_block,
                    "notes": diag.notes, "warnings": diag.warnings(),
                    "errors": diag.errors()}
        monthly_close = close.resample(FREQ_ME).last().dropna()
        monthly_open = opens.resample(FREQ_ME).first().dropna()
        if len(monthly_close) < cfg.trend_sma_window:   # FIX-2: SMA needs history
            return {"ticker": ticker, "as_of": str(end.date()),
                    "error": (f"insufficient price history for {ticker} "
                              f"on/before {end.date()} ({len(monthly_close)} "
                              f"monthly bars < {cfg.trend_sma_window} needed "
                              "for the trend SMA)"),
                    "source": "Yahoo (yfinance)",
                    "detail": {"n_obs": int(len(close)),
                               "n_months": int(len(monthly_close))},
                    "regime": regime_block,
                    "notes": diag.notes, "warnings": diag.warnings(),
                    "errors": diag.errors()}
        m_oc = ((monthly_close / monthly_open - 1.0)
                .dropna().loc[:end])            # monthly O→C returns

        # in-regime history reuses the FIRST classification pass (S3) — the
        # per-month scenario_key from signals_df, never a re-classification.
        # FIX-1 (v14.5): the label made at month-end t is traded in month
        # t+1 (§16.8), so pair it with month t+1's return, never with month
        # t's own already-realised print.  Both sides are keyed on Period-M
        # so a calendar-vs-business month-end mismatch cannot drop or shift
        # a pair; only forward months on or before `end` count, so the
        # label at `end` (no realised forward month) is excluded.
        scenario_by_month = pd.Series(
            final["scenario_key"].values,
            index=pd.PeriodIndex(pd.to_datetime(final["date"]), freq="M"))
        label_months = scenario_by_month.index[
            scenario_by_month == row["scenario_key"]]
        ret_by_month = m_oc.copy()
        ret_by_month.index = pd.PeriodIndex(ret_by_month.index, freq="M")
        fwd_idx = (label_months + 1).intersection(
            ret_by_month.index[ret_by_month.index <= end.to_period("M")])
        in_regime = (ret_by_month.loc[fwd_idx] if len(fwd_idx)
                     else pd.Series(dtype=float))
        n = int(len(in_regime))
        mean_ret = float(in_regime.mean()) if n else 0.0
        win_rate = float((in_regime > 0).mean()) if n else None
        ann_vol = float(in_regime.std() * np.sqrt(12.0)) if n >= 2 else None
        dd_series = (1.0 + in_regime).cumprod()
        mdd_pct = float(((dd_series / dd_series.cummax() - 1.0).min() * 100) if n else 0.0)

        sma = monthly_close.rolling(cfg.trend_sma_window).mean()
        last_close = float(monthly_close.iloc[-1])
        sma_v = float(sma.iloc[-1]) if pd.notna(sma.iloc[-1]) else None
        trend_pct = ((last_close / sma_v - 1.0) * 100) if (sma_v and sma_v > 0) else None

        role = ("long" if ticker in sig["longs"]
                else "short" if ticker in sig["shorts"] else None)
        alignment = 1.0 if role == "long" else (0.0 if role == "short" else 0.5)
        if n >= 6:
            edge_raw = mean_ret if role != "short" else -mean_ret
            edge = _clip01(0.5 + edge_raw / 0.04)
        else:
            edge = 0.5                       # insufficient sample: neutral
        if trend_pct is not None:
            trend_raw = (trend_pct / 100.0) if role != "short" else (-trend_pct / 100.0)
            trend = _clip01(0.5 + trend_raw / 0.20)
        else:
            trend = 0.5
        risk = _clip01(1.0 - (ann_vol / 0.50)) if ann_vol is not None else 0.5
        weights = {"alignment": 0.35, "edge": 0.30, "trend": 0.20, "risk": 0.15}
        components = {"alignment": round(alignment, 4), "edge": round(edge, 4),
                      "trend": round(trend, 4), "risk": round(risk, 4)}
        score = round(100.0 * sum(weights[k] * components[k] for k in weights), 1)
        verdict = ("Favorable" if score >= 75 else
                   "Constructive" if score >= 60 else
                   "Neutral" if score >= 45 else
                   "Cautious" if score >= 30 else "Adverse")

        out = {
            "ticker": ticker,
            "as_of": str(end.date()),
            "score": score,
            "verdict": verdict,
            "role": role,
            "regime": regime_block,
            "components": components,
            "component_weights": weights,
            "stats": {
                "in_regime_months": n,
                "mean_monthly_ret_pct": round(mean_ret * 100, 3),
                "win_rate_pct": round(win_rate * 100, 1) if win_rate is not None else None,
                "ann_vol_pct": round(ann_vol * 100, 1) if ann_vol is not None else None,
                "max_drawdown_pct": round(mdd_pct, 2),
                "last_close": round(last_close, 4),
                "sma_10m": round(sma_v, 4) if sma_v else None,
                "pct_vs_sma10m": round(trend_pct, 2) if trend_pct is not None else None,
            },
            "notes": list(r.get("notes", [])) + diag.notes,
            "warnings": diag.warnings(),
            "errors": diag.errors(),
        }
        # v14.6 STEP A.4: other tickers missing/truncated on the shared
        # basket frame -> the frame is PARTIAL (the own series is fine);
        # shown in yellow on the card.  v14.6 STEP B: the data fingerprint
        # of the frame this score used (print-only via --ticker).
        if _others:
            out["price_frame"] = "PARTIAL"
            out["price_frame_detail"] = [f"{t}: {why}"
                                         for t, why in sorted(_others.items())]
        out["price_frame_fingerprint"] = price_fingerprint(frame)
    return out


# ── § 23.5 · _print_ticker_score ── v14.4 --ticker: the short, colourful terminal card.
def _print_ticker_score(out: dict) -> None:
    """v14.4 --ticker: the short, colourful terminal card."""
    if "error" in out:
        print(_c(f"✗ {out.get('ticker', '?')} — score unavailable", "31"))
        print(f"  error : {out['error']}")
        for note in (out.get("detail", {}) or {}).get("tier_notes", [])[:1]:
            print(f"  tier  : {note}")
        print(f"  source: {out.get('source', '?')}")
        return
    colour = ("32" if out["score"] >= 60 else
              "33" if out["score"] >= 45 else "31")
    reg = out["regime"]
    print(_c(f"◆ {out['ticker']} — score {out['score']:.0f}/100 ({out['verdict']})", colour))
    print(f"  regime : {reg['name']} ({reg['scenario_key']}, {reg['cycle_phase']}) "
          f"confidence {reg['confidence']:.2f} · dominance {reg['dominance']:.2f}")
    # v14.6.2 STEP A: the credit state on the card — OFF is loud, ON adds
    # nothing (the score itself is unchanged by the ON marker).
    if reg.get("credit_signal") == "OFF":
        print(_c(f"  ⚠  {reg.get('credit_warning', 'credit signal OFF')}", "33"))
    print(f"  as of  : {out['as_of']} · tier {reg['data_tier']} · PIT {reg['pit_mode']}")
    basket = reg["basket"]
    basket_txt = f"L[{','.join(basket['longs'])}] S[{','.join(basket['shorts'])}]"
    role_txt = (f"{out['role'].upper()} in basket {basket_txt}" if out["role"]
                else f"not in current regime basket ({basket_txt})")
    print(f"  role   : {role_txt} · conviction {reg['conviction_leverage']:.2f}x")
    s = out["stats"]
    trend_txt = (f"{('+' if (s['pct_vs_sma10m'] or 0) >= 0 else '')}"
                 f"{s['pct_vs_sma10m']}% vs 10m SMA" if s["pct_vs_sma10m"] is not None
                else "n/a vs 10m SMA (insufficient history)")
    print(f"  trend  : {trend_txt}"
          f" · in-regime edge {s['mean_monthly_ret_pct']:+.2f}%/mo "
          f"(win {s['win_rate_pct']}, {s['in_regime_months']} mo)")
    c = out["components"]
    print(f"  parts  : alignment {c['alignment']:.2f} · edge {c['edge']:.2f} · "
          f"trend {c['trend']:.2f} · risk {c['risk']:.2f}")
    # v14.6 STEP A.4: a PARTIAL shared frame (other tickers missing or
    # truncated — the own series is fine) is shown in YELLOW on the card.
    if out.get("price_frame") == "PARTIAL":
        det = out.get("price_frame_detail") or ["?"]
        print(_c("  ⚠  price frame PARTIAL — " + "; ".join(det[:4])
                 + (f" (+{len(det) - 4} more)" if len(det) > 4 else ""), "33"))
    if out["warnings"]:
        print(_c(f"  ⚠ {len(out['warnings'])} warning(s) returned in the dict", "33"))


_SYMBOL_RE = re.compile(r"^[A-Z0-9.\-\^=]{1,15}$")   # FIX-2: valid exchange symbol


# ── § 23.6 · _symbol_ok ── v14.5 FIX-2: exchange-symbol syntax gate (no fetch on bad input)
def _symbol_ok(ticker: str) -> bool:
    """v14.5 FIX-2: True when `ticker` is a syntactically valid exchange
    symbol (A-Z, 0-9 and . - ^ =, 1-15 characters).  Gates the per-ticker
    download path BEFORE any network call."""
    return bool(_SYMBOL_RE.match(ticker))


# ── § 23.7 · _ticker_price_frame ── v14.5 FIX-2: the price frame ONE ticker needs — basket
def _ticker_price_frame(ticker: str, cfg: Config) -> pd.DataFrame:
    """v14.5 FIX-2: the daily price frame for ONE ticker.

    Basket symbols slice the canonical shared frame (S2: ONE download per
    run, unchanged); any other valid symbol is fetched on its own through
    the same _safe_yf_download -> _get_prices path and served from the same
    in-RAM memo (U10: a repeat call refetches nothing).  FORCE_SNAPSHOT
    never invents prices: a non-basket symbol gets an empty frame and the
    caller reports the snapshot-universe error."""
    if ticker in _CANONICAL_PRICE_TICKERS:
        return _engine_price_frame(cfg)
    if FORCE_SNAPSHOT:
        return pd.DataFrame()
    start, end = Backtester._price_window(cfg)
    return _get_prices([ticker], start, end)


# ── § 23.5 · _decision_row — the ONE row-selection shared by the layer.
def _decision_row(r: dict, end: pd.Timestamp):
    """v14.7 §3.3: the decision row of a finished _mrs pipeline — the LAST
    classified month-end at/before `end` — as (row, signal, index) or
    (None, None, None).  Extracted verbatim from regime_now so now()/span()
    select rows through the SAME code, never a second implementation."""
    final = r["signals_df"]
    if final is None or final.empty:
        return None, None, None
    final_d = pd.to_datetime(final["date"])
    keep = final.index[final_d <= end]
    if len(keep) == 0:
        return None, None, None
    i = keep[-1]
    sig = r["all_signals"][i] if r["all_signals"] else {}
    return final.loc[i], sig, i


# ── § 23.6 · _card_quality / _card_status — display-only layer verdicts.
def _card_quality(confidence, margin, credit_on: bool, cfg: Config) -> str:
    """v14.7 §3.3: HIGH/MED/LOW.  Display-only — never a Config field."""
    conf = float(confidence) if confidence is not None and pd.notna(confidence) else 0.0
    marg = float(margin) if margin is not None and pd.notna(margin) else 0.0
    if credit_on and conf >= QUALITY_HIGH_MIN_CONFIDENCE \
            and marg >= QUALITY_HIGH_MIN_MARGIN:
        return "HIGH"
    if conf >= cfg.min_confidence:
        return "MED"
    return "LOW"


# ── § 23.6.1 · _card_status — OK | DEGRADED | ERROR for a card/span result.
def _card_status(base: dict, panel, cfg: Config, end: pd.Timestamp) -> tuple[str, list[str]]:
    """v14.7 §3.4: OK | DEGRADED | ERROR for a card/span result, plus the
    reasons.  DEGRADED: credit OFF; data served from the cache while the
    cache file is older than the TTL; any core series whose last visible
    observation trails the decision date by more than its PIT lag + 35
    days.  ERROR: no prediction at all, or core coverage below
    cfg.pit_min_retained."""
    if base.get("error") is not None or base.get("scenario_key") is None:
        return "ERROR", [str(base.get("error") or "no prediction")]
    reasons: list[str] = []
    if base.get("credit_signal", "ON") == "OFF":
        reasons.append("credit signal OFF")
    tier = base.get("data_tier", "")
    if tier == "cache":
        try:
            age_s = time.time() - os.path.getmtime(VerifiedCache().path)
        except OSError:
            age_s = 0.0
        if age_s > CACHE_TTL_HOURS * 3600.0:
            reasons.append("served from a cache older than its TTL")
    lags = dict(cfg.pit_lag_days or ())
    if panel is not None and not panel.empty:
        # the EFFECTIVE core set: a credit-OFF run dropped the BAML cores
        # from its derived Config — judging it against the caller's default
        # set would flag a series the pipeline deliberately excluded.
        core_cols = list(cfg.core_columns)
        if base.get("credit_signal", "ON") == "OFF":
            core_cols = [c for c in core_cols if c not in CREDIT_MODE_SERIES]
        core = [c for c in core_cols if c in panel.columns]
        covered = 0
        for sid in core:
            s = panel[sid]
            last = s.last_valid_index()
            if last is None:
                continue
            covered += 1
            stale_days = (end - pd.Timestamp(last)).days
            if stale_days > int(lags.get(sid, 0)) + 35:
                reasons.append(f"core series {sid} is {stale_days}d old "
                               f"(lag {int(lags.get(sid, 0))}d + 35d)")
        want = len(core_cols)
        if want and covered < cfg.pit_min_retained * want:
            return "ERROR", [f"only {covered}/{want} core series retained "
                             f"(< pit_min_retained {cfg.pit_min_retained:.0%})"]
    return ("DEGRADED" if reasons else "OK"), reasons


# ── § 23.7 · now — v14.7 §3.3: the current prediction as ONE JSON-safe dict.
def now(cfg: Config | None = None) -> dict:
    """v14.7 §3.3: the CURRENT prediction as ONE JSON-safe dict — the
    regime_now() fields plus month / status / credit / quality / warnings.

    Reuses the existing PIT pipeline exactly once (regime_now, RAM-memoized
    per process); in card mode a FRESH verified card cache is preferred and
    a cold fetch is written back to meds_cache/fredcard/ (H7) so the next
    run is warm.  Never prints, never raises on data problems (failures
    return status='ERROR' with the real detail)."""
    cfg = cfg or CFG
    global _CARD_MODE
    _CARD_MODE = True
    try:
        base = regime_now(cfg=cfg)
        panel = _memo_get(_fred_panel_memo_key(cfg)) or {}
        panel = panel.get("panel") if isinstance(panel, dict) else None
    finally:
        _CARD_MODE = False
    if base.get("error") is not None:
        return {"status": "ERROR", "error": base["error"],
                "source": base.get("source", ""), "detail": base.get("detail", {}),
                "as_of": base.get("as_of"), "warnings": base.get("warnings", []),
                "errors": base.get("errors", [])}
    end = pd.Timestamp(base["as_of"])
    status, reasons = _card_status(base, panel, cfg, end)
    out = dict(base)                                   # regime_now fields
    out["month"] = base.get("next_trade_month") or ""
    out["status"] = status
    out["credit"] = "ON" if base.get("credit_signal", "ON") == "ON" else "OFF"
    out["quality"] = _card_quality(base.get("confidence"), base.get("dominance"),
                                   out["credit"] == "ON", cfg)
    out["version"] = __version__
    out["regime_class"] = ("defensive" if out.get("scenario_key") in cfg.defensive_regimes
                          else ("neutral" if out.get("scenario_key") == "NEUTRAL_WAIT_AND_SEE"
                                else "risk_on"))
    out["runner_up"] = _card_runner_up(base, panel, cfg)
    if out["credit"] == "OFF":
        out["excluded_scenarios"] = list(
            getattr(cfg, "excluded_scenarios", ())
            or ("CREDIT_CRUNCH", "EARLY_CYCLE_RE_ACCELERATION"))
    if reasons:
        out["status_reasons"] = reasons
        out["warnings"] = list(base.get("warnings", [])) + list(reasons)
    _json_safe_values(out)
    return out


# ── § 23.8.1 · _span_clamp / _span_rows — span's clamp + row builder.
def _span_clamp(start_m, end_m, first_avail, last_avail):
    """§3.2: clamp [start, end] to the predictable range, with a notice for
    every dropped side (future months cannot be predicted; nothing is
    classified before the first available month)."""
    notices: list[str] = []
    lo, hi = start_m, end_m
    if lo < first_avail:
        notices.append(f"start clamped {lo.strftime('%Y-%m')} -> "
                       f"{first_avail.strftime('%Y-%m')} (no classified month "
                       f"before it)")
        lo = first_avail
    if hi > last_avail:
        notices.append(f"end clamped {hi.strftime('%Y-%m')} -> "
                       f"{last_avail.strftime('%Y-%m')}: future months cannot "
                       f"be predicted")
        hi = last_avail
    return lo, hi, notices


# ── § 23.8.2 · _span_rows — the per-month JSON-safe row builder.
def _span_rows(by_month: dict, lo: pd.Period, hi: pd.Period) -> list[dict]:
    """§3.2: one JSON-safe row per month in [lo, hi] — the regime, baskets
    and leverage MEDS knew at the end of the previous month."""
    rows = []
    m = lo
    while m <= hi:
        key = m.strftime("%Y-%m")
        row, sig = by_month.get(key, (None, None))
        if row is not None:
            rows.append({
                "month": key,
                "scenario_key": row["scenario_key"], "name": row["scenario"],
                "regime": row["regime"], "cycle_phase": row["cycle_phase"],
                "confidence": round(float(row["confidence"]), 6),
                "dominance": round(float(row["dominance"]), 6),
                "conviction_leverage": round(float(row["conviction_leverage"]), 3),
                "longs": list(sig.get("longs", [])),
                "shorts": list(sig.get("shorts", [])),
            })
        m += 1
    return rows


# ── § 23.8 · span — v14.7 §3.2: month-by-month predictions from ONE pass.
def span(start: str, end: str | None = None, cfg: Config | None = None) -> dict:
    """v14.7 §3.2: month-by-month regime + baskets for [start, end] (YYYY-MM
    or YYYY-MM-DD) as {rows, status, notices}.  ONE fetch + ONE
    classification pass serves every row; row m is what MEDS knew at the
    end of m-1 (== mrs_at(prev month-end)).  `end` defaults to the current
    prediction month; out-of-range months clamp with a notice; start > end
    or a bad date raises ValueError (the CLI maps it to exit 2)."""
    cfg = cfg or CFG
    start_m = _parse_month_arg(start, "start")
    # §3.2: end defaults to the CURRENT prediction month (the month after
    # the last completed month-end).
    end_m = (pd.Period(_decision_month_end(cfg.output_end).strftime("%Y-%m"),
                       freq="M") + 1 if end is None
             else _parse_month_arg(end, "end"))
    if start_m > end_m:
        raise ValueError(f"start ({start}) is after end ({end or end_m})")
    global _CARD_MODE
    _CARD_MODE = True
    try:
        # the pipeline never runs past the last COMPLETED month-end (future
        # months clamp below) and its window is widened to cover the span's
        # own start so early spans answer from data.
        pipeline_end = min(_decision_month_end(end_m.to_timestamp(how="end")),
                           _decision_month_end(cfg.output_end))
        start_decision = (start_m - 1).to_timestamp(how="end")
        cfg_eff = replace(cfg, output_start=min(
            pd.Timestamp(cfg.output_start), start_decision).strftime("%Y-%m-%d"))
        with _capture_diagnostics() as diag:
            r = _run(_mrs(True, None, pipeline_end.strftime("%Y-%m-%d"), cfg_eff))
            r["notes"] = list(r.get("notes", [])) + diag.notes
            r["warnings"] = diag.warnings()
            r["errors"] = diag.errors()
    finally:
        _CARD_MODE = False
    if "error" in r:
        return {"rows": [], "status": "ERROR", "notices": [str(r["error"])],
                "error": r["error"], "source": r.get("source", ""),
                "detail": r.get("detail", {})}
    final = r["signals_df"]
    by_month = ({sig.get("month", ""): (final.loc[i], sig)
                 for i, sig in zip(final.index, r["all_signals"])}
                if final is not None and not final.empty
                and r.get("all_signals") else {})
    months = [m for m in by_month if m]
    if not months:
        return {"rows": [], "status": "ERROR",
                "notices": ["no predictable months in the pipeline result"]}
    first_avail = pd.Period(min(months), freq="M")
    last_avail = pd.Period(max(months), freq="M")
    lo, hi, notices = _span_clamp(start_m, end_m, first_avail, last_avail)
    if lo > hi:
        return {"rows": [], "status": "ERROR",
                "notices": notices + [
                    f"no predictable months in {start_m.strftime('%Y-%m')}"
                    f"..{end_m.strftime('%Y-%m')} (first predictable: "
                    f"{first_avail.strftime('%Y-%m')})"]}
    rows = _span_rows(by_month, lo, hi)
    status, reasons = _card_status(
        {"scenario_key": rows[-1]["scenario_key"] if rows else None,
         "credit_signal": r.get("credit_signal", "ON"), "error": None,
         "data_tier": _TIER_LABELS.get(r.get("source_mode", ""), "unknown")},
        r.get("panel"), cfg, pipeline_end)
    out = {"rows": rows, "status": status,
           "notices": notices + list(r.get("warnings", [])) + reasons,
           "as_of": str(pipeline_end.date()),
           "data_tier": _TIER_LABELS.get(r.get("source_mode", ""), "unknown"),
           "credit": "ON" if r.get("credit_signal", "ON") == "ON" else "OFF"}
    _json_safe_values(out)
    return out


# ── § 23.9 · helpers for the layer: month parsing + JSON-safe coercion.
def _parse_month_arg(value: str, label: str) -> pd.Period:
    """v14.7 §3.2: 'YYYY-MM' or 'YYYY-MM-DD' -> monthly Period (bad input
    raises ValueError with the offending value; the CLI maps it to exit 2)."""
    v = str(value).strip()
    for fmt in ("%Y-%m", "%Y-%m-%d"):
        try:
            ts = datetime.strptime(v, fmt)
        except ValueError:
            continue
        return pd.Period(f"{ts.year}-{ts.month:02d}", freq="M")
    raise ValueError(f"{label} expects YYYY-MM or YYYY-MM-DD, got {value!r}")


# ── § 23.9.1 · _json_safe_values — strict JSON-safety, in place.
def _json_safe_values(d: dict) -> None:
    """v14.7 §3.3/G5: make a layer dict strictly JSON-serializable in place:
    NaN/inf floats become None (json.dumps would emit invalid NaN tokens),
    numpy scalars become Python scalars."""
    for k, v in list(d.items()):
        if isinstance(v, float) and not math.isfinite(v):
            d[k] = None
        elif isinstance(v, (np.floating,)):
            d[k] = float(v) if np.isfinite(v) else None
        elif isinstance(v, (np.integer,)):
            d[k] = int(v)
        elif isinstance(v, dict):
            _json_safe_values(v)
        elif isinstance(v, list):
            d[k] = [_json_scalar(x) for x in v]


# ── § 23.9.2 · _json_scalar — one JSON-safe scalar (NaN/inf -> None).
def _json_scalar(v):
    if isinstance(v, float):
        return v if math.isfinite(v) else None
    if isinstance(v, (np.floating,)):
        return float(v) if np.isfinite(v) else None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, dict):
        _json_safe_values(v)
        return v
    if isinstance(v, list):
        return [_json_scalar(x) for x in v]
    return v


# ── § 23.9.3 · _fred_panel_memo_key — the _mrs RAM-memo key for the default pipeline.
def _fred_panel_memo_key(cfg: Config) -> tuple:
    """v14.7: the _mrs RAM-memo key for a live default pipeline — lets now()
    read the panel of the pipeline regime_now() just ran without a second
    fetch (misses simply skip the staleness check)."""
    end = _decision_month_end(cfg.output_end)
    return ("fred_panel", end.strftime("%Y-%m-%d")[:10], cfg.fetch_start,
            cfg.output_start, cfg.output_end,
            bool(FORCE_SNAPSHOT), bool(cfg.fred_api_key),
            getattr(cfg, "credit_mode", "auto"))


# ── § 23.9.4 · _card_runner_up — display-only second-best scenario.
def _card_runner_up(base: dict, panel, cfg: Config) -> dict | None:
    """v14.7 §3.1: the runner-up {key, confidence} for the card — the
    second-highest scenario score on the decision row, ordered exactly like
    _classify_row_full ((-fit, priority)).  Display-only; None when the
    panel/row is unavailable or the pipeline winner was a kill-switch the
    raw scores cannot reproduce."""
    if panel is None or panel.empty or not base.get("as_of"):
        return None
    try:
        drow = panel.loc[pd.Timestamp(base["as_of"])]
    except (KeyError, TypeError, ValueError):
        return None
    scored = []
    for sc in _scenarios_for(cfg):
        if sc.key == "NEUTRAL_WAIT_AND_SEE" or sc.score is None:
            continue
        try:
            fit = sc.score(drow)
        except Exception as e:
            # recorded (never silent), same contract as _classify_row_full
            _diag().score_errors.append(
                f"{sc.key} (card runner-up): {type(e).__name__}: {e}")
            continue
        if pd.notna(fit):
            scored.append((sc, float(fit)))
    if len(scored) < 2:
        return None
    scored.sort(key=lambda x: (-x[1], x[0].priority))
    return {"key": scored[1][0].key, "name": scored[1][0].name,
            "confidence": scored[1][1]}


# ── § 23.9.5 · _card_cache_ready — is the warm card servable right now?
def _card_cache_ready(cfg: Config) -> bool:
    """v14.7 §3.1/Step 8: True when the verified card cache can serve ALL
    series fresh — the precondition for staying silent on stderr (a cold
    card prints exactly ONE progress line there).  Any miss -> False."""
    try:
        client = FREDClient(cfg.fred_api_key or "", cfg)
        return len(client._load_card_series(INDICATORS)) == len(INDICATORS)
    except Exception:
        return False


# ── § 23.11 · render_card — v14.7 §3.1: the PURE card renderer.
def render_card(d: dict, color: bool | None = None) -> str:
    """v14.7 §3.1: render a now() dict as the prediction card — a PURE
    formatter (no market data, no I/O), <=22 lines, identical layout with
    or without colour.  Colors: header cyan; regime green (risk-on) /
    yellow (NEUTRAL) / red (defensive); LONG green, SHORT red; notes dim;
    warnings yellow."""
    on = _use_color() if color is None else bool(color)

    def c(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if on else text

    if d.get("status") == "ERROR" or d.get("error") is not None:
        return c("MEDS  no prediction: " + str(d.get("error", "unknown error"))[:160], "33")
    version = d.get("version", __version__)
    credit = d.get("credit", "ON")
    credit_txt = ("ON" if credit == "ON"
                  else "OFF (free FRED) \u26a0")
    lines = [
        c(f"MEDS v{version} | as of {d.get('as_of', '?')} | "
          f"data: {d.get('data_tier', '?')} | credit: {credit_txt}", "36"),
        "-" * 72,
    ]
    quality = str(d.get("quality", "MED"))
    qcolor = "32" if quality == "HIGH" else ("33" if quality == "MED" else "31")
    rclass = d.get("regime_class", "risk_on")
    rcolor = {"defensive": "31", "neutral": "33"}.get(rclass, "32")
    lines.append(
        f"PREDICTION  {d.get('month', '?')}   "
        + c(f"{d.get('name', '?'):<38.38}", rcolor)
        + f"quality {c(quality, qcolor)}")
    ru = d.get("runner_up") or {}
    ru_txt = (f"{ru.get('key', '-')} {float(ru.get('confidence', 0.0) or 0.0):.2f}"
              if ru else "-")
    lines.append(
        f"confidence  {float(d.get('confidence') or 0.0):.2f}  "
        f"dominance {float(d.get('dominance') or 0.0):.2f}  "
        f"phase {d.get('cycle_phase', '-')}  runner-up {ru_txt}")
    lines.append(f"leverage    conviction {float(d.get('conviction_leverage') or 0.0):.2f}")
    basket = d.get("basket") or {}
    longs = "  ".join(basket.get("longs") or []) or "-"
    shorts = "  ".join(basket.get("shorts") or []) or "-"
    lines.append(f"LONG        {c(longs, '32')}")
    lines.append(f"SHORT       {c(shorts, '31') if shorts != '-' else '-'}")
    if credit != "ON":
        excluded = ", ".join(d.get("excluded_scenarios")
                              or ("CREDIT_CRUNCH", "EARLY_CYCLE_RE_ACCELERATION"))
        lines.append(c(f"\u26a0 credit signal OFF: {excluded} excluded; "
                       f"kill-switch off. Not trade-grade.", "33"))
    elif d.get("status") == "DEGRADED":
        for reason in (d.get("status_reasons") or ["degraded data quality"])[:3]:
            lines.append(c(f"\u26a0 {reason}", "33"))
    for w in (d.get("warnings") or [])[:2]:
        if w not in (d.get("status_reasons") or []):
            lines.append(c(f"note: {w}", "2"))
    return "\n".join(lines)


# ── § 23.12 · render_span — v14.7 §3.2: the PURE span table renderer.
def render_span(result: dict, color: bool | None = None) -> str:
    """v14.7 §3.2: render a span() dict as the month-by-month table — a PURE
    formatter.  Tickers are NEVER cut (a long basket simply widens the row);
    regime names are trimmed to keep 80-column rows readable."""
    on = _use_color() if color is None else bool(color)

    def c(text: str, code: str) -> str:
        return f"\033[{code}m{text}\033[0m" if on else text

    if result.get("status") == "ERROR" and not result.get("rows"):
        return c("MEDS span: " + str(result.get("error")
                                     or (result.get("notices") or ["no rows"])[0])[:160], "33")
    head = (f"MEDS span {result['rows'][0]['month']} \u2192 {result['rows'][-1]['month']}"
            if result.get("rows") else "MEDS span (empty)")
    out = [c(f"{head} | as of {result.get('as_of', '?')} | "
             f"credit {result.get('credit', '?')}", "36")]
    if result.get("notices"):
        for n in result["notices"][:4]:
            out.append(c(f"  note: {n}", "2"))
    out.append(f"{'MONTH':<10} {'REGIME':<24} {'CONF':>5} {'LEV':>5}  "
               f"{'LONG':<16} SHORT")
    for row in result.get("rows") or []:
        rclass = ("defensive" if row.get("scenario_key") in CFG.defensive_regimes
                  else ("neutral" if row.get("scenario_key") == "NEUTRAL_WAIT_AND_SEE"
                        else "risk_on"))
        rcolor = {"defensive": "31", "neutral": "33"}.get(rclass, "32")
        name = str(row.get("name", "?"))[:24]
        longs = " ".join(row.get("longs") or []) or "-"
        shorts = " ".join(row.get("shorts") or []) or "-"
        out.append(
            f"{row.get('month', '?'):<10} "
            + c(f"{name:<24.24}", rcolor)
            + f" {float(row.get('confidence') or 0.0):5.2f}"
              f" {float(row.get('conviction_leverage') or 0.0):5.2f}  "
            + c(f"{longs:<16}", "32")
            + c(shorts, "31" if shorts != "-" else "0"))
    return "\n".join(out)


# ── § 23.13 · __all__ — the public API surface (v14.7 §3.3).
__all__ = [
    "mrs", "mrs_at", "mrs_ml", "regime_now", "ticker_score", "tpl",
    "now", "span", "render_card", "render_span",
    "Config", "CFG", "SCENARIOS", "INDICATORS",
    "FeatureEngine", "FREDClient", "RiskManager", "Backtester",
    "WalkForwardEngine", "generate_performance_summary",
    "safe_weighted_score", "safe_weighted_score_detail",
    "block_bootstrap_ci", "annualized_sharpe", "max_drawdown",
    "alpha_beta", "calmar", "extract_tickers", "parse_signals",
    "build_pit_manifest", "main_cli", "run_engine",
]


# ═══════════════════════════════════════════════════════════════════════════
#  § 24 · ML DATASET BUILDER
# ═══════════════════════════════════════════════════════════════════════════
_TICKER_UNIVERSE: list[str] = sorted({
    t for sc in SCENARIOS
    for t in extract_tickers(sc.long + sc.short)
})
_TICKER_IDX: dict[str, int] = {t: i for i, t in enumerate(_TICKER_UNIVERSE)}


# ── § 24.1 · _numeric_feature_cols
def _numeric_feature_cols(panel: pd.DataFrame) -> list[str]:
    return [c for c in panel.columns if pd.api.types.is_numeric_dtype(panel[c])]


# ── § 24.2 · _nan_summary
def _nan_summary(panel: pd.DataFrame, top: int = 20) -> pd.DataFrame:
    s = pd.DataFrame({
        "n_missing": panel.isna().sum(),
        "pct":       (panel.isna().mean() * 100).round(1),
        "first_ok":  panel.apply(lambda c: c.first_valid_index()),
        "last_ok":   panel.apply(lambda c: c.last_valid_index()),
    })
    return s.sort_values("pct", ascending=False).head(top)


# ── § 24.3 · build_ml_dataset ── Fetch (once) → run engine (once) → align X (t) with Y (t+1) → chu…
def build_ml_dataset(
    live: bool = True,
    data=None,
    cfg: Config = CFG,
    chunk_years: int = 5,
    nan_strategy: str = "drop_rows",   # "drop_rows" | "ffill" | "drop_cols" | "off"
    save: str | None = None,
    verbose: bool = True,
):
    """
    Fetch (once) → run engine (once) → align X (t) with Y (t+1) → chunk by 5y.

    v13 L-3 fix: the default nan_strategy is "drop_rows". The old default
    "ffill" called .bfill(), which back-filled early-sample features with
    FUTURE values. "ffill" now forward-fills ONLY (3-month staleness cap)
    and still drops rows whose leading NaNs cannot be filled.

    Returns
    -------
    X_chunks     : list[np.ndarray]  (N_i, F)
    y_cls_chunks : list[np.ndarray]  (N_i,)   int  {0,1}
    y_ret_chunks : list[np.ndarray]  (N_i,)   float decimal
    meta         : dict
    """
    # 1. Fetch + classify + backtest — ALL once.
    # v14.4 U7: the fetch runs under a private diagnostics sink — no prints,
    # no module-global mutation; collected notes ride along in meta/errors.
    with _capture_diagnostics() as _bd:
        r = _run(_mrs(live, data, None, cfg))
        if "error" in r:
            r["warnings"] = _bd.warnings()
            r["errors"] = _bd.errors()
            return None, None, None, r

    panel, final, sigs = r["panel"], r["signals_df"], r["all_signals"]

    if verbose and not _bd.quiet:
        print(f"[ml] panel: {len(panel.columns)} cols, {len(panel)} months "
              f"({panel.index[0].date()} → {panel.index[-1].date()})")

    # ── FIX: promote "date" column back to a DatetimeIndex ─────────────
    final = final.copy()
    final["date"] = pd.to_datetime(final["date"])
    final = final.set_index("date")

    bt = Backtester(cfg)
    uni = {t for s in sigs for t in (s["longs"] + s["shorts"])} | {"SPY", "QQQ", "^VIX", "VXX"}
    bt.preload_prices(uni, cfg)
    res = bt.run(sigs, cfg)
    if res.empty:
        return None, None, None, {"error": "Backtest returned no rows. "
                                           "Yahoo Finance likely failed — check network."}

    # 2. Align panel & regime on common DatetimeIndex
    common_idx = panel.index.intersection(final.index)
    panel = panel.loc[common_idx]
    final = final.loc[common_idx]

    res_idx = res.set_index("Month")
    trade_months = pd.Series(
        (common_idx + pd.DateOffset(months=1)).strftime("%Y-%m"),
        index=common_idx,
    )
    valid = trade_months.isin(res_idx.index).values
    if valid.sum() == 0:
        return None, None, None, {"error": "No overlapping months between panel & backtest."}

    panel_a = panel.loc[valid]
    final_a = final.loc[panel_a.index]
    Y_rows  = res_idx.loc[trade_months.values[valid]]

    if verbose and not _bd.quiet:
        print(f"[ml] overlap: {len(panel_a)} months "
              f"({panel_a.index[0].date()} → {panel_a.index[-1].date()})")

    # 3. Assemble X blocks
    num_cols = _numeric_feature_cols(panel_a)
    X_num = panel_a[num_cols].values.astype(np.float64)

    X_tick = np.zeros((len(panel_a), len(_TICKER_UNIVERSE)), dtype=np.float64)
    for i, (_, row) in enumerate(final_a.iterrows()):
        for t in extract_tickers(row["long"]):
            j = _TICKER_IDX.get(t)
            if j is not None: X_tick[i, j] = 1.0
        for t in extract_tickers(row["short"]):
            j = _TICKER_IDX.get(t)
            if j is not None: X_tick[i, j] = -1.0

    X_reg = np.zeros((len(panel_a), len(_CLASSES)), dtype=np.float64)
    for i, k in enumerate(final_a["scenario_key"].values):
        j = _CLASS_IDX.get(k)
        if j is not None: X_reg[i, j] = 1.0

    # v13: use the REALIZED leverage from the backtest (decided at entry from
    # information available at entry) instead of the classify_panel placeholder
    # that hardcodes regime_acc=0.5 / months=1.
    if "Conviction Lev" in Y_rows.columns:
        X_lev = Y_rows["Conviction Lev"].astype(float).values.reshape(-1, 1)
    else:
        X_lev = final_a["conviction_leverage"].astype(float).values.reshape(-1, 1)

    X = np.hstack([X_num, X_tick, X_reg, X_lev])
    feat_names = (
        num_cols
        + [f"L_{t}" for t in _TICKER_UNIVERSE]
        + [f"R_{k}" for k in _CLASSES]
        + ["conv_lev"]
    )

    # 4. Assemble Y
    ret_pct = Y_rows["Net Portfolio Return %"].astype(float).values
    y_ret = ret_pct / 100.0
    y_cls = (ret_pct > 0).astype(np.int32)

    # 5. NaN handling
    n_before = len(X)
    if nan_strategy == "drop_rows":
        keep = np.isfinite(X).all(axis=1) & np.isfinite(y_ret)
        X, y_cls, y_ret = X[keep], y_cls[keep], y_ret[keep]
        panel_a, final_a = panel_a.iloc[keep], final_a.iloc[keep]

    elif nan_strategy == "drop_cols":
        col_ok = np.isfinite(X).all(axis=0)
        X = X[:, col_ok]
        feat_names = [f for f, ok in zip(feat_names, col_ok) if ok]
        row_ok = np.isfinite(X).all(axis=1) & np.isfinite(y_ret)
        X, y_cls, y_ret = X[row_ok], y_cls[row_ok], y_ret[row_ok]
        panel_a = panel_a.iloc[row_ok]; final_a = final_a.iloc[row_ok]

    elif nan_strategy == "ffill":
        # L-3 FIX: forward-fill only (3-month staleness cap). NEVER bfill —
        # back-filling leaks future values into early-sample rows.
        X_df = pd.DataFrame(X, columns=feat_names, index=panel_a.index)
        X_df = X_df.ffill(limit=3)
        row_ok = X_df.notna().all(axis=1).values & np.isfinite(y_ret)
        X = X_df.values[row_ok]
        y_cls, y_ret = y_cls[row_ok], y_ret[row_ok]
        panel_a = panel_a.iloc[row_ok]; final_a = final_a.iloc[row_ok]

    elif nan_strategy == "off":
        pass
    else:
        return None, None, None, {"error": f"Unknown nan_strategy='{nan_strategy}'"}

    n_after = len(X)
    if verbose and not _bd.quiet:
        print(f"[ml] NaN ({nan_strategy}): {n_before} → {n_after} rows, "
              f"{len(feat_names)} features")

    if n_after == 0:
        print("\n  ❌ All rows dropped. Top-20 columns by % missing:")
        try:
            print(_nan_summary(panel_a).to_string())
        except (TypeError, ValueError):
            print(_nan_summary(panel).to_string())
        return None, None, None, {
            "error": "No rows survived NaN dropping. Check the missing-value "
                     "report above; series that start mid-sample must simply "
                     "start later in the chunks (that is the honest behavior)."
        }

    # 6. Chunk into calendar windows
    years = panel_a.index.year.values
    X_chunks, y_cls_chunks, y_ret_chunks, periods = [], [], [], []
    y0, y1 = int(years.min()), int(years.max())
    for ys in range(y0, y1 + 1, chunk_years):
        ye = ys + chunk_years
        m = (years >= ys) & (years < ye)
        if not m.any(): continue
        X_chunks.append(X[m])
        y_cls_chunks.append(y_cls[m])
        y_ret_chunks.append(y_ret[m])
        periods.append((ys, ye - 1, int(m.sum())))

    meta = {
        "feature_names": feat_names,
        "ticker_list":   _TICKER_UNIVERSE,
        "class_list":    _CLASSES,
        "chunk_periods": periods,
        "n_features":    len(feat_names),
        "n_chunks":      len(X_chunks),
        "date_range":    (str(panel_a.index[0].date()), str(panel_a.index[-1].date())),
        "class_balance": {int(c): int((y_cls == c).sum()) for c in np.unique(y_cls)},
        "nan_strategy":  nan_strategy,
        "notes": list(r.get("notes", [])) + _bd.notes,
        "warnings": _bd.warnings(),
    }

    if save:
        if not os.path.isabs(save):
            save = _dp(save)
        np.savez_compressed(
            save,
            **{f"X_{i}": a for i, a in enumerate(X_chunks)},
            **{f"y_cls_{i}": a for i, a in enumerate(y_cls_chunks)},
            **{f"y_ret_{i}": a for i, a in enumerate(y_ret_chunks)},
            meta=np.array([meta], dtype=object),
        )
        if verbose and not _bd.quiet:
            print(f"[ml] saved → {save}")

    return X_chunks, y_cls_chunks, y_ret_chunks, meta


# ═══════════════════════════════════════════════════════════════════════════
#  § 25 · CLI ENTRYPOINT — flags · exit codes · --check-endpoints
#     0   successful completion
#     1   runtime / unexpected failure
#     2   NO-GO or validation failure (data guards, empty results)
#     64  invalid configuration / arguments (EX_USAGE)
#     130 intentional stop / SIGINT
#   Errors are printed to stderr and NEVER accompany exit code 0.
# ═══════════════════════════════════════════════════════════════════════════
# ── § 25.1 · MedsConfigError ── v13.2 J-1: invalid configuration / command line (exit code 64).
class MedsConfigError(Exception):
    """v13.2 J-1: invalid configuration / command line (exit code 64)."""


# ── § 25.2 · _MedsArgumentParser ── Minimal argument parser whose errors exit with 64 (invalid usa…
class _MedsArgumentParser:
    """Minimal argument parser whose errors exit with 64 (invalid usage)
    instead of argparse's default 2 (which would be indistinguishable from
    a validation NO-GO)."""

    # · __init__
    def __init__(self) -> None:
        self.flags: dict[str, dict] = {}

    # · add_flag
    def add_flag(self, name: str, takes_value: bool = False, default=None,
                 metavar: str = "") -> None:
        self.flags[name] = {"takes_value": takes_value, "default": default,
                            "metavar": metavar}

    # · parse
    def parse(self, argv: list[str]) -> dict:
        out = {name: spec["default"] for name, spec in self.flags.items()}
        i = 0
        while i < len(argv):
            a = argv[i]
            if a in ("-h", "--help"):
                self.print_help()
                raise SystemExit(0)
            if a in self.flags:
                spec = self.flags[a]
                if spec["takes_value"]:
                    if i + 1 >= len(argv):
                        raise MedsConfigError(f"{a} requires a value ({spec['metavar']})")
                    out[a] = argv[i + 1]
                    i += 2
                else:
                    out[a] = True
                    i += 1
                continue
            raise MedsConfigError(f"unrecognized argument: {a}")
        return out

    # · print_help
    def print_help(self) -> None:
        print(f"meds.py — Macro Regime & L/S Scenario Engine (v{__version__})\n"
              "\n"
              "usage: meds.py [--audit] [--from DATE [--to DATE]] [--json]\n"
              "               [--ticker TICKER] [--csv FILE] [--check-endpoints]\n"
              "               [--snapshot] [--start DATE] [--end DATE]\n"
              "               [--fetch-start DATE] [--output-start DATE]\n"
              "               [--output-end DATE] [--ml] [--demo] [--paper]\n"
              "               [--pit-manifest] [--print-config]\n"
              "               [--check-config] [--require-credit]\n"
              "\n"
              "  (no flag)        THIS month's prediction as a short card:\n"
              "                   regime, confidence, leverage, LONG/SHORT\n"
              "                   basket, data tier and credit state.  No\n"
              "                   backtest; a cold run fetches 22 FRED series\n"
              "                   (one stderr line), later runs are warm.\n"
              "  --from DATE      month-by-month regimes + baskets for a span\n"
              "                   (DATE = YYYY-MM or YYYY-MM-DD; --to defaults\n"
              "                   to the current prediction month; months are\n"
              "                   clamped to the predictable range with a\n"
              "                   notice).  --start/--end alias --from/--to.\n"
              "  --json           with (no flag)/--from: machine-readable dict.\n"
              "  --audit          the FULL engine run: FRED fetch -> walk-\n"
              "                   forward -> backtest -> prereg evaluation ->\n"
              "                   readiness report (the v14.6.2 plain run;\n"
              "                   --csv FILE and --prereg-full imply it).\n"
              "  --validate       exact alias of the plain (card) run.\n"
              "  --ticker TICKER  score ONE ticker against the live regime and\n"
              "                   exit: prints the score card, or machine-\n"
              "                   readable JSON with --json.\n"
              "  --csv FILE       opt-in: write the monthly results table to FILE.\n"
              "  --check-endpoints  one tiny read-only request per source (FRED API,\n"
              "                   ALFRED vintage, fredgraph.csv, Yahoo, data/ CSVs) and\n"
              "                   the REAL response or failure for each.\n"
              "  --snapshot       force the frozen snapshot for FRED series AND prices\n"
              "                   (deterministic offline run; needs snapshot/)\n"
              "  --start DATE     first backtest month (alias for --output-start)\n"
              "  --end DATE       last backtest month (alias for --output-end)\n"
              "  --ml             build the ML dataset (data/macro_ml.npz)\n"
              "  --demo           short API demo (mrs / mrs_at, live data)\n"
              "  --paper          append the CURRENT signal to paper_record.csv as a\n"
              "                   timestamped FORWARD record (no backtest, no returns;\n"
              "                   >= 12 consecutive rows is the path to a STRATEGY\n"
              "                   verdict)\n"
              "  --pit-manifest   print the point-in-time manifest (generated from\n"
              "                   code: per-series publication lag + dated evidence)\n"
              "  --prereg-full    ALSO run the PREREG part-B robustness suites\n"
              "                   (C07-C11: ~24 full-window re-runs on the already-\n"
              "                   fetched data — costs x2/x3, publication lags\n"
              "                   +/-50%, decision thresholds +/-20%, the 3x3\n"
              "                   confidence/dominance grid) before the PREREG\n"
              "                   verdict.  Without it C07-C11 stay NOT_RUN and\n"
              "                   the overall verdict stays INCOMPLETE.\n"
              "  --require-credit refuse to run without the ICE BofA OAS credit\n"
              "                   history (BAMLH0A0HYM2 + BAMLC0A0CM reaching the\n"
              "                   window's need date, after any data/*_full.csv\n"
              "                   repair): NO-GO exit 2, the v14.6.1 behaviour.\n"
              "                   Default (auto) runs WITHOUT the credit signal\n"
              "                   when it is not available: both series dropped,\n"
              "                   CREDIT_CRUNCH + EARLY_CYCLE_RE_ACCELERATION\n"
              "                   excluded, credit kill-switch OFF, PREREG\n"
              "                   BLOCKED — loud banner, results not comparable\n"
              "                   to credit-ON runs.\n"
              "  --print-config   print the effective Config (API key redacted) and exit\n"
              "  --check-config   validate dates/windows offline and exit\n"
              "\n"
              "setup: pip install pandas numpy yfinance   (yfinance is optional —\n"
              "       everything except live prices works without it) and FREDAPI in\n"
              "       the environment or a .env next to this file (never created).\n"
              "\n"
              "exit codes: 0 ok | 1 unexpected failure | 2 NO-GO/validation |\n"
              "            64 invalid config/arguments | 130 SIGINT")

# ── § 25.3 · _validated_date
def _validated_date(value: str, flag: str) -> str:
    try:
        pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError) as e:
        raise MedsConfigError(f"{flag} expects a YYYY-MM-DD date, got {value!r} ({e})")
    return value


# ── § 25.4 · _validate_window ── Semantic window validation (exit 2, not 64: the dates parse, but…
def _validate_window(cfg: Config) -> None:
    """Semantic window validation (exit 2, not 64: the dates parse, but the
    configuration cannot produce a valid run)."""
    fs, os_, oe = (pd.Timestamp(cfg.fetch_start), pd.Timestamp(cfg.output_start),
                   pd.Timestamp(cfg.output_end))
    if oe < os_:
        raise MedsValidationError(
            f"output_end ({cfg.output_end}) is before output_start ({cfg.output_start}).")
    if os_ < fs:
        raise MedsValidationError(
            f"output_start ({cfg.output_start}) is before fetch_start ({cfg.fetch_start}); "
            f"there would be no warmup for the rolling features.")


# ── § 25.5 · _run_check_endpoints ── v14.4 section 4: --check-endpoints — ONE tiny read-only reque…
def _run_check_endpoints(cfg: Config) -> int:
    """v14.4 section 4: --check-endpoints — ONE tiny read-only request per
    source, the REAL response printed, nothing written, nothing created.
    Exit 0 only if every line is OK; skipped lines (no key set) are facts and
    count as not-OK per the spec."""
    all_ok = True

    def _ok(msg: str) -> None:
        nonlocal all_ok
        print(_c("OK   ", "32") + msg)

    def _fail(text: str) -> None:
        nonlocal all_ok
        all_ok = False
        print(_c("FAIL ", "31") + text)

    key = cfg.fred_api_key or _load_env_fredapi()

    # 1 ── FRED API: DFF, last 10 days
    if not key:
        print("skipped: FREDAPI not set in environment")
        all_ok = False
    else:
        today = datetime.now().strftime("%Y-%m-%d")
        start = (datetime.now() - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
        url = _build_fred_obs_url("DFF", key, observation_start=start,
                                  observation_end=today, units="lin")
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url)   # v14.7 Step 8: default UA (middlebox-safe)
            with urllib.request.urlopen(req, timeout=15.0) as r:
                payload = json.loads(r.read().decode("utf-8"))
            obs = payload.get("observations", [])
            last = obs[-1] if obs else {}
            _ok(f"FRED API DFF: HTTP {r.status}, count={payload.get('count')}, "
                f"last observation {last.get('date')}={last.get('value')} "
                f"elapsed {time.monotonic() - t0:.2f}s")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except (OSError, ValueError):
                body = ""
            _fail("FRED API DFF\n" + _describe_failure(
                "FRED API", "series=DFF", url=url, http=e, body=body,
                elapsed=time.monotonic() - t0))
        except OSError as e:
            _fail("FRED API DFF\n" + _describe_failure(
                "FRED API", "series=DFF", url=url, exc=e,
                elapsed=time.monotonic() - t0))
        except ValueError as e:            # non-JSON 200 body
            _fail("FRED API DFF (JSON parse)\n" + _describe_failure(
                "FRED API", "series=DFF", url=url, exc=e,
                elapsed=time.monotonic() - t0))

    # 2 ── ALFRED: CPIAUCSL with a small realtime window
    if not key:
        print("skipped: FREDAPI not set in environment")
    else:
        url = _build_fred_obs_url(
            "CPIAUCSL", key,
            observation_start="2020-01-01", observation_end="2020-06-30",
            units="lin", realtime_start="2020-01-01", realtime_end="2020-06-30")
        t0 = time.monotonic()
        try:
            req = urllib.request.Request(url)   # v14.7 Step 8: default UA (middlebox-safe)
            with urllib.request.urlopen(req, timeout=15.0) as r:
                payload = json.loads(r.read().decode("utf-8"))
            obs = payload.get("observations", [])
            first = obs[0] if obs else {}
            _ok(f"ALFRED CPIAUCSL realtime window: HTTP {r.status}, "
                f"count={payload.get('count')}, first row "
                f"realtime_start={first.get('realtime_start')} "
                f"realtime_end={first.get('realtime_end')} "
                f"date={first.get('date')} value={first.get('value')} "
                f"elapsed {time.monotonic() - t0:.2f}s")
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except (OSError, ValueError):
                body = ""
            _fail("ALFRED CPIAUCSL\n" + _describe_failure(
                "FRED API", "series=CPIAUCSL realtime 2020-01-01..2020-06-30",
                url=url, http=e, body=body, elapsed=time.monotonic() - t0))
        except OSError as e:
            _fail("ALFRED CPIAUCSL\n" + _describe_failure(
                "FRED API", "series=CPIAUCSL realtime 2020-01-01..2020-06-30",
                url=url, exc=e, elapsed=time.monotonic() - t0))
        except ValueError as e:
            _fail("ALFRED CPIAUCSL (JSON parse)\n" + _describe_failure(
                "FRED API", "series=CPIAUCSL realtime 2020-01-01..2020-06-30",
                url=url, exc=e, elapsed=time.monotonic() - t0))

    # 3 ── FRED public CSV: DFF, last 10 days
    cosd = (datetime.now() - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    coed = datetime.now().strftime("%Y-%m-%d")
    url = _build_public_csv_url("DFF", cosd, coed)
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url)   # v14.7 Step 8: default UA (middlebox-safe)
        with urllib.request.urlopen(req, timeout=15.0) as r:
            body = r.read().decode("utf-8", errors="replace")
        if "observation_date" not in body:
            _fail("FRED public CSV DFF (non-CSV body)\n" + _describe_failure(
                "FRED public CSV", "series=DFF", url=url,
                body=f"status 200 but no observation_date header: {body[:200]}"))
        else:
            lines = [l for l in body.splitlines() if l.strip()]
            _ok(f"FRED public CSV DFF: header {lines[0]!r}, last row {lines[-1]!r} "
                f"elapsed {time.monotonic() - t0:.2f}s")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            body = ""
        _fail("FRED public CSV DFF\n" + _describe_failure(
            "FRED public CSV", "series=DFF", url=url, http=e, body=body,
            elapsed=time.monotonic() - t0))
    except OSError as e:
        _fail("FRED public CSV DFF\n" + _describe_failure(
            "FRED public CSV", "series=DFF", url=url, exc=e,
            elapsed=time.monotonic() - t0))

    # 4 ── Yahoo: SPY, last 5 trading days
    yf_mod = _load_yf()
    if yf_mod is None:
        _fail("Yahoo SPY\n" + _describe_failure(
            "Yahoo (yfinance)", "ticker=SPY", exc=_YF_IMPORT_ERROR))
    else:
        try:
            df = yf_mod.download(["SPY"], period="10d", interval="1d",
                                 progress=False, auto_adjust=True)
            if df is None or df.empty:
                shared = getattr(yf_mod, "shared", None)
                errs = getattr(shared, "_ERRORS", None) or {}
                _fail("Yahoo SPY\n" + _describe_failure(
                    "Yahoo (yfinance)", "ticker=SPY period=10d",
                    body=str(errs.get("SPY", "empty frame"))))
            else:
                _ok(f"Yahoo SPY: shape {df.shape}, last date {df.index[-1]}")
        except Exception as e:
            _fail("Yahoo SPY\n" + _describe_failure(
                "Yahoo (yfinance)", "ticker=SPY period=10d", exc=e))

    # 5 ── data/: expected credit CSVs
    for sid in ("BAMLH0A0HYM2", "BAMLC0A0CM", "BAMLH0A1HYBBEY", "BAMLH0A0HYM2_full"):
        path = _dp(f"{sid}.csv")
        if not os.path.isfile(path):
            print(f"not found: {path}")
            continue
        try:
            df = pd.read_csv(path)
            first, last = str(df.iloc[0, 0]), str(df.iloc[-1, 0])
            _ok(f"local file {os.path.basename(path)}: {len(df)} rows, "
                f"first {first}, last {last}")
        except (ValueError, OSError) as e:
            _fail("local file " + path + "\n" + _describe_failure(
                "local file", f"file={path}", exc=e))
    return 0 if all_ok else 1



# ── § 25.6 · main_cli
def main_cli(argv: list[str] | None = None) -> int:
    import signal

    global FORCE_SNAPSHOT, _PHASE

    # v14 section 5.1 → v14.4 U4: required packages are pandas and numpy only
    # (yfinance is lazy — a missing package must not break --help /
    # --check-config / --pit-manifest / import; the price tiers degrade and
    # report the real import error).  One clear line + the exact pip command.
    _missing = [m for m, mod in (("pandas", pd), ("numpy", np)) if mod is None]
    if _missing:
        print(f"missing required package(s): {', '.join(_missing)}\n"
              f"install them with:  pip install {' '.join(_missing)}",
              file=sys.stderr)
        return 2

    def _sigint_handler(signum, frame):
        raise KeyboardInterrupt(f"SIGINT ({signum}) received")

    try:
        signal.signal(signal.SIGINT, _sigint_handler)
    except (ValueError, OSError):
        pass  # not the main thread / unsupported platform

    parser = _MedsArgumentParser()
    parser.add_flag("--validate")
    parser.add_flag("--audit")
    parser.add_flag("--from", takes_value=True, default=None, metavar="DATE")
    parser.add_flag("--to", takes_value=True, default=None, metavar="DATE")
    parser.add_flag("--ticker", takes_value=True, default=None, metavar="TICKER")
    parser.add_flag("--json")
    parser.add_flag("--csv", takes_value=True, default=None, metavar="FILE")
    parser.add_flag("--check-endpoints")
    parser.add_flag("--ml")
    parser.add_flag("--demo")
    parser.add_flag("--print-config")
    parser.add_flag("--check-config")
    parser.add_flag("--snapshot")
    parser.add_flag("--paper")
    parser.add_flag("--pit-manifest")
    parser.add_flag("--fetch-start", takes_value=True, default=None, metavar="DATE")
    parser.add_flag("--output-start", takes_value=True, default=None, metavar="DATE")
    parser.add_flag("--output-end", takes_value=True, default=None, metavar="DATE")
    parser.add_flag("--start", takes_value=True, default=None, metavar="DATE")
    parser.add_flag("--end", takes_value=True, default=None, metavar="DATE")
    parser.add_flag("--prereg-full")
    parser.add_flag("--require-credit")

    try:
        _PHASE = "cli"
        args = parser.parse(list(sys.argv[1:] if argv is None else argv))

        if args["--snapshot"]:
            # v13.3 M-3: force the frozen snapshot everywhere (offline runs).
            FORCE_SNAPSHOT = True

        cfg = CFG
        overrides = {}
        if args["--fetch-start"] is not None:
            overrides["fetch_start"] = _validated_date(args["--fetch-start"], "--fetch-start")
        if args["--output-start"] is not None:
            overrides["output_start"] = _validated_date(args["--output-start"], "--output-start")
        if args["--output-end"] is not None:
            overrides["output_end"] = _validated_date(args["--output-end"], "--output-end")
        # v14.7 §3.2: --start/--end keep their DATE validation (exit 64 on
        # junk, exactly as v14.6.2) and their backtest-window meaning WITH
        # --audit; without it they alias --from/--to (the span).
        if args["--start"] is not None:
            _validated_date(args["--start"], "--start")
            if args["--audit"]:
                overrides["output_start"] = args["--start"]
        if args["--end"] is not None:
            _validated_date(args["--end"], "--end")
            if args["--audit"]:
                overrides["output_end"] = args["--end"]
        # v14.6.2 STEP A: --require-credit = v14.6.1 behaviour exactly
        # (NO-GO when the ICE BofA OAS history is not usable).
        if args["--require-credit"]:
            overrides["credit_mode"] = "required"
        if overrides:
            cfg = replace(cfg, **overrides)
        _validate_window(cfg)
        # v13.3 M-2: dates the user pinned explicitly are never auto-clipped.
        explicit_dates = frozenset(
            field for flag, field in (("--fetch-start", "fetch_start"),
                                      ("--output-start", "output_start"),
                                      ("--output-end", "output_end"),
                                      ("--start", "output_start"),
                                      ("--end", "output_end"))
            if args[flag] is not None and (args["--audit"] or flag.startswith("--output")
                                           or flag == "--fetch-start"))

        if args["--print-config"]:
            d = asdict(cfg)
            d["fred_api_key"] = "<redacted:present>" if cfg.fred_api_key else "<redacted:empty>"
            d["version"] = __version__
            print(json.dumps(d, indent=2, default=str))
            return 0

        if args["--check-config"]:
            print(f"OK  meds v{__version__}: fetch_start={cfg.fetch_start} "
                  f"output_start={cfg.output_start} output_end={cfg.output_end} "
                  f"window validated")
            _dn = _dotenv_status()
            if _dn:
                print(f"  i  {_dn}")
            return 0

        # v14.1 S1 (audit D7): the PIT manifest is GENERATED FROM CODE — the
        # single source of truth (the shipped snapshot/PIT_MANIFEST.json is a
        # stale artifact of an older build).
        if args["--pit-manifest"]:
            print(json.dumps(build_pit_manifest(), indent=2, ensure_ascii=True))
            return 0

        # v14.4 section 4: the one diagnostic the owner runs himself.  Makes
        # ONE tiny read-only request per source, prints the real responses,
        # writes nothing, creates nothing.
        if args["--check-endpoints"]:
            rc = _run_check_endpoints(cfg)
            print("RESULT: OK" if rc == 0 else "RESULT: NO-GO one or more endpoints failed")
            return rc

        # v14.4 U1/U8: score ONE ticker and return (no full run).
        if args["--ticker"] is not None:
            _PHASE = "ticker score"
            out = ticker_score(args["--ticker"], cfg=cfg)
            if args["--json"]:
                # machine-readable stream: no RESULT line, key-free dict
                print(json.dumps(out, default=str, indent=2))
                return 0 if "error" not in out else 2
            _print_ticker_score(out)
            if "error" in out:
                print(_c("RESULT: NO-GO " + str(out["error"])[:200], "33"))
                return 2
            # v14.6 STEP B: the data fingerprint of the frame this score
            # used (print-only, <= 12 lines) — comparable across runs.
            print_price_fingerprint(out.get("price_frame_fingerprint"))
            print(_c("RESULT: OK", "32"))
            return 0

        # v14.1 S8: forward paper record — never a performance claim.
        if args["--paper"]:
            rc = run_paper_mode(cfg)
            print(_c("RESULT: OK", "32") if rc == 0 else
                  _c("RESULT: NO-GO paper mode failed (see PAPER MODE ERROR)", "33"))
            return rc

        if args["--ml"]:
            _PHASE = "ml dataset"
            print(f"▶ Building ML dataset → {_dp('macro_ml.npz')}")
            X, yc, yr, meta = build_ml_dataset(live=True, nan_strategy="drop_rows",
                                                save="macro_ml.npz", cfg=cfg)
            if X is None:
                print(f"ERROR: {meta}", file=sys.stderr)
                print(_c("RESULT: NO-GO ML dataset build failed", "33"))
                return 2
            print(f"\nchunks: {meta['n_chunks']}  | features: {meta['n_features']}")
            for (a, b, n), xc, cc, rc in zip(meta["chunk_periods"], X, yc, yr):
                print(f"  {a}-{b}: X={xc.shape}  y_cls={cc.shape}  "
                      f"win_rate={cc.mean():.1%}  avg_ret={rc.mean():+.3%}")
            print(f"\nSaved → {_dp('macro_ml.npz')}")
            print(_c("RESULT: OK", "32"))
            return 0

        if args["--demo"]:
            _PHASE = "demo"
            o = mrs(live=True, cfg=cfg)
            if "error" in o:
                print(f"ERR: {o['error']}", file=sys.stderr)
                print(_c("RESULT: NO-GO demo: no regime computed", "33"))
                return 2
            print("\n── LATEST ──")
            print({k: o["latest_regime"].get(k) for k in
                   ("date", "scenario_key", "regime", "conviction_leverage")})
            print("\n── NEXT-MONTH BASKET ──")
            print({k: o["latest_signal"].get(k) for k in
                   ("month", "longs", "shorts", "conviction_leverage")})
            print("\n── AS-OF 2020-03-31 ──")
            at = mrs_at("2020-03-31", live=True, cfg=cfg)
            if "error" in at:
                print(f"ERR: {at['error']}", file=sys.stderr)
                print(_c("RESULT: NO-GO demo as-of: no regime computed", "33"))
                return 2
            print(at)
            print(_c("RESULT: OK", "32"))
            return 0

        # ── v14.7 §3.1/§3.2: the CARD (bare run) and the SPAN (--from/--to) ─
        # The old full report moved behind --audit (--csv / --prereg-full
        # still imply it, so every v14.6.2 invocation keeps working).
        # Exit 0 = valid prediction (DEGRADED included); exit 2 = no
        # prediction / bad input, one line, no traceback.
        run_audit = bool(args["--audit"] or args["--csv"] is not None
                         or args["--prereg-full"])
        if not run_audit:
            _PHASE = "card"
            span_from = args["--from"] or args["--start"]
            span_to = args["--to"] or args["--end"]
            try:
                if span_from is not None or span_to is not None:
                    start = span_from or _decision_month_end(cfg.output_end).strftime("%Y-%m")
                    result = span(start, span_to, cfg=cfg)
                    if args["--json"]:
                        print(json.dumps(result, default=str, indent=1))
                        return 0 if result.get("status") != "ERROR" else 2
                    print(render_span(result))
                    return 0 if result.get("status") != "ERROR" else 2
                if not FORCE_SNAPSHOT and not _card_cache_ready(cfg):
                    print("MEDS: cold fetch — 22 FRED series (later runs are warm)",
                          file=sys.stderr)
                card = now(cfg=cfg)
                if card.get("status") == "ERROR":
                    # Step 8: when no key is configured, name the free-key fix.
                    hint = ("" if _load_env_fredapi() else
                            " — a free FRED API key may help: fred.stlouisfed.org "
                            "(set FREDAPI or a .env next to meds.py)")
                    print("MEDS: no prediction — "
                          + str(card.get("error", "unknown error"))[:200] + hint,
                          file=sys.stderr)
                    return 2
                if args["--json"]:
                    print(json.dumps(card, default=str, indent=1))
                    return 0
                print(render_card(card))
                return 0
            except ValueError as e:
                print(f"MEDS: {e}", file=sys.stderr)
                return 2

        # ── the full AUDIT run (--audit; --csv/--prereg-full imply it) ─────
        # v14.5 FIX-3 (part B): --prereg-full also runs the C07-C11
        # robustness suites (costs 2x/3x, ±50% publication lags, ±20%
        # decision thresholds, the 3x3 grid) before the PREREG verdict.
        df_results = main(cfg, explicit_dates,
                          prereg_full=bool(args["--prereg-full"]))
        if args["--csv"]:
            out_path = args["--csv"]
            os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
            df_results.to_csv(out_path, index=False)
            print(f"  saved → {out_path} (--csv)")
        print(_c("RESULT: OK", "32"))
        return 0

    except KeyboardInterrupt:
        # U5: Ctrl+C exits 130 cleanly, naming the phase it stopped in; the
        # traceback appears only under MEDS_DEBUG=1.
        print(f"Interrupted (SIGINT) during phase '{_PHASE}' — no results produced.",
              file=sys.stderr)
        if os.environ.get("MEDS_DEBUG"):
            import traceback
            traceback.print_exc()
        print(_c(f"RESULT: FAILED interrupted during phase '{_PHASE}' (SIGINT)", "31"))
        return 130
    except MedsConfigError as e:
        print(f"CONFIG ERROR: {e}", file=sys.stderr)
        print("Run with --help for usage.", file=sys.stderr)
        print(_c(f"RESULT: FAILED {e}", "31"))
        return 64
    except (MedsValidationError, RuntimeError) as e:
        # NO-GO / validation failures: guards refused to run, empty data, etc.
        print(f"NO-GO: {e}", file=sys.stderr)
        first_line = str(e).splitlines()[0] if str(e) else "validation refused to run"
        print(_c(f"RESULT: NO-GO {first_line}", "33"))
        return 2
    except SystemExit as e:
        return int(e.code or 0)
    except Exception as e:
        # v14.4 section 3: the final fatal path prints the REAL error text;
        # MEDS_DEBUG=1 adds the traceback.
        print(f"UNEXPECTED FAILURE: {type(e).__name__}: {e}", file=sys.stderr)
        if os.environ.get("MEDS_DEBUG"):
            import traceback
            traceback.print_exc()
        print(_c(f"RESULT: FAILED {type(e).__name__}: {e}", "31"))
        return 1


# ── § 25.7 · __main__ guard —— real exit code, never swallowed
if __name__ == "__main__":
    sys.exit(main_cli())
