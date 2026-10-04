import struct,collections,sys
LEP='/mnt/project-files/trn_174h.bin'; PRP='/mnt/project-files/tron/pro/TRN174VP.BIN'
le=open(LEP,'rb').read(); pro=open(PRP,'rb').read()
def f2a(o): return o if o<0x40000 else o-0x40000+0x01000000
def a2f(a): return a if a<0x01000000 else a-0x01000000+0x40000
def mask(b):
    out=bytearray(b)
    for i in range(0,len(b)-3,4):
        w=struct.unpack_from('<I',b,i)[0]
        if ((w>>25)&7)==5: out[i:i+3]=b'\0\0\0'          # B/BL
        elif (w&0x0f7f0000)==0x051f0000: out[i:i+2]=b'\0\0'  # ldr pc-rel
        elif (w&0x0e000000)==0x0 and False: pass
    return bytes(out)
# code regions
LEcode=[(0,0x36000),(0x40000,0x140000)]
PRcode=[(0,0x40000),(0x40000,0x140000)]
seeds=[]
for l in open('/home/claude/tron-legacy-le-rom-decryption/rules/tools/ghidra/seeds_final.tsv'):
    p=l.rstrip('\n').split('\t'); seeds.append((int(p[0],16),p[1] if len(p)>1 else ''))
names={}
for l in open('/home/claude/tron-legacy-le-rom-decryption/rules/tools/ghidra/seeds_named.tsv'):
    p=l.rstrip('\n').split('\t')
    if len(p)>1 and p[1]: names[int(p[0],16)]=p[1]
seeds.sort()
PM=mask(pro[:0x140000])
idx=collections.defaultdict(list)
K=12
for i in range(0,0x140000-K,4):
    idx[PM[i:i+K]].append(i)
res={}
for n,(a,_) in enumerate(seeds):
    nxt=seeds[n+1][0] if n+1<len(seeds) else a+64
    ln=min(nxt-a,256)
    if ln<12: continue
    o=a2f(a); L=mask(le[o:o+ln])
    # literal pool words at end may differ: trim trailing words that look like addresses
    cands=idx.get(L[:K],[])
    good=[c for c in cands if PM[c:c+ln]==L]
    if len(good)==1: res[a]=(f2a(good[0]),'exact')
    elif not good:
        # allow literal pool mismatch: compare only up to first literal-looking region (ln//2)
        h=max(12,(ln//2)//4*4)
        good=[c for c in cands if PM[c:c+h]==L[:h]]
        if len(good)==1: res[a]=(f2a(good[0]),'prefix')
print(len(seeds),len(res), collections.Counter(v[1] for v in res.values()))
import json
json.dump({hex(k):[hex(v[0]),v[1],names.get(k,'')] for k,v in res.items()},open('match1.json','w'),indent=0)
