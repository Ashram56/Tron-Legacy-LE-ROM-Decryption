# Recognizer 3-bank and Disc Battle (Tron Legacy LE 1.74)

Source: `tron/code/tron_game_decompiled_v2.c`; tables in `trn_174h.bin`. Function names in brackets are
addresses in the decompile; better names are in `work/ram/recognizer_and_disc_battle_functions.tsv`.
1 tick = 16.26 ms. Traces: `traces/recognizer_and_disc_battle.jsonl` (made with the fixed `tron_ref`,
factory settings, no pokes).

## 1. Summary

The Recognizer is a 3-bank of drop-style targets (sw49 L, sw50 C, sw51 R) on a motor-driven bank in front of
the spinning disc, with a rotating Recognizer head above it. One of the three targets is "lit" and the lit target
moves L → C → R → C every 1.5 s; hitting the lit target counts 2, any other target counts 1. Five counts light
**DISC BATTLE** ("DISC BATTLE READY", 200,000): the bank drops and the disc starts spinning. Each disc hit then
counts down "N MORE TO START DISC MULTIBALL"; the hit after the count reaches 0 awards 2,000,000 and starts
Disc Multiball (see `disc_multiball.md`). The number of disc hits grows with every Disc Multiball played.

## 2. Settings (operator adjustments)

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 67 | RECOGNIZER DIFFICULTY | 1 | 0-2 | Starting value of k in the disc-hits formula (§4.2). Read at game start per player [0x0101fd94] |
| 76 | DISABLE RECOGNIZER 3-BANK MOTOR | 0 | 0-1 | Passed to the 3-bank motor driver object (coil 6, sw52/53) [0x010224ec]; 1 = motor never driven, service report "3-BANK MOTOR DISABLED BY ADJ." (msg 0x4f8) [0x010223c4]. Rule logic is unchanged (inferred) |
| 81 | DISABLE RECOGNIZER MOTOR | 0 | 0-1 | Passed to the Recognizer head motor driver object (coil 23, sw54-56) [0x01022acc area, init at decompile line 89147]; 1 = head not moved (inferred) |

## 3. State

All per-player arrays are NVRAM bytes indexed [player-1]. Addresses below are for player 1.

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| rec_hits | 0x21117bc (1) | per player | 0 at game start, at battle lit and battle cleared | counts toward Disc Battle, lights at ≥5 [0x010201e4] |
| rec_targets_disabled_mask | 0x21117b8 (1) | per player | rebuilt from switch-disable state at game start / battle lit / battle end [0x0101fd1c, 0x01020ea4] | bit0 L, bit1 C, bit2 R: targets whose switch the OS has marked bad. Normally 0 |
| dbattle_lit | game flag 0x22 | per player (carries to next ball, verified) | set by battle start, cleared by Disc Multiball start | "DISC BATTLE" lit [0x01020b38] |
| dbattle_difficulty (k) | 0x21117d4 (1) | per player | = adj 67 at game start [0x0101fd94]; +1 at each Disc Multiball start [0x01020da8] | hits-to-start formula input |
| dbattle_need | 0x21117d8 (1) | per player | set when battle lit | min(4+2k,10), display only |
| dbattle_remaining | 0x21117dc (1) | per player | set to min(4+2k,10) when battle lit; −1 per disc hit | 0 = next disc hit starts the multiball. Reads 255 before the first battle |
| dbattle_award_level (j) | 0x21117d0 (1) | per player | 0 at game start; **never incremented in 1.74** | start award = min(2,000,000+1,000,000·j, 4,000,000) [0x01020ca4] → always 2,000,000 |
| rec_hits_stat, rec_battles_qualified | 0x21117c0, 0x21117c4 | per player | 0 at game start | statistics only (sat. 255) |
| rec_lit_pos / rec_prev_pos / rec_next_pos | 0x3b3f8 / 0x3b3fc / 0x3b3f4 (4) | game | set when the moving-target task starts | index 0-3 into table 0x040d32b4 |
| rec_motor_target | 0x3b400 (1) | game | 0x36 at game/ball start [0x0101ff28] | Recognizer head target, as switch number 54/55/56 |
| (unused) | 0x21117c8, 0x21117cc | per player | cleared with battle | never used by live code |

