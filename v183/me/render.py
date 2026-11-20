"""me/render.py — the terminal renderer (v1.8.0 split from master.py §6):
pure functions, no pandas; colour/plain/ASCII honoured at widths
40/70/110/160; strip_ansi(colour) == plain at every width; the JSON
payload is the stable --json schema (never NaN); _explain_block is the
--explain per-layer breakdown for one ticker."""
from __future__ import annotations

import argparse
import os
import statistics
import re
import shutil
import sys
import unicodedata
import codes
from datetime import date
from pathlib import Path
from typing import Any

from me.core import (CONFIG, Decision, LayerProvenance, LayerSignal, MacroState,
                     RunOutput, __version__, _base_conviction, _exc, _finite,
                     _ruleset, macro_tilt, macro_view)
from me.errors import MasterError

# v1.8.1 (F3): the quality engine's own flag words (quality.py flags the
# adapters surface verbatim — "ALTMAN_DISTRESS on BALL" etc.) — the
# classifier maps any of these to W_QUALITY_FLAG instead of W_UNUSUAL.
# v1.8.2 (W4): the quality engine's own per-name flag vocabulary
# (quality.py _FLAG_TEXT keys + the share-basis flags) — a warning that is
# exactly one of these words (bare or "FLAG on TICKER") classifies as
# W_QUALITY_FLAG instead of W_UNUSUAL.
_ENGINE_FLAG_WORDS = frozenset((
    "ALTMAN_DISTRESS", "NEGATIVE_EQUITY", "STALE_PRICE", "STALE_DATA",
    "SPLIT_BASIS_UNVERIFIED", "STALE_SHARES", "NO_POINT_IN_TIME_SHARES",
    "SECTOR_PEER_FALLBACK", "PIOTROSKI_LOW", "HIGH_ACCRUALS",
    "SHRINKING_REVENUE_RISING_DEBT", "INSUFFICIENT_DATA",
    "SECTOR_DATA_MISSING", "LOW_CER", "MARGIN_EROSION",
))


def _engines_sha256_live() -> dict[str, str]:
    """Late-bound _engines_sha256, resolved through master's namespace at
    call time (render is imported by master before master re-exports it, so
    a module-level binding would both break test patches of
    master._engines_sha256 and recurse)."""
    import master
    return master._engines_sha256()



# ════════════════════════════════════════════════════════════════════════
#  § 6 · RENDER — pure functions, no pandas; colour/ASCII/width honoured
# ════════════════════════════════════════════════════════════════════════
# phase 5 (C-1/C-2): bright 16-colour palette only — the SAME semantic
# palette at any detected depth (truecolor/256/16); cyan = headers+layer
# names, magenta = ML/SHADOW, green good, yellow warn/DEGRADED/STALE,
# red error/AVOID/veto, dim secondary, bold titles+tickers. Never colour
# alone: every glyph travels with its word.
_COLORS = {"head": "96", "ok": "92", "warn": "93", "err": "91",
           "dim": "90", "bold": "1", "ml": "95"}
_ASCII_MAP = {"█": "#", "░": "-", "╭": "+", "╮": "+", "╰": "+", "╯": "+", "─": "-",
              "│": "|", "✓": "v", "●": "*", "▲": "!", "✗": "x", "·": ".", "–": "-",
              "−": "-", "—": "-", "×": "x", "…": ".", "→": ">"}
_STRIP_ANSI = re.compile(r"\x1b\[[0-9;]*m")

# Windows-capable terminal markers (C-1): WT_SESSION (Windows Terminal),
# TERM_PROGRAM (VS Code et al.), ConEmuANSI (ConEmu) — treated as capable.
_CAPABLE_MARKERS = ("WT_SESSION", "TERM_PROGRAM", "ConEmuANSI")


def strip_ansi(text: str) -> str:
    """Remove every SGR escape sequence from text — the canonical
    colour==plain gate: strip_ansi(coloured) must equal the plain render
    at every width (tested, C-4)."""
    return _STRIP_ANSI.sub("", text)


def _disp_width(text: str) -> int:
    """Display width: ANSI escapes free + east-asian wide chars count 2
    (phase 5, C-3 — pad by display width, never by len())."""
    clean = strip_ansi(text)
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
               for ch in clean)


def _pad(text: str, width: int) -> str:
    """ljust by DISPLAY width (ANSI-aware, wide-char aware); truncation
    keeps the ellipsis and never leaves a colour bleeding (C-3)."""
    if _disp_width(text) <= width:
        return text + " " * (width - _disp_width(text))
    return _fit(text, width)


def _colour_choice(env: dict, is_tty: bool, choice: str) -> tuple[bool, str]:
    """The --color precedence table (phase 5, C-1), pure and testable.

    precedence (docs mirror this table verbatim):
      --color always  -> ON  (beats NO_COLOR, beats a pipe, beats dumb)
      --color never / --no-color / --plain -> OFF (silent: deliberate)
      auto:
        NO_COLOR (non-empty)                 -> OFF (beats FORCE_COLOR)
        FORCE_COLOR / CLICOLOR_FORCE (!="0") -> ON  (beats dumb, not NO_COLOR)
        not a TTY                            -> OFF + reason + fix
        TERM=dumb without a capable marker   -> OFF + reason + fix
        else                                 -> ON
    """
    choice = str(choice or "auto").strip().lower()
    if choice == "always":
        return True, "colour on: --color always (beats NO_COLOR, pipes, TERM)"
    if choice == "never":
        return False, "colour off: --color never"
    force = next((k for k in ("FORCE_COLOR", "CLICOLOR_FORCE")
                 if str(env.get(k) or "").strip() not in ("", "0")), None)
    no_color = str(env.get("NO_COLOR") or "").strip()
    term = str(env.get("TERM") or "")
    capable = [k for k in _CAPABLE_MARKERS if str(env.get(k) or "").strip()]
    if no_color:
        return False, ("colour off: NO_COLOR is set — unset NO_COLOR "
                       "or use --color always")
    if force:
        return True, f"colour on: {force} forces colour on (auto)"
    if not is_tty:
        return False, "colour off: stdout is not a TTY — use --color always"
    if term == "dumb" and not capable:
        return False, ("colour off: TERM=dumb — set TERM "
                       "(or use --color always)")
    if term == "dumb":
        return True, (f"colour on: TERM=dumb overridden by capable marker "
                      f"({', '.join(capable)})")
    return True, "colour on: auto (TTY, NO_COLOR unset, TERM not dumb)"


def _colour_depth(env: dict) -> str:
    """truecolor (COLORTERM) -> 256 (TERM *256color) -> 16 — reported in
    --doctor; the palette is the same 16-colour semantics at every depth."""
    ct = str(env.get("COLORTERM") or "").lower()
    if ct in ("truecolor", "24bit"):
        return "truecolor"
    term = str(env.get("TERM") or "")
    if ct == "256color" or term.endswith("256color"):
        return "256"
    return "16"


def _windows_vt_enable() -> tuple[bool | None, str]:
    """Enable Windows VT processing via ctypes (no new dependency). Returns
    (True, note) enabled · (False, reason) honest fallback · (None, note)
    not applicable (posix). Falls back WITH the reason, never silently."""
    if os.name != "nt":
        return None, "not Windows (VT setup n/a)"
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)        # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False, "GetConsoleMode failed — ANSI unavailable"
        if mode.value & 0x4:                      # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            return True, "VT already on"
        if kernel32.SetConsoleMode(handle, mode.value | 0x4):
            return True, "VT enabled"
        return False, ("SetConsoleMode failed — ANSI escapes would print "
                       "raw; colour disabled")
    except Exception as e:                        # pragma: no cover (win)
        return False, _exc(e)[:80]


class Style:
    """Colour + ASCII swap + width (+ depth/off-reason, phase 5).
    Colour-stripped output equals plain — the golden backbone."""

    def __init__(self, color: bool, ascii_only: bool, width: int,
                 depth: str = "16", why_off: str = "",
                 plain: bool = False) -> None:
        self.color, self.ascii_only, self.width = color, ascii_only, width
        self.depth = depth
        self.why_off = why_off          # set only when AUTO turned colour off
        self.plain = plain

    def mark(self, text: str, kind: str) -> str:
        code = _COLORS.get(kind)
        if not self.color or not code:
            return text
        return f"\033[{code}m{text}\033[0m"

    def swap(self, text: str) -> str:
        if not self.ascii_only:
            return text
        return "".join(_ASCII_MAP.get(ch, ch) for ch in text)

    def bar(self, frac: float, cols: int | None = None) -> str:
        """Coloured score bar: green -> yellow -> red zones on the ACTION
        door thresholds (single truth source; plain == _bar exactly)."""
        frac = max(0.0, min(1.0, float(frac)))
        txt = _bar(frac, cols)
        if frac * 100 >= float(CONFIG["ACTION_LONG_AT"]):
            zone = "ok"
        elif frac * 100 >= float(CONFIG["ACTION_WATCH_AT"]):
            zone = "warn"
        else:
            zone = "err"
        return self.mark(txt, zone)


def make_style(ns: argparse.Namespace | None = None,
               color: bool | None = None, ascii_only: bool | None = None,
               width: int | None = None) -> Style:
    """--color {auto,always,never} precedence (C-1); --no-color/--plain =
    never (deliberate, silent — no reason line); AUTO-off carries why_off
    so the report can print the ONE dim reason line with the fix."""
    env = os.environ
    choice = str(getattr(ns, "color", None) or "auto").strip().lower() \
        if ns is not None else "auto"
    no_color_flag = bool(getattr(ns, "no_color", False)) if ns is not None else False
    plain_flag = bool(getattr(ns, "plain", False)) if ns is not None else False
    if no_color_flag or plain_flag:
        choice = "never"
    why_off = ""
    if color is None:
        try:
            is_tty = sys.stdout.isatty()
        except Exception:
            is_tty = False
        on, reason = _colour_choice(env, is_tty, choice)
        color = on
        why_off = reason if (not on and choice == "auto") else ""
    if color and os.name == "nt":
        ok, note = _windows_vt_enable()
        if ok is False:                       # None = posix; True = enabled
            color = False
            why_off = f"colour off: Windows VT setup failed — {note}"
    depth = _colour_depth(env)
    ascii_only = bool(ns.ascii) if (ascii_only is None and ns is not None) else bool(ascii_only)
    if width is None:
        width = int(ns.width) if (ns is not None and ns.width) else 0
        if not width:
            try:
                width = shutil.get_terminal_size((96, 24)).columns
            except Exception:
                width = 96
        width = max(CONFIG["MIN_TERM_WIDTH"], min(width, CONFIG["MAX_TERM_WIDTH"]))
    width = max(40, min(width, CONFIG["MAX_TERM_WIDTH"]))
    return Style(color=color, ascii_only=ascii_only, width=width,
                 depth=depth, why_off=why_off, plain=plain_flag)


