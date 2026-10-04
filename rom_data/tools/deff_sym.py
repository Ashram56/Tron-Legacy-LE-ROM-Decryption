"""Small symbolic ARM interpreter for the Tron 1.74 ROM (used by deff_static.py).

Analyses one function at a time over its control-flow graph and records, for every call it
makes, the symbolic values of r0-r3, ip and the outgoing stack words. Values are tuples:
  ('c', v)                 constant
  ('ram', addr, size)      load from a fixed RAM address (0x36000-0x100000, NVRAM, IO)
  ('rom', addr, size)      (folded to a constant when the address is fixed)
  ('tbl', base, idx, size) load from ROM table base + idx (idx is a value)
  ('ld', base, off, size)  load from [base + off] (base is a value)
  ('task', off, size)      load from current task block (*0x372c0) + off
  ('arg', i)               i-th argument of the analysed function (0-3 = r0-r3, 4+ = stack)
  ('ret', fn, site)        return value of the call made at site
  ('sp', k)                address of a stack slot (k = offset from the entry sp)
  ('stk', k)               unknown content of stack slot k
  ('op', name, a, b)       arithmetic
  ('phi', (v1, v2, ...))   one of several values (branches / conditional moves)
  ('var', block, reg)      loop-variant value
  ('unk', why)
Not a decompiler: it is good enough for argument set-up before calls (constants, RAM loads,
task fields, table lookups), which is what the deff text tables need.
"""
import capstone
from capstone import arm as A
import rom
from rom import u32, u16, u8, foff

MD = rom.md()

RAM_LO, RAM_HI = 0x36000, 0x100000

# ---------------------------------------------------------------- function list
FUNCS = []      # sorted starts
FNAME = {}


def load_funcs(path="/home/claude/tron-legacy-le-rom-decryption/code/tron_game_decompiled_v2.c"):
    import re
    rx = re.compile(r"^// ==== ([0-9a-f]{8}) (\S+)")
    for line in open(path, errors="replace"):
        if line.startswith("// ===="):
            m = rx.match(line)
            if m:
                a = int(m.group(1), 16)
                FUNCS.append(a)
                FNAME[a] = m.group(2)
    FUNCS.sort()


def func_end(a):
    import bisect
    i = bisect.bisect_right(FUNCS, a)
    return FUNCS[i] if i < len(FUNCS) else a + 0x2000


def func_of(a):
    import bisect
    i = bisect.bisect_right(FUNCS, a) - 1
    return FUNCS[i] if i >= 0 else None


# ---------------------------------------------------------------- values
UNK = ('unk', '')


def C(v):
    return ('c', v & 0xffffffff)


def is_c(v):
    return v[0] == 'c'


def depth(v, d=0):
    if d > 8:
        return d
    if v[0] in ('op',):
        return max(depth(v[2], d + 1), depth(v[3], d + 1))
    if v[0] in ('ld', 'tbl'):
        return max(depth(v[1] if v[0] == 'ld' else v[2], d + 1), d + 1)
    if v[0] == 'phi':
        return max(depth(x, d + 1) for x in v[1])
    return d


def is_rom_const_addr(a):
    """Fixed (read-only) memory: OS code, game code, data banks."""
    return (0 <= a < RAM_LO) or (0x01000000 <= a < 0x01100000) or (0x04000000 <= a < 0x04800000)


