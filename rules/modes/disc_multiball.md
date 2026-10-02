# Disc Multiball (Tron Legacy LE 1.74)

Replaces the draft `tron/rules/disc_multiball_rules.md` (made from the old decompile). Corrections vs the draft:
the start also scores **100,000** and seeds the Total with it; deff 48 "JACKPOT" plays on **every** phase-0 hit
(blue shots too); the level L is "previous Disc Multiballs" because the counter is already incremented;
the restart window value 4 = off; the restart also works for 280 ticks after the countdown hits 0;
a missed restart never shows the Total; the start award (2,000,000) is always 2,000,000.
Sources: `tron/code/tron_game_decompiled_v2.c` (0x01006d00-0x01009c00), ROM tables. Traces (fixed `tron_ref`,
factory settings, no pokes): `traces/disc_multiball.jsonl` (full run), `traces/disc_multiball_restart.jsonl`.
1 tick = 16.26 ms.

## 1. Summary

Started from Disc Battle (see `recognizer_and_disc_battle.md`): a 3-ball multiball. Phase 0: the six blue
"(DISC)" shots each score and **add their value to the Jackpot**; shooting the spinning disc collects the Jackpot.
After 6 disc jackpots (adj 68) phase 1: hit the Recognizer 3 times (adj 69), each scoring the current Jackpot.
Phase 2: shoot the disc for the Super Jackpot (sum of all disc jackpots and Recognizer awards), then back to
phase 0. If the multiball ends before a Super Jackpot, a 10-second restart window lets one disc shot restart it
with 2 balls. At the end the Total is shown.

## 2. Settings

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 68 | DISC MULTIBALL DISC SHOTS | 6 | 4-8 | disc jackpots per phase-0 cycle [0x01007074] |
| 69 | DISC MULTIBALL RECOGNIZER SHOTS | 3 | 1-5 | Recognizer hits in phase 1 [0x010070b8] |
| 70 | DISC M.B. RESTART TIMER | 10 | 4-20 | restart countdown start value; **4 = no restart window** [0x0100769c]; one count = 68 ticks |
| 71 | DISC M.B. RESTART AUTOFIRE TIMER | 10 | 0-20 | ball save on restart = adj71 × 62 ticks; **0 = restart disabled** (disc hit in the window does nothing) [0x0100781c] |
| 77 | DISABLE DISC MOTOR | 0 | 0-1 | 1 = the disc never spins (all motor calls skipped) [0x010064a8] |

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| dmb_running | game flag 0x24 | while mode runs | set at start/restart, cleared at end | multiball active [0x01006eec] |
| dmb_restart_available | game flag 0x25 | while mode runs | set at start; cleared by Super Jackpot or when the window opens | a restart window will open at the end |
| dmb_phase | 0x3af04 (4) | while mode runs | 0 at start and after super | 0 disc jackpots, 1 Recognizer, 2 super |
| dmb_lit_mask | 0x3af08 (4) | while mode runs | 0xBF / 0x40 / 0x80 per phase | which shots score (table 0x040d26c0 masks) |
| dmb_level (D) | 0x3af0c (1) | while mode runs | 0 at start; **not** reset by super or restart | +1 per disc jackpot |
| dmb_disc_count | 0x3af10 (1) | while mode runs | 0 at start and after super | disc jackpots this cycle |
| dmb_recog_count | 0x3af14 (1) | while mode runs | 0 on entering phase 1 | Recognizer hits this cycle |
| dmb_jackpot | 0x3af18 (4) | while mode runs | seed (§4) | current Jackpot |
| dmb_super | 0x3af1c (4) | while mode runs | 100,000 at start and after super | Super Jackpot |
| dmb_total | 0x3af20 (4) | while mode runs | = points of the 100,000 start score | Total shown at the end |
| dmb_deff_variant | 0x3af24 (1) | while mode runs | 0 at start, after super, entering phase 1 | written to deff arg +0x34, never read (dead) |
| dmb_restart_secs | 0x3af28 (1) | restart window | adj 70 | countdown |
| dmb_started_count | 0x2111630+p−1 (1) | per player (game) | 0 at game start [0x01006d84] | multiballs started; L = count−1 |
| dmb_supers_collected | 0x2111634+p−1 (1) | per player | 0 at game start | statistics |
| disc_motor_direction | 0x3ae3c (1) | game | 1 at game start | disc direction relay state |

