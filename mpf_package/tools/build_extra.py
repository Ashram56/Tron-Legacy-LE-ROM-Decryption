import json,os,re,shutil,collections,csv
import numpy as np
from PIL import Image
from labels import L
T='/mnt/project-files/tron'; P=T+'/mpf_package'
STAGE='/home/claude/work/stage'   # build here, copy once
MS_PER_TICK=16.33
lib=json.load(open(P+'/media/dmd_library/index.json'))
res=json.load(open('anim_resolve.json'))
play=json.load(open('play.json')) if os.path.exists('play.json') else {'deff_anims':{}}
idx={int(k):v for k,v in json.load(open('anims/index.json')).items()}
H="# Generated from the Stern Tron Legacy LE v1.74 ROM (trn_174h). See ../README.md.\n"
def slug(d): return f"deff_{d:03d}_{L[d][0]}"
# ---- ticks per anim
ticks={}
for k,r in res.items():
    for u in r['clip_uses']: ticks.setdefault(int(k),u['ticks'])
P2=json.load(open('players.json'))
for k,l in P2.items():
    for e in l: ticks.setdefault(int(k),e['ticks'])
def frames_of(a):
    d=f"{P}/media/dmd_library/{a['name']}/frames"
    return [np.array(Image.open(f"{d}/{f}").convert('L')) for f in sorted(os.listdir(d))]
def canvas(fr,a):
    c=np.zeros((32,128),np.uint8)
    h,w=fr.shape; x=41 if w==87 else 0
    c[:min(32,h),x:x+w]=fr[:32,:]
    return c
def save_gif(cs,durs,path):
    ims=[Image.fromarray(c,'L').convert('P') for c in cs]
    ims[0].save(path,save_all=True,append_images=ims[1:],duration=[max(20,int(round(d))) for d in durs],loop=0,optimize=False,disposal=1)
os.makedirs(STAGE,exist_ok=True)
images=[H,"# Every full-size animation in the ROM as a 128x32 slide (87x32 animations sit at x=41, as the\n# ROM draws them). Frame time is the ROM's own (player ticks x 16.3 ms) where the code gives it.\nimages:\n"]
slides=["slides:\n"]; showp=[H,"# One event per library animation, so any of them can be played on its own.\nshow_player:\n"]
amap=[]
os.makedirs(f"{STAGE}/config/shows",exist_ok=True)
for a in lib:
    k=a['anim']; nm=a['name']; t=ticks.get(k,3); ms=t*MS_PER_TICK
    cs=[canvas(f,a) for f in frames_of(a)]
    out=f"{STAGE}/media/dmd_library/{nm}"; os.makedirs(out,exist_ok=True)
    save_gif(cs,[ms]*len(cs),f"{out}/animation_128x32.gif")
    total=int(round(ms*len(cs)))
    images.append(f"  lib_{nm}:\n    file: ../dmd_library/{nm}/animation_128x32.gif\n")
    slides.append(f"  lib_{nm}:\n    - type: image\n      image: lib_{nm}\n")
    open(f"{STAGE}/config/shows/lib_{nm}.yaml",'w').write(f"#show_version=6\n# Library animation {k}: images {a['first_image']}-{a['last_image']}, {len(cs)} frames at {ms:.0f} ms ({'ROM timing' if k in ticks else 'default timing, not found in code'}).\n- time: 0ms\n  slides:\n    lib_{nm}:\n      action: play\n- time: {total}ms\n  slides:\n    lib_{nm}:\n      action: remove\n")
    showp.append(f"  tron_lib_anim_{k:03d}: lib_{nm}\n")
    r=res[str(k)]
    obs=sorted(set(a['seen_in_deffs'])|{int(d) for d,v in play['deff_anims'].items() if nm in v})
    code=sorted({u['deff'] for u in r['clip_uses']}|{d for v in r['code_refs'].values() for d in v})
    how=sorted({f"effect {u['deff']}: {u['how']}" for u in r['clip_uses']})
    amap.append({'anim':k,'name':nm,'first_image':a['first_image'],'last_image':a['last_image'],'frames':len(cs),'size':f"{a['w']}x{a['h']}",
        'ms_per_frame':round(ms),'timing_source':'code' if k in ticks else 'default',
        'effects_observed':' '.join(map(str,obs)),'effects_by_code':' '.join(map(str,code)),
        'how_chosen':' | '.join(how),'code_functions':' '.join(sorted(r['code_refs'])),
        'mpf_event':f"tron_lib_anim_{k:03d}"})
open(f"{STAGE}/config/dmd_library.yaml",'w').write(''.join(images)+'\n'+''.join(slides)+'\n'+''.join(showp))
json.dump(amap,open('amap.json','w'))
print('library done',len(amap))