def _bar(frac: float, cols: int | None = None) -> str:
    frac = max(0.0, min(1.0, float(frac)))
    cols = cols or CONFIG["BAR_COLS"]
    n = int(round(frac * cols))
    return "█" * n + "░" * (cols - n)


def _fit(text: str, width: int) -> str:
    """Truncate with an ellipsis, width-safe. The budget is VISIBLE width
    (P1-8/A14): ANSI escapes pass through free — measuring the raw string
    truncated coloured output earlier than plain, so strip_ansi(coloured)
    != plain and the colour self-test failed on narrow terminals."""
    if len(strip_ansi(text)) <= width:
        return text
    cut = max(1, width - 1)
    kept: list[str] = []
    vis = 0
    i = 0
    colored = False
    while i < len(text) and vis < cut:
        m = _STRIP_ANSI.match(text, i)
        if m:                                  # escape sequence: keep, costs nothing
            colored = True
            kept.append(m.group(0))
            i = m.end()
            continue
        kept.append(text[i])
        vis += 1
        i += 1
    out = "".join(kept).rstrip() + "…"
    if colored:                                # never leave a colour bleeding
        out += "\033[0m"
    return out


def _wrap(text: str, width: int, indent: str = "   ") -> list[str]:
    """Wrap on word boundaries. v1.8.0 (W3): a separator token (· → | — /)
    is GLUED to the word that FOLLOWS it, so a wrapped line can never
    end on a dangling separator and never start with one (the v1.7.0
    header left '(live) ·' hanging at end-of-line)."""
    _SEPS = ("·", "→", "|", "—", "/")
    tokens = text.split()
    if tokens and tokens[-1] in _SEPS:
        tokens = tokens[:-1]               # cosmetic trailing separator
    units: list[str] = []
    pending = ""
    for w_ in tokens:
        if w_ in _SEPS:
            pending += w_ + " "              # carried onto the NEXT word
            continue
        units.append((pending + w_) if pending else w_)
        pending = ""
    if pending:                              # text ended mid-separator
        if units:
            units[-1] += " " + pending
        else:
            units.append(pending)
    lines, cur = [], ""
    for u in units:
        if cur and len(cur) + 1 + len(u) > width - len(indent):
            lines.append(cur)
            cur = u
        else:
            cur = f"{cur} {u}".strip()
    if cur:
        lines.append(cur)
    return [lines[0]] + [indent + ln for ln in lines[1:]] if lines else [""]


def _shorten_word(text: str, budget: int) -> str:
    """Truncate text to budget on a WORD boundary (hyphens/underscores
    count as boundaries inside a single word) with an explicit '…' —
    never a mid-word cut like the v1.7.0 layer rows' 'SYNTHETI…0.0s'."""
    if _disp_width(text) <= budget:
        return text
    keep = ""
    for w_ in text.split(" "):
        cand = (keep + " " + w_).strip()
        if _disp_width(cand) + 1 > budget:        # room for the '…' mark
            break
        keep = cand
    if keep and keep != text:
        out = keep + " …"
        return out if _disp_width(out) <= budget else keep
    if not keep:                                   # one long compound word
        segs = re.split(r"(?<=[-_])", text)
        keep2 = ""
        for seg in segs:
            if _disp_width(keep2 + seg) + 1 > budget:
                break
            keep2 += seg
        if keep2 and keep2 != text:
            return keep2.rstrip("-_") + "…"
        return text[:max(0, budget - 1)] + "…"     # no boundary exists
    return keep


def _pack_units(prefix: str, units: list[str], width: int,
                sep: str = "  |  ") -> list[str]:
    """Pack atomic units onto lines (C-3): the header's provenance cells
    are UNITS — wrapping splits BETWEEN cells, never inside one, so a
    status word like OK can never strand alone on its own line."""
    lines: list[str] = []
    cur = prefix
    for u in units:
        cand = (cur + sep + u) if cur != prefix else prefix + u
        if _disp_width(cand) > width and cur != prefix:
            lines.append(cur)
            cur = prefix + u
        else:
            cur = cand
    if cur and cur != prefix:
        lines.append(cur)
    return lines or [prefix.rstrip()]


def _header(st: Style, out: RunOutput, ns: argparse.Namespace) -> list[str]:
    """Phase-3 manifest header: identity · mode · net · as-of · stubs, then
    the engine versions (MISSING when an engine never answered), then the
    chain, then the one-line data-provenance summary (final phase §2.1).
    Wrapped inside the box at any width 40..160 (phase 5: provenance cells
    wrap as units; unknown values say n/a, never a bare '?')."""
    names = sorted(out.results, key=lambda n: out.results[n].order)
    chain = "→".join(names) or "no layers"
    as_of = out.ctx.as_of or f"{date.today().isoformat()} (live)"
    mode = str(getattr(ns, "depth", None) or getattr(ns, "mode", "") or "standard")
    offline = bool(out.ctx.flags.get("offline"))
    # final phase (§4): the banner NAMES the resolved mode and why.
    net = out.net_mode or ("offline" if offline else "")
    net_note = (f" ({out.net_probe})" if out.net_probe else "")
    row1 = (f"MASTER v{__version__} · mode {mode} · net {net}{net_note} · as of {as_of} · "
            f"stubs {'yes' if out.stubbed else 'no'}")
    engines = []
    for name in names:
        res = out.results[name]
        mod = _LAYER_MODULE.get(name, name)
        if res.engine_version:
            note = "" if res.engine_version == res.version_tested else " ≠tested"
            # phase 5 (C-3): a stub layer's version is "stub" — rendering
            # "vstub" was the owner's cryptic token; it now says what it is.
            ver = ("SYNTHETIC-stub" if res.engine_version == "stub" and out.stubbed
                   else f"v{res.engine_version}")
            engines.append(f"{mod} {ver}{note}")
        else:
            engines.append(f"{mod} MISSING (engine absent — layer salvaged)")
    row2 = "engines: " + (" · ".join(engines) or "none")
    row3 = "chain: " + chain
    rows = [row1, row2, row3]
    # phase 4 (P-1): the header LABELS the active ruleset — legacy's
    # missing-E advantage is never silent, and v2 names its fill.
    rs = str(getattr(ns, "ruleset", None) or CONFIG["RULESET"])
    if rs == "v2":
        rows.append(f"RULESET v2 - missing-E conservative fill "
                    f"E={float(CONFIG['E_MISSING_V2']):.1f} (invariant-tested; "
                    "doors unrounded)")
    else:
        rows.append("RULESET legacy - missing-E advantage ACTIVE (UNVALIDATED)")
    # F2 (v1.8.3): one additive disclosure — how many names this run
    # scored on the missing-E prior (quality scored, earnings absent or
    # scoreless, so fusion used the prior). Display-only: header lines
    # do not feed the decision hash.
    _miss = 0
    for d in out.decisions:
        q_s = d.layers.get("quality")
        e_s = d.layers.get("earnings")
        _q_ok = (q_s is not None and q_s.status == "OK"
                 and q_s.score is not None)
        _e_ok = (e_s is not None and e_s.status == "OK"
                 and e_s.score is not None)
        if _q_ok and not _e_ok:
            _miss += 1
    if _miss and out.decisions:
        _prior = (f"x{float(CONFIG['E_MISSING_HAIRCUT']):.2f} quality haircut"
                  if rs != "v2" else
                  f"E_MISSING_V2={float(CONFIG['E_MISSING_V2']):.1f} fill")
        rows.append(f"earnings prior: {_miss}/{len(out.decisions)} names "
                    f"scored with E missing ({_prior}; ruleset {rs}) — "
                    "NOT_SELECTED/MISSING_DATA indistinguishable here")
    # §2.1: one compact provenance line per layer — v1.8.0 (W3): the
    # cells are LABELLED ('macro: stub · as-of n/a · OK · age n/a') at
    # wide widths and degrade by dropping FIELDS (never truncating a
    # field mid-word); the v1.7.0 'macro stub n/a OK n/a' packed five
    # unlabeled values and read like noise.
    prov_lines: list[str] = []
    if out.provenance:
        cells = []
        for name in names:
            p = out.provenance.get(name)
            if p is None:
                continue
            disp, _kind = _prov_status(p)
            age_s = (f"{p.age_days}d" if p.age_days is not None else "n/a")
            asof = p.data_as_of or "n/a"
            if st.width >= 96:
                cells.append(f"{name}: {p.source} · as-of {asof} · "
                             f"{disp} · age {age_s}")
            elif st.width >= 64:
                cells.append(f"{name}: {p.source} · as-of {asof} · {disp}")
            else:
                cells.append(f"{name}: {p.source} · {disp}")
        if cells:
            prov_lines = _pack_units("data: ", cells, st.width - 4)
    w = st.width
    inner = w - 4
    lines = [st.swap("╭" + "─" * (w - 2) + "╮")]
    for row in rows:
        for ln in _wrap(row, inner, ""):
            lines.append(st.mark(
                st.swap("│ " + _pad(_fit(ln, inner), inner) + " │"), "head"))
    for ln in prov_lines:
        lines.append(st.mark(
            st.swap("│ " + _pad(_fit(ln, inner), inner) + " │"), "head"))
    lines.append(st.swap("╰" + "─" * (w - 2) + "╯"))
    return lines


_LAYER_MODULE = {"macro": "meds", "quality": "quality", "earnings": "earnings",
                 "ml": "ml_train", "risk": "master"}
_STATUS_GLYPH = {"OK": ("●", "ok"), "DEGRADED": ("▲", "warn"), "ERROR": ("✗", "err")}


# v1.8.2 (W3): the per-layer PUBLICATION CADENCE for the display status —
# an age inside the cadence with no failed refresh is 'refresh-due'
# (current for its cadence), not STALE. Keys are the same freshness
# thresholds layer_provenance gates on (single source of truth).
_CADENCE_KEYS = {"macro": "FRESHNESS_MACRO_MAX_AGE_D",          # 45d monthly
                 "quality": "FRESHNESS_QUALITY_MAX_AGE_D",      # 135d quarterly
                 "earnings": "FRESHNESS_EARNINGS_PRICE_MAX_AGE_D"}  # 5d daily


