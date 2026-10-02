# Portal Multiball

Stern Tron Legacy LE 1.74. Audits 0x89 PORTAL MULTIBALL STARTED, 0x8a PORTAL MULTIBALL AWARDS,
0x8b PORTAL MULTIBALL SUPER JACKPOTS, 0x8c PORTAL MULTIBALL BONUS AWARDS. No operator settings.

Value notation: every award goes through `score_add` (playfield multiplier applied). The Super
Jackpot value and the running total are built from the **already multiplied** awards, and the
Super is multiplied again when scored (a ROM quirk worth keeping if multipliers matter).

## 1. Summary

Portal is the game's wizard-style multiball. It is lit when all 9 items (Flynn, GEM, CLU, ZUSE,
Quorra, Disc, Light Cycle, Recognizer, TRON) are **collected**, and started at the VUK (Flynn's
Arcade scoop). It is a 4-ball multiball with a 15 s ball save. Six shots have to be made a set
number of times (left orbit 4, left ramp 3, left inner loop 5, right inner loop 3, right ramp 3,
right orbit 4 = 22 shots); each shot is worth 500,000 plus 50,000 per shot already made (max
1,500,000) and also builds the Super Jackpot. Completing a shot adds a ball. After all 22 the
Super Jackpot is lit at the spinning disc. Collecting it turns every shot into 1,000,000 for
the rest of the multiball. If no Sea of Simulation was started since the last Portal, the start
also awards a 50,000,000 "Sea of Simulation bonus". It ends at one ball left plus 5 s grace and
shows the total; each Portal started also adds 2,250,000 to that ball's end-of-ball bonus.

## 2. Settings (operator adjustments)

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| — | none | — | — | No adjustment is read by this feature. Ball save and values are constants. |

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| pm_running | game flag 0x37 | while mode runs | set at start; cleared at one ball left / end of ball | Multiball running [0x0102f474, 0x0102f8b8] |
| pm_grace | task 0xd2 | after one ball left | 312 ticks | Grace: shots still score [0x0102f8b8, 0x0102f8a4] |
| pm_phase | 0x0003b878, 4 B | while mode runs | 0 at start | 0 = shots, 1 = Super lit, 2 = all shots 1,000,000 [0x0102f6c8] |
| pm_cnt_* | 0x0003b85c, b860, b864, b868, b86c, b870, b874 (1 B each, 4 apart) | while mode runs | 0 at start | Hits on left orbit, left ramp, left inner loop, right inner loop, right ramp, right orbit, disc (disc max 0, never counts) [table 0x040d6e14] |
| pm_super_value | 0x0003b854, 4 B | while mode runs | 1,000,000 at start | Super Jackpot value; + every phase-0 award as returned by `score_add` [0x0102f6c8] |
| pm_total | 0x0003b858, 4 B | while mode runs | = start award (1,000,000 x multiplier) | Total for the end display: start award + awards + super + phase-2 awards; the 50M bonus is NOT included [0x0102f474, 0x0102f6c8] |
| pm_starts | 0x021118b8 (+player-1), 1 B | per player (whole game) | 0 at the player's FIRST ball only (event 0x26 fires once per player per game, 0x0102f2e8); kept from ball to ball (verified in traces/bonus.jsonl, see bonus.md) | Portals started so far this game (saturates 255); read by every end-of-ball bonus [0x01000cd4] |
| sos_since_portal | game flag 0x33 | per player (game flags are saved per player, inferred) | set when Sea of Simulation starts (0x01026520); cleared when Portal starts | Gates the 50M bonus [0x0102f474] |
| items_collected | byte 1 of word 0x02111690 + player*4 + item*16 (items 0..8) | per player | cleared by Portal start | All 9 non-zero = Portal lit [0x0101643c]. Owned by the items / Sea of Simulation feature |
| pm_eject_lit | 0x021118a0 (+player-1), 1 B | per player turn (cleared on event 0x26, 0x0102e834) | — | Portal entry (bit 8) of the shared eject-lit bytes 0x2111894 + 4 x index (lit_item_add/take/test 0x0102e8c0/0x0102eaa4/0x0102ec38); needed for the **static** lamp 40 in the eject-lamp updater (0x0102f024). No code sets it in this ROM, so in practice lamp 40 is only driven by leff 163 |
| (unknown) | 0x021118a8 (+player-1)x4, 4 B | per game | 0 at game start (event 0x2e, 0x0102f2a4) | No other reference found |

