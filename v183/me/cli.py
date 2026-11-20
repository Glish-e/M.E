"""me/cli.py — the CLI surface (v1.8.0 split from master.py §7): the
argparse parser (bad usage exits 64, never 2), the --mode quick/
standard/deep presets and the namespace validation. Every existing flag
is unchanged; new flags are additions only (R16)."""
from __future__ import annotations

import argparse
from datetime import date

from me.core import CONFIG, _finite
from me.errors import MasterError



# ════════════════════════════════════════════════════════════════════════
#  § 7 · CLI — argparse (flags only + tickers), exit codes, --check, --selftest
# ════════════════════════════════════════════════════════════════════════
class MasterParser(argparse.ArgumentParser):
    """argparse, but bad usage exits 64 (never 2)."""

    def error(self, message: str) -> None:                       # noqa: D102
        raise MasterError(f"{self.prog}: {message}", 2)


def build_parser() -> MasterParser:
    """Build the full CLI parser: every flag with its help text, the
    mode presets' defaults, and exit-code-64 usage errors (MasterParser
    overrides argparse's error()). One parser, one source of flags."""
    p = MasterParser(prog="master.py", description=__doc__.splitlines()[0])
    # v1.8.0 (W3): --help grouped by task (same flags, same defaults,
    # same exit codes — a display regrouping only, R16 additive).
    g_run = p.add_argument_group("run selection:")
    g_depth = p.add_argument_group("depth & speed:")
    g_data = p.add_argument_group("data source:")
    g_layers = p.add_argument_group("layers & fusion:")
    g_out = p.add_argument_group("output & format:")
    g_diag = p.add_argument_group("diagnostics:")
    g_bt = p.add_argument_group("backtest & ml:")
    g_run.add_argument("tickers", nargs="*", metavar="TICKER")
    g_run.add_argument("--tickers", dest="tickers_csv", action="append", default=[],
                   metavar="A,B,C", help="comma list, repeatable")
    g_run.add_argument("--watchlist", metavar="FILE", help="one per line or CSV: ticker[,sector]")
    g_depth.add_argument("--mode", choices=tuple(CONFIG["NET_MODES"]) + tuple(CONFIG["MODES"]),
                   default=None,
                   help="auto (default) | online | offline = the DATA mode: auto "
                        "probes once (2 s) and picks; offline serves cached "
                        "truth age-labelled, zero sockets; online refreshes "
                        "stale/missing items only. quick | standard | deep = "
                        "the DEPTH presets (they keep their v1.1.0 meaning "
                        "and default the data mode to auto). v1.8.2: the "
                        "data mode also has its own --net flag; --mode keeps "
                        "working exactly as before")
    g_data.add_argument("--net", choices=tuple(CONFIG["NET_MODES"]), default=None,
                   dest="net_flag",
                   help="v1.8.2 (W5): the DATA mode as its own flag "
                        "(auto|online|offline) — combines freely with the "
                        "depth presets (--mode quick|standard|deep). --net "
                        "online keeps the exit-3 probe contract. A usage "
                        "error (exit 2) if combined with --mode "
                        "auto/online/offline or --offline (two data modes)")
    g_depth.add_argument("--warm", action="store_true",
                   help="cache-fill run: macro+quality only, long budget "
                        "(WARM_TIMEOUT_S); fills the disk caches so the next "
                        "standard run is fast. Combine with --mode quick to "
                        "warm only the watchlist names")
    g_run.add_argument("--as-of", metavar="YYYY-MM-DD", help="point-in-time run, no lookahead")
    g_run.add_argument("--top", type=int, default=CONFIG["DEFAULT_TOP"], metavar="N",
                   help=f"table rows shown (default {CONFIG['DEFAULT_TOP']})")
    g_run.add_argument("--min-conviction", type=float, default=CONFIG["DEFAULT_MIN_CONV"],
                   metavar="X", help="hide rows below this conviction (table/csv)")
    g_run.add_argument("--only", default="", metavar="L1,L2", help="macro|quality|earnings|ml|risk (comma list)")
    g_run.add_argument("--skip", default="", metavar="L1,L2", help="macro|quality|earnings|ml|risk (comma list)")
    g_layers.add_argument("--earnings-mode", choices=("off", "boost", "trigger"), default="boost",
                   help="off=skip L3 · boost (default)=score modifier + NOW chip · "
                        "trigger=plan LONG required for LONG")
    g_layers.add_argument("--ruleset", choices=("legacy", "v2"), default=None, metavar="R",
                   help="decision ruleset: legacy (default — missing-E x0.90 advantage, "
                        "rounded doors) or v2 (missing-E conservative fill, unrounded "
                        "doors). The header labels the active one.")
    g_layers.add_argument("--sizing", choices=("legacy", "vol_target"), default=None,
                   metavar="MODE",
                   help="risk sizer mode: legacy (default — eff/8 correlation cap) "
                        "or vol_target (opt-in — gross solved to RISK_VOL_TARGET, "
                        "looser-than-norm labelled)")
    g_depth.add_argument("--earnings-top", type=int, default=None, metavar="K",
                   help="earnings runs only on the top-K L1+L2 survivors "
                        "(mode default: quick 10 / standard 25 / deep 40; "
                        "0 = run L3 on nobody, an explicit idle)")
    g_layers.add_argument("--earnings-backtest", action="store_true",
                   help="opt-in full 90-day price backtest per ticker (slow)")
    g_depth.add_argument("--earnings-prefetch", choices=("none", "all"), default=None,
                   help="all: warm earnings histories at t=0 (<=60 names; deep mode default)")
    g_layers.add_argument("--ml-models", metavar="DIR", default=None,
                   dest="ml_models_dir",
                   help=f"ML overlay model directory (default {CONFIG['ML_MODELS_DIR']}; "
                        "written by ml_train.py; absent = UNTRAINED, never an error)")
    g_data.add_argument("--peers", choices=("builtin", "watchlist"), default=None,
                   help="quality comparison pool: builtin=sector peers (standard/deep) · "
                        "watchlist=the requested names only (quick; rough percentiles)")
    g_run.add_argument("--sector", action="append", default=[], metavar="T=GROUP",
                   help="pin a ticker's quality sector, e.g. --sector PLTR=tech")
    g_run.add_argument("--bucket", action="append", default=[], metavar="T=staples|discretionary",
                   help="split quality's merged consumer group for this ticker")
    g_run.add_argument("--sectors", metavar="G1,G2|all",
                   help="score the quality universe's active names in these sector "
                        "groups (e.g. --sectors tech,healthcare; 'all' = whole "
                        "universe — the plan banner sizes it first)")
    g_run.add_argument("--cap", choices=("any", "mega", "large", "mid", "small"),
                   default="any",
                   help="market-cap band filter — only when the universe refs "
                        "expose market caps (today they do not: honest 64, "
                        "never a silent no-op)")
    g_run.add_argument("--discover", type=int, default=None, metavar="N",
                   help="surface up to N names (sets --top; wins over it). "
                        "DISPLAY ONLY — percentile pools are never truncated; "
                        "fewer qualifiers than N is a loud warning")
    g_data.add_argument("--source", choices=("auto", "fixtures", "sec", "yfinance"), default="auto",
                   help="passed through to quality")
    g_data.add_argument("--offline", action="store_true",
                   help="alias of --mode offline: cached truth only, zero sockets, "
                        "ages labelled (never silently fresh)")
    g_data.add_argument("--cache-dir", metavar="DIR",
                   help="redirect quality+earnings caches (QE_DATA_DIR/QE_CACHE_DIR set "
                        "before import; meds' location is fixed)")
    g_depth.add_argument("--workers", type=int, default=CONFIG["DEFAULT_WORKERS"], metavar="N",
                   help=f"earnings pool (default {CONFIG['DEFAULT_WORKERS']}; keep <=4)")
    g_depth.add_argument("--timeout", type=float, default=None, metavar="SEC",
                   help="per-layer wall-clock budget (mode default: quick 300 / "
                        "standard 900 / deep+warm 3600)")
    g_out.add_argument("--explain", metavar="TICKER", help="full per-layer breakdown for one ticker")
    g_out.add_argument("--json", action="store_true", help="one parseable JSON object on stdout")
    g_out.add_argument("--csv", metavar="FILE", help="opt-in CSV write (default run writes nothing)")
    g_out.add_argument("--md", metavar="FILE",
                       help="v1.8.0: also write a Markdown report beside the "
                            "terminal render (same filters as --csv)")
    g_out.add_argument("--html", metavar="FILE",
                       help="v1.8.0: also write an HTML report (offline-safe, "
                            "no external assets, same filters)")
    g_out.add_argument("--no-color", action="store_true",
                   help="colour OFF (same as --color never; deliberate, no "
                        "reason line)")
    g_out.add_argument("--color", choices=("auto", "always", "never"), default="auto",
                   help="colour switch: auto = TTY + env precedence "
                        "(NO_COLOR beats FORCE_COLOR, which beats TERM=dumb); "
                        "always beats NO_COLOR and works through pipes; never "
                        "= off. AUTO-off prints ONE dim reason line with the fix")
    g_out.add_argument("--plain", action="store_true",
                   help="no colour and no decoration beyond the box (equals "
                        "--no-color: the report adds no other decoration)")
    g_diag.add_argument("--debug", action="store_true",
                   help="print the traceback on unexpected errors (default: "
                        "one line, no traceback)")
    g_out.add_argument("--ascii", action="store_true", help="plain ASCII (# - | v * !) output")
    g_out.add_argument("--width", type=int, help=f"terminal width "
                   f"40..{int(CONFIG['MAX_TERM_WIDTH'])}")
    g_out.add_argument("--quiet", action="store_true", help="no [plan] banner, no live progress bar")
    g_out.add_argument("--verbose", action="store_true")
    g_diag.add_argument("--check", action="store_true", help="health probe: versions, env names, caches, tiny requests")
    g_diag.add_argument("--doctor", action="store_true",
                   help="ONE screen: engines+hashes, library versions, cache ages "
                        "per layer, network probe, ML head states, free disk, "
                        "and the single most useful NEXT action")
    g_diag.add_argument("--freeze", metavar="DIR",
                   help="after the run, write DIR/manifest.json (args, versions, "
                        "ENGINES hashes, provenance, ranking) + copy the run's "
                        "cache files (size-capped; exact for quick-mode runs)")
    g_diag.add_argument("--replay", metavar="DIR",
                   help="rerun FULLY OFFLINE from a freeze dir and verify the "
                        "ranking + convictions match its manifest (exit 65 on "
                        "any difference — reproducibility gate)")
    g_diag.add_argument("--selftest", action="store_true", help="stubbed unittest, no network (LIVE SKIP for live checks)")
    g_bt.add_argument("--backtest", action="store_true",
                   help="integration backtest: evaluate the ACTUAL M.E. "
                        "decisions recorded per month-end (or re-run them "
                        "via run_pipeline with --backtest-rerun) against "
                        "the dataset's forward labels, under the "
                        "preregistered conventions (10 bps/side, "
                        "next-open windows, cash zero)")
    g_bt.add_argument("--backtest-rerun", action="store_true",
                   help="re-decide every date with a DIRECT run_pipeline "
                        "call instead of the recorded harvests (online "
                        "behaviour; writes fresh date records)")
    g_bt.add_argument("--backtest-dataset", metavar="NPZ",
                   default=None, help="dataset to backtest "
                   "(default ml_data/dataset_v1.npz)")
    g_bt.add_argument("--backtest-out", metavar="JSON", default=None,
                   help="report JSON path (default "
                        "evidence/phase6_backtest.json; the report lands "
                        "beside it)")
    g_bt.add_argument("--bt-start", metavar="YYYY-MM-DD", default=None,
                   help="v1.8.0: evaluate a SUB-WINDOW of the dataset "
                        "(month-end) — descriptive only (R19), printed "
                        "beside the full-span numbers, never a verdict")
    g_bt.add_argument("--bt-end", metavar="YYYY-MM-DD", default=None,
                   help="v1.8.0: window end month-end (with --bt-start; "
                        "either flag may be used alone)")
    g_bt.add_argument("--bt-breaker", action="store_true", default=False,
                   help="v1.8.0 (W5): opt-in drawdown circuit-breaker what-if "
                        "on the net equity curve (RISK_DD_BREAKER_DD "
                        "threshold, RISK_DD_BREAKER_COOLDOWN_W cooldown) — "
                        "descriptive, never a verdict")
    g_bt.add_argument("--bt-spy", metavar="FILE", default=None,
                   help="v1.8.0 (W5): owner-supplied SPY monthly series "
                        "(scripts/owner_fetch_spy.py writes it) — adds SPY "
                        "window returns, LONG-minus-SPY excess, and (real "
                        "series only) answers prereg gate 3's SPY half "
                        "(v1.8.1 F1 wiring; SYNTHETIC files never do)")
    g_bt.add_argument("--bt-ablate", metavar="MODE", default=None,
                   choices=["macro_cap", "macro_mult", "macro_all"],
                   help="v1.8.3 (F6): opt-in ablation over the RECORDED "
                        "decisions (ml_data/cache/dates/*.json; no "
                        "re-decisions, no network): macro_cap counts "
                        "defensive-regime demoted WATCH rows (tilt<0, "
                        "conviction>=ACTION_LONG_AT) as LONG; macro_mult "
                        "rescales conviction by 1/(1+0.10*tilt) and "
                        "re-derives the action; macro_all applies both. "
                        "Prints n and the episode-count disclosure beside "
                        "every number — a what-if, never a verdict")
    g_run.add_argument("--strict", action="store_true", default=False,
                   help="v1.8.1 (F7): strict exit policy — a degraded "
                        "(warning) run exits 2 (fail fast in CI); NO-GO 4 "
                        "and usage 2 unchanged. Default = the documented "
                        "contract (degraded = 1)")
    g_run.add_argument("--lenient", action="store_true", default=False,
                   help="v1.8.1 (F7): lenient exit policy — a produced "
                        "result with warnings exits 0 (warnings still "
                        "listed; NO-GO 4 and usage 2 are NEVER forgiven)")
    g_diag.add_argument("--retry-failed", action="store_true", default=False,
                   help="v1.8.1 (N9): re-fetch ONLY the LAST run's "
                        "failed transient items (reads "
                        "data/fetch_ledger.jsonl; permanent 404s never "
                        "retried; healthy items never rerun) and update "
                        "the engine caches — then rerun master normally")
    g_diag.add_argument("--retry-failed-path", metavar="JSONL", default=None,
                   help="v1.8.1 (N9): the ledger to read for --retry-failed "
                        "(default CONFIG FETCH_LEDGER_PATH)")
    g_diag.add_argument("--version", action="store_true")
    p.epilog = (
        "examples (all executed for the RUNBOOK; see it for real outputs):\n"
        "  python3 master.py                          default watchlist, auto net mode\n"
        "  python3 master.py --mode offline           cached truth, zero sockets, ages shown\n"
        "  python3 master.py MU NVDA AAPL             three names, standard depth\n"
        "  python3 master.py --warm                   fill macro+quality caches (then rerun)\n"
        "  python3 master.py NEE --explain NEE        one name, per-layer breakdown\n"
        "  python3 master.py MU NVDA --json           machine-readable payload\n"
        "  python3 master.py --doctor                 one-screen health check\n"
        "  python3 master.py --mode quick --freeze /tmp/f1 && python3 master.py --replay /tmp/f1")
    p.formatter_class = argparse.RawDescriptionHelpFormatter
    return p