def _prov_status(p: "LayerProvenance") -> tuple[str, str]:
    """Display status word + colour kind for one provenance row (C-2):
    staleness IS a status — older than STALE_STATUS_DAYS shows STALE, never
    a green OK; freshness-gate statuses (MISSING_DATA/ERROR) keep their
    own words. Display only — no logic gate reads this.
    v1.8.2 (W3): cadence-aware — an age INSIDE the layer's publication
    cadence with no failed refresh this run shows 'refresh-due' (current
    for its cadence, e.g. a monthly macro series at 18-45d), NOT STALE
    and no W_STALE_CACHE. Past the cadence, or with a failed refresh
    (refresh_failed), it is STALE."""
    if p.status in ("ERROR", "MISSING_DATA", "STALE"):
        return p.status, "warn" if p.status != "ERROR" else "err"
    if p.age_days is not None and p.age_days > int(CONFIG["STALE_STATUS_DAYS"]):
        cad_key = _CADENCE_KEYS.get(p.layer)
        cad = int(CONFIG[cad_key]) if cad_key else None
        if bool(getattr(p, "refresh_failed", False)) or cad is None \
                or p.age_days > cad:
            return "STALE", "warn"
        return "refresh-due", "dim"     # current for its cadence; informational
    return p.status, "dim"


def _layers_block(st: Style, out: RunOutput) -> list[str]:
    """Layer chips (C-2): the LEAD glyph IS the status glyph — a DEGRADED
    layer shows yellow ▲ DEGRADED, never a green check; layer names cyan;
    scored bars coloured by zone; provenance sub-lines show STALE + age."""
    lines = []
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        res = out.results[name]
        glyph, kind = _STATUS_GLYPH.get(res.status, ("✗", "err"))
        mod = _LAYER_MODULE.get(name, name)
        ver = (f"{mod} SYNTHETIC-stub" if res.engine_version == "stub" and out.stubbed
               else f"{mod} v{res.engine_version}")
        if res.engine_version != res.version_tested:
            ver += " ≠tested"
        elapsed = f"{res.elapsed_s:.1f}s" if res.elapsed_s < 100 else f"{res.elapsed_s:.0f}s"
        extra = ""
        if res.ctx_out.get("total"):          # any layer that scored a pool
            scored, total = res.ctx_out["scored"], res.ctx_out["total"]
            extra = f"{scored}/{total} scored"
            if st.width >= 96:
                extra += f"  {st.bar(scored / max(total, 1), 12)}"
        else:
            missing = res.ctx_out.get("missing")
            if missing is not None:            # earnings-style per-name gaps
                extra = f"{len(missing)} no data" if missing else "OK"
        if res.ctx_out.get("weak"):
            # P-5 (v1.4.1 port, disclosure-only): state the EFFECTIVE weight,
            # not just the word — W_E is halved by EARNINGS_WEAK_SCALE then
            # renormalised, so the scorecard says exactly what runs.
            we = float(CONFIG["W_E"]) * float(CONFIG["EARNINGS_WEAK_SCALE"])
            eff = we / (float(CONFIG["W_Q"]) + we)
            extra = ((extra + " · ") if extra else "") + (
                f"weak x{float(CONFIG['EARNINGS_WEAK_SCALE']):g} ACTIVE — "
                f"E weight {float(CONFIG['W_E']):.0%} -> {eff:.0%}")
        if res.ctx_out.get("portfolio") is not None:
            extra = (extra + " · portfolio") if extra else "portfolio"
        # phase 5 (C-2): the lead carries the SAME glyph+word as the status
        # column — DEGRADED is ▲ (yellow), never the green ✓ it used to get.
        lead = st.mark(glyph, kind)
        name_col = st.mark(_pad(f"L{res.order} {name}", 13), "head")
        stat_col = st.mark(_pad(f"{glyph} {res.status}", 13), kind)
        # v1.8.0 (W3): assemble with DROP-BY-PRIORITY instead of slicing
        # the joined line: extra drops first, then the cache column, then
        # the elapsed column; the engine-name column shortens on a word
        # boundary (_shorten_word) and every kept cell keeps at least one
        # space before the next — the v1.7.0 rows could glue
        # 'SYNTHETI…0.0s' mid-name to the time column.
        ver_budget = 24 if st.width >= 96 else 22 if st.width >= 70 else 0
        ver_cell = _shorten_word(ver, ver_budget) if ver_budget else ""
        row_core = (f" {lead} {name_col} "
                    + (ver_cell + " " if ver_cell else ""))
        used = _disp_width(strip_ansi(row_core))
        tail_units: list[tuple[str, int]] = []
        if st.width >= 64:
            tail_units.append((_pad(elapsed, 6), 0))          # drop prio 2
        if st.width >= 96:
            tail_units.append((_pad(res.cache, 5), 1))        # drop prio 1
        tail_units.append((stat_col, -1))                     # never dropped
        for cell, _prio in tail_units:
            need = _disp_width(strip_ansi(cell)) + (1 if cell else 0)
            if used + need <= st.width or _prio < 0:
                row_core = row_core + (cell if _prio < 0 else
                                       ((" " if not row_core.endswith(" ")
                                         else "") + cell))
                used += need
        if extra and st.width >= 70:
            need = 1 + _disp_width(extra)
            if used + need <= st.width:
                row_core = row_core + " " + extra
        lines.append(st.swap(_fit(row_core, st.width)))
        # final phase (§2.1): one compact provenance line under each layer
        # (source · data as-of · status+age). phase 5: STALE display + n/a.
        p = (out.provenance or {}).get(name)
        if p is not None:
            disp, kind2 = _prov_status(p)
            age = f"{p.age_days}d" if p.age_days is not None else "n/a"
            pline = (f"     data {p.source} · as-of {p.data_as_of or 'n/a'} · "
                     f"{disp} {age}")
            lines.append(st.mark(st.swap(_fit(pline, st.width)), kind2))
    if "earnings" not in out.results and out.ctx.flags.get("earnings_mode") == "off":
        lines.append(st.swap(" · L3 earnings  off (--earnings-mode off)"))
    return lines


def _tilt_line(st: Style, state: "MacroState") -> list[str]:
    parts = []
    for sec in CONFIG["SECTOR_ORDER"]:
        t = macro_tilt(state, sec)
        abbr = CONFIG["SECTOR_ABBR"].get(sec, sec[:6])
        val = "–" if t is None else ("0" if not t else f"{t:+.1f}")
        parts.append(f"{abbr} {val}")
    txt = "   sector tilt  " + "  ·  ".join(parts)
    if state.degraded_for_damp:
        txt += f"  ·  macro {'DEGRADED' if state.status == 'DEGRADED' else 'credit OFF'}: tilt damped ×{CONFIG['MACRO_DEGRADED_DAMP']:.1f}"
    return [st.swap(x) for x in _wrap(txt, st.width, "     ")]


def _macro_card(st: Style, out: RunOutput) -> list[str]:
    state = out.ctx.regime
    if state is None or state.status == "ERROR":
        why = ""
        res = out.results.get("macro")
        if res is not None and res.warnings:
            why = res.warnings[0][:120]
        line = (f" ! MACRO UNAVAILABLE — no regime context (tilt –, risk budget "
                f"capped 1.0){' · ' + why if why else ''}")
        return [st.mark(st.swap(x), "err")
                for x in _wrap(line, st.width, "   ")]
    head = f" L1 MACRO ── {state.scenario_name or state.scenario_key} · {state.cycle_phase}"
    sub = (f"   conf {st.bar(state.confidence)} {state.confidence:.2f} · "
           f"lev {state.conviction_leverage:.2f}x · risk budget {out.ctx.risk_budget:.2f}")
    credit = state.credit
    credit_txt = (f"credit {credit} ▲ not trade-grade" if credit == "OFF" else f"credit {credit}")
    info = (f"   eff {state.effective_as_of or '–'} · data {state.data_tier or '–'} · "
            f"PIT {state.pit_mode or '–'} · {credit_txt} · next month {state.trade_month or '–'}")
    longs = " ".join(state.longs) or "–"
    shorts = " ".join(state.shorts) or "–"
    sleeve = " ".join(state.sleeve) or "–"
    basket = f"   LONG  {longs:<14} SHORT  {shorts:<10} sleeve: {sleeve}"
    lines = [st.swap(_fit(head, st.width)), st.swap(_fit(sub, st.width))]
    lines += [st.swap(x) for x in _wrap(info, st.width, "     ")]
    lines.append(st.swap(_fit(basket, st.width)))
    if state.credit == "OFF" and state.excluded:
        lines += [st.swap(x) for x in _wrap(
            f"   excluded (credit OFF): {', '.join(state.excluded)}",
            st.width, "   ")]
    if state.warnings:
        lines += [st.swap(x) for x in
                  _wrap("   macro warnings: " + " · ".join(state.warnings[:4]), st.width, "     ")]
    lines += _tilt_line(st, state)
    return lines


_Q_SHORT = {"INSUFFICIENT_DATA": "INSUF", "STALE_DATA": "STALE", "SECTOR_DATA_MISSING": "NOSEC",
            "NO_DATA": "NODATA", "DELISTED": "DELIST", "RENAMED": "RENAME", "ERROR": "ERR"}


def _q_cell(sig: LayerSignal | None) -> str:
    if sig is None:
        return "–"
    if sig.status == "OK" and sig.score is not None:
        return f"{sig.score:.0f} {sig.grade}"
    word = str(sig.facts.get("engine_status") or sig.status)
    return _Q_SHORT.get(word, word[:6])


_E_CELL_WORD = {"DISABLED": "off", "NOT_SELECTED": "n/a",
                "MISSING_DATA": "n/a", "ERROR": "n/a"}
# phase 5 (C-2): the cryptic 'n/sel'/'nodata' tokens are gone — n/a plus
# the reason in the ERRORS & WARNINGS block (never a bare '?'/'n/sel').


def _e_cell(sig: LayerSignal | None) -> str:
    if sig is None:
        return "off"
    if sig.status != "OK" or sig.score is None:
        return _E_CELL_WORD.get(sig.status, "–")     # P2-10: say WHY, not a bare dash
    cell = f"{sig.score:.0f} {sig.grade}"
    if sig.facts.get("now"):
        cell += "·NOW"
    return cell


def _flags_cell(d: Decision) -> str:
    """Phase 3: flags only — the veto/gate text lives in the REASONS column
    (it used to squat here); a blocked row with no flags shows the short
    blocked marker so the narrow tiers stay informative."""
    q = d.layers.get("quality")
    flags = [f for f in (q.flags if q else ()) if f not in CONFIG["VETO_FLAGS"]]
    if flags:
        return ", ".join(flags)
    if d.blocked:
        return d.blocked
    return "–"


