# ZUSE fast scoring

Audience: a developer rebuilding Tron Legacy LE 1.74 in MPF/Godot. Addresses refer to
`tron/code/tron_game_decompiled_v2.c` (function headers `// ==== <addr>`). 1 tick = 16.26 ms.
Reference trace: `traces/zuse_fast_scoring.jsonl` (scenario `traces/zuse_fast_scoring.txt`, factory settings, no pokes).

## 1. Summary
The four Z-U-S-E standup targets are sw7 (Z)USE, sw8 Z(U)SE, sw48 ZU(S)E and sw13 ZUS(E).

**Qualifying.** Each new letter scores 75,000. Completing the set scores 250,000 and more on later sets. The 1st
completion starts "FAST SCORING". After that, 4 more completions are needed for each further start.

**The mode.** It scores 100,000 and runs a clock of 25 s (operator adjustment 66). Nearly every playfield switch
scores the fast-scoring value. The value starts at 10,000 (+5,000 per earlier start, max 50,000). During the mode:
- each new ZUSE target adds +1,000 to the value;
- completing all four targets adds 10 seconds.

**End.** When the clock runs out, a ~4 s grace follows in which switches still score. Then "FAST SCORING TOTAL" is
shown. It also ends at end of ball or on tilt.

## 2. Settings (operator adjustments)
| Adj | Name | Default | Range | Effect |
|---|---|---|---|---|
| 66 | ZUSE FAST SCORING TIMER | 25 | 15–45 | starting seconds [0x010318ac adj_get(0x42)]. Also the default extension when 0x01031ab8 is called with 0 (never in v1.74; the target set always passes 10) |
| 86 | SHAKER MOTOR | 3 | 0–3 | at 3, every fast-scoring hit pulses the shaker [0x01031b88] |

## 3. State
Per-player arrays are indexed [player-1].

| Name | RAM | Size | Scope | Init / reset | Meaning |
|---|---|---|---|---|---|
| zuse_letters | 0x021118d4 +4*(p-1) | 4 | per player (game) | event 0x26 and each completion: set to the bits of *disabled* ZUSE switches (normally 0) [0x01033624] | lit qualifying letters: 1 = sw7 Z, 2 = sw8 U, 4 = sw48 S, 8 = sw13 E [table 0x040d7024] |
| zuse_completions | 0x021118e4 +(p-1) | 1 | per player (game) | 0 on event 0x26 [0x01033680] | ZUSE sets completed (cap 255) |
| zuse_needed | 0x021118e8 +(p-1) | 1 | per player (game) | 1 on event 0x26 | completions needed for the next start (+4 after each start) [0x01033790] |
| zfs_starts | 0x021118c4 +(p-1) | 1 | per player (game) | 0 on event 0x26 [0x010315d8] | fast-scoring starts (cap 255). Sets the start value |
| zfs_time_ext | 0x021118c8 +(p-1) | 1 | per player (game) | 0 on event 0x26 | all-targets time extensions earned (cap 255) [0x01031d0c] |
| zfs_switch_hits | 0x021118cc +2*(p-1) | 2 | per player, per ball | 0 on ball start (event 0x13) [0x01031624] | fast-scoring hits scored (cap 65535). Getter 0x01031fbc has no direct BL caller (maybe a table entry; use unknown) |
| zfs_timer | 0x0003b8f0 | 1 | while running | adj 66 at start; 45 on MORE TIME | seconds left [task_59 0x01031730] |
| zfs_value | 0x0003b8ec | 4 | while running | min(10,000 + 5,000 * zfs_starts, 50,000) at start (zfs_starts before this start) | points per hit [0x010318ac] |
| zfs_targets | 0x0003b8e8 | 4 | while running | 0x10 + bits of disabled targets | targets hit in the current FS set: 1 sw7, 2 sw8, 4 sw48, 8 sw13; 0x10 = "any switch" marker. A set is complete at 0x1f [table 0x040d6ef0, 0x01031588] |
| zfs_total | 0x0003b920 | 4 | while running | 100,000 (start award) | running total for the end display |
| zfs_queue | 0x0003b8f2 | 1 | while running | 0 | hits waiting to be scored, while task 0x80 runs [0x01031d0c, task_80 0x01031cc0] |
| zfs_recent | 0x0003b8f4..0x0003b918, idx 0x0003b91c/0x0003b91e | 10 x 4, 2, 2 | while running | idx 0 when deff 96 starts | ring of the last 10 hit values shown by deff 96 [0x01031b88] |
| zfs_timer_bar | 0x0003b58c (cur/max) | 1/1 | while running | | status panel bar [0x0102309c, 0x010230b0] |

