# Attract mode and tournament displays (short) — Stern Tron Legacy LE 1.74

Audience: a developer rebuilding the game in MPF/Godot. Sources are function addresses in
`tron/code/tron_game_decompiled_v2.c`. Emulator check: `traces/attract_and_service.jsonl` (power-up, 75 s of
attract, then flipper buttons), plus the end of `traces/game_flow.jsonl` (game over → attract).
Tournament and Bump 'n Win are covered only briefly, and the operator service menu is not covered.

## 1. Summary
With no game running (game state 0x37274 = 0x10) the display cycles through pages: GAME OVER (first pass only),
credits, last scores, the high-score table, a Tron logo scroll, an animation, the Stern web address and the clock.
Each text page stays up for 125 ticks (about 2 s). The lamps run one long attract light show (leff 1). The flipper
buttons step through the pages. When a game ends, a music/lamp show plays once (music 0x01d, leff 133).
[0x000015d4] [0x01034364] [0x01017dc4] [0x0100f29c] (verified in emulator: traces/attract_and_service.jsonl)

## 2. Settings (operator adjustments)
No attract-specific adjustments were traced. Tournament / Bump 'n Win pages only appear when those features are
enabled in the operator menus, and the clock page depends on the clock setting. [0x0002ed24] [0x0002f120] [0x00032d04] (inferred)

## 3. State
| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| attr_page_table | 0x00036e10 (pairs of u32 {condition fn, page fn}) | machine | built at boot (inferred) | The attract page list. The condition is called with the pass number; a page is skipped when it returns 0 [0x01034364] |
| attr_gameover_countdown | 0x0003afec (s32) | machine | random 4-6 (rand(3)+4) at power-up and after each speech | Game overs left until the "game over" speech 0x01e [0x0100f29c] |
| (game state) | 0x37274 = 0x10 | machine | set at game over | Attract running [0x00020a64] (verified in emulator: traces/game_flow.jsonl t 130.10, 152 → 16) |

## 4. How it starts
- At power-up and at the end of every game (after match): event 0x08 is posted; if not vetoed → **deff 1**
  (attract pages) and **leff 1** (attract lamp show) start. [0x000015d4]
  (verified in emulator: traces/attract_and_service.jsonl t 0.99 deff 5 → deff 1 + leff 1; traces/game_flow.jsonl t 130.10)
- At game over also task 0x45 starts: [0x0100f29c]
  - speech 0x01e when no game can be started on the current credits, or on every 4th-6th game over (random);
  - then music 0x01d with leff 133 for 625 ticks (10.2 s); then the music fades out.
  (verified in emulator: traces/game_flow.jsonl t 130.12 snd 0x01d + leff 133; no speech that game)

## 5. Behaviour while running

### 5.1 Page order (deff 1) [0x01034364]
Each page is a child task. A page ends when its task returns (125 frames for text pages) or a flipper is pressed.
Measured: one page every 2.016 s in attract (126 ticks at 16.0 ms). (verified in emulator: traces/attract_and_service.jsonl)

| # | Page fn | Shows | Condition / length |
|---|---|---|---|
| 1 | 0x010008a8 | "GAME OVER" (msg 0x1c2) | first pass only (condition 0x01000898: pass == 1); 125 frames |
| 2 | 0x01000128 | credits text ("CREDITS n" / "FREE PLAY", from 0x00004ff4) | 125 frames |
| 3 | 0x01000878 / 0880 / 0888 / 0890 | last game score of player 1 / 2 / 3 / 4 (0x01000768) | only for players in the last game (inferred); 125 frames each |
| 4 | 0x0100075c, 0750, 0744, 0738, 072c | high-score table entries 0-4 (0x01000564 with entry 0..4): entry 0 = GRAND CHAMPION, 1-4 = HIGH SCORE #1-#4; title / initials / score | entry exists; 125 frames each |
| 5 | 0x010001f0 | Tron logo bitmap 0x59f scrolled vertically, 2 ticks per pixel line | ≈ 3.76 s |
| 6 | 0x0100026c | animation bitmaps 0x5a0-0x5c4 (37 frames, 5 ticks each), then hold 62 ticks | ≈ 3.98 s |
| 7 | 0x01000468 | "LEARN MORE ABOUT / STERN PINBALL AT / WWW.STERNPINBALL.COM" | 125 frames |
| 8 | 0x01000308 | date and time text (OS clock); "CLOCK NOT SET" variant at 0x00032d04 | clock string available; 125 frames |
| — | OS pages | tournament: "PRIZE POOL:", "TOURNAMENT LEADERS:", place list; Bump 'n Win: "BUMP 'N' WIN SCORE", "TOP SCORE WINS" | only when tournament / Bump 'n Win is enabled (inferred) [0x0002f120] [0x000304a4] [0x0002ed24] [0x0002f4e8] |
Then the list wraps to page 2 (GAME OVER is not shown again).
- Measured single-player cycle after the first pass: credits, P1 score, 5 high-score pages, logo, animation, URL,
  clock = 25.9 s (t 30.99 → 56.87). (verified in emulator: traces/attract_and_service.jsonl)

