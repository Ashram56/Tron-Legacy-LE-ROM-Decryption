import sys, json, pickle, numpy as np, os, collections
from PIL import Image
sys.argv=['x']
from analyze import parse, windows
fr,hs=pickle.load(open('frames.pkl','rb'))
r2i={h['rid']:i for i,h in enumerate(hs)}
TEXT_LR={'290dc','2910c'}
OUT='/home/claude/work/anims'; os.makedirs(OUT,exist_ok=True)
def load_dmd(fn):
    d=open(fn,'rb').read(); n=len(d)//4104
    ts=np.frombuffer(b''.join(d[k*4104:k*4104+8] for k in range(n)),'<f8')
    return ts,[np.frombuffer(d[k*4104+8:(k+1)*4104],np.uint8).reshape(32,128) for k in range(n)]
def to_img(a, alpha=None):
    g=(np.minimum(a,15).astype(np.uint16)*17).astype(np.uint8)
    if alpha is None: return Image.fromarray(g,'L')
    return Image.fromarray(np.dstack([g,g,g,alpha]),'RGBA')
def frames_to_seq(frames):  # frames: list of (t, array, alpha) -> dedup with durations
    seq=[]
    for t,a,al in frames:
        key=(a.tobytes(), None if al is None else al.tobytes())
        if seq and seq[-1]['key']==key: continue
        seq.append({'t':t,'a':a,'al':al,'key':key})
    for k in range(len(seq)):
        seq[k]['dur']=(seq[k+1]['t']-seq[k]['t']) if k+1<len(seq) else None
    return seq
def save_gif(seq,path,end_t,scale=4,alpha=False):
    if not seq: return
    ims=[];durs=[]
    for k,s in enumerate(seq):
        a=s['a']; g=(np.minimum(a,15)*17).astype(np.uint8)
        if alpha and s['al'] is not None: g=np.where(s['al']>0,g,0).astype(np.uint8)
        im=Image.fromarray(g,'L').resize((128*scale,32*scale),Image.NEAREST)
        ims.append(im.convert('P'))
        d=s['dur'] if s['dur'] is not None else max(0.05,end_t-s['t'])
        durs.append(max(20,int(round(d*1000))))
    ims[0].save(path,save_all=True,append_images=ims[1:],duration=durs,loop=0,optimize=False)
index={}
for b in range(4):
    ev=parse(f'/home/claude/trace/f{b}.log'); ts,dmds=load_dmd(f'/home/claude/trace/f{b}.dmd')
    for w in windows(ev):
        d=w['id']; t0,t1=w['t0'],w['t1']
        # graphics layer
        canvas=None; gframes=[]; draws=[]; used=collections.Counter(); snd=[]; leff=[]; tubes=[]
        for t,k,kv in w['ev']:
            if k=='DRAW' and kv.get('deff')==str(d) and kv.get('lr') not in TEXT_LR:
                i=r2i.get(int(kv['rid']))
                if i is not None: draws.append((i,int(kv['x']),int(kv['y'])))
            elif k=='SHOW' and kv.get('deff')==str(d):
                a=np.zeros((32,128),np.uint8); al=np.zeros((32,128),np.uint8)
                for i,x,y in draws:
                    img=fr[i]; h,wd=img.shape
                    x0,y0=max(0,x),max(0,y); x1,y1=min(128,x+wd),min(32,y+h)
                    if x1<=x0 or y1<=y0: continue
                    sub=img[y0-y:y1-y, x0-x:x1-x]; m=sub!=255
                    a[y0:y1,x0:x1][m]=sub[m]; al[y0:y1,x0:x1][m]=255
                    used[i]+=1
                if draws: gframes.append((t,a,al))
                draws=[]
            elif k=='SND' and kv.get('deff')==str(d): snd.append({'t_ms':int((t-t0)*1000),'call':'0x%03x'%int(kv['call'],16)})
            elif k=='LEFF': leff.append({'t_ms':int((t-t0)*1000),'leff':int(kv['id']),'from_deff':kv.get('deff')})
            elif k=='TUBE': tubes.append(t)
        gseq=frames_to_seq(gframes)
        # reference capture
        sel=[(ts[k],dmds[k],None) for k in range(len(ts)) if t0<=ts[k]<=t1]
        rseq=frames_to_seq(sel)
        dd=f'{OUT}/deff_{d:03d}'; os.makedirs(dd+'/frames',exist_ok=True)
        meta={'deff':d,'run_seconds':round(t1-t0,3),'ended_by_timeout':(t1-t0)>11.9,
              'graphics_frames':[],'images_used':sorted(used),'sounds':snd,'light_effects':[l for l in leff if l['leff']!=10 or l['from_deff']==str(d)],
              'reference_frames':len(rseq)}
        for k,s in enumerate(gseq):
            to_img(s['a'],s['al']).save(f'{dd}/frames/{k:03d}.png')
            meta['graphics_frames'].append({'file':f'frames/{k:03d}.png','t_ms':int((s['t']-t0)*1000),'duration_ms':int(round((s['dur'] if s['dur'] is not None else max(0.05,t1-s['t']))*1000))})
        if gseq: save_gif(gseq,f'{dd}/animation.gif',t1,scale=1,alpha=True)
        if rseq: save_gif(rseq,f'{dd}/reference_capture.gif',t1,scale=1)
        if rseq: save_gif(rseq,f'{dd}/reference_capture_x4.gif',t1,scale=4)
        json.dump(meta,open(dd+'/timing.json','w'),indent=1)
        index[d]=meta
        print(d,len(gseq),len(rseq),len(snd),len(leff))
json.dump(index,open(OUT+'/index.json','w'))
