"""Coil table, automatic hardware rules and recommended MPF drive values.

Writes rom_data/io/coils.csv and rom_data/io/coil_rules.json. Needs rom_data/io/coil_calls.csv
(hw_calls.py) and rom_data/io/coil_observed.json (hw_trace.cpp runs summarised by hw_pulses.py).
Run: python3 rom_data/tools/hw_calls.py && python3 rom_data/tools/hw_coils.py
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, u8, u16, u32, foff, hx, msg, cstr
from hw_common import REPO, func_name

IO = os.path.join(REPO, 'rom_data', 'io')
DESC = 0x040e0f60          # coil descriptor table (table-of-tables RAM 0x36c48: count 0x24, 28 B)
NDESC = u32(0x36c48 + 4)
assert NDESC == 0x24 and u32(0x36c48) == DESC and u32(0x36c48 + 8) == 28

# ---- flag bits of descriptor +0x00: meaning and the code that reads them
FLAG_BITS = [
    (0x00000001, 'aux', 'no reader found; set only on the aux-bus ticket outputs 33-35', 'inferred'),
    (0x00000002, 'power_exempt', 'FUN_000041f0 0x4234: coils with bit 2 form the mask 0x3b984; the IO interrupt 0x12070 '
                 'writes shadow & mask when (RAM 0x3727c & 3) != 3 (power-status bits not both set, the state the coil test '
                 'reports as "50V / 20V DISABLED"), so only these outputs can drive then', 'code'),
    (0x00000004, 'flasher', 'flash-lamp test lists coils with (flags & 0x1004) == 4 (FUN_01040e6c/010412c0/01041340); '
                 'ball search skips it (mask 0xa0dc, FUN_000030a8)', 'code'),
    (0x00000008, 'flipper', 'ball search skips it (mask 0xa0dc, FUN_000030a8); no other reader found', 'code'),
    (0x00000040, 'ball_device_kicker', 'ball search skips it (mask 0xa0dc); the ball-device search kicks these instead', 'code'),
    (0x00000080, 'optional', 'ball search skips it (mask 0xa0dc); no other reader found', 'code'),
    (0x00000100, 'motor_or_long', 'no reader found (static scan of tst/and/bic immediates and the emulator table-read trace); '
                 'set on shaker, 3-bank motor/relay, recognizer motor relay', 'inferred'),
    (0x00000400, 'no_cycle_test', 'skipped by the cycling coil test task FUN_0103f47c (0x0103f4b4 ands #0x400)', 'code'),
    (0x00000800, 'hidden_in_tests', 'skipped by coil test and cycling coil test selection FUN_0103eb2c/0103ef70/0103efe0 (tst #0x800)', 'code'),
    (0x00002000, 'bumper', 'ball search skips the direct pulse (mask 0xa0dc); bumpers are pulsed by the bumper rule ball search FUN_00003a8c', 'code'),
    (0x00004000, 'relay', 'no reader found; set on disc direction relay and the two motor relays', 'inferred'),
    (0x00010000, 'solenoid', 'no reader found; set on every 50 V solenoid (kickers, bumpers, slings, flippers, post, disc motor)', 'inferred'),
]
KNOWN = sum(b for b, *_ in FLAG_BITS)

# ---- per-coil analysis (addresses are where the facts come from); kind/tags are this study's
KIND = {
    1: ('pulse', 'ball device 1 (trough) kicker'), 2: ('pulse', 'ball device 2 (shooter lane) auto launch'),
    3: ('pulse', 'drop target bank reset (drop_bank object, coil 3)'), 4: ('pulse', 'ball device 3 (video game eject / VUK) kicker'),
    5: ('motor', 'disc motor power, held on (or timed) by task_a8_disc_motor_run 0x010064c4'),
    6: ('motor', 'Recognizer 3-bank motor, held on until the up/down switch 53/52 (bank_motor object FUN_00018004, init 0x01022544)'),
    7: ('pulse_hold', 'orbit post: 64 ms pulse then pattern hold (post object, FUN_00000a78 / end callback 0x00000ab0)'),
    8: ('motor', 'shaker motor, timed on (shaker_run 0x010289b8 -> FUN_01028924)'),
    9: ('autofire', 'pop bumper (bumper rule 1)'), 10: ('autofire', 'pop bumper (bumper rule 2)'), 11: ('autofire', 'pop bumper (bumper rule 3)'),
    12: ('flipper', 'upper left flipper (flipper rule 2)'), 13: ('autofire', 'slingshot (sling rule 1)'), 14: ('autofire', 'slingshot (sling rule 2)'),
    15: ('flipper', 'left flipper (flipper rule 0)'), 16: ('flipper', 'right flipper (flipper rule 1)'),
    22: ('relay', 'disc direction relay, held (coil_on/coil_off in FUN_01006534)'),
    23: ('motor', 'Recognizer motor relay, held until the next position switch 54-56 (motor object FUN_00016c40, init 0x01022f08)'),
    24: ('pulse', 'knocker queue (table 0x040e2130 record 1, FUN_0000a844): 80 ms per knock'),
    30: ('relay', 'disc motor relay, held while the disc spins (task_a8_disc_motor_run)'),
    33: ('aux', 'ticket dispenser advance output (device 0x040f455c)'), 34: ('aux', 'ticket/coin meter, 100 ms per count (table 0x040e2130 record 2)'),
    35: ('aux', 'ticket dispenser enable, held while dispensing (device 0x040f455c)'),
}
for c in (17, 18, 19, 20, 21, 25, 26, 27, 28, 29, 31, 32):
    KIND[c] = ('flasher', 'flash lamp')

# Recommended MPF values: (default_pulse_ms, default_hold_power, pulse_power, recycle_ms, note, evidence)
MPF = {
    1: (64, None, None, None, 'trough eject', 'ball device 1 kick fn 0x0101bbc0 -> FUN_00002b60(1, 64, sync) [code]; observed 64-65 ms'),
    2: (64, None, None, None, 'auto launch', 'ball device 2 kick fn 0x0101bc7c -> FUN_00002b60(2, 64, sync) [code]; observed 64 ms'),
    3: (64, None, None, None, 'drop target reset', 'drop bank class vtable 0x39ae4 -> 0x0100be74: FUN_00002bc8(coil, 64, sync) [code]; coil 3 from drop_bank_init(&tron_drop_bank,3,...) call 0x0100b2e4 [code], vtable link [inferred]'),
    4: (64, None, 0.5, None, 'soft kick: 1 ms on / 1 ms off for 64 ms', 'ball device 3 kick fn 0x0101bdd0 -> FUN_00002e5c(4, 64, on 1, off 1, sync) at 0x0101bf2c [code]; observed 32 x 1 ms pulses at 2 ms period'),
    5: (None, 1.0, None, None, 'motor: enable/disable (hold full power)', 'task_a8_disc_motor_run 0x010064c4: coil_on(5) or timed FUN_00002cb0(5, secs*1000) [code]'),
    6: (None, 1.0, None, None, 'motor: enable until position switch', 'bank motor object (FUN_00018004) drives the output directly from the IO interrupt [code]; observed 626-629 ms runs in the ball sim'),
    7: (64, 0.143, None, None, 'post: 64 ms then hold 1 ms on / 6 ms off', 'FUN_00000a78: FUN_00002bc8(7, 64, end_fn 0xab0) [code]; 0xab0 switches the slot to pattern 1 over 7 bits for obj+0xc*16 ms [code]; observed 64-68 ms + 1.0/7.0 ms for 1.5-2.0 s'),
    8: (None, 1.0, None, None, 'shaker: enable for 200/384/1024 ms (strength 1/2/3)', 'table 0x040d3998 [code]; observed 203/390/1040 ms'),
    9: (32, None, None, 16, 'pop bumper autofire', 'bumper rule 0x040f0a68: pulse 32, recycle 16, extend 16, debounce 2 [code]; observed 30-49 ms'),
    10: (32, None, None, 16, 'pop bumper autofire', 'bumper rule 0x040f0a74 [code]; observed 49 ms (30 ms switch closure)'),
    11: (32, None, None, 16, 'pop bumper autofire', 'bumper rule 0x040f0a80 [code]; observed 49 ms (30 ms switch closure)'),
    12: (40, 0.083, None, None, 'flipper: 40 ms then 1 ms on / 11 ms off', 'flipper rule 0x040e2064 [code]; not driven in the emulator (its button D12 is not mapped by libpinmame)'),
    13: (32, None, None, 192, 'slingshot autofire', 'sling rule 0x040f0a94: pulse 32, recycle 192 [code]; observed 33.5-33.8 ms'),
    14: (32, None, None, 192, 'slingshot autofire', 'sling rule 0x040f0a9c [code]; observed 33.8 ms'),
    15: (40, 0.083, None, None, 'flipper: 40 ms then 1 ms on / 11 ms off', 'flipper rule 0x040e204c [code]; observed 40.4-41.2 ms then 1.0 ms every 12.2 ms'),
    16: (40, 0.083, None, None, 'flipper: 40 ms then 1 ms on / 11 ms off', 'flipper rule 0x040e2058 [code]; observed 40.0-40.5 ms then 1.0 ms every 12.1 ms'),
    22: (None, 1.0, None, None, 'relay: enable/disable', 'coil_on/coil_off from FUN_01006534 [code]'),
    23: (None, 1.0, None, None, 'motor relay: enable until position switch', 'motor object FUN_00016c40 [code]; observed 18-530 ms runs'),
    24: (80, None, None, None, 'knocker', 'table 0x040e2130 rec 1: 80 ms, gap 8 ticks [code]; observed 80-82 ms'),
    30: (None, 1.0, None, None, 'relay: enable/disable', 'coil_on/coil_off in task_a8_disc_motor_run / disc_motor_stop [code]'),
    33: (64, None, None, None, 'ticket advance (aux bus)', 'service test value +0x10 = 64 [code]; ticket device drives it from the IO interrupt'),
    34: (100, None, None, None, 'meter (aux bus)', 'table 0x040e2130 rec 2: 100 ms per count, gap 16 ticks [code]'),
    35: (None, 1.0, None, None, 'ticket enable (aux bus), held while dispensing', 'device 0x040f455c [code]'),
}


def name_of(n):
    p = u32(DESC + 28 * n + 0x0c)
    return cstr(u32(p)) if foff(p) is not None and foff(u32(p)) is not None else None


def read_desc(n):
    a = DESC + 28 * n
    return {
        'desc_addr': a, 'flags': u32(a), 'test_fn': u32(a + 4), 'ballsearch_fn': u32(a + 8), 'name_rec': u32(a + 0x0c),
        'test_ms': u16(a + 0x10), 'ballsearch_ms': u16(a + 0x12), 'wire1': u16(a + 0x14), 'wire2': u16(a + 0x16),
        'number': u8(a + 0x18), 'devices': u8(a + 0x19), 'pad': u16(a + 0x1a),
    }


def flipper_rules():
    """hardware rule table for flippers: table-of-tables RAM 0x36c9c = {0x040e204c, 3, 12}, built by FUN_00006ce4"""
    base, n, sz = u32(0x36c9c), u32(0x36ca0), u32(0x36ca4)
    out = []
    for i in range(n):
        a = base + i * sz
        b = ROM[foff(a):foff(a) + sz]
        out.append({
            'index': i, 'addr': hx(a), 'raw': b.hex(), 'type': b[0],
            'switch': b[1], 'switch_alt': b[2], 'coil': b[3], 'byte4': b[4], 'eos_switch': b[5],
            'pulse_ms': b[6], 'eos_cut_ms': b[7], 'hold_on_ms': b[8], 'hold_off_ms': b[9],
            'hold_duty': round(b[8] / (b[8] + b[9]), 4),
            'switch_name': 'SAM dedicated D%d (DED #%d)' % (b[1] - 0x81, b[1] - 0x80) if b[1] > 0x80 else b[1],
            'tag': 'code',
        })
    return {'table': hx(base), 'count_addr': '0x36ca0', 'count': n, 'record_size': sz, 'builder': '0x00006ce4 (from 0x0100f090)',
            'irq_service': '0x00012070 (block at 0x12920-0x12b98, every 4th IO interrupt = 1 ms)',
            'runtime': 'RAM ptr 0x3726c, count 0x37270, 0x40-byte entries',
            'fields': {
                'type': 'byte 0 -> runtime +0x22 (1 = left side, 2 = right side; no reader found) [code/inferred]',
                'switch': 'byte 1: flipper button (Stern dedicated switch 0x81+n = D(n)); runtime +0x2c',
                'switch_alt': 'byte 2: used instead of byte 1 when sw_is_disabled(byte 1) at build time (FUN_00006ce4 0x6d74)',
                'coil': 'byte 3: coil number; runtime +0x2a',
                'eos_switch': 'byte 5: end-of-stroke switch (0 = none); runtime +0x2d',
                'pulse_ms': 'byte 6: power pulse length in 1 ms units; runtime +0x27',
                'eos_cut_ms': 'byte 7: if the EOS (closed at the start) opens during the power pulse, the pulse is cut to at most this many ms more and an EOS re-pulse is armed; runtime +0x29',
                'hold_on_ms': 'byte 8: hold PWM on time (ms); runtime +0x3a',
                'hold_off_ms': 'byte 9: hold PWM off time (ms); runtime +0x3c. Phases of the flippers are staggered: +0x3d = index*(on+off)/count',
            },
            'behaviour': [
                'Button debounce: closed for switch-descriptor +0x1b ms (1 for D8/D10/D12) arms, open for +0x1c ms (3) releases (runtime +0x24/+0x26) [code; values from the runtime dump, observed]',
                'On arm: coil on for pulse_ms (40), then PWM hold hold_on/hold_off (1/11 ms = 8.3 %) until the button is released, then off [code; observed 40.4-41.2 ms + 1.0 ms every 12.1-12.2 ms]',
                'EOS: the EOS state is sampled at arm time (+0x30). If it was closed and is seen open (debounced) during the power pulse, the remaining pulse is cut to <= eos_cut_ms (8) and flag +0x38 is set; during hold, if flag set and EOS closes again, up to 2 re-pulses of pulse_ms are given (+0x39 = 2) [code, decompile of 0x12070; EOS polarity inferred]',
                'Rules are enabled per entry by FUN_00007090 (game play, ball in play) and disabled by FUN_00006ffc (tilt, game over); FUN_00007114 asks event 0x28 hooks first [code]',
            ]}, out


def bumper_rules():
    base = 0x040f0a5c   # FUN_0000378c reads records 1..3 (record 0 unused), 12 B
    out = []
    for i in range(1, 4):
        a = base + 12 * i
        out.append({'index': i, 'addr': hx(a), 'raw': ROM[foff(a):foff(a) + 12].hex(),
                    'pulse_ms': u16(a), 'recycle_ms': u16(a + 2), 'extend_ms': u8(a + 4), 'byte5': u8(a + 5),
                    'switch': u8(a + 6), 'coil': u8(a + 7), 'debounce_ms': u8(a + 8), 'tag': 'code'})
    return {'table': hx(base), 'records': '1..3 (record 0 empty), 12 B', 'builder': '0x0000378c', 'runtime': 'RAM ptr 0x37254, 0x20 B each',
            'irq_service': '0x00012070 (block after 0x12b98, every 4th IO interrupt = 1 ms)',
            'enable': 'FUN_00003984(i, on) (bumper_enable); all on/off: 0x3a4c/0x3a0c; ball search FUN_00003a8c pulses the coil for desc +0x12 ms',
            'behaviour': [
                'Idle: switch closed for debounce_ms (2) -> counter = pulse+recycle (48), coil on [code]',
                'While counter > recycle: counter--, coil stays on; if the switch opens: counter = recycle and the coil stays on extend_ms (16) more [code]',
                'Then coil off; counter holds at recycle while the switch stays closed, then counts down recycle_ms (16) before the next shot [code]',
                'Net: on-time = 32 ms if the switch is held >= 32 ms, else (release time + 16 ms); observed 30.5-49 ms [observed]',
            ]}, out


def sling_rules():
    base = 0x040f0a8c   # FUN_00003c98 reads records 1..2, 8 B
    out = []
    for i in range(1, 3):
        a = base + 8 * i
        out.append({'index': i, 'addr': hx(a), 'raw': ROM[foff(a):foff(a) + 8].hex(),
                    'pulse_ms': u16(a), 'recycle_ms': u16(a + 2), 'switch': u8(a + 4), 'coil': u8(a + 5), 'tag': 'code'})
    return {'table': hx(base), 'records': '1..2 (record 0 empty), 8 B', 'builder': '0x00003c98', 'runtime': 'RAM ptr 0x37258, 0x1c B each',
            'enable': 'FUN_00003e80(i, on) (sling_enable); ball search FUN_00003f88 pulses desc +0x12 ms',
            'behaviour': [
                'Switch closed (no debounce stage) -> counter = pulse+recycle (224), coil on [code]',
                'Coil on for pulse_ms (32), then off; counter holds at recycle while the switch is closed and counts down recycle_ms (192) after it opens before the next shot [code]',
                'Observed 33.5-33.8 ms per hit [observed]',
            ]}, out


def counter_queues():
    base, n, sz = u32(0x36cb4), u32(0x36cb8), u32(0x36cbc)
    out = []
    for i in range(1, n):
        a = base + sz * i
        out.append({'index': i, 'addr': hx(a), 'raw': ROM[foff(a):foff(a) + sz].hex(), 'pending_counter_nvram': hx(u32(a)),
                    'state_ram': hx(u32(a + 4)), 'pulse_ms': u16(a + 0x0e), 'gap_ticks': u16(a + 0x10) >> 4,
                    'gap_raw': u16(a + 0x10), 'coil': u8(a + 0x12), 'tag': 'code'})
    return {'table': hx(base), 'count': n, 'record_size': sz, 'service': 'FUN_0000a844 (task): while the NVRAM counter is non-zero, FUN_00002bc8(coil, pulse_ms, sync=1), decrement, wait gap_raw>>4 ticks',
            'meaning': 'record 1 = knocker (coil 24), record 2 = meter (coil 34) [inferred from the coils]'}, out


def ticket_device():
    a = 0x040f455c
    return {'table': '0x040f4544 (24 B records, record 1 used)', 'addr': hx(a), 'raw': ROM[foff(a):foff(a) + 24].hex(),
            'coil_enable': u8(a + 0x14), 'coil_advance': u8(a + 0x15), 'notch_switch': u8(a + 0x16),
            'init': 'FUN_000104a0', 'irq_service': '0x00012070 loop over 0x040f4548 runtime objects',
            'behaviour': 'while active: enable coil held on; advance coil on while the countdown +0x18 is 0, notch switch (DED #19 = 0x93) edges counted [code]', 'tag': 'code'}


def ball_devices():
    out = []
    kick = {0x0101bbc0: (1, 64, 'FUN_00002b60 queued, sync'), 0x0101bc7c: (2, 64, 'FUN_00002b60 queued, sync'),
            0x0101bdd0: (4, 64, 'FUN_00002e5c on 1 / off 1, sync')}
    for i in range(4):
        a = 0x040e41f4 + 36 * i
        sw = []
        p = u32(a + 8)
        while u8(p) and len(sw) < 8:
            sw.append(u8(p))
            p += 1
        fn = u32(a + 0x0c)
        k = kick.get(fn)
        out.append({'index': i, 'addr': hx(a), 'raw': ROM[foff(a):foff(a) + 36].hex(), 'switches': sw, 'kick_fn': hx(fn) if fn else None,
                    'kick_coil': k[0] if k else None, 'kick_ms': k[1] if k else None, 'kick_how': k[2] if k else None,
                    'u32_10': u32(a + 0x10), 'u32_14': u32(a + 0x14), 'u32_18': u32(a + 0x18), 'byte_20': u8(a + 0x20),
                    'tag': 'code'})
    return {'table': '0x040e41f4 (table-of-tables 0x36d44: 4 x 36 B)', 'note': 'device 0 empty, 1 trough, 2 shooter lane, 3 video game eject; +0x10/+0x14/+0x18 timing fields not decoded'}, out


def coil_groups():
    out = []
    n = u32(0x36cac)
    for g in range(n):
        p = u32(0x040e20c4 + 4 * g)
        cs = []
        while u8(p):
            cs.append(u8(p))
            p += 1
        out.append({'group': g, 'ptr': hx(p - len(cs)), 'coils': cs, 'names': [name_of(c) for c in cs], 'tag': 'code'})
    return {'table': '0x040e20c4 (table-of-tables 0x36ca8: %d x 4 B)' % n, 'note': 'coilgroup_pulse 0x6b24 / coilgroup_pulse_fn 0x6b94 / coilgroup_stop 0x6c0c; also the coil-group field (+8) of each lamp-matrix leff record (stopped at leff end)'}, out


def main():
    regs = {int(r['coil']): r for r in csv.DictReader(open(os.path.join(REPO, 'io', 'coils.csv')))}
    calls = list(csv.DictReader(open(os.path.join(IO, 'coil_calls.csv'))))
    obs = json.load(open(os.path.join(IO, 'coil_observed.json')))['bursts']
    fl_meta, flips = flipper_rules()
    bu_meta, bumps = bumper_rules()
    sl_meta, slings = sling_rules()
    cq_meta, cqs = counter_queues()
    bd_meta, bdevs = ball_devices()
    cg_meta, cgs = coil_groups()

    auto = defaultdict(list)
    for r in flips:
        auto[r['coil']].append('flipper rule %d @%s: button 0x%02x%s, EOS 0x%02x, pulse %d ms, hold %d on/%d off ms (duty %.3f), EOS cut %d ms [code]' % (
            r['index'], r['addr'], r['switch'], ' (alt 0x%02x)' % r['switch_alt'] if r['switch_alt'] != r['switch'] else '', r['eos_switch'], r['pulse_ms'], r['hold_on_ms'], r['hold_off_ms'], r['hold_duty'], r['eos_cut_ms']))
    for r in bumps:
        auto[r['coil']].append('bumper rule %d @%s: switch %d, pulse %d ms (+%d after early release), recycle %d ms, debounce %d ms [code]' % (
            r['index'], r['addr'], r['switch'], r['pulse_ms'], r['extend_ms'], r['recycle_ms'], r['debounce_ms']))
    for r in slings:
        auto[r['coil']].append('sling rule %d @%s: switch %d, pulse %d ms, recycle %d ms [code]' % (r['index'], r['addr'], r['switch'], r['pulse_ms'], r['recycle_ms']))
    for r in cqs:
        auto[r['coil']].append('counter queue %d @%s: %d ms per count, gap %d ticks [code]' % (r['index'], r['addr'], r['pulse_ms'], r['gap_ticks']))
    for r in bdevs:
        if r['kick_coil']:
            auto[r['kick_coil']].append('ball device %d @%s (switches %s): kick %d ms, %s [code]' % (r['index'], r['addr'], r['switches'], r['kick_ms'], r['kick_how']))
    td = ticket_device()
    auto[td['coil_enable']].append('ticket device @%s: enable, held while dispensing [code]' % td['addr'])
    auto[td['coil_advance']].append('ticket device @%s: advance, on until notch switch 0x%02x [code]' % (td['addr'], td['notch_switch']))
    auto[6].append('bank motor object @RAM 0x3b404 (FUN_00018004, init 0x01022544): on until switch 53 (up) / 52 (down) [code]')
    auto[23].append('recognizer motor object @RAM 0x3b47c (FUN_00016c40, init 0x01022f08): on until the next of switches 54/55/56 [code]')
    auto[7].append('post object orbit_post_obj (FUN_01009e94(&orbit_post_obj,7,0x4e,...) 0x00000b04): raise = 64 ms + hold pattern 1/7 for obj+0xc*16 ms (class 0x39908, FUN_00000a78); the alternative class 0x39c00 uses 128 ms + 1/12 (FUN_0100aa48 / 0x0100aa80) [code]')
    auto[3].append('drop bank object tron_drop_bank (drop_bank_init 0x0100af3c, coil 3, switch list 0x040d3d04): reset pulse 64 ms via 0x0100be74 [code; vtable link inferred]')

    gamecalls = defaultdict(list)
    for r in calls:
        cs = [int(r['coil'])] if r['coil'] else [int(x) for x in r['group_coils'].split()] if r['group_coils'] else []
        for c in cs:
            gamecalls[c].append(r)
    obsd = defaultdict(list)
    for b in obs:
        obsd[b['coil']].append(b)

    rows = []
    for n in range(1, NDESC):
        d = read_desc(n)
        assert d['number'] == n, (n, d['number'])
        rg = regs.get(n, {})
        kind, kind_note = KIND.get(n, ('?', ''))
        bits = {('f_%s' % hx(b)): int(bool(d['flags'] & b)) for b, *_ in FLAG_BITS}
        decoded = [nm for b, nm, *_ in FLAG_BITS if d['flags'] & b]
        unknown = d['flags'] & ~KNOWN
        # game call summary
        gc = Counter()
        sites = []
        for r in gamecalls.get(n, []):
            if r['api'] in ('coil_off', 'coil_pulse_stop', 'coilgroup_stop'):
                continue
            if r['api'] in ('coil_pulse_fn', 'coil_drive_pattern', 'coilgroup_pulse_fn'):
                key = '%s %sms pattern %s' % (r['api'], r['ms'] or '?', r['pattern'] or '(var)')
            elif r['api'] == 'coil_drive_onoff':
                key = '%s %sms on %s/off %s' % (r['api'], r['ms'] or '?', r['on_ms'] or '?', r['off_ms'] or '?')
            elif r['api'] == 'coil_on':
                key = 'coil_on (hold)'
            else:
                key = '%s %sms' % (r['api'], r['ms'] or '?')
            gc[key] += 1
            sites.append(r['call_site'])
        ob = obsd.get(n, [])
        firsts = sorted(set(round(b['first_on_ms']) for b in ob if b.get('first_on_ms') is not None))
        tails = sorted(set('%s/%s' % (b['tail_on_ms'], b['tail_period_ms']) for b in ob if b.get('tail_on_ms') and b.get('n_pulses', 0) > 5))
        mp = MPF.get(n)
        if mp is None and kind == 'flasher':
            ms_counts = Counter()
            for r in gamecalls.get(n, []):
                if r['api'] in ('coil_pulse', 'coilgroup_pulse') and r['ms']:
                    ms_counts[int(r['ms'])] += 1
            best = max(ms_counts.items(), key=lambda kv: (kv[1], kv[0]))[0] if ms_counts else 48
            mp = (best, None, None, None, 'flasher: game code pulses %s; test 64 ms' % dict(ms_counts),
                  'most common constant coil_pulse/coilgroup_pulse time for this flasher in coil_calls.csv [code]; observed 48-49 ms for 48 ms calls')
        if mp is None:
            mp = (d['test_ms'] or None, None, None, None, '', 'service test time +0x10 [code]')
        rows.append({
            'coil': n, 'name': name_of(n), 'register': rg.get('register', ''), 'reg_address': rg.get('address', ''), 'bit': rg.get('bit', ''),
            'desc_addr': hx(d['desc_addr']), 'flags_hex': '0x%08x' % d['flags'], 'flags_decoded': ' '.join(decoded) + (' unknown_0x%x' % unknown if unknown else ''),
            **bits,
            'test_pulse_ms': d['test_ms'], 'test_fn': hx(d['test_fn']) if d['test_fn'] else '',
            'test_fn_name': func_name(d['test_fn']) or '' if d['test_fn'] else '',
            'ballsearch_ms': d['ballsearch_ms'], 'ballsearch_fn': hx(d['ballsearch_fn']) if d['ballsearch_fn'] else '',
            'devices_on_driver': d['devices'],
            'wire_color_1': msg(d['wire1']), 'wire_color_1_msg': hx(d['wire1']), 'wire_color_2': msg(d['wire2']), 'wire_color_2_msg': hx(d['wire2']),
            'desc_tag': 'code',
            'kind': kind, 'kind_note': kind_note, 'kind_tag': 'inferred',
            'auto_rules': ' | '.join(auto.get(n, [])),
            'game_calls': '; '.join('%s x%d' % (k, v) for k, v in gc.most_common()),
            'game_call_sites': ' '.join(sites[:20]) + (' ...' if len(sites) > 20 else ''),
            'observed_first_on_ms': ' '.join(str(x) for x in firsts),
            'observed_pwm_on_period_ms': ' '.join(tails),
            'observed_runs': len(ob), 'observed_tag': 'observed' if ob else '',
            'mpf_default_pulse_ms': '' if mp[0] is None else mp[0],
            'mpf_default_hold_power': '' if mp[1] is None else mp[1],
            'mpf_pulse_power': '' if mp[2] is None else mp[2],
            'mpf_recycle_ms': '' if mp[3] is None else mp[3],
            'mpf_note': mp[4], 'mpf_evidence': mp[5], 'mpf_tag': 'inferred (recommendation from the code/observed values in mpf_evidence)',
        })
    for n in range(NDESC, 41):
        # driver slots 36-40 exist (0x28 slots at RAM 0x3b98c, aux byte 4 bits 3-7) but the descriptor table stops at 35
        rows.append({k: '' for k in rows[0]})
        rows[-1].update({'coil': n, 'kind': 'undefined', 'desc_tag': 'code',
                         'kind_note': 'no descriptor: table count 0x24 at RAM 0x36c4c covers coils 0-35; FUN_000029a0 accepts 1-40 and would index past the table (into 0x040e1350)'})
    cols = list(rows[0].keys())
    with open(os.path.join(IO, 'coils.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    rules = {
        'note': 'Automatic coil rules of Tron LE 1.74, decoded from the ROM tables. Times are in coil-service ticks: one tick = 4 IO '
                'interrupts; nominal 1 ms (PinMAME: IO interrupt every 250 us), measured 1.00-1.02 ms in the emulator.',
        'timebase': {'service': 'FUN_00012070 runs every IO interrupt; coil slots, flipper, bumper, sling and device blocks run every 4th (counters 0x37370/0x37380/0x3738c/0x37388/0x37390 reload 4)',
                     'unit_ms_nominal': 1.0, 'unit_ms_observed': '1.00-1.024', 'tag': 'code+observed'},
        'flippers': dict(fl_meta, rules=flips),
        'bumpers': dict(bu_meta, rules=bumps),
        'slingshots': dict(sl_meta, rules=slings),
        'counter_queues': dict(cq_meta, records=cqs),
        'ticket_device': td,
        'ball_devices': dict(bd_meta, devices=bdevs),
        'coil_groups': dict(cg_meta, groups=cgs),
        'motors': [
            {'coil': 6, 'object': 'RAM 0x3b404', 'class_init': 'FUN_00018004 via FUN_010221ec', 'init_call': '0x01022544', 'switches': {'up': 53, 'down': 52},
             'nvram': '0x021117e0', 'tag': 'code'},
            {'coil': 23, 'object': 'RAM 0x3b47c', 'class_init': 'FUN_00016c40 via FUN_010225cc', 'init_call': '0x01022f08', 'position_switches': [54, 55, 56],
             'nvram': '0x021117e4', 'tag': 'code'},
            {'coils': [5, 30, 22], 'what': 'disc: relay 30 on, direction relay 22 on (dir 0) / off (dir 1), power 5 on (or for secs*1000 ms)',
             'code': 'FUN_01006534, task_a8_disc_motor_run 0x010064c4, disc_motor_stop 0x010065ac; disabled by adj 77', 'tag': 'code'},
            {'coil': 8, 'what': 'shaker_run(strength, min_setting) 0x010289b8 -> FUN_01028924: if gf_state & 0x310 == 0 and the slot has less time left, FUN_00002bc8(8, ms, sync=1)',
             'ms_by_strength': {s: u16(0x040d3998 + 4 * s) for s in (1, 2, 3)}, 'table': '0x040d3998', 'gate': 'adj 86 SHAKER MOTOR >= min_setting', 'tag': 'code',
             'observed_ms': {1: 203, 2: 390, 3: 1040}},
        ],
        'ball_search': {
            'task': 'task_ball_search 0x0001f4a0 / FUN_0001f634',
            'order': ['FUN_00003138: every coil 1..35 whose flags & 0xa0dc == 0 (low 16 bits): call desc +0x08 fn, else FUN_00002cb0(coil, desc +0x12 ms, sync=1) -> slings 13, 14 (64 ms)',
                      'FUN_000072c8: flipper rules -> desc +0x12 of the flipper coil (0 = nothing)',
                      'FUN_0001fd48: ball devices (trough is not kicked; shooter 2 and VUK 4 are)',
                      'FUN_00003b68: bumper rules -> FUN_00002cb0(coil, desc +0x12 = 64 ms, sync=1)',
                      'FUN_00004068: sling rules -> desc +0x12 (64 ms) (second sling pulse observed)'],
            'observed': 'deff 11 every ~10 s with the ball idle; pulses 13,14 (64), 9,10,11 (64), 13,14 again, 2 (64), 4 (1/1 x 64), 7 post, 6 motor [observed hw_s2]',
            'tag': 'code+observed'},
        'coil_test': {
            'menu': 'COIL TEST FUN_0103f040, CYCLING COIL TEST FUN_0103eb8c, cycling task FUN_0103f47c; child FUN_0103ead4/0103ef18',
            'pulse': 'desc +0x04 fn if set (coil 5: 0x010067d8 disc motor 1 s each way; coil 6: 0x01022398 bank motor), else FUN_00002cb0(coil, desc +0x10 ms, sync=1)',
            'skips': 'flags 0x800 (coil test), 0x400 (cycling task); flash test lists (flags & 0x1004) == 4',
            'observed': 'injected FUN_00002bc8(coil, desc+0x10, sync=1) for every coil: 64.0-64.5 ms (shaker 1000 ms), start 1-24 ms after the call (zero-cross sync) [observed hw_s2]',
            'tag': 'code+observed'},
        'zero_cross_sync': {
            'what': 'A drive call with sync=1 leaves slot +0x25 = 0; the slot starts only when the zero-cross input (bit 2 of *(RAM 0x37350)) has just gone high (DAT_0003c9ac != 0 and the ms-since-edge counter 0x3c9a8 == slot +0x24 = 0). Sync is only used once 0x37310 is set (edge count per second stable within +-3 for 3 s; 60/s in the emulator).',
            'tag': 'code+observed'},
    }
    json.dump(rules, open(os.path.join(IO, 'coil_rules.json'), 'w'), indent=1)
    print('coils.csv', len(rows), 'rows; coil_rules.json written')


if __name__ == '__main__':
    main()
