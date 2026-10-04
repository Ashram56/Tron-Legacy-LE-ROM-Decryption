"""Build the machine-readable outputs of rom_data/states/ (Tron Legacy LE 1.74, trn_174h).

Inputs:
  the ROM (rom_data/tools/rom.py), rom_data/states/static_calls.json and dedicated_switches.csv (states_static.py),
  the scenario traces rom_data/states/traces/*.jsonl (states_ref.cpp), rules/traces/*.jsonl (task ids only),
  code/tron_game_decompiled_v2.c (function names only).
Outputs (rom_data/states/):
  hardware_facts.json   Part A: RGB ramp tubes, GI relay, dedicated switches (summary; rows in dedicated_switches.csv)
  os_model.json         tick, task id table, event hooks and posters, switch dispatch order, deff scheduler, rule lists,
                        game-flag classes and per-player lamp swap
  multiplayer.json, tilt.json, sea_of_simulation_late.json, match.json   Part B topics
  scenarios.json        one row per scenario in traces/ (purpose, pokes, duration, event counts)
Every fact row: {"id", "fact", "value", "address", "tag": observed|code|inferred, "evidence"}.
Each run re-checks the ROM facts it quotes (asserts) and re-reads the traces, so a changed ROM or trace fails loudly.
Run: python3 rom_data/tools/states_build.py
"""
import collections
import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rom import ROM, foff, u8, u16, u32, cstr, msg, md, find_bl_callers  # noqa: E402
import states_static as ss  # noqa: E402

REPO = ss.REPO
OUT = os.path.join(REPO, "rom_data", "states")
TR = os.path.join(OUT, "traces")


def hx(v):
    return None if v is None else "0x%x" % v


def F(fid, fact, value, address, tag, evidence=""):
    assert tag in ("observed", "code", "inferred"), tag
    return {"id": fid, "fact": fact, "value": value, "address": address, "tag": tag, "evidence": evidence}


def jl(name, pred=None):
    """Stream one trace; yield parsed rows that pass pred (applied to the raw line first for speed)."""
    p = os.path.join(TR, name + ".jsonl")
    with open(p) as f:
        for line in f:
            if pred is None or pred(line):
                try:
                    yield json.loads(line)
                except ValueError:
                    continue


def dis(a, b):
    return [(i.address, i.mnemonic, i.op_str) for i in md().disasm(ROM[foff(a):foff(b)], a)]


def has_ins(a, b, mnem, ops):
    return any(m == mnem and o == ops for _, m, o in dis(a, b))


TOT = 0x36c00   # table of tables {ptr, count, record size}


def tot_entry(addr):
    return {"ptr": hx(u32(addr)), "count": u32(addr + 4), "record_size": u32(addr + 8), "tot_addr": hx(addr)}


# =====================================================================================================  Part A
def light_tubes():
    facts = []
    rl = ss.regs_before(0x4f0)
    rr = ss.regs_before(0xd14)
    assert rl["r0"] == 0x3b1d8 and rl["r1"] == 0x10 and rr["r0"] == 0x3b504 and rr["r1"] == 0x20
    facts.append(F("tube_objects", "Two tube driver objects; the constructor's 2nd argument is the IO strobe bit",
                   {"left": {"obj": "0x3b1d8", "strobe": "0x10", "ctor": "0x340", "ctor_call": "0x4f0",
                             "rgb_bits": {"r": rl["r2"], "g": rl["r3"], "b": 8}},
                    "right": {"obj": "0x3b504", "strobe": "0x20", "ctor": "0xb64", "ctor_call": "0xd14"}},
                   "0x4f0, 0xd14", "code", "regs at the ctor BLs: r0=obj, r1=strobe, r2/r3/[sp]=R/G/B bit"))
    s1, s2 = cstr(0xd2fcc), cstr(0xd2fd4)
    assert s1 == "lrlt" and "left ramp light tube" in s2
    facts.append(F("tube_console", "Console command names: 'lrlt' = 'perform left ramp light tube operations' -> handler "
                   "0x390 (object 0x3b1d8, strobe 0x10); 'rrlt' = right -> handler 0xbb4 (object 0x3b504, strobe 0x20)",
                   {"lrlt": "0x390", "rrlt": "0xbb4"}, "0xd2fcc, 0xd2fd4, 0x514", "code",
                   "strings in the OS image; registration call at 0x514"))
    assert msg(0x51e) == "L. RAMP:" and msg(0x51f) == "R. RAMP:" and msg(0x51b) == "FIBER OPTIC LIGHT TUBE TEST"
    facts.append(F("tube_service_test", "Service test 'FIBER OPTIC LIGHT TUBE TEST' (fn 0x1012b50): row 'L. RAMP:' (msg 0x51e) "
                   "drives object 0x3b1d8 (strobe 0x10), row 'R. RAMP:' (msg 0x51f) drives 0x3b504 (strobe 0x20). Keys: "
                   "MINUS/PLUS move the cursor, SELECT toggles R/G/B of the row, BACK exits",
                   None, "0x1012b50, msgs 0x51b-0x525", "code", ""))
    masks = collections.Counter(u8(0x040e3c88 + 12 * i + 6) for i in range(106))
    assert masks == collections.Counter({3: 103, 0: 1, 1: 1, 2: 1})
    assert u8(0x040e3c88 + 12 * 11 + 6) == 1 and u8(0x040e3c88 + 12 * 12 + 6) == 2
    facts.append(F("tube_show_masks", "Tube show table 0x040e3c88 (106 x 12 B, mask byte +6): 103 shows use both tubes (3), "
                   "show 11 uses mask 1 only, show 12 mask 2 only, show 0 is empty. tube_show_start maps mask 1 -> 0x3b1d8, "
                   "mask 2 -> 0x3b504", dict((str(k), v) for k, v in sorted(masks.items())), "0x040e3c88, 0x0101b824",
                   "code", ""))
    assert dis(0x1028bac, 0x1028bb0)[0][2] == "r0, #0x70"
    facts.append(F("tube_skill_shot_link", "Tube rule id 11 (show 11, mask 1 = object 0x3b1d8) runs while task 0x70 runs "
                   "(cond 0x1028bac); task 0x70 = skill shot A = LEFT ramp (sw37). Tube rule id 12 (show 12, mask 2 = "
                   "object 0x3b504) runs while task 0x72 runs (cond 0x1028d98); task 0x72 = skill shot B = RIGHT ramp "
                   "(sw34). So the game itself pairs strobe 0x10 with the left ramp shot and 0x20 with the right",
                   None, "0x102976c, 0x1028bac, 0x1028d98", "code",
                   "rule list 4 dump (traces/tilt_modes.jsonl ev=rule list 4: ids 11 and 12); skill_shots.md"))
    facts.append(F("tube_pinmame", "PinMAME sam.c labels CSTB (0x10, lamps 101-103) 'Right RGB ramp' and DSTB (0x20, lamps "
                   "104-106) 'Left RGB ramp'. The labels came in commit 4440bcc4 (2024-02-09, 'PWM: rewrite all SAM aux "
                   "board') with no cited source; older code had no side names",
                   {"0x10": "right (PinMAME)", "0x20": "left (PinMAME)"}, "pinmame/src/wpc/sam.c 917-921", "code",
                   "external source, not the ROM"))
    facts.append(F("tube_vincent", "Owner schematic notes (Vincent's repo): Clk_input_aux bit4 = ESTB (J3 pin 12), bit5 = DSTB "
                   "(J3 pin 11), bit6 = CSTB (pin 10), bit7 = BSTB (pin 9); strobes B-E drive the 'Tron LE fiber optic "
                   "ramps'. No left/right is given. Note the letters differ from PinMAME's (PinMAME calls bit4 CSTB)",
                   {"0x10": "ESTB J3-12", "0x20": "DSTB J3-11"}, "external", "code", "external source"))
    facts.append(F("tube_verdict", "Most likely: strobe 0x10 = LEFT ramp tube, 0x20 = RIGHT. Three independent ROM sources "
                   "agree (console names, service test labels, skill-shot pairing); only PinMAME's unsourced comment says the "
                   "opposite. Not proven on hardware",
                   {"0x10": "left", "0x20": "right"}, "see tube_* rows", "inferred", ""))
    facts.append(F("tube_real_machine_test", "Test on the machine: service menu -> FIBER OPTIC LIGHT TUBE TEST; put the cursor "
                   "on 'L. RAMP:' R and press SELECT: the LEFT ramp tube should turn red. Electrical check: the line that "
                   "pulses when L. RAMP is lit is J3 pin 12 (Vincent: bit4/0x10 = ESTB). If the right ramp lights, the ROM "
                   "labels are swapped relative to the wiring and PinMAME is right", None, "0x1012b50", "inferred", ""))
    return facts


