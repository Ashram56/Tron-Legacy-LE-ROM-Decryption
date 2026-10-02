import json,re,struct,pickle,collections,bisect
rom=open('/mnt/project-files/trn_174h.bin','rb').read()
funcs,order,callees,callers,a2n=pickle.load(open('cg.pkl','rb'))
lib=json.load(open('/mnt/project-files/tron/mpf_package/media/dmd_library/index.json'))
firsts=[a['first_image'] for a in lib]
def anim_of(i):
    k=bisect.bisect_right(firsts,i)-1
    if k<0: return None
    a=lib[k]; return a['anim'] if a['first_image']<=i<=a['last_image'] else None
T=json.load(open('tables.json')); wr=T['wrappers']
deffaddr={i:struct.unpack_from('<I',rom,0xe1350+i*8)[0] for i in range(146)}
deffname={a2n.get(a):i for i,a in deffaddr.items() if a2n.get(a)}
fa=sorted(a2n)
def near(v):
    if v in a2n: return a2n[v]
    k=bisect.bisect_left(fa,v)
    if k<len(fa) and fa[k]-v<=16: return a2n[fa[k]]
    return None
def tbl(base,n): return [near(struct.unpack_from('<I',rom,base+4*i)[0]) for i in range(n)]
rules=[]  # (deff, rule, list of wrappers)
rules.append((48,'random pick of 12 clips (code: FUN_0000c6b4(12) at 0x1008920)',tbl(0xd2804,12)))
rules.append((49,'random pick of 12 clips (same list as effect 48)',tbl(0xd2804,12)))
lc=[struct.unpack_from('<4H',rom,0xd2ffc+8*i) for i in range(6)]
d3084=tbl(0xd3084,24)
for d,field in ((87,0),(88,2),(89,3)):
    rules.append((d,'clip chosen by Light Cycle multiball level 1-6 (code: table 0x40d2ffc field %d)'%field,[d3084[lc[i][field]] for i in range(6)]))
# check deff 87 actual field
d327c=tbl(0xd327c,5)
rules.append((68,'random pick of 3 clips',d327c[0:3]))
rules.append((69,'random pick of 2 clips',d327c[3:5]))
rules.append((111,'random pick of 11 clips',tbl(0xd337c,11)))
rules.append((97,'random pick of 2 clips',tbl(0xd6fd4,2)))
d2ac4=tbl(0xd2ac4,74)
rules.append((128,'clip number 0-29 passed by the caller (no caller found in game code; inferred: debug clip viewer)',d2ac4[:30]))
rules.append((129,'clip number 30-73 passed by the caller (no caller found in game code; inferred: debug clip viewer)',d2ac4[30:74]))
# anim -> uses
uses=collections.defaultdict(list)
for d,rule,ws in rules:
    for k,w in enumerate(ws):
        for (f,l,t) in wr.get(w,[]) if w else []:
            fi = int(f,0) if re.match(r'^(0x[0-9a-f]+|\d+)$',f) else None
            a=anim_of(l)
            uses[a].append({'deff':d,'how':rule,'variant':k,'first':fi,'last':l,'ticks':t,'via':w})
# unresolved wrappers in tables (None/raw) noted
# direct references: functions with constant image refs -> deffs reaching them
C=open('/mnt/project-files/tron/code/tron_game_decompiled.c').read().split('\n')
fn_at=[];cur=None
for l in C:
    m=re.match(r'// ==== ([0-9a-f]+) (\S+)',l)
    if m: cur=m.group(2)
    fn_at.append(cur)
direct=collections.defaultdict(set)
for i,l in enumerate(C):
    code=l.split('/*')[0]
    m=re.search(r'(FUN_0002b378|FUN_00028ca8|FUN_00028d5c|FUN_01023(?:fe4|edc|ddc|cb0))\((0x[0-9a-f]+|\d+)',code)
    if m:
        v=int(m.group(2),0); a=anim_of(v)
        if a is not None and v>=177: direct[a].add(fn_at[i])
    m=re.search(r'Var\d+ = (0x[0-9a-f]+);',code)
    if m:
        v=int(m.group(1),0); a=anim_of(v)
        if a is not None and v>=1400: direct[a].add(fn_at[i])
def updeffs(f,depth=4):
    out=set(); fr={f}; seen={f}
    for _ in range(depth+1):
        nf=set()
        for g in fr:
            if g in deffname: out.add(deffname[g]); continue
            for c in callers.get(g,()):
                if c not in seen: seen.add(c); nf.add(c)
        fr=nf
    return out
tabled={w for _,_,ws in rules for w in ws if w}
res={}
for a in lib:
    k=a['anim']
    r={'anim':k,'name':a['name'],'seen_in_deffs':a['seen_in_deffs'],'clip_uses':uses.get(k,[]),'code_refs':{}}
    for f in direct.get(k,()):
        if f in tabled: continue
        r['code_refs'][f]=sorted(updeffs(f))
    res[k]=r
json.dump(res,open('anim_resolve.json','w'),indent=1)
unres=[k for k,r in res.items() if not r['seen_in_deffs'] and not r['clip_uses'] and not any(r['code_refs'].values())]
print('unresolved',len(unres),unres)
for k in unres: print(k,res[k]['code_refs'])
