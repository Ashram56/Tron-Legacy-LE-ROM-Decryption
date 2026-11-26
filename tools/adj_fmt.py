#!/usr/bin/env python3
"""Run an adjustment value formatter of trn_174h from the ROM code (Unicorn) and return the string it writes.

formatter(buf, value): buf in r0, value in r1 (the table's formatter column). Replaces the emulator-run formatter labels of
rom_data/settings/adjustments.csv (strict rule: labels come from the code).
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(__file__))
import deff_unicorn as D
from unicorn import *
from unicorn.arm_const import *

BUF = 0x03004000


def fmt(addr, value, mu_factory=D.build):
    mu = mu_factory()
    mu.mem_map(0x03000000, 0x10000)
    mu.mem_write(0x372c0, struct.pack("<I", 0x03002000))
    mu.mem_write(0x03002000 + 0xc, struct.pack("<I", 0x03003000))

    def unmapped(mu, access, address, size, v, ud):
        try:
            mu.mem_map(address & ~0xfff, 0x1000)
        except UcError:
            return False
        return True
    mu.hook_add(UC_HOOK_MEM_UNMAPPED, unmapped)
    sent = 0x00ffff00
    mu.hook_add(UC_HOOK_CODE, lambda mu, a, s, u: mu.emu_stop(), begin=sent, end=sent)
    mu.reg_write(UC_ARM_REG_SP, 0x03008000)
    mu.reg_write(UC_ARM_REG_LR, sent)
    mu.reg_write(UC_ARM_REG_R0, BUF)
    mu.reg_write(UC_ARM_REG_R1, value & 0xffffffff)
    try:
        mu.emu_start(addr, sent, count=200000)
    except UcError as e:
        return "ERR %s" % e
    raw = bytes(mu.mem_read(BUF, 64)).split(b"\0")[0]
    return raw.decode("latin1")


if __name__ == "__main__":
    f = int(sys.argv[1], 16)
    for v in sys.argv[2:]:
        print(v, repr(fmt(f, int(v))))
