# Builds MPF shows for the ROM's lamp-matrix light effects (table 0x040e23e4) from the emulator
# captures made by lfx.cpp (caps.json, caps_pf.json), and wires them into the display-effect shows.
import json, re, struct, os, csv, collections, yaml

ROM = open('/mnt/project-files/trn_174h.bin', 'rb').read()
P = '/mnt/project-files/tron/mpf_package'
SH = P + '/config/shows'
L = '/home/claude/lfx'
CHANGED = set()

def leff_entry(i):
    fn, flags, grp, cgrp, pr = struct.unpack_from('<IHHHH', ROM, 0xe23e4 + i * 12)
    return dict(fn=fn, flags=flags, group=grp, coil_group=cgrp, prio=pr & 0xff)

def lamp_group(g):
    p = struct.unpack_from('<I', ROM, 0xe3acc + 4 * g)[0] - 0x04000000; out = []
    while ROM[p]: out.append(ROM[p]); p += 1
    return out

# hardware names
lights = {}
for m in re.finditer(r'\n  (l_\w+):\n    number: (\d+)\s+# ([^\n]*)', open(P + '/config/lights.yaml').read()):
    lights[int(m.group(2))] = (m.group(1), m.group(3).strip())
flashers = {}
for m in re.finditer(r'\n  (f_\w+):\n    number: (\d+)', open(P + '/config/coils.yaml').read()):
    flashers[int(m.group(2))] = m.group(1)

caps = json.load(open(L + '/caps.json'))
pf = json.load(open(L + '/caps_pf.json'))
PF_IDS = {c['id'] for c in pf.values()}

# who starts each effect (decompiled code)
src = open('/mnt/project-files/tron/code/tron_game_decompiled_v2.c').read()
sites = collections.defaultdict(list)
cur = None
for line in src.split('\n'):
    m = re.match(r'// ==== ([0-9a-f]{8}) (\S+)', line)
    if m: cur = m.group(2); continue
    for m2 in re.finditer(r'leff_start\((0x[0-9a-f]+|\d+)\)', line):
        sites[int(m2.group(1), 0)].append(cur)
rules = {}
for m in re.finditer(r'leff_rule_init\(([^;]*)\);', src):
    a = [x.strip() for x in m.group(1).split(',')]
    if len(a) > 3 and re.match(r'^(0x[0-9a-f]+|\d+)$', a[3]): rules[int(a[3], 0)] = a[2].lstrip('&')

# display effect -> show names in the package
deff_name = {int(r['deff']): r['name'] for r in csv.DictReader(open(P + '/event_map.csv'))}
deff_fn = {struct.unpack_from('<I', ROM, 0xe1350 + d * 8)[0]: d for d in range(1, 146)}
forced = {int(k): v for k, v in json.load(open(L + '/deff_lampfx_forced.json')).items()}
deff_of_leff = collections.defaultdict(set)
for d, evs in forced.items():
    for t, lid, lr in evs: deff_of_leff[lid].add(d)
for lid, fs in sites.items():
    for f in fs:
        m = re.match(r'deff_?(\d{3})', f)
        if m: deff_of_leff[lid].add(int(m.group(1)))

LAMP_PARAM = {37: 'on', 100: 'on', 119: 'on', 39: 'off', 102: 'off', 121: 'off', 127: 'off', 142: 'off', 87: 'off',
              38: 'flash', 86: 'flash', 89: 'flash', 131: 'flash', 141: 'flash', 120: 'flash', 126: 'flash', 41: 'flash'}
