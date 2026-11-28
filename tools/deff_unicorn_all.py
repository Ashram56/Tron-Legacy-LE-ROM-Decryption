#!/usr/bin/env python3
"""Run every deff of trn_174h through tools/deff_unicorn.py; write rom_data/deffs/code_draws.json.

Source: ROM code executed in Unicorn with OS stubs (no emulator capture). Per deff: entry fn, priority, and the ordered
call log (tick, call, r0-r3, 4 stack words, return address) of the first 400 calls. Status per deff: ok / empty / spins
(task_sleep loop, needs game state) / error. First pass: OS state (RAM, tasks) is not simulated, so values read from
RAM are zero and effects that wait on state stop early.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import deff_unicorn as D
out = {}
for d in range(1, 147):
    fn, fl, pr, log = D.run(d, 300000)
    sleeps = sum(1 for _, n, *_ in log if n == "task_sleep")
    st = "error" if any(n.startswith("UC_ERROR") for _, n, *_ in log) else "empty" if not log else "spins" if sleeps > 5000 else "ok"
    out[d] = {"fn": hex(fn), "flags": fl, "prio": pr, "status": st,
              "calls": [[t, n, [hex(x) for x in r], [hex(x) for x in s], hex(lr)] for t, n, r, s, lr in log[:400]]}
p = os.path.join(os.path.dirname(__file__), "..", "rom_data", "deffs", "code_draws.json")
json.dump(out, open(p, "w"), indent=0)
import collections
print(collections.Counter(v["status"] for v in out.values()))
