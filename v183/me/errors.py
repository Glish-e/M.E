"""me/errors.py — user-error type + phase registry + code registry (v1.8.0
split from master.py §5/§8). MasterError carries its exit code (2 NO-GO /
64 bad usage); _phase names the current run phase (the Ctrl-C line);
_code_registry lazily reads codes.py, the one-source registry of every
user-facing error code, its reason and its fix command (R18)."""
from __future__ import annotations

from typing import Any



class MasterError(Exception):
    """One-line user error carrying its exit code (2 NO-GO / 64 bad usage)."""

    def __init__(self, msg: str, code: int = 2) -> None:
        super().__init__(msg)
        self.code = code


_PHASE_NAME = "startup"


class _phase:
    """Context manager naming the current phase (printed on Ctrl-C, exit 130)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> "_phase":
        global _PHASE_NAME
        _PHASE_NAME = self.name
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


def phase_name() -> str:
    """The current run phase name ('startup' until the first `with
    _phase(...)`; printed on Ctrl-C so the user knows where it died)."""
    return _PHASE_NAME


def _code_registry() -> dict:
    """Lazy codes.py import (master must not import it at module scope)."""
    try:
        import codes
        return codes.REGISTRY
    except Exception:
        return {}