Tasks:
- 0x59: countdown. Renamed 0x5b during the end grace.
- 0x9b: queued intro display.
- 0x5a: reminder speech.
- 0x80: hit-queue drain.
- 0x55: queued total display.
- 0x4a: letter blink timer (62 ticks).
- 0x4c: 10-tick lockout after a completion.

For scoring, the time extension and ending, "running" means tasks 0x59–0x5b [0x01031b70]. For the background show,
lamps, value raise and reminder it means 0x59 only [0x01031b5c].

## 4. How it starts (qualifying)

### 4.1 Z-U-S-E targets
Each target handler [0x0102b08c sw7, 0x0102b0d4 sw8, … sw48, sw13] runs in this order:
1. `zuse_target_hit(idx)`, which only works while FS is running (5).
2. Other hooks.
3. `zuse_letter(idx, lamp)` [0x01033790].
4. The 1,130 switch score [0x0102a188].

Qualifying is enabled [0x01033744] only when all of these hold:
- FS is not running (tasks 0x59–0x5b);
- the wizard flag 0x34 is clear;
- the Portal multiball flag 0x37 is clear;
- the Daft Punk / End of Line flag 0x27 is clear [0x01004be8].

| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| ZUSE target | qualifying not enabled (e.g. during FS) | **5,000** | – | 0xa4 (sfx 0x083) | leff 119 (blink target) |
| ZUSE target | lockout task 0x4c running | nothing (switch score only) | | | |
| ZUSE target | letter already lit (and not all 4 lit) | **10,000** | – | 0xa5 (sfx 0x083) | leff 121 |
| ZUSE target | new letter, not the last | letter lit; **75,000**; task 0x4a (62 ticks) | deff 91 "COLLECT / FOR FASTSCORING" + 4 ZUSE icons (new one blinks), 30 x 4 ticks | 0xa6 (sfx 0x0da 0x0db 0x0dc) | leff 120 (blink target 10 x 2 ticks + flasher pulse) |
| ZUSE target | completes Z-U-S-E | see completion below | | 0xa8 (sfx 0x0ed) | leff 122 |

Every hit also gets the 1,130 switch score. The 75,000, 10,000 and 5,000 are flat `score_add` calls [0x01033790].

Completion [0x01033790]:
1. zuse_completions += 1 and letters are reset.
2. Score `min(250,000 + 25,000 * completions_before, 750,000)` [0x0103370c].
3. If zuse_completions < zuse_needed: show deff 92 "%d MORE / FOR FASTSCORING" with needed − completions.
4. Otherwise **start FS** and zuse_needed += 4.
5. Then a 10-tick lockout (task 0x4c).

So the 1st completion starts FS, then the 5th, the 9th, and so on.
(verified in emulator: traces/zuse_fast_scoring.jsonl, 1st set 250,000 + start; 2nd set 275,000 + deff 92 "4 MORE")

Flynn's Arcade "ADV. ZUSE" = `0x010339fc(1)` [from 0x0100e094]. It does one silent completion (no leff 122,
sound or deff 92) and may start FS.

