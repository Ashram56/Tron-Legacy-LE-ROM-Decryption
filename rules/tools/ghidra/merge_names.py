import glob,re,struct,collections,os
from romtables import *
R='/mnt/project-files/tron/rules/work/ram/'
api={int(l.split('\t')[0],16) for l in open('sigs.tsv') if l.strip()}
ram={};conf=[]
for f in sorted(glob.glob(R+'*.tsv')):
    if f.endswith('_functions.tsv'): continue
    for l in open(f):
        p=l.rstrip('\n').split('\t')
        if len(p)<2 or not p[0].startswith('0x'): continue
        try: a=int(p[0],16)
        except: continue
        n=re.sub(r'\W','_',p[1].strip())
        if not n: continue
        if a in ram and ram[a]!=n: conf.append(('ram',hex(a),ram[a],n,os.path.basename(f))); continue
        ram[a]=n
fn={}
for f in sorted(glob.glob(R+'*_functions.tsv')):
    for l in open(f):
        p=l.rstrip('\n').split('\t')
        if len(p)<2 or not p[0].startswith('0x'): continue
        try: a=int(p[0],16)
        except: continue
        n=re.sub(r'\W','_',p[1].strip())
        if not n or a in api: continue
        if a in fn and fn[a]!=n: conf.append(('fn',hex(a),fn[a],n,os.path.basename(f))); continue
        fn[a]=n
# unique names
seen=collections.Counter()
for d in (fn,ram):
    for a in sorted(d):
        n=d[a]; seen[n]+=1
        if seen[n]>1: d[a]='%s_%d'%(n,seen[n])
open('ram_symbols.tsv','w').write(''.join('0x%08x\t%s\n'%(a,n) for a,n in sorted(ram.items())))
# seeds: existing named, override with worker names; add data-table code pointers
seeds={}
for l in open('seeds_named.tsv'):
    a,n=l.rstrip('\n').split('\t'); seeds[int(a,16)]=n
starts=sorted(seeds)
import bisect, capstone
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_ARM)
added=0
for o in range(0xc0000,0xf8000,4):
    v=struct.unpack_from('<I',ROM,o)[0]
    if 0x01000000<=v<0x01092000 and v%4==0 and v not in seeds:
        i=bisect.bisect_left(starts,v)
        if i<len(starts) and 0<starts[i]-v<=8:
            ins=list(md.disasm(ROM[foff(v):foff(v)+4],v))
            if ins and ins[0].mnemonic in ('mov','ldr','push','stmdb'):
                seeds[v]=''; added+=1
for a,n in fn.items():
    seeds[a]=n
open('seeds_final.tsv','w').write(''.join('%08x\t%s\n'%(a,n) for a,n in sorted(seeds.items())))
print('ram',len(ram),'fn',len(fn),'ptr seeds added',added,'conflicts',len(conf))
for c in conf[:40]: print(c)
