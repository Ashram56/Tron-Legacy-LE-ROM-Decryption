import json,os,re,yaml,struct,pickle,bisect
import numpy as np
from PIL import Image
from labels import L
from build_extra_lib import P,STAGE,MS_PER_TICK,lib,frames_of,canvas,save_gif,H
res=json.load(open('anim_resolve.json'))
idx={int(k):v for k,v in json.load(open('anims/index.json')).items()}
byfirst={a['first_image']:a for a in lib}
def anim_for(first,last):
    for a in lib:
        if a['first_image']<=last<=a['last_image']: return a
# rules: deff -> list of (variant label, [(first,last,ticks)], how)
rules={}
for k,r in res.items():
    for u in r['clip_uses']:
        if u['deff'] in (128,129): continue
        rules.setdefault(u['deff'],{'how':u['how'],'v':{}})['v'].setdefault(u['variant'],[]).append((u['first'],u['last'],u['ticks']))
# light cycle jackpot (effect 87): clip = jackpot counter clamped to a per-level range (table 0x40d2ffc fields 0-1)
T_=json.load(open('tables.json'))['wrappers']
_rom=open('/mnt/project-files/trn_174h.bin','rb').read()
_funcs,_o,_ce,_cr,_a2n=pickle.load(open('cg.pkl','rb'))
_fa=sorted(_a2n)
def _near(v):
    k=bisect.bisect_left(_fa,v); return _a2n.get(v) or (_a2n[_fa[k]] if k<len(_fa) and _fa[k]-v<=16 else None)
_tbl=[_near(struct.unpack_from('<I',_rom,0xd3084+4*i)[0]) for i in range(24)]
v87={}
for L_ in range(6):
    lo,hi,_,_=struct.unpack_from('<4H',_rom,0xd2ffc+8*L_)
    for j,c in enumerate(range(lo,hi+1)):
        v87[f"{L_+1}_{j+1}"]=[(int(f,0) if f.startswith('0x') else None,l,t) for f,l,t in T_[_tbl[c]]]
rules[87]={'how':"clip chosen by Light Cycle multiball level 1-6 and the jackpot count within that level (code: table 0x40d2ffc, fields 0-1 give each level's clip range; past the range the first clip is used)",'v':v87}
rules[108]={'how':'random pick of 4 clips (code: deff_108 switch(random(4)); clips 1-2 full width at 49 ms, clips 3-4 at x=41 at 33 ms)',
  'v':{0:[(2683,2712,3)],1:[(2713,2742,3)],2:[(2623,2652,2)],3:[(2653,2682,2)]}}
# sea of simulation: FUN_01027374 random(2) of table 0x40d3980, FUN_01027478 table 0x40d3990
seav={0:[(6732,6760,3)],1:[(6761,6797,3)]}; seaalt={0:[(6798,6840,3)]}
for d in range(116,125):
    rules[d]={'how':'random pick of 2 clips; a third clip plays instead when the caller sets a flag (code: FUN_01027374 / FUN_01027478, flag meaning not traced)','v':seav,'alt':seaalt}
def first_frame_of_range(first,last):
    out=[]
    for a in lib:
        if a['last_image']<first or a['first_image']>last: continue
        fr=frames_of(a)
        for i,f in enumerate(fr):
            img=a['first_image']+i
            if first<=img<=last: out.append(canvas(f,a))
    return out
