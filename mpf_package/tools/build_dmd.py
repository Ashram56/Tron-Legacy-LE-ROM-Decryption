import json,csv,os,shutil,struct,re
from labels import L
T='/mnt/project-files/tron'; P=T+'/mpf_package'
idx={int(k):v for k,v in json.load(open('anims/index.json')).items()}
st={int(k):v for k,v in json.load(open('deff_static.json')).items()}
ms={int(k):v for k,v in json.load(open('deff_msgs.json')).items()}
leffcsv={int(r['leff']):r for r in csv.DictReader(open(T+'/io/light_effects.csv'))}
ct=list(csv.DictReader(open(T+'/callout_triggers.csv')))
code_snd={}
for r in ct:
    for d in r['display_effects'].split():
        code_snd.setdefault(int(d),[]).append(r['call_id'])
pools=set(re.findall(r'^  (call_[0-9a-f]{3}):',open(P+'/config/sounds.yaml').read(),re.M))
H="# Generated from the Stern Tron Legacy LE v1.74 ROM (trn_174h). See ../README.md.\n"
os.makedirs(P+'/media/dmd',exist_ok=True); os.makedirs(P+'/config/shows',exist_ok=True)
# copy tube light shows
for f in os.listdir(T+'/io/mpf/shows'): shutil.copy2(f'{T}/io/mpf/shows/{f}',f'{P}/config/shows/{f}')
leff_shows={int(f[5:8]) for f in os.listdir(T+'/io/mpf/shows')}
sweep=json.load(open('sweep.json')); swn=json.load(open(T+'/switch_names.json'))
obs={}
for sw_,dd in sweep['sw_deff'].items():
    for k,v in dd.items(): obs.setdefault(int(k),[]).append(f"{sw_} {swn[sw_]}")
lib=json.load(open(P+'/media/dmd_library/index.json'))
play=json.load(open('play.json'))
for k,v in play['deff_anims'].items():
    for a in v: libby_play=None
for d_,sw in play['deff_after_switch'].items():
    for s_,n_ in sw.items():
        if n_>=2 and s_ in swn:
            lab=f"{s_} {swn[s_]}"
            if lab not in obs.setdefault(int(d_),[]): obs[int(d_)].append(lab)
libby={}
for o in lib:
    for k in o['seen_in_deffs']: libby.setdefault(k,set()).add(o['name'])
for k,v in sweep['deff_anims'].items():
    for a in v: libby.setdefault(int(k),set()).add(lib[a]['name'])
for k,v in play['deff_anims'].items():
    for a in v: libby.setdefault(int(k),set()).add(a)
import pickle as _pk
_funcs,_o,_ce,_cr,_a2n=_pk.load(open('cg.pkl','rb'))
_rom=open('/mnt/project-files/trn_174h.bin','rb').read()
lampfx={}
for _d in range(1,146):
    _f=_a2n.get(struct.unpack_from('<I',_rom,0xe1350+_d*8)[0])
    if _f: lampfx[_d]=[int(x,0) for x in re.findall(r'FUN_000087ac\((0x[0-9a-f]+|\d+)\)',_funcs[_f]['body'])]
TEXT_OVERRIDE={10:'credits / PRESS START / INSERT COINS',15:'credits / PRESS START / INSERT COINS',17:'credits / PRESS START / INSERT COINS',
  105:'(no strings; award icons show level digits, msgs 0x61d-0x622)'}