GROUP_PARAM = {40: 31, 143: 50, 103: 52, 122: 54}   # group the callers pass (103: table group, no caller passes one)
TEST = {3: 'single lamp test', 4: 'test all lamps', 5: 'lamp row test', 6: 'lamp column test', 7: 'ordered lamp test', 8: 'burn-in'}
SLUG_FIX = {1: 'attract', 2: 'attract_lamps_off', 9: 'tilt_lamps_off', 12: 'slam_tilt_lamps_off', 13: 'ball_save_lamp', 14: 'ball_save_lamp_running',
            20: 'bonus_lamps_off', 133: 'game_over', 35: 'vuk_not_lit', 36: 'vuk_lit', 19: 'flasher_sweep', 89: 'clu_lane',
            109: 'skill_shot_ready_1', 111: 'skill_shot_ready_2', 113: 'skill_shot_ready_3', 132: 'find_flynn_rule', 157: 'find_flynn_roving_arrow',
            134: 'sea_of_simulation_rule', 136: 'sea_of_simulation_rule_2', 161: 'combo_rule', 118: 'unused', 43: 'unused', 102: 'unused',
            103: 'unused', 104: 'unused', 126: 'unused', 127: 'unused', 131: 'unused'}

def slug_for(i):
    if i in SLUG_FIX: return SLUG_FIX[i]
    if i in TEST: return 'test_' + TEST[i].replace(' ', '_').replace('-', '_')
    ds = sorted(deff_of_leff.get(i, []))
    if ds and ds[0] in deff_name: return deff_name[ds[0]][9:]
    if i in rules: return re.sub(r'^(leff\d*_|FUN_\w+|LAB_\w+)', '', rules[i]) or 'mode_rule'
    fs = [f for f in sites.get(i, []) if not f.startswith('FUN_')]
    if fs: return fs[0]
    return 'effect'

def coil_name(c):
    return flashers.get(c)

def timeline(c, token_lamp=None, token_group=None):
    """events: list of (t_ms, {'lights':{name:color}, 'flashers':{name:'Nms'}})"""
    ev = collections.defaultdict(lambda: {'lights': {}, 'flashers': {}})
    prev = {}
    for t, h in c['frames']:
        mask = int(h[:20], 16); a = int(h[20:40], 16); b = int(h[40:60], 16)
        for n in range(1, 81):
            bit = 1 << (80 - n)
            if not mask & bit:
                continue
            on = bool(a & bit) + bool(b & bit)
            col = 'ffffff' if on == 2 else ('7f7f7f' if on == 1 else '000000')
            if token_lamp and n == token_lamp: name = '(lamp)'
            elif token_group and n in token_group: name = '(lamps)'
            elif n in lights: name = lights[n][0]
            else: continue
            if prev.get(name) != col:
                ev[int(round(t * 1000))]['lights'][name] = col; prev[name] = col
    for t, coil, ms in c['coils']:
        if isinstance(coil, str): continue          # coil-group call; its coils are logged one by one too
        nm = coil_name(coil)
        if nm: ev[int(round(t * 1000))]['flashers'][nm] = '%dms' % ms
    return sorted(ev.items())