def _decisions_table(st: Style, out: RunOutput, ns: argparse.Namespace) -> list[str]:
    """Phase 5 (C-3) column budget, drop priority as width shrinks:
    REASONS (>=120) -> FLAGS (>=100) -> MACRO (>=80) -> WT and SECTOR (>=70).
    # · TICKER · ACTION · CONV · Q · E never drop. Cells are padded by
    DISPLAY width and every cell keeps >=1 trailing space, so no two values
    can join at any width (the 'NODATAn/sel' glue is structurally gone).
    The veto/gate text lives in REASONS, never hidden; the ONE conviction
    definition stays in the footer (score, not probability)."""
    rows = [d for d in out.decisions if d.conviction >= float(ns.min_conviction)]
    rows = rows[:int(ns.top)]
    hidden = len(out.decisions) - len(rows)
    w = st.width
    sized = any(d.weight is not None for d in out.decisions)  # sizer ran (P5)
    show = {"REASONS": w >= 120, "FLAGS": w >= 100, "MACRO": w >= 80,
            "WT": w >= 70 and sized, "SECTOR": w >= 70}
    bar = 12 if w >= 96 else (8 if w >= 70 else 4)
    e_w = 11 if w >= 70 else 7
    act_kind = {"LONG": "ok", "WATCH": "warn", "AVOID": "err"}

    def _cells(cells: list[tuple[str, int | None, str | None]],
               fit: bool = True) -> str:
        outp = []
        for text, cw, kind in cells:
            if kind:
                text = st.mark(text, kind)
            if cw is None:                      # last free-width cell
                outp.append(text)
            else:
                outp.append(_pad(_fit(text, cw - 1) if fit else text, cw))
        line = " ".join(outp)
        return _fit(line, w)

    head_cells = [(" #", 3, None), ("TICKER", 8, None)]
    if show["SECTOR"]:
        head_cells.append(("SECTOR", 9, None))
    head_cells += [("ACTION", 8, None), ("CONV", bar + 6, None),
                   ("Q", 7, None), ("E", e_w, None)]
    if show["WT"]:
        head_cells.append(("WT", 7, None))
    if show["MACRO"]:
        head_cells.append(("MACRO", 8, None))
    if show["FLAGS"]:
        head_cells.append(("FLAGS", 14, None))
    if show["REASONS"]:
        head_cells.append(("REASONS", None, None))
    lines = [st.mark(st.swap(_cells(head_cells, fit=False)), "bold")]
    for i, d in enumerate(rows, 1):
        m = d.layers.get("macro")
        t = m.facts.get("tilt") if m else None
        mac = "–" if t is None else ("0" if not t else f"{t:+.1f}")
        conv = f"{st.bar(d.conviction / 100, bar)} {d.conviction:.0f} {d.grade}"
        abbr = CONFIG["SECTOR_ABBR"].get(d.sector, d.sector[:6])
        cells: list[tuple[str, int | None, str | None]] = \
            [(f"{i:>2}", 3, None), (d.ticker, 8, "bold")]
        if show["SECTOR"]:
            cells.append((abbr, 9, None))
        cells += [(d.action, 8, act_kind[d.action]), (conv, bar + 6, None),
                  (_q_cell(d.layers.get("quality")), 7, None),
                  (_e_cell(d.layers.get("earnings")), e_w, None)]
        if show["WT"]:
            wt = "–" if d.weight is None else f"{d.weight * 100:.0f}%"
            if d.weight is not None and d.adv_checked is False:
                wt += "*"                  # F9 (v1.8.3): ADV-unchecked
            cells.append((wt, 7, None))
        if show["MACRO"]:
            cells.append((mac, 8, None))
        if show["FLAGS"]:
            cells.append((_flags_cell(d), 14, None))
        if show["REASONS"]:
            # room = width minus the fixed cells (their widths + separators)
            fixed_w = sum(c[1] for c in cells if c[1]) + len([c for c in cells if c[1]]) - 1
            room = w - fixed_w - 2
            cells.append(("; ".join(d.reasons[:3]) if room >= 12 else "", None, None))
        lines.append(st.swap(_cells(cells)))
    counts = {a: sum(1 for d in out.decisions if d.action == a)
              for a in ("LONG", "WATCH", "AVOID")}
    tail = (f" {counts['LONG']} LONG · {counts['WATCH']} WATCH · {counts['AVOID']} AVOID")
    if hidden:
        tail += f" · {hidden} hidden (--top {ns.top} / min-conviction {ns.min_conviction:g})"
    lines.append(st.mark(st.swap(tail), "dim"))
    # F9 (v1.8.3): the ADV-unchecked footnote — printed exactly when at
    # least one displayed row carries the * marker (weights assigned by
    # the sizer with advs=None: the participation cap could not bind).
    # Wrapped to the box width like every other long line (phase 5).
    if any(d.weight is not None and d.adv_checked is False for d in rows):
        lines.extend(st.swap(ln) for ln in _wrap(
            "* ADV-unchecked: the price feeds carry no volume, so the "
            "participation cap cannot bind [W_ADV_UNAVAILABLE]", w, "   "))
    return lines


def _earnings_scorecard(st: Style, out: RunOutput, ns: argparse.Namespace) -> list[str]:
    res = out.results.get("earnings")
    if res is None or not res.signals:
        return []
    # P1-4: scored rows filtered by --min-conviction as before; unscored rows
    # are ALWAYS shown (they are the honest "NO DATA" disclosure).
    scored = [(t, s) for t, s in res.signals.items() if s.score is not None]
    unscored = [(t, s) for t, s in res.signals.items() if s.score is None]
    scored.sort(key=lambda kv: (-kv[1].score, kv[0]))
    rows = [kv for kv in scored if kv[1].score >= float(ns.min_conviction)][:int(ns.top)]
    rows += sorted(unscored, key=lambda kv: kv[0])[:max(0, int(ns.top) - len(rows))]
    lines = [st.mark(st.swap(f" {'#':>2}  {'TICKER':<8}{'E':<11}{'STATUS':<9}"
                             f"{'PLAN':<7}{'P_NEXT':<7}LAST BIG"), "bold")]
    for i, (t, s) in enumerate(rows, 1):
        e = ((f"{s.score:.0f} {s.grade}" + ("·NOW" if s.facts.get("now") else ""))
             if s.score is not None else "NO DATA")
        plan = s.facts.get("plan") or "–"
        pn = s.facts.get("p_next_big")
        p_next = f"{pn * 100:.0f}%" if pn is not None else "–"   # missing ≠ 0%
        lines.append(st.swap(f" {i:>2}  {st.mark(f'{t:<8}', 'bold')}{e:<11}{s.status:<9}"
                             f"{plan:<7}{p_next:<7}{s.facts.get('last_big_date') or '–'}"))
    # P2-11: p_next_big is a beat probability, never a return expectation.
    note = (" p_next_big = modelled chance of a big EPS beat next quarter, "
            "not a return")
    lines += [st.mark(st.swap(x), "dim") for x in _wrap(note, st.width, "   ")]
    return lines


def _sector_table(st: Style, out: RunOutput) -> list[str]:
    """Phase 3: per-sector panel — macro tilt, scored count, median quality.
    Only sectors that actually have candidates; honest '–' when nothing
    scored; absent entirely when quality did not run (no table, no fake data)."""
    q_res = out.results.get("quality")
    if q_res is None:
        return []
    state = out.ctx.regime
    scored: dict[str, list[float]] = {}
    unscored: dict[str, int] = {}
    for _t, sig in q_res.signals.items():
        sec = (sig.facts.get("sector") or "").lower()
        if not sec:
            continue
        if sig.status == "OK" and sig.score is not None:
            scored.setdefault(sec, []).append(float(sig.score))
        else:
            unscored[sec] = unscored.get(sec, 0) + 1
    secs = [s for s in CONFIG["SECTOR_ORDER"] if s in scored or s in unscored]
    if not secs:
        return []
    w = st.width
    if w >= 70:
        head = f" {'SECTOR':<12}{'tilt':<7}{'scored':<9}median-Q"
    else:
        head = f" {'SEC':<9}{'tilt':<6}{'n':<6}med"
    lines = [st.mark(st.swap(_fit(head, w)), "bold")]
    for sec in secs:
        tilt = macro_tilt(state, sec)
        tilt_s = "–" if tilt is None else ("0" if not tilt else f"{tilt:+.1f}")
        ok_n = len(scored.get(sec, ()))
        n = ok_n + unscored.get(sec, 0)
        med_s = (f"{statistics.median(scored[sec]):.0f}" if ok_n else "–")
        if w >= 70:
            row = f" {sec:<12}{tilt_s:<7}{(f'{ok_n}/{n}'):<9}{med_s}"
        else:
            row = f" {sec[:8]:<9}{tilt_s:<6}{(f'{ok_n}/{n}'):<6}{med_s}"
        lines.append(st.swap(_fit(row, w)))
    return lines


def _footer(st: Style, out: RunOutput) -> list[str]:
    """Sizer portfolio lines, the ONE conviction definition (a score, not a
    probability), the standing disclosure + timings. Phase 5 (C-5): the
    warnings live in the ERRORS & WARNINGS block now — never a dim soup."""
    lines: list[str] = []
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        for pl in (out.results[name].ctx_out.get("portfolio") or ()):
            lines += [st.mark(st.swap(x), "dim")
                      for x in _wrap(pl, st.width, "   ")]
    score = (" conviction = 0.65*Q + 0.35*E (missing-E x0.90, weak-E x0.5) "
             "x macro tilt — score, not probability")
    lines += [st.mark(st.swap(x), "dim") for x in _wrap(score, st.width, "   ")]
    per = " · ".join(f"{n} {out.timings[n]:.1f}s" for n in
                     sorted(out.results, key=lambda n: out.results[n].order) if n in out.timings)
    disc = (f" research screener, not investment advice · survivorship-biased universe · "
            f"timings {out.timings.get('total', 0):.1f}s" + (f" ({per})" if per else ""))
    lines += [st.mark(st.swap(x), "dim") for x in _wrap(disc, st.width, "   ")]
    return lines


def _ml_line(st: Style, out: RunOutput) -> list[str]:
    """Phase 5 (C-2): one compact ML-overlay disclosure in plain English —
    head states with their training sample sizes ("SHADOW (n=974 train
    rows)", not "SHADOW(n 974)"), magenta so ML/SHADOW reads at a glance."""
    res = out.results.get("ml")
    if res is None:
        return []
    heads = res.ctx_out.get("heads") or {}
    segs = []
    for h in ("q", "e", "macro"):
        info = heads.get(h) or {}
        n = info.get("n_train")
        segs.append(f"{h} {info.get('state', 'n/a')}"
                    + (f" (n={n} train rows)" if n else ""))
    state = res.ctx_out.get("state", "n/a")
    tail = ("conviction_adj bounded ±%g (validation report passed)"
            % min(CONFIG["ML_ADJ_MAX"], CONFIG["OVERLAY_MAX_ADJ"])
            if state == "ACTIVE"
            else "probabilities logged, no decision changed")
    line = "ML OVERLAY " + " · ".join(segs) + " — " + tail
    return [st.mark(st.swap(x), "ml") for x in _wrap(line, st.width, "   ")]


