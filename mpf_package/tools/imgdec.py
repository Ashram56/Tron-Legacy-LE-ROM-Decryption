import struct, numpy as np
ROM=open('/mnt/project-files/trn_174h.bin','rb').read()
N=struct.unpack_from('<I',ROM,0x36f4c)[0]; TBL=struct.unpack_from('<I',ROM,0x36f50)[0]
ENTS=struct.unpack_from('<%dI'%N,ROM,TBL)
def addr(i):
    e=ENTS[i]; return (e>>24)*0x800000+(e&0xffffff)
def header(i):
    a=addr(i); rid,z,flags,w,h,t=struct.unpack_from('<HHIhhB',ROM,a); return dict(rid=rid,z=z,flags=flags,w=w,h=h,type=t,addr=a)
def rle(a,n,out,colmajor,w,h):
    p=a; k=0
    def put(v):
        nonlocal k
        if colmajor: out[(k%h)*w + k//h]=v
        else: out[k]=v
        k+=1
    b=ROM[p]; p+=1
    while b:
        n_=b>>2; op=b&3
        if op==1:
            for _ in range(n_): put(0)
        elif op==2:
            for _ in range(n_): put(15)
        elif op==0:
            for _ in range(n_): put(ROM[p]); p+=1
        else:
            v=ROM[p]; p+=1
            for _ in range(n_): put(v)
        b=ROM[p]; p+=1
def delta(a,out,colmajor,w,h):
    p=a; k=0
    b=ROM[p]; p+=1
    while b:
        c=b-256 if b>127 else b
        if c<0: k+=-c
        else:
            for _ in range(c):
                if colmajor: out[(k%h)*w + k//h]=ROM[p]
                else: out[k]=ROM[p]
                p+=1; k+=1
        b=ROM[p]; p+=1
def decode(i, prev=None):
    H=header(i); w,h,t=H['w'],H['h'],H['type']; a=H['addr']+13
    n=w*h
    if t in (3,9):
        out=bytearray(prev) if prev is not None and len(prev)==n else bytearray(n)
    else: out=bytearray(n)
    if t==0: out[:]=ROM[a:a+n]
    elif t==1: rle(a,n,out,True,w,h)
    elif t==7: rle(a,n,out,False,w,h)
    elif t==12:
        for j in range(n):
            bt=ROM[a+j//2]; out[j]= (bt&0xf) if j%2==0 else (bt>>4)
    elif t==3: delta(a,out,True,w,h)
    elif t==9: delta(a,out,False,w,h)
    else: raise Exception('type %d'%t)
    return np.frombuffer(bytes(out),dtype=np.uint8).reshape(h,w), out
