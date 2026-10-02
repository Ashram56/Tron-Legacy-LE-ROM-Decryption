# CLU hurry-up ("TERMINATE CLU")

Audience: a developer rebuilding Tron Legacy LE 1.74 in MPF/Godot. Addresses refer to
`tron/code/tron_game_decompiled_v2.c` (function headers `// ==== <addr>`). 1 tick = 16.26 ms.
Reference trace: `traces/clu_hurryup.jsonl` (scenario `traces/clu_hurryup.txt`, factory settings, no pokes).

## 1. Summary
Completing the three C-L-U rollover lanes lights the hurry-up at the VUK ("EJECT: CLU" flashes). Shooting the
VUK starts "TERMINATE CLU": 100,000 points, a 25-second clock and four lit "CLU helmet" shots (left orbit,
left inner loop, right orbit, VUK). Each lit shot scores 250,000 (more on later hurry-ups) and the value grows
75,000 per shot collected; a lit shot unlights when collected. Collecting all four ends it at once; otherwise it
ends when the clock runs out (plus a 2 s grace). A "TERMINATE CLU TOTAL" screen follows.

## 2. Settings (operator adjustments)
None. The 25 s clock, 100,000 start award and all values are constants in code. (Flynn's Arcade "MORE TIME"
award resets the clock to 40, see section 9.)

## 3. State
Per-player arrays are indexed [player-1].

| Name | RAM | Size | Scope | Init / reset | Meaning |
|---|---|---|---|---|---|
| clu_lane_bits | 0x02111724 +4*(p-1) | 4 | per ball, per player | 0 on ball start (event 0x13, `0x0101685c`) and on the player's first ball (event 0x26, `0x010167f4`) | lit C-L-U lanes: bit0 (C)LU, bit1 C(L)U, bit2 CL(U) [0x01016b0c] |
| clu_lane_completions | 0x02111734 +2*(p-1) | 2 | per player (game) | 0 on event 0x26 [0x010167f4] | lane sets completed that counted toward lighting (not those that auto-collected a shot) [0x01016b0c] |
| clu_lights | 0x0211173c +2*(p-1) | 2 | per player (game) | 0 on event 0x26 | times the hurry-up has been lit (n in the "needed" formula) [0x01016b0c] |
| clu_lit | 0x021118a4 +(p-1) | 1 | per player (game) | 0 on event 0x26 [`0x0102e834`] | hurry-up lit at VUK (0 or 1); shared "lit at VUK" table, bit 0x10 [0x0102e8c0 / 0x0102eaa4 / 0x0102ec38] |
| clu_starts | 0x021115f0 +(p-1) | 1 | per player (game) | 0 on event 0x26 [0x01001c2c] | hurry-ups started; sets the base value [0x01001f38] |
| clu_awards_count | 0x021115f4 +(p-1) | 1 | per player (game) | 0 on event 0x26 | CLU shots collected (all hurry-ups); passed to deff 74 [0x01002098] |
| clu_completed_count | 0x021115f8 +(p-1) | 1 | per player (game) | 0 on event 0x26 | hurry-ups where all 4 shots were collected [0x01002098] |
| clu_timer | 0x0003ad00 | 1 | while running | 25 at start; 40 on MORE TIME | seconds left (display) [0x01001f38, task_c0 0x01001e08] |
| clu_shots | 0x0003acfc | 4 | while running | 0x185 at start | lit shots: 0x001 left orbit, 0x004 left inner loop, 0x080 right orbit, 0x100 VUK [table 0x040d22dc] |
| clu_base | 0x0003ad08 | 4 | while running | min(250,000 + 75,000*clu_starts, 1,500,000) at start | base award [0x01001edc] |
| clu_hits | 0x0003ad04 | 1 | while running | 0 at start | shots collected in this hurry-up [0x01002098] |
| clu_total | 0x0003ad0c | 4 | while running | 100,000 (start award) | running total shown at the end [0x01001f38, 0x01002098] |
| clu_award_snd_idx | 0x00036f18 | 1 | while running | 0 at start | sfx variant for deff 73, cycles through call 0x89's 4 samples [deff_073 0x01002a74] |
| clu_timer_bar | 0x0003b57c / 0x0003b580 | 1/1 | while running | | status panel bar = timer*10/max [0x01022ffc, 0x01023010] |

Tasks: 0xc0 = countdown (task_c0), renamed 0xc1 during the end grace; 0x93 = queued intro display; 0x53 = queued total display.
"Running" for shot collection = task 0xc0 or 0xc1 alive [0x01001d54]; for lamps/display = 0xc0 only [0x01001d40].

## 4. How it starts (qualifying / lighting)

