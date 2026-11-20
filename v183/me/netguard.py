"""me/netguard.py — the v1.8.1 master-side network resilience layer (N1-N9).

Master-owned ONLY: this module never edits an engine file (R1). It wraps
the seams the engines already expose (quality.default_transport, the
earnings instance fetch hooks) and — for the paths with NO engine seam
(meds' FRED calls, earnings' finnhub requests.get) — installs disclosed
PROCESS-LEVEL guards (urllib.request.urlopen, requests.Session.request)
for the duration of one online run, restored afterwards. Every network
call is classified (N5), ledgered (N4), breaker-gated per host (N3),
preflighted (N2), budgeted (N1, N5) and — after a layer's main pass —
deferred-retried once (N9). The evidence map of every engine network
call and its wrappability is evidence/net_paths.md.

This module is importable with stdlib only (no engine imports).
"""
from __future__ import annotations

import itertools
import json
import math
import os
import random
import socket
import threading
import time
import urllib.error
import urllib.parse
from collections import deque
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

__all__ = [
    "Ledger", "CircuitBreaker", "NegCache", "RetryClock", "NetGuard",
    "BreakerOpenError", "classify_status", "classify_exc", "preflight",
    "worst_case_bound", "PERMANENT", "TRANSIENT", "CONFIG", "UNKNOWN",
]

PERMANENT = "PERMANENT"     # 404 / delisted / bad ticker: never retried
TRANSIENT = "TRANSIENT"    # timeout / 429 / 5xx / reset: backoff retries
CONFIG_ERR = "CONFIG"      # 401/403 / missing key: fix the environment
UNKNOWN = "UNKNOWN"

# Error-class words the quality engine's own transport seam returns
# (quality.py:1923-1928) — mapped to the master classification.
_Q_TRANSIENT = ("NETWORK_ERROR", "PROVIDER_ERROR", "RATE_LIMITED")
_Q_CONFIG = ("AUTH_ERROR",)
_Q_PERMANENT = ("NO_DATA", "SCHEMA_ERROR")

_TLS = threading.local()          # per-thread layer attribution (N4)


def _layer_tag() -> str:
    return str(getattr(_TLS, "layer", "") or "pipeline")


@contextmanager
def layer_scope(layer: str):
    """Tag this thread's fetches with the owning layer (N4 ledger)."""
    prev = getattr(_TLS, "layer", None)
    _TLS.layer = str(layer)
    try:
        yield
    finally:
        _TLS.layer = prev


def classify_status(code: int) -> str:
    """HTTP status -> failure class (N5)."""
    try:
        c = int(code)
    except (TypeError, ValueError):
        return UNKNOWN
    if c in (404, 410):
        return PERMANENT
    if c in (401, 403):
        return CONFIG_ERR
    if c == 429 or 500 <= c < 600:
        return TRANSIENT
    return UNKNOWN


def classify_exc(exc: BaseException) -> str:
    """One exception -> failure class (N5). Recognises urllib, socket and
    requests exception shapes plus the engines' own error words."""
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return classify_status(code)
    resp = getattr(exc, "response", None)
    if resp is not None:
        rc = getattr(resp, "status_code", None)
        if isinstance(rc, int):
            return classify_status(rc)
    if isinstance(exc, (socket.timeout, TimeoutError, ConnectionError,
                       ConnectionResetError, ConnectionRefusedError)):
        return TRANSIENT
    if isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, (socket.timeout, TimeoutError, ConnectionError)):
            return TRANSIENT
        text = str(exc).lower()
        if "timed out" in text or "timeout" in text:
            return TRANSIENT
        if "refused" in text or "reset" in text or "unreachable" in text:
            return TRANSIENT
        return TRANSIENT if reason is not None else UNKNOWN
    name = type(exc).__name__
    if any(w in name for w in ("Timeout", "ConnectError", "Connection",
                               "ChunkedEncoding", "Retry", "ProtocolError")):
        return TRANSIENT
    text = str(exc)
    if "api_key" in text or "API key" in text or "401" in text[:8] \
            or "403" in text[:8]:
        return CONFIG_ERR
    if "delisted" in text.lower() or "bad ticker" in text.lower():
        return PERMANENT
    for word in ("timeout", "timed out", "connection reset", "rate limit"):
        if word in text.lower():
            return TRANSIENT
    return UNKNOWN


def _retry_after_of(exc: BaseException) -> float | None:
    """Retry-After seconds from an HTTPError/requests response, if any."""
    hdrs = getattr(exc, "headers", None)
    if hdrs is not None:
        try:
            raw = hdrs.get("Retry-After")
        except Exception:
            raw = None
        if raw:
            try:
                return max(0.0, float(str(raw).strip()))
            except ValueError:
                return None
    return None


class BreakerOpenError(urllib.error.URLError):
    """Raised instantly while a host's circuit breaker is open (N3).
    Subclasses URLError (hence OSError) so every engine's existing
    except-clause treats it as a dead network, never a crash."""

    def __init__(self, host: str, cooldown_s: float):
        super().__init__(
            f"circuit breaker open for host {host} "
            f"(cooldown {cooldown_s:.0f}s — failing fast; probe again after)")
        self.host, self.cooldown_s = host, float(cooldown_s)


class CircuitBreaker:
    """Per-host circuit breaker (N3): closed -> open after K consecutive
    failures OR a failure RATE over a rolling window (v1.8.2, W1) -> calls
    fail instantly during a cooldown -> half-open single probe -> close on
    success, re-open on probe failure.

    v1.8.2 (W1) second trip rule: each record() pushes a weight onto a
    per-host rolling window of the last `window_n` calls (0 for ok,
    1 for a failure, `timeout_weight` for a TIMEOUT failure — timeouts
    cost a full call cap, so they count more); the breaker OPENS when the
    weighted sum reaches `rate * window_n`. This trips intermittent hosts
    (alternating ok/fail) that never accumulate K consecutive failures.
    The consecutive rule stays exactly as it was (v1.8.1)."""

    def __init__(self, k: int, cooldown_s: float, window_n: int = 20,
                 rate: float = 0.5, timeout_weight: float = 2.0):
        self.k = max(1, int(k))
        self.cooldown_s = max(0.05, float(cooldown_s))
        self.window_n = max(2, int(window_n))
        self.rate = min(1.0, max(0.0, float(rate)))
        self.timeout_weight = max(1.0, float(timeout_weight))
        self._fails: dict[str, int] = {}
        self._opened: dict[str, float] = {}
        self._probe: dict[str, bool] = {}
        self._ring: dict[str, deque] = {}

    def _opened_at(self, host: str) -> float | None:
        return self._opened.get(host)

    def state(self, host: str) -> str:
        t = self._opened.get(host)
        if t is None:
            return "closed"
        if time.monotonic() >= t + self.cooldown_s:
            return "half-open"
        return "open"

    def check(self, host: str) -> None:
        """Raise BreakerOpenError unless the call may proceed. In
        half-open, exactly ONE probe goes through (the rest fail fast)."""
        st = self.state(host)
        if st == "closed":
            return
        if st == "open":
            raise BreakerOpenError(host, self.cooldown_s)
        # half-open: single probe
        if self._probe.get(host):
            raise BreakerOpenError(host, self.cooldown_s)
        self._probe[host] = True

    def force_open(self, host: str) -> None:
        """Preflight wiring (N2): a host KNOWN dead in seconds opens its
        breaker immediately, without waiting for K fetch failures."""
        self._opened[host] = time.monotonic()
        self._fails[host] = self.k
        self._probe.pop(host, None)

    def force_open_all(self) -> list[str]:
        """v1.8.2 (W1): the brownout guard — open EVERY known host's
        breaker at once. Returns the hosts that were opened."""
        hosts = sorted(set(self._fails) | set(self._opened) | set(self._ring))
        for h in hosts:
            if self.state(h) == "closed":
                self.force_open(h)
        return hosts

    def _rate_trips(self, host: str) -> bool:
        ring = self._ring.get(host)
        if not ring:
            return False
        return sum(ring) >= self.rate * self.window_n

    def record(self, host: str, ok: bool, err_class: str = "",
               timeout: bool = False) -> None:
        ring = self._ring.setdefault(host, deque(maxlen=self.window_n))
        if ok:
            ring.append(0.0)
            self._fails.pop(host, None)
            self._opened.pop(host, None)
            self._probe.pop(host, None)
            return
        if err_class in (PERMANENT, UNKNOWN):
            # item-level failures are not host-health evidence (a 404 for
            # one ticker says nothing about the host)
            ring.append(0.0)
            return
        # v1.8.2 (W1): timeouts count more (a timeout consumed a full
        # call cap of wall time; a fast 5xx did not)
        ring.append(self.timeout_weight if timeout else 1.0)
        self._fails[host] = self._fails.get(host, 0) + 1
        self._probe.pop(host, None)
        if self._fails[host] >= self.k or self._rate_trips(host):
            self._opened[host] = time.monotonic()


