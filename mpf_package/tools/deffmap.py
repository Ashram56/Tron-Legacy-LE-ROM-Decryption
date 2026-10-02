import pickle,re,collections,struct,json
funcs,order,callees,callers,a2n=pickle.load(open('cg.pkl','rb'))
ROM=open('/mnt/project-files/trn_174h.bin','rb').read()
deffn={}
for i in range(146):
    fn,fl=struct.unpack_from('<II',ROM,0xe1350+i*8); deffn[i]=(fn,fl)
fn2deff={}
for i,(fn,fl) in deffn.items():
    if fn and fn!=0x1000000: fn2deff.setdefault(fn,[]).append(i)
starts=collections.defaultdict(set)
for f,d in funcs.items():
    for m in re.finditer(r'deff_start(?:_ex2?)?\((0x[0-9a-f]+|\d+)',d['body']):
        starts[int(m.group(1),0)].add(f)
def strings_of(f,depth=1):
    seen={f}; fr=[f]; out=[]
    for _ in range(depth):
        nf=[]
        for g in fr:
            for c in callees.get(g,()):
                if c not in seen and funcs[c]['addr']>=0x1000000: seen.add(c); nf.append(c)
        fr=nf
    for g in seen:
        for s in re.findall(r'0x[0-9a-f]+ "([^"]+)"',funcs[g]['body']): out.append(s)
    return list(dict.fromkeys(out))
def up_switches(f,maxd=6):
    res={}; fr={f}; seen={f}
    for d in range(1,maxd+1):
        nf=set()
        for g in fr:
            for c in callers.get(g,()):
                if c in seen: continue
                seen.add(c); nf.add(c)
                if c.startswith('sw') and re.match(r'sw\d\d_',c): res.setdefault(c,d)
        fr=nf
    return res
def near_on(f,maxd=3):
    res={}; fr={f}; seen={f}
    for d in range(0,maxd+1):
        for g in fr:
            if g.startswith('on_'): res.setdefault(g,d)
        nf=set()
        for g in fr:
            for c in list(callers.get(g,()))+list(callees.get(g,())):
                if c not in seen: seen.add(c); nf.add(c)
        fr=nf
    return res
oaddrs=sorted((d['addr'],f) for f,d in funcs.items() if f.startswith('on_'))
def loc_on(addr):
    best=None
    for a,f in oaddrs:
        if a<=addr and addr-a<0x3000: best=f
    return best
out={}
for i in range(1,146):
    fn,fl=deffn[i]
    dname=a2n.get(fn,'?')
    sites=sorted(starts.get(i,()))
    sw={};ons={}
    for s in sites:
        for k,v in up_switches(s).items(): sw[k]=min(v,sw.get(k,99))
        for k,v in near_on(s).items(): ons[k]=min(v,ons.get(k,99))
    out[i]=dict(fn=hex(fn),flags=hex(fl),priority=(fl>>16)&0xff,looping=bool(fl&1),name=dname,
        strings=strings_of(dname) if dname in funcs else [],
        started_from=sites,switches=dict(sorted(sw.items(),key=lambda x:x[1])),
        features=dict(sorted(ons.items(),key=lambda x:x[1])),
        feature_by_location=loc_on(fn) if fn>=0x1000000 else None)
json.dump(out,open('deff_static.json','w'),indent=1)
for i in [46,55,62,71,25,2,3]:
    print(i,out[i])