### 5.2 Buttons
| Trigger | Condition | Effect |
|---|---|---|
| Right flipper button | attract | next page at once [0x01034364] (verified in emulator: traces/attract_and_service.jsonl t 83.02 → 83.05) |
| Left flipper button | attract | previous page at once [0x01034364] (verified in emulator: traces/attract_and_service.jsonl t 84.20 → 84.24, back to credits) |
| Start button | credits / free play | starts a game (see game_flow.md §4.1) [0x00020d1c] |

### 5.3 Attract lamp show (leff 1) [0x01017dc4] [0x010178fc] [0x01017d0c]
Runs forever, in three phases. The lamps in 0x3908c, 0x36f64 and 0x36f65 (OS-owned lamps such as the start button) are left out.
1. **Chase**, 30 s (30 × 62 ticks): 15 lamp groups from table 0x040d2f00 stepped every 5 ticks (task 0x010178fc).
2. **Group flash**, 3 rounds × 8 groups (table 0x040d2f38, with tube show 0x040d2f3a for each group): each group
   flashes 16 times at 3 ticks on, 3 ticks off (2,304 ticks ≈ 37 s). (task 0x01017d0c)
3. **All-lamp flash**: on/off with periods slowing from 24 to 6 ticks, then 10 × 4 ticks, then 5 × 12 ticks
   (500 ticks ≈ 8 s).
- Measured: phase 2 started 29.9 s after power-up, and phase 1 restarted 44.95 s later (2,804 ticks at 16.0 ms).
  (verified in emulator: traces/attract_and_service.jsonl t 1.01, 30.88, 75.83)
- During phase 2, sound call 0x001 is posted about every 1.54 s (the end of each group's tube show; sound 0x001
  looks like a stop/reset call, inferred). (verified in emulator: traces/attract_and_service.jsonl)

## 6. How it ends
- Pressing START with credits (or on free play) starts a game: deff 1 and leff 1 are replaced by the game start
  (state 0x10 cleared). [0x00020afc]
- The game-over music task ends by itself after 625 ticks plus the fade. [0x0100f29c]

## 7. Media
| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| Power-up | deff 5 (boot), then deff 1 | 0x001 ×3 | leff 1 | — |
| Attract | deff 1 pages (§5.1) | 0x001 during leff 1 phase 2 | leff 1 | per-group shows from 0x040d2f3a |
| Game over | deff 1 | speech 0x01e (sample 0x2f8, sometimes), music 0x01d (sample 0x459) | leff 133 (10.2 s) | — |
| Tournament game start | deff 16 "n CREDITS FOR A / TOURNAMENT GAME" | — | — | — |
| Bump 'n Win start | deff 18 "BUMP 'N' WIN" / "BUMP 'N' WIN SCORE" + target score | — | — | — |
| Bump 'n Win reached in game | deff 29 "BUMP 'N' WIN" (task 0x00024938, leff 18) | — | leff 18 | — |
| Ticket award | deff 30 "n TICKET(S)" (task 0x00021cd8) | 0x11c | — | — |
| Tournament result | deff 34 "SORRY, / YOU DID NOT QUALIFY / PLEASE TRY AGAIN!"; deff 35 "PLAYER n / YOU QUALIFIED!" (bitmaps 0xd2/0xd3); deff 36 "FIRST…FIFTH PLACE"; deff 37 winner bitmaps 0xd0/0xd1 (from 0x00024c34, 0x0002511c) | — | — | — |
[table 0x040e1350] [0x01035e48] [0x01036030] [0x010126d4] [0x01012994] [0x01036a5c] [0x01036244] [0x0103649c] [0x010369bc]
- Tournament and Bump 'n Win displays were read from code only; they were not traced. (inferred)

## 8. Lamps
All playfield lamps belong to leff 1 in attract except the OS-owned lamps (start button and others in 0x3908c,
0x36f64, 0x36f65). [0x01017dc4]

## 9. Interactions
- Attract runs only while state bit 0x10 is set; the game start clears it. [0x00020afc]
- Last-score pages read the per-player scores 0x021109e4 of the last game. [0x01000768] (inferred)
- High-score pages read the high-score table that the game-over entry (0x0001ad4c) writes. [0x01000564]

## 10. Reference scenario
`traces/attract_and_service.txt` → `traces/attract_and_service.jsonl`: power-up, wait 75 s, right flipper, left flipper.
- t 0.99 deff 5 → deff 1 + leff 1; t 3.09 GAME OVER page; then a page every 2.016 s (credits 5.11, P1 score 7.12,
  high scores 9.14-17.21, logo 19.22, animation 22.98, URL 26.96, clock 28.97, credits 30.99 …).
- t 30.88 leff 1 phase 2; t 75.83 phase 1 again.
- t 83.02 right flipper → next page at 83.05; t 84.20 left flipper → previous page at 84.24.
Game over → attract: traces/game_flow.jsonl t 122.26 match deff 38 → t 130.10 deff 1, leff 1, music 0x01d, leff 133.

## 11. Open questions
- Where the page table at 0x36e10 is filled was not traced; the order above is taken from the run.
- The tournament / Bump 'n Win pages and deffs 16-37 were not traced (they need the tournament settings).
- The exact meaning of sound call 0x001 (posted by the attract tube shows) was not checked.
