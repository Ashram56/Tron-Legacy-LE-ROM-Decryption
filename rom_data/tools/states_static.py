"""Static extraction for rom_data/states (Tron Legacy LE 1.74, trn_174h).

Reads the ROM through rom_data/tools/rom.py and writes:
  rom_data/states/dedicated_switches.csv   dedicated switch table 0x040f4074 (D1-D32) + PinMAME numbers
  rom_data/states/static_calls.json        every call site of task_create*/event_hook_add/GI/RNG with resolved
                                           constant arguments (used by states_build.py for os_model.json)
Run: python3 rom_data/tools/states_static.py
"""
import bisect
import csv
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rom import ROM, foff, u8, u16, u32, cstr, disasm, find_bl_callers, md  # noqa: E402

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(REPO, "rom_data", "states")
DECOMP = os.path.join(REPO, "code", "tron_game_decompiled_v2.c")

# ---------------------------------------------------------------- function names from the decompile headers
_heads = []
if os.path.exists(DECOMP):
    for line in open(DECOMP, errors="replace"):
        m = re.match(r"// ==== ([0-9a-f]{8}) (\S+)", line)
        if m:
            _heads.append((int(m.group(1), 16), m.group(2)))
_heads.sort()
_haddr = [a for a, _ in _heads]
_hname = {a: n for a, n in _heads}


def func_of(a):
    i = bisect.bisect_right(_haddr, a) - 1
    return (_heads[i][0], _heads[i][1]) if i >= 0 else (None, None)


def name_of(a):
    return _hname.get(a)


# ---------------------------------------------------------------- tiny forward register tracker
def regs_before(call, window=24):
    """Constant values of r0-r3 at the BL `call`, from a forward scan of the previous `window` instructions.
    Handles mov/mvn #imm, ldr rX,[pc,#off], add/sub/orr rX,rY,#imm, mov rX,rY, lsl #imm; a BL clobbers r0-r3."""
    start = max(call - 4 * window, 0 if call < 0x1000000 else 0x1000000)
    regs = {}
    for ins in md().disasm(ROM[foff(start):foff(call)], start):
        mn, ops = ins.mnemonic, ins.op_str
        parts = [p.strip() for p in ops.split(",")]
        if mn in ("bl", "blx") or mn.startswith("bl") and not mn.startswith("bic"):
            for r in ("r0", "r1", "r2", "r3", "ip", "lr"):
                regs.pop(r, None)
            continue
        if mn in ("b", "bx") or (mn.startswith("b") and len(mn) <= 3 and mn not in ("bic",)):
            regs = {}   # branch target join: forget everything
            continue
        if not parts or not re.match(r"^(r\d+|ip|lr|sb|sl|fp)$", parts[0]):
            continue
        d = parts[0]
        try:
            if mn in ("mov", "movs") and parts[1].startswith("#"):
                regs[d] = int(parts[1][1:], 0) & 0xffffffff
            elif mn in ("mvn", "mvns") and parts[1].startswith("#"):
                regs[d] = (~int(parts[1][1:], 0)) & 0xffffffff
            elif mn in ("mov", "movs") and len(parts) == 2 and parts[1] in regs:
                regs[d] = regs[parts[1]]
            elif mn == "ldr" and "[pc" in ops:
                m = re.search(r"\[pc, #(-?0x[0-9a-f]+|-?\d+)\]", ops)
                off = int(m.group(1), 0) if m else 0
                regs[d] = u32(ins.address + 8 + off)
            elif mn in ("add", "sub", "orr", "lsl") and len(parts) == 3 and parts[2].startswith("#") and parts[1] in regs:
                imm = int(parts[2][1:], 0)
                v = regs[parts[1]]
                regs[d] = {"add": v + imm, "sub": v - imm, "orr": v | imm, "lsl": v << imm}[mn] & 0xffffffff
            elif mn == "add" and len(parts) == 3 and parts[1] == "pc" and parts[2].startswith("#"):
                regs[d] = (ins.address + 8 + int(parts[2][1:], 0)) & 0xffffffff
            else:
                regs.pop(d, None)
        except (ValueError, KeyError):
            regs.pop(d, None)
    return {k: regs.get(k) for k in ("r0", "r1", "r2", "r3")}


def hx(v):
    return None if v is None else "0x%x" % v


def sites(target, label):
    out = []
    for c, is_bl in find_bl_callers(target):
        r = regs_before(c)
        fa, fn = func_of(c)
        out.append({"site": hx(c), "func": hx(fa), "func_name": fn, "kind": label,
                    "r0": hx(r["r0"]), "r1": hx(r["r1"]), "r2": hx(r["r2"]), "r3": hx(r["r3"]),
                    "bl": is_bl})
    return out


# ---------------------------------------------------------------- dedicated switches
DED_TABLE = 0x040f4074   # 32 records x 32 B, also listed in the table of tables at RAM 0x36dd4
MATRIX_TABLE = 0x040f3574
# PinMAME numbers (core sw2m = n + 7 on SAM; col 0 = D17-D24, col 9 = D1-D8, col 11 = flippers, see sam.c)
PINMAME = {1: 65, 2: 66, 3: 67, 4: 68, 5: 69, 6: 70, 7: 71, 8: 72,
           9: 84, 10: 83, 11: 82, 12: 81, 13: 88, 14: 87, 15: 86, 16: 85,
           17: -7, 18: -6, 19: -5, 20: -4, 21: -3, 22: -2, 23: -1, 24: 0}
