"""Shared helpers for the rom_data/io/ hardware extraction (hw_*.py).

* function starts from the decompile headers (code/tron_game_decompiled_v2.c, `// ==== addr name`)
* resolve_call_args(): constant propagation over the straight-line code of the calling function, from
  its start to the BL, to recover the constant arguments (r0-r3 and outgoing stack words [sp+0..]).
  Branches are ignored (linear scan); a register written by a conditional instruction or by a load
  from non-constant memory is unknown (None). Good for the usual `mov r0,#coil; mov r1,#ms; bl` shape;
  every value it returns is a literal from the instruction stream (tag `code`).
"""
import bisect
import os
import re
import capstone
from capstone import arm as A

from rom import ROM, foff, u8, u16, u32, md, hx, find_bl_callers

REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
DECOMP = os.path.join(REPO, 'code', 'tron_game_decompiled_v2.c')

_funcs = None


def funcs():
    """sorted [(addr, name)] from the decompile headers"""
    global _funcs
    if _funcs is None:
        rx = re.compile(r'^// ==== ([0-9a-f]{8}) (\S+)')
        d = {}
        for line in open(DECOMP, encoding='latin1'):
            if line.startswith('// ===='):
                m = rx.match(line)
                if m:
                    d[int(m.group(1), 16)] = m.group(2)
        _funcs = sorted(d.items())
    return _funcs


def func_of(addr):
    f = funcs()
    i = bisect.bisect_right([a for a, _ in f], addr) - 1
    return f[i] if i >= 0 else (None, None)


_fa = None


def func_name(addr):
    global _fa
    if _fa is None:
        _fa = dict(funcs())
    return _fa.get(addr)


def decomp_body(addr):
    """text of one decompiled function"""
    f = funcs()
    keys = [a for a, _ in f]
    i = bisect.bisect_left(keys, addr)
    if i >= len(keys) or keys[i] != addr:
        return None
    nxt = keys[i + 1] if i + 1 < len(keys) else None
    out, on = [], False
    for line in open(DECOMP, encoding='latin1'):
        if line.startswith('// ==== '):
            a = int(line[8:16], 16)
            if a == addr:
                on = True
            elif on:
                break
        if on:
            out.append(line)
    return ''.join(out)


def insns(lo, hi):
    """ARM disassembly of [lo, hi); undecodable words (literal pools) are skipped, not fatal"""
    out = []
    a = lo
    while a < hi:
        o = foff(a)
        got = list(md().disasm(ROM[o:o + (hi - a)], a))
        out.extend(got)
        a = (got[-1].address + 4) if got else a
        if a < hi and (not got or got[-1].address + 4 == a):
            # stopped at an undecodable word: skip it
            nxt = a + 4 if not got or out[-1].address + 4 == a else a
            a = nxt
    return out


def _imm(op):
    return op.imm if op.type == A.ARM_OP_IMM else None


