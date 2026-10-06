import csv,sys
from ana import NAMES,ENT
rows=list(csv.DictReader(open(sys.argv[1])))
start=int(sys.argv[2]) if len(sys.argv)>2 else 0
n=int(sys.argv[3]) if len(sys.argv)>3 else 6
# find TC0 entries
idx=[i for i,r in enumerate(rows) if r['kind']=='ENTRY' and int(r['addr'],16)==0x13624]
for k in range(start,start+n):
    i0=idx[k]; i1=idx[k+1]; c0=int(rows[i0]['cycles'])
    print(f"--- tick {k}  t={float(rows[i0]['t']):.6f}  period={(int(rows[i1]['cycles'])-c0)} cyc")
    for r in rows[i0:i1]:
        a=int(r['addr'],16); dc=int(r['cycles'])-c0
        if r['kind']=='ENTRY': print(f"  +{dc:6d} cyc {dc*0.025:8.3f}us  >> {ENT.get(a,hex(a))}")
        else:
            nm=NAMES.get(a,hex(a))
            if nm in ('XILINX?','BANK'): continue
            print(f"  +{dc:6d} cyc {dc*0.025:8.3f}us  {r['kind']} {nm:8s} {int(r['data'],16):#06x}  pc={r['pc']}")