PINMAME_KEY = {1: "IPT_COIN1 key 3", 2: "IPT_COIN2 key 4", 3: "IPT_COIN3 key 5", 4: "IPT_COIN4 key 6",
               9: "left flipper key (LSHIFT)", 11: "right flipper key (RSHIFT)",
               17: "IPT_TILT key INSERT (port bit 0x0010)", 18: "'Slam Tilt' key HOME (0x0020)",
               19: "'Ticket Notch' key K (0x0040)", 20: "'Dedicated Sw#20' key L (0x0080)",
               21: "'Back' key 7 (0x0100)", 22: "'Minus' key 8 (0x0200)", 23: "'Plus' key 9 (0x0400)",
               24: "'Select' key 0 (0x0800)"}
FUNCTION = {
    0x20560: "coin switch (OS coin handler, slot index in +4)",
    0x102a1b4: "left flipper button handler (game)",
    0x102a294: "right flipper button handler (game)",
    0x102a2f0: "upper left flipper button handler (game)",
    0x24564: "tilt pendulum: DANGER warning / TILT (game_flow.md 5.3)",
    0x23e40: "slam tilt: deff 24, leff 12, snd 0x018, task 0x39 -> watchdog reset 311 ticks later",
    0x109c8: "ticket notch (ticket dispenser feedback)",
    0xfea8: "coin door button -> 0xfc20(switch, mask): BACK 1 -> RAM 0x3c950, MINUS 2 -> 0x3c960, "
            "PLUS 4 -> 0x3c970, SELECT 8 -> 0x3c980",
    0x60f0: "DIP switch reader",
}


def dedicated_rows():
    rows = []
    for k in range(32):
        a = DED_TABLE + 32 * k
        w = [u32(a + 4 * j) for j in range(8)]
        name = cstr(u32(w[2])) if foff(w[2]) is not None else None
        d = k + 1
        flags_hi = w[6] >> 16
        rows.append({
            "dedicated": "D%d" % d, "rom_switch_number": 128 + d, "pinmame_switch": PINMAME.get(d, ""),
            "pinmame_input": PINMAME_KEY.get(d, ""), "name": name,
            "handler": hx(w[0]) if w[0] else "", "handler_arg": w[1],
            "function": FUNCTION.get(w[0], "" if not w[0] else "?"),
            "descriptor_flags_0x10": hx(w[4]), "word_0x18": hx(w[6]), "id_byte": flags_hi & 0xff,
            "address": hx(a), "tag": "code"})
    return rows


# matrix switches that are cabinet buttons
def matrix_cabinet_rows():
    out = []
    for n in (15, 16):
        a = MATRIX_TABLE + 32 * (n - 1)
        w = [u32(a + 4 * j) for j in range(8)]
        out.append({"dedicated": "matrix", "rom_switch_number": n, "pinmame_switch": n,
                    "pinmame_input": {15: "'Tournament Start' key 2 (port bit 0x4000)", 16: "'Start Button' key 1 (0x8000)"}[n],
                    "name": cstr(u32(w[2])), "handler": hx(w[0]), "handler_arg": w[1],
                    "function": {15: "tournament start (OS 0x2101c)", 16: "start button (OS 0x21004, game_flow.md 4.1)"}[n],
                    "descriptor_flags_0x10": hx(w[4]), "word_0x18": hx(w[6]), "id_byte": (w[6] >> 16) & 0xff,
                    "address": hx(a), "tag": "code"})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = dedicated_rows() + matrix_cabinet_rows()
    cols = ["dedicated", "rom_switch_number", "pinmame_switch", "pinmame_input", "name", "handler", "handler_arg",
            "function", "descriptor_flags_0x10", "word_0x18", "id_byte", "address", "tag"]
    with open(os.path.join(OUT, "dedicated_switches.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    calls = {
        "task_create": sites(0xb624, "task_create"),
        "task_create_unique": sites(0xb718, "task_create_unique"),
        "task_recreate": sites(0xb76c, "task_recreate"),
        "task_timer_start": sites(0xb7d0, "task_timer_start"),
        "task_timer_restart": sites(0xb808, "task_timer_restart"),
        "task_set_id": sites(0xc0d0, "task_set_id"),
        "task_kill": sites(0xba3c, "task_kill"),
        "task_running": sites(0xbe68, "task_running"),
        "task_running_range": sites(0xbecc, "task_running_range"),
        "task_kill_range": sites(0xbb40, "task_kill_range"),
        "task_spawn_child": sites(0xb840, "task_spawn_child"),
        "event_hook_add": sites(0x7944, "event_hook_add"),
        "event_post": sites(0x79ec, "event_post"),
        "gi_off": sites(0xcaf8, "gi_off"), "gi_on": sites(0xcb24, "gi_on"),
        "gi_claim": sites(0xc9dc, "gi_claim"), "gi_claim_if_free": sites(0xc988, "gi_claim_if_free"),
        "gi_release": sites(0xca5c, "gi_release"), "gi_hw_init": sites(0xc914, "gi_hw_init"),
        "random": sites(0xc6b4, "random"), "random_percent": sites(0xc6d4, "random_percent"),
        "rng_next": sites(0xc684, "rng_next"), "rng_seed": sites(0xc674, "rng_seed"),
        "deff_start": sites(0x280b0, "deff_start"), "deff_start_ex": sites(0x280c4, "deff_start_ex"),
        "leff_start": sites(0x87ac, "leff_start"),
    }
    json.dump(calls, open(os.path.join(OUT, "static_calls.json"), "w"), indent=0)
    print("dedicated rows", len(rows), {k: len(v) for k, v in calls.items()})


if __name__ == "__main__":
    main()
