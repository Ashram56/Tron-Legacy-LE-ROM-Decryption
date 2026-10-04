"""Static pass over every display effect (deff) of trn_174h: text draws, images, timing, RNG.

Usage: python3 deff_static.py OUT.json
Walks the call tree from each deff function (table 0x040e1350, count from the table of tables
RAM 0x36c54) through game and OS code, function-pointer tables and spawned tasks, and records
every call to a text API, image API, timing call, sound/lamp/tube call and RNG call, with the
argument values resolved by deff_sym (symbolic ARM interpreter) and substituted along the path.
"""
import json
import os
import re
import sys
import glob

import rom
from rom import u32, u16, u8, foff, msg, hx
import deff_sym as S
RAM_LO, RAM_HI = 0x36000, 0x100000

S.load_funcs()
REPO = "/home/claude/tron-legacy-le-rom-decryption"

# ------------------------------------------------------------------ names
RAMNAME = {}
RAMMEAN = {}


def load_ram_names():
    for line in open(REPO + "/rules/tools/ghidra/ram_symbols.tsv"):
        p = line.rstrip("\n").split("\t")
        if len(p) >= 2 and p[0].startswith("0x"):
            RAMNAME[int(p[0], 16)] = p[1]
    for fn in glob.glob(REPO + "/rules/work/ram/*.tsv"):
        if fn.endswith("_functions.tsv"):
            for line in open(fn):
                p = line.rstrip("\n").split("\t")
                if len(p) >= 2 and p[0].startswith("0x"):
                    a = int(p[0], 16)
                    if S.FNAME.get(a, "").startswith("FUN_"):
                        S.FNAME[a] = p[1]
            continue
        for line in open(fn):
            p = line.rstrip("\n").split("\t")
            if len(p) >= 2 and p[0].startswith("0x"):
                a = int(p[0], 16)
                RAMNAME.setdefault(a, p[1])
                if len(p) >= 5 and p[4]:
                    RAMMEAN.setdefault(a, p[4])
    # OS API names
    for f in json.load(open(REPO + "/rules/work/os_api.json")):
        S.FNAME[int(f["addr"], 16)] = f["name"]


load_ram_names()

FNARGS = {}


def load_sigs(path=REPO + "/code/tron_game_decompiled_v2.c"):
    rx = re.compile(r"^// ==== ([0-9a-f]{8}) ")
    cur = None
    for line in open(path, errors="replace"):
        m = rx.match(line)
        if m:
            cur = int(m.group(1), 16)
            continue
        if cur is not None and "(" in line and not line.startswith("/*"):
            args = line[line.index("(") + 1:line.rindex(")")] if ")" in line else ""
            FNARGS[cur] = 0 if args.strip() in ("", "void") else args.count(",") + 1
            cur = None
    for f in json.load(open(REPO + "/rules/work/os_api.json")):
        sig = f["signature"]
        args = sig[sig.index("(") + 1:sig.rindex(")")]
        FNARGS[int(f["addr"], 16)] = 0 if args.strip() in ("", "void") else args.count(",") + 1


load_sigs()
EXTRA_NAMES = {0xa3b4: "language_get", 0x28c1c: "font_fit_msgs", 0x28c6c: "font_fit_str", 0x28a04: "msg_width",
               0x28a24: "msg_printf_width", 0x2b210: "bitmap_draw_buf", 0x28d08: "text_draw_msg_buf",
               0x28dd8: "text_printf_msg_buf", 0x28eb0: "text_printf_msg_fit", 0x29174: "text_printf_str_page",
               0x29248: "text_draw_str_fit_page", 0x291e4: "text_printf_str_buf", 0x29384: "text_printf_str_fit_page",
               0xc684: "lcg_next", 0xc6b4: "random_below", 0xc6d4: "random_percent", 0xc674: "rng_seed",
               0xc668: "rng_seed_default"}
S.FNAME.update(EXTRA_NAMES)
FNARGS.update({0xa3b4: 0, 0x28c1c: 3, 0x28c6c: 3, 0xc6b4: 1, 0xc6d4: 1, 0xc684: 0})
LANG_FNS = (0xa3b4, 0xa424)
N_LANG = 5   # language_get returns 0..4 (0x0000a424: value > 4 is replaced by the default)

# ---- font metrics from rom_data/fonts.json (for resolving font_fit_* statically, English)
FONTS = {f["font"]: f for f in json.load(open(REPO + "/rom_data/fonts.json"))["fonts"]}


def text_width(sx, font):
    """Port of text_width 0x28a74."""
    f = FONTS.get(font)
    if f is None or sx is None:
        return None
    pen = mn = mx = 0
    for ch in sx:
        g = f["glyphs"].get(ch)
        if g is None:
            continue
        pen += g["x_offset"]
        mn, mx = min(mn, pen), max(mx, pen)
        pen += g["w"]
        mn, mx = min(mn, pen), max(mx, pen)
        pen += f["spacing"]
    return mx - mn
EXTRA_RAM = {0x372c0: "current_task", 0x3d530: "dmd_work_page0", 0x3d52c: "dmd_work_page1",
             0x3d528: "dmd_shown_page1", 0x3d524: "dmd_shown_page0", 0x381a8: "deff_active_id",
             0x3817c: "current_player", 0x372c4: "rng_state"}
for k, v in EXTRA_RAM.items():
    RAMNAME.setdefault(k, v)