Shot table 0x040d6e14 (16 bytes per entry: shot bit, lamp group, counter pointer, max hits):

| Shot # | Shot (switch, handler) | Bit | Lamp group | Max | Lamps in group (lamps.csv) |
|---|---|---|---|---|---|
| 0 | Left orbit (sw43, 0x0102a728) | 0x01 | 0x59 | 4 | 13 LEFT ORBIT (CLU), 14 (LIGHT CYCLE), 15 (DISC), 16 L. LOOP ARROW |
| 1 | Left ramp (sw37 exit, 0x0102a940 / 0x0102a948 / 0x0102a9bc) | 0x02 | 0x5a | 3 | 11 LEFT RAMP (LIGHT CYCLE), 50 LEFT RAMP (DISC), 49 LEFT RAMP ARROW |
| 2 | Left inner loop (sw44 left spinner, first closure; 0x01029ba4) | 0x04 | 0x5b | 5 | 60 ADVANCE QUORRA, 61 L. INNER LOOP (CLU), 62 (LIGHT CYCLE), 63 (DISC), 64 L. INNER LOOP ARROW |
| 3 | Right inner loop (sw39, 0x0102ae3c / 0x0102ae44) | 0x08 | 0x5c | 3 | 59 R. INNER LOOP (LIGHT CYCLE), 58 (DISC), 57 R. INNER LOOP ARROW |
| 4 | Right ramp (sw34 exit, 0x0102aa50 / 0x0102aa58 / 0x0102aad8) | 0x10 | 0x5d | 3 | 42 R. RAMP (LIGHT CYCLE), 55 RIGHT RAMP (DISC), 56 R. RAMP ARROW |
| 5 | Right orbit (sw46, 0x0102a794) | 0x20 | 0x5e | 4 | 36 RIGHT ORBIT (CLU), 35 (LIGHT CYCLE), 34 (DISC), 33 R. LOOP ARROW |
| 6 | Disc (sw41 DISC OPTO, 0x0102ab6c) | 0x40 | none | 0 | — |

Shot detection belongs to the switch handlers (other files), but note: the left inner loop counts
once per spin (task 100 re-arms after 62 ticks with no spinner closure); orbits ignore the
opposite orbit switch for 187 ticks (ball passing through) and their own switch for 125 ticks;
the disc opto ignores a second closure within 125 ticks. In the emulator, left-orbit hits shortly
after an auto-launched ball were not counted as orbit shots (traces/portal_multiball_shots.jsonl,
two hits lost), so a launched ball going round the orbit is filtered somewhere (not traced).

## 4. How it starts (qualifying / lighting)

1. **Lit** = all 9 items collected: byte 1 of each item word non-zero [0x0101643c]. How items get
   collected is the items / Sea of Simulation file (Sea of Simulation stages collect them; the
   item modes do too).
2. **Startable** [0x0102f434] = lit AND no multiball running (`FUN_0100f918`: End of Line, Disc,
   Light Cycle, Quorra, Portal) AND Disc multiball start task 0xad not running AND Sea of
   Simulation not running (flag 0x34).
   While startable: leff 163 fades lamp 40 EJECT: PORTAL in and out (8-tick steps), leff 164 pulses
   coil 18 FLASH: VIDEO GAME every 8 ticks, tube show 79 (idle) runs [rules in 0x01030ed0].
3. **Start** when a ball enters the VUK (sw11, `on_vuk` 0x0102eddc). Portal is checked after the
   Flynn's Arcade award and **before** Sea of Simulation and End of Line in the VUK handler.

On start [0x0102f474]:
- `multiball_start(balls_in_play == 0 ? 4 : balls_in_play + 3, ball save 0x3a9 = 937 ticks
  (15.2 s), grace 0x138 = 312 ticks (5.1 s))`: a **4-ball multiball** (capped at the 4 installed
  balls). (verified in emulator: `multiball_start balls=4 save_ticks=937 grace_ticks=312`, 3 balls
  ejected and launched)
- Read flag 0x33 (Sea of Simulation started since the last Portal).
- All 7 shot counters = 0, `pm_super_value = 1,000,000`, `pm_phase = 0`.
- If no multiball is running (always true here): clear game flag 0x32 (meaning unknown).
- Set flag 0x37; `pm_starts_this_ball += 1`.
- Reset all 9 items (lit and collected bytes) for this player [0x01016164]; clear SoS byte
  0x2111804[player-1] [0x01026f4c]; clear flag 0x33.
