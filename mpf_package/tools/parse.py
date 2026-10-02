import re,json,glob,collections,sys
PAT=sys.argv[1]; OUTF=sys.argv[2]
caps={}
for f in sorted(glob.glob(PAT)):
    cur=None
    for l in open(f):
        p=l.split()
        if len(p)<3: continue
        t=float(p[0]) if p[0][0].isdigit() else None
        if p[1]=='BEGIN':
            key=f"{p[2]}:{p[3].split('=')[1]}"; cur={'id':int(p[2]),'par':int(p[3].split('=')[1]),'t0':t,'frames':[],'coils':[],'snd':[],'tube':[],'leff':[],'deff':[],'shaker':[],'status':None}; caps[key]=cur
        elif cur is None: continue
        elif p[1]=='RET': cur['created']=p[3]=='created'
        elif p[1]=='F' and int(p[2])==cur['id']: cur['frames'].append((round(t-cur['t0'],4),p[3]))
        elif p[1]=='END' and int(p[2])==cur['id']: cur['status']=p[3]; cur['dur']=round(t-cur['t0'],4); cur=None
        elif p[1] in('COIL',) and int(p[2])==cur['id']: cur['coils'].append((round(t-cur['t0'],4),int(p[3].split('=')[1]),int(p[4].split('=')[1])))
        elif p[1]=='COILGRP' and int(p[2])==cur['id']: cur['coils'].append((round(t-cur['t0'],4),'grp'+p[3].split('=')[1],int(p[4].split('=')[1])))
        elif p[1]=='SND' and int(p[2])==cur['id']: cur['snd'].append((round(t-cur['t0'],4),p[3].split('=')[1]))
        elif p[1]=='TUBE' and p[3]=='inleff=%d'%cur['id']: cur['tube'].append((round(t-cur['t0'],4),int(p[2])))
        elif p[1]=='LEFFSTART' and p[4]=='inleff=%d'%cur['id']: cur['leff'].append((round(t-cur['t0'],4),int(p[2])))
        elif p[1]=='DEFF' and p[3]=='inleff=%d'%cur['id']: cur['deff'].append((round(t-cur['t0'],4),int(p[2])))
        elif p[1]=='SHAKER' and int(p[2])==cur['id']: cur['shaker'].append((round(t-cur['t0'],4),p[3],p[4]))
json.dump(caps,open(OUTF,'w'))
st=collections.Counter((c['status'],bool(c['frames']) and any(int(h[:20],16) for _,h in c['frames'])) for c in caps.values())
print(len(caps),st)
for k,c in sorted(caps.items(),key=lambda x:(x[1]['id'],x[1]['par'])):
    lamps=set()
    for _,h in c['frames']:
        m=int(h[:20],16)
        for i in range(80):
            if m>>(79-i)&1: lamps.add(i+1)
    print(k,c['status'],c.get('dur'),'frames',len(c['frames']),'lamps',len(lamps),'coils',len(c['coils']),'snd',len(c['snd']),'tube',c['tube'][:2],'leff',c['leff'][:3],'deff',c['deff'][:2],'shk',c['shaker'][:1])
