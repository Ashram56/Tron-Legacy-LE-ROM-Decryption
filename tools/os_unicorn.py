#!/usr/bin/env python3
"""Boot a Stern SAM ROM (Tron LE 1.74 `trn_174h`) in Unicorn with its own task scheduler, and run it tick by tick.

Source: the ROM code itself; no emulator capture. Unlike deff_unicorn.py (one routine, OS calls stubbed), nothing
is stubbed here: the ROM boots from the reset vector, copies its data (memcpy loop 0x35e24), initialises the OS
and enters the scheduler loop 0x15a7c / 0x15a88, which waits until the tick counter word (RAM 0x37364) changes,
runs the tick pass 0x3405c and then every task of the list at 0x372b0 (context switches done by the ROM).
The harness only plays the hardware: whenever the scheduler waits on the tick counter (PC at 0x15a88) it adds one
to it, so one pass of the scheduler = one OS tick (16.26 ms of game time, 62 ticks = 1 s).

Memory map and the 0x04800000 bank window: see deff_unicorn.build(). Unmapped pages (IO registers, NVRAM) are mapped
on first touch and read zero.

Usage:  TRON_ROM=trn_174h.bin os_unicorn.py [ticks]       boots, runs `ticks` ticks (default 200), prints the task list
Library: boot() -> Machine; Machine.tick(n); Machine.tasks(); Machine.read32(addr); Machine.write32(addr, v)
"""
import collections
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deff_unicorn as D
from unicorn import UC_HOOK_CODE, UC_HOOK_MEM_UNMAPPED, UcError
from unicorn.arm_const import UC_ARM_REG_PC

TICK_WORD = 0x37364              # RAM: ticks since boot (the scheduler's wait word, 0x15a84 literal)
OS_CALLS = {0x280b0: "deff_start", 0x87ac: "leff_start", 0x2c8f4: "snd_play", 0xb624: "task_create", 0x1b824 + 0x0fe00000: "x"}
OS_CALLS.pop(0x1b824 + 0x0fe00000)
IDLE_PC = 0x15a88                # scheduler wait loop: ldr r2,[tick word]; cmp; beq
TASK_LIST = 0x372b0              # RAM word: head of the task list (task +0x1c = next)
STOP = 0x00ffff00


