"""Recipes for effects 94, 96, 99, 100, 102, 104, 105, 108, 113, 115, 119 (agent C of the deff recipe search, 2026-11-26).

Keys as in tools/gen_code_dmd.py RECIPES (args, ram, rng, init, counters) plus three that the generator needs to honour:
  max_insns : instruction limit of the run (the generator's MAX_INSNS = 6M cuts effects that end with deff_hold_frames);
  fn_addr   : run this routine instead of the deff's own (a child task body);
  runs      : list of recipes whose frames are concatenated (the reference holds several runs of one effect).
HARNESS FIX NEEDED (tools/deff_unicorn.py): `dmd_show_pages` 0x27830 is stubbed (NAMES), so the RAM words it writes are never
updated: DAT_0003d534 = DAT_0003d524; DAT_0003d524 = page1; DAT_0003d538 = DAT_0003d528; DAT_0003d528 = page0 (0x27830..0x27868).
Screen transitions (FUN_00027acc -> 0x102b980, 0x102b744 ...) and deff_hold_frames (0x1024460: copies page DAT_0003d528) read them.
install_show_pages_state() below does it from a hook; call it before F.frames (effect 94 needs it: 49 -> 53 of 53).
"""
import struct
import deff_state as S


def install_show_pages_state():
    import deff_unicorn as D
    from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1
    from unicorn import UC_HOOK_CODE
    orig = D.build

    def build():
        mu = orig()

        def h(mu, a, s, u):
            g = lambda x: struct.unpack('<I', bytes(mu.mem_read(x, 4)))[0]
            w = lambda x, v: mu.mem_write(x, struct.pack('<I', v))
            p0, p1 = mu.reg_read(UC_ARM_REG_R0), mu.reg_read(UC_ARM_REG_R1)
            w(0x3d534, g(0x3d524)); w(0x3d524, p1); w(0x3d538, g(0x3d528)); w(0x3d528, p0)
        mu.hook_add(UC_HOOK_CODE, h, begin=0x27830, end=0x27830)
        return mu
    D.build = build


class _Seq:
    """random_below (0xc6b4) draws in order (value capped to n-1 by the harness); single use per run."""
    def __init__(self, picks): self.p, self.i = picks, 0
    def __call__(self, n):
        v = self.p[self.i] if self.i < len(self.p) else 0
        self.i += 1
        return v


RECIPES_C = {
    94: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=6000000, needs_show_pages_state=True),   # 53/53
    96: dict(args=[0, 0, 0, 0], ram=S.game, fn_addr=0x01032a30, max_insns=9000000),            # 28/28 (child task 0x1032a30)
    99: dict(args=[710000, 0, 0, 0], ram=S.game, max_insns=12000000),                          # 58/59 (+0x30 = total, FUN_00028eb0 0x4e4)
    # prev = the screen shown BEFORE the effect starts (pages DAT_0003d528 / DAT_0003d524 at entry), taken from another effect's code run:
    # prev=dict(deff=19, frame=k) = the k-th distinct (page0, page1) pair of effect 19's run (recipe of effect 19: game state, init
    # INIT + (0x22c08, 0), counters=(0x21117f4,)), copied to two free pages with 0x3d528/0x3d524 pointing at them (see seed_previous_screen).
    100: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=12000000, prev=dict(deff=19, frame=1)),  # 13/13 with prev (10/13 without)
    102: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=12000000, first_frame_prev=dict(deff=19, frame=0)),  # 28/29 (29/29 with the pre-effect frame = effect 19 frame 0)
    104: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=12000000),                              # 82/82 (the hold frames need > 6M insns)
    105: dict(args=[0, 0, 0, 0], ram=lambda: {**S.game(), 0x2111608: 500000}, rng=_Seq([0, 1, 1, 0, 3, 6, 1]), max_insns=4000000),  # 38/38; rng is single use (set .i = 0 to reuse)
    108: dict(args=[0, 0, 0, 0], ram=S.game, rng=2, max_insns=12000000),                       # 52/52 (random_below(4): 2 or 3)
    113: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=20000000, first_frame_prev=dict(deff=19, frame=0)),  # 180/181 (181/181 with the pre-effect frame)
    115: dict(runs=[dict(args=[0, 0, 0, 0], ram=lambda: {**S.game(scores=(0, 0, 0, 0)), 0x3b630: 1000000}, max_insns=8000000),
                    dict(args=[1, 0, 0, 0], ram=lambda: {**S.game(scores=(0, 0, 0, 0)), 0x3b638: 2000000}, max_insns=8000000)]),  # 153/164
    119: dict(args=[0, 0, 0, 0], ram=S.game, rng=1, max_insns=6000000),                        # 47/47
}


def seed_previous_screen(ram, fg, bg, p0=20, p1=21):
    """Put a previous screen (two 0x1000-byte DMD pages) in RAM dict `ram` and point 0x3d528 / 0x3d524 at it."""
    for i in range(0, 0x1000, 4):
        ram[0x01080000 + 0x1000 * p0 + i] = struct.unpack_from('<I', fg, i)[0]
        ram[0x01080000 + 0x1000 * p1 + i] = struct.unpack_from('<I', bg, i)[0]
    ram[0x3d528], ram[0x3d524] = p0, p1
    return ram


REASONS_C = {
    99: "58 of 59 exact (+0x30 = 710000, the total printed by FUN_00028eb0 0x4e4 at 0x01033200; a forced run with the capture's own value). "
        "The last reference frame (58) is not drawn by deff_099_zfs_total (0x010331ac): after the loop the routine only runs deff_hold_frames "
        "(0x1024460), which copies the page DAT_0003d528 of the last frame it showed (our frames 58 = that page); the reference's last frame is a "
        "different full screen (text left, ring picture right) of the next display the live game started: emulator state, not this routine.",
    100: "10 of 13 without a previous screen, 13 of 13 with prev (effect 19 frame 1). Frames 0-2 are the first three steps of the dissolve "
         "FUN_00027acc(0xe) -> 0x0102b744, which copies the pages DAT_0003d528 / DAT_0003d524 at entry (0x0102b744: dmd_copy_rect of the shown pages): "
         "the screen shown before the effect, i.e. the score display (effect 19, exact in code).",
    102: "28 of 29. Reference frame 0 equals frame 0 of effect 19's code run (columns 41-127): the score display shown before the effect's first "
         "dmd_show_pages; deff_102_skill_shot (0x010294d0) draws nothing before its first flip. The 28 others are exact with arguments 0.",
    113: "180 of 181. Same as 102: reference frame 0 equals frame 0 of effect 19's code run (the screen on display when the capture starts); "
         "deff_113_sea_of (0x010268c4) draws its first frame only at its first deff_status_frames. 180 others exact.",
    115: "153 of 164 (two runs, item 0 = 1,000,000 and item 1 = 2,000,000). The 11 missing frames (0, 75-79, 159-163) are drawn by other effects "
         "around it: the effect lowers its priority with FUN_00028580(0x20) (0x28580, RAM 0x381aa) so the next deff replaces it (docs/dmd_from_code.md).",
}