Full list with sizes: `work/ram/recognizer_and_disc_battle.tsv`.

## 4. How it starts

### 4.1 Recognizer targets → DISC BATTLE

Targets "count" only when `recog_targets_count_active` [0x0101ffd8] is true: Disc Battle not lit, and none of
these running: Disc Multiball (flag 0x24), Light Cycle MB (0x2b), Quorra MB (0x29), Sea of Simulation (0x34),
Portal MB (0x37). (Daft Punk MB, flag 0x27, does not block it.)

Moving lit target (task 0x7d [0x01020034], runs only while targets count and no target switch is disabled
[0x010200f4]):
- Table 0x040d32b4, 4 steps `{mask, target switch, head position switch, lamp}`:
  0 = L (sw49, head sw56, lamp 53), 1 = C (sw50, head sw56, lamp 52), 2 = R (sw51, head sw56, lamp 51),
  3 = C (sw50, head **sw54**, lamp 52). Order 0→1→2→3→0, skipping disabled targets [0x0101fe20].
- One step = 93 ticks (1.51 s, measured 1.51 s). At tick 46 the *next* index is chosen and the head is sent to
  its position; at tick 93 the lit index moves. The previous lit target still counts as lit for the first 10 ticks
  (163 ms) of the new step [0x01020034]. (verified in emulator: traces/recognizer_and_disc_battle.jsonl)
- Oddity: three of the four steps send the head to sw56 (RECOG. MOTOR POS. 3) and only step 3 to sw54 (POS. 1);
  the head does not follow the lit target one-to-one. Reported as read from the ROM.

| Trigger | Condition | Effect | Display | Sound | Lamp | Next |
|---|---|---|---|---|---|---|
| sw49/50/51 (10-tick debounce task 0x7b per bank) | targets count, new count < 5 | rec_hits += 2 if the hit target is the lit (or just-previous) one, else += 1. Score **2,500** (x PF mult.). Item "Recognizer lit" (audit 0x76) [0x01016188(7,1)] | deff 108: "%u MORE / TO ACCESS / DISC" with 5−count, one of 4 random clips; speech 0x0d1 at frame 20/30 if count left < 3 | 0x0d0 | leff 101 (target flash), tube show 59 | – |
| same | new count ≥ 5 | Item collected audit 0x77; **DISC BATTLE lit** (§4.2); flag 0x2e set (bank-lowering sound cue) | deff 109 | see 4.2 | | battle lit |
| same | targets do not count (battle lit, multiballs) | **1,000** points | – | 0x0ce | leff 100 | – |

Every sw49-51 hit also runs (in this order, before the above): Quorra super-jackpot hook, Disc Multiball shot 6,
Zuse target hook, End-of-Line hook, simulation shot 0xd; after it the generic target score **1,080** (0x438)
[0x0102aec8/0x0102af44/0x0102afc0]. (verified: every hit shows a 1,080 score_add)

Trace example: L (unlit) → 1, C while lit index 3 (C) → 3, R → 4, L → battle (4 hits).

### 4.2 DISC BATTLE lit [on_recognizer_battle_started 0x01020d1c]

1. Game flag 0x22 set; k → hits needed `N = min(4 + 2·k, 10)`; dbattle_need = dbattle_remaining = N [0x01020c40].
   With factory adj 67 = 1: first battle N = 6, second 8, third and later 10.
2. Audit 0x8d RECOGNIZER BATTLE STARTED; score **200,000** (x PF mult.).
3. Display deff 109 "DISC / BATTLE / READY" (leff 105, tube show 60, sound 0x0d8, speech 0x0da at the end).
   When lit silently by the Flynn's Arcade award (§4.4) it is queued instead (task 0x9d → deff 109 queued).
4. rec_hits reset to 0 [0x0101fd1c].
5. The 3-bank drops (sound 0x0d3 when the bank motor starts with flag 0x2e set [0x01022308]) and the disc motor
   starts. (verified: coil 6 runs 0.68 s → bank_down; coil 5 DISC MOTOR POWER on 33 ms after the battle)

If called while already lit it only logs error 0xb9.

