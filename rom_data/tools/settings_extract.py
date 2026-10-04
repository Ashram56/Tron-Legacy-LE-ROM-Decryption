"""Build rom_data/settings/* (pricing, audits, adjustments, presets, service texts) from the Tron LE 1.74 ROM.

Inputs:  the ROM (rom.py), code/tron_game_decompiled_v2.c (function bodies, for call sites and text calls),
         rom_data/settings/emu/*.log (emulator runs of rom_data/tools/settings_emu.cpp, for `observed` facts).
Run:     python3 rom_data/tools/settings_extract.py
Every fact carries `tag` = code (read from code/tables), observed (seen in the emulator logs) or inferred.
"""
import bisect, collections, csv, json, os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rom import ROM, foff, u8, u16, u32, s32, cstr, msg, hx, disasm, find_bl_callers  # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, 'rom_data', 'settings')
EMU = os.path.join(OUT, 'emu')
DECOMP = os.path.join(REPO, 'code', 'tron_game_decompiled_v2.c')

# ---------------------------------------------------------------- OS / table addresses (code)
ADJ_TAB, ADJ_N = 0x040de218, 88          # 32 B; count 0x59 incl. entry 0 in table-of-tables 0x36c0c
ADJ_FMT = 0x040dd890                     # 8 B {fn, u16 msg list ptr}; 0x26 entries (0x36c00)
AUD_TAB, AUD_N = 0x040e0230, 150         # 16 B; 0x97 entries incl. 0 (0x36c30)
AUD_FMT = 0x040df3ec                     # 7 display-type formatters (0x36c24)
CNT_TAB = 0x040ded38                     # 12 B counters {nvram rec ptr, ?, flags}; 0x8f entries (0x36c18)
CREDSYS = 0x040e0bd8                     # credit system #1 (0x40e0bb0 + 1*0x28; 0x36c3c count 2)
PRICE_PTRS = 0x38078                     # RAM: u32[65] pricing record pointers, index = adj 28 value
COUNTRY_TAB = 0x040e17e0                 # 32 B x 28 (0x36c60)
ITEMS, MENUS = 0x040f4574, 0x040f5108    # 20 B x 0x86 (0x36df8), 12 B x 0x12 (0x36e04)
HS_TAB = 0x040e21fc                      # high-score table 0x20 B x 6 (0x36cc0)
F = dict(adj_get=0xe90, adj_default=0xf28, adj_set=0xf8c, adj_reset=0x1080, adj_apply_list=0x10e8,
         adj_list_installed=0x1118, adj_factory_all=0x1278, country_override=0x5f2c, adj_visible=0x34124,
         audit_add=0x178c, counter_get=0x164c, audit_value=0x1bc4, msg_get=0xa58c)


def mem32(a): return u32(a)
def mem16(a): return u16(a)


def msglist(a):
    out = []
    while mem16(a):
        out.append(mem16(a)); a += 2
    return out


def namep(p):
    """Per-language name pointer -> English string."""
    try:
        return cstr(u32(p))
    except Exception:
        return None


def wcsv(name, rows, cols):
    with open(os.path.join(OUT, name), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if r.get(k) is None else r.get(k)) for k in cols})
    print('wrote', name, len(rows))


# ---------------------------------------------------------------- decompile index
SRC = open(DECOMP).read().split('\n')
HEADS = []
for i, l in enumerate(SRC):
    m = re.match(r'// ==== ([0-9a-f]{8}) (\S+)', l)
    if m:
        HEADS.append((i, int(m.group(1), 16), m.group(2)))
H_START = sorted(a for _, a, _ in HEADS)
H_NAME = {a: n for _, a, n in HEADS}
H_LINE = {a: i for i, a, _ in HEADS}
H_BYNAME = {n: a for _, a, n in HEADS}
_lines = [i for i, _, _ in HEADS]


def func_of(a):
    k = bisect.bisect_right(H_START, a) - 1
    return H_START[k] if k >= 0 else None


def body(fa):
    i = H_LINE[fa]
    k = bisect.bisect_right(_lines, i)
    end = _lines[k] if k < len(_lines) else len(SRC)
    return SRC[i:end]


def fname(a):
    return H_NAME.get(a, 'FUN_%08x' % a)


# ---------------------------------------------------------------- emulator logs
def emu_lines(name):
    p = os.path.join(EMU, name)
    return open(p).read().split('\n') if os.path.exists(p) else []


def r0_const(site):
    """Constant in r0 before a BL, from the instructions before it (None when computed)."""
    ins = [i for i in disasm(site - 64, size=64) if i.address < site]
    add = 0
    for i in reversed(ins):
        ops, mn = i.op_str, i.mnemonic
        if not ops.startswith('r0,'):
            continue
        if mn == 'mov' and '#' in ops:
            return int(ops.split('#')[1], 0) + add
        if mn == 'add' and ops.startswith('r0, r0, #'):
            add += int(ops.split('#')[1], 0); continue
        if mn == 'ldr' and '[pc, #' in ops:
            return u32(i.address + 8 + int(ops.split('#')[1].rstrip(']'), 16)) + add
        return None
    return None


# ================================================================ adjustments
def adj_record(i):
    a = ADJ_TAB + 32 * i
    nv, d, mn, mx, step, f14, np_, ty = struct.unpack_from('<IiiiiIIi', ROM, foff(a))
    return dict(id=i, rec=a, nvram=nv, default=d, min=mn, max=mx, step=step, f14=f14, name=namep(np_),
                display_type=ty & 0xffff, nowrap=(ty >> 16) & 1)


def formatter_labels():
    """Labels per adjustment value: msg lists from the ROM, function formatters from emu/t8.log."""
    fnout = collections.defaultdict(dict)
    for l in emu_lines('t8.log'):
        m = re.match(r'[\d.]+ callstr 0x([0-9a-f]+)\(\d+,(-?\d+),', l)
        if m:
            s = l.split(' = ', 1)[1]
            txt = s[s.index('"') + 1:s.rindex('"')]
            fnout[int(m.group(1), 16)][int(m.group(2))] = txt.replace('|', '\n')
    out = {}
    for i in range(1, ADJ_N + 1):
        r = adj_record(i)
        fn, arg = struct.unpack_from('<II', ROM, foff(ADJ_FMT + 8 * r['display_type']))
        vals = list(range(r['min'], r['max'] + 1, r['step']))
        labels, tag = {}, 'code'
        if fn == 0 and arg:
            lst = msglist(arg)
            for v in vals:
                labels[v] = msg(lst[v]) if 0 <= v < len(lst) else str(v)
            src = 'msg list %s (%s)' % (hx(arg), ','.join(hx(x) for x in lst))
        else:
            got = fnout.get(fn, {})
            for v in vals:
                if v in got:
                    labels[v] = got[v]
            tag = 'observed' if got else 'missing'
            src = 'formatter fn %s run in the emulator (emu/t8.log)%s' % (
                hx(fn), '' if len(labels) == len(vals) else '; %d of %d values sampled' % (len(labels), len(vals)))
        out[i] = dict(fn=fn, arg=arg, labels=labels, src=src, tag=tag)
    return out


