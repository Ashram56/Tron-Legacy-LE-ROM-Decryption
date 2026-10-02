import re,sys
from romtables import *
src=open(sys.argv[1]).read()
out=sys.argv[2]
def num(s):
    try: return int(s,0)
    except: return None
def snd_c(v):
    k=SND.get(v); 
    return 'snd 0x%03x %s: %s'%(v,k[0] or '?',k[1][:60]) if k else 'snd 0x%03x'%v
def adj_c(v):
    a=adj(v); return 'adj %d %s (default %d, %d-%d)'%(v,a['name'],a['default'],a['min'],a['max']) if a and a['name'] else 'adj %d'%v
def deff_c(v): return 'deff %d'%v
def msg_c(v):
    s=msg(v); return 'msg 0x%x "%s"'%(v,s.replace('*/','* /')) if s is not None else None
def aud_c(v): return 'audit 0x%x %s'%(v,AUD.get(v,'?'))
def lamp_c(v): return 'lamp %d %s'%(v,LAMPS.get(v,'?'))
NM={}
for l in open('seeds_final.tsv'):
    a,n=l.rstrip('\n').split('\t')
    if n: NM[int(a,16)]=n
def deff_c(v):
    try: return 'deff %d = %s'%(v,NM.get(deff_fn(v),'?'))
    except Exception: return 'deff %d'%v
def leff_c(v):
    try: return 'lamp leff %d = %s'%(v,NM.get(leff_entry(v)[0],hex(leff_entry(v)[0])))
    except Exception: return 'leff %d'%v
def tube_c(v): return 'ramp tube show %d'%v
RULES=[
 (r'\bdeff_(?:start|running|stop)\w*\((0x[0-9a-f]+|\d+)', deff_c),
 (r'\bleff_(?:start|stop)\((0x[0-9a-f]+|\d+)', leff_c),
 (r'\btube_show_(?:start|stop)\((0x[0-9a-f]+|\d+)', tube_c),
 (r'\bsnd_play\w*\((0x[0-9a-f]+|\d+)', snd_c),
 (r'\bsnd_resolve_call\((0x[0-9a-f]+|\d+)', snd_c),
 (r'\badj_get\((0x[0-9a-f]+|\d+)', adj_c),
 (r'\baudit_add\((0x[0-9a-f]+|\d+)', aud_c),
 (r'\b(?:msg_get|text_draw_msg\w*|text_printf\w*|text_fit\w*)\((0x[0-9a-f]+|\d+)', msg_c),
 (r'\blamp_(?:on|off|toggle|bit_set|bit_clear|solid_on|off_noflash|test)\w*\((0x[0-9a-f]+|\d+)', lamp_c),
]
lines=src.split('\n')
res=[]
for ln in lines:
    notes=[]
    for pat,f in RULES:
        for m in re.finditer(pat,ln):
            v=num(m.group(1))
            if v is None: continue
            c=f(v)
            if c and c not in notes: notes.append(c)
    # data constants in flash
    for m in re.finditer(r'\b(?:DAT|PTR|s)_(04[0-9a-f]{6})\b',ln):
        a=int(m.group(1),16); s=cstr(a)
        if s and len(s)>=3 and all(32<=ord(ch)<127 for ch in s): notes.append('"%s"'%s.replace('*/','* /')[:60])
    if notes and not ln.lstrip().startswith('//'):
        ln=ln+'  /* '+'; '.join(notes)+' */'
    res.append(ln)
hdr='''/*
 * Stern Tron Legacy LE v1.74 (trn_174h): game and OS code decompiled with Ghidra 11.4.2 (ARM7 LE),
 * cleaned-up export (2026-10-02). See tron/rules/developer_guide.md for how to read it.
 * Memory map: 0x00000000-0x35fff OS code; 0x36000-0xfffff RAM (initial values from ROM);
 *   0x01000000- game rules code (file 0x40000+); 0x02100000 NVRAM (per-player and audit data);
 *   0x02400000 IO; 0x04000000 flash data tables (file 0x0-0x7fffff).
 * Changes vs code/tron_game_decompiled.c: correct signatures for 166 OS functions, ~570 game functions and ~250 RAM variables named from the mode specs (tron/rules/modes) (dropped call
 *   arguments recovered), RAM shown as globals (DAT_0003af18) instead of pointer literals,
 *   phantom "+4" duplicate functions removed, function-pointer arguments resolved to names,
 *   lamp leff vs ramp tube shows separated, and comments decoding sound calls, messages,
 *   adjustments, audits and lamps. Names: swNN_* switch handlers, deff_NNN_* display effects,
 *   leff_NNN lamp effects (table 0x040e23e4), tubeshow_NNN ramp tube shows (table 0x040e3c88),
 *   task_XX function started as task id XX, on_* functions that bump an audit counter
 *   (heuristic: the name says which audit, not what the whole function does).
 * Machine-generated pseudo-C: readable, not compilable.
 */
'''
open(out,'w').write(hdr+'\n'.join(res))
