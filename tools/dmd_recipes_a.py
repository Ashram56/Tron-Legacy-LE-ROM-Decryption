# Recipes for effects 10, 18, 21, 23, 24, 27, 31, 34, 35, 37, 43 (control: columns 41-127, every reference frame).
# Merge into tools/gen_code_dmd.py (S = deff_state). init = boot initialisers for deff_unicorn.run(init=...); gen_code_dmd.recipe()
# must pass r.get("init", S.INIT) to F.frames (it passes S.INIT today).
import deff_state as S

RECIPES_A = {
    # exact with the default recipe (args 0, S.game(), S.INIT): listed for the record
    21: dict(args=[0, 0, 0, 0], ram=S.game),     # 125/125
    23: dict(args=[0, 0, 0, 0], ram=S.game),     # 11/11
    31: dict(args=[0, 0, 0, 0], ram=S.game),     # 13/13
    34: dict(args=[0, 0, 0, 0], ram=S.game),     # 11/11
    35: dict(args=[0, 0, 0, 0], ram=S.game),     # 13/13
    # 18: tournament_get() (0x2553c) needs the valid zero tournament record 0 (checksum record written by FUN_00024698, 0x24698(0));
    # the second screen "BUMP 'N' WIN SCORE" (0x4a0) is drawn only when it is non-null.  27/27
    18: dict(args=[0, 0, 0, 0], ram=S.game, init=(0x2ae54, (0x1278, 0), (0x24698, 0))),
    # 43: pop_hits_left[player] (RAM 0x211179b + 1) = 25 = pop_hits_for_next_level() at first ball (pop_first_ball_reset 0x101c28c:
    # (adj 65 = 1 + 0) * 5 + 0x14); the effect shows "0 MORE" once, then "25 MORE".  27/27
    43: dict(args=[0, 0, 0, 0], ram=lambda: {**S.game(), 0x211179c: 25}),
    # equivalent: init=(0x2ae54, (0x1278, 0), (0x101c28c, 0))
}

REASONS_A = {
    10: "39 of 40 reference frames exact (cols 41-127). Missing: reference frame 0 only, a bottom-line text (rows 26-30) that deff_010 "
        "(0x1000000) never draws: its pages hold only the credit text (FUN_00004ff4, msgs 0x2fd/0x2fe at x 0x54) and "
        "deff_status_frames(0xf,0) (0x10241a0) fills cols 41-127 with 0xff (transparent). The same frame is frame 0 of the reference of "
        "effect 24: it is the idle screen shown before the effect's first dmd_show_pages, not this routine's output.",
    24: "1 of 2 exact. deff_024_slam_tilt (0x1035ccc) draws one page (msg 0x30a) then deff_frame_sleep(0x138) (0x2791c). Reference frame 0 "
        "is the idle bottom-line screen, byte-identical to frame 0 of the reference of effect 10; no instruction of the routine draws it.",
    27: "1 of 4 exact. deff_027 (0x1035090) only runs the callback table RAM 0x37038 (17 entries, ROM data) from index RAM 0x37438. "
        "Frame 0 = callback 0x2fcc0 (INSTANT INFO, exact). Frames 1 and 3 are the idle bottom-line screen (same as effect 10/24 frame 0), "
        "frame 2 is byte-identical to frame 0 of the reference of effect 19 (score display, '00' at x 0x54): other effects' frames. "
        "The code run also yields 2 more pages (callbacks 0x2f9a0 and 0x1001b54) that the capture's 4 frames do not contain.",
    37: "13 of 14 exact. Missing: reference frame 0, byte-identical to frame 0 of the reference of effect 19 and to frame 2 of effect 27 "
        "(score display '00' with status panel, x 0x54): drawn by the score display before deff_037 (0x10369bc) starts; deff_037 "
        "draws bitmap 0xd0 + FUN_01036934 (0x1036934) at x 0x40 only.",
}
