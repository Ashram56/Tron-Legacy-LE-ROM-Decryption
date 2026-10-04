"""Tron Pro 1.74 (TRN174VP.BIN = PinMAME trn_17402): coil descriptors, coil rules and every coil-API call site,
side by side with the LE 1.74 values. Writes rom_data/pro/ (coils_pro.csv, coil_calls_pro.csv, coil_rules_pro.json).

Run: TRON_PRO_ROM=/path/TRN174VP.BIN TRON_PRO_DECOMP=code/tron_pro_decompiled.c python3 rom_data/tools/pro_hw.py
The Pro ROM is not in the repository. Pro addresses come from rom_data/pro/le_to_pro_functions.csv (LE -> Pro
function match, masked byte signatures + call-graph propagation) and from the Pro table of tables (RAM 0x2fa00).
"""
import csv, json, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
PRO_ROM = os.environ.get('TRON_PRO_ROM', '/mnt/project-files/tron/pro/TRN174VP.BIN')
os.environ['TRON_ROM'] = PRO_ROM          # rom.py reads the Pro image from here on
sys.path.insert(0, HERE)
import rom
rom.code_ranges = lambda: [(0x0, 0x2fa00), (0x01000000, 0x01100000)]   # Pro OS code ends at 0x2fa00
import hw_common
hw_common.DECOMP = os.environ.get('TRON_PRO_DECOMP', os.path.join(REPO, 'code', 'tron_pro_decompiled.c'))
hw_common._funcs = None
import hw_calls
from rom import ROM, u8, u16, u32, foff, hx
OUT = os.path.join(REPO, 'rom_data', 'pro')

# ---- Pro tables (table of tables at RAM 0x2fa00, {ptr, count, size}; LE 0x36c00 + the same order) ----
def tt(a): return u32(a), u32(a + 4), u32(a + 8)
DESC, NDESC, _ = tt(0x2fa48)       # coil descriptors, LE 0x36c48
FLIP, NFLIP, SFLIP = tt(0x2fa9c)   # flipper rules, LE 0x36c9c
CGRP, NCGRP, _ = tt(0x2faa8)       # coil groups, LE 0x36ca8
CQ, NCQ, SCQ = tt(0x2fab4)         # counter queues (knocker, meter), LE 0x36cb4
LEFF, NLEFF, _ = tt(0x2faf0)       # lamp-matrix leffs, LE 0x36cf0
NAMES = 0x040c5ef4                 # coil names, 24 B records
MSG, NMSG = 0x040d3730, u32(0x040b9f2c)
SHAKER_TAB = 0x040bc8e0

def msg(i):
    if i is None or i >= NMSG: return None
    return rom.cstr(u32(u32(MSG + 4 * i)))
rom.msg = msg

# LE -> Pro function map
FMAP = {}
for r in csv.DictReader(open(os.path.join(OUT, 'le_to_pro_functions.csv'))):
    FMAP[int(r['le_addr'], 16)] = int(r['pro_addr'], 16)
FMAP.setdefault(0x010289b8, 0x010203ac)   # shaker_run: wrapper right after FUN_01020318 (= LE FUN_01028924), reads table 0x040bc8e0

def lits(fn, n=0x200):
    """flash-data literals (0x04xxxxxx) in the literal pool of a function"""
    out = []
    for k in range(0, n, 4):
        w = u32(fn + k)
        if 0x04000000 <= w < 0x04800000: out.append(w)
    return out

BUMP = [w for w in lits(FMAP[0x378c])][0]     # bumper rule table, LE 0x040f0a5c via FUN_0000378c
SLING = [w for w in lits(FMAP[0x3c98])][0]    # sling rule table, LE 0x040f0a8c via FUN_00003c98

FLAGS = [(0x1, 'aux'), (0x2, 'power_exempt'), (0x4, 'flasher'), (0x8, 'flipper'), (0x40, 'ball_device_kicker'),
         (0x80, 'optional'), (0x100, 'motor_or_long'), (0x400, 'no_cycle_test'), (0x800, 'hidden_in_tests'),
         (0x1000, 'not_in_flash_test'), (0x2000, 'bumper'), (0x4000, 'relay'), (0x10000, 'solenoid')]

def desc(n):
    a = DESC + 28 * n
    fl, f4, f8, fc, tm, bs, w1, w2, x = struct.unpack_from('<IIIIHHHHI', ROM, foff(a))
    return {'desc_addr': hx(a), 'flags_hex': '0x%08x' % fl, 'flags_decoded': ' '.join(nm for b, nm in FLAGS if fl & b),
            'test_fn': hx(f4) if f4 else '', 'test_pulse_ms': tm, 'ballsearch_ms': bs,
            'wire_color_1': msg(w1), 'wire_color_2': msg(w2), 'desc_tail_hex': '0x%08x' % x}

def coil_name(n): return rom.cstr(u32(NAMES + 24 * n))

