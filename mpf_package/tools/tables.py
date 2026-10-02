import json,re,struct,pickle,collections,bisect
rom=open('/mnt/project-files/trn_174h.bin','rb').read()
funcs,order,callees,callers,a2n=pickle.load(open('cg.pkl','rb'))
lines=open('/mnt/project-files/tron/code/tron_game_decompiled.c').read().split('\n')
# wrappers: functions whose body calls a player with constant range
wr={}
cur=None
for l in lines:
    m=re.match(r'// ==== ([0-9a-f]+) (\S+)',l)
    if m: cur=(int(m.group(1),16),m.group(2)); continue
    m=re.search(r'FUN_01023(fe4|edc|ddc|cb0)\(([^,]+),(?:&DAT_0000)?(0x[0-9a-f]+|\d+|[0-9a-f]{4}),(\d+)',l)
    if m and cur:
        f=m.group(2).replace('&DAT_0000','0x'); lv=m.group(3); lv=int(lv,0) if lv.startswith('0x') or '&DAT' not in l.split(m.group(2))[1][:12] and lv.isdigit() else int(lv,16)
        wr.setdefault(cur[1],[]).append((f,lv,int(m.group(4))))
n2a={v:k for k,v in a2n.items()}
def f2a(off): return off-0x40000+0x1000000
def a2f(a): return a-0x1000000+0x40000
# find all pointer table runs containing wrapper addresses
wset={n2a[n]:n for n in wr if n in n2a}
runs=[]
seen=set()
for off in range(0,0x800000-4,4):
    v=struct.unpack_from('<I',rom,off)[0]
    if v in wset and off not in seen:
        s=off
        while True:
            pv=struct.unpack_from('<I',rom,s-4)[0]
            if pv in a2n or 0x1000000<=pv<0x1060000: s-=4
            else: break
        e=off
        while True:
            nv=struct.unpack_from('<I',rom,e+4)[0]
            if nv in a2n or 0x1000000<=nv<0x1060000: e+=4
            else: break
        for o in range(s,e+4,4): seen.add(o)
        runs.append((s,e))
out=[]
for s,e in runs:
    ents=[a2n.get(struct.unpack_from('<I',rom,o)[0],hex(struct.unpack_from('<I',rom,o)[0])) for o in range(s,e+4,4)]
    # code refs to any address within table
    refs=[]
    for o in range(s,e+4,4):
        for m in re.finditer(re.escape(struct.pack('<I',f2a(o))),rom[:0x800000]):
            refs.append((hex(f2a(o)),hex(f2a(m.start()))))
    out.append({'start':hex(f2a(s)),'n':len(ents),'refs':refs,'ents':ents})
    print(hex(f2a(s)),len(ents),refs[:4],ents[:3])
json.dump({'tables':out,'wrappers':wr},open('tables.json','w'))
