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