def op(name, a, b):
    if a[0] == 'unk' or b[0] == 'unk':
        return ('unk', 'op')
    if a[0] == 'c' and b[0] == 'c':
        x, y = a[1], b[1]
        r = {'add': x + y, 'sub': x - y, 'rsb': y - x, 'and': x & y, 'orr': x | y, 'eor': x ^ y,
             'bic': x & ~y, 'lsl': x << (y & 31) if y < 32 else 0, 'lsr': x >> y if y < 32 else 0,
             'asr': (x - (1 << 32) if x & 0x80000000 else x) >> min(y, 31), 'mul': x * y,
             'ror': ((x >> (y & 31)) | (x << (32 - (y & 31)))) if y & 31 else x}.get(name)
        if r is not None:
            return C(r)
    if name == 'rsb':
        return op('sub', b, a)
    if a[0] == 'phi' and b[0] == 'c':
        return mkphi([op(name, x, b) for x in a[1]])
    if b[0] == 'phi' and a[0] == 'c':
        return mkphi([op(name, a, x) for x in b[1]])
    if name in ('add', 'sub') and a[0] == 'sp' and b[0] == 'c':
        return ('sp', a[1] + (b[1] if name == 'add' else -b[1]) if b[1] < 0x80000000 else a[1] - (0x100000000 - b[1]))
    if name == 'add' and b[0] == 'sp' and a[0] == 'c':
        return ('sp', b[1] + a[1])
    if name in ('add', 'sub') and b == C(0):
        return a
    if name == 'add' and a == C(0):
        return b
    if name in ('lsl', 'lsr', 'asr', 'orr', 'eor') and b == C(0):
        return a
    # lsl #16 / lsr #16 pairs (u16 casts): keep the inner value
    if name in ('lsr', 'asr') and a[0] == 'op' and a[1] == 'lsl' and a[3] == b and b[0] == 'c' and b[1] in (16, 24):
        return a[2]
    if name == 'and' and b[0] == 'c' and b[1] in (0xff, 0xffff) and a[0] in ('ram', 'task', 'ld', 'tbl') and a[-1] <= (1 if b[1] == 0xff else 2):
        return a
    v = ('op', name, a, b)
    if depth(v) > 7:
        return ('unk', 'deep')
    return v


def mkphi(vals):
    s = []
    for v in vals:
        for x in (v[1] if v[0] == 'phi' else (v,)):
            if x not in s:
                s.append(x)
    if len(s) == 1:
        return s[0]
    if len(s) > 8:
        return ('unk', 'many')
    return ('phi', tuple(s))


def load(base, off, size, signed=False):
    """Value of a load of size bytes at base+off."""
    if base[0] == 'c':
        a = (base[1] + off) & 0xffffffff
        if is_rom_const_addr(a) and foff(a) is not None:
            return C({1: u8, 2: u16, 4: u32}[size](a))
        return ('ram', a, size)
    if base[0] == 'op' and base[1] == 'add' and base[3][0] == 'c' and base[2][0] != 'c':
        return load(base[2], off + base[3][1], size)
    if base[0] == 'op' and base[1] == 'add':
        a, b = base[2], base[3]
        if b[0] == 'c':
            a, b = b, a
        if a[0] == 'c':
            return ('tbl', (a[1] + off) & 0xffffffff, b, size)
    if base == ('ram', 0x372c0, 4):
        return ('task', off, size)
    if base[0] == 'phi':
        return mkphi([load(x, off, size) for x in base[1]])
    if base[0] == 'unk':
        return ('unk', 'ld')
    v = ('ld', base, off, size)
    return v if depth(v) <= 7 else ('unk', 'deep')


# ---------------------------------------------------------------- state
class State:
    __slots__ = ('r', 'stk', 'flags', 'conds', 'shadow', 'base', 'view_cc')

    def __init__(self, r=None, stk=None, flags=None, conds=()):
        self.r = r if r is not None else {}
        self.stk = stk if stk is not None else {}
        self.flags = flags          # (kind, a, b) of the last flag-setting insn
        self.conds = conds          # tuple of (cc, kind, a, b) path conditions
        self.shadow = {}            # cc -> {reg: value written under that condition}
        self.base = {}              # reg -> value before the current run of conditional writes
        self.view_cc = None         # condition of the insn being executed

    def copy(self):
        s = State(dict(self.r), dict(self.stk), self.flags, self.conds)
        return s

    def get(self, reg):
        if self.view_cc is not None:
            sh = self.shadow.get(self.view_cc)
            if sh and reg in sh:
                return sh[reg]
            if reg in self.base:
                return self.base[reg]
        return self.r.get(reg, ('unk', 'r%d' % reg))

    def clear_cond(self):
        self.shadow = {}
        self.base = {}

    def key(self):
        return (tuple(sorted(self.r.items())), tuple(sorted(self.stk.items())), self.conds)


