# Quorra Multiball

Stern Tron Legacy LE 1.74. Sources are function addresses in `tron/code/tron_game_decompiled_v2.c`
unless marked `[table ...]`. Emulator runs: `traces/quorra_multiball.*` (natural lighting, start,
jackpots, super, add-a-ball, VUK during MB, end window) and
`traces/light_cycle_multiball_repeat_and_stack.*` (Quorra + Light Cycle started together).
1 tick = 16.26 ms. The asset package's `mode_by_code_location` column files the Quorra deffs under
Light Cycle; ignore it (asset_audit M2).

## 1. Summary

Shoot the left inner loop 5 times to light Quorra Multiball at the VUK (Flynn's Arcade scoop). The VUK
starts a 2-ball multiball worth 200,000. The left inner loop scores the Jackpot (350,000 on the first
Quorra MB, +25,000 each later MB and each Jackpot, max 500,000); every Jackpot also raises the Super
Jackpot, which is always lit on the right inner loop (starts at 1,000,000). Three hits on the Recognizer
3-bank add a ball (up to 2 times). The mode ends when one ball is left; shots keep scoring for about 5 s,
then the total is shown.

## 2. Settings (operator adjustments)

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| none | | | | No adjustment is read by any Quorra function (0x0101cd7c-0x0101fb1c). All values are constants. |

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| quorra_lit | 0x02111898 +(player-1), 1 B | per player | 0 at player init (event 0x26 handler 0x0101cd78 = `lit_item_take(2)`); 1 when lit (capped at 1); -1 at MB start | Quorra MB lit at the VUK (bit 2 of the shared lit-items block 0x02111894) [0x0102e8c0] |
| quorra_progress | 0x021117ac +(p-1), 1 B | per player | 0 at player init and when lit [0x0101cd7c] [0x0101f410] | left inner loops made toward lighting (0-5) |
| quorra_starts | 0x021117b0 +(p-1), 1 B | per player | 0 at player init; +1 per start, cap 255 [0x0101f55c] | used for the Jackpot base |
| quorra_supers | 0x021117b4 +(p-1), 1 B | per player | 0 at player init; +1 per Super, cap 255 [0x0101d0b4] | not read by Quorra code |
| game flag 0x29 | | while mode runs | set at start / resume, cleared when one ball is left or at end of ball | "Quorra MB running" [0x0101ce1c] |
| tasks 0xb3 → 0xb4 | | end window | [0x0101f76c] | 312 + 125 ticks after the end in which shots still score and the MB can resume |
| quorra_jackpot | 0x0003b374, 4 B | while mode runs | start: min(350,000 + 25,000 x quorra_starts_before_this_start, 500,000) [0x0101cfec] | +25,000 after every Jackpot, capped 500,000 [0x0101d044] |
| quorra_super | 0x0003b378, 4 B | while mode runs | start: 1,000,000 [0x0101d06c] | + the points of every Jackpot scored (no cap); after a Super: min(1,000,000 + 250,000 x quorra_mb_supers, 2,500,000) |
| quorra_mb_supers | 0x0003b370, 1 B | while mode runs | 0 at start | Supers this MB |
| quorra_aab_hits | 0x0003b360, 1 B | while mode runs | 0 at start, 0 after the 3rd hit | Recognizer hits toward add-a-ball |
| quorra_aab_count | 0x0003b364, 1 B | while mode runs | 0 at start | balls added this MB, max 2 |
| quorra_total | 0x0003b380, 4 B | while mode runs | = start award points at start | every Quorra award adds the points scored; shown by deff 70 |
| quorra_double_armed | 0x0003b36c, 1 B | while mode runs | cleared at start; **never set anywhere in 1.74** | gate for "All Jackpots Doubled" (dead feature, see 5) |
| quorra_double_secs | 0x0003b37c, 1 B | while doubled | 7 when the double window starts | seconds shown by deff 65 during the (unreachable) double window |
| 0x0003b368 | 1 B | | cleared at start, never used | |

## 4. How it starts (qualifying / lighting)

1. **Progress is open** when: Quorra MB not running and not in its end window, Disc MB not running and
   no Disc restart window (task 0xad), Simulation not running (flag 0x34), Portal MB not running
   (flag 0x37), Quorra not already lit, quorra_progress < 5, Daft Punk MB not running (flag 0x27).
   Light Cycle MB does **not** block it. [0x0101f384]
2. **Progress shot**: left inner loop = first pulse of the left spinner sw44 (more spins within 62 ticks
   of the last spin are only spins) [0x01029ba4] [0x01029b54]. Each one scores **10,000** x playfield
   multiplier and quorra_progress +1 (max 5). [0x0101f410]
3. Hits 1-4: deff 62 "`N` / TO LIGHT / QUORRA / MULTIBALL" with N = 5 - progress (4, 3, 2, 1), sfx 0x063,
   leff 65, tube show 32. The first hit of a game was hidden behind Light Cycle's deff 83 in the trace
   (same shot). [0x0101d33c] (verified in emulator: traces/quorra_multiball.jsonl)
4. Hit 5: `lit_item_add(2)` → quorra_lit = 1, quorra_progress = 0, deff 63 "QUORRA / MULTIBALL / IS LIT"
   with sfx 0x064 then speech 0x065, leff 66, tube show 33. [0x0101f410] [0x0101d6b4] (verified)
5. Hits needed are always 5 (no increase for later Quorra MBs).
6. Flynn's Arcade "ADV. QUORRA" award calls the same progress routine (one free left inner loop)
   [0x0100e0cc] (inferred from the award table, not traced).

### Start at the VUK (sw11)

The VUK handler (0x0102eddc) checks, in order: Flynn's Arcade award, Portal, Simulation, CLU, Light
Cycle, **Quorra** [0x0101f688]. If Quorra is running or in its end window, the VUK only arms the double
window when quorra_double_armed is set (never in 1.74), otherwise nothing. Else, if quorra_lit was set
when the ball entered and `quorra_can_start` holds (flag 0x29 clear, Disc MB not running, no Disc
restart window, not (all 9 items started and Simulation available), Simulation not running, not (Portal
start condition), Portal not running, Daft Punk not running) [0x0101f2f8], Quorra MB starts
[0x0101f55c]:

- `multiball_start(balls, 0, 625, 125)` with balls = balls in play + 1, or 2 if none in play (the held
  VUK ball does not count), normally **2 balls**; ball save **625 ticks (10.2 s)** with shoot-again
  leff 13, then **125 ticks (2.0 s)** grace. (verified in emulator: balls=2 save=625 grace=125)
- flag 0x29 set; quorra_jackpot initialised (formula above) **before** quorra_starts +1;
  stat "items lit: Quorra" +1 (audit 0x70); quorra_aab_hits, quorra_aab_count, 0x3b368, quorra_double_armed,
  quorra_mb_supers = 0; quorra_super = 1,000,000; audit 0x47 QUORRA MULTIBALL STARTED.
- **200,000** x playfield multiplier; quorra_total = points scored.
- task 0x8d queues the intro deff 64 behind the VUK's other displays.
- If Light Cycle MB ended less than 437 ticks ago it resumes [0x0101b488].
(verified in emulator: score_add 200000, jackpot 350000, super 1000000)

## 5. Behaviour while running

Quorra awards go through `quorra_mb_shot(mask)` [0x0101d0b4], active while flag 0x29 is set **or** in the
end window (tasks 0xb3/0xb4).

| Trigger | Condition | Effect (all via `score_add`, x playfield multiplier) | Display | Sound | Lamp / tube | Next state |
|---|---|---|---|---|---|---|
| left inner loop (first sw44 spin) | always | Jackpot: quorra_jackpot x D (D = 2 in the double window, else 1); audit 0x48; double window killed; quorra_super += points scored; quorra_jackpot += 25,000 (max 500,000) | deff 68 "JACKPOT" + points (double: "DOUBLE / JACKPOT"), random clip from table 0x040d327c, shaker | 0x06c sfx, 0x06d speech (double: 0x06e, 0x06f) | leff 72, tube 38 | |
| right inner loop sw39 | always | Super: quorra_super x D; quorra_supers +1; quorra_mb_supers +1; stat "items collected: Quorra" (audit 0x71); audit 0x49; double window killed; quorra_super = min(1,000,000 + 250,000 x quorra_mb_supers, 2,500,000) | deff 69 "SUPER / JACKPOT" + points (double: "DOUBLE / SUPER JACKPOT") | 0x070 sfx, 0x071 speech (double: 0x072, 0x073) | leff 73, tube 39 | |
| Recognizer 3-bank sw49 / sw50 / sw51 (one hit per 10 ticks for the whole bank, task 0x7b) | quorra_aab_count < 2; hit 1 or 2 | 50,000; quorra_aab_hits +1 | deff 66 "QUORRA MULTIBALL / `N` MORE TO / ADD BALL", N = 3 - hits | 0x069 sfx at frame 8 | leff 70, tube 36 | |
| same | quorra_aab_count < 2; hit 3 | quorra_aab_hits = 0; 500,000 (always); then `multiball_start(balls in play + 1, 0, 312, 187)`; if accepted: quorra_aab_count +1, Quorra resumes if it was in its end window, Light Cycle resumes if in its end window | deff 67 "QUORRA MULTIBALL / BALL / ADDED" (only if the ball was added) | 0x06a sfx, 0x06b speech | leff 71, tube 37 | add-a-ball save 312 ticks (5.1 s) + 187 ticks (3.0 s) grace |
| same | quorra_aab_count = 2 | nothing for Quorra | | | | |
| VUK sw11 | quorra_double_armed != 0 (never true in 1.74) | double window: task 0x5c counts quorra_double_secs 7 → 0, one per 62 ticks (434 ticks = 7.1 s), then task 0x5d 125 ticks; Jackpot and Super are x2 while either task runs; the next Jackpot or Super ends it | deff 65 shows "ALL JACKPOTS / DOUBLED" with the seconds on both sides | | leff 68 flash speeds up to 2 ticks | [0x0101f688] [0x0101cf84] [0x0101cf34] |

Worked example from the trace (multiplier 1, first Quorra MB): Jackpot 350,000 → jackpot 375,000, super
1,350,000; Jackpot 375,000 → jackpot 400,000, super 1,725,000; Super 1,725,000 → super 1,250,000.
(verified in emulator: traces/quorra_multiball.jsonl)

Odd ROM details:
- The Super grows by the points actually scored by the Jackpot, i.e. after the playfield multiplier
  (and the x2), and has no cap while growing; the 2,500,000 cap only applies to the reset value.
- The 500,000 of the 3rd Recognizer hit is paid even when the ball add is refused.
- VUK entries during the MB do nothing for Quorra in 1.74 (verified: VUK at 52.86 s, no Quorra event,
  quorra_double_armed stays 0).
- The shot's own switch score and other features on the same shot still run (left spinner 10,000,
  Recognizer target 1,000 + 1,080, Recognizer logic 250,000 + deff 75 on the right inner loop; those are
  other features).