def coil_group(g):
    if g is None or not (0 < g < NCGRP): return None
    p = u32(CGRP + 4 * g); out = []
    while u8(p): out.append(u8(p)); p += 1
    return out

def rules():
    flip = []
    for i in range(NFLIP):
        a = FLIP + SFLIP * i
        flip.append({'index': i, 'addr': hx(a), 'raw': ROM[foff(a):foff(a) + SFLIP].hex()})
    bump = []
    for i in range(1, 4):
        a = BUMP + 12 * i
        bump.append({'index': i, 'addr': hx(a), 'pulse_ms': u16(a), 'recycle_ms': u16(a + 2), 'extend_ms': u8(a + 4),
                     'switch': u8(a + 6), 'coil': u8(a + 7), 'debounce_ms': u8(a + 8), 'raw': ROM[foff(a):foff(a) + 12].hex()})
    sling = []
    for i in range(1, 3):
        a = SLING + 8 * i
        sling.append({'index': i, 'addr': hx(a), 'pulse_ms': u16(a), 'recycle_ms': u16(a + 2), 'switch': u8(a + 4),
                      'coil': u8(a + 5), 'raw': ROM[foff(a):foff(a) + 8].hex()})
    cq = []
    for i in range(1, NCQ):
        a = CQ + SCQ * i
        cq.append({'index': i, 'addr': hx(a), 'pulse_ms': u16(a + 0x0e), 'gap_ticks': u16(a + 0x10) >> 4, 'coil': u8(a + 0x12)})
    groups = {g: coil_group(g) for g in range(1, NCGRP)}
    leffs = []
    for i in range(1, NLEFF):
        a = LEFF + 12 * i
        g = u16(a + 8)
        if g: leffs.append({'leff': i, 'fn': hx(u32(a)), 'coil_group': g, 'coils': coil_group(g)})
    shaker = {s: u16(SHAKER_TAB + 4 * s) for s in (1, 2, 3)}
    return {'flipper_rules': {'table': hx(FLIP), 'records': flip}, 'bumper_rules': {'table': hx(BUMP), 'records': bump},
            'sling_rules': {'table': hx(SLING), 'records': sling}, 'counter_queues': {'table': hx(CQ), 'records': cq},
            'coil_groups': {'table': hx(CGRP), 'groups': groups}, 'leff_coil_groups': {'table': hx(LEFF), 'leffs': leffs},
            'shaker_ms_by_strength': {'table': hx(SHAKER_TAB), 'ms': shaker}, 'tag': 'code'}

def calls():
    api = {}
    for le_a, v in hw_calls.API.items():
        pa = FMAP.get(le_a)
        if pa is None: continue
        dname = hw_common.func_name(pa) or v[1]
        api[pa] = (v[0], dname, v[2], v[3])
    hw_calls.API.clear(); hw_calls.API.update(api)
    hw_calls.SHAKER_MS.clear(); hw_calls.SHAKER_MS.update({s: u16(SHAKER_TAB + 4 * s) for s in (1, 2, 3)})
    hw_calls.LEFF_TAB, hw_calls.LEFF_N = LEFF, NLEFF
    hw_calls.coil_group = coil_group
    hw_calls.OUT = OUT
    rows = hw_calls.main()
    os.replace(os.path.join(OUT, 'coil_calls.csv'), os.path.join(OUT, 'coil_calls_pro.csv'))
    return rows

