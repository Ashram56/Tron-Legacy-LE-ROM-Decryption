# Light Cycle Multiball

Stern Tron Legacy LE 1.74. Sources are function addresses in `tron/code/tron_game_decompiled_v2.c`
unless marked `[table ...]`. Emulator runs: `traces/light_cycle_multiball.*` (natural lighting, full
jackpot chain, timeout + grace, end) and `traces/light_cycle_multiball_repeat_and_stack.*` (6-shot repeat
lighting, LC + Quorra started together). 1 tick = 16.26 ms.

## 1. Summary

Six major shots carry a "Light Cycle" insert. Make 4 different ones (6 on every later attempt) and Light
Cycle Multiball is lit at the VUK (Flynn's Arcade scoop). Entering the VUK starts a 2-ball multiball worth
150,000. Three shots are lit for a 350,000 Jackpot (left ramp, right orbit, right ramp). A Jackpot briefly
(about 5 s) lights Super Jackpot shots (750,000); from the left ramp chain, a Super on the left inner loop
lights Double Super Jackpot (1,500,000) on the right inner loop / right ramp. The mode ends when one
ball is left, but lit shots keep scoring for about 5 s more, then the multiball total is shown.

## 2. Settings (operator adjustments)

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| none | | | | No adjustment is read by any Light Cycle function (no `adj_get` in 0x01018174-0x0101b5b4). Values below are constants. [0x01018804] [0x0101b26c] |

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| lc_lit | 0x0211189c +(player-1), 1 B | per player | 0 at player init (event 0x26 handler 0x010181b8 calls `lit_item_take(4)`); set to 1 when lit (capped at 1); back to 0 when the MB starts | Light Cycle MB lit at the VUK. Part of the shared "lit items" block 0x02111894 (1=?, 2=Quorra, 4=Light Cycle, 8=Portal, 0x10=CLU) [0x0102e8c0] [0x0102eaa4] [0x0102ec38] |
| lc_remaining_mask | 0x02111744 +(p-1), 1 B | per player | 0xcf at player init and every time LC is lit [0x01018174] | progress shots not yet made: 0x01 left orbit, 0x02 left ramp, 0x04 left inner loop, 0x08 right inner loop, 0x40 right ramp, 0x80 right orbit |
| lc_collected_mask | 0x02111754 +(p-1), 1 B | per player | 0 at player init / when lit [0x01018174] | progress shots made since last lighting |
| lc_starts | 0x02111764 +(p-1), 1 B | per player | 0 at player init [0x010181bc]; +1 per MB start, capped 255 [0x0101b26c] | 0 means 4 shots needed, otherwise 6 [0x010186bc] |
| lc_super_points | 0x02111768 +(p-1), 1 B | per player | 0 at player init; += level-1 on each award (Super +1, Double Super +2), capped 255 [0x01018804] | not read by Light Cycle code (other features may) |
| lc_clip_level / lc_clip_index | 0x0211176c / 0x02111774 (u16 per player) | per player | 0 at player init | cosmetic: which jackpot art clip deff 87 uses; level +1 per Double Super (wraps to 0 after 5) [0x01018804] [table 0x040d2ffc] |
| lc_a_lit / lc_a_level | 0x0003b280 (4 B) / 0x0003b28c (1 B) | while mode runs | 0x02 / 1 at MB start [0x0101b15c] | chain A lit shots and their award level (1 Jackpot, 2 Super, 3 Double Super) |
| lc_a_prev / lc_a_prev_level | 0x0003b284 / 0x0003b290 | while mode runs | 0 at start; set on timeout, cleared 125 ticks later [0x0101830c] [0x010182ec] | chain A shots still accepted in the grace period |
| lc_a_timer | 0x0003b288 | while mode runs | 312 when a chain A timer starts [0x010183a0] | remaining ticks, task 0xba counts it down by 7 every 7 ticks |
| lc_b_lit / lc_b_level / lc_b_prev / lc_b_prev_level / lc_b_timer | 0x0003b294 / 0x0003b2a0 / 0x0003b298 / 0x0003b2a4 / 0x0003b29c | while mode runs | 0x80 / 1 / 0 / 0 / 0 at start [0x0101b15c] | chain B, same layout, task 0xbc [0x010184b0] [0x01018544] |
| lc_c_lit / lc_c_level | 0x0003b2a8 / 0x0003b2b4 | while mode runs | 0x40 / 1 at start, never changed | right ramp is always a Jackpot shot. 0x0003b2ac/0x0003b2b0/0x0003b2b8 are a third chain's prev/timer/level that nothing ever sets (task 0xbe is never created) [0x0101b15c] [0x0101aecc] |
| lc_mb_super_points | 0x0003b2bc, 1 B | while mode runs | 0 at start | sum of (level-1) this MB; while it is above 2, every Super/Double Super also bumps the "items collected: Light Cycle" stat [0x01018804] |
| lc_total | 0x0003b2c0, 4 B | while mode runs | = points of the start award at start [0x0101b26c] | every award adds the points actually scored; shown by deff 90 at the end |
| game flag 0x2b | | while mode runs | set at start, cleared when one ball is left or at end of ball | "Light Cycle MB running" [0x01018240] |
| tasks 0xb8 → 0xb9 | | end window | created at end [0x0101b418] | 312 ticks (id 0xb8) then 125 ticks (id 0xb9) in which lit shots still score and the MB can resume |

## 4. How it starts (qualifying / lighting)

1. **Progress is open** when all of these hold: LC MB not running (flag 0x2b), Disc MB not running (flag
   0x24) and no Disc restart window (task 0xad), Simulation not running (flag 0x34), Portal MB not running
   (flag 0x37), LC not already lit, Daft Punk MB not running (flag 0x27). Quorra MB does **not** block it.
   [0x0101860c]
2. **Progress shots** (each counts once per lighting; repeats of an already-made shot do nothing):
   left orbit sw43 (mask 0x01), left ramp sw37 exit (0x02), left inner loop = first left spinner sw44 pulse
   (0x04; further spins within 62 ticks of the last one are spins, not loops [0x01029b54]), right inner
   loop sw39 (0x08), right ramp sw34 exit (0x40), right orbit sw46 (0x80). An orbit switch hit within
   125 ticks of the opposite orbit switch is a ball passing through and is not a shot. [0x0102a808]
   [0x0102a8a4] [0x01029ba4] [0x0102a940] [0x0102aa50] [0x0102ae3c] [0x010186bc]
   (verified in emulator: traces/light_cycle_multiball.jsonl)
3. **Shots needed** = 4 if the player has never started LC MB this game (lc_starts = 0), else 6, i.e.
   all six. [0x010186bc] (verified in emulator: traces/light_cycle_multiball_repeat_and_stack.jsonl)
4. A progress shot that does not yet light: deff 83 "`N` MORE / TO LIGHT / LIGHT CYCLE" with
   N = needed - made. No score from Light Cycle itself (the shot's own switch score still applies).
   [0x010186bc] [0x01018ba0]
5. The shot that reaches the count: `lit_item_add(4)` sets lc_lit = 1, the masks reset (0xcf / 0), deff
   84 "LIGHT CYCLE / MULTIBALL / IS LIT" with sfx 0x0bf then speech 0x0c0. [0x010186bc] [0x01018e48]
6. While lit, progress stops and the six progress inserts go dark; lamp 38 EJECT: LIGHT CYCLE is lit
   (only while a start would be allowed, see 5). [0x0101b4fc] [0x0102f024]
7. Flynn's Arcade award "ADV. LIGHT CYCLE" makes the first open progress shot in the order LO, LR,
   LIL, RIL, RR, RO, silently (no deff 83, deff 84 suppressed). [0x0100e184] [table 0x040d2978]
   (inferred: award id mapping from asset_audit W1)

### Start at the VUK (sw11)

The VUK handler (0x0102eddc) runs, in order: Flynn's Arcade award, Portal, Simulation, CLU, **Light
Cycle**, Quorra. Light Cycle starts if lc_lit was set when the ball entered and `lc_can_start`:
flag 0x2b clear, Disc MB not running and no Disc restart window, not (all 9 items started and
Simulation available), Simulation not running, not (Portal start condition), Portal not running, Daft
Punk not running. [0x0101b368] [0x0101b0dc]

On start [0x0101b26c]:
- `multiball_start(balls, 0, 625, 125)` where balls = balls in play + 1, or 2 when no ball is in play
  (the VUK ball is not "in play" while held), so normally **2 balls**. Ball save **625 ticks (10.2 s)**
  with the shoot-again lamp effect (leff 13), then **125 ticks (2.0 s)** grace without the lamp. If
  another multiball request is pending the larger ball count / timers win. [0x0001ed7c]
  (verified in emulator: multiball_start balls=2 save_ticks=625 grace_ticks=125)
- flag 0x2b set; lc_starts +1; lc_lit -1 (to 0); stat "items lit: Light Cycle" +1 (audit 0x74);
  audit 0x4a LIGHT CYCLE MULTIBALL STARTED.
- **150,000** x playfield multiplier (`score_add`); lc_total = the points scored.
- chains reset (A: left ramp, level 1; B: right orbit, level 1; C: right ramp, level 1); lc_mb_super_points = 0.
- task 0x92 queues the intro deff 85 behind whatever the VUK shows first (deff 105 arcade award etc.).
- Disc MB restart window is cancelled (tasks 0xad-0xaf killed) [0x010078c8]; if Quorra MB ended less
  than 437 ticks ago it is resumed [0x0101f7e8].

## 5. Behaviour while running

All awards go through `lc_mb_shot(mask)` [0x01018804], called from the same six shot handlers as the
progress shots. It runs while flag 0x2b is set **or** during the end window (tasks 0xb8/0xb9).

Lookup order for the shot's mask: chain A grace mask, chain B grace mask, (unused C grace), chain A lit
mask, chain B lit mask, chain C (right ramp). The first match gives the level:

| Level | Award (x playfield multiplier) | Audit | Deff |
|---|---|---|---|
| 1 Jackpot | 350,000 | 0x4b LIGHT CYCLE MULTIBALL JACKPOTS | 87 |
| 2 Super Jackpot | 750,000 | 0x4c LIGHT CYCLE MBALL SUPER JACKPOTS | 88 |
| 3 Double Super Jackpot | 1,500,000 | 0x4d LIGHT CYCLE MBALL 2X SUPER JPS | 89 |

Values are fixed: they do not grow. (verified in emulator: 350000 / 750000 / 1500000)

### Chain A (starts on the left ramp) [0x010183a0] [0x0101830c]

| Trigger | Condition | Effect | Display | Sound | Lamps | Next state |
|---|---|---|---|---|---|---|
| sw37 left ramp | A lit = left ramp, level 1 | Jackpot 350,000 | deff 87 | deff: 0x0c5, 50 % speech 0x0c7, 0x0c6 | leff 95, tube 55 | A lit = left orbit + left inner loop (0x05), level 2, timer 312 ticks |
| sw43 left orbit | A at level 2 | Super 750,000 | deff 88 | 0x0c8, 0x0c9 | leff 96, tube 56 | back to left ramp, level 1, timer stopped |
| sw44 left inner loop | A at level 2 | Super 750,000 | deff 88 | 0x0c8, 0x0c9 | leff 96, tube 56 | A lit = right inner loop + right ramp (0x48), level 3, timer restarted at 312 |
| sw39 right inner loop or sw34 right ramp | A at level 3 | Double Super 1,500,000 | deff 89 | 0x0ca, 0x0cb | leff 97, tube 57 | back to left ramp, level 1, timer stopped; lc_clip_level +1 |
| timer runs out | | A lit = left ramp, level 1; the old lit shots/level are kept as the grace mask for 125 ticks | | | | grace ends: grace mask cleared |
| a grace shot | within 125 ticks after timeout | award at the old level and the chain advances from that level as above | | | | |

Timer: 312 ticks counted down in steps of 7 ticks, so it lasts 315 ticks (5.1 s; measured 5.16 s),
then 125 ticks (2.0 s) of grace (measured 2.04 s). (verified in emulator: traces/light_cycle_multiball.jsonl,
marks jackpot_left_ramp_then_timeout / grace_left_orbit)

### Chain B (starts on the right orbit) [0x01018544] [0x010184b0]

| Trigger | Condition | Effect | Display | Next state |
|---|---|---|---|---|
| sw46 right orbit | B at level 1 | Jackpot 350,000 | deff 87 | B lit = right inner loop + right ramp (0x48), level 2, timer 312 ticks |
| sw39 right inner loop or sw34 right ramp | B at level 2 | Super 750,000 | deff 88 | back to right orbit, level 1, timer stopped |
| timer runs out | | B back to right orbit level 1; old shots accepted 125 ticks as grace | | |

Chain B never reaches a Double Super.

### Chain C: right ramp (sw34) is always a Jackpot (350,000)

unless chain A level 3 or chain B level 2 currently claims it (those are checked first). The right
inner loop scores nothing when neither chain has it lit.

### Common effects of every award [0x01018804]

- audit for the level +1; lc_total += points scored; lc_super_points (per player) and
  lc_mb_super_points += level-1; if lc_mb_super_points > 2, stat "items collected: Light Cycle"
  (audit 0x75) +1, on every award from then on (verified: audit 117 = 0x75 on each award after the
  first Double Super).
- the deff gets the points scored (shown "%,02lu") in its argument.
- The shot's normal switch score and every other feature hooked on that shot still run
  (e.g. the left spinner adds 10,000 and Quorra progress, the right inner loop also runs Recognizer
  logic that scored 250,000 + deff 75 in the trace; those belong to other features).

Interaction with progress: progress (section 4) is blocked while flag 0x2b is set, but **open during the
end window**, so the same shot can score a late Jackpot and count as a progress shot for the next LC
(verified: late right-orbit shot gave Jackpot + deff 83 3.1 s after the MB ended).

## 6. How it ends

- **One ball left**: the trough device handler, on a ball entering the trough, calls the multiball-end
  routine when fewer than 2 balls remain in play [0x0101bbc0 case 0xe] → [0x0101bcec] → `lc_mb_end`
  [0x0101b444]: flag 0x2b cleared, task 0xb8 started.
- **End window** [0x0101b418]: 312 ticks (task 0xb8), then 125 ticks (task 0xb9) = 437 ticks (7.1 s).
  During it lit shots still score (section 5), and if Quorra MB starts or a Quorra add-a-ball is
  awarded, Light Cycle MB **resumes** (flag set again, chains keep their state) [0x0101b488].
  When the window expires (and no tilt / game-over flags 0x310 are set) the total is shown:
  task 0x52 → deff 90 with lc_total. (verified in emulator: flag clear at 54.70 s, deff 90 at 61.84 s)
- **End of ball** (event 0x1d) while running or in the window: flag cleared, window killed, total shown
  (unless tilted). [0x0101b4cc] [0x0101b3c0]
- No award at the end besides the total screen. lc_starts, lc_super_points and progress masks carry over
  per player; the chains do not.

## 7. Media

| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| progress shot, not yet lit | deff 83: "%d MORE" (blinking) / "TO LIGHT" / "LIGHT CYCLE", light-cycle bitmap 0xf65-0xf67 or 0xf68-0xf6a sliding (direction by shot side), 59 frames x 2 ticks | none in deff (shot sfx is the switch's) | leff 91 | 51 |
| LC lit | deff 84: anim 0xb8d-0xbbf, "LIGHT CYCLE / MULTIBALL / IS LIT" colour cycling 10 frames, then 20 frames blinking "IS LIT" | 0x0bf sfx (0x0cd-0x0cf) at start, 0x0c0 speech (0x127) | leff 92 | 52 |
| MB start (queued behind VUK displays) | deff 85: clip 0xb1c-0xb8c (161 frames x 2 ticks), "LIGHT CYCLE / MULTIBALL" blinking from frame 107; alternative short version (image 0xb8c, 91 frames) when its arg >= 2 (never seen) | 0x0c3 speech at frame 10, 0x0c1 sfx at frame 24 (alt: 0x0c4) | leff 93 | 53 |
| MB running (background) | deff 86 (mode rule, see below): looping light-cycle art 0xfa7-0xfb1 with clip overlay, "LIGHT CYCLE / MULTIBALL" | music 0x0c2 (sample 0x454) | leff 94 (lit shot lamps, see 8) | 54 |
| Jackpot | deff 87: random clip (table 0x040d3084, range from 0x040d2ffc by lc_clip_level), "JACKPOT" + value blinking, 21 x 4 ticks; shaker | 0x0c5 sfx, 50 % 0x0c7 speech, 0x0c6 sfx | leff 95 | 55 |
| Super Jackpot | deff 88: "SUPER JACKPOT" + value | 0x0c8 sfx, 0x0c9 speech | leff 96 | 56 |
| Double Super Jackpot | deff 89: "DOUBLE / SUPER JACKPOT" + value | 0x0ca sfx, 0x0cb speech | leff 97 | 57 |
| End total | deff 90: "LIGHT CYCLE / MULTIBALL / TOTAL:" + lc_total | 0x0cc sfx, 0x0cd speech | leff 98 | 58 |

Mode rule registration [0x0101b5b4]: background deff 86 + music 0x0c2 (`lamp_rule_init(...,0x56,0xc2,...,7)`),
leff 94 and tube show 54 while `lc_mb_rule_active` (flag 0x2b set, and not while the intro task 0x92 waits
for deff 85) [0x0101ac3c]. Sound/deff ids verified in emulator (traces/light_cycle_multiball.jsonl).
Package names: deffs 83-90 exist in mpf_package; its `mode_by_code_location` column is unreliable
(asset_audit M2); sound calls 0x0bf-0x0cd all have samples (none in the W5 missing list).

## 8. Lamps

Light Cycle shot inserts [table 0x040d3104 / 0x040d3134, lamp group 0x28]: 14 LEFT ORBIT, 11 LEFT RAMP,
62 L. INNER LOOP, 59 R. INNER LOOP, 42 R. RAMP, 35 RIGHT ORBIT (all "(LIGHT CYCLE)").

| State | Lamps |
|---|---|
| progress open | inserts of shots not yet made are on (rule layer; shows as fast blinking ~85 ms in the emulator); made ones off [0x0101b4fc] |
| lit / progress blocked | all six off; 38 EJECT: LIGHT CYCLE on (rule layer, blinks ~82 ms in emulator) while a start is possible [0x0102f024] |
| MB running | leff 94: three layers, one per chain, flash the inserts in that chain's lit mask. Flash half-period 6 ticks (98 ms) when no timer runs; while a chain timer runs it is remaining/31 ticks, clamped 2-10 ticks, so it speeds up as the Super / Double Super window closes [0x0101ac84] [0x0101ada8] [0x0101aecc] |

## 9. Interactions

- **Blocks / blocked**: start needs no Disc MB (or its restart window), Simulation, Portal MB or Daft
  Punk MB running [0x0101b0dc]. Starting LC cancels a pending Disc MB restart window [0x010078c8].
- **Quorra MB** does not block LC and vice versa: both progresses run during the other's multiball, and
  one VUK entry can start both (LC first, then Quorra; the second `multiball_start` raises the ball
  count to balls in play + 1 = 3). (verified in emulator:
  traces/light_cycle_multiball_repeat_and_stack.jsonl). Starting either resumes the other if it is in
  its end window [0x0101b488] [0x0101f7e8].
- Shot hook order on each shot (e.g. left inner loop): Portal, Simulation, CLU hurry-up, Disc MB,
  Quorra MB, **LC MB award**, **LC progress**, Quorra progress, combos, Find Flynn [0x01029ba4].
- Playfield multiplier applies to every award and to the start award (`score_add`).
- Tilt / game over: `multiball_start` refuses while game-state bits 0x214 are set; totals are not shown
  when bits 0x310 are set [0x0001ed7c] [0x0101b3c0].
- Stats for wizard qualification: item 6 "lit" at start (audit 0x74), "collected" when
  lc_mb_super_points > 2 (audit 0x75) [0x01016188]. These per-player bytes (0x02111694 + 6*16) are read by
  `all_items_started/collected` [0x010163ec] [0x0101643c] (other workers: Simulation / End of Line).

## 10. Reference scenario

`traces/light_cycle_multiball.txt` (trace `.jsonl`), times from `ready`:

| t (s) | input | expected |
|---|---|---|
| 6.75-11.11 | sw37, sw34, sw43 | deff 83 each (3, 2, 1 more) |
| 14.28 | sw46 | lc_lit=1, deff 84, sound 0x0bf then 0x0c0 |
| 18.48 | sw11 | arcade award first (random), then multiball_start 2/625/125, flag 0x2b, audit 0x4a, score_add 150000; deff 85 at 21.3 with 0x0c3, 0x0c1; music 0x0c2 |
| 28.76 | sw37 | score_add 350000, deff 87, audit 0x4b |
| 30.95 | sw44 | 750000, deff 88, audit 0x4c, A -> 0x48 |
| 33.12 | sw39 | 1500000, deff 89, audit 0x4d |
| 36.29 | sw46 | 350000 (chain B) |
| 38.47 | sw34 | 750000 (chain B Super) |
| 41.65 | sw34 | 350000 (chain C) |
| 44.82 | sw37 | 350000; timeout at 50.00 (grace mask 0x05) |
| 50.99 | sw43 | 750000 (grace Super) |
| 54.17 | drain (1 ball left) | flag 0x2b cleared at 54.70 |
| 57.29 | sw46 | late Jackpot 350000 + LC progress (deff 83) |
| 61.84 | | deff 90 total 5,650,000, sound 0x0cc |

The second scenario pokes lc_starts (0x02111764) = 1 and shows deff 84 only on the 6th distinct shot, then
pokes quorra_lit (0x02111898) = 1 and starts both multiballs with one VUK entry.

Note: the shipped `tron_ref` received no coil callbacks for coils 1-32 in this build, so the trough never
ejected and `drain` was ignored. The traces were made with a copy that polls `PinmameGetSolenoid()` every
step (same scenario syntax).

## 11. Open questions

- deff 85 / deff 87 alternative branches: deff 85 has a short version when its argument is >= 2; task
  0x92 always passes 1, so when the short version plays was not found.
- Exact start of the ball-save countdown: it runs only while event 0x41 handlers allow it (held VUK
  ball, intros); the emulator ball model cannot show when the save really expires.
- What reads lc_super_points (0x02111768) was not traced (not Light Cycle code).
- Flynn's Arcade "ADV. LIGHT CYCLE" mapping to 0x0100e184 is from the award table layout, not traced in
  emulation.