Per-player arrays are NVRAM indexed [player−1]. Full list: `work/ram/disc_multiball.tsv`.

Value formulas (all integers):
- `L = max(dmb_started_count − 1, 0)` = Disc Multiballs this player started **before** this one [0x01007244].
- Jackpot seed: `J0 = min(250,000 + 5,000·(D + L), 375,000)` [0x01006fd4].
- Blue shot value for shot s: `V(s) = min(base_s + step_s·(D + L), max_s)` [0x01007018], table 0x040d26c0:

| Shot | Handler (switch) | Mask | Lamp group / insert | Base | Step | Max |
|---|---|---|---|---|---|---|
| 0 Left orbit | 0x0102a728 (sw43 left orbit made) | 0x01 | 0x62 / lamp 15 LEFT ORBIT (DISC) | 150,000 | 3,000 | 225,000 |
| 1 Left ramp | 0x0102a940/0x0102a9bc (sw37 L. ramp exit) | 0x02 | 0x63 / lamp 50 LEFT RAMP (DISC) | 100,000 | 2,000 | 150,000 |
| 2 Left inner loop | 0x01029ba4 (sw44 left spinner path) | 0x04 | 0x64 / lamp 63 L. INNER LOOP (DISC) | 125,000 | 2,500 | 187,500 |
| 3 Right inner loop | sw39 0x0102ae3c | 0x08 | 0x65 / lamp 58 R. INNER LOOP (DISC) | 225,000 | 4,500 | 337,500 |
| 4 Right ramp | 0x0102aa50/0x0102aad8 (sw34 R. ramp exit) | 0x10 | 0x66 / lamp 55 RIGHT RAMP (DISC) | 200,000 | 4,000 | 300,000 |
| 5 Right orbit | 0x0102a794 (sw46 right orbit made) | 0x20 | 0x67 / lamp 34 RIGHT ORBIT (DISC) | 175,000 | 3,500 | 262,500 |
| 6 Recognizer | sw49/50/51 | 0x40 | 0x68 / lamp 54 RECOGNIZER 3-BANK | (250,000) | (5,000) | (375,000) |
| 7 Spinning disc | sw41 DISC OPTO | 0x80 | none (disc flashers) | – | – | – |

Shot 6's base/step/max equal the jackpot seed numbers but are never used as a shot value (shot 6 is not lit
in phase 0). Note: a raw sw43/sw46 hit in the emulator did not score as orbit shots (the orbit "made"
handlers need the orbit sequence); sw37, sw39, sw34, sw44 did.

## 4. How it starts [on_disc_multiball_started 0x01007128]

