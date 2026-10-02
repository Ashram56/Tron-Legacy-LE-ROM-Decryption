# End-of-ball bonus — Stern Tron Legacy LE 1.74

Audience: a developer rebuilding the game in MPF/Godot. Sources are function addresses in
`tron/code/tron_game_decompiled_v2.c`. Emulator checks: `traces/bonus.jsonl` (shared `tron_ref`, factory
settings, item/SoS/Portal counts set by poke) and `traces/bonus_skip.jsonl` (both flippers held during the count).
Where the bonus fits in the end-of-ball order is in `game_flow.md` §6.1.

## 1. Summary
When a ball drains (and the game is not tilted) the bonus is counted on the display. It is a fixed
50,000 base, plus 50,000 for each of the nine items (FLYNN … TRON) that has been lit, or 250,000 if it has
been collected, plus 450,000 per Sea of Simulation played and 2,250,000 per Portal multiball played. The sum
is multiplied by the bonus multiplier (1X-25X), which goes up by 1 for each right inner loop shot (sw39) and
goes back to 1X every ball. The item, Sea of Simulation and Portal counts are kept for the whole game, so the
bonus grows from ball to ball. Holding both flipper buttons skips the count to the total screen.
[0x01000cf8] [0x01000e7c] [0x01001374] (verified in emulator: traces/bonus.jsonl)

## 2. Settings (operator adjustments)
No adjustment changes the bonus values or the multiplier limit. All values are constants in the code or in
the item table. [table 0x040d2dd0] [0x01000cb0] [0x01000cd4] [0x01000b28]

## 3. State
| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| bonus_x | 0x021115d4 + (player-1) (u8) | per ball | 1 at every ball start (event 0x11 handler entry 0x01000a84 loads flag id 0x2d and falls into 0x01000a88) unless game flag 0x2d is set, in which case the value is kept and flag 0x2d is cleared | Bonus multiplier, 1..25. +1 per sw39 shot, capped at 25 (0x19) [0x01000a88] [0x01000b28] (verified in emulator: traces/bonus.jsonl, 1→4 with 3 hits, back to 1 at ball 2) |
| bonus_base | 0x021115e0 + 4*(player-1) (u32) | per ball | 50,000 at every ball start | Base bonus. No code was found that adds to it in 1.74, so it is always 50,000 [0x01000a88] |
| bonus_unknown_word | 0x021115d8 + 2*(player-1) (u16) | per ball | 0 at ball start, together with bonus_x (only when flag 0x2d is clear) | Purpose not found; nothing in the bonus reads it (inferred) [0x01000a88] |
| bonus_item_state[i] | 0x02111694 + 0x10*i + 4*(player-1) (u32), i = 0..8 | per player (whole game) | 0 at the player's first ball (event 0x26, 0x010160b8) | byte 0 = times the item was lit, byte 1 = times it was collected. Written by find_flynn_and_items (0x01016188). The bonus only tests whether each byte is non-zero [0x01015f7c] |
| bonus_sos_count | 0x02111800 + (player-1) (u8) | per player (whole game) | 0 at the player's first ball (event 0x26) | Sea of Simulation starts; read by 0x01026390 [0x01000cb0] |
| bonus_portal_count | 0x021118b8 + (player-1) (u8) | per player (whole game) | 0 at the player's first ball (event 0x26, 0x0102f2e8) | Portal multiball starts; read by 0x0102f3e8 [0x01000cd4] (verified in emulator: traces/bonus.jsonl, still 1 on ball 2) |
| bonus_insert_mask | 0x0003aca4 (u32) | while bonus runs | 0 at deff 25 start; 0x1ff when it ends | One bit per item (bit i = item i) already counted. leff 20 uses it to show the centre item inserts one by one (inferred) [0x01001374] [0x01000e28] |
| (state bit) | 0x37274 bit 0x01 | while bonus runs | — | Game state "bonus running" (state value 5 during the count) [0x00020764] (verified in emulator: traces/bonus.jsonl) |

