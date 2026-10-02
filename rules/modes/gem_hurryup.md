# GEM hurry-up ("FOLLOW GEM")

Audience: a developer rebuilding Tron Legacy LE 1.74 in MPF/Godot. Addresses refer to
`tron/code/tron_game_decompiled_v2.c` (function headers `// ==== <addr>`). 1 tick = 16.26 ms.
Reference trace: `traces/gem_hurryup.jsonl` (scenario `traces/gem_hurryup.txt`, factory settings, no pokes).

## 1. Summary
Shooting the right inner loop (sw39) builds toward "FOLLOW GEM". Each loop scores 250,000. The 3rd loop starts
the hurry-up (5 loops on later starts). The start scores another 250,000 and runs a 25-second clock.
During the hurry-up every right inner loop collects a growing award: 750,000, then 1,000,000, and so on, up to
2,500,000. There is no limit on the number of collects. Each spinner spin adds one second (minimum 5, maximum 40)
and restarts the clock's lead-in. The mode ends when time runs out (plus a 2.8 s grace) or at end of ball.
A "FOLLOW GEM TOTAL" screen follows.

## 2. Settings (operator adjustments)
None. The 25 s clock, the loop counts and all values are constants in code [0x01013c5c, 0x01013a08].
Flynn's Arcade "MORE TIME" sets the clock to 40 (see section 9).

## 3. State
Per-player arrays are indexed [player-1].