def gi():
    facts = []
    # init and set/clear instructions
    assert has_ins(0xc958, 0xc96c, "orr", "r3, r3, #1") and has_ins(0xc970, 0xc984, "and", "r3, r3, #0xfe")
    facts += [
        F("gi_bit", "GI relay = bit 0 of the IO strobe/aux register 0x0240002B, ACTIVE LOW: 0 = GI on, 1 = GI off. The ROM "
          "keeps a shadow at RAM 0x3c758 and the IRQ writes it to the register every interrupt", {"bit": 0, "on": 0, "off": 1},
          "0x3c758, IRQ 0x133e8-0x13418", "code", "PinMAME: coreGlobals.gi[0] = (~data & 1) ? 9 : 0; Vincent: bit0 = RLY_DRV"),
        F("gi_init", "Power-up: 0xc914 sets AUX_DRV = 0, shadow = 0xfe and writes 0xfe -> GI ON from the first IO write. "
          "Observed at t 0.3665 s (caller 0x7aa4); PinMAME GI output 9 (on) from t 1.0", {"shadow": "0xfe"}, "0xc914",
          "observed", "traces/gi_and_tilt.jsonl ev=gi_write init=1"),
        F("gi_set_clear", "0xc958 shadow |= 1 (GI off); 0xc970 shadow &= ~1 (GI on). Both reached only through the ownership "
          "API below", None, "0xc958, 0xc970", "code", ""),
        F("gi_ownership", "One task owns GI at a time: owner pointer RAM 0x372d4, current task 0x372c0. gi_off 0xcaf8 / gi_on "
          "0xcb24 act only when the calling task is the owner. claim 0xc9dc(prio) takes it by priority; claim_if_free "
          "0xc988 only when nobody owns it; release 0xca5c clears the owner and turns GI ON; it is called from the leff "
          "cleanup 0x898c (call at 0x8a30), so GI comes back when the owning lamp effect ends or is killed",
          None, "0x372d4, 0xc9dc, 0xc988, 0xca5c, 0xcaf8, 0xcb24", "code", ""),
        F("gi_states", "GI per machine state", {"power_up": "on (0xfe)", "attract": "on, except leff 133 game-over show "
                                                "(GI off ~10 s after match)", "game": "on; short GI-off flashes by game leffs",
                                                "tilt_warning": "off 15 ticks (leff 11)", "tilt": "off until the end-of-ball "
                                                "task 0x2a releases it at the drain (leff 9)", "slam": "off until the reset (leff 12)",
                                                "after_reset": "on (re-init)"},
          "0x2ffa4, 0x2ff44, 0x2fefc", "observed", "traces/gi_and_tilt, slam_tilt, multiplayer_4p (leff 133)"),
    ]
    sc = json.load(open(os.path.join(OUT, "static_calls.json")))
    paths = {k: [r["site"] + " " + (r["func_name"] or "?") for r in sc[k]] for k in
             ("gi_off", "gi_on", "gi_claim", "gi_claim_if_free", "gi_release", "gi_hw_init")}
    facts.append(F("gi_call_sites", "Every static call site of the GI API (BL scan of the whole ROM)",
                   {k: {"count": len(v), "sites": v} for k, v in paths.items()},
                   "0xcaf8, 0xcb24, 0xc9dc, 0xc988, 0xca5c, 0xc914", "code", "states_static.py static_calls.json"))
    facts.append(F("gi_os_leffs", "OS lamp effects that own GI: leff 12 (0x2fefc) blackout + GI off forever = SLAM; leff 9 "
                   "(0x2ff44) GI off, then waits for task 0x2b (ball search) and turns GI on = TILT; leff 11 (0x2ffa4) GI off "
                   "15 ticks = tilt WARNING", {"9": "tilt", "11": "tilt warning", "12": "slam"},
                   "0x2fefc, 0x2ff44, 0x2ffa4", "code", ""))
    facts.append(F("gi_game_leffs", "Game leffs whose code turns GI off (claim + gi_off): 20 (bonus), 44, 48-50, 52, 55, 58, "
                   "61-63, 67, 77, 79, 93, 108, 129, 133 (game over), 135, 153, 165, 168-170",
                   [20, 44, 48, 49, 50, 52, 55, 58, 61, 62, 63, 67, 77, 79, 93, 108, 129, 133, 135, 153, 165, 168, 169, 170],
                   "gi_claim call sites", "code", "callers of 0xc9dc / 0xcaf8 inside leff functions (static_calls.json)"))
    # observed GI transitions per trace
    obs = []
    for name in ("gi_and_tilt", "slam_tilt", "multiplayer_4p", "multiplayer_3p"):
        for r in jl(name, lambda l: '"ev":"gi_out"' in l or '"ev":"gi_write"' in l or '"ev":"mark"' in l):
            if r["ev"] == "gi_out":
                obs.append({"trace": name, "t": r["t"], "gi": "on" if r["state"] else "off"})
    facts.append(F("gi_observed_transitions", "Every PinMAME GI output change in the GI-traced scenarios",
                   {"count": len(obs), "rows": obs}, "PinmameGetChangedGIs", "observed", "traces/*.jsonl ev=gi_out"))
    facts.append(F("gi_doc_note", "io/README.md says the Vincent capture value 0xbe means 'bit 6 low, GI on'. GI-on is bit 0 = 0 "
                   "(0xbe and 0xfe both have bit 0 = 0); bit 6 is the aux latch pulse the IRQ toggles when it writes coils",
                   None, "0x133e8-0x13418", "code", "contradiction with io/README.md wording"))
    return facts


