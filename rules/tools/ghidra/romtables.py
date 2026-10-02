import struct,json,csv,re
ROM=open('/mnt/project-files/trn_174h.bin','rb').read()
B=0x04000000
def foff(a):
    if a<0x36000: return a
    if 0x01000000<=a<0x01100000: return a-0x01000000+0x40000
    if B<=a<B+0x800000: return a-B
    return None
def u32(a): return struct.unpack_from('<I',ROM,foff(a))[0]
def u16(a): return struct.unpack_from('<H',ROM,foff(a))[0]
def cstr(a):
    o=foff(a)
    if o is None: return None
    e=ROM.find(b'\0',o)
    if e<0 or e-o>200: return None
    try: return ROM[o:e].decode('latin1')
    except: return None
def slug(s,n=40):
    s=re.sub(r'%[-0-9,.]*l?[a-zA-Z]','',s or '')
    s=re.sub(r'[^a-z0-9]+','_',s.lower()).strip('_')
    return s[:n].strip('_')
NMSG=u32(0x040d0da0)
def msg(i):
    if i>=NMSG: return None
    p=u32(0x040eeb7c+4*i)
    if foff(p) is None: return None
    q=u32(p)
    return cstr(q) if foff(q) is not None else None
NADJ=u32(0x040bd398)
def adj(i):
    a=0x040de218+i*32
    try:
        _,dflt,mn,mx=struct.unpack_from('<4i',ROM,foff(a)); np=u32(a+0x18)
        return dict(name=cstr(u32(np)),default=dflt,min=mn,max=mx)
    except Exception: return None
AUD={}
for i in range(400):
    a=0x040e022c+i*16
    w=struct.unpack_from('<4I',ROM,foff(a))
    nm=None
    for x in w:
        if foff(x) is not None and x>=B:
            s=cstr(x)
            if s and len(s)>2 and s.isprintable(): nm=s;break
            y=u32(x) if foff(x) is not None else 0
            if foff(y) is not None and y>=B:
                s=cstr(y)
                if s and len(s)>2 and s.isprintable(): nm=s;break
    if nm is None and i>10: break
    cid=w[3]>>16
    if cid and nm: AUD[cid]=nm
SW={int(k):v for k,v in json.load(open('/mnt/project-files/tron/switch_names.json')).items()}
SND={}
for r in csv.DictReader(open('/mnt/project-files/tron/sound_calls.csv')):
    SND[int(r['call_id'],16)]=(r['kinds'],r['sample_ids (one picked per play)'])
LAMPS={int(r['lamp']):r['name'] for r in csv.DictReader(open('/mnt/project-files/tron/io/lamps.csv'))}
def deff_fn(i): return u32(0x040e1350+i*8)
def leff_entry(i):
    fn,a,g,c,p,q=struct.unpack_from('<IHHHBB',ROM,foff(0x040e23e4+i*12)); return fn,p
def tube_fn(i): return u32(0x040e3c88+i*12)
def lamp_group(g):
    out=[];a=u32(0x040e3acc+4*g) if False else None
    return out