rows=[]; slides=[H,"# One slide per ROM display effect. The image is the effect's graphics layer (animated GIF,\n# 128x32, transparent where the ROM drew nothing). Text the ROM draws on top is listed in a\n# comment; lay it out with text widgets. Score-panel and number fields are dynamic.\nslides:\n"]
images=[H,"# Animated DMD images (128x32 GIF, 16 grey levels). Frame PNGs and exact timing are in\n# media/dmd/<name>/frames and timing.json.\nimages:\n"]
showp=[H,"# Post the event to play the effect: its animation, sounds and ramp tube light show together.\n# Each show is in config/shows/<name>.yaml. Event names are suggestions; see event_map.csv\n# for what triggers each one in the original ROM.\nshow_player:\n"]
disagree=[]
for d in range(1,146):
    slug,what,trig=L[d]; name=f'deff_{d:03d}_{slug}'
    m=idx.get(d,{}); s=st[d]
    src=f'anims/deff_{d:03d}'; dst=f'{P}/media/dmd/{name}'
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(src,dst)
    has_anim=bool(m.get('graphics_frames'))
    rendered=m.get('run_seconds',0)>0.5
    snds=[x for x in m.get('sounds',[]) if 'call_%s'%x['call'][2:] in pools]
    lefs=[x for x in m.get('light_effects',[]) if x['from_deff']==str(d)]
    # cross-check with IO thread
    for l in lefs:
        r=leffcsv.get(l['leff'])
        if r and r['display_effects'] and f'deff_{d}' not in r['display_effects'].split(): disagree.append((d,l['leff'],r['display_effects']))
    loop=s['looping']
    total=int(m.get('run_seconds',0)*1000)
    # show
    steps={}
    def add(t,k,v): steps.setdefault(t,{}).setdefault(k,{}).update(v)
    if has_anim: add(0,'slides',{name:{'action':'play'}})
    for l in lefs:
        if l['leff'] in leff_shows: add(l['t_ms'],'shows',{f"leff_{l['leff']:03d}":{'action':'play','loops':0} if leffcsv.get(l['leff'],{}).get('kind')=='once' else {'action':'play'}})
    for x in snds: add(x['t_ms'],'sounds',{'call_%s'%x['call'][2:]:{'action':'play'}})
    if d==105: add(883,'sounds',{'call_0e1':{'action':'stop'}})   # ROM stops the scroll sound when the scroll ends (FUN_0002ceb4(0xe1))
    if steps:
        y=['#show_version=6\n',f"# {name}: {what}\n# ROM trigger: {trig}. Timing from emulation"+(" (looping background effect, cut at 12 s)" if loop else "")+".\n"]
        times=sorted(steps)
        end=max(total, times[-1]+50)
        for t in times:
            y.append(f"- time: {t}ms\n")
            for k,v in steps[t].items():
                y.append(f"  {k}:\n")
                for nm,opt in v.items():
                    y.append(f"    {nm}:\n"+''.join(f"      {a}: {b}\n" for a,b in opt.items()))
        y.append(f"- time: {end}ms\n" + (f"  slides:\n    {name}:\n      action: remove\n" if has_anim and not loop else ""))
        open(f'{P}/config/shows/{name}.yaml','w').write(''.join(y))
        showp.append(f"  tron_{slug}: {name}" + ("   # loops until stopped: use show_player 'action: stop' when the mode ends\n" if loop else "\n"))
    if has_anim:
        images.append(f"  {name}:\n    file: {name}/animation.gif\n")
        txt=' / '.join(ms.get(d,[]))
        slides.append(f"  {name}:\n    # ROM text: {txt if txt else '(none)'}\n    - type: image\n      image: {name}\n")
    rows.append({'deff':d,'name':name,'mpf_event':f'tron_{slug}' if steps else '','shows':what,'rom_trigger':trig,
        'priority':s['priority'],'background_loop':'yes' if loop else '',
        'rom_text':TEXT_OVERRIDE.get(d,' / '.join(ms.get(d,[]))),
        'animation_frames':len(m.get('graphics_frames',[])),'run_ms':total,
        'rendered_in_emulation':('yes (emulated play)' if m.get('source') else 'yes') if rendered else 'no',
        'seen_in_emulated_play':play['deff_seen'].get(str(d),0),
        'sounds_heard':' '.join(f"{x['call']}@{x['t_ms']}ms" for x in m.get('sounds',[])),
        'sounds_in_code':' '.join(code_snd.get(d,[])),
        'tube_light_show':' '.join(f"leff_{x['leff']:03d}@{x['t_ms']}ms" for x in lefs),
        'lamp_effect_in_code':' '.join('0x%02x'%x for x in lampfx.get(d,[])),
        'observed_on_switches':' / '.join(obs.get(d,[])),
        'library_animations':' '.join(sorted(libby.get(d,()))),
        'started_by_code':' '.join(s['started_from']),
        'switches_reaching_start (depth)':' '.join(f"{k}({v})" for k,v in list(s['switches'].items())[:8]),
        'rom_function':s['fn']})
with open(P+'/event_map.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
open(P+'/config/dmd_slides.yaml','w').write(''.join(images)+'\n'+''.join(slides))
open(P+'/config/show_player.yaml','w').write(''.join(showp))
print('rows',len(rows),'anims',sum(1 for r in rows if r['animation_frames']),'shows',len(showp)-1)
print('disagree',disagree)
