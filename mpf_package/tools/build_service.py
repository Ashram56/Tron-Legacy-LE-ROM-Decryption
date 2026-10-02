# Service menu, operator adjustments and audits from the ROM -> config/settings.yaml,
# service_menu.md and service_menu.json in the MPF package.
import struct, json, re, csv, collections
exec(open('/mnt/project-files/tron/rules/tools/ghidra/romtables.py').read())
P = '/mnt/project-files/tron/mpf_package'
RAM = open('/home/claude/svc/ram20.bin', 'rb').read()
def r16(a): return struct.unpack_from('<H', RAM, a - 0x36000)[0]
def r32(a): return struct.unpack_from('<I', RAM, a - 0x36000)[0]
def mem16(a):
    return r16(a) if a >= 0x36000 else u16(a)

# ---------- adjustments ----------
fmt = collections.defaultdict(dict)
for line in open('/home/claude/svc/fmt_out.tsv'):
    i, fn, v, s = line.rstrip('\n').split('\t'); fmt[int(i)][int(v)] = s
def msglist(arg):
    out = []; a = arg
    while True:
        m = mem16(a)
        if not m: break
        out.append(msg(m)); a += 2
    return out
std_order = []
a = 0x39558
while r16(a): std_order.append(r16(a)); a += 2
adjs = []
for i in range(1, 89):
    w = struct.unpack_from('<8i', ROM, foff(0x040de218 + i * 32))
    _, d, mn, mx, step, _, namep, ty = w
    t = ty & 0xffff
    fn, arg = struct.unpack_from('<II', ROM, foff(0x040dd890 + t * 8))
    vals = list(range(mn, mx + 1, step))
    labels = {}
    if fn == 0 and arg:
        lst = msglist(arg)
        for k, v in enumerate(vals):
            labels[v] = lst[v] if 0 <= v < len(lst) else str(v)
    else:
        f = fmt.get(i, {})
        for v in vals:
            if v in f: labels[v] = f[v]
            elif t == 0x19: labels[v] = '{:,}'.format(v)
            else: labels[v] = str(v)
    group = 'feature' if i >= 65 else 'standard'
    adjs.append(dict(id=i, name=cstr(u32(namep)), default=d, min=mn, max=mx, step=step, display_type=t,
                     group=group, labels=labels, menu_order=(std_order.index(i) if i in std_order else 1000 + i)))

def setting_key(a):
    k = re.sub(r'[^a-z0-9]+', '_', a['name'].lower()).strip('_')
    if a['id'] in (87, 88): k += '_trim'
    k = {86: 'shaker_motor', 83: 'end_of_line_mb_letters_first', 84: 'end_of_line_mb_letters_later', 70: 'disc_mb_restart_timer',
         71: 'disc_mb_restart_autofire_timer'}.get(a['id'], k)
    return k
USED = {26: 'game_flow, flynns_arcade', 27: 'game_flow, flynns_arcade', 31: 'game_flow', 32: 'game_flow', 38: 'game_flow',
        42: 'flynns_arcade', 65: 'switches_and_shots', 66: 'zuse_fast_scoring', 67: 'recognizer_and_disc_battle',
        68: 'disc_multiball', 69: 'disc_multiball', 70: 'disc_multiball', 71: 'disc_multiball', 72: 'tron_targets',
        73: 'tron_targets', 74: 'tron_targets', 76: 'recognizer_and_disc_battle', 77: 'disc_multiball', 79: 'skill_shots',
        80: 'tron_targets', 81: 'recognizer_and_disc_battle', 83: 'end_of_line_multiball', 84: 'end_of_line_multiball',
        85: 'end_of_line_multiball', 86: 'shaker (config/shaker.yaml)', 7: 'language', 75: 'display effects (abort on flipper)',
        82: 'speech (insult callouts)'}

