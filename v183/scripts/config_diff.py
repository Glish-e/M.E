"""config_diff.py - H2 gate: diff CONFIG (+ rationales) between the baseline
master and the current one. Exit 0 = identical, exit 1 = differences (printed).

Usage: python3 scripts/config_diff.py baseline/master_v1_1_0.py master.py
"""
import importlib.util
import json
import sys


def load_config(path: str, alias: str) -> dict:
    # phase 5: master.py now imports codes.py (the central registry) — the
    # module's own directory must be importable when loading by path.
    import os
    mod_dir = os.path.dirname(os.path.abspath(path))
    if mod_dir not in sys.path:
        sys.path.insert(0, mod_dir)
    spec = importlib.util.spec_from_file_location(alias, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)          # import master has no side effects
    cfg, rat = dict(mod.CONFIG), dict(mod.config_rationales())
    sys.modules.pop(alias, None)
    return {"values": cfg, "rationales": rat}


def main() -> int:
    base_path, cur_path = sys.argv[1], sys.argv[2]
    base, cur = load_config(base_path, "master_base"), load_config(cur_path, "master_cur")
    vdiff = {}
    for k in sorted(set(base["values"]) | set(cur["values"])):
        b, c = base["values"].get(k, "<absent>"), cur["values"].get(k, "<absent>")
        try:
            same = (b == c) or (json.dumps(b, sort_keys=True, default=str)
                                == json.dumps(c, sort_keys=True, default=str))
        except TypeError:
            same = b == c
        if not same:
            vdiff[k] = (b, c)
    rdiff = {k: (base["rationales"].get(k, "<absent>"), cur["rationales"].get(k, "<absent>"))
             for k in sorted(set(base["rationales"]) | set(cur["rationales"]))
             if base["rationales"].get(k) != cur["rationales"].get(k)}
    print(f"baseline: {base_path} ({len(base['values'])} entries)")
    print(f"current : {cur_path} ({len(cur['values'])} entries)")
    if not vdiff and not rdiff:
        print("CONFIG DIFF: EMPTY (values and rationales identical)")
        return 0
    for k, (b, c) in vdiff.items():
        print(f"VALUE CHANGED {k}:\n  base={b!r}\n  curr={c!r}")
    for k, (b, c) in rdiff.items():
        print(f"RATIONALE CHANGED {k}:\n  base={b!r}\n  curr={c!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
