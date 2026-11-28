#!/usr/bin/env python3
"""Replay a reference scenario script (rom_data/states/traces/<name>.txt) on the ROM booted by os_unicorn.py.

The scenario commands are the ones the reference tracer ran (start N, wait S, mark TEXT, poke ADDR VALUE, hit SW,
release SW); the ROM runs unmodified with its own scheduler, so every call it makes is visible, including the ones the
reference trace does not log (rules_refresh_request, FUN_0100f164, ...). The output is one JSON line per call:
{"t": seconds, "ev": name, "r0": .., "caller": ..}.

Hardware the harness plays: trough switches 18-21 closed (switch 21 opens when the trough up-kicker, coil 1, fires and closes at `drain`), the coin and start switches, the switch scan (os_unicorn),
the real-time clock read (answered), the start-up lock-out counter RAM 0x37264 (counted down once per tick; 0x6180
would show "this machine will not operate" because the clock chip is absent).

Usage: TRON_ROM=trn_174h.bin os_scenario.py SCENARIO.txt OUT.jsonl [--stop SECONDS] [--watch ADDR,ADDR]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os_unicorn as O

TICK = 0.01626
CALLS = {
    0x280b0: "deff_start", 0x87ac: "leff_start", 0xc404: "leff_stop", 0x2c8f4: "snd_play", 0x178c: "audit_add",
    0x0101b824: "tube_show_start", 0x0101baac: "tube_show_stop", 0x19648: "rules_refresh_request",
    0x0100f164: "FUN_0100f164", 0x2340c: "score_add", 0xb624: "task_create", 0x6970: "coil_pulse",
    0x65d8: "game_flag_set", 0x6588: "game_flag_clear", 0x20afc: "game_start",
    0x2b60: "coil_queue_pulse",       # FUN_00002b60(coil, ms, sync): the ball devices' kicks (trough up-kicker = coil 1, kick fn 0x0101bbc0)
}


def run(script, out, stop=None):
    m = O.boot()
    m.rtc()
    m.stub(0x6180, lambda mm: 0)
    m.hooks.append(lambda mm: mm.write32(0x37264, max(0, mm.read32(0x37264) - 1)))
    log = m.trace(CALLS)
    seen = {}

    def coil_pending(mm):
        """FUN_000028f4(coil, handle, 1) = the pulse `handle` is still queued or firing. The coil IRQ (0x12070) is not run by the harness, so a
        pulse is answered as pending for 4 ticks (about 65 ms, the longest ball-device pulse is 64 ms, ROM 0x0101bbc0 event 9) after it was first asked about."""
        from unicorn.arm_const import UC_ARM_REG_R1
        h = mm.mu.reg_read(UC_ARM_REG_R1)
        first = seen.setdefault(h, mm.ticks)
        return 1 if mm.ticks - first < 4 else 0
    m.stub(0x28f4, coil_pending)
    for n in (18, 19, 20, 21):
        m.set_switch(n, True)
    m.tick(900)                                   # boot, attract, the start-up lock-out
    t0 = m.ticks
    held = set()
    marks = []

    def advance(seconds):
        m.tick(max(1, round(seconds / TICK)))

    def pulse(n, ticks=4):
        m.set_switch(n, True)
        m.tick(ticks)
        if n not in held:
            m.set_switch(n, False)
            m.tick(1)
    ejected = {"seen": 0, "todo": []}

    def eject_watch(mm):
        """The trough up-kicker (coil 1, FUN_00002b60 queued by the ball device 1 kick 0x0101bbc0) fired: the ball leaves the trough (switch 21 opens), rolls to the shooter lane (23 closes a second
        later) and is plunged (23 opens again) until `drain` puts it back in the trough."""
        n = sum(1 for e in log if e[1] == "coil_queue_pulse" and e[2] == 1)
        if n > ejected["seen"]:
            ejected["seen"] = n
            if getattr(mm, "switches", {}).get(21, True):
                mm.set_switch(21, False)
                ejected["todo"] = [(mm.ticks + 60, 23, True), (mm.ticks + 140, 23, False)]
        for item in list(ejected["todo"]):
            if mm.ticks >= item[0]:
                mm.set_switch(item[1], item[2])
                ejected["todo"].remove(item)
    m.hooks.append(eject_watch)
    for line in open(script, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        cmd, _, arg = line.partition(" ")
        now = (m.ticks - t0) * TICK
        if stop is not None and now > stop:
            break
        if cmd == "start":
            for _ in range(4):                    # coins until one credit, then the start button
                pulse(129, 12)
                m.tick(12)
            m.tick(100)
            pulse(16, 10)
        elif cmd == "wait":
            advance(float(arg))
        elif cmd == "mark":
            marks.append((m.ticks, arg))
            log.append((m.ticks, "mark:" + arg, 0, 0, 0, 0, 0))
        elif cmd == "poke":
            a, v = arg.split()
            m.mu.mem_write(int(a, 16), bytes([int(v, 16) & 0xff]))
        elif cmd == "button":                     # button start 150 / button coin 150: the switch held for that many ms (start = 16, coin = 129 as in `start`)
            name, _, ms = arg.partition(" ")
            if name in ("start", "coin"):
                pulse({"start": 16, "coin": 129}[name], max(1, round(float(ms or 150) / 1000 / TICK)))
        elif cmd == "hit":
            held.discard(int(arg))
            pulse(int(arg))
            if int(arg) == 11:                    # the VUK holds its ball until `release`
                held.add(11)
                m.set_switch(11, True)
        elif cmd == "release":
            held.discard(int(arg))
            m.set_switch(int(arg), False)
        elif cmd == "drain":                      # the ball rolls back into the trough: switch 22 (jam) closes for a second, then 21
            m.set_switch(22, True)                # the ball enters through the trough jam switch ...
            m.tick(60)
            m.set_switch(22, False)               # ... and settles at the kicker position
            m.set_switch(21, True)
            m.tick(2)
    with open(out, "w", encoding="utf-8") as f:
        for tick, name, r0, r1, r2, r3, caller in log:
            f.write(json.dumps({"t": round((tick - t0) * TICK, 4), "ev": name, "r0": r0, "r1": r1,
                                "caller": "0x%x" % caller}) + "\n")
    return log


if __name__ == "__main__":
    args = sys.argv[1:]
    stop = float(args[args.index("--stop") + 1]) if "--stop" in args else None
    run(args[0], args[1], stop)