### 4.2 Start [on_zuse_fastscoring_started 0x010318ac]
In order:
1. Clear flag 0x2c if no other timed mode is running.
2. Kill any old 0x59–0x5b.
3. zfs_timer = adj 66, and set the bar.
4. **100,000** (flat; stored as zfs_total).
5. Create task 0x59.
6. zfs_targets = 0x10 | disabled targets.
7. zfs_value = min(10,000 + 5,000 * zfs_starts, 50,000).
8. Queue the intro task 0x9b → deff 94 (shows the value).
9. Start the reminder task 0x5a.
10. Clear flag 0x31.
11. zfs_starts += 1.
12. SOS item 3 (ZUSE) level 1.
13. Audit 0x52 ZUSE FASTSCORING STARTED.
14. Register the status-panel entry.

(verified: timer 25, value 10,000, targets 0x10, total 100,000 at 26.51 s)

Unused path: `0x0103184c` sets flag 0x31 and shows deff 93 "ZUSE / FAST SCORING / READY". `0x01031888` would then
start FS if flag 0x31 is set. Neither has a caller in v1.74.

## 5. Behaviour while running

### 5.1 Fast-scoring hits
`zuse_target_hit(4)` ("any switch") is called from nearly every playfield switch handler (30 call sites), for example:
- slings, bumpers, lanes, orbits, ramps, spinners, sw12 ZEN, sw39;
- 0x0100b098 (TRON targets).

The ZUSE targets call it with their index 0–3 instead.

| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| any hooked switch | task 0x59–0x5b alive, task 0x80 not running | score **zfs_value** (flat score_add); zfs_total += it; zfs_switch_hits += 1; start task 0x80 | deff 96 pop-up (recent values "%luK"), unless deff 94 or task 0x9b runs, deff 96 is already up, or a multiball runs | 0xb1 (sfx 0x0ed) | leff 129 (if not running); shaker if adj 86 ≥ 3 [0x01031b88] |
| any hooked switch | task 0x80 running | zfs_queue += 1. Task 0x80 scores one queued hit per tick and exits after 93 idle ticks [task_80] | | | |
| new ZUSE target (bit not yet in zfs_targets), set not complete | task 0x59 alive (not grace) | bit set; zfs_value = min(value + 1,000, 50,000); then the hit scores the new value | deff 97 "ALL / TARGETS / value" (only if the value rose) | 0xaf (sfx 0x094), speech 0xb0 | leff 120 [0x01031a5c] |
| repeat ZUSE target | | hit scores the value | | | leff 121 |
| 4th ZUSE target (zfs_targets = 0x1f) | task 0x59–0x5b alive | zfs_targets reset; zfs_time_ext += 1; SOS item 3 level 2; **time +10** (cap 45); restart task 0x59 (kills the grace 0x5b), so the count starts over after the fecc wait; value **not** raised | deff 98 "TIME / EXTENDED / ALL TARGETS=value" | 0xb2, speech 0xb3 | leff 128 [0x01031ab8] |

Each ZUSE target hit during FS also gets 5,000 (blocked-qualifying path) and the 1,130 switch score.
Verified hits (verified in emulator: traces/zuse_fast_scoring.jsonl):
- slings scored 10,000 each;
- sw7 new: value 11,000 and deff 97; sw7 repeat: 11,000;
- sw8 and sw48: 12,000, then 13,000;
- sw13 completed the set: timer 16 → 26, deff 98, value stayed 13,000;
- a hit during the grace (timer 0) still scored 13,000.

### 5.2 Countdown [task_59 0x01031730]
1. Wait up to 312 ticks while a display show is busy [0x0100fecc]. There is no fixed lead-in like CLU/GEM. The
   queued intro task 0x9b is itself in the "show task" range 0x81–0xa7, so the clock is paused until the intro is
   over (inferred from 0x0100ff64).
2. Loop:
   - wait 11 steps of 6 ticks = **66 ticks (1073 ms)**. If the pause check is true at any step, the step count
     restarts at 0, so a pause restarts the current second;
   - then, if zfs_timer = 0, leave the loop;
   - else zfs_timer -= 1 and update the bar.

   So after the display reaches 0, one more 66-tick period runs before the grace.

