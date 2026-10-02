# End of Line Multiball (a.k.a. Daft Punk Multiball)

Stern Tron Legacy LE 1.74. One feature with two names: the display and speech call it
**END OF LINE MULTIBALL**, the audit calls it **DAFT PUNK MULTIBALL STARTED** (audit 0x8e), and
the lighting letters spell **DAFT** and **PUNK**. There is no separate "End of Line multiball"
audit and no second multiball. The code behind both names is the same
(`on_daft_punk_multiball_started` 0x01004cc0 starts deff 56 "END OF LINE / MULTIBALL").
`daft_punk_multiball.md` is a short companion page (naming, music, sounds). **This file is the
full rule.** The "END OF LINE" **combo** (audit 0x85, deff 139 "END OF LINE JACKPOT") is a
different feature, covered in the combo file; it is only mentioned here where it overlaps.

Value notation: all points go through `score_add`, so they are multiplied by the playfield
multiplier. "Total" values below are what `score_add` returned (already multiplied).

## 1. Summary

Each **left ramp** lights the next letter of D-A-F-T, each **right ramp** the next letter of
P-U-N-K. Spelling both words is one "set". After 2 sets (setting 83) the multiball is lit;
for later multiballs in the same game 8 sets are needed (setting 84). The first set of the game
(setting 85) also lights the Extra Ball. Shoot the **VUK (Flynn's Arcade scoop)** to start a 2-ball
multiball. During it every playfield switch scores a growing switch value (10,000 to 50,000),
the left ramp scores a Jackpot (500,000 and up), the right ramp a Double Jackpot, and the
spinning disc scores 200,000, raises the jackpot level, changes the music and earns add-a-balls.
It ends when only one ball is left (plus a ~5 s grace period), and shows the multiball total.

## 2. Settings (operator adjustments)

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 83 | 1ST END OF LINE M.B. LETTERS | 2 | 1-2 | Completed DAFT+PUNK sets needed to light the first multiball of the game [0x010042d0] (verified in emulator: traces/end_of_line_multiball.jsonl, lit on the 2nd set) |
| 84 | 2ND+ END OF LINE M.B. LETTERS | 8 | 4-10 | Sets needed for every later lighting (when the multiball has already been lit this game) [0x010042d0] |
| 85 | END OF LINE EXTRA BALL | 1 | 1-3 | The Extra Ball is lit when the game's total set count reaches exactly this number; once per game per player (flag 0x28). A value of 0 would disable it (code checks `!= 0`) [0x01004238] (verified in emulator: EB lit on set 1) |

The ROM says "LETTERS" but the unit is a **completed set of 8 letters** (DAFT + PUNK), not a
single letter. 2nd+ default 8 therefore means 64 ramp shots. That is what the code does.

## 3. State

Per-player arrays are indexed [player-1]; the decompile often shows them one byte lower and
indexed [player] (e.g. `DAT_02111617[p]` = `0x2111618[p-1]`).

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| eol_letters_left | 0x02111618 (+p-1), 1 B | per player | 0 at game start; 0 when a set completes | DAFT letters lit, 0..4 [0x010042d0] |
| eol_letters_right | 0x0211161c (+p-1), 1 B | per player | same | PUNK letters lit, 0..4 [0x010042d0] |
| eol_times_lit | 0x02111620 (+p-1), 1 B | per game per player | 0 at game start (FUN_01004198) | +1 each time the multiball gets lit; 0 = use adj 83, else adj 84 [0x010042d0] |
| eol_sets | 0x02111624 (+p-1), 1 B | per game per player | 0 at game start; 0 when the MB gets lit | Completed sets toward the next lighting (saturates at 255) [0x010042d0] |
| eol_sets_total | 0x02111628 (+p-1), 1 B | per game per player | 0 at game start | All completed sets this game; compared with adj 85 [0x010042d0] |
| eol_mb_lit | game flag 0x26 | per player (game flags are saved/restored per player at player change, inferred from FUN_00006700/FUN_00006744) | set when lit; cleared when the MB starts | Multiball lit at the VUK [0x01004bb0, 0x01004ddc] |
| eol_eb_given | game flag 0x28 | per player, per game | clear at game start (inferred) | The END OF LINE extra ball was already lit this game [0x01004238] |
| eol_running | game flag 0x27 | while mode runs | set at start; cleared at 1 ball left or end of ball | Multiball running [0x01004cc0, 0x0101bcec] |
| eol_grace | task 0xb0 then 0xb1 | after 1 ball left | 187 + 125 ticks | Grace period: shots still score (see 6) [0x010050f8] |
| eol_lit_mask | 0x0003adf0, 4 B | while mode runs | 7 at start | Lit jackpot shots: bit0 left ramp, bit1 right ramp, bit2 disc [0x01004cc0, 0x01004e94] |
| eol_level | 0x0003adf4, 4 B | while mode runs | 0 at start | Disc hits this multiball; raises the jackpot; selects music [0x01004e94] |
| eol_aab_left | 0x0003adf8, 4 B | while mode runs | 2 at start | Disc hits until the next add-a-ball [0x01004e94] |
| eol_aab_count | 0x0003adfc, 4 B | while mode runs | 0 at start | Add-a-balls earned; next target = count + 2 [0x01004e94] |
| eol_switch_value | 0x0003ae00, 4 B | while mode runs (value stays after the end, unused) | 10,000 at start | Points per switch; +1,000 per disc hit, max 50,000 [0x01004cc0, 0x01004e6c] |
| eol_total | 0x0003ae04, 4 B | while mode runs | = the 100,000 start award | Sum of everything this feature scored, shown at the end [0x01004cc0] |
| eol_starts_this_ball | 0x0211162c (+p-1), 1 B | per player turn (reset on event 0x26) | 0 | +1 per start; no reader found in the ROM |

Event 0x26 is posted at the start of a player's turn (not on a shoot-again ball; from
`FUN_00020650`: posted only when the ball-in-turn counter is 1, inferred). Event 0x1d = ball ended
(drain of the last ball). Event 0x2e = game start.

