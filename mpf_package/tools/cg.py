import re, collections, json, pickle
src=open('/mnt/project-files/tron/code/tron_game_decompiled.c').read()
funcs={}; order=[]
cur=None; buf=[]
for line in src.split('\n'):
    m=re.match(r'// ==== ([0-9a-f]{8}) (\S+)',line)
    if m:
        if cur: funcs[cur]['body']='\n'.join(buf)
        cur=m.group(2); funcs[cur]={'addr':int(m.group(1),16)}; order.append(cur); buf=[]
    else: buf.append(line)
funcs[cur]['body']='\n'.join(buf)
names=set(funcs)
callees={}; callers=collections.defaultdict(set)
for f,d in funcs.items():
    body=re.sub(r'/\*.*?\*/','',d['body'])
    cs=set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(',body))&names
    cs.discard(f); callees[f]=cs
    for c in cs: callers[c].add(f)
# also function pointers referenced as PTR_FUN_/LAB_ addresses e.g. "PTR_FUN_010013d4" comment values; capture DAT comments "=0x1xxxxxx" matching function addrs
addr2name={d['addr']:f for f,d in funcs.items()}
for f,d in funcs.items():
    for v in re.findall(r'=0x([0-9a-f]+)',d['body']):
        a=int(v,16)
        if a in addr2name and addr2name[a]!=f:
            callees[f].add(addr2name[a]); callers[addr2name[a]].add(f)
pickle.dump((funcs,order,callees,dict(callers),addr2name),open('cg.pkl','wb'))
print(len(funcs), sum(len(v) for v in callees.values()))