def dedicated_summary():
    rows = list(csv.DictReader(open(os.path.join(OUT, "dedicated_switches.csv"))))
    by = {r["dedicated"]: r for r in rows}
    ttot = tot_entry(0x36dd4)
    assert ttot["count"] == 32 and int(ttot["ptr"], 16) == 0x040f4074
    assert by["D22"]["name"] == "MINUS" and by["D23"]["name"] == "PLUS"
    return [
        F("ded_table", "Dedicated switch table 0x040f4074: 32 records x 32 B (table of tables entry 0x36dd4). ROM switch number "
          "of Dn = 128 + n (dispatcher loop 0x81..0xa0). Rows: dedicated_switches.csv", ttot, "0x040f4074, 0x36dd4", "code", ""),
        F("ded_22_23", "D22 = MINUS, D23 = PLUS. Evidence: (1) ROM names in the table; (2) the shared handler 0xfea8 passes "
          "mask 2 for D22 and 4 for D23 to 0xfc20, and the service code uses mask 2 to move back / volume down, 4 forward / "
          "up; (3) PinMAME's input port maps key 8 'Minus' to bit 0x200 (D22) and key 9 'Plus' to 0x400 (D23); (4) emulator: "
          "key 8 -> 0xfc20(r0 = 0x96 = switch 150 = D22, mask 2), key 9 -> 0x97 (151, D23, mask 4). Only the comment block in "
          "PinMAME sam.c ('D21 - DED #22 - Plus, D22 - DED #23 - Minus') says otherwise; it is wrong",
          {"D21": "BACK (1)", "D22": "MINUS (2)", "D23": "PLUS (4)", "D24": "SELECT (8)"}, "0x040f4074, 0xfea8, 0xfc20",
          "observed", "traces/coin_door_buttons.jsonl ev=call name=coin_door_key"),
        F("ded_back_attract", "BACK in attract (when the volume display is not running) adds a SERVICE CREDIT (audit 0x24, "
          "deff 17)", None, "0xfea8", "observed", "traces/coin_door_buttons.jsonl credits 0 -> 1"),
        F("ded_harness_limits", "In libpinmame the keyboard handler rewrites switch column 0 (D17-D24) every frame, so "
          "PinmameSetSwitch on those numbers is ignored; use the keys. The left flipper (PinMAME 84) did not reach handler "
          "0x102a1b4 via SetSwitch while 82/88 did (keyboard flipper mapping), not investigated further",
          None, "harness", "observed", "states_ref dsw command"),
    ]


