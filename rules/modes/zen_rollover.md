# ZEN rollover (sw12)

Audience: a developer rebuilding Tron Legacy LE 1.74 in MPF/Godot. Addresses refer to
`tron/code/tron_game_decompiled_v2.c` (function headers `// ==== <addr>`). 1 tick = 16.26 ms.
Reference trace: `traces/zen_rollover.jsonl` (scenario `traces/zen_rollover.txt`, factory settings, no pokes).

## 1. Summary
The ZEN rollover (sw12) is a "TRON letter helper".
- **Rollover hit**: when no multiball is running, each hit scores 42,000 and banks one **ZEN charge**. While at
  least one charge is banked, the ZEN flasher (coil 17) blinks.
- **Using a charge**: the next TRON standup that would light a *new* letter (other than the last one) uses one
  charge. Instead of lighting that letter, it completes T-R-O-N at once: 100,000, the TRON award and "TRON COMPLETED".
- **Persistence**: charges carry over between balls and reset only on the player's first ball.

There is no timer, no lit state to qualify, and no end other than running out of charges.

## 2. Settings (operator adjustments)
None [0x0103129c, 0x01031208].

## 3. State
| Name | RAM | Size | Scope | Init / reset | Meaning |
|---|---|---|---|---|---|
| zen_charges | 0x021118bc +2*(p-1) | 2 | per player (game) | 0 on the player's first ball (event 0x26) [0x0103116c] | banked ZEN charges (cap 65535) [0x0103129c] |
| (task 0xcc) | – | – | while charges > 0 | killed on event 0x26 and when charges reach 0; started at ball start if charges > 0 [0x010311ac, in the ball-start hook list 0x0003e3ec] | ZEN flasher blink task; "ZEN active" = this task is running [task_cc 0x01031138] |

Related (owned by the TRON targets feature, see `modes/tron_targets.md`):
- tron_letters 0x02111848 +(p-1) (bits 1 T, 2 R, 4 O, 8 N);
- tron_completions 0x02111840 +2*(p-1).

## 4. How it starts
### 4.1 sw12 ZEN ROLLOVER handler [0x0102ac5c]
The handler runs in this order:
1. 0x01028b74 (combo/lane hook).
2. `zuse_target_hit(4)`: a fast-scoring hit if ZUSE FS runs.
3. 0x01005074 (End of Line shot score).
4. `on_find_flynn_started` [0x0100d698].
5. **ZEN** [0x0103129c].
6. Switch score 1,090 [0x0102a188].

ZEN [0x0103129c], only when no multiball is running [0x0100f918: flags 0x27, 0x24, 0x2b, 0x29, 0x37]:
1. zen_charges += 1.
2. **42,000** (flat `score_add`).
3. If the flasher task 0xcc is not running (it was 0 charges): start task 0xcc and show deff 100 "ZEN".
4. Sound 0xe5.

During a multiball, sw12 gives only the switch score and the other hooks.

| Trigger | Condition | Effect | Display | Sound | Lamp / coil |
|---|---|---|---|---|---|
| sw12 | no multiball, ZEN not active | charges 0→1; 42,000; flasher task starts | deff 100 "ZEN" | 0xe5 (sfx 0x051) | leff 117 (via deff 100); coil 17 blinking |
| sw12 | no multiball, ZEN active | charges += 1; 42,000 | – | 0xe5 | – |
| sw12 | multiball running | nothing from ZEN | | | |

(verified in emulator: traces/zen_rollover.jsonl, 19.12 s: 42,000 + 1,090 with deff 100, charges 1; 21.31 s: 42,000 with
no deff, charges 2)

## 5. Behaviour while active (charges > 0)

### 5.1 Flasher
Task 0xcc: every 5 ticks it increments a counter. Every 7th step (35 ticks = 569 ms) it pulses coil 17 ZEN FLASHER
with `coil_pulse(17, 18)` [task_cc].
(verified: one flasher pulse every ~0.57 s; the trace shows ~0.24 s "on" per pulse)

### 5.2 Using a charge (TRON standups sw1–sw4) [FUN_0102c588 → 0x01031208(1)]
The TRON target handler takes this path only when the 10-tick TRON lockout (task 0x77) is not running:
- **Letter already lit** (and not all four lit): the normal repeat path. 450 points and sound 0x4a/0x4b. No
  charge is used.
- **New letter that would complete T-R-O-N** (the last one): the normal completion. No charge is used.
- **New letter that would not complete**: if ZEN is active (task 0xcc), a charge is used:
  1. speech 0xe6;
  2. zen_charges -= 1 (not below 0);
  3. task 0xcc is killed at 0;
  4. then **TRON is completed now**:
     - letters reset [0x0102c358];
     - the lit TRON award starts [0x0100c7bc];
     - tron_completions += 1;
     - SOS item 8 level 1;
     - deff 106 "TRON COMPLETED" via task 0x9f;
     - **100,000**;
     - lockout task 0x77 for 10 ticks.

  The letter itself is not lit, and the 10,000 / deff 107 "new letter" award is skipped.
  If ZEN is not active: the normal path (letter lit, 10,000, deff 107).