class RetryClock:
    """The total retry-time budget for one run (N5): sleeps for retries
    (backoff, Retry-After, deferred cooldowns) all draw from it."""

    def __init__(self, budget_s: float):
        self.budget_s = max(0.0, float(budget_s))
        self._spent = 0.0

    @property
    def remaining(self) -> float:
        return max(0.0, self.budget_s - self._spent)

    def can_retry(self, sleep_s: float) -> bool:
        return self.remaining >= max(0.0, float(sleep_s))

    def spend(self, sleep_s: float) -> None:
        self._spent += max(0.0, float(sleep_s))


class Ledger:
    """Every fetch attempt of one run (N4): host, layer, item, ok/fail,
    error class, latency, retry count — plus item skips, per-host and
    per-layer aggregation, the live progress line and the jsonl dump
    --retry-failed reads."""

    def __init__(self) -> None:
        self._entries: list[dict] = []
        self._skips: list[dict] = []
        self._recovered: tuple[int, int] | None = None
        self._lock = threading.Lock()
        self._ids = itertools.count(1)

    # -- recording -------------------------------------------------- #
    def new_call_id(self) -> str:
        with self._lock:
            return f"c{next(self._ids)}"

    def record(self, host: str, layer: str, item: Any, *, ok: bool,
               err_class: str = "", err: str = "", latency_s: float = 0.0,
               retries: int = 0, attempt: int = 1, call_id: str | None = None,
               call: str = "") -> None:
        e = {"ts": round(time.time(), 3), "host": str(host),
             "layer": str(layer or "pipeline"), "item": str(item or "")[:80],
             "call": str(call or ""), "ok": bool(ok),
             "err_class": str(err_class or ""), "err": str(err or "")[:160],
             "latency_ms": round(float(latency_s) * 1000.0, 1),
             "retries": int(retries), "attempt": int(attempt),
             "call_id": str(call_id or self.new_call_id()),
             "kind": "attempt"}
        with self._lock:
            self._entries.append(e)

    def skip(self, host: str, layer: str, item: Any, why: str = "",
             fix: str = "") -> None:
        s = {"ts": round(time.time(), 3), "host": str(host),
             "layer": str(layer or "pipeline"), "item": str(item or "")[:80],
             "call": "", "ok": False, "err_class": PERMANENT,
             "err": str(why or "")[:160], "latency_ms": 0.0, "retries": 0,
             "attempt": 0, "call_id": "", "kind": "skip",
             "why": str(why or "")[:160], "fix": str(fix or "")[:160]}
        with self._lock:
            self._skips.append(s)

    def set_recovered(self, n: int, m: int) -> None:
        self._recovered = (int(n), int(m))

    # -- reading ----------------------------------------------------- #
    @property
    def entries(self) -> list[dict]:
        with self._lock:
            return list(self._entries)

    @property
    def skips(self) -> list[dict]:
        with self._lock:
            return list(self._skips)

    def _finals(self) -> dict[str, dict]:
        """call_id -> its LAST attempt (the call's outcome)."""
        out: dict[str, dict] = {}
        for e in self._entries:
            out[e["call_id"]] = e
        return out

    def health(self) -> dict:
        with self._lock:
            finals = self._finals()
            hosts: dict[str, dict] = {}
            layers: dict[str, dict] = {}
            tot = {"ok": 0, "failed": 0, "skipped": 0}

            def _bump(bucket: dict, key: str, ok: bool) -> None:
                d = bucket.setdefault(key, {"ok": 0, "failed": 0,
                                            "skipped": 0})
                d["ok" if ok else "failed"] += 1

            for e in finals.values():
                _bump(hosts, e["host"], e["ok"])
                _bump(layers, e["layer"], e["ok"])
                tot["ok" if e["ok"] else "failed"] += 1
            for s in self._skips:
                hosts.setdefault(s["host"], {"ok": 0, "failed": 0,
                                            "skipped": 0})["skipped"] += 1
                layers.setdefault(s["layer"], {"ok": 0, "failed": 0,
                                               "skipped": 0})["skipped"] += 1
                tot["skipped"] += 1
            skipped_items = [{"host": s["host"], "layer": s["layer"],
                               "item": s["item"], "why": s.get("why", ""),
                               "fix": s.get("fix", "")}
                              for s in self._skips]
            rec = (list(self._recovered)
                   if self._recovered is not None else None)
            return {"hosts": hosts, "layers": layers, "total": tot,
                    "recovered": rec, "skipped_items": skipped_items}

    def health_lines(self) -> list[str]:
        h = self.health()
        lines = []
        for host in sorted(h["hosts"]):
            c = h["hosts"][host]
            lines.append(f"{host} {c['ok']} ok / {c['failed']} failed / "
                          f"{c['skipped']} skipped")
        t = h["total"]
        lines.append(f"totals {t['ok']} ok / {t['failed']} failed / "
                     f"{t['skipped']} skipped")
        if h["recovered"]:
            lines.append(f"recovered {h['recovered'][0]} of "
                         f"{h['recovered'][1]} (deferred retry)")
        for s in h["skipped_items"]:
            lines.append(f"skipped: {s['item']} ({s['why']} — "
                         f"fix: {s['fix']})")
        return lines

    def live(self) -> str:
        t = self.health()["total"]
        return f"ok {t['ok']} | fail {t['failed']} | skip {t['skipped']}"

    def transient_failures(self) -> list[dict]:
        """FINAL failures whose class was TRANSIENT (--retry-failed input
        and the deferred pass input)."""
        return [e for e in self._finals().values()
                if e["ok"] is False and e["err_class"] == TRANSIENT]

    def dump(self, path: str | Path) -> None:
        """Append-safe jsonl write of this run's entries + skips (the
        --retry-failed input; N9)."""
        p = Path(path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        with self._lock:
            rows = [*self._entries, *self._skips]
        tmp = p.with_name(p.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                for r in rows:
                    fh.write(json.dumps(r, default=str) + "\n")
            tmp.replace(p)
        except OSError:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def empty_health(note: str = "") -> dict:
        return {"hosts": {}, "layers": {}, "total": {"ok": 0, "failed": 0,
                                                     "skipped": 0},
                "recovered": None, "skipped_items": [], "note": note}


class NegCache:
    """Item-level negative cache with TTL in a master-owned file (N5/F8):
    PERMANENT failures (404, delisted, bad ticker) are not refetched until
    the TTL expires. Keyed layer:item — the call sites that know the item
    (the quality per-name loop, the earnings fetch hooks)."""

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None
        self.data: dict[str, dict] = {}

    def load(self) -> None:
        if not self.path or not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self.data = {str(k): v for k, v in raw.items()
                             if isinstance(v, dict)}
        except (OSError, ValueError):
            self.data = {}

    def put(self, layer: str, item: str, *, host: str = "", why: str,
            ttl_s: float, fix: str = "") -> None:
        key = f"{layer}:{item}"
        self.data[key] = {"host": str(host), "item": str(item),
                          "why": str(why)[:160], "fix": str(fix)[:160],
                          "until": time.time() + max(1.0, float(ttl_s))}

    def hit(self, layer: str, item: str) -> dict | None:
        e = self.data.get(f"{layer}:{item}")
        if not e:
            return None
        if float(e.get("until", 0.0)) <= time.time():
            self.data.pop(f"{layer}:{item}", None)
            return None
        return e

    def save(self) -> None:
        """Atomic write (B8): a crash mid-write can never truncate the
        previous file."""
        if not self.path:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(self.data, fh, default=str, indent=0)
            tmp.replace(self.path)
        except OSError:
            pass


# F1 (v1.8.3): the preflight DNS watchdog. The stdlib getaddrinfo has NO
# timeout parameter, so a hung resolver stalls the caller forever; each
# resolve now runs in a daemon thread joined with a cap. A stuck resolver
# is ABANDONED (daemon: never blocks interpreter exit) and counted — one
# preflight pass may strand at most _DNS_ABANDON_MAX before every further
# host is marked dead with the honest cap note.
_DNS_ABANDON_MAX = 8
_dns_abandoned = 0


def _reset_dns_abandon() -> None:
    """F1: reset the per-pass abandoned-resolver counter (called at the
    start of every preflight pass so the cap is per-run, never cumulative
    across runs in one process)."""
    global _dns_abandoned
    _dns_abandoned = 0


def _resolve_with_watchdog(host: str, port: int, cap_s: float) -> tuple:
    """(ok, infos_or_None, note). Runs socket.getaddrinfo in a daemon
    thread; join(cap_s). join does NOT kill a stuck resolver — the thread
    is abandoned (daemon: never blocks interpreter exit) and counted
    against _DNS_ABANDON_MAX. F1 (v1.8.3): the stdlib getaddrinfo has no
    timeout; without this the total budget is only checked BETWEEN hosts
    and one hung resolver stalls the run forever. The error note is the
    bare exception type name so a fast gaierror renders the SAME
    'probe failed: <Type>' note the direct call produced (fast-path
    identity); only the timed-out shape is new."""
    global _dns_abandoned
    box: dict = {}

    def _res():
        try:
            box["infos"] = socket.getaddrinfo(host, int(port),
                                               proto=socket.IPPROTO_TCP)
        except BaseException as e:            # noqa: BLE001 - relayed
            box["err"] = e
    th = threading.Thread(target=_res, daemon=True, name="master-dns-cap")
    th.start()
    th.join(float(cap_s))
    if th.is_alive():
        _dns_abandoned += 1
        return (False, None,
                f"dns timeout after {cap_s:.1f}s (resolver abandoned; "
                f"{_dns_abandoned}/{_DNS_ABANDON_MAX} this run)")
    if "err" in box:
        return (False, None, type(box["err"]).__name__)
    return (True, box.get("infos") or [], "")


def preflight(hosts: list, *, budget_s: float, retries: int,
              jitter: bool = True,
              total_budget_s: float | None = None) -> dict[str, dict]:
    """N2: per-host DNS+TCP probe, short timeout, `retries` retries with
    backoff and jitter. Loopback-friendly: hosts are 'host', ('host',
    port), 'host:port'. Returns {spec: {ok, note, latency_ms, attempts}}.
    Never raises.
    v1.8.2 (W1): `total_budget_s` caps the WHOLE preflight pass — once the
    accumulated wall time reaches it, the remaining hosts are marked DEAD
    (ok=False, note says the total budget ran out) so their breakers open
    and the layers fail fast. None keeps the v1.8.1 between-hosts-only
    bound.
    v1.8.3 (F1): the total budget is now enforced IN FLIGHT — each resolve
    runs in a daemon watchdog thread capped by the per-host budget and the
    remaining total (a stuck resolver is abandoned, capped per run by
    _DNS_ABANDON_MAX; a timed-out resolve is never retried past the
    budget), so a DNS-hang outage can no longer stall the pass even on
    the FIRST host. Fast resolvers keep byte-identical notes/latency/
    attempts semantics."""
    out: dict[str, dict] = {}
    t_start = time.monotonic()
    _reset_dns_abandon()
    for spec in hosts:
        if isinstance(spec, str):
            if ":" in spec and not spec.replace(".", "").isdigit():
                host, _, p = spec.rpartition(":")
                port = int(p)
            else:
                host, port = spec, 443
        else:
            host, port = spec
        key = f"{host}:{port}"
        # F1 (v1.8.3): remaining total, computed BEFORE the host is probed —
        # the in-flight resolve cap below draws from it, so the budget is
        # enforced DURING a resolve, not only between hosts.
        remaining = (None if total_budget_s is None else
                     float(total_budget_s) - (time.monotonic() - t_start))
        if remaining is not None and remaining <= 0.0:
            out[key] = {"ok": False,
                        "note": ("preflight total budget "
                                 f"({total_budget_s:.0f}s) exhausted before "
                                 "this host was probed — marked dead so the "
                                 "breaker fails fast (the network is in bad "
                                 "shape; verify with owner_net_check.sh)"),
                        "latency_ms": 0.0, "attempts": 0}
            continue
        if _dns_abandoned >= _DNS_ABANDON_MAX:
            out[key] = {"ok": False,
                        "note": ("dns watchdog abandoned-resolver cap "
                                 f"reached ({_DNS_ABANDON_MAX}) — marked "
                                 "dead; verify with owner_net_check.sh"),
                        "latency_ms": 0.0, "attempts": 0}
            continue
        attempts, ok, note, ms = 0, False, "", 0.0
        t0 = time.monotonic()
        for attempt in range(int(retries) + 1):
            attempts += 1
            try:
                # F1 (v1.8.3): the resolve runs under the daemon watchdog —
                # capped by the per-host budget AND the remaining total.
                host_cap = (float(budget_s) if remaining is None else
                            min(float(budget_s), remaining))
                dns_ok, infos, dns_note = _resolve_with_watchdog(
                    host, port, max(0.05, host_cap))
                if not dns_ok:
                    note = f"probe failed: {dns_note}"
                    if dns_note.startswith("dns timeout"):
                        # a timed-out resolve is NEVER retried past the
                        # budget — the resolver is still stuck.
                        break
                elif not infos:
                    note = "no address resolved"
                else:
                    with socket.create_connection(
                            infos[0][4], timeout=float(budget_s)) as s:
                        pass
                    ok = True
                    ms = (time.monotonic() - t0) * 1000.0
                    note = f"probe ok {ms:.0f} ms"
                    break
            except Exception as e:
                note = f"probe failed: {type(e).__name__}"
            if attempt < int(retries):
                back = 0.05 * (2 ** attempt)
                if jitter:
                    back *= (0.8 + 0.4 * random.random())
                time.sleep(min(back, float(budget_s)))
        out[key] = {"ok": ok, "note": note,
                     "latency_ms": round(ms, 1), "attempts": attempts}
    return out


def _is_timeout(exc: BaseException | None) -> bool:
    """v1.8.2 (W1): did this failure burn wall time waiting (a timeout),
    as opposed to failing fast (refused, 4xx/5xx)? Timeout failures count
    more in the breaker's rate rule — they cost a full call cap."""
    if exc is None:
        return False
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    name = type(exc).__name__
    if "timeout" in name.lower():
        return True
    return "timed out" in str(exc).lower()


class NetGuard:
    """One run's network resilience layer (N1-N9). Install wraps the
    process-level transports; the engine-seam wrappers (wrap_transport,
    wrap_fetch) are used by master's adapters directly.
    v1.8.2 (W1): `brownout_s` is the GLOBAL brownout budget — the total
    wall time the run may spend inside FAILED attempts before every
    breaker is force-opened and all further calls fail fast (successful
    attempts never count; a working-but-slow network does not trip it)."""

    def __init__(self, *, breaker_k: int = 5,
                 breaker_cooldown_s: float = 30.0, call_cap_s: float = 30.0,
                 retry_budget_s: float = 45.0, max_attempts: int = 3,
                 backoff: tuple = (0.5, 1.5), negcache_path: str | Path | None = None,
                 negcache_ttl_s: float = 21600.0, defer_cooldown_s: float = 1.5,
                 run_deadline: float | None = None,
                 layer: str = "pipeline", window_n: int = 20,
                 rate: float = 0.5, timeout_weight: float = 2.0,
                 brownout_s: float | None = None):
        self.ledger = Ledger()
        self.breaker = CircuitBreaker(k=breaker_k,
                                      cooldown_s=breaker_cooldown_s,
                                      window_n=window_n, rate=rate,
                                      timeout_weight=timeout_weight)
        self.clock = RetryClock(budget_s=retry_budget_s)
        self.negcache = NegCache(negcache_path)
        self.negcache.load()
        self.negcache_ttl_s = float(negcache_ttl_s)
        self.call_cap_s = float(call_cap_s)
        self.max_attempts = max(1, int(max_attempts))
        self.backoff = tuple(float(x) for x in backoff) or (0.5,)
        self.defer_cooldown_s = float(defer_cooldown_s)
        self._run_deadline = (float(run_deadline)
                              if run_deadline is not None else None)
        self._default_layer = str(layer or "pipeline")
        self._pending: list[dict] = []
        self._recovered: list[tuple[str, str]] = []
        self._installed: list[tuple[str, Any, Any]] = []
        self._preflight_res: dict[str, dict] = {}
        self._brownout_s = (float(brownout_s)
                            if brownout_s is not None else None)
        self._fail_wall = 0.0            # cumulative FAILED-attempt wall time
        self._brownout_noted = False     # one ledger row per trip, not per call

    # -- construction from CONFIG ------------------------------------ #
    @classmethod
    def from_config(cls, cfg: dict) -> "NetGuard":
        return cls(breaker_k=int(cfg.get("NET_BREAKER_K", 5)),
                   breaker_cooldown_s=float(cfg.get("NET_BREAKER_COOLDOWN_S",
                                                    30.0)),
                   call_cap_s=float(cfg.get("NET_CALL_CAP_S", 30.0)),
                   retry_budget_s=float(cfg.get("NET_RETRY_BUDGET_S", 45.0)),
                   max_attempts=int(cfg.get("RETRY_MAX_ATTEMPTS", 3)),
                   backoff=tuple(cfg.get("RETRY_BACKOFF_S", (0.5, 1.5))),
                   negcache_path=str(cfg.get("NET_NEG_CACHE_PATH",
                                             "data/negative_cache.json")),
                   negcache_ttl_s=float(cfg.get("NET_NEG_CACHE_TTL_S",
                                                21600.0)),
                   defer_cooldown_s=float(cfg.get("NET_DEFER_COOLDOWN_S",
                                                 1.5)),
                   window_n=int(cfg.get("NET_BREAKER_WINDOW_N", 20)),
                   rate=float(cfg.get("NET_BREAKER_RATE", 0.5)),
                   timeout_weight=float(cfg.get("NET_BREAKER_TIMEOUT_WEIGHT",
                                                2.0)),
                   brownout_s=(float(cfg["NET_BROWNOUT_S"])
                               if cfg.get("NET_BROWNOUT_S") else None))

    # -- layer attribution ------------------------------------------- #
    @contextmanager
    def layer_scope(self, layer: str):
        prev = getattr(_TLS, "layer", None)
        _TLS.layer = str(layer)
        try:
            yield
        finally:
            _TLS.layer = prev

    def _layer(self) -> str:
        return _layer_tag() or self._default_layer

    # -- run budget (N1) ---------------------------------------------- #
    @property
    def run_deadline(self) -> float | None:
        return self._run_deadline

    def set_run_deadline(self, deadline: float | None) -> None:
        self._run_deadline = (float(deadline)
                              if deadline is not None else None)

    def _deadline_error(self) -> urllib.error.URLError:
        return urllib.error.URLError(
            "run budget exhausted (RUN_BUDGET_S) — master stopped waiting; "
            "the run renders what it has")

    def _check_deadline(self) -> None:
        if self._run_deadline is not None \
                and time.monotonic() >= self._run_deadline:
            raise self._deadline_error()

    # -- global brownout budget (v1.8.2, W1) -------------------------- #
    @property
    def brownout_tripped(self) -> bool:
        """True once the cumulative FAILED-attempt wall time crossed
        NET_BROWNOUT_S (every breaker was force-opened)."""
        return self._brownout_s is not None and self._fail_wall >= self._brownout_s

    def _brownout_error(self) -> urllib.error.URLError:
        return urllib.error.URLError(
            f"network brownout budget exhausted (NET_BROWNOUT_S="
            f"{self._brownout_s:.0f}s of failed-attempt wall time) — every "
            "breaker force-opened, calls fail fast; the run renders what "
            "it has")

    def _check_brownout(self) -> None:
        if self.brownout_tripped:
            raise self._brownout_error()

    def _record_fail_wall(self, latency_s: float, host: str,
                          layer: str) -> None:
        """Accumulate FAILED-attempt wall time; trip the global guard once
        the budget is crossed (force-open every breaker + one ledger row)."""
        if self._brownout_s is None:
            return
        self._fail_wall += max(0.0, float(latency_s))
        if self._fail_wall >= self._brownout_s \
                and not self._brownout_noted:
            self.breaker.force_open_all()
            self.ledger.record("*", layer, "brownout-guard",
                               ok=False, err_class=TRANSIENT,
                               err=f"brownout budget {self._brownout_s:.0f}s "
                                   f"of failed-attempt wall time crossed "
                                   f"(host {host}) — every breaker open",
                               latency_s=0.0, attempt=1,
                               call_id=self.ledger.new_call_id(),
                               call="brownout")
            self._brownout_noted = True

    # -- preflight (N2) ----------------------------------------------- #
    def preflight(self, hosts: list, *, budget_s: float | None = None,
                  retries: int | None = None,
                  total_budget_s: float | None = None) -> dict[str, dict]:
        cfg_budget = budget_s
        res = preflight(hosts,
                        budget_s=float(cfg_budget if cfg_budget is not None
                                       else 2.0),
                        retries=int(retries if retries is not None else 2),
                        total_budget_s=total_budget_s)
        self._preflight_res = res
        for key, r in res.items():
            self.ledger.record(key.split(":")[0], "pipeline", key,
                               ok=bool(r["ok"]), call="preflight",
                               latency_s=r["latency_ms"] / 1000.0,
                               attempt=1, err_class=(
                                   "" if r["ok"] else TRANSIENT))
            if not r["ok"]:
                self.breaker.force_open(key)     # dead host known in secs
        return res

    # -- helpers ------------------------------------------------------ #
    def _host_item(self, url: str) -> tuple[str, str]:
        try:
            u = urllib.parse.urlparse(str(url))
            return (u.hostname or str(url).split("/")[0], u.path or "/")
        except Exception:
            return (str(url).split("/")[0], "/")

    def _sleep_for(self, attempt: int, exc: BaseException | None) -> float:
        ra = _retry_after_of(exc) if exc is not None else None
        base = self.backoff[min(attempt - 1, len(self.backoff) - 1)]
        if ra is not None:
            # Retry-After is honoured EXACTLY (never undercut by jitter);
            # only a longer backoff may extend it (N5).
            return max(float(ra), base)
        return base * (0.8 + 0.4 * random.random())

    # -- urlopen process guard (meds FRED paths + any urllib call) --- #
    def wrap_urlopen(self, orig: Callable) -> Callable:
        guard = self

        def urlopen_guard(req, timeout=None, *a, **k):
            url = getattr(req, "full_url", None) or str(req)
            host, item = guard._host_item(url)
            layer = guard._layer()
            guard._check_deadline()
            guard._check_brownout()
            guard.breaker.check(host)
            cap = guard.call_cap_s
            if timeout is not None:
                cap = min(float(timeout), guard.call_cap_s)
            cid = guard.ledger.new_call_id()
            attempt = 0
            last: Exception | None = None
            while True:
                attempt += 1
                t0 = time.monotonic()
                try:
                    resp = orig(req, timeout=cap, *a, **k)
                except Exception as e:
                    last = e
                    cls = classify_exc(e)
                    lat = time.monotonic() - t0
                    guard.breaker.record(host, False, cls,
                                         timeout=_is_timeout(e))
                    guard.ledger.record(
                        host, layer, item, ok=False, err_class=cls,
                        err=f"{type(e).__name__}: {e}"[:160],
                        latency_s=lat,
                        retries=attempt - 1, attempt=attempt, call_id=cid,
                        call="urlopen")
                    guard._record_fail_wall(lat, host, layer)
                    guard._check_brownout()
                    if cls != TRANSIENT or attempt >= guard.max_attempts:
                        raise
                    sleep = guard._sleep_for(attempt, e)
                    if not guard.clock.can_retry(sleep):
                        guard.ledger.skip(
                            host, layer, item,
                            why=f"retry budget exhausted after "
                                f"{attempt} attempt(s): {e}"[:160],
                            fix="rerun when the network is back, or "
                                "python3 master.py --retry-failed")
                        raise
                    guard.clock.spend(sleep)
                    time.sleep(sleep)
                    continue
                guard.breaker.record(host, True)
                guard.ledger.record(host, layer, item, ok=True,
                                     latency_s=time.monotonic() - t0,
                                     retries=attempt - 1, attempt=attempt,
                                     call_id=cid, call="urlopen")
                return resp
        urlopen_guard._master_netguard = True
        return urlopen_guard

    # -- requests process guard (finnhub, yfinance-when-present) ----- #
    def wrap_request(self, orig: Callable) -> Callable:
        guard = self

        def request_guard(*a, **k):
            url = ""
            for x in a[:2]:
                if isinstance(x, str) and "://" in x:
                    url = x
            url = url or str(k.get("url", ""))
            host, item = guard._host_item(url)
            layer = guard._layer()
            guard._check_deadline()
            guard._check_brownout()
            guard.breaker.check(host)
            cid = guard.ledger.new_call_id()
            attempt = 0
            while True:
                attempt += 1
                t0 = time.monotonic()
                try:
                    resp = orig(*a, **k)
                except Exception as e:
                    cls = classify_exc(e)
                    lat = time.monotonic() - t0
                    guard.breaker.record(host, False, cls,
                                         timeout=_is_timeout(e))
                    guard.ledger.record(
                        host, layer, item, ok=False, err_class=cls,
                        err=f"{type(e).__name__}: {e}"[:160],
                        latency_s=lat,
                        retries=attempt - 1, attempt=attempt, call_id=cid,
                        call="request")
                    guard._record_fail_wall(lat, host, layer)
                    guard._check_brownout()
                    if cls != TRANSIENT or attempt >= guard.max_attempts:
                        raise
                    sleep = guard._sleep_for(attempt, e)
                    if not guard.clock.can_retry(sleep):
                        raise
                    guard.clock.spend(sleep)
                    time.sleep(sleep)
                    continue
                code = getattr(resp, "status_code", 200)
                if isinstance(code, int) and code >= 400:
                    cls = classify_status(code)
                    lat = time.monotonic() - t0
                    guard.breaker.record(host, False, cls)
                    guard.ledger.record(
                        host, layer, item, ok=False, err_class=cls,
                        err=f"http_{code}", latency_s=lat,
                        retries=attempt - 1, attempt=attempt, call_id=cid,
                        call="request")
                    guard._record_fail_wall(lat, host, layer)
                    guard._check_brownout()
                    if cls != TRANSIENT or attempt >= guard.max_attempts:
                        import requests
                        raise requests.exceptions.HTTPError(
                            f"http_{code} for {host}")
                    sleep = guard._sleep_for(attempt, None)
                    if not guard.clock.can_retry(sleep):
                        raise
                    guard.clock.spend(sleep)
                    time.sleep(sleep)
                    continue
                guard.breaker.record(host, True)
                guard.ledger.record(host, layer, item, ok=True,
                                    latency_s=time.monotonic() - t0,
                                    retries=attempt - 1, attempt=attempt,
                                    call_id=cid, call="request")
                return resp
        request_guard._master_netguard = True
        return request_guard

    # -- quality transport seam wrapper (N3/N4/N5) -------------------- #
    def wrap_transport(self, base: Callable) -> Callable:
        guard = self

        def transport(url: str, headers: dict | None = None,
                      timeout: float | None = None):
            host, item = guard._host_item(url)
            layer = guard._layer()
            try:
                guard._check_deadline()
                guard._check_brownout()
                guard.breaker.check(host)
            except urllib.error.URLError as e:
                return "NETWORK_ERROR", None, None, str(e)
            cid = guard.ledger.new_call_id()
            attempt = 0
            result = None
            while True:
                attempt += 1
                t0 = time.monotonic()
                result = base(url, headers=headers, timeout=timeout)
                status = result[0] if isinstance(result, tuple) and result \
                    else ""
                if status in _Q_TRANSIENT:
                    lat = time.monotonic() - t0
                    timeoutish = "timeout" in str(result[-1]).lower() \
                        or "timed out" in str(result[-1]).lower()
                    guard.breaker.record(host, False, TRANSIENT,
                                         timeout=timeoutish)
                    guard.ledger.record(
                        host, layer, item, ok=False, err_class=TRANSIENT,
                        err=str(result[-1])[:160],
                        latency_s=lat,
                        retries=attempt - 1, attempt=attempt, call_id=cid,
                        call="transport")
                    guard._record_fail_wall(lat, host, layer)
                    guard._check_brownout()
                    if attempt >= guard.max_attempts:
                        return result
                    if guard.brownout_tripped:
                        return ("NETWORK_ERROR", None, None,
                                "network brownout budget exhausted "
                                "(NET_BROWNOUT_S)")
                    sleep = guard._sleep_for(attempt, None)
                    if isinstance(result, tuple) and len(result) >= 3 \
                            and result[2]:
                        try:
                            sleep = max(sleep, float(result[2]))
                        except (TypeError, ValueError):
                            pass
                    if not guard.clock.can_retry(sleep):
                        return result
                    guard.clock.spend(sleep)
                    time.sleep(sleep)
                    continue
                ok = status not in ("NETWORK_ERROR", "PROVIDER_ERROR",
                                    "RATE_LIMITED", "AUTH_ERROR",
                                    "NO_DATA", "SCHEMA_ERROR")
                guard.breaker.record(host, True)
                guard.ledger.record(
                    host, layer, item, ok=ok,
                    err_class=("" if ok else
                               (CONFIG_ERR if status in _Q_CONFIG
                                else PERMANENT)),
                    err="" if ok else str(status),
                    latency_s=time.monotonic() - t0,
                    retries=attempt - 1, attempt=attempt, call_id=cid,
                    call="transport")
                return result
        transport._master_retry = True        # existing idempotence marker
        transport._master_netguard = True
        return transport

    # -- yfinance wrappers (v1.8.2, W2) -------------------------------- #
    # quality's YfinancePriceClient bypasses default_transport entirely
    # (its own sockets via yf.Ticker().history / .info); when yfinance is
    # installed an ONLINE run would otherwise skip the breaker, the call
    # cap and the ledger. master swaps these wrappers onto the class /
    # module attributes for the run's lifetime (restored after; NEVER an
    # engine file edit). yfinance is ABSENT in the tested environment —
    # these wrappers are proven with a FAKE yfinance module only; the
    # owner pack's net_check verifies the real one (UNVERIFIED here).
    _YF_HOST = "query1.finance.yahoo.com"

    def _run_capped(self, fn, args: tuple, cap_s: float) -> tuple:
        """Run fn(*args) in a daemon thread, wait at most cap_s. Returns
        (done, result_or_exception, latency_s). An over-run call is
        ABANDONED (the daemon thread keeps sleeping; it cannot block the
        process exit) — Python threads cannot be killed, and the honest
        answer is a timeout failure, not a hang."""
        box: dict = {}
        t0 = time.monotonic()

        def _run():
            try:
                box["out"] = fn(*args)
            except BaseException as e:            # noqa: BLE001 - relayed
                box["err"] = e
        th = threading.Thread(target=_run, daemon=True,
                              name="master-yf-cap")
        th.start()
        th.join(float(cap_s))
        return (not th.is_alive(), box, time.monotonic() - t0)

    def wrap_yfinance_download(self, orig: Callable) -> Callable:
        """Wrap YfinancePriceClient._download (the engine's own test seam,
        quality.py:3163 — 'the only method that touches the network'):
        breaker gate + NET_CALL_CAP_S deadline (a hanging yf.Ticker()
        .history() is ABANDONED on a daemon thread) + ledger, ONE attempt
        (the engine's own rate-limit retry inside _download is untouched).
        The engine contract is preserved: _download RETURNS (None, err)
        and never raises — the wrapper does the same, so quality's caller
        sees the identical shape it already handles."""
        guard = self
        host = self._YF_HOST

        def _download(self_, ticker: str, start: str, end: str):
            layer = guard._layer()
            try:
                guard._check_deadline()
                guard._check_brownout()
                guard.breaker.check(host)
            except Exception as e:
                return None, f"master-guard:{type(e).__name__}"
            cid = guard.ledger.new_call_id()
            done, box, lat = guard._run_capped(
                orig, (self_, ticker, start, end), guard.call_cap_s)
            if not done:
                guard.breaker.record(host, False, TRANSIENT, timeout=True)
                guard.ledger.record(
                    host, layer, ticker, ok=False, err_class=TRANSIENT,
                    err=f"yfinance call exceeded NET_CALL_CAP_S "
                        f"({guard.call_cap_s:g}s) — abandoned daemon "
                        "thread", latency_s=lat, attempt=1, call_id=cid,
                    call="yfinance")
                guard._record_fail_wall(lat, host, layer)
                return None, "TimeoutError"
            if "err" in box:
                e = box["err"]
                guard.breaker.record(host, False, TRANSIENT,
                                     timeout=_is_timeout(e))
                guard.ledger.record(
                    host, layer, ticker, ok=False, err_class=TRANSIENT,
                    err=f"{type(e).__name__}: {e}"[:160], latency_s=lat,
                    attempt=1, call_id=cid, call="yfinance")
                guard._record_fail_wall(lat, host, layer)
                return None, type(e).__name__
            out = box.get("out")
            # the engine returns (None, err) for provider failures — the
            # wrapper ledgers that as a failed call (it IS one), and passes
            # the tuple through unchanged
            ok = not (isinstance(out, tuple) and len(out) == 2
                      and out[0] is None)
            errtxt = "" if ok else str(out[1])
            cls = ("" if ok else
                   (UNKNOWN if errtxt.startswith("import:") else TRANSIENT))
            guard.breaker.record(host, ok, cls or "",
                                 timeout="timeout" in errtxt.lower())
            guard.ledger.record(
                host, layer, ticker, ok=ok, err_class=cls,
                err=("" if ok else errtxt[:160]), latency_s=lat, attempt=1,
                call_id=cid, call="yfinance")
            if not ok:
                guard._record_fail_wall(lat, host, layer)
            return out
        _download._master_yf_guard = True
        _download._master_netguard = True
        return _download

    def wrap_yfinance_sector(self, orig: Callable) -> Callable:
        """Wrap quality._detect_sector_yfinance (quality.py:15661 —
        yfinance.Ticker(t).info direct call): same policy; the engine
        contract (None on any failure) is preserved, failures are
        ledgered so FETCH HEALTH shows the yfinance path."""
        guard = self
        host = self._YF_HOST

        def _detect(ticker: str):
            layer = guard._layer()
            try:
                guard._check_deadline()
                guard._check_brownout()
                guard.breaker.check(host)
            except Exception:
                return None                     # engine contract: None
            cid = guard.ledger.new_call_id()
            done, box, lat = guard._run_capped(
                orig, (ticker,), guard.call_cap_s)
            if not done:
                guard.breaker.record(host, False, TRANSIENT, timeout=True)
                guard.ledger.record(
                    host, layer, ticker, ok=False, err_class=TRANSIENT,
                    err="yfinance .info exceeded NET_CALL_CAP_S — "
                        "abandoned daemon thread", latency_s=lat,
                    attempt=1, call_id=cid, call="yfinance-sector")
                guard._record_fail_wall(lat, host, layer)
                return None
            if "err" in box:
                e = box["err"]
                cls = classify_exc(e)
                guard.breaker.record(host, False, cls,
                                     timeout=_is_timeout(e))
                guard.ledger.record(
                    host, layer, ticker, ok=False, err_class=cls,
                    err=f"{type(e).__name__}: {e}"[:160], latency_s=lat,
                    attempt=1, call_id=cid, call="yfinance-sector")
                guard._record_fail_wall(lat, host, layer)
                return None
            guard.breaker.record(host, True)
            guard.ledger.record(host, layer, ticker, ok=True,
                                latency_s=lat, attempt=1, call_id=cid,
                                call="yfinance-sector")
            return box.get("out")
        _detect._master_yf_guard = True
        _detect._master_netguard = True
        return _detect

    # -- earnings/provider fetch hook wrapper (N3/N4/N5) --------------- #
    def wrap_fetch(self, fn: Callable, label: str,
                   host_hint: str | None = None) -> Callable:
        guard = self

        def fetch(*a: Any, **k: Any):
            item = next((x for x in a if isinstance(x, str)), "")
            host = str(host_hint or label)
            layer = guard._layer()
            guard._check_deadline()
            guard._check_brownout()
            cid = guard.ledger.new_call_id()
            attempt = 0
            last: Exception | None = None
            while True:
                attempt += 1
                t0 = time.monotonic()
                try:
                    # F11 (v1.8.3): the provider call runs under the SAME
                    # daemon-thread cap as the yfinance wrappers. The
                    # earnings Yahoo provider (yf.Ticker().get_earnings_
                    # dates() / .history(); curl_cffi inside newer
                    # yfinance) previously sat INSIDE this loop with NO
                    # in-flight bound: a hung call outlived call_cap_s AND
                    # the run deadline (the deadline was checked only
                    # BEFORE the call). An over-run call is abandoned
                    # (daemon thread), the host's breaker is force-opened
                    # (a provider stuck past its cap is known-bad, the
                    # preflight treatment), and the honest URLError flows
                    # into the existing except-block as a TRANSIENT
                    # timeout (its text says 'timed out').
                    _rem = (None if guard._run_deadline is None else
                            guard._run_deadline - time.monotonic())
                    _cap = guard.call_cap_s
                    if _rem is not None:
                        _cap = max(0.1, min(_cap, _rem))
                    done, box, _lat = guard._run_capped(
                        lambda: fn(*a, **k), (), _cap)
                    if not done:
                        guard.breaker.force_open(host)
                        raise urllib.error.URLError(
                            f"provider call timed out — exceeded "
                            f"NET_CALL_CAP_S ({guard.call_cap_s:g}s), "
                            f"abandoned after {_lat:.1f}s")
                    if "err" in box:
                        raise box["err"]
                    out = box.get("out")
                except Exception as e:
                    last = e
                    cls = classify_exc(e)
                    lat = time.monotonic() - t0
                    guard.breaker.record(host, False, cls,
                                         timeout=_is_timeout(e))
                    guard.ledger.record(
                        host, layer, item, ok=False, err_class=cls,
                        err=f"{type(e).__name__}: {e}"[:160],
                        latency_s=lat,
                        retries=attempt - 1, attempt=attempt, call_id=cid,
                        call="fetch")
                    guard._record_fail_wall(lat, host, layer)
                    guard._check_brownout()
                    if cls != TRANSIENT or attempt >= guard.max_attempts:
                        # N9: a transient final failure is pending ONE more
                        # (deferred) attempt after the layer's main pass.
                        if cls == TRANSIENT:
                            guard.note_pending(host, layer, item, fn=fn,
                                               args=a, kwargs=k)
                        raise
                    sleep = guard._sleep_for(attempt, e)
                    if not guard.clock.can_retry(sleep):
                        guard.note_pending(host, layer, item, fn=fn,
                                           args=a, kwargs=k)
                        raise
                    guard.clock.spend(sleep)
                    time.sleep(sleep)
                    continue
                guard.breaker.record(host, True)
                guard.ledger.record(host, layer, item, ok=True,
                                   latency_s=time.monotonic() - t0,
                                   retries=attempt - 1, attempt=attempt,
                                   call_id=cid, call="fetch")
                return out
        fetch._master_retry = True
        fetch._master_netguard = True
        return fetch

    # -- deferred retry (N9) ------------------------------------------ #
    def note_pending(self, host: str, layer: str, item: Any, fn: Callable,
                     args: tuple = (), kwargs: dict | None = None,
                     on_ok: Callable | None = None) -> None:
        self._pending.append({"host": str(host), "layer": str(layer),
                              "item": str(item)[:80], "fn": fn,
                              "args": tuple(args),
                              "kwargs": dict(kwargs or {}),
                              "on_ok": on_ok})

    def pending(self, layer: str | None = None) -> list[dict]:
        return [p for p in self._pending
                if layer is None or p["layer"] == layer]

    def recovered_items(self, layer: str | None = None) -> list[str]:
        """Items the last deferred_pass recovered (layers re-score them)."""
        return [i for lay, i in self._recovered
                if layer is None or lay == layer]

    def deferred_pass(self, cooldown_s: float | None = None,
                      deadline: float | None = None) -> tuple[int, int]:
        """ONE more attempt per pending transient item after a cooldown,
        unless the host breaker is open (N9). Returns (recovered, total).
        Items that fail again (or are blocked) end SKIPPED and listed."""
        pend, self._pending = self._pending, []
        if not pend:
            self.ledger.set_recovered(0, 0)
            return (0, 0)
        cd = float(cooldown_s if cooldown_s is not None
                   else self.defer_cooldown_s)
        dl = deadline if deadline is not None else self._run_deadline
        if dl is not None and time.monotonic() + cd >= dl:
            for p in pend:
                self.ledger.skip(p["host"], p["layer"], p["item"],
                                 why="run budget exhausted before the "
                                     "deferred retry",
                                 fix="python3 master.py --retry-failed")
            self.ledger.set_recovered(0, len(pend))
            return (0, len(pend))
        if not self.clock.can_retry(cd):
            for p in pend:
                self.ledger.skip(p["host"], p["layer"], p["item"],
                                 why="retry budget exhausted before the "
                                     "deferred retry",
                                 fix="python3 master.py --retry-failed "
                                     "(reads this run's ledger)")
            self.ledger.set_recovered(0, len(pend))
            return (0, len(pend))
        self.clock.spend(cd)
        time.sleep(cd)
        recovered = 0
        self._recovered = []
        for p in pend:
            host, layer, item = p["host"], p["layer"], p["item"]
            try:
                self.breaker.check(host)
            except BreakerOpenError as e:
                self.ledger.skip(host, layer, item,
                                 why=f"circuit breaker open — {e}"[:160],
                                 fix="wait for the cooldown, rerun, or "
                                     "python3 master.py --retry-failed")
                continue
            t0 = time.monotonic()
            try:
                out = p["fn"](*p["args"], **p["kwargs"])
            except Exception as e:
                cls = classify_exc(e)
                self.breaker.record(host, False, cls)
                self.ledger.record(
                    host, layer, item, ok=False, err_class=cls,
                    err=f"deferred: {e}"[:160],
                    latency_s=time.monotonic() - t0, retries=0, attempt=1,
                    call_id=self.ledger.new_call_id(), call="deferred")
                self.ledger.skip(
                    host, layer, item,
                    why=f"deferred retry failed ({e}) — retry budget "
                        f"{self.clock.remaining:.1f}s left"[:160],
                    fix="python3 master.py --retry-failed after the "
                        "cooldown, or rerun when the host is back")
                continue
            recovered += 1
            self._recovered.append((layer, item))
            self.breaker.record(host, True)
            self.ledger.record(host, layer, item, ok=True,
                               latency_s=time.monotonic() - t0, retries=0,
                               attempt=1,
                               call_id=self.ledger.new_call_id(),
                               call="deferred")
            try:
                if p.get("on_ok") is not None:
                    p["on_ok"](out)
            except Exception:
                pass            # layer re-scoring must never break the pass
        self.ledger.set_recovered(recovered, len(pend))
        return (recovered, len(pend))

    # -- health passthrough ------------------------------------------- #
    def health(self) -> dict:
        h = self.ledger.health()
        if self._preflight_res:
            h["preflight"] = {k: bool(v["ok"])
                              for k, v in self._preflight_res.items()}
        # v1.8.2 (W1): the brownout-guard state (additive key)
        h["brownout"] = {"budget_s": self._brownout_s,
                         "fail_wall_s": round(self._fail_wall, 1),
                         "tripped": self.brownout_tripped}
        return h

    def health_lines(self) -> list[str]:
        return self.ledger.health_lines()

    def live(self) -> str:
        return self.ledger.live()

    # -- process-level install/uninstall (disclosed N3 guard) --------- #
    def install(self) -> None:
        """Patch urllib.request.urlopen (and requests.Session.request when
        requests is importable) for THIS run. Disclosed: a stdlib/third-
        party patch in the master process, NEVER an engine file edit."""
        import urllib.request
        if any(m[0] == "urllib" for m in self._installed):
            return
        orig = urllib.request.urlopen
        urllib.request.urlopen = self.wrap_urlopen(orig)
        self._installed.append(("urllib", urllib.request, orig))
        try:
            import requests
        except Exception:
            return
        if any(m[0] == "requests" for m in self._installed):
            return
        orig_r = requests.Session.request
        requests.Session.request = self.wrap_request(orig_r)
        self._installed.append(("requests", requests.Session, orig_r))

    def uninstall(self) -> None:
        while self._installed:
            _tag, obj, orig = self._installed.pop()
            try:
                if _tag == "urllib":
                    obj.urlopen = orig
                else:
                    obj.request = orig
            except Exception:
                pass


def worst_case_bound(*, preflight_total_s: float, cap_s: float,
                     max_attempts: int, breaker_k: int,
                     retry_budget_s: float, defer_cooldown_s: float,
                     brownout_s: float | None, backoff_max: float) -> dict:
    """v1.8.2 (W1): the WRITTEN worst-case wall-time bounds — the single
    source of truth evidence/net_bounds.md documents and the loopback
    tests assert against. All formulas are conservative (knob-derived
    upper bounds); measured loopback numbers are smaller.

    Components (per run, from t=0):
      preflight_total_s  the whole preflight pass is capped (NET_PREFLIGHT_
                         TOTAL_S): DNS-hang hosts cannot stretch it.
      per-call cost      max_attempts * cap_s + (max_attempts-1) * backoff
      per-host trip      ceil(breaker_k / max_attempts) calls to open a
                         host's breaker via the consecutive rule; the call
                         that trips still completes its attempts.
      brownout           with NET_BROWNOUT_S: preflight + the budget + ONE
                         in-flight attempt (cap) + the deferred-retry skip
                         (cooldown). Without it: per-host trip x 3 host
                         families (macro/quality/earnings run sequentially)
                         — the number that justified the knob.
      intermittent       fast failures trip the RATE rule; every retry
                         sleep is bounded by the total retry budget.
      outage_refused     preflight opens every breaker before the layers
                         (measured: 10 refused connects = 1.2 ms); the
                         layers then fail fast, only the deferred-retry
                         cooldown remains. WITHOUT preflight
                         (MASTER_NET=online valve) add the breaker-trip
                         backoffs.
    """
    attempts = max(1, int(max_attempts))
    k = max(1, int(breaker_k))
    slack = 1.0            # salvage + render + scheduler jitter (measured < 1 s)
    per_call = attempts * float(cap_s) + (attempts - 1) * float(backoff_max)
    calls_to_trip = max(1, math.ceil(k / attempts))
    per_host_trip = calls_to_trip * per_call
    outage_refused = float(preflight_total_s) + float(defer_cooldown_s) + slack
    outage_no_preflight = outage_refused + (calls_to_trip + 1) * float(backoff_max)
    if brownout_s:
        brownout = (float(preflight_total_s) + float(brownout_s)
                    + float(cap_s) + float(defer_cooldown_s) + slack)
    else:
        brownout = (float(preflight_total_s) + 3.0 * per_host_trip
                    + float(defer_cooldown_s) + slack)
    intermittent = (float(preflight_total_s) + float(retry_budget_s)
                    + float(defer_cooldown_s) + slack)
    return {
        "outage_refused": outage_refused,
        "outage_refused_no_preflight": outage_no_preflight,
        "brownout": brownout,
        "brownout_per_host_no_budget": per_host_trip,
        "brownout_no_budget_3_families": 3.0 * per_host_trip,
        "intermittent": intermittent,
        "slow_drip_ok": float(cap_s),
    }