### 4.3 Disc hits → start Disc Multiball [FUN_01020da8(type, silent) 0x01020da8]

Callers: sw41 DISC OPTO with (2, 0) [0x0102ab6c], and the Flynn's Arcade award "ADVANCE DISC" with (2, 1)
[0x0100e12c → wrapper 0x0100e134].
Counts only when `dbattle_can_progress` [0x01020b4c]: battle lit and none of Portal MB, Sea of Simulation,
Disc MB, Quorra MB, Light Cycle MB, Daft Punk MB running.

| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| disc hit | remaining > 0 | remaining −= 1 (a `type` of 1 would subtract 2; no caller uses it) | deff 111 "%d / MORE TO START / DISC MULTIBALL" with remaining+1, random clip of 11 (not when silent) | 0x0d7 | leff 108, tube show 62 |
| disc hit | remaining = 0 and type has bit 1 | score **2,000,000** (x PF mult.; = 2,000,000+1,000,000·j, j always 0); clear battle (flag 0x22, target state reset); FUN_0101c088 (picks a random value 0xbb-0xbe into per-player 0x211177c, owner unknown); k += 1; **start Disc Multiball** | (Disc Multiball intro) | | |

So the number of disc hits is **N + 1**: 7 with factory settings for the first multiball (6 count-downs + the
start hit), 9 for the second, 11 afterwards. (verified in emulator: hits at 21.8 … 38.0 s, remaining 6→0, 7th hit
scores 2,000,000 and calls multiball_start)

sw41 rules: a second opto interruption within 125 ticks (2.03 s, task 0x3f) only plays sound 0x054 and does
nothing else (verified). Otherwise sw41 runs, in order: Portal MB shot 6, simulation shot, Disc MB shot 7,
Disc MB restart check, Zuse hook, End-of-Line hook, FUN_01004e94(2), **Disc Battle (this)**, leff 75, sounds
0x052 + chained 0x053, and the base score **2,310** (0x906, x PF mult.).
Because the Disc MB shot is processed before the start, the starting hit never also scores a jackpot.

The status page [0x01021d9c] shows either "%u RECOGNIZER HIT(S) TO START "DISC BATTLE"" (5 − rec_hits) or
"%u DISC SHOT(S) TO START "DISC MULTIBALL"" (remaining + 1).

### 4.4 Flynn's Arcade awards (cross-feature)

Award table 0x040f0900 (6 words: available_fn, award_fn, ram, names, weight, audit):
- "ADVANCE DISC" (weight 25, audit 0x58): available while the battle can progress [0x0100e0dc]; award =
  FUN_01020da8(2, 1): one silent count-down, **or starts Disc Multiball if remaining is 0**.
- "ADVANCE RECOGNIZER" (weight 100, audit 0x5a): available while targets count [0x0100e1d8]; award =
  FUN_010201e4(0x32, 0x36, 1): a silent target hit with mask 0x32 (counts 2 when the C target is lit, else 1);
  may light the battle (queued deff 109).

## 5. Behaviour while running (battle lit)

| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| sw49-51 | battle lit | 1,000 + 1,080 | – | 0x0ce | leff 100 |
| sw41 | battle can progress | §4.3 | deff 111 | 0x0d7 | leff 108 |
| sw41 | battle lit but another multiball runs | nothing for the battle (counter frozen) | | | |

## 6. How it ends

- Disc Battle has no timer. It stays lit across balls (verified: lit at drain of ball 1, ball 2 disc hit counted
  3→2) and ends only when Disc Multiball starts [0x01020f10].
- Per-player values reset only at game start (event 0x26) [0x0101fd94].
- Whether flag 0x22 is saved per player in multi-player games was not tested (open question).

## 7. Media

