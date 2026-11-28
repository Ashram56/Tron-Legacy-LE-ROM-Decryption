#!/usr/bin/env python3
"""Remove every emulator-observed field from rom_data/deffs (owner decision 2026-11-26: delete and redo from the code).

What stays is what the static walker read from the ROM (tag "code"). Rows that existed only because the emulator
saw them (screen "observed_only") are dropped. Code-run data (Unicorn runs of the ROM routines) is added by tools/deff_runs.py.
"""
import csv, json, re, sys
D = "rom_data/deffs/"

def clean(o):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if "observed" in k or k == "capture_timing_json":
                continue
            out[k] = clean(v)
        if out.get("tag") == "observed":
            out["tag"] = "code"
        return out
    if isinstance(o, list):
        return [clean(x) for x in o]
    return o

d = json.load(open(D + "deffs.json"))
d = clean(d)
d["source"] = "trn_174h (Tron Legacy LE 1.74); read from the ROM code by rom_data/tools/deff_static.py (static walk), run data from tools/deff_*.py (Unicorn running the ROM routines)"
json.dump(d, open(D + "deffs.json", "w"), indent=1)

def strip_csv(name, drop_rows=lambda r: False):
    rows = list(csv.DictReader(open(D + name)))
    keep = [c for c in rows[0] if "observed" not in c]
    out = []
    for r in rows:
        if drop_rows(r) or r.get("tag") == "observed" and r.get("screen") == "observed_only":
            continue
        r = {c: r[c] for c in keep}
        if r.get("tag") == "observed": r["tag"] = "code"
        for c in ("notes", "picks"):
            if c in r:
                r[c] = re.sub(r"\s*\|\s*observed[^|]*", "", r[c])
                r[c] = re.sub(r"observed [^;|]*;?\s*", "", r[c])
        out.append(r)
    w = csv.DictWriter(open(D + name, "w", newline=""), fieldnames=keep); w.writeheader(); w.writerows(out)
    print(name, len(rows), "->", len(out))

strip_csv("text_draws.csv")
strip_csv("random_parts.csv")
