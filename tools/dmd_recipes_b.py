"""Recipes for deff 19 25 46 57 64 65 71 74 75 84 85 86 (columns 41-127 control, STRICT RULE: values read from the code, reference only tests).
Extra keys beyond gen_code_dmd.RECIPES (the generator must pass them to deff_frames.frames):
  max_insns   instruction limit (the effects loop for ever; 6M is too short for some)
  fn_addr     run this routine instead of the deff (child task body)
  extra_runs  more runs whose frames are added to the effect's (list of dict(fn_addr=, max_insns=, ram=))
  real_show_pages  True: do NOT stub dmd_show_pages (0x27830) in deff_unicorn.NAMES (run the real code, it keeps the shown-pages
                   bookkeeping RAM 0x3d524/0x3d528/0x3d534/0x3d538 that the dissolve transition 0x102b26c reads as its 'old' pages)
"""
import deff_state as S

RECIPES_B = {
    19: dict(args=[0, 0, 0, 0], ram=lambda: S.game(scores=(0, 0, 0, 0)), init=S.INIT + ((0x22c08, 0),),
             counters=(0x21117f4,), max_insns=20000000),          # 107/107, all columns
    25: dict(args=[0, 0, 0, 0], ram=lambda: {**S.game(), 0x21115e0: 50000, 0x21115d4: 1}, max_insns=20000000,
             extra_runs=[dict(fn_addr=0x1000e7c, max_insns=3000000)]),   # 12/12: child bonus_count_task frames 0-3 + effect frames 4-11
    46: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=40000000),    # 126/126
    57: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=15000000),    # 209/209 (eol_switch_value 0x3ae00 = 0 never visible: text at y 0x1f is off the visible rows)
    64: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=30000000, real_show_pages=True),   # 75/75
    65: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=20000000),    # 129/129
    71: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=20000000),    # 36/37 (frame 0 not this routine)
    74: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=20000000),    # 40/41
    75: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=20000000),    # 52/53
    84: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=20000000),    # 104/104
    85: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=20000000),    # 147/147
    86: dict(args=[0, 0, 0, 0], ram=S.game, max_insns=40000000),    # 254/254 (loop period 176 iterations x 4 flips needs >700 flips)
}

REASONS_B = {
    71: "36 of 37 exact; reference frame 0 is not drawn by deff_071 (0x10022d8): it is the picture on the DMD before the effect took over, with the 5-row text line at y 25-30 that is byte-identical in the first frames of 71, 74 and 75 (no text call in the routine draws it; the routine's first dmd_show_pages frame, bitmap 0x18d3, equals reference frame 1 exactly).",
    74: "40 of 41 exact; reference frame 0 (only a small text line at y 26-30, identical to frame 0 of 71 and 75) is the display before the effect (deff_074 0x1002d24 draws it nowhere); frames 1-40 exact.",
    75: "52 of 53 exact; reference frame 0 (previous screen + the same y 25-30 text line as in 71 and 74) is not drawn by deff_075 (0x10140f8); the routine's first frame equals reference frame 1 exactly.",
}