class Machine:
    def __init__(self):
        self.mu = D.build()
        self.mu.mem_map(0x03000000, 0x100000)
        self.mu.hook_add(UC_HOOK_MEM_UNMAPPED, self._unmapped)
        self.mu.hook_add(UC_HOOK_CODE, self._idle, begin=IDLE_PC, end=IDLE_PC)
        self.ticks = 0
        self.want = 0                  # ticks to run before stopping
        self.pc = 0                    # where to resume
        self.hooks = []                # callables(machine) run once per tick, before the tick is released

    # hardware ---------------------------------------------------------------------------------------------
    def _unmapped(self, mu, access, address, size, value, ud):
        try:
            mu.mem_map(address & ~0xfff, 0x1000)
            return True
        except UcError:
            return False

    def _idle(self, mu, address, size, ud):
        """The scheduler waits for the tick counter: release one tick."""
        for h in self.hooks:
            h(self)
        self.write32(TICK_WORD, (self.read32(TICK_WORD) + 1) & 0xffffffff)
        self.ticks += 1
        if self.ticks >= self.want:
            mu.emu_stop()

    def trace(self, entries):
        """Log a call to each routine address in `entries` ({address: name}) as (tick, name, r0, r1, r2, r3, caller):
        the ROM runs normally (nothing is stubbed); this only reads the registers on entry, like the reference tracer."""
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR
        self.log = getattr(self, "log", [])

        def hook(mu, address, size, name):
            self.log.append((self.ticks, name) + tuple(mu.reg_read(r) for r in
                            (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)) + (mu.reg_read(UC_ARM_REG_LR),))
        for addr, name in entries.items():
            self.mu.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr, user_data=name)
        return self.log

    # switches (IO tick, stage 1 of the debounce: assets/io/bus/CPU_BOARD_IO.md 5.3) ---------------------------
    RAW, STABLE, DIFF, PENDING, BOUNCED, ACK = 0x3c76a, 0x3c792, 0x3c77e, 0x3c7a6, 0x3c7ba, 0x3c7ce   # 16-bit words, one per column

    def set_switch(self, n, closed):
        """Switch n (ROM numbering 1-64 matrix, 129-160 dedicated) closes or opens at the next tick."""
        self.switches = getattr(self, "switches", {})
        self.switches[n] = bool(closed)
        if self.scan not in self.hooks:
            self.hooks.append(self.scan)

    @staticmethod
    def column_bit(n):
        if n >= 129:
            return 8 + (n - 129) // 16, (n - 129) % 16
        return (n - 1) // 16, (n - 1) % 16

    def _r16(self, a):
        return struct.unpack("<H", bytes(self.mu.mem_read(a, 2)))[0]

    def _w16(self, a, v):
        self.mu.mem_write(a, struct.pack("<H", v & 0xffff))

    def scan(self, _m=None):
        """The IO tick ISR's switch scan the harness plays: raw = the closed switches, then the stage-1 debounce
        (raw ^ stable differing on two consecutive scans = pending); run twice per tick (the real scan is 4 per tick)."""
        raw = collections.defaultdict(int)
        for n, closed in getattr(self, "switches", {}).items():
            if closed:
                c, b = self.column_bit(n)
                raw[c] |= 1 << b
        for _ in range(2):
            for c in (0, 1, 2, 3, 8, 9):
                a = 2 * c
                self._w16(self.RAW + a, raw[c])
                stable, old = self._r16(self.STABLE + a), self._r16(self.DIFF + a)
                new = raw[c] ^ stable
                ack = self._r16(self.ACK + a)                       # handled by the main loop: leaves pending / bounced
                pending = self._r16(self.PENDING + a) & ~ack
                bounced = self._r16(self.BOUNCED + a) & ~ack
                self._w16(self.ACK + a, 0)
                pending |= old & new
                bounced |= pending & ~new
                self._w16(self.DIFF + a, new)
                self._w16(self.PENDING + a, pending)
                self._w16(self.BOUNCED + a, bounced)

    def stub(self, addr, fn):
        """Answer a routine instead of running it (hardware the harness does not play): fn(machine) -> r0."""
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_LR

        def hook(mu, address, size, ud):
            mu.reg_write(UC_ARM_REG_R0, fn(self) & 0xffffffff)
            mu.reg_write(UC_ARM_REG_PC, mu.reg_read(UC_ARM_REG_LR))
        self.mu.hook_add(UC_HOOK_CODE, hook, begin=addr, end=addr)

    def rtc(self, year=2026, month=11, day=27, hour=12, minute=0, sec=0):
        """The real-time clock read 0xd244 (r0 = 8-byte buffer: u16 year, 3, month, day, hour, minute, second): answered."""
        from unicorn.arm_const import UC_ARM_REG_R0

        def read(m):
            m.mu.mem_write(m.mu.reg_read(UC_ARM_REG_R0), struct.pack("<HBBBBBB", year, 3, month, day, hour, minute, sec))
            return 1
        self.stub(0xd244, read)

    # access -------------------------------------------------------------------------------------------------
    def read32(self, addr):
        return struct.unpack("<I", bytes(self.mu.mem_read(addr, 4)))[0]

    def write32(self, addr, value):
        self.mu.mem_write(addr, struct.pack("<I", value & 0xffffffff))

    def tasks(self):
        """[(task address, id, flags, next)] of the OS task list (task +0x1c = next; id/flags from +0x00/+0x02)."""
        out, t = [], self.read32(TASK_LIST)
        while t and len(out) < 200:
            out.append((t, struct.unpack("<H", bytes(self.mu.mem_read(t, 2)))[0],
                        struct.unpack("<H", bytes(self.mu.mem_read(t + 2, 2)))[0], self.read32(t + 0x1c)))
            t = self.read32(t + 0x1c)
        return out

    # run ----------------------------------------------------------------------------------------------------
    def tick(self, n=1, max_insns=400000000):
        """Run until n more ticks have been released (boots from the reset vector on the first call)."""
        self.want = self.ticks + n
        try:
            self.mu.emu_start(self.pc, STOP, count=max_insns)
        except UcError as e:
            raise RuntimeError("Unicorn stopped at 0x%x: %s" % (self.mu.reg_read(UC_ARM_REG_PC), e))
        self.pc = self.mu.reg_read(UC_ARM_REG_PC)
        return self.ticks


def boot():
    return Machine()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    m = boot()
    log = m.trace(OS_CALLS)
    m.tick(n)
    for e in log[:40]:
        print("tick %5d %-14s r0=0x%x r1=0x%x caller=0x%x" % (e[0], e[1], e[2], e[3], e[6]))
    print("ticks %d, PC 0x%x, tick word %d" % (m.ticks, m.pc, m.read32(TICK_WORD)))
    for t, tid, flags, nxt in m.tasks():
        print("task 0x%08x id 0x%02x flags 0x%04x" % (t, tid, flags))