def resolve_call_args(bl, nstack=4, start=None):
    """-> (regs{0..3: value|None}, stack[list of value|None], start_addr)"""
    if start is None:
        start = func_of(bl)[0]
        if start is None or bl - start > 0x4000:
            start = max(bl - 0x200, 0)
    R = {}       # reg index -> const or None
    S = {}       # sp offset -> const or None (offsets relative to sp at the call)
    sp = 0       # running sp delta from the function entry
    regmap = {A.ARM_REG_R0 + i: i for i in range(13)}
    regmap[A.ARM_REG_SB] = 9
    regmap[A.ARM_REG_SL] = 10
    regmap[A.ARM_REG_FP] = 11
    regmap[A.ARM_REG_IP] = 12
    regmap[A.ARM_REG_SP] = 13
    regmap[A.ARM_REG_LR] = 14
    regmap[A.ARM_REG_PC] = 15

    def rv(op, pc):
        if op.type == A.ARM_OP_IMM:
            return op.imm
        if op.type == A.ARM_OP_REG:
            r = regmap.get(op.reg)
            if r == 15:
                return pc + 8
            v = R.get(r)
            if v is not None and op.shift.type != 0:
                st, sv = op.shift.type, op.shift.value
                if st == A.ARM_SFT_LSL:
                    v = (v << sv) & 0xffffffff
                elif st == A.ARM_SFT_LSR:
                    v = v >> sv
                elif st == A.ARM_SFT_ASR:
                    v = (v >> sv)
                else:
                    v = None
            return v
        return None

    for ins in insns(start, bl + 4):
        if ins.address == bl:
            break
        mn = ins.mnemonic
        ops = ins.operands
        cond = ins.cc not in (A.ARM_CC_AL, A.ARM_CC_INVALID)
        base = ins.insn_name()
        def setr(r, v):
            if r is None:
                return
            if cond:
                old = R.get(r)
                R[r] = old if old == v else None
            else:
                R[r] = v
        if base in ('bl', 'blx'):
            for r in (0, 1, 2, 3, 12, 14):
                R[r] = None
            continue
        if base in ('push', 'stmdb') and (base == 'push' or regmap.get(ops[0].reg) == 13):
            n = len(ops) - (0 if base == 'push' else 1)
            sp -= 4 * n
            continue
        if base in ('pop', 'ldm', 'ldmia') and (base == 'pop' or regmap.get(ops[0].reg) == 13):
            regs = ops if base == 'pop' else ops[1:]
            for o in regs:
                R[regmap.get(o.reg)] = None
            if base == 'pop' or ins.writeback:
                sp += 4 * len(regs)
            continue
        if base in ('sub', 'add') and len(ops) == 3 and ops[0].type == A.ARM_OP_REG and regmap.get(ops[0].reg) == 13 and regmap.get(ops[1].reg) == 13 and ops[2].type == A.ARM_OP_IMM:
            sp += -ops[2].imm if base == 'sub' else ops[2].imm
            continue
        if base in ('mov', 'mvn') and len(ops) == 2:
            v = rv(ops[1], ins.address)
            if v is not None and base == 'mvn':
                v = (~v) & 0xffffffff
            setr(regmap.get(ops[0].reg), v)
            continue
        if base in ('add', 'sub', 'orr', 'and', 'eor', 'bic', 'rsb', 'lsl', 'lsr', 'asr') and len(ops) == 3:
            a, b = rv(ops[1], ins.address), rv(ops[2], ins.address)
            v = None
            if a is not None and b is not None:
                v = {'add': a + b, 'sub': a - b, 'orr': a | b, 'and': a & b, 'eor': a ^ b, 'bic': a & ~b,
                     'rsb': b - a, 'lsl': a << b, 'lsr': a >> b, 'asr': a >> b}[base] & 0xffffffff
            setr(regmap.get(ops[0].reg), v)
            continue
        if base in ('ldr', 'ldrh', 'ldrb', 'ldrsh', 'ldrsb') and len(ops) >= 2 and ops[1].type == A.ARM_OP_MEM:
            m = ops[1].mem
            r = regmap.get(ops[0].reg)
            v = None
            if regmap.get(m.base) == 15 and m.index == 0:
                a = ins.address + 8 + m.disp
                v = u32(a) if base == 'ldr' else u16(a) if base == 'ldrh' else u8(a)
            elif regmap.get(m.base) == 13 and m.index == 0:
                v = S.get(sp + m.disp)
            setr(r, v)
            continue
        if base in ('str', 'strh', 'strb') and ops[1].type == A.ARM_OP_MEM:
            m = ops[1].mem
            if regmap.get(m.base) == 13 and m.index == 0:
                v = R.get(regmap.get(ops[0].reg))
                if v is not None and base == 'strb':
                    v &= 0xff
                if v is not None and base == 'strh':
                    v &= 0xffff
                S[sp + m.disp] = v
            continue
        # any other instruction writing a register: unknown
        if ops and ops[0].type == A.ARM_OP_REG and base not in ('cmp', 'cmn', 'tst', 'teq', 'b', 'bx', 'str', 'stm', 'stmia', 'strh', 'strb'):
            if base not in ('b', 'bx', 'bl', 'blx'):
                setr(regmap.get(ops[0].reg), None)
    regs = {i: R.get(i) for i in range(4)}
    stack = [S.get(sp + 4 * k) for k in range(nstack)]
    return regs, stack, start


def callers(target):
    return [a for a, link in find_bl_callers(target) if link]


def lit_refs(value, lo=0, hi=None):
    """file offsets where the u32 value appears"""
    import struct
    b = struct.pack('<I', value)
    out, o = [], lo
    hi = hi or len(ROM)
    while True:
        o = ROM.find(b, o, hi)
        if o < 0:
            return out
        out.append(o)
        o += 1