## 4. How it starts
1. The last ball in play drains. The end-of-ball sequence runs (game_flow.md §6.1): modes stop (event 0x1d),
   the game waits up to 169 ticks (2.75 s) for mode TOTAL displays (flag-0x2000 tasks), and the playfield
   multiplier is set to 1. [0x00020764]
2. If the game is tilted (state bit 0x200), there is no bonus at all: no display and no points. [0x00020764]
   (verified in emulator: traces/game_flow_tilt.jsonl, drain at t 21.09 → ball 2 at t 21.62 with no deff 25)
3. Otherwise event 0x14 is posted (it can veto; no Tron handler vetoes it), state |= 0x01, and **deff 25** starts
   (priority 242). The end-of-ball code waits for it to finish. [0x00020764] [0x01001374]
- Measured: drain → deff 25 = 0.535 s when no mode total is pending (trough settle). With a pending mode
  total (GEM hurry-up total deff 79) the bonus started 2.42 s after deff 79. (verified in emulator:
  traces/bonus.jsonl t 23.46 drain → 24.00 deff 79 → 26.42 deff 25)

## 5. Behaviour while running

### 5.1 Lines, in display order [0x01000e7c]
Each line is a full screen shown for 21 frames (deff_status_frames(0x15)). Measured at 0.341 s a line
(≈ 21 ticks). (verified in emulator: traces/bonus.jsonl, lines at t 26.418, 26.760, 27.101, 27.442, …)

| # | Line | Shown when | Value | Count variable | Screen text | Lamp effect | Tube show |
|---|---|---|---|---|---|---|---|
| 0 | Base | always | bonus_base = 50,000 | 0x021115e0 | "BONUS" (msg 0x306) / value | leff 20 (started by deff 25, runs the whole count) | — |
| 1-9 | Item i = FLYNN, GEM, CLU, ZUSE, QUORRA, DISC, LIGHT CYCLE, RECOGNIZER, TRON | the item's value is not 0 | 250,000 if collected at least once (byte 1 ≠ 0); else 50,000 if lit at least once (byte 0 ≠ 0); else 0 and the line is **skipped**. The count is not multiplied: lit 3 times is still 50,000 | 0x02111694 + 0x10*i | item name (msg 1491-1499) / "+%,02lu" item value / running total | leff 21 + i (21-29), stopped after the line | 93 + i (93-101) |
| 10 | Sea of Simulation | count > 0 | 450,000 × count | 0x02111800 | "SEA OF SIMULATION" (msg 0x610) / "+value" / running total | leff 30 | 102 |
| 11 | Portal | count > 0 | 2,250,000 × count | 0x021118b8 | "PORTAL" (msg 0x612) / "+value" / running total | leff 31 | 103 |
| 12.. | Multiplier steps n = 2 .. bonus_x | bonus_x > 1 | running total × n | 0x021115d4 | "%dX" (msg 0x614) / sum × n | leff 32 each step | 104 each step (step number written to the show) |
| last | Total | always | bonus_total | — | "TOTAL BONUS" (msg 0x616) / total, 43 frames, then hold 10 frames | — | 105 |
[table 0x040d2dd0] [0x01015f7c] [0x01000cb0] [0x01000cd4] [0x01001374] [0x01000d78]
- At the start of every item line the item's bit is OR'ed into bonus_insert_mask, even when the line is
  skipped. [0x01000e7c] [0x01015f24]
- The item values are table constants (offset +0x0c lit = 50,000, +0x10 collected = 250,000), the same for
  all nine items. [table 0x040d2dd0]

### 5.2 Formula [0x01000cf8]
```
sum = BONUS_BASE (50,000)
    + Σ over 9 items: (COLLECTED_i > 0 ? 250,000 : LIT_i > 0 ? 50,000 : 0)
    + 450,000 × SOS_COUNT
    + 2,250,000 × PORTAL_COUNT
bonus_total = bonus_x × sum
```
- The total is added to the current player's score by event 0x16 (provider 0x01000d60 writes the total) and
  score_add_player 0x00023428, with the playfield multiplier fixed at 1. So it is **not** multiplied by
  anything else, and it **counts toward replay** (a replay knocker can come right after the bonus).
  [0x01000d60] [0x00020764] (verified in emulator: traces/bonus_skip.jsonl, +32,500,000 → replay deff 28 at t 28.51)
