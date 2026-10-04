"""Lamp-matrix effects (leffs): table, classification, code-drawn leffs, and the rule registrations.

Writes rom_data/io/leff_table.csv, code_leffs.json, code_leffs.md and lamp_rules.csv.
Run: PYTHONPATH=rom_data/tools python3 rom_data/tools/hw_leffs.py

Leff record (table 0x040e23e4, table-of-tables RAM 0x36cf0 = {table, 172, 12}; record 0 unused):
  +0 fn, +4 u16 flags, +6 u16 lamp group, +8 u16 coil group, +0xa u8 priority  (leff_start 0x87ac)
The per-leff facts that can be read automatically (lamps, groups, coils, sleeps, RAM, GI calls) come from
the BL/B instructions of the leff function and every game function it calls or spawns (resolved with
hw_common.resolve_call_args). The behaviour text and pseudo-code for code-drawn leffs is hand-written
from the decompile/disassembly of the function named in each entry (tag code unless marked inferred).
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rom import u8, u16, u32, hx, find_bl_callers
from hw_common import resolve_call_args, func_of, func_name, funcs, insns, decomp_body, REPO
from hw_lamps import NAMES as GROUP_NAMES, members as group_members, lamp_names

OUT = os.path.join(REPO, 'rom_data', 'io')
LT, LN, LS = u32(0x36cf0), u32(0x36cf4), u32(0x36cf8)
CGT = 0x040e20c4
TICK_MS = 16.26

# ---------------------------------------------------------------- API used by leff code
LAMP_API = {0x833c: 'lamp_on', 0x81f8: 'lamp_off', 0x8478: 'lamp_toggle', 0x83b0: 'lamp_bit_set',
            0x826c: 'lamp_bit_clear', 0x8548: 'lamp_test', 0x85f4: 'lamp_bit_test', 0x84f8: 'lamp_bit_toggle'}
GROUP_API = {0x8f78: 'lampgroup_count', 0x8fdc: 'lampgroup_member', 0x9068: 'lampgroup_off',
             0x90d8: 'lampgroup_bit_clear', 0x9200: 'lampgroup_on', 0x9270: 'lampgroup_bit_set',
             0x9398: 'lampgroup_toggle', 0x9408: 'lampgroup_bit_toggle', 0x987c: 'lampgroup_rotate',
             0x9588: 'lampgroup_rotate_b', 0x9b9c: 'lampgroup_fill_rev', 0x9d00: 'lampgroup_fill',
             0x9e54: 'lampgroup_drain_rev', 0x9fb8: 'lampgroup_drain', 0x7d9c: 'lamp_layer_create'}
COIL_API = {0x6970: 'coil_pulse', 0x69c0: 'coil_pulse_fn', 0x2bc8: 'coil_drive_pulse'}
CGROUP_API = {0x6b24: 'coilgroup_pulse', 0x6b94: 'coilgroup_pulse_fn', 0x6a74: 'coilgroup_count',
              0x6ad8: 'coilgroup_member'}
GI_API = {0xc9dc: 'gi_claim (by leff priority)', 0xc988: 'gi_claim (if free)', 0xcaf8: 'gi_off', 0xcb24: 'gi_on'}
SLEEP = 0xb91c
SPAWN = 0xb840
LEFF_START, LEFF_STOP = 0x87ac, 0xc404
OTHER_STATE = {0xbe68: 'task_running', 0x2818c: 'deff_running', 0x1f2b0: 'playfield_is_valid',
               0x21360: 'current_player'}

# RAM the leffs read, with meaning (tag code unless stated); names from rules/work/ram/*.tsv where known
RAM_EXTRA = {
    0x372c0: ('current_task', 'current task block; leffs read their parameter at task+0x30'),
    0x3c224: ('leff_layer_image', 'the shared leff layer image claimed by leff_start for the leff table lamp group'),
    0x3c238: ('leff_layer_mask', 'mask of the shared leff layer'),
    0x3b134: ('flasher_step_counter', 'loop counter of the flasher-chase tails (deterministic, shared scratch)'),
    0x36f62: ('gf_shoot_again_lamp', 'lamp number of SHOOT AGAIN; ROM-initialised to 26 (file 0x36f62)'),
    0x36f64: ('start_button_lamp', 'lamp number of the START button; ROM-initialised to 65 (file 0x36f64)'),
    0x36f65: ('tournament_button_lamp', 'lamp number of the TOURNAMENT START button; ROM-initialised to 66'),
    0x3908c: ('extra_button_lamp', 'a lamp number left visible by the attract/tilt layers; 0 at power-up '
                                   '(file 0x3908c), set at run time (inferred: a third button lamp)'),
    0x3d4b8: ('ball_save_like_timer', 'u32 tick counter passed to leff 13 as task+0x30 (inferred: remaining time)'),
}

FLAG_BITS = {
    0x1: 'task flag 0x100 instead of 0x2000 (with bit 0x4 clear); set on every background/mode leff (inferred: '
         'survives end-of-ball wait, see 0x2000)',
    0x2: 'can be replaced by a leff of EQUAL priority (leff_start conflict test: equal priority wins only when '
         'the running leff has this bit)',
    0x4: 'task flags 0 (neither 0x100 nor 0x2000)',
}


def flag_task_bits(fl):
    t = 0x22
    if not fl & 4:
        t |= 0x100 if fl & 1 else 0x2000
    return t


def load_ram_names():
    d = {}
    rd = os.path.join(REPO, 'rules', 'work', 'ram')
    for fn in sorted(os.listdir(rd)):
        if not fn.endswith('.tsv') or fn.endswith('_functions.tsv'):
            continue
        for line in open(os.path.join(rd, fn)):
            p = line.rstrip('\n').split('\t')
            if len(p) >= 5 and p[0].startswith('0x'):
                try:
                    d.setdefault(int(p[0], 16), (p[1], p[4]))
                except ValueError:
                    pass
    return d


# ---------------------------------------------------------------- code walking
_starts = None
_entries = None
_entry_sorted = None


def _entry_points():
    """addresses that are real function entries: BL/B targets with link, task_spawn/leff literals"""
    import struct
    from rom import ROM
    out = set()
    for base, lo, hi in ((0, 0, 0x36000), (0x01000000, 0x40000, 0x140000)):
        for o in range(lo, min(hi, len(ROM)), 4):
            w = struct.unpack_from('<I', ROM, o)[0]
            if (w >> 24) & 0x0f == 0x0b and w >> 28 != 0xf:     # BL (any condition)
                off = w & 0xffffff
                if off & 0x800000:
                    off -= 0x1000000
                out.add(base + (o - lo) + 8 + 4 * off)
    # function pointers stored as data (leff/deff tables, task_create/spawn literals, vtables): only
    # values that are a decompile header (random data words would otherwise cut functions), plus the leff fns
    words = set(struct.unpack_from('<%dI' % (0x140000 // 4), ROM, 0))
    out |= words & set(a for a, _ in funcs())
    out |= set(u32(LT + 12 * i) for i in range(1, LN))
    # literal-pool pointers into game code (task_create / spawn targets): values of the words that an
    # 'ldr rX, [pc, #imm]' (encoding 0x051f0000 / 0x059f0000) loads
    for lo, n in ((0, 0x36000), (0x40000, 0x100000)):
        ws = struct.unpack_from('<%dI' % (n // 4), ROM, lo)
        for k, w in enumerate(ws):
            if w & 0x0f7f0000 == 0x051f0000:
                o = lo + 4 * k + 8 + ((w & 0xfff) if w & 0x00800000 else -(w & 0xfff))
                if lo <= o < lo + n - 3 and o % 4 == 0:
                    v = struct.unpack_from('<I', ROM, o)[0]
                    if 0x01000000 <= v < 0x01100000 or v < 0x36000:
                        out.add(v)
    return set(x for x in out if x % 4 == 0)


def _ends_before(a, h):
    """True when the code in [a, h) cannot fall through into h: the word at h-4 is a literal used by
    an ldr in [a, h) or an unconditional return/branch"""
    lits = set()
    last = None
    for ins in insns(a, h):
        if ins.insn_name().startswith('ldr') and '[pc, #' in ins.op_str:
            lits.add(ins.address + 8 + int(ins.op_str.split('#')[-1].rstrip(']'), 16))
        if ins.address == h - 4:
            last = ins
    if h - 4 in lits or last is None:
        return True
    from capstone import arm as A
    al = last.cc in (A.ARM_CC_AL, A.ARM_CC_INVALID)
    n, o = last.insn_name(), last.op_str
    return al and (n == 'b' or (n == 'bx' and o == 'lr') or (n == 'mov' and o.startswith('pc')) or
                   (n in ('pop', 'ldm') and 'pc' in o))


def fn_extent(a):
    """[a, end): a Ghidra header that is not a call/data target and that the code falls through into is a
    split of the same function, so it is skipped"""
    global _starts, _entries
    if _starts is None:
        _starts = sorted(x for x, _ in funcs())
        _entries = _entry_points()
    import bisect
    i = bisect.bisect_right(_starts, a)
    while i < len(_starts) and _starts[i] not in _entries and _starts[i] - a < 0x800 and not _ends_before(a, _starts[i]):
        i += 1
    end = _starts[i] if i < len(_starts) else a + 0x400
    # functions without a decompile header (some OS-space leffs) end at the next entry point
    global _entry_sorted
    if _entry_sorted is None:
        _entry_sorted = sorted(x for x in _entries if x < 0x36000 or 0x01000000 <= x < 0x01100000)
    j = bisect.bisect_right(_entry_sorted, a)
    if j < len(_entry_sorted):
        end = min(end, _entry_sorted[j])
    return a, min(end, a + 0x800)


def calls_in(fstart):
    """[(pc, target, kind)] for BL and for B leaving the function (tail call)"""
    lo, hi = fn_extent(fstart)
    out = []
    for ins in insns(lo, hi):
        if ins.mnemonic in ('bl', 'b') and ins.op_str.startswith('#'):
            t = int(ins.op_str[1:], 16)
            if ins.mnemonic == 'bl' or not (lo <= t < hi):
                out.append((ins.address, t, ins.mnemonic))
    return out


def lits_in(fstart):
    lo, hi = fn_extent(fstart)
    out = set()
    for ins in insns(lo, hi):
        if ins.mnemonic.startswith('ldr') and '[pc, #' in ins.op_str:
            d = int(ins.op_str.split('#')[-1].rstrip(']'), 16)
            out.add(u32(ins.address + 8 + d))
    return out


SKIP_NAMES = re.compile(r'^(tube_show|snd_|deff_|anim_|shaker_|score_|audit_)')


def walk(fn):
    """the leff function, its direct game-code helpers (one level), and the tasks it spawns (recursively)"""
    seen, todo = [], [(fn, 0)]
    while todo:
        a, depth = todo.pop(0)
        if a in seen:
            continue
        seen.append(a)
        for pc, t, k in calls_in(a):
            if t == SPAWN:
                regs, _, _ = resolve_call_args(pc, nstack=0, start=a)
                if regs.get(0):
                    todo.append((regs[0], 0))
            elif t >= 0x01000000 and depth == 0 and not SKIP_NAMES.match(func_name(t) or ''):
                todo.append((t, 1))
    return seen


def features(fn):
    fs = walk(fn)
    f = {'functions': [hx(a) for a in fs], 'lamps': set(), 'groups': set(), 'coils': set(), 'coil_groups': set(),
         'sleeps': [], 'gi': [], 'ram': set(), 'tables': set(), 'spawns': [], 'state_calls': set(),
         'leff_start': set(), 'reads_param': False, 'unresolved': []}
    for a in fs:
        for pc, t, k in calls_in(a):
            if t in LAMP_API or t in GROUP_API or t in COIL_API or t in CGROUP_API or t in (SLEEP, SPAWN, LEFF_START):
                regs, _, _ = resolve_call_args(pc, nstack=0, start=a)
                r0 = regs.get(0)
                if t in LAMP_API:
                    (f['lamps'].add(r0 & 0xff) if r0 is not None else f['unresolved'].append('%s %s lamp' % (hx(pc), LAMP_API[t])))
                elif t in GROUP_API:
                    if r0 is not None and (r0 & 0xffff):
                        f['groups'].add(r0 & 0xffff)
                    elif r0 is None:
                        f['unresolved'].append('%s %s group' % (hx(pc), GROUP_API[t]))
                elif t in COIL_API:
                    (f['coils'].add(r0 & 0xff) if r0 is not None else f['unresolved'].append('%s %s coil' % (hx(pc), COIL_API[t])))
                elif t in CGROUP_API:
                    if r0 is not None:
                        f['coil_groups'].add(r0 & 0xffff)
                elif t == SLEEP:
                    f['sleeps'].append(r0 if r0 is not None else 'var')
                elif t == SPAWN:
                    f['spawns'].append(hx(r0) if r0 is not None else 'var')
                elif t == LEFF_START:
                    f['leff_start'].add(r0)
            elif t in GI_API:
                f['gi'].append(GI_API[t])
            elif t in OTHER_STATE:
                f['state_calls'].add(OTHER_STATE[t])
        for v in lits_in(a):
            if 0x36000 <= v < 0x40000 or 0x02100000 <= v < 0x02120000:
                f['ram'].add(v)
            elif 0x040d0000 <= v < 0x040f0000:
                f['tables'].add(v)
        b = decomp_body(a) or ''
        if re.search(r'\(DAT_000372c0 \+ 0x30\)', b):
            f['reads_param'] = True
    if 0x372c0 in f['ram']:
        f['ram'].discard(0x372c0)
    return f


# ---------------------------------------------------------------- leff_start call sites (+ parameter)
REGNO = dict({'r%d' % i: i for i in range(13)}, sb=9, sl=10, fp=11, ip=12, sp=13, lr=14, pc=15)


def leff_start_sites():
    """[(pc, caller, leff_id or None, param or None/'var')]: param = value stored to task+0x30 right after"""
    out = []
    for pc, link in sorted(find_bl_callers(LEFF_START)):
        regs, _, _ = resolve_call_args(pc, nstack=0)
        lid = regs.get(0)
        param = None
        alias = {0}
        consts = {}
        for ins in insns(pc + 4, pc + 4 + 4 * 14):
            m, ops = ins.insn_name(), ins.op_str  # base mnemonic without condition code
            if m in ('bl', 'b', 'bx', 'pop') or m.startswith('ldm'):
                break
            R = r'(r\d+|sb|sl|fp|ip|lr)'
            mm = re.match(r'(movs?|subs) %s, %s(?:, #0)?$' % (R, R), m + ' ' + ops)
            if mm and REGNO[mm.group(3)] in alias:
                alias.add(REGNO[mm.group(2)])
                continue
            mm = re.match(r'(?:mov|mvn)\w* %s, #(0x[0-9a-f]+|\d+)$' % R, m + ' ' + ops)
            if mm:
                consts[REGNO[mm.group(1)]] = int(mm.group(2), 0)
                continue
            if m.startswith('ldr') and '[pc, #' in ops:
                d = int(ops.split('#')[-1].rstrip(']'), 16)
                consts[REGNO.get(ops.split(',')[0], -1)] = u32(ins.address + 8 + d)
                continue
            mm = re.match(r'str[hb]? %s, \[%s, #0x30\]' % (R, R), m + ' ' + ops)
            if mm and REGNO[mm.group(2)] in alias:
                param = consts.get(REGNO[mm.group(1)], 'var')
                break
        out.append((pc, func_of(pc), lid, param))
    return out


def rule_sites():
    rows = []
    for api, kind in ((0x19740, 'leff_rule'), (0x1982c, 'deff_rule')):
        ns = 3 if kind == 'leff_rule' else 5
        for pc, link in sorted(find_bl_callers(api)):
            regs, st, _ = resolve_call_args(pc, nstack=ns)
            rows.append((kind, pc, func_of(pc), regs, st))
    return rows


def cond_summary(addr):
    if addr is None:
        return '', ''
    name = func_name(addr) or ''
    b = decomp_body(addr)
    if not b:
        # LAB_ targets: short disassembly summary of the calls it makes
        cs = []
        for ins in insns(addr, addr + 0x40):
            if ins.mnemonic in ('bl', 'b') and ins.op_str.startswith('#'):
                t = int(ins.op_str[1:], 16)
                cs.append(func_name(t) or hx(t))
            if ins.mnemonic in ('bx',) or (ins.mnemonic == 'mov' and ins.op_str == 'pc, lr') or \
                    (ins.mnemonic.startswith('pop') and 'pc' in ins.op_str) or (ins.mnemonic.startswith('ldm') and 'pc' in ins.op_str):
                break
        return name or 'LAB_%08x' % addr, 'asm: calls ' + ', '.join(cs) if cs else 'asm: returns a constant/flag test'
    body = b.split('{', 1)[1] if '{' in b else b
    body = re.sub(r'\n\s*[A-Za-z_][\w ]*\*? ?[\w*]+(\[\d+\])?;', '', body)
    body = re.sub(r'\s+', ' ', body).strip().rstrip('}').strip()
    return name, body[:400]


# ---------------------------------------------------------------- hand-written behaviour of code-drawn leffs
P = 'task+0x30'
CODE = {
    # ---- parametric: lamp / group passed by the caller in the task block
    0x1015d40: dict(kind='parametric', what='blink one lamp given by the caller: 10 toggles, 2 ticks each (5 flashes, 20 ticks)',
                    param='task+0x30 u8 = lamp number', pseudo=[
                        'layer = lamp_layer_create(0, leff priority)', 'L = task+0x30 (byte)', 'mask L',
                        'repeat 10: toggle L; sleep 2', 'exit (layer freed with the task)'], exit='after 10 toggles'),
    0x1015ce8: dict(kind='parametric', what='one lamp ON for 8 ticks', param='task+0x30 u8 = lamp number',
                    pseudo=['layer = lamp_layer_create(0, prio)', 'L = task+0x30', 'mask L; L on', 'sleep 8; exit'], exit='after 8 ticks'),
    0x1015da4: dict(kind='parametric', what='one lamp forced OFF for 8 ticks', param='task+0x30 u8 = lamp number',
                    pseudo=['layer = lamp_layer_create(0, prio)', 'L = task+0x30', 'mask L; L off', 'sleep 8; exit'], exit='after 8 ticks'),
    0x1015dfc: dict(kind='parametric', what='blink a lamp group given by the caller: 24 toggles, 2 ticks each (12 flashes, 48 ticks)',
                    param='task+0x30 u16 = lamp group', pseudo=[
                        'G = task+0x30 (u16)', 'layer = lamp_layer_create(G, prio)  # owns G',
                        'repeat 24: toggle G; sleep 2', 'exit'], exit='after 24 toggles'),
    0x1033de4: dict(kind='parametric', what='flash the leff coil group twice and blink one lamp (10 toggles @2 ticks)',
                    param='task+0x30 u8 = lamp number; the child gets the coil group (leff table +8) in its own task+0x30',
                    pseudo=['child = spawn 0x01033da8 with child+0x30 = leff coil group',
                            '  child: repeat 2: coilgroup_pulse(group, 32 ms); sleep 5',
                            'layer = lamp_layer_create(0, prio); L = task+0x30; mask L',
                            'repeat 10: toggle L; sleep 2'], exit='after 10 toggles'),
    0x1031e28: dict(kind='parametric', what='flash the leff coil group once (32 ms) and blink one lamp (10 toggles @2 ticks)',
                    param='task+0x30 u8 = lamp number', pseudo=[
                        'coilgroup_pulse(leff coil group, 32 ms)', 'layer = lamp_layer_create(0, prio); L = task+0x30; mask L',
                        'repeat 10: toggle L; sleep 2'], exit='after 10 toggles'),
    0x1019588: dict(kind='parametric', what='GI-off lamp show; the parameter picks the flasher child',
                    param='task+0x30 u16: < 2 -> children 0x010194a0 + 0x010194fc, else child 0x01019580',
                    pseudo=['if task+0x30 < 2: spawn 0x010194a0, spawn 0x010194fc (flasher 28: 5 pattern pulses then 41 x 64 ms @8)',
                            'else: spawn 0x01019580', 'gi_claim; gi_off',
                            'layer = lamp_layer_create(group 38, prio); invert mask  # owns every lamp except group 38',
                            'for i in 0..120: if i == 65: gi_on; toggle group 39; sleep 3'], exit='after 121 x 3 ticks'),
    0x102114c: dict(kind='parametric', what='coil group (leff +8) pattern run plus a child that blinks the caller\'s lamp',
                    param='task+0x30 u8 = lamp number, read by the child leff_038 code (task_spawn_child copies task+0x30..+0x47 to the child)',
                    pseudo=['spawn leff_038 code (0x01015d40): blink lamp task+0x30, 10 toggles @2 ticks',
                            'g = leff coil group; for i in 0..16: coilgroup_pulse_fn(g, 100 ms, table 0x040d32dc[i]); sleep 2'],
                    exit='after 17 x 2 ticks'),
    0x1042578: dict(kind='service', what='lamp test, single lamp: every other lamp masked off, the lamp toggles every 8 ticks',
                    param='task+0x30 u8 = lamp number', pseudo=['layer = lamp_layer_create(0, 254); mask all lamps (image all off)',
                                                                 'L = task+0x30', 'forever: toggle L; sleep 8'], exit='until stopped'),
    0x1042ab8: dict(kind='service', what='lamp test, single lamp (same code shape as leff 3)',
                    param='task+0x30 u8 = lamp number', pseudo=['layer = lamp_layer_create(0, 254); mask all lamps',
                                                                 'L = task+0x30', 'forever: toggle L; sleep 8'], exit='until stopped'),
    0x1042f3c: dict(kind='service', what='lamp test, one matrix column: lamps (c-1)*8+1 .. c*8 toggle every 8 ticks',
                    param='task+0x30 u8 = column c (helpers 0x01042f0c / 0x01042f24 / 0x01042f30)',
                    pseudo=['layer = lamp_layer_create(0, 254); mask all lamps', 'c = task+0x30',
                            'forever: for L in first(c)..last(c): toggle L; sleep 8'], exit='until stopped'),
    0x1042160: dict(kind='service', what='lamp test, one matrix row: lamps r, r+8, r+16 ... toggle every 8 ticks',
                    param='task+0x30 u8 = row r (helpers 0x010420cc / 0x0104210c / 0x01042154)',
                    pseudo=['layer = lamp_layer_create(0, 254); mask all lamps', 'r = task+0x30',
                            'forever: for L in r, r+8, ... : toggle L; sleep 8'], exit='until stopped'),
    # ---- state-drawn
    0x2fd60: dict(kind='state', what='SHOOT AGAIN lamp blinks faster as a timer runs down',
                  param='task+0x30 = pointer to a u32 tick counter (leff_start site 0x0001ea60.. stores &0x3d4b8)',
                  ram=[0x36f62, 0x3d4b8], pseudo=[
                      'L = gf_shoot_again_lamp (0x36f62); if L == 0: exit', 'layer = lamp_layer_create(0, 0x81); mask L',
                      'p = task+0x30 (pointer)', 'forever: toggle L; t = (*p < 312) ? *p / 31 : 10; sleep max(t, 2)'],
                  exit='until stopped'),
    0x2fe1c: dict(kind='state', what='ball-save SHOOT AGAIN blink: waits for a valid playfield, then blinks faster as the ball-save time runs down',
                  param='task+0x30 = pointer to the ball_save_task local tick counter (set at 0x00019a20 ball_save_task)',
                  ram=[0x36f62], pseudo=[
                      'L = gf_shoot_again_lamp; if L == 0: exit', 'layer = lamp_layer_create(0, 0x80)',
                      'while not FUN_00023638() and not playfield_is_valid(): sleep 2', 'mask L; p = task+0x30',
                      'while task_running(0x31 ball_save_task): toggle L; t = (*p < 312) ? *p / 31 : 10; sleep max(t, 2)'],
                  exit='when ball_save_task (id 0x31) ends'),
    0x10014cc: dict(kind='state', what='bonus count: the 9 bonus-item lamps show which items were collected; GI off',
                    ram=[], pseudo=['layer = lamp_layer_create(group 108, prio); invert mask',
                                    'for i in 0..8: L = FUN_01015f60(i) (item lamp, table 0x040d2dd0);'
                                    ' if bonus_insert_mask & bonus_item_mask(i) == 0: lamp on (mask set) else mask clear',
                                    'gi_claim; gi_off', 'repeat 121: sleep 3'], exit='after 121 x 3 ticks',
                    note='bonus_insert_mask / bonus_item_mask: see rules/work/ram/bonus.tsv'),
    0x1008208: dict(kind='state', what='disc multiball shot lamps: groups of the lit shots blink (3 ticks), others released',
                    ram=[0x3af08], pseudo=['layer = lamp_layer_create(0, prio) (retry every 6 ticks)', 'on = true',
                                           'forever: for rec in table 0x040d26c0 (8 x {u16 mask, u16 group, ..}, 10 bytes):',
                                           '  if dmb_lit_mask & rec.mask: mask rec.group; group on if on else off',
                                           '  else: unmask rec.group', '  sleep 3; on = !on'], exit='until stopped (rule)'),
    0x1005658: dict(kind='conditional', what='End of Line disc flasher: pulses flasher 31 (even eol_level) or 32 (odd) for 32 ms every 8 ticks',
                    ram=[0x3adf4], pseudo=['forever: if playfield_is_valid() and not task_running(0x2b ball search):',
                                           '  coil_pulse(eol_level & 1 ? 32 : 31, 32 ms)', '  sleep 8'], exit='until stopped (rule)'),
    0x101f0f4: dict(kind='state', what='Quorra lamps blink; fast (2 ticks) while the double window runs, else 12 ticks',
                    ram=[0x3b37c], pseudo=['layer = lamp_layer_create(0, prio)', 'forever: t = quorra_double_secs ? 2 : 12',
                                           '  mask lamps 60, 64, 57; toggle group 37; sleep t'], exit='until stopped'),
    0x1006660: dict(kind='state', what='disc flasher: flasher 32 while any multiball runs, else flasher 31; 64 ms every 12 ticks',
                    ram=[], pseudo=['forever: c = any_multiball_running() ? 32 : 31 (FUN_01006648); coil_pulse(c, 64 ms); sleep 12'],
                    exit='until stopped (leff rule 0x01006610 leff76_disc_flasher_cond)'),
    0x10028ec: dict(kind='state', what='CLU hurry-up shot lamps: the 4 shot groups blink when lit in clu_shots, else off',
                    ram=[0x3acfc], pseudo=['layer = lamp_layer_create(0, prio); mask the 4 groups of table 0x040d22dc',
                                           'forever: for i in 0..3: if clu_shots & table[i].mask: toggle table[i].group else group off',
                                           '  sleep 3'], exit='until stopped (rule)'),
    0x101aff0: dict(kind='state', what='Light Cycle multiball chain lamps: three children draw the A/B/C chain shot lamps',
                    ram=[0x3b280, 0x3b288, 0x3b294, 0x3b29c, 0x3b2a8, 0x3b2b0],
                    pseudo=['spawn lc_leff_chain_a_lamps / _b_ / _c_ (0x0101ac84 / 0x0101ada8 / 0x0101aecc); forever sleep 8',
                            'each child: layer = lamp_layer_create(group 40, prio+2)',
                            '  forever: for i in 0..5 (table 0x040d3104: {mask, lamp}): if lit_mask & mask: mask lamp; on/off by phase',
                            '           else unmask lamp',
                            '    if task_running(0xba/0xbc/0xbe): t = timer < 312 ? timer/31 : 10; sleep max(t,2) else sleep 6; flip phase'],
                    exit='until stopped'),
    0x1020ff8: dict(kind='state', what='Recognizer target lamps for the current player: disabled targets solid, the lit (double) target blinks, the previous lit target plane 1 only, others off',
                    ram=[0x21117b7, 0x3b3f8, 0x3b3fc], pseudo=[
                        'layer = lamp_layer_create(0, prio); mask group 52', 'blink = true',
                        'forever: seen = 0; for i in 0..3 (table 0x040d32b4: {u8 bit, .., .., u8 lamp}):',
                        '  if bit & seen: continue',
                        '  if rec_targets_disabled_mask[current_player] (byte 0x21117b7 + player, player 1-4) & bit: lamp on (solid)',
                        '  elif bit == table[rec_lit_pos].bit: lamp on if blink else off',
                        '  elif bit == table[rec_prev_pos].bit: lamp plane 2 off, plane 1 on',
                        '  else lamp off', '  seen |= bit', 'sleep 3; blink = !blink'], exit='until stopped'),
    0x1032028: dict(kind='state', what='Zuse fast scoring target lamps: unhit targets blink (5 ticks), hit targets off',
                    ram=[0x3b8e8], pseudo=['layer = lamp_layer_create(0, prio)', 'forever: for i in 0..3 (table 0x040d6ef0, 8 bytes: u16 mask @0, lamp @5):',
                                           '  mask lamp; if zfs_targets & mask: off else on/off by phase', '  sleep 5; flip phase'],
                    exit='until stopped'),
    0x1026f74: dict(kind='state', what='Sea of Simulation: runs the per-stage lamp child from table 0x040d37d8 (9 x 0x28 bytes, fn at +0x10) and restarts when the stage changes',
                    ram=[0x3b628], pseudo=['layer = lamp_layer_create(group 76, prio)', 's = sos_stage',
                                           'rec = 0x040d37d8 + s*0x28 (FUN_0102635c); if rec.fn(+0x10): spawn rec.fn',
                                           'wait (sleep 1) until sos_stage != s; task_exit (the rule restarts the leff)'],
                    exit='when sos_stage changes'),
    0x100da04: dict(kind='state', what='Flynn\'s arcade roving arrow: only the group at position ff_pos is shown (on)',
                    ram=[0x3af9c], pseudo=['layer = lamp_layer_create(0, prio)', 'forever: p = ff_pos',
                                           '  for i in 0..5 (table 0x040d294c, 8 bytes, u16 group): if i == p: mask group; group on else unmask group',
                                           '  sleep 3'], exit='until stopped'),
    0x1003a74: dict(kind='state', what='combo arrows: lit combo shots blink, rate from combo_timer while the combo window (task 0xcd) runs',
                    ram=[0x3ad58, 0x3ad5c, 0x3ad60], pseudo=[
                        'layer = lamp_layer_create(0, prio); blink = true',
                        'forever: starters = combo_starters != 0; window = task_running(0xcd)',
                        '  for i in 0..5 (table 0x040d2324, 6 bytes: u32 mask, u16 group):',
                        '    if window and combo_lit & mask: mask group; on if blink else off',
                        '    elif window or starters: unmask group (combo_starters & mask with no window also unmasks)',
                        '  sleep window ? max(2, combo_timer < 312 ? combo_timer/31 : 10) : 6; blink = !blink'],
                    exit='until stopped (leff rule 0x01003bf0)'),
    0x1030198: dict(kind='state', what='Portal multiball shot lamps by phase: 0 = per-shot progress bars (count from RAM via table pointers), 1 = group 95 drains/fills, 2 = all shot groups blink',
                    ram=[0x3b878], pseudo=[
                        'layer = lamp_layer_create(0, prio); blink = true',
                        'forever: if pm_phase == 1: unmask the 7 groups of table 0x040d6e18; mask group 95;',
                        '            drain group 95 one lamp per 8 ticks until empty, then fill one per 8 ticks until full',
                        '  elif pm_phase == 0: mask+on group 95; for each of 7 records {u16 group, u8* count}:',
                        '            n = *count; lamps [0..n) on, lamp n blinks, the rest off',
                        '  elif pm_phase == 2: mask+on group 95; every record group on/off with blink',
                        '  sleep 3; blink = !blink'], exit='until stopped'),
    0x101cb28: dict(kind='random', what='one random coil of coil group 1 pulsed 32 ms (FUN_0000c6b4 = random(n), through the 6-slot limiter)',
                    pseudo=['n = coilgroup_count(1); c = coilgroup_member(1, random(n)); limiter slot = coil_drive_pulse(c, 32 ms)'],
                    exit='immediately'),
    0x1017dbc: dict(kind='state', what='attract lamp show (captured as lampfx_001); leaves the start-button lamps out of its layer',
                    ram=[0x3908c, 0x36f64, 0x36f65], pseudo=[
                        'layer = lamp_layer_create(0, 1); mask all lamps; unmask lamps in 0x3908c, 0x36f64 (65), 0x36f65 (66)',
                        'fill the 15 groups of table 0x040d2f00 one step at a time; spawn leff_001_chase_task (rotates the 15 groups every 5 ticks)',
                        '30 x sleep 62; then group_flash_task: 3 x 8 groups of 0x040d2f38 flash 16 x (3 on/3 off) with tube shows of 0x040d2f3a',
                        'blink cycles: blink time 24 -> 4, then 10 x 4, then 5 x 12'], exit='loops (attract)',
                    note='Deterministic apart from the lamp numbers in RAM; the exported show is usable if the start lamps are left to their own rule.'),
    0x100f430: dict(kind='state', what='tilt/flasher show with GI off: every lamp masked off except the start-button lamps, flashers of coil group 1 chase 512 steps',
                    ram=[0x3908c, 0x36f64, 0x36f65], pseudo=[
                        'layer = lamp_layer_create(0, prio); mask all lamps (all off); unmask 0x3908c, 0x36f64, 0x36f65',
                        'gi_claim; gi_off', 'repeat 512: 2 flashers of coil group (leff +8) 64 ms, next index; sleep 7'],
                    exit='after 512 x 7 ticks', note='Deterministic apart from the button lamps; exported show is usable.'),
    # ---- conditional: deterministic pattern that only runs while a condition holds
    0x100791c: dict(kind='conditional', what='flashers 26+27 pattern loop (14-step table 0x040d2760, 100 ms patterns) while the playfield is valid and no ball search',
                    pseudo=['i = 0; forever: if playfield_is_valid() and not task_running(0x2b):',
                            '  p = table[i++]; coil_pulse_fn(26, 100, p); coil_pulse_fn(27, 100, p); if i > 13: i = 0', 'else i = 0', 'sleep 4'],
                    exit='until stopped'),
    0x10051c4: dict(kind='conditional', what='flasher pattern loop from table 0x040d25c0 while the playfield is valid and no ball search',
                    pseudo=['same shape as leff 43 with table 0x040d25c0, sleep 6'], exit='until stopped'),
    0x100c748: dict(kind='conditional', what='flashers 20+21 pattern loop (14-step table 0x040d2890, 100 ms) while the playfield is valid and no ball search',
                    pseudo=['same shape as leff 43: coil_pulse_fn(20/21, 100, table[i]); sleep 4'], exit='until stopped'),
    0x1026814: dict(kind='conditional', what='flashers 17 and 18 run the 16-step table 0x040d3940 half a cycle apart (200 ms patterns) while the playfield is valid and no ball search',
                    pseudo=['a = 0; b = 8; forever: if valid and no ball search: coil_pulse_fn(17, 200, t[a++]); coil_pulse_fn(18, 200, t[b++]) (wrap at 16)',
                            'else a = 0; b = 8', 'sleep 6'], exit='until stopped'),
    0x1003e40: dict(kind='conditional', what='coil group (leff +8) pattern loop, 16-step table 0x040d248c, 200 ms, while valid and no ball search',
                    pseudo=['g = leff coil group; i = 0; forever: if valid and no ball search: coilgroup_pulse_fn(g, 200, t[i++]) (wrap 16) else i = 0; sleep 6'],
                    exit='until stopped'),
    0x10321b4: dict(kind='conditional', what='coil group (leff +8) chase, 14-step table 0x040d6f18, 150 ms; pauses while the playfield is not valid or ball search runs',
                    pseudo=['g = leff coil group; forever: wait (sleep 4) until valid and no ball search;',
                            '  for i in 0..13: coilgroup_pulse_fn(g, 150, t[i]); sleep 4'], exit='until stopped'),
    0x10083ec: dict(kind='conditional', what='coil group (leff +8) pulsed 32 ms every 8 ticks while valid and no ball search',
                    pseudo=['g = leff coil group; forever: if valid and no ball search: coilgroup_pulse(g, 32 ms); sleep 8'], exit='until stopped'),
    0x2ff44: dict(kind='conditional', what='all lamps off and GI off until task 0x2b runs, then GI back on and hold',
                  pseudo=['layer = lamp_layer_create(0, 1); mask all lamps (all off)', 'gi_claim_if_free; gi_off',
                          'sleep 6 until task_running(0x2b)', 'gi_on', 'forever sleep 937'], exit='until stopped'),
    0x101cb54: dict(kind='conditional', what='blink the leff lamp group (table +6 = 63, L. LOOP ARROW) every 4 ticks while the big-bumps window task 0xca runs',
                    pseudo=['layer = lamp_layer_create(0, prio); G = leff lamp group; mask G',
                            'while task_running(0xca): toggle G; sleep 4'], exit='when task 0xca ends (left ramp -> bumpers window, FUN_0101cc04)'),
    # ---- GI only / timers
    0x2ffa4: dict(kind='gi_only', what='GI off for 15 ticks (no lamps)', pseudo=['gi_claim_if_free; gi_off; sleep 15; exit'], exit='after 15 ticks'),
    0x1032cac: dict(kind='gi_only', what='GI off for 2 ticks (a GI blink; no lamps)', pseudo=['gi_claim; gi_off; sleep 2; exit'], exit='after 2 ticks'),
    0x2fdf8: dict(kind='timer_only', what='draws nothing; runs while deff 20 runs (holds the leff slot)', pseudo=['while deff_running(20): sleep 1'],
                  exit='when deff 20 ends'),
}
# same code shape at other addresses (checked: identical decompile apart from the name)
for a, b in ((0x101c79c, 0x1015d40), (0x1017174, 0x1015d40), (0x1017628, 0x1015d40), (0x100d158, 0x1015d40),
             (0x102792c, 0x1015d40), (0x10171d8, 0x1015da4), (0x1027990, 0x1015da4), (0x10279e8, 0x1015dfc),
             (0x1009880, 0x10083ec), (0x1021700, 0x10083ec), (0x102fa7c, 0x10083ec), (0x103041c, 0x10083ec)):
    CODE[a] = dict(CODE[b], same_code_as=hx(b))
HOLDERS = {0x1009834: 'creates an empty layer (no lamps masked) and sleeps forever: draws nothing',
           0x1005644: 'sleeps 8 ticks forever: draws nothing'}


def norm_decomp(a):
    b = decomp_body(a) or ''
    b = b.split('\n', 2)[-1]
    return re.sub(r'\b(leff_\d+\w*|FUN_[0-9a-f]+)\b', 'F', b)


def is_stub(fn):
    i = insns(fn, fn + 4)
    return bool(i) and i[0].mnemonic == 'mov' and i[0].op_str == 'pc, lr'


def main():
    assert LN == 172 and LS == 12, (LN, LS)
    lnames = lamp_names()
    ramn = load_ram_names()
    for k, v in RAM_EXTRA.items():
        ramn.setdefault(k, v)
    pkg = {int(r['leff']): r for r in csv.DictReader(open(os.path.join(REPO, 'mpf_package', 'lamp_effects.csv')))}
    # check the "same code" claims
    for a, e in CODE.items():
        if 'same_code_as' in e:
            assert norm_decomp(a) == norm_decomp(int(e['same_code_as'], 16)), hx(a)
    starts = leff_start_sites()
    by_leff = {}
    for pc, (fs, fname), lid, param in starts:
        by_leff.setdefault(lid, []).append((pc, fs, fname, param))
    rules = rule_sites()
    rule_by_leff = {}
    for kind, pc, (fs, fname), regs, st in rules:
        if kind == 'leff_rule' and regs.get(3) is not None:
            rule_by_leff.setdefault(regs[3] & 0xffff, []).append(pc)
    feats = {}
    rows, code = [], []
    for i in range(LN):
        a = LT + 12 * i
        fn, fl, lg, cg, pr = u32(a), u16(a + 4), u16(a + 6), u16(a + 8), u8(a + 10)
        if i == 0:
            rows.append({'leff': 0, 'entry_addr': hx(a), 'fn': hx(fn), 'class': 'unused record', 'tag': 'code'})
            continue
        if fn not in feats:
            feats[fn] = features(fn)
        f = feats[fn]
        pk = pkg.get(i, {})
        if is_stub(fn):
            cls, kind, note = 'empty_stub', 'stub', 'function is a bare return (mov pc, lr)'
        elif fn in HOLDERS:
            cls, kind, note = 'empty_stub', 'holder', HOLDERS[fn]
        elif fn in CODE and CODE[fn]['kind'] not in ('timer_only',):
            e = CODE[fn]
            cls, kind, note = 'code_drawn', e['kind'], e['what']
            if fn in (0x1017dbc, 0x100f430):
                cls = 'exported_show'
        elif fn in CODE:
            cls, kind, note = 'empty_stub', CODE[fn]['kind'], CODE[fn]['what']
        else:
            cls, kind, note = 'exported_show', 'fixed', ''
        cgc = []
        if cg:
            p = u32(CGT + 4 * cg)
            while u8(p):
                cgc.append(u8(p))
                p += 1
        sites = by_leff.get(i, [])
        params = sorted({str(s[3]) if not isinstance(s[3], int) else hx(s[3]) for s in sites if s[3] is not None})
        row = {
            'leff': i, 'entry_addr': hx(a), 'fn': hx(fn), 'fn_name': func_name(fn) or '',
            'same_fn_as': ' '.join(str(j) for j in range(1, LN) if j != i and u32(LT + 12 * j) == fn),
            'flags_hex': '0x%04x' % fl, 'flags_decoded': ' | '.join(FLAG_BITS[b].split(' (')[0].split(';')[0] for b in FLAG_BITS if fl & b),
            'task_flags_hex': '0x%04x' % flag_task_bits(fl),
            'lamp_group': lg or '', 'lamp_group_name': GROUP_NAMES.get(lg, '') if lg else '',
            'coil_group': cg or '', 'coil_group_coils': ' '.join(map(str, cgc)),
            'priority': pr,
            'class': cls, 'code_kind': kind, 'class_note': note,
            'package_show': pk.get('show', ''), 'package_kind': pk.get('kind', ''),
            'package_length_ms': pk.get('length_ms', ''), 'package_loops': pk.get('loops', ''),
            'gi': ' '.join(dict.fromkeys(f['gi'])),
            'lamps_const': ' '.join(map(str, sorted(f['lamps']))),
            'groups_const': ' '.join(map(str, sorted(f['groups']))),
            'coils_const': ' '.join(map(str, sorted(f['coils']))),
            'sleeps': ' '.join(map(str, f['sleeps'][:12])),
            'reads_task_param': int(f['reads_param']),
            'start_param_values': ' '.join(params),
            'leff_start_sites': ' '.join('%s:%s%s' % (hx(pc), fname or '?', '' if p is None else '(+0x30=%s)' % (hx(p) if isinstance(p, int) else p))
                                         for pc, fs, fname, p in sites),
            'leff_rule_sites': ' '.join(hx(x) for x in rule_by_leff.get(i, [])),
            'tag': 'code',
        }
        rows.append(row)
        if cls == 'code_drawn' or fn in (0x1017dbc, 0x100f430):
            e = CODE[fn]
            ram = []
            for r in sorted(set(e.get('ram', [])) | set(f['ram'])):
                n, m = ramn.get(r, ('', ''))
                if r in (0x3c224, 0x3c238, 0x3b134) and r not in e.get('ram', []):
                    pass
                ram.append({'addr': hx(r), 'name': n, 'meaning': m,
                            'tag': 'code' if r in RAM_EXTRA or n else 'code (address only)'})
            code.append({
                'leff': i, 'fn': hx(fn), 'fn_name': func_name(fn) or '', 'same_code_as': e.get('same_code_as', ''),
                'kind': e['kind'], 'priority': pr, 'flags_hex': '0x%04x' % fl,
                'lamp_group': lg, 'lamp_group_lamps': group_members(lg)[1] if lg else [],
                'coil_group': cg, 'coil_group_coils': cgc,
                'what': e['what'], 'param': e.get('param', ''),
                'param_values_at_leff_start': params,
                'lamps_touched': sorted(f['lamps']), 'lamp_names': [lnames.get(x, '?') for x in sorted(f['lamps'])],
                'groups_touched': sorted(f['groups']),
                'coils_touched': sorted(f['coils']), 'coil_groups_touched': sorted(f['coil_groups']),
                'rom_tables': [hx(t) for t in sorted(f['tables'])],
                'ram_read': ram,
                'sleeps_ticks': f['sleeps'], 'tick_ms': TICK_MS,
                'gi': list(dict.fromkeys(f['gi'])),
                'functions': f['functions'],
                'exit': e.get('exit', ''),
                'pseudo': e['pseudo'],
                'note': e.get('note', ''),
                'started_by': [{'site': hx(pc), 'caller': fname, 'param': (hx(p) if isinstance(p, int) else p)} for pc, fs, fname, p in sites],
                'leff_rules': [hx(x) for x in rule_by_leff.get(i, [])],
                'unresolved_args': f['unresolved'],
                'tag': 'code',
            })
    cols = list(rows[1].keys())
    with open(os.path.join(OUT, 'leff_table.csv'), 'w', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, '') for k in cols})
    with open(os.path.join(OUT, 'code_leffs.json'), 'w') as fo:
        json.dump({'source': 'leff table 0x040e23e4 (RAM 0x36cf0: %d x %d B); see README.md' % (LN, LS),
                   'tick_ms': TICK_MS, 'leffs': code}, fo, indent=1)
    write_md(code)
    write_rules(rules, ramn)
    from collections import Counter
    print('leffs', LN - 1, Counter(r['class'] for r in rows[1:]), 'code entries', len(code))
    print('leff_start sites', len(starts), 'with param', sum(1 for s in starts if s[3] is not None),
          'unresolved id', sum(1 for s in starts if s[2] is None))


def write_md(code):
    L = ['# Code-drawn lamp effects (leffs)', '',
         'Generated by `rom_data/tools/hw_leffs.py`; the same data is in `code_leffs.json`. One tick = 16.26 ms.',
         'Leffs whose function is shared are listed once per leff id. "valid" = `playfield_is_valid()`; '
         '"ball search" = task id 0x2b running. Every fact is read from the code (tag `code`) unless marked inferred.', '']
    for e in code:
        L.append('## leff %d - %s (%s)' % (e['leff'], e['what'], e['kind']))
        L.append('')
        L.append('- function `%s` %s%s; priority %d; flags %s; lamp group %s; coil group %s %s' % (
            e['fn'], e['fn_name'], (' (same code as %s)' % e['same_code_as']) if e['same_code_as'] else '',
            e['priority'], e['flags_hex'], e['lamp_group'] or '-', e['coil_group'] or '-',
            ('(coils %s)' % e['coil_group_coils']) if e['coil_group_coils'] else ''))
        if e['param']:
            L.append('- parameter: %s; values stored at leff_start sites: %s' % (e['param'], ', '.join(e['param_values_at_leff_start']) or 'none constant'))
        if e['ram_read']:
            L.append('- RAM read: ' + '; '.join('`%s` %s (%s)' % (r['addr'], r['name'], r['meaning']) for r in e['ram_read']))
        if e['lamps_touched'] or e['groups_touched']:
            L.append('- lamps (constant): %s; groups (constant): %s' % (
                ', '.join('%d %s' % (a, b) for a, b in zip(e['lamps_touched'], e['lamp_names'])) or '-',
                ', '.join(map(str, e['groups_touched'])) or '-'))
        if e['coils_touched'] or e['coil_groups_touched']:
            L.append('- coils: %s; coil groups: %s' % (', '.join(map(str, e['coils_touched'])) or '-',
                                                       ', '.join(map(str, e['coil_groups_touched'])) or '-'))
        if e['rom_tables']:
            L.append('- ROM tables: ' + ', '.join(e['rom_tables']))
        L.append('- sleeps (ticks): %s; exit: %s' % (', '.join(map(str, e['sleeps_ticks'])) or '-', e['exit']))
        if e['gi']:
            L.append('- GI: ' + ', '.join(e['gi']))
        if e['started_by'] or e['leff_rules']:
            L.append('- started by: ' + ', '.join('%s %s%s' % (s['site'], s['caller'], (' +0x30=%s' % s['param']) if s['param'] is not None else '')
                                                  for s in e['started_by']) +
                     ('; leff rules at ' + ', '.join(e['leff_rules']) if e['leff_rules'] else ''))
        if e['note']:
            L.append('- note: ' + e['note'])
        L.append('')
        L.append('```')
        L.extend(e['pseudo'])
        L.append('```')
        L.append('')
    with open(os.path.join(OUT, 'code_leffs.md'), 'w') as fo:
        fo.write('\n'.join(L))


def write_rules(rules, ramn):
    rows = []
    for kind, pc, (fs, fname), regs, st in rules:
        obj, lst, cond = regs.get(0), regs.get(1), regs.get(2)
        if kind == 'leff_rule':
            leff, mm, p6, prio = regs.get(3), st[0], st[1], st[2]
            deff = snd = cfn = None
        else:
            deff, snd, cfn, mm, p6, prio = regs.get(3), st[0], st[1], st[2], st[3], st[4]
            leff = None
        cname, csum = cond_summary(cond) if cond is not None else ('', '')
        fname2, fsum = cond_summary(cfn) if cfn else ('', '')
        rows.append({
            'site': hx(pc), 'caller_fn': hx(fs) if fs is not None else '', 'caller_name': fname or '',
            'kind': kind, 'init_api': '0x19740 leff_rule_init' if kind == 'leff_rule' else '0x1982c lamp_rule_init (a deff/sound rule)',
            'object': hx(obj) if obj is not None else '', 'list': '' if lst is None else lst & 0xff,
            'cond_fn': hx(cond) if cond is not None else '', 'cond_name': cname, 'cond_tests': csum,
            'leff': '' if leff is None else leff & 0xffff,
            'deff': '' if deff is None else deff & 0xffff,
            'sound': '' if snd is None else snd & 0xffff,
            'modify_fn': hx(cfn) if cfn else '', 'modify_fn_body': fsum,
            'mode_mask': '' if mm is None else '0x%04x' % (mm & 0xffff),
            'byte6': '' if p6 is None else p6 & 0xff, 'priority_byte7': '' if prio is None else prio & 0xff,
            'unresolved': ' '.join(n for n, v in (('obj', obj), ('list', lst), ('cond', cond), ('mode_mask', mm)) if v is None),
            'tag': 'code',
        })
    cols = list(rows[0].keys())
    with open(os.path.join(OUT, 'lamp_rules.csv'), 'w', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print('rules', len(rows), 'leff', sum(r['kind'] == 'leff_rule' for r in rows), 'deff', sum(r['kind'] == 'deff_rule' for r in rows))


if __name__ == '__main__':
    main()