def _verdict_reason(out: RunOutput) -> str:
    """Plain-English one-line reason for the VERDICT (C-2): names the real
    blocker — quality with no data, the first ERROR layer, or the top pick."""
    q = out.results.get("quality")
    if q is not None and q.ctx_out.get("total") \
            and not q.ctx_out.get("scored"):
        why = (q.warnings[0] if q.warnings else "no data")
        return f"quality had no data ({why[:70]})"
    errs = [r for r in sorted(out.results.values(), key=lambda r: r.order)
            if r.status == "ERROR"]
    if errs:
        r = errs[0]
        why = (r.warnings[0] if r.warnings else "failed")
        return f"{r.name} failed: {why[:70]}"
    if out.warnings:
        return f"{len(out.warnings)} warning(s): {out.warnings[0][:70]}"
    if out.decisions:
        top = max(out.decisions, key=lambda d: d.conviction)
        return f"top pick {top.ticker} {top.action} {top.conviction:.0f}"
    return "no decisions this run"


def _verdict_line(st: Style, out: RunOutput) -> list[str]:
    """C-2: ONE plain-English line under the header — counts + the real
    reason ('0 LONG / 0 WATCH / 2 AVOID — quality had no data ...')."""
    counts = {a: sum(1 for d in out.decisions if d.action == a)
              for a in ("LONG", "WATCH", "AVOID")}
    reason = _verdict_reason(out)
    any_err = any(r.status == "ERROR" for r in out.results.values())
    if any_err or (out.results.get("quality") is not None
                   and out.results["quality"].ctx_out.get("total")
                   and not out.results["quality"].ctx_out.get("scored")):
        kind = "err"
    elif out.warnings or any(r.status == "DEGRADED" for r in out.results.values()):
        kind = "warn"
    else:
        kind = "ok"
    line = (f"VERDICT {counts['LONG']} LONG / {counts['WATCH']} WATCH / "
            f"{counts['AVOID']} AVOID — {reason}")
    return [st.mark(st.swap(_fit(line, st.width)), kind)]


def _legend_line(st: Style) -> list[str]:
    """C-2: one dim LEGEND line — glyphs + colour words, never colour alone."""
    txt = ("LEGEND ● OK · ▲ DEGRADED · ✗ ERROR · n/a = no data (reason in "
           "warnings) · green good · yellow warn/STALE · red error/AVOID")
    return [st.mark(st.swap(x), "dim") for x in _wrap(txt, st.width, "  ")]


# ── § 6.4b · phase 5 (C-5): warning classification + the ERRORS block ──────
def _classify_warning(layer: str, text: str) -> str:
    """Stable code for one warning text (pattern table, C-5). Bracketed
    [W_...] codes from the emitting site win; provider/class patterns map
    to the network diagnosis codes; anything else is W_UNUSUAL (honest:
    unclassified, never silently dropped)."""
    t = str(text)
    low = t.lower()
    m = re.search(r"\[([WE]_[A-Z0-9_]+)\]", t)
    if m and m.group(1) in codes.REGISTRY:
        return m.group(1)
    # v1.8.1 (F3): the three orphan warnings get stable codes so
    # W_UNUSUAL becomes rare (earnings has no __version__ attr; the
    # watchlist-peers disclosure; quality engine flag names).
    if "exposes no __version__" in low:
        return "W_ENGINE_NO_VERSION"
    if "quality ranks are relative to" in low:
        return "W_PEERS_WATCHLIST"
    m = re.match(r"^([A-Z][A-Z0-9_]{3,})(?: on [A-Z0-9]{1,6})?$", t.strip())
    if m and m.group(1) in _ENGINE_FLAG_WORDS:
        return "W_QUALITY_FLAG"
    # v1.8.2 (W4): the routine messages of stub/offline/outage runs get
    # stable codes so W_UNUSUAL stays for the genuinely unclassified
    if " data stale:" in low:
        return "W_STALE_CACHE"     # the pipeline-level STALE warning copy
    if "no earnings report since" in low:
        # per-name earnings-event staleness (FRESHNESS_EARNINGS_EVENT_MAX_D):
        # the served earnings row is older than a quarter + filing lag
        return "W_STALE_CACHE"
    if "credit off" in low and "not trade-grade" in low:
        return "W_CREDIT_OFF"
    if "macro degraded (" in low:
        return "W_MACRO_DEGRADED"
    if "macro unavailable" in low:
        return "W_MACRO_UNAVAILABLE"
    if "empty shortlist" in low:
        return "W_SHORTLIST_EMPTY"
    if "score renormalized" in low and "retained weight" in low:
        return "W_SCENARIO_RENORMALIZED"
    if "earnings accuracy:" in low:
        return "W_EARNINGS_ACCURACY"
    if "earnings backtest:" in low:
        return "W_EARNINGS_BACKTEST"
    if "no earnings history" in low:
        return "W_EARNINGS_MISSING"     # any layer, incl. the pipeline copy
    if "equal-weight fallback" in low:
        return "W_EQW_FALLBACK"
    if "untrained" in low:
        return "W_HEAD_UNAVAILABLE"     # incl. the pipeline-level copy
    if "circuit breaker open" in low:
        return "W_HOST_BREAKER_OPEN"
    if "run budget exhausted" in low:
        return "W_RUN_BUDGET"
    if "auto mode: network probe failed" in low:
        return "W_NET_FALLBACK_CACHE"
    if "negative cache" in low or "no retry (permanent)" in low:
        return "W_ITEM_SKIPPED"
    if "retry budget exhausted" in low:
        return "W_RETRY_BUDGET"
    if "429" in low or "rate limit" in low or "retry-after" in low:
        return "W_RATE_LIMIT"
    if "offline mode: network disabled" in low \
            or ("net:offline" in low and "provider_errors" not in low):
        return "E_NET_OFFLINE"
    if "provider_errors" in low and ("network_error" in low or "net:" in low):
        return "W_NET_DOWN"
    if "network" in low and ("unreachable" in low or "failed" in low):
        return "W_NET_DOWN"
    if layer == "ml" or "unavailable" in low and "head" in low:
        return "W_HEAD_UNAVAILABLE"
    if layer == "earnings" and ("no earnings history" in low or "missing_data" in low):
        return "W_EARNINGS_MISSING"
    if "future-dated" in low or "future report" in low:
        return "W_FUTURE_REPORT"
    if "not writable" in low:
        return "E_CACHE_UNWRITABLE"
    return "W_UNUSUAL"


def _diag(code: str, layer: str, why: str) -> dict[str, str]:
    entry = dict(codes.REGISTRY[code])
    entry["code"] = code
    entry["layer"] = layer
    entry["why"] = why[:140]
    return entry


def _engines_sha_recorded() -> dict[str, str]:
    recorded: dict[str, str] = {}
    sha_file = Path(__file__).resolve().parent.parent / "ENGINES.sha256"
    if sha_file.is_file():
        for line in sha_file.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) == 2:
                key = parts[1].removesuffix(".py")
                recorded["earnings" if key == "earnings_engine" else key] = parts[0]
    return recorded


def _build_diags(out: RunOutput) -> list[dict[str, str]]:
    """Every error/warning this run produced as registry entries (C-5):
    layer ERRORs, engine hash mismatch, offline mode, ml heads, risk
    warn_codes, classified warnings, provenance staleness, SYNTHETIC runs.
    Order: errors first, then warnings, layer order, first occurrence."""
    diags: list[dict[str, str]] = []

    def add(code: str, layer: str, why: str = "") -> None:
        d = _diag(code, layer, why)
        if not any(x["code"] == code and x["layer"] == layer for x in diags):
            diags.append(d)

    # engine hash mismatch (read cheaply; absent file => skipped)
    try:
        have = _engines_sha256_live()
        want = _engines_sha_recorded()
        mism = [k for k in ("meds", "quality", "earnings")
                if have.get(k) and want.get(k) and have[k] != want[k]]
        if mism:
            add("E_HASH_MISMATCH", "engines",
                f"files differ from ENGINES.sha256: {', '.join(mism)}")
    except Exception:
        pass
    if out.stubbed:
        add("W_SYNTHETIC", "pipeline", "stub layers rendered (MASTER_STUBS)")
    if out.net_mode == "offline":
        add("W_NET_OFFLINE", "net", out.net_probe or "offline mode")
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        res = out.results[name]
        if res.status == "ERROR":
            # the why prefers the layer's own warning, else the first
            # SIGNAL's warning (provider errors live there), else the name
            why = (res.warnings[0] if res.warnings else
                   next((s.warnings[0] for s in res.signals.values()
                         if s.warnings), "") or f"{name} failed")
            add("E_LAYER", name, why)
        for w in res.warnings:
            add(_classify_warning(name, w), name, w)
        sig_warn = next((s.warnings[0] for s in res.signals.values()
                         if s.warnings), None)
        if sig_warn and sig_warn not in res.warnings:
            # provider/class diagnostics ride on the signals (the owner's
            # 'provider_errors:NETWORK_ERROR; ...' tail) — classify the
            # first one so the network diagnosis entry appears.
            add(_classify_warning(name, sig_warn), name, sig_warn)
        for u in (res.ctx_out.get("unavailable") or ()):
            add("W_HEAD_UNAVAILABLE", name, str(u))
        if name == "earnings" and res.ctx_out.get("missing"):
            # per-name gaps live on the SIGNALS — one honest aggregate entry
            add("W_EARNINGS_MISSING", name,
                f"{len(res.ctx_out['missing'])} name(s) with no usable "
                f"earnings history: {', '.join(res.ctx_out['missing'][:6])}")
        for c in (res.ctx_out.get("warn_codes") or ()):
            if c in codes.REGISTRY:
                add(c, name, f"{name} warn code {c}")
    for w in out.warnings:
        add(_classify_warning("pipeline", w), "pipeline", w)
    for name in sorted(out.provenance or {}, key=lambda n: n):
        p = out.provenance[name]
        disp, _k = _prov_status(p)
        if disp in ("STALE", "MISSING_DATA", "ERROR"):
            add("W_STALE_CACHE", name,
                f"{name} {p.source} as-of {p.data_as_of or 'n/a'} "
                f"{'STALE' if disp == 'STALE' else disp}"
                f" {p.age_days if p.age_days is not None else 'n/a'}")
    order = {"error": 0, "warning": 1}
    diags.sort(key=lambda d: (order.get(d["severity"], 2),
                              d.get("layer", ""), d["code"]))
    return diags


