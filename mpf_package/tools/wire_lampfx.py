# Adds the ROM lamp effects (lampfx_NNN) and the shaker to the display-effect shows, writes
# config/lamp_effects.yaml and config/shaker.yaml, and the light tags the token shows need.
import json, re, os, csv, struct, collections, yaml

P = '/mnt/project-files/tron/mpf_package'
SH = P + '/config/shows'
L = '/home/claude/lfx'
ROM = open('/mnt/project-files/trn_174h.bin', 'rb').read()
CHANGED = set(json.load(open(L + '/changed_lampfx.json')))
H = '# Generated from the Stern Tron Legacy LE v1.74 ROM (trn_174h). See ../README.md.\n'

shows = {int(k): v for k, v in json.load(open(L + '/shows_written.json')).items()}   # id -> [name, loop, prio, token]
rows = list(csv.DictReader(open(P + '/lamp_effects.csv')))
forced = {int(k): v for k, v in json.load(open(L + '/deff_lampfx_forced.json')).items()}
deff_name = {int(r['deff']): r['name'] for r in csv.DictReader(open(P + '/event_map.csv'))}

# display effect -> lamp effects it starts: observed (forced runs, all at 0 ms) + code
deff_lfx = collections.defaultdict(dict)
for d, evs in forced.items():
    for t, lid, lr in evs: deff_lfx[d][lid] = ('observed', t)
for r in rows:
    for m in re.finditer(r'effect (\d+) \(', r['started_by']):
        d = int(m.group(1)); lid = int(r['leff'])
        deff_lfx[d].setdefault(lid, ('code', 0))

def load_show(fn):
    txt = open(fn).read()
    hdr = []; body = []
    for line in txt.split('\n'):
        (hdr if (line.startswith('#') and not body) else body).append(line)
    return hdr, yaml.safe_load('\n'.join(body)) or []

def save_show(fn, hdr, steps):
    out = '\n'.join(hdr) + '\n' + yaml.safe_dump(steps, sort_keys=False, default_flow_style=False, width=200)
    if open(fn).read() != out:
        open(fn, 'w').write(out); CHANGED.add('config/shows/' + os.path.basename(fn))

def ms(v): return int(str(v).rstrip('ms'))

# shaker: strength per display effect from code (shaker_run(strength, min_setting) calls)
src = open('/mnt/project-files/tron/code/tron_game_decompiled_v2.c').read()
deff_fn = {struct.unpack_from('<I', ROM, 0xe1350 + d * 8)[0]: d for d in range(1, 146)}
shk = collections.defaultdict(list)
for m in re.finditer(r'// ==== ([0-9a-f]{8}) (\S+)\n(.*?)(?=\n// ==== )', src, re.S):
    a = int(m.group(1), 16); d = deff_fn.get(a) or deff_fn.get(a - 4)
    mm = re.match(r'deff_?(\d{3})', m.group(2))
    if mm: d = int(mm.group(1))
    if not d: continue
    for c in re.finditer(r'shaker_run\((\d),(\d)\)', m.group(3)):
        shk[d].append((int(c.group(1)), int(c.group(2))))
SHAKER_MS = {1: 75, 2: 265, 3: 1100}   # measured on coil 8 in emulated play (ROM table 0x040d3998: 200/384/1024)

# ---- wire into the display effect shows ----
wired = collections.defaultdict(list)
for f in sorted(os.listdir(SH)):
    m = re.match(r'deff_(\d{3})_', f)
    if not m: continue
    d = int(m.group(1))
    if d not in deff_lfx: continue
    hdr, steps = load_show(SH + '/' + f)
    if not steps or 'time' not in steps[0]: continue
    st0 = next((s for s in steps if ms(s['time']) == 0), None)
    if st0 is None:
        st0 = {'time': '0ms'}; steps.insert(0, st0)
    here = []
    for lid, (how, t) in sorted(deff_lfx[d].items()):
        if lid not in shows: continue
        name, loop, prio, token = shows[lid]
        if token: continue                                    # parameterised effects are started by rules code
        st0.setdefault('shows', {})[name] = {'action': 'play', 'loops': -1 if loop else 0}
        here.append(name)
        if name not in wired[d]: wired[d].append(name)
    note = '# Lamp effect: ' + ', '.join(here) + ' at 0 ms (observed in emulation when forced; code otherwise). Stops with this show.' if here else None
    hdr = [h for h in hdr if not h.startswith('# Lamp effect:')]
    if note: hdr.append(note)
    save_show(SH + '/' + f, hdr, steps)

# ---- light tags for the group-token shows ----
def lamp_group(g):
    p = struct.unpack_from('<I', ROM, 0xe3acc + 4 * g)[0] - 0x04000000; out = []
    while ROM[p]: out.append(ROM[p]); p += 1
    return out
TAGS = {31: 'TRON letters (leff 40, task_9f)', 50: 'CLU lamps (leff 143, Sea of Simulation stage 2)',
        52: 'leff 103 table group', 54: 'ZUSE lamps (leff 122)'}
tag_of = collections.defaultdict(list)
for g in TAGS:
    for n in lamp_group(g): tag_of[n].append('rom_group_%d' % g)
lt = open(P + '/config/lights.yaml').read()
def add_tags(m):
    n = int(m.group(2)); block = m.group(0)
    block = re.sub(r'\n    tags: [^\n]*', '', block)
    if tag_of.get(n): block += '\n    tags: ' + ', '.join(tag_of[n])
    return block
