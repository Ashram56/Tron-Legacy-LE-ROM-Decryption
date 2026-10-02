import sys,pickle,json,collections
fr,hs=pickle.load(open('/home/claude/work/frames.pkl','rb'))
r2i={h['rid']:i for i,h in enumerate(hs)}
lib=json.load(open('/mnt/project-files/tron/mpf_package/media/dmd_library/index.json'))
i2a={}
for k,v in (lib.items() if isinstance(lib,dict) else enumerate(lib)):
    for i in range(v['first_image'],v['last_image']+1): i2a.setdefault(i,v.get('name',k))
def run(fn):
    seq=[];last=None
    for line in open(fn):
        p=line.split()
        if len(p)<3 or p[1]!='DRAW': continue
        kv=dict(x.split('=',1) for x in p[2:] if '=' in x)
        if kv['lr'] in('2910c','290dc'): continue
        i=r2i.get(int(kv['rid']))
        a=i2a.get(i)
        key=(kv['deff'],a)
        if key!=last: seq.append((float(p[0]),kv['deff'],a,i)); last=key
    return seq
if __name__=='__main__':
    for t,d,a,i in run(sys.argv[1]): print(f"{t:8.2f} deff={d} {a} img={i}")
