import sys, capstone
sys.path.insert(0,'/mnt/project-files/tron/rom_data/tools')
from rom import ROM, foff
md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
def dis(a, n):
    o = foff(a)
    for i in md.disasm(ROM[o:o+4*n], a):
        print(f"{i.address:08x}: {i.mnemonic:8s} {i.op_str}")
if __name__ == '__main__':
    dis(int(sys.argv[1],16), int(sys.argv[2]))
