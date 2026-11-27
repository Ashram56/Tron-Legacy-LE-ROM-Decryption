#!/usr/bin/env python3
"""Run each foreground deff of the ROM booted by os_unicorn.py on its own and measure how long its task lives.

The ROM runs unmodified with its scheduler; the harness only calls deff_start(id) from the scheduler loop (the call is
injected at the idle PC, LR = idle PC) while the machine sits in attract, then counts ticks until the task created by
deff_start (task_create caller 0x27dbc, body = the deff routine) is gone. Deffs that read state (parameters at task +0x30,
mode variables, sounds) run with the attract state: their durations are the code's for that state only. The tracer
must be installed BEFORE the first tick: a hook added after a block was translated is not called for it.

Usage: TRON_ROM=trn_174h.bin os_deff_runs.py OUT.csv [first last] [--max TICKS]   (a fresh boot per deff, about 15 s each)
Output columns: deff, ticks (start to task end, 1 tick = 16.26 ms), body, ended (0 = still running at --max).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os_unicorn as O
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

DEFF_START, TASK_CREATE, DEFF_CALLER = 0x280b0, 0xb624, 0x27dbc


def machine():
    m = O.boot()
    m.rtc()
    m.stub(0x6180, lambda mm: 0)
    m.hooks.append(lambda mm: mm.write32(0x37264, max(0, mm.read32(0x37264) - 1)))
    log = m.trace({TASK_CREATE: "task_create"})
    for n in (18, 19, 20, 21):
        m.set_switch(n, True)
    m.tick(900)
    return m, log


def inject(m, addr, r0=0):
    m.tick(1)
    m.mu.reg_write(UC_ARM_REG_R0, r0)
    m.mu.reg_write(UC_ARM_REG_R1, 0)
    m.mu.reg_write(UC_ARM_REG_R2, 0)
    m.mu.reg_write(UC_ARM_REG_LR, m.pc)
    m.pc = addr


def run_deff(m, log, deff, max_ticks=800):
    n0 = len(log)
    inject(m, DEFF_START, deff)
    t0 = m.ticks
    m.tick(1)
    body = [e[3] for e in log[n0:] if e[1] == "task_create" and e[6] == DEFF_CALLER and e[2] == 2]
    if not body:
        return None
    body = body[0]
    end = []

    def watch(mm):
        """Once per tick, inside the ROM's own scheduler pass: stop stepping from outside, it changes the tick pacing."""
        if not any(mm.read32(a + 4) == body for a, tid, fl, nx in mm.tasks() if tid == 2):
            end.append(mm.ticks)
            mm.want = mm.ticks + 1
    m.hooks.append(watch)
    m.tick(max_ticks)
    m.hooks.remove(watch)
    return (end[0] if end else m.ticks) - t0, body, int(bool(end))

if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    mx = int(args[args.index("--max") + 1]) if "--max" in args else 800
    if "--max" in args:
        del args[args.index("--max"):args.index("--max") + 2]
    first, last = (int(args[1]), int(args[2])) if len(args) >= 3 else (1, 142)
    with open(args[0], "w") as f:
        f.write("deff,ticks,body,ended\n")
        for d in range(first, last + 1):          # a fresh machine per deff: a running deff of higher priority refuses the next
            m, log = machine()
            r = run_deff(m, log, d, mx)
            if r:
                f.write("%d,%d,0x%x,%d\n" % (d, r[0], r[1], r[2]))
                f.flush()
