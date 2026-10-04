import json,collections
from fmatch import le,pro,a2f,f2a,seeds,mask,PM,idx
m={int(k,16):int(v,16) for k,v in json.load(open('match2.json')).items()}
used=set(m.values())
add=0
for a,_ in seeds:
    if a in m: continue
    L=mask(le[a2f(a):a2f(a)+20])
    good=[c for c in idx.get(L[:12],[]) if PM[c:c+20]==L and f2a(c) not in used]
    if len(good)==1:
        m[a]=f2a(good[0]); used.add(m[a]); add+=1
print('added',add,len(m))
json.dump({hex(k):hex(v) for k,v in sorted(m.items())},open('match2.json','w'))
