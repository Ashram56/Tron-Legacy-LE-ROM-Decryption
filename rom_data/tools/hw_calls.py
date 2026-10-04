"""Every call site of the coil driver API in OS + game code, with constant arguments resolved.

Writes rom_data/io/coil_calls.csv. Run: python3 rom_data/tools/hw_calls.py
Argument meanings come from the OS functions (see rom_data/io/README.md, "Coil driver"):
  coil_pulse 0x6970(coil, ms)                      -> 0x2bc8(coil, ms, 0,0,0, sync=0) via the 6-slot table 0x3c198
  coil_pulse_fn 0x69c0(coil, ms, pattern)          -> 0x2d18(coil, ms, pattern, 32 bits, 0,0,0, sync=0)
  coil_drive_pulse 0x2bc8(coil, ms, start_fn, end_fn, [sp0]=arg, [sp4]=sync)      mode 3 (on for ms)
  coil_drive_pulse_wait 0x2cb0(same)               waits (task_sleep(1)) until the pulse ends
  coil_drive_pattern 0x2d18(coil, ms, pattern, bits, [sp0]=start_fn, [sp4]=end_fn, [sp8]=arg, [sp12]=sync)  mode 1
  coil_drive_onoff 0x2e5c(coil, ms, on_ms, off_ms, [sp0]=start_fn, [sp4]=end_fn, [sp8]=arg, [sp12]=sync)   mode 2
  coil_queue_pulse 0x2ac0 / 0x2b60(+wait)(coil, ms, start_fn, end_fn, [sp0]=arg, [sp4]=sync)  serialised queue
  coil_on 0x3034(coil) / coil_off 0x2fbc(coil) / coil_pulse_stop 0x6a20(coil)
  coilgroup_pulse 0x6b24(group, ms) / coilgroup_pulse_fn 0x6b94(group, ms, pattern) / coilgroup_stop 0x6c0c(group)
  shaker_run 0x10289b8(strength, min_setting)       -> 0x2bc8(8, table 0x040d3998[strength], sync=1)
"""
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rom import ROM, u8, u16, u32, foff, hx, find_bl_callers
from hw_common import resolve_call_args, func_of, decomp_body, REPO

OUT = os.path.join(REPO, 'rom_data', 'io')

# addr: (api name, decompile name, reg arg names, stack arg names)
API = {
    0x6970: ('coil_pulse', 'coil_pulse', ['coil', 'ms'], []),
    0x69c0: ('coil_pulse_fn', 'coil_pulse_fn', ['coil', 'ms', 'pattern'], []),
    0x2bc8: ('coil_drive_pulse', 'FUN_00002bc8', ['coil', 'ms', 'start_fn', 'end_fn'], ['arg', 'sync']),
    0x2cb0: ('coil_drive_pulse_wait', 'FUN_00002cb0', ['coil', 'ms', 'start_fn', 'end_fn'], ['arg', 'sync']),
    0x2d18: ('coil_drive_pattern', 'FUN_00002d18', ['coil', 'ms', 'pattern', 'bits'], ['start_fn', 'end_fn', 'arg', 'sync']),
    0x2de0: ('coil_drive_pattern_wait', 'FUN_00002de0', ['coil', 'ms', 'pattern', 'bits'], ['start_fn', 'end_fn', 'arg', 'sync']),
    0x2e5c: ('coil_drive_onoff', 'FUN_00002e5c', ['coil', 'ms', 'on_ms', 'off_ms'], ['start_fn', 'end_fn', 'arg', 'sync']),
    0x2f34: ('coil_drive_onoff_wait', 'FUN_00002f34', ['coil', 'ms', 'on_ms', 'off_ms'], ['start_fn', 'end_fn', 'arg', 'sync']),
    0x2ac0: ('coil_queue_pulse', 'FUN_00002ac0', ['coil', 'ms', 'start_fn', 'end_fn'], ['arg', 'sync']),
    0x2b60: ('coil_queue_pulse_wait', 'FUN_00002b60', ['coil', 'ms', 'start_fn', 'end_fn'], ['arg', 'sync']),
    0x3034: ('coil_on', 'FUN_00003034', ['coil'], []),
    0x2fbc: ('coil_off', 'FUN_00002fbc', ['coil'], []),
    0x6a20: ('coil_pulse_stop', 'FUN_00006a20', ['coil'], []),
    0x6b24: ('coilgroup_pulse', 'coilgroup_pulse', ['group', 'ms'], []),
    0x6b94: ('coilgroup_pulse_fn', 'FUN_00006b94', ['group', 'ms', 'pattern'], []),
    0x6c0c: ('coilgroup_stop', 'FUN_00006c0c', ['group'], []),
    0x10289b8: ('shaker_run', 'shaker_run', ['strength', 'min_setting'], []),
}
SHAKER_MS = {s: u16(0x040d3998 + 4 * s) for s in (1, 2, 3)}


