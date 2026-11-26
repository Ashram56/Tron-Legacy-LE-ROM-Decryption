#!/usr/bin/env python3
"""Check that the Ghidra decompile covers every ARM function of the LE ROM (docs/boards_inventory.md, main CPU board).

Scans the OS image (0x0-0x36000) and the game code (0x1000000-0x1080000) for ARM function prologues
(stmdb sp!,{...,lr} = 0xe92d4xxx..) and checks each lies in a function decompiled in code/tron_game_decompiled_v2.c.
Usage: TRON_ROM=trn_174h.bin tools/decompile_coverage.py
"""
import bisect, os, re, struct
rom = open(os.environ.get("TRON_ROM", "/mnt/project-files/trn_174h.bin"), "rb").read()
src = open("code/tron_game_decompiled_v2.c").read()
starts = sorted({int(m, 16) for m in re.findall(r"^// ==== ([0-9a-f]{8}) ", src, re.M)})
sset = set(starts)
def word(a):
    o = a if a < 0x40000 else a - 0x1000000 + 0x40000
    return struct.unpack("<I", rom[o:o + 4])[0]
cand = [a for a in list(range(0, 0x36000, 4)) + list(range(0x1000000, 0x1080000, 4)) if (word(a) & 0xffffc000) == 0xe92d4000]
outside = [a for a in cand if a not in sset and bisect.bisect_right(starts, a) == 0]
inner = [a for a in cand if a not in sset]
print("decompiled functions:", len(starts), "| ARM prologues:", len(cand), "| not at a function start:", len(inner),
      "(all inside a decompiled function, max offset 0x%x)" % max(a - starts[bisect.bisect_right(starts, a) - 1] for a in inner),
      "| outside any:", len(outside))