- Audit 0x89. Score **1,000,000**; `pm_total` = that.
- If flag 0x33 was clear: score **50,000,000** (the Sea of Simulation bonus).
- Task 0xa5 queues the intro deff 140 (waits for display priority, up to 3750 ticks), passing
  the total and the 50M bonus (0 if not given) [0x0102f408].
- Kill tasks 0xad-0xaf (Disc multiball start/battle tasks) [0x010078c8].
- Register the background rule (deff 141 + music) [0x01030188].
(verified: `score_add 1000000`, `score_add 50000000`, flag 55 set, flag 50 and 51 cleared, audit 137)

## 5. Behaviour while running

`portal_mb_shot(shot)` [0x0102f6c8] is the first rules hook in each shot handler (before
simulation, CLU, Disc MB, Quorra, Light Cycle, combos, Find Flynn, ZUSE, End of Line). It acts
while flag 0x37 is set OR grace task 0xd2 runs [0x0102f694].

Award value [0x0102f5f4]: `A = min(500,000 + 50,000 x S, 1,500,000)` where S = sum of all shot
counters **before** this shot.

### Phase 0: make the shots

| Trigger | Condition | Effect | Display | Sound | Lamp / leff | Next state |
|---|---|---|---|---|---|---|
| Shot 0-5 | counter < max | score A; counter += 1; `pm_super_value += A`; `pm_total += A`; audit 0x8a; if counter reached max: add a ball (`balls_in_play + 1`, save 62 ticks, grace 62 ticks; restarts the mode if in grace) | deff 142: animation + value (args: value, new count, ball-added flag) | in deff: 0x079, then 0x07a (twice) | leff 168, tube show 82 | if all 6 shots are at max: phase 1 |
| Shot 0-5 | counter = max | nothing | — | — | — | — |
| Disc | phase 0 | nothing (max 0) | — | — | — | — |

Verified (traces/portal_multiball_shots.jsonl, multiplier 1): awards 500,000, 550,000, 600,000
(left orbit 1-3), 650,000-750,000 (left ramp, 3rd adds a ball: `multiball_start balls=5 save=62 grace=62`),
800,000-1,000,000 (left inner loop x5), 1,050,000-1,150,000, 1,200,000-1,300,000, 1,350,000-1,500,000
(right orbit 4th = 1,500,000, the cap). A 4th left ramp scored nothing. `pm_super_value` reached
22,000,000 after 21 shots. With one left-orbit hit missing the disc stayed unlit (no super).

Sum check, multiplier 1: the 22 awards total 22,500,000, so a full run gives a Super of 23,500,000.

### Phase 1: Super Jackpot lit at the disc

| Trigger | Condition | Effect | Display | Sound | Lamp / leff | Next state |
|---|---|---|---|---|---|---|
| Disc (sw41) | phase 1 and all shots complete [0x0102f37c] | score `pm_super_value` (x multiplier again); `pm_total += it`; audit 0x8b | deff 143 "SUPER / JACKPOT" + value (8.9 s) | 0x07b; 0x07c at 2nd-loop frame 20; speech 0x07d at frame 40 | leff 169, tube show 83 | phase 2 |
| Shots 0-5 | phase 1 | nothing | — | — | — | — |

### Phase 2: all shots 1,000,000

| Trigger | Condition | Effect | Display | Sound | Lamp / leff | Next state |
|---|---|---|---|---|---|---|
| Any of the 7 shots incl. the disc | phase 2 | score 1,000,000; `pm_total += it`; audit 0x8c | deff 144: value on a lit screen (2.2 s) | 0x07e; 0x07f at frame 20 | leff 170, tube show 84 | phase 2 |

The phase-1 and phase-2 results were checked with the state-jump trace
(traces/portal_multiball.jsonl): see section 10.

### Add-a-ball summary

One ball per completed shot (6 possible), each with a 62-tick (1.0 s) save; the ball count never
exceeds the 4 installed balls (`multiball_start` caps it), so with 4 balls in play nothing is added
but the request still restarts a mode in grace.

### Background (rule 0x01030150, list 2, priority 7)