Called only from the Disc Battle start (sw41 or the Flynn's Arcade "ADVANCE DISC" award).
1. `multiball_start(balls = 3 if balls_in_play is 0 else balls_in_play + 2, save 625 ticks (10.16 s),
   grace 187 ticks (3.04 s))`. If it fails nothing else happens. (verified: balls 3 / 625 / 187)
2. Phase 0, mask 0xBF, disc count 0, D = 0; Jackpot = J0 with D = 0 (250,000 for the first multiball, +5,000
   for each earlier one, max 375,000); Super = 100,000; variant 0.
3. **Score 100,000** (x PF mult.); Total = the points scored (100,000 at x1). (verified)
4. Flags 0x24 and 0x25 set; dmb_started_count += 1; "ITEMS LIT: DISC" (audit 0x72) via FUN_01016188(5,1);
   audit 0x41 DISC MULTIBALL STARTED.
5. Intro deff 46 is queued (task 0x88, FUN_0100fbb0 with 0xea6 = 3,750-tick timeout) and plays when the display
   is free (seen 2.9 s after start). The status deff 47 rule waits until the intro has run [0x010081c0].
Before this the Disc Battle start scored 2,000,000 and raised k (recognizer doc).

## 5. Behaviour while running

All awards go through `dmb_shot(shot)` [0x01007244], which only acts while flag 0x24 is set or the end task
(0xab/0xac, 218 ticks after the end) runs, and only for a shot whose mask is in dmb_lit_mask.
Every award is added to the Total. All scores are x playfield multiplier; the stored values use the points
actually scored.

### 5.1 Phase 0 "SHOOT SPINNING DISC" (mask 0xBF)

| Trigger | Effect | Display | Sound | Lamp |
|---|---|---|---|---|
| blue shot 0-5 | score V(s); Jackpot += points scored; audit 0x43 | deff 48 "DISC MULTIBALL / JACKPOT / <points>" (yes, labelled JACKPOT; random clip of 12) | 0x05a, then 0x05c speech, 0x05b | leff 48, tube 44 |
| disc (sw41) | score Jackpot; Super += points; D += 1; disc count += 1; Jackpot = J0 (new D); audit 0x42; if disc count ≥ adj 68: phase 1 (mask 0x40, Recognizer count 0, variant 0) | deff 48 with the jackpot | same | same |

Verified (traces/disc_multiball.jsonl): left ramp 100,000, right inner loop 225,000, right ramp 200,000 → Jackpot
775,000; disc → 775,000 scored, Super 875,000, Jackpot 255,000; next disc jackpots 255,000, 260,000, 265,000,
270,000, 275,000; after the 6th: phase 1, Jackpot 280,000, Super 2,200,000.

### 5.2 Phase 1 "SHOOT RECOGNIZER" (mask 0x40)

The 3-bank rises (verified bank_up 0.63 s after phase 1), the disc motor stops (coil 5 off), the Recognizer head
swings between sw54 and sw56 every 62 ticks.

| Trigger | Effect | Display | Sound | Lamp |
|---|---|---|---|---|
| sw49/50/51 | score current Jackpot (not changed); Super += points; Recognizer count += 1; audit 0x44; at adj 69 hits: phase 2 (mask 0x80) | deff 49 "DISC MULTIBALL / JACKPOT / <points>" | 0x05d, 0x05c, 0x05b | leff 49, tube 45 |
| disc | not lit: base 2,310 only | | | |

The target hit also scores the normal 1,000 + 1,080. Verified: 3 hits of 280,000, Super 3,040,000.

### 5.3 Phase 2 "SHOOT SPINNING DISC" (mask 0x80) – Super Jackpot

| Trigger | Effect | Display | Sound | Lamp |
|---|---|---|---|---|
| disc | score Super; dmb_supers_collected += 1; audit 0x45; "ITEMS COLLECTED: DISC" (audit 0x73); back to phase 0 (mask 0xBF, disc count 0), Super = 100,000, variant 0; **flag 0x25 cleared (no restart window any more)**. D and Jackpot are kept | deff 50 "SUPER JACKPOT / <points>" | 0x05e, 0x05f at frame 30, speech 0x060 at frame 40 | leff 50, tube 46 |

Verified: Super 3,040,000 scored, Total 6,605,000; next left ramp 112,000 = 100,000 + 2,000·6 (D kept).

### 5.4 Disc motor [rule 0x010066c0]

The disc spins (coil 30 DISC MOTOR RELAY pulse, coil 5 DISC MOTOR POWER on, coil 22 direction relay) while the
game is in play and any of: Disc Battle lit; Disc MB phase 0 or 2 or the restart window [0x01006e88]; Quorra
stage 2; Portal MB; Sea of Simulation stage 2; Daft Punk MB. Otherwise it stops; 125 ticks after a stop, if still
stopped, the direction flips, so each new spin alternates direction (inferred). Adj 77 = 1 disables all of it.
(verified: coil 5 on at battle, stays on in phase 0, off in phase 1, on in phase 2, off at the end)

## 6. How it ends

- Trigger: fewer than 2 balls in play (trough event, [0x0101bbc0] → [0x0101bcec] → `dmb_end` [0x01007714]);
  flag 0x24 cleared.
- **Super collected (flag 0x25 clear)**: task 0xab: 156 ticks, id → 0xac, 62 ticks, then the Total deff 51
  "DISC MULTIBALL / TOTAL: / <total>" (task 0x4e) unless tilted/game over (mode bits 0x310). Total appears
  218 ticks (3.54 s) after the end (verified 3.54 s). While task 0xab/0xac runs, lit shots still score
  (dmb_shot accepts it), so a late drain-race shot can still be collected.
- **No super (flag 0x25 set)**: if adj 70 ≠ 4 the restart window opens [0x0100769c]: flag 0x25 cleared,
  countdown = adj 70, deff 52 "DISC / MULTIBALL / RESTART" queued (task 0x89), then rule display deff 53
  "DISC MULTIBALL / RESTART / SHOOT DISC / %d". Task 0xad [0x01007608]: waits in FUN_0100fecc(0x138) (≈2.8 s
  in the trace, likely until deff 52 is done), then every 68 ticks (1.106 s, measured 1.107 s) count −1;
  speech 0x02e when it reaches 7; speech 0x02f(n) at 5, 4, 3, 2, 1 (sample picked by n). At 0: id → 0xae
  (187 ticks), id → 0xaf (93 ticks), end. **A disc hit is accepted during all of this, including the 280 ticks
  (4.55 s) after the display reached 0** [0x010077d8] (verified: a restart at count 0 worked).
  With adj 70 = 10 the window lasts ≈ 2.8 + 11.06 + 4.55 ≈ 18.4 s.
- **Restart** [0x0100781c] (disc hit while tasks 0xad-0xaf run, adj 71 ≠ 0): `multiball_start(balls_in_play+1
  (2 if 0), save adj71·62 ticks (620 = 10.08 s), grace 93 ticks)`; flag 0x24 set; all values (phase, D, Jackpot,
  Super, Total) continue unchanged; deff 54 "DISC / MULTIBALL" (sounds 0x030, speech 0x031) queued (task 0x8a).
  No points for the restart. Flag 0x25 stays clear, so the next end goes straight to the Total (verified:
  traces/disc_multiball_restart.jsonl, Jackpot 255,000 continued, second end → deff 51 after 3.5 s).
- **Window expires without restart: the Total is never shown** (task_ad does not show it, and the end-of-ball
  hook only shows it while flag 0x24 or task 0xab/0xac is active). Verified in emulator (no deff 51). ROM quirk.
- End of ball (event 0x1d) [0x010078ec]: if still running or in task 0xab/0xac → clear and show Total.
- Another multiball start (Light Cycle, Portal, Quorra restart, Sea of Simulation) kills tasks 0xad-0xaf
  (window cancelled, no Total) [0x010078c8].
- Carry-over: dmb_started_count (raises L and the disc-hit requirement of the next Disc Battle). Nothing else.

## 7. Media

| When | Display effect | Sound calls | Lamp effect | Tube show |
|---|---|---|---|---|
| start (queued) | deff 46: "DISC / MULTIBALL" over animation 0x11dc-0x1214, colour cycling 10 frames, blinking 31 frames, 10 hold | speech 0x055+player (0x056-0x059: "player N…"), music 0x02a when deff 47 starts | 44 (all-lamp show, disc inserts excluded) | 42 |
| running | deff 47 (rule, background): "DISC MULTIBALL", phase 0: "%d" = adj68 − disc count, "SHOOT SPINNING DISC" (blinks), "JACKPOT=%,02lu"; phase 1: "%d" = adj69 − count, "SHOOT RECOGNIZER", "RECOGNIZER=%,02lu" (Jackpot); phase 2: "SHOOT SPINNING DISC", "SUPER=%,02lu" | | 45 (lit shot inserts flash) | 43 |
| phase-0 hit | deff 48 "DISC MULTIBALL / JACKPOT / %,02lu", random clip of 12 (table 0x040d2804), 21×4 frames | 0x05a sfx, 0x05c speech, 0x05b sfx | 48 | 44 |
| phase-1 hit | deff 49 same layout | 0x05d, 0x05c, 0x05b | 49 | 45 |
| phase 1 (rule) | – | – | 47 (Recognizer lamps 51-53 chase) | – |
| phase 2 (rule) | – | – | 46 (pulses disc flashers 26/27) + 76 | – |
| super | deff 50 "SUPER JACKPOT / %,02lu", 61×3 frames | 0x05e, 0x05f, speech 0x060 (0x150/0x151) | 50 | 46 |
| total | deff 51 "DISC MULTIBALL / TOTAL: / %,02lu" | 0x061 | 51 | 47 |
| window opens | deff 52 "DISC / MULTIBALL / RESTART" (blinking) | 0x02c | 52 | 48 |
| window running | deff 53 (rule) "DISC MULTIBALL / RESTART / SHOOT DISC / %d" | music 0x02b (sample 0x44d, not exported); speech 0x02e (0x19e/0x19f) at 7; 0x02f (0x17c,0x1a4…0x1a0) at 5..1 | 53, 54 (disc flashers) | 49 |
| restarted | deff 54 "DISC / MULTIBALL" | 0x030, speech 0x031 (0x188) | 55 | 50 |

## 8. Lamps

- (DISC) inserts = lamp groups 0x62-0x68 (one lamp each: 15, 50, 63, 58, 55, 34, 54). leff 45 [0x01008208]:
  inserts whose mask is in dmb_lit_mask flash (on/off every 3 ticks = 49 ms); the others are left to the normal
  lamp image. Phase 0: the six shot inserts flash (54 not). Phase 1: only lamp 54 flashes. Phase 2: none (the
  disc has no insert; leff 46/76 pulse the disc flashers).
- Recognizer lamps 51-53: leff 47 chase in phase 1.
- leff 44 (intro) claims the whole matrix except the (DISC) inserts.

## 9. Interactions

- Disc Battle (prerequisite) is blocked while this runs; targets do not count either.
- Starting another multiball during Disc MB stacks; all multiballs end together when < 2 balls remain
  ([0x0101bcec] ends Disc, Light Cycle, Quorra, Portal, Daft Punk). A Light Cycle / Portal / Sea of Simulation /
  Quorra-restart start cancels the Disc restart window.
- sw41 order (see recognizer doc): Portal MB shot runs before the Disc MB shot; base 2,310 after.
- Find Flynn items: start = "ITEMS LIT: DISC" (0x72), super = "ITEMS COLLECTED: DISC" (0x73).
- Tilt: Total display suppressed (mode bits 0x310) (inferred).
- Ball save: 625 ticks at start, adj71·62 at restart; drains inside it are re-served (seen in the emulator).

## 10. Reference scenario

`traces/disc_multiball.txt` (qualify as in the recognizer scenario, then: sw37, sw39, sw34 blue shots;
6 disc jackpots; a disc hit in phase 1; sw50, sw49, sw51; disc super; sw37; drain 2). Watch list used
(tron_ref watch.tsv, `name addr size`): dmb_phase 3af04 4, dmb_lit_mask 3af08 4, dmb_level 3af0c 1,
dmb_disc_count 3af10 1, dmb_recog_count 3af14 1, dmb_jackpot 3af18 4, dmb_super 3af1c 4, dmb_total 3af20 4,
dmb_deff_variant 3af24 1, dmb_restart_secs 3af28 1, rec_* 3b3f4/3b3f8/3b3fc 4, 3b400 1, 21117b8…21117dc 1,
dmb_count_p1 2111630 1, dmb_supers_p1 2111634 1.
Expected: 38.11 s multiball_start 3/625/187, 100,000, Jackpot 250,000, Total 100,000; 100,000 / 225,000 /
200,000 blue shots (Jackpot 775,000); disc jackpots 775,000, 255,000, 260,000, 265,000, 270,000, 275,000;
phase 1 at 57.76 s; three 280,000 Recognizer awards; phase 2 at 64.52 s; Super 3,040,000 at 66.25 s
(Total 6,605,000); 112,000; end at 73.67 s; deff 51 Total 6,717,000 at 77.21 s.
`traces/disc_multiball_restart.txt`: one jackpot, drain after save → window (10…0, speech 0x02e at 7, 0x02f at
5..1), disc at count 2 → multiball_start 2/620/93, deff 54; jackpot 255,000 continues; drain → Total after 3.5 s.

## 11. Open questions

- FUN_0100fecc(0x138) at the start of the countdown: exact wait condition not decoded (≈2.8 s observed).
- In the restart trace the bank rose and dropped once during the window (62.5 s / 64.7 s); cause not traced.
- snd_play2(0x2f, n) sample selection by n assumed (5→"five" … 1→"one"); samples not listened to.
- Orbit shots 0 and 5 not exercised in the emulator (raw sw43/sw46 pulses do not complete an orbit).