The TRON targets are always active (0x0102c4a4 returns 1), so a charge can be used during multiballs too (inferred
from code). Only *earning* a charge needs "no multiball".

Verified (verified in emulator: traces/zen_rollover.jsonl):
- **Charge used at 24.47 s.** With T lit and 2 charges, an R hit:
  - speech 0xe6, charges 2→1, letters 1→0, completions 0→1;
  - 100,000;
  - the TRON award (22,000 + deff 112, from 0x0100c7bc), then deff 106.
- **Charge used at 28.65 s.** O on empty letters: charges 1→0, completions 2, and the flasher stopped.
  - Score delta 244,060 = 2 x 122,030, because the TRON award running then doubled the score.
- **Normal letter at 32.83 s.** N with 0 charges: lit normally, 10,000 (doubled), deff 107.

## 6. How it ends
- Charges run out (each use takes one). The flasher task is killed at 0 [0x01031208].
- **End of ball** does **not** clear charges, and the flasher keeps blinking through the drain and bonus. At the next
  ball start, task 0xcc is (re)started if charges > 0 [0x010311ac].
  (verified: charge banked at 35.03 s, flasher still pulsing during bonus/ball 2; on ball 2 at 48.48 s a T hit with N lit
  used the charge and completed TRON: 0xe6, charges 1→0, completions 3)
- Event 0x26 (the player's first ball) clears charges and kills the task [0x0103116c].
- With several players, the ball-start hook re-checks the current player's charges. So the flasher follows the
  player who is up (inferred from code).

## 7. Media
| When | Display effect | Sound calls | Lamp effect (leff) | Coil |
|---|---|---|---|---|
| first charge (ZEN not active) | deff 100: "ZEN" over the status panel, 5 x 6 ticks (ends early if 0x0102a284 is true), hold 10 | 0xe5 (sfx 0x051) [every charge] | 117 (24 lamp-group steps x 2 ticks, table 0x040d6e84) | – |
| while charges > 0 | – | – | – | 17 ZEN FLASHER pulsed every 35 ticks |
| charge used | (TRON completed: deff 106; the TRON award deff 112) | speech 0xe6 (0x352 0x3a9 0x2bc 0x239 0x23e 0x25c 0x262 0x269) | (TRON: leff 40) | |

leff 118 (three coil-group pulses, 15 ticks apart) sits next to leff 117 in code. No caller from the ZEN path was found.
Package names: event_map row 100 = deff 100.

## 8. Lamps
No playfield lamp shows ZEN charges. The ZEN FLASHER (coil 17, a flasher driven as a coil) is the only indicator
[task_cc]. The TRON letter lamps are owned by the TRON targets rule.

## 9. Interactions
- **TRON targets**:
  - ZEN completes T-R-O-N early, which starts the TRON timed award (SPINNERS / BUMPERS / DOUBLE SCORING; see
    `tron_targets.md`) and lights SOS item 8.
  - Using a charge counts as a completion for every purpose: tron_completions, the TRON award and audit 0x78.
- **Multiballs**: block earning charges only.
- **ZUSE fast scoring**: sw12 is an FS hit.
- **Find Flynn**: sw12 also calls `on_find_flynn_started`. In the trace the first sw12 hit also gave audit 135 and
  deff 136 from that feature (0x0100d718), plus audit 104 from 0x01028b74.
- **Double scoring**: when the TRON DOUBLE SCORING award runs, the 42,000 is doubled like any score (verified 86,180 at
  35.03 s).

## 10. Reference scenario
`traces/zen_rollover.txt` → `traces/zen_rollover.jsonl`. The watch file uses the RAM names in `work/ram/zen_rollover.tsv`.
Key events:
- 16.93 s: T lit normally.
- 19.10 s and 21.29 s: ZEN gives charges 1 and 2. deff 100 shows once, and the flasher starts.
- 24.47 s: R uses a charge and TRON completes.
- 28.65 s: O uses the last charge and TRON completes again. The flasher stops.
- 32.83 s: N lit normally.
- 35.01 s: ZEN gives charge 1.
- 37.2 s: drain. The charge is kept and the flasher keeps going.
- 48.48 s: on ball 2, T uses the charge and completes TRON.

## 11. Open questions
- The ZEN flasher "on" time is coil_pulse(17, 18). The unit of 18 (ms or 1/x tick) was not resolved; the trace shows
  ~0.24 s.
- No caller was found for leff 118.
- A charge used during a multiball was not traced. That behaviour is read from code.