## 6. How it ends

- **One ball left**: trough handler → multiball end [0x0101bcec] → [0x0101f798]: flag 0x29 cleared,
  double window killed, task 0xb3 started.
- **End window** [0x0101f76c]: 312 ticks (task 0xb3) then 125 ticks (task 0xb4) = 437 ticks (7.1 s).
  Jackpot, Super and Recognizer shots still score; an add-a-ball (or a Light Cycle MB start) during the
  window resumes Quorra MB (flag 0x29 set again, values kept) [0x0101f7e8]. When the window ends (not
  tilted / game over, bits 0x310) task 0x50 shows deff 70 with quorra_total.
  (verified in emulator: flag cleared 60.70 s, late Jackpot 400,000 at 63.30 s, deff 70 at 67.83 s;
  total 3,650,000)
- **End of ball** (event 0x1d) while running or in the window: flag cleared, window killed, total shown
  unless tilted [0x0101f82c] [0x0101f714].
- Carried per player: quorra_starts (Jackpot base for the next MB), quorra_supers, quorra_progress /
  quorra_lit. Nothing else carries over.

## 7. Media

| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| progress 1-4 | deff 62: bitmap 0xae2 + sliding 0xae1/0xae0, "%d" (blinking) "TO LIGHT / QUORRA / MULTIBALL", 30 frames x 4 ticks | 0x063 sfx (0x041) | leff 65 | 32 |
| lit | deff 63: "QUORRA / MULTIBALL / IS LIT" (blinking) | 0x064 sfx (0x041), 0x065 speech (0x2a1/0x2bb/0x131) | leff 66 | 33 |
| MB start (queued) | deff 64: anim 0x1392-0x13b0 then "QUORRA / MULTIBALL" (arg >= 2 variant uses speech 0x068 only; not seen) | 0x066 music (0x456), 0x067 speech (~1.9 s) | leff 67 | 34 |
| MB running (background, mode rule) | deff 65: bitmap 6000, "QUORRA MULTIBALL", alternating "SHOOT LEFT INNER LOOP / FOR JACKPOT" and "SHOOT RIGHT INNER LOOP / FOR SUPER JACKPOT" [table 0x040d3278], "SUPER=%,02lu" | music 0x066 (mode rule `lamp_rule_init(...,0x41,0x66,...,7)`) | leff 68; leff 69 while add-a-ball available | 35 |
| Jackpot | deff 68 (see 5) | 0x06c, 0x06d (double 0x06e, 0x06f) | leff 72 | 38 |
| Super | deff 69 | 0x070, 0x071 (double 0x072, 0x073) | leff 73 | 39 |
| add-a-ball progress | deff 66, 31 frames x 4 ticks | 0x069 | leff 70 | 36 |
| ball added | deff 67 | 0x06a, 0x06b | leff 71 | 37 |
| total | deff 70: "QUORRA / MULTIBALL / TOTAL:" + total (right aligned) | 0x074 sfx (0x03a), 0x075 (sample 0x00c, not exported in mpf_package: asset_audit W5) | leff 74 | 40 |

