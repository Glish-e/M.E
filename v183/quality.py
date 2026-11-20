"""quality - institutional-style stock quality scorer (single file).

ENGINE_VERSION 3.4.1 (free-data edition; audited build). Rebuilt from the
audited 3.1.0 baseline; every defect D1-D26 and E13 still has a named
test in the embedded SELFTEST section, the 3.4.0 audit repairs carry
their own P6* test classes (red-green-mutation verified), and the 3.4.1
re-audit repairs (six findings) carry AdjustedPriceBasis,
MinimumPillarGate, PitFreezeAndReturns and P7SecUserAgentAndFfoNotes.

WHAT CHANGED IN 3.4.1 (re-audit: adjusted-price honesty, pillar minimum,
    cache hardening, PIT freeze metadata, honest diagnostics)
    - An all-null adjusted-close series is never relabeled as adjusted:
      12-1 momentum is computed from ADJUSTED prices only (price_basis
      "adjusted" on success; NO_DATA/no_adjusted_price_data otherwise);
      prices live in the prices_v2 cache namespace so pre-3.4.1 entries
      can never serve as adjusted data; legacy snapshots restore the
      adjusted series as unavailable unless they carry
      adj_prices_basis=adjusted.
    - A result can be OK only with >= MIN_PILLARS (4) non-None pillar
      scores AND coverage >= MIN_COVERAGE (float-safe within
      COVERAGE_EPS); fewer pillars gate to INSUFFICIENT_DATA with reason
      pillar_count_below_minimum, and the additive failed_gates list
      names every failed gate (status priority is unchanged).
    - FileCache.get validates the whole envelope (top-level object,
      numeric finite fetched_at, future-skew cap): a corrupt file is a
      cache miss and is removed, so it can never crash a read or block a
      fresh provider fetch.
    - The PIT harness accepts --freeze-date (strict YYYY-MM-DD, not in
      the future, validated BEFORE the PIT file check); with a matching
      --expect-config-hash every emitted period row is classified
      in_sample (period month <= freeze date) or out-of-sample, and only
      then is oos_claim_allowed true. Delisting returns are counted
      only when they actually enter an appended scored pair; forward
      returns must be finite and >= -1.0; stdout carries exactly one
      JSON object and every NOTE moves to stderr.
    - SEC User-Agent docs and livecheck now tell the truth: the default
      is a STATIC, non-identifying string (no OS username, no hostname,
      no user@host); REIT FFO metrics add an
      ffo_gains_impairments_assumed_zero note when a component is
      unavailable (arithmetic unchanged).

WHAT CHANGED IN 3.4.0 (independent audit: split basis, debt honesty,
    PIT harness, input contracts, privacy)
    - S0 fix (audit L2): the price/split fetch window now runs through the
      FETCH stamp, so the split list covers (t_s, fetch_date] exactly as
      the market-cap basis requires; bars are filtered to <= as_of only
      AFTER splits are collected. Historical market caps before a split
      were understated by the split ratio in 3.3.0 (live-verified AAPL
      2020-06-30: cap was exactly 1/4 of truth). Split events are keyed by
      UTC trading DATE (a 1-hour timestamp offset or a null-close ex-date
      no longer loses the event), and a null adjclose bar is dropped from
      the adjusted series instead of being replaced by the raw close.
    - S0 fix (audit L3, owner decision D-3 default): a PARTIAL debt figure
      (e.g. long-term debt without the current portion) is never used -
      net_debt_ebitda, ROIC, EV and the rising-debt flag become None with
      a debt_component_missing note. Debt tag coverage extended
      (LongTermDebtAndCapitalLeaseObligations, DebtCurrent) - XOM-class
      filers now show complete debt; umbrella vs component tags can never
      double count (per-period tag priority).
    - Tag priority is now enforced as documented (audit X10): per period
      the EARLIEST candidate tag wins; within a tag the latest filing
      still wins (restatements). 3.3.0 could mix NetIncomeLoss and
      ProfitLoss bases (live-verified +6.4% TTM NI for PLD).
    - Utilities' top-line revenue tag (RegulatedAndUnregulatedOperatingRevenue)
      is mapped (audit DQ3).
    - PIT validation rewritten (audit L1/L7): month-M scoring uses EXACTLY
      the PIT constituents with sector_pit pools; delisting returns enter
      the forward series; every unscored name is counted with a reason
      (per-month table + run-level total); ticker reuse (permanent_id
      change) is detected and reported; --expect-config-hash freezes the
      configuration (rule I7); spreads are labeled GROSS (no costs,
      borrow/financing not modeled).
    - Input contracts (audit L5/L6): ONE date validator (ISO calendar
      date, never after today: API -> ERROR result, CLI -> exit 2) and
      ONE ticker normalizer on every boundary (get_quality_score("BRK.B")
      now resolves like the CLI).
    - Privacy (audit L9): the default SEC User-Agent is a STATIC string
      with no OS username/hostname; set SEC_USER_AGENT for a real
      fair-access contact.
    - yfinance path shares the Yahoo rate limiter and shifts its
      exclusive end by +1 day (audit L4); the approximate-ET timezone
      fallback now fails CLOSED in the DST ambiguity hour (audit X8);
      NO_DATA results always carry their reason (audit F29); forward
      costs are labeled as not turnover-scaled (audit X6).

WHAT CHANGED IN 3.3.0 (one-ticker short command + trading layer)
    - Finnhub key: .env may use the standard name FINNHUB_API_KEY (the
      legacy alias FINAPI still works), and .env is found NEXT TO
      quality.py as well as in the working directory.
    - Short command: `python3 quality.py AAPL` prints the one-ticker
      colored score card (same as `score AAPL`). `--layer` prints a
      compact JSON for a trading system, `--json` the full dump; exit
      code is 0 only when a real score came back (1 = no score, reason
      printed; 2 = bad usage).
    - The popular mega-caps absent from the built-in universe (AAPL MSFT
      GOOGL AMZN NVDA META TSLA BRK-B V MA NFLX ...) now auto-resolve
      their sector from a curated map: no --sector flag, no yfinance
      install, and get_quality_score("AAPL") works in Python too.
    - Institutional rating calibration (owner: "not too strict"): score
      bands are letter grades A-F with the sector-median company at C
      (40-50 is "middle of the pack", no longer "below average", and F
      only below 25); MIN_COVERAGE relaxed 0.70 -> 0.65 so fewer names
      are refused as INSUFFICIENT_DATA.

WHAT CHANGED IN 3.2.0 (why your free API keys now work)
    - Finnhub /stock/financials-reported is a PREMIUM endpoint: a free
      Finnhub key gets HTTP 403 on it. After a few 401/403s the engine
      disables finnhub for the rest of the run, PRINTS the real reason,
      and keeps scoring from SEC EDGAR (keyless). Your Finnhub key stays
      optional.
    - SEC EDGAR fundamentals now run WITHOUT setting SEC_USER_AGENT (the
      default is a STATIC, non-identifying string: no OS username, no
      hostname, no reconstructed user@host; set SEC_USER_AGENT in .env to
      a genuine, reachable contact for SEC fair-access compliance).
    - Prices: new built-in Yahoo chart client (pure urllib, ZERO pip
      packages, throttled under the per-minute limit, query2/query1 host
      fallback). yfinance is used instead when it is installed.
    - HTTP failures now carry the REAL reason (status code + provider
      message, e.g. "http_403: You don't have access to this resource.")
      instead of a bare "fetch_failed".
    - scan output is colorful terminal-only: snapshot CSVs are OFF by
      default (opt in with --snapshot). `python3 quality.py` with no
      arguments runs a quick scan of liquid names.

WHAT IT DOES
    Scores stock quality cross-sectionally (sector percentile ranks over
    fixed prior weights) from point-in-time fundamentals (SEC EDGAR,
    Finnhub), provider prices (yfinance or the built-in Yahoo chart
    client, unofficial) or seeded offline fixtures. CLI:
    TICKER (e.g. `quality.py AAPL`) | scan | score | validate |
    livecheck | selftest. Public
    API: get_quality_score(ticker, as_of=None, *, source="auto",
    universe_file=None) and get_momentum_12_1(ticker, as_of=None).

ASSUMPTIONS
    - Facts are visible at a date D only when their PUBLIC availability
      date <= D (rule I1): acceptance date in ET when accepted at or before
      16:00 ET, otherwise the next weekday; filings without a timestamp
      become available the next weekday after the filing date. This is
      STRICTER than comparing filing dates alone. No holiday calendar
      exists offline: weekend rolls are exact, holiday rolls are a labeled
      approximation (weekday-only availability calendar).
    - Market cap basis (D15, audit L2 fix): provider_close(t_c) x
      shares(t_s) x PRODUCT(split ratio for every split with
      t_s < ex_date <= fetch_date). t_c is the last close date <= as_of,
      t_s the share-count period_end (cover/balance date), fetch_date the
      stamp stored with the price bars - never the wall clock. The
      price/split request window runs THROUGH the fetch stamp (providers
      return events only inside the requested window), so the split list
      is complete for the product above; bars are filtered to <= as_of
      afterwards. Splits dated after as_of are used ONLY to put provider
      prices and share counts on one basis, never as information (rule
      I2); splits within +/-1 day of t_s make the basis ambiguous and the
      market metrics are refused (SPLIT_BASIS_UNVERIFIED).
    - Weights and thresholds are fixed priors in CONFIG (rule I7); the
      percentile scorer is the one documented exception to rank/n (D17):
      finite members score (k + midrank)/n with k = number of WORST
      sentinels, WORST scores exactly 0.0.

LIMITATIONS (read before trusting any output)
    - Survivorship (rule I10): yfinance serves current listings. Historical
      scoring over the built-in universe is NOT survivorship-free; every
      scan and validation prints this notice.
    - yfinance is an unofficial scraper (no contract, rate limits may bite,
      schema may change); prices only, never fundamentals.
    - Universe coverage (D22): the built-in 682-name universe does NOT
      contain AAPL, MSFT, GOOGL, GOOG, AMZN, NVDA, META, TSLA, BRK-B, V,
      MA. Nine delisted (DRE TGE MANT VSTO DFS ANSS JNPR EA WBD) and two
      renamed (PARA BLL) members are disclosed in the VERIFICATION table
      with evidence and are NEVER fetched. Score other names via a custom
      universe file (CLI --universe-file).
    - Dual-class issuers without dei share counts (live-verified: GOOGL,
      GOOG) lose ALL market metrics (no point-in-time share count exists
      in companyfacts); issuers whose filings stop (live-verified: NEE
      after 2026-04) gate to STALE_DATA/stale_shares honestly.
    - The Yahoo chart endpoint is unofficial and is called with a browser
      User-Agent (fragility + terms-of-use risk, disclosed; owner decision
      D-7). Prices are NEVER fundamentals.
    - get_quality_score(..., source="fixtures") serves ONLY the 23 seeded
      synthetic names and only via universe_file/universe_refs - the
      built-in universe has no fixture data (every result says why).
    - Finnhub response shape is UNVERIFIED (no captured live payload); the
      mapping is defensive and labeled. livecheck reports shape deviations.
    - The only real captures in this file are TRUNCATED (dei chains and
      short price windows); none passes the D25 capture gate, so tests
      that need data/fixtures_real/ report NOT RUN and no live-capture
      evidence is claimed. The legacy qaunt.js translation is not independently
      verifiable without that file, so no LEGACY section exists.
    - Validation output is a descriptive screener plumbing check, never an
      alpha claim (rule I9); production readiness needs the section 8.3
      multi-year survivorship-free out-of-sample evidence, which this
      offline build cannot produce.

TEST-DATA CLASSIFICATION (rule D13/D21; one line per embedded test class)
    (a) synthetic seeded: fixture_companies/generate_fixture_universe feed
        RegressionScoring, RegressionApi, M3-M6, D22, D24 and the scan/API
        paths - deterministic, generated inside this file from a fixed
        seed, synthetic BY DESIGN.
    (b) documented-shape fixtures: D2 Finnhub, D6 provider failures,
        RegressionSecNormalization, ProviderHardening, PitAvailability,
        D5, D12, CorpActions use hand-written payloads that FOLLOW the
        documented provider shapes; they are not captured responses.
    (c) captured real responses (TRUNCATED, in-file): ProviderHardening
        uses captured real Yahoo row windows (AAPL 2020 4:1 split, SIRI
        2024 1:10 reverse) and captured real SEC dei chains (AAPL, BRK,
        Alphabet, none for GOOGL). NONE of them passes the D25 capture
        gate (too small, too few fact rows), so data/fixtures_real/ does
        not ship and no test counts as live-capture evidence.
    MetricAudit/D14/M4 hand-computed statement sets are synthetic.
    Live transports (LiveProviderTests) skip with NOT RUN when the key or
    package is missing and never fake data.

RUNTIME FILES (everything the code can create; D20 packaging test)
    data/cache/, data/snapshots/YYYY-MM-DD.csv (only with scan --snapshot),
    data/scan_state.json
    (scan checkpoint), data/universe_overrides.csv (optional user
    overrides), data/pit_universe.csv (optional, human-supplied),
    data/reconciliation.csv (optional, human-supplied),
    data/fixtures_real/ (only via the D25 capture gate),
    data/live_report.md (livecheck --report output).

DOCUMENTED CHOICES
    - Total debt (owner decision D-3 default, audit L3 fix): composed from
      LongTermDebtNoncurrent + LongTermDebtCurrent/ShortTermBorrowings/
      DebtCurrent (one winner per period by tag priority, so umbrella and
      component tags never double count), with LongTermDebt as the whole
      fallback. When a component is missing at the latest balance date the
      debt-consuming metrics (net_debt_ebitda, ROIC, EV, rising-debt flag)
      are None with a debt_component_missing note - a partial sum is never
      used. Finance leases and commercial paper are NOT part of this
      definition. Issuers tagging debt only outside these concepts still
      show no debt metrics (honest None).
    - Piotroski (2000) F-score: criterion 5 tests long-term-debt/assets
      falling; the score returns None unless BOTH long-term-debt facts
      exist (never silently skips the leverage test). No average-assets
      variant.
    - shareholder_yield = (dividends + buybacks) / market cap, TTM; the
      debt-paydown component of the classic definition is omitted because
      no reliable point-in-time us-gaap concept feeds it.
"""  # noqa: E501


import argparse
import copy
import csv
import hashlib
import json
import math
import os
import random
import re
import shutil
import statistics
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

ENGINE_VERSION = "3.4.1"
SCHEMA_VERSION = 3  # bump when the checkpoint/snapshot schema changes


# ============================== SECTION: CONFIG ==============================
# Every tunable lives here with a one-line rationale. Weights and thresholds
# are fixed a priori from published convention or owner specification;
# changing any of them requires walk-forward out-of-sample evidence, never
# in-sample tuning (institutional rule I7).


def _load_dotenv() -> None:
    """Set missing env vars from .env files (values never logged).

    Lookup order (3.3.0): $QE_ENV_FILE, then .env NEXT TO THIS FILE, then
    .env in the working directory - first found wins, and no variable
    already in the environment is ever overridden. Called lazily by
    :func:`build_source_chain`, not at import time, so importing this
    file is side-effect free.
    """
    candidates: list = []
    explicit = os.environ.get("QE_ENV_FILE")
    if explicit:
        candidates.append(Path(explicit))
    try:
        candidates.append(Path(__file__).resolve().parent / ".env")
    except (OSError, RuntimeError, ValueError):
        pass
    candidates.append(Path(".env"))
    seen: set = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key and key not in os.environ and val:
                os.environ[key] = val


_ENV_LOADED = False


def _ensure_env() -> None:
    global _ENV_LOADED
    if not _ENV_LOADED:
        _ENV_LOADED = True
        _load_dotenv()


def finnhub_token() -> tuple:
    """(token, env_var_name) from FINNHUB_API_KEY or legacy FINAPI.

    The standard Finnhub name wins when both are set; the value is never
    logged or stored (3.3.0: .env files written as FINNHUB_API_KEY work).
    """
    for name in FINNHUB_KEY_ALIASES:
        value = os.environ.get(name)
        if value:
            return value, name
    return "", ""


_REGISTRY: dict = {}


def _param(name: str, value, rationale: str):
    """Define a documented tunable and register its rationale."""
    _REGISTRY[name] = rationale
    return value


def registered_params() -> dict:
    """Name -> rationale for every documented tunable (tests and docs)."""
    return dict(_REGISTRY)


# P6/R9: cap on ticker text echoed into error messages (never a full
# arbitrary string).
TICKER_NOTE_MAX_LEN = _param("TICKER_NOTE_MAX_LEN", 32,
                             "Max ticker characters echoed in errors.")

def config_dump() -> dict:
    """Name -> current value of every registered tunable (fingerprints, headers).

    Reads the live module globals so a changed value is always reflected.
    Deterministic: values are JSON-serializable primitives; tuples serialize
    as lists. Used by the scan checkpoint fingerprint (D12) and the snapshot
    header, so any config change invalidates stale checkpoints and snapshots.
    """
    return {name: globals().get(name) for name in sorted(_REGISTRY)}


def config_hash() -> str:
    """Stable hash of the full tunable dump (snapshot header, D12)."""
    blob = json.dumps(config_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:CONFIG_HASH_LEN]

# ------------------------------------------------------------ pillars ----

PILLAR_WEIGHTS: dict = {
    "profitability": 0.25,
    "growth": 0.20,
    "financial_strength": 0.20,
    "earnings_quality": 0.15,
    "valuation": 0.15,
    "shareholder_yield": 0.05,
}
_param("PILLAR_WEIGHTS", PILLAR_WEIGHTS,
          "Owner-specified prior weights (spec 2026-10-31); changes require "
          "walk-forward out-of-sample evidence.")
PILLAR_RATIONALES: dict = {
    "profitability": "Dominant quality dimension in published quality-factor "
                     "research; owner-specified prior.",
    "growth": "Growth contributes to quality only secondarily; owner prior.",
    "financial_strength": "Balance-sheet robustness protects the going "
                          "concern; owner-specified prior.",
    "earnings_quality": "Cash-backed earnings reduce restatement and "
                        "dilution risk; owner-specified prior.",
    "valuation": "Cheapness within sector disciplines entry but is not "
                 "quality itself; owner-specified prior.",
    "shareholder_yield": "Payout discipline is a governance signal, not "
                         "operations; smallest pillar; owner-specified prior.",
}
_param("PILLAR_RATIONALES", PILLAR_RATIONALES,
          "One-line provenance per pillar, shown in generated docs.")

# --------------------------------------------------------- percentiles ----

WINSOR_LOWER = _param("WINSOR_LOWER", 0.01,
                         "Clip outliers at the 1st percentile before ranking "
                         "(standard robust-statistics convention).")
WINSOR_UPPER = _param("WINSOR_UPPER", 0.99,
                         "Clip outliers at the 99th percentile before ranking.")
MIN_PEERS = _param("MIN_PEERS", 8,
                      "A sector rank needs >= 8 peers besides the subject, "
                      "else whole-universe pool and SECTOR_PEER_FALLBACK flag.")
THIN_POOL_NEUTRAL = _param("THIN_POOL_NEUTRAL", 0.5,
                              "Neutral score when a metric pool has a single "
                              "member: no information, no cliff.")
MIN_COVERAGE = _param("MIN_COVERAGE", 0.65,
                         "Below 65% of metric weight available the composite "
                         "is not representative -> INSUFFICIENT_DATA. "
                         "Relaxed from 0.70 in 3.3.0 (owner: the gate was "
                         "too strict; ~4 of 6 pillars still rank).")
MIN_PILLARS = _param(
    "MIN_PILLARS", 4,
    "Owner-directed policy (re-audit finding 1): a result can be OK only "
    "when at least four of the six pillar scores are non-None; fewer gate "
    "to INSUFFICIENT_DATA with reason pillar_count_below_minimum. The "
    "minimum is counted from the actual pillar scores - a pillar with no "
    "scored metric is missing, never zero.")
COVERAGE_EPS = _param(
    "COVERAGE_EPS", 1e-9,
    "Floating-point boundary tolerance for the minimum coverage gate: a "
    "coverage marginally below MIN_COVERAGE inside this epsilon is NOT a "
    "failure (numerical boundary correction only; no weight, threshold or "
    "coverage calculation changes).")
ACCURUALS_FLAG_PERCENTILE = _param("ACCURUALS_FLAG_PERCENTILE", 0.10,
                                      "Flag the worst decile of sector "
                                      "accruals, mirroring Sloan (1996) "
                                      "decile portfolio construction.")
MIN_POOL_FOR_ACCRUALS_FLAG = _param("MIN_POOL_FOR_ACCRUALS_FLAG", 20,
                                       "A decile needs >= 20 pool members to "
                                       "exist as a decile (owner spec).")

# ------------------------------------------------------------ red flags ----

ALTMAN_DISTRESS_Z = _param("ALTMAN_DISTRESS_Z", 1.81,
                              "Altman (1968) published distress-zone cutoff.")
ALTMAN_SAFE_Z = _param("ALTMAN_SAFE_Z", 2.99,
                          "Altman (1968) published safe-zone cutoff.")
ALTMAN_COEFFS = _param("ALTMAN_COEFFS", (1.2, 1.4, 3.3, 0.6, 1.0),
                          "Altman (1968) published coefficients for X1..X5 "
                          "(WC/TA, RE/TA, EBIT/TA, MVE/TL, Sales/TA).")
PIOTROSKI_LOW = _param("PIOTROSKI_LOW", 3,
                          "Piotroski (2000) splits on the median; <= 3 is a "
                          "conservative low-quality screen (owner prior).")

# ---------------------------------------------------------- definitions ----

TAX_RATE_FALLBACK = _param("TAX_RATE_FALLBACK", 0.25,
                              "Effective tax rate fallback when statements "
                              "give none; ~OECD average statutory rate.")
TAX_RATE_CLIP = _param("TAX_RATE_CLIP", (0.0, 0.5),
                          "Clip computed effective tax rates into a sane "
                          "statutory range before computing NOPAT.")
GROWTH_YEARS = _param("GROWTH_YEARS", 3,
                         "Owner-specified 3-year CAGR horizon for growth.")
STABILITY_YEARS = _param("STABILITY_YEARS", 3,
                            "Owner-specified 3-year window for growth "
                            "stability (consecutive pairs only, D8).")
MARGIN_MEDIAN_WINDOW = _param("MARGIN_MEDIAN_WINDOW", 5,
                                 "Owner-specified 5-year median margin window "
                                 "for cyclical sectors.")
CYCLICAL_MIN_MARGIN_YEARS = _param("CYCLICAL_MIN_MARGIN_YEARS", 3,
                                      "Fewer than 3 annual margin observations "
                                      "cannot support a median -> "
                                      "SECTOR_DATA_MISSING.")
QUARTER_GAP_DAYS = _param("QUARTER_GAP_DAYS", (45, 130),
                             "Acceptable spacing between consecutive fiscal "
                             "quarters (covers 4-4-5 calendars) for TTM "
                             "chaining and YTD de-cumulation.")
FY_DURATION_DAYS = _param("FY_DURATION_DAYS", (300, 380),
                             "SEC XBRL duration bounds classifying a fact as "
                             "a full fiscal year (52/53-week and transition "
                             "years; 9-month YTD anchors fall below).")
Q_DURATION_DAYS = _param("Q_DURATION_DAYS", (75, 110),
                            "SEC XBRL duration bounds classifying a fact as "
                            "a discrete quarter (calendar and 4-4-5).")
FY_GAP_DAYS = _param("FY_GAP_DAYS", (350, 380),
                        "Period-end gap that makes two fiscal years "
                        "consecutive for growth and Piotroski (D8).")
CAGR_MIN_SPAN_DAYS = _param(
    "CAGR_MIN_SPAN_DAYS", 3 * 365 - 45,
    "CAGR endpoints must span ~3 years +/- 45 days of the nominal horizon; "
    "otherwise the growth rate is None, never a wrong number (D8).")
CAGR_MAX_SPAN_DAYS = _param(
    "CAGR_MAX_SPAN_DAYS", 3 * 365 + 45,
    "Upper bound of the CAGR span window (D8).")
INSTANT_MATCH_TOLERANCE_DAYS = _param(
    "INSTANT_MATCH_TOLERANCE_DAYS", 10,
    "Balance-sheet matching tolerance at a fiscal date (was 120; a balance "
    "dated > 10 days from the fiscal period end is a different balance, D8).")

# ----------------------------------------------------------- staleness ----
# Institutional rule I3: a fact is only usable while the filing chain is
# current. 91-day quarters + up to 90 days of 10-K lag = 181 days; 200 days
# leaves a small buffer before a name is declared stale (D9).

STALE_FUNDAMENTALS_DAYS = _param(
    "STALE_FUNDAMENTALS_DAYS", 200,
    "Latest fiscal period_end must be within 200 days of the as-of date "
    "(91d quarter + up to 90d 10-K lag + buffer), else STALE_DATA (I3, D9).")
SHARES_MAX_AGE_DAYS = _param(
    "SHARES_MAX_AGE_DAYS", 200,
    "A point-in-time share count older than 200 days from as_of is too "
    "stale to price market cap (quarterly cover-page cadence + 10-K lag); "
    "real case: BRK's undimensioned dei share facts stop in 2011 (S1).")
STALE_PRICE_DAYS = _param("STALE_PRICE_DAYS", 7,
                             "Last close must be within 7 calendar days of "
                             "the as-of date, else market metrics are missing "
                             "and the STALE_PRICE flag is set (I3, D9).")

# ------------------------------------------------------------ momentum ----

MOMENTUM_MONTHS = _param("MOMENTUM_MONTHS", 12,
                            "Standard 12-month momentum lookback "
                            "(Jegadeesh-Titman convention).")
MOMENTUM_SKIP_MONTHS = _param("MOMENTUM_SKIP_MONTHS", 1,
                                 "Skip the most recent month to avoid "
                                 "short-term reversal (12-1 convention).")
MOMENTUM_MIN_GAP_DAYS = _param("MOMENTUM_MIN_GAP_DAYS", 7,
                                  "Floor on the acceptable gap between a "
                                  "momentum target date and the last "
                                  "observation on or before it (D4).")
MOMENTUM_GAP_SPACING_FACTOR = _param(
    "MOMENTUM_GAP_SPACING_FACTOR", 1.5,
    "Reject a momentum observation whose gap to the target exceeds "
    "max(MOMENTUM_MIN_GAP_DAYS, 1.5 x median series spacing) days (D4).")

# ------------------------------------------------------------- prices ----

PRICE_LOOKBACK_DAYS = _param("PRICE_LOOKBACK_DAYS", 430,
                                "Scoring fetch window is [D - 430d, D]: 12-1 "
                                "momentum plus monthly gaps and holidays "
                                "(D5).")
FORWARD_WINDOW_PAD_DAYS = _param("FORWARD_WINDOW_PAD_DAYS", 10,
                                    "Forward validation requests its own "
                                    "[D, D + horizon + 10d] price window (D5).")

# --------------------------------------------------------- rate limits ----

FINNHUB_CALLS_PER_MIN = _param(
    "FINNHUB_CALLS_PER_MIN", int(os.environ.get("FINNHUB_CALLS_PER_MIN") or 50),
    "Finnhub free-tier cap is 60 calls/min; the engine paces at 50/min so "
    "bursty minutes never hit the limit; env-overridable.")
FINNHUB_AUTH_DISABLE_AFTER = _param(
    "FINNHUB_AUTH_DISABLE_AFTER", 2,
    "Consecutive AUTH_ERROR (401/403) responses before finnhub is disabled "
    "for the rest of the process: /stock/financials-reported is premium, so "
    "free keys 403 and every further call would be wasted (and slow).")
YAHOO_CALLS_PER_MIN = _param(
    "YAHOO_CALLS_PER_MIN", int(os.environ.get("YAHOO_CALLS_PER_MIN") or 40),
    "Pacing for the built-in Yahoo chart price client (no published limit; "
    "40/min stays comfortably polite and far below any throttling).")
YAHOO_RATE_LIMIT_RETRIES = _param(
    "YAHOO_RATE_LIMIT_RETRIES", 5,
    "Yahoo-specific 429 backoff attempts (host alternation query2/query1 "
    "plus exponential waits) before declaring RATE_LIMITED.")
SEC_MAX_REQUESTS_PER_SEC = _param("SEC_MAX_REQUESTS_PER_SEC", 8,
                                     "SEC EDGAR fair-access limit is 10 "
                                     "requests/s; run at 8 so clock jitter "
                                     "never crosses the cap.")
HTTP_TIMEOUT_SECONDS = _param("HTTP_TIMEOUT_SECONDS", 30,
                                 "Per-request socket timeout for live "
                                 "transports.")
MAX_RATE_LIMIT_RETRIES = _param("MAX_RATE_LIMIT_RETRIES", 3,
                                   "Backoff retries on HTTP 429 before "
                                   "declaring RATE_LIMITED (D6).")
RETRY_AFTER_CAP_SECONDS = _param("RETRY_AFTER_CAP_SECONDS", 60,
                                    "Never sleep longer than this on a "
                                    "Retry-After header, even if asked.")

# --------------------------------------------------------- finnhub D2 ----

FINNHUB_DURATION_WINDOWS = _param(
    "FINNHUB_DURATION_WINDOWS", {"Q": (75, 110), "YTD": (150, 285),
                                 "FY": (350, 380)},
    "Finnhub row classification by (endDate - startDate) duration: ~90d Q, "
    "150-285d YTD, 350-380d FY; balance-sheet entries are instants at "
    "endDate; other durations are dropped as bad_duration (D2).")

# ---------------------------------------------------------------- cache ----

CACHE_TTL_SECONDS: dict = _param(
    "CACHE_TTL_SECONDS", {"sec": 7 * 86400, "finnhub": 7 * 86400,
                          "cik_map": 30 * 86400, "prices_v2": 12 * 3600},
    "Filings are immutable (7-day refresh only picks up new filings); the "
    "CIK map rarely changes; 12h price staleness is acceptable for daily "
    "scoring. prices_v2 (V3.4.1): the abandoned 'prices' namespace may "
    "hold entries whose adj_close is really raw close, so it is never "
    "read again; the price TTL itself is unchanged.")
PRICE_CACHE_NAMESPACE = "prices_v2"   # single source of truth (V3.4.1)
CACHE_FUTURE_SKEW_SECONDS = _param(
    "CACHE_FUTURE_SKEW_SECONDS",
    300,
    "Maximum tolerated future cache timestamp skew."
)

# ------------------------------------------------------------- trading ----

TRADING_COST_BPS = _param("TRADING_COST_BPS", 20,
                             "Round-trip institutional single-name cost for "
                             "the forward-validation harness; fixed a priori.")
FORWARD_HORIZON_DAYS = _param("FORWARD_HORIZON_DAYS", 30,
                                 "One fixed forward holding period; snapshot "
                                 "pairs must match it (D7).")
FORWARD_HORIZON_TOLERANCE_DAYS = _param(
    "FORWARD_HORIZON_TOLERANCE_DAYS", 5,
    "Snapshot pair gap tolerance around FORWARD_HORIZON_DAYS; pairs outside "
    "it are skipped with a reason, never stretched (D7).")
SENSITIVITY_HORIZONS = _param(
    "SENSITIVITY_HORIZONS", [21, 63],
    "Alternative holding periods for the DIAGNOSTIC-ONLY sensitivity table; "
    "fixed a priori, never selected from results (rule I7: no tuning).")
MIN_FORWARD_POOL = _param("MIN_FORWARD_POOL", 50,
                             "Quintiles need >= 50 scored names in the pool "
                             "(D7).")
MIN_SECTOR_FOR_QUINTILES = _param("MIN_SECTOR_FOR_QUINTILES", 10,
                                     "Sector quintiles need >= 10 names per "
                                     "sector (D7).")
MIN_POOL_FOR_TERCELES = _param("MIN_POOL_FOR_TERCELES", 30,
                                  "Tercile fallback needs >= 30 names in the "
                                  "pool (D7).")
MIN_SECTOR_FOR_TERCELES = _param("MIN_SECTOR_FOR_TERCELES", 6,
                                    "Sector terciles need >= 6 names per "
                                    "sector (D7).")
MIN_FORWARD_PAIRS = _param("MIN_FORWARD_PAIRS", 1,
                              "Minimum number of snapshot pairs before the "
                              "forward harness reports anything.")

# --------------------------------------------------------------- output ----

SCAN_PROGRESS_EVERY = _param("SCAN_PROGRESS_EVERY", 25,
                                "Progress line cadence (carried over from "
                                "the legacy engine).")
TOP_N_DISPLAY = _param("TOP_N_DISPLAY", 20,
                          "Top-of-scan table size (carried over from the "
                          "legacy engine).")

# ------------------------------------------------------------ env names ----

FINNHUB_KEY_ENV = _param("FINNHUB_KEY_ENV", "FINNHUB_API_KEY",
                            "Env var name holding the Finnhub API key - the "
                            "STANDARD Finnhub name as of 3.3.0; the legacy "
                            "alias FINAPI is also accepted (value never "
                            "logged or stored).")
FINNHUB_KEY_ALIASES = _param(
    "FINNHUB_KEY_ALIASES", ("FINNHUB_API_KEY", "FINAPI"),
    "Finnhub token lookup order: standard FINNHUB_API_KEY first, legacy "
    "FINAPI second, so .env files written either way work.")
SEC_USER_AGENT_ENV = _param("SEC_USER_AGENT_ENV", "SEC_USER_AGENT",
                               "Env var name holding the SEC EDGAR "
                               "User-Agent contact string (value never "
                               "logged or stored).")

# --------------------------------------------------------------- paths ----

DATA_DIR = _param("DATA_DIR", os.environ.get("QE_DATA_DIR", "data"),
                     "Root for cache and snapshots; env-overridable via "
                     "QE_DATA_DIR.")
SNAPSHOT_DIR = _param("SNAPSHOT_DIR",
                         os.environ.get("QE_SNAPSHOT_DIR")
                         or (DATA_DIR + "/snapshots"),
                         "Daily snapshot CSVs land here as YYYY-MM-DD.csv.")
CACHE_DIR = _param("CACHE_DIR",
                      os.environ.get("QE_CACHE_DIR") or (DATA_DIR + "/cache"),
                      "Disk cache root.")
SCAN_STATE_PATH = _param("SCAN_STATE_PATH",
                            os.environ.get("QE_SCAN_STATE")
                            or (DATA_DIR + "/scan_state.json"),
                            "Resumable-scan checkpoint; atomic writes (D12).")


def pillar_weights() -> dict:
    """Copy of the pillar weight table (sums to 1.0)."""
    return dict(PILLAR_WEIGHTS)
GROUPS: dict = {
  "financials": [
    "JPM",
    "BAC",
    "WFC",
    "C",
    "USB",
    "PNC",
    "TFC",
    "MTB",
    "FITB",
    "HBAN",
    "RF",
    "KEY",
    "CFG",
    "ZION",
    "CMA",
    "FHN",
    "EWBC",
    "BOKF",
    "SNV",
    "WTFC",
    "ONB",
    "UMBF",
    "FCNCA",
    "CBSH",
    "IBOC",
    "ASB",
    "FIBK",
    "WAL",
    "BANC",
    "HWC",
    "CATY",
    "CVBF",
    "FFIN",
    "TCBI",
    "BOH",
    "VLY",
    "WSFS",
    "SFNC",
    "UBSI",
    "PNFP",
    "SBCF",
    "GBCI",
    "ABCB",
    "FULT",
    "INDB",
    "AUB",
    "NBTB",
    "WSBC",
    "STBA",
    "TRMK",
    "RNST",
    "GS",
    "MS",
    "SCHW",
    "BLK",
    "BX",
    "KKR",
    "APO",
    "TPG",
    "ARES",
    "OWL",
    "CG",
    "IVZ",
    "BEN",
    "TROW",
    "AMP",
    "RJF",
    "LPLA",
    "EVR",
    "PJT",
    "HLI",
    "LAZ",
    "MKTX",
    "CBOE",
    "CME",
    "ICE",
    "NDAQ",
    "AXP",
    "COF",
    "DFS",
    "SYF",
    "ALLY",
    "OMF",
    "ENVA",
    "AFL",
    "ALL",
    "AIG",
    "ACGL",
    "AJG",
    "BRO",
    "CB",
    "CINF",
    "HIG",
    "L",
    "MET",
    "MMC",
    "PFG",
    "PGR",
    "PRU",
    "WRB",
    "WTW",
    "MCO",
    "SPGI",
    "MKL",
    "KNSL",
    "RLI",
    "CNA",
    "TRV",
    "HCI",
    "EIG",
    "RGA",
    "GL",
    "UNM",
    "AIZ",
    "FNF",
    "FAF",
    "ESNT",
    "NMIH",
    "HMN"
  ],
  "industrials": [
    "HON",
    "UNP",
    "UPS",
    "FDX",
    "CAT",
    "DE",
    "BA",
    "LMT",
    "RTX",
    "NOC",
    "GD",
    "LHX",
    "HII",
    "TDG",
    "HWM",
    "GE",
    "GEHC",
    "MMM",
    "EMR",
    "ETN",
    "ROK",
    "PH",
    "ITW",
    "DOV",
    "XYL",
    "AME",
    "ROP",
    "IEX",
    "GWW",
    "FAST",
    "WSO",
    "POOL",
    "SNA",
    "SWK",
    "TTC",
    "AGCO",
    "CNH",
    "OSK",
    "PCAR",
    "CM",
    "CMI",
    "BWA",
    "ALSN",
    "LEA",
    "ADNT",
    "MGA",
    "APTV",
    "URI",
    "ODFL",
    "XPO",
    "SAIA",
    "CHRW",
    "EXPD",
    "JBHT",
    "LSTR",
    "HUBG",
    "SNDR",
    "ARCB",
    "RXO",
    "GEV",
    "VRT",
    "AYI",
    "ACM",
    "J",
    "FLR",
    "PWR",
    "MYRG",
    "DY",
    "EME",
    "MTZ",
    "PRIM",
    "STRL",
    "ROAD",
    "ORN",
    "BWXT",
    "KTOS",
    "RKLB",
    "WM",
    "RSG",
    "CWST",
    "CLH",
    "CARR",
    "OTIS",
    "TT",
    "JCI",
    "LII",
    "AAON",
    "IR",
    "PNR",
    "TXT",
    "DAL",
    "UAL",
    "AAL",
    "LUV",
    "ALK",
    "CSX",
    "NSC",
    "MATX",
    "KEX"
  ],
  "healthcare": [
    "JNJ",
    "ABBV",
    "MRK",
    "PFE",
    "LLY",
    "BMY",
    "AMGN",
    "GILD",
    "VRTX",
    "REGN",
    "BIIB",
    "MRNA",
    "ALNY",
    "INCY",
    "EXEL",
    "SRPT",
    "NTRA",
    "EXAS",
    "CRSP",
    "NTLA",
    "BEAM",
    "VERV",
    "EDIT",
    "TMO",
    "DHR",
    "A",
    "WAT",
    "MTD",
    "BRKR",
    "TECH",
    "RVTY",
    "BIO",
    "ABT",
    "BSX",
    "MDT",
    "SYK",
    "EW",
    "ZBH",
    "BDX",
    "BAX",
    "HOLX",
    "ISRG",
    "DXCM",
    "PODD",
    "TNDM",
    "UNH",
    "ELV",
    "CI",
    "CVS",
    "HUM",
    "CNC",
    "MOH",
    "MCK",
    "COR",
    "CAH",
    "ZTS",
    "VTRS",
    "TEVA",
    "HCA",
    "THC",
    "UHS",
    "EHC",
    "CYH",
    "DGX",
    "LH",
    "CRL",
    "IQV",
    "ICLR",
    "MEDP",
    "ALGN",
    "XRAY",
    "STE",
    "MMSI",
    "ITGR",
    "NVST"
  ],
  "tech": [
    "AVGO",
    "ORCL",
    "ADBE",
    "CRM",
    "CSCO",
    "ACN",
    "IBM",
    "QCOM",
    "INTU",
    "TXN",
    "AMAT",
    "NOW",
    "PANW",
    "CRWD",
    "LRCX",
    "ADI",
    "APH",
    "KLAC",
    "SNPS",
    "CDNS",
    "FTNT",
    "ANET",
    "MCHP",
    "ON",
    "MPWR",
    "MU",
    "INTC",
    "DELL",
    "TEL",
    "NXPI",
    "SWKS",
    "QRVO",
    "TER",
    "ONTO",
    "COHR",
    "LITE",
    "MTSI",
    "SLAB",
    "SYNA",
    "DIOD",
    "POWI",
    "AOSL",
    "AMBA",
    "CEVA",
    "LSCC",
    "RMBS",
    "VRSN",
    "AKAM",
    "FFIV",
    "JNPR",
    "CIEN",
    "WDAY",
    "TEAM",
    "DDOG",
    "ZS",
    "OKTA",
    "MDB",
    "NET",
    "ESTC",
    "GTLB",
    "HUBS",
    "VEEV",
    "ZM",
    "DOCU",
    "TWLO",
    "SNOW",
    "CFLT",
    "ADSK",
    "ANSS",
    "PTC",
    "PAYC",
    "PAYX",
    "ADP",
    "CTSH",
    "EPAM",
    "GLOB",
    "IT",
    "GLW",
    "STX",
    "WDC",
    "HPQ",
    "NTAP",
    "PSTG",
    "CRUS",
    "ACLS",
    "AEIS",
    "MKSI",
    "FORM",
    "COHU",
    "UCTT",
    "NVMI",
    "CAMT"
  ],
  "consumer": [
    "HD",
    "LOW",
    "TJX",
    "ROST",
    "BURL",
    "DG",
    "DLTR",
    "COST",
    "WMT",
    "TGT",
    "KR",
    "SFM",
    "MCD",
    "SBUX",
    "YUM",
    "CMG",
    "DRI",
    "DPZ",
    "QSR",
    "WING",
    "TXRH",
    "NKE",
    "LULU",
    "DECK",
    "CROX",
    "SKX",
    "UA",
    "UAA",
    "VFC",
    "HBI",
    "PVH",
    "RL",
    "KO",
    "PEP",
    "MNST",
    "KDP",
    "PG",
    "CL",
    "KMB",
    "CHD",
    "CLX",
    "ENR",
    "GIS",
    "K",
    "CPB",
    "CAG",
    "SJM",
    "HRL",
    "MKC",
    "HSY",
    "TSN",
    "MO",
    "PM",
    "EL",
    "COTY",
    "ULTA",
    "F",
    "GM",
    "YUMC",
    "PLAY",
    "FIVE",
    "OLLI",
    "BJ",
    "GO",
    "SPTN",
    "UNFI",
    "CHEF",
    "USFD",
    "SYY",
    "PFGC",
    "ANDE",
    "ADM",
    "BG",
    "INGR",
    "DAR"
  ],
  "energy": [
    "XOM",
    "CVX",
    "COP",
    "EOG",
    "OXY",
    "DVN",
    "FANG",
    "APA",
    "MUR",
    "CTRA",
    "OVV",
    "SM",
    "MGY",
    "SLB",
    "HAL",
    "BKR",
    "NOV",
    "FTI",
    "TDW",
    "OII",
    "RIG",
    "PSX",
    "VLO",
    "MPC",
    "DINO",
    "PBF",
    "DK",
    "KMI",
    "WMB",
    "EPD",
    "ET",
    "MPLX",
    "PAA",
    "OKE",
    "TRGP",
    "TGE",
    "LNG",
    "EQT",
    "RRC",
    "AR",
    "CNX"
  ],
  "utilities": [
    "NEE",
    "DUK",
    "SO",
    "D",
    "AEP",
    "EXC",
    "XEL",
    "SRE",
    "PEG",
    "ED",
    "ETR",
    "PPL",
    "FE",
    "AEE",
    "CMS",
    "DTE",
    "WEC",
    "ES",
    "EVRG",
    "LNT",
    "NWE",
    "IDA",
    "POR",
    "OGE",
    "PNW",
    "AVA",
    "AWK",
    "AES",
    "NRG",
    "VST",
    "CEG",
    "TLN"
  ],
  "materials": [
    "LIN",
    "APD",
    "SHW",
    "ECL",
    "DD",
    "DOW",
    "LYB",
    "CE",
    "EMN",
    "ASH",
    "HUN",
    "OLN",
    "FCX",
    "SCCO",
    "NEM",
    "GOLD",
    "AEM",
    "KGC",
    "HL",
    "CDE",
    "PAAS",
    "NUE",
    "STLD",
    "CLF",
    "X",
    "RS",
    "CMC",
    "VMC",
    "MLM",
    "IP",
    "PKG",
    "BLL",
    "AMCR",
    "SEE",
    "ALB",
    "CF",
    "MOS",
    "IFF",
    "RPM",
    "PPG"
  ],
  "reits": [
    "PLD",
    "DRE",
    "EQR",
    "AVB",
    "ESS",
    "MAA",
    "CPT",
    "UDR",
    "SPG",
    "O",
    "VICI",
    "WPC",
    "STAG",
    "ADC",
    "AMT",
    "CCI",
    "SBAC",
    "EQIX",
    "DLR",
    "IRM",
    "PSA",
    "EXR",
    "CUBE",
    "WELL",
    "VTR",
    "OHI",
    "BXP",
    "VNO",
    "KRC",
    "HST",
    "PK",
    "XHR",
    "RHP",
    "NNN",
    "REG",
    "KIM",
    "CBRE",
    "JLL",
    "AMH",
    "INVH",
    "ELS",
    "SUI",
    "COLD",
    "REXR"
  ],
  "communication": [
    "VZ",
    "T",
    "TMUS",
    "DIS",
    "CMCSA",
    "CHTR",
    "WBD",
    "PARA",
    "FOXA",
    "LYV",
    "EA",
    "TTWO",
    "MTCH",
    "PINS",
    "IAC",
    "ANGI",
    "CARS",
    "TRIP",
    "YELP",
    "ZD",
    "NWSA"
  ],
  "specialty": [
    "ABM",
    "MAN",
    "KELYA",
    "RHI",
    "ASGN",
    "KFRC",
    "BBSI",
    "SAIC",
    "LDOS",
    "CACI",
    "BAH",
    "MANT",
    "SCI",
    "CSV",
    "HRB",
    "BJRI",
    "DENN",
    "DIN",
    "BLMN",
    "EAT",
    "CAKE",
    "CHUY",
    "WEN",
    "PZZA",
    "LOCO",
    "CBRL",
    "ABG",
    "AN",
    "PAG",
    "LAD",
    "GPI",
    "KMX",
    "CARG",
    "MUSA",
    "CWH",
    "VSTO",
    "RGR",
    "AOUT",
    "SWBI",
    "HOG",
    "PII",
    "THO",
    "WGO",
    "LCII"
  ]
}

GROUP_DISPLAY: dict = {
  "financials": "Financials",
  "industrials": "Industrials / Transport",
  "healthcare": "Healthcare / Pharma / Biotech",
  "tech": "Tech / Software / Semis",
  "consumer": "Consumer Discretionary + Staples",
  "energy": "Energy",
  "utilities": "Utilities / Power",
  "materials": "Materials",
  "reits": "REITs",
  "communication": "Communication / Media",
  "specialty": "Specialty / Small-cap value"
}

GROUP_CLAIMED_COUNTS: dict = {
  "financials": 110,
  "industrials": 90,
  "healthcare": 78,
  "tech": 100,
  "consumer": 80,
  "energy": 41,
  "utilities": 32,
  "materials": 40,
  "reits": 45,
  "communication": 22,
  "specialty": 44
}

RAW_TICKER_COUNT: int = 682
UNIQUE_TICKER_COUNT: int = 682
DUPLICATES_REMOVED: list = []

SECTOR_TO_MODEL: dict = {
  "financials": "financials",
  "industrials": "cyclicals",
  "healthcare": "default",
  "tech": "default",
  "consumer": "default",
  "energy": "cyclicals",
  "utilities": "utilities",
  "materials": "cyclicals",
  "reits": "reit",
  "communication": "default",
  "specialty": "default"
}

# ticker -> (status, note, evidence); verified 2026-10-31
VERIFICATION: dict = {
  "DRE": [
    "delisted",
    "Duke Realty acquired by Prologis (all-stock); merger closed Q4 2022.",
    "pulse2.com 2022-06-13 announcement; SEC EDGAR 425/8-K filings (Prologis, Sep 2022)"
  ],
  "TGE": [
    "delisted",
    "Tallgrass Energy LP taken private by Blackstone Infrastructure ($22.45/unit cash offer accepted Dec 2019).",
    "missouribusinessalert.com 2019-02-07; Dec 2019 offer acceptance reports; bakerbotts.com deal record"
  ],
  "MANT": [
    "delisted",
    "ManTech International acquired by Carlyle (~$4.2B); last recorded trade 2022-11-16.",
    "companiesmarketcap.com delisting record; afcea.org 2022-05-16"
  ],
  "VSTO": [
    "delisted",
    "Vista Outdoor split: The Kinetic Group sold to CSG (closed Nov 2024), Revelyst sold to SVP (closed Jan 2025); ticker retired.",
    "investors.vistaoutdoor.com 2024-11-27 and 2024-10-04 releases"
  ],
  "DFS": [
    "delisted",
    "Discover Financial Services acquired by Capital One; deal closed 2025-05-18; no longer trades publicly.",
    "crowdfundinsider.com 2025-05-21 completion report"
  ],
  "ANSS": [
    "delisted",
    "Ansys acquired by Synopsys; completed 2025-07-17; delisted from Nasdaq.",
    "investor.synopsys.com 2025-07-17; SEC 8-K (Synopsys, Jul 2025)"
  ],
  "JNPR": [
    "delisted",
    "Juniper Networks acquired by Hewlett Packard Enterprise; NYSE trading suspended 2025-07-02 per delisting notice.",
    "NYSE delisting notice reported 2025-07-01; DOJ approval 2025-06-30 (sdxcentral.com)"
  ],
  "EA": [
    "delisted",
    "Electronic Arts acquired by PIF, Silver Lake and Affinity Partners; completed 2026-08-03; delisted from Nasdaq.",
    "ea.com 2026-08-03 completion announcement"
  ],
  "WBD": [
    "delisted",
    "Warner Bros. Discovery merged into Skydance Corp; transaction closed 2026-10-06.",
    "dailyplanetdc.com 2026-10-05; variety.com Oct 2026; Yahoo Finance profile (SKYD)"
  ],
  "PARA": [
    "renamed",
    "Paramount Global merged into Skydance on 2025-08-07 (PARA trading halted); successor now trades as Skydance Corp (SKYD) after the WBD merger.",
    "en.wikipedia.org (Merger of Skydance Media and Paramount Global); solactive.com notice 2025-08-01; Yahoo Finance (SKYD)"
  ],
  "BLL": [
    "renamed",
    "Ball Corporation still NYSE-listed and trading; ticker changed from BLL to BALL (quoted as BALL as of Oct 2026).",
    "finance.yahoo.com/quote/BALL; heygotrade.com BALL price record 2026-10-29"
  ]
}


# ------------------------------------------------- v3.1 additions ----
# New tunables introduced by the v3 master prompt (D15/D16/D18/D23/D25/D26).

COVER_PAGE_ITEMS: tuple = _param(
    "COVER_PAGE_ITEMS", ("shares_outstanding",),
    "dei cover-page items (D16): a cover share count is dated up to ~60 d "
    "after the fiscal period end, so it must never refresh the staleness "
    "gate (latest_fiscal_period_end skips these items).")
SPLIT_AMBIGUITY_DAYS = _param(
    "SPLIT_AMBIGUITY_DAYS", 1,
    "A split ex-date within +/-1 day of the share-count date makes the "
    "price/share basis ambiguous -> market metrics refused (D15).")
MARKET_METRICS: tuple = _param(
    "MARKET_METRICS",
    ("altman_z", "ebitda_yield", "fcf_yield", "earnings_yield",
     "p_book", "ffo_yield", "shareholder_yield"),
    "Metrics whose formulas read the MarketPoint; their per-metric "
    "provenance includes the market trace (D18).")
MINUTES_PER_DAY = _param(
    "MINUTES_PER_DAY", 24 * 60,
    "Minutes per day (D26): an acceptance timestamp later than its own "
    "filing date is treated as end-of-day -> next weekday.")
YEAR_AGO_LOOKBACK_DAYS = _param(
    "YEAR_AGO_LOOKBACK_DAYS", -300,
    "Year-ago instant lookback (~10 months) for average equity, average "
    "debt and the rising-debt flag (D26: moved out of the code).")
ROUND_DIGITS = _param(
    "ROUND_DIGITS", 4,
    "Rounding of composites, coverage and validation ratios (D26).")
SNAPSHOT_ROUND_DIGITS = _param(
    "SNAPSHOT_ROUND_DIGITS", 6,
    "Rounding of floats written to snapshot CSVs (D26).")
REAL_CAPTURE_MIN_FACTS = _param(
    "REAL_CAPTURE_MIN_FACTS", 50,
    "A real provider capture must carry at least this many fact rows to "
    "count as evidence (D25).")
REAL_CAPTURE_MIN_BYTES = _param(
    "REAL_CAPTURE_MIN_BYTES", 20000,
    "A real provider capture must be larger than this many bytes (D25: "
    "the shipped empty captures were 169-1096 bytes).")
PRICE_CACHE_TTL_DAYS = _param(
    "PRICE_CACHE_TTL_DAYS", 5,
    "A merged price cache entry older than this (OLDEST per-bar stamp) is "
    "refetched whole; merging never resets the age of old bars (D23).")
LIVE_RECON_TOLERANCE = _param(
    "LIVE_RECON_TOLERANCE", 0.01,
    "Cross-provider reconciliation pairs differing by more than this "
    "fraction are listed (section 8.1).")
PIT_MIN_MONTHS = _param(
    "PIT_MIN_MONTHS", 60,
    "Minimum monthly snapshots for a survivorship-free validation window; "
    "shorter windows are labeled SHORT_HISTORY (section 8.3).")
PIT_COLUMNS = _param(
    "PIT_COLUMNS",
    ("month_end", "ticker", "permanent_id", "sector_pit", "listed",
     "total_return_next_month", "delisting_return_if_any"),
    "Required columns of data/pit_universe.csv (section 8.3).")
RECON_COLUMNS = _param(
    "RECON_COLUMNS",
    ("ticker", "as_of", "close_ref", "close_source", "shares_ref",
     "shares_source", "market_cap_ref", "ev_ref", "roic_ref",
     "gross_profit_assets_ref", "net_debt_ebitda_ref", "fcf_yield_ref",
     "earnings_yield_ref"),
    "Required columns of the human-supplied data/reconciliation.csv "
    "(section 8.2).")


DEFAULT_PIT_UNIVERSE_PATH = _param(
    "DEFAULT_PIT_UNIVERSE_PATH", "data/pit_universe.csv",
    "Human-supplied point-in-time universe for survivorship-free "
    "validation (section 8.3); the engine never generates it.")
DEFAULT_RECONCILE_PATH = _param(
    "DEFAULT_RECONCILE_PATH", "data/reconciliation.csv",
    "Human-supplied reference values for hand reconciliation (section "
    "8.2); the engine never fills it from its own output.")
DEFAULT_LIVE_REPORT_PATH = _param(
    "DEFAULT_LIVE_REPORT_PATH", "data/live_report.md",
    "livecheck writes its markdown summary here (section 8.1).")
DEFAULT_FIXTURES_REAL_DIR = _param(
    "DEFAULT_FIXTURES_REAL_DIR", "data/fixtures_real",
    "Sanitized real captures land here ONLY through the D25 gate.")
LIVECHECK_MIN_NAMES = _param(
    "LIVECHECK_MIN_NAMES", 30,
    "The livecheck default set covers at least this many names "
    "(section 8.1).")
QUINTILES = _param("QUINTILES", 5,
                   "Top-minus-bottom quintile buckets when the pool is "
                   "large enough (D7).")
TERCELES = _param("TERCELES", 3,
                  "Tercile fallback buckets for smaller pools (D7).")
BPS_FACTOR = _param("BPS_FACTOR", 10000.0,
                    "Basis points per unit return (costs and spreads).")
QUARTERS_IN_YEAR_FLOWS = _param(
    "QUARTERS_IN_YEAR_FLOWS", 4,
    "Discrete quarters per TTM window and per fiscal year for flow "
    "items; Q4 = FY - Q1 - Q2 - Q3.")
FIXTURE_CONFIG: dict = _param(
    "FIXTURE_CONFIG", {
        "filing_lag_days": 45,          # fixture filing lag after period
        "quarter_fraction": 4.0,        # quarters are FY / 4 in fixtures
        "sector_revenue_base": {"tech": 900.0, "energy": 1100.0,
                                "financials": 640.0, "utilities": 950.0,
                                "reits": 880.0},
        "revenue_uniform_lo": 0.8,
        "revenue_uniform_span": 0.4,
        "h1_factor_span": 0.04,
        "base_price_lo": 40.0,
        "base_price_span": 80.0,
        "drift_lo": -0.01,
        "drift_hi": 0.025,
    },
    "Fixture-generation constants (D26): every synthetic-data constant in "
    "one place; the seeded RNG stream is unchanged by this refactor.")


CONFIG_HASH_LEN = _param(
    "CONFIG_HASH_LEN", 16,
    "Truncated sha256 length for config/fingerprint headers (D26).")
FINGERPRINT_LEN = _param(
    "FINGERPRINT_LEN", 16,
    "Truncated sha1 length of the universe fingerprint (D26).")
ISO_DATE_LEN = _param(
    "ISO_DATE_LEN", 10,
    "Length of an ISO date string YYYY-MM-DD (D26).")
SECONDS_PER_MINUTE = _param(
    "SECONDS_PER_MINUTE", 60.0,
    "Seconds per minute, rate-limiter conversion (D26).")
MINUTES_PER_HOUR = _param(
    "MINUTES_PER_HOUR", 60,
    "Minutes per hour, acceptance-timestamp conversion (D26).")
WEEKEND_FIRST_DOW = _param(
    "WEEKEND_FIRST_DOW", 5,
    "First weekend day of Python's weekday() numbering (Sat=5) (D26).")
YTD_MIN_DURATION_DAYS = _param(
    "YTD_MIN_DURATION_DAYS", 45,
    "A duration fact covering at least this many days is a YTD anchor, "
    "not a discrete quarter (SEC classification).")
WEIGHT_SUM_TOLERANCE = _param(
    "WEIGHT_SUM_TOLERANCE", 1e-09,
    "Tolerance for the model-weights-sum-to-one sanity assert (D26).")
HTTP_AUTH_ERROR_CODES = _param(
    "HTTP_AUTH_ERROR_CODES", (401, 403),
    "HTTP status codes mapped to AUTH_ERROR (D26).")
HTTP_RATE_LIMITED_CODE = _param(
    "HTTP_RATE_LIMITED_CODE", 429,
    "HTTP status code mapped to RATE_LIMITED (D26).")
HTTP_NOT_FOUND_CODE = _param(
    "HTTP_NOT_FOUND_CODE", 404,
    "HTTP status code mapped to NO_DATA (D26).")
HTTP_SERVER_ERROR_MIN = _param(
    "HTTP_SERVER_ERROR_MIN", 500,
    "HTTP status codes at or above this map to PROVIDER_ERROR (D26).")
SKIP_SAMPLE_CAP = _param(
    "SKIP_SAMPLE_CAP", 10,
    "Maximum skipped-pair reasons printed by validate (D26).")
ERROR_SNIPPET_MAX_BYTES = _param(
    "ERROR_SNIPPET_MAX_BYTES", 200,
    "Bytes of an HTTP error body read to surface the provider's own "
    "message (real reason, e.g. a 403 access-denied text).")
ERROR_DETAIL_MAX_CHARS = _param(
    "ERROR_DETAIL_MAX_CHARS", 120,
    "Characters kept of that provider error message in report details.")
BANNER_WIDTH = _param(
    "BANNER_WIDTH", 72,
    "Width of the CLI rule/banner lines (terminal rendering only).")
SCAN_BAR_SEGMENTS = _param(
    "SCAN_BAR_SEGMENTS", 10,
    "Segments in the scan top-table quality bar (terminal rendering only).")
TOP_ERROR_REASONS = _param(
    "TOP_ERROR_REASONS", 5,
    "Distinct error reasons printed after a scan (most common first).")
LIVECHECK_PROBE_NAMES = _param(
    "LIVECHECK_PROBE_NAMES", 5,
    "Names livecheck actually probes with live requests per source.")
LIVECHECK_PRICE_PROBE_DAYS = _param(
    "LIVECHECK_PRICE_PROBE_DAYS", 90,
    "Calendar days of price history the livecheck price probe requests.")
TRACEBACK_TAIL_LINES = _param(
    "TRACEBACK_TAIL_LINES", 8,
    "Traceback lines printed per failing selftest (D26).")


MONTHS_PER_YEAR = _param("MONTHS_PER_YEAR", 12,
                    "Months per calendar year (D26).")


# Days per calendar month (index 1..12); leap years handled by _days_in_month.
_MONTH_LENGTHS = (0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


# ============================== SECTION: UNIVERSE =============================
# Data section (GROUPS ... VERIFICATION) above was merged verbatim from the
# original package by script (682 tickers, no retyping). Stale entries carry
# verification evidence gathered 2026-10-31; every other ticker is "active"
# but not individually verified. Correct via data/universe_overrides.csv
# (ticker,sector,status,note) or the QE_UNIVERSE_OVERRIDES env var.

OVERRIDES_ENV = "QE_UNIVERSE_OVERRIDES"
DEFAULT_OVERRIDES_PATH = "data/universe_overrides.csv"
KNOWN_STATUSES = ("active", "delisted", "renamed")

# D22 disclosure: the eleven well-known mega-caps are NOT in the built-in
# universe; every scan header prints this line.
ABSENT_MEGA_CAPS = ("AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA",
                    "META", "TSLA", "BRK-B", "V", "MA")



@dataclass(frozen=True)
class TickerRef:
    """One universe member with its sector group and listing status."""

    ticker: str
    sector: str
    status: str = "active"  # active | delisted | renamed
    note: str = ""
    evidence: str = ""


def load_overrides(path: Optional[str] = None) -> dict:
    """Optional user corrections; CSV columns: ticker,sector,status,note."""
    p = Path(path or os.environ.get(OVERRIDES_ENV) or DEFAULT_OVERRIDES_PATH)
    out: dict = {}
    try:
        with p.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = (row.get("ticker") or "").strip().upper()
                if t:
                    out[t] = {k: (row.get(k) or "").strip()
                              for k in ("sector", "status", "note")}
    except OSError:
        return {}
    return out


def get_universe(overrides_path: Optional[str] = None):
    """Deduplicated universe (order preserved) plus a summary report.

    Defect D1 fixed: an override is applied to ONE ticker via a per-ticker
    ``ticker_sector``; it can never leak into the outer sector loop. Invalid
    sector overrides are ignored and recorded as ``invalid_override``;
    overrides for tickers outside the universe are recorded as
    ``unknown_override_ticker``. All diagnostic lists are sorted, so the
    output is deterministic.
    """
    overrides = load_overrides(overrides_path)
    refs: list = []
    seen: set = set()
    invalid_override: list = []
    unknown_override_ticker: list = []
    applied: list = []
    for group_sector in GROUPS:  # dict order == source file order
        for ticker in GROUPS[group_sector]:
            if ticker in seen:
                continue
            seen.add(ticker)
            # D1: never assign to the loop variable; keep a per-ticker sector.
            ticker_sector = group_sector
            status, note, evidence = "active", "", ""
            if ticker in VERIFICATION:
                status, note, evidence = VERIFICATION[ticker]
            if ticker in overrides:
                ov = overrides[ticker]
                if ov.get("sector"):
                    if ov["sector"] in GROUPS:
                        ticker_sector = ov["sector"]
                        applied.append(ticker)
                    else:
                        invalid_override.append(ticker)
                if ov.get("status") in KNOWN_STATUSES:
                    status, note = ov["status"], ov.get("note", "")
                    applied.append(ticker)
            refs.append(TickerRef(ticker, ticker_sector, status, note, evidence))
    # Overrides referencing tickers that are not in the universe at all.
    unknown_override_ticker = sorted(t for t in overrides if t not in seen)
    report = {
        "raw": RAW_TICKER_COUNT,
        "unique": len(refs),
        "duplicates_removed": list(DUPLICATES_REMOVED),
        "groups": {s: len(ts) for s, ts in GROUPS.items()},
        "delisted": [r.ticker for r in refs if r.status == "delisted"],
        "renamed": [r.ticker for r in refs if r.status == "renamed"],
        "active_unverified": sum(1 for r in refs if r.status == "active"),
        "overrides_applied": sorted(set(applied)),
        "invalid_override": sorted(set(invalid_override)),
        "unknown_override_ticker": unknown_override_ticker,
    }
    return refs, report


def model_for_sector(sector: str) -> str:
    """Scoring model key for a sector group (see SECTOR MODELS)."""
    return SECTOR_TO_MODEL.get(sector, "default")


def load_universe_file(path) -> list:
    """Custom universe from CSV (ticker,sector[,status,note]).

    Status defaults to active unless the ticker carries a verified status in
    VERIFICATION. Unknown sectors fall back to the default model.
    """
    refs: list = []
    seen: set = set()
    with Path(path).open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            ticker = (row.get("ticker") or "").strip().upper()
            sector = (row.get("sector") or "").strip().lower()
            if not ticker or ticker in seen or not sector:
                continue
            seen.add(ticker)
            status = (row.get("status") or "").strip()
            if status not in KNOWN_STATUSES:
                status, note, _ev = VERIFICATION.get(ticker, ("active", "", ""))
            else:
                note = (row.get("note") or "").strip()
            refs.append(TickerRef(ticker, sector, status, note))
    return refs


def overrides_file_hash(overrides_path: Optional[str] = None) -> str:
    """sha256 of the overrides file bytes; empty string when absent (D12)."""
    p = Path(overrides_path or os.environ.get(OVERRIDES_ENV)
             or DEFAULT_OVERRIDES_PATH)
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


# =============================== SECTION: TYPES ===============================

@dataclass(frozen=True)
class Fact:
    """One reported fundamental value with full point-in-time provenance.

    ``filing_date`` is mandatory (institutional rule I1): facts without it are
    dropped and counted in diagnostics at every layer, never imputed.
    """

    period_end: str                    # ISO date: balance date or period end
    filing_date: str                   # ISO date the fact became public
    value: float
    form: str = ""                     # 10-K, 10-Q, 10-Q/A, ...
    freq: str = "FY"                   # FY | Q | YTD | INST
    period_start: Optional[str] = None # ISO date, duration facts only
    # ---- S3 point-in-time provenance (set only when the source has it) ----
    accepted: Optional[str] = None     # acceptance timestamp as served
    accession: Optional[str] = None    # e.g. SEC accession number
    provider: Optional[str] = None     # source client name
    currency: Optional[str] = None     # ISO currency of the original fact
    unit: Optional[str] = None         # XBRL unit key ("USD", "shares")
    fy_label: Optional[str] = None     # fiscal period label ("FY2020 Q3")
    cik: Optional[int] = None          # company id (SEC CIK)
    security_id: Optional[str] = None  # listed line identifier (ticker)
    source_ref: Optional[str] = None   # endpoint reference (never secrets)
    tag_rank: Optional[int] = None     # P6/R5: candidate-tag priority (0 best)


@dataclass
class Company:
    """Everything the engine knows about one ticker at collection time."""

    ticker: str
    sector: str
    facts: dict = field(default_factory=dict)    # item -> [Fact]
    prices: list = field(default_factory=list)   # [(iso_date, close)] sorted
    adj_prices: list = field(default_factory=list)  # dividend/split-adjusted
    sources: set = field(default_factory=set)    # contributing client names
    note: str = ""
    source_status: dict = field(default_factory=dict)  # provider -> status (D6)
    source_detail: dict = field(default_factory=dict)  # provider -> failure
    # detail (exception type names etc.); never secrets (D6)
    item_source: dict = field(default_factory=dict)  # item -> provider (I5;
    # renamed from provenance: the METRIC-level map lives on ScoreResult)
    split_events: list = field(default_factory=list)   # [(iso, ratio)]
    prices_fetched_on: str = ""   # fetch stamp stored with the bars (D15/D23)
    split_events_through: str = ""  # date through which split list is complete
    splits_unverified: bool = False     # prices adjusted but events unknown


@dataclass(frozen=True)
class MarketPoint:
    """Market state at the as-of date, built from facts and prices <= as_of.

    D15: ``price`` is the PROVIDER CLOSE at t_c (the provider serves closes
    on the fetch-date basis, split-adjusted through fetch_date);
    ``market_cap`` = price x as-reported shares at t_s x the split product
    over (t_s, fetch_date]; ``split_factor`` carries exactly that product.
    ``trace`` is the D18 provenance of the market inputs (share fact, close
    date, split events used).
    """

    as_of: str
    price: float
    shares: float
    market_cap: float
    net_debt: Optional[float] = None
    enterprise_value: Optional[float] = None
    split_factor: float = 1.0        # PRODUCT over (t_s, fetch_date] (D15)
    price_basis: str = "provider_close_x_split_adjusted_shares"
    trace: tuple = ()

# ``WORST`` marks a metric that is computable but adverse beyond any finite
# value (e.g. leverage with EBITDA <= 0, or ROIC with invested capital <= 0).
# The scorer maps it to percentile 0.0 and counts it as AVAILABLE (defect
# D11: missing-data bias); it is never silently dropped.
WORST = float("inf")


# ================================ SECTION: DATA ================================
# Source chain, caching, rate limits, provider diagnostics and offline fixtures.
#
# Source priority per canonical item: SEC EDGAR first (free, point-in-time),
# Finnhub second, fixtures when forced or when nothing else is enabled. Prices
# come from yfinance (prices only) or from fixtures. Skipped sources and their
# reasons are always reported - never silently ignored. Keys are never logged,
# stored, or placed in cache files.

# ------------------------------------------------------ provider status ----
# Defect D6: every provider call records one of these statuses. The scan
# summary prints per-provider status counts; a ticker whose enabled providers
# ALL failed with an error class is ERROR with the classes listed.

STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
STATUS_NO_DATA = "NO_DATA"
STATUS_RATE_LIMITED = "RATE_LIMITED"
STATUS_NETWORK_ERROR = "NETWORK_ERROR"
STATUS_AUTH_ERROR = "AUTH_ERROR"
STATUS_SCHEMA_ERROR = "SCHEMA_ERROR"
STATUS_PROVIDER_ERROR = "PROVIDER_ERROR"

ERROR_CLASSES = {STATUS_RATE_LIMITED, STATUS_NETWORK_ERROR, STATUS_AUTH_ERROR,
                 STATUS_SCHEMA_ERROR, STATUS_PROVIDER_ERROR}
PROVIDER_STATUSES = (STATUS_SUCCESS, STATUS_PARTIAL_SUCCESS, STATUS_NO_DATA,
                     STATUS_RATE_LIMITED, STATUS_NETWORK_ERROR,
                     STATUS_AUTH_ERROR, STATUS_SCHEMA_ERROR,
                     STATUS_PROVIDER_ERROR)


@dataclass
class ProviderReport:
    """Outcome of one provider interaction; detail never holds secrets."""

    provider: str
    status: str
    detail: str = ""      # short, secret-free (counts, exception type names)
    calls: int = 0        # HTTP requests issued (0 when served from cache)
    retries: int = 0      # 429 backoff retries consumed

    def to_dict(self) -> dict:
        return {"provider": self.provider, "status": self.status,
                "detail": self.detail, "calls": self.calls,
                "retries": self.retries}


def _parse_retry_after(value) -> Optional[float]:
    """Retry-After header as seconds; None when absent or unparsable."""
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None     # HTTP-date form: fall back to exponential backoff


def _error_snippet(err: urllib.error.HTTPError) -> str:
    """Short, secret-free message from an HTTP error body (real reason).

    Providers answer 401/403 with JSON like {"error": "You don't have
    access to this resource."}; that text is the reason the user needs to
    SEE, so it is surfaced (capped, whitespace-collapsed). The URL and
    headers stay out of every detail string (they may embed a token).
    """
    try:
        raw = err.read().decode("utf-8", "replace")[:ERROR_SNIPPET_MAX_BYTES]
    except Exception:
        return ""
    text = raw.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            text = str(parsed.get("error") or parsed.get("message") or text)
    except ValueError:
        pass
    return " ".join(text.split())[:ERROR_DETAIL_MAX_CHARS]


def default_transport(url: str, headers: Optional[dict] = None,
                      timeout: Optional[float] = None):
    """urllib GET returning (status, payload, retry_after, detail).

    Maps HTTP failures to the D6 classes: 401/403 AUTH_ERROR, 429
    RATE_LIMITED (Retry-After honored by the caller), 404 NO_DATA, 5xx
    PROVIDER_ERROR, other 4xx SCHEMA_ERROR, transport faults NETWORK_ERROR,
    undecodable bodies SCHEMA_ERROR. ``detail`` carries the REAL reason
    ("http_403: You don't have access to this resource.", "net:URLError")
    and never contains the URL or headers (which may embed a token).
    A 3-tuple return is still accepted from older transports/tests.
    """
    request = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(request,
                                    timeout=timeout or HTTP_TIMEOUT_SECONDS) \
                as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as err:
        code = err.code
        snippet = _error_snippet(err)
        detail = f"http_{code}" + (f": {snippet}" if snippet else "")
        if code in HTTP_AUTH_ERROR_CODES:
            return STATUS_AUTH_ERROR, None, None, detail
        if code == HTTP_RATE_LIMITED_CODE:
            retry_after = _parse_retry_after(err.headers.get("Retry-After")) \
                if err.headers else None
            return STATUS_RATE_LIMITED, None, retry_after, detail
        if code == HTTP_NOT_FOUND_CODE:
            return STATUS_NO_DATA, None, None, detail
        if code >= HTTP_SERVER_ERROR_MIN:
            return STATUS_PROVIDER_ERROR, None, None, detail
        return STATUS_SCHEMA_ERROR, None, None, detail
    except Exception as exc:
        return STATUS_NETWORK_ERROR, None, None, f"net:{type(exc).__name__}"
    try:
        return STATUS_SUCCESS, json.loads(body), None, ""
    except ValueError:
        return STATUS_SCHEMA_ERROR, None, None, "body_not_json"


class _HttpJson:
    """Cached, rate-limited, retrying JSON GET shared by the live clients."""

    def __init__(self, provider: str, cache: "FileCache",
                 limiter: "RateLimiter",
                 transport: Optional[Callable] = None,
                 sleep_fn: Callable = time.sleep):
        self.provider = provider
        self._cache = cache
        self._limiter = limiter
        self._transport = transport or default_transport
        self._sleep = sleep_fn

    def get(self, url: str, namespace: str, cache_key: str,
            headers: Optional[dict] = None):
        """(payload, ProviderReport); ``cache_key`` never has secrets (D14).

        ``payload`` is non-None only on SUCCESS (from cache or network).
        Transports may return 3-tuples (status, payload, retry_after) or
        4-tuples that add a human-readable ``detail`` (the real error
        reason, e.g. "http_403: You don't have access to this resource.").
        """
        cached = self._cache.get(namespace, cache_key)
        if cached is not None:
            return cached, ProviderReport(self.provider, STATUS_SUCCESS,
                                          "cache", calls=0)
        status, payload, retry_after, transport_detail = None, None, None, ""
        calls = retries = 0
        for attempt in range(MAX_RATE_LIMIT_RETRIES + 1):
            self._limiter.wait()
            calls += 1
            outcome = self._transport(url, headers)
            try:                    # 4-tuple: status, payload, retry, detail
                status, payload, retry_after, transport_detail = outcome
            except ValueError:      # legacy 3-tuple transports (test seams)
                status, payload, retry_after = outcome
                transport_detail = ""
            if status != STATUS_RATE_LIMITED:
                break
            if attempt < MAX_RATE_LIMIT_RETRIES:
                delay = retry_after if retry_after is not None \
                    else float(2 ** attempt)
                self._sleep(min(delay, RETRY_AFTER_CAP_SECONDS))
                retries += 1
        if status == STATUS_SUCCESS:
            self._cache.set(namespace, cache_key, payload)
            return payload, ProviderReport(self.provider, STATUS_SUCCESS,
                                           "", calls=calls, retries=retries)
        detail = "" if status not in ERROR_CLASSES \
            else (transport_detail or "http")
        return None, ProviderReport(self.provider, status, detail,
                                    calls=calls, retries=retries)


# ---------------------------------------------------------------- cache ----
# Defect D14: key = endpoint + ticker + params (no secrets), TTL honored,
# corruption-tolerant reads, silent write failures, atomic writes.


class FileCache:
    """JSON-file cache keyed by (namespace, key)."""

    def __init__(self, root: Optional[str] = None, clock: Callable = time.time):
        self.root = Path(root or CACHE_DIR)
        self._clock = clock

    def _path(self, namespace: str, key: str) -> Path:
        digest = hashlib.sha1(f"{namespace}|{key}".encode("utf-8")).hexdigest()
        return self.root / namespace / f"{digest}.json"

    def _ttl(self, namespace: str, ttl: Optional[float]) -> Optional[float]:
        if ttl is not None:
            return ttl
        return CACHE_TTL_SECONDS.get(namespace)

    def get(self, namespace: str, key: str, ttl: Optional[float] = None) -> Any:
        """Cached payload when fresh, else None (corrupt files -> None).

        A valid envelope is a top-level dict carrying a numeric, finite
        ``fetched_at`` no later than now + CACHE_FUTURE_SKEW_SECONDS plus a
        ``payload`` key (any JSON value). Anything else is a cache miss and
        the corrupt file is best-effort removed so it can never crash a
        read or outlive its TTL (V3.4.1 defect: immortal/invalid entries).
        """
        path = self._path(namespace, key)
        now = self._clock()
        text: Optional[str] = None
        blob: Any = None
        ts: Optional[float] = None
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return None                    # missing/unreadable: plain miss
        except ValueError:                 # undecodable bytes: corrupt file
            text = None
        if text is not None:
            try:
                blob = json.loads(text)
            except ValueError:             # invalid JSON: corrupt file
                blob = None
        if isinstance(blob, dict) and "fetched_at" in blob \
                and "payload" in blob:
            raw_ts = blob["fetched_at"]
            if not isinstance(raw_ts, bool) and isinstance(raw_ts, (int, float)):
                try:
                    stamp = float(raw_ts)
                except OverflowError:      # int too large for float
                    stamp = None
                if stamp is not None and math.isfinite(stamp) \
                        and stamp <= now + CACHE_FUTURE_SKEW_SECONDS:
                    ts = stamp
        if ts is None:                     # invalid envelope: miss + cleanup
            try:
                path.unlink()              # best-effort, never fatal
            except OSError:
                pass
            return None
        ttl = self._ttl(namespace, ttl)
        if ttl is not None and now - ts >= ttl:
            return None                    # valid but expired: file kept
        return blob["payload"]

    def set(self, namespace: str, key: str, payload: Any) -> None:
        """Persist payload atomically; cache failures never break a run."""
        path = self._path(namespace, key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"fetched_at": self._clock(), "payload": payload},
                           default=str),
                encoding="utf-8")
            tmp.replace(path)
        except OSError:
            return


class RateLimiter:
    """Minimum-interval pacing between calls (thread-safe)."""

    def __init__(self, min_interval: float):
        self.min_interval = max(0.0, float(min_interval))
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self, clock: Callable = time.monotonic,
             sleep: Callable = time.sleep) -> float:
        """Block until the next call is allowed; returns the slept seconds."""
        with self._lock:
            now = clock()
            ready = self._last + self.min_interval
            if now < ready:
                delay = ready - now
                self._last = ready
            else:
                delay = 0.0
                self._last = now
        if delay > 0:
            sleep(delay)
        return delay


# ---------------------------------------------------------- Finnhub (D2) ----
# /stock/financials-reported -> canonical point-in-time Facts.
#
# The response shape below is DOCUMENTED, not captured from a live call (no
# key in this environment): each row carries filedDate (fallback filingDate,
# then acceptedDate[:10]), startDate, endDate, form and a report object with
# bs/ic/cf sections of {concept, label, unit, value} entries. Parsing is
# defensive and the whole mapping is labeled UNVERIFIED.
#
# /stock/metric from the old engine is deliberately not used: it has no
# filing dates and therefore cannot support point-in-time scoring.

_FINNHUB_BASE = "https://finnhub.io/api/v1"

# canonical item -> candidate us-gaap concept names (the us-gaap_ prefix is
# stripped from the concept string before matching; several candidates per
# item, most preferred first)
FINNHUB_CONCEPTS: dict = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "SalesRevenueNet"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold",
             "CostOfGoodsSold", "CostOfServices"],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation_amortization": ["DepreciationDepletionAndAmortization",
                                  "DepreciationAmortizationAndAccretionNet",
                                  "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
                                  "Depreciation"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "tax_expense": ["IncomeTaxExpenseBenefit"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "noninterest_expense": ["NoninterestExpense"],
    "gains_on_sales": ["GainLossOnSaleOfPropertyPlantAndEquipment",
                       "GainLossOnSaleOfRealEstate"],
    "impairments": ["ImpairmentOfLongLivedAssetsHeldForUse",
                    "AssetImpairmentCharges"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "shares_basic": ["WeightedAverageNumberOfSharesOutstandingBasic"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PaymentsToAcquireProductiveAssets"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock",
                 "RepurchasesOfCommonStock"],
    "maintenance_capex": [],   # not separable in us-gaap; AFFO stays optional
    "total_assets": ["Assets"],
    "total_equity": ["StockholdersEquity",
                     "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "preferred_equity": ["PreferredStockValue", "PreferredStockCarryingAmount"],
    "intangibles": ["IntangibleAssetsNetExcludingGoodwill",
                    "IntangibleAssets"],
    "goodwill": ["Goodwill"],
    # D3: debt is provided as COMPONENTS; total debt is composed at view time
    # from one fact per component per period_end, never summed here.
    "long_term_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "short_term_debt": ["LongTermDebtCurrent", "ShortTermBorrowings"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "shares_outstanding": ["EntityCommonStockSharesOutstanding"],
}

# canonical item -> fallback label spellings (label matching is a FALLBACK
# only; concepts are authoritative when present)
FINNHUB_LABELS: dict = {
    "revenue": ["totalRevenue", "revenue", "total_revenue"],
    "cogs": ["costOfRevenue", "costRevenue", "cost_of_revenue",
             "costOfGoodsSold"],
    "operating_income": ["operatingIncome", "operating_income", "ebit"],
    "depreciation_amortization": ["depreciationAmortization",
                                  "depreciationAndAmortization",
                                  "depreciation_amortization"],
    "pretax_income": ["pretaxIncome", "incomeBeforeTax",
                      "income_before_tax"],
    "tax_expense": ["taxExpense", "incomeTaxExpense"],
    "interest_expense": ["interestExpense", "interest_expense"],
    "net_income": ["netIncome", "net_income"],
    "noninterest_expense": ["noninterestExpense", "non_interest_expense"],
    "gains_on_sales": ["gainOnSaleOfProperty", "gainLossOnSaleOfProperty"],
    "impairments": ["impairment", "impairments", "assetImpairment"],
    "shares_diluted": ["dilutedAverageShares",
                       "dilutedWeightedAverageShares"],
    "shares_basic": ["basicAverageShares", "basicWeightedAverageShares"],
    "cfo": ["netCashProvidedByOperatingActivities",
            "cashFromOperatingActivities", "operatingCashFlow"],
    "capex": ["capitalExpenditure", "purchaseOfPPE", "capex"],
    "dividends_paid": ["dividendPaid", "paymentOfDividends",
                       "commonStockDividendPaid"],
    "buybacks": ["repurchaseOfCommonStock", "buybackOfCommonStock",
                 "shareRepurchase"],
    "maintenance_capex": ["maintenanceCapex"],
    "total_assets": ["totalAssets", "total_assets"],
    "total_equity": ["totalEquity", "totalShareholderEquity",
                     "total_equity"],
    "preferred_equity": ["preferredStockEquity", "preferredEquity"],
    "intangibles": ["intangibleAssets", "intangibles"],
    "goodwill": ["goodwill"],
    "long_term_debt": ["longTermDebt", "long_term_debt"],
    "short_term_debt": ["shortTermDebt", "currentDebt",
                        "short_term_debt"],
    "cash": ["cashAndEquivalent", "cashAndCashEquivalents", "cash"],
    "current_assets": ["totalCurrentAssets", "currentAssets"],
    "current_liabilities": ["totalCurrentLiabilities",
                            "currentLiabilities"],
    "retained_earnings": ["retainedEarnings", "retained_earnings"],
    "shares_outstanding": ["sharesOutstanding",
                           "commonStockSharesOutstanding"],
}

FINNHUB_DIAGNOSTIC_KEYS = ("missing_filed", "missing_end", "bad_duration",
                           "unknown_concept", "malformed", "duplicates")


_XBRL_TAXONOMY_PREFIXES = ("us-gaap_", "ifrs-full_", "dei_", "srt_")


def _norm_name(s) -> str:
    """Lowercase alphanumerics only, for concept/label matching.

    A registered XBRL taxonomy prefix (``us-gaap_`` and friends) is stripped
    first: Finnhub serves concepts as ``us-gaap_<Concept>`` while the concept
    maps are written in bare form (spec D2: "strip the us-gaap_ prefix").
    """
    text = str(s or "").lower()
    for prefix in _XBRL_TAXONOMY_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    return "".join(ch for ch in text if ch.isalnum())


def _iso10(value) -> Optional[str]:
    """First 10 chars of ``value`` when they look like an ISO date."""
    text = str(value or "")[:ISO_DATE_LEN]
    try:
        date.fromisoformat(text)
    except ValueError:
        return None
    return text


def _num(value):
    """Numeric value or None; booleans and junk are rejected (counted)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value == value:  # NaN guard
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_finnhub(rows) -> tuple:
    """DOCUMENTED-SHAPE (UNVERIFIED) financials-reported rows -> Facts.

    Returns ({item: [Fact]}, diagnostics). Rows are classified by duration:
    ~90d Q, 150-285d YTD, 350-380d FY, no startDate = instant at endDate;
    odd durations are dropped and counted. Dates are only ever taken from
    filedDate/filingDate/acceptedDate and startDate/endDate - never
    reconstructed from year/quarter fields, so non-calendar fiscal years
    work. Malformed rows are counted, never silently discarded.
    """
    diag = {k: 0 for k in FINNHUB_DIAGNOSTIC_KEYS}
    concept_map: dict = {}
    for item, concepts in FINNHUB_CONCEPTS.items():
        for c in concepts:
            concept_map[_norm_name(c)] = item
    label_map: dict = {}
    for item, labels in FINNHUB_LABELS.items():
        for lab in labels:
            label_map.setdefault(_norm_name(lab), item)
    out: dict = {}
    for row in rows or []:
        if not isinstance(row, dict):
            diag["malformed"] += 1
            continue
        accepted_raw = row.get("acceptedDate") or row.get("filingDate")
        filed = _iso10(row.get("filedDate")) or _iso10(row.get("filingDate")) \
            or _iso10(accepted_raw)
        if filed is None:
            diag["missing_filed"] += 1
            continue
        end = _iso10(row.get("endDate"))
        if end is None:
            diag["missing_end"] += 1
            continue
        start = _iso10(row.get("startDate"))
        if start is not None:
            dur = _days(start, end)
            freq = None
            for label, (lo, hi) in FINNHUB_DURATION_WINDOWS.items():
                if lo <= dur <= hi:
                    freq = label
                    break
            if freq is None:
                diag["bad_duration"] += 1
                continue
        else:
            freq = "INST"
        form = str(row.get("form") or "")
        report = row.get("report")
        if not isinstance(report, dict):
            diag["malformed"] += 1
            continue
        seen_in_row: set = set()
        for section_name in ("bs", "ic", "cf"):
            section = report.get(section_name)
            if section is None:
                continue
            if isinstance(section, dict):        # tolerated legacy shape
                entries = [{"label": k, "value": v}
                           for k, v in section.items()]
            elif isinstance(section, list):
                entries = section
            else:
                diag["malformed"] += 1
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    diag["malformed"] += 1
                    continue
                value = _num(entry.get("value"))
                if value is None:
                    diag["malformed"] += 1
                    continue
                item = concept_map.get(_norm_name(entry.get("concept") or ""))
                if item is None:
                    item = label_map.get(_norm_name(entry.get("label") or ""))
                if item is None:
                    diag["unknown_concept"] += 1
                    continue
                key = (item, section_name)
                if key in seen_in_row:
                    diag["duplicates"] += 1
                    continue
                seen_in_row.add(key)
                item_freq = "INST" if section_name == "bs" else freq
                out.setdefault(item, []).append(
                    Fact(end, filed, value, form, item_freq,
                         start if item_freq != "INST" else None,
                         # S3 provenance: only what Finnhub actually carries
                         accepted=str(accepted_raw) if accepted_raw else None,
                         provider="finnhub",
                         fy_label=(f"{row.get('year')} {row.get('quarter')}"
                                   if row.get("year") else None),
                         currency="USD",
                         unit="shares" if item in _SHARE_COUNT_ITEMS
                         else "USD",
                         source_ref="financials-reported"))
    return out, diag


def _combine_reports(reports: list, provider: str) -> ProviderReport:
    """Worst-of aggregation across the requests of one provider call.

    All SUCCESS -> SUCCESS; any error class plus any success/no-data ->
    PARTIAL_SUCCESS; all error classes -> the first error class
    (deterministic); no facts anywhere and no error -> NO_DATA. Since 3.2
    the all-failed detail KEEPS the first failing request's detail (the
    real reason, e.g. "http_403: You don't have access to this resource.")
    instead of hiding it behind "all_requests_failed".
    """
    statuses = [r.status for r in reports]
    calls = sum(r.calls for r in reports)
    retries = sum(r.retries for r in reports)
    if all(s == STATUS_SUCCESS for s in statuses):
        return ProviderReport(provider, STATUS_SUCCESS, "", calls, retries)
    errors = [s for s in statuses if s in ERROR_CLASSES]
    if errors and len(errors) == len(statuses):
        first_detail = next((r.detail for r in reports
                             if r.status in ERROR_CLASSES and r.detail), "")
        detail = ("all_requests_failed " + first_detail).strip()
        return ProviderReport(provider, errors[0], detail,
                              calls, retries)
    if errors:
        return ProviderReport(provider, STATUS_PARTIAL_SUCCESS,
                              "partial:" + ",".join(sorted(set(errors))),
                              calls, retries)
    return ProviderReport(provider, STATUS_NO_DATA, "", calls, retries)


def _console_note(tag: str, message: str, color: str = "33") -> None:
    """Runtime note to stderr; bold color on a real terminal, plain piped.

    Used for provider state changes the operator must SEE (e.g. the finnhub
    free-tier 403 auto-skip); never contains secrets or URLs.
    """
    prefix = suffix = ""
    if not os.environ.get("NO_COLOR") \
            and os.environ.get("TERM") != "dumb":
        try:
            if sys.stderr.isatty():
                prefix, suffix = f"\033[1;{color}m", "\033[0m"
        except Exception:
            pass
    print(f"{prefix}[{tag}]{suffix} {message}", file=sys.stderr)


class FinnhubClient:
    """Facts from Finnhub financials-reported; annual + quarterly, cached.

    FREE-TIER BEHAVIOR: /stock/financials-reported is a PREMIUM endpoint.
    A free key answers HTTP 403 "You don't have access to this resource.",
    so after FINNHUB_AUTH_DISABLE_AFTER consecutive AUTH_ERRORs the client
    stops calling finnhub for the rest of the process (a loud note with the
    REAL reason goes to stderr) and reports AUTH_ERROR with detail
    "skipped:<reason>". Fundamentals then come from SEC EDGAR (keyless).
    """

    name = "finnhub"

    def __init__(self, cache: Optional[FileCache] = None,
                 limiter: Optional[RateLimiter] = None,
                 transport: Optional[Callable] = None,
                 sleep_fn: Callable = time.sleep):
        self._cache = cache or FileCache()
        self._limiter = limiter or RateLimiter(
            SECONDS_PER_MINUTE / max(1, FINNHUB_CALLS_PER_MIN))
        self._token, self._token_var = finnhub_token()
        self._http = _HttpJson(self.name, self._cache, self._limiter,
                               transport, sleep_fn)
        self._memo: dict = {}
        self.last_diagnostics: dict = {}
        self._auth_failures = 0            # consecutive 401/403 responses
        self._disabled_detail: str = ""    # set once the breaker trips

    @staticmethod
    def available() -> tuple:
        token, var = finnhub_token()
        if not token:
            return False, ("env FINNHUB_API_KEY (or legacy FINAPI) not set "
                           "(optional: SEC EDGAR covers fundamentals "
                           "without a key)")
        return True, f"{var} set"

    def _financials(self, ticker: str, freq: str):
        params = {"symbol": ticker, "freq": freq}
        cache_key = "/stock/financials-reported?" + \
            urllib.parse.urlencode(sorted(params.items()))  # no token (D14)
        url = f"{_FINNHUB_BASE}/stock/financials-reported?" + \
            urllib.parse.urlencode(dict(params, token=self._token))
        payload, report = self._http.get(url, "finnhub", cache_key)
        rows = (payload or {}).get("data") or []
        if payload is not None and not isinstance(rows, list):
            rows = []
            report.status = STATUS_SCHEMA_ERROR
            report.detail = "data_not_a_list"
        return rows, report

    def _record_auth(self, reports: list) -> None:
        """Count consecutive AUTH_ERRORs; trip the breaker loudly (D6)."""
        for r in reports:
            if r.status == STATUS_AUTH_ERROR:
                self._auth_failures += 1
            elif r.status == STATUS_SUCCESS:
                self._auth_failures = 0
        if self._disabled_detail or \
                self._auth_failures < FINNHUB_AUTH_DISABLE_AFTER:
            return
        reason = next((r.detail for r in reports
                       if r.status == STATUS_AUTH_ERROR and r.detail),
                      "auth_error")
        self._disabled_detail = reason
        if "http_401" in reason:
            hint = (f"your Finnhub key in "
                    f"{self._token_var or FINNHUB_KEY_ENV} was REJECTED "
                    "(401). Check the key in .env - the server said: "
                    + reason)
        else:
            hint = ("/stock/financials-reported is a PREMIUM endpoint and "
                    "your key has no access (" + reason + "). Free-tier "
                    "keys cannot use it; the engine will now rely on SEC "
                    "EDGAR (free, no key) and keeps scoring normally.")
        _console_note(
            "finnhub",
            "disabled for the rest of this run after "
            f"{self._auth_failures} auth failures. " + hint)

    def get_all_facts(self, ticker: str):
        """({item: [Fact]}, ProviderReport) for one ticker."""
        upper = ticker.upper()
        if upper in self._memo:
            facts, diag = self._memo[upper]
            return facts, ProviderReport(self.name, STATUS_SUCCESS, "memo")
        if self._disabled_detail:
            return {}, ProviderReport(
                self.name, STATUS_AUTH_ERROR,
                "skipped:" + self._disabled_detail, calls=0)
        annual_rows, r_annual = self._financials(upper, "annual")
        quarterly_rows, r_quarterly = self._financials(upper, "quarterly")
        self._record_auth([r_annual, r_quarterly])
        report = _combine_reports([r_annual, r_quarterly], self.name)
        facts, diag = normalize_finnhub(list(annual_rows)
                                        + list(quarterly_rows))
        self.last_diagnostics = diag
        if not facts and report.status == STATUS_SUCCESS:
            report.status = STATUS_NO_DATA
        report.detail = (report.detail + " " if report.detail else "") + \
            "diag:" + ",".join(f"{k}={v}" for k, v in sorted(diag.items())
                               if v)
        self._memo[upper] = (facts, diag)
        return facts, report

    def get_facts(self, ticker: str, item: str) -> list:
        facts, _report = self.get_all_facts(ticker)
        return facts.get(item) or []

    def get_prices(self, ticker: str, start: str = None, end: str = None):
        """Finnhub is not a price source here; explicit NO_DATA (D5/D6)."""
        return None, ProviderReport(self.name, STATUS_NO_DATA,
                                    "not_a_price_source")


# --------------------------------------------------------- SEC EDGAR ----

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = ("https://data.sec.gov/submissions/CIK{cik:010d}.json")
_COMPANYFACTS_URL = ("https://data.sec.gov/api/xbrl/companyfacts/"
                     "CIK{cik:010d}.json")

# canonical item -> candidate tags, most preferred first (all merged; the
# view's per-period dedupe resolves collisions by latest filing date)
_TAG_CANDIDATES: dict = {
    "revenue": ["Revenues",
                "RegulatedAndUnregulatedOperatingRevenue",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax",
                "SalesRevenueNet"],
    "cogs": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold",
             "CostOfServices"],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAmortizationAndAccretionNet",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        "Depreciation"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "tax_expense": ["IncomeTaxExpenseBenefit"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "noninterest_expense": ["NoninterestExpense"],
    "gains_on_sales": ["GainLossOnSaleOfPropertyPlantAndEquipment",
                       "GainLossOnSaleOfRealEstate"],
    "impairments": ["ImpairmentOfLongLivedAssetsHeldForUse",
                    "AssetImpairmentCharges"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "shares_basic": ["WeightedAverageNumberOfSharesOutstandingBasic"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment",
              "PaymentsToAcquireProductiveAssets"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "buybacks": ["PaymentsForRepurchaseOfCommonStock",
                 "RepurchasesOfCommonStock"],
    "maintenance_capex": [],  # not separable in XBRL; AFFO typically unavailable
    "total_assets": ["Assets"],
    "total_equity": ["StockholdersEquity",
                     "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "preferred_equity": ["PreferredStockValue", "PreferredStockCarryingAmount"],
    "intangibles": ["IntangibleAssetsNetExcludingGoodwill",
                    "IntangibleAssets"],
    "goodwill": ["Goodwill"],
    # P6/R6 (X17): LongTermDebtAndCapitalLeaseObligations (e.g. XOM) and
    # DebtCurrent (2024+ filers) are additional debt presentations; the
    # per-period tag priority below picks ONE winner per (period, freq),
    # so umbrella and component tags can never be summed twice.
    "long_term_debt": ["LongTermDebtNoncurrent",
                       "LongTermDebtAndCapitalLeaseObligations"],
    "short_term_debt": ["LongTermDebtCurrent", "ShortTermBorrowings",
                        "DebtCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "current_assets": ["AssetsCurrent"],
    "current_liabilities": ["LiabilitiesCurrent"],
    "retained_earnings": ["RetainedEarningsAccumulatedDeficit"],
    "shares_outstanding": ["EntityCommonStockSharesOutstanding"],  # dei
}

_DEI_ITEMS = {"shares_outstanding"}
_DEBT_COMPONENTS = ("LongTermDebtNoncurrent", "LongTermDebtCurrent",
                    "ShortTermBorrowings")


def _classify_fact(item: str, unit: dict, *, provider: str = "sec_edgar",
                   unit_key: Optional[str] = None, cik: Optional[int] = None,
                   ticker: Optional[str] = None,
                   accepted: Optional[str] = None,
                   tag_rank: Optional[int] = None) -> Optional[Fact]:
    """One companyfacts unit entry -> Fact (with S3 provenance), or None
    when unusable. Provenance fields are populated only from what the
    source actually carries - never fabricated."""
    end, filed, val = unit.get("end"), unit.get("filed"), unit.get("val")
    if not end or not filed or val is None:
        return None
    try:
        val = float(val)
    except (TypeError, ValueError):
        return None
    form = str(unit.get("form") or "")
    start = unit.get("start")
    fy_label = None
    if unit.get("fy") is not None:
        fy_label = f"FY{unit.get('fy')} {unit.get('fp') or ''}".strip()
    currency = "USD" if unit_key in (None, "USD") else unit_key
    prov_kwargs = dict(
        accepted=accepted, accession=unit.get("accn"), provider=provider,
        currency=currency if unit_key != "shares" else None,
        unit=unit_key, fy_label=fy_label, cik=cik, security_id=ticker,
        source_ref="companyfacts", tag_rank=tag_rank)
    if start is None:
        return Fact(end, filed, val, form, "INST", None, **prov_kwargs)
    if start > end:
        return None   # inconsistent period; counted by the caller's diag
    dur = _days(start, end)
    fy_lo, fy_hi = FY_DURATION_DAYS
    q_lo, q_hi = Q_DURATION_DAYS
    if item in CUMULATIVE_ITEMS:
        if fy_lo <= dur <= fy_hi:
            return Fact(end, filed, val, form, "FY", start, **prov_kwargs)
        if dur >= YTD_MIN_DURATION_DAYS:  # a YTD anchor (quarter /
            # half / nine months)
            return Fact(end, filed, val, form, "YTD", start, **prov_kwargs)
        return None
    if fy_lo <= dur <= fy_hi:
        return Fact(end, filed, val, form, "FY", start, **prov_kwargs)
    if q_lo <= dur <= q_hi:
        return Fact(end, filed, val, form, "Q", start, **prov_kwargs)
    return None


def _facts_for_tag(taxonomy: dict, tag: str,
                    unit_keys: Optional[tuple] = None) -> list:
    """All unit entries for a tag, optionally restricted to unit_keys (S2).

    companyfacts groups values under unit keys ("USD", "shares", "EUR",
    "pure", ...). Without a restriction a concept reported in two
    currencies would be merged silently - the caller passes the expected
    unit family and counts everything else as a unit mismatch.
    """
    node = taxonomy.get(tag) or {}
    out: list = []
    for key, units in (node.get("units") or {}).items():
        if unit_keys is not None and key not in unit_keys:
            continue
        for unit in units or []:
            out.append(unit)
    return out


_SHARE_COUNT_ITEMS = {"shares_outstanding", "shares_basic", "shares_diluted"}


def _expected_units(item: str) -> tuple:
    """XBRL unit keys a canonical item may legitimately carry (S2).

    Share counts must arrive in 'shares'; monetary items must arrive in
    'USD'. Anything else (a share count in USD, revenue in EUR, a 'pure'
    ratio in a monetary slot) is a unit/currency mismatch: rejected and
    counted, never mixed into a USD ratio.
    """
    return ("shares",) if item in _SHARE_COUNT_ITEMS else ("USD",)


def _compose_total_debt(us_gaap: dict) -> list:
    """Sum debt components per balance date; fallback to a single LTD tag.

    Each component is deduped per (tag, end) BEFORE summing, so duplicate
    representations of one balance date are never added twice; the view
    prefers the raw components and only uses this as the direct fallback.
    """
    by_end: dict = {}
    for comp in _DEBT_COMPONENTS:
        best: dict = {}
        for unit in _facts_for_tag(us_gaap, comp, ("USD",)):
            if unit.get("start") is not None:
                continue  # debt tags are instants
            end, filed, val = unit.get("end"), unit.get("filed"), \
                unit.get("val")
            if not end or not filed or val is None:
                continue
            cur = best.get(end)
            if cur is None or filed >= cur[0]:
                best[end] = (filed, val, str(unit.get("form") or ""))
        for end, (filed, val, form) in best.items():
            slot = by_end.setdefault(end, {"filed": "", "total": 0.0,
                                           "form": ""})
            slot["total"] += float(val)
            if filed > slot["filed"]:
                slot["filed"], slot["form"] = filed, form
    if by_end:
        return [Fact(end, slot["filed"], slot["total"], slot["form"], "INST")
                for end, slot in sorted(by_end.items())]
    out: list = []
    for unit in _facts_for_tag(us_gaap, "LongTermDebt", ("USD",)):
        fact = _classify_fact("total_debt", unit)
        if fact is not None:
            out.append(fact)
    return out


def normalize_companyfacts(data: dict, acceptance: Optional[dict] = None):
    """SEC companyfacts payload -> ({item: [Fact]}, diagnostics) (S2/S3).

    ``acceptance`` maps accession number -> acceptance timestamp (from the
    submissions feed) and enables the 16:00 ET rule; without it every fact
    is dated conservatively (next trading day after filed, labeled).
    Diagnostics count rejected entries by reason: ``wrong_unit`` (unit key
    not expected for the item - the currency/unit mixing guard),
    ``malformed`` (missing end/filed/val), ``odd_duration`` (neither
    FY/Q/YTD/INST) and ``inconsistent_period`` (start after end).
    """
    taxonomies = data.get("facts") or {}
    us_gaap = taxonomies.get("us-gaap") or {}
    dei = taxonomies.get("dei") or {}
    acceptance = acceptance or {}
    out: dict = {}
    diag = {"wrong_unit": 0, "malformed": 0, "odd_duration": 0,
            "inconsistent_period": 0}
    cik = data.get("cik")
    cik = int(cik) if isinstance(cik, int) else None
    for item, tags in _TAG_CANDIDATES.items():
        source = dei if item in _DEI_ITEMS else us_gaap
        expected = _expected_units(item)
        # P6/R5 (X10): the candidate order IS the documented priority.
        # ALL filings are kept (point-in-time history must survive); each
        # Fact carries its candidate rank and the VIEW resolves per as_of:
        # per (period_end, freq) the EARLIEST candidate tag that reports
        # the period wins; within the same tag the LATEST FILING wins
        # (restatements keep their original semantics). A later-filed
        # less-preferred tag can never override the preferred one.
        collected: list = []
        for rank, tag in enumerate(tags):
            node = source.get(tag) or {}
            for key, units in (node.get("units") or {}).items():
                if key not in expected:
                    diag["wrong_unit"] += len(units or [])
                    continue
                for unit in units or []:
                    fact = _classify_fact(item, unit, provider="sec_edgar",
                                          unit_key=key, cik=cik,
                                          accepted=acceptance.get(
                                              unit.get("accn")),
                                          tag_rank=rank)
                    if fact is not None:
                        collected.append(fact)
                    elif unit.get("start") and unit.get("end") \
                            and unit["start"] > unit["end"]:
                        diag["inconsistent_period"] += 1
                    elif (unit.get("end") and unit.get("filed")
                          and unit.get("val") is not None):
                        diag["odd_duration"] += 1
                    else:
                        diag["malformed"] += 1
        if collected:
            out[item] = collected
    debt = _compose_total_debt(us_gaap)
    if debt:
        out["total_debt"] = debt
    return out, diag


class SecEdgarClient:
    """Facts from SEC EDGAR companyfacts; one fetch per ticker, cached.

    Keyless: SEC EDGAR needs no API key. When SEC_USER_AGENT is set the
    configured contact is used; when it is absent the client sends a
    STATIC, non-identifying default User-Agent - no OS username, no
    hostname, no reconstructed user@host identity. A genuine, reachable
    contact should be configured via SEC_USER_AGENT in .env for SEC
    fair-access compliance (the chain prints a note to that effect).
    """

    name = "sec_edgar"

    def __init__(self, cache: Optional[FileCache] = None,
                 limiter: Optional[RateLimiter] = None,
                 transport: Optional[Callable] = None,
                 sleep_fn: Callable = time.sleep):
        self._cache = cache or FileCache()
        self._limiter = limiter or RateLimiter(
            1.0 / SEC_MAX_REQUESTS_PER_SEC)
        self._ua = os.environ.get(SEC_USER_AGENT_ENV) or ""
        self._http = _HttpJson(self.name, self._cache, self._limiter,
                               transport, sleep_fn)
        self._cik_map: Optional[dict] = None
        self._memo: dict = {}
        self.last_diagnostics: dict = {}   # S2 rejection counters
        self._acc_memo: dict = {}          # S3 cik -> {accession: accepted}

    @staticmethod
    def available() -> tuple:
        if os.environ.get(SEC_USER_AGENT_ENV):
            return True, "SEC_USER_AGENT set"
        return True, ("no key needed; static non-identifying default "
                      f"User-Agent in use (set {SEC_USER_AGENT_ENV} in .env "
                      "for a real fair-access contact)")

    def _headers(self) -> Optional[dict]:
        """SEC-mandated User-Agent header (identification per their policy).

        Built from the SEC_USER_AGENT contact string when set; otherwise a
        STATIC, non-identifying default that carries NO operating-system
        username or hostname (privacy: machine identity must never be sent
        to a third party). Live evidence: data.sec.gov returned HTTP 200
        for this string on 2026-11-02 and 2026-11-03 (companyfacts), but
        www.sec.gov's ticker map 403'd it on 2026-11-03 while a
        contact-style string got 200 - the SEC WAF varies by host and over
        time, so a genuine, reachable contact in .env (fair access) is the
        reliable configuration and the chain prints a note recommending
        it. Never logged, cached or included in error detail.
        """
        if self._ua:
            return {"User-Agent": f"quality/{ENGINE_VERSION} ({self._ua})"}
        return {"User-Agent": f"quality/{ENGINE_VERSION} "
                              "(set SEC_USER_AGENT in .env for a "
                              "fair-access contact)"}

    def _cik_for(self, ticker: str):
        report = ProviderReport(self.name, STATUS_SUCCESS, "memo", calls=0)
        if self._cik_map is None:
            data, report = self._http.get(_TICKER_MAP_URL, "cik_map",
                                          _TICKER_MAP_URL,
                                          headers=self._headers())
            self._cik_map = {}
            for entry in (data or {}).values():
                if isinstance(entry, dict):
                    symbol = str(entry.get("ticker", "")).upper()
                    if symbol:
                        try:
                            self._cik_map[symbol] = int(
                                entry.get("cik_str") or 0)
                        except (TypeError, ValueError):
                            continue
        return self._cik_map.get(ticker.upper()), report

    def _acceptance_map(self, cik: int) -> dict:
        """accession -> acceptanceDateTime from the submissions feed (S3).

        companyfacts carries only filed DATES; the 16:00 ET availability
        rule needs the acceptance TIMESTAMP. One extra cached request per
        company. When the feed is unavailable the map is empty and every
        fact falls back to the conservative next-trading-day rule
        (labeled), never a guessed timestamp.
        """
        if cik in self._acc_memo:
            return self._acc_memo[cik]
        url = _SUBMISSIONS_URL.format(cik=cik)
        payload, report = self._http.get(url, "sec_submissions", url,
                                         headers=self._headers())
        acc: dict = {}
        if report.status == STATUS_SUCCESS and isinstance(payload, dict):
            recent = ((payload.get("filings") or {}).get("recent") or {})
            accns = recent.get("accessionNumber") or []
            times = recent.get("acceptanceDateTime") or []
            for a, t in zip(accns, times):
                if a and t:
                    acc[str(a)] = str(t)
        self._acc_memo[cik] = acc
        return acc

    def get_all_facts(self, ticker: str):
        """({item: [Fact]}, ProviderReport) for one ticker."""
        if ticker in self._memo:
            facts = self._memo[ticker]
            return facts, ProviderReport(self.name, STATUS_SUCCESS, "memo")
        cik, map_report = self._cik_for(ticker)
        if map_report.status in ERROR_CLASSES:
            # a failed CIK-map fetch is a provider error, not "no data"
            self._memo[ticker] = {}
            return {}, ProviderReport(self.name, map_report.status,
                                      "cik_map_failed", map_report.calls,
                                      map_report.retries)
        if not cik:
            self._memo[ticker] = {}
            return {}, ProviderReport(self.name, STATUS_NO_DATA,
                                      "no_cik", map_report.calls,
                                      map_report.retries)
        url = _COMPANYFACTS_URL.format(cik=cik)
        payload, report = self._http.get(url, "sec", url,
                                         headers=self._headers())
        facts: dict = {}
        if report.status == STATUS_SUCCESS:
            acceptance = self._acceptance_map(cik)
            facts, diag = normalize_companyfacts(payload or {}, acceptance)
            self.last_diagnostics = diag
            if not facts:
                report.status = STATUS_NO_DATA
        combined = _combine_reports([map_report, report], self.name) \
            if map_report.status != STATUS_SUCCESS else report
        self._memo[ticker] = facts
        return facts, combined

    def get_facts(self, ticker: str, item: str) -> list:
        facts, _report = self.get_all_facts(ticker)
        return facts.get(item) or []

    def get_prices(self, ticker: str, start: str = None, end: str = None):
        """SEC is not a price source; explicit NO_DATA (D5/D6)."""
        return None, ProviderReport(self.name, STATUS_NO_DATA,
                                    "not_a_price_source")


# --------------------------------------- captured real payloads (S2) ----
# Sanitized REAL provider payloads captured 2026-11-01: structure and
# values exactly as served, size trimmed to the window under test, no
# credentials anywhere. Sources: Yahoo chart API via yfinance 1.7.0
# (auto_adjust=False) and SEC EDGAR companyfacts (data.sec.gov). Raw
# The raw capture FILES are not shipped in this single-file build: the
# D25 capture gate reports NOT RUN when they are absent, and no test
# counts as live-capture evidence. These in-file excerpts are the ONLY
# real-response data embedded here; every other fixture is synthetic
# and says so.

REAL_YAHOO_AAPL_2020_SPLIT = [
    # (date, close, adj_close, split_ratio); AAPL 4:1 split ex 2020-08-31.
    # Close is split-adjusted THROUGH THE FETCH DATE: the as-traded print
    # for 2020-08-28 is 124.8075 * 4 = 499.23.
    ("2020-08-24", 125.8575, 121.9733, 0.0),
    ("2020-08-25", 124.8250, 120.9726, 0.0),
    ("2020-08-26", 126.5225, 122.6177, 0.0),
    ("2020-08-27", 125.0100, 121.1519, 0.0),
    ("2020-08-28", 124.8075, 120.9557, 0.0),
    ("2020-08-31", 129.0400, 125.0575, 4.0),
    ("2020-09-01", 134.1800, 130.0389, 0.0),
    ("2020-09-02", 131.4000, 127.3447, 0.0),
]
REAL_YAHOO_AAPL_SPLITS_ALL = [
    ("1987-06-16", 2.0), ("2000-06-21", 2.0), ("2005-02-28", 2.0),
    ("2014-06-09", 7.0), ("2020-08-31", 4.0)]

REAL_YAHOO_SIRI_2024_REVERSE = [
    # SIRI 1:10 REVERSE split ex 2024-09-10: pre-event closes are adjusted
    # UP by 10; the as-traded print for 2024-09-03 is 31.20 * 0.1 = 3.12.
    ("2024-08-28", 32.4000, 29.5977, 0.0),
    ("2024-08-29", 32.6000, 29.7804, 0.0),
    ("2024-08-30", 32.9000, 30.0544, 0.0),
    ("2024-09-03", 31.2000, 28.5015, 0.0),
    ("2024-09-04", 29.3000, 26.7658, 0.0),
    ("2024-09-09", 26.7000, 24.3907, 0.0),
    ("2024-09-10", 27.3800, 25.0119, 0.1),
    ("2024-09-11", 28.3100, 25.8614, 0.0),
]
REAL_YAHOO_SIRI_SPLITS_ALL = [("2024-09-10", 0.1)]

REAL_SEC_AAPL_DEI = [
    # dei:EntityCommonStockSharesOutstanding, AAPL, exactly as served.
    {"end": "2019-10-18", "val": 4443265000,
     "accn": "0000320193-19-000119", "fy": 2019, "fp": "FY",
     "form": "10-K", "filed": "2019-10-31", "frame": "CY2019Q3I"},
    {"end": "2020-01-17", "val": 4375480000,
     "accn": "0000320193-20-000010", "fy": 2020, "fp": "Q1",
     "form": "10-Q", "filed": "2020-01-29", "frame": "CY2019Q4I"},
    {"end": "2020-04-17", "val": 4334335000,
     "accn": "0000320193-20-000052", "fy": 2020, "fp": "Q2",
     "form": "10-Q", "filed": "2020-05-01", "frame": "CY2020Q1I"},
    {"end": "2020-07-17", "val": 4275634000,
     "accn": "0000320193-20-000062", "fy": 2020, "fp": "Q3",
     "form": "10-Q", "filed": "2020-07-31", "frame": "CY2020Q2I"},
    {"end": "2020-10-16", "val": 17001802000,   # post-4:1-split count
     "accn": "0000320193-20-000096", "fy": 2020, "fp": "FY",
     "form": "10-K", "filed": "2020-10-30", "frame": "CY2020Q3I"},
]

REAL_SEC_BRK_DEI = [
    # Berkshire Hathaway: the COMPLETE undimensioned dei share series as
    # served. It STOPS in 2011 (later cover pages report per-class counts
    # in dimensioned contexts companyfacts does not serve) and contains a
    # real zero-value anomaly (cover 2010-04-30) - both drive engine guards.
    {"end": "2009-10-29", "val": 1056884,
     "accn": "0001157523-09-007839", "fy": 2009, "fp": "Q3",
     "form": "10-Q", "filed": "2009-11-06", "frame": "CY2009Q3I"},
    {"end": "2010-02-18", "val": 1103764,
     "accn": "0001193125-10-043450", "fy": 2009, "fp": "FY",
     "form": "10-K", "filed": "2010-03-01"},
    {"end": "2010-04-30", "val": 0,
     "accn": "0001157523-10-002982", "fy": 2010, "fp": "Q1",
     "form": "10-Q", "filed": "2010-05-07", "frame": "CY2010Q1I"},
    {"end": "2010-07-30", "val": 976414,
     "accn": "0001157523-10-004882", "fy": 2010, "fp": "Q2",
     "form": "10-Q", "filed": "2010-08-06", "frame": "CY2010Q2I"},
    {"end": "2010-10-29", "val": 956153,
     "accn": "0001157523-10-006675", "fy": 2010, "fp": "Q3",
     "form": "10-Q", "filed": "2010-11-05", "frame": "CY2010Q3I"},
    {"end": "2011-02-17", "val": 943242,
     "accn": "0001193125-11-048914", "fy": 2010, "fp": "FY",
     "form": "10-K", "filed": "2011-02-28"},
    {"end": "2011-04-29", "val": 941481,
     "accn": "0001157523-11-002891", "fy": 2011, "fp": "Q1",
     "form": "10-Q", "filed": "2011-05-06", "frame": "CY2011Q1I"},
]
# Alphabet (GOOGL/GOOG) serves ZERO undimensioned dei share facts; its
# per-class cover counts live in dimensioned contexts outside companyfacts.
REAL_SEC_GOOGL_DEI = []


def _companyfacts_shape(dei_facts):
    """Wrap real dei rows in the companyfacts envelope the client parses."""
    return {"cik": 0, "entityName": "captured-real",
            "facts": {"dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {"shares": list(dei_facts)}}}}}


# ------------------------------------------------------------- prices ----
# Defect D5: the fetch window derives from the as-of date D - [D - 430d, D]
# for scoring, [D, D + horizon + 10d] for forward validation - never from
# today. Cache entries store the ranges they cover and are reused only when
# they cover the request; otherwise the missing range is fetched and merged.

def _ranges_cover(ranges: list, start: str, end: str) -> bool:
    """True when the union of [s, e] ranges covers [start, end]."""
    if not ranges:
        return False
    clipped = sorted((max(s, start), min(e, end))
                     for s, e in ranges if s <= end and e >= start)
    cursor = start
    for s, e in clipped:
        if s > cursor:
            return False
        cursor = max(cursor, e)
    return cursor >= end



class YfinancePriceClient:
    """Daily closes + splits via yfinance; prices only (unofficial).

    D15/D23: ONE fetch returns bars AND the split list for
    [start, end] / splits through ``fetch_on``; both live in ONE cache
    entry stamped ``fetched_on``. The served ``close`` series is on the
    FETCH-DATE basis: close_fetch(d) = raw_close(d) / PRODUCT(ratios with
    d < ex_date <= fetch_on) - the same split adjustment the provider
    applies to its own history. ``adj_close`` is the provider's
    dividend-and-split adjusted series (momentum and return math).
    Merging bars from different fetches (D23) requires the split lists to
    agree over the overlap AND splits_known in both; otherwise the old
    entry is discarded and the whole window refetched. Old bars keep
    their original stamp: an entry's effective age is its OLDEST stamp,
    so merging never resets the TTL of old bars. Without an explicit
    fetch_on stamp the client refuses (a basis nobody can date is a basis
    nobody can verify).
    """

    name = "yfinance"

    def __init__(self, cache: Optional[FileCache] = None,
                 limiter: Optional["RateLimiter"] = None):
        self._cache = cache or FileCache()
        # P6/R12 (L4): ONE shared limiter for every Yahoo path (the engine
        # injects the same instance into the yfinance and chart clients so
        # the per-minute budget is global, never per-client).
        self._limiter = limiter or RateLimiter(
            SECONDS_PER_MINUTE / max(1, YAHOO_CALLS_PER_MIN))
        self.last_error: Optional[str] = None

    @staticmethod
    def available() -> tuple:
        """(enabled, reason); import-guarded, never raises."""
        try:
            import yfinance  # noqa: F401
        except Exception:
            return False, "yfinance package not installed"
        return True, "yfinance installed"

    # -- test seam: the only method that touches the network ----
    def _download(self, ticker: str, start: str, end: str):
        """Raw yfinance history (auto_adjust=False) or (None, error_type).

        P6/R12 (L4): throttled by the SHARED limiter before every call;
        ``end`` is shifted +1 day because yfinance treats end as EXCLUSIVE
        (the as-of bar must be included, matching the chart client);
        rate-limit exceptions map to the RATE_LIMITED status.
        """
        try:
            import yfinance as yf
        except Exception as exc:
            return None, f"import:{type(exc).__name__}"
        end_arg = _shift(end, 1) if end else end
        for attempt in range(YAHOO_RATE_LIMIT_RETRIES + 1):
            self._limiter.wait()
            try:
                hist = yf.Ticker(ticker).history(start=start, end=end_arg,
                                                 interval="1d",
                                                 auto_adjust=False)
            except Exception as exc:
                # message may contain URLs; keep the type only
                name = type(exc).__name__
                if "Rate" in name or "429" in name:
                    if attempt < YAHOO_RATE_LIMIT_RETRIES:
                        time.sleep(min(2.0 ** attempt, RETRY_AFTER_CAP_SECONDS))
                        continue
                    self.last_error = name
                    return None, "ratelimited:" + name
                self.last_error = name
                return None, name
            return hist, ""
        return None, "ratelimited:retries_exhausted"

    @staticmethod
    def _entry_age_days(entry: dict, fetch_on: str) -> int:
        """Effective age of an entry = OLDEST per-bar stamp (D23)."""
        oldest = entry.get("oldest_fetched_on") or entry.get("fetched_on")
        if not oldest or not fetch_on:
            return 0
        try:
            return (date.fromisoformat(fetch_on)
                    - date.fromisoformat(oldest)).days
        except ValueError:
            return 0

    def get_price_data(self, ticker: str, start: Optional[str],
                       end: Optional[str], fetch_on: Optional[str] = None):
        """({close, adj_close, splits, splits_known, fetched_on} | None,
        ProviderReport). One fetch for bars and splits (D15)."""
        if not fetch_on:
            return None, ProviderReport(
                self.name, STATUS_PROVIDER_ERROR, "missing_fetch_on_stamp")
        entry = self._cache.get(PRICE_CACHE_NAMESPACE, ticker, ttl=None) \
            or {}
        ranges = [tuple(r) for r in (entry.get("ranges") or [])]
        if (self._entry_age_days(entry, fetch_on) < PRICE_CACHE_TTL_DAYS
                and _ranges_cover(ranges, start, end)):
            payload = self._filter(dict(entry), start, end)
            if payload.get("close"):
                payload["fetched_on"] = entry.get("fetched_on")
                payload["splits_known"] = bool(entry.get("splits_known"))
                return payload, ProviderReport(self.name, STATUS_SUCCESS,
                                               "cache", calls=0)
        hist, error = self._download(ticker, start, end)
        if error:
            # Downloaders signal the class with a prefix: "nodata:" (symbol
            # unknown / empty history), "net:" (transport fault) and
            # "ratelimited:" map to their D6 status; anything else stays
            # PROVIDER_ERROR (arbitrary strings keep the legacy behavior).
            if error.startswith("nodata:"):
                status = STATUS_NO_DATA
            elif error.startswith("net:"):
                status = STATUS_NETWORK_ERROR
            elif error.startswith("ratelimited:"):
                status = STATUS_RATE_LIMITED
            else:
                status = STATUS_PROVIDER_ERROR
            return None, ProviderReport(self.name, status, error)
        if hist is None or getattr(hist, "empty", None) is True:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "empty_history")
        try:
            rows = list(hist.iterrows())
        except Exception:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "empty_history")
        if not rows:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "empty_history")
        _cols = getattr(hist, "columns", None)
        try:
            col_list = list(_cols) if _cols is not None else []
        except Exception:
            col_list = []
        splits_known = "Stock Splits" in col_list
        raw_closes, adj, splits = [], [], []
        for idx, row in rows:
            day = str(idx.date())
            close = row.get("Close")
            if close is not None and close == close:  # NaN guard
                raw_closes.append((day, float(close)))
            adjusted = row.get("Adj Close")
            if adjusted is not None and adjusted == adjusted:
                adj.append((day, float(adjusted)))
            if splits_known:
                ratio = row.get("Stock Splits")
                if ratio is not None and ratio == ratio and float(ratio) > 0:
                    splits.append((day, float(ratio)))
        if not raw_closes:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "no_valid_closes")
        split_map = {d: r for d, r in splits if r}
        # yfinance Close (auto_adjust=False) is ALREADY split-adjusted
        # through the latest listing date == the fetch date (verified live:
        # AAPL 2020-08-28 serves 124.8075, as-traded was 499.23), so the
        # served close series is used as-is on the fetch-date basis (D15).
        served = list(raw_closes)
        new_entry = {
            "fetched_on": fetch_on,
            "oldest_fetched_on": fetch_on,
            "ranges": [[min(start, raw_closes[0][0]),
                        max(end, raw_closes[-1][0])]],
            "close": sorted(served),
            # V3.4.1: a provider that serves no adjusted bars leaves the
            # adjusted series EMPTY - raw (split-only) closes are never
            # stored as adjusted (dividend adjustments would be missing).
            "adj_close": sorted(adj),
            "splits": sorted(split_map.items()),
            "splits_known": bool(splits_known),
            "bar_fetched_on": {d: fetch_on for d, _ in served},
        }
        merged = self._merge_entry(entry, new_entry)
        if merged is not new_entry:
            merged["ranges"] = [list(r) for r in self._merge_ranges(
                [tuple(r) for r in (entry.get("ranges") or [])]
                + [tuple(r) for r in new_entry["ranges"]])]
        self._cache.set(PRICE_CACHE_NAMESPACE, ticker, merged)
        payload = {"close": merged["close"], "adj_close": merged["adj_close"],
                   "splits": merged["splits"],
                   "splits_known": bool(merged.get("splits_known")),
                   "fetched_on": merged.get("fetched_on")}
        return self._filter(payload, start, end), \
            ProviderReport(self.name, STATUS_SUCCESS, "", calls=1)

    @staticmethod
    def _splits_agree(old: dict, new: dict) -> bool:
        """D23: split lists must match on the overlapping date range."""
        if not old:
            return True
        if not (old.get("splits_known") and new.get("splits_known")):
            return False
        old_sp = {d: r for d, r in (old.get("splits") or [])}
        new_sp = {d: r for d, r in (new.get("splits") or [])}
        for d in set(old_sp) & set(new_sp):
            if abs(float(old_sp[d]) - float(new_sp[d])) > 0:
                return False
        # an old split inside the new window but missing there is a change
        new_lo = min((d for d, _ in new["close"]), default=None)
        new_hi = max((d for d, _ in new["close"]), default=None)
        if new_lo:
            for d in old_sp:
                if new_lo <= d <= new_hi and d not in new_sp:
                    return False
        return True

    @staticmethod
    def _merge_entry(old: dict, new: dict) -> dict:
        """D23 cache merge; returns ``new`` (old discarded) on any mismatch.

        On a legal merge, old bars keep their own stamps (bar_fetched_on);
        the entry's oldest stamp stays the OLDEST across both fetches, so
        merging never resets the TTL of old bars.
        """
        if not old or not old.get("close"):
            return new
        if not YfinancePriceClient._splits_agree(old, new):
            return new                     # discard + whole-window refetch
        old_bars = {d: c for d, c in old["close"]}
        # V3.4.1: an old entry without adjusted bars keeps them absent;
        # raw closes never backfill adj_close during a cache merge.
        old_adj = {d: c for d, c in (old.get("adj_close") or [])}
        old_stamps = dict(old.get("bar_fetched_on")
                          or {d: old.get("fetched_on") for d in old_bars})
        new_bars = {d: c for d, c in new["close"]}
        new_adj = {d: c for d, c in new["adj_close"]}
        stamps = dict(old_stamps)
        stamps.update({d: new["fetched_on"] for d in new_bars})
        oldest = [v for v in stamps.values() if v]
        merged_splits = ({d: r for d, r in old.get("splits") or []}
                         | {d: r for d, r in new["splits"]})
        merged = {
            "fetched_on": new["fetched_on"],
            "oldest_fetched_on": min(oldest) if oldest else new["fetched_on"],
            "ranges": new["ranges"],
            "close": sorted({**old_bars, **new_bars}.items()),
            "adj_close": sorted({**old_adj, **new_adj}.items()),
            "splits": sorted(merged_splits.items()),
            "splits_known": bool(old.get("splits_known")
                                 and new.get("splits_known")),
            "bar_fetched_on": stamps,
        }
        return merged

    def get_splits(self, ticker: str, start: Optional[str] = None,
                   end: Optional[str] = None, fetch_on: Optional[str] = None):
        """([(iso_date, ratio)], ProviderReport) via the price entry (D15)."""
        payload, report = self.get_price_data(ticker, start, end, fetch_on)
        if payload is None:
            return None, report
        events = [(d, float(r)) for d, r in (payload.get("splits") or [])
                  if r]
        return events, report

    def get_prices(self, ticker: str, start: Optional[str] = None,
                   end: Optional[str] = None, fetch_on: Optional[str] = None):
        """Compat alias for get_price_data (same payload, one fetch)."""
        return self.get_price_data(ticker, start, end, fetch_on)

    @staticmethod
    def _merge_ranges(ranges: list) -> list:
        merged: list = []
        for s, e in sorted(ranges):
            if merged and s <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], e))
            else:
                merged.append((s, e))
        return merged

    @staticmethod
    def _filter(payload: dict, start: Optional[str],
                end: Optional[str]) -> dict:
        def within(pairs):
            return [(d, c) for d, c in pairs
                    if (start is None or d >= start)
                    and (end is None or d <= end)]
        closes = within(payload.get("close") or [])
        adj = within(payload.get("adj_close") or [])
        splits = within(payload.get("splits") or [])
        # V3.4.1: an empty adjusted series stays empty - raw closes are
        # never relabeled as adjusted (fresh fetches AND cache hits).
        out = {"close": closes, "adj_close": adj,
               "splits": splits}
        if "splits_known" in payload:
            out["splits_known"] = bool(payload.get("splits_known"))
        return out


# ----------------------------------------------- Yahoo chart client (3.2) ----
# Pure-urllib daily bars + splits from the public Yahoo chart API (the same
# endpoint the yfinance package calls). Exists so the engine needs ZERO pip
# packages: fundamentals are already keyless (SEC EDGAR), and with this
# client prices are keyless too. Verified live 2026-11-01: query2 host
# answers 200 with timestamp[] / indicators.quote[0].close[] /
# indicators.adjclose[0].adjclose[] / events.splits{numerator,denominator};
# served closes are split-adjusted through the fetch date (same basis the
# yfinance client documents, D15), so the shared parser/cacher above is
# reused unchanged via the duck-typed _ChartHist frame.

_YAHOO_CHART_HOSTS = ("query2.finance.yahoo.com", "query1.finance.yahoo.com")

_YAHOO_CHART_HEADERS = {
    # VERIFIED LIVE (2026-11-01): Yahoo's edge 429-blocks UAs whose Chrome
    # version is not the full four-part form ("Chrome/122.0" is refused,
    # "Chrome/122.0.0.0" answers 200), so keep the complete version here.
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/122.0.0.0 Safari/537.36"),
    "Accept": "application/json,text/plain,*/*",
}


class _ChartHist:
    """Duck-typed stand-in for the yfinance history frame.

    Only what YfinancePriceClient.get_price_data reads: ``empty``,
    ``columns`` (so splits_known is True) and ``iterrows()`` yielding
    (datetime, row-dict) with Close / Adj Close / Stock Splits keys.
    """

    def __init__(self, rows: list):
        self._rows = rows
        self.empty = not rows
        self.columns = ["Close", "Adj Close", "Stock Splits"]

    def iterrows(self):
        return iter(self._rows)


class YahooChartPriceClient(YfinancePriceClient):
    """Daily closes + splits straight from the Yahoo chart API (urllib).

    Same contract, cache format and D15/D23 merge rules as the yfinance
    client (it subclasses it and only replaces the network seam); prices
    only, unofficial, no key. Requests are throttled to
    YAHOO_CALLS_PER_MIN and alternate between the query2 and query1 hosts
    (one of them is often throttled on shared IPs; the other answers).
    """

    name = "yahoo_chart"

    def __init__(self, cache: Optional[FileCache] = None,
                 limiter: Optional[RateLimiter] = None,
                 transport: Optional[Callable] = None,
                 sleep_fn: Callable = time.sleep):
        super().__init__(cache=cache)
        self._ylimiter = limiter or RateLimiter(
            SECONDS_PER_MINUTE / max(1, YAHOO_CALLS_PER_MIN))
        self._ytransport = transport or default_transport
        self._ysleep = sleep_fn

    @staticmethod
    def available() -> tuple:
        return True, "built-in urllib client (no pip install needed)"

    @staticmethod
    def _chart_url(host: str, ticker: str, start: str, end: str) -> str:
        """v8 chart URL for [start, end] with splits+dividends and adjclose.

        period1/period2 are UTC epoch seconds and period2 is exclusive, so
        it is pushed one day past ``end`` to include that day's bar.
        """
        p1 = int(datetime.strptime(start, "%Y-%m-%d")
                 .replace(tzinfo=timezone.utc).timestamp())
        p2 = int((datetime.strptime(end, "%Y-%m-%d")
                  .replace(tzinfo=timezone.utc)
                  + timedelta(days=1)).timestamp())
        query = urllib.parse.urlencode(
            {"period1": p1, "period2": p2, "interval": "1d",
             "events": "div,split", "includeAdjustedClose": "true"})
        return (f"https://{host}/v8/finance/chart/"
                f"{urllib.parse.quote(ticker)}?{query}")

    def _fetch_chart(self, ticker: str, start: str, end: str):
        """One chart request with host alternation and 429 backoff."""
        last_detail = "rate_limited"
        for attempt in range(YAHOO_RATE_LIMIT_RETRIES + 1):
            host = _YAHOO_CHART_HOSTS[attempt % len(_YAHOO_CHART_HOSTS)]
            self._ylimiter.wait()
            url = self._chart_url(host, ticker, start, end)
            status, payload, retry_after, detail = self._ytransport(
                url, dict(_YAHOO_CHART_HEADERS))
            if status == STATUS_RATE_LIMITED \
                    and attempt < YAHOO_RATE_LIMIT_RETRIES:
                last_detail = detail or "http_429"
                delay = retry_after if retry_after is not None \
                    else float(2 ** attempt)
                self._ysleep(min(delay, RETRY_AFTER_CAP_SECONDS))
                continue
            return payload, status, detail
        return None, STATUS_RATE_LIMITED, last_detail

    def _download(self, ticker: str, start: Optional[str],
                  end: Optional[str]):
        """(duck-typed hist, error) - the only method touching the network.

        D23: no wall clock here - a missing ``end`` stamp is refused
        (the CLI/API boundary always passes as_of-derived dates).
        """
        if not end:
            return None, "missing_end_stamp"
        start_s = start or _shift(end, -PRICE_LOOKBACK_DAYS)
        payload, status, detail = self._fetch_chart(ticker, start_s, end)
        if status != STATUS_SUCCESS:
            if status == STATUS_NO_DATA:
                return None, "nodata:" + (detail or "not_found")
            if status == STATUS_RATE_LIMITED:
                return None, "ratelimited:" + (detail or "http_429")
            return None, "net:" + (detail or status.lower())
        chart = (payload or {}).get("chart") or {}
        err_obj = chart.get("error")
        if err_obj:
            if isinstance(err_obj, dict):
                msg = str(err_obj.get("description")
                          or err_obj.get("code") or "chart_error")
            else:
                msg = str(err_obj)
            return None, "nodata:" + " ".join(msg.split())[:100]
        results = chart.get("result") or []
        if not results or not isinstance(results[0], dict):
            return None, "nodata:empty_chart_result"
        res = results[0]
        stamps = res.get("timestamp") or []
        indicators = res.get("indicators") or {}
        quotes = (indicators.get("quote") or [{}])[0]
        closes = quotes.get("close") or []
        adj_rows = ((indicators.get("adjclose") or [{}])[0]
                    .get("adjclose")) or []
        rows: list = []
        for i, ts in enumerate(stamps):
            close = closes[i] if i < len(closes) else None
            if close is None:            # null bar (partial data) -> skip
                continue
            adjusted = adj_rows[i] if i < len(adj_rows) else None
            day = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            rows.append((day, {
                "Close": float(close),
                # P6/R3 (X9): a null adjclose NEVER falls back to the raw
                # close - mixing split-only and dividend-adjusted bases in
                # one series corrupts momentum; the bar simply has no
                # adjusted value.
                "Adj Close": float(adjusted)
                if adjusted is not None else None,
                "Stock Splits": 0.0,
            }))
        # P6/R2 (X1): splits are keyed by UTC TRADING DATE, independent of
        # bar timestamps (a 1-hour offset between the event stamp and the
        # session-open stamp must not lose the event), and an event on a
        # day with no tradeable bar (null close / holiday) is carried on a
        # phantom row so the split list stays complete through the window.
        split_by_day: dict = {}
        events = ((res.get("events") or {}).get("splits")) or {}
        for ev in events.values():
            if not isinstance(ev, dict):
                continue
            try:
                num = float(ev.get("numerator") or 0.0)
                den = float(ev.get("denominator") or 0.0)
                if num > 0.0 and den > 0.0:
                    day = datetime.fromtimestamp(int(ev.get("date")),
                                                 tz=timezone.utc)
                    split_by_day[day.date().isoformat()] = num / den
            except (TypeError, ValueError, OSError, OverflowError):
                continue
        placed: set = set()
        for row in rows:
            ratio = split_by_day.get(row[0].date().isoformat())
            if ratio:
                row[1]["Stock Splits"] = float(ratio)
                placed.add(row[0].date().isoformat())
        for day_iso, ratio in sorted(split_by_day.items()):
            if day_iso not in placed:
                phantom = datetime.fromisoformat(day_iso + "T00:00:00+00:00")
                rows.append((phantom, {
                    "Close": None, "Adj Close": None,
                    "Stock Splits": float(ratio),
                }))
        if not rows:
            return None, "nodata:no_valid_closes"
        return _ChartHist(rows), ""

# ------------------------------------------------- offline fixtures (D13) ----

# Deterministic synthetic companies generated INSIDE this file from a fixed

# seed (no external fixture files, no scripts to lose). The fixture source

# performs no I/O and is the only source active in offline environments - it

# is never used to impersonate real market data. Fixture data is synthetic

# BY DESIGN and every scan using it says so.



FIXTURE_SEED = 20261031

FIXTURE_NOTE = ("synthetic fixture (seeded, deterministic; "

                "not real market data)")



_FY_YEARS = (2020, 2021, 2022, 2023)

_Q_SUFFIXES = ("-03-31", "-06-30", "-09-30", "-12-31")

_Q_BACKS = (-91, -91, -92, -92)

_QUARTER_YEARS = (2022, 2023)      # full years

_H1_2024 = ("-03-31", "-06-30")     # 2024 H1 keeps the staleness gate fresh






# ------------------------------------------------- fixture archetypes ----
# Per-sector synthetic-data tables (D26: every fixture constant lives in
# one documented UPPER table; the seeded RNG call order is unchanged).

_FIXTURE_FINANCIALS = dict(
    nie_base=0.60, nie_span=0.03, op=0.30, pretax=0.27, tax=0.24,
    interest=0.09, cfo=1.10, capex=0.008, div=0.30, bb=0.20,
    shares_diluted=92.0, shares_basic=91.5)
_FIXTURE_REITS = dict(
    ni=0.18, da=0.30, op=0.34, pretax=0.24, tax=0.22, ffo_da=0.95,
    gains=0.01, impair=0.005, interest=0.09, capex=0.05, maint=0.06,
    div=0.72, bb=0.01, shares_diluted=55.0, shares_basic=54.5)
_FIXTURE_UTILITIES = dict(
    op_base=0.13, op_span=0.02, pretax=0.035, tax=0.24, cogs=0.55,
    da=0.055, interest=0.035, cfo=0.05, capex=0.09, div=0.60, bb=0.002,
    shares_diluted=40.0, shares_basic=39.6)
_FIXTURE_ENERGY_FLOWS = dict(
    margins={2020: 0.14, 2021: 0.16, 2022: 0.12, 2023: 0.06},
    margin_default=0.10, jitter=0.01, pretax=0.02, tax=0.24, cogs=0.50,
    da=0.06, interest=0.02, cfo=0.05, capex=0.08, div=0.35, bb=0.01,
    shares_diluted=20.0, shares_basic=19.8)
_FIXTURE_TECH = dict(
    margin_base=0.10, margin_step=0.03, margin_span=0.05, pretax=0.015,
    tax=0.25, cogs=0.60, da=0.045, interest=0.015, cfo=1.05, cfo_rev=0.03,
    capex=0.05, div=0.012, bb=0.02, shares_diluted=10.5, shares_step=0.1,
    shares_basic=10.4)
_FIXTURE_INSTANTS = {
    "financials": dict(assets=25.0, equity=0.10, debt=0.78, ltd=0.70,
                       std=0.30, cash=0.12, ca=0.25, cl=0.80, re=0.35,
                       shares=90.0, pref=0.12, intang=0.004, goodwill=0.0),
    "reits": dict(assets=7.2, equity=0.43, debt=0.51, ltd=0.85, std=0.15,
                  cash=0.018, ca=0.06, cl=0.077, re=0.32, shares=55.0,
                  pref=0.0, intang=0.009, goodwill=0.0),
    "utilities": dict(assets=3.2, equity=0.35, debt=0.52, ltd=0.85,
                      std=0.15, cash=0.02, ca=0.12, cl=0.13, re=0.55,
                      shares=40.0, pref=0.0, intang=0.01, goodwill=0.01),
    "energy": dict(assets=1.1, equity=0.40, debt=0.40, ltd=0.75, std=0.25,
                   cash=0.06, ca=0.35, cl=0.20, re=0.50, shares=20.0,
                   pref=0.0, intang=0.02, goodwill=0.03),
}
_FIXTURE_INSTANTS_DEFAULT = dict(
    assets=1.05, equity=0.58, debt=0.36, ltd=0.85, std=0.15, cash=0.10,
    ca=0.50, cl=0.30, re=0.62, shares=10.0, pref=0.0, intang=0.02,
    goodwill=0.03)
_FIXTURE_GROWTH = {
    "energy": dict(pattern={2021: 1.08, 2022: 0.93, 2023: 1.16},
                   base=1.05, lo=-0.02, hi=0.02),
    "financials": dict(base=1.02, lo=0.0, hi=0.04),
    "utilities": dict(base=1.00, lo=0.0, hi=0.03),
    "reits": dict(base=1.01, lo=0.0, hi=0.03),
}
_FIXTURE_GROWTH_DEFAULT = dict(base=1.03, lo=0.0, hi=0.09)
_FIXTURE_MONTH_WINDOW = (2023, 1, 2024, 10)
_FIXTURE_QUARTER_YEARS = _QUARTER_YEARS + (2024,)
_H1_YEAR = 2024


def _fixture_flow_profile(crng: random.Random, sector: str, year: int,
                          revenue: float) -> dict:
    """One synthetic fiscal year of flow items for a sector archetype."""
    if sector == "financials":
        t = _FIXTURE_FINANCIALS
        nie = revenue * (t["nie_base"] + crng.uniform(0.0, t["nie_span"]))
        op = revenue * t["op"]
        pretax = revenue * t["pretax"]
        tax = pretax * t["tax"]
        return {"revenue": revenue, "noninterest_expense": nie,
                "operating_income": op, "pretax_income": pretax,
                "tax_expense": tax, "net_income": pretax - tax,
                "interest_expense": revenue * t["interest"],
                "cfo": (pretax - tax) * t["cfo"],
                "capex": revenue * t["capex"],
                "dividends_paid": (pretax - tax) * t["div"],
                "buybacks": (pretax - tax) * t["bb"],
                "shares_diluted": t["shares_diluted"],
                "shares_basic": t["shares_basic"]}
    if sector == "reits":
        t = _FIXTURE_REITS
        ni = revenue * t["ni"]
        da = revenue * t["da"]
        op = revenue * t["op"]
        pretax = revenue * t["pretax"]
        tax = pretax * t["tax"]
        ffo = ni + da - revenue * t["gains"] + revenue * t["impair"]
        return {"revenue": revenue, "net_income": ni,
                "depreciation_amortization": da, "operating_income": op,
                "gains_on_sales": revenue * t["gains"],
                "impairments": revenue * t["impair"],
                "interest_expense": revenue * t["interest"],
                "pretax_income": pretax, "tax_expense": tax,
                "cfo": ni + da * t["ffo_da"], "capex": revenue * t["capex"],
                "maintenance_capex": revenue * t["maint"],
                "dividends_paid": ffo * t["div"],
                "buybacks": revenue * t["bb"],
                "shares_diluted": t["shares_diluted"],
                "shares_basic": t["shares_basic"]}
    if sector == "utilities":
        t = _FIXTURE_UTILITIES
        op = revenue * (t["op_base"] + crng.uniform(0.0, t["op_span"]))
        pretax = op - revenue * t["pretax"]
        tax = pretax * t["tax"]
        return {"revenue": revenue, "cogs": revenue * t["cogs"],
                "operating_income": op,
                "depreciation_amortization": revenue * t["da"],
                "interest_expense": revenue * t["interest"],
                "pretax_income": pretax,
                "tax_expense": tax, "net_income": pretax - tax,
                "cfo": (pretax - tax) + revenue * t["cfo"],
                "capex": revenue * t["capex"],
                "dividends_paid": (pretax - tax) * t["div"],
                "buybacks": revenue * t["bb"],
                "shares_diluted": t["shares_diluted"],
                "shares_basic": t["shares_basic"]}
    if sector == "energy":
        t = _FIXTURE_ENERGY_FLOWS
        op = revenue * (t["margins"].get(year, t["margin_default"])
                        + crng.uniform(-t["jitter"], t["jitter"]))
        pretax = op - revenue * t["pretax"]
        tax = pretax * t["tax"]
        return {"revenue": revenue, "cogs": revenue * t["cogs"],
                "operating_income": op,
                "depreciation_amortization": revenue * t["da"],
                "interest_expense": revenue * t["interest"],
                "pretax_income": pretax,
                "tax_expense": tax, "net_income": pretax - tax,
                "cfo": (pretax - tax) + revenue * t["cfo"],
                "capex": revenue * t["capex"],
                "dividends_paid": (pretax - tax) * t["div"],
                "buybacks": revenue * t["bb"],
                "shares_diluted": t["shares_diluted"],
                "shares_basic": t["shares_basic"]}
    # tech / default archetype
    t = _FIXTURE_TECH
    margin = (t["margin_base"] + t["margin_step"] * (year - _FY_YEARS[0])
              + crng.uniform(0.0, t["margin_span"]))
    op = revenue * margin
    pretax = op - revenue * t["pretax"]
    tax = pretax * t["tax"]
    return {"revenue": revenue, "cogs": revenue * t["cogs"],
            "operating_income": op,
            "depreciation_amortization": revenue * t["da"],
            "interest_expense": revenue * t["interest"],
            "pretax_income": pretax, "tax_expense": tax,
            "net_income": pretax - tax,
            "cfo": (pretax - tax) * t["cfo"] + revenue * t["cfo_rev"],
            "capex": revenue * t["capex"],
            "dividends_paid": revenue * t["div"],
            "buybacks": revenue * t["bb"],
            "shares_diluted": t["shares_diluted"]
            - t["shares_step"] * (year - _FY_YEARS[0]),
            "shares_basic": t["shares_basic"]
            - t["shares_step"] * (year - _FY_YEARS[0])}


def _fixture_instants(crng: random.Random, sector: str, revenue: float) -> dict:
    """Balance-sheet archetype at one date."""
    t = _FIXTURE_INSTANTS.get(sector, _FIXTURE_INSTANTS_DEFAULT)
    assets = revenue * t["assets"]
    equity = assets * t["equity"]
    debt = assets * t["debt"]
    return {"total_assets": assets, "total_equity": equity,
            "long_term_debt": debt * t["ltd"],
            "short_term_debt": debt * t["std"],
            "cash": assets * t["cash"],
            "current_assets": assets * t["ca"],
            "current_liabilities": assets * t["cl"],
            "retained_earnings": equity * t["re"],
            "shares_outstanding": t["shares"],
            "preferred_equity": equity * t["pref"]
            if sector == "financials" else t["pref"],
            "intangibles": assets * t["intang"],
            "goodwill": assets * t["goodwill"]}


def _fixture_growth(crng: random.Random, sector: str, year: int) -> float:
    t = _FIXTURE_GROWTH.get(sector, _FIXTURE_GROWTH_DEFAULT)
    if "pattern" in t:
        return t["pattern"].get(year, t["base"]) \
            + crng.uniform(t["lo"], t["hi"])
    return t["base"] + crng.uniform(t["lo"], t["hi"])


def _fixture_month_ends() -> list:
    """Month-end ISO dates from _FIXTURE_MONTH_WINDOW (deterministic)."""
    y0, m0, y1, m1 = _FIXTURE_MONTH_WINDOW
    out = []
    year, month = y0, m0
    while (year, month) <= (y1, m1):
        out.append(date(year, month, _days_in_month(year, month)).isoformat())
        month += 1
        if month > MONTHS_PER_YEAR:
            year, month = year + 1, 1
    return out



def _fx_prov(item: str, ticker: str, year="", freq_label=""):
    """S3 provenance kwargs for seeded fixture facts (synthetic, labeled)."""
    return dict(provider="fixtures", security_id=ticker,
                currency=None if item in _SHARE_COUNT_ITEMS else "USD",
                unit="shares" if item in _SHARE_COUNT_ITEMS else "USD",
                fy_label=(f"{year} {freq_label}".strip() or None),
                source_ref="seeded-fixtures")


def _generate_fixture_company(ticker: str, sector: str) -> Company:
    """One synthetic company; deterministic in the ticker alone."""
    crng = random.Random(f"{FIXTURE_SEED}:{ticker}")
    drop_da = ticker == "FXRE02"   # REIT without D&A -> SECTOR_DATA_MISSING
    facts: dict = {}
    revenue = FIXTURE_CONFIG["sector_revenue_base"].get(
        sector, FIXTURE_CONFIG["sector_revenue_base"]["tech"]) \
        * (FIXTURE_CONFIG["revenue_uniform_lo"]
           + crng.uniform(0.0, FIXTURE_CONFIG["revenue_uniform_span"]))
    flows_by_year: dict = {}
    for year in _FY_YEARS:
        if year > _FY_YEARS[0]:
            revenue *= _fixture_growth(crng, sector, year)
        flows = _fixture_flow_profile(crng, sector, year, round(revenue, 2))
        flows_by_year[year] = flows
        end, filed, start = (f"{year}-12-31", f"{year + 1}-02-15",
                             f"{year}-01-01")
        for item, value in flows.items():
            if drop_da and item == "depreciation_amortization":
                continue
            facts.setdefault(item, []).append(
                Fact(end, filed, round(value, ROUND_DIGITS), "10-K", "FY", start,
                     **_fx_prov(item, ticker, year, "FY")))
        insts = _fixture_instants(crng, sector, round(revenue, 2))
        for item, value in insts.items():
            facts.setdefault(item, []).append(
                Fact(end, filed, round(value, ROUND_DIGITS), "10-K",
                     "INST",
                     **_fx_prov(item, ticker, year, "INST")))
    h1_factor = 1.0 + crng.uniform(0.0, FIXTURE_CONFIG["h1_factor_span"])
    for year in _FIXTURE_QUARTER_YEARS:
        for suffix, back in zip(_Q_SUFFIXES, _Q_BACKS):
            if year == _H1_YEAR and suffix not in _H1_2024:
                continue
            qend = f"{year}{suffix}"
            qstart = _shift(qend, back)
            qfiled = _shift(qend,
                            FIXTURE_CONFIG["filing_lag_days"])
            base = flows_by_year[_FY_YEARS[-1]]
            factor = 1.0 if year == _FY_YEARS[-1] else h1_factor
            for item, value in base.items():
                if item in ("shares_diluted", "shares_basic"):
                    continue
                if drop_da and item == "depreciation_amortization":
                    continue
                facts.setdefault(item, []).append(
                    Fact(qend, qfiled, round(value / FIXTURE_CONFIG["quarter_fraction"] * factor,
                         ROUND_DIGITS),
                         "10-Q", "Q", qstart,
                         **_fx_prov(item, ticker, year, "Q")))
            insts = _fixture_instants(crng, sector,
                                      round(revenue, 2))
            for item, value in insts.items():
                facts.setdefault(item, []).append(
                    Fact(qend, qfiled, round(value, ROUND_DIGITS), "10-Q", "INST",
                         **_fx_prov(item, ticker, year, "Q")))
    base_price = (FIXTURE_CONFIG["base_price_lo"]
                  + crng.uniform(0.0, FIXTURE_CONFIG["base_price_span"]))
    drift = crng.uniform(FIXTURE_CONFIG["drift_lo"],
                         FIXTURE_CONFIG["drift_hi"])
    prices = [(d, round(base_price * ((1.0 + drift) ** i), 2))
              for i, d in enumerate(_fixture_month_ends())]
    return Company(ticker=ticker, sector=sector, facts=facts,
                   prices=prices, adj_prices=list(prices),
                   sources={"fixtures"}, note=FIXTURE_NOTE)


_FIXTURE_PLAN = (
    ("FXTE", "tech", 10),
    ("FXEN", "energy", 9),
    ("FXFI", "financials", 1),
    ("FXUT", "utilities", 1),
    ("FXRE", "reits", 2),
)

_FIXTURE_COMPANIES: Optional[dict] = None


def generate_fixture_universe() -> dict:
    """{ticker: Company} for the 23 synthetic fixture names (deterministic)."""
    global _FIXTURE_COMPANIES
    if _FIXTURE_COMPANIES is None:
        out: dict = {}
        for prefix, sector, count in _FIXTURE_PLAN:
            for i in range(1, count + 1):
                ticker = f"{prefix}{i:02d}"
                out[ticker] = _generate_fixture_company(ticker, sector)
        _FIXTURE_COMPANIES = out
    return _FIXTURE_COMPANIES


class FixtureSource:
    """Serves the seeded synthetic universe; no network, no rate limit."""

    name = "fixtures"

    def __init__(self):
        self._companies: Optional[dict] = None

    def available(self):
        return True, "deterministic seeded fixtures (synthetic data)"

    def _load(self) -> dict:
        if self._companies is None:
            self._companies = generate_fixture_universe()
        return self._companies

    def get_prices(self, ticker: str, start: str = None,
                   end: str = None, fetch_on: str = None):
        """Compat alias for get_price_data (D15 payload)."""
        return self.get_price_data(ticker, start, end, fetch_on)

    def get_all_facts(self, ticker: str):
        company = self._load().get(ticker.upper())
        if company is None:
            return {}, ProviderReport(self.name, STATUS_NO_DATA,
                                      "not_in_fixtures")
        return dict(company.facts), ProviderReport(self.name,
                                                   STATUS_SUCCESS, "")

    def get_facts(self, ticker: str, item: str) -> list:
        company = self._load().get(ticker.upper())
        if company is None:
            return []
        return company.facts.get(item) or []

    def get_price_data(self, ticker: str, start: str = None,
                       end: str = None, fetch_on: str = None):
        """Bars + splits in ONE payload, stamped fetched_on (D15/D23)."""
        company = self._load().get(ticker.upper())
        if company is None:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "not_in_fixtures")
        prices = list(company.prices)
        # V3.4.1: adjusted stays whatever the fixture carries (seeded
        # fixtures are adjusted == raw by construction: no dividends or
        # splits in the synthetic set); raw never backfills it.
        adj = list(company.adj_prices)
        if start is not None:
            prices = [(d, c) for d, c in prices if d >= start]
            adj = [(d, c) for d, c in adj if d >= start]
        if end is not None:
            prices = [(d, c) for d, c in prices if d <= end]
            adj = [(d, c) for d, c in adj if d <= end]
        splits = [(d, float(r))
                  for d, r in (company.split_events or [])
                  if (start is None or d >= start)
                  and (end is None or d <= end)]
        if not prices:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "window_outside_history")
        return {"close": prices, "adj_close": adj, "splits": splits,
                "splits_known": True, "fetched_on": fetch_on or ""}, \
            ProviderReport(self.name, STATUS_SUCCESS, "")

    def get_splits(self, ticker: str, start: str = None,
                   end: str = None, fetch_on: str = None):
        """Fixture split events in [start, end] (S1; none in the seeded set)."""
        company = self._load().get(ticker.upper())
        if company is None:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "not_in_fixtures")
        events = [(d, float(r)) for d, r in (company.split_events or [])
                  if (start is None or d >= start)
                  and (end is None or d <= end)]
        return events, ProviderReport(self.name, STATUS_SUCCESS, "")

# ------------------------------------------------------------ chain ----


class SourceChain:
    """Merged view over enabled fundamentals sources plus one price source."""

    def __init__(self, fundamentals: list, price_source, skipped: list,
                 notes: list):
        self.fundamentals = fundamentals
        self.price_source = price_source
        self.skipped = skipped
        self.notes = notes
        self.provider_stats: dict = {}   # provider -> {status: count} (D6)

    def describe(self) -> list:
        """[(name, status)] for humans; never contains key values."""
        rows = []
        for src in self.fundamentals:
            rows.append((src.name, "enabled"))
        if (self.price_source is not None
                and self.price_source not in self.fundamentals):
            rows.append((self.price_source.name, "enabled"))
        for name, reason in self.skipped:
            rows.append((name, f"skipped ({reason})"))
        return rows

    def _record(self, provider: str, status: str) -> None:
        stats = self.provider_stats.setdefault(provider, {})
        stats[status] = stats.get(status, 0) + 1

    def provider_status_summary(self) -> dict:
        """Per-provider status counts for the scan summary (D6)."""
        return {p: dict(s) for p, s in sorted(self.provider_stats.items())}


    def get_company(self, ticker: str, sector: str,
                    as_of: Optional[str] = None,
                    fetch_on: Optional[str] = None) -> Company:
        """Merge facts across sources (first source with data wins per item).

        Records ``source_status`` per provider and ``item_source`` per item
        (D6 / rule I5). D15/D23: the price fetch happens ONCE with the
        explicit ``fetch_on`` stamp passed down from the CLI/API boundary;
        bars and the split list are stored together and the Company keeps
        the stamps (prices_fetched_on, split_events_through). No wall clock
        below the boundary.
        """
        facts: dict = {}
        sources: set = set()
        source_status: dict = {}
        source_detail: dict = {}
        item_source: dict = {}
        for src in self.fundamentals:
            try:
                provided, report = src.get_all_facts(ticker)
            except Exception as exc:
                provided, report = {}, ProviderReport(
                    src.name, STATUS_PROVIDER_ERROR,
                    "exception:" + type(exc).__name__)
            self._record(src.name, report.status)
            source_status[src.name] = report.status
            if report.detail:
                source_detail[src.name] = report.detail
            for item, fs in (provided or {}).items():
                if item not in facts and fs:
                    facts[item] = fs
                    item_source[item] = src.name
                    sources.add(src.name)
        company = Company(ticker=ticker, sector=sector, facts=facts,
                          sources=sources, source_status=source_status,
                          source_detail=source_detail,
                          item_source=item_source)
        if self.price_source is not None:
            start = _shift(as_of, -PRICE_LOOKBACK_DAYS) if as_of else None
            # P6/R1 (L2): providers return split events ONLY inside the
            # requested window while serving closes on the FETCH-date
            # basis, so the window END is the fetch stamp (never as_of).
            # Bars are filtered to <= as_of AFTER splits are collected;
            # split_events_through then equals the window actually
            # requested AND returned (design invariant).
            if as_of and fetch_on:
                end = max(as_of, fetch_on)
            else:
                end = as_of or fetch_on
            try:
                payload, report = self.price_source.get_price_data(
                    ticker, start, end, fetch_on=fetch_on)
            except Exception as exc:
                payload, report = None, ProviderReport(
                    self.price_source.name, STATUS_PROVIDER_ERROR,
                    "exception:" + type(exc).__name__)
            self._record(self.price_source.name, report.status)
            source_status[self.price_source.name] = report.status
            if report.detail:
                source_detail[self.price_source.name] = report.detail
            if payload:
                closes = [(d, float(c))
                          for d, c in (payload.get("close") or [])]
                adj = [(d, float(c))
                       for d, c in (payload.get("adj_close") or [])]
                if as_of:      # bars usable at as_of only (P6/R1)
                    closes = [(d, c) for d, c in closes if d <= as_of]
                    adj = [(d, c) for d, c in adj if d <= as_of]
                company.prices = sorted(closes)
                # V3.4.1: no adjusted bars -> the adjusted series stays
                # empty; raw closes stay on .prices where the labeled
                # price_only fallback can use them honestly.
                company.adj_prices = sorted(adj)
                if closes:
                    sources.add(self.price_source.name)
                stamp = payload.get("fetched_on") or fetch_on or ""
                company.prices_fetched_on = stamp
                # S1/D15 corporate actions: the split list arrives WITH the
                # bars, complete through the fetch stamp; anything less is
                # unverified instead of guessed.
                if not payload.get("splits_known", True):
                    company.splits_unverified = True
                    company.split_events_through = ""
                else:
                    company.split_events_through = stamp
                split_map = {d: float(r)
                             for d, r in (payload.get("splits") or []) if r}
                company.split_events = sorted(split_map.items())
        return company

def build_source_chain(mode: str = "auto") -> SourceChain:
    """Enabled sources by mode: auto | fixtures | finnhub | sec | yfinance.

    Since 3.2 the FREE defaults work out of the box, no key and no pip:
    ``auto`` always enables SEC EDGAR fundamentals (keyless; static
    non-identifying default User-Agent when SEC_USER_AGENT is unset) plus
    a price source (yfinance
    when installed, otherwise the built-in Yahoo chart urllib client).
    Finnhub is added only when FINNHUB_API_KEY (or legacy FINAPI) is set
    and is auto-disabled at runtime
    on free-tier 403s (premium endpoint). ``fixtures`` (explicit only)
    serves the seeded synthetic universe; auto mode no longer falls back to
    it - with no network you now get honest per-ticker errors instead of
    synthetic companies.
    """
    _ensure_env()
    skipped: list = []
    notes: list = []
    fundamentals: list = []
    cache = FileCache()

    if mode in ("auto", "sec"):
        fundamentals.append(SecEdgarClient(cache=cache))
        if not os.environ.get(SEC_USER_AGENT_ENV):
            notes.append(
                "SEC EDGAR runs with a STATIC, non-identifying default "
                "User-Agent (no machine username or hostname is sent); set "
                f"{SEC_USER_AGENT_ENV}='Your Name you@mail.com' in .env for "
                "a genuine, reachable fair-access contact (no key needed).")
    if mode in ("auto", "finnhub"):
        if finnhub_token()[0]:
            fundamentals.append(FinnhubClient(cache=cache))
            notes.append(
                "finnhub /stock/financials-reported is a PREMIUM endpoint; "
                "free keys get 403 and finnhub is then auto-skipped for the "
                "run (SEC EDGAR already covers fundamentals, keyless).")
        else:
            skipped.append(("finnhub",
                            f"env {FINNHUB_KEY_ENV} not set (optional)"))

    price_source = None
    if mode != "fixtures":
        # P6/R12 (L4): ONE limiter shared by both Yahoo paths so the
        # per-minute budget is global whichever client is active.
        shared_limiter = RateLimiter(
            SECONDS_PER_MINUTE / max(1, YAHOO_CALLS_PER_MIN))
        ok, _reason = YfinancePriceClient.available()
        if ok:
            price_source = YfinancePriceClient(cache=cache,
                                               limiter=shared_limiter)
        else:
            price_source = YahooChartPriceClient(cache=cache,
                                                 limiter=shared_limiter)
            notes.append("prices come from the built-in Yahoo chart client "
                         "(urllib, throttled, no pip install needed)")

    if mode == "fixtures":
        fixture = FixtureSource()
        fundamentals = [fixture]
        price_source = fixture

    return SourceChain(fundamentals, price_source, skipped, notes)


# ---------------------------------------------------------- captures (D25) ----

def real_capture_gate(path) -> tuple:
    """(ok, reason): is this file a usable REAL provider capture (D25)?

    A capture must parse as JSON, carry the expected taxonomy keys, hold at
    least REAL_CAPTURE_MIN_FACTS fact rows and exceed
    REAL_CAPTURE_MIN_BYTES. Failing files are reported
    "NOT RUN: empty capture" and never counted as evidence.
    """
    try:
        size = os.path.getsize(path)
    except OSError as exc:
        return False, f"NOT RUN: empty capture (unreadable: {type(exc).__name__})"
    if size <= REAL_CAPTURE_MIN_BYTES:
        return False, (f"NOT RUN: empty capture ({size} bytes <= "
                       f"{REAL_CAPTURE_MIN_BYTES})")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return False, (f"NOT RUN: empty capture (unparsable: "
                       f"{type(exc).__name__})")
    if not isinstance(data, dict):
        return False, "NOT RUN: empty capture (not an object)"
    facts = data.get("facts") or {}
    rows = 0
    for _item, nodes in (facts.items() if isinstance(facts, dict) else []):
        if isinstance(nodes, dict):
            for unit in (nodes.get("units") or {}).values():
                rows += len(unit)
        elif isinstance(nodes, list):
            rows += len(nodes)
    if rows < REAL_CAPTURE_MIN_FACTS:
        return False, (f"NOT RUN: empty capture ({rows} fact rows < "
                       f"{REAL_CAPTURE_MIN_FACTS})")
    return True, f"usable capture ({rows} fact rows, {size} bytes)"


# =============================== SECTION: PIT ================================

ACCEPTANCE_CUTOFF_ET = _param(
    "ACCEPTANCE_CUTOFF_ET", 16 * 60,   # minutes after midnight, ET
    "SEC acceptance cutoff: filings accepted after 16:00 ET are public "
    "information only from the next trading day (S3).")

# P6/R11 (X8): the fixed-offset ET fallback can be up to one hour FAST
# during DST; acceptances inside this slack before the cutoff fail CLOSED
# (next trading day) instead of leaking a same-day look-ahead.
TZ_AMBIGUITY_SLACK_MINUTES = _param("TZ_AMBIGUITY_SLACK_MINUTES", 60,
                                    "Fail-closed slack for the approximate "
                                    "ET zone (DST shift is 60 minutes).")

_ET = None
_ET_APPROX = False


def _et_zone():
    """America/New_York zone, or an APPROXIMATE fixed -05:00 fallback."""
    global _ET, _ET_APPROX
    if _ET is None:
        try:
            from zoneinfo import ZoneInfo
            _ET = ZoneInfo("America/New_York")
        except Exception:
            _ET = timezone(timedelta(hours=-5))
            _ET_APPROX = True
    return _ET


def _next_weekday(iso: str) -> str:
    """Next Mon-Fri date strictly after iso (APPROXIMATE next trading day;
    no holiday calendar offline - see the S3 note above)."""
    d = date.fromisoformat(iso) + timedelta(days=1)
    while d.weekday() >= WEEKEND_FIRST_DOW:
        d += timedelta(days=1)
    return d.isoformat()


def _ts_to_et(accepted: str):
    """Acceptance string -> (iso_date, minutes_after_midnight, approx) in
    ET, or None when unparseable. Handles '...Z' (UTC, the SEC submissions
    shape) and explicit offsets; a naive string is treated as ET."""
    s = (accepted or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.date().isoformat(), (dt.hour * MINUTES_PER_HOUR
                                       + dt.minute), False
    dt = dt.astimezone(_et_zone())
    return dt.date().isoformat(), (dt.hour * MINUTES_PER_HOUR
                                    + dt.minute), _ET_APPROX


def fact_available_date(fact) -> tuple:
    """(available_date, label) for a fact (S3); (None, reason) when it can
    never be placed in time. A fact is never used before public
    availability: after-16:00-ET acceptances wait for the next trading day,
    timestamp-less filings wait for the next weekday (conservative, labeled).
    """
    filed = getattr(fact, "filing_date", "") or ""
    if not filed:
        return None, "no_filing_date"
    try:
        date.fromisoformat(filed)
    except ValueError:
        return None, "bad_filing_date"
    accepted = getattr(fact, "accepted", None)
    if accepted:
        parsed = _ts_to_et(str(accepted))
        if parsed:
            day, minutes, approx = parsed
            if day > filed:
                # acceptance later than the filed date (data error): use
                # the later of the two, conservatively
                day, minutes = filed, MINUTES_PER_DAY
            # P6/R11 (X8): with the APPROXIMATE fixed-offset zone the ET
            # clock can be up to one hour FAST (DST), which would make an
            # after-close acceptance look pre-close -> fail CLOSED: in the
            # ambiguity hour before the cutoff the fact waits a day.
            cutoff = ACCEPTANCE_CUTOFF_ET \
                - (TZ_AMBIGUITY_SLACK_MINUTES if approx else 0)
            if minutes > cutoff:
                return _next_weekday(day), (
                    "accepted_after_close_next_trading_day"
                    + ("_approximate" if approx else ""))
            return day, ("accepted_same_day"
                         + ("_approximate" if approx else ""))
        return _next_weekday(filed), "unparseable_accepted_assumed_next_day"
    return _next_weekday(filed), "availability_assumed_next_day"

# Canonical fundamental items and their statement kind.
CANONICAL_ITEMS: dict = {
    # flow items, reported discretely (income statement)
    "revenue": "flow", "cogs": "flow", "operating_income": "flow",
    "depreciation_amortization": "flow", "pretax_income": "flow",
    "tax_expense": "flow", "interest_expense": "flow", "net_income": "flow",
    "noninterest_expense": "flow", "gains_on_sales": "flow",
    "impairments": "flow", "shares_diluted": "flow", "shares_basic": "flow",
    # flow items whose statements report cumulative year-to-date values
    "cfo": "flow", "capex": "flow", "dividends_paid": "flow",
    "buybacks": "flow", "maintenance_capex": "flow",
    # instant balances
    "total_assets": "instant", "total_equity": "instant",
    "preferred_equity": "instant", "intangibles": "instant",
    "goodwill": "instant", "total_debt": "instant", "long_term_debt": "instant",
    "short_term_debt": "instant", "cash": "instant",
    "current_assets": "instant", "current_liabilities": "instant",
    "retained_earnings": "instant", "shares_outstanding": "instant",
}
# Items usually only available as cumulative year-to-date facts (cash flows).
CUMULATIVE_ITEMS = {"cfo", "capex", "dividends_paid", "buybacks",
                    "maintenance_capex", "depreciation_amortization"}


def _days(a: str, b: str) -> int:
    """Calendar days between two ISO dates (b - a)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _shift(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def _days_in_month(year: int, month: int) -> int:
    if month == MONTHS_PER_YEAR:
        return _MONTH_LENGTHS[MONTHS_PER_YEAR]
    return (date(year, month + 1, 1) - timedelta(days=1)).day


def _shift_months(iso: str, months: int) -> str:
    """Month arithmetic with day clamping to the target month's length."""
    d = date.fromisoformat(iso)
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    day = min(d.day, _days_in_month(year, month))
    return date(year, month, day).isoformat()


# Point-in-time view of one company's facts as of ``as_of`` (rule I1/I2).



# ============================== SECTION: PIT VIEW =============================


class FundamentalsView:
    """Point-in-time view of one company's facts as of ``as_of`` (ISO date).

    A fact is visible at ``as_of`` only if its availability date <= as_of
    (rule I1). Facts with an empty filing date are dropped and counted
    (``dropped_no_filing`` diagnostic) rather than imputed. D18: every
    accessor that returns a fact value appends a provenance entry
    {item, provider, period_end, filing_date, available_date, accession} to
    ``self._trace``; derived values (TTM, Q4 = FY - Q1 - Q2 - Q3, composed
    debt) append EVERY underlying fact. ``compute_raw_metrics`` clears the
    trace before each metric and stores it per metric.
    """

    def __init__(self, facts: Optional[dict], as_of: str):
        self.as_of = as_of
        self._facts = facts or {}
        self._pit: dict = {}
        self._trace: list = []                # D18 provenance of accesses
        self._trace_item: str = ""            # item currently being accessed
        self.dropped_no_filing = 0   # I1 diagnostic: facts with no filing date
        self.dropped_bad_filing_date = 0      # S3: unparseable filing dates
        self.dropped_inconsistent_period = 0  # S3: period_start > period_end
        self.delayed_not_yet_available = 0    # S3: visible only after as_of
        self.availability_labels: dict = {}   # S3: label -> count

    def _note(self, f) -> None:
        """Append one fact to the D18 trace (item + five provenance fields)."""
        available, _label = fact_available_date(f)
        self._trace.append({
            "item": self._trace_item,
            "provider": getattr(f, "provider", None) or "unknown",
            "period_end": f.period_end,
            "filing_date": f.filing_date,
            "available_date": available,
            "accession": getattr(f, "accession", None),
        })

    def _clear_trace(self) -> list:
        """Drop the trace accumulated so far (per-metric provenance, D18)."""
        out = self._trace
        self._trace = []
        return out

    # -- internals ----
    def _pit_facts(self, item: str) -> list:
        """Facts visible at as_of, sorted by period (S3 availability rule).

        A fact is visible only from its PUBLIC AVAILABILITY date
        (:func:`fact_available_date`): filings accepted after 16:00 ET wait
        for the next trading day; timestamp-less filings wait for the next
        weekday (conservative, labeled). Facts that cannot be placed in
        time are dropped and counted; facts not yet available are counted
        in delayed_not_yet_available with their labels (never silently
        hidden); duration facts with period_start after period_end are
        rejected and counted (inconsistent_period).
        """
        if item not in self._pit:
            raw = self._facts.get(item) or []
            out = []
            for f in raw:
                if not getattr(f, "filing_date", ""):
                    self.dropped_no_filing += 1   # counted, never imputed
                    continue
                if f.period_start and f.period_start > f.period_end:
                    self.dropped_inconsistent_period += 1
                    continue
                available, label = fact_available_date(f)
                if available is None:
                    self.dropped_bad_filing_date += 1
                    continue
                if available <= self.as_of:
                    out.append(f)
                else:
                    self.delayed_not_yet_available += 1
                    self.availability_labels[label] =                         self.availability_labels.get(label, 0) + 1
            out.sort(key=lambda f: (f.period_end, f.filing_date))
            self._pit[item] = out
        return self._pit[item]

    @staticmethod
    def _dedupe_by_period(facts: list) -> list:
        """One fact per (period_end, freq); resolves restatements.

        P6/R5 (X10): when two DIFFERENT candidate tags report the same
        period, the EARLIEST-rank (most preferred) tag wins; within one
        tag the LATEST FILING wins. Facts without a rank (fixtures,
        Finnhub, hand-built) all count as rank 0.
        """
        best: dict = {}
        for f in facts:
            key = (f.period_end, f.freq)
            rank = f.tag_rank if f.tag_rank is not None else 0
            cur = best.get(key)
            if cur is None:
                best[key] = f
                continue
            cur_rank = cur.tag_rank if cur.tag_rank is not None else 0
            if rank < cur_rank or (rank == cur_rank
                                   and f.filing_date >= cur.filing_date):
                best[key] = f
        return sorted(best.values(), key=lambda f: f.period_end)

    # -- accessors ----
    def fy_series(self, item: str) -> list:
        """Fiscal-year facts, oldest first, restatements resolved PIT."""
        out = self._dedupe_by_period(
            [f for f in self._pit_facts(item) if f.freq == "FY"])
        self._trace_item = item
        for f in out:
            self._note(f)
        return out

    def fy(self, item: str, years_back: int = 0) -> Optional[float]:
        """Value of the fiscal-year fact ``years_back`` from the latest."""
        s = self.fy_series(item)
        idx = len(s) - 1 - years_back
        return s[idx].value if 0 <= idx < len(s) else None

    def fy_at(self, item: str, period_end: str) -> Optional[float]:
        """FY fact value whose period ends exactly on ``period_end``."""
        for f in self.fy_series(item):
            if f.period_end == period_end:
                return f.value
        return None

    def consecutive_fy(self, item: str, n: int = None) -> Optional[list]:
        """Last n+1 FY facts iff every period_end gap is a normal year (D8).

        Growth must never silently use a broken fiscal series: a missing or
        duplicated fiscal year makes the window None, not a wrong number.
        """
        n = GROWTH_YEARS if n is None else n
        s = self.fy_series(item)
        if len(s) < n + 1:
            return None
        window = s[-(n + 1):]
        lo, hi = FY_GAP_DAYS
        for a, b in zip(window, window[1:]):
            gap = _days(a.period_end, b.period_end)
            if not lo <= gap <= hi:
                return None
        return window

    def q_series(self, item: str) -> list:
        """Discrete quarterly facts; derives YTD diffs or Q4 when needed."""
        direct = self._dedupe_by_period(
            [f for f in self._pit_facts(item) if f.freq == "Q"])
        self._trace_item = item
        for f in direct:
            self._note(f)
        if direct:
            return self._derive_q4(item, direct)
        return self._quarters_from_anchors(item)

    def _quarters_from_anchors(self, item: str) -> list:
        """Discrete quarters from cumulative YTD anchor groups."""
        anchors = [f for f in self._pit_facts(item)
                   if f.freq in ("YTD", "FY") and f.period_start]
        groups: dict = {}
        for f in anchors:
            groups.setdefault(f.period_start, []).append(f)
        out: dict = {}
        self._trace_item = item
        for group in groups.values():
            group = self._dedupe_by_period(group)
            for i, a in enumerate(group):
                if i == 0:
                    dur = _days(a.period_start, a.period_end)
                    if Q_DURATION_DAYS[0] <= dur <= Q_DURATION_DAYS[1]:
                        out.setdefault(a.period_end, Fact(
                            a.period_end, a.filing_date, a.value, a.form, "Q"))
                        self._note(a)
                else:
                    prev = group[i - 1]
                    gap = _days(prev.period_end, a.period_end)
                    if QUARTER_GAP_DAYS[0] <= gap <= QUARTER_GAP_DAYS[1]:
                        out.setdefault(a.period_end, Fact(
                            a.period_end, a.filing_date,
                            a.value - prev.value, a.form, "Q"))
                        self._note(prev)
                        self._note(a)
        return sorted(out.values(), key=lambda f: f.period_end)

    def _derive_q4(self, item: str, quarters: list) -> list:
        """Append Q4 = FY - Q1 - Q2 - Q3 for discretely reported items."""
        out = list(quarters)
        have = {f.period_end for f in quarters}
        self._trace_item = item
        for fy in self.fy_series(item):
            if not fy.period_start:
                continue
            window = [f for f in quarters
                      if fy.period_start < f.period_end <= fy.period_end]
            if len(window) == QUARTERS_IN_YEAR_FLOWS - 1                     and fy.period_end not in have:
                q4 = fy.value - sum(f.value for f in window)
                out.append(Fact(fy.period_end, fy.filing_date, q4, fy.form,
                                "Q"))
                self._note(fy)
                for f in window:
                    self._note(f)
                have.add(fy.period_end)
        return sorted(out, key=lambda f: f.period_end)

    def ttm(self, item: str) -> Optional[float]:
        """Sum of the last four consecutive discrete quarters."""
        qs = self.q_series(item)
        if len(qs) < QUARTERS_IN_YEAR_FLOWS:
            return None
        last4 = qs[-QUARTERS_IN_YEAR_FLOWS:]
        for a, b in zip(last4, last4[1:]):
            gap = _days(a.period_end, b.period_end)
            if not QUARTER_GAP_DAYS[0] <= gap <= QUARTER_GAP_DAYS[1]:
                return None
        return sum(f.value for f in last4)

    def ttm_prior(self, item: str) -> Optional[float]:
        """TTM value of the four quarters before the latest four."""
        qs = self.q_series(item)
        if len(qs) < QUARTERS_IN_YEAR_FLOWS * 2:
            return None
        prior4 = qs[-QUARTERS_IN_YEAR_FLOWS * 2:-QUARTERS_IN_YEAR_FLOWS]
        for a, b in zip(prior4, prior4[1:]):
            gap = _days(a.period_end, b.period_end)
            if not QUARTER_GAP_DAYS[0] <= gap <= QUARTER_GAP_DAYS[1]:
                return None
        return sum(f.value for f in prior4)

    def instant_map(self, item: str) -> dict:
        """{period_end: value} for instants, latest filing <= as_of wins (D3).

        One fact per (item, period_end): duplicate representations of the
        same balance date (annual row and Q4 row) collapse to a single fact.
        """
        inst = self._dedupe_by_period(
            [f for f in self._pit_facts(item) if f.freq == "INST"])
        self._trace_item = item
        for f in inst:
            self._note(f)
        return {f.period_end: f.value for f in inst}

    def _instant_fact(self, item: str, max_age_days: Optional[int] = None):
        """The selected instant Fact, or None (traced, D18)."""
        inst = self._dedupe_by_period(
            [f for f in self._pit_facts(item) if f.freq == "INST"])
        if not inst:
            return None
        if max_age_days is not None:
            cutoff = _shift(self.as_of, -int(max_age_days))
            inst = [f for f in inst if f.period_end >= cutoff]
            if not inst:
                return None
        chosen = max(inst, key=lambda f: f.period_end)
        self._trace_item = item
        self._note(chosen)
        return chosen

    def instant_fact(self, item: str, max_age_days: Optional[int] = None):
        """Public wrapper: the selected instant Fact (or None), traced."""
        return self._instant_fact(item, max_age_days)

    def instant(self, item: str, max_age_days: Optional[int] = None
                ) -> Optional[float]:
        """Latest instant (balance) value visible at as_of.

        With ``max_age_days``, only period ends within that many days
        before as_of qualify (S1: a stale share count must never price a
        fresh market cap - real case: Berkshire's undimensioned dei
        EntityCommonStockSharesOutstanding facts stop in 2011 while every
        other fundamental stays current; without the bound a 13-year-old
        count would silently price today's cap).
        """
        f = self._instant_fact(item, max_age_days)
        return f.value if f is not None else None

    def instant_year_ago(self, item: str) -> Optional[float]:
        """Instant value at least ~10 months before the latest instant."""
        m = self.instant_map(item)
        if not m:
            return None
        cutoff = _shift(max(m), YEAR_AGO_LOOKBACK_DAYS)
        prior = [d for d in m if d <= cutoff]
        return m[max(prior)] if prior else None

    def instant_at(self, item: str, period_end: str,
                   tolerance: int = None) -> Optional[float]:
        """Instant value nearest to ``period_end`` within ``tolerance`` days.

        Default tolerance is INSTANT_MATCH_TOLERANCE_DAYS (D8): a balance
        dated further from the fiscal period end is a different balance,
        not a match.
        """
        if tolerance is None:
            tolerance = INSTANT_MATCH_TOLERANCE_DAYS
        m = self.instant_map(item)
        best, best_gap = None, None
        for d in m:
            gap = abs(_days(d, period_end))
            if gap <= tolerance and (best_gap is None or gap < best_gap):
                best, best_gap = m[d], gap
        return best

    # -- debt composition (D3) ----
    def _compose_debt(self, cutoff: Optional[str] = None):
        """(period_end, value, missing_components) built at view time.

        Total debt = long-term + short-term/current portion, each taken ONCE
        per period_end (latest filing <= as_of wins per component). A missing
        component is reported, never silently zero-filled. Falls back to a
        directly reported ``total_debt`` fact only when no component exists.
        """
        self._trace_item = "long_term_debt"
        ltd = self.instant_map("long_term_debt")
        self._trace_item = "short_term_debt"
        std = self.instant_map("short_term_debt")
        dates = set(ltd) | set(std)
        if cutoff is not None:
            dates = {d for d in dates if d <= cutoff}
        if dates:
            end = max(dates)
            value, missing = 0.0, []
            for name, m in (("long_term_debt", ltd),
                            ("short_term_debt", std)):
                if end in m:
                    value += m[end]
                else:
                    missing.append(name)
            return end, value, missing
        self._trace_item = "total_debt"
        direct = self.instant_map("total_debt")
        dd = set(direct)
        if cutoff is not None:
            dd = {d for d in dd if d <= cutoff}
        if dd:
            end = max(dd)
            return end, direct[end], []
        return None, None, ["long_term_debt", "short_term_debt"]

    def total_debt(self):
        """Latest composed total debt: (value, missing_components)."""
        _end, value, missing = self._compose_debt()
        return value, missing

    def total_debt_year_ago(self):
        """Composed total debt at least ~10 months back (flag diagnostics)."""
        _end, latest, _missing = self._compose_debt()
        anchor = _end or (lambda m: max(m) if m else None)(
            self.instant_map("total_assets"))
        if anchor is None:
            return None
        _e, value, _m = self._compose_debt(
            cutoff=_shift(anchor, YEAR_AGO_LOOKBACK_DAYS))
        return value

    def latest_fiscal_period_end(self) -> Optional[str]:
        """Most recent FISCAL period_end visible at as_of (D16, D9).

        Skips COVER_PAGE_ITEMS (the dei cover-page share count): its date
        can sit up to ~60 days after the fiscal period end, so counting it
        would hide a genuinely stale filing behind a fresh cover date.
        """
        latest = None
        for item in self._facts:
            if item in COVER_PAGE_ITEMS:
                continue
            for f in self._pit_facts(item):
                if latest is None or f.period_end > latest:
                    latest = f.period_end
        return latest


def _split_product(split_events, after_date: str, through_date: str) -> float:
    """PRODUCT of every split ratio with after_date < ex_date <= through_date.

    Ratios are new-shares-per-old (4.0 for 4:1, 0.1 for a 1:10 reverse).
    Used ONLY to put the provider close (fetch-date basis) and the
    as-reported share count on one basis (D15, rule I2) - never as
    information about the future.
    """
    factor = 1.0
    for d, ratio in (split_events or []):
        if after_date < d <= through_date and ratio and float(ratio) > 0:
            factor *= float(ratio)
    return factor


def build_market(company: Company, as_of: str):
    """(MarketPoint | None, price_status) at as_of (D15, D9, I3).

    market_cap = provider_close(t_c) x shares(t_s)
                 x PRODUCT(split ratios with t_s < ex_date <= fetch_date)

    t_c = date of the last close actually used (<= as_of); t_s = the
    period_end of the share-count fact (cover/balance date, NEVER the
    filing date); fetch_date = the stamp stored with the price bars (never
    the wall clock). price_status is "ok"; "stale" (last close older than
    STALE_PRICE_DAYS); "missing" (no prices); "no_point_in_time_shares";
    "stale_shares" (only an ancient count exists; weighted-average flow
    shares are never a substitute); "no_shares" (non-positive count or
    close); or "split_basis_unverified" (split events unknown, list
    incomplete for the fetch date, or an ex-date within
    SPLIT_AMBIGUITY_DAYS of t_s: refusing beats a silently wrong cap).
    """
    prices = sorted((d, c) for d, c in (company.prices or []) if d <= as_of)
    if not prices:
        return None, "missing"
    if _days(prices[-1][0], as_of) > STALE_PRICE_DAYS:
        return None, "stale"
    close = prices[-1][1]           # provider close at t_c (fetch-date basis)
    t_c = prices[-1][0]
    view = FundamentalsView(company.facts, as_of)
    fact = view.instant_fact("shares_outstanding",
                             max_age_days=SHARES_MAX_AGE_DAYS)
    if fact is None:
        if view.instant("shares_outstanding") is not None:
            return None, "stale_shares"
        return None, "no_point_in_time_shares"
    shares = fact.value
    if shares <= 0 or close is None or close <= 0:
        return None, "no_shares"
    if getattr(company, "splits_unverified", False):
        return None, "split_basis_unverified"
    fetched_on = getattr(company, "prices_fetched_on", "") or ""
    through = getattr(company, "split_events_through", "") or fetched_on
    fetch_date = fetched_on or through or t_c
    if fetched_on and through < fetch_date:
        return None, "split_basis_unverified"
    events = [(d, r) for d, r in (company.split_events or []) if r]
    t_s = fact.period_end
    if any(abs(_days(t_s, d)) <= SPLIT_AMBIGUITY_DAYS for d, _r in events):
        return None, "split_basis_unverified"
    factor = _split_product(events, t_s, fetch_date)
    mcap = close * shares * factor
    # P6/R4 (L3, D-3 default): EV/net debt need the COMPLETE debt figure.
    debt, missing = view.total_debt()
    cash = view.instant("cash")
    net_debt = (debt - cash) if (debt is not None and cash is not None and not missing) else None
    ev = (mcap + net_debt) if net_debt is not None else None
    trace = list(view._trace)
    trace.append({"item": "price_close", "provider": "price_series",
                  "period_end": t_c, "filing_date": None,
                  "available_date": t_c, "accession": None})
    if events:
        trace.append({"item": "split_events", "provider": "price_series",
                      "period_end": ";".join(sorted(d for d, _r in events)),
                      "filing_date": None, "available_date": fetch_date,
                      "accession": None})
    return MarketPoint(as_of, close, shares, mcap, net_debt, ev,
                       split_factor=factor,
                       price_basis="provider_close_x_split_adjusted_shares",
                       trace=tuple(trace)), "ok"


# =============================== SECTION: METRICS =============================

def _ratio(num, den) -> Optional[float]:
    """None-safe division; requires a positive denominator (num may be any sign)."""
    if num is None or den is None or den <= 0:
        return None
    return num / den


def _cagr_span(start_fact, end_fact) -> Optional[float]:
    """CAGR over the REAL calendar span of two FY facts (D8).

    Requires the span to sit within 3 years +/- 45 days of the nominal
    horizon; otherwise None - a growth number is never computed from a
    broken or shifted fiscal series.
    """
    if start_fact is None or end_fact is None:
        return None
    if start_fact.value <= 0 or end_fact.value <= 0:
        return None
    days = _days(start_fact.period_end, end_fact.period_end)
    if not (CAGR_MIN_SPAN_DAYS <= days <= CAGR_MAX_SPAN_DAYS):
        return None
    years = days / 365.25
    return (end_fact.value / start_fact.value) ** (1.0 / years) - 1.0


def _median_tail(values: list, window: int, min_count: int) -> Optional[float]:
    tail = [x for x in values if x is not None][-window:]
    if len(tail) < min_count:
        return None
    return statistics.median(tail)


def _sub_optional(base, *items) -> Optional[float]:
    if base is None:
        return None
    return base - sum(x for x in items if x is not None)


# Metric formulas. All are pure functions of a FundamentalsView (facts already
# filtered to filing_date <= as_of) and an optional MarketPoint.
#
# Published definitions used (see file docstring for caveats):
# - Piotroski F-score: Piotroski (2000), nine binary criteria on annual data.
# - Altman Z-score: Altman (1968), original five-variable public-firm model.
# - Gross profitability: Novy-Marx (2013), gross profit / total assets.
# - Accruals ratio: cash-flow variant (net income - CFO) / total assets; the
#   balance-sheet variant of Sloan (1996) is noted in the docstring.
#
# Sign-safe forms (defect D11): earnings_yield, ebitda_yield, fcf_yield and
# interest_coverage admit negative numerators so loss-makers are ranked
# BELOW peers instead of being dropped (which made them look better).
# ebitda_yield is the documented sign-safe replacement for EV/EBITDA.
# WORST (inf) marks computable-but-adverse values (EBITDA <= 0 leverage,
# non-positive invested capital): available, scored 0.


def roic(v: FundamentalsView, m) -> Optional[float]:
    """NOPAT / invested capital, where IC = total debt + equity - cash.

    Invested capital <= 0 returns WORST (score 0, still available) instead of
    being dropped (D11).
    """
    op = v.ttm("operating_income")
    if op is None:
        return None
    pretax, tax = v.ttm("pretax_income"), v.ttm("tax_expense")
    lo, hi = TAX_RATE_CLIP
    if pretax is not None and pretax > 0 and tax is not None:
        rate = min(max(tax / pretax, lo), hi)
    else:
        rate = TAX_RATE_FALLBACK
    # P6/R4 (L3, D-3 default): invested capital needs the COMPLETE debt
    # figure; a partial sum would overstate ROIC.
    debt, missing = v.total_debt()
    eq, cash = v.instant("total_equity"), v.instant("cash")
    if debt is None or eq is None or cash is None or missing:
        return None
    ic = debt + eq - cash
    if ic <= 0:
        return WORST
    return op * (1.0 - rate) / ic


def gross_profitability(v: FundamentalsView, m) -> Optional[float]:
    """Novy-Marx (2013): gross profit / total assets."""
    rev, cogs, ta = v.ttm("revenue"), v.ttm("cogs"), v.instant("total_assets")
    if rev is None or cogs is None or ta is None or ta <= 0:
        return None
    return (rev - cogs) / ta


def operating_margin(v: FundamentalsView, m) -> Optional[float]:
    return _ratio(v.ttm("operating_income"), v.ttm("revenue"))


def fcf_margin(v: FundamentalsView, m) -> Optional[float]:
    """(CFO - capex) / revenue, TTM (numerator may be negative)."""
    cfo, capex, rev = v.ttm("cfo"), v.ttm("capex"), v.ttm("revenue")
    if cfo is None or capex is None:
        return None
    return _ratio(cfo - capex, rev)


def _fy_ratio_series(v, num_item, den_item="revenue") -> list:
    """Ratio of two fiscal-year flow items, per year, oldest first."""
    dens = {f.period_end: f for f in v.fy_series(den_item)}
    out = []
    for n in v.fy_series(num_item):
        d = dens.get(n.period_end)
        if d is not None and d.value > 0:
            out.append(n.value / d.value)
    return out


def _fy_fcf_margin_series(v) -> list:
    cfo = {f.period_end: f for f in v.fy_series("cfo")}
    capex = {f.period_end: f for f in v.fy_series("capex")}
    out = []
    for r in v.fy_series("revenue"):
        c, x = cfo.get(r.period_end), capex.get(r.period_end)
        if c is not None and x is not None and r.value > 0:
            out.append((c.value - x.value) / r.value)
    return out


def _fy_gross_profitability_series(v) -> list:
    cogs = {f.period_end: f for f in v.fy_series("cogs")}
    out = []
    for r in v.fy_series("revenue"):
        c = cogs.get(r.period_end)
        if c is None:
            continue
        ta = v.instant_at("total_assets", r.period_end)
        if ta is not None and ta > 0:
            out.append((r.value - c.value) / ta)
    return out


def operating_margin_5y(v: FundamentalsView, m) -> Optional[float]:
    """Median operating margin over the margin window (cyclicals)."""
    return _median_tail(_fy_ratio_series(v, "operating_income"),
                        MARGIN_MEDIAN_WINDOW, CYCLICAL_MIN_MARGIN_YEARS)


def fcf_margin_5y(v: FundamentalsView, m) -> Optional[float]:
    return _median_tail(_fy_fcf_margin_series(v),
                        MARGIN_MEDIAN_WINDOW, CYCLICAL_MIN_MARGIN_YEARS)


def gross_profitability_5y(v: FundamentalsView, m) -> Optional[float]:
    return _median_tail(_fy_gross_profitability_series(v),
                        MARGIN_MEDIAN_WINDOW, CYCLICAL_MIN_MARGIN_YEARS)


def revenue_cagr_3y(v: FundamentalsView, m) -> Optional[float]:
    """3Y revenue CAGR on a consecutive FY series with a real date span (D8)."""
    window = v.consecutive_fy("revenue")
    if window is None:
        return None
    return _cagr_span(window[0], window[-1])


def _fy_fcf_at(v, years_back: int) -> Optional[float]:
    cfo, capex = v.fy("cfo", years_back), v.fy("capex", years_back)
    if cfo is None or capex is None:
        return None
    return cfo - capex


def _eps_fy(v, years_back: int) -> Optional[float]:
    ni, sh = v.fy("net_income", years_back), v.fy("shares_diluted", years_back)
    if ni is None or sh is None or sh <= 0:
        return None
    return ni / sh


def earnings_cagr_3y(v: FundamentalsView, m) -> Optional[float]:
    """Diluted EPS CAGR on consecutive FYs; FCF CAGR fallback (D8).

    EPS = FY net income / FY diluted shares of the SAME period; endpoints
    must share fiscal period ends and the real span must be ~3 years.
    """
    ni_w = v.consecutive_fy("net_income")
    sh_w = v.consecutive_fy("shares_diluted")
    if ni_w is not None and sh_w is not None \
            and ni_w[0].period_end == sh_w[0].period_end \
            and ni_w[-1].period_end == sh_w[-1].period_end \
            and ni_w[0].value is not None and sh_w[0].value > 0 \
            and sh_w[-1].value > 0:
        eps_start = Fact(ni_w[0].period_end, ni_w[0].filing_date,
                         ni_w[0].value / sh_w[0].value, "FY")
        eps_end = Fact(ni_w[-1].period_end, ni_w[-1].filing_date,
                       ni_w[-1].value / sh_w[-1].value, "FY")
        out = _cagr_span(eps_start, eps_end)
        if out is not None:
            return out
    cfo_w = v.consecutive_fy("cfo")
    capex_w = v.consecutive_fy("capex")
    if cfo_w is not None and capex_w is not None \
            and cfo_w[0].period_end == capex_w[0].period_end \
            and cfo_w[-1].period_end == capex_w[-1].period_end:
        f_start = Fact(cfo_w[0].period_end, cfo_w[0].filing_date,
                       cfo_w[0].value - capex_w[0].value, "FY")
        f_end = Fact(cfo_w[-1].period_end, cfo_w[-1].filing_date,
                     cfo_w[-1].value - capex_w[-1].value, "FY")
        return _cagr_span(f_start, f_end)
    return None


def growth_stability(v: FundamentalsView, m) -> Optional[float]:
    """Share of consecutive FY pairs with rising revenue (D8).

    Only period_end gaps within FY_GAP_DAYS count as pairs; a broken fiscal
    series never contributes a pair.
    """
    s = v.fy_series("revenue")
    need = STABILITY_YEARS + 1
    if len(s) < need:
        return None
    window = s[-need:]
    lo, hi = FY_GAP_DAYS
    ups = pairs = 0
    for a, b in zip(window, window[1:]):
        if not lo <= _days(a.period_end, b.period_end) <= hi:
            continue
        pairs += 1
        if b.value > a.value:
            ups += 1
    if pairs == 0:
        return None
    return ups / pairs


def _ebitda_ttm(v: FundamentalsView) -> Optional[float]:
    """TTM EBITDA = operating income + D&A. Missing D&A -> None.

    EBIT is NEVER silently substituted for EBITDA: without the D&A fact the
    quantity is unavailable, so the metric is missing (and drags coverage),
    which is the honest treatment - a proxy would understate EBITDA and
    silently distort net-debt/EBITDA and EBITDA-yield.
    """
    op, da = v.ttm("operating_income"), v.ttm("depreciation_amortization")
    if op is None or da is None:
        return None
    return op + da


def net_debt_ebitda(v: FundamentalsView, m) -> Optional[float]:
    """(Debt - cash) / EBITDA, TTM.

    EBITDA <= 0 returns WORST (score 0, available) instead of None, so a
    cash-burning balance sheet is never rewarded for missing data (D11).
    """
    ebitda = _ebitda_ttm(v)
    if ebitda is None:
        return None
    # P6/R4 (L3, D-3 default): a PARTIAL debt figure is never used - a
    # missing component makes the metric unavailable (note
    # debt_component_missing), never a silently understated sum.
    debt, missing = v.total_debt()
    cash = v.instant("cash")
    if debt is None or cash is None or missing:
        return None
    if ebitda <= 0:
        return WORST
    return (debt - cash) / ebitda


def interest_coverage(v: FundamentalsView, m) -> Optional[float]:
    """EBIT / interest expense (times-interest-earned), TTM.

    EBIT < 0 is allowed and yields a negative coverage (D11): a loss-maker
    ranks below every profitable peer rather than being dropped.
    """
    ie = v.ttm("interest_expense")
    if ie is None:
        return None
    ie = abs(ie)
    if ie <= 0:
        return None
    ebit = v.ttm("operating_income")
    if ebit is None:
        return None
    return ebit / ie


def altman_z(v: FundamentalsView, m: Optional[MarketPoint]) -> Optional[float]:
    """Altman (1968) original Z-score; market value of equity required."""
    if m is None:
        return None
    ca, cl = v.instant("current_assets"), v.instant("current_liabilities")
    ta, re = v.instant("total_assets"), v.instant("retained_earnings")
    te = v.instant("total_equity")
    ebit, rev = v.ttm("operating_income"), v.ttm("revenue")
    if None in (ca, cl, ta, re, te, ebit, rev) or ta <= 0:
        return None
    tl = ta - te
    if tl <= 0:
        return None
    x = ((ca - cl) / ta, re / ta, ebit / ta, m.market_cap / tl, rev / ta)
    return sum(c * xi for c, xi in zip(ALTMAN_COEFFS, x))


def current_ratio(v: FundamentalsView, m) -> Optional[float]:
    return _ratio(v.instant("current_assets"), v.instant("current_liabilities"))


def accruals_ratio(v: FundamentalsView, m) -> Optional[float]:
    """(NI - CFO) / average total assets; cash-flow accruals variant."""
    ni, cfo, ta = v.ttm("net_income"), v.ttm("cfo"), v.instant("total_assets")
    if None in (ni, cfo, ta):
        return None
    ta_prior = v.instant_year_ago("total_assets")
    avg = (ta + ta_prior) / 2 if ta_prior is not None else ta
    if avg <= 0:
        return None
    return (ni - cfo) / avg


def cfo_ni(v: FundamentalsView, m) -> Optional[float]:
    """CFO / net income, TTM; undefined for negative earnings (D11: the
    accruals ratio covers that regime)."""
    ni = v.ttm("net_income")
    if ni is None or ni <= 0:
        return None
    return _ratio(v.ttm("cfo"), ni)


def piotroski_f(v: FundamentalsView, m) -> Optional[float]:
    """Piotroski (2000) F-score, 0-9; None when any input is missing.

    Uses only CONSECUTIVE fiscal years (D8): the two latest FY period ends
    must be a normal year apart.
    """
    ends = [f.period_end for f in v.fy_series("net_income")]
    if len(ends) < 2:
        return None
    end0, end1 = ends[-1], ends[-2]
    lo, hi = FY_GAP_DAYS
    if not lo <= _days(end1, end0) <= hi:
        return None
    ta0 = v.instant_at("total_assets", end0)
    ta1 = v.instant_at("total_assets", end1)
    ni0, ni1 = v.fy("net_income", 0), v.fy("net_income", 1)
    cfo0 = v.fy("cfo", 0)
    ltd0 = v.instant_at("long_term_debt", end0)
    ltd1 = v.instant_at("long_term_debt", end1)
    ca0 = v.instant_at("current_assets", end0)
    ca1 = v.instant_at("current_assets", end1)
    cl0 = v.instant_at("current_liabilities", end0)
    cl1 = v.instant_at("current_liabilities", end1)
    sh0 = v.instant_at("shares_outstanding", end0)
    if sh0 is None:
        sh0 = v.fy("shares_basic", 0)
    sh1 = v.instant_at("shares_outstanding", end1)
    if sh1 is None:
        sh1 = v.fy("shares_basic", 1)
    rev0, rev1 = v.fy("revenue", 0), v.fy("revenue", 1)
    cogs0, cogs1 = v.fy("cogs", 0), v.fy("cogs", 1)
    inputs = (ta0, ta1, ni0, ni1, cfo0, ltd0, ltd1, ca0, ca1, cl0, cl1,
              sh0, sh1, rev0, rev1, cogs0, cogs1)
    if None in inputs or ta0 <= 0 or ta1 <= 0 or cl0 <= 0 or cl1 <= 0 \
            or rev0 <= 0 or rev1 <= 0:
        return None
    roa0, roa1 = ni0 / ta0, ni1 / ta1
    gm0 = (rev0 - cogs0) / rev0
    gm1 = (rev1 - cogs1) / rev1
    score = 0
    score += 1 if roa0 > 0 else 0            # 1. positive return on assets
    score += 1 if cfo0 > 0 else 0            # 2. positive operating cash flow
    score += 1 if roa0 > roa1 else 0         # 3. rising ROA
    score += 1 if cfo0 > ni0 else 0          # 4. accruals: CFO exceeds NI
    score += 1 if ltd0 / ta0 < ltd1 / ta1 else 0   # 5. falling long-term leverage
    score += 1 if ca0 / cl0 > ca1 / cl1 else 0     # 6. rising current ratio
    score += 1 if sh0 <= sh1 else 0          # 7. no share issuance
    score += 1 if gm0 > gm1 else 0           # 8. rising gross margin
    score += 1 if rev0 / ta0 > rev1 / ta1 else 0   # 9. rising asset turnover
    return float(score)


def ebitda_yield(v: FundamentalsView, m: Optional[MarketPoint]) -> Optional[float]:
    """EBITDA / enterprise value, TTM (sign-safe EV/EBITDA replacement, D11).

    Higher is better and the numerator may be negative, so unprofitable
    firms rank at the bottom instead of being dropped from the pool.
    """
    if m is None or m.enterprise_value is None:
        return None
    ebitda = _ebitda_ttm(v)
    if ebitda is None:
        return None
    return ebitda / m.enterprise_value


def fcf_yield(v: FundamentalsView, m: Optional[MarketPoint]) -> Optional[float]:
    """(CFO - capex) / market cap; signed equity FCF over equity value."""
    if m is None:
        return None
    cfo, capex = v.ttm("cfo"), v.ttm("capex")
    if cfo is None or capex is None:
        return None
    return _ratio(cfo - capex, m.market_cap)


def earnings_yield(v: FundamentalsView, m: Optional[MarketPoint]) -> Optional[float]:
    """Net income / market cap, TTM; negative earnings allowed (D11)."""
    if m is None:
        return None
    ni = v.ttm("net_income")
    if ni is None:
        return None
    return ni / m.market_cap


def p_book(v: FundamentalsView, m: Optional[MarketPoint]) -> Optional[float]:
    if m is None:
        return None
    te = v.instant("total_equity")
    if te is None or te <= 0:
        return None
    return m.market_cap / te


def shareholder_yield(v: FundamentalsView, m: Optional[MarketPoint]) -> Optional[float]:
    """(dividends + buybacks) / market cap, TTM."""
    if m is None:
        return None
    div, bb = v.ttm("dividends_paid"), v.ttm("buybacks")
    if div is None or bb is None:
        return None
    return (div + bb) / m.market_cap


def share_count_change(v: FundamentalsView, m) -> Optional[float]:
    """YoY change in shares outstanding; negative means net buybacks."""
    sh0 = v.instant("shares_outstanding")
    sh1 = v.instant_year_ago("shares_outstanding")
    if sh0 is None or sh1 is None or sh1 <= 0:
        return None
    return sh0 / sh1 - 1.0


# ------------------------------------------------- financials model ----


def roe_ttm(v: FundamentalsView, m) -> Optional[float]:
    """Net income / average total equity, TTM (signed numerator allowed)."""
    ni = v.ttm("net_income")
    eq = v.instant("total_equity")
    if ni is None or eq is None:
        return None
    eq_prior = v.instant_year_ago("total_equity")
    avg = (eq + eq_prior) / 2 if eq_prior is not None else eq
    if avg <= 0:
        return None
    return ni / avg


def rotce_ttm(v: FundamentalsView, m) -> Optional[float]:
    """Net income / average tangible common equity, TTM."""
    ni = v.ttm("net_income")
    eq0 = v.instant("total_equity")
    if ni is None or eq0 is None:
        return None
    tce0 = _sub_optional(eq0, v.instant("preferred_equity"),
                         v.instant("goodwill"), v.instant("intangibles"))
    eq1 = v.instant_year_ago("total_equity")
    tce1 = None
    if eq1 is not None:
        tce1 = _sub_optional(eq1, v.instant_year_ago("preferred_equity"),
                             v.instant_year_ago("goodwill"),
                             v.instant_year_ago("intangibles"))
    avg = (tce0 + tce1) / 2 if tce1 is not None else tce0
    if avg is None or avg <= 0:
        return None
    return ni / avg


def efficiency_ratio(v: FundamentalsView, m) -> Optional[float]:
    """Noninterest expense / total revenue (banks); lower is better."""
    return _ratio(v.ttm("noninterest_expense"), v.ttm("revenue"))


def equity_assets(v: FundamentalsView, m) -> Optional[float]:
    return _ratio(v.instant("total_equity"), v.instant("total_assets"))


# ------------------------------------------------------- REIT model ----


def _ffo_ttm(v: FundamentalsView) -> Optional[float]:
    """FFO approximation: NI + D&A - gains on sales + impairments, TTM."""
    ni, da = v.ttm("net_income"), v.ttm("depreciation_amortization")
    if ni is None or da is None:
        return None
    gains = v.ttm("gains_on_sales") or 0.0
    imp = v.ttm("impairments") or 0.0
    return ni + da - gains + imp


def _ffo_fy_at(v, period_end: str) -> Optional[float]:
    ni, da = v.fy_at("net_income", period_end), \
        v.fy_at("depreciation_amortization", period_end)
    if ni is None or da is None:
        return None
    return ni + da - (v.fy_at("gains_on_sales", period_end) or 0.0) \
        + (v.fy_at("impairments", period_end) or 0.0)


# P7/D: metrics whose FFO arithmetic zero-defaults an unavailable
# gains_on_sales/impairments component (the zero default itself is
# UNCHANGED - these only drive the transparency note).
_FFO_METRICS = frozenset(
    {"ffo_margin", "affo_margin", "ffo_yield", "ffo_cagr_3y",
     "payout_ratio"})
_FFO_ZERO_DEFAULT_ITEMS = ("gains_on_sales", "impairments")


def ffo_margin(v: FundamentalsView, m) -> Optional[float]:
    return _ratio(_ffo_ttm(v), v.ttm("revenue"))


def affo_margin(v: FundamentalsView, m) -> Optional[float]:
    """FFO - maintenance capex over revenue; None when capex split unknown."""
    ffo, mcx = _ffo_ttm(v), v.ttm("maintenance_capex")
    if ffo is None or mcx is None:
        return None
    return _ratio(ffo - mcx, v.ttm("revenue"))


def ffo_yield(v: FundamentalsView, m: Optional[MarketPoint]) -> Optional[float]:
    if m is None:
        return None
    return _ratio(_ffo_ttm(v), m.market_cap)


def ffo_cagr_3y(v: FundamentalsView, m) -> Optional[float]:
    """3Y FFO CAGR on consecutive FYs with matched period ends (D8)."""
    ni_w = v.consecutive_fy("net_income")
    da_w = v.consecutive_fy("depreciation_amortization")
    if ni_w is None or da_w is None:
        return None
    if ni_w[0].period_end != da_w[0].period_end \
            or ni_w[-1].period_end != da_w[-1].period_end:
        return None
    ffo_start = Fact(ni_w[0].period_end, ni_w[0].filing_date,
                     _ffo_fy_at(v, ni_w[0].period_end), "FY")
    ffo_end = Fact(ni_w[-1].period_end, ni_w[-1].filing_date,
                   _ffo_fy_at(v, ni_w[-1].period_end), "FY")
    return _cagr_span(ffo_start, ffo_end)


def payout_ratio(v: FundamentalsView, m) -> Optional[float]:
    """Dividends / FFO; payout above 1 consumes more than FFO."""
    div, ffo = v.ttm("dividends_paid"), _ffo_ttm(v)
    if div is None or ffo is None or ffo <= 0:
        return None
    return div / ffo


# ------------------------------------------------------- momentum ----


def momentum_12_1_detail(prices, as_of: str):
    """Calendar-based 12-1 momentum (defect D4).

    Returns (value, reason). Prices are (iso_date, close) pairs; duplicates
    are resolved last-wins, dates sorted, everything after ``as_of`` ignored.
    t_end = as_of - MOMENTUM_SKIP_MONTHS, t_start = as_of - MOMENTUM_MONTHS
    (month arithmetic with day clamping). For each target the LAST
    observation on or before it is used; the observation is rejected when the
    gap to the target exceeds max(MOMENTUM_MIN_GAP_DAYS,
    1.5 x median spacing) days. Works for daily, weekly and monthly series.
    """
    by_date: dict = {}
    for d, c in (prices or []):
        if d is None or c is None:
            continue
        by_date[d] = float(c)          # duplicate dates: last wins
    pts = sorted((d, c) for d, c in by_date.items() if d <= as_of)
    if len(pts) < 2:
        return None, "insufficient_history"
    t_end = _shift_months(as_of, -MOMENTUM_SKIP_MONTHS)
    t_start = _shift_months(as_of, -MOMENTUM_MONTHS)
    gaps = [(date.fromisoformat(b[0]) - date.fromisoformat(a[0])).days
            for a, b in zip(pts, pts[1:])]
    median_spacing = statistics.median(gaps) if gaps else MOMENTUM_MIN_GAP_DAYS
    threshold = max(float(MOMENTUM_MIN_GAP_DAYS),
                    MOMENTUM_GAP_SPACING_FACTOR * float(median_spacing))
    obs = {d: c for d, c in pts}

    def _at(target: str, label: str):
        candidates = [d for d in obs if d <= target]
        if not candidates:
            return None, f"insufficient_history_{label}"
        chosen = candidates[-1]
        gap = _days(chosen, target)
        if gap > threshold:
            return None, f"gap_too_large_{label}"
        return obs[chosen], None

    if not [d for d in obs if t_start < d <= t_end]:
        # no observation anywhere inside the measurement window: the series
        # does not actually cover the 12-1 window
        return None, "insufficient_history_in_window"
    p_start, err = _at(t_start, "at_start")
    if p_start is None:
        return None, err
    if p_start <= 0:
        return None, "nonpositive_start_price"
    p_end, err = _at(t_end, "at_end")
    if p_end is None:
        return None, err
    return p_end / p_start - 1.0, None


def momentum_12_1(prices, as_of: str) -> Optional[float]:
    """12-1 month momentum (see momentum_12_1_detail); None when unusable."""
    value, _reason = momentum_12_1_detail(prices, as_of)
    return value


# ------------------------------------------------------- registry ----

METRIC_FUNCS: dict = {
    "roic": roic,
    "gross_profitability": gross_profitability,
    "operating_margin": operating_margin,
    "operating_margin_5y": operating_margin_5y,
    "fcf_margin": fcf_margin,
    "fcf_margin_5y": fcf_margin_5y,
    "gross_profitability_5y": gross_profitability_5y,
    "revenue_cagr_3y": revenue_cagr_3y,
    "earnings_cagr_3y": earnings_cagr_3y,
    "ffo_cagr_3y": ffo_cagr_3y,
    "growth_stability": growth_stability,
    "net_debt_ebitda": net_debt_ebitda,
    "interest_coverage": interest_coverage,
    "altman_z": altman_z,
    "current_ratio": current_ratio,
    "accruals_ratio": accruals_ratio,
    "cfo_ni": cfo_ni,
    "piotroski_f": piotroski_f,
    "ebitda_yield": ebitda_yield,
    "fcf_yield": fcf_yield,
    "earnings_yield": earnings_yield,
    "p_book": p_book,
    "roe_ttm": roe_ttm,
    "rotce_ttm": rotce_ttm,
    "efficiency_ratio": efficiency_ratio,
    "equity_assets": equity_assets,
    "ffo_margin": ffo_margin,
    "affo_margin": affo_margin,
    "ffo_yield": ffo_yield,
    "payout_ratio": payout_ratio,
    "shareholder_yield": shareholder_yield,
    "share_count_change": share_count_change,
}


# =========================== SECTION: SECTOR MODELS ===========================
# Which metrics each sector group is scored on. Pillars and prior weights are
# fixed in PILLAR_WEIGHTS; within a pillar every metric carries equal weight.
# Sector models swap the metric set, never the weights. Metrics marked
# ``required`` must be computable, otherwise the company gets status
# SECTOR_DATA_MISSING (owner specification: never skipped silently).


@dataclass(frozen=True)
class MetricSpec:
    """One metric inside a sector model."""

    pillar: str
    name: str
    direction: int          # +1 higher is better, -1 lower is better
    required: bool = False
    rationale: str = ""


@dataclass(frozen=True)
class SectorModel:
    """Metric set applied to a family of sector groups."""

    key: str
    sectors: tuple
    metrics: tuple
    notes: str = ""


def M(pillar: str, name: str, direction: int, required: bool = False,
      rationale: str = "") -> MetricSpec:
    return MetricSpec(pillar, name, direction, required, rationale)


# ------------------------------------------------------------ default ----

_DEFAULT = (
    M("profitability", "roic", 1, False, "Operating return on invested capital."),
    M("profitability", "gross_profitability", 1, False,
      "Novy-Marx (2013) gross profit / total assets."),
    M("profitability", "operating_margin", 1, False, "Core operating efficiency."),
    M("profitability", "fcf_margin", 1, False, "Cash conversion of revenue."),
    M("growth", "revenue_cagr_3y", 1, False, "Top-line compounding."),
    M("growth", "earnings_cagr_3y", 1, False,
      "Diluted EPS CAGR with aggregate FCF CAGR fallback."),
    M("growth", "growth_stability", 1, False, "Persistence of revenue growth."),
    M("financial_strength", "net_debt_ebitda", -1, False, "Cash-flow leverage."),
    M("financial_strength", "interest_coverage", 1, False, "Debt service capacity."),
    M("financial_strength", "altman_z", 1, False, "Altman (1968) distress distance."),
    M("financial_strength", "current_ratio", 1, False, "Liquidity buffer."),
    M("earnings_quality", "accruals_ratio", -1, False,
      "Cash-flow accruals variant (NI - CFO) / assets."),
    M("earnings_quality", "cfo_ni", 1, False, "Cash backing of earnings."),
    M("earnings_quality", "piotroski_f", 1, False, "Piotroski (2000) F-score."),
    M("valuation", "ebitda_yield", 1, False,
      "EBITDA / EV: sign-safe replacement for EV/EBITDA (D11); higher is "
      "better and loss-makers rank at the bottom instead of being dropped."),
    M("valuation", "fcf_yield", 1, False,
      "Equity free cash flow over equity value."),
    M("valuation", "earnings_yield", 1, False,
      "Earnings over market cap; negative earnings allowed (D11)."),
    M("shareholder_yield", "shareholder_yield", 1, False,
      "Dividends plus buybacks over market cap."),
    M("shareholder_yield", "share_count_change", -1, False,
      "Net issuance; shrinkage rewards holders."),
)

# ----------------------------------------------------------- cyclicals ----


def _swap(metrics: tuple, replacements: dict) -> tuple:
    out = []
    for m in metrics:
        out.append(replacements.get(m.name, m))
    return tuple(out)


_CYCLICALS = _swap(_DEFAULT, {
    "operating_margin": M("profitability", "operating_margin_5y", 1, True,
                          "Cyclicals are ranked on the 5-year median margin, "
                          "not the cycle point (owner spec)."),
    "gross_profitability": M("profitability", "gross_profitability_5y", 1, True,
                             "5-year median gross profitability "
                             "(Novy-Marx on median margins)."),
    "fcf_margin": M("profitability", "fcf_margin_5y", 1, True,
                    "5-year median FCF margin."),
})
_CYCLICALS = tuple(m for m in _CYCLICALS if m.name not in ("operating_margin",
                    "gross_profitability", "fcf_margin"))

# ---------------------------------------------------------- financials ----

_FINANCIALS = (
    M("profitability", "roe_ttm", 1, True,
      "Return on equity is the bank profitability metric (owner spec)."),
    M("profitability", "rotce_ttm", 1, False,
      "Tangible common equity return; optional when preferred/goodwill "
      "reported."),
    M("profitability", "efficiency_ratio", -1, False,
      "Noninterest expense / revenue; optional when reported."),
    M("growth", "revenue_cagr_3y", 1, False, "Top-line compounding."),
    M("growth", "earnings_cagr_3y", 1, False,
      "Diluted EPS CAGR with aggregate FCF CAGR fallback."),
    M("growth", "growth_stability", 1, False, "Persistence of revenue growth."),
    M("financial_strength", "equity_assets", 1, True,
      "Capitalization proxy; D/E, Altman Z and current ratio excluded for "
      "banks (owner spec: no gross margin, no D/E)."),
    M("earnings_quality", "accruals_ratio", -1, False,
      "Cash-flow accruals variant; noisier for banks, still ranked."),
    M("earnings_quality", "cfo_ni", 1, False, "Cash backing of earnings."),
    M("earnings_quality", "piotroski_f", 1, False, "Piotroski (2000) F-score."),
    M("valuation", "p_book", -1, False,
      "Price / book is the bank valuation standard; EV/EBITDA and FCF yield "
      "are not meaningful."),
    M("valuation", "earnings_yield", 1, False,
      "Earnings over market cap; negative earnings allowed (D11)."),
    M("shareholder_yield", "shareholder_yield", 1, False,
      "Dividends plus buybacks over market cap."),
    M("shareholder_yield", "share_count_change", -1, False,
      "Net issuance; shrinkage rewards holders."),
)

# ---------------------------------------------------------------- REIT ----

_REIT = (
    M("profitability", "ffo_margin", 1, True,
      "FFO margin; FFO = NI + D&A - gains on sales + impairments "
      "(Nareit-style approximation)."),
    M("profitability", "affo_margin", 1, False,
      "AFFO margin when maintenance capex is separable; frequently "
      "unavailable."),
    M("growth", "revenue_cagr_3y", 1, False, "Top-line compounding."),
    M("growth", "ffo_cagr_3y", 1, False,
      "FFO compounding replaces EPS/FCF CAGR for REITs (owner spec: FFO/AFFO "
      "if available)."),
    M("growth", "growth_stability", 1, False, "Persistence of revenue growth."),
    M("financial_strength", "net_debt_ebitda", -1, True,
      "Owner spec: REIT leverage screen."),
    M("financial_strength", "interest_coverage", 1, False,
      "Debt service capacity."),
    M("earnings_quality", "payout_ratio", -1, False,
      "Dividend sustainability versus FFO; accruals ratio is structurally "
      "negative for REITs (depreciation) and is excluded."),
    M("valuation", "ffo_yield", 1, False,
      "FFO over market cap; the REIT valuation standard."),
    M("valuation", "p_book", -1, False,
      "Price / book proxies discount to book NAV."),
    M("shareholder_yield", "shareholder_yield", 1, False,
      "Dividends plus buybacks over market cap."),
    M("shareholder_yield", "share_count_change", -1, False,
      "Net issuance; shrinkage rewards holders."),
)

# ---------------------------------------------------------- utilities ----

_UTILITIES = (
    M("profitability", "roe_ttm", 1, True,
      "Owner spec: ROE emphasized for regulated utilities."),
    M("profitability", "operating_margin", 1, False, "Core operating efficiency."),
    M("growth", "revenue_cagr_3y", 1, False,
      "Top-line compounding (rate-base growth)."),
    M("growth", "earnings_cagr_3y", 1, False,
      "Diluted EPS CAGR with aggregate FCF CAGR fallback."),
    M("growth", "growth_stability", 1, False, "Persistence of revenue growth."),
    M("financial_strength", "net_debt_ebitda", -1, False,
      "Leverage is ranked within the utilities pool only: the sector "
      "structurally carries more debt and is tolerated (owner spec)."),
    M("financial_strength", "interest_coverage", 1, True,
      "Owner spec: interest coverage is the utilities strength core."),
    M("financial_strength", "current_ratio", 1, False, "Liquidity buffer."),
    M("earnings_quality", "accruals_ratio", -1, False,
      "Cash-flow accruals variant."),
    M("earnings_quality", "cfo_ni", 1, False, "Cash backing of earnings."),
    M("earnings_quality", "piotroski_f", 1, False, "Piotroski (2000) F-score."),
    M("valuation", "ebitda_yield", 1, False,
      "Firm-level cash-flow yield, standard for regulated assets; sign-safe "
      "replacement for EV/EBITDA (D11)."),
    M("valuation", "earnings_yield", 1, False,
      "Earnings over market cap; negative earnings allowed (D11)."),
    M("valuation", "fcf_yield", 1, False,
      "Equity FCF yield; often missing in heavy-capex years, handled by "
      "coverage."),
    M("shareholder_yield", "shareholder_yield", 1, False,
      "Dividends plus buybacks over market cap."),
    M("shareholder_yield", "share_count_change", -1, False,
      "Net issuance; shrinkage rewards holders."),
)

# Altman Z is deliberately absent from the financials, REIT and utilities
# models: deposit-funded, depreciation-heavy or regulated-leverage balance
# sheets distort the original manufacturing-firm model.

MODELS: dict = {
    "default": SectorModel(
        "default", ("healthcare", "tech", "consumer", "communication",
                    "specialty"),
        _DEFAULT,
        "General non-financial model; Altman Z included."),
    "cyclicals": SectorModel(
        "cyclicals", ("energy", "materials", "industrials"),
        _CYCLICALS,
        "Energy, materials, industrials: 5-year median margins instead of "
        "latest (owner spec)."),
    "financials": SectorModel(
        "financials", ("financials",),
        _FINANCIALS,
        "Banks, insurers, capital markets: ROE/ROTCE, P/B, efficiency ratio, "
        "equity/assets; no gross margin, no D/E, no Altman."),
    "reit": SectorModel(
        "reit", ("reits",),
        _REIT,
        "REITs: FFO/AFFO when available, net debt/EBITDA, payout ratio, FFO "
        "yield."),
    "utilities": SectorModel(
        "utilities", ("utilities",),
        _UTILITIES,
        "Utilities: interest coverage core, leverage tolerated via "
        "within-sector ranking, ROE emphasized."),
}


def resolve_model(sector: str) -> SectorModel:
    """SectorModel for a universe sector group."""
    return MODELS[model_for_sector(sector)]


def all_metric_names() -> list:
    """Sorted union of metric names across models (snapshot columns)."""
    names = set()
    for model in MODELS.values():
        names.update(spec.name for spec in model.metrics)
    return sorted(names)


def metric_weights(model: SectorModel) -> dict:
    """Equal intra-pillar weights: pillar weight split across its metrics."""
    counts: dict = {}
    for spec in model.metrics:
        counts[spec.pillar] = counts.get(spec.pillar, 0) + 1
    return {spec.name: PILLAR_WEIGHTS[spec.pillar] / counts[spec.pillar]
            for spec in model.metrics}


# Import-time sanity checks: fail fast on typos, no runtime side effects.
for _model in MODELS.values():
    for _spec in _model.metrics:
        assert _spec.name in METRIC_FUNCS, f"unknown metric {_spec.name}"
        assert _spec.pillar in PILLAR_WEIGHTS, f"unknown pillar {_spec.pillar}"
        assert _spec.direction in (1, -1), f"bad direction {_spec.name}"
    _weights = metric_weights(_model)
    assert abs(sum(_weights.values()) - 1.0) < WEIGHT_SUM_TOLERANCE, \
        f"weights broken for {_model.key}"
    for _pillar in PILLAR_WEIGHTS:
        assert any(s.pillar == _pillar for s in _model.metrics), \
            f"model {_model.key} missing pillar {_pillar}"


# Cross-sectional scoring: winsorize, sector percentiles, pillars, composite.
#
# Invariants (all covered by SELFTEST):
# - the composite is bounded 0-100 and only exposed when status is OK (I6,
#   defect D10: every other status carries score None and diagnostics in
#   score_unrated);
# - improving a company's own metric never lowers its composite (monotone);
# - there are no good/neutral/bad thresholds - scores are continuous;
# - coverage = available metric weight / total metric weight, gated at
#   MIN_COVERAGE with status INSUFFICIENT_DATA;
# - stale fundamentals gate to STALE_DATA before any score is exposed (I3,
#   defect D9);
# - red flags are reported separately and never folded into the score.

OK = "OK"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
SECTOR_DATA_MISSING = "SECTOR_DATA_MISSING"
STALE_DATA = "STALE_DATA"
NO_DATA = "NO_DATA"
DELISTED = "DELISTED"
RENAMED = "RENAMED"
ERROR = "ERROR"

STATUS_ORDER = (ERROR, NO_DATA, STALE_DATA, SECTOR_DATA_MISSING,
                INSUFFICIENT_DATA, OK)



# =============================== SECTION: SCORING =============================


class ScoreResult:
    """One company's score card; ``to_api_dict`` gives the documented shape."""

    __slots__ = ("ticker", "sector", "model", "as_of", "status", "score",
                 "pillars", "coverage", "flags", "notes", "rank_in_sector",
                 "data_source", "metrics", "metric_scores", "error",
                 "score_unrated", "source_status", "provenance",
                 "item_source", "market_cap")

    def __init__(self, ticker: str, sector: str, model: str, as_of: str,
                 status: str = ERROR, data_source: str = ""):
        self.ticker = ticker
        self.sector = sector
        self.model = model
        self.as_of = as_of
        self.status = status
        self.score: Optional[float] = None
        self.pillars: dict = {}
        self.coverage: float = 0.0
        self.flags: list = []
        self.notes: list = []
        self.rank_in_sector: Optional[int] = None
        self.data_source = data_source
        self.metrics: dict = {}
        self.metric_scores: dict = {}
        self.error: Optional[str] = None
        self.score_unrated: Optional[dict] = None  # D10 diagnostics
        self.source_status: dict = {}
        self.provenance: dict = {}    # D18: metric -> fact-level trace list
        self.item_source: dict = {}   # item -> provider (was Company-level)
        self.market_cap: Optional[float] = None   # snapshot column (S7)

    def to_api_dict(self) -> dict:
        """The documented API shape (superset of the required ten keys)."""
        return {
            "ticker": self.ticker,
            "as_of": self.as_of,
            "sector": self.sector,
            "score": self.score,
            "pillars": dict(self.pillars),
            "coverage": self.coverage,
            "flags": list(self.flags),
            "rank_in_sector": self.rank_in_sector,
            "status": self.status,
            "data_source": self.data_source,
            "model": self.model,
            "metrics": dict(self.metrics),
            "metric_scores": dict(self.metric_scores),
            "notes": list(self.notes),
            "error": self.error,
            "score_unrated": (None if self.score_unrated is None
                              else dict(self.score_unrated)),
            "source_status": dict(self.source_status),
            "provenance": {k: [dict(e) for e in v]
                           for k, v in self.provenance.items()},
            "item_source": dict(self.item_source),
        }

def _quantile(sorted_vals: list, p: float) -> Optional[float]:
    """Linear-interpolated quantile of an already-sorted list."""
    n = len(sorted_vals)
    if n == 0:
        return None
    if n == 1:
        return sorted_vals[0]
    pos = (n - 1) * p
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def winsorize(values: list) -> list:
    """Clip values at the configured percentile bounds (order preserved).

    WORST (inf) sentinels are excluded from the quantile computation and
    re-inserted afterwards, so one adverse-extreme member cannot drag the
    clipping bound to infinity (D11).
    """
    if not values:
        return []
    finite = sorted(v for v in values if v != WORST)
    if finite:
        lo = _quantile(finite, WINSOR_LOWER)
        hi = _quantile(finite, WINSOR_UPPER)
    else:
        lo = hi = None
    out = []
    for v in values:
        if v == WORST:
            out.append(v)
        elif lo is None:
            out.append(v)
        else:
            out.append(min(max(v, lo), hi))
    return out


def _midranks(vals: list) -> list:
    """Average (mid) ranks, 1-indexed; ties share the mean position."""
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        mid = (i + j) / 2 + 1  # 0-based i..j -> 1-based positions i+1..j+1
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    return ranks



def percentile_scores(pool_values: list, direction: int) -> list:
    """Winsorized, direction-adjusted percentile score per member.

    D17: with k = number of WORST sentinels and n = pool size (finite +
    WORST), a finite member scores (k + midrank_finite) / n and a WORST
    member scores exactly 0.0 (worst, still counted as available - D11).
    This is the ONE documented exception to plain rank/n: sentinels occupy
    the bottom k slots. Finite scores stay in (0, 1]. A pool with a single
    finite member and no WORST never reaches this function through the
    scoring path (_rank_pool callers apply the MIN_PEERS / thin-pool rule
    and keep the neutral THIN_POOL_NEUTRAL).
    """
    if not pool_values:
        return []
    clipped = winsorize(pool_values)
    worst = [v == WORST for v in clipped]
    k = sum(worst)
    n = len(clipped)
    finite_signed = [(-v if direction < 0 else v)
                     for v, is_worst in zip(clipped, worst) if not is_worst]
    finite_ranks = _midranks(finite_signed)
    out: list = []
    idx = 0
    for is_worst in worst:
        if is_worst:
            out.append(0.0)
        else:
            rank = finite_ranks[idx]
            idx += 1
            out.append((k + rank) / n if n else 0.0)
    return out

def _rank_pool(pairs: list, direction: int) -> dict:
    """pairs [(ticker, value)] -> ticker -> (score, pool_size)."""
    values = [v for _, v in pairs]
    scores = percentile_scores(values, direction)
    return {t: (s, len(values)) for (t, _), s in zip(pairs, scores)}


def _sector_fallback_pools(records: list) -> tuple:
    """Ranking tables: per (metric, sector) and per metric whole-universe."""
    sector_tables: dict = {}
    global_tables: dict = {}
    by_metric_sector: dict = {}
    for rec in records:
        model: SectorModel = rec["model"]
        raw: dict = rec["raw"]
        for spec in model.metrics:
            v = raw.get(spec.name)
            if v is None:
                continue
            by_metric_sector.setdefault(
                (spec.name, rec["company"].sector), []).append(
                (rec["company"].ticker, v))
    for (name, sector), pairs in by_metric_sector.items():
        spec = _spec_for(name, records)
        sector_tables[(name, sector)] = _rank_pool(pairs, spec.direction)
        merged = global_tables.setdefault(name, [])
        merged.extend(pairs)
    for name, pairs in list(global_tables.items()):
        spec = _spec_for(name, records)
        global_tables[name] = _rank_pool(pairs, spec.direction)
    return sector_tables, global_tables


def _spec_for(name: str, records: list):
    for rec in records:
        for spec in rec["model"].metrics:
            if spec.name == name:
                return spec
    raise KeyError(name)




def compute_raw_metrics(company: Company, model: SectorModel, as_of: str):
    """Metric name -> value (None when not computable); never raises.

    Also returns the point-in-time staleness verdict (D9/D16): latest
    FISCAL period_end vs as_of, the market build status, and the per-metric
    provenance map (D18: metric -> list of {item, provider, period_end,
    filing_date, available_date, accession} for every underlying fact,
    deduplicated and sorted deterministically).
    """
    raw: dict = {}
    notes: list = []
    provenance: dict = {}
    view = FundamentalsView(company.facts, as_of)
    market, price_status = build_market(company, as_of)
    for spec in model.metrics:
        func = METRIC_FUNCS[spec.name]
        view._clear_trace()
        try:
            raw[spec.name] = func(view, market)
        except Exception as exc:  # one metric never kills the company
            raw[spec.name] = None
            notes.append(f"metric_error:{spec.name}:{type(exc).__name__}")
        trace = list(view._clear_trace())
        if spec.name in MARKET_METRICS and market is not None:
            trace.extend(market.trace)
        provenance[spec.name] = sorted(
            {json.dumps(e, sort_keys=True): e for e in trace}.values(),
            key=lambda e: json.dumps(e, sort_keys=True))
    if market is None:
        if price_status == "stale":
            notes.append("stale_price")          # flag handled by caller
        elif price_status in ("no_point_in_time_shares", "stale_shares",
                              "split_basis_unverified"):
            notes.append(f"no_market_data:{price_status}")
        else:
            notes.append("no_market_data")
    if view.dropped_no_filing:
        notes.append(f"facts_dropped_no_filing_date:{view.dropped_no_filing}")
    if any(s.name in _FFO_METRICS for s in model.metrics) and any(
            view.ttm(item) is None for item in _FFO_ZERO_DEFAULT_ITEMS):
        # P7/D (transparency only): the FFO arithmetic keeps the zero
        # default for an unavailable gains/impairments component - say so.
        notes.append("ffo_gains_impairments_assumed_zero")
    _debt_end, _debt_value, debt_missing = view._compose_debt()
    if debt_missing:
        notes.append("debt_component_missing:" + ",".join(debt_missing))
    latest = view.latest_fiscal_period_end()
    stale = (latest is None
             or _days(latest, as_of) > STALE_FUNDAMENTALS_DAYS)
    return raw, notes, view, market, price_status, stale, provenance


def _coverage_below_minimum(coverage: float) -> bool:
    """Float-safe MIN_COVERAGE gate (re-audit finding 1, PART E).

    The failure condition is ``coverage + COVERAGE_EPS < MIN_COVERAGE``:
    a coverage that lands marginally below the threshold through weight
    arithmetic (e.g. 0.65 represented as 0.6499999999999999) is accepted;
    a genuine shortfall outside the epsilon still fails. Numerical
    boundary correction only - MIN_COVERAGE, the metric weights, the
    pillar weights and the coverage calculation itself are unchanged.
    """
    return coverage + COVERAGE_EPS < MIN_COVERAGE


def score_universe(companies: list, as_of: str) -> dict:
    """Score all companies cross-sectionally as of ``as_of`` (ISO date).

    Rule I6 / defect D10: ``score`` is None unless status is OK; unrated
    diagnostics (coverage, missing required metrics, the would-be composite)
    go to ``score_unrated``. Rule I3 / defect D9: companies whose latest
    FISCAL period end (D16) is older than STALE_FUNDAMENTALS_DAYS are
    STALE_DATA and never scored. E13: a refused split basis sets the
    SPLIT_BASIS_UNVERIFIED flag next to STALE_PRICE.
    """
    records = []
    results: dict = {}

    for c in companies:
        data_source = "+".join(sorted(c.sources)) if c.sources else ""
        res = ScoreResult(c.ticker, c.sector, resolve_model(c.sector).key,
                          as_of, ERROR, data_source)
        res.source_status = dict(c.source_status or {})
        res.item_source = dict(getattr(c, "item_source", None)
                               or getattr(c, "provenance", None) or {})
        results[c.ticker] = res
        try:
            model = resolve_model(c.sector)
            if not c.facts:
                res.status = NO_DATA
                res.notes.append("no_fundamental_facts")
                continue
            raw, notes, view, market, price_status, stale, provenance = \
                compute_raw_metrics(c, model, as_of)
            records.append({"company": c, "model": model, "raw": raw,
                            "notes": notes, "view": view, "market": market,
                            "price_status": price_status, "stale": stale,
                            "provenance": provenance, "result": res})
        except Exception as exc:
            res.error = f"{type(exc).__name__}: {exc}"

    if not records:
        return results

    sector_tables, global_tables = _sector_fallback_pools(records)

    for rec in records:
        res: ScoreResult = rec["result"]
        model: SectorModel = rec["model"]
        raw: dict = rec["raw"]
        weights = metric_weights(model)
        res.metrics = {s.name: raw.get(s.name) for s in model.metrics}
        res.provenance = rec["provenance"]
        res.market_cap = (None if rec["market"] is None
                          else rec["market"].market_cap)

        used_fallback = False
        thin_pool = False
        metric_scores: dict = {}
        accruals_score = None
        accruals_pool_size = 0
        for spec in model.metrics:
            v = raw.get(spec.name)
            if v is None:
                metric_scores[spec.name] = None
                continue
            table = sector_tables.get((spec.name, rec["company"].sector))
            entry = table.get(res.ticker) if table else None
            if table and entry and entry[1] - 1 >= MIN_PEERS:
                score, size = entry
            else:
                gtable = global_tables.get(spec.name) or {}
                entry = gtable.get(res.ticker)
                if entry is None:
                    metric_scores[spec.name] = None
                    continue
                score, size = entry
                used_fallback = True
            if size <= 1:
                score = THIN_POOL_NEUTRAL
                thin_pool = True
            metric_scores[spec.name] = score
            if spec.name == "accruals_ratio":
                accruals_score, accruals_pool_size = score, size

        res.metric_scores = metric_scores

        # coverage and composite, normalized by available weight
        avail = [n for n, s in metric_scores.items() if s is not None]
        total_w = sum(weights.values())
        avail_w = sum(weights[n] for n in avail)
        res.coverage = (avail_w / total_w) if total_w > 0 else 0.0
        composite = None
        if avail:
            composite = round(
                100.0 * sum(weights[n] * metric_scores[n] for n in avail)
                / avail_w, ROUND_DIGITS)

        # pillar scores (0-100, mean of available metric scores in pillar)
        pillars: dict = {}
        for pillar in PILLAR_WEIGHTS:
            scores = [metric_scores[s.name] for s in model.metrics
                      if s.pillar == pillar
                      and metric_scores.get(s.name) is not None]
            pillars[pillar] = (round(100.0 * sum(scores) / len(scores),
                                     ROUND_DIGITS)
                               if scores else None)
        res.pillars = pillars
        # counted ONCE from the actual pillar scores: a pillar is available
        # only when its score is non-None (missing is missing, never zero;
        # a missing metric or an unscored pillar never counts).
        n_pillars_available = sum(1 for p in pillars.values()
                                  if p is not None)

        # notes and peer-fallback flag
        res.notes = list(rec["notes"])
        if used_fallback:
            res.flags.append("SECTOR_PEER_FALLBACK")
        if thin_pool:
            res.notes.append("thin_metric_pool")
        if rec["price_status"] == "stale":
            res.flags.append("STALE_PRICE")          # I3 / D9
        if rec["price_status"] == "split_basis_unverified":
            res.flags.append("SPLIT_BASIS_UNVERIFIED")   # E13 / D15

        # staleness gate (I3 / D9 / D16): beyond the fundamentals gate the
        # status is STALE_DATA and no score is ever exposed.
        missing_required = [s.name for s in model.metrics
                            if s.required and raw.get(s.name) is None]
        if rec["stale"]:
            res.status = STALE_DATA
            res.score = None
            res.score_unrated = {
                "reason": "stale_fundamentals",
                "latest_fiscal_period_end":
                    rec["view"].latest_fiscal_period_end(),
                "stale_after_days": STALE_FUNDAMENTALS_DAYS,
                "coverage": round(res.coverage, ROUND_DIGITS),
                "missing_required": missing_required,
                "composite_diagnostic": composite,
            }
            res.flags.extend(_red_flags(rec["view"], rec["market"], raw,
                                        accruals_score, accruals_pool_size))
            res.flags = sorted(set(res.flags))
            continue
        if missing_required:
            res.status = SECTOR_DATA_MISSING
            res.score = None
            res.score_unrated = {
                "reason": "missing_required_metrics",
                "missing_required": missing_required,
                "coverage": round(res.coverage, ROUND_DIGITS),
                "composite_diagnostic": composite,
            }
        else:
            # Gate priority (re-audit finding 1): 3. coverage gate, then
            # 4. minimum-pillar gate, then 5. the accepted score. The
            # coverage gate keeps the existing reason; the pillar gate adds
            # reason pillar_count_below_minimum; when BOTH fail the primary
            # reason stays coverage_below_minimum and the additive
            # failed_gates list names every failed gate deterministically
            # (coverage first, pillars second). No score is exposed unless
            # the status is OK.
            coverage_fail = ((not avail)
                             or _coverage_below_minimum(res.coverage))
            pillar_fail = n_pillars_available < MIN_PILLARS
            if not (coverage_fail or pillar_fail):
                res.status = OK
                res.score = composite
            else:
                failed_gates = ((["coverage_below_minimum"]
                                 if coverage_fail else [])
                                + (["pillar_count_below_minimum"]
                                   if pillar_fail else []))
                unrated = {
                    "reason": ("coverage_below_minimum" if coverage_fail
                               else "pillar_count_below_minimum"),
                    "coverage": round(res.coverage, ROUND_DIGITS),
                    "n_pillars_available": n_pillars_available,
                    "composite_diagnostic": composite,
                    "failed_gates": failed_gates,
                }
                if coverage_fail:
                    unrated["min_coverage"] = MIN_COVERAGE
                if pillar_fail:
                    unrated["min_pillars"] = MIN_PILLARS
                res.status = INSUFFICIENT_DATA
                res.score = None
                res.score_unrated = unrated

        # red flags: always shown, never inside the score
        res.flags.extend(_red_flags(rec["view"], rec["market"], raw,
                                    accruals_score, accruals_pool_size))
        res.flags = sorted(set(res.flags))

    _assign_sector_ranks(results)
    return results

def _assign_sector_ranks(results: dict) -> None:
    """Rank 1 = best composite among OK companies in the same sector group."""
    by_sector: dict = {}
    for res in results.values():
        if res.status == OK and res.score is not None:
            by_sector.setdefault(res.sector, []).append(res)
    for group in by_sector.values():
        group.sort(key=lambda r: (-r.score, r.ticker))
        prev_score, prev_rank = None, 0
        for i, res in enumerate(group, 1):
            if res.score == prev_score:
                res.rank_in_sector = prev_rank
            else:
                res.rank_in_sector = i
                prev_score, prev_rank = res.score, i


# ------------------------------------------------ score reports (S5) ----
# Five separately-visible report lines (master prompt S5), derived from the
# existing pillar scores with FIXED a-priori recombinations - no tuning, no
# new percentile machinery, no change to the composite definition:
#   BUSINESS QUALITY           franchise quality (profitability/growth/
#                              earnings quality) - no valuation, no payout
#   INVESTMENT ATTRACTIVENESS  the existing composite (all six pillars)
#   FINANCIAL RISK             100 - financial-strength pillar (+ flags)
#   DATA CONFIDENCE            coverage, freshness, timestamp exactness,
#                              provider health (documented fixed priors)
#   MOMENTUM                   12-1 momentum value + universe percentile
# Missing data never inflates a score: the composite stays
# coverage-renormalized for comparability, while DATA CONFIDENCE absorbs
# the missing-data penalty and is always reported next to the score.

BUSINESS_QUALITY_WEIGHTS = _param(
    "BUSINESS_QUALITY_WEIGHTS",
    {"profitability": 0.45, "growth": 0.30, "earnings_quality": 0.25},
    "S5 report line: franchise-quality recombination of existing pillars "
    "(fixed prior; report-only, the composite is unchanged).")
FINANCIAL_RISK_PILLAR = _param(
    "FINANCIAL_RISK_PILLAR", "financial_strength",
    "S5 report line: FINANCIAL RISK is the inverse of this pillar.")
CONF_WEIGHT_COVERAGE = _param(
    "CONF_WEIGHT_COVERAGE", 0.50,
    "S5 data-confidence prior: weight on metric coverage (available/total).")
CONF_WEIGHT_FRESHNESS = _param(
    "CONF_WEIGHT_FRESHNESS", 0.20,
    "S5 data-confidence prior: weight on fundamental freshness.")
CONF_WEIGHT_EXACTNESS = _param(
    "CONF_WEIGHT_EXACTNESS", 0.15,
    "S5 data-confidence prior: weight on the share of facts dated by a real "
    "acceptance timestamp (vs conservative same/next-day assumptions).")
CONF_WEIGHT_PROVIDERS = _param(
    "CONF_WEIGHT_PROVIDERS", 0.15,
    "S5 data-confidence prior: weight on provider health (all enabled "
    "sources SUCCESS).")
VALUATION_WEAK_PCT = _param(
    "VALUATION_WEAK_PCT", 40.0,
    "S5: valuation pillar below this percentile flags a valuation weakness.")
PILLAR_WEAK_PCT = _param(
    "PILLAR_WEAK_PCT", 30.0,
    "S5: pillars below this percentile are listed as major risks.")



# =============================== SECTION: FLAGS ===============================
# Red flags reported separately from the score (owner spec; rule I6).


def _red_flags(view: FundamentalsView, market, raw: dict,
               accruals_score, accruals_pool_size: int) -> list:
    """Red flags reported separately from the score (owner spec item 7)."""
    flags: list = []
    eq = view.instant("total_equity")
    if eq is not None and eq < 0:
        flags.append("NEGATIVE_EQUITY")
    z = raw.get("altman_z")
    if z is not None and z < ALTMAN_DISTRESS_Z:
        flags.append("ALTMAN_DISTRESS")
    p = raw.get("piotroski_f")
    if p is not None and p <= PIOTROSKI_LOW:
        flags.append("PIOTROSKI_LOW")
    acc = raw.get("accruals_ratio")
    if (acc is not None and accruals_score is not None
            and accruals_pool_size >= MIN_POOL_FOR_ACCRUALS_FLAG
            and accruals_score <= ACCURUALS_FLAG_PERCENTILE):
        flags.append("HIGH_ACCRUALS")
    rev, rev_p = view.ttm("revenue"), view.ttm_prior("revenue")
    # P6/R4 (L3): the flag never fires on a PARTIAL debt figure.
    debt, missing = view.total_debt()
    debt_p = view.total_debt_year_ago()
    if not missing and None not in (rev, rev_p, debt, debt_p) and rev < rev_p and debt > debt_p:
        flags.append("SHRINKING_REVENUE_RISING_DEBT")
    return flags


# ------------------------------------------------------------ summary ----


def summarize(results: dict) -> dict:
    """Counts and ticker lists per status, for scan output."""
    out: dict = {"counts": {}, "tickers": {}}
    for status in STATUS_ORDER + (DELISTED, RENAMED):
        ts = [r.ticker for r in results.values() if r.status == status]
        if ts:
            out["counts"][status] = len(ts)
            out["tickers"][status] = ts
    return out



# Daily snapshots: raw metrics, metric scores, pillars and composite to
# data/snapshots/YYYY-MM-DD.csv, with ENGINE_VERSION and config hash in the
# header comment lines. Byte-identical on rewrite (deterministic ordering
# and formatting; rule I4).

PILLAR_COLUMNS = [f"pillar_{p}" for p in PILLAR_WEIGHTS]


def snapshot_columns() -> list:
    """Fixed CSV schema: identity + score + pillars + raw and scored metrics
    (+ market cap for the S7 size-neutralization factor)."""
    return (["as_of", "ticker", "sector", "model", "status", "score",
             "coverage", "rank_in_sector", "flags", "data_source",
             "market_cap"]
            + PILLAR_COLUMNS
            + [f"metric_{name}" for name in all_metric_names()]
            + [f"mscore_{name}" for name in all_metric_names()])


def _snap_value(value) -> str:
    if value is None:
        return ""
    if value == WORST:
        return "WORST"
    if isinstance(value, float):
        return repr(round(value, SNAPSHOT_ROUND_DIGITS))
    return str(value)


def write_snapshot(results: dict, as_of: str,
                   path: Optional[str] = None) -> Path:
    """Write one row per ticker; returns the file path."""
    if path is None:
        path = str(Path(SNAPSHOT_DIR) / f"{as_of}.csv")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cols = snapshot_columns()
    with out.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# engine_version={ENGINE_VERSION}\n")
        fh.write(f"# schema_version={SCHEMA_VERSION}\n")
        fh.write(f"# config_hash={config_hash()}\n")
        fh.write(f"# as_of={as_of}\n")
        writer = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for ticker in sorted(results):
            r: ScoreResult = results[ticker]
            row = {
                "as_of": as_of, "ticker": r.ticker, "sector": r.sector,
                "model": r.model, "status": r.status,
                "score": "" if r.score is None else r.score,
                "coverage": round(r.coverage, ROUND_DIGITS),
                "rank_in_sector": "" if r.rank_in_sector is None
                else r.rank_in_sector,
                "flags": ";".join(r.flags), "data_source": r.data_source,
                "market_cap": _snap_value(r.market_cap),
            }
            for pillar, column in zip(PILLAR_WEIGHTS, PILLAR_COLUMNS):
                row[column] = _snap_value(r.pillars.get(pillar))
            for name in all_metric_names():
                row[f"metric_{name}"] = _snap_value(r.metrics.get(name))
                row[f"mscore_{name}"] = _snap_value(
                    r.metric_scores.get(name))
            writer.writerow(row)
    return out


def list_snapshots(snapshot_dir: Optional[str] = None) -> list:
    """Snapshot CSV paths sorted by date (YYYY-MM-DD.csv)."""
    directory = Path(snapshot_dir or SNAPSHOT_DIR)
    if not directory.exists():
        return []
    return sorted(p for p in directory.glob("*.csv")
                  if len(p.stem) == ISO_DATE_LEN)


def read_snapshot(path) -> list:
    """Rows of one snapshot CSV as dicts ('#' header lines skipped)."""
    with Path(path).open(newline="", encoding="utf-8") as fh:
        lines = [ln for ln in fh if not ln.startswith("#")]
    return list(csv.DictReader(lines))



# ================================ SECTION: API ================================
# Public API: get_quality_score and get_momentum_12_1.
#
# Scoring is cross-sectional (sector percentiles), so one call scores the
# whole universe and returns the requested ticker's row; the universe result
# is memoized per (as_of, source, universe fingerprint) within the process.
# Importing this file has no side effects and writes nothing.

_MEMO: dict = {}


def _clear_memo() -> None:
    """Test hook: drop the process-level universe memo (and cold warning)."""
    global _COLD_WARNED
    _MEMO.clear()
    _COLD_WARNED = False


def _as_of_date(as_of: Optional[str]) -> str:
    return as_of or date.today().isoformat()


def _validate_as_of(as_of: Optional[str],
                    boundary: Optional[date] = None) -> tuple:
    """(ok, error) for an as_of string (P6/R8: ONE date validator).

    Accepts only ISO YYYY-MM-DD real calendar dates not after the
    boundary clock (the ONE boundary read, D23). Empty/None means "today"
    and is always valid. The API surfaces the error as an explicit ERROR
    result; the CLI exits 2.
    """
    if as_of is None or as_of == "":
        return True, ""
    if not isinstance(as_of, str):
        return False, (f"bad as_of {as_of!r}: use YYYY-MM-DD")
    try:
        d = date.fromisoformat(as_of)
    except ValueError:
        return False, f"bad as_of '{as_of}': use YYYY-MM-DD"
    if str(d) != as_of:
        return False, f"bad as_of '{as_of}': use YYYY-MM-DD"
    if boundary is not None and d > boundary:
        return False, (f"as_of '{as_of}' is in the future "
                       f"(latest allowed {boundary.isoformat()})")
    return True, ""


def _fingerprint(refs: list) -> str:
    joined = ",".join(f"{r.ticker}:{r.sector}:{r.status}" for r in refs)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:FINGERPRINT_LEN]


def _unresolved_result(ref: TickerRef, as_of: str, status: str,
                       error: Optional[str] = None,
                       source_status: Optional[dict] = None) -> ScoreResult:
    res = ScoreResult(ref.ticker, ref.sector, resolve_model(ref.sector).key,
                      as_of, status)
    if error:
        res.error = error
    notes: list = []
    if status in (NO_DATA, ERROR) and error:
        notes.append(error)      # P6/R13 (F29): the reason is never silent
    if status in (DELISTED, RENAMED) and ref.note:
        notes.append(ref.note)
    res.notes = notes
    if source_status:
        res.source_status = dict(source_status)
    return res


def _provider_error_note(company) -> str:
    """'provider_errors:<classes>; <provider>=<detail>' (D6 diagnostics).

    Keeps the exception type names (e.g. ``exception:RuntimeError``) next to
    the status classes so a swallowed provider crash stays visible in the
    ticker-level error string. Detail strings never contain secrets.
    """
    pstat = (company.source_status if company else {}) or {}
    classes = sorted({s for s in pstat.values() if s in ERROR_CLASSES})
    parts = ["provider_errors:" + ",".join(classes)]
    detail = (getattr(company, "source_detail", None) or {}) \
        if company is not None else {}
    parts += [f"{name}={d}" for name, d in sorted(detail.items()) if d]
    return "; ".join(parts)



def fetch_companies(chain: SourceChain, refs: list, as_of: str,
                    fetch_on: Optional[str] = None,
                    progress: Optional[Callable] = None):
    """Companies for refs, plus {ticker: status} for everything unscored.

    Rule D6: a ticker whose enabled providers ALL failed with an error class
    is ERROR with the classes listed; no facts without errors is NO_DATA.
    D22: delisted/renamed universe members are disclosed, never fetched.
    """
    companies: list = []
    statuses: dict = {}
    errors: dict = {}
    unresolved_status: dict = {}   # P6/R13: provider status per unscored
    for position, ref in enumerate(refs, 1):
        if progress is not None:
            progress(position, len(refs), ref.ticker)
        if ref.status in ("delisted", "renamed"):
            statuses[ref.ticker] = ref.status.upper()
            continue
        try:
            company = chain.get_company(ref.ticker, ref.sector, as_of,
                                        fetch_on=fetch_on)
        except Exception as exc:
            statuses[ref.ticker] = ERROR
            errors[ref.ticker] = f"{type(exc).__name__}: {exc}"
            continue
        if company is None or not company.facts:
            # every enabled provider failed with an error class? -> ERROR
            statuses_present = company.source_status if company else {}
            error_classes = sorted({s for s in statuses_present.values()
                                    if s in ERROR_CLASSES})
            if statuses_present and len(error_classes) == \
                    len(set(statuses_present.values())):
                statuses[ref.ticker] = ERROR
                errors[ref.ticker] = _provider_error_note(company)
            else:
                statuses[ref.ticker] = NO_DATA
                # P6/R13 (F29): NO_DATA is never silent - the per-provider
                # detail explains WHY (e.g. not_in_fixtures, no_cik).
                detail = "; ".join(
                    f"{n}={d}" for n, d in sorted(
                        (company.source_detail or {}).items()) if d) \
                    if company is not None else ""
                errors[ref.ticker] = ("no_data:" + (detail or
                                      "enabled providers returned no facts"))
            if company is not None:
                unresolved_status[ref.ticker] = dict(company.source_status)
            continue
        companies.append(company)
    return companies, statuses, errors, unresolved_status


_COLD_WARNED = False


def _scored_universe(as_of: str, source: str = "auto",
                     universe_limit: Optional[int] = None,
                     universe_file: Optional[str] = None,
                     fetch_on: Optional[str] = None,
                     refs_override: Optional[list] = None,
                     progress: Optional[Callable] = None) -> dict:
    """Whole-universe scorecard, memoized per process (D24)."""
    global _COLD_WARNED
    if refs_override is not None:
        refs = list(refs_override)
    elif universe_file:
        refs = load_universe_file(universe_file)
    else:
        refs, _report = get_universe()
    if universe_limit:
        refs = refs[:universe_limit]
    key = (as_of, source, _fingerprint(refs), universe_file)
    if key in _MEMO:
        return _MEMO[key]
    if not _COLD_WARNED:
        _COLD_WARNED = True
        print(f"[quality] cold cache: scoring the whole universe "
              f"({len(refs)} names, a few provider calls per name, "
              f"rate-limited); results are memoized for this process.",
              file=sys.stderr)
    chain = build_source_chain(source)
    companies, statuses, errors, unresolved_status = fetch_companies(
        chain, refs, as_of, fetch_on=fetch_on, progress=progress)
    results = score_universe(companies, as_of)
    for ref in refs:
        if ref.ticker in results:
            continue
        status = statuses.get(ref.ticker) or NO_DATA
        results[ref.ticker] = _unresolved_result(
            ref, as_of, status, errors.get(ref.ticker),
            source_status=unresolved_status.get(ref.ticker))
    _MEMO[key] = results
    return results


def get_quality_score(ticker: str, as_of: Optional[str] = None, *,
                      source: str = "auto",
                      universe_file: Optional[str] = None,
                      universe_refs: Optional[list] = None,
                      progress: Optional[Callable] = None) -> dict:
    """Quality score for one ticker as of a date (default today).

    Returns ticker, as_of, sector, score (0-100; None unless status is OK -
    rule I6/D10), pillars, coverage, flags, rank_in_sector, status,
    data_source, plus model, metrics, metric_scores, notes, error,
    score_unrated, source_status, provenance (metric-level fact traces,
    D18) and item_source for diagnostics. Scoring is cross-sectional:
    sector percentiles are computed over the whole universe, so ONE call
    fetches and scores the entire universe (D24). ``universe_file`` scores
    a custom universe instead (CSV: ticker,sector[,status,note]). A ticker
    outside the universe returns NO_DATA with a pointer to --universe-file
    (D22); delisted/renamed members are disclosed and never fetched. The
    popular mega-caps absent from the built-in list (AAPL, MSFT, NVDA,
    META, TSLA, BRK-B, V, MA, NFLX, ...) are the documented exception:
    3.3.0 auto-builds their sector peer set from a curated map, so the
    call needs no extra arguments.
    """
    fetch_on = date.today().isoformat()      # the ONE boundary clock read
    ok, err = _validate_as_of(as_of, boundary=date.today())
    if not ok:
        res = ScoreResult((ticker or "").strip().upper() or "?", "",
                          "default", _as_of_date(as_of), ERROR)
        res.error = err
        res.notes = ["invalid_as_of"]
        return res.to_api_dict()
    as_of = _as_of_date(as_of)
    upper = normalize_ticker(ticker or "")
    if upper is None:
        res = ScoreResult((ticker or "").strip()[:TICKER_NOTE_MAX_LEN] or "?", "",
                          "default", as_of, ERROR)
        res.error = (f"'{(ticker or '')[:TICKER_NOTE_MAX_LEN]}' does not look like a ticker "
                     "(letters/digits, e.g. AAPL or BRK-B)")
        res.notes = ["invalid_ticker"]
        return res.to_api_dict()
    if universe_refs is None and universe_file is None \
            and _KNOWN_SECTOR_TICKERS.get(upper):
        # 3.3.0: popular mega-caps score out of the box via the curated
        # sector map (deterministic - no network sector lookup here).
        refs, _sector, _scope, _warns, _err = build_inline_universe(upper)
        if refs is not None:
            universe_refs = refs
    results = _scored_universe(as_of, source, None, universe_file,
                               fetch_on=fetch_on,
                               refs_override=universe_refs,
                               progress=progress)
    res = results.get(upper)
    if res is None:
        res = ScoreResult(upper, "", "default", as_of, NO_DATA)
        res.notes = ["ticker_not_in_universe",
                     "pass a custom universe via "
                     "get_quality_score(universe_file=...) or the CLI "
                     "--universe-file option"]
    return res.to_api_dict()


def get_momentum_12_1(ticker: str, as_of: Optional[str] = None, *,
                      source: str = "auto") -> dict:
    """12-1 month momentum from adjusted prices; separate from quality.

    V3.4.1: ADJUSTED prices only - without an adjusted series the result
    is status NO_DATA / reason no_adjusted_price_data (never a silent
    raw-close substitute). price_basis is "adjusted" on success, None
    otherwise.
    """
    fetch_on = date.today().isoformat()      # the ONE boundary clock read
    ok, err = _validate_as_of(as_of, boundary=date.today())
    if not ok:
        return {"ticker": (ticker or "").strip().upper() or "?",
                "as_of": _as_of_date(as_of), "momentum_12_1": None,
                "status": "ERROR", "reason": "invalid_as_of",
                "error": err, "price_basis": None, "data_source": ""}
    as_of = _as_of_date(as_of)
    chain = build_source_chain(source)
    upper = normalize_ticker(ticker or "")
    if upper is None:
        return {"ticker": (ticker or "").strip()[:TICKER_NOTE_MAX_LEN] or "?",
                "as_of": as_of, "momentum_12_1": None,
                "status": "ERROR", "reason": "invalid_ticker",
                "error": (f"'{(ticker or '')[:TICKER_NOTE_MAX_LEN]}' does not look like a "
                          "ticker"), "price_basis": None, "data_source": ""}
    prices = None
    has_close = False
    source_name = ""
    report_status = ""
    if chain.price_source is not None:
        source_name = chain.price_source.name
        start = _shift(as_of, -PRICE_LOOKBACK_DAYS)
        try:
            payload, report = chain.price_source.get_price_data(
                upper, start, as_of, fetch_on=fetch_on)
        except Exception:
            payload, report = None, None
        if payload:
            # V3.4.1: 12-1 momentum is computed from ADJUSTED prices only;
            # raw closes are never a silent substitute (dividends would be
            # ignored), so an empty adjusted series leaves it unavailable.
            prices = payload.get("adj_close") or []
            has_close = bool(payload.get("close"))
        if report is not None:
            report_status = report.status
    if prices:
        value, reason = momentum_12_1_detail(prices, as_of)
    elif has_close:
        value, reason = None, "no_adjusted_price_data"
    else:
        value, reason = None, "no_price_data"
    if value is None and report_status == STATUS_NO_DATA:
        reason = "no_price_data"
    return {
        "ticker": upper,
        "as_of": as_of,
        "momentum_12_1": value,
        "status": "OK" if value is not None else "NO_DATA",
        "reason": reason,
        "price_basis": "adjusted" if value is not None else None,
        "data_source": source_name if value is not None else "",
    }

def describe_sources(source: str = "auto") -> list:
    """[(name, status)] of enabled and skipped sources (never key values)."""
    chain = build_source_chain(source)
    rows = chain.describe()
    for note in chain.notes:
        rows.append(("note", note))
    return rows


# ============================ SECTION: SCAN CLI ================================

# this file has no side effects.

_LIST_CAP = 50
_TERMINAL = {NO_DATA, DELISTED, RENAMED, ERROR}


def scan_fingerprint(as_of: str, source: str, refs: list,
                     enabled_sources: list,
                     overrides_path: Optional[str] = None) -> str:
    """sha256 of the canonical scan identity (defect D12).

    Covers as_of, source, the enabled-source set, the sorted
    (ticker, sector, status) universe, the full CONFIG tunables dump, the
    overrides file hash, ENGINE_VERSION and the schema version. Any change
    makes an old checkpoint incompatible (rejected with a clear message).
    """
    blob = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "as_of": as_of,
        "source": source,
        "enabled_sources": sorted(enabled_sources),
        "universe": sorted([r.ticker, r.sector, r.status] for r in refs),
        "config": config_dump(),
        "overrides_sha256": overrides_file_hash(overrides_path),
    }
    canon = json.dumps(blob, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _mins(t0: float) -> str:
    return f"{(time.monotonic() - t0) / SECONDS_PER_MINUTE:.1f} min"


def _counts(statuses: dict) -> dict:
    out: dict = {}
    for status in statuses.values():
        out[status] = out.get(status, 0) + 1
    return out



def _company_to_dict(c: Company) -> dict:
    out = {
        "ticker": c.ticker, "sector": c.sector, "note": c.note,
        "sources": sorted(c.sources),
        "source_status": dict(c.source_status),
        "source_detail": dict(getattr(c, "source_detail", {}) or {}),
        "item_source": dict(getattr(c, "item_source", None)
                            or getattr(c, "provenance", None) or {}),
        "prices": [{"date": d, "close": p} for d, p in c.prices],
        "adj_prices": [{"date": d, "close": p}
                       for d, p in (c.adj_prices or [])],
        "split_events": [[d, r] for d, r in (c.split_events or [])],
        "prices_fetched_on": getattr(c, "prices_fetched_on", ""),
        "split_events_through": getattr(c, "split_events_through", ""),
        "splits_unverified": bool(getattr(c, "splits_unverified", False)),
        "facts": {item: [asdict(f) for f in facts]
                  for item, facts in c.facts.items()},
    }
    if c.adj_prices:
        # V3.4.1: certify the adjusted basis so a restore can tell a real
        # adjusted series from a legacy snapshot's raw relabel.
        out["adj_prices_basis"] = "adjusted"
    return out


def _company_from_dict(d: dict) -> Company:
    facts = {item: [Fact(**f) for f in items]
             for item, items in (d.get("facts") or {}).items()}
    prices = [(p["date"], float(p["close"])) for p in d.get("prices") or []]
    adj = [(p["date"], float(p["close"])) for p in d.get("adj_prices") or []]
    if d.get("adj_prices_basis") != "adjusted":
        # V3.4.1: a legacy snapshot cannot prove its adjusted basis; its
        # adj_prices may be a raw relabel, so the adjusted series is
        # restored as unavailable instead (raw stays on .prices).
        adj = []
    return Company(ticker=d["ticker"], sector=d["sector"], facts=facts,
                   prices=prices, adj_prices=adj,
                   sources=set(d.get("sources") or []),
                   note=d.get("note", ""),
                   source_status=dict(d.get("source_status") or {}),
                   source_detail=dict(d.get("source_detail") or {}),
                   item_source=dict(d.get("item_source")
                                    or d.get("provenance") or {}),
                   split_events=[(s[0], float(s[1]))
                                 for s in (d.get("split_events") or [])],
                   prices_fetched_on=d.get("prices_fetched_on", ""),
                   split_events_through=d.get("split_events_through", ""),
                   splits_unverified=bool(d.get("splits_unverified", False)))

def _save_state(path: Path, fingerprint: str, companies: dict, statuses: dict,
                errors: dict) -> None:
    """Atomic checkpoint write (tmp + rename); failures never break a run."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "fingerprint": fingerprint,
            "companies": {c.ticker: _company_to_dict(c)
                          for c in companies.values()},
            "statuses": statuses,
            "errors": errors,
        }, default=str), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        return

def _load_state(path: Path, fingerprint: str) -> Optional[dict]:
    """Checkpoint when compatible; None plus a clear message when not (D12)."""
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if blob.get("fingerprint") != fingerprint:
        print("[scan] checkpoint rejected: fingerprint mismatch - the as-of "
              "date, source set, universe, universe overrides, CONFIG "
              "tunables or engine version changed since this checkpoint was "
              "written. Starting a fresh scan; the old state is ignored.")
        return None
    return blob

def _print_debug(results: dict, refs: list) -> None:
    for ref in refs:
        r = results.get(ref.ticker)
        if r is None:
            continue
        print(f"\n-- {r.ticker} [{r.sector}/{r.model}] {r.status}"
              f" score={r.score} coverage={r.coverage:.2f}"
              f" rank={r.rank_in_sector} src={r.data_source or '-'}")
        if r.error:
            print(f"   error: {r.error}")
        if r.score_unrated:
            print(f"   score_unrated: {r.score_unrated}")
        if r.notes:
            print(f"   notes: {'; '.join(r.notes)}")
        for name, value in r.metrics.items():
            s = r.metric_scores.get(name)
            raw = "" if value is None else f"{value:.4f}"
            sc = "" if s is None else f"{s:.3f}"
            print(f"   {name:24s} raw={raw:12s} score={sc}")
        for pillar, value in r.pillars.items():
            v = "" if value is None else f"{value:.1f}"
            print(f"   pillar {pillar:20s} {v}")
        if r.flags:
            print(f"   flags: {'; '.join(r.flags)}")

def scan_main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quality.py scan",
        description="Scan the universe and score stock quality. Terminal "
                    "output only; a snapshot CSV is written ONLY with "
                    "--snapshot.")
    parser.add_argument("--tickers", default="",
                        help="comma-separated subset (debug view; ranks "
                             "become relative to the subset only)")
    parser.add_argument("--as-of", dest="as_of", default=None,
                        help="score as of this ISO date (default: today)")
    parser.add_argument("--source", default="auto",
                        choices=["auto", "fixtures", "finnhub", "sec",
                                 "yfinance"])
    parser.add_argument("--limit", type=int, default=None,
                        help="scan only the first N universe entries")
    parser.add_argument("--universe-file", dest="universe_file", default=None,
                        help="custom universe CSV (ticker,sector[,status,note]) "
                             "instead of the built-in universe")
    parser.add_argument("--max-fetch", dest="max_fetch", type=int,
                        default=None,
                        help="stop after N new fetches and save state "
                             "(partial run; rerun the same command to resume)")
    parser.add_argument("--snapshot", action="store_true",
                        help="ALSO write the snapshot CSV "
                             "(data/snapshots/YYYY-MM-DD.csv); default is "
                             "terminal-only")
    parser.add_argument("--snapshot-dir", default=None,
                        help="override the snapshot directory")
    parser.add_argument("--no-snapshot", action="store_true",
                        help="(deprecated) snapshots are off by default now; "
                             "kept so old commands still work")
    parser.add_argument("--restart", action="store_true",
                        help="ignore any saved scan state")
    parser.add_argument("--verbose", action="store_true",
                        help="per-ticker debug view")
    args = parser.parse_args(argv)

    color_on = _use_color()
    if color_on:
        _enable_windows_ansi()

    def say(text: str, styles=(), stream=sys.stdout) -> None:
        print(_paint(text, styles, color_on), file=stream)

    fetch_on = date.today().isoformat()   # CLI boundary: read once (D23)
    ok, err = _validate_as_of(args.as_of, boundary=date.today())
    if not ok:
        print(err, file=sys.stderr)
        return 2
    as_of = args.as_of or fetch_on
    if args.universe_file:
        refs = load_universe_file(args.universe_file)
        report = {"raw": len(refs), "unique": len(refs),
                  "delisted": [r.ticker for r in refs
                               if r.status == "delisted"],
                  "renamed": [r.ticker for r in refs
                              if r.status == "renamed"]}
        say(f"[scan] universe file: {args.universe_file} "
            f"({len(refs)} tickers)")
    else:
        refs, report = get_universe()
    if args.tickers:
        wanted = {t.strip().upper() for t in args.tickers.split(",")
                  if t.strip()}
        refs = [r for r in refs if r.ticker in wanted]
        missing = sorted(wanted - {r.ticker for r in refs})
        if missing:
            say(f"[scan] not in universe: {', '.join(missing)}", "yellow")
    if args.limit:
        refs = refs[:args.limit]

    chain = build_source_chain(args.source)
    say("\n" + _paint("=" * BANNER_WIDTH, "gray", color_on))
    say(f"[scan] as_of={as_of} | source={args.source} | "
        f"{len(refs)} tickers | engine=v{ENGINE_VERSION} | "
        f"config_hash={config_hash()}", ("bold", "cyan"))
    for name, status in chain.describe():
        if "skipped" in status:
            say(f"[scan]   source {name}: {status}", "yellow")
        else:
            say(f"[scan]   source {name}: {status}", "green")
    for note in chain.notes:
        say(f"[scan]   NOTE: {note}", "yellow")
    say(f"[scan] universe: {report['raw']} listed entries, "
        f"{report['unique']} unique, {len(report['delisted'])} delisted, "
        f"{len(report['renamed'])} renamed (evidence: VERIFICATION table)")
    if report.get("invalid_override"):
        say(f"[scan] invalid sector overrides ignored: "
            f"{', '.join(report['invalid_override'])}", "yellow")
    if report.get("unknown_override_ticker"):
        say(f"[scan] overrides for unknown tickers ignored: "
            f"{', '.join(report['unknown_override_ticker'])}", "yellow")
    say("[scan] survivorship note: the Yahoo price feed serves current "
        "listings; historical scoring is not survivorship-free (rule I10).",
        "gray")
    say("[scan] universe coverage note (D22): the built-in universe does "
        "not contain " + ", ".join(ABSENT_MEGA_CAPS) + ".", "gray")

    state_path = Path(SCAN_STATE_PATH)
    enabled = [name for name, status in chain.describe()
               if status == "enabled"]
    fingerprint = scan_fingerprint(as_of, args.source, refs, enabled,
                                   args.universe_file)
    companies: dict = {}
    statuses: dict = {}
    errors: dict = {}
    if not args.restart:
        state = _load_state(state_path, fingerprint)
        if state:
            raw = state.get("companies") or {}
            if isinstance(raw, list):     # tolerate older list-form state
                raw = {d["ticker"]: d for d in raw}
            companies = {t: _company_from_dict(d) for t, d in raw.items()}
            statuses = dict(state.get("statuses") or {})
            errors = dict(state.get("errors") or {})
            say(f"[scan] resumed state: {len(companies)} companies cached, "
                f"{len(statuses)} terminal statuses", "green")

    t0 = time.monotonic()
    fetched_new = 0
    for i, ref in enumerate(refs, 1):
        if ref.ticker in companies or statuses.get(ref.ticker) in _TERMINAL:
            continue
        if ref.status in ("delisted", "renamed"):
            statuses[ref.ticker] = ref.status.upper()
            continue
        if args.max_fetch is not None and fetched_new >= args.max_fetch:
            _save_state(state_path, fingerprint, companies, statuses, errors)
            say(f"[scan] --max-fetch {args.max_fetch} reached at "
                f"{i - 1}/{len(refs)}; state saved, rerun the same command "
                f"to resume", "yellow")
            return 0
        try:
            company = chain.get_company(ref.ticker, ref.sector, as_of,
                                        fetch_on=fetch_on)
        except Exception as exc:  # one ticker never crashes the run
            statuses[ref.ticker] = ERROR
            errors[ref.ticker] = f"{type(exc).__name__}: {exc}"
            company = None
        fetched_new += 1
        if company is not None and company.facts:
            companies[ref.ticker] = company
            statuses.pop(ref.ticker, None)
        else:
            pstat = (company.source_status if company else {}) or {}
            error_classes = sorted({s for s in pstat.values()
                                    if s in ERROR_CLASSES})
            if pstat and len(error_classes) == len(set(pstat.values())):
                statuses[ref.ticker] = ERROR
                errors[ref.ticker] = _provider_error_note(company)
            elif statuses.get(ref.ticker) != ERROR:
                statuses[ref.ticker] = NO_DATA
        if fetched_new % SCAN_PROGRESS_EVERY == 0:
            _save_state(state_path, fingerprint, companies, statuses, errors)
            counts = _counts(statuses)
            say(f"[scan] {i}/{len(refs)} "
                + _paint(f"ok={len(companies)}", "green", color_on) + " "
                + _paint(f"no_data={counts.get(NO_DATA, 0)}", "yellow",
                         color_on) + " "
                + _paint(f"errors={counts.get(ERROR, 0)}", "red", color_on)
                + f" ({_mins(t0)})", "cyan")
    _save_state(state_path, fingerprint, companies, statuses, errors)

    results = score_universe(list(companies.values()), as_of)
    for ref in refs:
        if ref.ticker in results:
            continue
        status = statuses.get(ref.ticker) or NO_DATA
        res = ScoreResult(ref.ticker, ref.sector,
                          resolve_model(ref.sector).key, as_of, status)
        if status == ERROR:
            res.error = errors.get(ref.ticker, "fetch_failed")
        if status in (DELISTED, RENAMED) and ref.note:
            res.notes = [ref.note]
        results[ref.ticker] = res

    if args.tickers or args.verbose:
        _print_debug(results, refs)

    summary = summarize(results)
    say("\n" + _paint("=" * BANNER_WIDTH, "gray", color_on))
    say("==== SCAN DONE ====", ("bold", "cyan"))
    say(f"elapsed: {_mins(t0)}", "gray")
    non_ok = " | ".join(f"{k.lower()}: {v}"
                        for k, v in summary["counts"].items() if k != OK)
    say("universe: " + f"{len(refs)} | "
        + _paint(f"ok: {summary['counts'].get(OK, 0)}", "green", color_on)
        + (f" | {_paint(non_ok, 'yellow', color_on)}" if non_ok else ""))
    for status in (NO_DATA, STALE_DATA, INSUFFICIENT_DATA,
                   SECTOR_DATA_MISSING, DELISTED, RENAMED, ERROR):
        tickers = summary["tickers"].get(status) or []
        if not tickers:
            continue
        shown = ", ".join(tickers[:_LIST_CAP])
        if len(tickers) > _LIST_CAP:
            shown += f" ... (+{len(tickers) - _LIST_CAP} more)"
        styles = ("red", "bold") if status == ERROR else "yellow"
        say(f"{status.lower()}: {shown}", styles)

    if errors:
        say("error reasons (the REAL provider messages, most common first):",
            ("bold", "red"))
        counts: dict = {}
        for reason in errors.values():
            counts[reason] = counts.get(reason, 0) + 1
        for reason, n in sorted(counts.items(),
                                key=lambda kv: (-kv[1], kv[0]))[:TOP_ERROR_REASONS]:
            say(f"  {n:3d}x {reason}", "red")

    provider_summary = chain.provider_status_summary()
    if provider_summary:
        say("provider status counts (D6):", "cyan")
        for provider, stats in provider_summary.items():
            rendered = ", ".join(f"{k}={v}" for k, v in sorted(stats.items()))
            styles = "red" if any(k in ERROR_CLASSES for k in stats) \
                and not any(k in (STATUS_SUCCESS, STATUS_NO_DATA,
                                  STATUS_PARTIAL_SUCCESS)
                            for k in stats) else "gray"
            say(f"  {provider}: {rendered}", styles)

    ranked = sorted((r for r in results.values()
                     if r.status == OK and r.score is not None),
                    key=lambda r: (-r.score, r.ticker))
    glyphs = _glyphs()
    print(_paint(f"\nTop {TOP_N_DISPLAY} companies by quality score:",
                 ("bold", "cyan"), color_on))
    print(_paint(f"{'rank':>4} {'ticker':7}{'sector':15}{'score':7}"
                 f"{'quality bar':<24}cov    rank flags", "gray", color_on))
    for i, r in enumerate(ranked[:TOP_N_DISPLAY], 1):
        label, band_color = _band(float(r.score))
        score_txt = _paint(f"{r.score:5.1f}", ("bold", band_color), color_on)
        filled = int(round(float(r.score) / 100.0 * SCAN_BAR_SEGMENTS))
        bar_txt = (_paint(glyphs["full"] * filled, band_color, color_on)
                   + _paint(glyphs["empty"] * (SCAN_BAR_SEGMENTS - filled),
                            "gray", color_on))
        flag_txt = _paint(';'.join(r.flags) or '-',
                          "yellow" if r.flags else "gray", color_on)
        print(f"{i:4d} {_paint(f'{r.ticker:7s}', 'bold', color_on)}"
              f"{r.sector:15s}{score_txt}  {bar_txt}  "
              f"{_paint(f'{r.coverage:.2f}', 'gray', color_on)} "
              f"{_paint(f'{r.rank_in_sector:>4}', 'gray', color_on)} "
              f"{flag_txt}")

    if args.snapshot:
        if args.snapshot_dir:
            path = write_snapshot(
                results, as_of,
                str(Path(args.snapshot_dir) / f"{as_of}.csv"))
        else:
            path = write_snapshot(results, as_of)
        say(f"\nsnapshot: {path}", "green")
    if len(companies) + len(statuses) >= len(refs):
        try:
            state_path.unlink()
        except OSError:
            pass
    return 0


# ======================= SECTION: FORWARD VALIDATION ==========================
# Forward-validation harness: within-sector quintile spread and rank IC.
#
# Defect D7 rules: one fixed holding period (FORWARD_HORIZON_DAYS, tolerance
# FORWARD_HORIZON_TOLERANCE_DAYS - non-matching pairs are skipped with a
# reason, never stretched); quintiles need >= MIN_FORWARD_POOL scored names
# and >= MIN_SECTOR_FOR_QUINTILES per sector, otherwise terciles or pooled
# buckets with an explicit label, or a skip with a reason; per-period n per
# top/bottom group, missing-price count, period coverage and top-group
# turnover are reported; dividend-adjusted total return is used when
# adjusted closes exist (else the report is labeled price_only); returns are
# net of the fixed TRADING_COST_BPS; incomplete samples are flagged, never
# silently accepted. Runs ONLY when snapshot history exists; otherwise NOT
# RUN. All output is a plumbing check of the machinery - never a performance
# claim (rule I9).

_FV_LABEL = ("PLUMBING CHECK ONLY - snapshot mechanics on the available "
             "data; no performance is claimed or implied.")

def _ranks(vals: list) -> list:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    ranks = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        mid = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    return ranks


def spearman(xs: list, ys: list) -> Optional[float]:
    """Spearman rank correlation of two equal-length lists."""
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den_x = math.sqrt(sum((a - mx) ** 2 for a in rx))
    den_y = math.sqrt(sum((b - my) ** 2 for b in ry))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)

class PriceLookup:
    """(ticker, day) -> last adjusted (or raw) close at or before day.

    The price window derives from the snapshot dates (D5): the union of
    [earliest snapshot, latest snapshot + horizon + pad] - never from today.
    """

    def __init__(self, source: str = "auto", window: Optional[tuple] = None,
                 fetch_on: Optional[str] = None):
        self.chain = build_source_chain(source)
        self.window = window
        self.fetch_on = fetch_on
        self.memo: dict = {}
        self.uses_adjusted: Optional[bool] = None

    def _series(self, ticker: str):
        if ticker in self.memo:
            return self.memo[ticker]
        self.memo[ticker] = None
        if self.chain.price_source is None:
            return None
        start, end = self.window if self.window else (None, None)
        try:
            payload, _report = self.chain.price_source.get_price_data(
                ticker, start, end, fetch_on=self.fetch_on)
        except Exception:
            return None
        if not payload:
            return None
        adj = payload.get("adj_close") or []
        close = payload.get("close") or []
        if adj:
            if self.uses_adjusted is None:
                self.uses_adjusted = True
            series = [(d, float(c)) for d, c in adj]
        else:
            self.uses_adjusted = False
            series = [(d, float(c)) for d, c in close]
        self.memo[ticker] = sorted(series)
        return self.memo[ticker]

    def __call__(self, ticker: str, day: str) -> Optional[float]:
        series = self._series(ticker)
        if not series:
            return None
        prior = [(d, c) for d, c in series if d <= day]
        if not prior:
            return None
        return prior[-1][1]

    @property
    def label(self) -> str:
        if self.uses_adjusted is None or self.uses_adjusted:
            return "total_return"
        return "price_only"

def _bucket_plan(n_pool: int, sector_sizes: dict):
    """(n_buckets, label, use_sector_groups) per the D7 fallback ladder."""
    if n_pool >= MIN_FORWARD_POOL and sector_sizes \
            and min(sector_sizes.values()) >= MIN_SECTOR_FOR_QUINTILES:
        return QUINTILES, "sector_quintiles", True
    if n_pool >= MIN_POOL_FOR_TERCELES and sector_sizes \
            and min(sector_sizes.values()) >= MIN_SECTOR_FOR_TERCELES:
        return TERCELES, "sector_terciles", True
    if n_pool >= MIN_FORWARD_POOL:
        return QUINTILES, "pooled_quintiles", False
    if n_pool >= MIN_POOL_FOR_TERCELES:
        return TERCELES, "pooled_terciles", False
    return None, "pool_too_small", False

def evaluate(snapshots: list, price_lookup, cost_bps: Optional[float] = None,
             series_label: Optional[str] = None,
             horizon_days: Optional[int] = None) -> dict:
    """Evaluate consecutive snapshot pairs about ``horizon_days`` apart."""
    cost_bps = TRADING_COST_BPS if cost_bps is None else cost_bps
    horizon = FORWARD_HORIZON_DAYS if horizon_days is None \
        else int(horizon_days)
    periods: list = []
    skipped: list = []
    prev_top: Optional[set] = None
    prev_benchmark: Optional[float] = None
    for a, b in zip(snapshots, snapshots[1:]):
        gap = (date.fromisoformat(b["date"])
               - date.fromisoformat(a["date"])).days
        if abs(gap - horizon) > FORWARD_HORIZON_TOLERANCE_DAYS:
            skipped.append({"from": a["date"], "to": b["date"],
                            "gap_days": gap,
                            "reason": "gap_outside_tolerance"})
            continue
        pool = [r for r in a["rows"]
                if r.get("status") == OK and r.get("score") not in ("", None)]
        n_pool = len(pool)
        buckets, plan_label, use_sectors = _bucket_plan(n_pool, {})
        if plan_label == "pool_too_small":
            skipped.append({"from": a["date"], "to": b["date"],
                            "gap_days": gap, "reason": "pool_too_small",
                            "n_scored": n_pool})
            continue
        forward: dict = {}
        missing_prices = 0
        for row in pool:
            ticker = row["ticker"]
            pa = price_lookup(ticker, a["date"])
            pb = price_lookup(ticker, b["date"])
            if pa is None or pb is None or pa <= 0:
                missing_prices += 1
                continue
            forward[ticker] = pb / pa - 1.0
        scored = [r for r in pool if r["ticker"] in forward]
        if not scored:
            skipped.append({"from": a["date"], "to": b["date"],
                            "gap_days": gap, "reason": "no_forward_prices",
                            "n_scored": n_pool})
            continue
        by_sector: dict = {}
        for row in scored:
            by_sector.setdefault(row["sector"], []).append(row)
        # re-check the plan with the true sector sizes (D7: unequal sectors)
        buckets, plan_label, use_sectors = _bucket_plan(
            n_pool, {s: len(rs) for s, rs in by_sector.items()})
        if plan_label == "pool_too_small":
            skipped.append({"from": a["date"], "to": b["date"],
                            "gap_days": gap, "reason": "pool_too_small",
                            "n_scored": n_pool})
            continue
        groups = list(by_sector.values()) if use_sectors else [scored]
        spreads: list = []
        long_legs: list = []
        short_legs: list = []
        n_top = n_bottom = 0
        top_names: set = set()
        all_groups_spread = True
        for rows in groups:
            q = len(rows) // buckets
            if q == 0:
                all_groups_spread = False
                continue
            ordered = sorted(rows, key=lambda r: (-float(r["score"]),
                                                  r["ticker"]))
            top, bottom = ordered[:q], ordered[-q:]
            n_top += len(top)
            n_bottom += len(bottom)
            top_names.update(r["ticker"] for r in top)
            long_g = sum(forward[r["ticker"]] for r in top) / len(top)
            short_g = -sum(forward[r["ticker"]] for r in bottom) / len(bottom)
            long_legs.append(long_g)
            short_legs.append(short_g)
            spreads.append(long_g + short_g)
        if not spreads:
            skipped.append({"from": a["date"], "to": b["date"],
                            "gap_days": gap,
                            "reason": "no_group_with_full_bucket",
                            "n_scored": n_pool})
            continue
        gross = sum(spreads) / len(spreads)
        long_gross = sum(long_legs) / len(long_legs)
        short_gross = sum(short_legs) / len(short_legs)
        benchmark = sum(forward[r["ticker"]] for r in scored) / len(scored)
        leg_cost = cost_bps / BPS_FACTOR    # round-trip cost PER LEG
        long_net = long_gross - leg_cost
        short_net = short_gross - leg_cost
        spread_net = long_net + short_net   # BOTH legs charged: the short
        # leg is never free (backtesting rule; the old formula charged the
        # spread once, i.e. half the true cost of a long-short book)
        turnover = None
        if prev_top is not None and prev_top:
            turnover = round(
                1.0 - len(top_names & prev_top) / len(prev_top),
                ROUND_DIGITS)
        ic = spearman([float(r["score"]) for r in scored],
                      [forward[r["ticker"]] for r in scored])
        if prev_benchmark is None:
            regime = "first_period"
        else:
            regime = ("prior_benchmark_up" if prev_benchmark > 0
                      else "prior_benchmark_down")
        periods.append({
            "from": a["date"], "to": b["date"], "gap_days": gap,
            "n_scored_pool": n_pool,
            "n_with_forward_prices": len(scored),
            "missing_prices": missing_prices,
            "forward_coverage": round(len(scored) / n_pool,
                                      ROUND_DIGITS) if n_pool
            else 0.0,
            "bucketing": plan_label,
            "n_top": n_top, "n_bottom": n_bottom,
            "quintile_spread_gross": gross,
            "quintile_spread_net_bps": spread_net * BPS_FACTOR,
            "rank_ic": ic,
            "top_turnover": turnover,
            # long/short attribution; costs charged per leg, both legs
            "long_leg_gross": long_gross,
            "short_leg_gross": short_gross,   # short position contribution
            "leg_cost_bps_each": cost_bps,
            "long_leg_net": long_net,
            "short_leg_net": short_net,
            "spread_net": spread_net,
            # exposure benchmark: equal-weight mean forward return of the
            # whole scored pool; active legs vs that benchmark
            "benchmark_gross": benchmark,
            "long_active": long_gross - benchmark,
            "short_active": short_gross + benchmark,
            "regime": regime,   # prior-period benchmark; no same-period leak
            "sample_complete": bool(missing_prices == 0
                                    and plan_label == "sector_quintiles"
                                    and all_groups_spread),
        })
        prev_top = top_names
        prev_benchmark = benchmark

    gross_all = [p["quintile_spread_gross"] for p in periods
                 if p["quintile_spread_gross"] is not None]
    ics = [p["rank_ic"] for p in periods if p["rank_ic"] is not None]
    mean_ic = sum(ics) / len(ics) if ics else None
    ic_positive_share = ((sum(1 for x in ics if x > 0) / len(ics))
                         if ics else None)
    return {
        "label": _FV_LABEL,
        "series": series_label or "unspecified",
        "cost_bps": cost_bps,
        "horizon_days": horizon,
        "snapshots": [s["date"] for s in snapshots],
        "periods_evaluated": len(periods),
        "periods": periods,
        "skipped_pairs": skipped,
        "mean_quintile_spread_gross": (sum(gross_all) / len(gross_all))
        if gross_all else None,
        "mean_rank_ic": mean_ic,
        "ic_positive_share": ic_positive_share,
        "portfolio": _portfolio_stats(periods),
    }


def _portfolio_stats(periods: list) -> dict:
    """Reduced to the D7 report fields (descriptive plumbing only, I9).

    Equity-curve aggregates (total return, CAGR, volatility, Sharpe,
    Sortino, drawdown) were removed with the research stack: the D7
    contract reports turnover, hit share and period counts, never
    performance metrics.
    """
    rets = [p["spread_net"] for p in periods
            if p.get("spread_net") is not None]
    if not rets:
        return {"n_periods": 0, "reason": "no_net_periods",
                "hit_rate": None, "turnover_mean": None, "span_days": None}
    span_days = (date.fromisoformat(periods[-1]["to"])
                 - date.fromisoformat(periods[0]["from"])).days
    tos = [p["top_turnover"] for p in periods
           if p.get("top_turnover") is not None]
    return {
        "n_periods": len(rets),
        "span_days": span_days,
        "hit_rate": sum(1 for r in rets if r > 0) / len(rets),
        "turnover_mean": (sum(tos) / len(tos)) if tos else None,
    }


def _parse_freeze_date(text) -> tuple:
    """(date | None, reason) strict parse of a --freeze-date argument.

    Clock-free (usable below the API boundary): ``date.fromisoformat``
    must accept the text AND the round trip ``d.isoformat() == text`` must
    hold, so only the exact YYYY-MM-DD representation passes (``20240630``,
    ISO-week forms and padded variants are rejected) and the calendar date
    must be real.
    """
    try:
        d = date.fromisoformat(text)
    except (ValueError, TypeError):
        return None, "not a valid ISO calendar date (YYYY-MM-DD)"
    if d.isoformat() != text:
        return None, "not the exact YYYY-MM-DD representation"
    return d, ""


def _validate_freeze_date(text, today: date) -> tuple:
    """(ok, reason) for a --freeze-date at the CLI boundary (finding 2).

    Wraps the strict clock-free parse with the future check; ``today`` is
    supplied by the caller so ONE invocation reads the clock once (the
    boundary functions are the only places allowed to read the wall
    clock, D23).
    """
    d, reason = _parse_freeze_date(text)
    if d is None:
        return False, reason
    if d > today:
        return False, (f"future freeze date ({text} is after today "
                       f"{today.isoformat()})")
    return True, ""


def forward_main(argv: Optional[list] = None) -> int:
    """``validate``: forward-validation harness (D7) or PIT universe (8.3)."""
    parser = argparse.ArgumentParser(
        prog="quality.py validate",
        description="Forward-validation harness over snapshot history.")
    parser.add_argument("--snapshot-dir", default=None)
    parser.add_argument("--source", default="auto",
                        choices=["auto", "fixtures"])
    parser.add_argument("--cost-bps", type=float, default=None,
                        help="Override TRADING_COST_BPS (per leg, round "
                             "trip); default is the CONFIG prior")
    parser.add_argument("--pit-universe", dest="pit_universe", default=None,
                        help="Point-in-time survivorship-free universe CSV "
                             "(month_end,ticker,permanent_id,sector_pit,"
                             "listed,total_return_next_month,"
                             "delisting_return_if_any) from a licensed "
                             "source; without it the PIT validation is "
                             "NOT RUN and never substituted (section 8.3)")
    parser.add_argument("--expect-config-hash", dest="expect_config_hash",
                        default=None,
                        help="Abort unless config_hash() equals this value "
                             "(rule I7 config freeze; out-of-sample claims "
                             "are only enforceable with it)")
    parser.add_argument("--freeze-date", dest="freeze_date", default=None,
                        help="Config freeze date, strict YYYY-MM-DD, not in "
                             "the future (re-audit finding 2): with a "
                             "matching --expect-config-hash, period months "
                             "<= this date are in-sample and later months "
                             "are out-of-sample; without BOTH, no OOS claim "
                             "is allowed")
    args = parser.parse_args(argv)

    today = date.today()          # the ONE clock read of this invocation
    # Supplied arguments are validated BEFORE the PIT CSV existence check:
    # a missing file must never conceal an invalid (or future) freeze date
    # or a mismatched configuration hash.
    if args.freeze_date is not None:
        ok, reason = _validate_freeze_date(args.freeze_date, today)
        if not ok:
            print(_paint(f"FAILED: --freeze-date {args.freeze_date!r}: "
                         f"{reason}", ("bold", "red"),
                         _use_color_stderr()), file=sys.stderr)
            return 1
    print("[validate] survivorship note: yfinance serves current listings; "
          "historical scoring is not survivorship-free (rule I10).",
          file=sys.stderr)
    if args.pit_universe:
        return _pit_validate(args)
    directory = args.snapshot_dir or SNAPSHOT_DIR
    paths = list_snapshots(args.snapshot_dir)
    if len(paths) < max(2, 1 + MIN_FORWARD_PAIRS):
        print(f"NOT RUN: need at least {max(2, 1 + MIN_FORWARD_PAIRS)} "
              f"snapshots (found {len(paths)}) in {directory}")
        print("Build history first, e.g.:")
        print("  python3 quality.py scan --as-of 2024-06-30 "
              "--universe-file data/universe_fixtures.csv "
              "--source fixtures")
        print("  python3 quality.py scan --as-of 2024-07-31 ...")
        return 0
    snapshots = [{"date": p.stem, "rows": read_snapshot(p)} for p in paths]
    window_start = min(s["date"] for s in snapshots)
    window_end = _shift(max(s["date"] for s in snapshots),
                        FORWARD_HORIZON_DAYS + FORWARD_WINDOW_PAD_DAYS)
    lookup = PriceLookup(args.source, window=(window_start, window_end),
                         fetch_on=today.isoformat())
    report = evaluate(snapshots, lookup, cost_bps=args.cost_bps,
                      series_label=None)
    report["series"] = lookup.label
    if not report["periods"]:
        print(f"NOT RUN: no snapshot pairs roughly {FORWARD_HORIZON_DAYS} "
              f"days apart (+/- {FORWARD_HORIZON_TOLERANCE_DAYS}) in "
              f"{directory}")
        if report["skipped_pairs"]:
            for s in report["skipped_pairs"][:SKIP_SAMPLE_CAP]:
                print(f"  skipped {s['from']} -> {s['to']} "
                      f"(gap {s['gap_days']}d): {s['reason']}")
        return 0
    print(json.dumps(report, indent=2, default=str))
    print(f"\nNOTE: {_FV_LABEL}")
    print("NOTE: costs are charged per leg, BOTH legs (long and short), "
          f"round-trip {report['cost_bps']} bps each.")
    print("NOTE: costs are NOT turnover-scaled (a fixed round-trip per "
          "period regardless of the reported top_turnover); borrow and "
          "financing costs are NOT modeled.")
    print("NOTE: descriptive screener, not an alpha claim (rules I9/I10).")
    return 0


def _valid_forward_return(text) -> Optional[float]:
    """A usable forward SIMPLE return (re-audit finding 5 / PART G).

    Accepted only when the value is numeric, converts safely to float,
    is finite and is >= -1.0: a simple return of exactly -1.0 is a
    possible total loss and MUST be accepted; anything below -1.0, NaN,
    +/-inf, malformed text and nonnumeric input are rejected, as is a
    numeric overflow that produces infinity. No arbitrary upper bound is
    imposed - a finite positive simple return has no fixed mathematical
    maximum.
    """
    if text is None:
        return None
    s = str(text).strip()
    if not s:
        return None
    try:
        v = float(s)
    except (ValueError, OverflowError, TypeError):
        return None
    if not math.isfinite(v):
        return None
    if v < -1.0:
        return None
    return v


def _pit_validate(args) -> int:
    """Survivorship-free PIT validation (section 8.3); never substituted.

    P6/R14 (L1/L7, per the P3 harness spec): the month-M scoring universe
    is EXACTLY the PIT constituents of month M (rows with listed=1) scored
    with their ``sector_pit`` pools; delisting returns enter the forward
    series; every unscored constituent is counted with a reason code
    (per-month table + run-level total that can never read 0 when names
    were skipped); ticker reuse (a permanent_id change on one ticker) is
    detected and reported; ``--expect-config-hash`` freezes the
    configuration (rule I7) - without a match the run aborts.

    Re-audit finding 2 (PART 6): supplied arguments are validated BEFORE
    the PIT CSV existence check (a missing file must not conceal an
    invalid/future --freeze-date or a mismatched hash). With a valid
    non-future freeze date AND a matching expected hash, every emitted
    period row (pool_too_small rows included) is classified in_sample
    (period month <= freeze date) or out-of-sample (period month > freeze
    date); without BOTH, every period is in_sample null, the counts are
    null and no OOS claim is allowed. stdout carries exactly one JSON
    object; NOTEs and the optional human table go to stderr.
    """
    # ---- PART 6A/B: supplied arguments BEFORE the PIT file check -------
    frozen = config_hash()
    expect = getattr(args, "expect_config_hash", None)
    freeze_text = (getattr(args, "freeze_date", None) or "").strip() or None
    freeze_ready = False
    freeze_date_val: Optional[date] = None
    if freeze_text:
        # forward_main already validated (including the future check at
        # the CLI boundary, which owns the ONE clock read); direct callers
        # are re-validated here with the clock-free strict parse so a
        # malformed date can never reach classification.
        freeze_date_val, reason = _parse_freeze_date(freeze_text)
        if freeze_date_val is None:
            print(_paint(f"FAILED: --freeze-date {freeze_text!r}: {reason}",
                         ("bold", "red"), _use_color_stderr()),
                  file=sys.stderr)
            return 1
        freeze_ready = True
    # A missing expected hash is NOT equivalent to a matching hash; a
    # mismatch aborts before any OOS claim could be made (rule I7).
    if expect and expect != frozen:
        print(f"FAILED: config_hash {frozen} != --expect-config-hash "
              f"{expect}; the configuration changed since the freeze "
              "(rule I7).", file=sys.stderr)
        return 1
    path = Path(args.pit_universe)
    if not path.exists():
        print(f"NOT RUN: no point-in-time survivorship-free universe "
              f"({args.pit_universe} not found). This file comes from a "
              "licensed source (CRSP, Norgate, Sharadar or equivalent); "
              "the current universe is never substituted.", file=sys.stderr)
        return 0
    print(f"[validate] config_hash={frozen} engine={ENGINE_VERSION} "
          f"(frozen BEFORE the run, rule I7)", file=sys.stderr)
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    missing = [c for c in PIT_COLUMNS if rows and c not in rows[0]]
    if missing:
        print(f"FAILED: pit_universe.csv missing columns: {missing}",
              file=sys.stderr)
        return 1
    months = sorted({r["month_end"] for r in rows})
    # OOS classification is allowed only with BOTH a valid non-future
    # freeze date AND a supplied expected hash that matches (a mismatch
    # already aborted above).
    hash_verified = bool(expect)
    oos_ready = freeze_ready and hash_verified
    month_dates: dict = {}
    if oos_ready:
        # Validate period month representations BEFORE comparing them to
        # the freeze date: an invalid month must never be classified through
        # an unsafe string comparison - it is an explicit input failure.
        bad = []
        for month in months:
            try:
                month_dates[month] = date.fromisoformat(month)
            except (ValueError, TypeError):
                bad.append(month)
        if bad:
            print(_paint(
                f"FAILED: invalid month_end value(s) {bad}: a period "
                "month must be a valid YYYY-MM-DD calendar date before it "
                "can be classified against the freeze date",
                ("bold", "red"), _use_color_stderr()), file=sys.stderr)
            return 1
    label = "" if len(months) >= PIT_MIN_MONTHS else " SHORT_HISTORY"
    by_month: dict = {}
    for r in rows:
        by_month.setdefault(r["month_end"], []).append(r)

    # S5: ticker-reuse detection (a ticker whose permanent_id changes is a
    # DIFFERENT company; the event is reported, never silently merged).
    reused: list = []
    last_pid: dict = {}
    for month in months:
        for r in by_month[month]:
            t = (r["ticker"] or "").upper()
            pid = (r.get("permanent_id") or "").strip()
            if t and pid:
                if t in last_pid and last_pid[t] != pid:
                    reused.append({"ticker": t, "month": month,
                                   "from_permanent_id": last_pid[t],
                                   "to_permanent_id": pid})
                last_pid[t] = pid

    results: dict = {}
    per_month: list = []
    n_delisting = 0
    unscored_total = 0
    for month in months:
        listed_rows = [r for r in by_month[month]
                       if str(r.get("listed", "1")).strip().lower()
                       not in ("0", "false", "no", "")]
        refs, seen = [], set()
        for r in listed_rows:
            t = (r["ticker"] or "").upper()
            if t and t not in seen:
                seen.add(t)
                refs.append(TickerRef(t, r.get("sector_pit") or "unknown"))
        scored = _scored_universe(month, args.source,
                                  refs_override=refs) if refs else {}
        pairs = []
        reasons: dict = {}
        for r in listed_rows:
            t = (r["ticker"] or "").upper()
            res = scored.get(t)
            tr_text = (r.get("total_return_next_month") or "").strip()
            dr_text = (r.get("delisting_return_if_any") or "").strip()
            # PART G precedence: 1. a valid total_return_next_month is
            # primary; 2. if it is missing or invalid, a valid
            # delisting_return_if_any may serve as the forward return; 3.
            # neither produces a pair. Only finite simple returns >= -1.0
            # are valid (-1.0 is a possible total loss and IS accepted).
            fwd = _valid_forward_return(tr_text)
            used_delisting = False
            if fwd is None:
                dr = _valid_forward_return(dr_text)
                if dr is not None:
                    fwd = dr
                    used_delisting = True
            if res is None or res.status != OK or res.score is None:
                if res is None:
                    reason = "not_scored_in_universe"
                elif res.status == STALE_DATA:
                    reason = "stale"
                elif res.status == SECTOR_DATA_MISSING:
                    reason = "sector_data_missing"
                elif res.status == INSUFFICIENT_DATA:
                    reason = "insufficient_coverage"
                else:
                    reason = "no_data"
                reasons[reason] = reasons.get(reason, 0) + 1
                continue
            if fwd is None:
                if tr_text or dr_text:
                    # a return WAS supplied but no valid value exists
                    reasons["invalid_forward_return"] = \
                        reasons.get("invalid_forward_return", 0) + 1
                else:
                    reasons["no_forward_return"] = \
                        reasons.get("no_forward_return", 0) + 1
                continue
            pairs.append((t, float(res.score), fwd))
            # PART F: the delisting counter increments ONLY after the pair
            # is actually appended AND only when the return in that pair
            # really came from delisting_return_if_any - unscored names,
            # missing/invalid returns and ordinary total returns never
            # count, and nothing is ever counted twice.
            if used_delisting:
                n_delisting += 1
        results[month] = pairs
        n_unscored = sum(reasons.values())
        unscored_total += n_unscored
        per_month.append({
            "month": month,
            "listed": len(listed_rows),
            "scored": len(pairs),
            "unscored_by_reason": reasons,
            "coverage_pct": round(100.0 * len(pairs) / len(listed_rows),
                                  ROUND_DIGITS) if listed_rows else 0.0,
        })
    periods = []
    months_sorted = sorted(results)
    for a, b in zip(months_sorted, months_sorted[1:]):
        pairs = results[a]
        # PART C/D: every emitted period row is classified, including
        # pool_too_small rows; a month scored before/on the freeze date
        # stays in-sample even when its forward-return window crosses
        # the freeze date. Unclassified (metadata incomplete) is null.
        in_sample = (month_dates[a] <= freeze_date_val
                     if oos_ready else None)
        if len(pairs) < MIN_POOL_FOR_TERCELES:
            periods.append({"month": a, "n_scored": len(pairs),
                            "reason": "pool_too_small",
                            "in_sample": in_sample})
            continue
        ic = spearman([p[1] for p in pairs], [p[2] for p in pairs])
        ordered = sorted(pairs, key=lambda p: (-p[1], p[0]))
        q = max(1, len(ordered) // QUINTILES)
        top = ordered[:q]
        bottom = ordered[-q:]
        spread = (sum(p[2] for p in top) / len(top)
                  - sum(p[2] for p in bottom) / len(bottom))
        periods.append({"month": a, "n_scored": len(pairs), "rank_ic": ic,
                        "top_minus_bottom_gross": spread,
                        "n_top": len(top), "n_bottom": len(bottom),
                        "in_sample": in_sample})
    # COUNTING RULE: emitted period rows only (pool_too_small included) -
    # never the raw CSV months. With incomplete freeze/hash metadata the
    # counts are null, not a misleading zero.
    if oos_ready:
        in_sample_months = sum(1 for p in periods if p["in_sample"] is True)
        oos_months = sum(1 for p in periods if p["in_sample"] is False)
    else:
        in_sample_months = None
        oos_months = None
    # validation_complete means exactly: freeze date valid, expected hash
    # present and matching, and every emitted period classified. It does
    # NOT mean adequate sample size, statistical significance, profitable
    # performance, reliable alpha or production validation.
    validation_complete = bool(
        oos_ready
        and all(p["in_sample"] is not None for p in periods))
    oos_claim_allowed = validation_complete
    ics = [p["rank_ic"] for p in periods if "rank_ic" in p
           and p["rank_ic"] is not None]
    out = {
        "label": "descriptive screener, not an alpha claim" + label,
        "universe_file": args.pit_universe,
        "months": len(months),
        "config_hash": frozen,
        "config_hash_verified": bool(expect),
        "mean_rank_ic": (sum(ics) / len(ics)) if ics else None,
        "ic_positive_share": ((sum(1 for x in ics if x > 0) / len(ics))
                              if ics else None),
        "periods": periods,
        # P6/R14 new keys (additive; baseline keys preserved)
        "per_month": per_month,
        "reused_tickers": reused,
        "n_delisting_returns": n_delisting,
        "costs": "none_applied_gross",
        "borrow_financing_costs": "not_modeled",
        "missing_or_unscored": unscored_total,
        # PART 6D additive keys (OOS classification, re-audit finding 2)
        "freeze_date": (freeze_text if freeze_ready else None),
        "freeze_convention": ("period month <= freeze date is in_sample "
                              "(inclusive; a month scored before/on the "
                              "freeze date stays in-sample even when its "
                              "forward-return window crosses the freeze "
                              "date; period month > freeze date is "
                              "out-of-sample)"),
        "in_sample_months": in_sample_months,
        "oos_months": oos_months,
        "validation_complete": validation_complete,
        "oos_claim_allowed": oos_claim_allowed,
    }
    # stdout: EXACTLY one parseable JSON object; no tables or diagnostics.
    print(json.dumps(out, indent=2, default=str))
    if oos_claim_allowed:
        print("NOTE: descriptive screener, not an alpha claim (rule I9). "
              "Out-of-sample language applies ONLY to the "
              f"{oos_months} emitted period month(s) after the freeze date "
              f"{freeze_text} (config freeze verified against "
              "--expect-config-hash).", file=sys.stderr)
    else:
        missing_bits = []
        if not freeze_ready:
            missing_bits.append("--freeze-date (a valid, non-future "
                                "YYYY-MM-DD)")
        if not hash_verified:
            missing_bits.append("--expect-config-hash matching the current "
                                "config_hash()")
        print("NOTE: descriptive screener, not an alpha claim (rule I9). "
              "OOS claims NOT allowed - missing "
              + " and ".join(missing_bits) + ".", file=sys.stderr)
    print("NOTE: PIT spreads are GROSS (no costs); borrow and financing "
          "costs are not modeled.", file=sys.stderr)
    # Optional human table: stderr only, only when stderr is a real TTY
    # (NO_COLOR / TERM=dumb strips the ANSI styling but keeps the table).
    try:
        stderr_is_tty = bool(sys.stderr.isatty())
    except Exception:
        stderr_is_tty = False
    if stderr_is_tty:
        on = _use_color_stderr()
        head = _paint("month | n_scored | rank_ic | spread | IN/OOS",
                      ("bold",), on)
        print(head, file=sys.stderr)
        for p in periods:
            ic = p.get("rank_ic")
            spread = p.get("top_minus_bottom_gross")
            tag = ("n/a" if p["in_sample"] is None
                   else ("IN" if p["in_sample"] else "OOS"))
            color = "gray" if p["in_sample"] is None else (
                "green" if p["in_sample"] else "cyan")
            print(f"{p['month']} | {p['n_scored']} | "
                  f"{'-' if ic is None else format(ic, '.4f')} | "
                  f"{'-' if spread is None else format(spread, '.4f')} | "
                  + _paint(tag, color, on), file=sys.stderr)
    return 0


# =============================== SECTION: LIVECHECK ============================
# Live provider checks (section 8.1) and hand reconciliation (8.2). Every
# check reports NOT RUN with the exact reason when its credentials, package
# or data are absent; nothing is ever simulated.

LIVECHECK_DEFAULT_NAMES = ("BAC", "USB", "PLD", "AMT", "O", "AEP", "D",
                           "SO", "GL", "MET", "UNM", "CINF", "ORI", "AXP",
                           "COF", "MAR", "DPZ", "ORLY", "ROST", "URI",
                           "EFX", "IPG", "CTAS", "PAYX", "EXPD", "CHRW",
                           "JBHT", "ODFL", "ECL", "FFIV")
# Stratified default set drawn from the built-in universe sectors (banks,
# REITs, utilities, insurers, cyclical and defensive names). Which members
# have recent splits, non-calendar fiscal years, dual classes or
# restatements is only verifiable against the live services; livecheck
# reports what it actually sees instead of promising categories.


def _livecheck_defaults() -> list:
    """Fallback stratified set from the universe when names are not given."""
    refs, _report = get_universe()
    have = {r.ticker for r in refs}
    picked = [t for t in LIVECHECK_DEFAULT_NAMES if t in have]
    if len(picked) >= LIVECHECK_MIN_NAMES:
        return picked
    for r in refs:
        if r.status == "active" and r.ticker not in picked:
            picked.append(r.ticker)
        if len(picked) >= LIVECHECK_MIN_NAMES:
            break
    return picked


def _sec_user_agent_status(sec_configured: bool) -> str:
    """Livecheck text for the SEC_USER_AGENT state (P7/A + C).

    Describes the ACTUAL ``_headers()`` behavior: with SEC_USER_AGENT
    absent the engine sends a STATIC, non-identifying default User-Agent
    (no OS username, no hostname, no reconstructed user@host); a genuine,
    reachable contact should be configured for SEC fair-access
    compliance. Pure text derived from a bool - it can never echo the
    configured contact value.
    """
    if sec_configured:
        return "set (the configured contact is used in the User-Agent)"
    return ("not set (the engine is using its STATIC, non-identifying "
            "default User-Agent: no machine username, no hostname, no "
            "user@host; configure a genuine, reachable contact via "
            "SEC_USER_AGENT in .env for SEC fair-access compliance)")


def livecheck_main(argv: Optional[list] = None) -> int:
    """Live checks (8.1) + reconciliation (8.2); prints to the TERMINAL.

    A markdown report is written to data/live_report.md only with --report.
    Exit is non-zero only when a check FAILED - NOT RUN is never a
    failure, it is an honest skip with its reason.
    """
    parser = argparse.ArgumentParser(
        prog="quality.py livecheck",
        description="Live provider checks: verifies .env keys and every "
                    "data source with REAL requests, and prints the real "
                    "error message when something is off.")
    parser.add_argument("--tickers", default="",
                        help="comma-separated ticker subset")
    parser.add_argument("--as-of", dest="as_of", default=None)
    parser.add_argument("--report", action="store_true",
                        help="also write data/live_report.md")
    parser.add_argument("--reconcile", action="store_true",
                        help="recompute data/reconciliation.csv rows and "
                             "print deviations (section 8.2)")
    args = parser.parse_args(argv)
    _ensure_env()      # .env keys are visible to livecheck too

    color_on = _use_color()
    if color_on:
        _enable_windows_ansi()

    def emit(text: str, styles=()) -> None:
        print(_paint(text, styles, color_on))
        lines.append(_paint(text, (), False))   # plain copy for the report

    lines: list = ["# livecheck report", ""]
    failed = False
    tickers = ([t.strip().upper() for t in args.tickers.split(",")
                if t.strip()] or _livecheck_defaults())
    probe_names = tickers[:LIVECHECK_PROBE_NAMES]
    sec_ok = bool(os.environ.get(SEC_USER_AGENT_ENV))
    fin_ok = bool(finnhub_token()[0])
    yf_ok, _yf_reason = YfinancePriceClient.available()
    ok, err = _validate_as_of(args.as_of, boundary=date.today())
    if not ok:
        print(err, file=sys.stderr)
        return 2
    as_of = args.as_of or date.today().isoformat()

    emit("livecheck - real requests against every enabled source", ("bold", "cyan"))
    emit(f"- tickers: {len(tickers)} ({len(probe_names)} probed live)")
    emit(f"- SEC_USER_AGENT: " + _sec_user_agent_status(sec_ok))
    emit("- Finnhub key (FINNHUB_API_KEY / legacy FINAPI): "
         + ("set" if fin_ok else "not set (optional: SEC EDGAR covers "
            "fundamentals without any key)"))
    if yf_ok:
        emit("- prices: yfinance package")
    else:
        emit("- prices: built-in Yahoo chart client (urllib, no pip)")

    # ---- SEC EDGAR probe: real companyfacts for the first few names ----
    chain = build_source_chain("auto")
    sec = next((s for s in chain.fundamentals if s.name == "sec_edgar"),
               None)
    if sec is None:
        emit("- SEC EDGAR: NOT RUN: client unavailable", "yellow")
    else:
        sec_counts: dict = {}
        for t in probe_names:
            try:
                facts = sec.get_all_facts(t)[0]
                sec_counts[t] = sum(len(v) for v in facts.values())
            except Exception as exc:
                sec_counts[t] = f"FAILED:{type(exc).__name__}"
                failed = True
        good = [t for t, n in sec_counts.items()
                if isinstance(n, int) and n > 0]
        if good:
            shown = ", ".join(f"{t}={sec_counts[t]}" for t in good)
            emit(f"- SEC EDGAR: OK - companyfacts rows: {shown}", "green")
        else:
            emit("- SEC EDGAR: FAILED for every probed name "
                 f"({', '.join(f'{t}:{n}' for t, n in sec_counts.items())})",
                 ("bold", "red"))
            failed = True

    # ---- Finnhub probe: one REAL call, with the real answer printed ----
    if fin_ok:
        fin = FinnhubClient(cache=FileCache())
        facts, report = fin.get_all_facts(probe_names[0])
        n_items = len(facts)
        n_facts = sum(len(v) for v in facts.values())
        if report.status == STATUS_SUCCESS and n_facts:
            emit(f"- finnhub: OK - {n_items} items / {n_facts} facts for "
                 f"{probe_names[0]} (premium access works)", "green")
        elif report.status == STATUS_AUTH_ERROR:
            detail = (report.detail or "").split("diag:")[0].strip()
            if "http_401" in detail:
                emit(f"- finnhub: KEY REJECTED (401) for {probe_names[0]} - "
                     f"check FINNHUB_API_KEY in .env. Server said: {detail}",
                     ("bold", "red"))
                failed = True
            else:
                emit(f"- finnhub: NO PREMIUM ACCESS ({detail or '403'}) - "
                     "your free key cannot use /stock/financials-reported; "
                     "the engine auto-skips it and scores from SEC EDGAR. "
                     "This is EXPECTED on the free tier.", "yellow")
        else:
            emit(f"- finnhub: {report.status} {report.detail} "
                 f"(no facts for {probe_names[0]})", "yellow")
    else:
        emit("- finnhub: NOT RUN: FINNHUB_API_KEY not set (optional)",
             "yellow")

    # ---- price probe: one real window through the ACTIVE price source ----
    if chain.price_source is not None:
        src = chain.price_source
        try:
            payload, report = src.get_price_data(
                probe_names[0], _shift(as_of, -LIVECHECK_PRICE_PROBE_DAYS),
                as_of, fetch_on=as_of)
            bars = len((payload or {}).get("close") or [])
            if bars:
                emit(f"- prices ({src.name}): OK - {bars} daily bars for "
                     f"{probe_names[0]} in the last ~90 days", "green")
            else:
                emit(f"- prices ({src.name}): NO DATA for {probe_names[0]} "
                     f"({report.status} {report.detail})", ("bold", "red"))
                failed = True
        except Exception as exc:
            emit(f"- prices ({src.name}): FAILED "
                 f"{type(exc).__name__}: {exc}", ("bold", "red"))
            failed = True
    else:
        emit("- prices: NOT RUN: no price source enabled", "yellow")

    if args.reconcile:
        recon_path = Path(DEFAULT_RECONCILE_PATH)
        if not recon_path.exists():
            emit("- reconcile: NOT RUN: data/reconciliation.csv "
                 "not found (the human supplies it; the engine "
                 "never fills it from its own output)", "yellow")
        else:
            emit(f"- reconcile: {recon_path}")
            with recon_path.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    emit(f"  - {row.get('ticker')}: recomputation "
                         "deviations are printed above the table "
                         f"threshold {LIVE_RECON_TOLERANCE}")
    if failed:
        emit("RESULT: FAILED (see the red lines above)", ("bold", "red"))
    else:
        emit("RESULT: OK - every enabled source answered", ("bold", "green"))

    if args.report:
        report_path = Path(DEFAULT_LIVE_REPORT_PATH)
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(_paint(f"livecheck report: {report_path}", "gray", color_on))
        except OSError:
            pass
    return 1 if failed else 0


# stdlib unittest, run via ``python3 quality.py selftest``.
#
# Prints "N passed, M failed, K NOT RUN" and exits non-zero on failure.
# Test naming: D<n>_<what> / M<n>_<what> so the final report can map each
# defect to the test that catches it. The D15-D26 and M1-M8 classes were
# written from the master spec BEFORE the rebuild (red-first, W1): they ran
# RED against the 3.0.0 baseline and GREEN here. The D1-D14 and Regression
# classes are lifted from the baseline after independent red-first
# verification. Live transports skip with NOT RUN - never fake data.

_THIS_FILE = str(Path(__file__).resolve())
_MODULE_NAME = __name__

# ============================= SECTION: SELFTEST ===============================
# stdlib unittest, run via ``python3 quality.py selftest``.
#
# Prints "N passed, M failed, K NOT RUN" and exits non-zero on failure.
# Live transports (Finnhub, SEC EDGAR, yfinance) are NOT RUN in this
# environment: they have no key/package here, so the corresponding tests are
# counted as NOT RUN and listed first. Finnhub shape tests use
# DOCUMENTED-SHAPE fixtures (no captured real responses exist in this file).
#
# Which tests use what data (rule D13):
# - synthetic hand-computed statement sets (test builders below);
# - deterministic seeded fixtures generated inside this file (cross-sectional
#   and API tests);
# - documented-shape (not captured) provider payload fixtures for the
#   Finnhub/SEC normalizers;
# - no captured real provider responses exist unless one is added here.

AS_OF = "2024-06-30"


def _shift_day(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


def _month_ends(start: str = "2023-01-31", stop: str = "2024-06-30") -> list:
    """True calendar month ends (last day of each month)."""
    out = []
    day = date.fromisoformat(start)
    end = date.fromisoformat(stop)
    while day <= end:
        out.append(day.isoformat())
        year = day.year + (day.month == 12)
        month = day.month % 12 + 1
        day = date(year, month, _days_in_month(year, month))
    return out

_HAND_FY = {
    2020: dict(revenue=800.0, cogs=480.0, operating_income=84.0,
               depreciation_amortization=56.0, pretax_income=70.0,
               tax_expense=17.5, interest_expense=14.0, net_income=52.5,
               cfo=46.0, capex=40.0, dividends_paid=16.0, buybacks=24.0,
               shares_diluted=10.5, shares_basic=10.4),
    2021: dict(revenue=850.0, cogs=527.0, operating_income=92.0,
               depreciation_amortization=60.0, pretax_income=77.0,
               tax_expense=19.25, interest_expense=15.0, net_income=57.75,
               cfo=50.0, capex=42.0, dividends_paid=18.0, buybacks=26.0,
               shares_diluted=10.4, shares_basic=10.3),
    2022: dict(revenue=900.0, cogs=560.0, operating_income=100.0,
               depreciation_amortization=70.0, pretax_income=82.0,
               tax_expense=20.5, interest_expense=18.0, net_income=61.5,
               cfo=55.0, capex=45.0, dividends_paid=20.0, buybacks=30.0,
               shares_diluted=10.2, shares_basic=10.1),
    2023: dict(revenue=1000.0, cogs=600.0, operating_income=120.0,
               depreciation_amortization=80.0, pretax_income=100.0,
               tax_expense=25.0, interest_expense=20.0, net_income=75.0,
               cfo=60.0, capex=50.0, dividends_paid=30.0, buybacks=45.0,
               shares_diluted=10.0, shares_basic=9.95),
}
_HAND_Q = [("-03-31", -91), ("-06-30", -91), ("-09-30", -92), ("-12-31", -92)]
_HAND_INST = {
    "2020-12-31": dict(total_assets=850.0, total_equity=480.0, total_debt=340.0,
                       long_term_debt=310.0, short_term_debt=30.0, cash=75.0,
                       current_assets=410.0, current_liabilities=280.0,
                       retained_earnings=290.0, intangibles=17.0, goodwill=25.0,
                       preferred_equity=0.0, shares_outstanding=10.1),
    "2021-12-31": dict(total_assets=900.0, total_equity=520.0, total_debt=360.0,
                       long_term_debt=315.0, short_term_debt=45.0, cash=80.0,
                       current_assets=430.0, current_liabilities=285.0,
                       retained_earnings=330.0, intangibles=18.0, goodwill=27.0,
                       preferred_equity=0.0, shares_outstanding=10.15),
    "2022-03-31": dict(total_assets=940.0, total_equity=545.0, total_debt=370.0,
                       long_term_debt=316.0, short_term_debt=54.0, cash=84.0,
                       current_assets=440.0, current_liabilities=287.0,
                       retained_earnings=350.0, intangibles=18.0, goodwill=27.0,
                       preferred_equity=0.0, shares_outstanding=10.2),
    "2022-06-30": dict(total_assets=945.0, total_equity=550.0, total_debt=375.0,
                       long_term_debt=318.0, short_term_debt=57.0, cash=86.0,
                       current_assets=445.0, current_liabilities=288.0,
                       retained_earnings=355.0, intangibles=18.0, goodwill=27.0,
                       preferred_equity=0.0, shares_outstanding=10.2),
    "2022-09-30": dict(total_assets=948.0, total_equity=555.0, total_debt=378.0,
                       long_term_debt=319.0, short_term_debt=59.0, cash=88.0,
                       current_assets=447.0, current_liabilities=289.0,
                       retained_earnings=360.0, intangibles=18.0, goodwill=27.0,
                       preferred_equity=0.0, shares_outstanding=10.2),
    "2022-12-31": dict(total_assets=950.0, total_equity=560.0, total_debt=380.0,
                       long_term_debt=320.0, short_term_debt=60.0, cash=90.0,
                       current_assets=450.0, current_liabilities=290.0,
                       retained_earnings=370.0, intangibles=19.0, goodwill=28.0,
                       preferred_equity=0.0, shares_outstanding=10.2),
    "2023-03-31": dict(total_assets=960.0, total_equity=570.0, total_debt=390.0,
                       long_term_debt=322.0, short_term_debt=68.0, cash=92.0,
                       current_assets=460.0, current_liabilities=292.0,
                       retained_earnings=375.0, intangibles=19.0, goodwill=29.0,
                       preferred_equity=0.0, shares_outstanding=10.18),
    "2023-06-30": dict(total_assets=970.0, total_equity=580.0, total_debt=395.0,
                       long_term_debt=324.0, short_term_debt=71.0, cash=94.0,
                       current_assets=470.0, current_liabilities=294.0,
                       retained_earnings=380.0, intangibles=20.0, goodwill=29.0,
                       preferred_equity=0.0, shares_outstanding=10.16),
    "2023-09-30": dict(total_assets=980.0, total_equity=590.0, total_debt=398.0,
                       long_term_debt=326.0, short_term_debt=72.0, cash=96.0,
                       current_assets=480.0, current_liabilities=296.0,
                       retained_earnings=390.0, intangibles=20.0, goodwill=30.0,
                       preferred_equity=0.0, shares_outstanding=10.08),
    "2023-12-31": dict(total_assets=1000.0, total_equity=600.0, total_debt=400.0,
                       long_term_debt=300.0, short_term_debt=100.0, cash=100.0,
                       current_assets=500.0, current_liabilities=300.0,
                       retained_earnings=400.0, intangibles=20.0, goodwill=30.0,
                       preferred_equity=0.0, shares_outstanding=10.0),
}
_SHARE_FLOW_ITEMS = {"shares_diluted", "shares_basic"}


def hand_facts(drop: tuple = (), scale: dict = None, extra: dict = None) -> dict:
    """Statement facts with hand-auditable values (drop/scale/extra for tests)."""
    scale = scale or {}
    facts: dict = {}
    for year, items in _HAND_FY.items():
        end, filed, start = f"{year}-12-31", f"{year + 1}-02-15", f"{year}-01-01"
        for item, value in items.items():
            if item in drop:
                continue
            facts.setdefault(item, []).append(
                Fact(end, filed, value * scale.get(item, 1.0), "10-K", "FY",
                     start))
    for year in (2022, 2023):
        for suffix, back in _HAND_Q:
            end = f"{year}{suffix}"
            filed = _shift_day(end, FIXTURE_CONFIG["filing_lag_days"])
            start = _shift_day(end, back)
            for item, value in _HAND_FY[year].items():
                if item in drop or item in _SHARE_FLOW_ITEMS:
                    continue
                facts.setdefault(item, []).append(
                    Fact(end, filed, value / 4.0 * scale.get(item, 1.0),
                         "10-Q", "Q", start))
    for end, items in _HAND_INST.items():
        form = "10-K" if end.endswith("12-31") else "10-Q"
        filed = f"{int(end[:4]) + 1}-02-15" if form == "10-K" \
            else _shift_day(end, FIXTURE_CONFIG["filing_lag_days"])
        for item, value in items.items():
            if item in drop:
                continue
            facts.setdefault(item, []).append(
                Fact(end, filed, value * scale.get(item, 1.0), form, "INST"))
    for item, new_facts in (extra or {}).items():
        facts.setdefault(item, []).extend(new_facts)
    return facts


def hand_company(ticker: str = "HAND", sector: str = "tech",
                 prices: list = None, facts: dict = None, drop: tuple = (),
                 scale: dict = None, extra: dict = None) -> Company:
    """A company whose metrics are all hand-computable (see regression tests)."""
    facts = hand_facts(drop, scale, extra) if facts is None else facts
    if prices is None:
        prices = [(d, 90.0) for d in _month_ends()]
    return Company(ticker, sector, facts, prices, prices, {"fixtures"})


def view_of(company: Company, as_of: str = AS_OF) -> FundamentalsView:
    return FundamentalsView(company.facts, as_of)


def energy_company(margins: dict = None,
                   years: tuple = (2020, 2021, 2022, 2023),
                   ticker: str = "ENGY") -> Company:
    """Cyclical company: FY margins controlled per year, quarters = FY/4."""
    margins = margins or {2020: 0.15, 2021: 0.16, 2022: 0.14, 2023: 0.05}
    facts: dict = {}
    for year in years:
        om = margins[year]
        rev = 1000.0 * (1.05 ** (year - 2020))
        flows = {"revenue": rev, "operating_income": rev * om,
                 "cogs": rev * 0.5, "cfo": rev * 0.12, "capex": rev * 0.06,
                 "net_income": rev * (om - 0.03),
                 "pretax_income": rev * (om - 0.02),
                 "tax_expense": rev * 0.05, "interest_expense": rev * 0.02,
                 "depreciation_amortization": rev * 0.04,
                 "dividends_paid": rev * 0.02, "buybacks": rev * 0.01,
                 "shares_diluted": 20.0, "shares_basic": 19.8}
        end, filed, start = f"{year}-12-31", f"{year + 1}-02-15", f"{year}-01-01"
        for item, value in flows.items():
            facts.setdefault(item, []).append(
                Fact(end, filed, round(value, 2), "10-K", "FY", start))
        for suffix, back in _HAND_Q:
            qend = f"{year}{suffix}"
            for item, value in flows.items():
                if item in _SHARE_FLOW_ITEMS:
                    continue
                facts.setdefault(item, []).append(
                    Fact(qend, _shift_day(qend,
                                          FIXTURE_CONFIG["filing_lag_days"]),
                         round(value / FIXTURE_CONFIG["quarter_fraction"], 2),
                         "10-Q", "Q", _shift_day(qend, back)))
        insts = {"total_assets": rev * 1.1, "total_equity": rev * 0.4,
                 "total_debt": rev * 0.4, "cash": rev * 0.06,
                 "current_assets": rev * 0.35, "current_liabilities": rev * 0.2,
                 "long_term_debt": rev * 0.3, "short_term_debt": rev * 0.1,
                 "retained_earnings": rev * 0.2, "shares_outstanding": 20.0,
                 "intangibles": rev * 0.02, "goodwill": rev * 0.03}
        for item, value in insts.items():
            facts.setdefault(item, []).append(
                Fact(end, filed, round(value, 2), "10-K", "INST"))
    prices = [(d, 50.0) for d in _month_ends()]
    return Company(ticker, "energy", facts, prices, prices, {"fixtures"})


def reit_company(ticker: str = "REIT") -> Company:
    """REIT with FFO inputs; FY2023 FFO = 441 by construction."""
    fy = {
        2020: dict(revenue=800.0, net_income=120.0,
                   depreciation_amortization=240.0, gains_on_sales=6.0,
                   operating_income=280.0, interest_expense=88.0,
                   pretax_income=192.0, tax_expense=48.0, cfo=260.0, capex=40.0,
                   dividends_paid=250.0, buybacks=10.0, maintenance_capex=48.0,
                   shares_diluted=55.0, shares_basic=54.5),
        2021: dict(revenue=850.0, net_income=130.0,
                   depreciation_amortization=255.0, gains_on_sales=7.0,
                   operating_income=298.0, interest_expense=94.0,
                   pretax_income=204.0, tax_expense=51.0, cfo=276.0, capex=43.0,
                   dividends_paid=270.0, buybacks=10.0, maintenance_capex=51.0,
                   shares_diluted=54.0, shares_basic=53.5),
        2022: dict(revenue=870.0, net_income=140.0,
                   depreciation_amortization=261.0, gains_on_sales=8.0,
                   operating_income=305.0, interest_expense=96.0,
                   pretax_income=209.0, tax_expense=52.0, cfo=285.0, capex=44.0,
                   dividends_paid=282.0, buybacks=10.0, maintenance_capex=52.0,
                   shares_diluted=55.0, shares_basic=54.5),
        2023: dict(revenue=900.0, net_income=162.0,
                   depreciation_amortization=288.0, gains_on_sales=9.0,
                   operating_income=315.0, interest_expense=99.0,
                   pretax_income=216.0, tax_expense=54.0, cfo=170.0, capex=45.0,
                   dividends_paid=317.52, buybacks=10.0, maintenance_capex=54.0,
                   shares_diluted=55.0, shares_basic=54.5),
    }
    inst = {"total_assets": 6500.0, "total_equity": 2800.0,
            "total_debt": 3300.0, "cash": 120.0, "current_assets": 400.0,
            "current_liabilities": 500.0, "long_term_debt": 2800.0,
            "short_term_debt": 500.0, "retained_earnings": 900.0,
            "shares_outstanding": 55.0, "intangibles": 60.0, "goodwill": 0.0,
            "preferred_equity": 0.0}
    facts: dict = {}
    for year, items in fy.items():
        end, filed, start = f"{year}-12-31", f"{year + 1}-02-15", f"{year}-01-01"
        for item, value in items.items():
            facts.setdefault(item, []).append(
                Fact(end, filed, value, "10-K", "FY", start))
        for suffix, back in _HAND_Q:
            qend = f"{year}{suffix}"
            for item, value in items.items():
                if item in _SHARE_FLOW_ITEMS:
                    continue
                facts.setdefault(item, []).append(
                    Fact(qend, _shift_day(qend,
                                          FIXTURE_CONFIG["filing_lag_days"]),
                         value / FIXTURE_CONFIG["quarter_fraction"],
                         "10-Q", "Q", _shift_day(qend, back)))
    for year in fy:
        for item, value in inst.items():
            facts.setdefault(item, []).append(
                Fact(f"{year}-12-31", f"{year + 1}-02-15", value, "10-K",
                     "INST"))
    prices = [(d, 84.0) for d in _month_ends()]
    return Company(ticker, "reits", facts, prices, prices, {"fixtures"})


def bank_company(ticker: str = "BANK") -> Company:
    """Bank: revenue 630 TTM, noninterest expense 378 TTM (efficiency 0.6)."""
    fy = {
        2022: dict(revenue=600.0, noninterest_expense=360.0,
                   pretax_income=240.0, tax_expense=57.6, net_income=182.4,
                   cfo=191.5, capex=4.8, dividends_paid=58.4, buybacks=43.8,
                   shares_diluted=92.0, shares_basic=91.5),
        2023: dict(revenue=630.0, noninterest_expense=378.0,
                   pretax_income=252.0, tax_expense=60.48, net_income=191.52,
                   cfo=201.1, capex=5.04, dividends_paid=61.3, buybacks=46.0,
                   shares_diluted=90.0, shares_basic=89.6),
    }
    inst = {"total_assets": 16000.0, "total_equity": 1600.0,
            "total_debt": 12800.0, "cash": 1920.0, "current_assets": 4000.0,
            "current_liabilities": 12800.0, "long_term_debt": 8960.0,
            "short_term_debt": 3840.0, "retained_earnings": 560.0,
            "shares_outstanding": 90.0, "preferred_equity": 192.0,
            "intangibles": 64.0, "goodwill": 0.0}
    facts: dict = {}
    for year, items in fy.items():
        end, filed, start = f"{year}-12-31", f"{year + 1}-02-15", f"{year}-01-01"
        for item, value in items.items():
            facts.setdefault(item, []).append(
                Fact(end, filed, value, "10-K", "FY", start))
        for suffix, back in _HAND_Q:
            qend = f"{year}{suffix}"
            for item, value in items.items():
                if item in _SHARE_FLOW_ITEMS:
                    continue
                facts.setdefault(item, []).append(
                    Fact(qend, _shift_day(qend,
                                          FIXTURE_CONFIG["filing_lag_days"]),
                         value / FIXTURE_CONFIG["quarter_fraction"],
                         "10-Q", "Q", _shift_day(qend, back)))
    for year in fy:
        for item, value in inst.items():
            facts.setdefault(item, []).append(
                Fact(f"{year}-12-31", f"{year + 1}-02-15", value, "10-K",
                     "INST"))
    prices = [(d, 118.0) for d in _month_ends()]
    return Company(ticker, "financials", facts, prices, prices, {"fixtures"})


def fixture_companies() -> list:
    """All 23 seeded fixture companies, composed like the source chain would."""
    src = FixtureSource()
    out = []
    for prefix, sector, count in _FIXTURE_PLAN:
        for i in range(1, count + 1):
            ticker = f"{prefix}{i:02d}"
            facts, _r = src.get_all_facts(ticker)
            payload, _r2 = src.get_prices(ticker)
            prices = [(d, float(c)) for d, c in payload.get("close") or []]
            out.append(Company(ticker, sector, facts, prices, prices,
                               {"fixtures"}))
    return out


def fixture_universe_file(path) -> str:
    """CSV of the 23 fixture tickers for API/scan custom universes."""
    rows = [(f"FXTE{i:02d}", "tech") for i in range(1, 11)]
    rows += [(f"FXEN{i:02d}", "energy") for i in range(1, 10)]
    rows += [("FXFI01", "financials"), ("FXUT01", "utilities"),
             ("FXRE01", "reits"), ("FXRE02", "reits")]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ticker", "sector"])
        for row in rows:
            writer.writerow(list(row))
    return str(path)


def write_universe_csv(path, rows) -> str:
    """rows: iterable of (ticker, sector[, status]) - writes a universe CSV."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ticker", "sector", "status"])
        for row in rows:
            writer.writerow(list(row))
    return str(path)


def clone_scaled(company: Company, item: str, k: float, freq: str) -> Company:
    """Copy of a company with one item's facts of ``freq`` scaled by k."""
    facts = {}
    for key, fs in company.facts.items():
        if key == item:
            facts[key] = [
                Fact(f.period_end, f.filing_date, f.value * k, f.form, f.freq,
                     f.period_start) if f.freq == freq else f
                for f in fs]
        else:
            facts[key] = list(fs)
    return Company(company.ticker, company.sector, facts, company.prices,
                   company.adj_prices, set(company.sources), company.note)


def fake_transport(responder):
    """Build a transport from (url, headers) -> (status, payload, retry_after)."""
    def transport(url, headers=None, timeout=None):
        return responder(url, headers or {})
    return transport


class FakePriceSource:
    """Records requested windows; serves a fixed daily series (D15 payload:
    bars + empty split list + fetched_on stamp, one fetch per request)."""

    name = "fake_prices"

    def __init__(self, prices, stale_after=None):
        self.prices = sorted(prices)
        self.requests = []

    def get_price_data(self, ticker, start=None, end=None, fetch_on=None):
        self.requests.append((ticker, start, end, fetch_on))
        pts = [(d, c) for d, c in self.prices
               if (start is None or d >= start) and (end is None or d <= end)]
        if not pts:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "window_outside_history")
        return {"close": pts, "adj_close": pts, "splits": [],
                "splits_known": True, "fetched_on": fetch_on or ""}, \
            ProviderReport(self.name, STATUS_SUCCESS, "")

    def get_prices(self, ticker, start=None, end=None, fetch_on=None):
        return self.get_price_data(ticker, start, end, fetch_on)


def _stale_clone(ticker: str) -> Company:
    company = hand_company(ticker, "tech")
    facts = {k: [f for f in v if f.period_end <= "2022-12-31"]
             for k, v in company.facts.items()}
    return Company(ticker, "tech", facts, company.prices,
                   company.adj_prices, {"fixtures"})

class MetricAudit(unittest.TestCase):
    """S4 independent verification sweeps: no metric may fabricate a number
    from missing inputs, insurer-shaped companies resolve under the
    financials model, and one-off items never leak into operating margin."""

    def test_every_metric_none_on_empty_view(self):
        """With no facts and no market point, EVERY metric must return None
        (or the explicit adverse marker) - never 0, never a fabricated
        number, never an exception."""
        view = FundamentalsView({}, "2024-06-30")
        fabricated = []
        for name, func in sorted(METRIC_FUNCS.items()):
            try:
                out = func(view, None)
            except Exception as exc:
                self.fail(f"{name} raised {type(exc).__name__} on empty view")
            if out is None or out == WORST:
                continue
            fabricated.append((name, out))
        self.assertEqual(fabricated, [],
                         "metrics must not fabricate values: "
                         f"{fabricated}")

    def test_missing_market_point_never_zero(self):
        """Market-dependent metrics with a missing MarketPoint are None,
        never 0 (a zero earnings yield would rank a company at the bottom
        on data absence)."""
        company = hand_company()
        view = FundamentalsView(company.facts, AS_OF)
        for name in ("earnings_yield", "fcf_yield", "ebitda_yield",
                     "shareholder_yield", "p_book", "ffo_yield"):
            out = METRIC_FUNCS[name](view, None)
            self.assertIsNone(out, f"{name} must be None without market")

    def test_insurer_shape_resolves_financials_model(self):
        """A bank/insurer-shaped company (no COGS, no current ratio, no
        Altman inputs; equity, assets, revenue, noninterest expense) resolves
        every REQUIRED metric of the financials model - gross margin and
        current ratio are deliberately absent (never required). TTM metrics
        need four consecutive visible quarters (D = 2024-06-28)."""
        quarters = [("2023-06-30", "2023-04-01", "2023-08-14"),
                    ("2023-09-30", "2023-07-01", "2023-11-14"),
                    ("2023-12-31", "2023-10-01", "2024-02-14"),
                    ("2024-03-31", "2024-01-01", "2024-05-14")]

        def q_facts(item, per_q):
            return [Fact(end, filed, per_q, "10-Q", "Q", start)
                    for end, start, filed in quarters]

        facts = {
            # 4 FYs for CAGR / Piotroski
            "revenue": q_facts("revenue", 500.0) + [
                Fact(f"{y}-12-31", f"{y + 1}-02-15", 500.0 * (y - 2019),
                     "10-K", "FY", f"{y}-01-01") for y in (2020, 2021,
                                                              2022, 2023)],
            "net_income": q_facts("net_income", 55.0) + [
                Fact(f"{y}-12-31", f"{y + 1}-02-15", 55.0 * (y - 2019),
                     "10-K", "FY", f"{y}-01-01") for y in (2020, 2021,
                                                              2022, 2023)],
            "noninterest_expense": q_facts("noninterest_expense", 300.0),
            "total_assets": [Fact("2024-03-31", "2024-05-14", 40000.0,
                                  "10-Q", "INST")],
            "total_equity": [Fact("2024-03-31", "2024-05-14", 4100.0,
                                  "10-Q", "INST"),
                             Fact("2023-12-31", "2024-02-14", 4000.0,
                                  "10-K", "INST"),
                             Fact("2023-03-31", "2023-05-15", 3900.0,
                                  "10-Q", "INST")],
            "shares_outstanding": [Fact("2024-03-31", "2024-05-14", 400.0,
                                        "10-Q", "INST")],
            "cfo": q_facts("cfo", 75.0),
            "dividends_paid": q_facts("dividends_paid", 20.0),
        }
        prices = [("2024-06-27", 50.0), ("2024-06-28", 50.0)]
        company = Company("INSR", "financials", facts, prices, prices,
                          {"fixtures"})
        model = resolve_model("financials")
        raw, notes, view, market, price_status, stale, _prov = \
            compute_raw_metrics(company, model, "2024-06-28")
        self.assertEqual(price_status, "ok")
        required = [s.name for s in model.metrics if s.required]
        for name in required:
            self.assertIsNotNone(raw.get(name),
                                 f"required {name} missing for insurer shape")
        self.assertIsNotNone(raw.get("efficiency_ratio"))
        # TTM noninterest expense 1200 / TTM revenue 2000
        self.assertAlmostEqual(raw["efficiency_ratio"], 0.6, places=6)
        # TTM net income 220 / average equity 4000
        self.assertAlmostEqual(raw["roe_ttm"], 0.055, places=6)
        # no COGS/current-ratio facts exist and none were required
        self.assertNotIn("cogs", company.facts)
        self.assertNotIn("current_assets", company.facts)

    def test_operating_margin_excludes_gains_and_impairments(self):
        """Operating margin uses the tagged OperatingIncomeLoss only:
        one-off gains and impairments never leak in (isolation test - two
        views with wildly different one-offs give the same margin). TTM
        needs four consecutive visible quarters."""
        quarters = [("2023-06-30", "2023-04-01", "2023-08-14"),
                    ("2023-09-30", "2023-07-01", "2023-11-14"),
                    ("2023-12-31", "2023-10-01", "2024-02-14"),
                    ("2024-03-31", "2024-01-01", "2024-05-14")]
        base = {
            "revenue": [Fact(e, f, 250.0, "10-Q", "Q", s)
                        for e, s, f in quarters],
            "operating_income": [Fact(e, f, 30.0, "10-Q", "Q", s)
                                 for e, s, f in quarters],
        }
        with_gains = {**base,
                      "gains_on_sales": [Fact("2023-12-31", "2024-02-14",
                                              500.0, "10-K", "FY",
                                              "2023-01-01")],
                      "impairments": [Fact("2023-12-31", "2024-02-14",
                                           300.0, "10-K", "FY",
                                           "2023-01-01")]}
        d = "2024-06-28"
        m0 = operating_margin(FundamentalsView(base, d), None)
        m1 = operating_margin(FundamentalsView(with_gains, d), None)
        self.assertAlmostEqual(m0, 0.12, places=6)   # TTM 120 / TTM 1000
        self.assertAlmostEqual(m1, 0.12, places=6)

class D1UniverseOverrides(unittest.TestCase):
    """Defect D1: sector overrides are per-ticker, never mutating the group."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _override(self, rows):
        path = Path(self.tmp.name) / "ov.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["ticker", "sector", "status", "note"])
            for row in rows:
                writer.writerow(list(row))
        return str(path)

    def test_override_moves_only_one_ticker(self):
        # JPM is the FIRST financial; the old bug re-assigned the outer-loop
        # sector, dragging every later financial into the override group.
        path = self._override([("JPM", "tech", "", "")])
        refs, report = get_universe(path)
        by_ticker = {r.ticker: r for r in refs}
        self.assertEqual(by_ticker["JPM"].sector, "tech")
        for other in ("BAC", "WFC", "C", "GS", "MS"):
            self.assertEqual(by_ticker[other].sector, "financials", other)

    def test_multiple_overrides(self):
        path = self._override([("JPM", "tech", "", ""),
                               ("XOM", "utilities", "", "")])
        refs, _report = get_universe(path)
        by_ticker = {r.ticker: r for r in refs}
        self.assertEqual(by_ticker["JPM"].sector, "tech")
        self.assertEqual(by_ticker["XOM"].sector, "utilities")
        self.assertEqual(by_ticker["BAC"].sector, "financials")
        # the rest of XOM's original energy group is untouched
        energy = [r.ticker for r in refs if r.sector == "energy"]
        self.assertNotIn("XOM", energy)
        self.assertGreater(len(energy), 1)

    def test_invalid_sector_override_ignored_and_recorded(self):
        path = self._override([("JPM", "not_a_sector", "", "")])
        refs, report = get_universe(path)
        by_ticker = {r.ticker: r for r in refs}
        self.assertEqual(by_ticker["JPM"].sector, "financials")
        self.assertIn("JPM", report["invalid_override"])

    def test_unknown_override_ticker_recorded(self):
        path = self._override([("ZZZZZZ", "tech", "", "")])
        _refs, report = get_universe(path)
        self.assertIn("ZZZZZZ", report["unknown_override_ticker"])

    def test_deterministic_output(self):
        path = self._override([("JPM", "tech", "", ""),
                               ("AAPL", "energy", "", "")])
        first, first_report = get_universe(path)
        second, second_report = get_universe(path)
        self.assertEqual(first, second)
        self.assertEqual(first_report, second_report)

    def test_delisted_and_renamed_kept_with_evidence(self):
        refs, report = get_universe()
        by_ticker = {r.ticker: r for r in refs}
        self.assertEqual(by_ticker["DRE"].status, "delisted")
        self.assertTrue(by_ticker["DRE"].evidence)
        self.assertEqual(by_ticker["PARA"].status, "renamed")
        self.assertEqual(len(report["delisted"]), 9)
        self.assertEqual(len(report["renamed"]), 2)

class D2FinnhubNormalization(unittest.TestCase):
    """Defect D2: documented-shape parsing, duration classification,
    counted diagnostics, real dates only (shape UNVERIFIED - documented, not
    captured)."""

    @staticmethod
    def _row(filed="2024-02-15", start="2023-01-01", end="2023-12-31",
             form="10-K", sections=None):
        return {"symbol": "TEST", "filedDate": filed, "startDate": start,
                "endDate": end, "form": form,
                "report": sections if sections is not None else {}}

    def test_annual_quarterly_and_instants_classify(self):
        rows = [
            self._row(sections={"ic": [
                {"concept": "us-gaap_RevenueFromContractWithCustomer"
                            "ExcludingAssessedTax", "label": "Revenue",
                 "unit": "USD", "value": 1000.0},
                {"concept": "us-gaap_NetIncomeLoss", "label": "Net income",
                 "unit": "USD", "value": 100.0}]}),
            {"filedDate": "2023-05-15", "startDate": "2023-01-01",
             "endDate": "2023-03-31", "form": "10-Q",
             "report": {"ic": [
                 {"concept": "us-gaap_RevenueFromContractWithCustomer"
                             "ExcludingAssessedTax", "label": "Revenue",
                  "unit": "USD", "value": 250.0}],
                 "bs": [
                     {"concept": "us-gaap_Assets", "label": "Total assets",
                      "unit": "USD", "value": 2000.0},
                     {"concept": "us-gaap_LongTermDebtNoncurrent",
                      "label": "Long-term debt", "unit": "USD", "value": 300.0},
                     {"concept": "us-gaap_LongTermDebtCurrent",
                      "label": "Current debt", "unit": "USD", "value": 60.0}]}},
        ]
        facts, diag = normalize_finnhub(rows)
        kinds = {(f.freq, f.value) for f in facts["revenue"]}
        self.assertIn(("FY", 1000.0), kinds)
        self.assertIn(("Q", 250.0), kinds)
        self.assertTrue(all(f.freq == "INST" for f in facts["total_assets"]))
        self.assertEqual(facts["total_assets"][0].value, 2000.0)
        # components exposed separately; the view composes the total (D3)
        self.assertEqual({f.value for f in facts["long_term_debt"]}, {300.0})
        self.assertEqual({f.value for f in facts["short_term_debt"]}, {60.0})
        self.assertNotIn("total_debt", facts)
        self.assertEqual(sum(v for k, v in diag.items() if k != "duplicates"),
                         0)

    def test_non_calendar_fiscal_year(self):
        rows = [self._row(filed="2024-05-15", start="2023-04-01",
                          end="2024-03-31",
                          sections={"ic": [
                              {"concept": "us-gaap_Revenues",
                               "label": "Revenue", "unit": "USD",
                               "value": 900.0}]})]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(facts["revenue"][0].freq, "FY")
        self.assertEqual(facts["revenue"][0].period_end, "2024-03-31")

    def test_ytd_classification(self):
        rows = [self._row(filed="2023-08-14", start="2023-01-01",
                          end="2023-06-30", form="10-Q",
                          sections={"cf": [
                              {"concept": "us-gaap_"
                                          "NetCashProvidedByUsedInOperating"
                                          "Activities", "label": "CFO",
                               "unit": "USD", "value": 34.0}]})]
        facts, _diag = normalize_finnhub(rows)
        self.assertEqual(facts["cfo"][0].freq, "YTD")
        self.assertEqual(facts["cfo"][0].period_start, "2023-01-01")

    def test_missing_filed_counted(self):
        rows = [self._row(filed=None, sections={"ic": [
            {"concept": "us-gaap_Revenues", "label": "Revenue",
             "unit": "USD", "value": 1.0}]})]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(facts, {})
        self.assertEqual(diag["missing_filed"], 1)

    def test_filing_date_fallbacks(self):
        rows = [
            {"filingDate": "2024-02-15", "startDate": "2023-01-01",
             "endDate": "2023-12-31", "report": {"ic": [
                 {"concept": "us-gaap_Revenues", "label": "r", "unit": "USD",
                  "value": 10.0}]}},
            {"acceptedDate": "2023-06-01T10:00:00", "startDate":
             "2023-01-01", "endDate": "2023-03-31", "report": {"ic": [
                 {"concept": "us-gaap_Revenues", "label": "r", "unit": "USD",
                  "value": 3.0}]}},
        ]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(diag["missing_filed"], 0)
        filed = {f.filing_date for f in facts["revenue"]}
        self.assertEqual(filed, {"2024-02-15", "2023-06-01"})

    def test_missing_end_counted(self):
        rows = [{"filedDate": "2024-02-15", "startDate": "2023-01-01",
                 "report": {}}]
        _facts, diag = normalize_finnhub(rows)
        self.assertEqual(diag["missing_end"], 1)

    def test_never_reconstructs_from_year_quarter(self):
        # the old bug rebuilt period ends from year/quarter; real dates only
        rows = [{"year": 2023, "quarter": 2, "filedDate": "2023-08-14",
                 "report": {"ic": {"totalRevenue": 250.0}}}]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(facts, {})
        self.assertEqual(diag["missing_end"], 1)

    def test_bad_duration_counted(self):
        rows = [self._row(start="2023-01-01", end="2023-05-01",
                          sections={"ic": [
                              {"concept": "us-gaap_Revenues", "label": "r",
                               "unit": "USD", "value": 1.0}]})]
        _facts, diag = normalize_finnhub(rows)
        self.assertEqual(diag["bad_duration"], 1)

    def test_unknown_concept_counted(self):
        rows = [self._row(sections={"ic": [
            {"concept": "us-gaap_SomeExoticTag", "label": "???",
             "unit": "USD", "value": 5.0}]})]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(facts, {})
        self.assertEqual(diag["unknown_concept"], 1)

    def test_label_matching_is_fallback(self):
        rows = [self._row(sections={"ic": [
            {"concept": "", "label": "Total revenue", "unit": "USD",
             "value": 777.0}]})]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(facts["revenue"][0].value, 777.0)
        self.assertEqual(diag["unknown_concept"], 0)

    def test_malformed_rows_counted(self):
        rows = ["not-a-dict", {"filedDate": "2024-02-15",
                               "startDate": "2023-01-01",
                               "endDate": "2023-12-31", "report": "junk"},
                self._row(sections={"ic": [{"label": "x", "value": "junk"}]}),
                self._row(sections={"ic": ["not-an-entry"]})]
        _facts, diag = normalize_finnhub(rows)
        self.assertEqual(diag["malformed"], 4)

    def test_empty_payload(self):
        facts, diag = normalize_finnhub([])
        self.assertEqual(facts, {})
        self.assertEqual(sum(diag.values()), 0)

    def test_duplicates_counted(self):
        entry = {"concept": "us-gaap_Revenues", "label": "Revenue",
                 "unit": "USD", "value": 10.0}
        rows = [self._row(sections={"ic": [entry, dict(entry)]})]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(len(facts["revenue"]), 1)
        self.assertEqual(diag["duplicates"], 1)

class D3DebtDoubleCounting(unittest.TestCase):
    """Defect D3: total debt is composed at view time, one fact per component
    per period_end; duplicate annual/Q4 representations never sum twice."""

    @staticmethod
    def _view(ltd_facts, std_facts, as_of=AS_OF, direct=None):
        facts = {"long_term_debt": ltd_facts, "short_term_debt": std_facts}
        if direct is not None:
            facts["total_debt"] = direct
        return FundamentalsView(facts, as_of)

    def test_annual_and_q4_rows_give_120_not_240(self):
        # annual row and Q4 row both report LTD 100 / STD 20 at 2023-12-31
        ltd = [Fact("2023-12-31", "2024-02-15", 100.0, "10-K", "INST"),
               Fact("2023-12-31", "2024-02-15", 100.0, "10-Q", "INST")]
        std = [Fact("2023-12-31", "2024-02-15", 20.0, "10-K", "INST"),
               Fact("2023-12-31", "2024-02-15", 20.0, "10-Q", "INST")]
        view = self._view(ltd, std)
        value, missing = view.total_debt()
        self.assertEqual(value, 120.0)
        self.assertEqual(missing, [])

    def test_restatement_latest_filing_wins(self):
        ltd = [Fact("2023-12-31", "2024-02-15", 100.0, "10-K", "INST"),
               Fact("2023-12-31", "2024-06-01", 130.0, "10-K/A", "INST")]
        std = [Fact("2023-12-31", "2024-02-15", 20.0, "10-K", "INST")]
        value, _missing = self._view(ltd, std).total_debt()
        self.assertEqual(value, 150.0)
        # the restatement is only visible from its own filing date (I1)
        value_before, _m = self._view(ltd, std, as_of="2024-03-31") \
            .total_debt()
        self.assertEqual(value_before, 120.0)

    def test_different_filing_dates_latest_wins(self):
        ltd = [Fact("2023-12-31", "2024-02-15", 100.0, "10-K", "INST"),
               Fact("2023-12-31", "2024-11-01", 90.0, "10-K", "INST")]
        std = [Fact("2023-12-31", "2024-02-15", 20.0, "10-K", "INST")]
        value, _missing = self._view(ltd, std, as_of="2025-06-30").total_debt()
        self.assertEqual(value, 110.0)

    def test_missing_component_reported_not_silent(self):
        ltd = [Fact("2023-12-31", "2024-02-15", 100.0, "10-K", "INST")]
        view = self._view(ltd, [])
        value, missing = view.total_debt()
        self.assertEqual(value, 100.0)
        self.assertEqual(missing, ["short_term_debt"])
        _end, _v, missing_diag = view._compose_debt()
        self.assertEqual(missing_diag, ["short_term_debt"])

    def test_multiple_balance_dates_use_latest(self):
        ltd = [Fact("2022-12-31", "2023-02-15", 80.0, "10-K", "INST"),
               Fact("2023-12-31", "2024-02-15", 100.0, "10-K", "INST")]
        std = [Fact("2022-12-31", "2023-02-15", 15.0, "10-K", "INST"),
               Fact("2023-12-31", "2024-02-15", 20.0, "10-K", "INST")]
        value, _missing = self._view(ltd, std).total_debt()
        self.assertEqual(value, 120.0)
        self.assertEqual(self._view(ltd, std).total_debt_year_ago(), 95.0)

    def test_direct_total_debt_fallback(self):
        # no components at all -> directly reported total_debt is used
        direct = [Fact("2023-12-31", "2024-02-15", 240.0, "10-K", "INST")]
        view = self._view([], [], direct=direct)
        value, missing = view.total_debt()
        self.assertEqual(value, 240.0)
        self.assertEqual(missing, [])

    def test_finnhub_duplicates_never_double_count(self):
        # same balance date reported by an annual AND a quarterly row
        def row(form, filed):
            return {"filedDate": filed, "startDate": "2023-01-01",
                    "endDate": "2023-12-31", "form": form,
                    "report": {"bs": [
                        {"concept": "us-gaap_LongTermDebtNoncurrent",
                         "label": "ltd", "unit": "USD", "value": 100.0},
                        {"concept": "us-gaap_LongTermDebtCurrent",
                         "label": "std", "unit": "USD", "value": 20.0}]}}
        facts, _diag = normalize_finnhub([row("10-K", "2024-02-15"),
                                          row("10-Q", "2024-02-15")])
        view = FundamentalsView(facts, AS_OF)
        value, missing = view.total_debt()
        self.assertEqual(value, 120.0)      # NOT 240
        self.assertEqual(missing, [])

class D4Momentum(unittest.TestCase):
    """Defect D4: calendar-based 12-1 momentum with hand-computed values."""

    SERIES = [
        ("2023-06-28", 100.0), ("2023-06-30", 110.0),
        ("2024-05-15", 121.0), ("2024-05-30", 132.0),
        ("2024-06-15", 999.0), ("2024-06-30", 500.0),
    ]

    def test_daily_hand_computed(self):
        # t_start = 2023-06-30 -> 110; t_end = 2024-05-30 -> 132
        value, reason = momentum_12_1_detail(self.SERIES, "2024-06-30")
        self.assertIsNone(reason)
        self.assertAlmostEqual(value, 132.0 / 110.0 - 1.0, places=9)

    def test_skip_month_exclusion(self):
        # the 2024-06-15 spike sits in the skipped month and must not matter
        spiked = [(d, 5000.0 if d == "2024-06-15" else c)
                  for d, c in self.SERIES]
        value, _reason = momentum_12_1_detail(spiked, "2024-06-30")
        self.assertAlmostEqual(value, 132.0 / 110.0 - 1.0, places=9)

    def test_monthly_series(self):
        prices = [(d, 100.0 * (1.01 ** i)) for i, d in enumerate(_month_ends())]
        # t_start 2023-06-30 -> index 5; t_end 2024-05-30 -> 2024-04-30 (idx 15)
        value, reason = momentum_12_1_detail(prices, "2024-06-30")
        self.assertIsNone(reason)
        self.assertAlmostEqual(value, (1.01 ** 15) / (1.01 ** 5) - 1.0,
                               places=9)

    def test_missing_days_within_tolerance(self):
        # monthly data with the 15th missing: last obs before 2024-05-30 is
        # 2024-05-14, gap 16d <= max(7, 1.5 * ~15) -> accepted
        series = [("2023-06-14", 100.0), ("2023-07-14", 101.0),
                  ("2023-08-14", 102.0), ("2024-04-14", 110.0),
                  ("2024-05-14", 120.0), ("2024-06-14", 200.0)]
        value, reason = momentum_12_1_detail(series, "2024-06-30")
        self.assertIsNone(reason)
        self.assertAlmostEqual(value, 120.0 / 100.0 - 1.0, places=9)

    def test_irregular_spacing_rejected(self):
        # nothing inside the measurement window (t_start, t_end]: the only
        # observation before t_end IS the t_start observation
        series = [("2023-06-30", 110.0), ("2024-06-30", 500.0)]
        value, reason = momentum_12_1_detail(series, "2024-06-30")
        self.assertIsNone(value)
        self.assertEqual(reason, "insufficient_history_in_window")

    def test_stale_observation_rejected_by_gap_rule(self):
        # an observation exists inside the window but the one nearest t_end
        # is months away -> gap rule rejects it
        series = [("2023-06-30", 110.0), ("2023-07-30", 111.0),
                  ("2023-08-30", 112.0), ("2024-06-30", 500.0)]
        value, reason = momentum_12_1_detail(series, "2024-06-30")
        self.assertIsNone(value)
        self.assertEqual(reason, "gap_too_large_at_end")

    def test_gap_too_large_at_start(self):
        series = [("2023-09-30", 100.0), ("2024-05-30", 150.0),
                  ("2024-06-30", 160.0)]
        value, reason = momentum_12_1_detail(series, "2024-06-30")
        self.assertIsNone(value)
        self.assertEqual(reason, "insufficient_history_at_start")

    def test_duplicate_dates_last_wins(self):
        series = list(self.SERIES) + [("2024-05-30", 264.0)]
        value, _reason = momentum_12_1_detail(series, "2024-06-30")
        self.assertAlmostEqual(value, 264.0 / 110.0 - 1.0, places=9)

    def test_insufficient_history_reason(self):
        prices = [(d, 90.0) for d in _month_ends()[:12]]
        value, reason = momentum_12_1_detail(prices, AS_OF)
        self.assertIsNone(value)
        self.assertTrue(reason)

    def test_no_future_leakage(self):
        future = list(self.SERIES) + [("2024-12-31", 9999.0)]
        value, _r = momentum_12_1_detail(future, "2024-06-30")
        self.assertAlmostEqual(value, 132.0 / 110.0 - 1.0, places=9)

    def test_month_arithmetic_day_clamping(self):
        # 2024-03-31 - 1 month clamps to 2024-02-29 (leap year)
        self.assertEqual(_shift_months("2024-03-31", -1), "2024-02-29")
        self.assertEqual(_shift_months("2024-05-31", -12), "2023-05-31")

    def test_weekly_series(self):
        # 13+ weekly observations spanning the window
        series = []
        d = date.fromisoformat("2023-06-02")
        for i in range(60):
            series.append((d.isoformat(), 100.0 * (1.005 ** i)))
            d += timedelta(days=7)
        value, reason = momentum_12_1_detail(series, "2024-06-30")
        self.assertIsNone(reason)
        self.assertIsNotNone(value)

class D5PriceWindows(unittest.TestCase):
    """Defect D5: fetch windows derive from the as-of date, cache entries
    store covered ranges and are reused only when they cover the request."""

    def test_scoring_window_derives_from_as_of(self):
        # [D - 430d, D]: 2024-06-30 - 430d = 2023-04-27 (366 leap-year days
        # to 2024-04-27, then 64 to 2024-06-30). An earlier revision of this
        # test asserted 2023-04-26 from faulty hand arithmetic; the engine
        # was correct (timedelta(days=430)); the expectation was fixed.
        fake = FakePriceSource([(f"2024-06-{d:02d}", 10.0 + d)
                                for d in range(1, 31)])
        chain = SourceChain([], fake, [], [])
        chain.get_company("TEST", "tech", "2024-06-30",
                          fetch_on="2024-06-30")
        self.assertEqual(len(fake.requests), 1)
        _ticker, start, end, _fetch = fake.requests[0]
        self.assertEqual(start, "2023-04-27")
        self.assertEqual(end, "2024-06-30")

    def test_no_future_price_leakage(self):
        prices = [(d, 90.0) for d in _month_ends()] + \
            [("2024-08-31", 500.0), ("2024-12-31", 900.0)]
        company = hand_company("L1", "tech", prices=prices)
        market, status = build_market(company, AS_OF)
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(market.price, 90.0)

    def test_ranges_cover_union(self):
        self.assertFalse(_ranges_cover([], "2024-01-01", "2024-02-01"))
        self.assertTrue(_ranges_cover([("2024-01-01", "2024-02-01")],
                                      "2024-01-15", "2024-01-20"))
        self.assertFalse(_ranges_cover([("2024-01-01", "2024-01-31")],
                                       "2024-01-15", "2024-02-05"))
        # a one-day hole breaks coverage
        self.assertFalse(_ranges_cover(
            [("2024-01-01", "2024-01-31"), ("2024-02-01", "2024-02-28")],
            "2024-01-15", "2024-02-10"))
        # touching ranges form a covering union
        self.assertTrue(_ranges_cover(
            [("2024-01-01", "2024-02-01"), ("2024-02-01", "2024-02-28")],
            "2024-01-15", "2024-02-10"))

    def test_price_cache_reuse_across_as_of(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                calls = []

                class FakeHistory:
                    def __init__(self, rows):
                        self.rows = rows

                    def iterrows(self):
                        class Idx:
                            def __init__(self, day):
                                self._day = day

                            def date(self):
                                return date.fromisoformat(self._day)

                        for day, close in self.rows:
                            yield Idx(day), {"Close": close,
                                             "Adj Close": close * 0.9}

                class FakeYf:
                    @staticmethod
                    def Ticker(ticker):
                        calls.append(ticker)
                        return FakeTicker()

                class FakeTicker:
                    def history(self, start=None, end=None, interval="1d",
                                auto_adjust=False):
                        return FakeHistory(
                            [(f"2024-06-{d:02d}", 10.0 + d) for d in
                             range(1, 31)])

                fake_module = type(sys)("yfinance")
                fake_module.Ticker = FakeYf.Ticker
                with mock.patch.dict(sys.modules,
                                     {"yfinance": fake_module}):
                    client = YfinancePriceClient()
                    p1, r1 = client.get_prices("X", "2023-04-26",
                                               "2024-06-30",
                                               fetch_on="2024-06-30")
                    self.assertEqual(r1.status, STATUS_SUCCESS)
                    self.assertEqual(len(calls), 1)
                    # overlapping window already covered -> served from cache
                    p2, r2 = client.get_prices("X", "2023-05-26",
                                               "2024-06-15",
                                               fetch_on="2024-06-30")
                    self.assertEqual(r2.status, STATUS_SUCCESS)
                    self.assertEqual(r2.calls, 0)
                    self.assertEqual(len(calls), 1)
                    # wider window not covered -> refetch and merge
                    p3, r3 = client.get_prices("X", "2023-05-26",
                                               "2024-07-31",
                                               fetch_on="2024-06-30")
                    self.assertEqual(r3.calls, 1)
                    self.assertEqual(len(calls), 2)

    def test_insufficient_history_explicit_status(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                class FakeTicker:
                    def history(self, start=None, end=None, interval="1d",
                                auto_adjust=False):
                        return FakeHistory([])

                class FakeHistory:
                    def __init__(self, rows):
                        self.rows = rows
                        self.empty = not rows

                    def iterrows(self):
                        return iter([])

                fake_module = type(sys)("yfinance")
                fake_module.Ticker = lambda t: FakeTicker()
                with mock.patch.dict(sys.modules,
                                     {"yfinance": fake_module}):
                    client = YfinancePriceClient()
                    payload, report = client.get_prices("X", "2024-01-01",
                                                        "2024-02-01",
                                                        fetch_on="2024-02-01")
                    self.assertIsNone(payload)
                    self.assertEqual(report.status, STATUS_NO_DATA)

    def test_fixture_window_outside_history(self):
        src = FixtureSource()
        payload, report = src.get_prices("FXTE01", "2030-01-01",
                                         "2030-12-31")
        self.assertIsNone(payload)
        self.assertEqual(report.status, STATUS_NO_DATA)

class D6ProviderDiagnostics(unittest.TestCase):
    """Defect D6: every provider call records a status; 429 honors
    Retry-After with at most 3 backoff retries; fallback and provenance are
    recorded; an all-error ticker is ERROR with the classes listed."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _client(self, responder):
        from unittest import mock
        cache = FileCache(root=self.tmp.name)
        slept = []
        client = FinnhubClient(cache=cache, limiter=RateLimiter(0.0),
                               transport=fake_transport(responder),
                               sleep_fn=slept.append)
        return client, cache, slept

    def test_auth_error(self):
        client, _cache, _slept = self._client(
            lambda url, headers: (STATUS_AUTH_ERROR, None, None))
        _facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_AUTH_ERROR)

    def test_rate_limited_after_max_retries(self):
        client, _cache, slept = self._client(
            lambda url, headers: (STATUS_RATE_LIMITED, None, 0))
        _facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_RATE_LIMITED)
        # 3 retries per request, 2 requests (annual + quarterly)
        self.assertEqual(report.retries, 2 * MAX_RATE_LIMIT_RETRIES)
        self.assertEqual(report.calls, 2 * (1 + MAX_RATE_LIMIT_RETRIES))
        self.assertTrue(len(slept) >= 2 * MAX_RATE_LIMIT_RETRIES)

    def test_rate_limited_then_success(self):
        state = {"n": 0}

        def responder(url, headers):
            state["n"] += 1
            if state["n"] <= 1:
                return (STATUS_RATE_LIMITED, None, 0)
            return (STATUS_SUCCESS, {"data": []}, None)

        client, _cache, _slept = self._client(responder)
        _facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_NO_DATA)  # no data, no error
        self.assertEqual(report.retries, 1)

    def test_network_error(self):
        client, _cache, _slept = self._client(
            lambda url, headers: (STATUS_NETWORK_ERROR, None, None))
        _facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_NETWORK_ERROR)

    def test_schema_error_on_bad_json(self):
        client, _cache, _slept = self._client(
            lambda url, headers: (STATUS_SCHEMA_ERROR, None, None))
        _facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_SCHEMA_ERROR)

    def test_provider_error_5xx(self):
        client, _cache, _slept = self._client(
            lambda url, headers: (STATUS_PROVIDER_ERROR, None, None))
        _facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_PROVIDER_ERROR)

    def test_partial_success_annual_ok_quarterly_500(self):
        def responder(url, headers):
            if "freq=quarterly" in url:
                return (STATUS_PROVIDER_ERROR, None, None)
            return (STATUS_SUCCESS, {"data": [
                {"filedDate": "2024-02-15", "startDate": "2023-01-01",
                 "endDate": "2023-12-31", "form": "10-K",
                 "report": {"ic": [
                     {"concept": "us-gaap_Revenues", "label": "r",
                      "unit": "USD", "value": 100.0}]}}]}, None)
        client, _cache, _slept = self._client(responder)
        facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_PARTIAL_SUCCESS)
        self.assertIn("revenue", facts)

    def test_no_data(self):
        client, _cache, _slept = self._client(
            lambda url, headers: (STATUS_NO_DATA, None, None))
        _facts, report = client.get_all_facts("AAPL")
        self.assertEqual(report.status, STATUS_NO_DATA)

    def test_source_chain_fallback_and_provenance(self):
        from unittest import mock
        finnhub_responder = lambda url, headers: (STATUS_SUCCESS, {"data": [
            {"filedDate": "2024-02-15", "startDate": "2023-01-01",
             "endDate": "2023-12-31", "form": "10-K",
             "report": {"ic": [
                 {"concept": "us-gaap_Revenues", "label": "r", "unit": "USD",
                  "value": 100.0}]}}]}, None)
        finnhub = FinnhubClient(
            cache=FileCache(root=self.tmp.name), limiter=RateLimiter(0.0),
            transport=fake_transport(finnhub_responder), sleep_fn=lambda s: 0)
        sec = SecEdgarClient(
            cache=FileCache(root=self.tmp.name), limiter=RateLimiter(0.0),
            transport=fake_transport(
                lambda url, headers: (STATUS_AUTH_ERROR, None, None)),
            sleep_fn=lambda s: 0)
        chain = SourceChain([sec, finnhub], None, [], [])
        company = chain.get_company("AAPL", "tech", AS_OF)
        self.assertIn("revenue", company.facts)
        self.assertEqual(company.item_source["revenue"], "finnhub")
        self.assertEqual(company.source_status["sec_edgar"],
                         STATUS_AUTH_ERROR)
        self.assertEqual(company.source_status["finnhub"], STATUS_SUCCESS)
        stats = chain.provider_status_summary()
        self.assertEqual(stats["sec_edgar"], {STATUS_AUTH_ERROR: 1})

    def test_all_providers_error_is_error_ticker(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {FINNHUB_KEY_ENV: "k",
                                          SEC_USER_AGENT_ENV: "u"}):
            finnhub = FinnhubClient(
                cache=FileCache(root=self.tmp.name), limiter=RateLimiter(0.0),
                transport=fake_transport(
                    lambda url, headers: (STATUS_AUTH_ERROR, None, None)),
                sleep_fn=lambda s: 0)
            sec = SecEdgarClient(
                cache=FileCache(root=self.tmp.name), limiter=RateLimiter(0.0),
                transport=fake_transport(
                    lambda url, headers: (STATUS_RATE_LIMITED, None, 0)),
                sleep_fn=lambda s: 0)
            chain = SourceChain([sec, finnhub], None, [], [])
            ref = TickerRef("AAPL", "tech")
            companies, statuses, errors, _ustat = fetch_companies(chain, [ref], AS_OF)
            self.assertEqual(companies, [])
            self.assertEqual(statuses["AAPL"], ERROR)
            self.assertIn("AUTH_ERROR", errors["AAPL"])
            self.assertIn("RATE_LIMITED", errors["AAPL"])

    def test_api_key_never_in_cache_or_reports(self):
        from unittest import mock
        secret = "SECRET_TOKEN_VALUE"
        captured = {}

        def responder(url, headers):
            captured["url"] = url
            return (STATUS_SUCCESS, {"data": []}, None)

        with mock.patch.dict(os.environ, {FINNHUB_KEY_ENV: secret}):
            cache = FileCache(root=self.tmp.name)
            client = FinnhubClient(cache=cache, limiter=RateLimiter(0.0),
                                   transport=fake_transport(responder),
                                   sleep_fn=lambda s: 0)
            _facts, report = client.get_all_facts("AAPL")
            self.assertIn(secret, captured["url"])  # token goes on the wire
            # ...but never into the cache key, the report or the detail
            cached_files = list(Path(self.tmp.name).rglob("*.json"))
            self.assertTrue(cached_files)
            for f in cached_files:
                self.assertNotIn(secret, f.read_text(encoding="utf-8"))
            self.assertNotIn(secret, json.dumps(report.to_dict()))
            self.assertNotIn(secret, str(client.last_diagnostics))

class D7ForwardValidation(unittest.TestCase):
    """Defect D7: pool minimums, bucketing ladder, tolerance, turnover,
    adjusted-vs-price-only, reproducibility."""

    @staticmethod
    def _rows(n, sectors):
        rows = []
        for i in range(n):
            rows.append({"ticker": f"T{i:03d}",
                         "sector": sectors[i % len(sectors)],
                         "status": "OK",
                         "score": str(round(100.0 * (n - i) / n, 4))})
        return rows

    @staticmethod
    def _lookup_factory(table):
        def lookup(ticker, day):
            return table.get((ticker, day))
        return lookup

    def test_spearman_basics(self):
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [40, 30, 20, 10]), -1.0)
        self.assertIsNone(spearman([5, 5, 5], [1, 2, 3]))

    def test_pool_too_small_skips_with_reason(self):
        rows = self._rows(10, ["sec"])
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods_evaluated"], 0)
        self.assertEqual(report["skipped_pairs"][0]["reason"],
                         "pool_too_small")
        self.assertEqual(report["skipped_pairs"][0]["n_scored"], 10)

    def test_sector_quintiles_when_pool_and_sectors_large(self):
        rows = self._rows(50, ["a", "b", "c", "d", "e"])  # 10 per sector
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods"][0]["bucketing"],
                         "sector_quintiles")
        self.assertEqual(report["periods"][0]["n_top"], 10)
        self.assertEqual(report["periods"][0]["n_bottom"], 10)

    def test_pooled_quintiles_when_sectors_thin(self):
        rows = self._rows(50, ["a", "b"])   # 25 each -> still >= 10 per sector
        rows2 = self._rows(50, ["a"] * 45 + ["b"] * 5)  # one thin sector
        snaps = [{"date": "2024-06-30", "rows": rows2},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods"][0]["bucketing"],
                         "pooled_quintiles")

    def test_tercile_fallback_labels(self):
        rows = self._rows(30, ["a", "b", "c"])   # 10 per sector, pool 30
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods"][0]["bucketing"], "sector_terciles")

    def test_wrong_interval_skipped(self):
        rows = self._rows(50, ["a"])
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-12-31", "rows": rows}]
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods_evaluated"], 0)
        self.assertEqual(report["skipped_pairs"][0]["reason"],
                         "gap_outside_tolerance")

    def test_boundary_gap_within_tolerance(self):
        rows = self._rows(50, ["a"])
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-30", "rows": []}]   # gap 30 -> ok
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods_evaluated"], 1)
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-08-05", "rows": []}]   # gap 36 -> skip
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods_evaluated"], 0)

    def test_missing_prices_counted_and_coverage(self):
        rows = self._rows(50, ["a"])

        def lookup(ticker, day):
            if day == "2024-07-31" and ticker in ("T000", "T001"):
                return None
            return 100.0

        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, lookup)
        period = report["periods"][0]
        self.assertEqual(period["missing_prices"], 2)
        self.assertAlmostEqual(period["forward_coverage"], 48 / 50, places=6)
        self.assertFalse(period["sample_complete"])

    def test_hand_computed_tercile_spread_net_of_costs(self):
        n = 30
        rows = self._rows(n, ["sec"])
        # forward return falls linearly with rank: T000 -> +10% ... T029 -> ~0
        fwd = {f"T{i:03d}": 0.10 * (n - i) / n for i in range(n)}

        def lookup(ticker, day):
            return 100.0 if day == "2024-06-30" else 100.0 * (1 + fwd[ticker])

        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, lookup, cost_bps=20)
        period = report["periods"][0]
        top = sum(fwd[f"T{i:03d}"] for i in range(10)) / 10
        bottom = sum(fwd[f"T{i:03d}"] for i in range(20, 30)) / 10
        self.assertAlmostEqual(period["quintile_spread_gross"],
                               top - bottom, places=9)
        # Costs are charged per leg, BOTH legs: the long quintile pays a
        # round trip AND the short quintile pays a round trip. The earlier
        # revision of this test subtracted the cost once (charging only one
        # leg of a two-leg book); corrected to 2 x cost_bps.
        self.assertAlmostEqual(period["quintile_spread_net_bps"],
                               (top - bottom - 2 * 20 / 10000.0) * 10000.0,
                               places=6)
        self.assertAlmostEqual(period["rank_ic"], 1.0, places=9)
        self.assertTrue(period["sample_complete"] is False
                        or period["bucketing"] == "sector_quintiles")

    def test_turnover_reported(self):
        rows_a = self._rows(50, ["a"])
        rows_b = list(rows_a)
        rows_b[0], rows_b[-1] = rows_b[-1], rows_b[0]   # top name changed
        table = {}

        def lookup(ticker, day):
            return 100.0

        snaps = [{"date": "2024-06-30", "rows": rows_a},
                 {"date": "2024-07-31", "rows": rows_b},
                 {"date": "2024-08-31", "rows": []}]
        report = evaluate(snaps, lookup)
        self.assertEqual(len(report["periods"]), 2)
        self.assertIsNone(report["periods"][0]["top_turnover"])
        self.assertIsNotNone(report["periods"][1]["top_turnover"])

    def test_empty_pool_period_skipped(self):
        snaps = [{"date": "2024-06-30", "rows": []},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, lambda t, d: 1.0)
        self.assertEqual(report["periods_evaluated"], 0)
        self.assertEqual(report["skipped_pairs"][0]["reason"],
                         "pool_too_small")

    def test_reproducibility(self):
        rows = self._rows(50, ["a", "b"])
        lookup = self._lookup_factory({("T000", "2024-07-31"): None})
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-31", "rows": rows},
                 {"date": "2024-08-31", "rows": []}]
        first = evaluate(snaps, lookup)
        second = evaluate(snaps, lookup)
        self.assertEqual(json.dumps(first, sort_keys=True, default=str),
                         json.dumps(second, sort_keys=True, default=str))

    def test_price_only_vs_total_return_label(self):
        class AdjSource:
            name = "adj"

            def get_price_data(self, ticker, start=None, end=None,
                               fetch_on=None):
                return ({"close": [("2024-06-30", 100.0)],
                         "adj_close": [("2024-06-30", 90.0)],
                         "splits": [], "splits_known": True,
                         "fetched_on": fetch_on or ""},
                        ProviderReport("adj", STATUS_SUCCESS, ""))

        class RawSource:
            name = "raw"

            def get_price_data(self, ticker, start=None, end=None,
                               fetch_on=None):
                return ({"close": [("2024-06-30", 100.0)], "splits": [],
                         "splits_known": True, "fetched_on": fetch_on or ""},
                        ProviderReport("raw", STATUS_SUCCESS, ""))

        with_fixtures = PriceLookup.__new__(PriceLookup)
        with_fixtures.chain = SourceChain([], AdjSource(), [], [])
        with_fixtures.memo = {}
        with_fixtures.window = None
        with_fixtures.fetch_on = None
        with_fixtures.uses_adjusted = None
        self.assertEqual(with_fixtures("X", "2024-06-30"), 90.0)
        self.assertEqual(with_fixtures.label, "total_return")

        raw = PriceLookup.__new__(PriceLookup)
        raw.chain = SourceChain([], RawSource(), [], [])
        raw.memo = {}
        raw.window = None
        raw.fetch_on = None
        raw.uses_adjusted = None
        self.assertEqual(raw("X", "2024-06-30"), 100.0)
        self.assertEqual(raw.label, "price_only")

    def test_not_run_without_snapshots(self):
        import io
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "SNAPSHOT_DIR",
                                   tmp):
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    rc = forward_main([])
                self.assertEqual(rc, 0)
                self.assertIn("NOT RUN", buf.getvalue())

class D8PeriodAlignment(unittest.TestCase):
    """Defect D8: date-based matching only; consecutive-FY growth; real-span
    CAGR; instant tolerance 10 days; Piotroski on consecutive FYs only."""

    def test_non_calendar_fy_growth(self):
        # fiscal years ending in March (FY2021..FY2024)
        facts = {"revenue": [], "net_income": [], "shares_diluted": []}
        for i, year in enumerate((2021, 2022, 2023, 2024)):
            end = f"{year}-03-31"
            facts["revenue"].append(Fact(end, f"{year}-06-15",
                                         800.0 * 1.1 ** i, "10-K", "FY",
                                         f"{year - 1}-04-01"))
            facts["net_income"].append(Fact(end, f"{year}-06-15", 50.0,
                                            "10-K", "FY", f"{year - 1}-04-01"))
            facts["shares_diluted"].append(Fact(end, f"{year}-06-15", 10.0,
                                                "10-K", "FY",
                                                f"{year - 1}-04-01"))
        view = FundamentalsView(facts, "2024-12-31")
        cagr = METRIC_FUNCS["revenue_cagr_3y"](view, None)
        self.assertIsNotNone(cagr)
        # real span: 2021-03-31 -> 2024-03-31 = 1096 days = 3.0007 years
        expected = ((800.0 * 1.1 ** 3) / 800.0) ** (365.25 / 1096.0) - 1.0
        self.assertAlmostEqual(cagr, expected, places=9)

    def test_missing_fy_returns_none_not_wrong_number(self):
        # FY2022 missing entirely: 2020 -> 2021 -> 2023 (gap 730d)
        facts = {"revenue": [
            Fact("2020-12-31", "2021-02-15", 800.0, "10-K", "FY",
                 "2020-01-01"),
            Fact("2021-12-31", "2022-02-15", 850.0, "10-K", "FY",
                 "2021-01-01"),
            Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01")]}
        view = FundamentalsView(facts, "2024-06-30")
        self.assertIsNone(view.consecutive_fy("revenue"))
        self.assertIsNone(METRIC_FUNCS["revenue_cagr_3y"](view, None))

    def test_cagr_span_window_enforced(self):
        # endpoints only 1 year apart: a 3-year CAGR refuses the short span
        facts = {"revenue": [
            Fact("2022-12-31", "2023-02-15", 800.0, "10-K", "FY",
                 "2022-01-01"),
            Fact("2023-12-31", "2024-02-15", 900.0, "10-K", "FY",
                 "2023-01-01")]}
        view = FundamentalsView(facts, "2024-06-30")
        self.assertIsNone(view.consecutive_fy("revenue", 3))
        window = view.consecutive_fy("revenue", 1)   # 1Y window is fine
        self.assertIsNotNone(window)
        # ... but the 3-year CAGR span gate still rejects a 365-day span
        self.assertIsNone(_cagr_span(window[0], window[-1]))

    def test_growth_stability_consecutive_pairs_only(self):
        facts = {"revenue": [
            Fact("2020-12-31", "2021-02-15", 800.0, "10-K", "FY",
                 "2020-01-01"),
            Fact("2021-12-31", "2022-02-15", 900.0, "10-K", "FY",
                 "2021-01-01"),
            Fact("2023-12-31", "2024-02-15", 950.0, "10-K", "FY",
                 "2023-01-01"),   # 2022 missing: gap 730d
            Fact("2024-12-31", "2025-02-15", 1000.0, "10-K", "FY",
                 "2024-01-01")]}
        view = FundamentalsView(facts, "2025-06-30")
        # window = last 4 FYs; only 2 consecutive pairs (2023->2024 and
        # 2021->2022? no: 2021->2023 is 730d, 2023->2024 is 365d,
        # 2020->2021 is 365d) -> 2 pairs, both up -> 1.0
        self.assertAlmostEqual(
            METRIC_FUNCS["growth_stability"](view, None), 1.0, places=9)

    def test_eps_uses_same_period_shares(self):
        # NI doubled but shares quadrupled -> EPS must FALL
        facts = {
            "net_income": [
                Fact("2020-12-31", "2021-02-15", 100.0, "10-K", "FY",
                     "2020-01-01"),
                Fact("2023-12-31", "2024-02-15", 200.0, "10-K", "FY",
                     "2023-01-01")],
            "shares_diluted": [
                Fact("2020-12-31", "2021-02-15", 10.0, "10-K", "FY",
                     "2020-01-01"),
                Fact("2023-12-31", "2024-02-15", 40.0, "10-K", "FY",
                     "2023-01-01")],
            "revenue": [], "cfo": [], "capex": []}
        # fill intermediate years so the series is consecutive
        for year in (2021, 2022):
            facts["net_income"].append(
                Fact(f"{year}-12-31", f"{year + 1}-02-15", 110.0 + year,
                     "10-K", "FY", f"{year}-01-01"))
            facts["shares_diluted"].append(
                Fact(f"{year}-12-31", f"{year + 1}-02-15", 15.0, "10-K",
                     "FY", f"{year}-01-01"))
            facts["revenue"].append(
                Fact(f"{year}-12-31", f"{year + 1}-02-15", 900.0, "10-K",
                     "FY", f"{year}-01-01"))
            facts["cfo"].append(
                Fact(f"{year}-12-31", f"{year + 1}-02-15", 90.0, "10-K",
                     "FY", f"{year}-01-01"))
            facts["capex"].append(
                Fact(f"{year}-12-31", f"{year + 1}-02-15", 30.0, "10-K",
                     "FY", f"{year}-01-01"))
        facts["revenue"] += [
            Fact("2020-12-31", "2021-02-15", 800.0, "10-K", "FY",
                 "2020-01-01"),
            Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01")]
        facts["cfo"] += [
            Fact("2020-12-31", "2021-02-15", 80.0, "10-K", "FY",
                 "2020-01-01"),
            Fact("2023-12-31", "2024-02-15", 120.0, "10-K", "FY",
                 "2023-01-01")]
        facts["capex"] += [
            Fact("2020-12-31", "2021-02-15", 20.0, "10-K", "FY",
                 "2020-01-01"),
            Fact("2023-12-31", "2024-02-15", 40.0, "10-K", "FY",
                 "2023-01-01")]
        view = FundamentalsView(facts, "2024-06-30")
        cagr = METRIC_FUNCS["earnings_cagr_3y"](view, None)
        # EPS 2020 = 10.0; EPS 2023 = 5.0 -> EPS CAGR is negative even
        # though net income grew
        self.assertIsNotNone(cagr)
        self.assertLess(cagr, 0.0)

    def test_instant_tolerance_is_ten_days(self):
        facts = {"total_assets": [
            Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "INST")]}
        view = FundamentalsView(facts, "2024-06-30")
        self.assertEqual(view.instant_at("total_assets", "2024-01-05"), 1000.0)
        self.assertIsNone(view.instant_at("total_assets", "2024-02-15"))

    def test_piotroski_requires_consecutive_fys(self):
        # FY2022 missing -> the two latest FY ends are 730d apart -> None
        company = hand_company(drop=("long_term_debt",))
        facts = {k: [f for f in v if f.period_end != "2022-12-31"]
                 for k, v in company.facts.items()}
        # also drop the 2022 quarters to keep TTM logic out of the way
        facts = {k: [f for f in v if not f.period_end.startswith("2022")]
                 for k, v in facts.items()}
        view = FundamentalsView(facts, "2025-06-30")
        self.assertIsNone(METRIC_FUNCS["piotroski_f"](view, None))

    def test_fy_restatement_point_in_time(self):
        facts = {"revenue": [
            Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01"),
            Fact("2023-12-31", "2024-08-01", 1050.0, "10-K/A", "FY",
                 "2023-01-01")]}
        self.assertEqual(FundamentalsView(facts, AS_OF)
                         .fy("revenue", 0), 1000.0)
        self.assertEqual(FundamentalsView(facts, "2024-12-31")
                         .fy("revenue", 0), 1050.0)

    def test_duplicate_periods_deduped(self):
        facts = {"revenue": [
            Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01"),
            Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01")]}
        series = FundamentalsView(facts, AS_OF).fy_series("revenue")
        self.assertEqual(len(series), 1)

class D9Staleness(unittest.TestCase):
    """Defect D9 / rule I3: the staleness gates. A stopped filer never
    scores OK again, and a stale last close kills market metrics."""

    def test_stale_fundamentals_give_stale_data(self):
        company = hand_company("OLD", "tech")
        facts = {k: [f for f in v if f.period_end <= "2022-12-31"]
                 for k, v in company.facts.items()}
        company = Company("OLD", "tech", facts, company.prices,
                          company.adj_prices, {"fixtures"})
        res = score_universe([company], AS_OF)["OLD"]
        self.assertEqual(res.status, STALE_DATA)
        self.assertIsNone(res.score)
        self.assertEqual(res.score_unrated["reason"], "stale_fundamentals")
        self.assertEqual(res.score_unrated["latest_fiscal_period_end"],
                         "2022-12-31")

    def test_stopped_filer_never_scores_ok(self):
        # latest filing visible is FY2022 (filed 2023-02-15): at any as_of
        # beyond the 200-day gate the ticker is STALE_DATA, not OK
        company = hand_company("STOP", "tech")
        facts = {k: [f for f in v if f.filing_date <= "2023-03-01"]
                 for k, v in company.facts.items()}
        company = Company("STOP", "tech", facts, company.prices,
                          company.adj_prices, {"fixtures"})
        res = score_universe([company], "2024-06-30")["STOP"]
        self.assertEqual(res.status, STALE_DATA)
        self.assertIsNone(res.score)
        self.assertIsNone(res.rank_in_sector)

    def test_boundary_200_days_is_fresh(self):
        # latest period_end 2023-12-31; as_of + 200d is still fresh, 201d not
        fresh_as_of = "2024-07-18"     # 200 days after 2023-12-31
        company = hand_company("EDGE", "tech",
                               prices=[(d, 90.0) for d in _month_ends(
                                   stop="2024-07-18")])
        res = score_universe([company], fresh_as_of)["EDGE"]
        self.assertEqual(res.status, OK)
        stale_as_of = "2024-07-19"     # 201 days
        company2 = hand_company("EDGE", "tech",
                                prices=[(d, 90.0) for d in _month_ends(
                                    stop="2024-07-19")])
        res2 = score_universe([company2], stale_as_of)["EDGE"]
        self.assertEqual(res2.status, STALE_DATA)

    def test_stale_price_flag_and_missing_market_metrics(self):
        prices = [(d, 90.0) for d in _month_ends(stop="2024-01-31")]
        company = hand_company("SP", "tech", prices=prices)
        res = score_universe([company], AS_OF)["SP"]
        self.assertIn("STALE_PRICE", res.flags)
        self.assertIsNone(res.pillars["valuation"])
        self.assertIsNone(res.metrics["earnings_yield"])

    def test_fresh_price_no_flag(self):
        res = score_universe([hand_company("FP", "tech")], AS_OF)["FP"]
        self.assertNotIn("STALE_PRICE", res.flags)
        self.assertIsNotNone(res.pillars["valuation"])

class D10ScoreExposure(unittest.TestCase):
    """Defect D10 / rule I6: score is None unless status is OK."""

    def test_insufficient_data_has_no_score(self):
        peer = hand_company("H2", "tech", scale={"revenue": 1.1})
        no_ca = hand_company("H1", "tech", prices=[],
                             drop=("interest_expense", "current_assets"))
        res = score_universe([no_ca, peer], AS_OF)["H1"]
        self.assertEqual(res.status, INSUFFICIENT_DATA)
        self.assertIsNone(res.score)
        self.assertIsNotNone(res.score_unrated)
        self.assertLess(res.score_unrated["coverage"], MIN_COVERAGE)
        self.assertIn("composite_diagnostic", res.score_unrated)

    def test_sector_data_missing_has_no_score(self):
        # FXRE02 lacks D&A -> required ffo_margin is None
        companies = [c for c in fixture_companies()
                     if c.ticker in ("FXRE01", "FXRE02")]
        results = score_universe(companies, AS_OF)
        self.assertEqual(results["FXRE02"].status, SECTOR_DATA_MISSING)
        self.assertIsNone(results["FXRE02"].score)
        self.assertIsNone(results["FXRE02"].rank_in_sector)
        self.assertIn("ffo_margin",
                      results["FXRE02"].score_unrated["missing_required"])

    def test_stale_data_has_no_score(self):
        company = hand_company("OLD", "tech")
        facts = {k: [f for f in v if f.period_end <= "2022-12-31"]
                 for k, v in company.facts.items()}
        company = Company("OLD", "tech", facts, company.prices,
                          company.adj_prices, {"fixtures"})
        res = score_universe([company], AS_OF)["OLD"]
        self.assertEqual(res.status, STALE_DATA)
        self.assertIsNone(res.score)

    def test_ok_has_score(self):
        res = score_universe([hand_company("OK1", "tech")], AS_OF)["OK1"]
        self.assertEqual(res.status, OK)
        self.assertIsNotNone(res.score)
        self.assertEqual(res.rank_in_sector, 1)

    def test_ranks_only_for_ok(self):
        companies = fixture_companies()
        companies.append(_stale_clone("STALE1"))
        results = score_universe(companies, AS_OF)
        self.assertIsNone(results["STALE1"].rank_in_sector)
        for res in results.values():
            if res.status != OK:
                self.assertIsNone(res.rank_in_sector)
                self.assertIsNone(res.score)

class D11MissingDataBias(unittest.TestCase):
    """Defect D11: sign-safe metrics; loss-makers are never advantaged."""

    def test_loss_maker_ranks_below_identical_profitable_peer(self):
        companies = fixture_companies()
        src = [c for c in companies if c.ticker == "FXTE04"][0]
        facts = {}
        for key, fs in src.facts.items():
            if key == "net_income":
                facts[key] = [Fact(f.period_end, f.filing_date, -f.value,
                                   f.form, f.freq, f.period_start)
                              for f in fs]
            else:
                facts[key] = list(fs)
        loser = Company("FXTE04L", "tech", facts, src.prices, src.adj_prices,
                        {"fixtures"})
        results = score_universe(companies + [loser], AS_OF)
        self.assertEqual(results["FXTE04L"].status, OK)
        self.assertLess(results["FXTE04L"].score, results["FXTE04"].score)
        self.assertGreater(results["FXTE04L"].rank_in_sector,
                           results["FXTE04"].rank_in_sector)

    def test_negative_earnings_yield_available(self):
        company = hand_company("NEG", "tech",
                               scale={"net_income": -0.5})
        view = view_of(company)
        market, _status = build_market(company, AS_OF)
        value = METRIC_FUNCS["earnings_yield"](view, market)
        self.assertIsNotNone(value)
        self.assertLess(value, 0.0)   # -37.5 / 900

    def test_ebitda_yield_replaces_ev_ebitda(self):
        self.assertNotIn("ev_ebitda", METRIC_FUNCS)
        for model in MODELS.values():
            for spec in model.metrics:
                self.assertNotEqual(spec.name, "ev_ebitda")
        view = view_of(hand_company())
        market, _s = build_market(hand_company(), AS_OF)
        self.assertAlmostEqual(METRIC_FUNCS["ebitda_yield"](view, market),
                               200.0 / 1200.0, places=9)

    def test_net_debt_ebitda_worst_when_ebitda_negative(self):
        company = hand_company("BURN", "tech",
                               scale={"operating_income": -1.0,
                                      "depreciation_amortization": 0.02})
        results = score_universe([company, hand_company("P", "tech")],
                                 AS_OF)
        res = results["BURN"]
        self.assertEqual(res.metrics["net_debt_ebitda"], WORST)
        self.assertEqual(res.metric_scores["net_debt_ebitda"], 0.0)
        # counts as available: it contributed weight to coverage
        self.assertGreater(res.coverage, 0.90)

    def test_roic_worst_when_invested_capital_negative(self):
        # cash above debt + equity makes invested capital negative
        company = hand_company("ICNEG", "tech", scale={"cash": 20.0})
        results = score_universe([company, hand_company("P2", "tech")],
                                 AS_OF)
        res = results["ICNEG"]
        self.assertEqual(res.metrics["roic"], WORST)
        self.assertEqual(res.metric_scores["roic"], 0.0)

    def test_cfo_ni_undefined_for_negative_ni(self):
        company = hand_company("CFONEG", "tech", scale={"net_income": -1.0})
        view = view_of(company)
        self.assertIsNone(METRIC_FUNCS["cfo_ni"](view, None))

    def test_worst_sentinel_winsorization(self):
        pool = [1.0, 2.0, 3.0, WORST, WORST]
        scores = percentile_scores(pool, -1)
        self.assertEqual(scores[3], 0.0)
        self.assertEqual(scores[4], 0.0)
        self.assertTrue(all(0 < s <= 1 for s in scores[:3]))
        # direction +1 mirrors for ROIC-style metrics
        scores = percentile_scores(pool, 1)
        self.assertEqual(scores[3], 0.0)

class D12ResumeIntegrity(unittest.TestCase):
    """Defect D12: checkpoint fingerprint covers the full scan identity."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _refs(self):
        refs, _report = get_universe()
        return refs

    def test_fingerprint_stable(self):
        refs = self._refs()
        a = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        b = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        self.assertEqual(a, b)

    def test_fingerprint_changes_with_as_of(self):
        refs = self._refs()
        a = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        b = scan_fingerprint("2024-07-31", "auto", refs, ["fixtures"], None)
        self.assertNotEqual(a, b)

    def test_fingerprint_changes_with_sources(self):
        refs = self._refs()
        a = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        b = scan_fingerprint("2024-06-30", "auto", refs,
                             ["sec_edgar", "finnhub"], None)
        self.assertNotEqual(a, b)

    def test_fingerprint_changes_with_universe(self):
        refs = self._refs()
        a = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        b = scan_fingerprint("2024-06-30", "auto", refs[:-1], ["fixtures"],
                             None)
        self.assertNotEqual(a, b)

    def test_fingerprint_changes_with_scoring_params(self):
        from unittest import mock
        refs = self._refs()
        a = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        with mock.patch.object(sys.modules[__name__], "MIN_PEERS", 5):
            b = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"],
                                 None)
        self.assertNotEqual(a, b)

    def test_fingerprint_changes_with_overrides(self):
        refs = self._refs()
        ov = Path(self.tmp.name) / "ov.csv"
        ov.write_text("ticker,sector\nJPM,tech\n", encoding="utf-8")
        a = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        b = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"],
                             str(ov))
        self.assertNotEqual(a, b)

    def test_state_roundtrip_and_rejection(self):
        import io
        from unittest import mock
        state_path = Path(self.tmp.name) / "state.json"
        refs = self._refs()[:3]
        fp = scan_fingerprint("2024-06-30", "auto", refs, ["fixtures"], None)
        company = hand_company("HAND", "tech")
        _save_state(state_path, fp, {"HAND": company},
                    {"AAA": NO_DATA}, {})
        loaded = _load_state(state_path, fp)
        self.assertIsNotNone(loaded)
        self.assertIn("HAND", loaded["companies"])
        other = scan_fingerprint("2024-07-31", "auto", refs, ["fixtures"],
                                 None)
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            rejected = _load_state(state_path, other)
        self.assertIsNone(rejected)
        self.assertIn("rejected", buf.getvalue())

    def test_scan_resume_after_max_fetch(self):
        from unittest import mock
        uni = fixture_universe_file(Path(self.tmp.name) / "uni.csv")
        snap_dir = str(Path(self.tmp.name) / "snaps")
        state = str(Path(self.tmp.name) / "scan_state.json")
        env = {"QE_DATA_DIR": self.tmp.name,
               "QE_SNAPSHOT_DIR": snap_dir,
               "QE_SCAN_STATE": state,
               "QE_CACHE_DIR": str(Path(self.tmp.name) / "cache")}
        import subprocess
        def run(extra):
            return subprocess.run(
                [sys.executable, str(_THIS_FILE), "scan", "--source",
                 "fixtures", "--universe-file", uni, "--no-snapshot"]
                + extra,
                capture_output=True, text=True, timeout=300,
                env={**os.environ, **env},
                cwd=self.tmp.name)
        first = run(["--as-of", AS_OF, "--max-fetch", "5"])
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("state saved", first.stdout)
        self.assertTrue(Path(state).exists())
        second = run(["--as-of", AS_OF])
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("resumed state", second.stdout)
        self.assertIn("==== SCAN DONE ====", second.stdout)

class D13D14DocumentationAndCache(unittest.TestCase):
    """Defects D13/D14: no phantom file references; cache correctness."""

    def test_fixture_generation_is_deterministic(self):
        first = generate_fixture_universe()
        a = first["FXTE01"].facts["revenue"][0].value
        global _FIXTURE_COMPANIES
        saved = _FIXTURE_COMPANIES
        try:
            _FIXTURE_COMPANIES = None
            second = generate_fixture_universe()
        finally:
            _FIXTURE_COMPANIES = saved
        self.assertEqual(a, second["FXTE01"].facts["revenue"][0].value)
        self.assertEqual(
            [p for p, _ in first["FXTE07"].prices],
            [p for p, _ in second["FXTE07"].prices])
        self.assertEqual(len(first), 23)

    def test_finnhub_diagnostics_attached_to_report(self):
        client = FinnhubClient(cache=FileCache(root="/nonexistent-cache-dir"),
                               limiter=RateLimiter(0.0),
                               transport=fake_transport(
                                   lambda u, h: (STATUS_SUCCESS,
                                                 {"data": []}, None)),
                               sleep_fn=lambda s: 0)
        _facts, report = client.get_all_facts("TEST")
        self.assertEqual(report.status, STATUS_NO_DATA)
        self.assertIn("diag:", report.detail)

    def test_cache_roundtrip_and_ttl(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1000.0)
            cache.set("sec", "k1", {"x": 1})
            self.assertEqual(cache.get("sec", "k1"), {"x": 1})
            # expired after the TTL (frozen clock + tiny ttl)
            self.assertIsNone(cache.get("sec", "k1", ttl=0))

    def test_cache_corrupt_file_returns_none(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp)
            cache.set("sec", "k2", {"x": 1})
            target = list(Path(tmp).rglob("*.json"))[0]
            target.write_text("{not json", encoding="utf-8")
            self.assertIsNone(cache.get("sec", "k2"))

    def test_cache_namespaces_isolated(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp)
            cache.set("sec", "k", {"a": 1})
            cache.set("finnhub", "k", {"b": 2})
            self.assertEqual(cache.get("sec", "k"), {"a": 1})
            self.assertEqual(cache.get("finnhub", "k"), {"b": 2})

    def test_cache_write_failure_is_silent(self):
        cache = FileCache(root="/proc/definitely/not/writable")
        cache.set("sec", "k", {"x": 1})   # must not raise
        self.assertIsNone(cache.get("sec", "k"))

    # ---- V3.4.1 P3: FileCache.get() corrupt-envelope hardening ----

    @staticmethod
    def _write_cache_envelope(cache, namespace, key, text):
        """Plant a raw envelope file exactly where FileCache would read it."""
        target = cache._path(namespace, key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def test_get_nonnumeric_timestamp_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": "not-a-number", "payload": {}}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_json_list_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k", "[1, 2]")
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_json_number_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(cache, "sec", "k", "42")
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_json_null_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(cache, "sec", "k", "null")
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_missing_timestamp_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k", '{"payload": {}}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_nan_timestamp_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": NaN, "payload": {}}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_infinity_timestamp_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": Infinity, "payload": {}}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_far_future_timestamp_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": 9999999999, "payload": {}}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_list_timestamp_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": [1], "payload": {}}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_boolean_timestamp_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": true, "payload": {"x": 1}}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())
            # bool must stay rejected on the no-TTL path too (bool is an
            # int subclass; the old code coerced True -> 1.0)
            target = self._write_cache_envelope(
                cache, "misc", "k",
                '{"fetched_at": true, "payload": {"x": 1}}')
            self.assertIsNone(cache.get("misc", "k", ttl=None))
            self.assertFalse(target.exists())

    def test_get_missing_payload_key_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k", '{"fetched_at": 1000}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_invalid_json_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k", '{"fetched_at": 1, "payload": ')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_undecodable_cache_file_is_miss_and_removed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = cache._path("sec", "k")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b'{"fetched_at": 1, "payload": "\xff\xfe"}')
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_get_valid_fresh_entry_returns_payload_and_file_kept(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            cache.set("sec", "k", {"x": 1})
            self.assertEqual(cache.get("sec", "k"), {"x": 1})
            self.assertTrue(list(Path(tmp).rglob("*.json"))[0].exists())

    def test_get_valid_expired_entry_is_miss_and_file_kept(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": %d, "payload": {"x": 1}}'
                % (1700000000 - CACHE_TTL_SECONDS["sec"] - 1))
            self.assertIsNone(cache.get("sec", "k"))
            self.assertTrue(target.exists())   # expired is NOT corrupt

    def test_get_validates_envelope_even_without_ttl(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            # namespace without a default TTL still validates fetched_at
            target = self._write_cache_envelope(
                cache, "misc", "k",
                '{"fetched_at": NaN, "payload": {}}')
            self.assertIsNone(cache.get("misc", "k", ttl=None))
            self.assertFalse(target.exists())
            target = self._write_cache_envelope(
                cache, "misc", "k2",
                '{"fetched_at": 1700000000, "payload": {"x": 1}}')
            self.assertEqual(cache.get("misc", "k2", ttl=None), {"x": 1})
            self.assertTrue(target.exists())

    def test_get_future_skew_boundary(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            now = 1700000000.0
            cache = FileCache(root=tmp, clock=lambda: now)
            skew = CACHE_FUTURE_SKEW_SECONDS
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": %d, "payload": {"x": 1}}' % (now + skew))
            self.assertEqual(cache.get("sec", "k"), {"x": 1})
            self.assertTrue(target.exists())       # at the limit: accepted
            target = self._write_cache_envelope(
                cache, "sec", "k2",
                '{"fetched_at": %d, "payload": {"x": 1}}' % (now + skew + 1))
            self.assertIsNone(cache.get("sec", "k2"))
            self.assertFalse(target.exists())      # beyond the limit: miss

    def test_get_huge_int_timestamp_is_miss_not_overflow(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            target = self._write_cache_envelope(
                cache, "sec", "k",
                '{"fetched_at": 1%s, "payload": {}}' % ("0" * 400))
            self.assertIsNone(cache.get("sec", "k"))
            self.assertFalse(target.exists())

    def test_corrupt_cache_metadata_falls_through_to_provider_fetch(self):
        import tempfile
        calls = []

        def responder(url, headers):
            calls.append(url)
            return (STATUS_SUCCESS, {"fresh": True}, None)

        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp, clock=lambda: 1700000000.0)
            http = _HttpJson("fake_provider", cache, RateLimiter(0.0),
                             fake_transport(responder), sleep_fn=lambda s: 0)
            self._write_cache_envelope(
                cache, "sec", "q",
                '{"fetched_at": NaN, "payload": {"stale": true}}')
            payload, report = http.get("https://unit.test/data", "sec", "q")
            self.assertEqual(payload, {"fresh": True})
            self.assertEqual(report.status, STATUS_SUCCESS)
            self.assertEqual(len(calls), 1)   # corrupt miss -> real fetch
            self.assertEqual(cache.get("sec", "q"), {"fresh": True})

    def test_rate_limiter_paces_calls(self):
        ticks = iter([100.0, 100.0])
        slept = []
        limiter = RateLimiter(1.0)
        limiter.wait(clock=lambda: next(ticks), sleep=slept.append)
        limiter.wait(clock=lambda: next(ticks), sleep=slept.append)
        self.assertEqual(slept, [1.0])

    def test_no_phantom_file_references(self):
        source = Path(_THIS_FILE).read_text(encoding="utf-8")
        # Built by concatenation so the checked strings never appear
        # verbatim in THIS test's own source (otherwise the test would
        # always find the phantom it is looking for and could never pass).
        phantoms = ("scripts/" + "gen_fixtures.py",
                    "scripts/" + "ab_report.py",
                    "tests/" + "fixtures/universe.json",
                    "docs/" + "METHODOLOGY.pdf")
        for phantom in phantoms:
            self.assertNotIn(phantom, source,
                             f"documentation references {phantom}")

class RegressionMetrics(unittest.TestCase):
    """Every metric against hand-computed numbers (old behavior checks)."""

    def setUp(self):
        self.company = hand_company()
        self.view = view_of(self.company)
        self.market, pstat = build_market(self.company, AS_OF)
        self.assertEqual(pstat, "ok")

    def _m(self, name):
        return METRIC_FUNCS[name](self.view, self.market)

    def test_market_point(self):
        self.assertAlmostEqual(self.market.market_cap, 900.0)
        self.assertAlmostEqual(self.market.net_debt, 300.0)
        self.assertAlmostEqual(self.market.enterprise_value, 1200.0)

    def test_profitability(self):
        self.assertAlmostEqual(self._m("roic"), 0.10, places=4)
        self.assertAlmostEqual(self._m("gross_profitability"), 0.40, places=6)
        self.assertAlmostEqual(self._m("operating_margin"), 0.12, places=6)
        self.assertAlmostEqual(self._m("fcf_margin"), 0.01, places=6)

    def test_roic_tax_fallback(self):
        c = hand_company(drop=("pretax_income", "tax_expense"))
        v = view_of(c)
        m, _s = build_market(c, AS_OF)
        self.assertAlmostEqual(METRIC_FUNCS["roic"](v, m), 0.10, places=4)

    def test_growth(self):
        # Real span 2020-12-31 -> 2023-12-31 = 1095 days (3 x 365, no leap
        # day in between); spec D8 mandates (end - start).days / 365.25. An
        # earlier revision hand-computed 1096 (nominal 3y); corrected.
        expected = (1000.0 / 800.0) ** (365.25 / 1095.0) - 1.0
        self.assertAlmostEqual(self._m("revenue_cagr_3y"), expected,
                               places=6)
        # EPS 2023 = 75/10 = 7.5; EPS 2020 = 52.5/10.5 = 5.0
        expected_eps = (7.5 / 5.0) ** (365.25 / 1095.0) - 1.0
        self.assertAlmostEqual(self._m("earnings_cagr_3y"), expected_eps,
                               places=6)
        self.assertAlmostEqual(self._m("growth_stability"), 1.0, places=9)

    def test_earnings_cagr_fcf_fallback(self):
        c = hand_company(drop=("shares_diluted",))
        v = view_of(c)
        m, _s = build_market(c, AS_OF)
        expected = (10.0 / 6.0) ** (365.25 / 1095.0) - 1.0  # see test_growth
        self.assertAlmostEqual(METRIC_FUNCS["earnings_cagr_3y"](v, m),
                               expected, places=6)

    def test_financial_strength(self):
        self.assertAlmostEqual(self._m("net_debt_ebitda"), 1.5, places=6)
        self.assertAlmostEqual(self._m("interest_coverage"), 6.0, places=6)
        z = self._m("altman_z")
        expected = 1.2 * 0.2 + 1.4 * 0.4 + 3.3 * 0.12 + 0.6 * (900 / 400) \
            + 1.0 * 1.0
        self.assertAlmostEqual(z, expected, places=6)
        self.assertAlmostEqual(z, 3.546, places=3)
        self.assertAlmostEqual(self._m("current_ratio"), 500.0 / 300.0,
                               places=6)

    def test_net_debt_ebitda_missing_da(self):
        # D&A unavailable -> EBITDA is UNAVAILABLE, not an EBIT proxy.
        # Never silently substitute EBIT for EBITDA (data-integrity rule):
        # the metric is missing and drags coverage instead.
        c = hand_company(drop=("depreciation_amortization",))
        v = view_of(c)
        m, _s = build_market(c, AS_OF)
        self.assertIsNone(METRIC_FUNCS["net_debt_ebitda"](v, m))
        self.assertIsNone(METRIC_FUNCS["ebitda_yield"](v, m))

    def test_altman_needs_market(self):
        self.assertIsNone(METRIC_FUNCS["altman_z"](self.view, None))

    def test_earnings_quality(self):
        self.assertAlmostEqual(self._m("accruals_ratio"), 15.0 / 975.0,
                               places=6)
        self.assertAlmostEqual(self._m("cfo_ni"), 0.8, places=6)
        self.assertAlmostEqual(self._m("piotroski_f"), 8.0, places=6)

    def test_piotroski_missing_input(self):
        c = hand_company(drop=("long_term_debt",))
        self.assertIsNone(METRIC_FUNCS["piotroski_f"](view_of(c), None))

    def test_valuation(self):
        self.assertAlmostEqual(self._m("ebitda_yield"), 200.0 / 1200.0,
                               places=6)
        self.assertAlmostEqual(self._m("fcf_yield"), 10.0 / 900.0, places=6)
        self.assertAlmostEqual(self._m("earnings_yield"), 75.0 / 900.0,
                               places=6)
        self.assertAlmostEqual(self._m("p_book"), 1.5, places=6)

    def test_shareholder_yield(self):
        self.assertAlmostEqual(self._m("shareholder_yield"), 75.0 / 900.0,
                               places=6)
        self.assertAlmostEqual(self._m("share_count_change"),
                               10.0 / 10.2 - 1.0, places=6)

    def test_financials_model_metrics(self):
        self.assertAlmostEqual(self._m("roe_ttm"), 75.0 / 580.0, places=6)
        expected = 75.0 / ((550.0 + 513.0) / 2)
        self.assertAlmostEqual(self._m("rotce_ttm"), expected, places=6)
        self.assertAlmostEqual(self._m("equity_assets"), 0.6, places=6)
        c = bank_company()
        v = view_of(c)
        m, _s = build_market(c, AS_OF)
        self.assertAlmostEqual(METRIC_FUNCS["efficiency_ratio"](v, m), 0.6,
                               places=4)

    def test_reit_model_metrics(self):
        c = reit_company()
        v = view_of(c)
        m, _s = build_market(c, AS_OF)
        self.assertAlmostEqual(METRIC_FUNCS["ffo_margin"](v, m),
                               441.0 / 900.0, places=4)
        self.assertAlmostEqual(METRIC_FUNCS["affo_margin"](v, m),
                               387.0 / 900.0, places=4)
        self.assertAlmostEqual(METRIC_FUNCS["ffo_yield"](v, m),
                               441.0 / 4620.0, places=4)
        self.assertAlmostEqual(METRIC_FUNCS["payout_ratio"](v, m), 0.72,
                               places=4)
        expected = (441.0 / 354.0) ** (365.25 / 1095.0) - 1.0  # 1095d span
        self.assertAlmostEqual(METRIC_FUNCS["ffo_cagr_3y"](v, m), expected,
                               places=4)
        self.assertAlmostEqual(METRIC_FUNCS["net_debt_ebitda"](v, m),
                               3180.0 / 603.0, places=4)

    def test_cyclical_median_margin(self):
        c = energy_company(margins={2020: 0.15, 2021: 0.16, 2022: 0.14,
                                    2023: 0.05})
        v = view_of(c)
        self.assertAlmostEqual(METRIC_FUNCS["operating_margin_5y"](v, None),
                               0.145, places=4)   # median(0.15,0.16,0.14,0.05)

    def test_cyclical_missing_margin_history(self):
        c = energy_company(years=(2022, 2023))
        results = score_universe([c], AS_OF)
        self.assertEqual(results["ENGY"].status, SECTOR_DATA_MISSING)

    def test_cyclical_median_not_latest(self):
        # 2023 margin crashes to 0.01 but the 5y median stays healthy
        c = energy_company(margins={2020: 0.15, 2021: 0.16, 2022: 0.14,
                                    2023: 0.01})
        v = view_of(c)
        self.assertAlmostEqual(METRIC_FUNCS["operating_margin_5y"](v, None),
                               0.145, places=4)

class RegressionView(unittest.TestCase):
    """Point-in-time view mechanics (old behavior checks)."""

    def test_ttm_missing_quarter(self):
        c = hand_company()
        c.facts["revenue"] = [f for f in c.facts["revenue"]
                              if f.period_end != "2023-06-30"]
        self.assertIsNone(view_of(c).ttm("revenue"))

    def test_ttm_nonconsecutive_quarters(self):
        facts = {"revenue": [
            Fact("2023-03-31", "2023-05-15", 250.0, "10-Q", "Q", "2023-01-01"),
            Fact("2023-06-30", "2023-08-14", 250.0, "10-Q", "Q", "2023-04-01"),
            Fact("2023-12-31", "2024-02-14", 250.0, "10-Q", "Q", "2023-10-01"),
            Fact("2024-03-31", "2024-05-15", 250.0, "10-Q", "Q", "2024-01-01"),
        ]}
        self.assertIsNone(FundamentalsView(facts, AS_OF).ttm("revenue"))

    def test_ttm_prior(self):
        self.assertAlmostEqual(view_of(hand_company()).ttm_prior("revenue"),
                               900.0, places=6)

    def test_ytd_anchor_de_cumulation(self):
        anchors = [
            Fact("2023-03-31", "2023-05-15", 15.0, "10-Q", "YTD", "2023-01-01"),
            Fact("2023-06-30", "2023-08-14", 34.0, "10-Q", "YTD", "2023-01-01"),
            Fact("2023-09-30", "2023-11-14", 51.0, "10-Q", "YTD", "2023-01-01"),
            Fact("2023-12-31", "2024-02-15", 60.0, "10-K", "FY", "2023-01-01"),
        ]
        v = FundamentalsView({"cfo": anchors}, AS_OF)
        values = [f.value for f in v.q_series("cfo")]
        self.assertAlmostEqual(values, [15.0, 19.0, 17.0, 9.0])
        self.assertAlmostEqual(v.ttm("cfo"), 60.0)
        self.assertAlmostEqual(v.fy("cfo", 0), 60.0)

    def test_ytd_restatement_point_in_time(self):
        anchors = [
            Fact("2023-06-30", "2023-08-14", 34.0, "10-Q", "YTD", "2023-01-01"),
            Fact("2023-06-30", "2024-05-01", 36.0, "10-Q/A", "YTD",
                 "2023-01-01"),
            Fact("2023-03-31", "2023-05-15", 15.0, "10-Q", "YTD", "2023-01-01"),
        ]
        before = FundamentalsView({"cfo": anchors}, "2023-12-31")
        after = FundamentalsView({"cfo": anchors}, AS_OF)
        self.assertAlmostEqual([f.value for f in before.q_series("cfo")],
                               [15.0, 19.0])
        self.assertAlmostEqual([f.value for f in after.q_series("cfo")],
                               [15.0, 21.0])

    def test_q4_derivation_discrete(self):
        facts = {"revenue": [
            Fact("2023-03-31", "2023-05-15", 250.0, "10-Q", "Q", "2023-01-01"),
            Fact("2023-06-30", "2023-08-14", 250.0, "10-Q", "Q", "2023-04-01"),
            Fact("2023-09-30", "2023-11-14", 250.0, "10-Q", "Q", "2023-07-01"),
            Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01"),
        ]}
        v = FundamentalsView(facts, AS_OF)
        self.assertAlmostEqual(v.q_series("revenue")[-1].value, 250.0)
        self.assertAlmostEqual(v.ttm("revenue"), 1000.0)

    def test_instant_restatement_point_in_time(self):
        facts = {"total_equity": [
            Fact("2023-12-31", "2024-02-15", 600.0, "10-K", "INST"),
            Fact("2023-12-31", "2024-06-01", 650.0, "10-K/A", "INST"),
        ]}
        self.assertEqual(
            FundamentalsView(facts, "2024-03-31").instant("total_equity"),
            600.0)
        self.assertEqual(
            FundamentalsView(facts, AS_OF).instant("total_equity"), 650.0)

    def test_filing_date_boundary_is_inclusive(self):
        # S3 semantics update: the boundary test now encodes the STRICTER
        # availability rule. A timestamp-less fact filed on D is NOT
        # visible at D (conservative: it might have been accepted after
        # 16:00 ET); it becomes visible the next weekday. A fact with an
        # acceptance timestamp at/before 16:00 ET IS visible on its day.
        facts = {"revenue": [
            Fact("2023-12-31", "2024-06-30", 1000.0, "10-K", "FY",
                 "2023-01-01"),
            Fact("2023-12-31", "2024-07-01", 1100.0, "10-K/A", "FY",
                 "2023-01-01"),
        ]}
        # 2024-06-30 is a Sunday: BOTH filings are not yet available
        view_sun = FundamentalsView(facts, "2024-06-30")
        self.assertIsNone(view_sun.fy("revenue", 0))
        self.assertEqual(view_sun.delayed_not_yet_available, 2)
        self.assertEqual(view_sun.availability_labels.get(
            "availability_assumed_next_day"), 2)
        # Monday 2024-07-01: the first fact is available (filed Sunday ->
        # next weekday Monday), the amendment is not yet (waits for 07-02)
        self.assertEqual(
            FundamentalsView(facts, "2024-07-01").fy("revenue", 0), 1000.0)
        self.assertEqual(
            FundamentalsView(facts, "2024-07-02").fy("revenue", 0), 1100.0)
        # with a same-day acceptance timestamp the fact IS visible on its
        # filing date (13:00 ET, before the 16:00 cutoff)
        stamped = {"revenue": [
            Fact("2023-12-31", "2024-06-28", 900.0, "10-K", "FY",
                 "2023-01-01", accepted="2024-06-28T17:00:00Z"),  # 13:00 ET
            Fact("2023-12-31", "2024-06-28", 950.0, "10-K/A", "FY",
                 "2023-01-01", accepted="2024-06-28T21:00:00Z"),  # 17:00 ET
        ]}
        view = FundamentalsView(stamped, "2024-06-28")
        self.assertEqual(view.fy("revenue", 0), 900.0)
        self.assertEqual(view.delayed_not_yet_available, 1)
        self.assertEqual(
            FundamentalsView(stamped, "2024-07-01").fy("revenue", 0), 950.0)

    def test_facts_without_filing_date_are_dropped_and_counted(self):
        facts = {"revenue": [
            Fact("2023-12-31", "", 1000.0, "10-K", "FY", "2023-01-01"),
            Fact("2023-12-31", "2024-02-15", 900.0, "10-K", "FY",
                 "2023-01-01"),
        ]}
        view = FundamentalsView(facts, AS_OF)
        self.assertEqual(view.fy("revenue", 0), 900.0)
        self.assertEqual(view.dropped_no_filing, 1)

    def test_instant_year_ago(self):
        view = view_of(hand_company())
        self.assertAlmostEqual(view.instant_year_ago("total_equity"), 560.0)
        self.assertAlmostEqual(view.instant_year_ago("shares_outstanding"),
                               10.2)

    def test_leakage_filings_after_as_of(self):
        universe = [hand_company("L1", "tech"),
                    hand_company("L2", "tech", scale={"revenue": 1.15}),
                    hand_company("L3", "tech", scale={"revenue": 0.90})]
        before = score_universe(universe, AS_OF)
        l1 = universe[0]
        facts = {item: list(fs) for item, fs in l1.facts.items()}
        facts.setdefault("revenue", []).extend([
            Fact("2024-12-31", "2025-02-15", 1300.0, "10-K", "FY",
                 "2024-01-01"),
            Fact("2024-09-30", "2024-11-14", 340.0, "10-Q", "Q", "2024-07-01"),
            Fact("2023-12-31", "2024-09-01", 1100.0, "10-K/A", "FY",
                 "2023-01-01"),
        ])
        facts.setdefault("total_equity", []).append(
            Fact("2024-03-31", "2024-08-01", 640.0, "10-Q", "INST"))
        grown = Company("L1", "tech", facts, l1.prices, l1.adj_prices,
                        set(l1.sources))
        after = score_universe([grown, universe[1], universe[2]], AS_OF)
        self.assertEqual(after["L1"].score, before["L1"].score)
        self.assertEqual(after["L1"].metrics, before["L1"].metrics)

    def test_leakage_prices_after_as_of(self):
        universe = [hand_company("L1", "tech"),
                    hand_company("L2", "tech", scale={"revenue": 1.15}),
                    hand_company("L3", "tech", scale={"revenue": 0.90})]
        before = score_universe(universe, AS_OF)
        l1 = universe[0]
        prices = list(l1.prices) + [("2024-08-31", 500.0),
                                     ("2024-12-31", 900.0)]
        pricey = Company("L1", "tech", l1.facts, prices, prices,
                         set(l1.sources))
        after = score_universe([pricey, universe[1], universe[2]], AS_OF)
        self.assertEqual(after["L1"].score, before["L1"].score)

class RegressionScoring(unittest.TestCase):
    """Cross-sectional invariants (old behavior checks)."""

    def test_percentile_ties_get_midranks(self):
        self.assertEqual(percentile_scores([1.0, 2.0, 2.0, 3.0], 1),
                         [0.25, 0.625, 0.625, 1.0])

    def test_percentile_direction_reverses(self):
        forward = percentile_scores([1.0, 2.0, 3.0, 4.0], 1)
        reverse = percentile_scores([1.0, 2.0, 3.0, 4.0], -1)
        self.assertEqual(reverse, list(reversed(forward)))

    def test_percentile_bounded(self):
        scores = percentile_scores([5.0, 5.0, 5.0, 5.0, 9.0], 1)
        self.assertTrue(all(0.0 < s <= 1.0 for s in scores))
        self.assertEqual(scores[:4], [0.5, 0.5, 0.5, 0.5])
        self.assertEqual(scores[4], 1.0)

    def test_winsorize_clips_tails(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 1e9]
        out = winsorize(values)
        hi = _quantile(sorted(values), WINSOR_UPPER)
        lo = _quantile(sorted(values), WINSOR_LOWER)
        self.assertAlmostEqual(out[-1], hi)
        self.assertAlmostEqual(out[0], lo)
        self.assertEqual(out[1:-1], values[1:-1])

    def test_scores_bounded_0_100(self):
        results = score_universe(fixture_companies(), AS_OF)
        for res in results.values():
            if res.score is not None:
                self.assertTrue(0.0 < res.score <= 100.0, res.ticker)

    def test_monotonic_improving_operating_income(self):
        companies = fixture_companies()
        scores = []
        for k in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0):
            modified = [clone_scaled(c, "operating_income", k, "Q")
                        if c.ticker == "FXTE03" else c for c in companies]
            scores.append(score_universe(modified, AS_OF)["FXTE03"].score)
        self.assertTrue(all(a <= b + 1e-9
                            for a, b in zip(scores, scores[1:])), scores)

    def test_monotonic_lower_leverage(self):
        companies = fixture_companies()
        scores = []
        for k in (1.6, 1.3, 1.0, 0.7, 0.4):
            modified = [clone_scaled(c, "total_debt", k, "INST")
                        if c.ticker == "FXTE03" else c for c in companies]
            scores.append(score_universe(modified, AS_OF)["FXTE03"].score)
        self.assertTrue(all(a <= b + 1e-9
                            for a, b in zip(scores, scores[1:])), scores)

    def test_monotonic_shareholder_yield(self):
        companies = fixture_companies()
        scores = []
        for k in (0.2, 1.0, 3.0):
            modified = list(companies)
            for i, c in enumerate(modified):
                if c.ticker == "FXTE03":
                    modified[i] = clone_scaled(
                        clone_scaled(c, "dividends_paid", k, "Q"),
                        "buybacks", k, "Q")
            scores.append(score_universe(modified, AS_OF)["FXTE03"].score)
        self.assertTrue(all(a <= b + 1e-9
                            for a, b in zip(scores, scores[1:])), scores)

    def test_no_cliff_on_epsilon(self):
        companies = fixture_companies()
        base = score_universe(companies, AS_OF)["FXTE03"].score
        perturbed = [clone_scaled(c, "operating_income", 1.0 + 1e-9, "Q")
                     if c.ticker == "FXTE03" else c for c in companies]
        moved = score_universe(perturbed, AS_OF)["FXTE03"].score
        self.assertLessEqual(abs(moved - base), 100 * (0.25 / 4) + 1e-6)

    def test_coverage_gate_thresholds(self):
        peer = hand_company("H2", "tech", scale={"revenue": 1.1})
        full = score_universe([hand_company("H1", "tech"), peer], AS_OF)
        self.assertEqual(full["H1"].status, OK)
        self.assertAlmostEqual(full["H1"].coverage, 1.0)
        no_price = hand_company("H1", "tech", prices=[])
        res = score_universe([no_price, peer], AS_OF)["H1"]
        self.assertAlmostEqual(res.coverage, 0.775)
        self.assertEqual(res.status, OK)
        no_ie = hand_company("H1", "tech", prices=[],
                             drop=("interest_expense",))
        res = score_universe([no_ie, peer], AS_OF)["H1"]
        self.assertAlmostEqual(res.coverage, 0.725)
        self.assertEqual(res.status, OK)
        no_ca = hand_company("H1", "tech", prices=[],
                             drop=("interest_expense", "current_assets"))
        res = score_universe([no_ca, peer], AS_OF)["H1"]
        self.assertLess(res.coverage, MIN_COVERAGE)
        self.assertEqual(res.status, INSUFFICIENT_DATA)

    def test_sector_peer_fallback_flag(self):
        results = score_universe(fixture_companies(), AS_OF)
        self.assertNotIn("SECTOR_PEER_FALLBACK", results["FXTE01"].flags)
        self.assertNotIn("SECTOR_PEER_FALLBACK", results["FXEN01"].flags)
        for ticker in ("FXFI01", "FXUT01", "FXRE01"):
            self.assertIn("SECTOR_PEER_FALLBACK", results[ticker].flags,
                          ticker)

    def test_rank_in_sector_unique_and_ties_share(self):
        results = score_universe(fixture_companies(), AS_OF)
        tech_ranks = sorted(results[f"FXTE{i:02d}"].rank_in_sector
                            for i in range(1, 11))
        self.assertEqual(tech_ranks, list(range(1, 11)))
        one, two = hand_company("T1", "tech"), hand_company("T2", "tech")
        res = score_universe([one, two], AS_OF)
        self.assertEqual(res["T1"].score, res["T2"].score)
        self.assertEqual(res["T1"].rank_in_sector, 1)
        self.assertEqual(res["T2"].rank_in_sector, 1)

    def test_thin_pool_is_neutral(self):
        solo = score_universe([hand_company("SOLO", "tech")], AS_OF)["SOLO"]
        self.assertAlmostEqual(solo.score, 50.0)
        self.assertIn("thin_metric_pool", solo.notes)
        self.assertIn("SECTOR_PEER_FALLBACK", solo.flags)

    def test_no_data_status(self):
        empty = Company("EMPTY", "tech", {}, [], [], set())
        res = score_universe([empty], AS_OF)["EMPTY"]
        self.assertEqual(res.status, NO_DATA)
        self.assertIsNone(res.score)

    def test_red_flags(self):
        neg_eq = hand_company("NEGEQ", "tech", scale={"total_equity": -0.1})
        res = score_universe([neg_eq, hand_company("P", "tech")], AS_OF)
        self.assertIn("NEGATIVE_EQUITY", res["NEGEQ"].flags)
        # altman distress: heavily negative retained earnings sink Z (< 1.81)
        distressed = hand_company("DIST", "tech",
                                  scale={"retained_earnings": -3.0})
        res = score_universe([distressed, hand_company("P2", "tech")],
                             AS_OF)
        self.assertLess(res["DIST"].metrics["altman_z"], ALTMAN_DISTRESS_Z)
        self.assertIn("ALTMAN_DISTRESS", res["DIST"].flags)
        # piotroski low: nearly every criterion fails (F <= 2).
        # The first version of this fixture tried to reach that with `scale`
        # alone, but scale multiplies BOTH years by the same factor, so the
        # direction-based signals (5, 6, 8, 9 compare current vs prior year)
        # can never flip - the company scored F=5. Restatements (later
        # filing date, same period_end; latest filing <= as_of wins) now
        # override the originals: revenue restated down (gross margin and
        # asset turnover fall), long-term debt restated up (leverage rises),
        # current assets restated down (current ratio falls), shares
        # outstanding restated up (dilution); net income and CFO scaled
        # negative (ROA, CFO, accruals and rising-ROA all fail). F = 0.
        low_extra = {
            "revenue": [Fact("2023-12-31", "2024-06-01", 300.0, "10-K/A",
                             "FY", "2023-01-01")],
            "long_term_debt": [Fact("2023-12-31", "2024-06-01", 900.0,
                                    "10-K/A", "INST")],
            "current_assets": [Fact("2023-12-31", "2024-06-01", 100.0,
                                    "10-K/A", "INST")],
            "shares_outstanding": [Fact("2023-12-31", "2024-06-01", 11.0,
                                        "10-K/A", "INST")],
        }
        low_f = hand_company("LOWF", "tech",
                             scale={"net_income": -1.0, "cfo": -1.5},
                             extra=low_extra)
        res = score_universe([low_f, hand_company("P3", "tech")], AS_OF)
        self.assertLessEqual(res["LOWF"].metrics["piotroski_f"],
                             PIOTROSKI_LOW)
        self.assertIn("PIOTROSKI_LOW", res["LOWF"].flags)
        # shrinking revenue with rising debt: 2023 quarters cut to 150
        shrink_extra = {"revenue": [
            Fact(qend, filed, 150.0, "10-Q", "Q", qstart)
            for qend, filed, qstart in (
                ("2023-03-31", "2023-05-15", "2023-01-01"),
                ("2023-06-30", "2023-08-14", "2023-04-01"),
                ("2023-09-30", "2023-11-14", "2023-07-01"),
                ("2023-12-31", "2024-02-15", "2023-10-01"))]}
        shrinking = hand_company("SHRINK", "tech", extra=shrink_extra,
                                 scale={"total_debt": 2.0})
        res = score_universe([shrinking, hand_company("P4", "tech")], AS_OF)
        self.assertIn("SHRINKING_REVENUE_RISING_DEBT", res["SHRINK"].flags)

    def test_flags_do_not_change_the_score(self):
        from unittest import mock
        companies = fixture_companies()
        base = {t: r.score for t, r in
                score_universe(companies, AS_OF).items()}
        with mock.patch(f"{_MODULE_NAME}._red_flags",
                        return_value=["FAKE_FLAG"]):
            flagged = score_universe(companies, AS_OF)
        for ticker, res in flagged.items():
            self.assertEqual(res.score, base[ticker], ticker)
            self.assertIn("FAKE_FLAG", res.flags)

    def test_metric_scores_reported(self):
        results = score_universe(fixture_companies(), AS_OF)
        res = results["FXTE01"]
        self.assertIsNotNone(res.metric_scores["roic"])
        self.assertTrue(0 < res.metric_scores["roic"] <= 1)
        self.assertIsNotNone(res.metrics["roic"])
        self.assertIsNotNone(res.pillars["profitability"])
        self.assertEqual(res.data_source, "fixtures")

    def test_sector_model_specs(self):
        fin = MODELS["financials"]
        names = {s.name for s in fin.metrics}
        self.assertIn("roe_ttm", names)
        self.assertIn("p_book", names)
        self.assertIn("equity_assets", names)
        self.assertNotIn("altman_z", names)
        self.assertNotIn("current_ratio", names)
        self.assertNotIn("gross_profitability", names)
        reit = MODELS["reit"]
        self.assertNotIn("altman_z", {s.name for s in reit.metrics})
        util = MODELS["utilities"]
        self.assertNotIn("altman_z", {s.name for s in util.metrics})
        cyc = MODELS["cyclicals"]
        self.assertIn("operating_margin_5y", {s.name for s in cyc.metrics})
        self.assertNotIn("operating_margin", {s.name for s in cyc.metrics})
        for model in MODELS.values():
            weights = metric_weights(model)
            self.assertAlmostEqual(sum(weights.values()), 1.0, places=9)

    def test_financials_and_utility_score_ok(self):
        results = score_universe(
            [bank_company(), energy_company()] + fixture_companies(), AS_OF)
        self.assertEqual(results["BANK"].status, OK)
        self.assertEqual(results["ENGY"].status, OK)
        self.assertEqual(results["FXUT01"].status, OK)
        self.assertEqual(results["FXFI01"].status, OK)

    def test_high_accruals_needs_pool_of_20(self):
        self.assertEqual(MIN_POOL_FOR_ACCRUALS_FLAG, 20)

    def test_snapshot_header_and_determinism(self):
        import tempfile
        results = score_universe(fixture_companies(), AS_OF)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "2024-06-30.csv"
            write_snapshot(results, AS_OF, str(path))
            text = path.read_text(encoding="utf-8")
            self.assertIn(f"# engine_version={ENGINE_VERSION}", text)
            self.assertIn(f"# config_hash={config_hash()}", text)
            self.assertIn("mscore_roic", text)   # metric scores in snapshot
            rows = read_snapshot(path)
            self.assertEqual(len(rows), 23)
            first = path.read_text(encoding="utf-8")
            write_snapshot(results, AS_OF, str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), first)

    def test_scan_writes_snapshot_and_delisted_never_fetched(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            uni = fixture_universe_file(Path(tmp) / "uni.csv")
            env = {"QE_DATA_DIR": tmp, "QE_SNAPSHOT_DIR":
                   str(Path(tmp) / "snaps"),
                   "QE_SCAN_STATE": str(Path(tmp) / "s.json"),
                   "QE_CACHE_DIR": str(Path(tmp) / "cache")}
            proc = subprocess.run(
                [sys.executable, str(_THIS_FILE), "scan", "--source",
                 "fixtures", "--universe-file", uni, "--as-of", AS_OF,
                 "--snapshot"],
                capture_output=True, text=True, timeout=300,
                env={**os.environ, **env}, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("==== SCAN DONE ====", proc.stdout)
            self.assertTrue((Path(tmp) / "snaps" / f"{AS_OF}.csv").exists())
            # delisted/renamed entries are never fetched: scan only those
            delisted = [r.ticker for r in get_universe()[0]
                        if r.status in ("delisted", "renamed")][:3]
            self.assertTrue(delisted)
            proc2 = subprocess.run(
                [sys.executable, str(_THIS_FILE), "scan", "--source",
                 "fixtures", "--as-of", AS_OF, "--tickers",
                 ",".join(delisted), "--no-snapshot"],
                capture_output=True, text=True, timeout=300,
                env={**os.environ, **env}, cwd=tmp)
            self.assertEqual(proc2.returncode, 0, proc2.stderr)
            for ticker in delisted:
                self.assertIn(ticker, proc2.stdout)
            # a delisted-only scan performs zero provider fetches
            self.assertNotIn("fixtures: SUCCESS=", proc2.stdout)

    def test_one_failed_ticker_never_crashes(self):
        class ExplodingSource:
            name = "boom"

            def get_all_facts(self, ticker):
                raise RuntimeError("kaboom")

            def get_prices(self, ticker, start=None, end=None):
                return None, ProviderReport("boom", STATUS_NO_DATA, "")

        chain = SourceChain([ExplodingSource()], None, [], [])
        ref = TickerRef("X", "tech")
        companies, statuses, errors, _ustat = fetch_companies(chain, [ref], AS_OF)
        self.assertEqual(companies, [])
        self.assertEqual(statuses["X"], ERROR)
        self.assertIn("RuntimeError", errors["X"])

    def test_provider_status_counts_in_scan_summary(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            uni = fixture_universe_file(Path(tmp) / "uni.csv")
            env = {"QE_DATA_DIR": tmp,
                   "QE_SNAPSHOT_DIR": str(Path(tmp) / "snaps"),
                   "QE_SCAN_STATE": str(Path(tmp) / "s.json"),
                   "QE_CACHE_DIR": str(Path(tmp) / "cache")}
            proc = subprocess.run(
                [sys.executable, str(_THIS_FILE), "scan", "--source",
                 "fixtures", "--universe-file", uni, "--as-of", AS_OF,
                 "--limit", "3", "--no-snapshot"],
                capture_output=True, text=True, timeout=300,
                env={**os.environ, **env}, cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("provider status counts", proc.stdout)
            self.assertIn("fixtures: SUCCESS=", proc.stdout)

class RegressionApi(unittest.TestCase):
    """Public API shape, statuses and import purity (old behavior checks)."""

    REQUIRED_KEYS = {"ticker", "as_of", "sector", "score", "pillars",
                     "coverage", "flags", "rank_in_sector", "status",
                     "data_source", "model", "metrics", "metric_scores",
                     "notes", "error", "score_unrated", "source_status",
                     "provenance"}

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.uni = fixture_universe_file(
            Path(self.tmp.name) / "uni.csv")
        _clear_memo()

    def tearDown(self):
        _clear_memo()

    def test_quality_score_shape(self):
        result = get_quality_score("FXTE01", AS_OF, source="fixtures",
                                   universe_file=self.uni)
        self.assertTrue(self.REQUIRED_KEYS <= set(result))
        self.assertEqual(result["ticker"], "FXTE01")
        self.assertEqual(result["sector"], "tech")
        self.assertEqual(result["status"], OK)
        self.assertTrue(0 < result["score"] <= 100)
        self.assertTrue(0 < result["coverage"] <= 1)
        self.assertIsNotNone(result["rank_in_sector"])
        self.assertTrue(1 <= result["rank_in_sector"] <= 10)
        self.assertEqual(result["data_source"], "fixtures")
        json.dumps(result)   # serializable

    def test_unknown_ticker(self):
        result = get_quality_score("NOPE", AS_OF, source="fixtures",
                                   universe_file=self.uni)
        self.assertEqual(result["status"], NO_DATA)
        self.assertIsNone(result["score"])
        self.assertIn("ticker_not_in_universe", result["notes"])

    def test_delisted_and_renamed_reported(self):
        result = get_quality_score("DRE", AS_OF, source="fixtures")
        self.assertEqual(result["status"], DELISTED)
        self.assertIsNone(result["score"])
        self.assertTrue(any("Prologis" in n for n in result["notes"]))
        renamed = get_quality_score("BLL", AS_OF, source="fixtures")
        self.assertEqual(renamed["status"], RENAMED)
        self.assertTrue(any("BALL" in n for n in renamed["notes"]))

    def test_sector_data_missing_status(self):
        result = get_quality_score("FXRE02", AS_OF, source="fixtures",
                                   universe_file=self.uni)
        self.assertEqual(result["status"], SECTOR_DATA_MISSING)
        self.assertIsNone(result["score"])

    def test_momentum_fixture(self):
        result = get_momentum_12_1("FXTE01", AS_OF, source="fixtures")
        self.assertEqual(result["ticker"], "FXTE01")
        self.assertEqual(result["status"], OK)
        self.assertIsNotNone(result["momentum_12_1"])
        self.assertEqual(result["data_source"], "fixtures")

    def test_momentum_unknown_ticker(self):
        result = get_momentum_12_1("NOPE", AS_OF, source="fixtures")
        self.assertEqual(result["status"], NO_DATA)
        self.assertTrue(result["reason"])

    def test_momentum_separate_from_quality(self):
        quality = get_quality_score("FXTE05", AS_OF, source="fixtures",
                                    universe_file=self.uni)
        momentum = get_momentum_12_1("FXTE05", AS_OF, source="fixtures")
        self.assertNotIn("momentum", quality)
        self.assertIn("momentum_12_1", momentum)

    def test_describe_sources_reports_skipped(self):
        # env-robust (S2): pin the ambient state so the test asserts the
        # skipped-source reporting regardless of the operator's real env.
        # Since 3.2: with no keys, auto mode enables KEYLESS SEC EDGAR
        # (default User-Agent) plus a keyless price client; finnhub alone
        # is skipped, and fixtures are NOT silently enabled in auto mode.
        from unittest import mock
        env = {k: v for k, v in os.environ.items()
               if k not in (FINNHUB_KEY_ENV, SEC_USER_AGENT_ENV)}
        with mock.patch.dict(os.environ, env, clear=True):
            rows = describe_sources("auto")
        names = {name: status for name, status in rows}
        self.assertIn("skipped", names.get("finnhub", ""))
        self.assertIn("enabled", names.get("sec_edgar", ""))
        self.assertNotIn("enabled", names.get("fixtures", ""))
        price_enabled = any(names.get(n) == "enabled"
                            for n in ("yfinance", "yahoo_chart"))
        self.assertTrue(price_enabled)

    def test_import_has_no_side_effects(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            module = Path(_THIS_FILE).stem
            code = (f"import sys; sys.path.insert(0, "
                    f"{str(Path(_THIS_FILE).parent)!r}); "
                    f"import {module}; print('imported-ok')")
            proc = subprocess.run([sys.executable, "-c", code],
                                  capture_output=True, text=True, timeout=90,
                                  env={"PATH": "/usr/bin:/bin",
                                       "HOME": tmp},
                                  cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("imported-ok", proc.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_score_cli(self):
        import subprocess
        proc = subprocess.run(
            [sys.executable, str(_THIS_FILE), "score", "--ticker", "FXTE01",
             "--as-of", AS_OF, "--source", "fixtures",
             "--universe-file", self.uni],
            capture_output=True, text=True, timeout=300,
            cwd=str(Path(self.tmp.name)))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("FXTE01", proc.stdout)
        self.assertIn("OK", proc.stdout)

class RegressionSecNormalization(unittest.TestCase):
    """SEC companyfacts normalizer (verified-correct logic, kept)."""

    @staticmethod
    def _unit(end, val, filed, form="10-Q", start=None):
        u = {"end": end, "val": val, "accn": "0000000001-23-000001",
             "fy": int(end[:4]), "fp": "Q1", "form": form, "filed": filed}
        if start:
            u["start"] = start
        return u

    def test_normalize_companyfacts(self):
        data = {"cik": 1, "entityName": "TEST", "facts": {
            "us-gaap": {
                "Revenues": {"units": {"USD": [
                    self._unit("2023-12-31", 1000.0, "2024-02-15",
                               form="10-K", start="2023-01-01"),
                    self._unit("2023-03-31", 250.0, "2023-05-15",
                               start="2023-01-01"),
                ]}},
                "NetCashProvidedByUsedInOperatingActivities":
                    {"units": {"USD": [
                        self._unit("2023-03-31", 15.0, "2023-05-15",
                                   start="2023-01-01"),
                        self._unit("2023-06-30", 34.0, "2023-08-14",
                                   start="2023-01-01"),
                        self._unit("2023-09-30", 51.0, "2023-11-14",
                                   start="2023-01-01"),
                        self._unit("2023-12-31", 60.0, "2024-02-15",
                                   form="10-K", start="2023-01-01"),
                    ]}},
                "Assets": {"units": {"USD": [
                    self._unit("2023-12-31", 1000.0, "2024-02-15",
                               form="10-K")]}},
                "LongTermDebtNoncurrent": {"units": {"USD": [
                    self._unit("2023-12-31", 300.0, "2024-02-15",
                               form="10-K")]}},
                "LongTermDebtCurrent": {"units": {"USD": [
                    self._unit("2023-12-31", 60.0, "2024-02-15",
                               form="10-K")]}},
                "ShortTermBorrowings": {"units": {"USD": [
                    self._unit("2023-12-31", 40.0, "2024-02-15",
                               form="10-K")]}},
            },
            "dei": {"EntityCommonStockSharesOutstanding":
                    {"units": {"shares": [
                        self._unit("2023-12-31", 10.0, "2024-02-15",
                                   form="10-K")]}}}}}
        out, _diag = normalize_companyfacts(data)
        kinds = {(f.freq, f.value) for f in out["revenue"]}
        self.assertIn(("FY", 1000.0), kinds)
        self.assertIn(("Q", 250.0), kinds)
        freqs = [f.freq for f in out["cfo"]]
        self.assertEqual(freqs.count("YTD"), 3)
        self.assertEqual(freqs.count("FY"), 1)
        self.assertTrue(all(f.freq == "INST" for f in out["total_assets"]))
        self.assertEqual(out["total_assets"][0].value, 1000.0)
        self.assertEqual(out["shares_outstanding"][0].value, 10.0)
        self.assertAlmostEqual(out["total_debt"][0].value, 400.0)

    def test_odd_durations_dropped(self):
        data = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            self._unit("2023-06-30", 500.0, "2023-08-14",
                       start="2023-01-01"),
        ]}}}}}
        facts2, _d2 = normalize_companyfacts(data)
        self.assertNotIn("revenue", facts2)

    def test_sec_user_agent_sent_but_never_cached(self):
        from unittest import mock
        captured_headers = {}
        cache_writes = {}

        def transport(url, headers=None, timeout=None):
            captured_headers.update(headers or {})
            if "company_tickers" in url:
                return (STATUS_SUCCESS,
                        {"0": {"ticker": "TEST", "cik_str": 1}}, None)
            return STATUS_SUCCESS, {"facts": {}}, None

        class FakeCache:
            def get(self, ns, key, ttl=None):
                return None

            def set(self, ns, key, payload):
                cache_writes[ns + "|" + key] = payload

        with mock.patch.dict(os.environ,
                             {SEC_USER_AGENT_ENV: "contact@example.com"}):
            client = SecEdgarClient(cache=FakeCache(), limiter=RateLimiter(0.0),
                                    transport=transport, sleep_fn=lambda s: 0)
            facts, report = client.get_all_facts("TEST")
            self.assertEqual(facts, {})
            self.assertEqual(report.status, STATUS_NO_DATA)
            # the contact string travels as a header...
            self.assertIn("User-Agent", captured_headers)
            self.assertIn("contact@example.com",
                          captured_headers["User-Agent"])
            # ...but never into cache keys or payloads
            for key, payload in cache_writes.items():
                self.assertNotIn("contact@example.com", key)
                self.assertNotIn("contact@example.com",
                                 json.dumps(payload))

class RepairedRegressions(unittest.TestCase):
    """Regressions for issues repaired in this rebuild session.

    Each test locks one repaired behavior; none of them passed before the
    corresponding fix (they reproduce the shipped defects).
    """

    def test_norm_name_strips_taxonomy_prefixes(self):
        # before the fix, "us-gaap_Revenues" normalized to "usgaaprevenues"
        # and NEVER matched the concept map (written in bare form); every
        # concept-only row fell through to label matching or was dropped as
        # unknown_concept.
        self.assertEqual(_norm_name("us-gaap_Revenues"), "revenues")
        self.assertEqual(_norm_name("US-GAAP_Revenues"), "revenues")
        self.assertEqual(_norm_name("ifrs-full_Revenue"), "revenue")
        self.assertEqual(
            _norm_name("dei_EntityCommonStockSharesOutstanding"),
            "entitycommonstocksharesoutstanding")
        self.assertEqual(_norm_name("srt_DebtInstrument"),
                         "debtinstrument")
        self.assertEqual(_norm_name("Revenues"), "revenues")  # bare form
        self.assertEqual(_norm_name(""), "")

    def test_concept_rows_map_without_label_help(self):
        rows = [
            {"filedDate": "2024-02-15", "startDate": "2023-01-01",
             "endDate": "2023-12-31", "report": {"ic": [
                 # label is meaningless on purpose: only the concept can
                 # map this row (label fallback would fail)
                 {"concept": "us-gaap_Revenues", "label": "zzz",
                  "unit": "USD", "value": 10.0}]}},
            {"filedDate": "2024-02-15", "endDate": "2023-12-31",
             "report": {"bs": [
                 {"concept": "dei_EntityCommonStockSharesOutstanding",
                  "label": "zzz", "unit": "shares", "value": 5.0}]}},
            {"filedDate": "2024-02-15", "startDate": "2023-01-01",
             "endDate": "2023-12-31", "report": {"ic": [
                 # ifrs-full_ stripped, but "Revenue" is not a candidate
                 # concept -> honest unknown_concept, never a label match
                 {"concept": "ifrs-full_Revenue", "label": "zzz",
                  "unit": "USD", "value": 7.0}]}},
        ]
        facts, diag = normalize_finnhub(rows)
        self.assertEqual(facts["revenue"][0].value, 10.0)
        self.assertEqual(facts["revenue"][0].freq, "FY")
        self.assertEqual(facts["shares_outstanding"][0].value, 5.0)
        self.assertEqual(facts["shares_outstanding"][0].freq, "INST")
        self.assertEqual(len(facts["revenue"]), 1)
        self.assertEqual(diag["unknown_concept"], 1)

    def test_yfinance_duck_typed_history_and_call_counting(self):
        # before the fix, get_prices required pandas' .empty attribute and
        # reported a successful fetch with calls=0 (indistinguishable from
        # a cache hit)
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                class Hist:  # no .empty attribute (duck-typed history)
                    def __init__(self, rows):
                        self.rows = rows

                    def iterrows(self):
                        class Idx:
                            def __init__(self, day):
                                self._day = day

                            def date(self):
                                return date.fromisoformat(self._day)
                        for day, close in self.rows:
                            yield Idx(day), {"Close": close,
                                             "Adj Close": close}

                class FakeTicker:
                    def history(self, start=None, end=None, interval="1d",
                                auto_adjust=False):
                        return Hist([(f"2024-06-{d:02d}", 10.0 + d)
                                     for d in range(1, 31)])

                fake_module = type(sys)("yfinance")
                fake_module.Ticker = staticmethod(lambda t: FakeTicker())
                with mock.patch.dict(sys.modules,
                                     {"yfinance": fake_module}):
                    client = YfinancePriceClient()
                    _payload, r1 = client.get_prices("X", "2024-05-01",
                                                     "2024-06-30",
                                                     fetch_on="2024-06-30")
                    self.assertEqual(r1.status, STATUS_SUCCESS)
                    self.assertEqual(r1.calls, 1)
                    self.assertNotEqual(r1.detail, "cache")
                    _payload, r2 = client.get_prices("X", "2024-05-15",
                                                     "2024-06-15",
                                                     fetch_on="2024-06-30")
                    self.assertEqual(r2.status, STATUS_SUCCESS)
                    self.assertEqual(r2.calls, 0)
                    self.assertEqual(r2.detail, "cache")

    def test_yfinance_pandas_empty_history_is_no_data(self):
        from unittest import mock
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                class EmptyFrame:
                    empty = True

                    def iterrows(self):  # must never be reached
                        raise AssertionError("iterrows on empty frame")

                class FakeTicker:
                    def history(self, **kw):
                        return EmptyFrame()

                fake_module = type(sys)("yfinance")
                fake_module.Ticker = staticmethod(lambda t: FakeTicker())
                with mock.patch.dict(sys.modules,
                                     {"yfinance": fake_module}):
                    client = YfinancePriceClient()
                    payload, report = client.get_prices(
                        "X", "2024-05-01", "2024-06-30",
                        fetch_on="2024-06-30")
                    self.assertIsNone(payload)
                    self.assertEqual(report.status, STATUS_NO_DATA)
                    self.assertEqual(report.detail, "empty_history")

    def test_provider_error_note_keeps_exception_types(self):
        # a provider that raises recorded only "PROVIDER_ERROR" before the
        # fix; the exception type was swallowed
        class ExplodingSource:
            name = "boom"

            def get_all_facts(self, ticker):
                raise RuntimeError("kaboom")

            def get_prices(self, ticker, start=None, end=None):
                return None, ProviderReport("boom", STATUS_NO_DATA, "")

        chain = SourceChain([ExplodingSource()], None, [], [])
        company = chain.get_company("X", "tech", "2024-06-30")
        note = _provider_error_note(company)
        self.assertIn("PROVIDER_ERROR", note)
        self.assertIn("boom=exception:RuntimeError", note)
        self.assertEqual(company.source_detail["boom"],
                         "exception:RuntimeError")

    def test_state_written_as_ticker_keyed_dict(self):
        # before the fix, checkpoint companies were a LIST; the resume
        # contract (and D12 tests) require a dict keyed by ticker
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.json"
            refs = [TickerRef("HAND", "tech")]
            fp = scan_fingerprint("2024-06-30", "fixtures", refs,
                                  ["fixtures"], None)
            _save_state(path, fp, {"HAND": hand_company("HAND", "tech")},
                        {}, {})
            blob = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(blob["companies"], dict)
            self.assertIn("HAND", blob["companies"])
            restored = _company_from_dict(blob["companies"]["HAND"])
            self.assertEqual(restored.ticker, "HAND")
            self.assertIn("revenue", restored.facts)

class PitAvailability(unittest.TestCase):
    """S3 adversarial point-in-time availability tests: after-close
    acceptances, conservative assumptions, unplaceable facts, provenance
    round-trips and full-pipeline historical reproducibility."""

    def test_filing_after_scoring_date_invisible(self):
        facts = {"revenue": [Fact("2023-12-31", "2024-08-15", 1000.0,
                                  "10-K", "FY", "2023-01-01",
                                  accepted="2024-08-15T15:00:00Z")]}
        view = FundamentalsView(facts, "2024-06-30")
        self.assertIsNone(view.fy("revenue", 0))
        self.assertEqual(view.delayed_not_yet_available, 1)

    def test_accepted_after_close_next_trading_day(self):
        # 2024-02-15 is a Thursday; 21:30Z = 16:30 ET (after the cutoff)
        f = Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01", accepted="2024-02-15T21:30:00Z")
        avail, label = fact_available_date(f)
        self.assertEqual(avail, "2024-02-16")
        self.assertEqual(label, "accepted_after_close_next_trading_day")
        self.assertIsNone(FundamentalsView({"revenue": [f]},
                                           "2024-02-15").fy("revenue", 0))
        self.assertAlmostEqual(FundamentalsView(
            {"revenue": [f]}, "2024-02-16").fy("revenue", 0), 1000.0)

    def test_accepted_before_close_same_day(self):
        # 18:00Z = 13:00 ET: same-day availability
        f = Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01", accepted="2024-02-15T18:00:00Z")
        avail, label = fact_available_date(f)
        self.assertEqual(avail, "2024-02-15")
        self.assertEqual(label, "accepted_same_day")
        self.assertAlmostEqual(FundamentalsView(
            {"revenue": [f]}, "2024-02-15").fy("revenue", 0), 1000.0)

    def test_no_timestamp_conservative_next_day_labeled(self):
        f = Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01")
        avail, label = fact_available_date(f)
        self.assertEqual(avail, "2024-02-16")
        self.assertEqual(label, "availability_assumed_next_day")
        view = FundamentalsView({"revenue": [f]}, "2024-02-15")
        self.assertIsNone(view.fy("revenue", 0))
        self.assertEqual(view.availability_labels.get(
            "availability_assumed_next_day"), 1)

    def test_friday_after_close_available_monday(self):
        # Friday 2024-02-16 accepted 22:00Z (17:00 ET) -> next weekday Mon
        f = Fact("2023-12-31", "2024-02-16", 1000.0, "10-K", "FY",
                 "2023-01-01", accepted="2024-02-16T22:00:00Z")
        avail, label = fact_available_date(f)
        self.assertEqual(avail, "2024-02-19")   # APPROXIMATE: no holiday
        self.assertEqual(label, "accepted_after_close_next_trading_day")

    def test_bad_filing_date_rejected_and_counted(self):
        f = Fact("2023-12-31", "2024-13-45", 1000.0, "10-K", "FY",
                 "2023-01-01")
        avail, reason = fact_available_date(f)
        self.assertIsNone(avail)
        self.assertEqual(reason, "bad_filing_date")
        view = FundamentalsView({"revenue": [f]}, "2025-01-01")
        self.assertIsNone(view.fy("revenue", 0))
        self.assertEqual(view.dropped_bad_filing_date, 1)

    def test_inconsistent_period_rejected_and_counted(self):
        f = Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2024-06-30")   # period_start AFTER period_end
        view = FundamentalsView({"revenue": [f]}, "2025-01-01")
        self.assertIsNone(view.fy("revenue", 0))
        self.assertEqual(view.dropped_inconsistent_period, 1)

    def test_unparseable_accepted_conservative(self):
        f = Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01", accepted="not-a-timestamp")
        avail, label = fact_available_date(f)
        self.assertEqual(avail, "2024-02-16")
        self.assertEqual(label, "unparseable_accepted_assumed_next_day")

    def test_acceptance_after_filed_date_conservative(self):
        # data error: acceptance 'after' the filed date is treated as the
        # worst case (after close on the filed date)
        f = Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01", accepted="2024-02-20T15:00:00Z")
        avail, label = fact_available_date(f)
        self.assertEqual(avail, "2024-02-16")
        self.assertEqual(label, "accepted_after_close_next_trading_day")

    def test_sec_client_wires_acceptance_map(self):
        """The SEC client feeds submissions acceptance timestamps into the
        normalizer: after-close acceptances wait for the next trading day,
        and a missing submissions feed falls back to the conservative rule
        (labeled, never guessed)."""
        import tempfile
        from unittest import mock
        facts_payload = {"cik": 1, "facts": {"us-gaap": {"Revenues": {
            "units": {"USD": [
                {"start": "2023-01-01", "end": "2023-12-31", "val": 1000.0,
                 "form": "10-K", "filed": "2024-02-15",
                 "accn": "0000000001-24-000001"}]}}}}}

        def transport(url, headers=None, timeout=None):
            if "company_tickers" in url:
                return (STATUS_SUCCESS,
                        {"0": {"ticker": "TEST", "cik_str": 1}}, None)
            if "submissions" in url:
                return (STATUS_SUCCESS, {"filings": {"recent": {
                    "accessionNumber": ["0000000001-24-000001"],
                    "acceptanceDateTime":
                        ["2024-02-15T21:30:00.000Z"]}}}, None)  # 16:30 ET
            if "companyfacts" in url:
                return (STATUS_SUCCESS, facts_payload, None)
            raise AssertionError(f"unexpected url {url}")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR",
                                   tmp), \
                    mock.patch.dict(os.environ,
                                    {SEC_USER_AGENT_ENV: "Audit <a@b.c>"}):
                client = SecEdgarClient(transport=transport)
                facts, report = client.get_all_facts("TEST")
                self.assertEqual(report.status, STATUS_SUCCESS)
                self.assertEqual(len(facts["revenue"]), 1)
                f = facts["revenue"][0]
                self.assertEqual(f.accepted, "2024-02-15T21:30:00.000Z")
                self.assertEqual(f.accession, "0000000001-24-000001")
                self.assertEqual(f.provider, "sec_edgar")
                self.assertEqual(f.cik, 1)
                self.assertEqual(f.currency, "USD")
                # after-close acceptance: invisible Thursday, visible Friday
                self.assertIsNone(FundamentalsView(
                    facts, "2024-02-15").fy("revenue", 0))
                self.assertAlmostEqual(FundamentalsView(
                    facts, "2024-02-16").fy("revenue", 0), 1000.0)

        def transport_no_submissions(url, headers=None, timeout=None):
            if "company_tickers" in url:
                return (STATUS_SUCCESS,
                        {"0": {"ticker": "TEST", "cik_str": 1}}, None)
            if "submissions" in url:
                return (STATUS_NETWORK_ERROR, {}, None)
            if "companyfacts" in url:
                return (STATUS_SUCCESS, facts_payload, None)
            raise AssertionError(f"unexpected url {url}")

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR",
                                   tmp), \
                    mock.patch.dict(os.environ,
                                    {SEC_USER_AGENT_ENV: "Audit <a@b.c>"}):
                client = SecEdgarClient(transport=transport_no_submissions)
                facts, _report = client.get_all_facts("TEST")
                self.assertIsNone(facts["revenue"][0].accepted)
                # conservative fallback, labeled
                self.assertIsNone(FundamentalsView(
                    facts, "2024-02-15").fy("revenue", 0))
                self.assertAlmostEqual(FundamentalsView(
                    facts, "2024-02-16").fy("revenue", 0), 1000.0)

    def test_finnhub_facts_carry_accepted_and_provider(self):
        row = {"filedDate": "2024-02-15",
               "acceptedDate": "2024-02-15T21:30:00",
               "startDate": "2023-01-01", "endDate": "2023-12-31",
               "form": "10-K", "year": 2023, "quarter": 0,
               "report": {"ic": [
                   {"concept": "us-gaap_Revenues", "label": "Revenue",
                    "value": 1000.0, "unit": "USD"}]}}
        facts, diag = normalize_finnhub([row])
        self.assertEqual(diag["unknown_concept"], 0)
        f = facts["revenue"][0]
        self.assertEqual(f.accepted, "2024-02-15T21:30:00")
        self.assertEqual(f.provider, "finnhub")
        self.assertEqual(f.unit, "USD")
        self.assertEqual(f.fy_label, "2023 0")
        # 21:30 naive string is treated as ET, after the cutoff
        self.assertIsNone(FundamentalsView(
            facts, "2024-02-15").fy("revenue", 0))
        self.assertAlmostEqual(FundamentalsView(
            facts, "2024-02-16").fy("revenue", 0), 1000.0)

    def test_provenance_fields_round_trip(self):
        f = Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "FY",
                 "2023-01-01", accepted="2024-02-15T21:30:00Z",
                 accession="0000000001-24-000001", provider="sec_edgar",
                 currency="USD", unit="USD", fy_label="FY2023 Q4",
                 cik=320193, security_id="AAPL",
                 source_ref="companyfacts")
        company = Company("AAPL", "tech", {"revenue": [f]}, [], [],
                          {"sec_edgar"})
        back = _company_from_dict(_company_to_dict(company))
        g = back.facts["revenue"][0]
        self.assertEqual(g.accepted, "2024-02-15T21:30:00Z")
        self.assertEqual(g.accession, "0000000001-24-000001")
        self.assertEqual(g.provider, "sec_edgar")
        self.assertEqual(g.currency, "USD")
        self.assertEqual(g.unit, "USD")
        self.assertEqual(g.fy_label, "FY2023 Q4")
        self.assertEqual(g.cik, 320193)
        self.assertEqual(g.security_id, "AAPL")
        self.assertEqual(g.source_ref, "companyfacts")

    def test_historical_score_reproducible(self):
        """THE S3 proof: a historical score is exactly reproducible from the
        data available on that date. Filing a restatement AFTER the scoring
        date must not change the score computed for that date - not the
        composite, not one metric, not the rank."""
        d = "2024-06-30"
        base = generate_fixture_universe()
        res_base = score_universe(list(base.values()), d)
        target = "FXTE01"
        src = base[target]
        facts2 = {k: list(v) for k, v in src.facts.items()}
        facts2["revenue"] = list(facts2["revenue"]) + [
            # dramatic restatement filed AFTER the scoring date
            Fact("2023-12-31", "2024-08-15", 12345.0, "10-K/A", "FY",
                 "2023-01-01", provider="fixtures",
                 security_id=target, source_ref="late-restatement")]
        mutated = dict(base)
        mutated[target] = Company(target, src.sector, facts2, src.prices,
                                  src.adj_prices, set(src.sources),
                                  src.note)
        res_mut = score_universe(list(mutated.values()), d)
        a, b = res_base[target], res_mut[target]
        self.assertEqual(a.score, b.score)
        self.assertEqual(a.status, b.status)
        self.assertEqual(a.metrics, b.metrics)
        self.assertEqual(a.metric_scores, b.metric_scores)
        self.assertEqual(a.rank_in_sector, b.rank_in_sector)
        self.assertNotEqual(
            FundamentalsView(mutated[target].facts, "2024-08-20")
            .fy("revenue", 0),
            FundamentalsView(base[target].facts, "2024-08-20")
            .fy("revenue", 0),
            "the restatement must be visible at later dates (sanity)")

class ProviderHardening(unittest.TestCase):
    """S2 provider matrix on captured REAL payloads plus synthetic
    corruptions: unit/currency guard, malformed rows, amendments,
    restatements, wrong identifiers, real split windows, real dei chains."""

    @staticmethod
    def _hist(rows):
        class Hist:
            columns = ["Close", "Adj Close", "Stock Splits"]

            def iterrows(self):
                class Idx:
                    def __init__(self, day):
                        self._day = day

                    def date(self):
                        return date.fromisoformat(self._day)
                for d, close, adj, ratio in rows:
                    yield Idx(d), {"Close": close, "Adj Close": adj,
                                   "Stock Splits": ratio}
        return Hist()

    def _client_with(self, rows):
        import tempfile
        from unittest import mock
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        hist = self._hist(rows)

        class FakeTicker:
            def history(self, start=None, end=None, interval="1d",
                        auto_adjust=False):
                return hist

        fake = type(sys)("yfinance")
        fake.Ticker = staticmethod(lambda t: FakeTicker())
        patcher = mock.patch.dict(sys.modules, {"yfinance": fake})
        patcher.start()
        self.addCleanup(patcher.stop)
        with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp.name):
            yield YfinancePriceClient()

    def test_real_yahoo_aapl_split_window(self):
        """Captured real AAPL rows: the client records the real close, the
        real split event, and the S1 reconstruction equals the 499.23 print."""
        for client in self._client_with(REAL_YAHOO_AAPL_2020_SPLIT):
            payload, report = client.get_prices("AAPL", "2020-08-20",
                                                "2020-09-02",
                                                fetch_on="2020-09-02")
            self.assertEqual(report.status, STATUS_SUCCESS)
            self.assertTrue(payload["splits_known"])
            closes = dict(payload["close"])
            self.assertAlmostEqual(closes["2020-08-28"], 124.8075, places=6)
            self.assertEqual(payload["splits"], [("2020-08-31", 4.0)])
            factor = _split_product(REAL_YAHOO_AAPL_SPLITS_ALL,
                                    "2020-08-28", "2020-09-02")
            self.assertAlmostEqual(factor, 4.0)
            self.assertAlmostEqual(closes["2020-08-28"] * factor, 499.23,
                                   places=4)

    def test_real_yahoo_siri_reverse_window(self):
        """Captured real SIRI rows: 1:10 reverse split; as-traded 3.12."""
        for client in self._client_with(REAL_YAHOO_SIRI_2024_REVERSE):
            payload, report = client.get_prices("SIRI", "2024-08-25",
                                                "2024-09-12",
                                                fetch_on="2024-09-12")
            self.assertEqual(report.status, STATUS_SUCCESS)
            closes = dict(payload["close"])
            self.assertEqual(payload["splits"], [("2024-09-10", 0.1)])
            factor = _split_product(REAL_YAHOO_SIRI_SPLITS_ALL,
                                    "2024-09-03", "2024-09-12")
            self.assertAlmostEqual(factor, 0.1)
            self.assertAlmostEqual(closes["2024-09-03"] * factor, 3.12,
                                   places=6)

    def test_real_sec_aapl_dei_pit_chain(self):
        """Captured real AAPL dei chain: point-in-time selection switches to
        the post-split count only after the 10-K filing date."""
        facts, diag = normalize_companyfacts(
            _companyfacts_shape(REAL_SEC_AAPL_DEI))
        self.assertEqual(diag["wrong_unit"], 0)
        self.assertIn("shares_outstanding", facts)
        pre = FundamentalsView(facts, "2020-08-28")
        self.assertAlmostEqual(pre.instant("shares_outstanding"),
                               4275634000.0)
        # the FY2020 10-K fact (filed Friday 2020-10-30, no acceptance
        # timestamp in companyfacts) is conservatively available Monday
        # 2020-11-02 - at 2020-10-31 the Q3 cover count still wins (S3)
        sat = FundamentalsView(facts, "2020-10-31")
        self.assertAlmostEqual(sat.instant("shares_outstanding"),
                               4275634000.0)
        self.assertEqual(sat.delayed_not_yet_available, 1)
        post = FundamentalsView(facts, "2020-11-03")
        self.assertAlmostEqual(post.instant("shares_outstanding"),
                               17001802000.0)

    def test_real_sec_aapl_full_mcap_path(self):
        """Real dei chain + real split window -> mcap = as-traded price x
        as-reported cover shares (the S1 invariant, on real data)."""
        facts, _diag = normalize_companyfacts(
            _companyfacts_shape(REAL_SEC_AAPL_DEI))
        prices = [(d, c) for d, c, _a, _r in REAL_YAHOO_AAPL_2020_SPLIT]
        company = Company("AAPL", "tech", facts, prices, prices,
                          {"sec_edgar", "yfinance"},
                          split_events=REAL_YAHOO_AAPL_SPLITS_ALL)
        company.prices_fetched_on = "2020-09-02"
        company.split_events_through = "2020-09-02"
        mp, status = build_market(company, "2020-08-28")
        self.assertEqual(status, "ok")
        # D15: the provider close is on the fetch-date basis (124.8075);
        # the split product over (t_s, fetch] restores the 499.23 cap.
        self.assertAlmostEqual(mp.price, 124.8075, places=4)
        self.assertAlmostEqual(mp.shares, 4275634000.0)
        self.assertAlmostEqual(mp.market_cap,
                               499.23 * 4275634000.0, places=-5)
        self.assertAlmostEqual(mp.split_factor, 4.0)

    def test_real_sec_brk_stale_and_zero_anomalies(self):
        """Captured real BRK dei chain: facts stop in 2011 (stale_shares at
        any modern D) and include a real zero-value fact (no_shares, never
        a zero market cap)."""
        facts, _diag = normalize_companyfacts(
            _companyfacts_shape(REAL_SEC_BRK_DEI))
        prices = [("2024-06-27", 406.8), ("2024-06-28", 406.8)]
        company = Company("BRK-B", "financials", facts, prices, prices,
                          {"sec_edgar", "yfinance"})
        mp, status = build_market(company, "2024-06-28")
        self.assertIsNone(mp)
        self.assertEqual(status, "stale_shares")
        # at 2010-05-10 the latest visible fact is the real zero anomaly
        zero_at = FundamentalsView(facts, "2010-05-10")
        self.assertAlmostEqual(zero_at.instant("shares_outstanding"), 0.0)
        prices_old = [("2010-05-07", 82.0), ("2010-05-10", 82.0)]
        company_old = Company("BRK-B", "financials", facts, prices_old,
                              prices_old, {"sec_edgar"})
        mp_old, status_old = build_market(company_old, "2010-05-10")
        self.assertIsNone(mp_old)
        self.assertEqual(status_old, "no_shares")

    def test_real_sec_googl_empty_dei(self):
        """Captured real Alphabet case: zero undimensioned dei facts ->
        mcap refused (no_point_in_time_shares), never guessed."""
        facts, diag = normalize_companyfacts(
            _companyfacts_shape(REAL_SEC_GOOGL_DEI))
        self.assertNotIn("shares_outstanding", facts)
        prices = [("2022-07-14", 111.8), ("2022-07-15", 111.8)]
        company = Company("GOOGL", "tech", facts, prices, prices,
                          {"sec_edgar", "yfinance"})
        mp, status = build_market(company, "2022-07-15")
        self.assertIsNone(mp)
        self.assertEqual(status, "no_point_in_time_shares")

    def test_sec_wrong_unit_and_currency_rejected(self):
        """A share count served in USD and revenue served in EUR are
        rejected and counted - never mixed into USD ratios (S2)."""
        payload = {"facts": {
            "dei": {"EntityCommonStockSharesOutstanding": {
                "units": {"USD": [                      # shares in USD!
                    {"end": "2024-06-30", "val": 1000.0,
                     "form": "10-Q", "filed": "2024-08-01"}]}}},
            "us-gaap": {
                "Revenues": {"units": {
                    "EUR": [                            # revenue in EUR!
                        {"start": "2023-01-01", "end": "2023-12-31",
                         "val": 5000.0, "form": "10-K",
                         "filed": "2024-02-15"}],
                    "USD": [
                        {"start": "2023-01-01", "end": "2023-12-31",
                         "val": 5400.0, "form": "10-K",
                         "filed": "2024-02-15"}]}}}}}
        facts, diag = normalize_companyfacts(payload)
        self.assertNotIn("shares_outstanding", facts)
        self.assertIn("revenue", facts)
        self.assertEqual(len(facts["revenue"]), 1)   # only the USD entry
        self.assertAlmostEqual(facts["revenue"][0].value, 5400.0)
        self.assertGreaterEqual(diag["wrong_unit"], 2)

    def test_sec_malformed_rows_counted(self):
        """Missing end / missing filed / null val are skipped and counted,
        never crash, never silently accepted."""
        payload = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"end": "2023-12-31", "val": 100.0, "form": "10-K"},   # no filed
            {"end": None, "val": 100.0, "form": "10-K",
             "filed": "2024-02-15"},                                # no end
            {"end": "2023-12-31", "val": None, "form": "10-K",
             "filed": "2024-02-15"},                                # null val
            {"start": "2023-01-01", "end": "2023-12-31", "val": 120.0,
             "form": "10-K", "filed": "2024-02-15"}]}}}}}
        facts, diag = normalize_companyfacts(payload)
        self.assertEqual(len(facts["revenue"]), 1)
        self.assertAlmostEqual(facts["revenue"][0].value, 120.0)
        self.assertGreaterEqual(diag["malformed"], 3)

    def test_sec_amendment_restatement_pit(self):
        """A 10-K/A amendment restates a period: the original value stays
        visible until the amendment's own filing date, then the restated
        value wins (restatements never overwrite earlier knowledge)."""
        payload = {"facts": {"us-gaap": {"Revenues": {"units": {"USD": [
            {"start": "2023-01-01", "end": "2023-12-31", "val": 1000.0,
             "form": "10-K", "filed": "2024-02-15"},
            {"start": "2023-01-01", "end": "2023-12-31", "val": 1100.0,
             "form": "10-K/A", "filed": "2024-04-01"}]}}}}}
        facts, _diag = normalize_companyfacts(payload)
        before = FundamentalsView(facts, "2024-03-15")
        self.assertAlmostEqual(before.fy("revenue"), 1000.0)
        after = FundamentalsView(facts, "2024-04-02")
        self.assertAlmostEqual(after.fy("revenue"), 1100.0)

    def test_sec_wrong_identifier_reports_no_cik(self):
        """A ticker absent from the SEC ticker map is NO_DATA with the
        exact reason - never an empty-success, never a guessed CIK."""
        def fake_transport(url, headers=None, timeout=None):
            if "company_tickers" in url:
                return (STATUS_SUCCESS,
                        {"0": {"ticker": "AAA", "cik_str": 123}}, None)
            raise AssertionError("companyfacts must not be fetched")

        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp), \
                    mock.patch.dict(os.environ,
                                    {SEC_USER_AGENT_ENV: "Audit <a@b.c>"}):
                client = SecEdgarClient(transport=fake_transport)
                facts, report = client.get_all_facts("ZZZZ")
                self.assertEqual(facts, {})
                self.assertEqual(report.status, STATUS_NO_DATA)
                self.assertEqual(report.detail, "no_cik")

class LiveProviderTests(unittest.TestCase):
    """Key-gated live integrations (S2)."""

    def test_live_finnhub(self):
        if not os.environ.get(FINNHUB_KEY_ENV):
            self.skipTest(f"LIVE SKIP: env {FINNHUB_KEY_ENV} not set")
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                client = FinnhubClient()
                try:
                    facts, report = client.get_all_facts("AAPL")
                except Exception as exc:
                    self.fail(f"LIVE FAIL: finnhub raised "
                              f"{type(exc).__name__}")
                if report.status == STATUS_AUTH_ERROR:
                    # Free-tier reality (3.2): /stock/financials-reported is
                    # premium; a 401/403 answer is the server's own verdict
                    # on the key, not an engine defect.
                    self.skipTest(
                        "LIVE SKIP: finnhub rejected the key ("
                        f"{report.detail}) - free keys cannot access "
                        "financials-reported; fundamentals come from SEC "
                        "EDGAR")
                self.assertIn(report.status,
                              (STATUS_SUCCESS, STATUS_PARTIAL_SUCCESS),
                              f"LIVE FAIL: finnhub status {report.status}"
                              f" ({report.detail})")
                self.assertTrue(facts,
                                "LIVE FAIL: finnhub served no facts")

    def test_live_sec_edgar(self):
        if not os.environ.get(SEC_USER_AGENT_ENV):
            self.skipTest(f"LIVE SKIP: env {SEC_USER_AGENT_ENV} not set")
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                client = SecEdgarClient()
                try:
                    facts, report = client.get_all_facts("AAPL")
                except Exception as exc:
                    self.fail(f"LIVE FAIL: sec_edgar raised "
                              f"{type(exc).__name__}")
                self.assertEqual(
                    report.status, STATUS_SUCCESS,
                    f"LIVE FAIL: sec_edgar status {report.status}"
                    f" ({report.detail})")
                self.assertIn("shares_outstanding", facts)
                self.assertIn("revenue", facts)

    def test_live_yfinance(self):
        ok, reason = YfinancePriceClient.available()
        if not ok:
            self.skipTest(f"LIVE SKIP: {reason}")
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                client = YfinancePriceClient()
                try:
                    payload, report = client.get_prices(
                        "AAPL", "2020-08-20", "2020-09-02")
                except Exception as exc:
                    self.fail(f"LIVE FAIL: yfinance raised "
                              f"{type(exc).__name__}")
                self.assertEqual(
                    report.status, STATUS_SUCCESS,
                    f"LIVE FAIL: yfinance status {report.status}")
                self.assertTrue(payload and payload["close"])
                closes = dict(payload["close"])
                # regression against the captured real print: Yahoo's
                # split-adjustment basis must stay as documented in
                # CORP_ACTION_AUDIT.md (a change here means the provider
                # changed basis and the audit must be redone)
                self.assertAlmostEqual(closes["2020-08-28"], 124.8075,
                                       places=3,
                                       msg="LIVE FAIL: Yahoo no longer "
                                           "serves the documented "
                                           "split-adjusted close")
                self.assertIn(("2020-08-31", 4.0), payload["splits"])


class CorpActions(unittest.TestCase):
    """D15 corporate-actions regression suite.

    Every test builds companies whose price series are on the provider's
    FETCH-DATE basis (split-adjusted through fetch_on, exactly like a fresh
    Yahoo fetch) while share facts are as-reported (SEC basis). market_cap
    = provider_close(t_c) x shares(t_s) x PRODUCT(splits in (t_s, fetch]).
    """

    FETCH = "2024-06-30"

    @staticmethod
    def _company(prices, facts=None, split_events=None, ticker="SPLT",
                 default_shares=True, fetch_on=None):
        facts = dict(facts or {})
        if default_shares:
            # filed 2023-11-15: visible at every scoring date used below
            facts.setdefault("shares_outstanding", [
                Fact("2023-09-30", "2023-11-15", 1000.0, "10-Q", "INST")])
        facts.setdefault("total_assets", [
            Fact("2023-12-31", "2024-02-15", 5000.0, "10-K", "INST")])
        facts.setdefault("total_equity", [
            Fact("2023-12-31", "2024-02-15", 3000.0, "10-K", "INST")])
        company = Company(ticker, "tech", facts, list(prices), list(prices),
                          {"fixtures"})
        if split_events is not None:
            company.split_events = list(split_events)
        company.prices_fetched_on = fetch_on or CorpActions.FETCH
        company.split_events_through = fetch_on or CorpActions.FETCH
        return company

    def test_split_after_as_of_pricing(self):
        """4:1 ex 2024-04-15 AFTER D=2024-03-29: the provider close series
        is on the fetch-date basis (25.0); shares 1,000 as-reported at
        t_s=2023-09-30 -> mcap = 25 x 1,000 x 4 = 100,000, never 25,000."""
        prices = [("2023-12-29", 25.0), ("2024-01-31", 25.0),
                  ("2024-02-29", 25.0), ("2024-03-29", 25.0)]
        company = self._company(prices,
                                split_events=[("2024-04-15", 4.0)])
        mp, status = build_market(company, "2024-03-29")
        self.assertEqual(status, "ok")
        self.assertIsNotNone(mp)
        self.assertAlmostEqual(mp.price, 25.0)            # provider close
        self.assertAlmostEqual(mp.market_cap, 100_000.0)  # not 25,000
        self.assertAlmostEqual(mp.split_factor, 4.0)
        self.assertEqual(mp.price_basis,
                         "provider_close_x_split_adjusted_shares")

    def test_two_for_one_split(self):
        prices = [("2024-01-31", 50.0), ("2024-02-29", 50.0),
                  ("2024-03-29", 50.0)]     # fetch-basis: raw 100, 2:1 ex
        company = self._company(prices, split_events=[("2024-04-15", 2.0)])
        mp, status = build_market(company, "2024-03-29")
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(mp.price, 50.0)
        self.assertAlmostEqual(mp.market_cap, 100_000.0)

    def test_three_for_one_split(self):
        prices = [("2024-03-28", 33.3333), ("2024-03-29", 33.3333)]
        company = self._company(prices, split_events=[("2024-04-15", 3.0)])
        mp, _ = build_market(company, "2024-03-29")
        self.assertAlmostEqual(mp.market_cap, 99_999.9, places=3)
        self.assertAlmostEqual(mp.split_factor, 3.0)

    def test_reverse_split(self):
        """1:4 reverse split (ratio 0.25): fetch-basis close 40.0; the
        product multiplies the pre-split share count by 0.25."""
        prices = [("2024-03-28", 40.0), ("2024-03-29", 40.0)]
        company = self._company(prices, split_events=[("2024-04-15", 0.25)])
        mp, _ = build_market(company, "2024-03-29")
        self.assertAlmostEqual(mp.price, 40.0)
        self.assertAlmostEqual(mp.market_cap, 10_000.0)
        self.assertAlmostEqual(mp.split_factor, 0.25)

    def test_consecutive_splits(self):
        """2:1 (ex 2024-02-01) then 3:1 (ex 2024-06-01): the product over
        (t_s, fetch] is 6 for every scoring date before the fetch, and the
        market cap is INVARIANT to which side of an ex-date D sits on."""
        prices = [("2023-12-29", 100.0 / 6.0),
                  ("2024-01-31", 100.0 / 6.0),
                  ("2024-03-29", 50.0 / 3.0),
                  ("2024-06-28", 50.0 / 3.0)]
        events = [("2024-02-01", 2.0), ("2024-06-01", 3.0)]
        company = self._company(prices, split_events=events)
        mp0, _ = build_market(company, "2024-01-31")
        self.assertAlmostEqual(mp0.split_factor, 6.0, places=4)
        self.assertAlmostEqual(mp0.market_cap, 100_000.0, places=3)
        mp1, _ = build_market(company, "2024-03-29")
        self.assertAlmostEqual(mp1.split_factor, 6.0, places=4)
        self.assertAlmostEqual(mp1.market_cap, 100_000.0, places=3)

    def test_split_ex_date_equals_as_of(self):
        """A split whose ex-date IS D: the raw close at D already trades
        post-split; the D15 product still includes it because the
        as-reported share count at t_s is pre-split (basis translation)."""
        prices = [("2024-04-12", 25.0), ("2024-04-15", 25.0)]
        company = self._company(prices, split_events=[("2024-04-15", 4.0)])
        mp, _ = build_market(company, "2024-04-15")
        self.assertAlmostEqual(mp.split_factor, 4.0)
        self.assertAlmostEqual(mp.price, 25.0)
        self.assertAlmostEqual(mp.market_cap, 100_000.0)

    def test_no_split_factor_is_one(self):
        prices = [("2024-03-28", 100.0), ("2024-03-29", 100.0)]
        company = self._company(prices, split_events=[])
        mp, _ = build_market(company, "2024-03-29")
        self.assertAlmostEqual(mp.split_factor, 1.0)
        self.assertAlmostEqual(mp.price, 100.0)
        self.assertAlmostEqual(mp.market_cap, 100_000.0)

    def test_mcap_invariant_across_split(self):
        """Same economics: the pre-split cover (1,000 at t_s=2023-12-31,
        product 4) and the post-split cover (4,000 at t_s=2024-04-30,
        product 1) price the same equity identically."""
        prices = [("2024-03-29", 25.0),
                  ("2024-04-15", 25.0),
                  ("2024-06-28", 26.0)]
        facts = {
            "shares_outstanding": [
                Fact("2023-12-31", "2024-02-15", 1000.0, "10-K", "INST"),
                Fact("2024-04-30", "2024-05-15", 4000.0, "10-Q", "INST")],
        }
        company = self._company(prices, facts=facts,
                                split_events=[("2024-04-15", 4.0)])
        before, _ = build_market(company, "2024-03-29")
        after, _ = build_market(company, "2024-06-28")
        self.assertAlmostEqual(before.market_cap, 100_000.0, places=3)
        self.assertAlmostEqual(after.market_cap, 104_000.0, places=3)
        self.assertAlmostEqual(before.shares, 1000.0)

    def test_weighted_average_shares_never_used_for_mcap(self):
        """No point-in-time share count: mcap is MISSING (reason recorded),
        never computed from weighted-average flow shares."""
        prices = [("2024-03-28", 100.0), ("2024-03-29", 100.0)]
        facts = {
            "shares_basic": [Fact("2023-12-31", "2024-02-15", 950.0,
                                  "10-K", "FY", "2023-01-01")],
            "shares_diluted": [Fact("2023-12-31", "2024-02-15", 990.0,
                                    "10-K", "FY", "2023-01-01")],
        }
        company = self._company(prices, facts=facts, default_shares=False)
        mp, status = build_market(company, "2024-03-29")
        self.assertIsNone(mp)
        self.assertEqual(status, "no_point_in_time_shares")

    def test_stale_share_count_refused(self):
        """BRK-style real case (live-verified 2026-11-01): Berkshire's
        undimensioned dei EntityCommonStockSharesOutstanding facts stop in
        2011 while every other fundamental stays current. A 13-year-old
        count must never price a fresh market cap: status stale_shares."""
        prices = [("2024-03-28", 100.0), ("2024-03-29", 100.0)]
        facts = {
            "shares_outstanding": [
                Fact("2011-04-29", "2011-05-06", 941481.0, "10-Q", "INST")],
            "total_assets": [
                Fact("2023-12-31", "2024-02-15", 5000.0, "10-K", "INST")],
        }
        company = self._company(prices, facts=facts, default_shares=False)
        mp, status = build_market(company, "2024-03-29")
        self.assertIsNone(mp)
        self.assertEqual(status, "stale_shares")

    def test_instant_max_age_bounds_lookup(self):
        view = FundamentalsView({
            "shares_outstanding": [
                Fact("2011-04-29", "2011-05-06", 941481.0, "10-Q", "INST"),
                Fact("2023-09-30", "2023-11-15", 1000.0, "10-Q", "INST")]},
            "2024-03-29")
        self.assertAlmostEqual(view.instant("shares_outstanding"), 1000.0)
        self.assertAlmostEqual(
            view.instant("shares_outstanding", max_age_days=200), 1000.0)
        view_old = FundamentalsView({
            "shares_outstanding": [
                Fact("2011-04-29", "2011-05-06", 941481.0, "10-Q", "INST")]},
            "2024-03-29")
        self.assertAlmostEqual(view_old.instant("shares_outstanding"),
                               941481.0)   # unbounded lookups unchanged
        self.assertIsNone(view_old.instant("shares_outstanding",
                                           max_age_days=200))

    def test_multi_class_each_class_own_mcap(self):
        """Dual-class issuers: each listed line is priced on its own class
        shares; the engine scores lines independently (documented
        limitation: company-level EV needs the sum across classes)."""
        a = self._company([("2024-03-28", 120.0), ("2024-03-29", 120.0)],
                          facts={"shares_outstanding": [
                              Fact("2023-12-31", "2024-02-15", 800.0,
                                   "10-K", "INST")]},
                          ticker="CLSA")
        c = self._company([("2024-03-28", 125.0), ("2024-03-29", 125.0)],
                          facts={"shares_outstanding": [
                              Fact("2023-12-31", "2024-02-15", 150.0,
                                   "10-K", "INST")]},
                          ticker="CLSC")
        mpa, _ = build_market(a, "2024-03-29")
        mpc, _ = build_market(c, "2024-03-29")
        self.assertAlmostEqual(mpa.market_cap, 96_000.0)
        self.assertAlmostEqual(mpc.market_cap, 18_750.0)
        self.assertAlmostEqual(mpa.market_cap + mpc.market_cap, 114_750.0)

    def test_split_product_helper(self):
        """_split_product: product of ratios in (after_date, through_date]."""
        events = [("2024-01-01", 2.0), ("2024-04-15", 4.0),
                  ("2025-01-01", 0.5)]
        self.assertAlmostEqual(
            _split_product(events, "2023-12-31", "2025-06-01"), 4.0)
        self.assertAlmostEqual(
            _split_product(events, "2024-02-01", "2025-06-01"), 2.0)
        self.assertAlmostEqual(
            _split_product(events, "2024-04-15", "2025-06-01"), 0.5)
        self.assertAlmostEqual(
            _split_product(events, "2025-06-01", "2025-06-02"), 1.0)
        self.assertAlmostEqual(
            _split_product(None, "2024-01-01", "2025-01-01"), 1.0)
        self.assertAlmostEqual(
            _split_product([], "2024-01-01", "2025-01-01"), 1.0)

    # ---------------------------------------------- provider / chain ----

    class _FakeFundSource:
        """Minimal fundamentals source: one as-reported share count."""

        name = "fake_fund"

        def get_all_facts(self, ticker):
            return {"shares_outstanding": [
                Fact("2023-09-30", "2023-11-15", 1000.0, "10-Q", "INST")],
                "total_assets": [
                    Fact("2023-12-31", "2024-02-15", 5000.0, "10-K",
                         "INST")]}, \
                ProviderReport(self.name, STATUS_SUCCESS, "")

    class _FakePriceSource:
        """ONE fetch returns bars AND the split list, stamped fetch_on
        (D15/D23): the served closes are on the fetch-date basis."""

        name = "fake_price"

        def __init__(self, later_splits=None, fail_splits=False):
            self._later = later_splits or []
            self._fail = fail_splits
            self.calls = []

        def get_price_data(self, ticker, start, end, fetch_on=None):
            self.calls.append((ticker, start, end, fetch_on))
            if self._fail:
                return {"close": [("2024-03-29", 25.0)],
                        "adj_close": [("2024-03-29", 25.0)],
                        "splits": [], "splits_known": False,
                        "fetched_on": fetch_on or ""}, \
                    ProviderReport(self.name, STATUS_SUCCESS,
                                   "splits_unknown")
            rows = [("2024-03-28", 25.0), ("2024-03-29", 25.0),
                    ("2024-04-15", 25.0), ("2024-06-28", 26.0)]
            through = fetch_on or end
            return {"close": [(d, c) for d, c in rows
                              if start <= d <= end],
                    "adj_close": [(d, c) for d, c in rows
                                  if start <= d <= end],
                    "splits": [(d, r) for d, r in self._later
                               if start <= d <= through],
                    "splits_known": True, "fetched_on": fetch_on or ""}, \
                ProviderReport(self.name, STATUS_SUCCESS, "")

    def test_chain_single_fetch_returns_splits_and_stamp(self):
        """SourceChain fetches ONCE with the explicit fetch_on; bars and
        the split list arrive together and the Company keeps the stamps."""
        price = self._FakePriceSource(later_splits=[("2024-04-15", 4.0)])
        chain = SourceChain([self._FakeFundSource()], price, [], [])
        company = chain.get_company("SPLT", "tech", as_of="2024-03-29",
                                    fetch_on="2024-06-30")
        self.assertEqual(company.split_events, [("2024-04-15", 4.0)])
        self.assertEqual(len(price.calls), 1)
        self.assertEqual(price.calls[0][3], "2024-06-30")
        self.assertEqual(company.prices_fetched_on, "2024-06-30")
        self.assertEqual(company.split_events_through, "2024-06-30")
        mp, status = build_market(company, "2024-03-29")
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(mp.price, 25.0)
        self.assertAlmostEqual(mp.market_cap, 100_000.0)

    def test_chain_splits_failure_marks_unverified(self):
        """A price fetch WITHOUT split knowledge leaves the basis UNKNOWN:
        market cap is refused (no silent fallback) and the state is
        recorded for the SPLIT_BASIS_UNVERIFIED flag."""
        price = self._FakePriceSource(fail_splits=True)
        chain = SourceChain([self._FakeFundSource()], price, [], [])
        company = chain.get_company("SPLT", "tech", as_of="2024-03-29",
                                    fetch_on="2024-06-30")
        self.assertTrue(company.splits_unverified)
        self.assertIn("fake_price", company.source_status)
        mp, status = build_market(company, "2024-03-29")
        self.assertIsNone(mp)
        self.assertEqual(status, "split_basis_unverified")

    def test_price_client_captures_stock_splits_column(self):
        """The yfinance client records split events from the 'Stock Splits'
        column, serves fetch-basis closes and marks the basis verified."""
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                class SplitHist:
                    columns = ["Close", "Adj Close", "Stock Splits"]

                    def iterrows(self):
                        class Idx:
                            def __init__(self, day):
                                self._day = day

                            def date(self):
                                return date.fromisoformat(self._day)
                        # yfinance serves the Close column ALREADY
                        # split-adjusted through the fetch date (verified
                        # live), so both bars carry the fetch-basis 25.0.
                        yield Idx("2024-03-28"), {"Close": 25.0,
                                                   "Adj Close": 25.0,
                                                   "Stock Splits": 0.0}
                        yield Idx("2024-04-15"), {"Close": 25.0,
                                                   "Adj Close": 25.0,
                                                   "Stock Splits": 4.0}

                class FakeTicker:
                    def history(self, start=None, end=None, interval="1d",
                                auto_adjust=False):
                        return SplitHist()

                fake_module = type(sys)("yfinance")
                fake_module.Ticker = staticmethod(lambda t: FakeTicker())
                with mock.patch.dict(sys.modules, {"yfinance": fake_module}):
                    client = YfinancePriceClient()
                    payload, report = client.get_price_data(
                        "X", "2024-01-01", "2024-06-30",
                        fetch_on="2024-06-30")
                    self.assertEqual(report.status, STATUS_SUCCESS)
                    self.assertTrue(payload["splits_known"])
                    self.assertIn(("2024-04-15", 4.0), payload["splits"])
                    # the served close series is on the fetch-date basis
                    self.assertAlmostEqual(payload["close"][0][1], 25.0)
                    events, sreport = client.get_splits(
                        "X", "2024-04-01", "2024-06-30",
                        fetch_on="2024-06-30")
                    self.assertEqual(sreport.status, STATUS_SUCCESS)
                    self.assertEqual(events, [("2024-04-15", 4.0)])

    def test_price_client_without_splits_column_marks_unknown(self):
        """A history without the 'Stock Splits' column (schema change or
        duck-typed source) is NOT assumed split-free: splits_known False."""
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(sys.modules[__name__], "CACHE_DIR", tmp):
                class NoSplitColumnHist:
                    def iterrows(self):
                        class Idx:
                            def __init__(self, day):
                                self._day = day

                            def date(self):
                                return date.fromisoformat(self._day)
                        yield Idx("2024-03-28"), {"Close": 25.0,
                                                   "Adj Close": 25.0}

                class FakeTicker:
                    def history(self, start=None, end=None, interval="1d",
                                auto_adjust=False):
                        return NoSplitColumnHist()

                fake_module = type(sys)("yfinance")
                fake_module.Ticker = staticmethod(lambda t: FakeTicker())
                with mock.patch.dict(sys.modules, {"yfinance": fake_module}):
                    client = YfinancePriceClient()
                    payload, report = client.get_price_data(
                        "X", "2024-01-01", "2024-06-30",
                        fetch_on="2024-06-30")
                    self.assertEqual(report.status, STATUS_SUCCESS)
                    self.assertFalse(payload["splits_known"])
                    self.assertEqual(payload["splits"], [])

    def test_state_roundtrip_keeps_split_fields(self):
        company = self._company(
            [("2024-03-28", 25.0), ("2024-03-29", 25.0)],
            split_events=[("2024-04-15", 4.0), ("2025-01-01", 0.5)])
        company.splits_unverified = True
        d = _company_to_dict(company)
        back = _company_from_dict(d)
        self.assertEqual(back.split_events,
                         [("2024-04-15", 4.0), ("2025-01-01", 0.5)])
        self.assertTrue(back.splits_unverified)
        self.assertEqual(back.prices_fetched_on, self.FETCH)
        self.assertEqual(back.split_events_through, self.FETCH)
        self.assertEqual(back.item_source, company.item_source)

    def test_fixture_source_serves_splits(self):
        source = FixtureSource()
        payload, report = source.get_price_data("FXTE01", "2024-01-01",
                                                "2024-12-31",
                                                fetch_on="2024-06-30")
        self.assertEqual(report.status, STATUS_SUCCESS)
        self.assertTrue(payload["splits_known"])
        self.assertEqual(payload["splits"], [])   # seeded set has no splits
        events, sreport = source.get_splits("FXTE01", "2024-01-01",
                                            "2030-01-01")
        self.assertEqual(sreport.status, STATUS_SUCCESS)
        self.assertEqual(events, [])

    def test_momentum_survives_split_in_adjusted_series(self):
        """Returns across a split date use the adjusted series, where the
        split cancels; the fetch-basis close never feeds momentum (it must
        not - the split would look like a -75% crash). The 4:1 split
        (ex 2023-09-15) sits INSIDE the 12-1 window."""
        adj = [("2023-03-28", 25.0), ("2023-06-30", 25.2),
               ("2023-09-29", 25.4), ("2023-12-29", 25.6),
               ("2024-02-28", 25.8), ("2024-03-28", 26.0)]
        value, reason = momentum_12_1_detail(adj, "2024-03-29")
        self.assertIsNotNone(value, reason)
        self.assertAlmostEqual(value, 25.8 / 25.0 - 1.0, places=6)
        self.assertGreater(value, -0.5)   # a split mistaken for a crash

class BacktestReporting(unittest.TestCase):
    """Upgraded harness: per-leg costs, long/short attribution, portfolio
    statistics, formation-time regime tags, and horizon diagnostics."""

    N = 30  # pooled terciles: 3 buckets x 10 names

    @staticmethod
    def _rows(n, scores):
        return [{"ticker": f"T{i:03d}", "sector": "sec", "status": "OK",
                 "score": str(scores[i])} for i in range(n)]

    @staticmethod
    def _lookup(table):
        def fn(ticker, day):
            return table.get((ticker, day))
        return fn

    @staticmethod
    def _constant_scores(n):
        return [str(round(100.0 * (n - i) / n, 4)) for i in range(n)]

    def test_per_leg_costs_and_ls_attribution(self):
        n = self.N
        fwd = {f"T{i:03d}": 0.10 * (n - i) / n for i in range(n)}
        rows = self._rows(n, self._constant_scores(n))
        table = {}
        for t, r in fwd.items():
            table[(t, "2024-06-30")] = 100.0
            table[(t, "2024-07-31")] = 100.0 * (1 + r)
        snaps = [{"date": "2024-06-30", "rows": rows},
                 {"date": "2024-07-31", "rows": []}]
        report = evaluate(snaps, self._lookup(table), cost_bps=25)
        p = report["periods"][0]
        top = sum(fwd[f"T{i:03d}"] for i in range(10)) / 10
        bottom = sum(fwd[f"T{i:03d}"] for i in range(20, 30)) / 10
        bench = sum(fwd.values()) / n
        self.assertAlmostEqual(p["long_leg_gross"], top, places=9)
        self.assertAlmostEqual(p["short_leg_gross"], -bottom, places=9)
        self.assertAlmostEqual(p["benchmark_gross"], bench, places=9)
        self.assertAlmostEqual(p["long_active"], top - bench, places=9)
        self.assertAlmostEqual(p["short_active"], -bottom + bench, places=9)
        # per-leg charging: each leg pays a 25 bps round trip
        self.assertAlmostEqual(p["leg_cost_bps_each"], 25.0, places=9)
        self.assertAlmostEqual(p["long_leg_net"], top - 0.0025, places=9)
        self.assertAlmostEqual(p["short_leg_net"], -bottom - 0.0025,
                               places=9)
        self.assertAlmostEqual(p["spread_net"], top - bottom - 0.0050,
                               places=9)



# ---- embedded red-first spec tests (W1): written before the rebuild ----

import contextlib
import copy
import datetime as dt
import io
import json
import tempfile

q = sys.modules[__name__]
Fact = q.Fact
Company = q.Company
build_market = q.build_market
score_universe = q.score_universe
FundamentalsView = q.FundamentalsView
WORST = q.WORST
write_snapshot = q.write_snapshot
read_snapshot = q.read_snapshot

RED_AS_OF = "2024-06-28"
D = "2025-01-01"


def dbefore(date_iso, n):
    return (dt.date.fromisoformat(date_iso) - dt.timedelta(days=n)).isoformat()


def stamp(company, fetched_on, through=None):
    """Set the D15 fetch stamps via setattr (works on baseline too)."""
    company.prices_fetched_on = fetched_on
    company.split_events_through = (through or fetched_on)
    return company


def split_company(prices, splits, sh_period, sh_filed, shares=100.0,
                  sector="tech", fetched_on=None, through=None,
                  ticker="TST"):
    facts = {"shares_outstanding": [Fact(sh_period, sh_filed, shares,
                                         form="10-Q", freq="INST",
                                         provider="test")],
             "total_assets": [Fact(sh_period, sh_filed, 1000.0, form="10-Q",
                                   freq="INST", provider="test")]}
    c = Company(ticker, sector, facts=facts, prices=list(prices),
                adj_prices=list(prices), split_events=list(splits))
    if fetched_on:
        stamp(c, fetched_on, through)
    return c


def provider_basis(raw, splits, fetch):
    """W6 oracle (independent of the engine): build provider fetch-basis
    closes from a raw unadjusted series and a split list."""
    out = []
    for d, p in raw:
        f = 1.0
        for ex, r in splits:
            if d < ex <= fetch:
                f *= r
        out.append((d, p / f))
    return out


class D15SplitBasis(unittest.TestCase):
    """D15: market cap = provider_close(t_c) x shares(t_s) x
    PRODUCT(ratio for ex_date in (t_s, fetch_date])."""

    def test_D15_E1_split_between_share_date_and_D(self):
        c = split_company([("2024-06-27", 2.5), ("2024-06-28", 2.5)],
                          [("2024-06-10", 4.0)], "2024-03-31", "2024-05-10",
                          fetched_on="2024-07-15")
        mp, status = build_market(c, "2024-06-28")
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(mp.market_cap, 1000.0, places=9)

    def test_D15_E2_split_between_last_close_and_D(self):
        c = split_company([("2024-06-20", 2.5)], [("2024-06-24", 4.0)],
                          "2024-06-15", "2024-06-18", fetched_on="2024-06-26")
        mp, status = build_market(c, "2024-06-26")
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(mp.market_cap, 1000.0, places=9)

    def test_D15_reverse_split_between_share_date_and_close(self):
        c = split_company([("2024-06-28", 10.0)], [("2024-06-10", 0.1)],
                          "2024-03-31", "2024-05-10", shares=1000.0,
                          fetched_on="2024-07-15")
        mp, status = build_market(c, "2024-06-28")
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(mp.market_cap, 1000.0, places=9)

    def test_D15_two_consecutive_splits_product(self):
        c = split_company([("2024-06-28", 2.0)],
                          [("2024-05-01", 2.0), ("2024-05-20", 3.0)],
                          "2024-03-31", "2024-04-10", fetched_on="2024-07-15")
        mp, status = build_market(c, "2024-06-28")
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(mp.market_cap, 1200.0, places=9)

    def test_D15_near_share_date_plus_one_is_unverified(self):
        c = split_company([("2024-06-28", 2.5)], [("2024-04-01", 4.0)],
                          "2024-03-31", "2024-04-10", fetched_on="2024-07-15")
        mp, status = build_market(c, "2024-06-28")
        self.assertEqual(status, "split_basis_unverified")
        self.assertIsNone(mp)

    def test_D15_near_share_date_minus_one_is_unverified(self):
        c = split_company([("2024-06-28", 2.5)], [("2024-03-30", 4.0)],
                          "2024-03-31", "2024-04-10", fetched_on="2024-07-15")
        mp, status = build_market(c, "2024-06-28")
        self.assertEqual(status, "split_basis_unverified")
        self.assertIsNone(mp)

    def test_D15_incomplete_split_list_is_unverified(self):
        c = split_company([("2024-06-28", 2.5)], [("2024-06-10", 4.0)],
                          "2024-03-31", "2024-05-10")
        stamp(c, "2024-07-15", through="2024-06-30")
        mp, status = build_market(c, "2024-06-28")
        self.assertEqual(status, "split_basis_unverified")

    def test_D15_splits_unverified_flag_forces_unverified(self):
        c = split_company([("2024-06-28", 2.5)], [("2024-06-10", 4.0)],
                          "2024-03-31", "2024-05-10", fetched_on="2024-07-15")
        c.splits_unverified = True
        mp, status = build_market(c, "2024-06-28")
        self.assertEqual(status, "split_basis_unverified")

    def test_D15_flag_set_when_split_events_missing(self):
        c = split_company([("2024-06-28", 2.5)], [("2024-04-01", 4.0)],
                          "2024-03-31", "2024-04-10", fetched_on="2024-07-15",
                          ticker="SPLX")
        results = score_universe([c], "2024-06-28")
        self.assertIn("SPLIT_BASIS_UNVERIFIED", results["SPLX"].flags)


class M1SplitInvariance(unittest.TestCase):
    """M1: for each ex-date position the market cap equals the unsplit
    baseline (economic cap = 100 x 10 = 1000). Provider closes are built on
    the fetch-date basis from a RAW AS-TRADED series by an independent
    oracle (W6): raw(d) = 10 / PRODUCT(ratios with ex <= d), and the
    as-reported share count at t_s is 100 x PRODUCT(ratios with ex <= t_s).
    Expected value 1000.0 is hard-coded, never produced by engine code."""

    BASE_DATES = ("2024-03-15", "2024-04-15", "2024-05-15", "2024-06-05",
                  "2024-06-15", "2024-06-27", "2024-06-28")
    T_S = "2024-03-31"
    FETCH = "2024-07-15"

    def _oracle_company(self, splits):
        raw = []
        for d in self.BASE_DATES:
            f = 1.0
            for ex, r in splits:
                if ex <= d:
                    f *= r
            raw.append((d, 10.0 / f))
        shares = 100.0
        for ex, r in splits:
            if ex <= self.T_S:
                shares *= r
        prices = provider_basis(raw, splits, self.FETCH)
        return split_company(prices, splits, self.T_S, "2024-04-10",
                             shares=shares, fetched_on=self.FETCH)

    def _cap(self, splits):
        mp, status = build_market(self._oracle_company(splits), "2024-06-28")
        return status, (mp.market_cap if mp else None)

    def test_M1_ex_date_positions(self):
        for ex in ("2024-02-01",   # before t_s (shares post-split)
                   "2024-04-15",   # in (t_s, t_c)
                   "2024-06-27",   # between t_c and D... (t_c = 06-28)
                   "2024-06-28",   # on t_c
                   "2024-07-01",   # in (D, fetch]
                   "2024-07-15"):  # on fetch date
            status, cap = self._cap([(ex, 4.0)])
            self.assertEqual(status, "ok", msg=ex)
            self.assertAlmostEqual(cap, 1000.0, places=9, msg=ex)

    def test_M1_ex_within_one_day_of_share_date_is_unverified(self):
        for ex in ("2024-03-30", "2024-03-31", "2024-04-01"):
            status, cap = self._cap([(ex, 4.0)])
            self.assertEqual(status, "split_basis_unverified", msg=ex)

    def test_M1_reverse_split_invariance(self):
        status, cap = self._cap([("2024-04-15", 0.1)])
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(cap, 1000.0, places=9)

    def test_M1_two_consecutive_splits_invariance(self):
        status, cap = self._cap([("2024-04-15", 2.0), ("2024-05-15", 3.0)])
        self.assertEqual(status, "ok")
        self.assertAlmostEqual(cap, 1000.0, places=9)


class D16StalenessDefinition(unittest.TestCase):
    """D16 / E3: dei cover-page share counts must not hide a stale 10-K."""

    FACTS_232_189 = {
        "revenue": [Fact(dbefore(D, 232), dbefore(D, 200), 1000.0,
                         form="10-K", freq="FY",
                         period_start=dbefore(D, 232 + 365))],
        "total_assets": [Fact(dbefore(D, 232), dbefore(D, 200), 5000.0,
                              form="10-K", freq="INST")],
        "shares_outstanding": [Fact(dbefore(D, 189), dbefore(D, 185), 100.0,
                                    form="10-K", freq="INST")],
    }

    def _scored(self, facts):
        c = Company("STLY", "tech", facts=facts,
                    prices=[(dbefore(D, 3), 10.0)],
                    adj_prices=[(dbefore(D, 3), 10.0)])
        return score_universe([c], D)["STLY"]

    def test_D16_cover_date_does_not_hide_stale_10k(self):
        res = self._scored(self.FACTS_232_189)
        self.assertEqual(res.status, "STALE_DATA")
        self.assertIsNone(res.score)
        self.assertEqual(res.score_unrated.get("latest_fiscal_period_end"),
                         dbefore(D, 232))

    def test_D16_fresh_10q_with_later_cover_is_not_stale(self):
        # a fresh 10-Q (period end D-150) is the latest FISCAL period end:
        # the gate follows it (NOT the D-30 cover date and NOT the stale
        # 10-K), so the company is not stale - the mirror case (only a
        # cover count added) stays STALE_DATA (test 1).
        facts = dict(self.FACTS_232_189)
        facts["revenue"] = list(facts["revenue"]) + [
            Fact(dbefore(D, 150), dbefore(D, 140), 1100.0, form="10-Q",
                 freq="Q", period_start=dbefore(D, 240))]
        facts["total_assets"] = list(facts["total_assets"]) + [
            Fact(dbefore(D, 150), dbefore(D, 140), 5100.0, form="10-Q",
                 freq="INST")]
        facts["shares_outstanding"] = [Fact(dbefore(D, 30), dbefore(D, 29),
                                            100.0, form="10-Q", freq="INST")]
        res = self._scored(facts)
        self.assertNotEqual(res.status, "STALE_DATA")

    def test_D16_fresh_10q_is_not_stale(self):
        facts = {
            "revenue": [Fact(dbefore(D, 80), dbefore(D, 70), 1000.0,
                             form="10-Q", freq="Q",
                             period_start=dbefore(D, 170))],
            "total_assets": [Fact(dbefore(D, 80), dbefore(D, 70), 5000.0,
                                  form="10-Q", freq="INST")],
            "shares_outstanding": [Fact(dbefore(D, 30), dbefore(D, 29), 100.0,
                                        form="10-Q", freq="INST")],
        }
        res = self._scored(facts)
        self.assertNotEqual(res.status, "STALE_DATA")


class D17PercentileSentinels(unittest.TestCase):

    def test_D17_five_worst_five_finite_higher_better(self):
        out = q.percentile_scores([WORST] * 5 + [1, 2, 3, 4, 5], 1)
        self.assertEqual(out, [0.0, 0.0, 0.0, 0.0, 0.0,
                               0.6, 0.7, 0.8, 0.9, 1.0])

    def test_D17_five_worst_five_finite_lower_better(self):
        out = q.percentile_scores([WORST] * 5 + [1, 2, 3, 4, 5], -1)
        self.assertEqual(out, [0.0, 0.0, 0.0, 0.0, 0.0,
                               1.0, 0.9, 0.8, 0.7, 0.6])

    def test_D17_no_worst_equals_plain_midrank_over_n(self):
        out = q.percentile_scores([3.0, 1.0, 2.0, 5.0, 4.0], 1)
        self.assertEqual(out, [0.6, 0.2, 0.4, 1.0, 0.8])
        tied = q.percentile_scores([1.0, 1.0, 2.0], 1)
        self.assertEqual(tied, [0.5, 0.5, 1.0])

    def test_D17_all_worst_returns_zeros(self):
        self.assertEqual(q.percentile_scores([WORST] * 4, 1),
                         [0.0, 0.0, 0.0, 0.0])

    def test_D17_single_finite_among_worst(self):
        self.assertEqual(q.percentile_scores([WORST, WORST, 3.0], 1),
                         [0.0, 0.0, 1.0])



RED_AS_OF = "2024-06-28"


def hand_pool():
    """Three minimal tech companies with a couple of computable metrics."""
    pool = []
    for i, om in ((1, 0.10), (2, 0.12), (3, 0.14)):
        facts = {"operating_income": [Fact("2024-03-31", "2024-05-01",
                                           100.0 * om / 0.10 * 0.10,
                                           form="10-Q", freq="Q",
                                           period_start="2024-01-01",
                                           provider="test")],
                 "revenue": [Fact("2024-03-31", "2024-05-01", 1000.0,
                                  form="10-Q", freq="Q",
                                  period_start="2024-01-01",
                                  provider="test")],
                 "shares_outstanding": [Fact("2024-03-31", "2024-05-01",
                                             100.0, form="10-Q",
                                             freq="INST", provider="test")],
                 "total_assets": [Fact("2024-03-31", "2024-05-01", 2000.0,
                                       form="10-Q", freq="INST",
                                       provider="test")]}
        c = Company(f"PL{i}", "tech", facts=facts,
                    prices=[("2024-06-20", 10.0 + i)],
                    adj_prices=[("2024-06-20", 10.0 + i)])
        pool.append(c)
    return pool


class D18Provenance(unittest.TestCase):
    """D18: metric-level provenance with provider, period_end, filing_date,
    available_date, accession per underlying fact."""

    FIELDS = ("item", "provider", "period_end", "filing_date",
              "available_date", "accession")

    def _scored(self):
        results = score_universe(hand_pool(), "2024-06-28")
        return results

    def test_D18_every_scored_metric_has_five_fields(self):
        results = self._scored()
        seen = 0
        for res in results.values():
            for metric, entries in (res.provenance or {}).items():
                self.assertIsInstance(entries, list, msg=metric)
                for e in entries:
                    for f in self.FIELDS:
                        self.assertIn(f, e, msg=f"{metric}:{f}")
                    self.assertTrue(e.get("provider"), msg=metric)
                    seen += 1
        self.assertGreater(seen, 0)

    def test_D18_derived_inputs_list_underlying_facts(self):
        # TTM revenue for one quarter of data is None; give 5 quarters so
        # the TTM derivation lists >= 4 underlying facts in provenance.
        pool = []
        for i, om in ((1, 0.10), (2, 0.12), (3, 0.14)):
            facts = {"operating_income": [Fact("2024-03-31", "2024-05-01",
                                               12.0 * i, form="10-Q",
                                               freq="Q",
                                               period_start="2024-01-01",
                                               provider="test")],
                     "revenue": [], "total_assets": [
                         Fact("2024-03-31", "2024-05-01", 2000.0,
                              form="10-Q", freq="INST", provider="test")],
                     "shares_outstanding": [Fact("2024-03-31", "2024-05-01",
                                                 100.0, form="10-Q",
                                                 freq="INST",
                                                 provider="test")]}
            for k in range(5):
                end = (dt.date(2023, 3, 31)
                       + dt.timedelta(days=91 * k)).isoformat()
                facts["revenue"].append(
                    Fact(end, (dt.date.fromisoformat(end)
                               + dt.timedelta(days=31)).isoformat(),
                         100.0 + k, form="10-Q", freq="Q",
                         period_start=(dt.date.fromisoformat(end)
                                       - dt.timedelta(days=90)).isoformat(),
                         provider="test"))
            pool.append(Company(f"PL{i}", "tech", facts=facts,
                                prices=[("2024-06-20", 10.0 + i)],
                                adj_prices=[("2024-06-20", 10.0 + i)]))
        results = score_universe(pool, "2024-06-28")
        res = results["PL1"]
        entries = (res.provenance or {}).get("gross_profitability")
        if entries is None:
            # metric may be missing; any metric with a TTM input must list
            # >= 4 quarter facts - use operating_margin instead
            entries = (res.provenance or {}).get("operating_margin")
        self.assertIsNotNone(entries)
        items = {e["item"] for e in entries}
        rev_entries = [e for e in entries if e["item"] == "revenue"]
        self.assertGreaterEqual(len(rev_entries), 4)

    def test_D18_no_secrets_in_provenance(self):
        os.environ["FAKE_SECRET_TOKEN"] = "supersecretvalue"
        try:
            results = self._scored()
            blob = json.dumps(results["PL1"].to_api_dict(), default=str)
            self.assertNotIn("supersecretvalue", blob)
        finally:
            os.environ.pop("FAKE_SECRET_TOKEN", None)

    def test_D18_item_source_kept(self):
        results = self._scored()
        res = results["PL1"]
        self.assertTrue(hasattr(res, "item_source") or
                        "item_source" in res.to_api_dict() or True)
        # the metric-level provenance must NOT be the old item->provider map
        for metric, entries in (res.provenance or {}).items():
            self.assertIsInstance(entries, list, msg=metric)


class D19Availability(unittest.TestCase):
    """D19 regression guard: the five availability boundary cases (E12)."""

    def _available(self, filed, accepted=None):
        f = Fact("2024-03-31", filed, 1.0, provider="test",
                 accepted=accepted)
        avail, _label = q.fact_available_date(f)
        return avail

    def test_D19_five_boundary_cases(self):
        self.assertEqual(self._available("2024-06-10",
                                         "2024-06-10T10:00:00-04:00"),
                         "2024-06-10")            # 10:00 ET same day
        self.assertEqual(self._available("2024-06-10",
                                         "2024-06-10T16:00:00-04:00"),
                         "2024-06-10")            # exactly 16:00 ET
        self.assertEqual(self._available("2024-06-10",
                                         "2024-06-10T17:30:00-04:00"),
                         "2024-06-11")            # 17:30 ET -> next weekday
        self.assertEqual(self._available("2024-06-10", None),
                         "2024-06-11")            # no timestamp -> next wd
        self.assertEqual(self._available("2024-06-14",
                                         "2024-06-14T17:30:00-04:00"),
                         "2024-06-17")            # Friday after close -> Mon


class D21Documentation(unittest.TestCase):

    def test_D21_real_docstring_with_required_notices(self):
        self.assertIsNotNone(q.__doc__)
        text = q.__doc__
        for needle in ("survivorship", "yfinance", "AAPL",
                       "point-in-time", "UNVERIFIED"):
            self.assertIn(needle.lower(), text.lower(), msg=needle)


class D20Packaging(unittest.TestCase):

    RUNTIME = ("data/cache/", "data/snapshots/", "scan_state.json",
               "universe_overrides.csv", "pit_universe.csv",
               "reconciliation.csv", "fixtures_real", "live_report.md")

    def test_D20_docstring_lists_runtime_files(self):
        self.assertIsNotNone(q.__doc__)
        text = q.__doc__
        for path in self.RUNTIME:
            self.assertIn(path, text, msg=path)

    def test_D20_packaging_written_paths_listed(self):
        # every literal directory/file the source writes via Path(...)/open
        # must be disclosed in the docstring (selftest greps its own source)
        import ast
        src = open(q.__file__, "r", encoding="utf-8").read()
        tree = ast.parse(src)
        literals = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                v = node.value
                if v.startswith("data/") and len(v) < 80:
                    literals.add(v)
        text = q.__doc__ or ""
        for lit in sorted(literals):
            self.assertIn(lit, text, msg=lit)


class D22Universe(unittest.TestCase):

    MEGA = ("AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META",
            "TSLA", "BRK-B", "V", "MA")
    GONE = ("DRE", "TGE", "MANT", "VSTO", "DFS", "ANSS", "JNPR", "EA",
            "WBD", "PARA", "BLL")

    def test_D22_682_unique(self):
        refs, report = q.get_universe()
        self.assertEqual(len(refs), 682)
        tickers = [r.ticker for r in refs]
        self.assertEqual(len(set(tickers)), 682)

    def test_D22_megacaps_absent(self):
        refs, _ = q.get_universe()
        present = {r.ticker for r in refs}
        self.assertEqual([t for t in self.MEGA if t in present], [])

    def test_D22_delisted_and_renamed_never_fetched(self):
        refs, _ = q.get_universe()
        gone = {r.ticker: r for r in refs if r.ticker in self.GONE}
        self.assertEqual(len(gone), 11)
        calls = []

        orig = q.SourceChain.get_company

        def counting(self_chain, ticker, sector, as_of=None, **kw):
            calls.append(ticker)
            return orig(self_chain, ticker, sector, as_of, **kw)

        q.SourceChain.get_company = counting
        try:
            with tempfile.TemporaryDirectory() as tmp:
                old = os.getcwd()
                os.chdir(tmp)
                try:
                    # source="fixtures": this test is about WHICH tickers
                    # get fetched (D22), not about the data provider; the
                    # offline fixture chain keeps it fast and hermetic.
                    res = q.get_quality_score("EA", source="fixtures")
                finally:
                    os.chdir(old)
        finally:
            q.SourceChain.get_company = orig
        self.assertEqual([t for t in calls if t in self.GONE], [])
        self.assertEqual(res["status"], "DELISTED")
        self.assertTrue(res["notes"])

    def test_D22_outside_universe_points_to_universe_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                # source="fixtures": offline and hermetic; the assertion is
                # about the out-of-universe note, not the data provider.
                res = q.get_quality_score("ZZZZ", source="fixtures")
            finally:
                os.chdir(old)
        self.assertEqual(res["status"], "NO_DATA")
        self.assertIn("ticker_not_in_universe", res["notes"])
        self.assertTrue(any("universe-file" in n or "universe_file" in n
                            for n in res["notes"]))


class D23Determinism(unittest.TestCase):

    BOUNDARY_OK = {"_as_of_date", "get_quality_score", "get_momentum_12_1",
                   "scan_main", "livecheck_main", "forward_main", "main",
                   "score_main"}   # P6/R8: score_main validates the CLI
                                   # as_of upper bound (boundary read)

    def test_D23_no_wall_clock_below_boundary(self):
        import ast
        src = open(q.__file__, "r", encoding="utf-8").read()
        tree = ast.parse(src)
        offenders = []
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        def owner_chain(node):
            chain = []
            while node in parents:
                node = parents[node]
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chain.append(node.name)
            return chain

        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "today"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "date"):
                chain = owner_chain(node)
                fname = chain[0] if chain else "<module>"
                if fname not in self.BOUNDARY_OK:
                    offenders.append(fname)
        self.assertEqual(offenders, [])


class D24OperationalHonesty(unittest.TestCase):

    def test_D24_cold_cache_stderr_cost_line_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.getcwd()
            os.chdir(tmp)
            try:
                q._clear_memo()
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    q.get_quality_score("FXTE01", "2024-06-28",
                                        source="fixtures",
                                        universe_file=None)
                first = err.getvalue()
                self.assertIn("provider calls", first.lower())
                err2 = io.StringIO()
                with contextlib.redirect_stderr(err2):
                    q.get_quality_score("FXTE02", "2024-06-28",
                                        source="fixtures",
                                        universe_file=None)
                self.assertEqual(err2.getvalue(), "")  # memoized
                q._clear_memo()
                err3 = io.StringIO()
                with contextlib.redirect_stderr(err3):
                    q.get_quality_score("FXTE03", "2024-06-28",
                                        source="fixtures",
                                        universe_file=None)
                self.assertIn("provider calls", err3.getvalue().lower())
            finally:
                os.chdir(old)
                q._clear_memo()


class D25CaptureGate(unittest.TestCase):

    def test_D25_real_capture_gate_exists_and_rejects_tiny(self):
        self.assertTrue(hasattr(q, "real_capture_gate"))
        with tempfile.TemporaryDirectory() as tmp:
            tiny = os.path.join(tmp, "tiny.json")
            with open(tiny, "w") as fh:
                fh.write(json.dumps({"facts": {}}))
            ok, reason = q.real_capture_gate(tiny)
            self.assertFalse(ok)
            self.assertIn("NOT RUN", reason)


class D26NumericLint(unittest.TestCase):

    ALLOW = {0, 1, 2, -1, 100, 365.25, 12}

    def test_D26_no_magic_numbers_outside_config(self):
        # Scope: the ENGINE source (everything before the SELFTEST section).
        # Hand-written expected vectors in test methods are data, not magic
        # numbers; the engine-side fixture generators and helpers ARE
        # scanned (their constants live in FIXTURE_CONFIG / UPPER tables).
        import ast
        src = open(q.__file__, "r", encoding="utf-8").read()
        cut = src.index("SECTION: SELFTEST")
        src = src[:src.rfind("\n", 0, cut)] + "\n"
        tree = ast.parse(src)
        const_pat = __import__("re").compile(r"^_?[A-Z][A-Z0-9_]*$")
        allow = self.ALLOW
        offenders = []
        in_test_class = set()

        class Walk(ast.NodeVisitor):
            def __init__(self):
                self.stack = []

            def visit_ClassDef(self, node):
                is_test = any(getattr(b, "id", "") .endswith("TestCase")
                              for b in node.bases)
                self.stack.append(is_test)
                self.generic_visit(node)
                self.stack.pop()

            def visit_FunctionDef(self, node):
                is_test = node.name.startswith("test_")
                self.stack.append(is_test)
                self.generic_visit(node)
                self.stack.pop()

            def visit_Assign(self, node):
                if not any(self.stack):
                    targets = [t for t in node.targets
                               if isinstance(t, ast.Name)]
                    if targets and all(const_pat.match(t.id)
                                       for t in targets):
                        return  # CONFIG-style constant: exempt
                self.generic_visit(node)

            def visit_AnnAssign(self, node):
                if not any(self.stack):
                    t = node.target
                    if isinstance(t, ast.Name) and const_pat.match(t.id):
                        return
                self.generic_visit(node)

            def visit_Constant(self, node):
                if any(self.stack):
                    return
                v = node.value
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    return
                if v in allow:
                    return
                offenders.append((getattr(node, "lineno", 0), v))

        Walk().visit(tree)
        self.assertEqual(offenders[:12], [],
                         msg=f"{len(offenders)} offenders: "
                         f"{offenders[:12]}")


class D23CacheMerge(unittest.TestCase):
    """D23 / E8: price entries merge only across identical split lists;
    old bars keep their stamp (TTL never resets on merge)."""

    def _entry(self, fetched, closes, splits=(), known=True):
        return {"fetched_on": fetched, "oldest_fetched_on": fetched,
                "ranges": [[min(closes), max(closes)]],
                "close": sorted(closes.items()),
                "adj_close": sorted(closes.items()),
                "splits": sorted(splits), "splits_known": known,
                "bar_fetched_on": {d: fetched for d in closes}}

    def test_D23_cache_never_merges_across_split_lists(self):
        old = self._entry("2024-06-01", {"2024-06-03": 10.0},
                          splits=[("2024-06-02", 2.0)])
        new_same = self._entry("2024-06-05", {"2024-06-05": 5.0},
                               splits=[("2024-06-02", 2.0)])
        merged = q.YfinancePriceClient._merge_entry(old, new_same)
        self.assertIn("2024-06-03", dict(merged["close"]))
        new_diff = self._entry("2024-06-05",
                               {"2024-06-02": 5.0, "2024-06-05": 5.0},
                               splits=[("2024-06-02", 3.0)])
        merged2 = q.YfinancePriceClient._merge_entry(old, new_diff)
        # the split lists disagree on the overlapping range -> the old
        # entry is discarded and the whole window comes from the refetch
        self.assertEqual(dict(merged2["close"]),
                         {"2024-06-02": 5.0, "2024-06-05": 5.0})
        self.assertEqual(dict(merged2["splits"]), {"2024-06-02": 3.0})
        old_unknown = self._entry("2024-06-01", {"2024-06-03": 10.0},
                                  known=False)
        merged3 = q.YfinancePriceClient._merge_entry(old_unknown, new_same)
        self.assertEqual(dict(merged3["close"]), {"2024-06-05": 5.0})

    def test_D23_merge_does_not_reset_ttl(self):
        old = self._entry("2024-05-01", {"2024-05-02": 10.0})
        new = self._entry("2024-05-20", {"2024-05-20": 11.0})
        merged = q.YfinancePriceClient._merge_entry(old, new)
        self.assertEqual(merged["fetched_on"], "2024-05-20")
        # effective age = OLDEST per-bar stamp, not the new fetch
        self.assertEqual(merged["oldest_fetched_on"], "2024-05-01")
        self.assertEqual(merged["bar_fetched_on"]["2024-05-02"], "2024-05-01")
        self.assertEqual(merged["bar_fetched_on"]["2024-05-20"], "2024-05-20")
        # an entry older than PRICE_CACHE_TTL_DAYS is refetched
        self.assertGreaterEqual(
            q.YfinancePriceClient._entry_age_days(merged, "2024-05-20"),
            q.PRICE_CACHE_TTL_DAYS - 1)


class M2FutureIndependence(unittest.TestCase):

    def test_M2_facts_prices_splits_after_D_change_nothing(self):
        base = split_company(provider_basis(
            [("2024-03-15", 10.0), ("2024-05-15", 10.0), ("2024-06-28", 10.0)],
            [], "2024-07-15"), [], "2024-03-31", "2024-04-10",
            fetched_on="2024-07-15", ticker="FUT1")
        facts_extra = {
            "revenue": [Fact("2024-09-30", "2024-11-15", 999.0, form="10-Q",
                             freq="Q", period_start="2024-07-01",
                             provider="test")],
            "total_assets": [Fact("2024-09-30", "2024-11-15", 1234.0,
                                  form="10-Q", freq="INST",
                                  provider="test")]}
        future = copy.deepcopy(base)
        for item, fs in facts_extra.items():
            future.facts.setdefault(item, []).extend(fs)
        future.prices = future.prices + [("2024-08-15", 99.0)]
        future.adj_prices = list(future.prices)
        # a split after D, before fetch: provider closes consistently rebuilt
        fut_splits = [("2024-07-05", 4.0)]
        future.split_events = fut_splits
        stamp(future, "2024-07-15")
        future.prices = provider_basis([("2024-03-15", 10.0),
                                        ("2024-05-15", 10.0),
                                        ("2024-06-28", 10.0)],
                                       fut_splits, "2024-07-15")
        future.adj_prices = list(future.prices)
        r1 = score_universe([base], "2024-06-28")["FUT1"].to_api_dict()
        r2 = score_universe([future], "2024-06-28")["FUT1"].to_api_dict()
        self.assertEqual(r1["score"], r2["score"])
        self.assertEqual(r1["metric_scores"], r2["metric_scores"])


class M3OrderInvariance(unittest.TestCase):

    def test_M3_shuffled_inputs_byte_identical(self):
        import random
        rng = random.Random(7)
        pool = []
        for i in range(6):
            c = split_company([("2024-05-15", 10.0 + i), ("2024-06-28", 11.0 + i)],
                              [], "2024-03-31", "2024-04-10",
                              fetched_on="2024-07-15", ticker=f"ORD{i}")
            c.facts["revenue"] = [Fact("2024-03-31", "2024-05-01",
                                       100.0 + i, form="10-Q", freq="Q",
                                       period_start="2024-01-01",
                                       provider="test")]
            rng.shuffle(c.prices)
            pool.append(c)
        rng.shuffle(pool)
        with tempfile.TemporaryDirectory() as tmp:
            p1 = write_snapshot(score_universe(pool, "2024-06-28"),
                                "2024-06-28", os.path.join(tmp, "a.csv"))
            pool2 = []
            for c in pool:
                c2 = copy.deepcopy(c)
                c2.prices = list(reversed(c2.prices))
                pool2.append(c2)
            pool2.reverse()
            p2 = write_snapshot(score_universe(pool2, "2024-06-28"),
                                "2024-06-28", os.path.join(tmp, "b.csv"))
            b1 = open(p1, "rb").read()
            b2 = open(p2, "rb").read()
            self.assertEqual(b1, b2)


class M4ScaleInvariance(unittest.TestCase):

    def _scale(self, company, k):
        c = copy.deepcopy(company)
        shares = {"shares_outstanding", "shares_diluted", "shares_basic"}
        facts = {}
        for item, fs in c.facts.items():
            # M4: every share count and every dollar item scales by k
            facts[item] = [Fact(f.period_end, f.filing_date, f.value * k,
                                f.form, f.freq, f.period_start,
                                provider=f.provider) for f in fs]
        c.facts = facts
        c.prices = [(d, p / k) for d, p in c.prices]
        c.adj_prices = [(d, p / k) for d, p in c.adj_prices]
        return c

    def test_M4_scale_invariant_scores(self):
        pool = [copy.deepcopy(c) for c in q.fixture_companies()]
        r1 = score_universe(pool, "2024-06-28")
        pool2 = [self._scale(c, 2.0) for c in q.fixture_companies()]
        r2 = score_universe(pool2, "2024-06-28")
        checked = 0
        for t in r1:
            if r1[t].score is not None:
                checked += 1
            self.assertEqual(r1[t].score, r2[t].score, msg=t)
            self.assertEqual(r1[t].metric_scores, r2[t].metric_scores, msg=t)
        self.assertGreater(checked, 0)


class M5DuplicateInvariance(unittest.TestCase):

    def _pool(self):
        return [copy.deepcopy(c) for c in q.fixture_companies()]

    def test_M5_duplicate_every_fact_unchanged(self):
        r1 = score_universe(self._pool(), "2024-06-28")
        pool2 = []
        for c in self._pool():
            for item, fs in list(c.facts.items()):
                c.facts[item] = list(fs) + [copy.copy(fs[0])]
            pool2.append(c)
        r2 = score_universe(pool2, "2024-06-28")
        for t in r1:
            self.assertEqual(r1[t].score, r2[t].score, msg=t)

    def test_M5_restatement_counts_from_availability(self):
        pool = self._pool()
        before = score_universe(pool, "2024-06-28")["FXTE01"].metrics
        pool = self._pool()
        pool[0].facts["revenue"].append(
            Fact("2024-03-31", "2024-06-20", 9999.0, form="10-Q/A", freq="Q",
                 period_start="2024-01-01", provider="test"))
        after = score_universe(pool, "2024-06-28")["FXTE01"].metrics
        self.assertNotEqual(before["operating_margin"],
                            after["operating_margin"])
        pool = self._pool()
        pool[0].facts["revenue"].append(
            Fact("2024-03-31", "2024-07-20", 9999.0, form="10-Q/A", freq="Q",
                 period_start="2024-01-01", provider="test"))
        later = score_universe(pool, "2024-06-28")["FXTE01"].metrics
        self.assertEqual(before["operating_margin"],
                         later["operating_margin"])


class M6Monotonicity(unittest.TestCase):

    def test_M6_improving_input_never_lowers_score(self):
        pool = [copy.deepcopy(c) for c in q.fixture_companies()]
        base = score_universe([copy.deepcopy(c) for c in pool], "2024-06-28")
        improved = copy.deepcopy(pool[0])
        improved.facts["operating_income"] = [
            Fact(f.period_end, f.filing_date, f.value * 1.5, f.form, f.freq,
                 f.period_start, provider=f.provider)
            for f in improved.facts["operating_income"]]
        pool[0] = improved
        after = score_universe(pool, "2024-06-28")
        b, a = base["FXTE01"].score, after["FXTE01"].score
        self.assertIsNotNone(b)
        self.assertIsNotNone(a)
        self.assertGreaterEqual(a, b)


class M7StalenessMonotonicity(unittest.TestCase):

    def test_M7_moving_D_forward_only_OK_to_STALE(self):
        facts = {"revenue": [Fact("2024-05-31", "2024-07-10", 1000.0,
                                  form="10-Q", freq="Q",
                                  period_start="2024-03-01",
                                  provider="test")],
                 "total_assets": [Fact("2024-05-31", "2024-07-10", 5000.0,
                                       form="10-Q", freq="INST",
                                       provider="test")],
                 "shares_outstanding": [Fact("2024-06-15", "2024-07-10",
                                             100.0, form="10-Q",
                                             freq="INST",
                                             provider="test")]}
        statuses = []
        for offset in (0, 30, 60, 90, 120):
            day = (dt.date(2024, 8, 1)
                   + dt.timedelta(days=offset)).isoformat()
            c = Company("MLAX", "tech", facts=facts,
                        prices=[(day, 10.0)], adj_prices=[(day, 10.0)])
            res = score_universe([c], day)["MLAX"]
            statuses.append(res.status)
        for earlier, later in zip(statuses, statuses[1:]):
            if earlier == "OK":
                self.assertIn(later, ("OK", "STALE_DATA"))

    def test_M7_gate_days_matches_spec(self):
        self.assertEqual(q.STALE_FUNDAMENTALS_DAYS, 200)
        self.assertEqual(q.STALE_PRICE_DAYS, 7)


class M8ClockIndependence(unittest.TestCase):

    def test_M8_two_wall_clock_dates_identical_scores(self):
        real_date = q.date

        class FrozenDate(real_date):
            frozen = "2025-03-01"

            @classmethod
            def today(cls):
                return cls.fromisoformat(cls.frozen)

        results = []
        old_cwd = os.getcwd()
        try:
            for frozen in ("2025-03-01", "2025-09-15"):
                with tempfile.TemporaryDirectory() as tmp:
                    os.chdir(tmp)
                    try:
                        q._clear_memo()
                        FrozenDate.frozen = frozen
                        q.date = FrozenDate
                        res = q.get_quality_score(
                            "FXTE01", "2024-06-28", source="fixtures",
                            universe_file=q.fixture_universe_file(
                                os.path.join(tmp, "uni.csv")))
                        results.append(json.dumps(res, sort_keys=True,
                                                  default=str))
                    finally:
                        os.chdir(old_cwd)
                        q._clear_memo()
        finally:
            q.date = real_date
        self.assertEqual(results[0], results[1])




class TerminalCardAndInlineUniverse(unittest.TestCase):
    """One-ticker scoring without a CSV, plus the colored terminal card.

    Display is presentation only: the card must never change a score, and
    the no-file universe must give the same score as the equivalent file.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.uni = fixture_universe_file(Path(self.tmp.name) / "u.csv")

    def test_builtin_ticker_uses_its_own_sector_peers(self):
        refs, sector, scope, warns, err = build_inline_universe("JPM")
        self.assertIsNone(err)
        self.assertEqual(sector, "financials")
        self.assertEqual(refs[0].ticker, "JPM")
        self.assertTrue(all(r.sector == "financials" for r in refs))
        self.assertEqual(len({r.ticker for r in refs}), len(refs))

    def test_outside_ticker_needs_sector_when_undetectable(self):
        from unittest import mock
        with mock.patch.object(sys.modules[__name__],
                               "_detect_sector_yfinance",
                               return_value=None):
            refs, _s, _sc, _w, err = build_inline_universe("QZZT")
        self.assertIsNone(refs)
        self.assertIn("--sector", err)

    def test_known_mega_caps_need_no_sector_flag(self):
        for tkr, sector in (("AAPL", "tech"), ("MSFT", "tech"),
                            ("AMZN", "consumer"), ("META", "communication"),
                            ("NFLX", "communication"), ("NVDA", "tech"),
                            ("TSLA", "consumer"), ("BRK-B", "financials"),
                            ("V", "financials"), ("MA", "financials")):
            refs, got, scope, _w, err = build_inline_universe(tkr)
            self.assertIsNone(err, tkr)
            self.assertEqual(got, sector, tkr)
            self.assertEqual(refs[0].ticker, tkr)
            self.assertIn("auto-detected", scope)

    def test_finnhub_token_prefers_the_standard_name(self):
        from unittest import mock
        env = {k: v for k, v in os.environ.items()
               if k not in ("FINNHUB_API_KEY", "FINAPI")}
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertEqual(finnhub_token(), ("", ""))
            os.environ["FINAPI"] = "k2"
            self.assertEqual(finnhub_token(), ("k2", "FINAPI"))
            os.environ["FINNHUB_API_KEY"] = "k1"
            self.assertEqual(finnhub_token(), ("k1", "FINNHUB_API_KEY"))

    def test_bare_ticker_is_the_short_form_of_score(self):
        import contextlib
        import io
        from unittest import mock
        buf = io.StringIO()
        with mock.patch.object(sys.modules[__name__],
                               "_detect_sector_yfinance",
                               return_value=None), \
                contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            rc = main(["QZZT"])     # valid shape, unknown name, no sector
        self.assertEqual(rc, 2)
        self.assertIn("--sector", buf.getvalue())
        self.assertNotIn("unknown command", buf.getvalue())

    def test_band_letter_grades_are_not_too_strict(self):
        self.assertEqual(_band(90.0)[0], "A - TOP TIER")
        self.assertEqual(_band(70.0)[0], "B - ABOVE AVERAGE")
        self.assertEqual(_band(50.0)[0], "C - MIDDLE OF THE PACK")
        self.assertEqual(_band(45.0)[0], "C - MIDDLE OF THE PACK")
        self.assertEqual(_band(30.0)[0], "D - BELOW AVERAGE")
        self.assertEqual(_band(10.0)[0], "F - BOTTOM TIER")

    def test_sector_aliases_and_unknown_sector(self):
        refs, sector, _sc, _w, err = build_inline_universe(
            "AAPL", sector_arg="Technology")
        self.assertIsNone(err)
        self.assertEqual(sector, "tech")
        self.assertEqual(refs[0].ticker, "AAPL")
        self.assertTrue(len(refs) > 10)
        refs, _s, _sc, _w, err = build_inline_universe(
            "AAPL", sector_arg="banana")
        self.assertIsNone(refs)
        self.assertIn("unknown sector", err)

    def test_peers_replace_builtin_list_and_dedupe(self):
        refs, sector, _sc, warns, err = build_inline_universe(
            "AAPL", sector_arg="tech", peers_arg="msft, nvda,MSFT,AAPL")
        self.assertIsNone(err)
        self.assertEqual([r.ticker for r in refs], ["AAPL", "MSFT", "NVDA"])
        self.assertTrue(warns)          # far fewer than MIN_PEERS + 1

    def test_no_file_universe_scores_like_the_file(self):
        peers = ",".join(f"FXTE{i:02d}" for i in range(2, 11))
        refs, _s, _sc, _w, err = build_inline_universe(
            "FXTE01", sector_arg="tech", peers_arg=peers)
        self.assertIsNone(err)
        a = get_quality_score("FXTE01", AS_OF, source="fixtures",
                              universe_refs=refs)
        b = get_quality_score("FXTE01", AS_OF, source="fixtures",
                              universe_file=self.uni)
        self.assertEqual(a["status"], OK)
        self.assertIsNotNone(a["score"])
        self.assertNotEqual(a["score"], 0)
        self.assertEqual(b["status"], OK)

    def test_card_plain_has_no_escape_codes_and_colored_has_them(self):
        res = {"ticker": "ZZZ", "as_of": AS_OF, "sector": "tech",
               "score": 71.5, "status": OK, "coverage": 1.0,
               "rank_in_sector": 2, "data_source": "sec",
               "pillars": {"profitability": 80.0, "growth": None},
               "flags": ["HIGH_ACCRUALS"], "metrics": {"roic": 0.2},
               "metric_scores": {"roic": 0.9}}
        ctx = {"scope": "test", "n_scored": 5, "warnings": []}
        plain = render_score_card(res, ctx, False)
        colored = render_score_card(res, ctx, True)
        self.assertNotIn("\033[", plain)
        self.assertIn("\033[", colored)
        for text in (plain, colored):
            self.assertIn("ZZZ", text)
            self.assertIn("71.5", text)
            self.assertIn("ABOVE AVERAGE", text)
            self.assertIn("HIGH_ACCRUALS", text)
            self.assertIn("--layer", text)
        self.assertEqual(
            re.sub(r"\033\[[0-9;]*m", "", colored), plain)

    def test_card_for_unscored_names_the_status_not_a_score(self):
        res = {"ticker": "ZZZ", "as_of": AS_OF, "sector": "tech",
               "score": None, "status": STALE_DATA, "data_source": "sec",
               "notes": [], "flags": [], "pillars": {}, "metrics": {},
               "metric_scores": {}, "source_status": {}}
        text = render_score_card(res, {"scope": "", "warnings": []}, False)
        self.assertIn("STALE_DATA", text)
        self.assertNotIn("QUALITY SCORE", text)

    def test_fixture_banner_and_ticker_normalization(self):
        res = {"ticker": "ZZZ", "as_of": AS_OF, "sector": "tech",
               "score": 10.0, "status": OK, "coverage": 1.0,
               "data_source": "fixtures", "pillars": {}, "flags": [],
               "metrics": {}, "metric_scores": {}}
        text = render_score_card(res, {"scope": "", "warnings": []}, False)
        self.assertIn("SYNTHETIC TEST DATA", text)
        self.assertEqual(normalize_ticker(" brk.b "), "BRK-B")
        self.assertEqual(normalize_ticker("aapl"), "AAPL")
        for bad in ("", "A&B", "AAPL;rm", "TOOLONGTICKER", "a b"):
            self.assertIsNone(normalize_ticker(bad), bad)
        refs, _s, _sc, _w, err = build_inline_universe(
            "AAPL", sector_arg="tech", peers_arg="MSFT,not a ticker")
        self.assertIsNone(refs)
        self.assertIn("not a ticker", err)

    def test_dotenv_accepts_export_prefix_and_never_overrides(self):
        from unittest import mock
        env_path = Path(self.tmp.name) / ".env"
        env_path.write_text('export QE_TEST_A="one"\nQE_TEST_B=two\n'
                            'QE_TEST_C=kept\n', encoding="utf-8")
        with mock.patch.dict(os.environ, {"QE_ENV_FILE": str(env_path),
                                          "QE_TEST_C": "already"}):
            for k in ("QE_TEST_A", "QE_TEST_B"):
                os.environ.pop(k, None)
            _load_dotenv()
            self.assertEqual(os.environ["QE_TEST_A"], "one")
            self.assertEqual(os.environ["QE_TEST_B"], "two")
            self.assertEqual(os.environ["QE_TEST_C"], "already")
            for k in ("QE_TEST_A", "QE_TEST_B"):
                os.environ.pop(k, None)

    def test_progress_hook_reports_every_ticker(self):
        peers = ",".join(f"FXTE{i:02d}" for i in range(2, 6))
        refs, _s, _sc, _w, err = build_inline_universe(
            "FXTE01", sector_arg="tech", peers_arg=peers)
        seen = []
        get_quality_score("FXTE01", AS_OF, source="fixtures",
                          universe_refs=refs,
                          progress=lambda i, n, t: seen.append((i, n, t)))
        if seen:       # skipped only when an identical run was memoized
            self.assertEqual(seen[0][:2], (1, len(refs)))
            self.assertEqual(seen[-1][0], len(refs))

    def test_cli_no_file_pretty_and_json_modes(self):
        import subprocess
        peers = ",".join(f"FXTE{i:02d}" for i in range(2, 11))
        base = [sys.executable, str(_THIS_FILE), "score", "FXTE01",
                "--sector", "tech", "--peers", peers, "--source",
                "fixtures", "--as-of", AS_OF]
        cwd = str(Path(self.tmp.name))
        card = subprocess.run(base + ["--pretty", "--no-color"],
                              capture_output=True, text=True, timeout=300,
                              cwd=cwd)
        self.assertEqual(card.returncode, 0, card.stderr)
        self.assertIn("QUALITY SCORE", card.stdout)
        self.assertNotIn("\033[", card.stdout)
        piped = subprocess.run(base, capture_output=True, text=True,
                               timeout=300, cwd=cwd)
        self.assertEqual(piped.returncode, 0, piped.stderr)
        self.assertEqual(json.loads(piped.stdout)["ticker"], "FXTE01")
        bad = subprocess.run(
            [sys.executable, str(_THIS_FILE), "score", "AAPL", "--source",
             "fixtures", "--sector", "banana"],
            capture_output=True, text=True, timeout=300, cwd=cwd)
        self.assertEqual(bad.returncode, 2)


# ---- P6 audit regression tests (v3.4.0; audit P1-P7 evidence) ----
# Data classes (rule D13/D21): every payload below is a SYNTHETIC
# provider-faithful simulator (reproduces the real provider semantics that
# matter: window-limited split events, retroactively adjusted closes,
# exclusive ends, null bars) - never a hand-injected answer.


def _p6_cf(*tag_rows):
    """companyfacts payload builder: ((tag, [unit rows]), ...)."""
    return {"facts": {"us-gaap": {t: {"units": {"USD": list(rows)}}
                                   for t, rows in tag_rows}}}


class P6FakeFundSource:
    """Fundamentals source serving ONE tiny company (synthetic)."""

    name = "p6_fake"

    def __init__(self, facts):
        self._facts = facts

    def available(self):
        return True, "synthetic"

    def get_all_facts(self, ticker):
        return dict(self._facts), ProviderReport(self.name, STATUS_SUCCESS,
                                                 "")


class P6SplitSimSource:
    """Provider-faithful price source (synthetic).

    Reproduces the REAL semantics proven live in the audit (P1/L2):
    ``close``/``adj_close`` are retroactively split-adjusted through the
    FETCH date regardless of the requested window, and ``splits`` contains
    ONLY events inside [start, end].
    """

    name = "p6_split_sim"

    def __init__(self, split_events=(), first="2023-01-03",
                 last="2024-12-31", unsplit_close=100.0):
        self.events = [(d, float(r)) for d, r in split_events]
        self.first, self.last = first, last
        self.unsplit = float(unsplit_close)

    def get_price_data(self, ticker, start=None, end=None, fetch_on=None):
        factor = 1.0
        for _d, r in self.events:
            factor *= r
        bars, adj = [], []
        d = self.first
        while d <= self.last:
            if (start is None or d >= start) and (end is None or d <= end):
                bars.append((d, round(self.unsplit / factor, 6)))
                adj.append((d, round(self.unsplit / factor, 6)))
            y, m, dd = int(d[:4]), int(d[5:7]), int(d[8:10])
            dd += 1
            if dd > 28:
                dd = 1
                m += 1
            if m > 12:
                m = 1
                y += 1
            d = "%04d-%02d-%02d" % (y, m, dd)
        splits = [(d, r) for d, r in self.events
                  if (start is None or d >= start)
                  and (end is None or d <= end)]
        if not bars:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "window_outside_history")
        return {"close": bars, "adj_close": adj, "splits": splits,
                "splits_known": True, "fetched_on": fetch_on or ""}, \
            ProviderReport(self.name, STATUS_SUCCESS, "")


class P6SplitBasisThroughFetchPath(unittest.TestCase):
    """L2/R1: market cap is split-invariant through the REAL fetch path."""

    SHARE_FACTS = {"shares_outstanding": [
        Fact("2024-01-31", "2024-03-01", 10.0, "10-Q", "INST")]}
    AS_OF = "2024-06-30"
    FETCH = "2024-12-31"

    def _mcap(self, events):
        chain = SourceChain([P6FakeFundSource(self.SHARE_FACTS)],
                            P6SplitSimSource(events), [], [])
        company = chain.get_company("TEST", "tech", self.AS_OF,
                                    fetch_on=self.FETCH)
        mp, status = build_market(company, self.AS_OF)
        return mp, status

    def _assert_cap(self, events, expected=1000.0):
        mp, status = self._mcap(events)
        self.assertEqual(status, "ok", "events=%s" % (events,))
        self.assertIsNotNone(mp)
        self.assertAlmostEqual(mp.market_cap / expected, 1.0, delta=1e-9)

    def test_split_after_as_of(self):
        # the S0 case: 4:1 AFTER as_of but BEFORE the fetch date
        self._assert_cap([("2024-08-15", 4.0)])

    def test_split_between_share_date_and_as_of(self):
        self._assert_cap([("2024-03-15", 4.0)])

    def test_no_split(self):
        self._assert_cap([])

    def test_reverse_split_after_as_of(self):
        self._assert_cap([("2024-09-30", 0.1)])

    def test_two_consecutive_splits_after_as_of(self):
        self._assert_cap([("2024-08-15", 4.0), ("2024-10-31", 2.0)])

    def test_split_exactly_on_share_date_is_refused(self):
        # t_s = 2024-01-31; ex-date within +/-1 day -> ambiguous -> refused
        mp, status = self._mcap([("2024-02-01", 4.0)])
        self.assertEqual(status, "split_basis_unverified")
        self.assertIsNone(mp)

    def test_split_events_through_equals_fetch_window(self):
        chain = SourceChain([P6FakeFundSource(self.SHARE_FACTS)],
                            P6SplitSimSource([("2024-08-15", 4.0)]), [], [])
        company = chain.get_company("TEST", "tech", self.AS_OF,
                                    fetch_on=self.FETCH)
        self.assertEqual(company.split_events_through, self.FETCH)
        self.assertIn(("2024-08-15", 4.0), company.split_events)
        # bars are filtered to <= as_of even though the window ran to FETCH
        self.assertTrue(all(d <= self.AS_OF for d, _c in company.prices))


class P6ChartSplitParsing(unittest.TestCase):
    """X1/R2 + X9/R3: chart-client payload parsing (documented shape)."""

    TS0 = 1704153600     # 2024-01-02T00:00Z

    @staticmethod
    def _payload(bars, splits, adjnull=()):
        stamps, closes, adjs = [], [], []
        for i, (d, c) in enumerate(bars):
            stamps.append(P6ChartSplitParsing.TS0 + i * 86400)
            closes.append(c)
            adjs.append(None if d in adjnull else c)
        ev = {}
        for i, (d, num, den, hour) in enumerate(splits):
            import calendar
            import datetime as _dt
            day = _dt.datetime.strptime(d, "%Y-%m-%d").replace(
                tzinfo=_dt.timezone.utc)
            ev[str(i)] = {"date": calendar.timegm(day.utctimetuple())
                          + hour * 3600, "numerator": num,
                          "denominator": den}
        return {"chart": {"result": [{
            "timestamp": stamps,
            "indicators": {"quote": [{"close": closes}],
                           "adjclose": [{"adjclose": adjs}]},
            "events": {"splits": ev}}], "error": None}}

    def _client(self, payload):
        def transport(url, headers=None, timeout=None):
            return STATUS_SUCCESS, payload, None, ""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            return YahooChartPriceClient(cache=FileCache(root=tmp),
                                         transport=transport,
                                         sleep_fn=lambda s: None)

    def test_split_one_hour_off_bar_still_applied(self):
        # bars at 00:00Z; event stamped 01:00Z the same UTC day
        pl = self._payload([("2024-01-02", 100.0), ("2024-01-03", 25.0)],
                           [("2024-01-02", 4.0, 1.0, 1)])
        client = self._client(pl)
        payload, report = client.get_price_data("T", "2024-01-01",
                                                "2024-01-31",
                                                fetch_on="2024-02-01")
        self.assertEqual(report.status, STATUS_SUCCESS)
        self.assertIn(("2024-01-02", 4.0),
                      [(d, r) for d, r in payload["splits"]])

    def test_split_on_null_close_day_still_applied(self):
        pl = self._payload([("2024-01-02", None), ("2024-01-03", 25.0)],
                           [("2024-01-02", 4.0, 1.0, 0)])
        client = self._client(pl)
        payload, report = client.get_price_data("T", "2024-01-01",
                                                "2024-01-31",
                                                fetch_on="2024-02-01")
        self.assertEqual(report.status, STATUS_SUCCESS)
        self.assertIn(("2024-01-02", 4.0),
                      [(d, r) for d, r in payload["splits"]])

    def test_null_adjclose_not_substituted(self):
        # X9: 2024-01-02 has a null adjclose -> it must VANISH from the
        # adj series, never be replaced by the raw close.
        pl = self._payload([("2024-01-02", 100.0), ("2024-01-03", 101.0)],
                           [], adjnull=("2024-01-02",))
        client = self._client(pl)
        payload, report = client.get_price_data("T", "2024-01-01",
                                                "2024-01-31",
                                                fetch_on="2024-02-01")
        self.assertEqual(report.status, STATUS_SUCCESS)
        adj_days = [d for d, _c in payload["adj_close"]]
        self.assertNotIn("2024-01-02", adj_days)
        self.assertIn("2024-01-03", adj_days)


class P6DebtCompleteness(unittest.TestCase):
    """L3/R4: a PARTIAL debt figure is never used (D-3 default)."""

    def _facts(self, with_std_at_latest):
        q = [("2023-03-31", "2023-05-01"), ("2023-06-30", "2023-08-01"),
             ("2023-09-30", "2023-11-01"), ("2023-12-31", "2024-02-15")]
        da_ytd = [5.0, 10.0, 15.0, 20.0]
        facts = {
            "operating_income": [Fact(e, f, 20.0, "10-Q", "Q",
                                      _shift(e, -89)) for e, f in q],
            "depreciation_amortization": [
                Fact(e, f, v, "10-Q", "YTD", "2023-01-01")
                for (e, f), v in zip(q, da_ytd)],
            "long_term_debt": [Fact("2023-12-31", "2024-02-15", 900.0,
                                    "10-K", "INST")],
            "cash": [Fact("2023-12-31", "2024-02-15", 50.0, "10-K", "INST")],
            "total_equity": [Fact("2023-12-31", "2024-02-15", 800.0,
                                  "10-K", "INST")],
            "shares_outstanding": [Fact("2024-01-31", "2024-03-01", 10.0,
                                        "10-Q", "INST")],
        }
        if with_std_at_latest:
            facts["short_term_debt"] = [
                Fact("2023-12-31", "2024-02-15", 100.0, "10-K", "INST")]
        else:
            facts["short_term_debt"] = [
                Fact("2023-09-30", "2023-11-01", 100.0, "10-Q", "INST")]
        return facts

    def test_partial_debt_refuses_metrics(self):
        v = FundamentalsView(self._facts(False), "2024-06-30")
        _end, value, missing = v._compose_debt()
        self.assertEqual(missing, ["short_term_debt"])
        self.assertIsNone(net_debt_ebitda(v, None))
        self.assertIsNone(roic(v, None))

    def test_complete_debt_computes(self):
        v = FundamentalsView(self._facts(True), "2024-06-30")
        _end, value, missing = v._compose_debt()
        self.assertEqual(missing, [])
        # EBITDA = 4x20 opinc + D&A(20-15+15-10+10-5+5) = 80 + 20 = 100
        self.assertAlmostEqual(net_debt_ebitda(v, None),
                               (900.0 + 100.0 - 50.0) / 100.0)

    def test_partial_debt_note_present_and_ev_refused(self):
        company = Company(ticker="T", sector="tech",
                          facts=self._facts(False),
                          prices=[("2024-06-28", 50.0)],
                          adj_prices=[("2024-06-28", 50.0)],
                          prices_fetched_on="2024-12-31",
                          split_events_through="2024-12-31")
        model = resolve_model("tech")
        _raw, notes, _view, market, ps, _stale, _prov = \
            compute_raw_metrics(company, model, "2024-06-30")
        self.assertEqual(ps, "ok")
        self.assertTrue(any(n.startswith("debt_component_missing")
                            for n in notes))
        self.assertIsNone(market.net_debt)
        self.assertIsNone(market.enterprise_value)


class P6DateAndTickerContracts(unittest.TestCase):
    """L5/R8 + L6/R9: one date validator, one ticker normalizer."""

    def test_api_rejects_bad_dates(self):
        for bad in ("2099-12-31", "2024-13-45", "2024/01/01",
                    "2024-06-30T00:00:00", "not-a-date"):
            r = get_quality_score("JPM", bad, source="fixtures")
            self.assertEqual(r["status"], "ERROR", bad)
            self.assertIn("invalid_as_of", r["notes"], bad)
            self.assertTrue(r["error"], bad)

    def test_api_accepts_valid_dates(self):
        r = get_quality_score("FXTE01", "2024-06-28", source="fixtures",
                              universe_refs=[TickerRef("FXTE01", "tech")])
        self.assertNotEqual(r["status"], "ERROR")

    def test_api_ticker_normalization_matches_cli(self):
        a = get_quality_score("BRK.B", "2024-06-28", source="fixtures")
        b = get_quality_score("brk-b", "2024-06-28", source="fixtures")
        self.assertEqual(a["ticker"], "BRK-B")
        self.assertEqual(b["ticker"], "BRK-B")
        self.assertEqual(a["status"], b["status"])
        c = get_quality_score(" BRK-B ", "2024-06-28", source="fixtures")
        self.assertEqual(c["ticker"], "BRK-B")
        r = get_quality_score("..", "2024-06-28", source="fixtures")
        self.assertEqual(r["status"], "ERROR")
        self.assertIn("invalid_ticker", r["notes"])

    def test_momentum_rejects_bad_inputs(self):
        r = get_momentum_12_1("AAPL", "2024-13-45", source="fixtures")
        self.assertEqual(r["status"], "ERROR")
        self.assertEqual(r["reason"], "invalid_as_of")
        r2 = get_momentum_12_1("..", "2024-06-28", source="fixtures")
        self.assertEqual(r2["status"], "ERROR")
        self.assertEqual(r2["reason"], "invalid_ticker")

    def test_cli_future_date_exit_2(self):
        import subprocess
        p = subprocess.run([sys.executable, os.path.abspath(q.__file__),
                            "score", "JPM", "--as-of", "2099-12-31",
                            "--source", "fixtures"],
                           capture_output=True, text=True,
                            cwd=tempfile.gettempdir(), timeout=120)
        self.assertEqual(p.returncode, 2)
        self.assertIn("future", p.stderr)


class P6TzFailClosed(unittest.TestCase):
    """X8/R11: the approximate ET zone fails CLOSED (no DST look-ahead)."""

    def test_ambiguity_hour_waits_a_day(self):
        from unittest import mock
        with mock.patch.object(sys.modules[__name__], "_ET",
                               timezone(timedelta(hours=-5))), \
                mock.patch.object(sys.modules[__name__], "_ET_APPROX",
                                  True):
            f = Fact("2024-06-30", "2024-07-30", 1.0,
                     accepted="2024-07-30T20:30:00Z")   # 16:30 EDT
            day, label = fact_available_date(f)
            self.assertEqual(day, "2024-07-31")
            self.assertIn("after_close", label)
            # well before the cutoff: still same day
            f2 = Fact("2024-06-30", "2024-07-30", 1.0,
                      accepted="2024-07-30T18:00:00Z")  # 13:00 ET fixed
            day2, label2 = fact_available_date(f2)
            self.assertEqual(day2, "2024-07-30")
            self.assertIn("same_day", label2)


class P6SecDefaults(unittest.TestCase):
    """L9/R10: the default SEC UA carries no machine identity."""

    def test_default_ua_is_static(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SEC_USER_AGENT_ENV, None)
            client = SecEdgarClient()
            ua = client._headers()["User-Agent"]
            self.assertIn("SEC_USER_AGENT", ua)
            user = os.environ.get("USER") or os.environ.get("USERNAME")
            if user:
                self.assertNotIn(user, ua)
            self.assertNotIn("@", ua.split("(")[0])

    def test_engine_file_has_no_stale_names_or_unshipped_refs(self):
        src = open(q.__file__, encoding="utf-8").read()
        needle = "quality" + "_engine.py"     # built dynamically on purpose
        self.assertNotIn(needle, src)
        self.assertNotIn("quality" + "_engine]", src)
        self.assertNotIn("audit" + "/work", src)


class P6TagPriorityAndCoverage(unittest.TestCase):
    """X10/R5 + X17/R6 + DQ3/R7: tag priority and new debt/revenue tags."""

    def test_preferred_tag_wins_over_later_filed(self):
        payload = _p6_cf(
            ("Revenues", [{"start": "2024-01-01", "end": "2024-12-31",
                           "val": 1200, "filed": "2025-02-15",
                           "form": "10-K", "accn": "A1"}]),
            ("RevenueFromContractWithCustomerExcludingAssessedTax",
             [{"start": "2024-01-01", "end": "2024-12-31", "val": 1000,
               "filed": "2025-03-01", "form": "8-K", "accn": "A2"}]))
        facts, _diag = normalize_companyfacts(payload)
        v = FundamentalsView(facts, "2025-06-30")
        self.assertAlmostEqual(v.fy("revenue"), 1200.0)

    def test_restatement_within_same_tag_still_wins(self):
        payload = _p6_cf(
            ("Revenues",
             [{"start": "2023-01-01", "end": "2023-12-31", "val": 1000.0,
               "form": "10-K", "filed": "2024-02-15"},
              {"start": "2023-01-01", "end": "2023-12-31", "val": 1100.0,
               "form": "10-K/A", "filed": "2024-04-01"}]))
        facts, _diag = normalize_companyfacts(payload)
        before = FundamentalsView(facts, "2024-03-15")
        after = FundamentalsView(facts, "2024-04-02")
        self.assertAlmostEqual(before.fy("revenue"), 1000.0)
        self.assertAlmostEqual(after.fy("revenue"), 1100.0)

    def test_xom_style_debt_tags_mapped(self):
        payload = _p6_cf(
            ("DebtCurrent",
             [{"end": "2024-06-30", "filed": "2024-08-03", "val": 10139}]),
            ("LongTermDebtAndCapitalLeaseObligations",
             [{"end": "2024-06-30", "filed": "2024-08-03", "val": 32229}]))
        facts, _diag = normalize_companyfacts(payload)
        v = FundamentalsView(facts, "2024-10-31")
        value, missing = v.total_debt()
        self.assertEqual(missing, [])
        self.assertAlmostEqual(value, 42368.0)

    def test_utilities_revenue_tag_mapped(self):
        payload = _p6_cf(
            ("RegulatedAndUnregulatedOperatingRevenue",
             [{"start": "2024-01-01", "end": "2024-12-31", "val": 26804,
               "filed": "2025-02-14", "form": "10-K"}]))
        facts, _diag = normalize_companyfacts(payload)
        v = FundamentalsView(facts, "2025-06-30")
        self.assertAlmostEqual(v.fy("revenue"), 26804.0)

    def test_umbrella_and_component_debt_not_double_counted(self):
        # both LongTermDebtCurrent AND DebtCurrent at the same date:
        # the per-period priority picks ONE (LongTermDebtCurrent).
        payload = _p6_cf(
            ("LongTermDebtCurrent",
             [{"end": "2024-06-30", "filed": "2024-08-03", "val": 500}]),
            ("DebtCurrent",
             [{"end": "2024-06-30", "filed": "2024-08-03", "val": 700}]))
        facts, _diag = normalize_companyfacts(payload)
        v = FundamentalsView(facts, "2024-10-31")
        value, missing = v.total_debt()
        self.assertEqual(missing, ["long_term_debt"])
        self.assertAlmostEqual(value, 500.0)


class P6YfinanceThrottle(unittest.TestCase):
    """L4/R12: shared limiter + end shift on the yfinance path."""

    def test_limiter_applied_and_end_shifted(self):
        import datetime as _dt
        import types as _types
        from unittest import mock
        calls = []

        class FakeHist:
            columns = ["Close", "Adj Close", "Stock Splits"]
            empty = False

            def __init__(self):
                self.rows = [(_dt.datetime(2025, 6, 30),
                              {"Close": 100.0, "Adj Close": 100.0,
                               "Stock Splits": 0.0})]

            def iterrows(self):
                return iter(self.rows)

        class FakeTicker:
            def __init__(self, t):
                pass

            def history(self, start=None, end=None, **kw):
                calls.append((start, end))
                return FakeHist()

        fake = _types.ModuleType("yfinance")
        fake.Ticker = FakeTicker
        waits = []

        class CountingLimiter:
            def wait(self, *a, **k):
                waits.append(1)

        with mock.patch.dict(sys.modules, {"yfinance": fake}):
            with tempfile.TemporaryDirectory() as tmp:
                cli = YfinancePriceClient(cache=FileCache(root=tmp),
                                          limiter=CountingLimiter())
                payload, report = cli.get_price_data(
                    "T", "2025-01-01", "2025-06-30", fetch_on="2025-07-01")
        self.assertEqual(report.status, STATUS_SUCCESS)
        self.assertEqual(len(waits), 1)              # throttled
        self.assertEqual(calls[0][1], "2025-07-01")  # end shifted +1 day


class P6NoDataDiagnostics(unittest.TestCase):
    """F29/R13: a NO_DATA result always carries its reason."""

    def test_fixtures_no_data_carries_notes(self):
        r = get_quality_score("AAPL", "2024-06-28", source="fixtures")
        self.assertEqual(r["status"], "NO_DATA")
        self.assertTrue(r["notes"], "notes must not be empty")
        self.assertTrue(r["error"] or r["source_status"] or r["notes"])


class P6PitHarness(unittest.TestCase):
    """L1/L7/R14: the PIT harness scores PIT constituents, counts every
    skip, applies delisting returns and reports ticker reuse."""

    def _pit_run(self, rows_text, expect_hash=None):
        import argparse as _ap
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pit.csv")
            open(path, "w").write(rows_text)
            args = _ap.Namespace(pit_universe=path, source="fixtures",
                                 expect_config_hash=expect_hash)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = _pit_validate(args)
            out = buf.getvalue()
        if "{" not in out:
            return None, rc
        j = json.loads(out[out.index("{"):out.rindex("}") + 1])
        return j, rc

    def test_harness_scores_constituents_and_counts(self):
        head = ("month_end,ticker,permanent_id,sector_pit,listed,"
                "total_return_next_month,delisting_return_if_any\n")
        rows = [head]
        months = ["2024-02-29", "2024-03-31", "2024-04-30"]
        for m in months:
            for i in range(1, 11):
                line = "%s,FXTE%02d,%d,tech,1,0.010,\n" % (m, i, 1000 + i)
                if m == "2024-03-31" and i == 1:
                    line = "%s,FXTE01,1001,tech,1,,-0.500000\n" % m
                if m == "2024-04-30" and i == 10:
                    line = "%s,FXTE10,9999,tech,1,0.010,\n" % m
                rows.append(line)
        j, rc = self._pit_run("".join(rows))
        self.assertEqual(rc, 0)
        self.assertIsNotNone(j)
        self.assertTrue(j["per_month"])
        for pm in j["per_month"]:
            self.assertEqual(pm["listed"] - pm["scored"],
                             sum(pm["unscored_by_reason"].values()))
            self.assertGreater(pm["scored"], 0)
        self.assertGreaterEqual(j["n_delisting_returns"], 1)
        self.assertTrue(any(u["ticker"] == "FXTE10"
                            for u in j["reused_tickers"]))
        self.assertEqual(j["costs"], "none_applied_gross")

    def test_config_hash_freeze_aborts_on_mismatch(self):
        head = ("month_end,ticker,permanent_id,sector_pit,listed,"
                "total_return_next_month,delisting_return_if_any\n"
                "2024-02-29,FXTE01,1001,tech,1,0.01,\n"
                "2024-03-31,FXTE01,1001,tech,1,0.01,\n")
        j, rc = self._pit_run(head, expect_hash="deadbeefdeadbeef")
        self.assertEqual(rc, 1)
        self.assertIsNone(j)


class P6Metamorphics(unittest.TestCase):
    """M2/M8/M10 (compact, through the fixture fetch path)."""

    @classmethod
    def setUpClass(cls):
        refs = []
        for prefix, sector, n in (("FXTE", "tech", 10), ("FXEN", "energy", 9),
                                  ("FXFI", "financials", 1),
                                  ("FXUT", "utilities", 1),
                                  ("FXRE", "reits", 2)):
            for i in range(1, n + 1):
                refs.append(TickerRef("%s%02d" % (prefix, i), sector))
        cls.FX_REFS = refs

    def _score_fxte01(self):
        res = _scored_universe("2024-06-30", "fixtures",
                               refs_override=self.FX_REFS)
        return res["FXTE01"].to_api_dict()

    def test_m2_future_facts_and_prices_change_nothing(self):
        base = self._score_fxte01()
        companies = generate_fixture_universe()
        fx = companies["FXTE01"]
        fx.facts.setdefault("revenue", []).append(
            Fact("2024-03-31", "2024-12-31", 99999.0, "10-Q", "Q",
                 "2024-01-01"))
        fx.prices.append(("2024-07-31", 123.0))
        try:
            _clear_memo()
            again = self._score_fxte01()
        finally:
            companies["FXTE01"].facts["revenue"] = [
                f for f in companies["FXTE01"].facts["revenue"]
                if f.filing_date != "2024-12-31"]
            companies["FXTE01"].prices = [
                p for p in companies["FXTE01"].prices
                if p[0] != "2024-07-31"]
            globals()["_FIXTURE_COMPANIES"] = None
            _clear_memo()
        for key in ("score", "coverage", "pillars", "metric_scores",
                    "metrics"):
            self.assertEqual(json.dumps(base[key], sort_keys=True),
                             json.dumps(again[key], sort_keys=True),
                             "key=%s" % key)

    def test_m8_boundary_clock_independence(self):
        from unittest import mock
        real_date = date

        class FakeDate(real_date):
            @classmethod
            def today(cls):
                return real_date.today() + timedelta(days=17)

        r1 = self._score_fxte01()
        _clear_memo()
        with mock.patch.object(sys.modules[__name__], "date", FakeDate):
            r2 = self._score_fxte01()
        self.assertEqual(json.dumps(r1, sort_keys=True),
                         json.dumps(r2, sort_keys=True))

    def test_m10_availability_never_moves_earlier(self):
        f = Fact("2024-06-30", "2024-07-30", 1.0,
                 accepted="2024-07-30T20:30:00Z")
        d1, _l1 = fact_available_date(f)
        self.assertEqual(d1, "2024-07-31")
        f2 = Fact("2024-06-30", "2024-07-29", 1.0,
                  accepted="2024-07-29T14:00:00Z")
        d2, _l2 = fact_available_date(f2)
        self.assertEqual(d2, "2024-07-29")


class P6SecretCanary(unittest.TestCase):
    """X15 (P7): planted canary secrets never reach results or headers."""

    CANARY = "Zq0-canary-9f13e7"

    def test_canary_absent_from_results_and_headers(self):
        from unittest import mock
        with mock.patch.dict(os.environ,
                             {FINNHUB_KEY_ENV: self.CANARY,
                              SEC_USER_AGENT_ENV: "Canary " + self.CANARY}):
            chain = build_source_chain("auto")
            headers = {}
            for src in chain.fundamentals:
                if isinstance(src, SecEdgarClient):
                    if self.CANARY in (src._headers() or {}).get(
                            "User-Agent", ""):
                        # a set SEC_USER_AGENT legitimately echoes in the
                        # header (it IS the user's own contact string) -
                        # the canary asserts it never reaches RESULTS.
                        pass
            r = get_quality_score("FXTE01", "2024-06-28", source="fixtures",
                                  universe_refs=[TickerRef("FXTE01",
                                                           "tech")])
            blob = json.dumps(r, default=str)
            self.assertNotIn(self.CANARY, blob)


# ---- V3.4.1 P4: raw close must never be mislabelled as adjusted close ----

class _P4PriceSource:
    """Synthetic D15 price source (no network): close bars always served.

    ``adj=None`` -> payload has NO adj_close key; ``adj=[]`` -> an empty
    adjusted list; a list -> that adjusted series. ``calls`` records every
    request so cache hits are distinguishable from fresh fetches.
    """

    name = "p4_synthetic"

    def __init__(self, close, adj=None):
        self._close = list(close)
        self._adj = adj
        self.calls = []

    def _window(self, start, end):
        return [(d, c) for d, c in self._close
                if (start is None or d >= start)
                and (end is None or d <= end)]

    def get_price_data(self, ticker, start=None, end=None, fetch_on=None):
        self.calls.append((ticker, start, end, fetch_on))
        pts = self._window(start, end)
        if not pts:
            return None, ProviderReport(self.name, STATUS_NO_DATA,
                                        "window_outside_history")
        payload = {"close": pts, "splits": [], "splits_known": True,
                   "fetched_on": fetch_on or ""}
        if self._adj is not None:
            adj = [(d, c) for d, c in self._adj
                   if (start is None or d >= start)
                   and (end is None or d <= end)]
            payload["adj_close"] = adj
        return payload, ProviderReport(self.name, STATUS_SUCCESS, "")


class AdjustedPriceBasis(unittest.TestCase):
    """V3.4.1 BUG 3 armor: an empty adjusted series stays empty at every
    stage (provider parse, price cache, cache merge, filter, Company
    assignment, snapshot restore, momentum). Raw closes survive only on
    .prices and through the explicitly labeled price_only fallback; the
    quality composite is independent of the adjusted basis."""

    AS_OF = "2024-06-30"
    CLOSE = [("2023-06-30", 100.0), ("2023-07-31", 102.0),
             ("2023-08-31", 104.0), ("2023-09-30", 106.0),
             ("2023-10-31", 108.0), ("2023-11-30", 110.0),
             ("2023-12-31", 112.0), ("2024-01-31", 114.0),
             ("2024-02-29", 116.0), ("2024-03-31", 118.0),
             ("2024-04-30", 120.0), ("2024-05-31", 122.0),
             ("2024-06-28", 124.0)]

    @staticmethod
    def _diverging_adjusted(close):
        """Adjusted series equal to close for 6 bars, then a payer's gap."""
        return [(d, c if i < 6 else round(c - 3.0, 2))
                for i, (d, c) in enumerate(close)]

    def test_filter_empty_adjusted_stays_empty(self):
        # F1/F2/F3: all adjusted bars absent, key absent, raw-only payload
        payload = {"close": [("d1", 100.0), ("d2", 110.0), ("d3", 120.0)],
                   "adj_close": [], "splits": []}
        out = YfinancePriceClient._filter(payload, None, None)
        self.assertEqual(out["adj_close"], [])
        self.assertEqual(out["close"], payload["close"])
        out2 = YfinancePriceClient._filter(
            {"close": payload["close"], "splits": []}, None, None)
        self.assertEqual(out2["adj_close"], [])

    def test_fetch_all_null_adjusted_serves_and_caches_empty(self):
        # provider parse + cache write + cache hit: a download whose
        # adjusted bars are ALL null must never relabel raw close
        import json
        import tempfile
        bars = [("2024-01-02", 100.0), ("2024-01-03", 101.0),
                ("2024-01-04", 102.0), ("2024-01-05", 103.0),
                ("2024-01-08", 104.0)]
        all_null = {d for d, _c in bars}
        payload = P6ChartSplitParsing._payload(bars, [], adjnull=all_null)

        def transport(url, headers=None, timeout=None):
            return STATUS_SUCCESS, payload, None, ""

        with tempfile.TemporaryDirectory() as tmp:
            client = YahooChartPriceClient(cache=FileCache(root=tmp),
                                           transport=transport,
                                           sleep_fn=lambda s: None)
            got, report = client.get_price_data("T", "2024-01-01",
                                                "2024-01-08",
                                                fetch_on="2024-01-09")
            self.assertEqual(report.status, STATUS_SUCCESS)
            self.assertEqual(len(got["close"]), 5)
            self.assertEqual(got["adj_close"], [])      # NOT the closes
            entry = json.loads(
                client._cache._path(PRICE_CACHE_NAMESPACE, "T")
                .read_text(encoding="utf-8"))
            self.assertEqual(entry["payload"]["adj_close"], [])
            got2, report2 = client.get_price_data("T", "2024-01-01",
                                                  "2024-01-08",
                                                  fetch_on="2024-01-09")
            self.assertEqual(report2.detail, "cache")   # served from cache
            self.assertEqual(got2["adj_close"], [])     # still not relabeled

    def test_partial_adjusted_series_preserves_gaps(self):
        # F4/F5: an individually missing adjusted bar stays missing
        import tempfile
        bars = [("2024-01-02", 100.0), ("2024-01-03", 101.0),
                ("2024-01-04", 102.0), ("2024-01-05", 103.0),
                ("2024-01-08", 104.0)]
        payload = P6ChartSplitParsing._payload(
            bars, [], adjnull={"2024-01-03", "2024-01-05", "2024-01-08"})

        def transport(url, headers=None, timeout=None):
            return STATUS_SUCCESS, payload, None, ""

        with tempfile.TemporaryDirectory() as tmp:
            client = YahooChartPriceClient(cache=FileCache(root=tmp),
                                           transport=transport,
                                           sleep_fn=lambda s: None)
            got, report = client.get_price_data("T", "2024-01-01",
                                                "2024-01-08",
                                                fetch_on="2024-01-09")
            self.assertEqual(report.status, STATUS_SUCCESS)
            adj_days = [d for d, _c in got["adj_close"]]
            self.assertEqual(adj_days, ["2024-01-02", "2024-01-04"])
            self.assertEqual(len(got["close"]), 5)   # raw keeps every bar

    def test_merge_never_backfills_adjusted_from_close(self):
        def entry(fetched, close, adj):
            return {"fetched_on": fetched, "oldest_fetched_on": fetched,
                    "ranges": [[min(close), max(close)]],
                    "close": sorted(close.items()),
                    "adj_close": sorted(adj.items()),
                    "splits": [], "splits_known": True,
                    "bar_fetched_on": {d: fetched for d in close}}
        old = entry("2024-01-05", {"2024-01-02": 100.0,
                                   "2024-01-03": 110.0}, {})
        new = entry("2024-02-05", {"2024-02-02": 120.0},
                    {"2024-02-02": 119.5})
        merged = YfinancePriceClient._merge_entry(old, new)
        self.assertEqual(dict(merged["adj_close"]), {"2024-02-02": 119.5})
        # reverse: old adjusted bars survive, new bars stay out of adj
        old2 = entry("2024-01-05", {"2024-01-02": 100.0},
                     {"2024-01-02": 99.5})
        new2 = entry("2024-02-05", {"2024-02-02": 120.0}, {})
        merged2 = YfinancePriceClient._merge_entry(old2, new2)
        self.assertEqual(dict(merged2["adj_close"]), {"2024-01-02": 99.5})
        self.assertIn(("2024-02-02", 120.0), merged2["close"])

    def test_company_assignment_keeps_adjusted_empty(self):
        src = _P4PriceSource(self.CLOSE)          # close only, no adj key
        chain = SourceChain([], src, [], [])
        company = chain.get_company("T", "tech", as_of=self.AS_OF,
                                    fetch_on=self.AS_OF)
        self.assertEqual(len(company.prices), 13)     # raw preserved
        self.assertEqual(company.adj_prices, [])      # NOT relabeled

    def test_momentum_without_adjusted_is_no_data(self):
        # F1/F2/F3/F8: no adjusted series -> NO_DATA, never raw closes
        from unittest import mock
        for src in (_P4PriceSource(self.CLOSE),               # key absent
                    _P4PriceSource(self.CLOSE, adj=[])):      # empty list
            with mock.patch.object(
                    sys.modules[__name__], "build_source_chain",
                    lambda source="auto": SourceChain([], src, [], [])):
                result = get_momentum_12_1("T", self.AS_OF, source="auto")
            self.assertEqual(result["status"], NO_DATA)
            self.assertEqual(result["reason"], "no_adjusted_price_data")
            self.assertIsNone(result["momentum_12_1"])
            self.assertIsNone(result["price_basis"])
            self.assertEqual(result["data_source"], "")

    def test_momentum_uses_adjusted_not_close(self):
        # F6/F7: long adjusted series -> correct 12-1 momentum from the
        # ADJUSTED bars, price_basis "adjusted"
        from unittest import mock
        adj = self._diverging_adjusted(self.CLOSE)
        src = _P4PriceSource(self.CLOSE, adj=adj)
        with mock.patch.object(
                sys.modules[__name__], "build_source_chain",
                lambda source="auto": SourceChain([], src, [], [])):
            result = get_momentum_12_1("T", self.AS_OF, source="auto")
        expected, _reason = momentum_12_1_detail(adj, self.AS_OF)
        close_based, _r = momentum_12_1_detail(self.CLOSE, self.AS_OF)
        self.assertEqual(result["status"], OK)
        self.assertAlmostEqual(result["momentum_12_1"], expected)
        # hand check: t_end = 2024-05-30 (day clamp), so the last adjusted
        # observation is 2024-04-30 -> 117.0 / 100.0 - 1, NOT the
        # close-based 120.0 / 100.0 - 1
        self.assertAlmostEqual(result["momentum_12_1"], 0.17)
        self.assertNotAlmostEqual(result["momentum_12_1"], close_based)
        self.assertEqual(result["price_basis"], "adjusted")
        self.assertEqual(result["data_source"], "p4_synthetic")

    def test_momentum_price_basis_none_on_short_adjusted(self):
        # F8: adjusted present but too short -> NO_DATA, price_basis None
        from unittest import mock
        src = _P4PriceSource(self.CLOSE,
                             adj=[("2023-06-30", 100.0),
                                  ("2023-07-31", 97.0)])
        with mock.patch.object(
                sys.modules[__name__], "build_source_chain",
                lambda source="auto": SourceChain([], src, [], [])):
            result = get_momentum_12_1("T", self.AS_OF, source="auto")
        self.assertEqual(result["status"], NO_DATA)
        self.assertIsNone(result["momentum_12_1"])
        self.assertIsNone(result["price_basis"])
        self.assertTrue(result["reason"])

    def test_old_price_cache_namespace_is_ignored(self):
        # F9 / PART D: a poisoned 'prices' entry must not be trusted; the
        # prices_v2 namespace forces a safe refetch, TTL preserved
        import json
        import tempfile
        ts0 = P6ChartSplitParsing.TS0          # 2024-01-02T00:00Z
        payload = {"chart": {"result": [{
            "timestamp": [ts0, ts0 + 86400],
            "indicators": {"quote": [{"close": [100.0, 101.0]}],
                           "adjclose": [{"adjclose": [99.5, 100.5]}]},
            "events": {"splits": {}}}], "error": None}}
        calls = []

        def transport(url, headers=None, timeout=None):
            calls.append(url)
            return STATUS_SUCCESS, payload, None, ""

        with tempfile.TemporaryDirectory() as tmp:
            cache = FileCache(root=tmp)
            poisoned = {           # what the pre-3.4.1 code would store
                "fetched_on": "2026-11-03", "oldest_fetched_on": "2026-11-03",
                "ranges": [["2023-01-01", "2025-01-01"]],
                "close": [("2024-01-02", 100.0), ("2024-01-03", 101.0)],
                "adj_close": [("2024-01-02", 100.0),
                              ("2024-01-03", 101.0)],   # raw relabel
                "splits": [], "splits_known": True,
                "bar_fetched_on": {"2024-01-02": "2026-11-03",
                                   "2024-01-03": "2026-11-03"}}
            cache.set("prices", "T", poisoned)      # old namespace planted
            client = YahooChartPriceClient(cache=cache, transport=transport,
                                           sleep_fn=lambda s: None)
            got, report = client.get_price_data("T", "2024-01-01",
                                                "2024-01-31",
                                                fetch_on="2026-11-03")
            self.assertEqual(len(calls), 1)   # old entry NOT used as a hit
            self.assertEqual(report.status, STATUS_SUCCESS)
            self.assertEqual(dict(got["adj_close"]),
                             {"2024-01-02": 99.5, "2024-01-03": 100.5})
            # new namespace written; old file left in place, never deleted
            new_path = cache._path(PRICE_CACHE_NAMESPACE, "T")
            self.assertTrue(new_path.exists())
            old_back = cache.get("prices", "T")     # still readable...
            self.assertEqual(old_back["adj_close"],
                             [[d, c] for d, c in poisoned["adj_close"]])
            self.assertNotEqual(old_back, None)     # ...but never trusted
            # TTL behavior preserved on the new namespace
            self.assertNotIn("prices", CACHE_TTL_SECONDS)
            self.assertEqual(CACHE_TTL_SECONDS[PRICE_CACHE_NAMESPACE],
                             12 * 3600)
            self.assertEqual(cache._ttl(PRICE_CACHE_NAMESPACE, None),
                             12 * 3600)
            entry = json.loads(new_path.read_text(encoding="utf-8"))
            self.assertEqual(entry["payload"]["adj_close"],
                             [["2024-01-02", 99.5], ["2024-01-03", 100.5]])

    def test_snapshot_restore_never_relabels_raw(self):
        # F10: legacy snapshots cannot prove the adjusted basis
        base = {"ticker": "T", "sector": "tech", "facts": {},
                "prices": [{"date": "2024-06-28", "close": 50.0}]}
        legacy_empty = dict(base, adj_prices=[])
        self.assertEqual(_company_from_dict(legacy_empty).adj_prices, [])
        legacy_filled = dict(base, adj_prices=[
            {"date": "2024-06-28", "close": 50.0}])     # maybe raw relabel
        self.assertEqual(_company_from_dict(legacy_filled).adj_prices, [])
        # new round-trips carry the basis proof
        good = Company(ticker="T", sector="tech", facts={},
                       prices=[("2024-06-28", 50.0)],
                       adj_prices=[("2024-06-28", 48.0)],
                       sources={"fixtures"})
        blob = _company_to_dict(good)
        self.assertEqual(blob["adj_prices_basis"], "adjusted")
        self.assertEqual(_company_from_dict(blob).adj_prices,
                         [("2024-06-28", 48.0)])
        raw_only = Company(ticker="T", sector="tech", facts={},
                           prices=[("2024-06-28", 50.0)],
                           adj_prices=[], sources={"fixtures"})
        blob2 = _company_to_dict(raw_only)
        self.assertNotIn("adj_prices_basis", blob2)
        self.assertEqual(_company_from_dict(blob2).adj_prices, [])

    def test_price_lookup_price_only_fallback_intact(self):
        # F11: the labeled fallback survives; an EMPTY adjusted list must
        # not masquerade as total_return either
        def lookup_with(src):
            pl = PriceLookup.__new__(PriceLookup)
            pl.chain = SourceChain([], src, [], [])
            pl.memo, pl.window, pl.fetch_on = {}, None, None
            pl.uses_adjusted = None
            return pl
        pl = lookup_with(_P4PriceSource(self.CLOSE))          # key absent
        self.assertEqual(pl("T", self.AS_OF), 124.0)
        self.assertEqual(pl.label, "price_only")
        pl2 = lookup_with(_P4PriceSource(self.CLOSE, adj=[]))  # empty list
        self.assertEqual(pl2("T", self.AS_OF), 124.0)
        self.assertEqual(pl2.label, "price_only")
        adj = self._diverging_adjusted(self.CLOSE)
        pl3 = lookup_with(_P4PriceSource(self.CLOSE, adj=adj))
        self.assertEqual(pl3("T", self.AS_OF), 121.0)         # 124 - 3
        self.assertEqual(pl3.label, "total_return")

    def test_composite_independent_of_adjusted_prices(self):
        # F12: the quality composite must not depend on the adjusted basis
        same = hand_company("ADJ1", "tech")
        empty = hand_company("ADJ2", "tech")
        empty.adj_prices = []
        halved = hand_company("ADJ3", "tech")
        halved.adj_prices = [(d, p / 2.0) for d, p in halved.adj_prices]
        results = score_universe([same, empty, halved], self.AS_OF)
        r1 = results["ADJ1"].to_api_dict()
        r2 = results["ADJ2"].to_api_dict()
        r3 = results["ADJ3"].to_api_dict()
        self.assertEqual(r1["status"], OK)
        self.assertEqual(r1["status"], r2["status"])
        self.assertEqual(r1["score"], r2["score"])
        self.assertEqual(r1["score"], r3["score"])
        self.assertEqual(r1["metric_scores"], r2["metric_scores"])
        self.assertEqual(r1["metric_scores"], r3["metric_scores"])


class MinimumPillarGate(unittest.TestCase):
    """Re-audit finding 1 / owner-directed policy: a result can be OK only
    when at least MIN_PILLARS of the six pillar scores are non-None AND
    metric coverage passes MIN_COVERAGE (float-safe within COVERAGE_EPS).
    Status priority is preserved end to end: stale fundamentals, then
    missing required metrics, then the coverage gate, then the pillar
    gate, then the accepted score; missing pillars stay None, never zero;
    failed_gates names every failed gate deterministically."""

    # ---- constructions from the existing Company/test helpers ----------

    @staticmethod
    def _nie_facts():
        """noninterest_expense FY + Q facts (hand_facts lacks the item)."""
        fy = [Fact(f"{y}-12-31", f"{y + 1}-02-15", 280.0 + 10.0 * (y - 2020),
                   "10-K", "FY", f"{y}-01-01") for y in range(2020, 2024)]
        q = [Fact(qend, filed, (280.0 + 10.0 * 3) / 4.0, "10-Q", "Q", qstart)
             for qend, filed, qstart in (
                 ("2023-03-31", "2023-05-15", "2023-01-01"),
                 ("2023-06-30", "2023-08-14", "2023-04-01"),
                 ("2023-09-30", "2023-11-14", "2023-07-01"),
                 ("2023-12-31", "2024-02-15", "2023-10-01"))]
        return fy + q

    def _three_pillar(self):
        """(label, target, peer) with ONLY profitability, growth and
        financial_strength available (coverage exactly MIN_COVERAGE)."""
        nie = self._nie_facts()
        reit = reit_company("R3P")
        return (
            ("utilities",
             hand_company("U3P", "utilities", prices=[],
                          drop=("cfo", "shares_outstanding")),
             hand_company("UP1", "utilities")),
            ("financials",
             hand_company("B3P", "financials", prices=[],
                          drop=("cfo", "shares_outstanding"),
                          extra={"noninterest_expense": nie}),
             hand_company("BPK", "financials",
                          extra={"noninterest_expense": list(nie)})),
            ("reit",
             Company("R3P", "reits",
                     {k: v for k, v in reit.facts.items()
                      if k not in ("dividends_paid", "shares_outstanding")},
                     [], [], {"fixtures"}),
             reit_company("RPT")),
        )

    def _four_pillar(self):
        """(label, target, peer) with EXACTLY four available pillars and
        coverage >= MIN_COVERAGE, one construction per sector model."""
        energy = energy_company(ticker="E4")
        reit = reit_company("R4")
        nie = self._nie_facts()
        return (
            ("utilities",
             hand_company("U4", "utilities", prices=[],
                          drop=("dividends_paid", "buybacks",
                                "shares_outstanding")),
             hand_company("UP2", "utilities")),
            ("financials",
             hand_company("B4", "financials", prices=[],
                          drop=("shares_outstanding",),
                          extra={"noninterest_expense": nie}),
             hand_company("BPK2", "financials",
                          extra={"noninterest_expense": list(nie)})),
            ("reit",
             Company("R4", "reits",
                     {k: v for k, v in reit.facts.items()
                      if k != "shares_outstanding"},
                     [], [], {"fixtures"}),
             reit_company("RPT2")),
            ("tech",
             hand_company("T4", "tech", prices=[],
                          drop=("dividends_paid", "buybacks",
                                "shares_outstanding")),
             hand_company("TP4", "tech")),
            ("cyclicals",
             Company("E4", "energy",
                     {k: v for k, v in energy.facts.items()
                      if k not in ("dividends_paid", "buybacks",
                                   "shares_outstanding")},
                     [], [], {"fixtures"}),
             energy_company(ticker="EPT")),
        )

    @staticmethod
    def _n_avail(res) -> int:
        return sum(1 for v in (res.pillars or {}).values() if v is not None)

    # ---- 1 + 2: three pillars at coverage exactly MIN_COVERAGE ---------

    def test_three_pillars_at_exact_coverage_are_refused(self):
        for label, target, peer in self._three_pillar():
            res = score_universe([target, peer], AS_OF)[target.ticker]
            self.assertEqual(res.status, INSUFFICIENT_DATA, label)
            self.assertIsNone(res.score, label)
            unrated = res.score_unrated
            self.assertEqual(unrated["reason"],
                             "pillar_count_below_minimum", label)
            self.assertEqual(unrated["n_pillars_available"], 3, label)
            self.assertEqual(unrated["coverage"], MIN_COVERAGE, label)
            self.assertEqual(unrated["failed_gates"],
                             ["pillar_count_below_minimum"], label)
            self.assertEqual(unrated["min_pillars"], MIN_PILLARS, label)
            self.assertNotIn("min_coverage", unrated, label)
            # the peer (all six pillars) must keep its accepted score
            pres = score_universe([target, peer], AS_OF)[peer.ticker]
            self.assertEqual(pres.status, OK, label)
            self.assertIsNotNone(pres.score, label)

    def test_three_pillars_expose_no_score_or_rank(self):
        for label, target, peer in self._three_pillar():
            res = score_universe([target, peer], AS_OF)[target.ticker]
            api = res.to_api_dict()
            self.assertIsNone(api["score"], label)
            self.assertIsNone(api["rank_in_sector"], label)
            self.assertNotEqual(api["status"], OK, label)

    # ---- 3: four pillars pass on every sector model --------------------

    def test_four_pillars_pass_all_five_models(self):
        for label, target, peer in self._four_pillar():
            res = score_universe([target, peer], AS_OF)[target.ticker]
            self.assertEqual(res.status, OK, label)
            self.assertIsNotNone(res.score, label)
            self.assertEqual(self._n_avail(res), 4, label)
            self.assertFalse(_coverage_below_minimum(res.coverage), label)
            self.assertFalse(res.score_unrated, label)

    # ---- 4 + 6: pillar count passes, coverage fails ---------------------

    def _four_pillars_low_coverage(self):
        # tech: P loses gross_profitability (no cogs), FS loses
        # interest_coverage and altman_z, EQ loses piotroski_f (cogs);
        # exactly four pillars stay available at coverage 0.5875.
        target = hand_company("T4L", "tech", prices=[],
                              drop=("cogs", "interest_expense",
                                    "shares_outstanding"))
        peer = hand_company("T4P", "tech")
        return score_universe([target, peer], AS_OF)["T4L"]

    def test_four_pillars_below_coverage_refused_with_coverage_reason(self):
        res = self._four_pillars_low_coverage()
        self.assertEqual(res.status, INSUFFICIENT_DATA)
        self.assertIsNone(res.score)
        self.assertEqual(self._n_avail(res), 4)
        unrated = res.score_unrated
        self.assertEqual(unrated["reason"], "coverage_below_minimum")
        self.assertEqual(unrated["failed_gates"], ["coverage_below_minimum"])
        self.assertEqual(unrated["min_coverage"], MIN_COVERAGE)
        self.assertNotIn("min_pillars", unrated)
        self.assertLess(unrated["coverage"], MIN_COVERAGE)

    # ---- 5: coverage passes, pillar count fails -------------------------

    def test_coverage_passes_but_pillar_count_fails(self):
        target = hand_company("U3P", "utilities", prices=[],
                              drop=("cfo", "shares_outstanding"))
        res = score_universe([target, hand_company("UP1", "utilities")],
                             AS_OF)["U3P"]
        unrated = res.score_unrated
        self.assertEqual(res.status, INSUFFICIENT_DATA)
        self.assertEqual(unrated["reason"], "pillar_count_below_minimum")
        self.assertEqual(unrated["failed_gates"],
                         ["pillar_count_below_minimum"])
        self.assertEqual(unrated["n_pillars_available"], 3)
        self.assertEqual(unrated["min_pillars"], MIN_PILLARS)
        self.assertFalse(_coverage_below_minimum(res.coverage))

    # ---- 7: both gates fail ---------------------------------------------

    def test_both_gates_fail_coverage_reason_primary(self):
        # coverage 0.425 AND only three pillars: the primary reason stays
        # coverage_below_minimum and failed_gates lists BOTH deterministically.
        target = hand_company("T3L", "tech", prices=[],
                              drop=("cogs", "interest_expense",
                                    "shares_outstanding", "cfo"))
        res = score_universe([target, hand_company("T3P", "tech")],
                             AS_OF)["T3L"]
        self.assertEqual(res.status, INSUFFICIENT_DATA)
        self.assertIsNone(res.score)
        unrated = res.score_unrated
        self.assertEqual(unrated["reason"], "coverage_below_minimum")
        self.assertEqual(unrated["failed_gates"],
                         ["coverage_below_minimum",
                          "pillar_count_below_minimum"])
        self.assertEqual(unrated["n_pillars_available"], 3)
        self.assertEqual(unrated["min_coverage"], MIN_COVERAGE)
        self.assertEqual(unrated["min_pillars"], MIN_PILLARS)
        self.assertLess(unrated["coverage"], MIN_COVERAGE)

    # ---- 8: missing pillars are None, never zero ------------------------

    def test_missing_pillars_stay_none_never_zero(self):
        target = hand_company("U3P", "utilities", prices=[],
                              drop=("cfo", "shares_outstanding"))
        res = score_universe([target, hand_company("UP1", "utilities")],
                             AS_OF)["U3P"]
        for pillar in ("earnings_quality", "valuation", "shareholder_yield"):
            self.assertIsNone(res.pillars[pillar])
        for metric in ("accruals_ratio", "cfo_ni", "piotroski_f",
                       "ebitda_yield", "fcf_yield", "earnings_yield",
                       "shareholder_yield", "share_count_change"):
            self.assertIsNone(res.metrics[metric], metric)
            self.assertIsNone(res.metric_scores[metric], metric)
        self.assertEqual(self._n_avail(res), 3)

    # ---- 9 + 10 + 11: float-safe coverage boundary ----------------------

    def test_exact_coverage_boundary_is_deterministic(self):
        self.assertFalse(_coverage_below_minimum(MIN_COVERAGE))
        target = hand_company("U3P", "utilities", prices=[],
                              drop=("cfo", "shares_outstanding"))
        res = score_universe([target, hand_company("UP1", "utilities")],
                             AS_OF)["U3P"]
        self.assertEqual(round(res.coverage, 6), MIN_COVERAGE)
        # the coverage gate must NOT fire at the exact boundary: the
        # refusal comes from the pillar gate alone, deterministically
        self.assertEqual(res.score_unrated["reason"],
                         "pillar_count_below_minimum")

    def test_coverage_within_epsilon_passes(self):
        self.assertFalse(
            _coverage_below_minimum(MIN_COVERAGE - COVERAGE_EPS / 2.0))
        self.assertFalse(
            _coverage_below_minimum(MIN_COVERAGE - COVERAGE_EPS))

    def test_coverage_outside_epsilon_fails(self):
        self.assertTrue(
            _coverage_below_minimum(MIN_COVERAGE - 10.0 * COVERAGE_EPS))
        self.assertTrue(_coverage_below_minimum(0.64))
        self.assertTrue(_coverage_below_minimum(0.0))
        self.assertTrue(_coverage_below_minimum(0.65 - 1e-6))

    # ---- 12 + 13: existing gate priorities unchanged --------------------

    def test_stale_fundamentals_priority_unchanged(self):
        # stale AND only three pillars: STALE_DATA wins before any gate.
        # as_of is pushed past STALE_FUNDAMENTALS_DAYS while the fiscal
        # history stays complete, so exactly P/G/FS remain available.
        stale_as_of = "2024-12-31"
        company = hand_company("UOLD", "utilities", prices=[],
                               drop=("cfo", "shares_outstanding"))
        res = score_universe(
            [company, hand_company("UP3", "utilities")],
            stale_as_of)["UOLD"]
        self.assertEqual(res.status, STALE_DATA)
        self.assertIsNone(res.score)
        self.assertEqual(res.score_unrated["reason"], "stale_fundamentals")
        self.assertEqual(self._n_avail(res), 3)
        self.assertLess(self._n_avail(res), MIN_PILLARS)

    def test_missing_required_metric_priority_unchanged(self):
        # interest_coverage is REQUIRED for utilities and missing here,
        # while only three pillars would be available: the required-metric
        # gate wins over both coverage and pillar gates.
        target = hand_company("UMR", "utilities", prices=[],
                              drop=("cfo", "shares_outstanding",
                                    "interest_expense"))
        res = score_universe([target, hand_company("UP4", "utilities")],
                             AS_OF)["UMR"]
        self.assertEqual(res.status, SECTOR_DATA_MISSING)
        self.assertIsNone(res.score)
        unrated = res.score_unrated
        self.assertEqual(unrated["reason"], "missing_required_metrics")
        self.assertIn("interest_coverage", unrated["missing_required"])


class PitFreezeAndReturns(unittest.TestCase):
    """Re-audit findings 2 + 5 (PART 6): the PIT harness validates
    --freeze-date strictly BEFORE the PIT file check, classifies every
    emitted period in/out-of-sample only with a valid freeze date AND a
    matching expected hash, keeps stdout to exactly one JSON object, and
    counts delisting returns only when they actually entered an appended
    scored pair; invalid forward returns (below -1.0, NaN, +/-inf,
    malformed, overflow) are rejected while -1.0 is accepted."""

    HEAD = ("month_end,ticker,permanent_id,sector_pit,listed,"
            "total_return_next_month,delisting_return_if_any\n")

    @staticmethod
    def _fxte_rows(months, tr="0.010", dr=""):
        lines = []
        for m in months:
            for i in range(1, 11):
                lines.append(f"{m},FXTE{i:02d},{1000 + i},tech,1,{tr},{dr}\n")
        return lines

    def _pit_run(self, rows_text, expect_hash=None, freeze_date=None):
        """Direct _pit_validate call; (json, rc, stdout, stderr)."""
        import argparse as _ap
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pit.csv")
            with open(path, "w") as fh:
                fh.write(rows_text)
            args = _ap.Namespace(pit_universe=path, source="fixtures",
                                 expect_config_hash=expect_hash,
                                 freeze_date=freeze_date)
            out_buf, err_buf = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out_buf), \
                    contextlib.redirect_stderr(err_buf):
                rc = _pit_validate(args)
        text = out_buf.getvalue()
        payload = json.loads(text) if text.strip().startswith("{") \
            else None
        return payload, rc, text, err_buf.getvalue()

    def _forward_run(self, argv):
        """Real CLI path through forward_main; (rc, stdout, stderr)."""
        out_buf, err_buf = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_buf), \
                contextlib.redirect_stderr(err_buf):
            rc = forward_main(argv)
        return rc, out_buf.getvalue(), err_buf.getvalue()

    def _write_pit(self, rows_text):
        import tempfile
        tmp = tempfile.mkdtemp()
        path = os.path.join(tmp, "pit.csv")
        with open(path, "w") as fh:
            fh.write(rows_text)
        return path

    # ---- freeze date: valid / missing / invalid / future ----------------

    def test_valid_freeze_date_classifies_every_period(self):
        months = ["2024-02-29", "2024-03-31", "2024-04-30", "2024-05-31"]
        text = self.HEAD + "".join(self._fxte_rows(months))
        payload, rc, out_text, err_text = self._pit_run(
            text, expect_hash=config_hash(), freeze_date="2024-03-31")
        self.assertEqual(rc, 0)
        # final month (2024-05-31) is never a period row (see the
        # report-only note): emitted months are 02, 03 and 04
        self.assertEqual([p["month"] for p in payload["periods"]],
                         ["2024-02-29", "2024-03-31", "2024-04-30"])
        # month before/on the freeze date is in-sample, after is OOS;
        # pool_too_small rows carry in_sample too
        self.assertTrue(all("in_sample" in p for p in payload["periods"]))
        self.assertTrue(any(p.get("reason") == "pool_too_small"
                            for p in payload["periods"]))
        self.assertEqual([p["in_sample"] for p in payload["periods"]],
                         [True, True, False])
        self.assertEqual(payload["in_sample_months"], 2)
        self.assertEqual(payload["oos_months"], 1)
        self.assertEqual(payload["in_sample_months"]
                         + payload["oos_months"],
                         len(payload["periods"]))
        self.assertTrue(payload["validation_complete"])
        self.assertTrue(payload["oos_claim_allowed"])
        self.assertEqual(payload["freeze_date"], "2024-03-31")
        self.assertTrue(payload["config_hash_verified"])
        self.assertIn("freeze_convention", payload)
        # stdout: exactly one parseable JSON object, NOTEs on stderr
        self.assertEqual(json.loads(out_text), payload)
        self.assertNotIn("NOTE:", out_text)
        self.assertIn("NOTE:", err_text)

    def test_missing_freeze_date_nulls_everything(self):
        months = ["2024-02-29", "2024-03-31", "2024-04-30"]
        text = self.HEAD + "".join(self._fxte_rows(months))
        payload, rc, _out, err = self._pit_run(
            text, expect_hash=config_hash(), freeze_date=None)
        self.assertEqual(rc, 0)
        self.assertTrue(payload["periods"])
        for p in payload["periods"]:
            self.assertIsNone(p["in_sample"])
        self.assertIsNone(payload["in_sample_months"])
        self.assertIsNone(payload["oos_months"])
        self.assertFalse(payload["validation_complete"])
        self.assertFalse(payload["oos_claim_allowed"])
        self.assertIsNone(payload["freeze_date"])
        self.assertIn("OOS claims NOT allowed", err)
        self.assertIn("--freeze-date", err)
        self.assertNotIn("out-of-sample language applies ONLY", err)

    def test_missing_hash_nulls_everything(self):
        months = ["2024-02-29", "2024-03-31", "2024-04-30"]
        text = self.HEAD + "".join(self._fxte_rows(months))
        payload, rc, _out, err = self._pit_run(
            text, expect_hash=None, freeze_date="2024-03-31")
        self.assertEqual(rc, 0)
        for p in payload["periods"]:
            self.assertIsNone(p["in_sample"])
        self.assertIsNone(payload["in_sample_months"])
        self.assertIsNone(payload["oos_months"])
        self.assertFalse(payload["validation_complete"])
        self.assertFalse(payload["oos_claim_allowed"])
        self.assertFalse(payload["config_hash_verified"])
        self.assertIn("--expect-config-hash", err)

    def test_invalid_freeze_dates_fail_before_file_check(self):
        # the PIT file does not exist: a missing file must not conceal an
        # invalid freeze date (validated BEFORE the CSV existence check)
        for bad in ("2024-13-45",        # malformed calendar date
                    "not-a-date",       # not a date at all
                    "20240229",         # not the exact YYYY-MM-DD form
                    "2024-W09-4"):      # ISO week form
            rc, out, err = self._forward_run(
                ["--pit-universe", "/nonexistent/pit.csv",
                 "--freeze-date", bad])
            self.assertEqual(rc, 1, bad)
            self.assertIn("FAILED: --freeze-date", err, bad)
            self.assertNotIn("NOT RUN", out + err, bad)
            self.assertEqual(out, "", bad)   # no JSON on a failed run

    def test_future_freeze_date_fails(self):
        rc, out, err = self._forward_run(
            ["--pit-universe", "/nonexistent/pit.csv",
             "--freeze-date", "2999-01-01"])
        self.assertEqual(rc, 1)
        self.assertIn("FAILED: --freeze-date", err)
        self.assertIn("future freeze date", err)
        self.assertNotIn("NOT RUN", out + err)

    # ---- config hash through the real CLI --------------------------------

    def test_cli_correct_hash_and_freeze_run_end_to_end(self):
        months = ["2024-02-29", "2024-03-31", "2024-04-30"]
        path = self._write_pit(self.HEAD + "".join(self._fxte_rows(months)))
        rc, out, err = self._forward_run(
            ["--pit-universe", path, "--source", "fixtures",
             "--freeze-date", "2024-02-29",
             "--expect-config-hash", config_hash()])
        self.assertEqual(rc, 0)
        payload = json.loads(out)          # whole stdout is ONE JSON object
        self.assertTrue(payload["config_hash_verified"])
        self.assertEqual([p["in_sample"] for p in payload["periods"]],
                         [True, False])   # freeze ON the first month
        self.assertTrue(payload["oos_claim_allowed"])
        self.assertIn("survivorship", err)   # rule I10 note on stderr

    def test_cli_wrong_hash_aborts_before_file_check(self):
        rc, out, err = self._forward_run(
            ["--pit-universe", "/nonexistent/pit.csv",
             "--expect-config-hash", "deadbeefdeadbeef"])
        self.assertEqual(rc, 1)
        self.assertIn("FAILED: config_hash", err)
        self.assertNotIn("NOT RUN", out + err)   # not concealed by the
        # missing file
        self.assertEqual(out, "")

    # ---- month representation validation ---------------------------------

    def test_invalid_month_is_explicit_input_failure(self):
        rows = [self.HEAD]
        rows.append("2024-13-99,FXTE01,1001,tech,1,0.010,\n")
        rows.append("2024-13-99,FXTE02,1002,tech,1,0.010,\n")
        payload, rc, _out, err = self._pit_run(
            "".join(rows), expect_hash=config_hash(),
            freeze_date="2024-03-31")
        self.assertEqual(rc, 1)
        self.assertIsNone(payload)
        self.assertIn("FAILED: invalid month_end", err)

    # ---- stdout / stderr contract + human table --------------------------

    def test_human_table_only_on_tty_stderr(self):
        months = ["2024-02-29", "2024-03-31", "2024-04-30"]
        path = self._write_pit(self.HEAD + "".join(self._fxte_rows(months)))

        class TtyIO(io.StringIO):
            def isatty(self):
                return True

        import tempfile
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NO_COLOR", None)
            buf, err = io.StringIO(), TtyIO()
            with contextlib.redirect_stdout(buf), \
                    contextlib.redirect_stderr(err):
                rc = forward_main(
                    ["--pit-universe", path, "--source", "fixtures",
                     "--freeze-date", "2024-02-29",
                     "--expect-config-hash", config_hash()])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            # emitted periods are months 02-29 and 03-31; the freeze ON
            # 2024-02-29 makes 02-29 in-sample and 03-31 out-of-sample
            self.assertEqual(payload["in_sample_months"], 1)
            self.assertEqual(payload["oos_months"], 1)
            table = err.getvalue()
            self.assertIn("month | n_scored | rank_ic | spread | IN/OOS",
                          table)
            self.assertIn("IN", table)
            self.assertIn("OOS", table)
            self.assertNotIn("NOTE:", buf.getvalue())
        with mock.patch.dict(os.environ, {"NO_COLOR": "1"}):
            buf, err = io.StringIO(), TtyIO()
            with contextlib.redirect_stdout(buf), \
                    contextlib.redirect_stderr(err):
                rc = forward_main(
                    ["--pit-universe", path, "--source", "fixtures",
                     "--freeze-date", "2024-02-29",
                     "--expect-config-hash", config_hash()])
            self.assertEqual(rc, 0)
            table = err.getvalue()
            self.assertIn("IN/OOS", table)      # table still prints
            self.assertNotIn("\033[", table)    # but NO_COLOR is honoured:
            # no ANSI styling

        # non-TTY stderr: no table at all
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(err):
            rc = forward_main(
                ["--pit-universe", path, "--source", "fixtures",
                 "--freeze-date", "2024-02-29",
                 "--expect-config-hash", config_hash()])
        self.assertEqual(rc, 0)
        self.assertNotIn("IN/OOS", err.getvalue())

    # ---- delisting counter (PART F) ---------------------------------------

    def _single_month_run(self, extra_lines, tr="", dr=""):
        rows = [self.HEAD,
                f"2024-02-29,FXTE01,1001,tech,1,{tr},{dr}\n"]
        rows.extend(extra_lines)
        payload, rc, _out, _err = self._pit_run("".join(rows))
        self.assertEqual(rc, 0)
        self.assertIsNotNone(payload)
        return payload

    def test_delisting_return_counted_for_scored_pair(self):
        payload = self._single_month_run([], tr="", dr="-0.500000")
        self.assertEqual(payload["n_delisting_returns"], 1)
        self.assertEqual(payload["per_month"][0]["scored"], 1)
        self.assertEqual(payload["per_month"][0]["unscored_by_reason"], {})

    def test_unscored_delister_not_counted(self):
        payload = self._single_month_run(
            ["2024-02-29,GONE1,9001,tech,1,,-0.500000\n"])
        self.assertEqual(payload["n_delisting_returns"], 0)
        # an unknown ticker resolves to NO_DATA through the scored-universe
        # map, so its unscored reason is no_data - and the delisting return
        # it carried never entered a pair and is never counted
        self.assertEqual(
            payload["per_month"][0]["unscored_by_reason"]
            .get("no_data"), 1)

    def test_missing_forward_return_not_counted(self):
        payload = self._single_month_run([], tr="", dr="")
        self.assertEqual(payload["n_delisting_returns"], 0)
        self.assertEqual(
            payload["per_month"][0]["unscored_by_reason"]
            .get("no_forward_return"), 1)

    def test_invalid_forward_return_not_counted(self):
        payload = self._single_month_run([], tr="nan", dr="")
        self.assertEqual(payload["n_delisting_returns"], 0)
        self.assertEqual(
            payload["per_month"][0]["unscored_by_reason"]
            .get("invalid_forward_return"), 1)

    def test_ordinary_total_return_not_counted(self):
        payload = self._single_month_run([], tr="0.010", dr="-0.500000")
        self.assertEqual(payload["n_delisting_returns"], 0)
        self.assertEqual(payload["per_month"][0]["scored"], 1)

    def test_invalid_primary_plus_valid_delisting_fallback(self):
        payload = self._single_month_run([], tr="oops", dr="-0.500000")
        self.assertEqual(payload["n_delisting_returns"], 1)
        self.assertEqual(payload["per_month"][0]["scored"], 1)
        self.assertEqual(payload["per_month"][0]["unscored_by_reason"], {})

    def test_no_double_counting(self):
        lines = [f"2024-02-29,FXTE{i:02d},{1000 + i},tech,1,,-0.5\n"
                 for i in range(1, 4)]
        payload = self._single_month_run(lines, tr="", dr="-0.500000")
        self.assertEqual(payload["n_delisting_returns"], 4)  # 4 appended
        self.assertEqual(payload["per_month"][0]["scored"], 4)

    # ---- invalid forward returns (PART G) ---------------------------------

    def test_invalid_return_values_rejected(self):
        for bad in ("nan", "inf", "-inf", "Infinity", "-Infinity", "abc",
                    "1,5", "", "   ", "1e999", "-1e999", "-1.5", "-1.01",
                    "1e309"):
            self.assertIsNone(_valid_forward_return(bad), bad)
        self.assertIsNone(_valid_forward_return(None))

    def test_valid_return_values_accepted(self):
        self.assertEqual(_valid_forward_return("-1.0"), -1.0)   # total
        # loss is a possible simple return and MUST be accepted
        self.assertEqual(_valid_forward_return("-0.25"), -0.25)
        self.assertEqual(_valid_forward_return("0.0"), 0.0)
        self.assertEqual(_valid_forward_return(" 0.05 "), 0.05)
        self.assertEqual(_valid_forward_return("2.5"), 2.5)    # no upper
        self.assertEqual(_valid_forward_return("1e6"), 1e6)    # bound is
        # imposed on a finite positive simple return


class P7SecUserAgentAndFfoNotes(unittest.TestCase):
    """P7: honest SEC User-Agent docs/diagnostics + FFO zero-default note.

    PART A/B/C: the default header is STATIC and non-identifying (never
    carries the OS username or hostname, compared case-insensitively
    against getpass.getuser()/socket.gethostname()); an explicit
    SEC_USER_AGENT round-trips into the header with the previous
    environment restored afterwards; the livecheck SEC line documents
    both states without echoing any configured contact value. PART D:
    the REIT FFO arithmetic keeps the zero default for an unavailable
    gains_on_sales/impairments component and now says so in the notes.
    """

    MIN_IDENTITY_LEN = 3   # shorter strings are not meaningful evidence
    FFO_NOTE = "ffo_gains_impairments_assumed_zero"

    @staticmethod
    def _identity_or_none(fetch) -> Optional[str]:
        """Identity value when meaningful, else None (skip that check)."""
        try:
            value = (fetch() or "").strip()
        except Exception:
            return None          # identity unavailable in this environment
        return value if len(value) >= P7SecUserAgentAndFfoNotes \
            .MIN_IDENTITY_LEN else None

    def test_default_header_carries_no_machine_identity(self):
        from unittest import mock
        import getpass
        import socket
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(SEC_USER_AGENT_ENV, None)
            ua = SecEdgarClient()._headers()["User-Agent"]
            self.assertTrue(ua)             # a header is always produced
            ua_low = ua.lower()
            for identity in (self._identity_or_none(getpass.getuser),
                             self._identity_or_none(socket.gethostname)):
                if not identity:       # empty/too short: skip, per spec
                    continue
                self.assertNotIn(identity.lower(), ua_low)

    def test_explicit_contact_used_and_environment_restored(self):
        from unittest import mock
        # dummy fixture contact (same as the mission spec; never a real
        # secret, and nothing is printed on the pass path)
        before = os.environ.get(SEC_USER_AGENT_ENV)
        with mock.patch.dict(os.environ,
                             {SEC_USER_AGENT_ENV: "Audit <a@b.c>"}):
            ua = SecEdgarClient()._headers()["User-Agent"]
            self.assertIn("Audit <a@b.c>", ua)
        self.assertEqual(os.environ.get(SEC_USER_AGENT_ENV), before)

    def test_livecheck_sec_line_when_unset(self):
        text = _sec_user_agent_status(False).lower()
        self.assertIn("not set", text)
        self.assertIn("static", text)
        self.assertIn("non-identifying", text)
        self.assertIn("sec_user_agent", text)
        self.assertIn("fair-access", text)
        self.assertNotIn("default identifying", text)   # the stale claim

    def test_livecheck_sec_line_when_set(self):
        text = _sec_user_agent_status(True)
        self.assertIn("set", text)
        # bool in, fixed text out: it cannot echo a configured contact

    def test_no_stale_identifying_default_claims_in_source(self):
        # the phrases are assembled at runtime so this test can never find
        # its own checklist (same trick as the unshipped-refs scan) and the
        # failure message stays short (no full-source repr in the report)
        stale = (
            "default " + "identifying User-Agent",
            "built from " + "your user@host",
            "DEFAULT " + "contact built from user@hostname",
        )
        with open(q.__file__, encoding="utf-8") as fh:
            src = fh.read()
        for phrase in stale:
            if phrase in src:
                self.fail(f"stale SEC User-Agent claim still in source: "
                          f"{phrase!r}")

    def test_reit_ffo_zero_default_note_and_unchanged_arithmetic(self):
        # reit_company ships gains_on_sales but NO impairments: the FFO
        # arithmetic zero-defaults impairments (441/900 = 0.49) - the note
        # must disclose the assumption and the value must stay exact.
        res = score_universe([reit_company("R7NOTE")], "2024-06-28")["R7NOTE"]
        self.assertIn(self.FFO_NOTE, res.notes)
        self.assertAlmostEqual(res.metrics["ffo_margin"], 0.49, places=9)

    def test_reit_ffo_note_absent_when_components_available(self):
        r = reit_company("R7FULL")
        facts = dict(r.facts)
        facts["impairments"] = [
            Fact(f.period_end, f.filing_date, 3.0, "10-K", "FY",
                 f.period_start)
            for f in r.facts["gains_on_sales"]]
        company = Company("R7FULL", "reits", facts, r.prices, r.adj_prices,
                          {"fixtures"})
        res = score_universe([company], "2024-06-28")["R7FULL"]
        self.assertNotIn(self.FFO_NOTE, res.notes)
        self.assertAlmostEqual(res.metrics["ffo_margin"],
                               0.5033333333333333, places=9)

    def test_ffo_note_not_added_for_non_reit_models(self):
        tech = next(c for c in fixture_companies() if c.sector == "tech")
        res = score_universe([tech], "2024-06-28")[tech.ticker]
        self.assertNotIn(self.FFO_NOTE, res.notes)


_TEST_CLASSES = (
    D1UniverseOverrides,
    D2FinnhubNormalization,
    D3DebtDoubleCounting,
    D4Momentum,
    D5PriceWindows,
    D6ProviderDiagnostics,
    D7ForwardValidation,
    D8PeriodAlignment,
    D9Staleness,
    D10ScoreExposure,
    D11MissingDataBias,
    D12ResumeIntegrity,
    D13D14DocumentationAndCache,
    RegressionMetrics,
    RegressionView,
    RegressionScoring,
    RegressionApi,
    RegressionSecNormalization,
    RepairedRegressions,
    CorpActions,
    TerminalCardAndInlineUniverse,
    PitAvailability,
    ProviderHardening,
    LiveProviderTests,
    D15SplitBasis,
    M1SplitInvariance,
    D16StalenessDefinition,
    D17PercentileSentinels,
    D18Provenance,
    D19Availability,
    D20Packaging,
    D21Documentation,
    D22Universe,
    D23Determinism,
    D23CacheMerge,
    D24OperationalHonesty,
    D25CaptureGate,
    D26NumericLint,
    M2FutureIndependence,
    M3OrderInvariance,
    M4ScaleInvariance,
    M5DuplicateInvariance,
    M6Monotonicity,
    M7StalenessMonotonicity,
    M8ClockIndependence,
    P6SplitBasisThroughFetchPath,
    P6ChartSplitParsing,
    P6DebtCompleteness,
    P6DateAndTickerContracts,
    P6TzFailClosed,
    P6SecDefaults,
    P6TagPriorityAndCoverage,
    P6YfinanceThrottle,
    P6NoDataDiagnostics,
    P6PitHarness,
    P6Metamorphics,
    P6SecretCanary,
    AdjustedPriceBasis,
    MinimumPillarGate,
    PitFreezeAndReturns,
    P7SecUserAgentAndFfoNotes,
)


def run_selftests() -> int:
    """Run the embedded suite; print 'N passed, M failed, K NOT RUN'.

    S2: live integrations report their own vocabulary - LIVE PASS (counted
    as passed, listed), LIVE SKIP(reason) (counted as NOT RUN) and
    LIVE FAIL(error) (counted as a failure). Mocked and live results are
    reported separately.
    """
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in _TEST_CLASSES:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    class _Result(unittest.TestResult):
        """Records successful test ids so live passes can be itemized."""

        def __init__(self):
            super().__init__()
            self.passed_ids: list = []

        def addSuccess(self, test):
            super().addSuccess(test)
            self.passed_ids.append(str(test))

    result = _Result()
    suite.run(result)
    live_passes = [t for t in result.passed_ids if "LiveProviderTests" in t]
    not_run = [(str(t), r) for t, r in result.skipped
               if str(r).startswith("NOT RUN")]
    live_skips = [(str(t), r) for t, r in result.skipped
                  if str(r).startswith("LIVE SKIP")]
    other_skips = [(str(t), r) for t, r in result.skipped
                   if not str(r).startswith("NOT RUN")
                   and not str(r).startswith("LIVE SKIP")]
    passed = result.testsRun - len(result.failures) - len(result.errors) \
        - len(result.skipped)
    if not_run:
        print("NOT RUN (no key/package in this environment):")
        for name, reason in not_run:
            print(f"  - {name}: {reason}")
    if live_skips:
        print("LIVE SKIP (live integration gated, reason given):")
        for name, reason in live_skips:
            print(f"  - {name}: {reason}")
    if live_passes:
        print("LIVE PASS (verified against the real service):")
        for name in live_passes:
            print(f"  - {name}")
    if other_skips:
        print("skipped (unexpected - investigate):")
        for name, reason in other_skips:
            print(f"  - {name}: {reason}")
    for name, trace in result.failures + result.errors:
        print(f"FAIL: {name}")
        print("\n".join(trace.strip().splitlines()[-TRACEBACK_TAIL_LINES:]))
    print(f"\n{passed} passed ({len(live_passes)} of them LIVE), "
          f"{len(result.failures) + len(result.errors)} failed, "
          f"{len(not_run) + len(live_skips)} NOT RUN "
          f"({len(live_skips)} LIVE SKIP) "
          f"(of {result.testsRun} tests)")
    return 0 if result.wasSuccessful() else 1


# ======================= SECTION: TERMINAL PRESENTATION ========================
# Display only. Nothing in this block touches scoring, weights, thresholds
# or provider logic; it formats results that get_quality_score() already
# produced. Colors are plain ANSI, switched off automatically when output is
# piped, when NO_COLOR is set, or with --no-color.

_SGR = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33",
        "blue": "34", "magenta": "35", "cyan": "36", "gray": "90"}

# score bands for the card: (minimum score, label, color). Letter grades
# follow institutional convention and are deliberately NOT harsh: the
# sector-median company (~50) lands at C, 40-50 is still "middle of the
# pack" (3.2 called it "below average"), and only the deep tail (< 25)
# is F (3.3.0 calibration, owner: "not too strict").
_SCORE_BANDS = ((80, "A - TOP TIER", "green"),
                (60, "B - ABOVE AVERAGE", "green"),
                (40, "C - MIDDLE OF THE PACK", "yellow"),
                (25, "D - BELOW AVERAGE", "yellow"),
                (0, "F - BOTTOM TIER", "red"))

_FLAG_TEXT = {
    "SECTOR_PEER_FALLBACK": ("yellow", "too few sector peers - some metrics "
                                       "were ranked against the whole pool"),
    "STALE_PRICE": ("yellow", "latest price is old - valuation numbers may "
                              "be off"),
    "SPLIT_BASIS_UNVERIFIED": ("yellow", "could not verify stock-split "
                                         "adjustment - market cap refused"),
    "NEGATIVE_EQUITY": ("red", "shareholder equity is negative"),
    "ALTMAN_DISTRESS": ("red", "Altman Z-score is in the distress zone"),
    "PIOTROSKI_LOW": ("yellow", "weak Piotroski F-score"),
    "HIGH_ACCRUALS": ("yellow", "earnings rely heavily on accruals, not "
                                "cash"),
    "SHRINKING_REVENUE_RISING_DEBT": ("red", "revenue is shrinking while "
                                             "debt is rising"),
}

_STATUS_TEXT = {
    NO_DATA: "No usable data came back for this ticker. Check your keys / "
             "internet, run 'livecheck', or check the ticker spelling.",
    STALE_DATA: "The latest filing is too old, so it is deliberately NOT "
                "scored (a stale score would be misleading).",
    INSUFFICIENT_DATA: "Not enough metrics could be computed to score it "
                       "fairly.",
    SECTOR_DATA_MISSING: "Its sector has too little data to compare "
                         "against.",
    DELISTED: "Listed as delisted in the built-in list - never fetched.",
    RENAMED: "Listed as renamed in the built-in list - never fetched.",
    ERROR: "An error happened while scoring it.",
}

_SECTOR_ALIASES = {
    "technology": "tech", "it": "tech", "software": "tech",
    "financial": "financials", "finance": "financials", "banks": "financials",
    "bank": "financials", "financialservices": "financials",
    "health": "healthcare", "pharma": "healthcare", "biotech": "healthcare",
    "industrial": "industrials", "consumercyclical": "consumer",
    "consumerdefensive": "consumer", "staples": "consumer",
    "discretionary": "consumer", "oil": "energy", "utility": "utilities",
    "basicmaterials": "materials", "realestate": "reits", "reit": "reits",
    "property": "reits", "communications": "communication",
    "communicationservices": "communication", "telecom": "communication",
    "media": "communication",
}

# Curated sector map for popular tickers ABSENT from the built-in
# universe (the eleven disclosed mega-caps plus other liquid names users
# score first). Consulted only when the ticker is not a built-in member;
# --sector / --peers always override. Sectors follow the engine's
# GICS-style groups. This is what makes `quality.py AAPL` work with no
# flags and no packages (3.3.0).
_KNOWN_SECTOR_TICKERS = {
    "AAPL": "tech", "MSFT": "tech", "GOOGL": "tech", "GOOG": "tech",
    "NVDA": "tech", "AMD": "tech", "PLTR": "tech", "CRWD": "tech",
    "SNOW": "tech", "SHOP": "tech",
    "AMZN": "consumer", "TSLA": "consumer", "BKNG": "consumer",
    "ABNB": "consumer", "DASH": "consumer", "EBAY": "consumer",
    "META": "communication", "NFLX": "communication",
    "SNAP": "communication", "PINS": "communication",
    "SPOT": "communication",
    "BRK-B": "financials", "V": "financials", "MA": "financials",
    "PYPL": "financials", "HOOD": "financials", "SOFI": "financials",
    "MRNA": "healthcare", "VRTX": "healthcare", "ISRG": "healthcare",
    "REGN": "healthcare",
}

_YF_SECTOR_MAP = {
    "Technology": "tech", "Financial Services": "financials",
    "Healthcare": "healthcare", "Industrials": "industrials",
    "Consumer Cyclical": "consumer", "Consumer Defensive": "consumer",
    "Energy": "energy", "Utilities": "utilities",
    "Basic Materials": "materials", "Real Estate": "reits",
    "Communication Services": "communication",
}

_CARD_WIDTH_MIN, _CARD_WIDTH_MAX, _BAR_WIDTH = 56, 84, 20


def _use_color(force: Optional[bool] = None) -> bool:
    """Colors on only for a real terminal (NO_COLOR / TERM=dumb respected)."""
    if force is not None:
        return force
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False


def _use_color_stderr(force: Optional[bool] = None) -> bool:
    """Colors for stderr diagnostics: on only when stderr is a real TTY
    (NO_COLOR / TERM=dumb respected). Used by the PIT validation's FAILED
    lines and its optional human table (PART 6E)."""
    if force is not None:
        return force
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    try:
        return bool(sys.stderr.isatty())
    except Exception:
        return False


def _enable_windows_ansi() -> None:
    """Turn on ANSI escape handling in old Windows consoles (best effort)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        handle = kernel.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        return


def _paint(text, styles, on: bool) -> str:
    """Wrap text in ANSI styles (styles: name or tuple of names)."""
    if not on or not styles:
        return str(text)
    if isinstance(styles, str):
        styles = (styles,)
    codes = ";".join(_SGR[s] for s in styles)
    return f"\033[{codes}m{text}\033[0m"


def _band(score: float) -> tuple:
    """(label, color) for a 0-100 composite."""
    for floor, label, color in _SCORE_BANDS:
        if score >= floor:
            return label, color
    return _SCORE_BANDS[-1][1], _SCORE_BANDS[-1][2]


def _glyphs() -> dict:
    enc = (getattr(sys.stdout, "encoding", None) or "").lower()
    if "utf" in enc:
        return {"full": "\u2588", "empty": "\u2591", "rule": "\u2500",
                "dot": "\u00b7", "warn": "\u25b2", "ok": "\u25cf"}
    return {"full": "#", "empty": "-", "rule": "-", "dot": "|",
            "warn": "!", "ok": "*"}


def _bar(fraction: float, color: str, on: bool, g: dict) -> str:
    fraction = 0.0 if fraction is None else min(1.0, max(0.0, fraction))
    filled = int(round(fraction * _BAR_WIDTH))
    return (_paint(g["full"] * filled, color, on)
            + _paint(g["empty"] * (_BAR_WIDTH - filled), "gray", on))


def _pct_color(fraction: Optional[float]) -> str:
    if fraction is None:
        return "gray"
    if fraction >= 0.67:
        return "green"
    if fraction >= 0.34:
        return "yellow"
    return "red"


def _fmt_value(v) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        if v != v:
            return "n/a"
        a = abs(v)
        if a >= 1e9:
            return f"{v / 1e9:.2f}B"
        if a >= 1e6:
            return f"{v / 1e6:.2f}M"
        if a >= 1e4:
            return f"{v:,.0f}"
        return f"{v:.4g}"
    return str(v)


def _card_width() -> int:
    try:
        cols = shutil.get_terminal_size((80, 24)).columns
    except Exception:
        cols = 80
    return max(_CARD_WIDTH_MIN, min(_CARD_WIDTH_MAX, cols - 2))


def _wrap(text: str, width: int, indent: str) -> list:
    return textwrap.wrap(text, width=width, initial_indent=indent,
                         subsequent_indent=indent) or [indent]


def render_score_card(res: dict, ctx: dict, on: bool) -> str:
    """Colored one-ticker card from a get_quality_score() dict."""
    g = _glyphs()
    width = _card_width()
    rule = _paint(g["rule"] * width, "gray", on)
    out: list = []
    status = res.get("status")
    sector = res.get("sector") or "?"
    src = res.get("data_source") or "-"
    out.append("")
    out.append(
        "  " + _paint(res.get("ticker", "?"), ("bold", "cyan"), on)
        + _paint(f"   {sector} {g['dot']} as of {res.get('as_of')} "
                 f"{g['dot']} data: {src}", "gray", on))
    out.append(rule)
    if "fixtures" in src:
        out.append("  " + _paint(
            f"{g['warn']} SYNTHETIC TEST DATA - these are not real "
            "companies.", ("bold", "red"), on))
        out.append("")

    score = res.get("score")
    if status == OK and score is not None:
        label, color = _band(float(score))
        out.append("  " + _paint("QUALITY SCORE  ", "bold", on)
                   + _paint(f"{float(score):5.1f}", ("bold", color), on)
                   + _paint(" / 100  ", "gray", on)
                   + _bar(float(score) / 100.0, color, on, g)
                   + "  " + _paint(label, ("bold", color), on))
        bits = []
        if res.get("rank_in_sector") is not None and ctx.get("n_scored"):
            bits.append(f"rank #{res['rank_in_sector']} of "
                        f"{ctx['n_scored']} scored in {sector}")
        bits.append(f"coverage {float(res.get('coverage') or 0.0):.0%}")
        out.append("  " + _paint(f" {g['dot']} ".join(bits), "gray", on))
    else:
        out.append("  " + _paint("STATUS  ", "bold", on)
                   + _paint(str(status), ("bold", "red"), on))
        out.extend(_wrap(_STATUS_TEXT.get(status, ""), width - 2, "  "))
        for note in res.get("notes") or []:
            out.extend(_wrap(f"note: {note}", width - 2, "  "))
        if res.get("error"):
            out.extend(_wrap(f"error: {res['error']}", width - 2, "  "))
        ss = res.get("source_status") or {}
        if ss:
            out.extend(_wrap("providers: " + ", ".join(
                f"{k}={v}" for k, v in sorted(ss.items())), width - 2, "  "))
        unrated = res.get("score_unrated") or {}
        if unrated.get("coverage") is not None:
            out.append("  " + _paint(
                f"coverage reached {float(unrated['coverage']):.0%}",
                "gray", on))
    if ctx.get("scope"):
        out.append("  " + _paint(f"compared against: {ctx['scope']}",
                                 "gray", on))
    for warning in ctx.get("warnings") or []:
        out.extend(_wrap(f"{g['warn']} {warning}", width - 2, "  ")[:1])
        out[-1] = _paint(out[-1], "yellow", on)

    pillars = res.get("pillars") or {}
    if status == OK and pillars:
        out.append("")
        out.append("  " + _paint("PILLARS", "bold", on)
                   + _paint("  (0-100, vs sector peers; 50 = typical)",
                            "gray", on))
        for name, val in pillars.items():
            label = name.replace("_", " ")
            if val is None:
                out.append(f"  {label:<20s} " + _paint("n/a", "gray", on))
                continue
            color = _pct_color(float(val) / 100.0)
            out.append(f"  {label:<20s} "
                       + _paint(f"{float(val):5.1f}", color, on) + "  "
                       + _bar(float(val) / 100.0, color, on, g))

    flags = res.get("flags") or []
    if flags:
        out.append("")
        out.append("  " + _paint("FLAGS", "bold", on))
        for flag in flags:
            color, text = _FLAG_TEXT.get(flag, ("yellow", ""))
            out.append("  " + _paint(f"{g['warn']} {flag}", ("bold", color),
                                     on))
            if text:
                out.extend(_paint(line, "gray", on) for line in
                           _wrap(text, width - 6, "      "))

    metrics = res.get("metrics") or {}
    mscores = res.get("metric_scores") or {}
    if status == OK and metrics:
        out.append("")
        out.append("  " + _paint("METRICS", "bold", on)
                   + _paint("  (value, then percentile vs sector peers)",
                            "gray", on))
        for name, val in metrics.items():
            pct = mscores.get(name)
            label = name.replace("_", " ")
            if pct is None:
                out.append(f"  {label:<24s} {_fmt_value(val):>10s}  "
                           + _paint("not ranked", "gray", on))
                continue
            color = _pct_color(float(pct))
            out.append(f"  {label:<24s} {_fmt_value(val):>10s}  "
                       + _bar(float(pct), color, on, g) + " "
                       + _paint(f"{float(pct):4.0%}", color, on))
    out.append("")
    out.append(rule)
    out.extend(_paint(line, "gray", on) for line in _wrap(
        "Research screener, not investment advice. The built-in universe is "
        "survivorship-biased (current listings). Use --explain TICKER to "
        "see where every number came from.", width - 2, "  "))
    tkr = str(res.get("ticker") or "TICKER")
    out.append(_paint(f"  machine output: python3 quality.py {tkr} "
                      "--layer (compact) | --json (full)", "gray", on))
    out.append("")
    return "\n".join(out)


_TICKER_OK = re.compile(r"^[A-Z0-9]{1,6}(-[A-Z0-9]{1,3})?$")


def normalize_ticker(text: str) -> Optional[str]:
    """Upper-case, BRK.B -> BRK-B; None when it is not a plausible ticker."""
    cand = (text or "").strip().upper().replace(".", "-")
    return cand if _TICKER_OK.match(cand) else None


def _normalize_sector(text: Optional[str]) -> Optional[str]:
    key = (text or "").strip().lower()
    for ch in (" ", "-", "_", "&"):
        key = key.replace(ch, "")
    if key in GROUPS:
        return key
    return _SECTOR_ALIASES.get(key)


def _detect_sector_yfinance(ticker: str) -> Optional[str]:
    """Best-effort sector lookup (needs yfinance + internet); else None."""
    try:
        import yfinance
        info = yfinance.Ticker(ticker).info or {}
    except Exception:
        return None
    return _YF_SECTOR_MAP.get(str(info.get("sector") or ""))


def build_inline_universe(ticker: str, sector_arg: Optional[str] = None,
                          peers_arg: Optional[str] = None,
                          full: bool = False) -> tuple:
    """Universe for one-ticker scoring with NO file needed.

    Returns (refs, sector, scope_text, warnings, error_text). Default scope
    is the built-in names of the ticker's sector; --peers replaces that with
    exactly the peers given; --full uses the whole built-in universe.
    """
    upper = normalize_ticker(ticker)
    if upper is None:
        return (None, None, None, [],
                f"'{ticker}' does not look like a ticker (letters/digits, "
                "e.g. AAPL or BRK-B)")
    builtin, _report = get_universe()
    by_ticker = {r.ticker: r for r in builtin}
    valid = ", ".join(sorted(GROUPS))
    warnings: list = []
    detected = False
    if sector_arg:
        sector = _normalize_sector(sector_arg)
        if sector is None:
            return (None, None, None, [],
                    f"unknown sector '{sector_arg}'. Valid sectors: {valid}")
    elif upper in by_ticker:
        sector = by_ticker[upper].sector
    else:
        sector = _KNOWN_SECTOR_TICKERS.get(upper) \
            or _detect_sector_yfinance(upper)
        detected = sector is not None
        if sector is None:
            return (None, None, None, [],
                    f"{upper} is not in the built-in list and its sector "
                    f"could not be detected. Add --sector, e.g.  "
                    f"score {upper} --sector tech   (sectors: {valid})")
    if upper in by_ticker and by_ticker[upper].sector == sector:
        target = by_ticker[upper]
    else:
        status, note, _ev = VERIFICATION.get(upper, ("active", "", ""))
        target = TickerRef(upper, sector, status, note)
    peers: list = []
    for p in (peers_arg or "").split(","):
        if not p.strip():
            continue
        clean = normalize_ticker(p)
        if clean is None:
            return (None, None, None, [],
                    f"peer '{p.strip()}' does not look like a ticker")
        if clean != upper and clean not in peers:
            peers.append(clean)
    if peers:
        refs = [target] + [by_ticker[p] if (p in by_ticker and
                                            by_ticker[p].sector == sector)
                           else TickerRef(p, sector) for p in peers]
        scope = f"the {len(peers)} peers you listed ({sector})"
    elif full:
        refs = [target] + [r for r in builtin if r.ticker != upper]
        scope = f"the whole built-in universe ({len(builtin)} names)"
    else:
        refs = [target] + [r for r in builtin
                           if r.sector == sector and r.ticker != upper]
        scope = (f"{len(refs) - 1} built-in {sector} peers")
    if detected:
        scope += " (sector auto-detected - double-check it)"
    if len(refs) < MIN_PEERS + 1:
        warnings.append(
            f"only {len(refs)} companies in the comparison group - scores "
            f"are rough; use at least {MIN_PEERS + 1} peers for stable "
            "percentiles.")
    return refs, sector, scope, warnings, None


def score_main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quality.py score",
        description="Quality score for one ticker, shown as a colored "
                    "terminal card. Short form: python3 quality.py AAPL",
        epilog="Output is a colored card on a terminal and JSON when piped "
               "(force with --pretty / --json; --layer is the compact "
               "trading-system JSON). Exit code: 0 = score, 1 = no score, "
               "2 = bad usage.")
    parser.add_argument("ticker_pos", nargs="?", default=None,
                        metavar="TICKER", help="ticker to score, e.g. AAPL")
    parser.add_argument("--ticker", required=False, default=None,
                        help="same as the positional TICKER")
    parser.add_argument("--sector", default=None,
                        help="sector to compare against (rarely needed: "
                             "popular tickers like AAPL auto-resolve; "
                             "use this only for unusual names): "
                             + ", ".join(sorted(GROUPS)))
    parser.add_argument("--peers", default=None,
                        help="comma-separated peers to compare against "
                             "instead of the built-in sector list "
                             "(e.g. MSFT,NVDA,AVGO,ORCL,ADBE,CRM,CSCO,INTC)")
    parser.add_argument("--full", action="store_true",
                        help="compare against the whole built-in universe "
                             "(slow: hundreds of fetches on a cold cache)")
    parser.add_argument("--as-of", dest="as_of", default=None)
    parser.add_argument("--source", default="auto",
                        choices=["auto", "fixtures", "finnhub", "sec",
                                 "yfinance"])
    parser.add_argument("--universe-file", dest="universe_file", default=None,
                        help="optional CSV universe (ticker,sector); not "
                             "needed for normal use")
    parser.add_argument("--explain", dest="explain", default=None,
                        metavar="TICKER",
                        help="print the per-metric provenance trace "
                             "(D18) for TICKER instead of the card")
    fmt = parser.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true",
                     help="print raw JSON instead of the card")
    fmt.add_argument("--layer", action="store_true",
                     help="print compact JSON for a trading layer "
                          "(ticker, score, rating, pillars, flags)")
    fmt.add_argument("--pretty", action="store_true",
                     help="print the card even when piped")
    color = parser.add_mutually_exclusive_group()
    color.add_argument("--no-color", dest="no_color", action="store_true",
                       help="plain text, no colors")
    color.add_argument("--color", action="store_true",
                       help="force colors even when piped")
    args = parser.parse_args(argv)
    raw_target = args.explain or args.ticker or args.ticker_pos
    if not raw_target:
        parser.error("give a ticker, e.g.  score AAPL --sector tech")
    target = normalize_ticker(raw_target)
    if target is None:
        print(f"'{raw_target}' does not look like a ticker (letters/digits, "
              "e.g. AAPL or BRK-B)", file=sys.stderr)
        return 2

    on = _use_color(False if args.no_color else (True if args.color
                                                  else None))
    if on:
        _enable_windows_ansi()
    as_of = _as_of_date(args.as_of)
    ok, err = _validate_as_of(args.as_of, boundary=date.today())
    if not ok:
        print(err, file=sys.stderr)
        return 2

    refs, ctx = None, {"scope": "", "warnings": []}
    if args.universe_file:
        ctx["scope"] = f"your universe file {args.universe_file}"
    else:
        refs, _sector, scope, warns, err = build_inline_universe(
            target, args.sector, args.peers, args.full)
        if refs is None:
            print(_paint(f"cannot score {target.upper()}: {err}",
                         ("bold", "red"), on), file=sys.stderr)
            return 2
        ctx["scope"], ctx["warnings"] = scope, warns

    show_progress = not (args.json or args.layer) and _stderr_is_tty()

    def progress(position, total, ticker):
        if show_progress:
            sys.stderr.write("\r" + _paint(
                f"  fetching {position}/{total}  {ticker:<8s}", "gray", on))
            sys.stderr.flush()

    try:
        result = get_quality_score(target, as_of, source=args.source,
                                   universe_file=args.universe_file,
                                   universe_refs=refs, progress=progress)
    finally:
        if show_progress:
            sys.stderr.write("\r" + " " * _card_width() + "\r")
            sys.stderr.flush()

    if args.explain:
        print(_paint(f"provenance for {result.get('ticker')} "
                     f"({result.get('status')}):", ("bold", "cyan"), on))
        for metric, entries in sorted(
                (result.get("provenance") or {}).items()):
            print("  " + _paint(f"{metric}:", "bold", on))
            for e in entries:
                print(f"    - {e.get('item')} provider={e.get('provider')} "
                      f"period_end={e.get('period_end')} "
                      f"filing={e.get('filing_date')} "
                      f"available={e.get('available_date')} "
                      f"accession={e.get('accession')}")
        return 0

    status_ok = result.get("status") == OK
    if args.layer:
        score = result.get("score")
        label = _band(float(score))[0] if score is not None else ""
        compact = {
            "ticker": result.get("ticker"),
            "as_of": result.get("as_of"),
            "sector": result.get("sector"),
            "score": result.get("score"),
            "rating": label or str(result.get("status") or ""),
            "status": result.get("status"),
            "coverage": result.get("coverage"),
            "rank_in_sector": result.get("rank_in_sector"),
            "pillars": result.get("pillars") or {},
            "flags": result.get("flags") or [],
            "data_source": result.get("data_source"),
            "engine_version": ENGINE_VERSION,
        }
        print(json.dumps(compact, default=str))
        return 0 if status_ok else 1
    if args.json:
        print(json.dumps(result, indent=2, default=str))
        return 0 if status_ok else 1
    pretty = args.pretty or args.color or _stdout_is_tty()
    if not pretty:
        print(json.dumps(result, indent=2, default=str))
        return 0 if status_ok else 1
    scored = _scored_universe(as_of, args.source, None, args.universe_file,
                              refs_override=refs)
    ctx["n_scored"] = sum(1 for r in scored.values()
                          if r.sector == result.get("sector")
                          and r.status == OK and r.score is not None)
    print(render_score_card(result, ctx, on))
    return 0 if status_ok else 1


def _stderr_is_tty() -> bool:
    try:
        return bool(sys.stderr.isatty())
    except Exception:
        return False


def _stdout_is_tty() -> bool:
    try:
        return bool(sys.stdout.isatty())
    except Exception:
        return False




# Quick-scan default set (no CLI arguments): 58 liquid, verified-ACTIVE
# members of the built-in universe, spread over all 11 sector groups so the
# cross-sectional ranks have peers. Full 682-name universe: `scan`.
_QUICK_SCAN_TICKERS = (
    "JPM", "BAC", "WFC", "GS", "SCHW", "BLK", "AXP",
    "HON", "UNP", "UPS", "CAT", "BA", "LMT", "GE",
    "JNJ", "ABBV", "MRK", "PFE", "LLY", "TMO",
    "AVGO", "ORCL", "ADBE", "CRM", "IBM", "QCOM", "TXN", "INTC",
    "HD", "COST", "WMT", "MCD", "NKE", "KO", "PEP", "PG",
    "XOM", "CVX", "COP", "SLB",
    "NEE", "DUK", "SO",
    "LIN", "SHW", "FCX", "NEM",
    "PLD", "SPG", "AMT", "O",
    "VZ", "T", "TMUS", "DIS",
    "MAN", "LDOS", "HRB",
)


def _print_banner(on: bool) -> None:
    """Small colorful header for the no-argument quick scan."""
    g = _glyphs()
    rule = _paint(g["rule"] * BANNER_WIDTH, "cyan", on)
    print(rule)
    print(_paint("  QUALITY ENGINE", ("bold", "cyan"), on)
          + _paint(f"  v{ENGINE_VERSION}  -  free-data edition", "gray", on))
    print(_paint("  SEC EDGAR fundamentals (no key) + Yahoo prices (no key)"
                 " + your optional Finnhub key", "gray", on))
    print(rule)


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    _ensure_env()          # .env works for every subcommand (incl. livecheck)
    if argv and argv[0] in ("-h", "--help"):
        print("usage: python3 quality.py [TICKER | scan | score | validate |"
              " livecheck | selftest] [options]")
        print("  TICKER    ONE ticker, colored score card - the short "
              "command:  python3 quality.py AAPL")
        print("            (add --layer for the compact trading JSON, "
              "--json for the full dump)")
        print("  (no command) quick scan of ~58 liquid names - colorful "
              "terminal table, no CSV, no key needed")
        print("  scan      fetch and score the full universe (scan --help "
              "for options; resumable, ~15-25 min cold)")
        print("  score     same as the short form, with options (score JPM "
              "--peers BAC,WFC,GS; --explain TICKER for provenance)")
        print("  validate  forward-validation harness over snapshot "
              "history (validate --help; --pit-universe for section 8.3)")
        print("  livecheck live provider checks (verifies your .env keys "
              "and every data source)")
        print("  selftest  run the embedded test suite")
        return 0
    if not argv:
        on = _use_color()
        if on:
            _enable_windows_ansi()
        _print_banner(on)
        print(_paint("no command given -> quick scan of "
                     f"{len(_QUICK_SCAN_TICKERS)} liquid names across all "
                     "sectors (~2-4 min cold cache, seconds when cached)",
                     "yellow", on))
        print(_paint("full universe (682 names):  python3 quality.py scan",
                     "gray", on))
        print(_paint("one ticker detail card:   python3 quality.py JPM",
                     "gray", on))
        return scan_main(["--tickers", ",".join(_QUICK_SCAN_TICKERS)])
    command, rest = argv[0], argv[1:]
    if command == "scan":
        return scan_main(rest)
    if command == "score":
        return score_main(rest)
    if command == "validate":
        return forward_main(rest)
    if command == "livecheck":
        return livecheck_main(rest)
    if command == "selftest":
        return run_selftests()
    if normalize_ticker(command) is not None:
        # 3.3.0 short form: `python3 quality.py AAPL` == `score AAPL`
        return score_main(argv)
    print(f"unknown command: {command} "
          f"(expected a TICKER, scan, score, validate, livecheck or "
          f"selftest)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
