# Sea of Simulation (SOS)

## 1. Summary
Sea of Simulation is the mini-wizard mode. Light all nine items (FLYNN, GEM, CLU, ZUSE, QUORRA, DISC, LIGHT CYCLE, RECOGNIZER, TRON) and shoot the video game eject (VUK) to start it for 1,000,000. You then play nine stages in item order. Each stage asks for that item's shot(s) and pays 100,000-900,000 per shot. Completing a stage collects its item. Stages whose item is already collected are skipped and pay a one-time bonus of (stage number) million. SOS is single-ball and ends when the ball drains (with a TOTAL display) or when the last stage is completed.

## 2. Settings (operator adjustments)
No SOS-specific adjustment found.

## 3. State
| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| sos_total | 0x0003b624 (u32) | while mode runs | 1,000,000 at start [0x01026520] | Points earned in SOS (shown in deff 126) |
| sos_stage | 0x0003b628 (u32) | while mode runs | 0 at start | Current stage 0-8 |
| sos_needed_mask | 0x0003b62c (u32) | while mode runs | set by each stage's setup fn | Shot-id bits still needed in this stage (bit = 1<<shot id) |
| sos_skip_queue | 0x0003b630 (u32) + paid flag 0x0003b634 (u8), stride 8, 9 entries | while mode runs | - | Skip bonus value and "paid" flag per stage [0x01026794] |
| sos_count | 0x02111800 (u8, [player-1]) | per player (game) | 0 at game start | SOS starts by this player |
| sos_skip_bonus_flags | 0x02111804 (u16, [player-1]) | per player (game) | 0 at game start (event 0x26) | Bit k = the skip bonus for stage k has been given (verified: bit 2 set when CLU was skipped) |
| sos flags | game flags 0x33, 0x34 (running), 0x35, 0x36 (completed) | - | start: 0x34 set, 0x35/0x36 clear, 0x33 set [0x01026520] | Running/completed status read by other features |

## 4. How it starts (qualifying / lighting)
1. Qualify: all nine items lit (item byte 0 != 0 for all) [FUN_010163ec]. See find_flynn_and_items.md for who lights each item.
2. Start at the VUK (sw11) [0x0102eddc -> 0x010265f4 -> 0x01026520]. Conditions:
   - all items lit;
   - no multiball;
   - !FUN_010077ac (inferred: portal not ready / running);
   - SOS not already running.

   The arcade award (if lit) is collected first on the same VUK shot (verified: 500K then SOS).
3. On start:
   - task 0xa0 (deff 113 intro);
   - 1,000,000 points, which start sos_total;
   - stage = 0 and the stage is set up [0x01026490];
   - flags as above;
   - sos_count += 1;
   - every item's lit byte is cleared [FUN_010160c8(1)].
   - Audit 0x67 SOS STARTS was **not** bumped in the trace, and no writer of audit 0x67 was found in game code.
4. While task 0xa0 or 0xa2 runs, the TRON award timers pause (tron_targets.md).

## 5. Behaviour while running

### Shot ids [table 0x040d35dc, value = 1<<id]
| Id | Shot | Id | Shot |
|---|---|---|---|
| 0 | VUK (sw11) | 1 | disc opto (sw41) |
| 2-5 | T, R, O, N drop targets (sw1-4) | 6-8 | C, L, U helmets (sw25, 14, 28) |
| 9-12 | Z, U, S, E targets (sw7, 8, 48, 13) | 13 | recognizer 3-bank |
| 14 | left orbit | 15 | left ramp |
| 16 | left inner loop | 17 | right inner loop |
| 18 | right ramp | 19 | right orbit |

Features post shots with simulation_shot(id, quiet). Example: the drop hook posts 2-5 (tron_targets.md).

### Stages [table 0x040d37d8]
Each stage row is 40 bytes: {item, lamp, setup fn, value fn, leff fn, display task, msg, shot fn, spot fn, audit}.

| k | Item (lamp) | Needed shots | Points per shot | Display msg | Stage deff |
|---|---|---|---|---|---|
| 0 | FLYNN (27) | VUK | 100,000 | "SHOOT" / "FLYNNS ARCADE" | 116 |
| 1 | GEM (25) | right inner loop | 200,000 | "SHOOT" / "GEM" | 117 |
| 2 | CLU (24) | VUK + left orbit + left inner loop + right orbit (mask 0x94001) | 300,000 | "SHOOT" / "CLU HELMETS" | 118 |
| 3 | ZUSE (23) | Z, U, S, E targets | 400,000 each | "SHOOT" / "ZUSE TARGETS" | 119 |
| 4 | QUORRA (22) | left inner loop | 500,000 | "SHOOT" / "QUORRA" | 120 |
| 5 | DISC (21) | the 6 major shots (0xfc000) | 600,000 | "SHOOT" / "DISCS" | 121 |
| 6 | LIGHT CYCLE (20) | right orbit, right ramp, left ramp (0xc8000), chained [table 0x040d3748]; shots already made are excluded | 700,000 | "SHOOT" / "LIGHT CYCLES" | 122 |
| 7 | RECOGNIZER (19) | 6 recognizer bank hits | 800,000 each | "SHOOT" / "RECOGNIZER" | 123 |
| 8 | TRON (18) | T, R, O, N targets | 900,000 each | "SHOOT" / "TRON TARGETS" | 124 |

