import json,csv,os,collections
from build_extra_lib import P,STAGE,MS_PER_TICK,lib,ticks,H
res=json.load(open('anim_resolve.json')); play=json.load(open('play.json')); var=json.load(open('variants.json'))
# variant events per anim
import yaml
vev=collections.defaultdict(list)
dv=open(f"{STAGE}/config/dmd_variants.yaml").read()
cur=None
for line in dv.split('\n'):
    if line.startswith('  ') and line.strip().endswith(':') and not line.startswith('    '): cur=line.strip()[:-1]
    if line.strip().startswith('# clip:') and cur:
        for a in line.split(':',1)[1].strip().split(' + '): vev[a].append(cur)
rows=[]
for a in lib:
    k=a['anim']; nm=a['name']; r=res[str(k)]
    obs_forced=sorted(a['seen_in_deffs']); obs_play=sorted(int(d) for d,v in play['deff_anims'].items() if nm in v)
    code=sorted({u['deff'] for u in r['clip_uses']}|{d for v in r['code_refs'].values() for d in v})
    how=sorted({f"effect {u['deff']}: {u['how']}" for u in r['clip_uses'] if u['deff'] not in (128,129)})
    clipno=sorted({(u['deff'],u['variant']+(30 if u['deff']==129 else 0)) for u in r['clip_uses'] if u['deff'] in (128,129)})
    if clipno: how.append("ROM clip number %s (effects 128/129 play a clip by number; no caller found in the game code, inferred debug clip viewer)"%(','.join(str(c) for _,c in clipno)))
    used=sorted(set(obs_forced)|set(obs_play)|set(code)-{128,129})
    if k==0: note='Stern logo shown at power-on (inferred)'
    elif k in (4,5): note='attract mode: Stern logo scroll then TRON intro (observed, see flow_attract_dmd)'
    elif not used and not clipno: note='no code reference found in v1.74 and never drawn in emulation; probably unused in this version'
    else: note=''
    rows.append({'anim':k,'name':nm,'images':f"{a['first_image']}-{a['last_image']}",'frames':a['frames'],'size':f"{a['w']}x{a['h']}",
      'ms_per_frame':round(ticks.get(k,3)*MS_PER_TICK),'timing_source':'code' if k in ticks else 'default',
      'effects_seen_forced':' '.join(map(str,obs_forced)),'effects_seen_in_play':' '.join(map(str,obs_play)),'effects_by_code':' '.join(str(x) for x in code if x not in (128,129)),
      'how_chosen':' | '.join(how),'variant_slides':' '.join(sorted(set(vev.get(nm,[])))),'notes':note,
      'mpf_event':f"tron_lib_anim_{k:03d}"})
with open(f"{STAGE}/animation_map.csv",'w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
lin=[r for r in rows if r['effects_seen_forced'] or r['effects_seen_in_play'] or r['effects_by_code'] or r['how_chosen'] or r['notes'].startswith(('attract','Stern'))]
print('animations linked to a trigger:',len(lin),'of',len(rows)); print('unlinked:',[r['anim'] for r in rows if r not in lin])
gf=H+"""# Game flow: what the ROM shows and plays at attract, game start, ball start, ball end and game over.
# Events are MPF's own built-in events, so this works without any extra code. All observed in emulation.
images:
  flow_attract_cycle:
    file: flow_attract_cycle/animation.gif
slides:
  flow_attract_cycle:
    - type: image
      image: flow_attract_cycle
show_player:
  mode_attract_started:
    flow_attract_dmd:
      loops: -1
    flow_attract_lights:
      loops: -1
  mode_attract_stopped:
    flow_attract_dmd:
      action: stop
    flow_attract_lights:
      action: stop
  game_started: flow_game_start        # music 0x01a, tube show 10 (post tron_arcade_lit when the arcade becomes lit)
  ball_started{ball>1}: flow_ball_start  # music 0x029, tube show 10 (add tron_arcade_lit / tron_shoot_again when they apply)
  ball_ending: flow_ball_end_bonus     # bonus count (effect 25) with its music and lamp shows
  game_ending: flow_game_over          # match (effect 38); high score entry runs first if earned
"""
open(f"{STAGE}/config/game_flow.yaml",'w').write(gf)