Pause rule [0x0100ff64]: the playfield is not validated, or a show task 0x81–0xa7 runs, or the Light Cycle video
mode is on, or a pop bumper was hit in the last 156 ticks.

Measured: one count = 1.09 s on average (66 ticks plus pause restarts). The start was at 26.51 s and the first
count at 31.61 s (intro deff 94 first).

Reminder [task 0x5a, 0x0103167c]:
- sleeps 625 ticks (10.2 s);
- then, while task 0x59 runs and no multiball is running, plays call 0xb5 (at most as many times as 0xb5 has
  samples: 1);
- then sleeps 625 ticks between checks.

## 6. How it ends
- **Time out**:
  1. One extra 66-tick period at 0.
  2. Become task 0x5b and sleep **250 ticks (4065 ms)**. This is the grace: switches still score, but the value
     does not rise, and the background show, lamps and reminder are off.
  3. The total display, then a rules refresh (inlined `rules_refresh_request`: 0x37418 = 1) [task_59].
  (verified in emulator: timer 0 at 71.42 s; hits scored at 71.53, 73.20, 74.88 and 76.56 s; deff 99 at 77.63 s)
- **End of ball** (event 0x1d) and **tilt** (event 0x65) [0x01031664 / 0x01031654 → 0x01031f8c]: kill 0x59–0x5b,
  then the total display.
- Total display [0x0103171c]:
  - bar cleared;
  - task 0x55 → deff 99 (queued);
  - only if zfs_total ≠ 0 and not in tilt / game-over state (0x37274 & 0x310 = 0).
- Carries over:
  - zfs_starts raises the next start value;
  - zuse_letters and zuse_completions persist across balls (reset only on event 0x26);
  - zfs_switch_hits resets each ball.

## 7. Media
| When | Display effect | Sound calls | Lamp effect (leff) | Tube show |
|---|---|---|---|---|
| new letter | deff 91: "COLLECT / FOR FASTSCORING", Z-U-S-E icons (lit, new blinking), 30 frames x 4 | 0xa6 | 120 | 26 (single flash) |
| repeat letter / blocked | – | 0xa5 / 0xa4 | 121 / 119 | – |
| set complete, more needed | deff 92: "%d MORE / FOR FASTSCORING", icons blink, 40 frames x 3 | 0xa8 | 122 | 27 (6 flashes x 12 ticks) |
| FS start (queued task 0x9b) | deff 94: ZUSE animation, "FAST SCORING", value ("ALL TARGETS / SCORE / %,02lu POINTS" panel, 0x010323d0), 24 x 4 ticks + tail | 0xad (0x00c), speech 0xae (0x317 0x343 0x215 0x43e 0x313 0x317) | 123 | 29 |
| while running (rule, task 0x59 and not "intro queued but not yet showing" [0x01031fe0]) | deff 95 (background): seconds left (large "%u"), "ALL TARGETS=%,02lu" (value) | music 0xaa (sample 0x450) [lamp_rule_init 0x0003b894] | 124 (unhit ZUSE target lamps flash, 5-tick toggle; hit ones off) and 125 (lamp-group chase, 14 steps x 4 ticks, only while the playfield is valid) | 30 (fade loop) |
| each scored hit | deff 96 pop-up: scrolling "%luK" values (ring of last 10) | 0xb1 | 129 | – |
| new target during FS | deff 97: "ALL / TARGETS / value" 21 x 3 ticks | 0xaf, speech 0xb0 (0x347 0x385 0x383 0x346 0x349) | 120 | – |
| all four during FS | deff 98: "TIME / EXTENDED" + timer and "ALL TARGETS=value", 31 frames | 0xb2 (0x05b 0x05c 0x05d), speech 0xb3 (0x1c7 0x19b 0x10e 0x334) | 128 | – |
| reminder | – | 0xb5 (0x00c) | – | – |
| end | deff 99: image 0xadf, "FAST SCORING / TOTAL: / value", 51 x 3 ticks, hold 10 | 0xb4 (sfx 0x05e) | 130 | 31 |
| unused | deff 93 "ZUSE / FAST SCORING / READY" | 0xab, 0xac | – | 28 |
| instant info | "%u ZUSE TARGET COMPLETION(S) / TO START / "ZUSE FAST SCORING"" while qualifying is enabled | | | [0x01034130] |

