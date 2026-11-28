"""Game states for the display effects that read RAM/NVRAM, built from what the ROM code reads and writes.
Used with tools/deff_frames.py (frames(..., ram=..., init=...)).

Each state is a dict {address: u32 word} for D.run(ram=...). Where the state comes from (code):
 - factory settings: INSTALL FACTORY 0x1278 (run as init), writes the adjustments the effects read with adj_get;
 - credits record at 0x2111008 {i32 units, u8 credits, u8 checksum = ~sum(first 5 bytes)} (descriptor table
   0x040e0bb0 + 0x28, FUN_00004d48 / FUN_0000482c);
 - game: gf_state 0x37274, players 0x2110900, current player / ball 0x3817c / 0x3817d, scores 0x021109e4;
 - display pages: DAT_0003d530 (work 0 page) and DAT_0003d52c (work 1 page) from dmd_page_alloc_pair;
 - error log (deff 9): ten records at 0x02110084 + 8*i {u32 type (1 or 2), u16 code, u8 check at +6}, written by
   error_log 0x5ac8 style callers (FUN_000012bc and others), summary read by FUN_00005b08 / FUN_00005b60.
"""
import struct

INIT = (0x2ae54, (0x1278, 0))   # image cache heap, INSTALL FACTORY


def credit(units=0, credits=0):
    b = bytearray(8)
    struct.pack_into('<i', b, 0, units)
    b[4] = credits
    b[5] = (~sum(b[:5])) & 255
    return {0x2111008: struct.unpack_from('<I', b, 0)[0], 0x211100c: struct.unpack_from('<I', b, 4)[0]}


def game(nplayers=1, cur=1, ball=1, scores=(0, 0, 0, 0), credits=0):
    r = {0x37274: 0, 0x2110900: nplayers, 0x3817c: cur | (ball << 8), 0x3d52c: 1, 0x3d530: 0}
    r.update(credit(0, credits))
    for i, s in enumerate(scores):
        r[0x21109e4 + 4 * i] = s
    return r


def error_log(n2=0, n1=0, code=0x35):
    ram = {}
    for i in range(10):
        t = 2 if i < n2 else (1 if i < n2 + n1 else 0)
        if not t:
            continue
        b = bytes([t, 0, 0, 0]) + bytes([code & 255, code >> 8])
        ram[0x02110084 + 8 * i] = t
        ram[0x02110088 + 8 * i] = code | (((~sum(b)) & 255) << 16)
    return ram
