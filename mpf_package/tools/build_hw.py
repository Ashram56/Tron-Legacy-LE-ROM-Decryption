import json,csv,re,os,shutil,collections
T='/mnt/project-files/tron'; P=T+'/mpf_package'
os.makedirs(P+'/config',exist_ok=True)
def slug(s):
    m=re.search(r'\(([A-Za-z])\)',s)
    if m and re.fullmatch(r'[A-Z]*\([A-Z]\)[A-Z]*',s.strip()):   # letter targets like (T)RON -> tron_t
        return slug0(s.replace('('+m.group(1)+')',m.group(1)))+'_'+m.group(1).lower()
    return slug0(s)
def slug0(s):
    s=s.lower().replace('(','').replace(')','').replace('.',' ').replace("'",'')
    s=re.sub(r'[^a-z0-9]+','_',s).strip('_'); return s
H="# Generated from the Stern Tron Legacy LE v1.74 ROM (trn_174h). See ../README.md.\n"
# switches
sw=json.load(open(T+'/switch_names.json'))
tags={18:'trough',19:'trough',20:'trough',21:'trough',22:'trough_jam',23:'shooter_lane',16:'start',15:'tournament_start'}
active=set(range(1,65))-{18,19,20,21,22,15,16,52,53,54,55,56,11,23}   # ball device / shooter switches are not playfield_active in MPF
lines=[H,"# number: the SAM switch number (Stern numbering, 1-64). Replace with your platform's\n# address. Flipper buttons, EOS and coin door are SAM dedicated switches and are not in the ROM's\n# switch table; add them for your hardware.\nswitches:\n"]
for k in range(1,65):
    n=sw[str(k)]
    if n=='NOT USED': continue
    t=[]
    if k in tags: t.append(tags[k])
    if k in active: t.append('playfield_active')
    lines.append(f"  s_{slug(n)}:\n    number: {k}   # {n}\n" + (f"    tags: {', '.join(t)}\n" if t else ''))
    if k in (41,): lines.append("    type: NC   # disc opto: the ROM's ball search runs unless it reads closed (inferred from emulation)\n")
    if k in (21,22,41): lines.append("    # ROM switch descriptor (0x040f3574, word +0x10) sets bit 0x80 only on switches 21, 22 and 41; it may mean opto/inverted (not verified). Check on hardware.\n")
open(P+'/config/switches.yaml','w').write(''.join(lines))
# coils
lines=[H,"# number: the SAM coil/driver number (1-40). FLASH: entries are flashers (driver outputs),\n# 33-35 are the ticket outputs on the aux bus (ESTB). Motors and relays (5, 6, 8, 22, 23, 30) are held\n# outputs, so they get default_hold_power (use digital_outputs instead if your platform prefers).\ncoils:\n"]
fl=[H,"flashers:\n"]
for r in csv.DictReader(open(T+'/io/coils.csv')):
    n=r['name']; k=int(r['coil'])
    if n.startswith('FLASH') or 'FLASHER' in n:
        fl.append(f"  f_{slug(n.replace('FLASH:',''))}:\n    number: {k}   # {n}\n")
    else:
        lines.append(f"  c_{slug(n)}:\n    number: {k}   # {n}\n" + ("    default_hold_power: 1.0   # motor/relay: held on, not pulsed (ROM drive flags not decoded)\n" if k in (5,6,8,22,23,30) else ""))
open(P+'/config/coils.yaml','w').write(''.join(lines)+'\n'+''.join(fl[1:]))
# lights: lamp matrix + tubes
lines=[H,"# Lamp matrix: 66 named lamps of 80 (numbers as in the ROM's lamp test; 41, 44 and 67-80 are NOT USED).\n# Letter lamps are named by their letter: lamp 1 is TRO(N) = l_tron_n. The two ramp fiber optic tubes\n# are not matrix lamps; they come from ../io (aux bus RGB, see README).\nlights:\n"]
for r in csv.DictReader(open(T+'/io/lamps.csv')):
    if r['name']=='NOT USED': continue
    lines.append(f"  l_{slug(r['name'])}:\n    number: {r['lamp']}   # {r['name']}\n")
tube=open(T+'/io/mpf/lights.yaml').read().split('lights:\n',1)[1]
lines.append(tube)
open(P+'/config/lights.yaml','w').write(''.join(lines))
# sounds
os.makedirs(P+'/media/sounds',exist_ok=True)
samples={}
for r in csv.DictReader(open(T+'/samples_index.csv')):
    samples[int(r['sample_id'],16)]=r
track={'speech':'voice','sfx':'sfx','music':'music'}
# 17 streams the first export missed (decoded in this thread, tools/adpcm.py): sfx 0x09-0x14, 0x16-0x19, music 0x44d
for sid in list(range(0x09,0x15))+list(range(0x16,0x1a))+[0x44d]:
    kind='music' if sid>=0x400 else 'sfx'
    samples[sid]={'kind':kind,'file':f"newsnd/{kind}/{sid:04x}.wav",'local':True}
lines=[H,"# One entry per decoded ROM sample (mono WAV). Most speech is 12 kHz; 53 speech samples, all sfx and all\n# music are 24 kHz. Each file's own header carries its rate. Files live in media/sounds/<kind>/.\n# Whether the ROM loops music beds (e.g. snd_045a) was not verified; add loops: -1 if yours should loop.\nsounds:\n"]
for sid,r in sorted(samples.items()):
    kind=r['kind']; f=os.path.basename(r['file'])
    dst=f"{P}/media/sounds/{kind}"; os.makedirs(dst,exist_ok=True)
    if not os.path.exists(f"{dst}/{f}"): shutil.copy2(r['file'] if r.get('local') else f"{T}/{r['file']}",f"{dst}/{f}")
    lines.append(f"  snd_{sid:04x}:\n    file: {f}\n    track: {track[kind]}\n" + ("    mode_end_action: stop\n" if kind=='music' else ''))
calls=list(csv.DictReader(open(T+'/sound_calls.csv')))
lines.append("\n# The ROM plays 'sound calls'. A call picks one sample from its list, so each call is a random pool.\nsound_pools:\n")
nc=0
for r in calls:
    ids=[int(x,16) for x in r['sample_ids (one picked per play)'].split()]
    ids=[i for i in ids if i in samples]
    if not ids: continue
    cid=int(r['call_id'],16); nc+=1
    lines.append(f"  call_{cid:03x}:\n    type: random_force_all\n    sounds: {', '.join('snd_%04x'%i for i in ids)}\n")
open(P+'/config/sounds.yaml','w').write(''.join(lines))
print('sounds',len(samples),'pools',nc)