def _apply_mode(ns: argparse.Namespace) -> argparse.Namespace:
    """v1.1.0: fill the mode-driven defaults ONCE, right after parsing
    (idempotent — explicit flags always win, so tests/direct run_pipeline
    callers can call it again safely). --warm selects macro+quality and the
    long budget; a --skip that removes one of them is honoured.
    Final phase (§4): --mode carries EITHER a depth preset (quick/standard/
    deep — unchanged v1.1.0 semantics, data mode defaults to auto) OR a
    data mode (auto/online/offline — depth defaults to standard). --offline
    stays an alias of --mode offline.
    v1.8.2 (W5): --net {auto,online,offline} is the separate data-mode flag;
    --mode is untouched (compatibility). Two data-mode sources (--net with
    --mode auto/online/offline, or --net with --offline) are a CLEAR exit-2
    usage error, never a silent precedence guess."""
    net_flag = getattr(ns, "net_flag", None)
    if net_flag is not None:
        # conflict checks BEFORE the mode default fill: a bare --net must
        # never be reported as conflicting with --mode's implicit default
        # (nor with the fill a previous idempotent _apply_mode call made —
        # run_pipeline applies mode defaults a second time)
        m = getattr(ns, "mode", None)
        if m is not None and m in CONFIG["NET_MODES"] \
                and not getattr(ns, "_mode_defaulted", False):
            raise MasterError(
                f"--net {net_flag} and --mode {m} both set the data mode — "
                "pass a depth preset to --mode (quick|standard|deep) and "
                "the data mode to --net, or use just one of the two flags", 2)
        if getattr(ns, "offline", False):
            raise MasterError(
                f"--net {net_flag} and --offline both set the data mode — "
                "pick one (e.g. --net offline alone)", 2)
    if getattr(ns, "mode", None) is None:
        ns.mode = CONFIG["NET_MODE_DEFAULT"]
        ns._mode_defaulted = True       # idempotency marker (see above)
    # split the two halves of --mode (depth preset vs data mode)
    if ns.mode in CONFIG["NET_MODES"]:
        ns.net = ns.mode
        ns.depth = CONFIG["MODE_DEFAULT"]
    else:
        ns.depth = ns.mode
        ns.net = "auto"
    if net_flag is not None:
        # v1.8.2 (W5): the explicit --net flag wins over the implicit
        # 'auto' a depth preset implies (a conflicting --mode data mode
        # was already rejected above)
        ns.net = net_flag
    if getattr(ns, "offline", False):
        ns.net = "offline"
    if getattr(ns, "warm", False) and not getattr(ns, "only", ""):
        # --warm fills caches: it makes no sense to warm OFFLINE (nothing
        # would be fetched) — the depth preset stays, the data mode must be
        # online-capable. Explicit --mode offline + --warm is a usage error.
        if ns.net == "offline":
            raise MasterError("--warm fills caches from the network — combine with "
                              "--mode auto/online, not --mode offline", 2)
    preset = CONFIG["MODES"].get(ns.depth) or CONFIG["MODES"][CONFIG["MODE_DEFAULT"]]
    if ns.depth == "standard":
        # v1.4.1 (B6) port: the standard preset RE-RESOLVES from the two
        # CONFIG keys at apply time (not just at import), so a changed
        # key is honoured on the next run and the key/preset can never
        # drift apart — the monkeypatch test proves the keys are live.
        preset = dict(preset,
                      timeout=float(CONFIG["LAYER_TIMEOUT_S"]),
                      earnings_top=int(CONFIG["EARNINGS_TOP_K"]))
    warm = bool(getattr(ns, "warm", False))
    if warm and not getattr(ns, "only", ""):
        skip = {s.strip() for s in (getattr(ns, "skip", "") or "").split(",") if s.strip()}
        ns.only = ",".join(n for n in ("macro", "quality") if n not in skip)
        if not ns.only:
            # P2-7: an EMPTY only-set is explicit: --warm exists to fill the
            # macro+quality caches; skipping both leaves nothing to warm, and
            # silently running EVERYTHING (earnings included) is wrong.
            raise MasterError("--warm with macro+quality both skipped selects nothing "
                              "to warm — drop --skip, keep at least one, or drop --warm", 2)
    if getattr(ns, "timeout", None) is None:
        ns.timeout = CONFIG["WARM_TIMEOUT_S"] if warm else preset["timeout"]
    if getattr(ns, "peers", None) is None:
        ns.peers = preset["peers"]
    if getattr(ns, "earnings_top", None) is None:
        ns.earnings_top = preset["earnings_top"]
    if getattr(ns, "earnings_prefetch", None) is None:
        ns.earnings_prefetch = preset["earnings_prefetch"]
    # phase 4 (P-1/P-2): the two opt-in selectors resolve from their CONFIG
    # keys at apply time (an owner CONFIG flip changes the default; an
    # explicit --ruleset/--sizing always wins). Identical pattern to
    # LAYER_TIMEOUT_S / EARNINGS_TOP_K so key and preset cannot drift.
    if getattr(ns, "ruleset", None) is None:
        ns.ruleset = str(CONFIG["RULESET"])
    if getattr(ns, "sizing", None) is None:
        ns.sizing = str(CONFIG["RISK_SIZING_MODE"])
    if getattr(ns, "discover", None) is not None:
        # phase 3: --discover sizes the table (never the pools); it wins over
        # --top so the wizard and the flag can never disagree.
        ns.top = int(ns.discover)
    return ns


