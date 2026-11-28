#!/usr/bin/env python3
"""Instruction count of the IO tick ISR 0x12070 per phase, from the ROM code (Unicorn).

The ISR phase is the down-counter at RAM 0x37370 (reload 4): phase 0 runs the STATUS sample and the coil burst,
1 the dedicated switches, 2 the hardware rule lists, 3 the bumpers/devices and the lamp blank. We run one tick with
the counter set so that the tick lands on each phase and count the ARM instructions executed (every instruction of
the ISR, the bus accesses included). Cycles are not computed (they need the EBI wait states of peripheral_init.csv).
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deff_unicorn as D
from unicorn import *
from unicorn.arm_const import *

def count(phase_counter):
    mu = D.build()
    mu.mem_map(0x03000000, 0x10000)
    def unmapped(mu, access, address, size, value, ud):
        try: mu.mem_map(address & ~0xfff, 0x1000)
        except UcError: return False
        return True
    mu.hook_add(UC_HOOK_MEM_UNMAPPED, unmapped)
    n = [0]
    mu.hook_add(UC_HOOK_CODE, lambda *a: n.__setitem__(0, n[0] + 1), begin=0, end=0x36000)
    mu.mem_write(0x37370, struct.pack("<i", phase_counter))
    mu.reg_write(UC_ARM_REG_SP, 0x03008000); mu.reg_write(UC_ARM_REG_LR, D.SENT)
    try: mu.emu_start(0x12070, D.SENT, count=200000)
    except UcError: pass
    return n[0]

if __name__ == "__main__":
    for c, name in ((1, "phase 0 (counter reaches 0, reload 4)"), (3, "other phase")):
        print(name, count(c), "instructions")
