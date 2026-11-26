# Classic 128x32 DMD from the ROM's code (STRICT RULE: no capture)

Method (2026-11-26): the ROM's own display effect routines run in Unicorn (ARM, `tools/deff_unicorn.py`) with the ROM's own
drawing code (blit, fonts, text, image cache); only task switching, sound, lamps and coils are stubbed. At each `dmd_show_pages`
(0x27830) the two DMD pages are copied (`tools/deff_frames.py`) and mixed with the display rule (mask = fg >> 4;
pixel = (bg & mask) | (fg & ~mask), low 4 bits; CPU_BOARD_IO.md 3.2). PinMAME captures are used only as a **control**
(`tools/deff_measure.py`, `tools/deff_compare.py`), never as a source.

What the harness needed (all read from the code):

| Mechanism | Address | Why |
|---|---|---|
| Flash bank window | write 0x02580000 (`flash_bank_select` 0x11e8c), read-back 0x01180000 (bits 0-3 bank, 4-6 revision), window 0x04800000, 8 MB per bank (image table 0x125ae8: bank 0 offsets up to 0x7ff208, bank 1 up to 0x4b2cc; file = bank * 0x800000 + offset) | `bitmap_draw` 0x2b378 selects a bank, draws at window + offset, restores the bank |
| Image cache heap | init 0x2ae54 (heap at 0x01098000, 0x5ff4 bytes); allocator 0x2ae84 | decoding an image allocates a cached copy (0x2aac0, 0x2ac00) |
| Current task block | RAM 0x372c0 +0x30.. effect arguments | effects read their arguments there |
| Random clips | `random_below` 0xc6b4 | 19 effects pick a clip at random; forced per variant for comparison |

Result against the references (`tools/deff_measure.py`, columns 41-127, every reference frame, instruction limit 20M): 7176 of 8477
reference frames reproduced exactly (84.7 %; 1091 before the bank and heap model). Lowest: effects 9, 14, 19, 25, 32, 33, 36, 48, 49,
68, 96, 105, 111, 115, 119, 138 (0 frames): entry screens and the score display need game state; the clip effects 48, 49, 68, 111,
115, 119 need the clip variant forced (`rng`) and the arguments searched; 9, 14, 33, 96 are one-frame effects with arguments.

Open points, each with its reason:

| Point | Reason | To decode |
|---|---|---|
| Effects 22, 45, 146 | code: 22 is `return` (0x1035d3c), 45 is dead code in 1.74 (0x102dd50), 146 is a null table entry | nothing to render |
| Attract (deff 1): pages 7-10 (high scores) | render with the high score table reset by `0x1a9f4(2)` (`attr_page_high_score` 0x1000564) | wire them into the attract loop timing (task sleeps of the parent) |
| Attract pages 2-6 (last score, `attr_page_last_score` 0x1000768) | show the last played game's record (`0x22b38`), which exists only after a game | model a finished game state |
| Attract pages 11-12 (0x2f120, 0x2f260) | code: tournament pages (PRIZE POOL), gated by `tournament_get_type() == 4` (0x2f0e8): never shown in normal play | nothing to render without a tournament |
| Effects 16, 112 and the entry screens 32, 36 | read their arguments (task block +0x30..+0x44, a pointer to a record) | the callers' argument layout, per effect |
| Status panel, columns 0-40 | drawn by `deff_draw_status_panel` 0x10230ec from live game state (score, ball, credits) | game state model, per scenario |
| Clip effects with a random pick | variants 0-11 searched (2026-11-26, columns 41-127): 48 = 66/66 frames with variant 9, 49 = 79/79 with variant 10, 68 = 100/100 with variant 1, 119 = 47/47 with variant 1, 111 = 52/95 with variant 7 (rest not matched), 115 = 0/164 in every variant | 111 (remaining 43 frames) and 115: the clip index is not the only random draw; trace the other `random_below` calls in the effect |
| Effect 9 | error-log summary: `FUN_00005b08` counts the ten NVRAM records at 0x02110084 (type 2 = error); reproduced **exactly** with ten type-2 records (`tools/deff_state.py error_log(10)`) | done |
| Effect 14 | score display with credits: reproduced **exactly** with factory settings (INSTALL FACTORY 0x1278), credits record 0x2111008 = 0, 1 player, ball 1, pages 0/1 (`tools/deff_state.py game()`) | done |
| Effect 138 | 37 of 37 reference frames exact with all arguments 0 (the reference is a forced run with zero arguments) and `eol_combo_jackpot` = 500,000 (value set at every ball start, 0x010031ac) | done |
| Effect 33 | 17 of 17 frames reproduce but 19 pixels: the reference is a forced run with a null record, so `lang_select` (0xa440) dereferences the word at 0x14 (0xe1a00000, an unmapped address): PinMAME returns a value there, Unicorn maps zeros. Needs a valid high-score record to be meaningful (callers 0x0001abfc, record table 0x040e22fc + 0x24 * i) | the unmapped read has no ROM source |
| Effect 19 | **exact: 107 of 107 reference frames** (full 128x32, columns 0-127) with the game state of `tools/deff_state.py game()`, the replay levels set by `FUN_00022c08` (0x22c08, game start: the middle text is `REPLAY AT ...` from `FUN_01023704` 0x1023704) and the status panel counter RAM 0x021117f4 incremented once per tick slept (`counters=(0x21117f4,)`; the blink hides the score block 7 of every 14 counts after 0x3e, 0x1023940). The incrementer is a per-tick counter; its store is not visible in the decompile (event object at 0xb14 points at 0x021117f0) | the exact store of 0x021117f4 |
| Effect 25 (bonus) | **exact: 12 of 12 reference frames**: frames 4-11 from the effect's own run (total screen, `bonus_total_frames` after the child ends), frames 0-3 from the child task `bonus_count_task` (0x1000e7c, run with `fn_addr`) with the player's base bonus `bonus_base` (RAM 0x21115e0) = 50000 (the value the code sets at 0x1001374 callers, e.g. line `bonus_base = 50000` in the ball-start code) and no item values | none |
| Effect 105 (Arcade award slot machine) | **exact: 38 of 38 reference frames** (128x32, columns 41-127) with argument 0 (+0x30, no award code: the reel without icon) and the 7 `random_below` draws (0xc6b4) 4,13,4,13,4,13,3 = 0,1,1,0,3,6,1 (reel pictures 1477, 1478, 1480 from table 0x040d2990; icon codes from 0x040d29a0). Found by coordinate descent (`deff_unicorn.run(rng=callable)`, 4.5 s per run) | the LCG seed that gives these draws is run state, not ROM data; the picks are what the code consumes |
| Effect 96 (ZUSE hit pop-up) | **exact: 28 of 28 reference frames** (128x32, columns 41-127) from the background child task FUN_01032a30 (0x1032a30) run with `fn_addr` (`deff_frames.frames(96, fn_addr=0x01032a30, init=INIT, ram=game())`, 9M instructions); the pop-up children FUN_01032900 (0x1032900) only add the `%luK` text on page 0x12 when the ring 0x3b91c/0x3b91e holds hits, which the reference run does not have | none |
| Display timing | the flip ticks come from `task_sleep` arguments, not yet checked against the references' frame periods | compare per effect |
