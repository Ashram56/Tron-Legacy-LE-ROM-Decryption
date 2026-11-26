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

Result against the references (columns 41-127, first 20 frames of each reference): 58 effects exact on every checked frame,
123 of about 140 with at least one exact frame (baseline before the bank and heap model: 41 and 63).

Open points, each with its reason:

| Point | Reason | To decode |
|---|---|---|
| Effects 22, 45, 146 | code: 22 is `return` (0x1035d3c), 45 is dead code in 1.74 (0x102dd50), 146 is a null table entry | nothing to render |
| Attract (deff 1): pages 7-10 (high scores) | render with the high score table reset by `0x1a9f4(2)` (`attr_page_high_score` 0x1000564) | wire them into the attract loop timing (task sleeps of the parent) |
| Attract pages 2-6 (last score, `attr_page_last_score` 0x1000768) | show the last played game's record (`0x22b38`), which exists only after a game | model a finished game state |
| Attract pages 11-12 (0x2f120, 0x2f260) | code: tournament pages (PRIZE POOL), gated by `tournament_get_type() == 4` (0x2f0e8): never shown in normal play | nothing to render without a tournament |
| Effects 16, 112 and the entry screens 32, 36 | read their arguments (task block +0x30..+0x44, a pointer to a record) | the callers' argument layout, per effect |
| Status panel, columns 0-40 | drawn by `deff_draw_status_panel` 0x10230ec from live game state (score, ball, credits) | game state model, per scenario |
| Clip effects with a random pick | the reference holds one pick | compare every variant (0-11) |
| Display timing | the flip ticks come from `task_sleep` arguments, not yet checked against the references' frame periods | compare per effect |
