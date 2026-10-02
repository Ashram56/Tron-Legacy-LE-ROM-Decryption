import sys,glob,json,collections,pickle
sys.path.insert(0,'/home/claude/work')
from loganim import r2i,i2a
res={'deff_seen':collections.Counter(),'deff_anims':collections.defaultdict(set),'clip128':collections.Counter(),
     'game_start':[], 'ball_start':[], 'drain':[], 'deff_after_switch':collections.defaultdict(collections.Counter),'rendered':collections.defaultdict(int)}
for fn in sorted(glob.glob('/home/claude/trace/p[0-3].log')):
    ev=[]
    for line in open(fn):
        p=line.split()
        if len(p)<2: continue
        try: t=float(p[0])
        except: continue
        ev.append((t,p[1],p[2:]))
    lastsw=(0,None); marks=[]
    for t,k,a in ev:
        kv=dict(x.split('=',1) for x in a if '=' in x)
        if k=='SWITCH': lastsw=(t,a[0])
        elif k=='PLAY': marks.append((t,a[0],kv))
        elif k=='DEFF_START' and kv.get('lr')!='34080':
            d=int(kv['id']); res['deff_seen'][d]+=1
            if t-lastsw[0]<0.4: res['deff_after_switch'][d][lastsw[1]]+=1
        elif k=='DRAW' and kv.get('lr','2910c') not in ('2910c','290dc'):
            a_=i2a.get(r2i.get(int(kv.get('rid',0))))
            if a_: res['deff_anims'][int(kv.get('deff',0))].add(a_)
            res['rendered'][int(kv.get('deff',0))]+=1
        elif k=='CLIP128': res['clip128'][kv['idx']]+=1
    # windows
    def window(t0,t1):
        out=[]
        for t,k,a in ev:
            if t0<=t<=t1 and (k in('SND','LEFF') or (k=='DEFF_START' and 'lr=34080' not in a)):
                out.append(f"{t-t0:.2f} {k} {' '.join(x for x in a if x.startswith(('id=','call=','lr=')))}")
        return out
    for t,m,kv in marks:
        if m=='start': res['game_start'].append((fn,t,window(t,t+12)[:40]))
        if m=='drain' and kv.get('inplay')=='0': res['drain'].append((fn,t,window(t,t+15)[:40]))
print('deffs seen in play:',sorted(res['deff_seen']))
print('clip128',res['clip128'])
for d in sorted(res['deff_anims']): print(d,sorted(res['deff_anims'][d]))
json.dump({'deff_seen':res['deff_seen'],'deff_anims':{k:sorted(v) for k,v in res['deff_anims'].items()},
  'deff_after_switch':{k:dict(v) for k,v in res['deff_after_switch'].items()},'game_start':res['game_start'],'drain':res['drain'],'rendered':res['rendered']},open('play.json','w'),indent=0)
