import json,struct,collections,bisect
from fmatch import le,pro,a2f,f2a,seeds
G='/home/claude/tron-legacy-le-rom-decryption/rules/tools/ghidra/'
m={int(k,16):int(v,16) for k,v in json.load(open('match2.json')).items()}
names={int(k,16):v for k,v in json.load(open('le_names.json')).items()}
for l in open(G+'seeds_final.tsv'):
    p=l.rstrip('\n').split('\t')
    if len(p)>1 and p[1]: names.setdefault(int(p[0],16),p[1])
seedset=sorted(a for a,_ in seeds)
def fend(a):
    i=bisect.bisect_right(seedset,a); return seedset[i] if i<len(seedset) else a+0x400
# RAM map from pc-relative literal loads at equal positions
votes=collections.defaultdict(collections.Counter)
for la,pa in m.items():
    n=fend(la)-la
    for k in range(0,min(n,0x1000),4):
        lw=struct.unpack_from('<I',le,a2f(la)+k)[0]; pw=struct.unpack_from('<I',pro,a2f(pa)+k)[0]
        if (lw&0x0f7f0000)==0x051f0000 and (pw&0x0f7f0000)==0x051f0000 and (lw&0xf000)==(pw&0xf000):
            lo=(lw&0xfff)*(1 if lw&0x800000 else -1); po=(pw&0xfff)*(1 if pw&0x800000 else -1)
            try:
                lv=struct.unpack_from('<I',le,a2f(la+k+8+lo))[0]; pv=struct.unpack_from('<I',pro,a2f(pa+k+8+po))[0]
            except Exception: continue
            votes[lv][pv]+=1
ram={}
for lv,c in votes.items():
    pv,n=c.most_common(1)[0]
    if n>=1 and len(c)==1 or n>=2*sum(c.values())//3: ram[lv]=pv
ramsym=[]
for l in open(G+'ram_symbols.tsv'):
    p=l.split()
    a=int(p[0],16)
    if a in ram: ramsym.append((ram[a],p[1]))
print('ram syms',len(ramsym),'of 253; literal pairs',len(ram))
# seeds for pro
out=[]
used=set()
for la,pa in sorted(m.items(),key=lambda x:x[1]):
    n=names.get(la,'')
    if n.startswith('FUN_'): n=''
    if n in used: n=''
    if n: used.add(n)
    out.append('%08x\t%s'%(pa,n))
open('pro_seeds.tsv','w').write('\n'.join(out)+'\n')
sig=[]
for l in open(G+'sigs.tsv'):
    if not l.strip() or l.startswith('#'): continue
    a,s=l.rstrip('\n').split('\t',1); a=int(a,16)
    if a in m: sig.append('%08x\t%s'%(m[a],s))
open('pro_sigs.tsv','w').write('\n'.join(sig)+'\n')
open('pro_ram_symbols.tsv','w').write('\n'.join('0x%08x\t%s'%x for x in sorted(set(ramsym)))+'\n')
json.dump({hex(k):hex(v) for k,v in ram.items()},open('ram_map.json','w'))
print('seeds',len(out),'named',len(used),'sigs',len(sig))
