"""Recipes for effects 32 33 36 48 49 68 125 128 129 137 138 140 141 143 (agent D).
Same format as RECIPES in tools/gen_code_dmd.py (needs `import deff_state as S` from tools/), plus two keys the generator must honour:
  max_insns : instruction limit for the run (MAX_INSNS 6M cuts the long effects: 125 needs ~25M, 128/129/140/143 ~15-30M).
HARNESS FIX NEEDED (found with 140, whose first dissolve transition FUN_0102b26c reads the SHOWN pages 0x3d528 / 0x3d524):
  deff_unicorn stubs dmd_show_pages (0x27830, NAMES) so its stores never happen; the stub must do what the code does
  (0x27830): [0x3d534]=[0x3d524]; [0x3d524]=r1; [0x3d538]=[0x3d528]; [0x3d528]=r0   (words), then return as now.
  All results below were measured with that fix (/tmp/h2.py); 125 128 129 138 48 49 68 143 do not need it, 140 does.
Control = reference frames of columns 41-127 reproduced exactly (frames order-independent as in gen_code_dmd.control).
"""
import deff_state as S

G = S.game
RECIPES_D = {
    32: dict(args=[0, 0, 0, 0, 0, 0], ram=G, max_insns=3000000),                     # 0/107 exact (see REASONS_D)
    33: dict(args=[0, 0, 0, 0], ram=G, max_insns=3000000),                           # 0/17 exact (see REASONS_D)
    36: dict(args=[0, 0, 0, 0], ram=G, max_insns=3000000),                           # 0/106 exact (see REASONS_D)
    48: dict(args=[0, 0, 0, 0], ram=G, rng=9, max_insns=20000000),                   # 66/66
    49: dict(args=[0, 0, 0, 0], ram=G, rng=10, max_insns=20000000),                  # 79/79
    68: dict(args=[0, 0, 0, 0], ram=G, rng=1, max_insns=20000000),                   # 100/100
    125: dict(args=[0, 0, 0, 0], ram=G, max_insns=60000000),                         # 258/258 (arg +0x30 = 0: "%,02lu" prints 0)
    128: dict(args=[0, 0, 0, 0], ram=G, max_insns=60000000),                         # 142/142 (+0x30 = 0 -> table 0x040d2ac4[0] = FUN_01011394, anim 0x1215-0x1285)
    129: dict(args=[0, 0, 0, 0], ram=G, max_insns=60000000),                         # 142/142
    137: dict(args=[0, 0, 0, 0], ram=G, max_insns=6000000),                          # 39/40 (frame 0 not drawn by the effect, REASONS_D)
    138: dict(args=[0, 0, 0, 0], ram=lambda: {**S.game(), 0x2111608: 500000}, max_insns=20000000),  # 37/37 (eol_combo_jackpot)
    140: dict(args=[0, 0, 0, 0], ram=G, max_insns=60000000),                         # 144/144 (needs the dmd_show_pages fix above)
    141: dict(args=[0, 0, 0, 0], ram=G, max_insns=4000000),                          # 107/108 (infinite loop effect: 4M is enough; frame 0 REASONS_D)
    143: dict(args=[0, 0, 0, 0], ram=G, max_insns=60000000),                         # 265/265
}

# NOT for the generator unless the owner waives (docs/pinmame_waivers.md): the byte of emulator memory at address 1 is
# the only thing missing for 32 and 36; the value 0x58 was found by testing candidates against the control, it has no ROM source.
RECIPES_D_FITTED = {
    32: dict(args=[0, 0, 0, 0, 0, 0], ram=lambda: {**S.game(), 0: 0x5800}, max_insns=3000000),   # 106/107
    36: dict(args=[0, 0, 0, 0], ram=lambda: {**S.game(), 0: 0x5800}, max_insns=3000000),          # 106/106
}

REASONS_D = {
    32: "106 of 107 reference frames carry only 34 wrong pixels (x 70-74, rows 12-21: the 2nd character of the text field), the other frame (index 0) is the screen shown before the forced run started. The reference is a forced run with all arguments 0: the record pointer (task +0x38) is address 0, FUN_00033afc (0x33afc) stores 0 at address 0 and deff_032 (0x010346e8) writes the typed chars into [0 + index] then draws the field from that buffer (FUN_010363a4 0x10363a4); the 2nd character is the byte at ADDRESS 1, i.e. emulator memory at a null buffer, not a game value (our harness holds ROM[1]=0xf0 there, which has no glyph). Proof: the byte at address 1 is the only unknown; with it = 0x58 the code gives 106/107 (the 107th is the pre-effect frame), everything else exact. 0 exact frames under the 100% criterion.",
    33: "17 of 17 frames differ only by one glyph (19 pixels, x 62-66, rows 8-12). Reference = forced run with null record: deff_033 (0x01034f88) -> FUN_01034e78 (0x1034e78) calls lang_select(param_1[5]) (0xa440) with param_1 = 0, so it reads the word at address 0x14 (0xe1a00000, the vector-table NOP) as a pointer to a language list and dereferences 0xe1a00000, an unmapped address; the value PinMAME returns there is the string drawn by FUN_00029248 (a null result draws nothing: our run). A string whose first char is 'X' (0x58) at that pointer reproduces 17/17, so the only missing datum is that unmapped-memory read; it has no ROM source. 0 exact frames.",
    36: "0 of 106 exact, but every frame differs by the same 34 pixels as effect 32 (x 70-74, rows 12-21). deff_036_place (0x0103649c) is the same forced null-record run: iVar10 = *(task+0x30) = 0, FUN_00033afc(local_34, 0, ...) makes address 0 the text buffer (0x33afc), the loop writes s[i] at [0+index] and FUN_010363a4 (0x10363a4) shows buffer byte 1, read from emulator memory at address 1. With that byte = 0x58 the code gives 106/106 (RECIPES_D_FITTED), so nothing else differs; the byte has no ROM source (ROM[1] = 0xf0).",
    137: "39 of 40 exact with all arguments 0 (task +0x30 = 0 prints '00'). The missing frame is index 0: it shows the status panel and a one-line text at rows 26-30 from the screen displayed before the forced run started; deff_137 (0x0100daec) never draws it (its first flip is bitmap 0xaca on a cleared work page), the same frame 0 appears in effects 32 and 141. A capture artefact, not code.",
    141: "107 of 108 exact (task args 0, RAM zero: pm_phase 0x3b878 = 0). The missing frame is index 0, the same pre-effect screen as in 137 (deff_141 0x0102ffa0 clears work page 0, draws the panel and 'PORTAL MULTIBALL' first); it is not drawn by this routine.",
}