The shaker runs at deff 93, 94, 97 and 98 [shaker_run(2,2)].
Package names: event_map rows 91–99 match these ids.

## 8. Lamps
| Lamp | State |
|---|---|
| 12 (Z)USE, 10 Z(U)SE, 43 ZU(S)E, 29 ZUS(E) | Not in FS, qualifying enabled: flashing = letter unlit, solid = letter lit. Qualifying blocked: off (the rule runs at prio 0x20) [0x01033efc]. During FS: leff 124 flashes the targets not yet hit in the current set, and hit ones are off |
| 23 CENTER ZUSE | SOS item 3: flashing after the first FS start, solid after the first all-targets extension [0x010164a0] |

## 9. Interactions
- **Every switch feeds FS.** Rebuilders should treat "any playfield switch while FS runs" as one hit, except that a
  switch sets off one `zuse_target_hit` call per handler. Bursts (spinners, pops) are queued and scored one per tick.
- **Multiballs**:
  - They do not block the FS start. Only qualifying is blocked, by flags 0x34, 0x37 and 0x27.
  - Disc, Light Cycle, Quorra and the other multiballs (FUN_0100f918) only hide deff 96 and stop the reminder speech.
- **Flynn's Arcade**:
  - "MORE TIME" [0x01031f08, from 0x0100f9a0]: while 0x59–0x5b run, it sets zfs_timer to 45 and the bar to 45/45,
    and restarts tasks 0x59 and 0x5a. The arcade sets flag 0x2c.
  - "ADV. ZUSE": see 4.1.
- **Sea of Simulation**: item 3 level 1 on start, level 2 on the first all-targets extension.
- **CLU / GEM** can run at the same time. Their shots also score FS hits.
- `0x0101283c` (ends CLU/GEM/ZUSE together) has no caller.

## 10. Reference scenario
`traces/zuse_fast_scoring.txt` → `traces/zuse_fast_scoring.jsonl`. The watch file uses the RAM names in
`work/ram/zuse_fast_scoring.tsv`. Key events:
- 18.43, 21.12 and 23.81 s: sw7, sw8, sw48 score 75,000 + 1,130 each, with deff 91 (letters 1, 3, 7).
- 26.50 s: sw13 completes the set. It scores 250,000, starts FS (100,000) and adds 1,130.
  - timer 25, value 10,000;
  - zuse_needed 1 → 5;
  - deff 94, then the background deff 95 with music 0xaa.
- 31.61 s: first count.
- 31.67–33.10 s: slings score 10,000 each (deff 96). The burst hits are scored through the queue.
- 34.74 s: sw7 raises the value to 11,000 (deff 97) and scores 11,000 + 5,000 + 1,130.
- 36.41 s: sw7 repeat scores 11,000.
- 38.09 s and 39.76 s: sw8 → 12,000, sw48 → 13,000.
- 41.44 s: sw13 completes the set. The timer goes 16 → 26 and deff 98 shows.
- 43–76 s: slings score 13,000 each. The timer reaches 0 at 71.42 s, the grace scores until 76.56 s, and deff 99
  shows at 77.63 s.
- 97.8–104.3 s: second set: 75,000 x 3, then 275,000 and deff 92 (4 more needed).

## 11. Open questions
- The leff 120/121/119 parameter is the handler's switch-object byte (+0x34). The table lamp (entry +5) is used only
  inside FS. Which lamp the qualifying blink lands on was not traced.
- Who reads zfs_switch_hits is unknown. Its getter 0x01031fbc has no direct caller, so it may be reached through a pointer table.
- Flag 0x31 and deff 93 ("READY") are a dead path in v1.74.