showdir=f"{P}/config/shows"
images=[H,"# Effects that pick a different film clip each time (at random, or by mode level).\n# The ROM's choice is reproduced with one show per clip.\nimages:\n"]; slides=["slides:\n"]
rep=["random_event_player:\n"]; sp=["show_player:\n"]
renamed={}
summary={}
for d in sorted(rules):
    slug,what,trig=L[d]; base=f"deff_{d:03d}_{slug}"
    bf=f"{showdir}/{base}.yaml"
    if not os.path.exists(bf): print('no base show',d); continue
    steps=yaml.safe_load(open(bf).read())
    end=int(steps[-1]['time'].rstrip('ms'))
    groups=[('',rules[d]['v'])]+([('_alt',rules[d]['alt'])] if 'alt' in rules[d] else [])
    level='Light Cycle' in rules[d]['how']
    evs={}
    for suf,vs in groups:
        for vk in sorted(vs, key=lambda x: (str(x).zfill(4))):
            cs=[];durs=[]; used=[]
            for first,last,t in vs[vk]:
                if first is None: first=anim_for(first,last)['first_image']
                fr=first_frame_of_range(first,last); cs+=fr; durs+=[t*MS_PER_TICK]*len(fr)
                used.append(anim_for(first,last)['name'])
            if not cs: continue
            hold=end-sum(durs)
            if hold>20: cs.append(cs[-1]); durs.append(hold)
            vname=(f"{base}{suf}_level_{vk}" if isinstance(vk,str) and "_" in vk else f"{base}{suf}_level_{int(vk)+1}") if level else f"{base}{suf}_v{int(vk):02d}"
            od=f"{STAGE}/media/dmd/{base}/variants"; os.makedirs(od,exist_ok=True)
            save_gif(cs,durs,f"{od}/{vname[len(base)+1:]}.gif")
            images.append(f"  {vname}:\n    file: {base}/variants/{vname[len(base)+1:]}.gif\n")
            slides.append(f"  {vname}:\n    # clip: {' + '.join(used)}\n    - type: image\n      image: {vname}\n")
            y=['#show_version=6\n',f"# {vname}: {what}, clip {' + '.join(used)}.\n# Same sounds and tube show as {base}; only the clip differs. {rules[d]['how']}.\n"]
            for st in steps:
                st2=json.loads(json.dumps(st))
                if 'slides' in st2:
                    st2['slides']={(vname if k==base else k):v for k,v in st2['slides'].items()}
                y.append(yaml.safe_dump([st2],sort_keys=False))
            if not any('slides' in s for s in steps):
                y.append(yaml.safe_dump([{'time':'0ms','slides':{vname:{'action':'play'}}},{'time':f'{end}ms','slides':{vname:{'action':'remove'}}}],sort_keys=False))
            os.makedirs(f"{STAGE}/config/shows",exist_ok=True)
            open(f"{STAGE}/config/shows/{vname}.yaml",'w').write(''.join(y))
            ev=f"tron_{slug}{suf}_"+((f"level_{vk}" if isinstance(vk,str) and "_" in vk else f"level_{int(vk)+1}") if level else f"v{int(vk):02d}")
            sp.append(f"  {ev}: {vname}\n"); evs.setdefault(suf,[]).append(ev)
    if level:
        rep.append(f"  # effect {d}: no random pick; post the tron_{slug}_level_... event for the current Light Cycle level from your mode\n")
    else:
        for suf,l in evs.items():
            rep.append(f"  tron_{slug}{suf}:\n    force_different: true\n    events:\n"+''.join(f"      - {e}\n" for e in l))
        renamed[base]=f"tron_{slug}"
    summary[d]={'how':rules[d]['how'],'events':evs,'level':level}
open(f"{STAGE}/config/dmd_variants.yaml",'w').write(''.join(images)+'\n'+''.join(slides)+'\n'+''.join(rep)+'\n'+''.join(sp))
# show_player.yaml: the random trigger replaces the base mapping; keep base as _as_captured
spf=open(f"{P}/config/show_player.yaml").read()
for base,ev in renamed.items():
    spf=re.sub(rf"^  {ev}: {base}\b", f"  {ev}_as_captured: {base}", spf, flags=re.M)
os.makedirs(f"{STAGE}/config",exist_ok=True); open(f"{STAGE}/config/show_player.yaml",'w').write(spf)
json.dump(summary,open('variants.json','w'),indent=1)
print(json.dumps({d:(v['how'][:40],{k:len(x) for k,x in v['events'].items()}) for d,v in summary.items()},indent=0))