While flag 0x37 is set (and the intro is not still pending: task 0xa5 running with deff 140 not
yet shown): deff 141 status screen and music call **0x076** (sample 0x459, 55.2 s) [0x01030ed0].
Deff 141 (4-tick frames): "PORTAL MULTIBALL"; phase 0: "NEXT SHOT=<A>" and "SUPER=<super>";
phase 1: "SUPER JACKPOT LIT" (blinking), "SHOOT DISC", "SUPER=<super>"; phase 2:
"ALL SHOTS=1,000,000" (blinking). The same rule runs leff 166 (shot lamps) and tube show 81
(both ramp tubes fade white in/out, 31 ticks each way). While all shots are complete (phase 1
and also phase 2, the test does not check the phase) leff 167 pulses coils 26/27 FLASH: DISC
(LEFT/RIGHT) every 8 ticks [0x0102f37c rule], and the disc feature's leff 76 rule also fires
(0x01006610, inferred to request disc spinning/lights).

## 6. How it ends

- **One ball left**: the trough handler (`FUN_0101bbc0` event 0xe -> 0x0101bcec) calls
  `FUN_0102f8b8`: clear flag 0x37, start task 0xd2 = sleep **0x138 = 312 ticks (5.07 s)**, then
  show the total. During those 312 ticks shots still score in the current phase, and completing a
  phase-0 shot (add-a-ball) restarts the mode (flag set again, task killed) [0x0102f8fc].
  Measured: flag 0x37 cleared 0.53 s after the third drain, deff 145 5.10 s later
  (traces/portal_multiball_shots.jsonl).
- **Total**: if `pm_total != 0` and the game is not tilted / over (`DAT_00037274 & 0x310`), task
  0x57 shows deff 145 "PORTAL MULTIBALL / TOTAL:" + `pm_total` (3.0 s) [0x0102f94c].
- **End of ball / tilt** (event 0x1d, 0x0102f9a4): if running or in grace: clear flag, kill task
  0xd2, show the total (not when tilted).
- **End-of-ball bonus** [0x01000cf8, 0x01000e7c]: a "PORTAL +value" line with
  `value = 2,250,000 x pm_starts_this_ball`, part of the bonus that is multiplied by the bonus
  multiplier (0x21115d3[player]). Shown with leff 31 and tube show 103.
- Carried over: items are reset (start again from zero), `pm_starts_this_ball` until the next
  player turn, flag 0x33 cleared. Shot counters and phase are re-initialised at the next start.

## 7. Media

| When | Display effect | Sound calls | Lamp effect (leff) | Ramp tube show |
|---|---|---|---|---|
| Lit | — | — | 163 (lamp 40 fade), 164 (coil 18 pulse) | 79 (idle) |
| Start (intro) | deff 140 (prio 192, ~5 s) [0x0102faec]: animation 0x1b55-0x1b97 at 2 ticks/frame with "%,02lu / SEA OF SIMULATION / BONUS" only when the 50M bonus was given; then "PORTAL / MULTIBALL" blinking 21 x 3 ticks; then "COMPLETE ALL SHOTS / FOR / SUPER JACKPOT" blinking 35 frames, hold 2 | 0x077 (sfx 0x01f) at start; speech 0x078 (0x116) before the 3rd part | 165 (flashers, coil 18 pulses + group pulses) | 80 |
| Running | deff 141 (prio 1, background) | music 0x076 (0x459) | 166 shot lamps (section 8), 167 when all shots done | 81 |
| Shot award | deff 142 (prio 193, 3.4 s): animation 0x1d56-0x1d78 at 3 ticks, then the value blinking 31 x 3 ticks, hold 10 | 0x079 (sfx 0x09c/0x09d/0x09e), 0x07a (0x05f/0x060) at value frame 0 and 10 | 168 (flasher bursts) | 82 |
| Super Jackpot | deff 143 (prio 195, 8.9 s): animation 0x1f29-0x1fac at 2 ticks, then "SUPER / JACKPOT" + value 91 x 3 ticks | 0x07b, 0x07c (frame 20), speech 0x07d (0x150/0x151, frame 40) | 169 | 83 |
| Phase-2 award | deff 144 (prio 194, 2.2 s): value on a filled screen, 41 x 3 ticks | 0x07e, 0x07f (frame 20) | 170 | 84 |
| End | deff 145 (prio 196, 3.0 s): "PORTAL MULTIBALL / TOTAL:" + total blinking | 0x080 (sfx 0x052) | 171 | 85 |