def pair_calls(pro_rows):
    """pair each LE coil call site with the Pro call site at the same position in the matched function"""
    le_rows = list(csv.DictReader(open(os.path.join(REPO, 'rom_data', 'io', 'coil_calls.csv'))))
    by_fn_le, by_fn_pro = {}, {}
    for r in le_rows:
        if r['caller_fn']: by_fn_le.setdefault(int(r['caller_fn'], 16), []).append(r)
    for r in pro_rows:
        if r['caller_fn']: by_fn_pro.setdefault(int(r['caller_fn'], 16), []).append(r)
    out = []
    for lf, lr in sorted(by_fn_le.items()):
        pf = FMAP.get(lf)
        pr = by_fn_pro.get(pf, []) if pf else []
        status = 'no Pro function match' if pf is None else ('paired' if len(pr) == len(lr) else 'call count differs (%d LE, %d Pro)' % (len(lr), len(pr)))
        for i, l in enumerate(lr):
            p = {k: str(v) for k, v in pr[i].items()} if status == 'paired' else {}
            def g(d, k): return d.get(k, '') if d else ''
            same_t = '' if not p else ('yes' if (l['ms'], l['pattern'], l['on_ms'], l['off_ms'], l['strength']) == (p['ms'], p['pattern'], p['on_ms'], p['off_ms'], p['strength']) else 'no')
            out.append({'le_call_site': l['call_site'], 'le_caller': l['caller_name'], 'le_api': l['api'], 'le_coil': l['coil'], 'le_group_coils': l['group_coils'],
                        'le_ms': l['ms'], 'le_pattern': l['pattern'], 'pro_call_site': g(p, 'call_site'), 'pro_caller_fn': hx(pf) if pf else '',
                        'pro_api': g(p, 'api'), 'pro_coil': g(p, 'coil'), 'pro_group_coils': g(p, 'group_coils'), 'pro_ms': g(p, 'ms'), 'pro_pattern': g(p, 'pattern'),
                        'same_timing': same_t, 'same_coil': '' if not p else ('yes' if (l['coil'], l['group_coils']) == (p['coil'], p['group_coils']) else 'no'),
                        'pairing': status, 'tag': 'code'})
    with open(os.path.join(OUT, 'coil_calls_le_vs_pro.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    return out


def observed(path=os.path.join(OUT, 'traces', 'pro_hw_s1.jsonl')):
    """on-times per coil measured at the 1 ms coil IRQ (0x11628) in pro_hw_trace.cpp, split by scenario mark"""
    if not os.path.exists(path): return {}
    mark, res = 'pre', {}
    for l in open(path):
        e = json.loads(l)
        if e['ev'] == 'mark': mark = e['text']
        elif e['ev'] == 'drv' and e['on'] == 0:
            res.setdefault(e['coil'], {}).setdefault(mark, []).append(round(e['on_ms'], 1))
    return res


def obs_summary(d):
    if not d: return '', ''
    parts = []
    for mark, v in d.items():
        long = sorted(x for x in v if x >= 5)
        short = [x for x in v if x < 5]
        s = []
        if long: s.append('%s ms' % ('%g' % long[0] if long[0] == long[-1] else '%g-%g' % (long[0], long[-1])))
        if short: s.append('%d x ~1 ms pattern bits' % len(short))
        parts.append('%s: %s' % (mark, ', '.join(s)))
    return '; '.join(parts), 'observed'


def main():
    os.makedirs(OUT, exist_ok=True)
    R = rules()
    json.dump(R, open(os.path.join(OUT, 'coil_rules_pro.json'), 'w'), indent=1)
    global OBS
    OBS = observed()
    rows = calls()
    pairs = pair_calls(rows)
    print('LE call sites', len(pairs), 'paired', sum(1 for p in pairs if p['pairing'] == 'paired'),
          'same timing', sum(1 for p in pairs if p['same_timing'] == 'yes'), 'coil differs', sum(1 for p in pairs if p['same_coil'] == 'no'))
    # LE reference rows, by coil number and by name
    le = {int(r['coil']): r for r in csv.DictReader(open(os.path.join(REPO, 'rom_data', 'io', 'coils.csv')))}
    le_by_name = {r['name']: r for r in le.values()}
    alias = {'FLASH: RED DISC (LEFT)': 'FLASH: RED DISC', 'FLASH: RED DISC (RIGHT)': 'FLASH: BLUE DISC'}
    by_coil = {}
    for r in rows:
        for c in ([int(r['coil'])] if r['coil'] != '' else [int(x) for x in r['group_coils'].split()] if r['group_coils'] else []):
            by_coil.setdefault(c, []).append(r)
    leff_by_coil = {}
    for l in R['leff_coil_groups']['leffs']:
        for c in l['coils'] or []: leff_by_coil.setdefault(c, []).append(l['leff'])
    out = []
    for n in range(1, NDESC):
        d = desc(n); name = coil_name(n)
        lr = le_by_name.get(name) or (le_by_name.get(alias[name]) if name in alias else None)
        same = le.get(n)
        calls_n = by_coil.get(n, [])
        summ = {}
        for r in calls_n:
            k = '%s %sms' % (r['api'], r['ms'] if r['ms'] != '' else '?')
            if r['pattern']: k += ' pat ' + r['pattern']
            summ[k] = summ.get(k, 0) + 1
        le_calls = lr['game_calls'] if lr else ''
        o, otag = obs_summary(OBS.get(n))
        row = {'coil': n, 'name': name, **d,
               'game_calls': '; '.join('%s x%d' % kv for kv in sorted(summ.items())),
               'game_call_sites': ' '.join(sorted({r['call_site'] for r in calls_n})),
               'leffs_using_coil': ' '.join(map(str, leff_by_coil.get(n, []))),
               'le_coil_same_number': same['name'] if same else '',
               'le_same_device_coil': lr['coil'] if lr else '',
               'le_same_device_name': lr['name'] if lr else '',
               'le_flags_hex': lr['flags_hex'] if lr else '', 'le_test_pulse_ms': lr['test_pulse_ms'] if lr else '',
               'le_game_calls': le_calls,
               'le_mpf_default_pulse_ms': lr['mpf_default_pulse_ms'] if lr else '',
               'observed_on_ms': o, 'observed_tag': otag,
               'tag': 'code'}
        out.append(row)
    with open(os.path.join(OUT, 'coils_pro.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys())); w.writeheader(); w.writerows(out)
    print('coils', len(out))

if __name__ == '__main__':
    main()