def _diag_line(st: Style, d: dict[str, str]) -> str:
    """One ERRORS & WARNINGS entry (C-5): layer · stable CODE · what on the
    first line; why and the EXACT fix command each on their own line — the
    fix is never truncated away by a long unbreakable why-token."""
    glyph, kind = (("✗", "err") if d["severity"] == "error" else ("▲", "warn"))
    head = f" {glyph} {_pad(d['layer'], 9)} {_pad(d['code'], 20)} {d['what']}"
    why = f"      why: {d['why']}"
    fix = f"      fix: {d['fix']}"
    lines = [st.mark(st.swap(_fit(head, st.width)), kind)]
    lines += [st.mark(st.swap(_fit(x, st.width)), kind)
              for x in _wrap(why, st.width, "      ")]
    lines += [st.mark(st.swap(_fit(x, st.width)), kind)
              for x in _wrap(fix, st.width, "      ")]
    return "\n".join(lines)


def _data_sources_line(st: Style, out: RunOutput) -> list[str]:
    """C-5: DATA SOURCES — layer -> live/cache/SYNTHETIC -> age (+STALE),
    and the macro path on its own line (FRED key -> API; no key ->
    public fredgraph.csv; cache with AGE when cold).
    v1.8.0 (W3): the per-layer cells are UNITS packed between ' · '
    separators — the v1.7.0 line was one hard-truncated string and cut
    the last cell mid-name ('risk SYNTHET…') at narrow widths."""
    parts = []
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        p = (out.provenance or {}).get(name)
        if p is None:
            continue
        src = p.source
        if src == "stub":
            src = "SYNTHETIC"
        elif src == "network":
            src = "live"
        disp, _k = _prov_status(p)
        age = f"{p.age_days}d" if p.age_days is not None else "n/a"
        parts.append(f"{name} {src} {age}{' STALE' if disp == 'STALE' else ''}")
    if parts:
        packed = _pack_units("DATA SOURCES: ", parts, st.width, sep=" · ")
    else:
        packed = ["DATA SOURCES: none"]
    lines = [st.mark(st.swap(ln), "dim") for ln in packed]
    if "macro" in out.results or out.ctx.regime is not None:
        if os.environ.get("FREDAPI") or os.environ.get("FRED_API_KEY"):
            path = "macro path: FRED API (key set)"
        else:
            path = "macro path: no FRED key → public fredgraph.csv"
        lines += [st.mark(st.swap(x), "dim")
                  for x in _wrap(path, st.width, "   ")]
    return lines


def _summary_card(st: Style, out: RunOutput) -> list[str]:
    """v1.8.0 (W3): the summary card — verdict counts, top picks, the
    macro risk posture and the warning count in ONE place at the top,
    tiered by width. Research vocabulary only: a screener summary, never
    advice or a probability."""
    counts = {"LONG": 0, "WATCH": 0, "AVOID": 0}
    for d in out.decisions:
        if d.action in counts:
            counts[d.action] += 1
    _order = {"LONG": 0, "WATCH": 1, "AVOID": 2}
    picks = sorted(out.decisions,
                   key=lambda d: (_order.get(d.action, 9),
                                  -float(d.conviction), d.ticker))[:3]
    pick_txt = " · ".join(f"{d.ticker} {d.action} "
                          f"{d.conviction:.0f}" for d in picks) or "none"
    st_reg = out.ctx.regime
    risk = ""
    if st_reg is not None:
        # regime is a MacroState dataclass — the card shows its CLASS
        # (risk_on / defensive / neutral), never the whole repr.
        risk = str(getattr(st_reg, "regime_class", "")
                   or getattr(st_reg, "status", "") or "")
    n_warn = len(out.warnings or [])
    if st.width >= 70:
        # fields are APPENDED only while they fit (v1.8.0 W3): the card
        # never exceeds the width and never slices a field.
        head = (f"SUMMARY  verdict {counts['LONG']} LONG / {counts['WATCH']} "
                f"WATCH / {counts['AVOID']} AVOID")
        if _disp_width(head + f" · risk {risk or 'n/a'}") <= st.width:
            head += f" · risk {risk or 'n/a'}"
        if _disp_width(head + f" · warnings {n_warn}") <= st.width:
            head += f" · warnings {n_warn}"
        lines = [head] + _wrap(f"top picks {pick_txt}", st.width - 2,
                               "         ")
        return [st.mark(st.swap(x), "bold") for x in lines if x]
    # narrow: everything on one packed line, fields dropped not sliced
    one = (f"SUMMARY {counts['LONG']}L/{counts['WATCH']}W/"
           f"{counts['AVOID']}A · {risk or 'n/a'} · warn {n_warn} · "
           f"picks {pick_txt}")
    return [st.mark(st.swap(_shorten_word(one, st.width)), "bold")]


def _errors_block(st: Style, out: RunOutput) -> list[str]:
    """C-5: EVERY run ends with ERRORS & WARNINGS — red errors, yellow
    warnings, clean = green '0 errors, 0 warnings'; then the DATA SOURCES
    line and (v1.8.1, N4) the FETCH HEALTH block. Entries carry layer,
    stable code, what, why and the EXACT fix."""
    diags = _build_diags(out)
    lines = [st.mark(st.swap("ERRORS & WARNINGS"), "bold")]
    if not diags:
        lines.append(st.mark(st.swap(
            " ● 0 errors, 0 warnings"), "ok"))
    for d in diags:
        lines.append(_diag_line(st, d))
    lines += _data_sources_line(st, out)
    lines += _fetch_health_block(st, out)
    return lines


def _fetch_health_block(st: Style, out: RunOutput) -> list[str]:
    """v1.8.1 (N4): the FETCH HEALTH block — printed EVERY run: per host
    and per layer 'ok / failed / skipped' counts, totals, the deferred
    'recovered n of m' line and the skipped-items list (item, why, fix).
    Runs with no fetches print the honest one-line reason instead."""
    fh = getattr(out, "fetch_health", None) or {}
    lines = [st.mark(st.swap("FETCH HEALTH"), "bold")]
    note = str(fh.get("note") or "")
    if note:
        lines.append(st.mark(st.swap(
            _fit(f"  {note}", st.width)), "dim"))
    hosts = fh.get("hosts") or {}
    for host in sorted(hosts):
        c = hosts[host] or {}
        lines.append(st.swap(_fit(
            f"  {host} {c.get('ok', 0)} ok / {c.get('failed', 0)} "
            f"failed / {c.get('skipped', 0)} skipped", st.width)))
    t = fh.get("total") or {}
    if t or hosts:
        lines.append(st.swap(_fit(
            f"  totals {t.get('ok', 0)} ok / {t.get('failed', 0)} failed / "
            f"{t.get('skipped', 0)} skipped", st.width)))
    rec = fh.get("recovered")
    if rec and rec[1]:
        lines.append(st.swap(_fit(
            f"  recovered {rec[0]} of {rec[1]} (deferred retry pass)",
            st.width)))
    for s in (fh.get("skipped_items") or [])[:6]:
        lines.append(st.swap(_fit(
            f"  skipped: {s.get('item', '?')} ({s.get('why', '')} — "
            f"fix: {s.get('fix', '')})", st.width)))
    if len(fh.get("skipped_items") or []) > 6:
        lines.append(st.swap(_fit(
            f"  … +{len(fh['skipped_items']) - 6} more skipped item(s) "
            "(JSON has them all)", st.width)))
    if not hosts and not note:
        lines.append(st.mark(st.swap(
            "  no fetch attempts this run"), "dim"))
    return lines


def render_report(out: RunOutput, ns: argparse.Namespace) -> str:
    """Phase 5 (C-1..C-5) report order: [colour-off reason line] · [SYNTHETIC
    stub banner] · manifest header box · VERDICT · layer chips (+provenance)
    · macro card · sector table · ML line · ranked table · footer · LEGEND ·
    ERRORS & WARNINGS + DATA SOURCES (last — every run ends with it)."""
    st = make_style(ns)
    blocks: list[str] = []
    if st.why_off and not st.plain:
        # C-1: ONE dim top line with the reason + the fix — the owner's
        # plain-white terminal finally explains itself.
        blocks.append(st.mark(st.swap(_fit(st.why_off, st.width)), "dim"))
        blocks.append("")
    if out.stubbed:                           # P1-9 (A2): never look like real data
        banner = ("*** STUBBED RUN (SYNTHETIC stub layers) — NOT real engine "
                  "data — never for any decision ***")
        blocks += [st.mark(st.swap(x), "err") for x in _wrap(banner, st.width, "  ")] + [""]
    blocks += _header(st, out, ns) + [""]
    blocks += _summary_card(st, out) + [""]          # v1.8.0 (W3)
    blocks += _verdict_line(st, out) + [""]
    blocks += _layers_block(st, out) + [""]
    if out.ctx.regime is not None or "macro" in out.results:
        blocks += _macro_card(st, out) + [""]
    blocks += _sector_table(st, out) + [""]
    blocks += _ml_line(st, out) + [""]
    if out.decisions:
        blocks += _decisions_table(st, out, ns) + [""]
    elif "earnings" in out.results and "quality" not in out.results:
        blocks += _earnings_scorecard(st, out, ns) + [""]
    blocks += _footer(st, out) + [""]
    blocks += _legend_line(st) + [""]
    blocks += _errors_block(st, out)
    return "\n".join(blocks)


# ── § 6.5 · --explain: per-layer breakdown + fusion arithmetic + provenance
def _pillars_line(st: Style, sig: LayerSignal) -> list[str]:
    pillars = sig.facts.get("pillars") or {}
    names = [k for k in ("profitability", "growth", "financial_strength",
                         "earnings_quality", "valuation", "shareholder_yield") if k in pillars]
    out = []
    for i in range(0, len(names), 2):
        seg = []
        for k in names[i:i + 2]:
            v = pillars.get(k)
            seg.append(f"{k:<19}{_bar((v or 0) / 100, 8)} {v:.0f}" if isinstance(v, (int, float))
                       else f"{k:<19}{'–':>11}")
        out.append(st.swap("            " + "  ".join(seg)))
    return out or [st.swap("            pillars n/a")]


