import re,sys
from romtables import *
src=open(sys.argv[1]).read()
parts=re.split(r'^// ==== ([0-9a-f]{8}) (\S+)$',src,flags=re.M)
F={}
for i in range(1,len(parts),3): F[int(parts[i],16)]=(parts[i+1],parts[i+2])
api={int(l.split('\t')[0],16) for l in open('sigs.tsv') if l.strip()}
names={}; role={}
def put(a,n,r):
    if a not in F or a in api: return
    if a in names: return
    base=n; k=2
    while n in names.values(): n='%s_%d'%(base,k); k+=1
    names[a]=n; role[a]=r
def num(s): return int(s,0)
def msgslug(body):
    for m in re.finditer(r'(?:text_draw_msg\w*|text_printf\w*|msg_get|text_\w+)\((0x[0-9a-f]+|\d+)',body):
        s=msg(num(m.group(1)))
        if s and slug(s): return slug(s,30)
    return ''
# switch handlers
for n in range(1,65):
    h=u32(0x040f3574+(n-1)*32) if False else None
for n in range(0,80):
    try: h=u32(0x040f3574+n*32)
    except Exception: break
    if h in F and SW.get(n+1) and SW[n+1] not in ('NOT USED','INVALID'):
        put(h,'sw%02d_%s'%(n+1,slug(SW[n+1],24)),'switch')
for i in range(1,146):
    fn=deff_fn(i)
    if fn in F: put(fn,'deff_%03d%s'%(i,('_'+msgslug(F[fn][1])) if msgslug(F[fn][1]) else ''),'deff')
for i in range(1,0xac):
    fn,_=leff_entry(i)
    if fn in F: put(fn,'leff_%03d'%i,'leff')
for i in range(1,106):
    fn=tube_fn(i)
    if fn in F: put(fn,'tubeshow_%03d'%i,'tube')
for a,(n,b) in sorted(F.items()):
    m=re.search(r'audit_add\((0x[0-9a-f]+|\d+),',b)
    if m and a>=0x01000000 and (n.startswith('FUN_') or n.startswith('on_')):
        nm=AUD.get(num(m.group(1)))
        if nm: put(a,'on_'+slug(nm,36),'audit')
for a,(n,b) in sorted(F.items()):
    for m in re.finditer(r'task_(?:create|recreate|create_unique)\w*\((0x[0-9a-f]+|\d+),(FUN_([0-9a-f]{8}))',b):
        t=int(m.group(3),16); put(t,'task_%02x'%num(m.group(1)),'task')
    for m in re.finditer(r'task_(?:create|recreate|create_unique)\w*\((0x[0-9a-f]+|\d+),(?:FUN_|LAB_)',b): pass
print(len(names),file=sys.stderr)
import collections; print(collections.Counter(role.values()),file=sys.stderr)
# seeds with names (keep existing OS/sw names otherwise)
seeds=[]
for l in open('seeds.tsv'):
    a,n=l.rstrip('\n').split('\t')
    a=int(a,16)
    if a in names: n=names[a]
    elif n.startswith(('on_','deff_','sw')): n=''   # regenerated above
    seeds.append('%08x\t%s'%(a,n))
have={int(s.split('\t')[0],16) for s in seeds}
for a,n in names.items():
    if a not in have: seeds.append('%08x\t%s'%(a,n))
open('seeds_named.tsv','w').write('\n'.join(sorted(seeds))+'\n')
