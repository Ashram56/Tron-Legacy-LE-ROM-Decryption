#!/usr/bin/env python3
"""Switch -> sound calls, from the ROM code only: run each switch's handler (descriptor word 0, descriptors of 32 bytes
from 0x040f3574, index = switch number - 1) in Unicorn and record the snd_play (0x2c8f4) call ids it makes.

Replaces the `emulated` rows (PinMAME) of callouts/switch_sound_map.csv (owner decision 2026-11-26). Rows already
found statically keep their source; new ones get source "code run (handler 0x...)".
Run after `python tools/switch_sounds.py` from the repository root; needs TRON_ROM=trn_174h.bin and unicorn.
"""
import csv, json, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deff_unicorn as D
import deff_state as S
from multiprocessing import Pool

def run(sw):
    fn = struct.unpack_from("<I", D.ROM, 0xf3574 + 32 * (sw - 1))[0]
    if not fn: return sw, 0, []
    try:
        _, _, _, log = D.run(1, 300000, args=[sw, 0, 0, 0], ram=S.game(), init=S.INIT, fn_addr=fn)
    except Exception:
        return sw, fn, []
    return sw, fn, sorted({x[0] for t, n, x, s, lr in log if n == "snd_play"})

if __name__ == "__main__":
    names = json.load(open("callouts/switch_names.json"))
    calls = {int(r["call_id"], 16): r for r in csv.DictReader(open("callouts/sound_calls.csv"))}
    rows = list(csv.DictReader(open("callouts/switch_sound_map.csv")))
    have = {(int(r["switch"]), int(r["call_id"], 16)) for r in rows}
    with Pool(4) as p:
        res = p.map(run, range(1, 161))
    add = 0
    for sw, fn, ids in res:
        for c in ids:
            if (sw, c) in have or c not in calls: continue
            samples = calls[c]["sample_ids (one picked per play)"].split()
            rows.append({"switch": sw, "switch_name": names.get(str(sw), ""), "call_id": "0x%03x" % c,
                         "source": "code run (handler 0x%x)" % fn, "times_heard": "", "hits": "", "generic": "",
                         "samples_heard": "", "all_samples": calls[c]["sample_ids (one picked per play)"], "kinds": calls[c]["kinds"],
                         "wav": " ".join("samples/%s/%s.wav" % (calls[c]["kinds"].split()[0], s[2:]) for s in samples[:3])})
            add += 1
    rows.sort(key=lambda r: (int(r["switch"]), r["call_id"]))
    w = csv.DictWriter(open("callouts/switch_sound_map.csv", "w", newline=""), fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)
    print("added", add, "rows; total", len(rows))