| Name | RAM | Size | Scope | Init / reset | Meaning |
|---|---|---|---|---|---|
| gem_starts | 0x02111678 +(p-1) | 1 | per player (game) | 0 on event 0x26 [0x010138f8] | hurry-ups started (cap 255). 0 means 3 loops are needed, otherwise 5 [0x010139b8] |
| gem_awards | 0x0211167c +(p-1) | 1 | per player (game) | 0 on event 0x26 and at every start [0x01013c5c] | loops collected in the current hurry-up (cap 255). Sets the award; passed to deff 78/79 [0x01013da8] |
| gem_progress | 0x02111680 +(p-1) | 1 | per player (game) | 0 on event 0x26 and at start | qualifying loops made toward the next start (cap 255) [0x01013a08] |
| gem_snd_idx | 0x02111684 +4*(p-1) | 4 | per player (game) | 0 on event 0x26 and at start | sfx variant for deff 75 (cycles through call 0x8e's 3 samples) [deff_075 0x010140f8] |
| gem_shots | 0x0003b128 | 4 | while running | 8 at start | award shot mask. Only 8 (right inner loop) is used [0x01013c5c, 0x0102aeac] |
| gem_timer | 0x0003b12c | 1 | while running | 25 at start; 40 on MORE TIME | seconds left (display) [task_c2 0x01013b88] |
| gem_total | 0x0003b130 | 4 | while running | 250,000 (the start award as returned by score_add) | running total shown at the end [0x01013c5c, 0x01013da8] |
| gem_award_snd_idx | 0x00036fec | 1 | while running | 0 at start | sfx variant for deff 78 (call 0x92, 4 samples) [deff_078 0x0101476c] |
| gem_timer_bar | 0x0003b584 / 0x0003b588 | 1/1 | while running | | status panel bar (cur/max), set by 0x0102304c / 0x01023060 [0x01013c5c] |

Tasks: 0xc2 is the countdown (task_c2). It is renamed 0xc3 during the end grace. 0x96 is the queued intro
display. 0x54 is the queued total display.
For collecting and spinner time, "running" means task 0xc2 or 0xc3 is alive [0x01013b70]. For the background
display, music, lamp show and tube show it means 0xc2 only [0x01013b5c].

## 4. How it starts (qualifying)

### 4.1 Right inner loop (sw39)
The sw39 handler [0x0102ae40] runs in this order: other features (the combo/ramp hooks, `zuse_target_hit(4)`), then
`on_gem_hurryup_awards(8)`, then `gem_qualify(0)` [0x01013a08], then the 1,190 switch score [0x0102a188].

Qualifying is enabled [0x01013980] only when all of these hold:
- the hurry-up is not running (tasks 0xc2/0xc3);
- the wizard flag 0x34 is clear [0x010263f0];
- the Portal multiball flag 0x37 is clear [0x0102f680].

Other multiballs do **not** block qualifying or starting (inferred from code: no multiball test in 0x01013980).

| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| sw39 | qualifying enabled, gem_progress+1 < needed | gem_progress += 1; **250,000** | deff 75 "%d / MORE TO START / FOLLOW GEM" (needed - progress) | 0x8e (variant cycles) | leff 81, tube 16 [0x01013a08, deff_075] |
| sw39 | qualifying enabled, gem_progress+1 ≥ needed | hurry-up starts (4.2); then **250,000** for the loop | deff 76 (intro) | | |
| sw39 | not enabled | switch score only (1,190) | | | |

needed = 3 if gem_starts = 0, else 5 [0x010139b8]. The 250,000 is added flat with `score_add`, not through the
switch-score multiplier path [0x01013aac].
The verified counts are:
- 250,000 at 18.45 s and at 21.12 s (gem_progress 1, 2; deff 75);
- 3rd loop at 23.79 s: start (250,000) + loop (250,000) + 1,190 = 501,190.
(verified in emulator: traces/gem_hurryup.jsonl)

Flynn's Arcade "ADV. GEM" calls `gem_qualify(1)` [0x0100e008]. It works like one loop: it scores 250,000 and can
start the mode, but it shows no deff 75.

### 4.2 Start [on_gem_hurryup_started 0x01013c5c]
The start only happens if qualifying is still enabled. In order:
1. Clear flag 0x2c ("more time given") if no other timed mode is running [0x0100f930].
2. gem_progress = 0.
3. **250,000** (score_add; the returned value is stored as gem_total).
4. Create countdown task 0xc2, then set gem_shots = 8, gem_timer = 25 and the status bar to 25/25.
5. Queue the intro (task 0x96 → deff 76, waits its turn up to 3750 ticks [0x0100fbb0]).
6. gem_starts += 1.
7. SOS item 1 (GEM) level 1 [0x01016188(1,1)].
8. gem_awards = 0, gem_snd_idx = 0, gem_award_snd_idx = 0.
9. Audit 0x50 GEM HURRYUP STARTED.
10. Register the status-panel entry [0x01013fd4].

(verified in emulator: traces/gem_hurryup.jsonl, timer 25, total 250,000, starts 1, audit 80 at 23.79 s)

## 5. Behaviour while running

Award formula: `award = min(750,000 + 250,000 * gem_awards, 2,500,000)` [0x01013da8]. gem_awards is counted
before this shot. This gives 750k, 1.0M, 1.25M, 1.5M, 1.75M, 2.0M, 2.25M, then 2.5M from the 8th on.
The verified awards were 750,000 then 1,000,000 (verified in emulator: traces/gem_hurryup.jsonl).

| Trigger | Condition | Effect | Display | Sound | Lamp | Next |
|---|---|---|---|---|---|---|
| sw39 right inner loop | task 0xc2/0xc3 alive and gem_shots & 8 | **award** (flat score_add); gem_total += award; gem_awards += 1; SOS item 1 level 2; audit 0x51 | deff 78 "FOLLOW GEM / %d FOLLOWING(S) / value" | 0x92 (variant cycles) | leff 84, tube 19 | stays running; the shot stays lit [0x01013da8] |
| sw44 left spinner / sw36 right orbit spinner, each spin | task 0xc2/0xc3 alive | if gem_timer < 5 set it to 5, else +1 (max 40). Kill and recreate task 0xc2, which restarts the lead-in (fecc + 156 ticks) [0x01013eac, from 0x0102a6f4 / 0x0102a718] | | | | |
| other switches | | no GEM effect | | | | |

The loop does not unlight after a collect. gem_shots stays 8 for the whole mode.
A spin during the end grace (task 0xc3) revives the countdown as task 0xc2 with at least 5 seconds (inferred from code).

Verified spinner behaviour (verified in emulator: traces/gem_hurryup.jsonl):
- three sw36 spins at 40.65, 41.13 and 41.63 s raised the timer 14→15→16→17;
- the next count came at 46.90 s, 5.27 s after the last spin;
- each spin also scored the spinner's own 10,000 + 90.

Countdown [task_c2 0x01013b88]. It works the same way as CLU:
1. Wait while the intro task 0x96 runs.
2. Wait up to 312 ticks while a display show is busy [0x0100fecc].
3. Sleep 156 ticks (2.54 s).
4. Loop:
   - accumulate 64 un-paused ticks (16 steps of 4 ticks);
   - then gem_timer -= 1 and update the status bar;
   - stop at 0.
   One count = 64 ticks = 1041 ms (verified: 1.044 s average).
   Paused when [0x0100ff64]:
   - the playfield is not validated (0x372e8);
   - a show task 0x81-0xa7 is running;
   - Light Cycle video mode is on;
   - a pop bumper was hit in the last 156 ticks.

Verified timing: start at 23.79 s, first count at 29.92 s (deff 76 ran first).

## 6. How it ends
- **Time out**: at gem_timer = 0:
  1. Sleep 46 ticks (748 ms).
  2. Become task 0xc3 for 125 ticks (2033 ms). This is a grace period: loops still collect and spins still add
     time, but the background display, music, lamps and tube show are already off.
  3. Then the total display, then a rules refresh (inlined `rules_refresh_request`: 0x37418 = 1) [task_c2 0x01013b88].
  (verified in emulator: timer 0 at 63.60 s, deff 79 at 66.39 s)
- **End of ball** (event 0x1d) [0x01013970 → 0x01013fa0]: kill 0xc2/0xc3 and show the total.
- Collecting never ends it. There is no "all shots" end.
- Total display [0x01013b48 → 0x01013ad0]:
  - bar cleared;
  - deff 79 queued as task 0x54 (3750-tick queue);
  - the total and gem_awards are passed;
  - only if gem_total ≠ 0 and the game is not in tilt / game-over (0x37274 & 0x310 = 0).
- Carries over: gem_starts (5 loops needed next time) and gem_progress (partial qualifying stays, per player).

## 7. Media
| When | Display effect | Sound calls | Lamp effect (leff) | Tube show |
|---|---|---|---|---|
| qualifying loop | deff 75: image 0x18d1, blinking "%d" + "MORE TO START" + "FOLLOW GEM", 41 x 3 ticks, hold 10 | 0x8e (sfx 0x055 0x056 0x057, variant = gem_snd_idx) | 81 | 16 |
| start (queued, task 0x96) | deff 76: GEM animation 0x1fae.. (20 frames), "FOLLOW GEM" blinking, "SHOOT / RIGHT INNER LOOP", 51 x 3 ticks | 0x90 (sfx 0x058), speech 0x91 (0x133 0x134) at frame 20 | 82 | 17 |
| while running (rule, task 0xc2) | deff 77 (background): "FOLLOW GEM", seconds left "%d", "SHOOT RIGHT INNER LOOP", score | music 0x8f (sample 0x451) [lamp_rule_init 0x0003b0e8] | 83: lamp 57 R. INNER LOOP ARROW toggles every 4 ticks [leff_083 0x01013fe4] | 18 (fade loop 31 ticks) |
| loop collected | deff 78: "FOLLOW GEM / %d FOLLOWING(S) / value" over the GEM animation, 51 x 3 ticks | 0x92 (sfx 0x065 0x066 0x067 0x068, variant cycles) | 84 | 19 |
| end | deff 79: image 0xace, "FOLLOW / GEM / TOTAL: / value" 23 x 6 ticks, hold 10 | 0x94 (sfx 0x021), 0x95 (0x00c) at frame 15 | 85 | 20 |
| instant info | "%u RIGHT INNER LOOP SHOT(S) TO START "FOLLOW GEM"" while qualifying is enabled | | | [0x01014c6c] |

The shaker (coil 8) runs at deff 76 and 78 [shaker_run(2,2)].
Package names: event_map rows 75–79 match these ids.

## 8. Lamps
| Lamp | State |
|---|---|
| 57 R. INNER LOOP ARROW | while task 0xc2 runs: leff 83 fast flash (toggle every 4 ticks) [leff_rule_init 0x0003b100, leff_083]. Otherwise it is under the control of other features (combos etc.) |
| 25 CENTER GEM | SOS item 1: flashing after the first GEM start, solid after the first loop is collected [0x010164a0] |
| (qualifying) | no dedicated "GEM lit / progress" lamp was found. Progress is shown only by deff 75 and instant info [0x01014c6c] |

## 9. Interactions
- **Sea of Simulation**: SOS item 1 is set to level 1 on start and to level 2 on the first collect [0x01016188].
- **Flynn's Arcade**:
  - "MORE TIME" [0x01013f34, from 0x0100f990]: while 0xc2/0xc3 run, it sets gem_timer to 40 and the bar to 40/40,
    and recreates task 0xc2 (lead-in again). The arcade sets flag 0x2c.
  - "ADV. GEM" = `gem_qualify(1)` (see 4.1).
- **Wizard (flag 0x34) and Portal multiball (flag 0x37)**: they block qualifying and starting. They do not end a
  running GEM.
- **Other modes**: CLU and ZUSE can run at the same time, since nothing prevents it.
  - The status-panel bars are separate: 0x3b57c (CLU), 0x3b584 (GEM), 0x3b58c (ZUSE).
  - Each sw39 also feeds ZUSE fast scoring (`zuse_target_hit(4)`).
- **Spinners**: the time bonus is in addition to the normal spinner score (10,000 + 90 per spin).
- `0x0101283c` (ends CLU, GEM and ZUSE together) calls 0x01013fa0. It has no caller in v1.74.

## 10. Reference scenario
`traces/gem_hurryup.txt` → `traces/gem_hurryup.jsonl`. The watch file uses the RAM names in `work/ram/gem_hurryup.tsv`.
Key events:
- 15.26 s: sw30 validates the playfield.
- 18.45 s and 21.12 s: sw39 scores 250,000 + 1,190 each, with deff 75 (2, then 1 more to start).
- 23.79 s: sw39 starts the mode.
  - Scores 501,190 in total, with audit 0x50.
  - Sets timer 25 and total 250,000.
  - deff 76, then the background deff 77 with music 0x8f.
- 29.92 s: first count (24). Counts follow every ~1.044 s.
- 32.30 s: sw39 collects 750,000 (deff 78, audit 0x51, total 1,000,000).
- 35.47 s: sw39 collects 1,000,000 (total 2,000,000).
- 40.65–41.63 s: three sw36 spins raise the timer 14→17. The next count is at 46.90 s.
- 63.60 s: timer reaches 0.
- 66.39 s: deff 79 (total 2,000,000).

## 11. Open questions
- No lamp shows GEM qualifying progress. If one exists, it is driven outside the GEM code (not found).
- Arcade "ADV. GEM" was not traced in this run. Its behaviour is read from code [0x0100e008].