def merge(a, b, blk, count):
    out = State()
    out.conds = tuple(c for c in a.conds if c in b.conds)
    for k in set(a.r) | set(b.r):
        x = a.r.get(k, ('unk', 'undef'))
        y = b.r.get(k, ('unk', 'undef'))
        m = mkphi([x, y])
        if x == y or m == x:
            out.r[k] = x
        elif count > 6 or x[0] == "var":
            out.r[k] = ('var', blk, k)
        else:
            out.r[k] = m
    for k in set(a.stk) | set(b.stk):
        x = a.stk.get(k, ('stk', k))
        y = b.stk.get(k, ('stk', k))
        m = mkphi([x, y])
        if x == y or m == x:
            out.stk[k] = x
        elif count > 6 or x[0] == "var":
            out.stk[k] = ('var', blk, 'stk%d' % k)
        else:
            out.stk[k] = m
    return out


R = {A.ARM_REG_R0: 0, A.ARM_REG_R1: 1, A.ARM_REG_R2: 2, A.ARM_REG_R3: 3, A.ARM_REG_R4: 4, A.ARM_REG_R5: 5,
     A.ARM_REG_R6: 6, A.ARM_REG_R7: 7, A.ARM_REG_R8: 8, A.ARM_REG_R9: 9, A.ARM_REG_R10: 10,
     A.ARM_REG_R11: 11, A.ARM_REG_R12: 12, A.ARM_REG_R13: 13, A.ARM_REG_R14: 14, A.ARM_REG_R15: 15}
SP, LR, PC = 13, 14, 15

SHIFT = {A.ARM_SFT_LSL: 'lsl', A.ARM_SFT_LSR: 'lsr', A.ARM_SFT_ASR: 'asr', A.ARM_SFT_ROR: 'ror',
         A.ARM_SFT_LSL_REG: 'lsl', A.ARM_SFT_LSR_REG: 'lsr', A.ARM_SFT_ASR_REG: 'asr', A.ARM_SFT_ROR_REG: 'ror'}


def opval(st, o, pc):
    if o.type == A.ARM_OP_IMM:
        return C(o.imm)
    if o.type == A.ARM_OP_REG:
        r = R.get(o.reg)
        v = C(pc + 8) if r == PC else st.get(r)
        if o.shift.type and o.shift.type != A.ARM_SFT_INVALID:
            sh = SHIFT.get(o.shift.type)
            if o.shift.type in (A.ARM_SFT_LSL_REG, A.ARM_SFT_LSR_REG, A.ARM_SFT_ASR_REG, A.ARM_SFT_ROR_REG):
                amt = st.get(R[o.shift.value])
            else:
                amt = C(o.shift.value)
            if sh:
                v = op(sh, v, amt)
        return v
    return ('unk', 'opnd')


ALU = {A.ARM_INS_ADD: 'add', A.ARM_INS_SUB: 'sub', A.ARM_INS_RSB: 'rsb', A.ARM_INS_AND: 'and',
       A.ARM_INS_ORR: 'orr', A.ARM_INS_EOR: 'eor', A.ARM_INS_BIC: 'bic', A.ARM_INS_ADC: 'add',
       A.ARM_INS_SBC: 'sub', A.ARM_INS_RSC: 'rsb', A.ARM_INS_MUL: 'mul',
       A.ARM_INS_LSL: 'lsl', A.ARM_INS_LSR: 'lsr', A.ARM_INS_ASR: 'asr', A.ARM_INS_ROR: 'ror'}
LDR = {A.ARM_INS_LDR: 4, A.ARM_INS_LDRH: 2, A.ARM_INS_LDRB: 1, A.ARM_INS_LDRSH: 2, A.ARM_INS_LDRSB: 1}
STR = {A.ARM_INS_STR: 4, A.ARM_INS_STRH: 2, A.ARM_INS_STRB: 1}


