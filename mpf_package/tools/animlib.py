import json,pickle,collections,struct,re
fr,hs=pickle.load(open('frames.pkl','rb'))
funcs,order,callees,callers,a2n=pickle.load(open('cg.pkl','rb'))
ROM=open('/mnt/project-files/trn_174h.bin','rb').read()
anims=[];cur=[]
for i in range(len(hs)):
    if cur and (hs[i]['w'],hs[i]['h'])!=(hs[cur[-1]]['w'],hs[cur[-1]]['h']): anims.append(cur); cur=[]
    cur.append(i)
    if hs[i]['flags']&2: anims.append(cur); cur=[]
if cur: anims.append(cur)
big=[a for a in anims if hs[a[0]]['w']>=60 and hs[a[0]]['h']>=20]
starts={a[0]:k for k,a in enumerate(big)}
anyidx={i:k for k,a in enumerate(big) for i in a}
idx=json.load(open('anims/index.json'))
seen=collections.defaultdict(set)
for d,v in idx.items():
    for i in v['images_used']:
        if i in anyidx: seen[anyidx[i]].add(int(d))
# static: deff function tree -> constants & tables
deffn={i:struct.unpack_from('<I',ROM,0xe1350+i*8)[0] for i in range(146)}
static=collections.defaultdict(set)
for d in range(1,146):
    f=a2n.get(deffn[d]); 
    if not f: continue
    tree={f}; fr_=[f]
    for _ in range(2):
        nf=[]
        for g in fr_:
            for c in callees.get(g,()):
                if c not in tree and funcs[c]['addr']>=0x1000000 and not c.startswith('deff_') and len(callers.get(c,()))<6: tree.add(c); nf.append(c)
        fr_=nf
    for g in tree:
        body=funcs[g]['body']
        for v in re.findall(r'\b(0x[0-9a-f]+|\d+)\b',re.sub(r'/\*.*?\*/','',body)):
            v=int(v,0)
            if v in starts: static[starts[v]].add(d)
        for v in re.findall(r'=0x(40[0-9a-f]{5})\b',body):
            a=int(v,16)-0x4000000
            for k in range(64):
                w=struct.unpack_from('<I',ROM,a+k*4)[0]
                if w in starts: static[starts[w]].add(d)
                for h in struct.unpack_from('<2H',ROM,a+k*4):
                    if h in starts and h>500: static[starts[h]].add(d)
out=[]
for k,a in enumerate(big):
    out.append({'anim':k,'first_image':a[0],'last_image':a[-1],'frames':len(a),'w':hs[a[0]]['w'],'h':hs[a[0]]['h'],
                'seen_in_deffs':sorted(seen.get(k,())),'referenced_by_deff_code':sorted(static.get(k,()))})
json.dump(out,open('animlib.json','w'),indent=0)
print(sum(1 for o in out if o['seen_in_deffs']), sum(1 for o in out if not o['seen_in_deffs'] and o['referenced_by_deff_code']), sum(1 for o in out if not o['seen_in_deffs'] and not o['referenced_by_deff_code']))
for o in out:
    if not o['seen_in_deffs']: print(o['anim'],o['first_image'],o['frames'],o['w'],o['referenced_by_deff_code'])