| When | Display effect | Sound calls | Lamp effect | Tube show |
|---|---|---|---|---|
| counting target hit | deff 108 "%u MORE / TO ACCESS / DISC" (random of 4 clips: images 0xa7b+/0xa99+ x=0 3 ticks/frame, 0xa3f+/0xa5d+ x=41 2 ticks/frame) | 0x0d0 sfx (sample 0x0d9); speech 0x0d1 (0x42d) when < 3 left | 101 | 59 |
| non-counting target hit | – | 0x0ce (sample 0x08a) | 100 | – |
| battle lit | deff 109 "DISC / BATTLE / READY" | 0x0d8 (0x0d9), speech 0x0da (0x185/0x12e); bank 0x0d3 (0x07f) | 105 | 60 |
| disc count-down hit | deff 111 "%d / MORE TO START / DISC MULTIBALL" | 0x0d7 (sample 0x00c, not exported, see asset_audit W5) | 108 | 62 |
| start | 2,000,000 then Disc Multiball intro (deff 46) | | | |

Deff 110 "RECOGNIZER BATTLE! / SHOOT RECOGNIZER" exists in the deff table but no code starts it (unused).

## 8. Lamps

| Lamp(s) | State |
|---|---|
| 53 RECOGNIZER POS. 3 (L target), 52 POS. 2 (C), 51 POS. 1 (R) [table 0x040d32a8] | Targets counting: flashing (disabled targets solid) [0x01020f44]. While the moving target runs, leff 99 overrides: lit target flashes (toggle every 3 ticks), just-previous target dim, others off. Not counting: off |
| 54 RECOGNIZER 3-BANK (lamp group 0x60) | Battle lit: leff 106 toggles it every 4 ticks (rule [0x01021ff4]) |
| disc flashers coils 26/27 (coil group 16) | Battle ready (remaining 0): leff 107 pulses them every 8 ticks + tube show 61 |
| red/blue disc flasher coil 31 or 32 | Battle lit (and Disc MB disc phases): leff 76 pulses one every 12 ticks [0x01006610] |

## 9. Interactions

- Blocked by: Disc MB, Light Cycle MB, Quorra MB, Sea of Simulation, Portal MB (targets); the same plus Daft Punk
  MB (disc count-down). Counters freeze, nothing is lost.
- Bank position rule [0x0102227c]: bank **up** (targets in front of disc) by default; **down** while the battle is lit,
  during Disc MB phases 0 and 2 and its restart window; **up** in Disc MB phase 1 (verified bank_up/bank_down in
  traces/disc_multiball.jsonl); Portal MB and Daft Punk states force down; Quorra/Sea of Simulation states choose
  per their own phase.
- Recognizer head rule [0x01022668]: rests at sw55 (POS. 2) unless targets count, Disc MB phase 1, Quorra phase < 2
  or Sea of Simulation stage 7; in those multiballs it swings between sw54 and sw56 every 62 ticks [task_7e 0x0101fe80].
- Disc motor [0x010066c0]: spins while the battle is lit, in Disc MB phases 0/2 and restart window, Quorra stage 2,
  Portal MB, Sea of Simulation stage 2, Daft Punk MB (see disc_multiball.md §5.4).
- Find Flynn items: counting hits bump "ITEMS LIT: RECOGNIZER" (audit 0x76), battle lit bumps "ITEMS COLLECTED:
  RECOGNIZER" (0x77) via FUN_01016188(7,·).
- Each Disc Multiball start raises k, so later battles need more disc hits.

## 10. Reference scenario

`traces/recognizer_and_disc_battle.txt` (watch list = the RAM table above; same as disc_multiball):
start, sw49/50/51/49 → battle at the 4th hit (counts 1,3,4,5), two target hits while lit (1,000 each),
7 disc hits (one extra hit inside the 2 s debounce is ignored), multiball starts.
Key events: 2,500 x3 + deff 108; at 17.29 s audit 0x8d, 200,000, deff 109, rec_remaining 6, bank_down 0.65 s later;
deff 111 + 2,310 per disc hit, remaining 5…0; at 38.11 s 2,000,000, multiball_start balls 3 / save 625 / grace 187,
k 1→2.

## 11. Open questions

- adj 76 / 81: only seen as parameters of the OS motor-driver objects; what the game does when a motor is
  disabled (e.g. bank left up) was not tested.
- Head position table: 3 of 4 steps point to sw56 — physically odd; behaviour on the real machine unknown.
- Multi-player: whether game flag 0x22 (battle lit) is stored per player was not tested.
- FUN_0101c088 (called at multiball start, random 0xbb-0xbe stored per player at 0x211177c) belongs to another
  feature; meaning not traced.
