"""Annotate the raw Ghidra export of Tron Pro 1.74 (TRN174VP.BIN, PinMAME trn_17402).
usage: python3 pro_annotate.py pro_raw.c ../../../code/tron_pro_decompiled.c
Adds comments for coil numbers on coil-API calls, message ids, adjustment ids and lamp numbers, using the Pro's
own tables (not the LE ones). Names come from the LE -> Pro function map (rom_data/pro/le_to_pro_functions.csv)."""
import re, struct, sys, os
ROM = open(os.environ.get('TRON_PRO_ROM', '/mnt/project-files/tron/pro/TRN174VP.BIN'), 'rb').read()
def foff(a):
    if a < 0x100000: return a
    if 0x01000000 <= a < 0x01100000: return a - 0x01000000 + 0x40000
    if 0x04000000 <= a < 0x04800000: return a - 0x04000000
def u32(a): return struct.unpack_from('<I', ROM, foff(a))[0]
def cstr(a):
    o = foff(a)
    if o is None: return None
    e = ROM.find(b'\0', o)
    return ROM[o:e].decode('latin1') if 0 <= e - o < 200 else None
NMSG = u32(0x040b9f2c)
def msg(i): return cstr(u32(u32(0x040d3730 + 4 * i))) if i < NMSG else None
NADJ = u32(0x2fa10)
def adj(i):
    if i >= NADJ: return None
    a = 0x040c35a0 + 32 * i
    _, d, mn, mx = struct.unpack_from('<4i', ROM, foff(a))
    return '%s (default %d, %d-%d)' % (cstr(u32(u32(a + 0x18))), d, mn, mx)
def coil(i): return cstr(u32(0x040c5ef4 + 24 * i)) if 0 < i < 36 else None
def lamp(i): return cstr(u32(0x040c7e30 + 24 * i)) if 0 < i < 81 else None
num = lambda s: int(s, 0)
src, out = sys.argv[1], sys.argv[2]
COILAPI = r'coil_pulse\w*|coil_on|coil_off|FUN_000021f0|FUN_000022d8|FUN_00002340|FUN_00002408|FUN_00002484|FUN_0000255c|FUN_000020e8|FUN_00002188|FUN_0000265c|FUN_000025e4|FUN_00006048'
RULES = [
    (r'\b(?:%s)\((0x[0-9a-f]+|\d+)\s*[,)]' % COILAPI, lambda v: 'coil %d %s' % (v, coil(v)) if coil(v) else None),
    (r'\badj_get\((0x[0-9a-f]+|\d+)\)', lambda v: 'adj %d %s' % (v, adj(v)) if adj(v) else None),
    (r'\b(?:msg_get|text_draw_msg\w*|text_printf_msg\w*)\((0x[0-9a-f]+|\d+)', lambda v: 'msg 0x%x "%s"' % (v, msg(v).replace('*/', '* /')) if msg(v) is not None else None),
    (r'\blamp_\w+\((0x[0-9a-f]+|\d+)\s*[,)]', lambda v: 'lamp %d %s' % (v, lamp(v)) if lamp(v) else None),
]
res = []
for ln in open(src, encoding='latin1').read().split('\n'):
    notes = []
    for pat, f in RULES:
        for m in re.finditer(pat, ln):
            c = f(num(m.group(1)))
            if c and c not in notes: notes.append(c)
    if notes and not ln.lstrip().startswith('//'): ln += '  /* ' + '; '.join(notes) + ' */'
    res.append(ln)
hdr = '''/*
 * Stern Tron Legacy PRO v1.74 (TRN174VP.BIN = TRN17402.BIN, PinMAME trn_17402): game and OS code decompiled with
 * Ghidra 11.4.2 (ARM7 LE), 2026-10-04. The ROM image is not in this repository.
 * Memory map: 0x00000000-0x2f9ff OS code; 0x2fa00-0xfffff RAM (initial values from ROM; table of tables at
 *   0x2fa00); 0x01000000- game code (file 0x40000+); 0x02100000 NVRAM; 0x02400000 IO; 0x04000000 flash data.
 * Names: functions matched to the LE 1.74 decompile (rom_data/pro/le_to_pro_functions.csv: 2,420 of the LE's
 *   3,938 seeds, by masked byte signature and call-graph propagation) carry the LE name; RAM globals carry LE
 *   names where the literal pools of matched functions pair them (194 of 253). Unmatched functions keep Ghidra
 *   names (FUN_xxxxxxxx): they are Pro-only or changed code. A matched name says the code is the same shape as
 *   the LE function, not that every constant is equal.
 * Comments decode coil numbers, messages, adjustments and lamps from the Pro's own tables.
 * Coil API (Pro addresses): coil_drive_pulse 0x21f0, coil_drive_pulse_wait 0x22d8, coil_drive_pattern 0x2340,
 *   coil_drive_onoff 0x2484, coil_queue_pulse 0x20e8 / 0x2188 (wait), coil_on 0x265c, coil_off 0x25e4,
 *   coil_pulse 0x5f98, coil_pulse_fn 0x5fe8, coilgroup_pulse 0x614c, shaker_run 0x010203ac.
 * Machine-generated pseudo-C: readable, not compilable.
 */
'''
open(out, 'w').write(hdr + '\n'.join(res))
print('written', out)
