#!/usr/bin/env python3
"""Run every deff routine of trn_174h in Unicorn (the ROM's own code) and tabulate the calls it makes.

Replaces the emulator-observed runs removed from rom_data/deffs (owner decision 2026-11-26). Source: ROM code only; no PinMAME.
Output: rom_data/deffs/code_runs.csv, one row per OS call (deff, tick, call, r0..r3, stack0..3, caller).
Usage: TRON_ROM=trn_174h.bin deff_runs.py
"""
import csv, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from multiprocessing import Pool
import deff_unicorn as D

INIT = (0x2ae54, (0x1278, 0))      # image heap init, INSTALL FACTORY (adjustments); see tools/deff_state.py

def job(e):
    try:
        fn, fl, pr, log = D.run(e, 1500000, args=[0, 0, 0, 0], init=INIT)
    except Exception as x:
        return e, [(0, "ERROR %s" % x, [], [], 0)]
    return e, log

if __name__ == "__main__":
    out = "rom_data/deffs/code_runs.csv"
    with Pool(4) as p:
        res = p.map(job, range(1, 146))
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["deff", "first_tick", "count", "call", "r0", "r1", "r2", "r3", "s0", "s1", "s2", "s3", "caller"])
        for e, log in res:
            seen = {}
            for t, n, r, s, lr in log:      # one row per distinct call (same args and caller), with its count
                if n.startswith("auto_map"): continue
                k = (n, tuple(r), tuple(s), lr)
                if k in seen: seen[k][1] += 1
                else: seen[k] = [t, 1]
            for (n, r, s, lr), (t, c) in seen.items():
                w.writerow([e, t, c, n] + [hex(x) for x in (list(r) + [0] * 4)[:4]] + [hex(x) for x in (list(s) + [0] * 4)[:4]] + [hex(lr)])
    print(sum(len(l) for _, l in res), "calls over", len(res), "deffs")