def _explain_block(st: Style, out: RunOutput, ns: argparse.Namespace, ticker: str) -> str:
    d = next((x for x in out.decisions if x.ticker == ticker), None)
    if d is None:
        sig = None
        for res in out.results.values():
            if ticker in res.signals:
                sig = res.signals[ticker]
        if sig is None:
            raise MasterError(f"--explain {ticker}: not in this run "
                               f"(tickers: {', '.join(c.ticker for c in out.ctx.tickers)})", 2)
    state = out.ctx.regime
    q = (d.layers.get("quality") if d else _res_signal(out, "quality", ticker))
    e = (d.layers.get("earnings") if d else _res_signal(out, "earnings", ticker))
    title = f"── {ticker} · {d.sector if d else '?'} · {d.action} {d.conviction:.0f} {d.grade}" if d else f"── {ticker}"
    lines = [st.mark(st.swap(title), "bold")]
    # L1
    if state is not None and state.status != "ERROR":
        lines.append(st.swap(f" L1 macro    {state.scenario_key} · {state.scenario_name} · "
                             f"conf {state.confidence:.2f} · lev {state.conviction_leverage:.2f}x "
                             f"(risk budget {out.ctx.risk_budget:.2f})"))
        lines.append(st.swap(f"             longs {' '.join(state.longs) or '–'} · shorts "
                             f"{' '.join(state.shorts) or '–'} · sleeve {' '.join(state.sleeve) or '–'}"))
        sec = (q.facts.get("macro_sector") if q else "") or (d.sector if d else "")
        mv = macro_view(state, sec)
        lines.append(st.swap(f"             {sec}: {mv['mapped'] or 'no ETF mapping'} → tilt "
                             f"{('–' if mv['tilt'] is None else format(mv['tilt'], '+.1f'))}, "
                             f"damp ×{mv['damp']:.1f} → conviction ×{mv['mult']:.3f}"))
    elif "macro" in out.results:
        lines.append(st.mark(st.swap(" L1 macro    MACRO UNAVAILABLE — no regime context"), "err"))
    # L2
    if q is not None:
        cov = q.facts.get("coverage")
        cov_s = "–" if cov is None else f"{cov:.0%}"
        head = (f" L2 quality  {_q_cell(q)} · rank {q.facts.get('rank') or '–'}/"
                f"{q.facts.get('pool_size') or '–'} {q.facts.get('sector') or '–'} · "
                f"coverage {cov_s} · "
                f"{q.facts.get('data_source') or '–'} · {q.status}")
        lines.append(st.swap(head))
        lines += _pillars_line(st, q)
        metrics = q.facts.get("metrics_top") or {}
        if metrics:
            lines.append(st.swap("             metrics  " + " · ".join(
                f"{k} {v:g}" for k, v in metrics.items())))
        if q.flags:
            lines.append(st.swap(f"             flags    {', '.join(q.flags)} "
                                 f"({'veto' if set(q.flags) & CONFIG['VETO_FLAGS'] else 'warning'})"))
    # L3
    if e is not None and out.ctx.flags.get("earnings_mode") != "off":
        if e.status == "OK":
            f = e.facts
            lines.append(st.swap(f" L3 earnings {e.score:.0f} {e.grade} · last4 {f.get('last4_big')}/4 big · "
                                 f"streak {f.get('streak_big')} · last big {f.get('last_big_date') or '–'} "
                                 f"{(f.get('last_big_pct') or 0):+.0f}% · p_next_big "
                                 f"{_pct(f.get('p_next_big'))} "
                                 "(chance of a big EPS beat, not a return)"))
            plan = f.get("plan")
            if plan:
                seg = (f"             plan {plan} @ {f.get('price') or 0:.2f} → target "
                       f"{f.get('target') or 0:.2f}")
                if f.get("stop_px") is not None:      # v3 signals carry no stop
                    seg += f" · stop {f['stop_px']:.2f}"
                seg += (f" · exit by {f.get('exit_by') or '–'} · "
                        f"report {f.get('days_since') if f.get('days_since') is not None else '?'}d ago")
                lines.append(st.swap(seg))
            else:
                lines.append(st.swap("             plan n/a (as-of mode or no fresh price)"))
        else:
            lines.append(st.swap(f" L3 earnings {e.status} · {(e.warnings[0] if e.warnings else '')[:80]}"))
    # L4+ (registered extra layers, phase 3) — never silently skipped
    for name in [n for n in sorted(out.results, key=lambda n: out.results[n].order)
                 if n not in ("macro", "quality", "earnings")]:
        sig = (d.layers.get(name) if d else None) or _res_signal(out, name, ticker)
        if sig is None:
            continue
        bit = f" {name} {name:<10} {sig.status}"
        if sig.score is not None:
            bit += f" · {sig.score:.0f} {sig.grade}"
        adj = sig.facts.get("conviction_adj")
        if adj is not None:
            bit += f" · conviction_adj {adj:+.0f} (bounded)"
        lines.append(st.swap(bit))
    # fusion arithmetic
    if d is not None:
        e_res = out.results.get("earnings")
        weak = bool(e_res is not None and e_res.ctx_out.get("weak"))
        qv = q.score if (q and q.status == "OK") else None
        ev = e.score if (e and e.status == "OK") else None
        m_sig = d.layers.get("macro")
        mult = m_sig.facts.get("mult", 1.0) if m_sig else 1.0
        if qv is not None:
            if ev is None and _ruleset() == "v2":
                # phase 4 (P-1): v2 shows the fill arithmetic, not the haircut
                base_s = (f"base = {CONFIG['W_Q']:.2f}×{qv:.0f} + "
                          f"{CONFIG['W_E']:.2f}×{float(CONFIG['E_MISSING_V2']):.1f} "
                          "(E missing -> v2 conservative fill)")
            elif ev is None:
                base_s = f"base = {qv:.0f} × {CONFIG['E_MISSING_HAIRCUT']:.2f} (E missing haircut)"
            elif weak:
                base_s = (f"base = ({CONFIG['W_Q']:.2f}×{qv:.0f} + {CONFIG['W_E']:.2f}×"
                          f"{float(CONFIG['EARNINGS_WEAK_SCALE']):g}×{ev:.0f})"
                          f" / {CONFIG['W_Q'] + CONFIG['W_E'] * float(CONFIG['EARNINGS_WEAK_SCALE']):.3f} "
                          f"(E weak ×{float(CONFIG['EARNINGS_WEAK_SCALE']):g})")
            else:
                base_s = f"base = {CONFIG['W_Q']:.2f}×{qv:.0f} + {CONFIG['W_E']:.2f}×{ev:.0f}"
            base = _base_conviction(qv, ev, weak)
            lines.append(st.swap(f" fusion      {base_s} = {base:.1f}"))
            lines.append(st.swap(f"             × macro {mult:.3f} → conviction {d.conviction:.1f} "
                                 f"→ {d.grade} → {d.action}"))
            # P2-11 (H5): conviction is a heuristic, never a probability.
            lines.append(st.swap("             conviction is a 0-100 research heuristic, "
                                 "never a probability"))
        if d.reasons:
            lines.append(st.swap("             reasons  " + " | ".join(d.reasons)))
    # provenance
    prov = []
    if state is not None:
        prov.append(f"macro: {state.data_tier or '–'}/{state.pit_mode or '–'} ({state.status})")
    if q is not None:
        prov.append(f"quality: {q.facts.get('data_source') or '–'} ({q.status}; engine {q.facts.get('engine_status')})")
    e_res = out.results.get("earnings")
    if e_res is not None:
        prov.append(f"earnings: yahoo ({e_res.status}; {e_res.ctx_out.get('verdict', '')[:60]})")
    if prov:
        lines.append(" provenance  " + " · ".join(prov))
    return "\n".join(st.swap(_fit(x, st.width)) for x in lines)


def _res_signal(out: RunOutput, layer: str, ticker: str) -> LayerSignal | None:
    res = out.results.get(layer)
    if res is None:
        return None
    if layer == "macro":
        return res.signals.get(ticker)    # per-ticker macro signals exist only via fusion
    return res.signals.get(ticker)


def _pct(x: Any) -> str:
    return "–" if x is None or x != x else f"{x * 100:.0f}%"


# ── § 6.9 · stable --json schema ─────────────────────────────────────────
def _json_num(x: Any) -> float | None:
    """Strict-JSON-safe number (P1-5): non-finite/out-of-range -> None so
    _cli_run can pass allow_nan=False and still never raise on a real run."""
    return _finite(x, -1e12, 1e12)