Rule registration [0x0101fb1c]: deff 65 + music 0x066, leff 68 and tube show 35 while `quorra_mb_rule_active`
(flag 0x29 and not while the intro task 0x8d waits for deff 64) [0x0101f0ac]; leff 69 while
`quorra_add_ball_available` (running or end window, and quorra_aab_count < 2) [0x0101ce90].
Status page (instant info, inferred) [0x0101f8e0]: "%u / LEFT INNER LOOP SHOT(S) / TO LIGHT / QUORRA
MULTIBALL", or "QUORRA MULTIBALL / LIT", or during the MB "QUORRA MULTIBALL / JACKPOT=... / SUPER JACKPOT=...".

## 8. Lamps

| State | Lamps |
|---|---|
| start possible and not lit | 60 ADVANCE QUORRA on (rule layer; blinks ~100 ms in the emulator) [0x0101f85c] |
| lit and start possible | 39 EJECT: QUORRA on (rule layer; blinks ~82 ms in the emulator) [0x0102f024] |
| MB running | leff 68 claims 60 ADVANCE QUORRA, 64 L. INNER LOOP ARROW, 57 R. INNER LOOP ARROW and toggles them every 12 ticks (195 ms; 2 ticks while the double window runs) [0x0101f0f4] (verified: ~195 ms edges) |
| add-a-ball available | leff 69 chases lamp group 0x34 = 51/52/53 RECOGNIZER POS. 1-3, 8-tick steps [0x0101f188] |