# country presets
def plist(a):
    out = []
    while a and u32(a) & 0xffff:
        out.append((u32(a) & 0xffff, s32(a + 4))); a += 8
    return out


def countries():
    rows = []
    for c in range(28):
        a = COUNTRY_TAB + 32 * c
        w = struct.unpack_from('<IIIIIHHHHI', ROM, foff(a))
        rows.append(dict(code=c, rec=a, name=msg(w[5]), os_list=w[1], game_list=w[2], cec_msgs=w[3],
                         redemption_defaults=w[4], os=plist(w[1]), game=plist(w[2])))
    return rows


# visibility rules from adj_visible 0x34124 (disassembled jump table at 0x34148)
VISIBLE = {12: 'REPLAY TYPE (11) is DYNAMIC or AUTO', 13: 'REPLAY TYPE (11) is FIXED or AUTO (case 13 falls through into case 14 at 0x3423c)',
           14: 'REPLAY TYPE (11) is FIXED or AUTO', 15: 'REPLAY TYPE (11) is AUTO', 16: 'REPLAY TYPE (11) is DYNAMIC',
           17: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 1', 18: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 2',
           19: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 3', 20: 'REPLAY TYPE (11) is FIXED and REPLAY LEVELS (14) >= 4',
           21: 'REPLAY TYPE (11) is FIXED or AUTO', 23: 'SPECIAL LIMIT (22) != 0', 24: 'SPECIAL LIMIT (22) != 0',
           27: 'EXTRA BALL LIMIT (26) != 0', 29: 'MATCH PERCENTAGE (30) != OFF'}
for _k in range(49, 62):
    VISIBLE[_k] = 'ALLOW HIGH SCORES (48) != 0'

# what each adj_get call site does (code; from the decompile at that address)
SITE_NOTE = {
    0xa264: 'player language select: when YES, start-of-game language choice is offered (0xa288 counts languages)',
    0xa300: 'sets the active display language at game start (falls back to factory default, then 0x2d39c)',
    0xa3d0: 'language_get: current language for msg_get when no override (RAM 0x372a0 == 5)',
    0xd774: 'date/time text: 12-hour (AM/PM) or 24-hour clock', 0xd840: 'date/time editor: 12/24-hour display',
    0x19ad0: 'ball_save_arm: 0 = no ball save, else start ball_save_task with this time',
    0x19ea4: 'competition mode (or game flag 0xf): returns 1 = competition rules (no random awards)',
    0x19eec: 'player competition: in a game (gf_state&0x118==0x10) and YES -> allow buy-in/competition prompt',
    0x1a04c: 'extra ball award: refused if player tilted (0x252a0) or player EB count >= limit (0 = none, 10 = unlimited)',
    0x1a460: 'HSTD reset count: reload the games-until-reset counter (NVRAM 0x2110800)',
    0x1a4f8: 'HSTD reset count: 0 = OFF; else count down per game and reset high scores at 0',
    0x1a508: 'allow high scores: when not YES skip high-score processing', 0x1a6b4: 'allow high scores: predicate',
    0x1a748: 'HSTD initials: 3 initials vs 10-letter name when storing an entry', 0x1af84: 'high_score_entry: 3 or 10 characters to enter',
    0x1b390: 'Q24 option stored for the award knocker/meter output (coin meter, token dispenser or knocker)',
    0x1b4b8: 'knocker volume: 0 = off, else knocker strength', 0x1b678: 'match: OFF (11) disables match, else percentage',
    0x1b8b8: 'match_award: 0 credit, 1 ticket, 2 token', 0x1e62c: 'timed plunger: 0 = off, else auto-plunge after N seconds',
    0x1ea34: 'coin-door ball saver: when YES and door open, drains are saved',
    0x1f7b4: 'lost ball recovery: when YES the OS re-feeds a lost ball (0x1e080)',
    0x20f28: 'start button during a game: GAME RESTART YES allows a restart by holding start',
    0x213e0: 'balls per game (getter used everywhere)', 0x22818: 'dynamic replay: reset dynamic start score (NVRAM 0x2102f8c)',
    0x229c0: 'replay score: levels beyond REPLAY LEVELS give no replay', 0x229d0: 'replay score: branch on replay type',
    0x229f8: 'replay score (AUTO): level n = n x AUTO REPLAY START (x boost)', 0x22a04: 'replay boost: add boost count x score',
    0x22a64: 'replay boost: add boost count x score', 0x22b80: 'replay award text: msg 0x301 + REPLAY AWARD',
    0x22d74: 'replay_award: 0 credit, 1 ticket, 3 extra ball', 0x22e04: 'replay_award: DYNAMIC raises the dynamic level',
    0x22e28: 'replay_award (DYNAMIC): add DYNAMIC REPLAY START to the dynamic level', 0x23054: 'auto replay percentage adjust (target %)',
    0x23280: 'auto/dynamic replay adjust at game end', 0x2328c: 'auto/dynamic replay percentage',
    0x23f8c: 'special allowed: refused when tilted or player specials >= SPECIAL LIMIT',
    0x240e0: 'special_award: 0 credit, 1 ticket, 2 token, 3 points, 4 extra ball',
    0x2435c: 'tilt: coin door open + COIN DOOR DISABLE TILT YES ignores tilt', 0x243b4: 'tilt_warning: warnings before tilt',
    0x25918: 'balls per game (end-of-ball/game check)', 0x2dcf4: 'flipper ball launch: which flipper launches the ball',
    0x2dd04: 'flipper ball launch', 0x2dde0: 'flipper ball launch',
    0x34214: 'adjustment menu visibility (adj 12)', 0x34230: 'visibility (adj 13)', 0x34240: 'visibility (adj 13/14)',
    0x34258: 'visibility (adj 15)', 0x34270: 'visibility (adj 16)', 0x34288: 'visibility (adj 17-20)', 0x342a8: 'visibility (adj 17-20)',
    0x342c0: 'visibility (adj 21)', 0x342ec: 'visibility (adj 29)', 0x34300: 'visibility (adj 23/24 by 22, 27 by 26, 49-61 by 48)',
    0x10002e8: 'attract: show the custom message when CUSTOM MESSAGE = ON',
    0x1000a10: 'bonus/extra-ball percentage control (compare recent EB % with EXTRA BALL PERCENTAGE)',
    0x100425c: 'End of Line: light extra ball at the configured EOL multiball count',
    0x10043e4: 'End of Line letters ramp: EOL extra ball setting', 0x1004414: 'End of Line letters needed (1st multiball)',
    0x1004420: 'End of Line letters needed (2nd+ multiball)', 0x10064b0: 'disc motor disabled predicate',
    0x1007080: 'Disc multiball: disc shots needed', 0x10070c4: 'Disc multiball: Recognizer shots needed',
    0x10076a8: 'Disc MB restart window timer (NONE = no restart)', 0x1007844: 'Disc MB restart autofire time (0 = none)',
    0x100c5ac: 'TRON award timer: double scoring seconds', 0x100c5d0: 'TRON award timer: bumpers seconds',
    0x100c5f4: 'TRON award timer: spinners seconds', 0x100d378: 'refill double scoring time', 0x100d3bc: 'refill bumpers time',
    0x100d400: 'refill spinners time', 0x100e30c: "Flynn's Arcade: extra ball weight vs EXTRA BALL PERCENTAGE",
    0x100e384: "Flynn's Arcade: special weight vs SPECIAL PERCENTAGE", 0x100fbfc: 'flipper aborts animations: NONE/ONE/ALL',
    0x100fdc4: 'abort animations', 0x10127d8: 'outlane insult speech when INSULT LEVEL > 0',
    0x101c24c: 'pop bumper hits for next level = (difficulty + levels done) x 5 + 20',
    0x101fdb8: 'Recognizer difficulty copied per player at game start', 0x102374c: 'replay award text: msg 0x526 + REPLAY AWARD',
    0x10289cc: 'shaker_run: run only when SHAKER MOTOR != NONE and >= min_setting', 0x1029180: 'skill shot on serve: plunge post disabled -> alternate skill shot',
    0x102a3b0: 'shooter lane: raise plunge post unless disabled', 0x10318f0: 'Zuse fast scoring timer start value',
    0x1031adc: 'Zuse fast scoring add time', 0x1037048: 'deff_005 (boot): FAST BOOT skips the long boot checks',
}
# adj_get call sites whose id comes from a data structure (code + observed in emu/t2,t3 logs)
STRUCT_SITES = {
    0x48c8: ([33], 'credits_add 0x4890: credit system +0x1e = adj 33; caps credits at CREDIT LIMIT'),
    0x49ac: ([28], 'pricing_current 0x4990/0x498c: credit system +0x18 = adj 28; selects the pricing record'),
    0x4ab8: ([62], 'coin task 0x4a50: credit system +0x1a = adj 62; wait N ticks re-checking the coin lockout, 61 = OFF (no wait)'),
    0x4fdc: ([34], 'free_play 0x4fb4: credit system +0x1c = adj 34; YES -> "FREE PLAY", starts need no credit'),
    0xa744: ([44], 'meter_add 0xa6f0: meter table 0x40e2130 +0xc = adj 44; software coin meter counts only when Q24 OPTION = COIN METER'),
    0x17c38: ([81], 'device disable predicate 0x17c20 (device struct +0x1a); observed id 81 DISABLE RECOGNIZER MOTOR'),
    0x19178: ([76], 'device disable predicate 0x19160 (struct +0x16); observed id 76 DISABLE RECOGNIZER 3-BANK MOTOR'),
    0x1a780: ([49, 50, 51, 52, 53], 'HS entry save 0x1a728: HS table 0x40e21fc +0x1a (adj 49-53) stored with the entry as its reset score'),
    0x1ac4c: ([55, 56, 57, 58, 59], 'HS award 0x1abfc: HS table +0x1e = number of awards for that place'),
    0x1ac5c: ([54], 'HS award 0x1abfc: HS table +0x1c = HIGH SCORE AWARD (0 credit, 1 ticket)'),
    0x22a58: ([17, 18, 19, 20], 'replay score 0x22998 (FIXED): adj 16+level = REPLAY LEVEL #n'),
    0x100aad0: ([78], 'post/device predicate 0x100aac8 (struct +2); observed id 78 DISABLE ORBIT UP-POST'),
    0x100b928: ([80], 'drop target predicate 0x100b910 (struct +0x12); observed id 80 DISABLE DROP TARGETS'),
    0x100f0f4: ([87, 88], 'sound call volume trim 0x100f0cc: music class -> adj 87, speech class -> adj 88'),
    0x1064: ([], 'adj_set 0xf8c: read back after write (all ids)'), 0x10cc: ([], 'adj_reset 0x1080: compare with default (all ids)'),
    0x1154: ([], 'install preset check 0x1118: compares current values with a preset list'),
    0x11b8: ([], 'install preset check 0x1118'),
    0x103de4c: ([], 'adjustment menu 0x103dd00: value shown'), 0x103e26c: ([], 'adjustment menu: value after SELECT'),
    0x103e3c0: ([], 'adjustment menu: next item'), 0x103e4b4: ([], 'adjustment menu: previous item'),
    0x103e55c: ([], 'adjustment menu: BACK restores the stored value'),
}