def json_payload(out: RunOutput, ns: argparse.Namespace) -> dict[str, Any]:
    """One parseable object on stdout; keys are stable across releases."""
    state = out.ctx.regime
    layers = []
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        res = out.results[name]
        entry: dict[str, Any] = {
            "name": name, "stage": res.stage, "order": res.order, "status": res.status,
            "engine_version": res.engine_version, "version_tested": res.version_tested,
            "elapsed_s": res.elapsed_s, "cache": res.cache,
            "warnings": list(res.warnings)[:8]}
        # final phase (§2.1): per-layer provenance in the SAME schema in
        # every mode (§3.7) — only the data and the provenance differ.
        p = (out.provenance or {}).get(name)
        entry["provenance"] = (p.as_dict() if p is not None else
                               {"source": "none", "data_as_of": "", "age_days": None,
                                "status": "DISABLED", "reason": "not computed",
                                "basis": ""})
        if name == "macro" and state is not None:
            entry["regime"] = {
                "scenario_key": state.scenario_key, "name": state.scenario_name,
                "class": state.regime_class, "cycle_phase": state.cycle_phase,
                "confidence": _json_num(round(state.confidence, 4)),
                "conviction_leverage": _json_num(round(state.conviction_leverage, 3)),
                "credit": state.credit, "quality": state.quality_tier,
                "data_tier": state.data_tier, "pit_mode": state.pit_mode,
                "effective_as_of": state.effective_as_of, "trade_month": state.trade_month,
                "longs": list(state.longs), "shorts": list(state.shorts),
                "sleeve": list(state.sleeve), "excluded": list(state.excluded)}
        if name == "earnings":
            entry["verdict"] = res.ctx_out.get("verdict")
            entry["weak"] = bool(res.ctx_out.get("weak"))
            entry["backtest"] = res.ctx_out.get("backtest")
        if name == "ml":                        # phase 5: head states + macro p's
            entry["heads"] = res.ctx_out.get("heads")
            entry["ml_state"] = res.ctx_out.get("state")
        if name == "risk":                      # phase 5: the sized book
            entry["portfolio"] = res.ctx_out.get("summary")
        layers.append(entry)
    decisions = []
    for d in out.decisions:
        q, e, m = d.layers.get("quality"), d.layers.get("earnings"), d.layers.get("macro")
        decisions.append({
            "ticker": d.ticker, "sector": d.sector, "action": d.action,
            "conviction": _json_num(d.conviction), "grade": d.grade, "weight": d.weight,
            "adv_checked": d.adv_checked,   # F9 (v1.8.3): additive key
            "blocked": d.blocked,
            "macro": {"tilt": _json_num(m.facts.get("tilt") if m else None),
                      "damp": _json_num(m.facts.get("damp") if m else 1.0),
                      "mult": _json_num(m.facts.get("mult") if m else 1.0),
                      "mapped": (m.facts.get("mapped") if m else "")},
            "quality": {"score": (q.score if q else None), "grade": (q.grade if q else "-"),
                        "status": (q.status if q else "MISSING"),
                        "engine_status": (q.facts.get("engine_status") if q else None),
                        "rank": (q.facts.get("rank") if q else None),
                        "pool": (q.facts.get("sector") if q else None),
                        "coverage": (q.facts.get("coverage") if q else None),
                        "flags": list(q.flags) if q else []},
            "earnings": {"score": (e.score if e else None), "grade": (e.grade if e else "-"),
                         "status": (e.status if e else "MISSING"),
                         "plan": (e.facts.get("plan") if e else None),
                         "now": bool(e.facts.get("now")) if e else False,
                         "p_next_big": _json_num(e.facts.get("p_next_big") if e else None)},
            "reasons": list(d.reasons)})
        # phase 3: registered extra layers; phase 5: ML p / n / adj carried
        ov = {}
        for lname, s in d.layers.items():
            if lname in ("macro", "quality", "earnings"):
                continue
            e2: dict[str, Any] = {"status": s.status, "score": _json_num(s.score),
                                  "grade": s.grade}
            for k in ("p_q", "p_e", "p_m", "n_q", "n_e", "adj", "state"):
                v = s.facts.get(k)
                if v is None:
                    continue
                e2[k] = (_json_num(v) if isinstance(v, (int, float))
                         and not isinstance(v, bool) else v)
            ov[lname] = e2
        if ov:
            decisions[-1]["overlays"] = ov   # phase 3: registered extra layers
    return {
        "schema": 1, "master": __version__, "mode": str(getattr(ns, "depth", None)
                                                         or getattr(ns, "mode", "") or ""),
        "net_mode": out.net_mode, "net_probe": out.net_probe,
        "refresh": (dict(out.refresh) if out.refresh else None),
        # v1.8.1 (N4): FETCH HEALTH in JSON (ADDITIVE key; the empty
        # ledger is still an object — nulls only inside, never NaN).
        "fetch_health": (dict(getattr(out, "fetch_health", None) or {})),
        "as_of": out.ctx.as_of, "live_date": (None if out.ctx.as_of else date.today().isoformat()),
        "macro_effective": (state.effective_as_of if state else None),
        "risk_budget": _json_num(round(float(out.ctx.risk_budget), 3)),
        "stubbed": out.stubbed,
        "offline": bool(out.ctx.flags.get("offline")),      # P2-2: the manifest says it
        "definitions": {                                     # P2-11 (H5)
            "conviction": "0-100 research heuristic (0.65*Q + 0.35*E, missing-E "
                          "x0.90 haircut, weak-E x0.5 renormalised, macro tilt "
                          "max +/-10 percent); never a probability",
            "p_next_big": "modelled chance of a big EPS beat next quarter "
                          "(engine output), not an expected return",
        },
        "disclaimer": "research screener, not investment advice; never a buy/sell "
                      "instruction or an alpha claim",
        "layers": layers, "decisions": decisions,
        "warnings": list(out.warnings),
        "timings": {k: round(v, 2) for k, v in out.timings.items()}}



# ── § 6.9b · v1.8.0 (W3): Markdown / HTML export (plain, offline-safe) ──────
def _fmt_num(x: Any, spec: str | None = None) -> str:
    """v1.8.0 (W3): ONE number formatter for the export surfaces —
    CONF_DIGITS is the single source (conviction:1, mult:3, score:0,
    time:1), so every number in md/html renders with the same digits a
    terminal reader sees. None stays 'n/a' (never NaN, never a bare 0)."""
    d = CONFIG["CONF_DIGITS"]
    spec = spec or (".1f" if d.get("conviction", 1) == 1 else ".0f")
    if x is None or (isinstance(x, float) and x != x):
        return "n/a"
    try:
        return format(float(x), spec)
    except (TypeError, ValueError):
        return str(x)


def _export_rows(out: RunOutput, ns: argparse.Namespace) -> list[Decision]:
    """The same filter the table applies (--top N, --min-conviction X)."""
    rows = [d for d in out.decisions
            if float(d.conviction) >= float(getattr(ns, "min_conviction", 0.0))]
    top = int(getattr(ns, "top", CONFIG["DEFAULT_TOP"]) or 20)
    return rows[:top]


def render_markdown(out: RunOutput, ns: argparse.Namespace) -> str:
    """v1.8.0 (W3): the Markdown report — same decisions, same filters,
    same honest wording as the terminal render; plain text, no colour,
    no external assets; numbers via _fmt_num (CONF_DIGITS)."""
    md: list[str] = []
    md.append(f"# M.E. report — master v{__version__} · "
              f"{getattr(ns, 'mode', 'standard')}")
    md.append("")
    counts = {"LONG": 0, "WATCH": 0, "AVOID": 0}
    for d in out.decisions:
        if d.action in counts:
            counts[d.action] += 1
    md.append(f"verdict: {counts['LONG']} LONG / {counts['WATCH']} WATCH / "
              f"{counts['AVOID']} AVOID · warnings: {len(out.warnings or [])}"
              + (f" · SYNTHETIC (stubbed)" if out.stubbed else ""))
    md.append("")
    md.append("| layer | engine | status | scored | elapsed |")
    md.append("| --- | --- | --- | --- | --- |")
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        res = out.results[name]
        mod = _LAYER_MODULE.get(name, name)
        ver = ("stub" if res.engine_version == "stub" and out.stubbed
               else str(res.engine_version or "?"))
        scored = (f"{res.ctx_out.get('scored', 'n/a')}/"
                  f"{res.ctx_out.get('total', 'n/a')}"
                  if res.ctx_out.get("total") else "n/a")
        md.append(f"| {name} | {mod} {ver} | {res.status} | {scored} | "
                  f"{_fmt_num(res.elapsed_s, '.1f')}s |")
    md.append("")
    rows = _export_rows(out, ns)
    if rows:
        md.append("| ticker | sector | action | conviction | grade | "
                  "quality | earnings |")
        md.append("| --- | --- | --- | --- | --- | --- | --- |")
        for d in rows:
            q = d.layers.get("quality")
            e = d.layers.get("earnings")
            md.append(f"| {d.ticker} | {d.sector or 'n/a'} | {d.action} | "
                      f"{_fmt_num(d.conviction)} | {d.grade} | "
                      f"{_fmt_num(q.score if q else None)} | "
                      f"{_fmt_num(e.score if e else None)} |")
        md.append("")
    for w in (out.warnings or [])[:20]:
        md.append(f"- warning: {w}")
    if out.warnings:
        md.append("")
    md.append("---")
    md.append("Research screener, not investment advice. No live trades "
              "are placed.")
    return "\n".join(md) + "\n"


def render_html(out: RunOutput, ns: argparse.Namespace) -> str:
    """v1.8.0 (W3): the HTML report — self-contained (no external
    assets, no scripts), the same rows/wording as render_markdown; HTML
    is escaped; numbers via _fmt_num."""
    def esc(x: Any) -> str:
        return (str(x).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    counts = {"LONG": 0, "WATCH": 0, "AVOID": 0}
    for d in out.decisions:
        if d.action in counts:
            counts[d.action] += 1
    h = ["<!DOCTYPE html>", "<html lang=\"en\">", "<head>",
         "<meta charset=\"utf-8\">",
         f"<title>M.E. report v{esc(__version__)}</title>", "</head>",
         "<body>", f"<h1>M.E. report — master v{esc(__version__)} · "
         f"{esc(getattr(ns, 'mode', 'standard'))}</h1>",
         f"<p>verdict: {counts['LONG']} LONG / {counts['WATCH']} WATCH / "
         f"{counts['AVOID']} AVOID · warnings: {len(out.warnings or [])}"
         + (" · SYNTHETIC (stubbed)" if out.stubbed else "") + "</p>",
         "<h2>layers</h2>", "<table>",
         "<tr><th>layer</th><th>engine</th><th>status</th>"
         "<th>scored</th><th>elapsed</th></tr>"]
    for name in sorted(out.results, key=lambda n: out.results[n].order):
        res = out.results[name]
        mod = _LAYER_MODULE.get(name, name)
        ver = ("stub" if res.engine_version == "stub" and out.stubbed
               else str(res.engine_version or "?"))
        scored = (f"{res.ctx_out.get('scored', 'n/a')}/"
                  f"{res.ctx_out.get('total', 'n/a')}"
                  if res.ctx_out.get("total") else "n/a")
        h.append(f"<tr><td>{esc(name)}</td><td>{esc(mod)} {esc(ver)}</td>"
                 f"<td>{esc(res.status)}</td><td>{esc(scored)}</td>"
                 f"<td>{_fmt_num(res.elapsed_s, '.1f')}s</td></tr>")
    h.append("</table>")
    rows = _export_rows(out, ns)
    if rows:
        h += ["<h2>decisions</h2>", "<table>",
              "<tr><th>ticker</th><th>sector</th><th>action</th>"
              "<th>conviction</th><th>grade</th><th>quality</th>"
              "<th>earnings</th></tr>"]
        for d in rows:
            q = d.layers.get("quality")
            e = d.layers.get("earnings")
            h.append(f"<tr><td>{esc(d.ticker)}</td>"
                     f"<td>{esc(d.sector or 'n/a')}</td>"
                     f"<td>{esc(d.action)}</td>"
                     f"<td>{_fmt_num(d.conviction)}</td>"
                     f"<td>{esc(d.grade)}</td>"
                     f"<td>{_fmt_num(q.score if q else None)}</td>"
                     f"<td>{_fmt_num(e.score if e else None)}</td></tr>")
        h.append("</table>")
    if out.warnings:
        h += ["<h2>warnings</h2>", "<ul>"]
        h += [f"<li>{esc(w)}</li>" for w in out.warnings[:20]]
        h.append("</ul>")
    h += ["<hr>", "<p>Research screener, not investment advice. "
          "No live trades are placed.</p>", "</body>", "</html>"]
    return "\n".join(h) + "\n"