# ------------------------------------------------------------------ API tables
# arg spec: 'rN' register, 'sN' outgoing stack word N, 'ip'
TEXT_APIS = {
    0x28ca8: ("text_draw_msg", "msg", "font", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), None),
    0x28d08: ("text_draw_msg_buf", "msg", "font", dict(text="r0", buf="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), None),
    0x28d5c: ("text_printf_msg", "msg", "font", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), 3),
    0x28dd8: ("text_printf_msg_buf", "msg", "font", dict(text="r0", buf="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), 3),
    0x28e48: ("text_draw_msg_fit", "msg", "list", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2", max_width="s3"), None),
    0x28eb0: ("text_printf_msg_fit", "msg", "list", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2", max_width="s3"), 4),
    0x28f34: ("text_draw_str_page", "str", "font", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), None),
    0x28f74: ("text_draw_str", "str", "font", dict(text="r0", buf="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), None),
    0x29174: ("text_printf_str_page", "fmt", "font", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), 3),
    0x29178: ("text_printf_str_page_ip", "fmt", "font", dict(text="ip", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), 3),
    0x291e4: ("text_printf_str_buf", "fmt", "font", dict(text="r0", buf="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), 3),
    0x291e8: ("text_printf_str_buf_ip", "fmt", "font", dict(text="ip", buf="r1", font="r2", flags="r3", x="s0", y="s1", color="s2"), 3),
    0x29248: ("text_draw_str_fit_page", "str", "list", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2", max_width="s3"), None),
    0x2928c: ("text_draw_str_fit", "str", "list", dict(text="r0", buf="r1", font="r2", flags="r3", x="s0", y="s1", color="s2", max_width="s3"), None),
    0x29384: ("text_printf_str_fit_page", "fmt", "list", dict(text="r0", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2", max_width="s3"), 4),
    0x29388: ("text_printf_str_fit_page_ip", "fmt", "list", dict(text="ip", page="r1", font="r2", flags="r3", x="s0", y="s1", color="s2", max_width="s3"), 4),
}
IMG_APIS = {
    0x2b378: ("bitmap_draw", dict(image="r0", page="r1", x="r2", y="r3", palette="s0")),
    0x2b424: ("bitmap_draw_masked", dict(image="r0", page="r1", x="r2", y="r3", palette="s0", transparent="s1")),
    0x2b210: ("bitmap_draw_buf", dict(image="r0", buf="r1", x="r2", y="r3", palette="s0")),
    0x1023edc: ("anim_play", dict(first_image="r0", last_image="r1", ticks_per_frame="r2", loops="r3", sound_cues="s0")),
    0x1023fe4: ("anim_play_pal", dict(first_image="r0", last_image="r1", ticks_per_frame="r2", loops="r3", sound_cues="s0")),
}
TIME_APIS = {
    0xb91c: ("task_sleep", dict(ticks="r0")),
    0x2791c: ("deff_frame_sleep", dict(ticks="r0")),
    0x10241a0: ("deff_status_frames", dict(frames="r0", arg="r1")),
    0x1024460: ("deff_hold_frames", dict(frames="r0", arg="r1")),
    0x27830: ("dmd_show_pages", dict(page0="r0", page1="r1")),
    0x278b8: ("dmd_flip", dict()),
}
FX_APIS = {
    0x2c8f4: ("snd_play", dict(call="r0")),
    0x2c984: ("snd_play_after", dict(call="r0")),
    0x2ca1c: ("snd_play_chain", dict(call="r0")),
    0x87ac: ("leff_start", dict(leff="r0")),
    0x101b824: ("tube_show_start", dict(show="r0")),
    0x10289b8: ("shaker_run", dict(strength="r0", min_setting="r1")),
    0x280b0: ("deff_start", dict(deff="r0", queue="r1", force="r2")),
}
RNG_APIS = {
    0xc6b4: ("random_below", "r0 = (n * lcg_next()) >> 32, uniform 0..n-1", dict(n="r0")),
    0xc6d4: ("random_percent", "returns 1 when 1 + ((lcg_next() * 100) >> 32) <= p, i.e. p % chance", dict(p="r0")),
    0xc684: ("lcg_next", "state = state * 0x19660d + 1 (RAM 0x372c4), returns new state", dict()),
    0xc708: ("bag_weighted_pick", "weighted pick over an array of {fn/weight}; random_below(sum of weights) unless one weight >= 1000", dict(bag="r0")),
}
PAL_APIS = {0x2b554: "palette_identity", 0x2b56c: "palette_fill"}
SPRINTF = {0x35e6c: "sprintf"}
COMPONENTS = {0x10230ec: "status_panel", 0x10241a0: "deff_status_frames", 0x1024460: "deff_hold_frames",
              0x1023edc: "anim_play", 0x1023fe4: "anim_play_pal"}
# OS functions we never descend into (pure library / framework); everything else is followed
OS_LEAF = set()
for f in json.load(open(REPO + "/rules/work/os_api.json")):
    a = int(f["addr"], 16)
    if a < 0x36000:
        OS_LEAF.add(a)
OS_LEAF |= {0xa58c, 0x35fb0, 0x35e6c, 0x28a74, 0x28940}


def getarg(call, spec):
    if spec == "ip":
        return call.regs[4]
    if spec[0] == "r":
        return call.regs[int(spec[1:])]
    k = int(spec[1:])
    return call.stack[k] if k < len(call.stack) else ("unk", "stack")


def sub(v, ctx):
    return S.subst(v, ctx) if ctx is not None else v


# ------------------------------------------------------------------ rendering
def fname(a):
    if isinstance(a, int):
        return S.FNAME.get(a, "FUN_%08x" % a)
    return "indirect"


CALLINFO = {}   # site -> (Call, ctx) for rendering ret values


def ramstr(a, size):
    n = RAMNAME.get(a)
    s = "RAM[%s]%s" % (hx(a), {1: ".u8", 2: ".u16", 4: ""}[size])
    return s + (" (%s)" % n if n else "")


def render(v, d=0):
    t = v[0]
    if d > 6:
        return "..."
    if t == "c":
        x = v[1]
        return str(x) if x < 0x10000 else (hx(x) if x < 0x80000000 else str(x - (1 << 32)))
    if t == "ram":
        return ramstr(v[1], v[2])
    if t == "task":
        return "task+%s%s" % (hx(v[1]), {1: ".u8", 2: ".u16", 4: ""}[v[2]])
    if t == "tbl":
        return "ROM[%s + %s]%s" % (hx(v[1]), render(v[2], d + 1), {1: ".u8", 2: ".u16", 4: ""}[v[3]])
    if t == "ld":
        nm = RAMNAME.get(v[2])
        sz = {1: ".u8", 2: ".u16", 4: ""}[v[3]]
        if nm or (0x02100000 <= v[2] < 0x02120000) or (RAM_LO <= v[2] < RAM_HI):
            return "RAM[%s + %s]%s%s" % (hx(v[2]), render(v[1], d + 1), sz, " (%s)" % nm if nm else "")
        return "[%s + %s]%s" % (render(v[1], d + 1), hx(v[2]), sz)
    if t == "arg":
        return "arg%d" % v[1]
    if t == "ret":
        ci = CALLINFO.get(v[2])
        if isinstance(v[1], int) and ci is not None:
            c, ctx = ci
            nargs = min(FNARGS.get(v[1], 0), 4)
            args = ", ".join(render(sub(c.regs[k], ctx), d + 1) for k in range(nargs))
            return "%s(%s)@%s" % (fname(v[1]), args, hx(v[2]))
        return "%s()@%s" % (fname(v[1]) if isinstance(v[1], int) else "indirect", hx(v[2]))
    if t == "sp":
        return "stack_buf[sp%+d]" % v[1]
    if t == "stk":
        return "stack[sp%+d]" % v[1]
    if t == "op":
        sym = {"add": "+", "sub": "-", "and": "&", "orr": "|", "eor": "^", "lsl": "<<", "lsr": ">>",
               "asr": ">>", "mul": "*", "bic": "&~", "ror": "ror", "mull_hi": "*hi*", "mull_lo": "*lo*"}.get(v[1], v[1])
        return "(%s %s %s)" % (render(v[2], d + 1), sym, render(v[3], d + 1))
    if t == "phi":
        return "one of {%s}" % ", ".join(render(x, d + 1) for x in v[1])
    if t == "var":
        return "loop_var@%s" % hx(v[1])
    if t == "unk":
        return "?" + (v[1] or "")
    return str(v)


CC = {1: "==", 2: "!=", 3: ">=u", 4: "<u", 5: "<0", 6: ">=0", 9: ">u", 10: "<=u", 11: ">=", 12: "<", 13: ">", 14: "<="}


def render_cond(c, ctx):
    cc, kind, a, b = c
    a, b = sub(a, ctx), sub(b, ctx)
    if kind == "tst":
        return "(%s & %s) %s 0" % (render(a), render(b), {1: "==", 2: "!="}.get(cc, CC.get(cc, "?")))
    if kind == "cmn":
        return "%s %s -%s" % (render(a), CC.get(cc, "?"), render(b))
    return "%s %s %s" % (render(a), CC.get(cc, "?"), render(b))


def interesting_cond(c):
    """Keep selectors on game state (RAM, task fields, call results, arguments), drop pure constants."""
    def st(v):
        return v[0] in ("ram", "task", "ret", "arg", "tbl", "ld") or (v[0] == "op" and (st(v[2]) or st(v[3])))
    return st(c[2]) or st(c[3])


def fold(v, lang=None):
    """Constant-fold v; with lang set, language_get() results become that constant."""
    t = v[0]
    if t == "ret" and lang is not None and v[1] in LANG_FNS:
        return S.C(lang)
    if t == "op":
        return S.op(v[1], fold(v[2], lang), fold(v[3], lang))
    if t == "tbl":
        idx = fold(v[2], lang)
        if idx[0] == "c":
            return S.load(S.C(v[1] + idx[1]), 0, v[3])
        return ("tbl", v[1], idx, v[3])
    if t == "ld":
        return S.load(fold(v[1], lang), v[2], v[3])
    if t == "phi":
        return S.mkphi([fold(x, lang) for x in v[1]])
    return v


def uses_lang(v):
    t = v[0]
    if t == "ret":
        return v[1] in LANG_FNS
    if t == "op":
        return uses_lang(v[2]) or uses_lang(v[3])
    if t == "tbl":
        return uses_lang(v[2])
    if t == "ld":
        return uses_lang(v[1])
    if t == "phi":
        return any(uses_lang(x) for x in v[1])
    return False


def by_language(v):
    """[value for language 0..4] when v depends on language_get(), else None."""
    if not uses_lang(v):
        return None
    out = []
    for k in range(N_LANG):
        f = fold(v, k)
        out.append(consts(f))
    return out


def fit_choice(t, fl, flags, x, maxw):
    """Port of the font selection loop of text_draw_str_fit 0x2928c (English text)."""
    for f in fl:
        w = text_width(t, f)
        if w is None:
            return None
        if maxw:
            if w <= maxw:
                return f
            continue
        if flags & 1 and x + w <= 128:
            return f
        if flags & 2:
            left = x - (w >> 1)
            if left >= 0 and left + w <= 128:
                return f
            continue
        if flags & 4:
            if x - w - 1 <= 127 and x - 2 * w >= 0:
                return f
            continue
    return 0


def u16list(a, n=32):
    out = []
    while len(out) < n and foff(a) is not None:
        w = u16(a)
        if w == 0:
            break
        out.append(w)
        a += 2
    return out


def font_picker(v):
    """Describe a font chosen at run time by font_fit_msgs 0x28c1c / font_fit_str 0x28c6c."""
    if v[0] == "ret" and v[1] in (0x28e48, 0x2928c, 0x29248):
        c, ctx = CALLINFO.get(v[2], (None, None))
        d = {"picker": hx(v[1]), "picker_name": fname(v[1]), "call_site": hx(v[2]),
             "rule": "the font that the fit draw at call_site chose (it returns the font it used)"}
        if c is not None:
            fl = fold(sub(c.regs[2], ctx))
            if fl[0] == "c":
                d["font_list_addr"] = hx(fl[1])
                d["font_list"] = font_list(fl[1])
            if v[1] == 0x28e48:
                mid = fold(sub(c.regs[0], ctx))
                fx, fy = fold(sub(c.stack[0], ctx)), fold(sub(c.regs[3], ctx))
                mw = fold(sub(c.stack[3], ctx))
                if mid[0] == "c" and d.get("font_list") and fx[0] == "c" and fy[0] == "c" and mw[0] == "c":
                    d["english_choice"] = fit_choice(msg(mid[1]), d["font_list"], fy[1], fx[1], mw[1])
        return d
    if v[0] != "ret" or v[1] not in (0x28c1c, 0x28c6c):
        return None
    c, ctx = CALLINFO.get(v[2], (None, None))
    if c is None:
        return None
    a0, a1, a2 = (fold(sub(c.regs[k], ctx)) for k in range(3))
    d = {"picker": hx(v[1]), "picker_name": fname(v[1]), "call_site": hx(v[2])}
    fl = font_list(a1[1]) if a1[0] == "c" else None
    d["font_list_addr"] = hx(a1[1]) if a1[0] == "c" else render(a1)
    d["font_list"] = fl
    d["max_width"] = a2[1] if a2[0] == "c" else render(a2)
    texts = None
    if v[1] == 0x28c1c and a0[0] == "c":
        ids = u16list(a0[1])
        d["msg_list_addr"] = hx(a0[1])
        d["msg_ids"] = ids
        texts = [msg(i) for i in ids]
        d["rule"] = "first font in font_list in which every message of msg_list is <= max_width pixels wide (else 0, the list terminator = font 0)"
    elif v[1] == 0x28c6c:
        src = a0
        if src[0] == "ret" and src[1] == 0xa58c:
            mc, mctx = CALLINFO.get(src[2], (None, None))
            ids = consts(fold(sub(mc.regs[0], mctx))) if mc else None
            d["msg_ids"] = ids
            texts = [msg(i) for i in ids] if ids else None
        elif src[0] == "c":
            texts = [rom.cstr(src[1])]
        d["rule"] = "first font in font_list in which the string is <= max_width pixels wide (else the 0 terminator -> font 0)"
    if fl and texts and a2[0] == "c":
        chosen = None
        for fnt in fl:
            if all((text_width(t, fnt) or 0) <= a2[1] for t in texts if t):
                chosen = fnt
                break
        if chosen is None:
            chosen = 0
        d["english_choice"] = chosen
        d["english_widths"] = {str(fnt): [text_width(t, fnt) for t in texts if t] for fnt in fl}
    return d


def cval(v):
    return v[1] if v[0] == "c" else None


def consts(v):
    if v[0] == "c":
        return [v[1]]
    if v[0] == "phi" and all(x[0] == "c" for x in v[1]):
        return [x[1] for x in v[1]]
    return None


def _s32(x):
    x &= 0xffffffff
    return x - (1 << 32) if x & 0x80000000 else x


def evalc(v, d=0):
    """Values of v for English text: constants, font_height(const) 0x28940 from fonts.json, the font a
    font picker returns (English choice), language_get() = 0. None when not fully resolvable."""
    if d > 12:
        return None
    t = v[0]
    if t == "c":
        return [_s32(v[1])]
    if t == "phi":
        out = []
        for x in v[1]:
            r = evalc(x, d + 1)
            if r is None:
                return None
            out += [y for y in r if y not in out]
        return out
    if t == "ret":
        if v[1] in LANG_FNS:
            return [0]
        if v[1] == 0x28940:
            c, ctx = CALLINFO.get(v[2], (None, None))
            if c is None:
                return None
            fs = evalc(fold(sub(c.regs[0], ctx)), d + 1)
            if not fs or any(FONTS.get(f & 0xff) is None for f in fs):
                return None
            return sorted({FONTS[f & 0xff]["height"] for f in fs})
        fp = font_picker(v)
        if fp and fp.get("english_choice") is not None:
            return [fp["english_choice"]]
        return None
    if t == "tbl":
        idx = evalc(v[2], d + 1)
        if idx is None or len(idx) > 8:
            return None
        out = []
        for i in idx:
            a = v[1] + i
            if foff(a) is None:
                return None
            x = {1: rom.u8, 2: rom.u16, 4: rom.u32}[v[3]](a)
            if x not in out:
                out.append(x)
        return out
    if t == "op":
        a, b = evalc(v[2], d + 1), evalc(v[3], d + 1)
        if a is None or b is None or len(a) * len(b) > 16:
            return None
        out = []
        for x in a:
            for y in b:
                n = v[1]
                if n == "add": r = x + y
                elif n == "sub": r = x - y
                elif n == "rsb": r = y - x
                elif n == "mul": r = x * y
                elif n == "mull_hi": r = (x * y) >> 32
                elif n == "mull_lo": r = x * y
                elif n == "and": r = x & y
                elif n == "orr": r = x | y
                elif n == "eor": r = x ^ y
                elif n == "bic": r = x & ~y
                elif n == "lsl": r = x << (y & 31)
                elif n == "lsr": r = (x & 0xffffffff) >> (y & 31)
                elif n == "asr": r = x >> min(y, 31)
                else: return None
                r = _s32(r)
                if r not in out:
                    out.append(r)
        return out
    return None


# ------------------------------------------------------------------ helpers for args
def font_list(addr):
    out = []
    a = addr
    while len(out) < 16:
        if foff(a) is None:
            return None
        w = u32(a)
        if w == 0:
            break
        if w > 64:
            return None
        out.append(w)
        a += 4
    return out


def count_conversions(fmt):
    """Number of 32-bit argument words vsprintf 0x35fb0 consumes for fmt."""
    if fmt is None:
        return 0
    n = 0
    i = 0
    convs = []
    while i < len(fmt):
        if fmt[i] != "%":
            i += 1
            continue
        i += 1
        if i < len(fmt) and fmt[i] == "%":
            i += 1
            continue
        start = i
        while i < len(fmt) and fmt[i] in "+,-":
            i += 1
        while i < len(fmt) and fmt[i].isdigit():
            i += 1
        ll = False
        if i < len(fmt) and fmt[i] == "l":
            i += 1
            if i < len(fmt) and fmt[i] == "l":
                ll = True
                i += 1
        if i >= len(fmt):
            break
        c = fmt[i]
        i += 1
        if c == "P":
            while i < len(fmt) and fmt[i].isdigit():
                i += 1
            # options /a/b/.../%  -> skip to the closing %
            j = fmt.find("%", i)
            spec = fmt[start - 1:(j + 1 if j >= 0 else len(fmt))]
            i = j + 1 if j >= 0 else len(fmt)
            convs.append((spec, 2 if ll else 1))
            n += 2 if ll else 1
            continue
        convs.append((fmt[start - 1:i], 2 if ll else 1))
        n += 2 if ll else 1
    return n, convs


PALETTES = {}   # (func, sp offset) -> description


def palette_desc(fstart, v, ctx):
    if v[0] == "c" and v[1] == 0:
        return "none (0)"
    if v[0] == "sp":
        ops = PALETTES.get((fstart, v[1]))
        if ops:
            return "local palette sp%+d: %s" % (v[1], "; ".join(ops))
        return "local palette sp%+d" % v[1]
    if v[0] == "phi":
        return "one of {%s}" % ", ".join(palette_desc(fstart, x, ctx) for x in v[1])
    if v[0] == "c" and foff(v[1]) is not None and S.is_rom_const_addr(v[1]):
        a = v[1]
        return "ROM palette %s = %s" % (hx(a), list(rom.ROM[foff(a):foff(a) + 16]))
    return render(v)


def collect_palettes(f):
    seq = sorted(f.calls.items())
    for site, c in seq:
        if c.target == 0x2b554 and c.regs[0][0] == "sp":
            PALETTES.setdefault((f.start, c.regs[0][1]), []).append("identity")
        if c.target == 0x2b56c and c.regs[0][0] == "sp":
            val, lo, hi = (render(c.regs[k]) for k in (1, 2, 3))
            PALETTES.setdefault((f.start, c.regs[0][1]), []).append("levels %s..%s -> %s" % (lo, hi, val))


def str_source(f, v, ctx):
    """Describe a char* argument: msg_get(id) result, ROM string, or a stack buffer filled by sprintf."""
    v = sub(v, ctx)
    if v[0] == "ret" and v[1] == 0xa58c:
        c, cctx = CALLINFO.get(v[2], (None, None))
        if c is not None:
            mid = sub(c.regs[0], cctx)
            return {"kind": "msg", "msg": mid}
    if v[0] == "c" and foff(v[1]) is not None:
        return {"kind": "rom_string", "addr": v[1], "text": rom.cstr(v[1])}
    if v[0] == "sp":
        for site, c in sorted(f.calls.items()):
            if c.target in (0x35e6c, 0x35ef0) and c.regs[0] == v:
                return {"kind": "sprintf" if c.target == 0x35e6c else "strcpy", "site": site, "fmt": sub(c.regs[1], ctx),
                        "call": c, "ctx": ctx}
        return {"kind": "stack_buffer"}
    return {"kind": "value", "value": v}


def text_of(v):
    """Message id(s) / literal for a text value."""
    cs = consts(v)
    return cs


# ------------------------------------------------------------------ walker
class Walker:
    def __init__(self, root, label):
        self.root = root
        self.label = label
        self.draws = []
        self.images = []
        self.timing = []
        self.fx = []
        self.rng = []
        self.funcs = []
        self.components = set()
        self.indirect = []
        self.spawned = []
        self.visited = set()
        self.attract = []

    def walk(self, fstart, ctx, path, conds, depth=0):
        key = (fstart, repr(ctx)[:400])
        if key in self.visited or depth > 9 or len(self.visited) > 400:
            return
        self.visited.add(key)
        f = S.analyse(fstart)
        collect_palettes(f)
        self.funcs.append({"fn": fstart, "name": fname(fstart), "depth": depth, "path": [hx(p) for p in path]})
        for site, c in sorted(f.calls.items()):
            CALLINFO.setdefault(site, (c, ctx))
        for site, c in sorted(f.calls.items()):
            cc = conds + [render_cond(x, ctx) for x in c.conds if interesting_cond(x) and interesting_cond((x[0], x[1], fold(sub(x[2], ctx)), fold(sub(x[3], ctx))))]
            t = c.target
            here = path + [site]
            if isinstance(t, int):
                if t in TEXT_APIS:
                    self.text(f, site, c, ctx, here, cc)
                    continue
                if t in IMG_APIS:
                    nm, spec = IMG_APIS[t]
                    rec = {"site": site, "api": nm, "path": [hx(p) for p in here], "conds": cc}
                    for k, s in spec.items():
                        v = sub(getarg(c, s), ctx)
                        rec[k] = palette_desc(fstart, v, ctx) if k == "palette" else render(v)
                        if k in ("image", "first_image", "last_image"):
                            rec[k + "_ids"] = consts(v)
                    self.images.append(rec)
                    if t in COMPONENTS:
                        self.components.add(COMPONENTS[t])
                    continue
                if t in TIME_APIS:
                    nm, spec = TIME_APIS[t]
                    rec = {"site": site, "api": nm, "path": [hx(p) for p in here], "conds": cc}
                    for k, s in spec.items():
                        rec[k] = render(sub(getarg(c, s), ctx))
                    self.timing.append(rec)
                    if t in COMPONENTS:
                        self.components.add(COMPONENTS[t])
                    continue
                if t in FX_APIS:
                    nm, spec = FX_APIS[t]
                    rec = {"site": site, "api": nm, "conds": cc}
                    for k, s in spec.items():
                        rec[k] = render(sub(getarg(c, s), ctx))
                    self.fx.append(rec)
                    continue
                if t in RNG_APIS:
                    self.rng_call(f, site, c, ctx, here, cc)
                    continue
                if t in COMPONENTS:
                    self.components.add(COMPONENTS[t])
                    continue
                if t in OS_LEAF and t not in (0xb624, 0xb718, 0xb76c, 0xb840, 0xc1b8):
                    continue
                if t in (0xb624, 0xb718, 0xb76c, 0xb840, 0xc1b8):
                    # task creation: follow the function pointer argument
                    spec = {0xb624: "r1", 0xb718: "r1", 0xb76c: "r1", 0xb840: "r0", 0xc1b8: "r1"}[t]
                    fv = sub(getarg(c, spec), ctx)
                    for fp in consts(fv) or []:
                        if fp in S.FNAME:
                            self.spawned.append({"site": site, "api": fname(t), "fn": fp})
                            self.walk(fp, None, here, cc, depth + 1)
                    continue
                if t in S.FNAME:
                    args = [sub(c.regs[k], ctx) for k in range(4)] + [sub(x, ctx) for x in c.stack]
                    self.walk(t, args, here, cc, depth + 1)
                continue
            # indirect call
            if isinstance(t, tuple) and t and t[0] == "ind":
                base, off = t[1], t[2]
                base = sub(base, ctx)
                off = sub(off, ctx)
                ents = self.table_entries(base, off)
                self.indirect.append({"site": site, "table": render(base), "index": render(off),
                                      "entries": [hx(e) for e in ents]})
                for k, e in enumerate(ents):
                    self.walk(e, [None] * 4, here, cc + ["indirect table entry %d" % k], depth + 1)
            else:
                v = sub(t, ctx) if isinstance(t, tuple) else t
                for fp in consts(v) or []:
                    if fp in S.FNAME:
                        self.walk(fp, [sub(c.regs[k], ctx) for k in range(4)], here, cc, depth + 1)

    def table_entries(self, base, off):
        if base[0] != "c":
            return []
        b = base[1]
        n = None
        # index = rng(n) << 2
        if off[0] == "op" and off[1] == "lsl" and off[3] == ("c", 2):
            idx = off[2]
            if idx[0] == "ret" and idx[1] == 0xc6b4:
                c, cctx = CALLINFO.get(idx[2], (None, None))
                if c is not None:
                    n = cval(sub(c.regs[0], cctx))
            cs = consts(idx)
            if cs:
                return [u32(b + 4 * k) for k in cs if foff(b + 4 * k) is not None]
        out = []
        for k in range(n or 64):
            if foff(b + 4 * k) is None:
                break
            e = u32(b + 4 * k)
            if e not in S.FNAME:
                break
            out.append(e)
        return out

    def text(self, f, site, c, ctx, here, cc):
        nm, kind, fkind, spec, va = TEXT_APIS[c.target]
        vals = {k: sub(getarg(c, s), ctx) for k, s in spec.items()}
        rec = {"site": site, "api": nm, "api_addr": c.target, "fn": f.start, "path": [hx(p) for p in here],
               "conds": cc}
        tv = fold(vals["text"])
        rec["text_value"] = render(tv)
        bl = by_language(tv)
        if bl and kind == "msg":
            rec["msg_by_language"] = bl
            tv = S.mkphi([S.C(x) for l in bl if l for x in l])
        fmts = []
        if kind == "msg":
            ids = consts(tv)
            rec["msg_ids"] = ids
            if ids:
                fmts = [msg(i) for i in ids]
        else:
            src = str_source(f, tv, None)
            rec["str_source"] = src["kind"]
            if src["kind"] == "msg":
                ids = consts(src["msg"])
                rec["msg_ids"] = ids
                rec["text_value"] = "msg_get(%s)" % render(src["msg"])
                fmts = [msg(i) for i in ids] if ids else []
            elif src["kind"] == "rom_string":
                fmts = [src["text"]]
                rec["str_addr"] = src["addr"]
            elif src["kind"] in ("sprintf", "strcpy"):
                fv = src["fmt"]
                rec["sprintf_site"] = src["site"]
                if fv[0] == "ret" and fv[1] == 0xa58c:
                    mc, mctx = CALLINFO.get(fv[2], (None, None))
                    ids = consts(sub(mc.regs[0], mctx)) if mc else None
                    rec["msg_ids"] = ids
                    fmts = [msg(i) for i in ids] if ids else []
                elif fv[0] == "c" and foff(fv[1]) is not None:
                    fmts = [rom.cstr(fv[1])]
                    rec["str_addr"] = fv[1]
                # sprintf varargs: r2, r3, stack...
                sc = src["call"]
                n, convs = count_conversions(fmts[0]) if fmts and fmts[0] else (0, [])
                words = [sc.regs[2], sc.regs[3]] + list(sc.stack)
                rec["args"] = self.va_args(words, n, convs, src["ctx"])
            elif kind == "fmt":
                if tv[0] == "c" and foff(tv[1]) is not None:
                    fmts = [rom.cstr(tv[1])]
                    rec["str_addr"] = tv[1]
        if kind == "fmt" and tv[0] == "c" and foff(tv[1]) is not None and not fmts:
            fmts = [rom.cstr(tv[1])]
        rec["formats"] = fmts
        vals = {k: fold(v) for k, v in vals.items()}
        fv = vals["font"]
        rec["font_value"] = render(fv)
        if fkind == "font":
            rec["font"] = consts(fv)
            bl = by_language(fv)
            if bl:
                rec["font_by_language"] = bl
                rec["font"] = bl[0]
            fp = font_picker(fv)
            if fp:
                rec["font_picker"] = fp
                rec["font"] = [fp["english_choice"]] if "english_choice" in fp else None
            if not rec["font"]:
                ev = evalc(fv)
                if ev is not None and len(ev) <= 8:
                    rec["font"] = ev
                    rec["font_evaluated"] = "English: %s evaluated" % render(fv)
        else:
            cs = consts(fv)
            bl = by_language(fv)
            if bl:
                rec["font_list_by_language"] = [[hx(a) for a in x] if x else None for x in bl]
                cs = sorted({a for x in bl if x for a in x})
            rec["font_list_addr"] = cs
            rec["font_lists"] = {hx(a): font_list(a) for a in cs} if cs else None
            rec["_fit"] = True
        rec["flags"] = consts(vals["flags"])
        rec["flags_value"] = render(vals["flags"])
        for k in ("x", "y", "max_width"):
            if k in vals:
                rec[k] = consts(vals[k])
                rec[k + "_value"] = render(vals[k])
                if rec[k] is None:
                    ev = evalc(vals[k])
                    if ev is not None and len(ev) <= 8:
                        rec[k] = ev
                        rec[k + "_evaluated"] = "English: %s evaluated with fonts.json font heights / fit choices" % render(vals[k])
                bl = by_language(vals[k])
                if bl:
                    rec[k + "_by_language"] = bl
        rec["color"] = palette_desc(f.start, vals["color"], ctx)
        rec["page"] = render(vals.get("page", vals.get("buf")))
        if va is not None:
            words = c.stack[va:]
            words = [sub(w, ctx) for w in words]
            fmt0 = next((x for x in fmts if x), None)
            n, convs = count_conversions(fmt0) if fmt0 else (0, [])
            # several candidate formats: take the max number of words
            for fx in fmts:
                if fx:
                    n2, cv2 = count_conversions(fx)
                    if n2 > n:
                        n, convs = n2, cv2
            rec["args"] = self.va_args(words, n, convs, None)
        if rec.pop("_fit", False):
            fl = rec["font_lists"]
            fx, ffl, mw = (rec.get("x") or [None])[0], (rec.get("flags") or [None])[0], (rec.get("max_width") or [None])[0]
            if fl and len(fl) == 1 and fmts and len(fmts) == 1 and fmts[0] and fx is not None and ffl is not None and mw is not None \
                    and not rec.get("args"):
                rec["english_font_choice"] = fit_choice(fmts[0], list(fl.values())[0] or [], ffl, fx, mw)
        self.draws.append(rec)

    def va_args(self, words, n, convs, ctx):
        out = []
        k = 0
        for order, (spec, w) in enumerate(convs):
            v = sub(words[k], ctx) if k < len(words) else ("unk", "")
            a = {"order": order + 1, "conversion": spec, "source": render(v)}
            if v[0] == "ram":
                a["ram_addr"] = hx(v[1])
                a["name"] = RAMNAME.get(v[1])
                if RAMMEAN.get(v[1]):
                    a["meaning"] = RAMMEAN[v[1]]
            elif v[0] == "task":
                a["task_field"] = hx(v[1])
                a["meaning"] = "deff task block parameter (written by the code that started the deff)"
            elif v[0] == "ret" and isinstance(v[1], int):
                a["function"] = hx(v[1])
                a["name"] = fname(v[1])
            elif v[0] == "c":
                a["constant"] = v[1]
            if w == 2:
                a["words"] = 2
            out.append(a)
            k += w
        return out

    def rng_call(self, f, site, c, ctx, here, cc):
        nm, algo, spec = RNG_APIS[c.target]
        rec = {"site": site, "fn": f.start, "rng_fn": c.target, "rng_name": nm, "conds": cc,
               "path": [hx(p) for p in here]}
        for k, s in spec.items():
            rec[k] = render(sub(getarg(c, s), ctx))
            rec[k + "_const"] = cval(sub(getarg(c, s), ctx))
        # uses of the result inside this function
        rv = ("ret", c.target, site)
        uses = []

        def contains(v):
            if v == rv:
                return True
            if v[0] == "op":
                return contains(v[2]) or contains(v[3])
            if v[0] in ("ld",):
                return contains(v[1])
            if v[0] == "tbl":
                return contains(v[2])
            if v[0] == "phi":
                return any(contains(x) for x in v[1])
            return False
        for s2, c2 in sorted(f.calls.items()):
            if s2 <= site:
                continue
            if isinstance(c2.target, tuple) and c2.target[0] == "ind" and contains(c2.target[2]):
                uses.append({"site": s2, "use": "indirect call through table", "table": render(c2.target[1]),
                             "index": render(c2.target[2])})
                continue
            for k, v in enumerate(list(c2.regs[:4]) + list(c2.stack[:8])):
                if contains(v):
                    uses.append({"site": s2, "use": "arg %s of %s" % (("r%d" % k) if k < 4 else "stack%d" % (k - 4), fname(c2.target) if isinstance(c2.target, int) else "indirect"),
                                 "value": render(v)})
            for cd in c2.conds:
                if contains(cd[2]) or contains(cd[3]):
                    u = {"site": s2, "use": "branch condition", "cond": render_cond(cd, None)}
                    if u not in uses:
                        uses.append(u)
        rec["uses"] = uses[:40]
        self.rng.append(rec)


def deff_table():
    ptr, count, size = u32(0x36c54), u32(0x36c58), u32(0x36c5c)
    assert ptr == 0x040e1350 and size == 8, (hx(ptr), size)
    out = []
    for i in range(count):
        a = ptr + 8 * i
        out.append({"id": i, "entry_addr": a, "fn": u32(a), "flags": u16(a + 4), "priority": u8(a + 6), "byte7": u8(a + 7)})
    return out, count


def is_stub(fn):
    ins = rom.disasm(fn, 2)
    return bool(ins) and ins[0].mnemonic == "mov" and ins[0].op_str == "pc, lr" or (ins and ins[0].mnemonic == "bx" and ins[0].op_str == "lr")


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items() if k not in ("call", "ctx")}
    if isinstance(o, (list, tuple)):
        return [jsonable(x) for x in o]
    if isinstance(o, set):
        return sorted(o)
    return o


def main(out):
    table, count = deff_table()
    res = {"table": {"addr": "0x040e1350", "count": count, "count_source": "table of tables RAM 0x36c54 {ptr,count,size}"},
           "deffs": [], "components": {}}
    for d in table:
        if d["fn"] == 0:
            res["deffs"].append(dict(d, stub="null entry"))
            continue
        w = Walker(d["fn"], d["id"])
        stub = is_stub(d["fn"])
        if not stub:
            w.walk(d["fn"], None, [], [])
        if d["id"] == 1:
            # deff_001 walks the attract page table attr_page_table (RAM 0x36e10, initial value from the ROM
            # image at the same offset): {cond_fn, page_fn} pairs up to page_fn == 0; page_fn runs as a child task
            # with task+0x30 = attract pass number, when cond_fn(pass) != 0 or cond_fn == 0.
            a = 0x36e10
            k = 0
            while u32(a + 4):
                cf, pf = u32(a), u32(a + 4)
                sel = "attract page %d (attr_page_table RAM 0x%x): %s" % (k, a, "always" if cf == 0 else "%s(pass) != 0" % fname(cf))
                if pf not in S.FNAME:
                    S.FNAME[pf] = "sub_%08x" % pf
                w.attract.append({"page": k, "entry_addr": hx(a), "cond_fn": hx(cf), "cond_name": fname(cf) if cf else None,
                                  "page_fn": hx(pf), "page_name": fname(pf)})
                w.walk(pf, None, [0x10343a0], [sel], 1)
                a += 8
                k += 1
        rec = dict(d)
        rec.update(stub=stub, functions=w.funcs, draws=w.draws, images=w.images, timing=w.timing, fx=w.fx,
                   rng=w.rng, components=sorted(w.components), indirect=w.indirect, spawned=w.spawned,
                   attract_pages=w.attract)
        res["deffs"].append(rec)
    for a, nm in COMPONENTS.items():
        w = Walker(a, nm)
        w.walk(a, None, [], [])
        res["components"][nm] = {"fn": a, "draws": w.draws, "images": w.images, "timing": w.timing, "functions": w.funcs, "rng": w.rng}
    json.dump(jsonable(res), open(out, "w"), indent=1, default=str)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/tmp/claude-0/work_deffs/static.json")