### 4.1 C-L-U lanes (sw25 (C)LU, sw14 C(L)U, sw28 CL(U))
Lanes are active only when no wizard/End-of-Line state is on: game flags 0x34, 0x37 (Portal MB) and 0x27 (Daft
Punk / End of Line MB) all clear [0x0101688c]. While inactive, a lane hit gives only its switch score and the lane
lamps are off.

| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| lane switch | lane unlit | lane lit; 10,000 x PF mult | – | (C) 0x99, (L) 0x9a, (U) 0x9b | leff 86 (blink lane lamp 10x2 ticks) [0x01016b0c] |
| lane switch | lane already lit | 1,000 | – | (C) 0x96, (L) 0x97, (U) 0x98 | leff 87 [0x01016b0c] |
| every lane switch | always | switch score 1,090 [handlers 0x0102ad20/54/88 → 0x0102a188] | | | |
| third lane lit (bits = 7) | | lanes cleared; **lane completion** below | deff 80 | 0x9c | leff 88, tube show 21 |

Lane change: one flipper button rotates the lit lanes toward (C) (C wraps to U) [0x01016fc0, from 0x0102a1b4], the
other rotates toward U (U wraps to C) [0x01017074, from 0x0102a294] (which button is which: inferred left/right).
Not while tilted / game not in play (0x37274 & 0x311).

Lane completion [0x01016b0c]:
1. Score `min(50,000 + 5,000 * clu_lane_completions, 250,000)` (completions counted *before* this one)
   [0x01016abc] (verified in emulator: 50,000, 55,000, 60,000, 65,000, 70,000).
2. If CLU hurry-up is running (incl. grace): the first still-lit CLU shot in table order (left orbit, left inner
   loop, right orbit, VUK) is collected as if shot [0x01002268] (verified: 55,000 + 325,000), and nothing else
   happens (completion counter not raised, no deff 80).
3. Otherwise `clu_lane_completions += 1`. If `clu_lane_completions > 4 * clu_lights` the hurry-up is lit:
   `clu_lit` is raised to 1 (max 1) and `clu_lights += 1` (clu_lights is raised even if clu_lit was already 1)
   [0x0102e8c0(0x10,0)]. So: 1st completion lights it, then every 4 further completions (5th, 9th, ...).
4. deff 80 shows "%d MORE / TO LIGHT HURRY-UP" with `(4*clu_lights_before + 1) - clu_lane_completions`, or
   "HURRY-UP / IS LIT" when it was just lit [deff_080 0x01017230].

Flynn's Arcade award "ADV. CLU" runs the same completion silently (no deff 80, no leff 88/sound) [0x01016d14 via 0x0100e058].

### 4.2 Start at the VUK (sw11 VIDEO GAME EJECT)
On a VUK entry `on_vuk` [0x0102eddc] first offers the ball to the CLU shot (if running), then the arcade/portal/
simulation awards, then: if `clu_lit` was non-zero at entry, still non-zero, and the start condition holds,
the hurry-up starts and `clu_lit -= 1` [0x01001cf8].
Start condition [0x01001c98]: no multiball running (flags 0x27, 0x24 Disc, 0x2b, 0x29, 0x37 all clear; `0x0100f8b0`),
the wizard mode (flag 0x34) neither running nor qualifying at this VUK (`0x010263b0`), Portal not qualifying at this VUK
(`0x0102f434`). If blocked, the hurry-up stays lit for a later VUK.

Start [on_clu_hurryup_started 0x01001f38]:
- clears "more time given" flag 0x2c if no other timed mode (CLU, GEM, ZUSE, tasks 0xc6-0xc8) is running;
- clu_timer = 25, clu_hits = 0, clu_shots = 0x185, clu_base = min(250,000 + 75,000*clu_starts, 1,500,000);
- **100,000 x PF mult** (stored as clu_total);
- queues intro deff 71 (task 0x93); clu_starts += 1 (cap 255); SOS item 2 (CLU) level 1 [0x01016188(2,1)];
  audit 0x4e CLU HURRYUP STARTED.

## 5. Behaviour while running

Value formula: `award = min(clu_base + 75,000 * clu_hits, 1,500,000)` [0x01002054], clu_hits counted before this shot.
First hurry-up: 250,000 / 325,000 / 400,000 / 475,000 (verified). Second hurry-up base 325,000 (verified).

