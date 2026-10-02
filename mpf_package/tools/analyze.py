import re,sys,json,collections,pickle
fr,hs=pickle.load(open('/home/claude/work/frames.pkl','rb'))
r2i={h['rid']:i for i,h in enumerate(hs)}
def parse(fn):
    ev=[]
    for line in open(fn):
        p=line.split()
        if len(p)<2: continue
        t=float(p[0]); k=p[1]; kv={}
        for x in p[2:]:
            if '=' in x: a,b=x.split('=',1); kv[a]=b
        if k=='FORCE': kv['id']=p[2]
        if k=='FORCE_END': kv['id']=p[2]
        ev.append((t,k,kv))
    return ev
def windows(ev):
    out=[];cur=None
    for t,k,kv in ev:
        if k=='FORCE': cur={'id':int(kv['id']),'t0':t,'ev':[]}
        elif k=='FORCE_END' and cur: cur['t1']=t; out.append(cur); cur=None
        elif cur: cur['ev'].append((t,k,kv))
    return out
def summarize(w):
    d=w['id']; frames=[]; curdraws=[]; snd=[]; leff=[]; tube=[]
    for t,k,kv in w['ev']:
        if k=='DRAW' and kv.get('deff')==str(d):
            rid=int(kv['rid']); i=r2i.get(rid)
            if i is None: continue
            h=hs[i]
            curdraws.append((i,int(kv['x']),int(kv['y']),h['w'],h['h']))
        elif k=='SHOW' and kv.get('deff')==str(d):
            frames.append((t,curdraws)); curdraws=[]
        elif k=='SND' and kv.get('deff') in (str(d),): snd.append((round(t-w['t0'],3),kv['call']))
        elif k=='LEFF': leff.append((round(t-w['t0'],3),int(kv['id']),kv.get('deff')))
        elif k=='TUBE': tube.append(t)
    return frames,snd,leff
if __name__=='__main__':
    ev=parse(sys.argv[1])
    for w in windows(ev):
        frames,snd,leff=summarize(w)
        big=[f for f in frames if any(ww>=60 for _,_,_,ww,hh in f[1])]
        print(w['id'],round(w['t1']-w['t0'],2),'shows',len(frames),'bigframes',len(big),'snd',snd[:6],'leff',leff[:4])
        if big: print('   first big', big[0][1][:3], 'last', big[-1][1][:2])