def coil_group(g):
    if g is None or not (0 < g < 0x1b):
        return None
    p = u32(0x040e20c4 + 4 * g)
    out = []
    while u8(p):
        out.append(u8(p))
        p += 1
    return out


def decomp_calls(fn_addr, dname):
    body = decomp_body(fn_addr) or ''
    rx = re.compile(r'\b%s\(([^;]*)\);' % re.escape(dname))
    return [m.group(0).strip() for m in rx.finditer(body)]


LEFF_TAB, LEFF_N = u32(0x36cf0), u32(0x36cf4)


def leffs_by_fn():
    d = {}
    for i in range(1, LEFF_N):
        d.setdefault(u32(LEFF_TAB + 12 * i), []).append(i)
    return d


def main():
    lbf = leffs_by_fn()
    rows = []
    for tgt, (api, dname, rnames, snames) in API.items():
        sites = sorted(find_bl_callers(tgt))
        by_fn = {}
        for pc, link in sites:
            by_fn.setdefault(func_of(pc)[0], []).append((pc, link))
        for fstart, lst in by_fn.items():
            dc = decomp_calls(fstart, dname) if fstart is not None else []
            for k, (pc, link) in enumerate(lst):
                regs, stack, _ = resolve_call_args(pc, nstack=len(snames))
                args = {}
                for i, n in enumerate(rnames):
                    args[n] = regs.get(i)
                for i, n in enumerate(snames):
                    args[n] = stack[i] if i < len(stack) else None
                if 'coil' in args and args['coil'] is not None:
                    args['coil'] &= 0xff
                for n in ('ms', 'on_ms', 'off_ms', 'group'):
                    if args.get(n) is not None:
                        args[n] &= 0xffff
                fname = func_of(pc)[1]
                group_src = ''
                leff_ids = lbf.get(fstart, [])
                if 'group' in args and args['group'] is None and leff_ids:
                    # leff tasks get their coil group from leff_current_info 0x8d90 = leff table +8
                    gs = sorted(set(u16(LEFF_TAB + 12 * i + 8) for i in leff_ids))
                    if len(gs) == 1:
                        args['group'] = gs[0]
                    group_src = 'leff table +8 (leff_current_info 0x8d90): ' + ' '.join('leff %d -> group %d' % (i, u16(LEFF_TAB + 12 * i + 8)) for i in leff_ids)
                coils = None
                if 'coil' in args:
                    coils = [args['coil']] if args['coil'] is not None else None
                elif 'group' in args:
                    coils = coil_group(args['group'])
                elif api == 'shaker_run':
                    coils = [8]
                ms = args.get('ms')
                if api == 'shaker_run' and args.get('strength') in SHAKER_MS:
                    ms = SHAKER_MS[args['strength']]
                unresolved = [n for n, v in args.items() if v is None]
                if group_src and args.get('group') is not None:
                    pass
                row = {
                    'call_site': hx(pc), 'kind': 'bl' if link else 'b (tail call)',
                    'caller_fn': hx(fstart) if fstart is not None else '', 'caller_name': fname or '',
                    'api': api, 'api_addr': hx(tgt),
                    'coil': '' if not coils or len(coils) != 1 else coils[0],
                    'group': '' if args.get('group') is None else args['group'],
                    'group_coils': '' if 'group' not in args or not coils else ' '.join(map(str, coils)),
                    'group_source': group_src,
                    'leff_ids': ' '.join(map(str, leff_ids)),
                    'ms': '' if ms is None else ms,
                    'pattern': '' if args.get('pattern') is None else '0x%08x' % args['pattern'],
                    'pattern_bits': '' if args.get('bits') is None else args['bits'],
                    'on_ms': '' if args.get('on_ms') is None else args['on_ms'],
                    'off_ms': '' if args.get('off_ms') is None else args['off_ms'],
                    'strength': '' if args.get('strength') is None else args['strength'],
                    'min_setting': '' if args.get('min_setting') is None else args['min_setting'],
                    'start_fn': '' if args.get('start_fn') in (None, 0) else hx(args['start_fn']),
                    'end_fn': '' if args.get('end_fn') in (None, 0) else hx(args['end_fn']),
                    'sync': '' if args.get('sync') is None else (args['sync'] & 0xff),
                    'waits': 1 if api.endswith('_wait') else 0,
                    'unresolved_args': ' '.join(unresolved),
                    'decompile': dc[k] if len(dc) == len(lst) else '',
                    'tag': 'code',
                }
                if api in ('coil_pulse', 'coil_pulse_fn', 'coilgroup_pulse', 'coilgroup_pulse_fn'):
                    row['sync'] = 0  # fixed inside the API
                rows.append(row)
    rows.sort(key=lambda r: int(r['call_site'], 16))
    cols = list(rows[0].keys())
    with open(os.path.join(OUT, 'coil_calls.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(len(rows), 'call sites;', sum(1 for r in rows if r['unresolved_args']), 'with unresolved args')
    return rows


if __name__ == '__main__':
    main()