| Trigger | Condition | Effect | Display | Sound | Lamp | Next |
|---|---|---|---|---|---|---|
| sw43 left orbit (`0x0102a728`; only if right-orbit timer 0x68 not running) | bit 0x001 lit, task 0xc0/0xc1 alive | award x PF mult; bit cleared; clu_total += award; clu_hits += 1; clu_awards_count += 1; audit 0x4f | deff 73 (award; param = award, shots left) | 0x89 (variant cycles), then speech 0x8b if 1 shot left else 0x8a | leff 79, tube 24 | |
| sw44 left spinner, first spin of a burst (on_l_inner_loop `0x01029ba4`, task 100 not running) | bit 0x004 lit | same | same | same | same | |
| sw46 right orbit (`0x0102a794`; only if left-orbit timer 0x66 not running; also from right-orbit spinner when orbit post state 0x3b4f0 = 1) | bit 0x080 lit | same | | | | |
| sw11 VUK (`on_vuk`) | bit 0x100 lit | same | | | | |
| CLU lane completion | any bit lit | collects first lit bit in order 0x001, 0x004, 0x080, 0x100 | | | | |
| last lit shot collected | clu_shots = 0 | clu_completed_count += 1; SOS item 2 level 2; hurry-up ends now [0x01002234] | deff 74 | | | ended |

Note: the right ramp handlers also call the award with 0x040, but 0x040 is never lit, so the right ramp is not a CLU shot.

Countdown [task_c0 0x01001e08]:
1. wait while intro task 0x93 runs (it waits for its turn among full-screen shows, up to 3750 ticks, then plays deff 71);
2. wait up to 312 ticks while a display show is still busy [0x0100fecc];
3. sleep 156 ticks (2.54 s);
4. loop: accumulate 64 un-paused ticks (16 x 4-tick steps; paused steps are not counted, partial progress kept),
   then clu_timer -= 1 and update the status-panel bar; stop when clu_timer reaches 0.
   One count = 64 ticks = 1041 ms (verified: 1.045 s average over 24 counts).
   Paused when [0x0100ff64]: playfield not validated (OS flag 0x372e8; set by the first valid playfield
   switch after a launch, re-set by ball save), or any show task 0x81-0xa7 running, or Light Cycle video mode
   (0x0102e608), or a pop bumper was hit in the last 156 ticks (task 0x40, started by bumper handlers).
   Verified: start-to-first-count 5.7–8.6 s depending on queued displays.

## 6. How it ends
- **Time out**: at clu_timer = 0 the task sleeps 46 ticks (748 ms), becomes task 0xc1 (grace: shots and lane auto-collect
  still award; lamps/background display already off) for 125 ticks (2033 ms), then the total display [0x01001df4].
  Verified: timer 0 at 102.13 s, deff 74 at 104.92 s.