def adj_readers():
    rows = []
    obs = collections.Counter()
    for fn in ('t2_adj_get_counts.txt',):
        for l in emu_lines(fn):
            m = re.match(r'\s*(\d+) id=(\d+) lr=0x([0-9a-f]+)', l)
            if m:
                obs[(int(m.group(2)), int(m.group(3), 16) - 4)] += int(m.group(1))
    for l in emu_lines('t3.log'):
        m = re.search(r'adj_get id=(\d+) lr=0x([0-9a-f]+)', l)
        if m:
            obs[(int(m.group(1)), int(m.group(2), 16) - 4)] += 1
    for site, isbl in find_bl_callers(F['adj_get']):
        fa = func_of(site)
        c = r0_const(site)
        if c is not None and 1 <= c <= ADJ_N:
            ids, how = [c], 'r0 constant'
            note = SITE_NOTE.get(site, '')
        else:
            ids, note = STRUCT_SITES.get(site, ([], 'computed id (not resolved)'))
            how = 'from data structure' if ids else 'any id (generic code)'
        seen = [i for i in (ids or range(1, ADJ_N + 1)) if obs.get((i, site))]
        for i in (ids or [None]):
            rows.append(dict(adj=i if i else 'any', accessor='adj_get 0xe90', site=hx(site), call='bl' if isbl else 'b',
                             function=hx(fa) if fa else '', function_name=fname(fa) if fa else '', id_source=how,
                             what=note, tag='observed' if (i and obs.get((i, site))) else 'code',
                             observed_calls=obs.get((i, site), '') if i else (','.join(map(str, seen)) if seen else '')))
    # the other accessors (generic, all ids)
    for nm in ('adj_default', 'adj_set', 'adj_reset', 'adj_apply_list', 'adj_list_installed', 'country_override'):
        for site, isbl in find_bl_callers(F[nm]):
            fa = func_of(site)
            c = r0_const(site)
            rows.append(dict(adj=c if c and 1 <= c <= ADJ_N else 'any', accessor='%s %s' % (nm, hx(F[nm])), site=hx(site),
                             call='bl' if isbl else 'b', function=hx(fa), function_name=fname(fa),
                             id_source='r0 constant' if c and 1 <= c <= ADJ_N else 'any id (generic code)',
                             what={'adj_default': 'factory default = country override (0x5f2c) else table default',
                                   'adj_set': 'write value (event 4 may veto; event 5 after)',
                                   'adj_reset': 'reset one adjustment to its factory default',
                                   'adj_apply_list': 'apply an install-preset (adj,value) list',
                                   'adj_list_installed': 'check whether a preset is installed',
                                   'country_override': 'country/game override lists'}[nm], tag='code'))
    return rows