# =====================================================================================================  OS model
def os_model():
    sc = json.load(open(os.path.join(OUT, "static_calls.json")))
    m = {}
    # --- tick
    ticks = [r for r in jl("gi_and_tilt", lambda l: '"ev":"tick"' in l)]
    per = []
    for a, b in zip(ticks, ticks[1:]):
        if b["hw"] != a["hw"]:
            per.append((b["t"] - a["t"]) / (b["hw"] - a["hw"]) * 1000)
    assert any("#0x40" in o for _, _, o in dis(0x120b4, 0x120cc))
    m["tick"] = [
        F("tick_counter", "OS tick counter RAM 0x37364 is incremented once per 64 IO interrupts (IRQ down-counter reloads "
          "0x40 at 0x120b4-0x120c8). Nominal 64 / 4000 Hz = 16.0 ms; PinMAME's 4008 Hz IRQ gives 15.97 ms",
          {"irq_per_tick": 64}, "0x37364, 0x120b4", "code", ""),
        F("tick_loop", "The scheduler 0x15a7c busy-waits for 0x37364 to change, then runs the tick pass 0x3405c: event 0x20, "
          "service calls (0xf378, 0x42a8, deff queue 0x27ff0, ...), rng_next 0xc684 (lr 0x3409c), switch dispatcher 0xeadc "
          "-> 0xe85c, 0xfec0, then the ready tasks. One tick-loop pass = one counter increment (measured)",
          None, "0x15a7c, 0x3405c", "code", ""),
        F("tick_measured", "Measured tick length (emulator, wall-clock emulated time per 0x37364 increment)",
          {"samples": len(per), "mean_ms": round(sum(per) / len(per), 3) if per else None,
           "attract_ms": 16.02, "game_ms": 16.19}, "0x37364", "observed",
          "traces/gi_and_tilt.jsonl ev=tick (every 62 passes); game_flow.md quotes 16.26 ms"),
        F("tick_seconds", "ROM timers count ticks; 62 ticks is the ROM's 'one second' (e.g. tilt bob debounce 62 ticks, "
          "sleep(62) loops)", 62, "various", "code", ""),
    ]
    # --- RNG
    m["rng"] = [
        F("rng_lcg", "rng_next 0xc684: seed(0x372c4) = seed * 0x19660d + 1 (mod 2^32), returns the new seed. random(n) 0xc6b4 = "
          "(n * rng_next()) >> 32 (0..n-1). percent(p) 0xc6d4 = ((rng_next() * 100) >> 32) + 1 <= p",
          {"a": "0x19660d", "c": 1, "seed_ram": "0x372c4"}, "0xc684, 0xc6b4, 0xc6d4", "code", ""),
        F("rng_seed", "Initial seed 0x4277dc9 set at boot by 0xc668 (from 0x7b10); seed setter 0xc674 is used only by flash/update "
          "code (0x11a1c, 0x11b88)", "0x4277dc9", "0xc668, 0xc674", "code", ""),
        F("rng_tick", "The OS advances the RNG once per tick (tick pass calls 0xc684, lr 0x3409c) besides every random() call, "
          "so the sequence depends on timing (switch times), not only on call order", None, "0x3405c", "code", ""),
        F("rng_sites", "Static call sites", {"random": len(sc["random"]), "percent": len(sc["random_percent"]),
                                             "rng_next": len(sc["rng_next"]), "rng_seed": len(sc["rng_seed"])},
          "0xc6b4, 0xc6d4, 0xc684, 0xc674", "code", "static_calls.json"),
    ]
    # --- event system
    names = event_names(sc)
    hooks_rt = [r for r in jl("tilt_modes", lambda l: '"ev":"event_hook"' in l)]
    by_ev = collections.defaultdict(list)
    for r in hooks_rt:
        by_ev[r["event"]].append({"order": r["order"], "fn": r["fn"], "fn_name": ss.name_of(int(r["fn"], 16)),
                                  "prio": r["prio"]})
    static_hooks = collections.defaultdict(list)
    for s in sc["event_hook_add"]:
        if s["r1"] is not None:
            static_hooks[int(s["r1"], 16)].append({"site": s["site"], "fn": s["r2"], "prio": s["r3"]})
    posters = collections.defaultdict(list)
    for s in sc["event_post"]:
        if s["r0"] is not None:
            posters[int(s["r0"], 16)].append(s["site"] + " " + (s["func_name"] or "?"))
    events = []
    for e in sorted(set(list(by_ev) + list(static_hooks) + list(posters))):
        events.append({"event": hx(e), "dec": e, "meaning": names.get(e, ""), "posted_by": posters.get(e, []),
                       "hooks_runtime_in_call_order": by_ev.get(e, []), "hooks_static": static_hooks.get(e, [])})
    m["events"] = {
        "facts": [
            F("event_hook_add", "event_hook_add 0x7944(ctx, id < 0x6d, fn, prio): node {fn, prio u8, next} inserted into list "
              "0x3e3a0[id] in DESCENDING priority; an equal priority goes AFTER the existing entries (so static-init order "
              "breaks ties)", None, "0x7944, 0x3e3a0", "code", ""),
            F("event_post", "event_post 0x79ec(id, arg) calls the hooks in list order; a hook returning 0 VETOES: the chain "
              "stops and event_post returns 0. Many OS steps post a 'may I?' event first (0x12 ball start, 0x1e end of ball, "
              "0x2f game start, 0x47 next player, 0x55 slam, 0x14 bonus) and skip the step on a veto",
              None, "0x79ec", "code", ""),
            F("event_counts", "Hook nodes in RAM after init = static event_hook_add sites",
              {"runtime_nodes": len(hooks_rt), "static_sites": len(sc["event_hook_add"]),
               "static_resolved": sum(1 for s in sc["event_hook_add"] if s["r1"] is not None),
               "event_post_sites": len(sc["event_post"])}, "0x3e3a0", "observed",
              "traces/tilt_modes.jsonl ev=event_hook (dump after start)"),
        ],
        "events": events,
    }
    # --- tasks
    m["tasks"] = task_table(sc)
    # --- switches
    m["switch_dispatch"] = [
        F("sw_dispatch", "Switch dispatcher 0xe85c runs once per tick (called from 0xeadc in the tick pass). Per switch: "
          "debounce counters desc+0x1b (close) / +0x1c (open); a close edge is reported only if desc flags(+0xe) & 0x400, an "
          "open edge only if & 0x800", None, "0xe85c, 0xeadc", "code", ""),
        F("sw_gate", "Game-state gate: the handler runs when gf_state (0x37274) == 0 or (desc flags & gf_state) != 0. So with "
          "TILT (0x200) or attract (0x10) set, only switches whose flags carry that bit are handled", None, "0xe85c", "code", ""),
        F("sw_order", "Order per accepted edge: (1) task_create(desc+0x14 task id, desc handler, desc+0xc flags, 0x300) with "
          "the switch number at task+0x30 and desc+4 at +0x34 - the task is only queued; (2) synchronous event_post 0x6c "
          "if desc flag 0x2000 (instant / force switch) or 0x6b if flag 0x1000 (counting switch) - the valid-playfield "
          "logic hooks these; (3) the handler task body runs later in the same tick's task pass. So event hooks for "
          "0x6b/0x6c always run BEFORE the switch handler", None, "0xe85c, 0xea88 (0x6c), 0xead4 (0x6b)", "observed",
          "traces/tilt_modes.jsonl: event 0x6c caller 0xea88 logged before the handler effects"),
        F("sw_matrix_table", "Matrix switch table", tot_entry(0x36dc8), "0x36dc8", "code", ""),
        F("sw_dedicated_table", "Dedicated switch table", tot_entry(0x36dd4), "0x36dd4", "code", ""),
    ]
    # --- deffs
    m["deff_scheduler"] = [
        F("deff_table", "Deff table {fn, u16 flags +4, u8 prio +6}", tot_entry(0x36c54), "0x36c54 -> 0x040e1350", "code", ""),
        F("deff_start_rule", "deff_start 0x280b0(id, a, b) -> shared body. Refused when the caller is itself a deff task (task "
          "flag 4). Starts when: (no deff active, OR the active one is the background deff 0x381ae, OR the new one is not a "
          "background deff) AND (b = force, OR new prio > current prio 0x381aa, OR equal prio and current flags & 3)",
          None, "0x280b0, 0x381a8 active id, 0x381aa prio, 0x381ae background", "code", ""),
        F("deff_start_effects", "On start: every deff task is killed; task_create(2, fn, 0x806 | 0x2000 if !(flags & 5), 0x300); "
          "active id -> 0x381a8; event 0x1b posted; two DMD pages allocated unless flags & 0x10", None, "0x280b0", "code", ""),
        F("deff_queue", "Not started + (arg a OR flags & 0x20) + not background -> queued in a ring at 0x3d540: 12 slots x 0x6c B "
          "(11 usable), head 0x381b0, tail 0x381b4; full -> error 0x23. Each tick 0x27ff0 starts the queue head when no deff "
          "runs, otherwise restarts the background deff", {"slots": 12, "usable": 11, "entry_bytes": 0x6c},
          "0x3d540, 0x381b0, 0x381b4, 0x27ff0", "code", ""),
        F("deff_flags", "Deff flag bits: 0x1 background (sets 0x381ae, restarted when idle), 0x2/0x1 allow equal-priority "
          "replacement, 0x4 with 0x1 -> no 0x2000 task flag, 0x10 no page allocation, 0x20 queue if blocked",
          None, "0x040e1350", "code", ""),
        F("deff_stop", "deff_stop 0x282e0(id, run_queue, restart_background)", None, "0x282e0", "code", ""),
        F("deff_sites", "Static deff_start sites (9 with a non-constant id: deff rules 0x19940, tilt 0x24424/0x244e8, wrappers "
          "0x100f868 / 0x100fa6c / 0x100fcb0 / 0x100fe64, 0x28834, 0x1018a74)", len(sc["deff_start"]), "0x280b0", "code",
          "static_calls.json"),
    ]
    # --- rule lists
    rules = [r for r in jl("tilt_modes", lambda l: '"ev":"rule"' in l)]
    lists = collections.defaultdict(list)
    for r in rules:
        lists[r["list"]].append({k: r[k] for k in ("order", "obj", "vtable", "fn", "mode_mask", "prio", "cond", "id")})
    kinds = {0: ("task rules (rule_obj_init 0x194f8 direct)", "0x39fa8"),
             1: ("function rules, mode mask 0x3ff (mech/flipper upkeep)", "0x39fa8"),
             2: ("DEFF rules: init 0x1982c (named lamp_rule_init in the decompile; vtable 0x39f60, id = deff number), started "
                 "via 0x198a8 -> deff_start at 0x19940", "0x39f60"),
             3: ("LEFF rules: init 0x19740 leff_rule_init (vtable 0x39f88, id = leff number), started at 0x19814",
                 "0x39f88"),
             4: ("TUBE-SHOW rules: init 0xda4 (vtable 0x39b08, id = tube show), started at 0xe78", "0x39b08"),
             5: ("lamp functions, mode mask 0x20 (game)", "0x39fa8")}
    static_init = {2: len(find_bl_callers(0x1982c)), 3: len(find_bl_callers(0x19740)), 4: len(find_bl_callers(0xda4))}
    m["rule_lists"] = {
        "facts": [
            F("rule_eval", "Six rule lists at RAM 0x3e560[0..5]. rule_obj_init 0x194f8 inserts objects sorted by priority (+7). "
              "rules_refresh_request 0x19648 (116 call sites) asks for a re-evaluation (0x1965c). Each rule: if (mode_mask & "
              "gf_state-derived mode) and cond() is true the effect is (re)started, otherwise stopped", None,
              "0x3e560, 0x194f8, 0x19648", "code", ""),
            F("rule_counts", "Runtime list sizes after game start vs static init sites",
              {"runtime": {str(k): len(v) for k, v in sorted(lists.items())},
               "static_init_sites": {str(k): v for k, v in static_init.items()}}, "0x3e560", "observed",
              "traces/tilt_modes.jsonl ev=rule (dump at t 11.75)"),
        ],
        "lists": [{"list": k, "kind": kinds[k][0], "vtable": kinds[k][1], "rules": v} for k, v in sorted(lists.items())],
    }
    m["game_flags"] = game_flag_classes()
    m["table_of_tables"] = [dict(tot_entry(a), index=(a - TOT) // 12) for a in range(TOT, 0x36d64, 12)
                            if 0 < u32(a + 4) < 100000 and u32(a + 8) < 4096]
    return m


def event_names(sc):
    """Short meaning per event id: curated from game_flow.md / developer_guide.md and this work (tagged in os_model.md)."""
    n = {
        0x0f: "ball served to shooter (arg = reason)", 0x11: "ball start: per-ball init", 0x12: "ball start: veto check",
        0x13: "ball start finished", 0x14: "bonus: veto check", 0x15: "bonus done", 0x16: "bonus value gather",
        0x1b: "deff started", 0x1d: "end of ball: stop modes", 0x1e: "end of ball: veto check (ball save)",
        0x1f: "end of ball finished", 0x20: "every tick", 0x26: "player's first ball (per-player init)",
        0x27: "ball start: after per-ball init", 0x2a: "game over", 0x2b: "game over finished (music, attract)",
        0x2e: "game start", 0x2f: "game start: veto check", 0x30: "game start finished", 0x47: "next player: veto check",
        0x48: "next player done", 0x54: "slam tilt", 0x55: "slam tilt: veto check", 0x65: "tilt (modes)",
        0x66: "tilt (first, from 0x24490)", 0x67: "tilt finished", 0x68: "tilt warning", 0x69: "tilt warning finished",
        0x6a: "playfield validated", 0x6b: "counting switch", 0x6c: "instant (force) switch",
    }
    return n


def task_table(sc):
    """Task id table: static task_create* sites with a constant id + runtime task_start events from every trace."""
    rows = collections.OrderedDict()

    def add(tid, **kw):
        r = rows.setdefault(tid, {"task_id": hx(tid), "fns": set(), "sites": set(), "observed_in": set(), "names": set()})
        for k, v in kw.items():
            if v:
                r[k].add(v)
    for k in ("task_create", "task_create_unique", "task_recreate", "task_timer_start", "task_timer_restart", "task_set_id"):
        for s in sc[k]:
            if s["r0"] is None:
                continue
            tid = int(s["r0"], 16)
            fn = s["r1"] if k != "task_set_id" else None
            add(tid, fns=fn, sites="%s %s" % (k, s["site"]))
            if fn:
                nm = ss.name_of(int(fn, 16))
                if nm:
                    rows[tid]["names"].add(nm)
    files = sorted(glob.glob(os.path.join(REPO, "rules", "traces", "*.jsonl"))) + sorted(glob.glob(os.path.join(TR, "*.jsonl")))
    for p in files:
        base = os.path.basename(p)[:-6]
        with open(p) as f:
            for line in f:
                if '"ev":"task_start"' not in line:
                    continue
                r = json.loads(line)
                tid = int(r["task"], 16)
                add(tid, fns=r["fn"], observed_in=base)
                nm = ss.name_of(int(r["fn"], 16))
                if nm:
                    rows[tid]["names"].add(nm)
    out = []
    for tid in sorted(rows):
        r = rows[tid]
        out.append({"task_id": r["task_id"], "function_count": len(r["fns"]), "functions": sorted(r["fns"])[:24],
                    "names": sorted(r["names"])[:24],
                    "static_sites": sorted(r["sites"])[:12], "static_site_count": len(r["sites"]),
                    "observed_in": sorted(r["observed_in"]),
                    "tag": "observed" if r["observed_in"] else "code"})
    known = {0x2: "deff task (every display effect runs as task 2)", 0x3: "leff tasks", 0x29: "game start", 0x2a: "end of ball",
             0x2b: "ball search", 0x39: "slam reset (0x23e18)", 0x56: "SOS TOTAL display", 0x70: "skill shot A (left ramp)",
             0x72: "skill shot B (right ramp)", 0xa0: "SOS intro", 0xa1: "SOS quiet award", 0xa2: "SOS skip-bonus payer"}
    for r in out:
        r["role"] = known.get(int(r["task_id"], 16), "")
    return {"facts": [F("task_ids", "Task ids are u16 numbers chosen by the caller (not handles). task_create 0xb624, "
                        "create_unique 0xb718, recreate 0xb76c, timer_start 0xb7d0, timer_restart 0xb808, set_id 0xc0d0, "
                        "kill 0xba3c(id, mask), kill_range 0xbb40, running 0xbe68, running_range 0xbecc, spawn_child 0xb840. "
                        "Every switch handler runs as a task with the id from its switch descriptor (+0x14)",
                        {"ids": len(out), "observed_ids": sum(1 for r in out if r["observed_in"])}, "0xb624..0xc0d0", "code", "")],
            "ids": out}


def game_flag_classes():
    cls = []
    for i in range(0x38):
        v = u16(0x040e1f6c + 4 * i)
        d = u8(0x040e1f6c + 4 * i + 2)
        cls.append({"flag": i, "flag_hex": hx(i), "class_bits": hx(v), "default": d,
                    "global_not_swapped": bool(v & 1), "reset_game_start": bool(v & 2), "reset_ball_start": bool(v & 4),
                    "reset_tilt": bool(v & 8)})
    per_player = [c["flag"] for c in cls if not c["global_not_swapped"] and c["flag"] not in (0,)]
    glob_lamps = [l for l in range(1, 0x51) if u8(0x040e3395 + 12 * l) & 1]
    assert glob_lamps == [26, 65, 66]
    return {
        "facts": [
            F("flags_block", "Game flags live in one 8-byte block (pointer RAM 0x37268, 56 flags 0..55) plus four 8-byte save "
              "slots (pointers 0x3c188[0..3]), allocated by 0x64a4", None, "0x37268, 0x3c188, 0x64a4", "code", ""),
            F("flags_swap", "On a player change (0x214d0) the ROM saves the block to the old player's slot (0x6700) and "
              "restores the new player's slot (0x6744) for every flag whose descriptor bit 0 is CLEAR; flags with bit 0 SET "
              "are global and keep the current value. Descriptor table 0x040e1f6c, 4 B per flag {u16 class, u8 default}",
              {"per_player_flags": per_player}, "0x214d0, 0x6700, 0x6744, 0x040e1f6c", "code",
              "developer_guide.md said 'inferred, not tested with 2 players'; now read from code"),
            F("flags_reset", "0x63c0(class) resets every flag whose class has that bit to its default (all defaults are 0): "
              "class 2 at game start (0x205f4; also in all 4 player slots for per-player flags), class 4 at every ball start "
              "(0x206ac), class 8 at tilt (0x2444c)", None, "0x63c0, 0x205f4, 0x206ac", "code", ""),
            F("lamps_swap", "Lamp state is swapped per player too: 0x21080 saves 20 B from 0x3c204 and 10 B from 0x3c218 to "
              "0x21108ed + 0x14*p / 0x2110947 + 10*p; 0x210d4 restores every lamp except those whose lamp-table byte "
              "(0x040e3390 + 12*lamp + 5) has bit 0 set: lamps 26 SHOOT AGAIN, 65 START BUTTON, 66 TOURNAMENT START",
              {"global_lamps": glob_lamps}, "0x21080, 0x210d4, 0x040e3390", "code", ""),
        ],
        "flags": cls,
    }


# =====================================================================================================  Part B
def rotation(name):
    seq = []
    cur = {"player": None, "ball": None}
    for r in jl(name, lambda l: '"name":"cur_player"' in l or '"name":"ball_num"' in l or '"name":"num_players"' in l
                or '"id":26,' in l and "deff_start" in l or '"ev":"mark"' in l or '"name":"tilt_warnings"' in l):
        if r["ev"] == "var":
            seq.append({"t": r["t"], r["name"]: r["value"]})
        elif r["ev"] == "deff_start":
            seq.append({"t": r["t"], "shoot_again_deff_26": True})
        elif r["ev"] == "mark":
            seq.append({"t": r["t"], "mark": r["text"]})
    return seq


def multiplayer():
    facts = [
        F("mp_add_players", "Players are added by START (with credit) while the current ball number is 1 - also after the "
          "playfield is valid on ball 1; num_players 0x2110900 increments, audit 0x11, one credit taken. On ball 2 the same "
          "press does nothing (credit kept)", None, "0x20c5c, 0x20d14", "observed",
          "traces/multiplayer_3p.jsonl t 19.02 (3rd player on ball 1 after valid) and t 57.70 (no 4th player on ball 2)"),
        F("mp_rotation", "End of ball -> 0x214d0: event 0x47 (veto); if an extra ball is pending (0x1a27c) flag 9 (shoot "
          "again) is set and the SAME player shoots again; else next = player + 1; past the last player -> player 1 and "
          "ball + 1; past the balls-per-game limit (adj 31, or the tournament value) -> game over 0x20a64. Then save the old "
          "player's flags/lamps, set 0x3817c, restore the new player's, event 0x48",
          None, "0x214d0, 0x21404, 0x213bc", "code", ""),
        F("mp_rotation_observed_4p", "4 players, 3 balls: P1 P2 P3 P3(shoot again: deff 26 + leff 16, same ball) P4 | P1 ...; "
          "ball_num changes when player 1 comes up", None, "0x3817c, 0x3817d", "observed", "traces/multiplayer_4p.jsonl"),
        F("mp_rotation_observed_2p", "2 players: P1 B1, P2 B1, P1 B2 (extra ball collected) -> P1 shoot again -> P2 B2, P1 B3, "
          "P2 B3 -> match -> attract", None, "0x3817c", "observed", "traces/multiplayer_2p.jsonl"),
        F("mp_events", "Ball start order (0x20650): 0x12 veto -> kill tasks flag 0x80 -> first = (ball == 1 and not flag 9) -> "
          "reset class-4 flags -> ... -> if first: event 0x26 (per-player init, ONLY on that player's first ball) -> 0x11 "
          "(every ball) -> 0x27 -> if shoot again: deff 26 + leff 16 (arg = player) -> deff 19 score display -> 0x13",
          None, "0x20650-0x20760", "observed", "traces/multiplayer_2p.jsonl ev=event ids 18, 38, 17, 39, 19"),
        F("mp_player_up_media", "There is no dedicated 'PLAYER n UP' display effect: the score display (deff 19) shows the "
          "current player and the ball-start music call 0x01a plays for every ball. deff 104 'ARCADE IS LIT' (leff 115, sound "
          "0x0df) appears at a player's first ball because the per-player arcade flag goes 0 -> 1 there; it is not a "
          "player-up screen. Shoot again shows deff 26 + leff 16 + sound 0x11b", None, "0x20650, 0x100de10",
          "observed", "traces/multiplayer_2p.jsonl, multiplayer_4p.jsonl"),
        F("mp_extra_ball", "Extra ball in multi-player: collected EB sets shoot_again_pending 0x37430 and eb_collected[p]; at "
          "that player's drain the bonus runs, then the same player gets a new ball on the SAME ball number (deff 26 SHOOT "
          "AGAIN); after it drains play passes to the next player normally", None, "0x1a27c, 0x37430", "observed",
          "traces/multiplayer_2p.jsonl t 56.18 -> 66.75 -> 83.00"),
        F("mp_tilt_in_mp", "A tilt ends only the tilting player's ball: no bonus, warnings reset at the next ball start, the "
          "next player is up", None, "0x2444c", "observed", "traces/multiplayer_3p.jsonl t 34.97 -> 38.67 (P2 tilts, P3 up)"),
        F("mp_end_of_game", "End of game after the last player's last bonus: per-player audit 46 (one per player) and 32 -> "
          "sound 0x039 -> high-score check: deff 31 then initials entry deff 32 per qualifying player (START presses, sound "
          "0x035; after the last letter audit 16, sound 0x036, deff 33, high-score credit award + knocker 0x019) -> match "
          "deff 38 (game state 152, music 0x01c) -> attract deff 1, leff 1, then game-over music 0x01d with leff 133",
          None, "0x20a64, 0x1ad4c, 0x1b660, 0x100f29c", "observed", "traces/multiplayer_4p.jsonl t 140-171"),
        F("mp_replay_in_mp", "A replay score reached by one player in a multi-player game: credit + knocker 0x019 + deff 28 + "
          "leff 17 at that player's bonus end", None, "0x22cac", "observed", "traces/multiplayer_4p.jsonl (P3 poked to 60 M)"),
        F("mp_game_over_speech", "Speech 0x01e plays at some game overs (attract countdown 0x3afec, random 4-6 games)",
          None, "0x100f29c", "observed", "match_natural / multiplayer_2p: 0x01e after deff 1"),
    ]
    facts += game_flag_classes()["facts"]
    scope = per_player_scope()
    return {"facts": facts, "state_scope": scope,
            "rotation": {"multiplayer_2p": rotation("multiplayer_2p"), "multiplayer_3p": rotation("multiplayer_3p"),
                         "multiplayer_4p": rotation("multiplayer_4p")}}


def per_player_scope():
    rows = []
    for p in sorted(glob.glob(os.path.join(REPO, "rules", "work", "ram", "*.tsv"))):
        if p.endswith("_functions.tsv"):
            continue
        mode = os.path.basename(p)[:-4]
        for line in open(p):
            f = line.rstrip("\n").split("\t")
            if len(f) < 4 or not f[0].startswith("0x"):
                continue
            sc = f[3].lower()
            if "per player" in sc or "[player-1]" in (f[4] if len(f) > 4 else "").lower():
                kind = "per_player"
            elif "per ball" in sc or sc.startswith("ball"):
                kind = "per_ball_shared"
            elif "mode" in sc or "window" in sc or "chain" in sc or "session" in sc or "pick" in sc or "start" in sc:
                kind = "transient_shared"
            elif "game" in sc or "machine" in sc:
                kind = "shared"
            else:
                kind = "other"
            rows.append({"mode": mode, "address": f[0], "name": f[1], "size": f[2], "scope_text": f[3], "class": kind,
                         "tag": "code"})
    rows.append({"mode": "os", "address": "0x37268 / 0x3c188", "name": "game flags", "size": "8", "scope_text":
                 "per player except class-bit-0 flags (see os_model.json game_flags)", "class": "per_player_swapped",
                 "tag": "code"})
    rows.append({"mode": "os", "address": "0x3c204 / 0x3c218", "name": "lamp states", "size": "30",
                 "scope_text": "per player except lamps 26, 65, 66", "class": "per_player_swapped", "tag": "code"})
    for a, n, k in (("0x3d4f8", "tilt warnings", "per_ball_shared"), ("0x372e8", "valid playfield", "per_ball_shared"),
                    ("0x37430", "shoot again pending", "shared"), ("0x3d46c", "extra balls lit [p-1]", "per_player"),
                    ("0x3d470", "extra balls collected [p-1]", "per_player"), ("0x2110900", "players in game", "shared"),
                    ("0x3817c", "current player", "shared"), ("0x3817d", "ball number", "shared")):
        rows.append({"mode": "os", "address": a, "name": n, "size": "", "scope_text": "states watch list", "class": k,
                     "tag": "observed"})
    return rows


def tilt():
    facts = [
        F("tilt_warning", "Tilt bob (D17, handler 0x24564): a bob within 62 ticks of the last accepted one is ignored. Each "
          "accepted bob below adj 32 (TILT WARNINGS, default 2): warnings+1 (0x3d4f8), event 0x68, deff 23 'DANGER', leff 11 "
          "(GI off 15 ticks), sound 0x016, event 0x69; sound 0x03d 0.5 s later", None, "0x24564, 0x24404-0x24444",
          "observed", "traces/tilt_modes.jsonl t 14.48, 16.35; gi_and_tilt.jsonl"),
        F("tilt_tilt", "The bob that reaches the limit TILTS (0x2444c): event 0x66 (0x24490), audit 42, event 0x65 (0x244dc), "
          "deff 21 'TILT', leff 9 (GI off), sound 0x017, event 0x67 (0x24510); gf_state |= 0x200 (512); class-8 game flags "
          "reset (flag 46); sound 0x03e 1 s later", None, "0x2444c", "observed", "traces/tilt_modes.jsonl t 18.23, 63.85"),
        F("tilt_switches", "While tilted the switch gate blocks every switch whose descriptor flags lack 0x200, so playfield "
          "switches score nothing (base_score_if_not_tilted 0x102a188 checks again)", None, "0xe85c, 0x102a188", "code", ""),
        F("tilt_ball_save", "Tilt inside the ball-save window: the drain is NOT saved (no BALL SAVED, no re-serve); event 0x1e "
          "-> 0x1d, audit 8, no bonus, next ball", None, "0x20764", "observed",
          "traces/tilt_modes.jsonl t 18.23 tilt at 5 s ball save, drain 20.01 -> ball 2 at 21.93"),
        F("tilt_no_bonus", "End of ball when tilted: 0x20764 skips the bonus (gf_state & 0x200) - deff 25 does not run; ball "
          "start clears 0x200 and the tilt warnings", None, "0x2089c-0x208a4, 0x209b0", "observed",
          "traces/tilt_modes.jsonl, gi_and_tilt.jsonl, multiplayer_3p.jsonl"),
        F("tilt_multiball", "Tilt during Disc Multiball: the tilt does not drain balls; the multiball keeps running until the "
          "balls drain, then its normal end display runs (deff 52, leff 52 - which also takes GI ownership while tilted - "
          "sound 0x02c) and the end of ball follows with no bonus", None, "0x10076e8", "observed",
          "traces/tilt_modes.jsonl t 63.85 tilt, 68.70 MB end, 69.83 end of ball, 71.53 ball 3"),
        F("tilt_gi", "GI off from the tilt until the end-of-ball task 0x2a releases the leff at the drain", None, "0x2ff44",
          "observed", "traces/gi_and_tilt.jsonl t 27.85 -> 31.64"),
        F("tilt_modes_cancel", "Modes stop on event 0x1d (end of ball) as usual; mode-specific tilt hooks on 0x65/0x66 (e.g. "
          "SOS pays unpaid skip bonuses on 0x66) run at the tilt itself", None, "0x01026794", "code",
          "sea_of_simulation.md"),
        F("slam", "Slam (D18, 0x23e40): ignored in service mode; event 0x55 veto; gf_state |= 0x200 (512 in game, 528 in "
          "attract); kill tasks; event 0x54; task 0x39 slam_reset_task 0x23e18; deff 24, leff 12 (blackout + GI off), sound "
          "0x018. After 0xda + 0x5d = 311 ticks (4.99 s measured) it calls 0x10ce8: 0x16a94(1) then an endless loop waiting "
          "for the hardware watchdog -> full machine reset. The game in progress is lost; credits survive (NVRAM)",
          None, "0x23e40, 0x23e18, 0x10ce8", "observed", "traces/slam_tilt.jsonl t 17.88 -> reset_request 22.87"),
        F("slam_attract", "Slam in attract also resets the machine", None, "0x23e40", "observed",
          "traces/slam_tilt.jsonl t 54.15 -> 59.14"),
        F("slam_harness", "PinMAME does not emulate the SAM watchdog: without help the emulator spins in 0x10ce8 forever. "
          "states_ref resets the machine (PinmameReset) when the ROM reaches 0x10ce8", None, "0x10ce8", "observed",
          "states_ref.cpp watchdog emulation"),
    ]
    ev = []
    for r in jl("tilt_modes", lambda l: '"ev":"event"' in l):
        if r["id"] in (0x65, 0x66, 0x67, 0x68, 0x69, 0x1d, 0x1e, 0x1f):
            ev.append({"t": r["t"], "event": hx(r["id"]), "caller": r["caller"]})
    return {"facts": facts, "observed_event_sequence": ev}


def sos_late():
    st = {}
    for r in jl("sos_stages_4_to_8", lambda l: '"name":"sos_' in l or '"ev":"mark"' in l or '"deff_start"' in l):
        pass
    seq = [r for r in jl("sos_stages_4_to_8", lambda l: ('"name":"sos_stage"' in l or '"name":"sos_needed_mask"' in l
                                                        or '"name":"sos_total"' in l or '"ev":"mark"' in l
                                                        or '"id":12' in l and "deff_start" in l
                                                        or '"id":11' in l and "deff_start" in l))]
    chain = []
    for i in range(6):
        a = 0x040d3748 + 16 * i
        chain.append({"shot_id": u32(a), "shot_bit": hx(u32(a + 4)), "adds_when_made": hx(u32(a + 8)), "lamp": u32(a + 12)})
    assert chain[5]["adds_when_made"] == "0x60000"
    facts = [
        F("sos_poke", "Reached with pokes on player 1: all 9 item lit bytes = 1 and items 0-3 collected (0x2111694 + 0x10*i, "
          "byte 0 lit, byte 1 collected), then VUK. Stages 0-3 are skipped and each pays its one-time (k+1) M skip bonus "
          "(deff 115, sound 0x109) - the 3 M and 4 M were still being paid after stage 4 was already complete",
          None, "0x2111694", "observed", "traces/sos_stages_4_to_8.jsonl t 15.02 - 34.74"),
        F("sos_stage4", "Stage 4 QUORRA: mask 0x10000 (left inner loop, sw44 first spin). One shot: 500,000, deff 120",
          {"mask": "0x10000", "points": 500000, "deff": 120}, "0x1025458, 0x102564c", "observed", "t 31.44"),
        F("sos_stage5", "Stage 5 DISC: mask 0xfc000 = all six major shots, 600,000 each, deff 121. The disc opto sw41 spots "
          "the next needed shot (here the last one, right orbit)", {"mask": "0xfc000", "points": 600000, "deff": 121},
          "0x1025720, 0x10258f0, 0x1025a0c", "observed", "t 36.61 - 48.08"),
        F("sos_stage6", "Stage 6 LIGHT CYCLE: starts with mask 0xc8000 (left ramp, right ramp, right orbit); each made shot "
          "ADDS its chained shots from table 0x040d3748 and every shot already made this stage is removed; the stage ends when "
          "the mask is empty. In practice all six major shots are needed once. 700,000 each, deff 122",
          {"start_mask": "0xc8000", "points": 700000, "deff": 122, "chain_table": chain},
          "0x1025a74, 0x1025c50, 0x040d3748", "observed", "t 53.17 - 64.59 (46, 34, 37, 39, 44, 43)"),
        F("sos_stage6_doc", "sea_of_simulation.md lists stage 6 as 'right orbit, right ramp, left ramp (0xc8000), chained': "
          "true for the start mask, but the chain adds right inner loop, left orbit and left inner loop, so 3 shots are not "
          "enough (first run of this scenario stalled at mask 0x34000)", None, "0x1025c50", "observed",
          "contradiction / clarification"),
        F("sos_stage7", "Stage 7 RECOGNIZER: mask 0x2000 (shot 13 = recognizer bank, posted by sw49-51 when task 0x7b is not "
          "running); 6 counted hits (counter 0x3b680), 800,000 each, deff 123", {"hits": 6, "points": 800000, "deff": 123},
          "0x1025df8, 0x1025f64", "observed", "t 69.75 - 76.64"),
        F("sos_stage8", "Stage 8 TRON: mask 0x3c (T R O N drop targets, shots 2-5), 900,000 each, deff 124",
          {"mask": "0x3c", "points": 900000, "deff": 124}, "0x1026058, 0x1026228", "observed", "t 81.81 - 85.97"),
        F("sos_complete", "Completion (0x1026430): game flag 0x36 set, then sos_end 0x1026754 clears flag 0x34 and creates "
          "task 0x56 which shows deff 126 'TOTAL' (sound 0x115) via 0x100f7f0 - the same display as a drain. Audit 121. "
          "deff 125 'SEA OF SIMULATION COMPLETED' has no deff_start site and no deff rule in 1.74 (unreached; its speech "
          "0x113 is inside deff 125, so it never plays)", {"deff": 126, "sound": "0x115"},
          "0x1026430, 0x1026754, 0x1026714", "observed", "t 85.97 flag 54 set, flag 52 clear; 88.25 deff 126"),
        F("sos_complete_doc", "sea_of_simulation.md says completion shows deff 125 with speech 0x113: not observed and no "
          "code path found", None, "0x1028140", "code", "contradiction"),
        F("sos_after", "After completion the ball stays in normal play; the drain shows bonus as usual", None, "", "observed",
          "t 94.1 drain"),
    ]
    return {"facts": facts, "observed": seq}


def match():
    assert has_ins(0x1b6ac, 0x1b6b0, "bl", "#0xc6b4")
    assert has_ins(0x1b690, 0x1b694, "cmp", "r8, #0xb")
    facts = [
        F("match_skip", "Match 0x1b660 runs at game over unless adj 30 MATCH PERCENTAGE = 11 (off) or tournament mode "
          "(0x252a0(1))", None, "0x1b660-0x1b694", "code", ""),
        F("match_number", "The number is drawn FIRST, always: m = random(10) * 10 (call at 0x1b6ac) -> 00, 10, ..., 90",
          None, "0x1b6ac", "code", ""),
        F("match_rate", "rate = audit 0xf (TOTAL MATCHES) * 100 / audit 0x11 (GAMES STARTED), read via 0x164c(id, 0xc0); rate "
          "= 0 if no games", None, "0x1b6b8-0x1b6f8", "code", ""),
        F("match_win_branch", "If rate < adj 30: every player p (1..players) whose score % 100 == m wins: bit p set in a mask "
          "(-> deff +0x30) and the winner count 0x3743e increments", None, "0x1b700-0x1b76c", "code", ""),
        F("match_loss_branch", "Else (rate >= adj 30): forced loss - m steps +10 (99 -> 0) and is re-checked against all "
          "players until nobody matches; it ALWAYS moves at least once, so the shown number is never the drawn one; error "
          "log 0xb1 if it cycles back", None, "0x1b770-0x1b7e4", "code", ""),
        F("match_odds", "Per player the natural chance is 1/10 when rate < adj 30 and 0 otherwise, so the lifetime match "
          "rate settles just under adj 30 percent (factory 9 %) per game; a score's last two digits are always x0 in this "
          "game (all awards are multiples of 10)", None, "0x1b660", "inferred", ""),
        F("match_display", "deff 38 gets the winner mask (+0x30) and the number (+0x34); music 0x01c at start, sfx 0x041, "
          "0x03f, 0x040, 0x042 (identical in win and loss); a win adds 0x043 when the award is given and 0x045 1.6 s later",
          None, "0x1b7f0-0x1b80c", "observed", "traces/match_win.jsonl vs match_natural.jsonl"),
        F("match_award", "After the deff, per winner every 31 ticks (0x1b954 -> match_award 0x1b86c): adj 29 MATCH AWARD 0 -> "
          "credit 0x4cf0(0x36f66) + knocker 0x1b370(1,1) (sound 0x019); 1 -> ticket 0x100f8; 2 -> nothing. Audit 0xf",
          None, "0x1b86c", "observed", "traces/match_win.jsonl t 37.86 audit 15, credits 0 -> 1, sound 0x019"),
        F("match_timing", "deff 38 lasts 6.24 s on a loss and 7.84 s on a win, then attract deff 1", None, "", "observed",
          "match_natural 33.67 -> 39.91; match_win 33.67 -> 41.51"),
        F("match_force", "Forcing in the emulator: pokeat 1b6ac 372c4 SEED 4 writes the seed just before random(10). SEED = "
          "(next - 1) * inverse(0x19660d) mod 2^32 with next in [d * 2^32 / 10, (d + 1) * 2^32 / 10) for the wanted digit d. "
          "d = 4 -> SEED 0xa7bf957a (next 0x73333333)", {"seed": "0xa7bf957a", "digit": 4}, "0x372c4", "observed",
          "traces/match_win.txt"),
    ]
    res = {}
    for name in ("match_natural", "match_win", "match_forced_loss"):
        d = {"draw": None, "winners": 0, "credit_award": False, "final_score": None}
        for r in jl(name, lambda l: '0x1b6b0' in l or '"match_winners"' in l or '"name":"credits"' in l or '"ev":"score"' in l):
            if r["ev"] == "rng":
                d["draw"] = r["next"] * 10
                d["seed_before"] = r["seed"]
            elif r["ev"] == "var" and r["name"] == "match_winners" and r["value"]:
                d["winners"] = r["value"]
            elif r["ev"] == "var" and r["name"] == "credits" and d["draw"] is not None and r["value"] > r["old"]:
                d["credit_award"] = True
            elif r["ev"] == "score":
                d["final_score"] = r["total"]
        res[name] = d
    assert res["match_win"]["winners"] == 1 and res["match_forced_loss"]["winners"] == 0
    assert res["match_natural"]["draw"] == 50 and res["match_natural"]["final_score"] % 100 == 40
    facts.append(F("match_runs", "Scenario results (same play, final score 757,740 -> 40)", res, "0x1b660", "observed",
                   "traces/match_natural|match_win|match_forced_loss.jsonl"))
    return {"facts": facts}


def scenarios():
    out = []
    for p in sorted(glob.glob(os.path.join(TR, "*.txt"))):
        name = os.path.basename(p)[:-4]
        jp = os.path.join(TR, name + ".jsonl")
        if not os.path.exists(jp):
            continue
        txt = open(p).read().splitlines()
        head = [l[1:].strip() for l in txt if l.startswith("#")]
        pokes = [l for l in txt if l.split()[:1] in (["poke"], ["pokeat"], ["adj"])]
        cnt = collections.Counter()
        end = None
        with open(jp) as f:
            for line in f:
                m = re.search(r'"ev":"([a-z_]+)"', line)
                if m:
                    cnt[m.group(1)] += 1
                if '"ev":"end"' in line:
                    end = json.loads(line)["t"]
        out.append({"scenario": "traces/%s.txt" % name, "trace": "traces/%s.jsonl" % name, "purpose": " ".join(head)[:600],
                    "pokes_and_adjustments": pokes, "emulated_seconds": end, "event_counts": dict(cnt),
                    "watch": "sos_watch.tsv" if name.startswith("sos") else "states_watch.tsv"})
    return out


def main():
    hw = {"light_tubes": light_tubes(), "gi": gi(), "dedicated_switches": dedicated_summary()}
    json.dump(hw, open(os.path.join(OUT, "hardware_facts.json"), "w"), indent=1)
    osm = os_model()
    json.dump(osm, open(os.path.join(OUT, "os_model.json"), "w"), indent=1)
    json.dump(multiplayer(), open(os.path.join(OUT, "multiplayer.json"), "w"), indent=1)
    json.dump(tilt(), open(os.path.join(OUT, "tilt.json"), "w"), indent=1)
    json.dump(sos_late(), open(os.path.join(OUT, "sea_of_simulation_late.json"), "w"), indent=1)
    json.dump(match(), open(os.path.join(OUT, "match.json"), "w"), indent=1)
    sc = scenarios()
    json.dump(sc, open(os.path.join(OUT, "scenarios.json"), "w"), indent=1)
    print("hardware facts", sum(len(v) for v in hw.values()), "| events", len(osm["events"]["events"]),
          "| task ids", len(osm["tasks"]["ids"]), "| rule lists", [len(l["rules"]) for l in osm["rule_lists"]["lists"]],
          "| scenarios", len(sc))


if __name__ == "__main__":
    main()