lt2 = re.sub(r'\n  (l_\w+):\n    number: (\d+)[^\n]*(?:\n    tags: [^\n]*)?', add_tags, lt)
if lt2 != lt: open(P + '/config/lights.yaml', 'w').write(lt2); CHANGED.add('config/lights.yaml')

# ---- lamp_effects.yaml: one event per effect ----
out = [H, "# ROM lamp-matrix light effects (leff table 0x040e23e4) as MPF shows: config/shows/lampfx_NNN_*.yaml.\n"
       "# These are separate from the ramp tube shows (leff_NNN.yaml). Display-effect shows already start\n"
       "# the lamp effect their ROM effect starts. Post these events from your modes for the rest; who starts\n"
       "# each one in the ROM is in ../lamp_effects.csv (started_by). Priority is the ROM's (1-254).\n"
       "# Token shows: (lamp) is a light name, (lamps) a light tag (rom_group_N in lights.yaml), e.g.\n"
       "#   tron_lampfx_038_tron_letter_collect: {lampfx_038_tron_letter_collect: {show_tokens: {lamp: l_tron_t}}}\n"
       "show_player:\n"]
for r in rows:
    if not r['show']: continue
    lid = int(r['leff']); name, loop, prio, token = shows[lid]
    ev = 'tron_' + name
    opts = {'loops': -1 if loop else 0, 'priority': prio}
    if token:
        opts['show_tokens'] = {'lamp': 'l_tron_t'} if '(lamp)' in token else {'lamps': 'rom_group_%d' % {40: 31, 143: 50, 103: 52, 122: 54}[lid]}
    line = '  %s:\n    %s: %s' % (ev, name, json.dumps(opts).replace('"', ''))
    if r['started_by']: line += '   # ' + r['started_by'][:150]
    out.append(line + '\n')
    if loop:
        out.append('  %s_stop:\n    %s:\n      action: stop\n' % (ev, name))
txt = ''.join(out)
fn = P + '/config/lamp_effects.yaml'
if not os.path.exists(fn) or open(fn).read() != txt: open(fn, 'w').write(txt); CHANGED.add('config/lamp_effects.yaml')

# ---- shaker ----
sh_rows = []
for s, msv in SHAKER_MS.items():
    fn = SH + '/shaker_strength_%d.yaml' % s
    txt = ('#show_version=6\n# Shaker motor (coil 8) run, ROM strength %d: about %d ms on (measured in emulation;\n'
           '# the ROM asks for %d units from table 0x040d3998). A new run only replaces a shorter one in the ROM.\n'
           % (s, msv, {1: 200, 2: 384, 3: 1024}[s]))
    txt += yaml.safe_dump([{'duration': '%dms' % msv, 'coils': {'c_shaker_motor_optional': {'action': 'enable'}}},
                           {'duration': '10ms', 'coils': {'c_shaker_motor_optional': {'action': 'disable'}}}], sort_keys=False)
    if not os.path.exists(fn) or open(fn).read() != txt: open(fn, 'w').write(txt); CHANGED.add('config/shows/' + os.path.basename(fn))
sp = {}
for r in csv.reader(open(P + '/config/show_player.yaml')): pass
ev_of = {}
for m in re.finditer(r'\n  (\S+): (deff_(\d{3})_\S+)', open(P + '/config/show_player.yaml').read()):
    if m.group(1).endswith('_as_captured'): continue
    ev_of.setdefault(int(m.group(3)), m.group(1))
for m in re.finditer(r'\n  (\S+):\n    random_events', open(P + '/config/dmd_variants.yaml').read() if os.path.exists(P + '/config/dmd_variants.yaml') else ''):
    pass
out = [H, "# Shaker motor. The ROM runs it from display effects (and two switch handlers) with\n"
       "# shaker_run(strength, min_setting): only when setting shaker_motor (adjustment 86: 0 off, 1-3) is\n"
       "# at least min_setting, never while tilted or in game over (gf_state & 0x310). Strength 1/2/3 is\n"
       "# about 75/265/1100 ms of motor. Conditions use the machine setting from settings.yaml.\n"
       "show_player:\n"]
done = set()
for d in sorted(shk):
    for s, mn in shk[d]:
        ev = ev_of.get(d) or ('tron_' + deff_name[d][9:] if d in deff_name else None)
        key = (ev, s, mn)
        if not ev or key in done: continue
        done.add(key)
        out.append('  %s{settings.shaker_motor>=%d}: shaker_strength_%d   # effect %d %s\n' % (ev, mn, s, d, deff_name.get(d, '')))
        sh_rows.append((d, s, mn, ev))
    if not (ev_of.get(d) or d in deff_name):
        out.append('  # effect %d %s: shaker_run%s, no MPF event for this effect yet\n' % (d, deff_name.get(d, ''), shk[d]))
out.append("  # Switch handlers (post these from your code):\n"
           "  tron_shaker_drop_target{settings.shaker_motor>=3}: shaker_strength_1   # drop target bank hit (vtable fn 0x0100b148), not while tilted\n"
           "  tron_shaker_zuse_score{settings.shaker_motor>=3}: shaker_strength_1    # every ZUSE Fast Scoring hit (zfs_score_hit)\n")
txt = ''.join(out)
fn = P + '/config/shaker.yaml'
if not os.path.exists(fn) or open(fn).read() != txt: open(fn, 'w').write(txt); CHANGED.add('config/shaker.yaml')
json.dump({str(k): v for k, v in wired.items()}, open(L + '/wired.json', 'w'))
json.dump(sorted(CHANGED), open(L + '/changed_all.json', 'w'))
print(len(wired), 'effects wired;', len(sh_rows), 'shaker entries;', len(CHANGED), 'changed files')
