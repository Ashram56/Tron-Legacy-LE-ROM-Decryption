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
| Effects 9, 14, 25, 33, 96, 105, 138 | argument 0-5 searched: 0 exact frames, so the missing input is game state, not the argument | model the state they read (score, item counts, combo count) |
| Display timing | the flip ticks come from `task_sleep` arguments, not yet checked against the references' frame periods | compare per effect |