- **All four shots**: ends immediately with the total display (verified: deff 74 ~4.8 s later because Flynn's Arcade deff 105 was queued first).
- **End of ball** (event 0x1d, drain): ends [0x01001c88 → 0x01002234].
- MORE TIME: see 9.
- Total display: deff 74 via queued task 0x53 (3750-tick queue), only if clu_total ≠ 0 and the game is not in tilt / game-over state (0x37274 & 0x310 = 0) [0x01001d7c].
- Nothing carries over except per-player counters (clu_starts raises the next base; clu_lit can stay lit across balls).

## 7. Media
| When | Display effect | Sound calls | Lamp effect (leff) | Tube show |
|---|---|---|---|---|
| lane lit / relit | – | 0x99/0x9a/0x9b (sfx samples 0x0a5/0x0a6/0x0a7); relit 0x96/0x97/0x98 (0x0dd/0x0de/0x0df) | 86 / 87 (prio 128, blink the lane lamp) | – |
| lane completion | deff 80 (prio 159): "%d MORE / TO LIGHT HURRY-UP" or "HURRY-UP / IS LIT", 3 CLU icons blinking, 21 x 6 ticks | 0x9c (sfx 0x0ed) | 88 (group 50 = C-L-U lamps toggle 24x2 ticks) | 21 |
| start (queued) | deff 71 (prio 177): CLU animation images 0x18d3–0x18df x 3 ticks, then "TERMINATE CLU / SHOOT / CLU HELMET SHOTS" color flash 10 x 2 ticks, then 31 x 2 ticks, hold | 0x87 (sfx 0x0bb) at start, speech 0x88 (0x435 0x436 0x2d2 0x2d6 0x2dc 0x2dd 0x329) | 77 (prio 176; toggles groups 42/43 = CLU shot + lane lamps, spawns flasher pulses coils 28/25/19) | 22 |
| while running (rule) | deff 72 (prio 1, background): "TERMINATE CLU", seconds left ("%d"), "SHOOT CLU HELMET SHOTS", player score | music 0x86 (sample 0x458) | 78 (prio 7, see 8) | 23 |
| shot collected | deff 73 (prio 176): award value over images 0x18e1–0x18ed, then blinking value | 0x89 (sfx 0x062 0x063 0x064 0x022, variant cycles), then speech 0x8b (0x409) if exactly 1 shot left, else 0x8a (0x328 0x437 0x3e4 0x3e5 0x438) | 79 (prio 176) | 24 |
| end | deff 74 (prio 178): image 0xab7, "TERMINATE / CLU / TOTAL: / value" 23 x 6 ticks | 0x8c (sfx 0x0ec), speech 0x8d (0x2de) at frame 12 | 80 (prio 178) | 25 |
| status (instant info) | "TERMINATE CLU" LIT, or "%u CLU LANE COMPLETION(S) TO LIGHT TERMINATE CLU" | | | [0x0101768c] |
Shaker (coil 8) runs at deff 71 and 73 if adj 86 SHAKER ≥ 2 [shaker_run(2,2)].
Package names: event_map rows 71–74 and 80 match these ids.

## 8. Lamps
| Lamp | State |
|---|---|
| 9 (C)LU, 30 C(L)U, 31 CL(U) | solid when the lane is lit, off when not or when lanes are inactive [0x010168d0] |
| 28 EJECT: CLU | flashing while clu_lit > 0 and the start condition holds, else off [0x0102f024] |
| 13 LEFT ORBIT (CLU), 61 L. INNER LOOP (CLU), 36 RIGHT ORBIT (CLU), 28 EJECT: CLU | while counting: leff 78 toggles each still-lit shot lamp every 3 ticks (fast flash); collected shots off [leff_078 0x010028ec, groups 44–47] |
| 24 CENTER CLU | SOS item: flashing after the first CLU start, solid after all four shots were collected once [0x010164a0] |
| 8 LEFT OUTLANE, 32 RIGHT OUTLANE | lane routine also keeps the special-lit outlane lamps in step with the special count (not part of CLU) |

## 9. Interactions
- VUK order (0x0102eddc): CLU award (bit 0x100) → Flynn's Arcade award → Portal → others → CLU start. A VUK entry
  can both award the arcade mystery and start CLU (verified: deff 105 first, then deff 71).
- Multiballs block the start (not the running mode); lanes are inactive under flags 0x34/0x37/0x27.
- Flynn's Arcade "MORE TIME" (0x0100f98c, only offered while CLU/GEM/ZUSE etc. runs and flag 0x2c clear): CLU clock
  set to 40 and the countdown task restarted (re-waits the 156-tick lead-in) [0x010021c8]; sets flag 0x2c.
- Flynn's Arcade "ADV. CLU": one silent lane completion (see 4.1).
- SOS items (Sea of Simulation): item 2 level 1 on start, level 2 when all four shots collected [0x01016188].
- Zuse fast scoring: every CLU lane, orbit and VUK switch also scores the fast-scoring value when that runs.
- Status-panel timer bar 0x3b57c is shared display code with GEM (0x3b584) and ZUSE (0x3b58c).
- `0x0101283c` (ends CLU, GEM and ZUSE together) has no caller in v1.74.

## 10. Reference scenario
`traces/clu_hurryup.txt` → `traces/clu_hurryup.jsonl` (watch file uses the RAM names in `work/ram/clu_hurryup.tsv`). Key events:
- 16.94/18.11 s lanes: 10,000 each; 19.28 s third lane: 10,000 + 50,000, deff 80, clu_lit 0→1.
- 22.45 s VUK: 100,000, clu_timer 25, base 250,000; deff 105 (arcade) then deff 71 at 26.02 s, deff 72 + music 0x86.
- 31.76 s first count (24); counts every ~1.045 s.
- 34.61 s left orbit: 250,000, deff 73. 39.16 s lane set: 55,000 + 325,000 (inner loop auto-collected).
- 42.31 s right orbit 400,000, speech 0x8b (one left). 46.25 s VUK 475,000 → all done, deff 74 at 51.05 s.
- 55.2–67.9 s four lane sets: 55k, 60k, 65k, 70k; the 4th of them (5th overall) relights (clu_lights 2).
- 70.52 s VUK: second hurry-up, base 325,000; counts to 0 at 102.13 s; deff 74 at 104.92 s.

## 11. Open questions
- Which flipper button is handler 0x0102a1b4 vs 0x0102a294 (switch ids 0x89/0x8b are cabinet switches) was not traced; the rotation directions are read from code.
- 0x372e8 is named `is_tilted` in the decompile; behaviour (verified) shows it is the OS "playfield validated" flag (switch-validation object, set by `FUN_00010c70` when enough playfield switches are seen; forced on by ball save `0x0001ea60` and tilt `0x0002444c`).
