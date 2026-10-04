"""Shared reader for trn_174h.bin (Tron Legacy LE 1.74, Stern SAM).

Runtime address -> file offset, as in AGENTS.md section 2:
  0x00000000-0x000fffff  OS code + RAM initial values (same offset in the file)
  0x01000000-0x010fffff  game code, file = addr - 0x01000000 + 0x40000
  0x04000000-0x047fffff  data, first 8 MB of the file
  banked pointers        (p >> 24) * 0x800000 + (p & 0xffffff)
Set TRON_ROM to the ROM path (default /mnt/project-files/trn_174h.bin).
"""
import os
import struct

ROM_PATH = os.environ.get("TRON_ROM", "/mnt/project-files/trn_174h.bin")
ROM = open(ROM_PATH, "rb").read()


def foff(a):
    if a < 0x100000:
        return a
    if 0x01000000 <= a < 0x01100000:
        return a - 0x01000000 + 0x40000
    if 0x04000000 <= a < 0x04800000:
        return a - 0x04000000
    return None


def banked(p):
    """File offset of a banked pointer bank<<24 | offset."""
    return (p >> 24) * 0x800000 + (p & 0xffffff)


def u8(a): return ROM[foff(a)]
def u16(a): return struct.unpack_from("<H", ROM, foff(a))[0]
def s16(a): return struct.unpack_from("<h", ROM, foff(a))[0]
def u32(a): return struct.unpack_from("<I", ROM, foff(a))[0]
def s32(a): return struct.unpack_from("<i", ROM, foff(a))[0]
def fu8(o): return ROM[o]
def fu16(o): return struct.unpack_from("<H", ROM, o)[0]
def fs16(o): return struct.unpack_from("<h", ROM, o)[0]
def fu32(o): return struct.unpack_from("<I", ROM, o)[0]


def cstr_file(o, maxlen=400):
    e = ROM.find(b"\0", o)
    if e < 0 or e - o > maxlen:
        return None
    return ROM[o:e].decode("latin1")


def cstr(a, maxlen=400):
    o = foff(a)
    return None if o is None else cstr_file(o, maxlen)


NMSG = u32(0x040d0da0)


def msg(i):
    """Message text (language 0 = English) for message id i, via msg_get 0xa58c's table 0x040eeb7c."""
    if i is None or i >= NMSG:
        return None
    p = u32(0x040eeb7c + 4 * i)
    if foff(p) is None:
        return None
    q = u32(p)
    return cstr(q) if foff(q) is not None else None


def hx(v, w=0):
    return ("0x%0" + str(w) + "x") % v if w else "0x%x" % v


# ---- capstone helpers -------------------------------------------------------------------
_md = None


def md():
    global _md
    if _md is None:
        import capstone
        _md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        _md.detail = True
    return _md


def disasm(a, n=None, size=0x400):
    o = foff(a)
    return list(md().disasm(ROM[o:o + size], a))[: n or None]


def code_ranges():
    """(start, end) of the two ARM code blocks."""
    return [(0x0, 0x36000), (0x01000000, 0x01000000 + 0x100000)]


def find_bl_callers(target):
    """Addresses of every BL/B to target in both code blocks (ARM mode, 4-byte aligned)."""
    out = []
    for lo, hi in code_ranges():
        o0 = foff(lo)
        n = (hi - lo) // 4
        for i in range(n):
            w = struct.unpack_from("<I", ROM, o0 + i * 4)[0]
            if (w >> 24) & 0xf in (0xa, 0xb) and (w >> 28) != 0xf:
                off = w & 0xffffff
                if off & 0x800000:
                    off -= 0x1000000
                pc = lo + i * 4
                if pc + 8 + off * 4 == target:
                    out.append((pc, (w >> 24) & 0xf == 0xb))
    return out