# ================================================================ pricing
def pricing():
    cs = struct.unpack_from('<6I8H', ROM, foff(CREDSYS))
    credsys = dict(address=hx(CREDSYS), state_nvram=hx(cs[0]), pricing_table_ram=hx(cs[1]), custom_record_nvram=hx(cs[2]),
                   custom_coin_door_nvram=hx(cs[3]), custom_ladder_nvram=hx(cs[4]), slot_audit_list=hx(cs[5]),
                   adj_pricing=cs[6], adj_coin_input_delay=cs[7], adj_free_play=cs[8], adj_credit_limit=cs[9],
                   meter_id=cs[10], units_counter=cs[11], credits_counter=cs[12], lockout_id=cs[13] & 0xff, tag='code')
    slot_counters = msglist(cs[5])
    aud_by_counter = {}
    for a in range(1, AUD_N + 1):
        w = struct.unpack_from('<4I', ROM, foff(AUD_TAB + 16 * a))
        if not w[0]:
            aud_by_counter.setdefault(w[2] >> 16, (a, namep(w[1])))
    key_obs = {}
    for l in emu_lines('t1.log'):
        pass
    slots = []
    keys = {0: 'COIN1 (PinMAME key 3)', 1: 'COIN2 (key 4)', 2: 'COIN3 (key 5)', 3: 'COIN4 (key 6)', 4: None}
    for s, c in enumerate(slot_counters):
        a, nm = aud_by_counter.get(c, (None, None))
        slots.append(dict(slot=s, audit_counter=c, audit=a, audit_name=nm, pinmame_input=keys.get(s),
                          tag='observed' if s < 4 else 'code'))
    summ, names_obs = {}, {}
    lines = emu_lines('t7.log')
    for k in range(0, len(lines)):
        m = re.search(r'callstr 0xac18\(\d+,(\d+),(\d+),(\d+)', lines[k])
        if m:
            summ[(int(m.group(2)))] = lines[k][lines[k].index('"') + 1:lines[k].rindex('"')]
        m = re.search(r'callstr 0x2e0fc\(\d+,(\d+),', lines[k])
        if m:
            names_obs[int(m.group(1))] = lines[k][lines[k].index('"') + 1:lines[k].rindex('"')]
    ctry = countries()
    default_for = collections.defaultdict(list)
    for c in ctry:
        for adj, v in c['os'] + c['game']:
            if adj == 28:
                default_for[v].append(c['name'])
    default_for[62].append('(table default; U.S.A. has no override)')
    presets = []
    for i in range(64):
        p = u32(PRICE_PTRS + 4 * i)
        s, k, lad, n = [u32(p + 4 * j) for j in range(4)]
        m = [u16(p + 16 + 2 * j) for j in range(4)]
        units = []
        q = s
        while u32(q) and len(units) < 10:
            units.append(dict(unit_value=u32(q), slot_units=[u8(q + 4 + j) for j in range(5)], address=hx(q)))
            q += 12
        sel = units[k]
        uv = sel['unit_value']
        ladder = [u8(lad + j) for j in range(n)]
        cum, tot = [], 0
        for j, c in enumerate(ladder):
            tot += c
            if c:
                cum.append(dict(units=j + 1, money=(j + 1) * uv, credits=tot))
        first = cum[0]['units'] if cum else None
        fmt_money = msg(m[2])

        def money(x, f=fmt_money):
            try:
                return f.replace('%,d', '%d') % ((x // 100, x % 100) if f.count('%') >= 2 else (x // 100,))
            except Exception:
                return str(x)
        presets.append(dict(
            adj_value=i, name=msg(m[0]), name_msg=hx(m[0]), record=hx(p), coin_door=hx(s), unit_table=units, unit_index=k,
            unit_value_minor=uv, money_formats=dict(plain=msg(m[1]), short=msg(m[2]), long=msg(m[3]), msg_ids=[hx(x) for x in m[1:]]),
            slot_units=sel['slot_units'], slot_money=[money(x * uv) for x in sel['slot_units']],
            ladder=ladder, ladder_address=hx(lad), ladder_length=n, cycle_money=money(n * uv), cycle_credits=tot,
            awards=[dict(units=c['units'], money=money(c['money']), credits_total=c['credits']) for c in cum],
            first_credit_units=first, first_credit_money=money(first * uv) if first else None,
            service_summary=summ.get(lad), service_summary_tag='observed' if lad in summ else None,
            name_observed=names_obs.get(i), factory_default_for=default_for.get(i, []), tag='code'))
    custom = dict(adj_value=64, name=msg(0x26e), name_msg=hx(0x26e),
                  record='NVRAM %s (0x1a bytes + ~checksum16): {coin-door ptr -> %s (10 x 12 B unit table), unit index, ladder ptr -> %s (<= 100 B), '
                         'ladder length, u16 name msg 0x26e, u16 money formats x3, u8 valid}' % (hx(cs[2]), hx(cs[3]), hx(cs[4])),
                  editor='SET CUSTOM PRICING (item 107, 0x103d8bc -> 0x103d070); also opened from GAME PRICING = CUSTOM (event 6 hook 0x103d8dc)',
                  how='0x52b4 copies the current preset (unit table, unit index, money formats) with an empty ladder; the operator sets, step by step, '
                      'the credits (0-10) given at each unit (shown as "N CREDIT(S) AT: <money>", money = unit_value x step / 100), up to 100 steps; '
                      'INSTALL saves it with 0x53f8 (trailing zero steps are trimmed) and sets adj 28 = 64',
                  factory='empty (0x51e4 clears it): no units table, no ladder -> coins give no credits until it is set up', tag='code')
    algo = r'''credit system #1 = 0x040e0bd8 (table 0x040e0bb0 + id*0x28, id = RAM 0x36f66 = 1)
  state  NVRAM 0x2111008: s32 pos (-1 = start), u8 credits, u8 ~checksum8(5)   [0x482c validates, 0x47f8 resets]
on coin switch (dedicated coin switch -> task_create(0x13, coin_task 0x4a50); 0x4cb4 is the creator; task+0x38 = slot 0-4, +0x30 = credit system):
  coin_task 0x4a50:
    if slot >= 5: error_log(100); return
    if coin lockout (0x49f8: gf_state&0x100, 0x2dc78 coin-door check, or lockout output 5 via 0x10ad4): return     # coin ignored
    d = adj_get(62 COIN INPUT DELAY); if d != 61 (OFF): repeat d times { task_sleep(1); if lockout: return }   # ~0.49 s at 30 (observed)
    audit_add(slot_counter[slot] = 2,3,4,5,6 (LEFT,CENTER,RIGHT,FOURTH,FIFTH), 1)
    P = pricing[adj_get(28 GAME PRICING)]       # 0x498c; RAM table 0x38078, 64 presets + CUSTOM (NVRAM)
    units = P.coin_door[P.unit_index].slot_units[slot]   # byte at coin_door + unit_index*12 + 4 + slot
    if units == 0: return
    meter_add(1, units) 0xa6f0                  # software coin meter (counter at NVRAM 0x2111014) only when adj 44 Q24 OPTION = COIN METER
    audit_add(7 units counter = METER CLICKS / TOTAL EARNINGS, units)
    0x2dc40 -> 0x21abc(...)                      # game hook (credit/coin accepted)
    repeat units times:
        pos = pos + 1; if pos >= P.ladder_len: pos = 0      # the ladder repeats
        c = P.ladder[pos]
        if c: n = credits_add(c) 0x4890            # capped: credits + c <= adj_get(33 CREDIT LIMIT) (byte arithmetic)
              audit_add(1 TOTAL PAID CREDITS, c)    # note: counts c, not the capped n
              event_post(0x19, {cs, n})             # credit added -> start lamp, sounds
        deff_start(10)                              # coin/credit display effect
    if no credit was added: event_post(0x1a, {cs})  # coin accepted, partial credit
display: 0x4ff4 -> "FREE PLAY" when adj 34 = YES, else "CREDITS %d" / "CREDITS %d/%d" / "CREDITS %d %d/%d"
         fraction (0x4d48) = units since the last ladder award / units between that award and the next, reduced by gcd.
pricing change (event 5 hook 0x50f4 on adj 28): pos = -1 (credits kept)       [observed]
0x4f18 (called from 0x5538 and 0x2157c): keep only the units after the last award: pos = pos - last_award_index - 1
free play (adj 34 = YES): start needs no credit; coin units still counted and still credited.
service credit: BACK/MINUS/PLUS/SELECT handler 0xfc20 case 1 in attract: credits_add(1), audit_add(36 SERVICE CREDITS, 1)
replay/special/match/high-score credits use credits_add 0x4cf0 (same cap); FREE GAME LIMIT (adj 25) is not checked (see adjustments).'''
    verif = []
    for l in emu_lines('t4.log') + emu_lines('t6.log') + emu_lines('t1.log'):
        if re.search(r' (credits|callstr 0x4ff4|mark|adjset 28|country)', l):
            verif.append(l.strip())
    return dict(credit_system=credsys, coin_slots=slots, presets=presets, custom=custom, algorithm=algo,
                countries=[dict(code=c['code'], name=c['name'], record=hx(c['rec']), os_overrides=c['os'], game_overrides=c['game'],
                                os_list=hx(c['os_list']), game_list=hx(c['game_list']), redemption_defaults=hx(c['redemption_defaults']))
                           for c in ctry],
                related_adjustments={28: 'GAME PRICING: 0-63 presets below, 64 = CUSTOM', 33: 'CREDIT LIMIT 4-50', 34: 'FREE PLAY',
                                     62: 'COIN INPUT DELAY 30-60 ticks, 61 = OFF', 44: 'Q24 OPTION (coin meter)', 37: 'BILL VALIDATOR (no adj_get reader in 1.74)'},
                verification_log=verif)


# ================================================================ audits
AUD_FORMULA = {
    2: ('0x2e34c', 'c17 ? audit28 * 100 / c17 : 0', 'FREE GAME PERCENTAGE = TOTAL FREE PLAYS x 100 / paid plays (counter 17)'),
    3: ('0x2e274', 'c8 ? c63 / c8 : 0', 'AVERAGE BALL TIME (s) = ball time counter 63 / TOTAL BALLS PLAYED (counter 8)'),
    4: ('0x2e2b4', 'audit29 ? c60 / audit29 : 0', 'AVERAGE GAME TIME (s) = game time counter 60 / TOTAL PLAYS'),
    10: ('0x2e4c8', 'c2 + c3 + c4 + c5 + c6', 'TOTAL COINS = sum of the five slot counters'),
    11: ('0x2e534', 'c7  (shown as money: c7 x unit value of the CURRENT pricing, 64-bit, /100 and %100, money format +0x16)',
         'TOTAL EARNINGS = units counter 7 converted with the pricing selected now (formatter 0x2e62c)'),
    13: ('0x32b24', '0  (function is "mov r0,#0; mov pc,lr")', 'SOFTWARE METER: always 0 in v1.74'),
    16: ('0x2e300', 'c17 ? c9 * 100 / c17 : 0', 'EXTRA BALL PERCENTAGE = extra balls (counter 9) x 100 / paid plays'),
    21: ('0x2e5d4', 'c10 + c11 + c12 + c13', 'TOTAL REPLAYS = replay 1-4 awards'),
    22: ('0x2e3ec', 'c17 ? audit21 * 100 / c17 : 0', 'REPLAY PERCENTAGE'),
    24: ('0x2e438', 'c17 ? c14 * 100 / c17 : 0', 'SPECIAL PERCENTAGE'),
    27: ('0x2e398', 'c17 ? c16 * 100 / c17 : 0', 'HIGH SCORE PERCENT'),
    28: ('0x2e54c', 'audit21 + c14 + c15 + c16', 'TOTAL FREE PLAYS = replays + specials + matches + high score awards'),
    29: ('0x2e5a4', 'c17 + c18', 'TOTAL PLAYS = counter 17 (paid starts) + counter 18 (free starts)'),
    47: ('0x2e2f4 -> 0x2367c', '(score_sum_u64 / score_count) / 10 * 10, low 32 bits; 0 when the record at NVRAM 0x21109d4 fails its checksum or count = 0',
         'AVERAGE SCORES from NVRAM 0x21109d4 {u64 sum, u32 count, ~checksum16}'),
    53: ('0x2e484', 'c8 - c40 - c41', 'CENTER DRAINS = balls played - left drains - right drains'),
    72: ('0x2e3e4', '0  (function is "mov r0,#0; mov pc,lr")', 'RECENT REPLAY PERCENT: always 0% in v1.74'),
}
TYPE_FMT = {1: ('0x32b2c', '"%d"'), 2: ('0x32b3c', '"%d%%"'), 3: ('0x32b4c', '"%2d:%02d" of value/60, value%60 (seconds)'),
            4: ('0x2e62c', 'money: value x unit_value(current pricing) -> fmt msg at pricing record +0x16 (e.g. "USD %,d.%02d")'),
            5: ('0x2e778', 'score: fmt msg RAM 0x36f5e (0x4e4 "%,02lu")'),
            6: ('0x2e6c4', 'count + share of TOTAL PLAYS p: p=0 -> msg 0x4e2 "%u\\n%u%% OF GAMES"(v,0); v/p=0 -> 0x4e2 (v, v*100/p); '
                           'else 0x4e3 "%u\\n%u%u%% OF GAMES" (v, v/p, (v%p)*100/p)  [integer part and fraction are printed side by side]')}


def audits():
    obs = {}
    phase = 'zero'
    for l in emu_lines('t4.log'):
        if 'mark POKE' in l:
            phase = 'poked'
        if 'mark PRICING' in l:
            phase = 'later'
        m = re.match(r'[\d.]+ audit (\d+) sel=0x(\w+) type=\d+ value=(-?\d+) text="(.*)"', l)
        if m and phase in ('zero', 'poked'):
            obs.setdefault((int(m.group(1)), m.group(2), phase), (m.group(3), m.group(4).replace('|', '\\n')))
    inc = collections.defaultdict(list)
    for site, isbl in find_bl_callers(F['audit_add']):
        c = r0_const(site)
        if c is not None:
            inc[c].append(fname(func_of(site)))
    rows = []
    for a in range(1, AUD_N + 1):
        w = struct.unpack_from('<4I', ROM, foff(AUD_TAB + 16 * a))
        fn, np_, cw, fl = w
        cnt, ty = cw >> 16, cw & 0xffff
        menu, num = ('EARNINGS AUDITS', 'EARNINGS AUDIT #%d' % a) if a <= 13 else \
            (('STANDARD AUDITS', 'STANDARD AUDIT #%d' % (a - 13)) if a <= 72 else ('FEATURE AUDITS', 'FEATURE AUDIT #%d' % (a - 72)))
        rec = struct.unpack_from('<3I', ROM, foff(CNT_TAB + 12 * cnt)) if not fn else None
        f = AUD_FORMULA.get(a)
        zero = obs.get((a, 'c0', 'zero'))
        pok = obs.get((a, 'c0', 'poked'))
        rows.append(dict(
            audit=a, menu=menu, menu_label=num, name=namep(np_), table_entry=hx(AUD_TAB + 16 * a),
            counter=cnt if not fn else '', counter_nvram=hx(rec[0]) if rec else '', counter_flags=hx(rec[2]) if rec else '',
            display_type=ty, display_format=TYPE_FMT.get(ty, ('', ''))[1], formatter=TYPE_FMT.get(ty, ('', ''))[0],
            lifetime_line='yes ([LIFETIME: x], sel 0x90)' if fl & 1 else '',
            computed_fn=hx(fn) if fn else '', formula=f[1] if f else ('counter %d' % cnt), meaning=f[2] if f else '',
            div_by_zero='0' if f and '?' in f[1] else '',
            rounding='integer division, truncated' if f and '/' in f[1] else '',
            incremented_by=';'.join(sorted(set(inc.get(cnt, []))))[:200] if not fn else '',
            observed_zero=('%s -> "%s"' % zero) if zero else '', observed_poked=('%s -> "%s"' % pok) if pok else '',
            tag='observed' if pok else 'code'))
    return rows


# ================================================================ service texts
TEXT_API = ('text_draw_msg_fit', 'text_printf_msg', 'text_draw_msg', 'msg_get')
MSG_HELPERS = {'FUN_0103e690': [6], 'FUN_0103dd00': [6], 'FUN_01041a10': [3, 4, 5, 6], 'FUN_0103b4ac': [2], 'FUN_0000d814': [3]}


def split_args(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth == 0:
                break
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip()); cur = ''
        else:
            cur += ch
    out.append(cur.strip())
    return out


def lit(s):
    s = re.sub(r'^\((ushort|uint|short|int)\)', '', s.strip())
    return int(s, 0) if re.fullmatch(r'0x[0-9a-fA-F]+|\d+', s) else None


def texts_in(fa):
    """[(msg_id or None, api, args, expr)] for text calls in the function body."""
    out = []
    for l in body(fa):
        for api in TEXT_API + tuple(MSG_HELPERS):
            for m in re.finditer(r'\b%s\(' % api, l):
                args = split_args(l[m.end():])
                if api in MSG_HELPERS:
                    for k in MSG_HELPERS[api]:
                        if len(args) >= k and lit(args[k - 1]) is not None:
                            out.append((lit(args[k - 1]), '%s arg%d' % (api, k), args, args[k - 1]))
                    continue
                v = lit(args[0])
                out.append((v, api, args, args[0]))
    return out


def callees(fa):
    out = set()
    for l in body(fa)[1:]:
        for m in re.finditer(r'\b(FUN_[0-9a-f]{8}|[a-z_][a-z0-9_]*)\(', l):
            a = H_BYNAME.get(m.group(1))
            if a is not None and a != fa:
                out.add(a)
    return out


def service_texts():
    items = {}
    for k in range(1, 0x86):
        vis, act, scr, m, icon, sub = struct.unpack_from('<IIIHHI', ROM, foff(ITEMS + 20 * k))
        items[k] = dict(vis=vis, act=act, scr=scr, msg=m, icon=icon, sub=sub)
    menus = {}
    for k in range(0x12):
        _, _, p = struct.unpack_from('<3I', ROM, foff(MENUS + 12 * k))
        menus[k] = msglist(p) if foff(p) is not None else []
    # runtime menus (observed, emu/t4.log call 0xf754)
    obs_menus = {}
    lines = emu_lines('t4.log')
    for i, l in enumerate(lines):
        m = re.search(r'call 0xf754\((\d+),\d+,0,0\) = (\d+)', l)
        if m and i + 1 < len(lines):
            hexs = ''.join(lines[i + 1].split()[3:])
            vals = [int(hexs[j + 2:j + 4] + hexs[j:j + 2], 16) for j in range(0, len(hexs), 4)]
            obs_menus[int(m.group(1))] = vals[:int(m.group(2))]
    parent = {}
    for mk, lst in obs_menus.items():
        for it in lst:
            parent.setdefault(it, mk)
    menu_name = {1: 'MAIN MENU'}
    for k, it in items.items():
        if it['act'] == 0x103dad0 and it['sub']:
            menu_name.setdefault(it['sub'], msg(it['msg']))

    def path(k):
        p, seen = [], set()
        mk = parent.get(k)
        while mk and mk not in seen:
            seen.add(mk); p.append(menu_name.get(mk, 'menu %d' % mk))
            owner = [i for i, x in items.items() if x['act'] == 0x103dad0 and x['sub'] == mk]
            mk = parent.get(owner[0]) if owner else None
        return ' > '.join(reversed(p))
    rows = []
    GENERIC = {0x103dad0, 0x103db70, 0x103dbb8, 0x103db6c, 0}
    for k, it in items.items():
        kind = {0x103dad0: 'opens submenu' if it['sub'] else 'opens page', 0x103db70: 'back', 0x103dbb8: 'exit',
                0x103db6c: 'help (empty stub 0x103db6c)'}.get(it['act'], 'screen' if it['scr'] else 'action')
        rows.append(dict(msg=hx(it['msg']), text=msg(it['msg']), role='menu item name (drawn under the icon when selected)',
                         menu=path(k) or '(not in any runtime menu)', item=k, item_text=msg(it['msg']),
                         screen_fn=hx(it['scr'] or it['act']), drawn_by='0x1037588 menu renderer text_draw_msg(x=0x40,y=0x1e)',
                         notes='%s; icon image %d/%d%s' % (kind, it['icon'], it['icon'] + 1,
                                                          '; visible only if %s() != 0' % hx(it['vis']) if it['vis'] else ''),
                         tag='observed' if k in parent else 'code'))
    # screens: BFS from each item's screen/action function
    callers_count = collections.Counter()
    for fa in H_START:
        for c in callees(fa):
            callers_count[c] += 1
    seen_rows = set()
    roots = [(k, it['scr'] or it['act']) for k, it in items.items() if (it['scr'] or it['act']) not in GENERIC]
    roots += [(None, 0x1037a6c), (None, 0x1037994), (None, 0x103d070), (None, 0x103d90c)]
    for k, root in roots:
        if root not in H_LINE:
            continue
        frontier, depth, visited = [root], 0, {root}
        while frontier and depth <= 3:
            nxt = []
            for fa in frontier:
                for v, api, args, expr in texts_in(fa):
                    key = (v if v is not None else expr, fa)
                    if key in seen_rows:
                        continue
                    seen_rows.add(key)
                    y = args[5] if api.startswith('text_') and len(args) > 5 else ''
                    rows.append(dict(msg=hx(v) if v is not None else '', text=msg(v) if v is not None else '',
                                     role=('dynamic: %s' % expr[:80]) if v is None else api.split()[0],
                                     menu=path(k) if k else 'service menu shell', item=k or '', item_text=msg(items[k]['msg']) if k else '',
                                     screen_fn=hx(root), drawn_by='%s %s%s' % (hx(fa), fname(fa), (' y=%s' % y) if y else ''),
                                     notes='', tag='code'))
                for c in callees(fa):
                    if c in visited or callers_count[c] > 12 or not (0x1000000 <= c or 0x1000 <= c):
                        continue
                    nm = fname(c)
                    if not nm.startswith('FUN_') and not (0x1036000 <= c < 0x1048000):
                        continue
                    visited.add(c); nxt.append(c)
            frontier, depth = nxt, depth + 1
    # adjustment value labels and titles drawn by the adjustment screen
    for i in range(1, ADJ_N + 1):
        r = adj_record(i)
        fn, arg = struct.unpack_from('<II', ROM, foff(ADJ_FMT + 8 * r['display_type']))
        if fn == 0 and arg:
            for v, mid in enumerate(msglist(arg)):
                rows.append(dict(msg=hx(mid), text=msg(mid), role='adjustment value label', menu='ADJUSTMENTS',
                                 item=58 if i <= 64 else 125, item_text='STANDARD ADJUSTMENTS' if i <= 64 else 'FEATURE ADJUSTMENTS',
                                 screen_fn='0x103dd00', drawn_by='0x12bc msg-list formatter (via 0x103dd00, y=0x16)',
                                 notes='adj %d %s value %d' % (i, r['name'], v), tag='code'))
    # msg ids computed in registers (missed by the decompile parser): SWITCH TEST 0x1044bfc
    for mid, cond in ((0x113, 'switch is a matrix switch (0xdec0 returns non-zero); %d = switch number'),
                      (0x114, 'switch is a dedicated switch (0xdec0 returns 0); %d = switch number - 0x80')):
        for site in ('0x1045094', '0x104512c'):
            rows.append(dict(msg=hx(mid), text=msg(mid), role='last-switch line under the switch name',
                             menu='SWITCH TEST', item=21, item_text=msg(u16(ITEMS + 20 * 21 + 12)), screen_fn='0x1044bfc',
                             drawn_by='text_printf_msg 0x28d5c at %s (y=0x15); id = 0x110+3, moveq 0x114' % site,
                             notes=cond + ('; drawn after "NONE" (msg 0x115, y=0xf) when no switch name' if site == '0x1045094'
                                           else '; drawn after the switch name (y=0xf)'), tag='code'))
    for c in range(28):
        mid = 0x370 + c
        rows.append(dict(msg=hx(mid), text=msg(mid), role='country name (msg 0x370 + DIP country)', menu='boot / country check',
                         item='', item_text='', screen_fn='', drawn_by='country table 0x040e17e0 +0x14', notes='country %d' % c, tag='code'))
    for i in range(64):
        mid = 0x299 + i
        rows.append(dict(msg=hx(mid), text=msg(mid), role='pricing preset name', menu='ADJUSTMENTS', item=58, item_text='STANDARD ADJUSTMENTS',
                         screen_fn='0x103dd00', drawn_by='0x2e0fc (adj 28 formatter: pricing record +0x10)', notes='GAME PRICING = %d' % i, tag='observed'))
    helper_role = {'FUN_01041a10': 'install screen text: msg passed to 0x1041a10 (args 3-6, drawn at y=9/10/0x12 and status line)',
                   'FUN_0103e690': 'audit screen title: msg passed to 0x103e690 (arg 6, y=5)',
                   'FUN_0103dd00': 'adjustment screen title: msg passed to 0x103dd00 (arg 6, y=5)',
                   'FUN_0103b4ac': 'msg passed to helper 0x103b4ac (arg 2), which draws it',
                   'FUN_0000d814': 'msg passed to helper 0xd814 (arg 3), which draws it'}
    for r in rows:
        for k, v in helper_role.items():
            if r['role'].startswith(k):
                r['role'] = v
    return rows, obs_menus


# ================================================================ main
def main():
    os.makedirs(OUT, exist_ok=True)
    # ---- pricing
    P = pricing()
    json.dump(P, open(os.path.join(OUT, 'pricing.json'), 'w'), indent=1)
    prow = []
    for p in P['presets']:
        prow.append(dict(adj_value=p['adj_value'], name=p['name'], record=p['record'], coin_door=p['coin_door'], unit_index=p['unit_index'],
                         unit_value_minor=p['unit_value_minor'], currency_format=p['money_formats']['long'],
                         slot1_units=p['slot_units'][0], slot2_units=p['slot_units'][1], slot3_units=p['slot_units'][2],
                         slot4_units=p['slot_units'][3], slot5_units=p['slot_units'][4],
                         slot_money='|'.join(p['slot_money']), ladder=' '.join(map(str, p['ladder'])), ladder_len=p['ladder_length'],
                         first_credit=p['first_credit_money'], awards='|'.join('%s=%d' % (a['money'], a['credits_total']) for a in p['awards']),
                         service_summary=p['service_summary'], factory_default_for='|'.join(p['factory_default_for']), tag=p['tag']))
    prow.append(dict(adj_value=64, name='CUSTOM', record=P['custom']['record'], tag='code'))
    wcsv('pricing.csv', prow, ['adj_value', 'name', 'record', 'coin_door', 'unit_index', 'unit_value_minor', 'currency_format',
                               'slot1_units', 'slot2_units', 'slot3_units', 'slot4_units', 'slot5_units', 'slot_money', 'ladder',
                               'ladder_len', 'first_credit', 'awards', 'service_summary', 'factory_default_for', 'tag'])
    # ---- audits
    A = audits()
    wcsv('audits.csv', A, ['audit', 'menu', 'menu_label', 'name', 'table_entry', 'counter', 'counter_nvram', 'counter_flags', 'display_type',
                           'display_format', 'formatter', 'lifetime_line', 'computed_fn', 'formula', 'meaning', 'div_by_zero', 'rounding',
                           'incremented_by', 'observed_zero', 'observed_poked', 'tag'])
    # ---- adjustments
    labels = formatter_labels()
    ctry = countries()
    over = collections.defaultdict(list)
    for c in ctry:
        for adj, v in c['os']:
            over[adj].append('%s=%d' % (c['name'], v))
        for adj, v in c['game']:
            over[adj].append('%s=%d (game list)' % (c['name'], v))
    std_order = msglist(0x39558)
    R = adj_readers()
    rd = collections.defaultdict(list)
    for r in R:
        if r['accessor'].startswith('adj_get') and r['adj'] != 'any':
            rd[r['adj']].append('%s %s' % (r['site'], r['function_name']))
    obs_def = {}
    for l in emu_lines('t4.log'):
        m = re.search(r'call 0xf28\((\d+),0,0,0\) = (-?\d+)', l)
        if m:
            obs_def[int(m.group(1))] = int(m.group(2))
    rows = []
    for i in range(1, ADJ_N + 1):
        r = adj_record(i)
        lb = labels[i]
        menu = 'STANDARD ADJUSTMENTS' if i in std_order else 'FEATURE ADJUSTMENTS'
        num = (std_order.index(i) + 1) if i in std_order else i - 64
        rows.append(dict(adj=i, menu=menu, menu_label='%s #%d' % (menu[:-1], num), name=r['name'], table_entry=hx(r['rec']),
                         nvram=hx(r['nvram']), default=r['default'], default_label=lb['labels'].get(r['default'], ''),
                         factory_default_usa=obs_def.get(i, ''), min=r['min'], max=r['max'], step=r['step'],
                         wraps='no' if r['nowrap'] else 'yes', display_type=r['display_type'],
                         formatter=hx(lb['fn']) if lb['fn'] else 'msg list %s' % hx(lb['arg']),
                         labels=json.dumps({str(k): v for k, v in sorted(lb['labels'].items())}, ensure_ascii=False),
                         labels_source=lb['src'], visible_if=VISIBLE.get(i, 'always'), country_overrides='; '.join(over.get(i, [])),
                         readers='; '.join(rd.get(i, [])) or 'none (no adj_get call site; see README)',
                         tag='observed' if i in obs_def else 'code'))
    wcsv('adjustments.csv', rows, ['adj', 'menu', 'menu_label', 'name', 'table_entry', 'nvram', 'default', 'default_label',
                                   'factory_default_usa', 'min', 'max', 'step', 'wraps', 'display_type', 'formatter', 'labels',
                                   'labels_source', 'visible_if', 'country_overrides', 'readers', 'tag'])
    wcsv('adjustment_readers.csv', R, ['adj', 'accessor', 'site', 'call', 'function', 'function_name', 'id_source', 'what',
                                       'observed_calls', 'tag'])
    # ---- presets
    pr = []
    INST = [(71, 0x394a8, 0x36f7c), (72, 0x394a0, 0x36f84), (73, 0x394d0, 0x36f8c), (74, 0x394b8, 0x36f94), (75, 0x394b0, 0x36f9c),
            (76, 0x39498, 0x36fa4), (77, 0x394c0, 0x394c8), (102, 0x39248, 0x36fac), (103, 0x39258, 0x36fb4),
            (104, 0x392c8, 0x39310), (105, 0x39318, 0x39370), (106, 0x39268, 0x392c0)]
    name_of = {i: adj_record(i)['name'] for i in range(1, ADJ_N + 1)}
    for item, l1, l2 in INST:
        nm = msg(u16(ITEMS + 20 * item + 12))
        entries = [('os', l1, a, v) for a, v in plist(l1)] + [('game', l2, a, v) for a, v in plist(l2)]
        if not entries:
            pr.append(dict(kind='install', preset=nm, item=item, list='os', list_address=hx(l1), adj='', name='(empty list: changes nothing)',
                           value='', label='', applied_by='0x1041a10 -> adj_apply_list 0x10e8 (os list, then game list %s)' % hx(l2), tag='code'))
        for which, la, a, v in entries:
            pr.append(dict(kind='install', preset=nm, item=item, list=which, list_address=hx(la), adj=a, name=name_of.get(a),
                           value=v, label=labels[a]['labels'].get(v, '') if a in labels else '', applied_by='0x1041a10 -> 0x10e8', tag='code'))
    pr.append(dict(kind='install', preset=msg(u16(ITEMS + 20 * 78 + 12)), item=78, list='', adj='all', name='every adjustment',
                   value='factory default', label='', applied_by='0x1041874 -> 0x1278 (0x1080 for ids 1-88: country override else table default)', tag='code'))
    for c in ctry:
        for which, lst, la in (('os', c['os'], c['os_list']), ('game', c['game'], c['game_list'])):
            for a, v in lst:
                pr.append(dict(kind='country', preset=c['name'], item='DIP %d' % c['code'], list=which, list_address=hx(la), adj=a,
                               name=name_of.get(a), value=v, label=labels[a]['labels'].get(v, '') if a in labels else '',
                               applied_by='factory default 0xf28 -> 0x5f2c (country NVRAM 0x21100d8, set from the DIP at boot by 0x605c)',
                               tag='observed' if (c['code'], a) in ((7, 28), (7, 7), (7, 35), (19, 28), (19, 25), (19, 13), (0, 10)) else 'code'))
    wcsv('presets.csv', pr, ['kind', 'preset', 'item', 'list', 'list_address', 'adj', 'name', 'value', 'label', 'applied_by', 'tag'])
    # ---- service texts
    T, obs_menus = service_texts()
    T.sort(key=lambda r: (str(r['item']).zfill(4) if r['item'] != '' else 'zzzz', r['msg']))
    wcsv('service_texts.csv', T, ['msg', 'text', 'role', 'menu', 'item', 'item_text', 'screen_fn', 'drawn_by', 'notes', 'tag'])
    json.dump({str(k): v for k, v in obs_menus.items()}, open(os.path.join(OUT, 'menus_runtime.json'), 'w'), indent=1)
    print('menus', len(obs_menus))


if __name__ == '__main__':
    main()