def add_cond(conds, c):
    # only keep conditions on meaningful values (not loop counters / unknowns)
    def ok(v):
        return v[0] not in ('unk', 'var', 'stk') and depth(v) < 6
    if not (ok(c[2]) and ok(c[3])):
        return conds
    out = tuple(x for x in conds if x[1:] != c[1:])
    return (out + (c,))[-12:]


def replace(v, eqs):
    if v in eqs:
        return eqs[v]
    t = v[0]
    if t == 'op':
        return op(v[1], replace(v[2], eqs), replace(v[3], eqs))
    if t == 'phi':
        return mkphi([replace(x, eqs) for x in v[1]])
    if t == 'ld':
        return load(replace(v[1], eqs), v[2], v[3])
    if t == 'tbl':
        return ('tbl', v[1], replace(v[2], eqs), v[3])
    return v


def inv_cc(cc):
    return cc + 1 if cc % 2 == 1 else cc - 1


def setreg(st, rd, v, cond, pc=None, cc=None):
    if cond:
        if rd not in st.base:
            st.base[rd] = st.r.get(rd, ('unk', 'r%d' % rd))
        st.shadow.setdefault(cc, {})[rd] = v
        other = st.shadow.get(inv_cc(cc), {}).get(rd, st.base[rd])
        st.r[rd] = mkphi([other, v])
        return
    st.r[rd] = v
    if rd in st.base:
        del st.base[rd]
        for sh in st.shadow.values():
            sh.pop(rd, None)


class Call:
    __slots__ = ('site', 'target', 'regs', 'stack', 'ind', 'conds')

    def __init__(self, site, target, regs, stack, ind=None):
        self.site, self.target, self.regs, self.stack, self.ind = site, target, regs, stack, ind


def mem_addr(st, o, pc):
    m = o.mem
    base = C(pc + 8) if R.get(m.base) == PC else st.get(R[m.base])
    if m.index and m.index != A.ARM_REG_INVALID:
        idx = st.get(R[m.index])
        if o.shift.type and o.shift.type != A.ARM_SFT_INVALID:
            idx = op(SHIFT[o.shift.type], idx, C(o.shift.value))
        if o.subtracted:
            return base, ('neg', idx)
        return base, idx
    d = m.disp
    return base, C(d)


