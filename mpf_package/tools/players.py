import pickle,re,struct,collections,json
funcs,order,callees,callers,a2n=pickle.load(open('cg.pkl','rb'))
ROM=open('/mnt/project-files/trn_174h.bin','rb').read()
lib=json.load(open('/mnt/project-files/tron/mpf_package/media/dmd_library/index.json'))
anyimg={i:o['anim'] for o in lib for i in range(o['first_image'],o['last_image']+1)}
P=['FUN_01023ddc','FUN_01023edc','FUN_01023fe4','FUN_01023cb0']
pat=re.compile(r'(FUN_01023ddc|FUN_01023edc|FUN_01023fe4|FUN_01023cb0)\(([^;]*)\);')
uses=[]
for f,d in funcs.items():
    for m in pat.finditer(d['body']):
        args=[a.strip() for a in m.group(2).split(',')]
        try: a0=int(args[0],0); a1=int(args[1],0); spd=int(args[2],0)
        except: a0=a1=spd=None
        uses.append((f,m.group(1),a0,a1,spd,args))
# reverse refs: ROM u32 tables pointing to function addr
data=ROM[:0x800000]
def refs_to(addr):
    out=[];b=struct.pack('<I',addr);s=0
    while True:
        k=data.find(b,s)
        if k<0: break
        if k%4==0: out.append(k)
        s=k+1
    return out
# map table addr -> code functions referencing (via DAT comments =0x4xxxxxx near)
datref=collections.defaultdict(set)
for f,d in funcs.items():
    for v in re.findall(r'=0x(4[0-9a-f]{6})\b',d['body']): datref[int(v,16)-0x4000000].add(f)
res={}
for f,p,a0,a1,spd,args in uses:
    if a0 is None or a0 not in anyimg: continue
    an=anyimg[a0]
    who=set(callers.get(f,()))
    tabs=[]
    if not who:
        for t in refs_to(funcs[f]['addr']):
            # find table start: walk back while entries look like code ptrs
            st=t
            while st>=4 and 0x1000000<=struct.unpack_from('<I',data,st-4)[0]<0x1080000: st-=4
            tabs.append((t,st,(t-st)//4))
            for tt in range(st-8,st+8,4): who|=datref.get(tt,set())
    res.setdefault(an,[]).append({'fn':f,'player':p,'first':a0,'last':a1,'ticks':spd,'callers':sorted(who),'tables':tabs})
json.dump(res,open('players.json','w'),indent=0)
unseen=[o['anim'] for o in lib if not o['seen_in_deffs']]
print(len(uses), 'anims via players',len(res),'unseen covered',sum(1 for a in unseen if a in res))
for a in sorted(res):
    r=res[a][0]; print(a, 'seen' if lib[a]['seen_in_deffs'] else 'UNSEEN', r['fn'],r['first'],r['last'],r['ticks'],r['callers'][:4],[(hex(t),hex(s),i) for t,s,i in r['tables']][:2])
