import sys,json,glob,collections,numpy as np,os
sys.argv=['x']
import export_anims_lib as E
from analyze import parse
TARGET=[int(x) for x in os.environ.get('DEFFS','22,27,45,85,99,112,115').split(',')]
index=json.load(open(E.OUT+'/index.json'))
done=set()
for fn in sorted(glob.glob('/home/claude/trace/p[0-3].log')):
    ev=parse(fn); ts,dmds=E.load_dmd(fn.replace('.log','.dmd'))
    for i,(t,k,kv) in enumerate(ev):
        if k!='DEFF_START' or kv.get('lr')=='34080': continue
        d=int(kv['id'])
        if d not in TARGET or d in done: continue
        # window: until active != d for 0.3s, max 12s
        w=[];last_active=t;t1=t+12
        for t2,k2,kv2 in ev[i:]:
            if t2>t+12: break
            if 'active' in kv2:
                if kv2['active']==str(d): last_active=t2
                elif t2-last_active>0.3: t1=t2; break
            w.append((t2,k2,kv2))
        if last_active-t<0.3: continue
        meta=E.export({'id':d,'t0':t,'t1':min(t1,last_active+0.05),'ev':w},ts,dmds)
        meta['source']='emulated play (%s)'%os.path.basename(fn)
        index[str(d)]=meta; done.add(d); print('exported',d,fn,round(meta['run_seconds'],2),len(meta['graphics_frames']))
json.dump(index,open(E.OUT+'/index.json','w'))
print('not found',set(TARGET)-done)