- The value added is always computed again by bonus_total, so skipping the display does not change it.
  [0x01001374] [0x01000cf8]
- Worked examples (verified in emulator: traces/bonus.jsonl):
  - Ball 1: bonus_x 4; FLYNN lit, GEM collected, TRON lit+collected, SoS 2, Portal 1 →
    (50,000 + 50,000 + 250,000 + 250,000 + 900,000 + 2,250,000) × 4 = **15,000,000** (t 30.42).
  - Ball 2: same counts (they persist), bonus_x back to 1 → **3,750,000** (t 50.33).
  - traces/bonus_skip.jsonl: FLYNN lit, SoS 2, Portal 1, bonus_x 10 → 3,250,000 × 10 = **32,500,000**.

### 5.3 Raising the multiplier
| Trigger | Condition | Effect | Display | Sound | Lamp | Next |
|---|---|---|---|---|---|---|
| sw39 right inner loop (shot handler 0x0102ae44) | any time in a game, also during multiballs | bonus_x += 1, max 25 (no award past 25) | none of its own | none of its own | none found | — |
[0x0102ae44] [0x01000b28] (verified in emulator: traces/bonus.jsonl, 3 hits → 4X shown as 2X, 3X, 4X steps)
- This is the only caller of the bonus_x increment in 1.74. [0x01000b28]

### 5.4 Skipping
| Trigger | Condition | Effect |
|---|---|---|
| Hold both flipper buttons | during deff 25, before the total screen | Count stops at once, goes to the "TOTAL BONUS" screen (sound 0x0ba, tube 105) |
- deff 25 polls the flipper inputs every tick. It breaks out of its wait when both are down or when the counting
  task has finished, with a hard limit of 0x753 ticks = 1,875 ticks ≈ 30.5 s. [0x01001374]
- Verified: bonus_x 10 (9 steps expected); both flippers held at t 27.566, one step after the first 2X step →
  TOTAL BONUS (sound 0x0ba) at t 27.600, score added at t 28.495. (verified in emulator: traces/bonus_skip.jsonl)
- One flipper alone does not skip. [0x01001374]

## 6. How it ends
- After the last line: sound 0x0ba, tube show 105, "TOTAL BONUS" + total for 43 frames, then hold 10 frames
  (flag 0x20). Measured TOTAL screen → score = 0.907 s. [0x01001374] [0x01000d78] (verified in emulator: traces/bonus.jsonl t 29.510 → 30.417)
- On exit (normal or skipped) the exit handler: bonus_insert_mask = 0x1ff, stops item leffs/tube shows
  (0x01016048, 0x01016080), stops leff 30/31/32 and tube shows 102/103, and kills any running tube show 104 task.
  [0x01000e28]
- Then the end-of-ball code adds the total, posts event 0x15, clears state bit 0x01 and goes on to the next
  ball. [0x00020764]
- Timing per bonus: 0.341 s × (1 + number of non-zero lines + (bonus_x − 1)) + ≈0.9 s for the total. Example:
  1 base + 3 items + SoS + Portal + 3 steps = 9 screens × 0.341 + 0.91 ≈ 3.98 s (measured 4.00 s, t 26.418 → 30.417).
  (verified in emulator: traces/bonus.jsonl)
- Carry-over: bonus_x and bonus_base reset at the next ball start; item states, SoS and Portal counts are kept
  for the rest of the game for that player. [0x01000a88] [0x010160b8]

