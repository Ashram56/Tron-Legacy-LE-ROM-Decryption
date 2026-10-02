import json,os,re,glob,sys
sys.argv=['x']
from analyze import parse
import export_anims_lib as E
from labels import L
T='/mnt/project-files/tron'; P=T+'/mpf_package'; STAGE='/home/claude/work/stage'
H="# Generated from the Stern Tron Legacy LE v1.74 ROM (trn_174h). See ../README.md.\n"
shows={f[:-5] for f in os.listdir(P+'/config/shows')}
leffs={f[:-5] for f in os.listdir(T+'/io/mpf/shows')}
pools=set(re.findall(r'^  (call_[0-9a-f]{3}):',open(P+'/config/sounds.yaml').read(),re.M))
def deffshow(d):
    n=f"deff_{d:03d}_{L[d][0]}"; return n if n in shows else None
def steps_from(ev,t0,t1,skip_deffs=(1,19)):
    steps={}; notes=[]
    for t,k,kv in ev:
        if t<t0 or t>t1: continue
        ms=int(round((t-t0)*1000))
        if k=='DEFF_START' and kv.get('lr')!='34080':
            d=int(kv['id'])
            if d in skip_deffs: continue
            s=deffshow(d); notes.append(f"{ms}ms effect {d} ({L[d][1]})")
            if s: steps.setdefault(ms,{}).setdefault('shows',{})[s]={'action':'play'}
        elif k=='SND':
            c='call_%03x'%int(kv['call'],16)
            if c in pools and kv.get('deff')=='0': steps.setdefault(ms,{}).setdefault('sounds',{})[c]={'action':'play'}
        elif k=='LEFF':
            l='leff_%03d'%int(kv['id'])
            if l in leffs and kv.get('deff')=='0': steps.setdefault(ms,{}).setdefault('shows',{})[l]={'action':'play'}
    return steps,notes
def write_show(name,desc,steps,end_ms,extra_first=None):
    y=['#show_version=6\n',''.join(f"# {l}\n" for l in desc)]
    if extra_first:
        for k,v in extra_first.items(): steps.setdefault(0,{}).setdefault(k,{}).update(v)
    for t in sorted(steps):
        y.append(f"- time: {t}ms\n")
        for k,v in steps[t].items():
            y.append(f"  {k}:\n"+''.join(f"    {n}:\n"+''.join(f"      {a}: {b}\n" for a,b in o.items()) for n,o in v.items()))
    y.append(f"- time: {end_ms}ms\n")
    open(f"{STAGE}/config/shows/{name}.yaml",'w').write(''.join(y))
os.makedirs(STAGE+'/config/shows',exist_ok=True)
out={}
def lparse(fn):
    ev=[]
    for line in open(fn):
        p=line.split()
        if len(p)<3 or p[1] not in ('DEFF_START','SND','LEFF','PLAY'): continue
        kv=dict(x.split('=',1) for x in p[2:] if '=' in x)
        try: ev.append((float(p[0]),p[1],kv))
        except ValueError: pass
    return ev
logs={fn:lparse(fn) for fn in ['/home/claude/trace/p0.log']}
def find(fn,pred,after=0):
    for i,(t,k,kv) in enumerate(logs[fn]):
        if t>=after and pred(t,k,kv): return t
# --- game start: first DEFF_START 104 from start handler (lr 100de10) after PLAY start
fn='/home/claude/trace/p0.log'; ev=logs[fn]
t0=find(fn,lambda t,k,kv:k=='DEFF_START' and kv.get('id')=='104')
st,notes=steps_from(ev,t0-0.05,t0+2.0,skip_deffs=(1,19,104))
write_show('flow_game_start',["Start of game (observed): main play music (call 0x01a) and tube show 10. The ROM also shows effect 104","(FLYNN'S ARCADE IS LIT) here, but only because the arcade starts lit; post tron_arcade_lit from your arcade logic.","Then the score display (effect 19) runs."],{(int(k)+50 if False else int(k)):v for k,v in st.items()},3300)
out['flow_game_start']=('game_started','start button pressed with credits',notes)
# --- ball end: deff 25 bonus on a drain that is not the last ball; until next ball's deff 19 (lr 2074c)
cands=[]
for fn,ev in logs.items():
    for i,(t,k,kv) in enumerate(ev):
        if k=='DEFF_START' and kv.get('id')=='25' and kv.get('lr')!='34080':
            tn=find(fn,lambda t2,k2,kv2:k2=='DEFF_START' and kv2.get('id')=='19' and kv2.get('lr')=='2074c',t)
            tg=find(fn,lambda t2,k2,kv2:k2=='DEFF_START' and kv2.get('id') in('31','32','38','130') ,t)
            cands.append((fn,t,tn,tg))
nb=[c for c in cands if c[2] and (not c[3] or c[3]>c[2]) and c[2]-c[1]<10]
fn,tb,tn,_=nb[0]; ev=logs[fn]
# include the mode totals shown just before the bonus
st,notes=steps_from(ev,tb-0.02,tn-0.02)
write_show('flow_ball_end_bonus',["End of ball (observed): bonus count. Before it, the ROM shows a total for each mode that ran","during the ball (effects 70, 74, 79, 90, 99 and others), each with its own show.",*notes],st,int((tn-tb)*1000))
out['flow_ball_end_bonus']=('ball_ending','ball drained (after any mode-total effects)',notes)
st,notes=steps_from(ev,tn-0.01,tn+1.0)
write_show('flow_ball_start',["Start of the next ball (observed): music restarts (call 0x029 or 0x01a) with tube show 10.","When Flynn's Arcade is lit the ROM also plays effect 104, and after an extra ball effect 26.",*notes],st,1000)
out['flow_ball_start']=('ball_started','each new ball after the first',notes)
# --- game over: deff 25 followed by 31/32/38/130 before next game start
go=[c for c in cands if c[3] and (not c[2] or c[3]<c[2])]
if go:
    fn,tb,_,tg=go[0]; ev=logs[fn]
    ta=find(fn,lambda t2,k2,kv2:k2=='DEFF_START' and kv2.get('id')=='1' and kv2.get('lr')!='34080',tb) or tb+20
    tm=find(fn,lambda t2,k2,kv2:k2=='DEFF_START' and kv2.get('id')=='38',tg)
    st,notes=steps_from(ev,tm-0.02,ta+0.2,skip_deffs=(19,10,1))
    write_show('flow_game_over',["End of game (observed). After the last ball's bonus, a high score first runs initials entry","(effect 31 tron_enter_initials, effect 32 high score value, effect 33 player n) until initials are entered;","then this show: the match sequence, then attract mode (effect 1).",*notes],st,int((ta-tm)*1000)+200)
    out['flow_game_over']=('game_ending','last ball drained',notes)
    print('game over',fn,tg,ta,notes)
json.dump(out,open('flow.json','w'),indent=1)
for k,v in out.items(): print(k,v[0],v[2])