def find_period(evs, total_ms):
    """(start, k, period): smallest repeat of the event sequence from index start
    (same content, same spacing within 25 ms). Light states are absolute, so a repeat is exact."""
    if len(evs) < 4: return None
    sig = [json.dumps(e, sort_keys=True) for _, e in evs]
    ts = [t for t, _ in evs]
    for s0 in range(0, max(1, min(len(evs) // 3, 40))):
        for k in range(1, (len(evs) - s0) // 2 + 1):
            per = ts[s0 + k] - ts[s0]
            if per < 50: continue
            ok = all(sig[i] == sig[i + k] and abs((ts[i + k] - ts[i]) - per) <= 25 for i in range(s0, len(evs) - k))
            if ok: return s0, k, per
    return None

def norm(evs):
    """drop timing jitter: snap to 1 ms grid starting at 0"""
    if not evs: return evs
    t0 = evs[0][0] if evs[0][0] < 40 else 0
    return [(max(0, t - t0), e) for t, e in evs]

def to_steps(evs, end_ms):
    steps = []
    for i, (t, e) in enumerate(evs):
        nxt = evs[i + 1][0] if i + 1 < len(evs) else end_ms
        st = {'duration': '%dms' % max(1, nxt - t)}
        if e['lights']: st['lights'] = dict(sorted(e['lights'].items()))
        if e['flashers']: st['flashers'] = dict(sorted(e['flashers'].items()))
        steps.append(st)
    return steps

# ---------- synthesized from code: effects that only run in states the capture did not reach ----------
def bits(x): return bin(x & 0xffffffff).count('1')
PWM = [struct.unpack_from('<i', ROM, 0xd25c0 + 4 * i)[0] for i in range(16)]
def synth_breathe(per_tick_ms=98):
    # leff 57 / 134: zen (17) and video game (18) flashers pulsed 200 ms every 6 ticks with a PWM
    # pattern from a 16-step table (brightness ramps up and down), the two half a cycle apart.
    evs = []
    for k in range(16):
        b1 = bits(PWM[k]); b2 = bits(PWM[(k + 8) % 16]); e = {'lights': {}, 'flashers': {}}
        if b1: e['flashers']['f_zen_flasher'] = '%dms' % max(4, round(200 * b1 / 32))
        if b2: e['flashers']['f_video_game'] = '%dms' % max(4, round(200 * b2 / 32))
        evs.append((k * per_tick_ms, e))
    return evs, 16 * per_tick_ms
SYNTH = {
    57: (synth_breathe, 'code: zen and video game flashers breathe (PWM table 0x040d25c0) while End of Line is lit; pauses while ball search runs (inferred from task 0x2b)'),
    134: (synth_breathe, 'code: same breathing zen/video game flashers (table 0x040d3940, identical values)'),
    167: (lambda: ([(0, {'lights': {}, 'flashers': {'f_disc_left': '32ms', 'f_disc_right': '32ms'}})], 131),
          'code: disc flashers (coil group 14) pulsed 32 ms every 8 ticks'),
}

STATE_ONLY = {
    15: 'waits while display effect 20 (ball saved) runs; no lamps',
    45: 'Disc Multiball status lamps: draws lamp groups from mode state (rule leff_rule_init, dmb_status_display_cond)',
    53: 'Disc Multiball restart: lamp layer driven by mode state',
    59: 'empty loop that only holds its priority (blocks lower effects) while End of Line runs',
    94: 'Light Cycle Multiball: spawns child effects from mode state',
    159: 'combo arrows: lights the arrows of the current combo from game state (rule FUN_01003bf0)',
    14: 'ball save: blinks the shoot again lamp while the ball save timer runs (pointer parameter)',
}

rows = []; shows_written = {}
for i in range(1, 172):
    e = leff_entry(i)
    cands = [c for c in list(caps.values()) + list(pf.values()) if c['id'] == i]
    par = None
    if i in LAMP_PARAM: par = 33
    elif i in GROUP_PARAM: par = 0x10000 + 12
    c = None
    if i in PF_IDS:
        c = [x for x in pf.values() if x['id'] == i][0]
    if c is None or (not c['frames'] or not any(int(h[:20], 16) for _, h in c['frames'])) and not c['coils']:
        pick = [x for x in caps.values() if x['id'] == i and x['par'] == (par if par is not None else -1)]
        if pick: c = pick[0] if (pick[0]['coils'] or any(int(h[:20], 16) for _, h in pick[0]['frames'])) or c is None else c
    tok_lamp = 33 if i in LAMP_PARAM else None
    tok_group = lamp_group(12) if i in GROUP_PARAM else None
    note = ''; kind = ''
    if i in SYNTH:
        evs, per = SYNTH[i][0](); loop = True; total = per; note = SYNTH[i][1]; src_ = 'code'
    else:
        src_ = 'observed'
        evs = norm(timeline(c, tok_lamp, tok_group)) if c else []
        dur = int(round((c or {}).get('dur', 0) * 1000))
        loop = c is not None and c['status'] == 'cap'
        total = dur
        if loop and evs:
            fp = find_period(evs, dur)
            if fp and evs[fp[0]][0] > 200: fp = None; note = 'loops in the ROM after a lead-in; capture cut at 12 s, show repeats that'
            if fp:
                s0, k, per = fp
                if s0:
                    # the loop body must carry every light's state, as the intro steps are dropped
                    state = {}
                    for _, e2 in evs[:s0 + 1]: state.update(e2['lights'])
                    first = {'lights': dict(state), 'flashers': dict(evs[s0][1]['flashers'])}
                    note = 'loops in the ROM; the first %d ms (a lead-in before the loop settles) are left out' % evs[s0][0]
                    body = [(evs[s0][0], first)] + evs[s0 + 1:s0 + k]
                else:
                    body = evs[:k]
                t0 = body[0][0]; evs = [(t - t0, e2) for t, e2 in body]; total = per
            else:
                total = 12000; note = note or 'loops in the ROM until stopped; capture cut at 12 s, show repeats that'
    lit = any(e2['lights'] for _, e2 in evs); fl = any(e2['flashers'] for _, e2 in evs)
    allfirst = evs and len(evs) == 1 and all(v == '000000' for v in evs[0][1]['lights'].values()) and not fl
    if not evs:
        if i in STATE_ONLY: kind = 'state display'; note = STATE_ONLY[i]
        elif c and c['status'] == 'natural' and c.get('dur', 1) < 0.1: kind = 'no-op'; note = note or 'empty in v1.74 (the task ends at once)'
        else: kind = 'state display'; note = note or 'drew nothing in the captured state; it depends on mode state (see started_by)'
    elif allfirst: kind = 'lamps off'
    else: kind = ('lamps+flashers' if lit and fl else 'lamps' if lit else 'flashers')
    name = 'lampfx_%03d_%s' % (i, slug_for(i))
    started = []
    for d in sorted(deff_of_leff.get(i, [])): started.append('effect %d (%s)' % (d, deff_name.get(d, '?')))
    if i in rules: started.append('rule: while %s' % rules[i])
    for f in sorted(set(sites.get(i, []))):
        if not re.match(r'deff_?\d', f): started.append('code: %s' % f)
    if i in TEST: started.append('service menu: %s' % TEST[i])
    token = '(lamp) = the lamp the caller passes' if tok_lamp else ('(lamps) = a light tag for the lamp group the caller passes' if tok_group else '')
    if kind in ('no-op', 'state display'):
        rows.append(dict(leff=i, show='', kind=kind, source=src_ if kind != 'no-op' else 'observed', loops='', length_ms='', priority=e['prio'],
                         lamps='', flashers='', tokens='', started_by='; '.join(started), notes=note))
        continue
    if allfirst:
        steps = [{'duration': '%dms' % (1000 if loop else max(total, 100)), 'lights': evs[0][1]['lights']}]
    else:
        steps = to_steps(evs, max(total, evs[-1][0] + 1))
    lampset = sorted({k for _, e2 in evs for k in e2['lights']}); flset = sorted({k for _, e2 in evs for k in e2['flashers']})
    hdr = ['#show_version=6',
           '# ROM lamp effect %d (leff table 0x040e23e4, function 0x%x, priority %d). %s.' % (i, e['fn'], e['prio'],
               'Captured in emulation' if src_ == 'observed' else 'Rebuilt from code'),
           '# %s. %s' % ('Loops until stopped' if loop else 'Plays once', note)]
    if token: hdr.append('# Show token %s (captured with lamp 33 / group 12 standing in).' % token)
    if kind == 'lamps off': hdr.append('# Holds these lamps off (a blackout layer) for as long as it runs.')
    if started: hdr.append('# Started by: ' + '; '.join(started))
    txt = '\n'.join(hdr) + '\n' + yaml.safe_dump(steps, sort_keys=False, default_flow_style=False, width=200)
    fn = SH + '/' + name + '.yaml'
    if not os.path.exists(fn) or open(fn).read() != txt:
        open(fn, 'w').write(txt); CHANGED.add('config/shows/' + name + '.yaml')
    shows_written[i] = (name, loop, e['prio'], token)
    rows.append(dict(leff=i, show=name, kind=kind, source=src_, loops='-1' if loop else '0', length_ms='until stopped' if (allfirst and loop) else total,
                     priority=e['prio'], lamps=' '.join(lampset), flashers=' '.join(flset), tokens=token,
                     started_by='; '.join(started), notes=note))

json.dump({str(k): v for k, v in shows_written.items()}, open(L + '/shows_written.json', 'w'))
json.dump(sorted(CHANGED), open(L + '/changed_lampfx.json', 'w'))
with open(P + '/lamp_effects.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(collections.Counter(r['kind'] for r in rows))
print(len(shows_written), 'shows')
