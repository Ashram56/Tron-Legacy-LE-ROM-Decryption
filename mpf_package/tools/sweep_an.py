import json,pickle,collections
fr,hs=pickle.load(open('frames.pkl','rb'))
r2i={h['rid']:i for i,h in enumerate(hs)}
lib=json.load(open('animlib.json')); anyidx={i:o['anim'] for o in lib for i in range(o['first_image'],o['last_image']+1)}
sw_deff=collections.defaultdict(collections.Counter); deff_anims=collections.defaultdict(set); sw_leff=collections.defaultdict(collections.Counter)
newseen=set()
for b in range(4):
    cur=None
    for line in open(f'/home/claude/trace/s{b}.log'):
        p=line.split()
        if len(p)<2: continue
        if p[1]=='SWITCH': cur=int(p[2]); continue
        kv=dict(x.split('=',1) for x in p[2:] if '=' in x)
        if p[1]=='DEFF_START' and kv.get('lr')!='34080' and cur: sw_deff[cur][int(kv['id'])]+=1
        if p[1]=='LEFF' and cur: sw_leff[cur][int(kv['id'])]+=1
        if p[1]=='DRAW':
            i=r2i.get(int(kv['rid']))
            if i in anyidx: deff_anims[int(kv.get('deff',0))].add(anyidx[i]); newseen.add(anyidx[i])
sw=json.load(open('/mnt/project-files/tron/switch_names.json'))
for s in sorted(sw_deff): print(s,sw[str(s)],dict(sw_deff[s]),dict(sw_leff[s]))
prev=set(o['anim'] for o in lib if o['seen_in_deffs'])
print('new anims',sorted(newseen-prev))
print({d:sorted(a) for d,a in deff_anims.items()})
json.dump({'sw_deff':{k:dict(v) for k,v in sw_deff.items()},'sw_leff':{k:dict(v) for k,v in sw_leff.items()},'deff_anims':{k:sorted(v) for k,v in deff_anims.items()}},open('sweep.json','w'))
