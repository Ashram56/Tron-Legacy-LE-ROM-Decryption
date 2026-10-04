import json,struct,collections
from fmatch import le,pro,a2f,f2a,seeds,names
m={int(k,16):int(v[0] if isinstance(v,list) else v,16) for k,v in json.load(open(__import__('sys').argv[1])).items()}
seedset=sorted(a for a,_ in seeds)
import bisect
def fend(a):
    i=bisect.bisect_right(seedset,a)
    return seedset[i] if i<len(seedset) else a+0x400
def bls(d,a,end):
    out=[];o=a2f(a)
    for k in range(0,min(end-a,0x2000),4):
        w=struct.unpack_from('<I',d,o+k)[0]
        if (w>>24)==0xeb:  # BL always
            off=w&0xffffff
            if off&0x800000: off-=0x1000000
            out.append(a+k+8+off*4)
        # stop at function end heuristics: ldmfd ... pc or bx lr followed by literal
    return out
def pro_end(pa,lelen):
    return pa+lelen
changed=True; rounds=0
while changed and rounds<10:
    changed=False; rounds+=1
    for la,pa in list(m.items()):
        le_end=fend(la); L=bls(le,la,le_end); P=bls(pro,pa,pa+(le_end-la)+64)
        P=P[:len(L)] if len(P)>=len(L) else P
        if len(L)!=len(P) or not L: continue
        for x,y in zip(L,P):
            if x not in m and x in set(seedset):
                m[x]=y; changed=True
    print('round',rounds,len(m))
# consistency: duplicates in pro targets
c=collections.Counter(m.values()); dups={k for k,v in c.items() if v>1}
print('dup targets',len(dups))
json.dump({hex(k):hex(v) for k,v in sorted(m.items()) if v not in dups},open('match2.json','w'))
print('named matched',sum(1 for k,v in m.items() if k in names and v not in dups),'of',len(names))
