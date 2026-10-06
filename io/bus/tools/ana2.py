import csv,sys,collections
def region(a):
    if a>=0xFFE00000 and a<0xFFE00100: return 'EBI'
    if a>=0xFFFFF000: return 'AIC'
    if 0xFFFE0000<=a<0xFFFE0100: return 'TC%d'%((a-0xFFFE0000)//0x40) if a<0xFFFE00C0 else 'TCB'
    if 0xFFFF0000<=a<0xFFFF4000: return 'PIO'
    if 0xFFFF4000<=a<0xFFFF8000: return 'PS'
    if 0xFFFF8000<=a<0xFFFFC000: return 'WD'
    if 0xFFFD0000<=a<0xFFFD4000: return 'US0'
    if 0xFFFCC000<=a<0xFFFD0000: return 'US1'
    if 0xFFF00000<=a<0xFFF01000: return 'SF'
    if a>=0xFFC00000: return 'INT?'
    if 0x01080000<=a<0x0109F000: return 'DMDRAM'
    if 0x0109F000<=a<0x01100000: return 'SNDBUF'
    return 'IO'
for fn in sys.argv[1:]:
    rows=csv.DictReader(open(fn))
    c=collections.Counter(); vals=collections.defaultdict(set); t0=t1=None; pcs=collections.defaultdict(set)
    for r in rows:
        if r['kind']=='ENTRY': continue
        a=int(r['addr'],16); t=float(r['t']); t0=t if t0 is None else t0; t1=t
        reg=region(a)
        key=(reg, hex(a) if reg not in('DMDRAM','SNDBUF') else '', r['kind'])
        c[key]+=1
        if len(vals[key])<12: vals[key].add(r['data'])
        if len(pcs[key])<6: pcs[key].add(r['pc'])
    print('==',fn,'span %.3f s'%(t1-t0))
    for k,v in sorted(c.items()): print(f"{k[0]:7s}{k[1]:12s}{k[2]} {v:8d}  vals={sorted(vals[k])[:12]} pcs={sorted(pcs[k])}")