## 9. Interactions

- Blocked by Disc MB (and its restart window), Simulation, Portal MB, Daft Punk MB; also not started when
  all 9 items are started and Simulation can start (that VUK entry starts Simulation instead).
  [0x0101f2f8] [0x010263b0]
- **Light Cycle MB**: neither blocks the other. Progress for each continues during the other's MB, one
  VUK entry can start both (Light Cycle first, then Quorra; total balls = balls in play + 1 = 3), and
  starting either resumes the other if it is in its end window. (verified in emulator:
  traces/light_cycle_multiball_repeat_and_stack.jsonl)
- Shot hook order on the left inner loop: Portal, Simulation, CLU, Disc MB, **Quorra MB (Jackpot)**,
  LC MB, LC progress, **Quorra progress**, combos, Find Flynn [0x01029ba4]. Right inner loop: Portal,
  Simulation, combos, Find Flynn, Disc MB, **Quorra Super**, LC MB, LC progress, ... [0x0102ae3c].
  Recognizer bank: **Quorra add-a-ball** first, then Disc MB [0x0102aec8].
- Tilt / game over: `multiball_start` refuses while game-state bits 0x214 are set; no totals with bits
  0x310 [0x0001ed7c] [0x0101f714].
- Wizard stats: item 4 "lit" at start (audit 0x70), "collected" on every Super (audit 0x71)
  [0x01016188]; per-player at 0x02111694 + 4*16.

## 10. Reference scenario

`traces/quorra_multiball.txt` (trace `.jsonl`), times from `ready`:

| t (s) | input | expected |
|---|---|---|
| 6.75, 8.94, 11.12, 13.29 | sw44 | score_add 10000 (0x0101f440) each, deff 62 (hit 1 hidden by LC deff 83), sound 0x063 |
| 15.47 | sw44 | quorra_lit = 1, deff 63, 0x064 then 0x065 |
| 19.65 | sw11 | other VUK awards first, then multiball_start 2/625/125, flag 0x29, audit 0x47, score_add 200000; deff 64 at 24.18 with music 0x066 and speech 0x067 |
| 31.81 | sw44 | Jackpot 350000, deff 68, audit 0x48 |
| 34.99 | sw44 | Jackpot 375000 |
| 38.17 | sw39 | Super 1725000, deff 69, audit 0x49 |
| 42.35, 44.51 | sw49, sw50 | 50000 each, deff 66 |
| 46.68 | sw51 | 500000, multiball_start 3/312/187, deff 67 |
| 52.86 | sw11 | nothing for Quorra |
| 58.05, 60.17 | drain, drain | flag 0x29 cleared at 60.70 |
| 63.28 | sw44 | late Jackpot 400000 |
| 67.83 | | deff 70 total 3,650,000, sounds 0x074, 0x075 |

Note: made with a copy of `tron_ref` that polls `PinmameGetSolenoid()` each step; the shipped binary
got no coil callbacks for coils 1-32, so its trough never ejected and `drain` was ignored.

## 11. Open questions

- "All Jackpots Doubled": quorra_double_armed (0x0003b36c) is only cleared (0x0101f55c) and read
  (0x0101f688); no store of a non-zero value was found (literal 0x3b36c appears only in those two
  functions, and no base+offset access from 0x3b360/0x3b364/0x3b368 writes it). Treat the feature as
  unreachable in 1.74 unless found elsewhere.
- deff 64 short variant (arg >= 2) trigger unknown (task 0x8d always passes 1).
- Ball-save countdown start point (paused while the VUK holds the ball) not measured.
