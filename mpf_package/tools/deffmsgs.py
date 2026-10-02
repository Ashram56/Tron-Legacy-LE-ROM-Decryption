import pickle,re,json,struct
funcs,order,callees,callers,a2n=pickle.load(open('cg.pkl','rb'))
msgs={int(k):v for k,v in json.load(open('msgs.json')).items()}
ROM=open('/mnt/project-files/trn_174h.bin','rb').read()
pat=re.compile(r'(?:FUN_00028ca8|FUN_00028d5c|FUN_00028d08|FUN_0000a58c|FUN_00028d64|FUN_00028e48|FUN_00028eb0)\((0x[0-9a-f]+|\d+)')
res={}
for i in range(1,146):
    fn=struct.unpack_from('<I',ROM,0xe1350+i*8)[0]
    f=a2n.get(fn)
    if not f: continue
    seen=[f]; fr=[f]
    for _ in range(2):
        nf=[]
        for g in fr:
            for c in sorted(callees.get(g,())):
                if c not in seen and funcs[c]['addr']>=0x1000000 and not c.startswith('deff_') and len(callers.get(c,()))<6: seen.append(c); nf.append(c)
        fr=nf
    ids=[]
    for g in seen:
        for m in pat.finditer(funcs[g]['body']):
            v=int(m.group(1),0)
            if v in msgs and msgs[v] and v not in ids: ids.append(v)
    res[i]=[msgs[v] for v in ids]
json.dump(res,open('deff_msgs.json','w'),indent=0)
for i in range(1,146): print(i, ' | '.join(res.get(i,[]))[:150])