## 4. How it starts (qualifying / lighting)

### 4.1 Letters (DAFT on the left ramp, PUNK on the right ramp)

Each completed ramp calls `eol_letters_ramp(side)` [0x010042d0] from the ramp-made handlers:
left ramp = sw37 L. RAMP EXIT (`on_left_ramp` 0x0102a940, also 0x0102a948 / 0x0102a9bc) with side 0,
right ramp = sw34 R. RAMP EXIT (`on_right_ramp` 0x0102aa50, also 0x0102aa58 / 0x0102aad8) with side 1.
It is the **last** hook in those handlers (after Portal, simulation, Disc MB, Light Cycle, combos,
Find Flynn, ZUSE, `eol_shot_score` and `eol_jackpot_shot`).

Letters only advance when ALL of these hold [0x01004298]:
- the multiball is not already lit (flag 0x26 clear),
- no multiball is running (`FUN_0100f918`: End of Line, Disc, Light Cycle, Quorra or Portal),
- Sea of Simulation is not running (flag 0x34).
(During any multiball's grace period the running flag is already clear, so letters do advance.)

Step by step on a qualifying ramp:
1. Left ramp: if `eol_letters_left < 4`, +1. Right ramp: if `eol_letters_right < 4`, +1. A ramp
   whose word is already full adds nothing but still shows deff 55.
2. `needed = adj83` if `eol_times_lit == 0`, else `adj84`.
3. If both words are full (`left >= 4 and right >= 4`), a set is complete:
   - `eol_sets += 1`.
   - If `eol_sets >= needed`: light the multiball (set flag 0x26 if it was clear),
     `eol_times_lit += 1`, `eol_sets = 0`.
   - `eol_sets_total += 1`. If flag 0x28 is clear, adj85 != 0 and `eol_sets_total == adj85`, light
     the Extra Ball (`FUN_0102e8c0(1,1)`, the VUK "EJECT: EXTRA BALL" award, lamp 37) and set flag 0x28.
   - Both words are cleared to 0 letters.
4. Deff 55 (letters display) is started with: letters before (left, right), letters after
   (left, right), flags and a "more to go" number (below).

Deff 55 flags [0x010042d0]: bit0 = Extra Ball lit by this ramp, bit1 = multiball lit by this ramp,
bit2/bit3 = what the "%u MORE TO" line refers to:
- `mb_left = needed - eol_sets` (after the update), `eb_left = adj85 - eol_sets_total` (only if positive).
- Default: bit3 ("LIGHT MULTIBALL"), number = mb_left.
- If eb_left > 0 and eb_left < mb_left: bit2 ("LIGHT EX. BALL"), number = eb_left.
- If eb_left > 0 and eb_left == mb_left: bits 2+3 ("LIGHT M.B. + E.B."), number = mb_left.

Verified (traces/end_of_line_multiball.jsonl): ramps alternate L/R; 4th right ramp completes set 1
and sets flag 40 (0x28, EB lit); set 2 completes on the 16th ramp, flag 38 (0x26) set,
`eol_times_lit` 0 -> 1, `eol_sets` 1 -> 0, `eol_sets_total` 2. Each ramp also scored its normal
1,170 ramp points (not this feature).

### 4.2 Start at the VUK

When the ball enters the VUK (sw11, `on_vuk` 0x0102eddc), after the Portal/Simulation/Flynn's
Arcade checks, `eol_vuk_start_if_lit` [0x01004ddc] runs: if flag 0x26 is set, it calls the start
[0x01004cc0]; on success flag 0x26 is cleared.

Start conditions [0x01004c68]: no multiball running and Sea of Simulation not running.
If they fail, the lit flag stays set and the VUK can start it later.

On start [0x01004cc0]:
- Balls: `multiball_start(balls_in_play == 0 ? 2 : balls_in_play + 1, ball save 0x271 = 625 ticks
  (10.2 s), grace 0x7d = 125 ticks (2.0 s))`, i.e. a **2-ball multiball** (one ball added).
  (verified in emulator: `multiball_start balls=2 save_ticks=625 grace_ticks=125`)
  Ball save semantics (from `FUN_0001ea60`): the save time runs with the shoot-again lamp effect
  (leff 13); after it, the grace time is a further silent save (inferred).
- `eol_lit_mask = 7`, `eol_level = 0`, `eol_aab_left = 2`, `eol_aab_count = 0`,
  `eol_switch_value = 10,000`, flag 0x27 set, `eol_starts_this_ball += 1`, audit 0x8e.
- Scores **100,000** (start award); `eol_total = that`.
- Task 0xa6 queues the intro deff 56 (waits for higher display priority, up to 3750 ticks) [0x01004c94].
- Starts the background rule (deff 57 + music) [0x01005634].
- Because `on_vuk` calls `eol_shot_score` right after, the VUK switch also scores the switch value
  (10,000) at once. (verified: start = 100,000 + 10,000, eol_total 110,000)

## 5. Behaviour while running

"Active" for scoring = flag 0x27 set OR task 0xb0/0xb1 (grace) running [0x01004c30].

### 5.1 Switch value (`eol_shot_score` 0x01005074)

Every listed switch scores `eol_switch_value` and adds it to `eol_total`.
Called from: sw1-4 TRON standups (via FUN_0100b050, inferred), sw7/8/48/13 ZUSE, sw11 VUK,
sw12 ZEN rollover, sw14/25/28 CLU, sw24/29 outlanes, sw26/27 slingshots, sw30/31/32 bumpers,
sw34/37 ramp exits (via the ramp-made handler), sw35/38 ramp entrances, sw36 right orbit spinner,
sw39 right inner loop, sw41 disc, sw43 left orbit (via 0x0102a728, inlined copy), sw44 left spinner,
sw46 right orbit (via 0x0102a794), sw49/50/51 Recognizer 3-bank (when the bank handler runs).
Spinners score per spinner switch closure. A ramp shot scores the entrance AND the exit.

| Trigger | Condition | Effect | Display | Sound | Lamp / leff | Next state |
|---|---|---|---|---|---|---|
| any switch above | active | + eol_switch_value (10,000 + 1,000 x disc hits, max 50,000) | (background deff 57 shows "SWITCHES=value") | none | none | — |

### 5.2 Jackpot shots (`eol_jackpot_shot` 0x01004e94, table 0x040d25a8: shot 0 = bit 1, 1 = bit 2, 2 = bit 4)

`J = min(500,000 + 25,000 x eol_level, 1,250,000)` [0x01004e10].

| Trigger | Condition | Effect | Display | Sound | Lamp / leff | Next state |
|---|---|---|---|---|---|---|
| Left ramp (sw37 exit) | active, mask bit0 set | score J; clear bit0; if bits 0 and 1 are both clear -> mask = 7 | deff 58 "JACKPOT" + value | 0x027 (in deff) | leff 61, tube show 89 | left ramp unlit until the right ramp is made |
| Left ramp | bit0 clear | nothing (switch value only) | — | — | — | — |
| Right ramp (sw34 exit) | active, mask bit1 set | score **2 x J** (computed before multiplier, then multiplied); clear bit1; refill to 7 if both ramp bits clear | deff 59 "DOUBLE JACKPOT" + value | 0x028 | leff 62, tube show 90 | — |
| Disc (sw41 DISC OPTO) | active (bit2 is never cleared, always lit) | `eol_level += 1`; `eol_aab_left -= 1`; if it reaches 0: `eol_aab_count += 1`, `eol_aab_left = eol_aab_count + 2`, add a ball (`balls_in_play + 1`, save 0x138 = 312 ticks / 5.1 s, grace 0xbb = 187 ticks / 3.0 s); mask = 7; score **200,000**; `eol_switch_value += 1,000` (max 50,000) | deff 60: value + "BALL ADDED", or value + "%u MORE FOR / ADD-A-BALL" (= eol_aab_left) | music changes (5.4) | leff 63, tube show 91 | — |

The jackpot shot runs after `eol_shot_score` in the same handler, so a lit left ramp scores
switch value + J. All jackpot awards and the 200,000 are added to `eol_total`.

Add-a-ball schedule: 2nd disc hit, then 3 more (5th), then 4 more (9th), ... (+1 each time).
Ball count is capped at the installed balls (4) by `multiball_start`. An add-a-ball during the
grace period restarts the multiball (flag 0x27 set again, grace tasks killed) [0x010050b8].
The disc opto has its own 125-tick (2.0 s) re-trigger lockout (task 0x3f) in sw41's handler: a
second interruption within that time is ignored (only sound 0x54).

Verified (traces/end_of_line_multiball.jsonl, multiplier 1):
- left ramp lit: 10,000 + 500,000; again (unlit): 10,000 only; right ramp: 10,000 + 1,000,000, mask back to 7;
- disc 1: 10,000 + 200,000, level 1, aab_left 1, switch value 11,000;
- disc 2: 11,000 + 200,000, `multiball_start balls=3 save=312 grace=187`, aab_left 3, aab_count 1, switch 12,000;
- left ramp at level 2: 12,000 + 550,000.

### 5.3 What the rest of the game does meanwhile

While flag 0x27 is set, every condition function that tests `FUN_01004be8` (End of Line running)
or `FUN_0100f918` (any multiball running) returns false. Callers found: Portal start (0x0102f434),
Light Cycle qualifying (0x0101860c), Quorra qualifying (0x0101f2f8, 0x0101f384), disc-feature rule
0x01020b4c, Find Flynn start (0x0100d654), CLU eject (0x01001c98), item rule 0x0101688c, rule
0x01033744. Which feature each of these belongs to is the other files' job; the effect is that
no other multiball can be lit or started meanwhile (inferred from these conditions). The DAFT/PUNK
letters do not advance.

### 5.4 Music

The background rule [0x010055d8 + 0x01005610] keeps deff 57 on screen and plays music call
**0x20 + (eol_level & 3)**: level 0 -> 0x020 (sample 0x447, 10.0 s), 1 -> 0x021 (0x448, 22.0 s),
2 -> 0x022 (0x449, 12.0 s), 3 -> 0x023 (0x44a, 11.0 s), 4 -> 0x020 again, and so on. The rule
re-checks on every rules refresh and starts the call only if it is not already playing, so the
track changes right after each disc hit. Background priority is 7.
(verified: 0x020 at the intro, 0x021 after disc 1, 0x022 after disc 2)
The rule is active while flag 0x27 is set and the intro is not still waiting (task 0xa6 running
without deff 56 on screen). It stops at the grace period, so normal music returns then.

## 6. How it ends

- **One ball left**: the trough handler (`FUN_0101bbc0` event 0xe, then `FUN_0101bcec` 0x0101bcec)
  runs when fewer than 2 balls remain in play. It clears flag 0x27 and starts task 0xb0
  [0x010050f8]: sleep 187 ticks (3.04 s), become task 0xb1, sleep 125 ticks (2.03 s), then show
  the total. **Grace = 312 ticks (5.07 s)** (verified: flag 0x27 cleared 0.54 s after the drain, grace jackpot scored, total 5.43 s later because a deff was still showing). During the grace, switch value and jackpots still score
  (`FUN_01004c30` includes tasks 0xb0/0xb1). An add-a-ball (disc) in the grace restarts the mode.
  The background deff/music and leffs stop at the start of the grace (they test flag 0x27 only).
- **Total**: after the grace, if `eol_total != 0` and the game is not tilted/over (`DAT_00037274 & 0x310`),
  task 0x4f shows deff 61 "END OF LINE / MULTIBALL / TOTAL: value" [0x01006240].
- **Ball end / tilt** (event 0x1d, `FUN_01005124`): if active, flag 0x27 cleared, grace tasks killed,
  total shown (same tilt check, so not on tilt).
- Nothing carries over: the running variables are re-initialised at the next start. Lit state
  (flag 0x26) and the letters/set counters stay with the player for the rest of the game.

## 7. Media

| When | Display effect | Sound calls | Lamp effect (leff) | Ramp tube show |
|---|---|---|---|---|
| Ramp while qualifying | deff 55 (prio 159, 41 frames x 3 ticks + 10 hold = 2.2 s): two rows of 4 letter images, DAFT (images 0x9db,0x9d8,0x9dd,0x9eb from table 0x040d2588) and PUNK (0x9e7,0x9ec,0x9e5,0x9e2 from 0x040d2598); letters already lit drawn normally, letters lit by this shot blink, others dimmed; text "MULTIBALL + E.B. / ARE LIT", "EXTRA BALL / IS LIT", "MULTIBALL / IS LIT" or "%u MORE TO" + "LIGHT MULTIBALL" / "LIGHT EX. BALL" / "LIGHT M.B. + E.B." [0x0100461c] | none in deff (ramp sfx 0x0eb comes from the ramp handler) | 56 (empty layer) | 86 (empty) |
| Lit, waiting for VUK | — | — | 57: pulses coils 17 ZEN FLASHER and 18 FLASH: VIDEO GAME with a 16-step strength table 0x040d25c0 every 6 ticks [0x010051c4] | — |
| Start (intro) | deff 56 (prio 192, 4.1 s): animation images 0x1fd7-0x1ff3 (4 ticks/frame) then "END OF LINE / MULTIBALL" blinking 21 x 6 ticks [0x01005260] | speech 0x024 -> 0x025 -> 0x026 chained (samples 0x320, 0x321, 0x322) | 58 (all flashers, 120 x 8 ticks) | 87 |
| Running (background) | deff 57 (prio 1, loop): same animation, "SWITCHES=%,02lu" blinking [0x01005524] | music 0x020-0x023 (5.4) | 59 (idle), 60: pulses 31 FLASH: RED DISC when eol_level is even, 32 FLASH: BLUE DISC when odd, every 8 ticks [0x01005658] | 88: left tube pulses white while the left ramp jackpot is lit, right tube while the right ramp is lit (0x010056b8) |
| Left ramp jackpot | deff 58 (prio 196, 2.2 s) "JACKPOT" + value | 0x027 (sfx 0x03c) | 61 | 89 |
| Right ramp double | deff 59 (prio 197, 2.2 s) "DOUBLE JACKPOT" + value | 0x028 (sfx 0x03b) | 62 | 90 |
| Disc | deff 60 (prio 195, 2.2 s) value + "BALL ADDED" or "%u MORE FOR / ADD-A-BALL" | none in deff (disc sfx 0x052/0x053 from sw41) | 63 | 91 |
| End | deff 61 (prio 207, 3.2 s) "END OF LINE / MULTIBALL / TOTAL:" + value | none | 64 | 92 |

All deff-started leffs 58, 61-64 and deff 58-60 run the shaker (`shaker_run`, adj 86).
Deff ids/prio match `mpf_package/event_map.csv` (checked in asset_audit "Verified correct").
Package names `deff_056_end_of_line_intro`, `deff_057_end_of_line_running`, `deff_058..061` are
usable; their `leff_NNN` references are **tube** shows (asset_audit M1), the lamp leffs above are
not in the package.

## 8. Lamps

No playfield insert is dedicated to this feature. Lit state is shown by flashers 17/18 (leff 57)
and by deff 55. While running, the ramp light tubes show which jackpot ramps are lit (tube show 88)
and the red/blue disc flashers pulse (leff 60). The Extra Ball it lights uses lamp 37
EJECT: EXTRA BALL (owned by the extra-ball feature).

## 9. Interactions

- **Stacking**: none in either direction. It cannot start while Disc, Light Cycle, Quorra or Portal
  multiball (or Sea of Simulation) runs [0x01004c68], and those refuse to start while it runs (5.3).
  A lit End of Line waits at the VUK; the VUK handler checks Portal before End of Line, so with
  both lit and nothing running, Portal starts first and End of Line stays lit.
- **VUK order** (`on_vuk` 0x0102eddc): simulation shot, CLU hurry-up, extra-ball collect (if lit), Flynn's Arcade award, Portal start, Sea of Simulation start,
  CLU / Light Cycle / Quorra eject awards, **End of Line start**, ZUSE, `eol_shot_score`.
- **Shot hook order** on a ramp: Portal shot, simulation, Disc MB, Light Cycle, combos, Find Flynn,
  ZUSE, `eol_shot_score`, `eol_jackpot_shot`, `eol_letters_ramp`. On the disc: Portal, simulation,
  Disc MB, ZUSE, `eol_shot_score`, `eol_jackpot_shot`.
- **END OF LINE combo** (other file): a separate award; in the reference trace the VUK shot that
  started this multiball also scored the combo's 500,000 with deff 139. Not part of this feature.
- **Extra ball**: lit through the generic eject award (lamp 37), collected at the VUK; see the
  extra-ball file. In the traces the same VUK shot collected it (audit 9).
- **Tilt**: ball end clears the mode; no total shown when tilted.
- **End-of-ball bonus**: this feature adds nothing to the bonus.

## 10. Reference scenario

`traces/end_of_line_multiball.txt` / `.jsonl` (no pokes, factory settings). 16 alternating ramps
light it (Extra Ball lit after 8), the VUK starts it, the script waits 30 s so the ball save
(which counts from the multiball eject, ~13 s after the VUK because of the queued displays) is
over, one ball drains, a left ramp and the right spinner are shot in the grace, a ramp is shot
after the end, then the last ball drains.

Expected key events (seconds after `ready`, multiplier 1):
- 25.5 set 1 complete: `flag_set 40`; 46.9 set 2: `flag_set 38`, `var eol_times_lit 1`.
- 50.3 VUK: `multiball_start balls=2 save_ticks=625 grace_ticks=125`, `flag_set 39`, `audit 142`,
  `score_add 100000`, `flag_clear 38`, `score_add 10000` (VUK switch value).
- 58.0 deff 56 + sound 0x024 (0x025, 0x026 chained), deff 57 + music 0x020.
- 79.7 drain -> 80.26 `flag_clear 39`, normal music 0x01b.
- 81.8 grace left ramp: `score_add 10000` + `score_add 500000` (deff 58), and deff 55 (DAFT letter 1:
  letters advance in the grace).
- 84.0 grace spinner: `score_add 10000` (switch value; the other 10,000 is the spinner's own score).
- 85.68 deff 61 total (630,000). The grace task ends 312 ticks (5.07 s) after 80.26; the total deff
  appeared 5.43 s after, because the grace jackpot's deff 58 / 55 were still on screen (inferred:
  the total task waits for display priority).
- 90.2 ramp after the end: no switch value, letters advance.

Second trace `traces/end_of_line_multiball_scoring.txt` / `.jsonl`: jackpots, unlit ramp,
double jackpot, disc hits 1-2 (add-a-ball, music 0x021 / 0x022), jackpot at level 2 (550,000).
Its drains happen inside the add-a-ball ball save, so the balls come back (no end in that trace).
Music over five disc hits and the 1,250,000 cap: `traces/daft_punk_multiball.jsonl`.

## 11. Open questions

- `eol_starts_this_ball` (0x211162c) has no reader in the decompile; maybe used through a table.
- Game flags 0x26/0x28 per player: inferred from the flag save/restore functions, not traced with
  2 players.