## 7. Media
| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| Bonus start | deff 25 (prio 242), "BONUS" + 50,000 | 0x0b6 music (sample 0x455) | leff 20 (whole count) | — |
| Each item line | item name / "+50,000" or "+250,000" / running total | — | leff 21-29 (FLYNN…TRON) | 93-101 |
| Sea of Simulation line | "SEA OF SIMULATION" / "+value" / running total | — | leff 30 | 102 |
| Portal line | "PORTAL" / "+value" / running total | — | leff 31 | 103 |
| Each multiplier step | "2X", "3X", … / running total × n | 0x0b9 sfx (sample 0x0ed) | leff 32 | 104 |
| Total | "TOTAL BONUS" / total | 0x0ba sfx (sample 0x06f) | — | 105 |
[0x01000e7c] [0x01001374] (verified in emulator: traces/bonus.jsonl, all ids above seen in order)
- All screens are drawn with the standard fonts (font 0xf for the base/total value, font 2 for line names,
  font 0xc for "nX" and "TOTAL BONUS"). No bitmap animation. [0x01000e7c] [0x01000d78]

## 8. Lamps
| Lamp | Name | During bonus |
|---|---|---|
| 27, 25, 24, 23, 22, 21, 20, 19, 18 | CENTER FLYNN, GEM, CLU, ZUSE, QUORRA, DISC, LIGHT CYCLE, RECOGNIZER, TRON | Revealed one by one as the line count reaches each item (bonus_insert_mask + leff 20); leff 21-29 flash the matching insert during its line (inferred from leff numbering = item order) [table 0x040d2dd0 +6] [0x01001374] |
- Outside the bonus these inserts show the item ladder (see find_flynn_and_items.md).

## 9. Interactions
- **Tilt**: no bonus. A tilt does not clear the item/SoS/Portal counts, so they still count on later balls.
  [0x00020764] (verified in emulator: traces/game_flow_tilt.jsonl)
- **Ball save**: a saved drain is not an end of ball, so no bonus. (verified in emulator: traces/game_flow.jsonl)
- **Extra ball / shoot again**: the bonus is counted first, then the same player shoots again with bonus_x
  reset to 1 (the ball start runs the per-ball init again). [0x00020764] [0x000214d0]
- **Mode totals**: the bonus waits up to 169 ticks for mode TOTAL displays (e.g. GEM deff 79, SoS deff 126).
  [0x00020764] (verified in emulator: traces/bonus.jsonl)
- **Replay**: the bonus is a normal score add, so it can earn the replay (deff 28 after the bonus).
  (verified in emulator: traces/bonus_skip.jsonl)
- **Multiplayer**: every variable is indexed by the current player; each player has their own multiplier,
  ladders and counts. [0x01000cf8]
- Written by other features: item states (find_flynn_and_items, sea_of_simulation completes items),
  SoS count (sea_of_simulation), Portal count (portal_multiball), bonus_x (sw39 shot handler, shared with combos
  and many modes).
- Game flag 0x2d "hold bonus X" is tested at ball start, but nothing sets it in 1.74, so the multiplier
  always resets. [0x01000a88]

## 10. Reference scenario
`traces/bonus.txt` → `traces/bonus.jsonl` (watch list: work/ram/bonus.tsv addresses). Pokes set late-game
state (item ladders, SoS and Portal counts) because reaching them by play takes too long.
- t 13.25 valid; sw39 ×3 → bonus_x 4.
- t 16.45 poke FLYNN lit, GEM collected, TRON lit+collected, SoS 2, Portal 1.
- t 23.46 drain → t 24.00 GEM total deff 79 → t 26.42 deff 25 + snd 0x0b6 + leff 20 → item lines leff 21/22/29
  → leff 30 → leff 31 → 3 × (snd 0x0b9, leff 32) → t 29.51 snd 0x0ba → t 30.42 +15,000,000, ball 2, bonus_x 1.
- t 45.76 drain → t 47.38 deff 25 → 5 lines, no steps → t 49.44 total → t 50.33 +3,750,000.
`traces/bonus_skip.txt` → `traces/bonus_skip.jsonl`: bonus_x poked to 10; both flippers held 2 s after the
drain → total at once; +32,500,000; replay deff 28 follows.

## 11. Open questions
- Game flag 0x2d (keep bonus X) has no setter in 1.74. It may be a leftover or set by an OS feature not found.
- The role of 0x021115d8 (u16 per player, cleared with bonus_x) is unknown.
- Whether leff 20 dims or blinks the not-yet-counted inserts was read from the mask logic, not seen on lamps.
