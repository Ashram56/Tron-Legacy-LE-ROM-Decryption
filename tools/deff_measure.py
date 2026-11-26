#!/usr/bin/env python3
"""CONTROL ONLY (confirm, never source): how many frames of each reference capture the generated frames reproduce exactly.

Columns 41-127 (the status panel, columns 0-40, depends on live game state), every reference frame. Usage:
  TRON_ROM=... deff_measure.py [OUT.json]
"""
import sys, glob, os, json
sys.path.insert(0, os.path.dirname(__file__))
import deff_frames as F
from PIL import Image, ImageSequence
from multiprocessing import Pool
BASE = os.path.join(os.path.dirname(__file__), "..", "mpf_package", "media", "dmd")


def score(d):
    g = glob.glob(BASE + "/deff_%03d_*/reference_capture.gif" % d)
    if not g:
        return d, None
    try:
        snaps, _ = F.frames(d)
    except Exception:
        return d, None
    mine = [F.mix(a, b) for r0, r1, a, b in snaps]
    if not mine:
        return d, None
    crop = [bytes(f[y * 128 + x] for y in range(32) for x in range(41, 128)) for f in mine]
    have = set(crop)
    refs = [[v // 17 for v in fr.convert("L").resize((128, 32)).get_flattened_data()] for fr in ImageSequence.Iterator(Image.open(g[0]))]
    ex = sum(1 for rr in refs if bytes(rr[y * 128 + x] for y in range(32) for x in range(41, 128)) in have)
    return d, (ex, len(refs), len(mine))


if __name__ == "__main__":
    with Pool(4) as p:
        res = dict(p.map(score, range(1, 146), chunksize=2))
    ok = {d: v for d, v in res.items() if v}
    print("effects with every reference frame reproduced:", sum(1 for v in ok.values() if v[0] == v[1]), "of", len(ok))
    print("reference frames reproduced:", sum(v[0] for v in ok.values()), "of", sum(v[1] for v in ok.values()))
    print("effects without frames:", [d for d, v in res.items() if v is None])
    if len(sys.argv) > 1:
        json.dump(res, open(sys.argv[1], "w"))
