#!/usr/bin/env python3
"""Run one display-effect routine of trn_174h in Unicorn (ARM) and log what it calls.

Source: the ROM code itself (deff table 0x040e1350, 8-byte records {fn,flags,prio}); no emulator capture.
OS routines are stubbed and logged (name, r0-r3, first stack words); task_sleep advances a fake tick count.
Usage: TRON_ROM=trn_174h.bin deff_unicorn.py DEFF_ID [max_insns]
"""
import os, struct, sys
from unicorn import *
from unicorn.arm_const import *

ROM = open(os.environ.get("TRON_ROM", "/mnt/project-files/trn_174h.bin"), "rb").read()
NAMES = {0xb91c: "task_sleep", 0x2b194: "bitmap_blit", 0x2b2a0: "bitmap_blit_masked", 0x28ca8: "text_draw_msg",
         0x28d5c: "text_printf_msg", 0x28e48: "text_draw_msg_fit", 0x27830: "dmd_show_pages",
         0x280b0: "deff_start", 0x2c8f4: "snd_play", 0xa58c: "msg_get", 0xb624: "task_create"}
SENT = 0x00ffff00


def build():
    mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    mu.mem_map(0, 0x01000000)                      # OS + RAM
    mu.mem_write(0, ROM[:0x100000])
    mu.mem_map(0x01000000, 0x00200000)             # game code + DMD pages + IO window
    mu.mem_write(0x01000000, ROM[0x40000:0x40000 + 0x80000])
    mu.mem_map(0x02000000, 0x00800000)             # NVRAM + IO (zero)
    mu.mem_map(0x04000000, 0x800000)               # data: first 8 MB of the file (fixed)
    mu.mem_write(0x04000000, ROM[:0x800000])
    mu.mem_map(0x04800000, 0x800000)               # banked window: 8 MB, bank N = file[N*8MB:] (image table: bank 0 or 1)
    mu.mem_write(0x04800000, ROM[:0x800000])

    def bank_select(mu, access, address, size, value, ud):    # flash_bank_select 0x11e8c writes 0x02580000
        n = value & 0xff
        chunk = ROM[n * 0x800000:(n + 1) * 0x800000]
        mu.mem_write(0x04800000, chunk + b"\xff" * (0x800000 - len(chunk)))
        mu.mem_write(0x01180000, struct.pack("<H", (n & 0xf) | 0x10))   # read-back: bits 0-3 bank, 4-6 board revision
    mu.hook_add(UC_HOOK_MEM_WRITE, bank_select, begin=0x02580000, end=0x02580003)
    mu.mem_write(0x01180000, struct.pack("<H", 0x10))
    return mu


TASK = 0x03002000   # fake current-task block: +0x30.. are the effect's arguments


def run(deff, max_insns=200000, args=None, ram=None, rng=None, init=()):
    mu = build()
    tab = 0x040e1350 + 8 * deff
    fn, flags, prio = struct.unpack_from("<IHB", ROM, tab - 0x04000000)
    log, state = [], {"tick": 0}

    def stack(mu, n):
        sp = mu.reg_read(UC_ARM_REG_SP)
        return [struct.unpack("<I", mu.mem_read(sp + 4 * i, 4))[0] for i in range(n)]

    def hook(mu, addr, size, ud):
        if addr == 0xc6b4 and rng is not None:       # random_below(n) (0xc6b4): forced pick, capped to n-1
            n = mu.reg_read(UC_ARM_REG_R0)
            mu.reg_write(UC_ARM_REG_R0, min(rng, max(n - 1, 0)))
            mu.reg_write(UC_ARM_REG_PC, mu.reg_read(UC_ARM_REG_LR))
        elif addr in NAMES:
            r = [mu.reg_read(x) for x in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
            log.append((state["tick"], NAMES[addr], r, stack(mu, 4), mu.reg_read(UC_ARM_REG_LR)))
            if NAMES[addr] == "task_sleep":
                state["tick"] += r[0]
            mu.reg_write(UC_ARM_REG_R0, 0)
            mu.reg_write(UC_ARM_REG_PC, mu.reg_read(UC_ARM_REG_LR))
        elif addr == SENT:
            mu.emu_stop()
    mu.hook_add(UC_HOOK_CODE, hook, begin=0, end=0x36000)
    mu.hook_add(UC_HOOK_CODE, hook, begin=SENT, end=SENT)
    mu.mem_map(0x03000000, 0x10000)

    def unmapped(mu, access, address, size, value, ud):
        base = address & ~0xfff
        try:
            mu.mem_map(base, 0x1000)
        except UcError:
            return False
        log.append((state["tick"], "auto_map 0x%x" % base, [], [], mu.reg_read(UC_ARM_REG_PC)))
        return True
    mu.hook_add(UC_HOOK_MEM_UNMAPPED, unmapped)
    mu.mem_write(0x372c0, struct.pack("<I", TASK))              # RAM 0x372c0: current task
    mu.mem_write(TASK + 0xc, struct.pack("<I", 0x03003000))     # +0xc: pointer to a (zero) context block
    for i, v in enumerate(args or []):
        mu.mem_write(TASK + 0x30 + 4 * i, struct.pack("<I", v))
    for a, v in (ram or {}).items():
        mu.mem_write(a, struct.pack("<I", v))
    mu.reg_write(UC_ARM_REG_SP, 0x03008000)
    mu.reg_write(UC_ARM_REG_LR, SENT)
    try:
        for i in init:               # boot initialisers the effect relies on, run as the OS does at startup
            mu.reg_write(UC_ARM_REG_LR, SENT)
            mu.emu_start(i, SENT, count=100000)
        mu.reg_write(UC_ARM_REG_LR, SENT)
        mu.emu_start(fn, SENT, count=max_insns)
    except UcError as e:
        log.append((state["tick"], "UC_ERROR %s" % e, [], [], mu.reg_read(UC_ARM_REG_PC)))
    return fn, flags, prio, log


if __name__ == "__main__":
    d = int(sys.argv[1])
    fn, flags, prio, log = run(d, int(sys.argv[2]) if len(sys.argv) > 2 else 200000)
    print("deff %d fn 0x%x flags 0x%x prio %d" % (d, fn, flags, prio))
    for t, n, r, s, lr in log[:80]:
        print("t=%4d %-20s r=%s stack=%s lr=0x%x" % (t, n, [hex(x) for x in r], [hex(x) for x in s], lr))
