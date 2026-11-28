#!/usr/bin/env python3
"""CONTROL ONLY (confirm, never source): compare generated frames with the reference captures, columns 41-127."""
import sys,glob,os
sys.path.insert(0,'tools')
import deff_frames as F
from PIL import Image, ImageSequence
base='mpf_package/media/dmd'
dirs={int(os.path.basename(d).split('_')[1]):d for d in glob.glob(base+'/deff_*')}
# per effect: best match of each reference frame vs generated frames, ignoring columns 0-40 (status panel); report diff pixels
out=[]
for d in sorted(dirs):
    g=os.path.join(dirs[d],'reference_capture.gif')
    if not os.path.exists(g): continue
    try: snaps,_=F.frames(d)
    except Exception: continue
    mine=[F.mix(a,b) for r0,r1,a,b in snaps]
    if not mine: out.append((d,'none')); continue
    refs=[list(f.convert('L').resize((128,32)).getdata()) for f in ImageSequence.Iterator(Image.open(g))]
    best=[]
    for r in refs[:20]:
        rr=[v//17 for v in r]
        m=min(sum(1 for y in range(32) for x in range(41,128) if abs(rr[y*128+x]-f[y*128+x])>1) for f in mine)
        best.append(m)
    out.append((d,len(refs),sum(1 for b in best if b==0),min(best),max(best)))
print(sum(1 for o in out if len(o)>2 and o[2]==o[1] or (len(o)>2 and o[2]>=min(o[1],20))),'effects with every checked ref frame exact (cols 41-127)')
for o in out: print(o)