def thin(vals, d):
    """MPF settings need a list of values; keep the ROM's step up to 150 values, else a coarser ladder."""
    if len(vals) <= 150: return vals
    keep = set(vals[:20]) | {d, vals[-1]}
    n = len(vals); stride = max(1, n // 120)
    keep |= set(vals[::stride])
    return sorted(keep)

out = ['# Generated from the Stern Tron Legacy LE v1.74 ROM (trn_174h). See ../service_menu.md.\n'
       '# All 88 operator adjustments, as MPF machine settings. Keys are the ROM names in snake case.\n'
       '# setting_type: standard = the ROM\'s STANDARD ADJUSTMENTS menu, feature = FEATURE ADJUSTMENTS (Tron).\n'
       '# sort is the ROM menu order. Labels are what the ROM shows for each value (English).\n'
       '# Settings with very long ranges (scores, IDs) list a coarser ladder; the ROM range is in the comment.\n'
       'settings:\n']
for a in sorted(adjs, key=lambda x: x['menu_order']):
    vals = thin(sorted(a['labels']), a['default'])
    k = setting_key(a)
    out.append('  %s:   # adj %d, ROM range %s..%s step %s%s\n' % (k, a['id'], a['min'], a['max'], a['step'],
               ('; used by ' + USED[a['id']]) if a['id'] in USED else ''))
    out.append('    label: %s\n' % json.dumps(a['name']))
    out.append('    values:\n')
    for v in vals: out.append('      %d: %s\n' % (v, json.dumps(a['labels'][v])))
    out.append('    default: %d\n    key_type: int\n    sort: %d\n    setting_type: %s\n' % (a['default'], (a['menu_order'] + 1) * 10 if a['group'] == 'standard' else 1000 + a['id'] * 10, a['group']))
open(P + '/config/settings.yaml', 'w').write(''.join(out))

# ---------- audits ----------
auds = []
for i in range(1, 151):
    w = struct.unpack_from('<4I', ROM, foff(0x040e022c + i * 16))
    nm = cstr(u32(w[2])) if foff(w[2]) is not None else None
    grp = 'earnings' if i <= 13 else ('standard' if i <= 72 else 'feature (Tron)')
    auds.append(dict(id=i, name=nm, menu=grp, counter=w[3] >> 16, computed=bool(w[1])))

# ---------- menu tree ----------
items = {}
for k in range(1, 0x86):
    vis, act, scr, m, ic, sub = struct.unpack_from('<IIIHHI', ROM, 0x0f4574 + 20 * k)
    kind = {0x103dad0: 'submenu', 0x103db70: 'back', 0x103dbb8: 'exit', 0x103db6c: 'help'}.get(act, 'screen' if scr else 'action')
    items[k] = dict(item=k, text=msg(m), kind=kind, submenu=sub if kind == 'submenu' else None,
                    shown_only_if=('0x%x' % vis) if vis else None, screen_fn=('0x%x' % scr) if scr else None)
menus = {}
for k in range(0x12):
    a_, b_, p_ = struct.unpack_from('<3I', ROM, 0x0f5108 + 12 * k)
    ids = []
    if foff(p_) is not None:
        q = p_
        while u16(q): ids.append(u16(q)); q += 2
    menus[k] = ids
# the game adds its own items to these menus through event 0x5d (inferred from the item names)
menus[8] = menus[8][:2] + [124] + menus[8][2:]          # FEATURE AUDITS after STANDARD AUDITS
menus[9] = menus[9][:1] + [125] + menus[9][1:]          # FEATURE ADJUSTMENTS after STANDARD ADJUSTMENTS
menus[2] = menus[2][:13] + [126] + menus[2][13:]        # GAME-SPECIFIC TESTS
MENU_NAMES = {1: 'MAIN MENU', 2: 'DIAGNOSTICS', 3: 'SWITCH MENU', 4: 'COIL MENU', 5: 'LAMP MENU', 6: 'FLASH LAMPS MENU',
              7: 'DR. PINBALL', 8: 'AUDITS', 9: 'ADJUSTMENTS', 10: 'UTILITIES', 11: 'INSTALLS', 12: 'RESETS', 13: 'SERIAL',
              14: 'USB', 15: 'TOURNAMENT', 16: 'REDEMPTION', 17: 'GAME-SPECIFIC TESTS'}
# installs presets: (os list, game list) addresses from the install screens
PRESETS = {71: (0x394a8, 0x36f7c), 72: (0x394a0, 0x36f84), 73: (0x394d0, 0x36f8c), 74: (0x394b8, 0x36f94), 75: (0x394b0, 0x36f9c),
           76: (0x39498, 0x36fa4), 77: (0x394c0, 0x394c8), 102: (0x39248, 0x36fac), 103: (0x39258, 0x36fb4), 106: (0x39268, 0x392c0),
           104: (0x392c8, 0x39310), 105: (0x39318, 0x39370)}
adj_by = {a['id']: a for a in adjs}
def plist(addr):
    out = []; q = addr
    while r32(q) & 0xffff:
        i_, v_ = r32(q) & 0xffff, struct.unpack_from('<i', RAM, q + 4 - 0x36000)[0]
        a_ = adj_by.get(i_); out.append(dict(adj=i_, name=a_['name'] if a_ else '?', value=v_, label=a_['labels'].get(v_, str(v_)) if a_ else str(v_)))
        q += 8
    return out
presets = {}
for it, (o, g) in PRESETS.items():
    presets[items[it]['text']] = plist(o) + plist(g)

json.dump(dict(menus={MENU_NAMES.get(k, str(k)): [items[i] for i in v] for k, v in menus.items() if v},
               adjustments=adjs, audits=auds, install_presets=presets), open(P + '/service_menu.json', 'w'), indent=1)

# ---------- markdown ----------
def esc(s): return (s or '').replace('|', '/')
md = ['# Tron Legacy LE v1.74: service menu, adjustments and audits\n',
      'Read from the ROM (`trn_174h`). The menu tree, item texts, adjustment table (88 entries), value\n'
      'labels and audit names come from the ROM\'s own tables; the value labels were produced by running the\n'
      'ROM\'s own formatting code in the emulator. Your MPF service mode can look different, but it should\n'
      'offer the same options. `config/settings.yaml` has every adjustment as an MPF setting.\n',
      '\n## Buttons\n\nThe coin door has four service buttons: BACK, MINUS, PLUS and SELECT (SAM dedicated switches).\n'
      'SELECT enters the menu from attract mode and opens an item, MINUS/PLUS move or change a value, BACK leaves.\n'
      'Every menu ends with a return item, EXIT SERVICE MENU and DISPLAY HELP SCREEN.\n',
      '\n## Menu tree\n\nItems marked *(Tron)* are added by the game code; the rest are the Stern SAM operating system.\n'
      'Items marked *(only when …)* are hidden unless that feature is on.\n']
def walk(k, depth, seen):
    for i in menus.get(k, []):
        it = items[i]
        if it['kind'] in ('back', 'exit', 'help'): continue
        tag = ' *(Tron)*' if i >= 124 else ''
        if it['shown_only_if']: tag += ' *(only when %s)*' % {98: 'a redemption system is installed or the ticket dispenser is on',
                                                                     99: 'tournament mode is available', 14: 'errors were logged',
                                                                     37: 'enabled', 110: 'no tournament runs', 111: 'a tournament runs',
                                                                     112: 'tournament data exists'}.get(i, 'enabled')
        md.append('%s- %s%s\n' % ('  ' * depth, it['text'], tag))
        if it['kind'] == 'submenu' and it['submenu'] and it['submenu'] not in seen:
            walk(it['submenu'], depth + 1, seen | {it['submenu']})
        if it['text'] == 'STANDARD ADJUSTMENTS': md.append('%s  - adjustments 1-64, listed below\n' % ('  ' * depth))
        if it['text'] == 'FEATURE ADJUSTMENTS': md.append('%s  - adjustments 65-88, listed below\n' % ('  ' * depth))
        if it['text'] == 'EARNINGS AUDITS': md.append('%s  - audits 1-13\n' % ('  ' * depth))
        if it['text'] == 'STANDARD AUDITS': md.append('%s  - audits 14-72\n' % ('  ' * depth))
        if it['text'] == 'FEATURE AUDITS': md.append('%s  - audits 73-150\n' % ('  ' * depth))
walk(1, 0, {1})
md.append('\nNotes:\n- GO TO FUSE TABLE, SINGLE SWITCH TEST and the three FLOW CHART items open help pages, not a menu.\n'
          '- ORDERED LAMP TEST (item 37) exists in the ROM but is not in the lamp menu list, so it cannot be reached in v1.74.\n'
          '- GAME-SPECIFIC TESTS, FEATURE AUDITS and FEATURE ADJUSTMENTS are inserted by the game at run time; their position in the menu is inferred.\n'
          '- The four lamp tests drive the ROM lamp effects 3 to 7 (`lampfx_003`-`lampfx_007`); BEGIN BURN-IN uses lamp effect 8.\n'
          '- FIBER OPTIC LIGHT TUBE TEST cycles the two ramp tubes through their colours (ROM function 0x1012b50).\n')
md.append('\n## Adjustments\n\n`setting` is the key in `config/settings.yaml`. Values: the ROM label for each value, '
          '"a..b" for a plain number range.\n\n| # | Name | Menu | Default | Values | Setting | Used by |\n|---|---|---|---|---|---|---|\n')
for a in sorted(adjs, key=lambda x: (x['group'] != 'standard', x['menu_order'])):
    labs = a['labels']; ks = sorted(labs)
    plain = all(labs[v] == str(v) or labs[v] == '{:,}'.format(v) for v in ks)
    if plain or len(ks) > 12:
        vs = '%s..%s step %s' % (labs[ks[0]], labs[ks[-1]], '{:,}'.format(a['step'])) if len(ks) > 1 else labs[ks[0]]
        if not plain: vs += ' (e.g. %s)' % ', '.join(labs[v] for v in ks[:4])
    else:
        vs = ', '.join('%d=%s' % (v, labs[v]) for v in ks)
    md.append('| %d | %s | %s | %s | %s | `%s` | %s |\n' % (a['id'], esc(a['name']), a['group'], esc(labs.get(a['default'], str(a['default']))),
                                                         esc(vs), setting_key(a), USED.get(a['id'], '')))
md.append('\n## Install presets\n\nINSTALL items (UTILITIES > GO TO INSTALLS MENU) set several adjustments at once. '
          'Lists read from emulator RAM after boot. In v1.74 the difficulty presets (EXTRA EASY to EXTRA HARD, '
          'DIRECTOR\'S CUT) change nothing: both their OS and game lists are empty. INSTALL FACTORY resets every '
          'adjustment to its default.\n\n')
for k, v in presets.items():
    md.append('- **%s**: %s\n' % (k, ', '.join('%s = %s' % (x['name'], x['label']) for x in v) if v else 'no changes'))
md.append('\n## Audits\n\n| # | Name | Menu |\n|---|---|---|\n')
for a in auds: md.append('| %d | %s | %s |\n' % (a['id'], esc(a['name']), a['menu']))
open(P + '/service_menu.md', 'w').write(''.join(md))
print(len(adjs), 'adjustments', len(auds), 'audits', sum(len(v) for v in menus.values()), 'menu items')
