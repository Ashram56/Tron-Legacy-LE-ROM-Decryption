"""CONTROL ONLY (confirm, never source): how many effects reproduce the reference captures exactly (columns 41-127, first 20 frames)."""
import sys,glob,os,ast
sys.path.insert(0,'tools')
import deff_frames as F
from PIL import Image, ImageSequence
INIT=tuple(int(x,16) for x in os.environ.get('INIT','').split(',') if x)
base='mpf_package/media/dmd'
res={}
for d in range(1,146):
    g=glob.glob(base+'/deff_%03d_*/reference_capture.gif'%d)
    if not g: continue
    try: snaps,_=F.frames(d,init=INIT)
    except Exception as e: res[d]=None; continue
    mine=[F.mix(a,b) for r0,r1,a,b in snaps]
    if not mine: res[d]=None; continue
    refs=[[v//17 for v in f.convert('L').resize((128,32)).get_flattened_data()] for f in ImageSequence.Iterator(Image.open(g[0]))]
    ex=0
    for rr in refs[:20]:
        if any(sum(1 for y in range(32) for x in range(41,128) if abs(rr[y*128+x]-f[y*128+x])>1)==0 for f in mine): ex+=1
    res[d]=(ex,min(len(refs),20))
full=[d for d,v in res.items() if v and v[0]==v[1]]
some=[d for d,v in res.items() if v and v[0]>0]
print('INIT',INIT,'all-checked-exact',len(full),'some-exact',len(some),'none',len([1 for v in res.values() if v is None]))