All of 142-145 and 140 run the shaker (`shaker_run`, adj 86). The `mpf_package` names
(`deff_140_portal_multiball_intro`, `deff_141_portal_multiball_running`, `deff_142_portal_shot`,
`deff_143_portal_super_jackpot`, `deff_144_portal_jackpot`, `deff_145_portal_total`) match; note 144
is the phase-2 "all shots" award, not a jackpot. Their `leff_NNN` entries are tube shows
(asset_audit M1); the lamp leffs listed above are not in the package.

## 8. Lamps

leff 166 [0x01030198] owns the shot lamps while the mode runs (3-tick blink):
- **Phase 0**: lamp group 0x5f (17 CENTER PORTAL and the 9 CENTER item lamps 18-25, 27) solid on.
  For each shot group (table above): lamp i (in group order) is on if i < hits, blinking if
  i == hits, off if i > hits. So each shot shows its progress and the next lamp blinks.
- **Phase 1**: the shot groups are released (normal lamps show through); group 0x5f fades in and
  out (8-tick steps).
- **Phase 2**: group 0x5f solid; all six shot groups blink together.
Lamp 40 EJECT: PORTAL fades (leff 163) while Portal is lit and startable.

## 9. Interactions

- **Stacking**: none. Portal cannot start while any multiball or Sea of Simulation runs, and every
  other multiball's lighting/start test checks `FUN_0102f680` (Portal running) or
  `FUN_0100f918` (any multiball): Light Cycle 0x0101860c / 0x0101b0dc, Quorra 0x0101f2f8 / 0x0101f384,
  disc rule 0x01020b4c and 0x0101ffd8, End of Line 0x01004c68, Find Flynn 0x0100d654, CLU eject
  0x01001c98, and others (0x01013980, 0x0101688c, 0x0101cc04 Big Bumps, 0x01033744).
- **Sea of Simulation**: both start at the VUK; Portal is tested first. Sea of Simulation
  starting sets flag 0x33, which cancels the next Portal's 50M bonus.
- **End of Line (Daft Punk)**: if both are lit, Portal starts first and End of Line stays lit.
  The DAFT/PUNK letters do not advance while Portal runs, but do during its grace (verified: deff
  55 on a ramp in the grace).
- **Disc multiball**: Portal start kills the Disc multiball start tasks 0xad-0xaf.
- **Tilt**: ball end clears the mode, no total display.
- Ball save is the standard multiball save (section 4); add-a-ball saves are 62 ticks.

## 10. Reference scenario

Two traces, made with the fixed shared tron_ref.

1. `traces/portal_multiball.txt` / `.jsonl` (main reference, **state jump**): pokes the 9 item
   "collected" bytes (0x2111695 + 16 x item = 1), starts Portal at the VUK, waits for the balls,
   pokes the shot counters to 3/3/5/3/3/4 (one left orbit missing), makes the last left orbit,
   a left ramp while the Super is lit, the disc Super, a phase-2 left ramp and disc, drains to one
   ball, shoots a ramp in the grace and drains the last ball.
   Expected: start `multiball_start balls=4 save_ticks=937 grace_ticks=312`, `score_add 1000000`,
   `score_add 50000000`, deff 140, deff 141 + sound 0x076; last left orbit `score_add 1500000`
   (S = 20, capped), `pm_phase 1`; left ramp: no Portal score; disc: `score_add` = pm_super_value
   (2,500,000), deff 143, `pm_phase 2`; phase-2 shots `score_add 1000000` + deff 144; grace
   ramp `score_add 1000000`; deff 145 about 5.1 s after the mode drops to one ball.
2. `traces/portal_multiball_shots.txt` / `.jsonl` (natural shots, only the item pokes): 21 of the
   22 shots with every award value listed in section 5, add-a-ball requests, no Super because two
   left-orbit hits were filtered after ball launches, grace and total at 22,000,000, end-of-ball bonus.

## 11. Open questions

- Game flag 0x32 is cleared at Portal start; no code that sets it was found.
- 0x021118a0 (static lamp 40 gate) and 0x021118a8 have no setter / reader found.
- `is_tilted()` in leffs 164/167 probably means "flashers allowed" (they pulse in normal play);
  name kept from the decompile.
- Exact item-collection rules (what collects an item) are not covered here.
