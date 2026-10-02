import re,struct,capstone,json,os
ROM=open('/mnt/project-files/trn_174h.bin','rb').read()
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_ARM)
def foff(a):
    if a<0x36000: return a
    if 0x01000000<=a<0x01100000: return a-0x01000000+0x40000
    if 0x04000000<=a<0x04800000: return a-0x04000000
    return None
def u32(a): return struct.unpack_from('<I',ROM,foff(a))[0]
src=open('/mnt/project-files/tron/code/tron_game_decompiled.c').read()
heads=[(int(a,16),n) for a,n in re.findall(r'^// ==== ([0-9a-f]{8}) (\S+)$',src,flags=re.M)]
old={a:n for a,n in heads}
# BL targets
bl=set()
for base,start,end in [(0,0,0x36000),(0x01000000,0x40000,0x92000)]:
    for o in range(start,end,4):
        w=struct.unpack_from('<I',ROM,o)[0]
        if (w>>24)&0xf==0xb and (w>>28)!=0xf:
            off=w&0xffffff
            if off&0x800000: off-=0x1000000
            t=base+(o-start)+8+off*4
            if (0<=t<0x36000) or (0x01000000<=t<0x01092000): bl.add(t)
def is_movr0(a):
    o=foff(a); 
    if o is None: return False
    i=list(md.disasm(ROM[o:o+4],a))
    return bool(i) and i[0].mnemonic=='mov' and i[0].op_str.startswith('r0, #')
seeds={}
for a,n in heads:
    if a>=0x010e0000: continue
    if (a-4) in old and is_movr0(a-4) and a not in bl: continue   # phantom +4 entry
    seeds[a]=n
for t in bl:
    seeds.setdefault(t,None)
# tables: deffs, leffs, switch handlers
for i in range(146):
    fn=u32(0x040e1350+i*8)
    if fn: seeds[fn]=('deff_%03d'%i) if seeds.get(fn) in (None,) or str(seeds.get(fn)).startswith(('FUN_','deff_')) else seeds[fn]
for i in range(106):
    fn=u32(0x040e3c88+i*12)
    if fn and (0x01000000<=fn<0x01092000 or fn<0x36000):
        if seeds.get(fn) is None or str(seeds.get(fn)).startswith('FUN_'): seeds[fn]='leff_%03d'%i
keep=lambda n: n and not n.startswith(('FUN_','thunk_','switchD','default','Reset','Undefined','Supervisor','Prefetch','DataAbort','IRQ','FIQ'))
out=[]
for a in sorted(seeds):
    n=seeds[a]
    out.append('%08x\t%s'%(a, n if keep(n) else ''))
open('seeds.tsv','w').write('\n'.join(out)+'\n')
print(len(seeds),'seeds; bl targets',len(bl),'old',len(heads),'dropped phantoms',sum(1 for a,n in heads if a not in seeds))