def _validate_ns(ns: argparse.Namespace) -> None:
    """Fail fast on bad values, BEFORE any network call or engine import.
    Mode-driven defaults may still be unset here (None) — _apply_mode fills
    them; the range checks only run on explicitly passed values."""
    if ns.as_of:
        try:
            d = date.fromisoformat(ns.as_of)
        except ValueError:
            raise MasterError(f"--as-of {ns.as_of!r}: expected YYYY-MM-DD", 2) from None
        if d > date.today():
            raise MasterError(f"--as-of {ns.as_of} is in the future "
                              "(quality rejects future dates; no lookahead)", 2)
    if ns.json and ns.explain:
        raise MasterError("--explain is a terminal view; incompatible with --json", 2)
    if ns.top < 1:
        raise MasterError("--top must be >= 1", 2)
    mc = _finite(ns.min_conviction, 0.0, 100.0)          # P1-1: nan/inf -> 64
    if mc is None:
        raise MasterError(f"--min-conviction must be a number in 0..100 "
                          f"(got {ns.min_conviction!r})", 2)
    ns.min_conviction = mc
    if ns.timeout is not None:                           # P1-1: nan/inf -> 64
        to = _finite(ns.timeout, 1.0, 30 * 24 * 3600.0)
        if to is None:
            raise MasterError(f"--timeout must be a number >= 1 second "
                              f"(got {ns.timeout!r})", 2)
        ns.timeout = to
    if ((ns.earnings_top is not None and ns.earnings_top < 0)
            or (ns.workers is not None and ns.workers < 1)):
        # P1-1: 0 IS allowed for --earnings-top (deliberate "run L3 on nobody",
        # disclosed in --help and as a layer warning); negatives are usage errors.
        raise MasterError("--earnings-top must be >= 0 (0 = L3 idle); --workers must be >= 1", 2)
    if ns.width is not None and not 40 <= ns.width <= int(CONFIG["MAX_TERM_WIDTH"]):
        raise MasterError(f"--width {ns.width}: out of range "
                          f"40..{int(CONFIG['MAX_TERM_WIDTH'])}", 2)
    # phase 5 (C-1): contradictory colour flags are a usage error, not a
    # silent guess — loud and early.
    if str(getattr(ns, "color", "auto") or "auto") == "always" \
            and (getattr(ns, "no_color", False) or getattr(ns, "plain", False)):
        raise MasterError("--color always contradicts --no-color/--plain "
                          "(pick one: always / never / plain)", 2)
    if getattr(ns, "discover", None) is not None and not 1 <= int(ns.discover) <= 500:
        raise MasterError(f"--discover {ns.discover}: expected 1..500", 2)
    if getattr(ns, "sectors", None) and ns.sectors.strip().lower() != "all":
        bad = [s for s in (x.strip().lower() for x in ns.sectors.split(","))
               if s and s not in CONFIG["QUALITY_SECTORS"]]
        if bad:
            raise MasterError(f"--sectors: unknown group(s) {', '.join(bad)} "
                               f"(known: {', '.join(sorted(CONFIG['QUALITY_SECTORS']))}", 2)
    # phase 3: fail fast on unknown layer names — the same check _parse_layers
    # runs at pipeline time; parsing-time is earlier and louder.
    if getattr(ns, "only", None) or getattr(ns, "skip", None):
        known = set(_layer_registry())
        have = ({s.strip() for s in (ns.only or "").split(",") if s.strip()}
                | {s.strip() for s in (ns.skip or "").split(",") if s.strip()})
        bad_layers = have - known
        if bad_layers:
            raise MasterError(f"unknown layer(s): {', '.join(sorted(bad_layers))} "
                               f"(known: {', '.join(sorted(known))})", 2)


def _layer_registry() -> "dict[str, type]":
    """Late-bound LAYER_REGISTRY (defined in master.py AFTER this module
    is imported by it): resolving at call time keeps me/cli acyclic and
    honours test monkeypatches on master.LAYER_REGISTRY."""
    import master
    return master.LAYER_REGISTRY