Stage notes:
- Stage 2 (CLU): completing the C-L-U helmets spots the next needed shot. The helmet letters rotate with the flipper buttons (inferred from code, not run).
- Stage 5 (DISC): the disc opto spots the next needed shot.
- A shot that is spotted quietly (quiet = 1, e.g. the Flynn's Arcade ADV. SOS award) scores 10% of the stage value (stage 0: 10,000 instead of 100,000). It is shown by task 0xa1 instead of the stage deff [0x010248ec] (read for stage 0; the other stage fns are assumed to follow the same pattern).

| Trigger | Condition | Effect | Display | Sound | Lamp | Next state |
|---|---|---|---|---|---|---|
| Needed shot | its bit is in sos_needed_mask | stage value points (score_add, so x playfield multiplier, x2 under DS); sos_total += points; clear bit | stage deff 116+k | speech 0x10a, then 0x111 | stage leff fn | - |
| Last needed shot of stage | - | item k collected (audit 0x69+2k); stage++ and set-up of the next stage | 116+k, then deff 114 | as above | item lamp on | next stage |
| Stage set-up for an already-collected item | - | stage skipped. First time for this player (bit k of 0x02111804 clear): queue (k+1) x 1,000,000, paid by task 0xa2 / deff 115 (verified 3,000,000 for CLU) | deff 115 | 0x109 | - | next stage |
| Other shot | - | normal scoring | deff 114 (SOS status, shown by a deff rule whenever no other deff runs) | - | - | - |

Verified (traces/sea_of_simulation.jsonl):
- VUK: 100,000, deff 116, audit 105.
- Right inner loop: 200,000, deff 117, audit 107.
- CLU skipped: 3,000,000 via deff 115, sos_total 4,300,000.
- Z, U, S, E: 4 x 400,000 with deff 119 each, ZUSE collected (audit 111).
- Each Zuse target also scored its own 5,000.

## 6. How it ends
- **Completed:** after stage 8, FUN_01026430 sets flag 0x36 and clears 0x34. deff 125 "SEA OF SIMULATION COMPLETED", speech 0x113. Every item is then collected, which qualifies the Portal (find_flynn_and_items.md).
- **Drain:** event 0x1d clears flag 0x34. deff 126 "TOTAL" + sos_total, sound 0x115, speech 0x114 (verified: deff 126 0.54 s after the drain, before bonus deff 25).
- **Tilt (event 0x66)** [0x01026794]: if SOS is active, every queued skip bonus not yet paid is added to the score (and to sos_total). The ROM pays these even on tilt.
- No timer. Lit bytes were cleared at start, so all nine items must be lit again to replay SOS. Items collected in SOS stay collected.

## 7. Media
| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| Start | deff 113 intro (task 0xa0) | 0x107, then 0x106 (1.76 s later) | leff 135 | 65 |
| Running status | deff 114 "SEA OF SIMULATION" + stage msgs (table 0x040d37d8 msg field) | 0x108 at first show; speech 0x112 on the final stage | stage leff fn; leff 134 available | 64 available |
| Stage shot | deff 116+k | 0x10a, then 0x111 | - | - |
| Skip bonus | deff 115 | 0x109 | - | - |
| Completed | deff 125 "SEA OF SIMULATION COMPLETED" | speech 0x113 | - | - |
| Drain | deff 126 "TOTAL" | 0x115, speech 0x114 | - | - |

## 8. Lamps
The stage's item lamp (27, 25, 24, 23, 22, 21, 20, 19, 18) shows the item state: flashing = lit, on = collected [0x010164a0]. The shot arrows for the needed shots are driven by each stage's leff/lamp fn (not individually traced).

## 9. Interactions
- **Blocks:** Find Flynn start, Flynn's Arcade weights (GEM, CLU, DISC, REC are 0 during SOS), and the CLU/GEM qualifiers.
- **Flynn's Arcade:** ADV. SOS gets weight 1101 while flag 0x34 is set, so it is always picked.
- **Multiball:** cannot start during MB.
- **TRON awards:** their timers pause during deffs 113 / 115 (tasks 0xa0 / 0xa2).
- **Portal:** SOS completion collects every item, which is the portal qualifier.
- **Shot hooks:** every feature's shot handler calls simulation_shot. On drop targets it is called before the TRON letter rule.

## 10. Reference scenario
`traces/sea_of_simulation.txt` -> `traces/sea_of_simulation.jsonl`. **Poke used:** all 9 item lit bytes = 1 and CLU collected = 1. Expected:
- VUK at 14.27: skill shot 500,000, arcade 500,000 (audit 83), SOS 1,000,000, flags 52 set, 53/54 clear, 51 set, sos_count 1, lit bytes cleared, deff 113 at 18.46.
- VUK: 100,000, deff 116.
- Right inner loop: 200,000, deff 117, then deff 115 with 3,000,000.
- Z, U, S, E: 400,000 each, stage -> 4 (QUORRA, mask 0x10000 = left inner loop).
- Drain: flag 52 clear, deff 126, sound 0x115.

## 11. Open questions
- Audit 0x67 SOS STARTS: not bumped in the trace and no immediate writer found. Perhaps never written in 1.74.
- What FUN_010077ac checks (assumed portal).
- The CLU helmet rotation with flippers, were read from code and not run. tron_ref now has `button left|right`, so this could be checked.
- Stages 4-8 were not played in the emulator (values read from the stage functions).
