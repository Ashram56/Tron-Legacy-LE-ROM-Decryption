#!/usr/bin/env python3
"""Run a deff with the ROM's own OS drawing routines in Unicorn and dump the two DMD pages shown at each flip.

No stub for the blit and text routines: the OS code draws into the DMD pages (0x01080000 + 0x1000 * index, one byte per
pixel, 255 = untouched), dmd_show_pages(page0, page1) (0x27830) snapshots them. Output: PNG per flip (page0 level, page1
level, 255 shown as 0) and frames.json (tick, page indices). page0 is the foreground, page1 the background; the mix is the FPGA's
(rule from PinMAME's model, hardware tag; to confirm, boards_inventory.md DMD output).
Usage: deff_frames.py DEFF_ID OUTDIR [max_ticks]
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import deff_unicorn as D
from unicorn.arm_const import *
from unicorn import UC_HOOK_CODE
from PIL import Image

for k in (0x2b194, 0x2b2a0, 0x28ca8, 0x28d5c, 0x28e48, 0xa58c):   # real OS routines draw
    D.NAMES.pop(k, None)


def frames(deff, max_ticks=400):
    snaps, orig = [], D.build

    def build():
        mu = orig()

        def h(mu, a, s, u):
            r0, r1 = mu.reg_read(UC_ARM_REG_R0), mu.reg_read(UC_ARM_REG_R1)
            snaps.append((r0, r1, bytes(mu.mem_read(0x01080000 + 0x1000 * r0, 0x1000)),
                          bytes(mu.mem_read(0x01080000 + 0x1000 * r1, 0x1000))))
        mu.hook_add(UC_HOOK_CODE, h, begin=0x27830, end=0x27830)
        return mu
    D.build = build
    try:
        fn, fl, pr, log = D.run(deff, 600000)
    finally:
        D.build = orig
    ticks = [t for t, n, *_ in log if n == "dmd_show_pages"]
    return snaps, ticks


def mix(fg, bg):
    """Display mixer (knowledge/sam_hardware/CPU_BOARD_IO.md 3.2, PinMAME sam_dmd; hardware, no ROM firmware):
    mask = fg >> 4; pixel = (bg & mask) | (fg & ~mask), low 4 bits."""
    return [(((b & (f >> 4)) | (f & ~(f >> 4))) & 15) for f, b in zip(fg, bg)]


def png(fg, bg):
    im = Image.new("L", (128, 32))
    im.putdata([v * 17 for v in mix(fg, bg)])
    return im


if __name__ == "__main__":
    d, out = int(sys.argv[1]), sys.argv[2]
    os.makedirs(out, exist_ok=True)
    snaps, ticks = frames(d)
    meta = []
    for i, (r0, r1, a, b) in enumerate(snaps):
        png(a, b).save(os.path.join(out, "f%03d.png" % i))
        meta.append({"frame": i, "tick": ticks[i] if i < len(ticks) else None, "page0": r0, "page1": r1})
    json.dump(meta, open(os.path.join(out, "frames.json"), "w"), indent=1)
    print(len(snaps), "flips")