class Func:
    """Analyse function at start; results: calls (list of Call merged per site), returns value."""

    def __init__(self, start, end=None):
        self.start = start
        self.end = end or func_end(start)
        self.calls = {}
        self.ret = None
        self.insns = {}
        self.indirect = []
        self.switches = []
        self.stores = []
        self.analyse()

    def insn(self, a):
        i = self.insns.get(a)
        if i is None:
            o = foff(a)
            lst = list(MD.disasm(rom.ROM[o:o + 4], a))
            i = lst[0] if lst else None
            self.insns[a] = i
        return i

    def analyse(self):
        st0 = State()
        for k in range(4):
            st0.r[k] = ('arg', k)
        st0.r[SP] = ('sp', 0)
        for k in range(4, 12):
            st0.r[k] = ('unk', 'callee-saved r%d' % k)
        for k in range(0, 0x40, 4):
            st0.stk[k] = ('arg', 4 + k // 4)
        work = [(self.start, st0)]
        seen = {}
        cnt = {}
        steps = 0
        while work and steps < 60000:
            a, st = work.pop()
            prev = seen.get(a)
            if prev is not None:
                if prev.key() == st.key():
                    continue
                cnt[a] = cnt.get(a, 0) + 1
                if cnt[a] > 20:
                    continue
                st = merge(prev, st, a, cnt[a])
                if st.key() == prev.key():
                    continue
            seen[a] = st
            # run block
            st = st.copy()
            pc = a
            while steps < 60000:
                steps += 1
                i = self.insn(pc)
                if i is None:
                    break
                nxt = self.step(i, st)
                if nxt is None:            # fall through
                    pc += 4
                    if pc in seen and pc != a:
                        work.append((pc, st))
                        break
                    continue
                for t, s in nxt:
                    if t is not None:
                        work.append((t, s))
                break

    def record_call(self, site, target, st, ind=None):
        regs = [st.get(k) for k in range(4)] + [st.get(12)]
        sp = st.get(SP)
        stack = []
        if sp[0] == 'sp':
            for k in range(16):
                stack.append(st.stk.get(sp[1] + 4 * k, ('stk', sp[1] + 4 * k)))
        # path-sensitive refinement: on a path where (x == const) holds, x is that constant
        eqs = {}
        for cc, kind, a, b in st.conds:
            if cc == A.ARM_CC_EQ and kind == 'cmp' and b[0] == 'c' and a[0] != 'c':
                eqs[a] = b
            elif cc == A.ARM_CC_EQ and kind == 'tst' and b[0] == 'c' and a[0] != 'c' and b[1] in (0xff, 0xffff, 0xffffffff):
                eqs[a] = C(0)
        if eqs:
            regs = [replace(v, eqs) for v in regs]
            stack = [replace(v, eqs) for v in stack]
        c = Call(site, target, regs, stack, ind)
        c.conds = st.conds
        self.calls[site] = c      # last visit = most general state (block entry states only widen)

    def after_call(self, st, site, target):
        st.flags = None
        st.clear_cond()
        st.r[0] = ('ret', target, site)
        for k in (1, 2, 3, 12):
            st.r[k] = ('unk', 'clobbered')

    def step(self, i, st):
        """Execute one insn. Returns None (fall through) or list of (target, state) successors."""
        cond = i.cc not in (A.ARM_CC_AL, A.ARM_CC_INVALID)
        st.view_cc = i.cc if cond else None
        try:
            r = self._step(i, st, cond)
        finally:
            st.view_cc = None
        if r is not None:
            for _, s2 in r:
                s2.clear_cond()
        return r

    def _step(self, i, st, cond):
        ops = i.operands
        iid = i.id
        pc = i.address
        if iid == A.ARM_INS_BL:
            t = ops[0].imm
            self.record_call(pc, t, st)
            self.after_call(st, pc, t)
            return None
        if iid == A.ARM_INS_B:
            t = ops[0].imm
            if t in FNAME and t != self.start and not (self.start <= t < self.end):
                # tail call
                self.record_call(pc, t, st)
                if cond:
                    s2 = st.copy()
                    self.after_call(s2, pc, t)
                    return [(pc + 4, st)]
                return [(None, st)]
            if cond:
                s1 = st.copy()
                if st.flags is not None:
                    s1.conds = add_cond(st.conds, (i.cc,) + st.flags)
                    st.conds = add_cond(st.conds, (inv_cc(i.cc),) + st.flags)
                return [(t, s1), (pc + 4, st)]
            return [(t, st)]
        if iid == A.ARM_INS_BX:
            r = R[ops[0].reg]
            if r == LR:
                self.ret = mkphi([self.ret, st.get(0)]) if self.ret else st.get(0)
                return [(pc + 4, st)] if cond else [(None, st)]
            v = st.get(r)
            self.record_call(pc, v, st, ind='bx')
            return [(None, st)]
        # loads
        if iid in LDR:
            size = LDR[iid]
            rd = R[ops[0].reg]
            base, off = mem_addr(st, ops[1], pc)
            if off[0] == 'c':
                o = off[1] - (1 << 32) if off[1] & 0x80000000 else off[1]
                if ops[1].subtracted:
                    o = -o
                v = self.load(st, base, o, size)
            elif off[0] == 'neg':
                v = ('unk', 'ld-neg')
            else:
                if base[0] == 'c' and is_rom_const_addr(base[1]):
                    v = ('tbl', base[1], off, size)
                else:
                    v = load(op('add', base, off), 0, size)
            if len(ops) > 2 or i.writeback:
                # post/pre indexed writeback
                rn = R[ops[1].mem.base]
                inc = ops[2].imm if len(ops) > 2 and ops[2].type == A.ARM_OP_IMM else ops[1].mem.disp
                if len(ops) > 2 and ops[2].type == A.ARM_OP_IMM and ops[2].subtracted:
                    inc = -inc
                if len(ops) > 2 and ops[2].type == A.ARM_OP_IMM:
                    # post-index: load uses base only
                    v = self.load(st, base, 0, size)
                st.r[rn] = op('add', base, C(inc))
            if rd == PC:
                # ldr pc, [...] : indirect call when preceded by mov lr, pc
                prev = self.insn(pc - 4)
                if prev is not None and prev.id == A.ARM_INS_MOV and prev.op_str.startswith('lr, pc'):
                    self.indirect.append((pc, base, off))
                    self.record_call(pc, ('ind', base, off), st, ind='table')
                    self.after_call(st, pc, ('ind',))
                    return [(pc + 4, st)]
                if base == C(pc + 8) and ops[1].mem.index and ops[1].mem.index != A.ARM_REG_INVALID:
                    # switch jump table: cmp rX, #n ; ldrls pc, [pc, rX, lsl #2] ; b default ; .word targets
                    idx = st.get(R[ops[1].mem.index])
                    n = None
                    for back in range(1, 4):
                        p = self.insn(pc - 4 * back)
                        if p is not None and p.id == A.ARM_INS_CMP and p.operands[1].type == A.ARM_OP_IMM \
                                and R.get(p.operands[0].reg) == R[ops[1].mem.index]:
                            n = p.operands[1].imm + 1
                            break
                    if n is None or n > 64:
                        n = 0
                    targets = {}
                    for k in range(n):
                        targets.setdefault(u32(pc + 8 + 4 * k), []).append(k)
                    self.switches.append((pc, idx, {t: ks for t, ks in targets.items()}))
                    succ = []
                    for t, ks in targets.items():
                        s2 = st.copy()
                        cv = C(ks[0]) if len(ks) == 1 else mkphi([C(k) for k in ks])
                        s2.conds = add_cond(st.conds, (A.ARM_CC_EQ, 'cmp', idx, cv))
                        succ.append((t, s2))
                    if cond:
                        succ.append((pc + 4, st))
                    return succ
                if base == ('sp',) or (base[0] == 'sp'):
                    self.ret = mkphi([self.ret, st.get(0)]) if self.ret else st.get(0)
                    return [(None, st)]
                self.record_call(pc, ('ind', base, off), st, ind='jump')
                return [(None, st)]
            setreg(st, rd, v, cond, pc, i.cc)
            return None
        if iid in STR:
            size = STR[iid]
            v = st.get(R[ops[0].reg])
            base, off = mem_addr(st, ops[1], pc)
            if off[0] == 'c':
                o = off[1] - (1 << 32) if off[1] & 0x80000000 else off[1]
                if len(ops) > 2:
                    o = 0
                ad = op('add', base, C(o))
                rb, ro = ad, 0
                if rb[0] == 'op' and rb[1] == 'add' and rb[3][0] == 'c':
                    rb, ro = rb[2], rb[3][1]
                if rb[0] == 'ret':
                    self.stores.append((pc, rb, ro, size, v))
                if ad[0] == 'sp' and size == 4:
                    st.stk[ad[1]] = mkphi([st.stk.get(ad[1], ('stk', ad[1])), v]) if cond else v
                elif ad[0] == 'sp':
                    st.stk[ad[1] & ~3] = ('unk', 'partial')
            if len(ops) > 2 or i.writeback:
                rn = R[ops[1].mem.base]
                inc = ops[2].imm if len(ops) > 2 and ops[2].type == A.ARM_OP_IMM else ops[1].mem.disp
                st.r[rn] = op('add', base, C(inc))
            return None
        if iid in (A.ARM_INS_PUSH, A.ARM_INS_STMDB) or (iid == A.ARM_INS_STMDB):
            regs = [R[o.reg] for o in ops] if iid == A.ARM_INS_PUSH else [R[o.reg] for o in ops[1:]]
            base_r = SP if iid == A.ARM_INS_PUSH else R[ops[0].reg]
            sp = st.get(base_r)
            if sp[0] == 'sp':
                n = len(regs)
                new = sp[1] - 4 * n
                for k, r in enumerate(regs):
                    st.stk[new + 4 * k] = st.get(r)
                if iid == A.ARM_INS_PUSH or i.writeback:
                    st.r[base_r] = ('sp', new)
            return None
        if iid in (A.ARM_INS_POP, A.ARM_INS_LDM, A.ARM_INS_LDMIB, A.ARM_INS_LDMDA, A.ARM_INS_LDMDB):
            if iid == A.ARM_INS_POP:
                base_r, regs, wb = SP, [R[o.reg] for o in ops], True
            else:
                base_r, regs, wb = R[ops[0].reg], [R[o.reg] for o in ops[1:]], i.writeback
            b = st.get(base_r)
            vals = []
            n = len(regs)
            start = {A.ARM_INS_LDMIB: 4, A.ARM_INS_LDMDA: -4 * (n - 1), A.ARM_INS_LDMDB: -4 * n}.get(iid, 0)
            for k, r in enumerate(regs):
                if b[0] == 'sp':
                    vals.append(st.stk.get(b[1] + start + 4 * k, ('stk', b[1] + start + 4 * k)))
                else:
                    vals.append(load(b, start + 4 * k, 4))
            for r, v in zip(regs, vals):
                if r != PC:
                    setreg(st, r, v, cond, pc, i.cc)
            if wb and b[0] == 'sp':
                st.r[base_r] = ('sp', b[1] + 4 * len(regs))
            if PC in regs:
                self.ret = mkphi([self.ret, st.get(0)]) if self.ret else st.get(0)
                return [(pc + 4, st)] if cond else [(None, st)]
            return None
        if iid in (A.ARM_INS_STM, A.ARM_INS_STMIB, A.ARM_INS_STMDA):
            b = st.get(R[ops[0].reg])
            regs = [R[o.reg] for o in ops[1:]]
            n = len(regs)
            start = {A.ARM_INS_STM: 0, A.ARM_INS_STMIB: 4, A.ARM_INS_STMDA: -4 * (n - 1)}[iid]
            if b[0] == 'sp':
                for k, r in enumerate(regs):
                    st.stk[b[1] + start + 4 * k] = st.get(r)
            if i.writeback and b[0] == 'sp':
                st.r[R[ops[0].reg]] = ('sp', b[1] + (4 * n if iid != A.ARM_INS_STMDA else -4 * n))
            return None
        if iid in (A.ARM_INS_MOV, A.ARM_INS_MVN):
            rd = R[ops[0].reg]
            v = opval(st, ops[1], pc)
            if iid == A.ARM_INS_MVN:
                v = C(~v[1]) if v[0] == 'c' else op('eor', v, C(0xffffffff))
            if rd == PC:
                src = R.get(ops[1].reg) if ops[1].type == A.ARM_OP_REG else None
                if src == LR:
                    self.ret = mkphi([self.ret, st.get(0)]) if self.ret else st.get(0)
                    return [(pc + 4, st)] if cond else [(None, st)]
                prev = self.insn(pc - 4)
                if prev is not None and prev.id == A.ARM_INS_MOV and prev.op_str.startswith('lr, pc'):
                    self.record_call(pc, v, st, ind='reg')
                    self.after_call(st, pc, ('ind',))
                    return [(pc + 4, st)]
                self.record_call(pc, v, st, ind='jump')
                return [(None, st)]
            if i.update_flags:
                st.flags = ('cmp', v, C(0))
                st.clear_cond()
            if rd == LR and ops[1].type == A.ARM_OP_REG and R.get(ops[1].reg) == PC:
                st.r[LR] = C(pc + 8)
                return None
            setreg(st, rd, v, cond, pc, i.cc)
            return None
        if iid in ALU:
            rd = R[ops[0].reg]
            if len(ops) == 3:
                a, b = opval(st, ops[1], pc), opval(st, ops[2], pc)
                v = op(ALU[iid], a, b)
            elif ALU[iid] in ('lsl', 'lsr', 'asr', 'ror'):
                a, b = opval(st, ops[1], pc), C(0)
                v = a
            else:
                a, b = st.get(rd), opval(st, ops[1], pc)
                v = op(ALU[iid], a, b)
            if i.update_flags:
                st.flags = ('cmp', v, C(0)) if ALU[iid] != 'sub' else ('cmp', a, b)
                st.clear_cond()
            if rd == PC:
                self.record_call(pc, v, st, ind='jump')
                return [(None, st)]
            setreg(st, rd, v, cond, pc, i.cc)
            return None
        if iid in (A.ARM_INS_MLA,):
            rd = R[ops[0].reg]
            setreg(st, rd, op('add', op('mul', opval(st, ops[1], pc), opval(st, ops[2], pc)), opval(st, ops[3], pc)), cond, pc, i.cc)
            return None
        if iid in (A.ARM_INS_UMULL, A.ARM_INS_SMULL, A.ARM_INS_UMLAL, A.ARM_INS_SMLAL):
            lo, hi = R[ops[0].reg], R[ops[1].reg]
            x, y = opval(st, ops[2], pc), opval(st, ops[3], pc)
            setreg(st, lo, ('op', 'mull_lo', x, y) if depth(x) < 6 else UNK, cond)
            setreg(st, hi, ('op', 'mull_hi', x, y) if depth(x) < 6 else UNK, cond)
            return None
        if iid in (A.ARM_INS_CMP, A.ARM_INS_CMN, A.ARM_INS_TST, A.ARM_INS_TEQ):
            a, b = opval(st, ops[0], pc), opval(st, ops[1], pc)
            st.flags = ({A.ARM_INS_CMP: 'cmp', A.ARM_INS_CMN: 'cmn', A.ARM_INS_TST: 'tst', A.ARM_INS_TEQ: 'teq'}[iid], a, b)
            if cond:
                st.flags = None     # conditional compare: combined condition, not tracked
            else:
                st.clear_cond()
            return None
        if iid == A.ARM_INS_NOP:
            return None
        if iid in (A.ARM_INS_SVC, A.ARM_INS_MRS, A.ARM_INS_MSR):
            return None
        # anything else writing a register
        if ops and ops[0].type == A.ARM_OP_REG and R.get(ops[0].reg) is not None:
            rd = R[ops[0].reg]
            if rd == PC:
                return [(None, st)]
            st.r[rd] = ('unk', i.mnemonic)
        return None

    def load(self, st, base, o, size):
        if base[0] == 'sp':
            k = base[1] + o
            if size == 4:
                return st.stk.get(k, ('stk', k))
            v = st.stk.get(k & ~3)
            if v is not None and v[0] == 'c':
                return C((v[1] >> (8 * (k & 3))) & ((1 << (8 * size)) - 1))
            return ('unk', 'stk-part')
        return load(base, o, size)


# ---------------------------------------------------------------- substitution
def subst(v, args):
    """Replace ('arg', i) in v by args[i] (args = list of caller values)."""
    t = v[0]
    if t == 'arg':
        return args[v[1]] if v[1] < len(args) and args[v[1]] is not None else ('unk', 'arg%d' % v[1])
    if t == 'op':
        return op(v[1], subst(v[2], args), subst(v[3], args))
    if t == 'ld':
        return load(subst(v[1], args), v[2], v[3])
    if t == 'tbl':
        return ('tbl', v[1], subst(v[2], args), v[3])
    if t == 'phi':
        return mkphi([subst(x, args) for x in v[1]])
    return v


def has_arg(v):
    t = v[0]
    if t == 'arg':
        return True
    if t == 'op':
        return has_arg(v[2]) or has_arg(v[3])
    if t == 'ld':
        return has_arg(v[1])
    if t == 'tbl':
        return has_arg(v[2])
    if t == 'phi':
        return any(has_arg(x) for x in v[1])
    return False


_cache = {}


def analyse(start):
    f = _cache.get(start)
    if f is None:
        f = Func(start)
        _cache[start] = f
    return f
