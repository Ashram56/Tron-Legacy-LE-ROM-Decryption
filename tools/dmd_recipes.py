"""Recipes of the classic DMD generator (tools/gen_code_dmd.py): for each display effect, the arguments (task block words +0x30..), RAM state,
random_below draws and boot initialisers under which the ROM's own routine, run in Unicorn, draws what the effect draws. Every value was read
from the effect's decompiled code (docs/dmd_from_code.md); the PinMAME capture only tested candidates. Keys: args, ram, rng (int / callable),
init, counters, max_insns, fn_addr (run a child task body), extra_runs, runs (concatenated recipes), real_show_pages (run the real
dmd_show_pages 0x27830: it keeps the shown-pages bookkeeping RAM 0x3d524/28/34/38 that dissolve transitions read), prev / first_frame_prev
(the screen on display before the effect = another effect's frame). REASONS: effects that stay under 100 % against the capture and why.
The four modules were written by effect group (A: service screens, B: modes, C: wizards, D: clips and multiballs).
"""
import deff_state as S
from dmd_recipes_a import RECIPES_A, REASONS_A
from dmd_recipes_b import RECIPES_B, REASONS_B
from dmd_recipes_c import RECIPES_C, REASONS_C
from dmd_recipes_d import RECIPES_D, REASONS_D

RECIPES = {
    9: dict(ram=lambda: {**S.game(), **S.error_log(10)}),                  # error summary counts ten type-2 records
    14: dict(args=[0], ram=S.game),
    112: dict(args=[4]),                                                    # stage 4: SUPER SPINNERS (task+0x30.u8 == 4), 3X
    111: dict(args=[6], rng=7, max_insns=20000000),                         # clip variant 7, "6 more to start"
}
REASONS = {}
for _r, _w in ((RECIPES_A, REASONS_A), (RECIPES_B, REASONS_B), (RECIPES_C, REASONS_C), (RECIPES_D, REASONS_D)):
    RECIPES.update(_r)
    REASONS.update(_w)
for _e in (64, 94, 100, 102, 113, 140):                # transitions read the shown pages: run the real dmd_show_pages
    RECIPES[_e]["real_show_pages"] = True
