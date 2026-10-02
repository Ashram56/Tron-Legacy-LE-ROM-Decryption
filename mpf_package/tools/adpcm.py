import struct,wave,numpy as np
rom=open('/mnt/project-files/trn_174h.bin','rb').read()
STEP=[7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,20350,22385,24623,27086,29794,32767]
IDX=[-1,-1,-1,-1,2,4,6,8]*2
def f(p): return (p>>24)*0x800000+(p&0xffffff)
def decode(p,lownib=True,n=None):
    o=f(p); cnt,_,div,_=struct.unpack_from('<IHBB',rom,o)
    if n: cnt=n
    data=rom[o+8:o+8+(cnt+1)//2]
    out=np.zeros(cnt,np.int16); pred=0; idx=0
    for i in range(cnt):
        b=data[i>>1]; nib=(b&15) if ((i&1)==0)==lownib else (b>>4)
        st=STEP[idx]; d=st>>3
        if nib&1: d+=st>>2
        if nib&2: d+=st>>1
        if nib&4: d+=st
        if nib&8: pred-=d
        else: pred+=d
        pred=max(-32768,min(32767,pred)); idx=max(0,min(88,idx+IDX[nib])); out[i]=pred
    return out,24000//div
