# Flynn's Arcade

## 1. Summary
Flynn's Arcade is the award collected at the video game eject (VUK, sw11). It is lit at the start of every ball and relit by a right orbit shot when no multiball is running. Shooting the VUK while it is lit plays a slot-machine style display and gives one random award from a weighted bag. The awards are 500,000 points, an advance of one of the main features (GEM, CLU, ZUSE, QUORRA, DISC, LIGHT CYCLE, RECOGNIZER, SEA OF SIMULATION), MORE TIME for running timed modes, LIGHT EXTRA BALL or LIGHT SPECIAL. Collecting it unlights the arcade until the next right orbit or ball.

## 2. Settings (operator adjustments)
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 42 | COMPETITION MODE | 0 | 0-1 | When 1, the 500K weight gets +1000, so 500K is always chosen unless SOS is running [0x0100df98] (verified in emulator: traces/flynns_arcade.jsonl) |
| 26 | EXTRA BALL LIMIT | 5 | 0-10 | LIGHT EXTRA BALL weight is 0 once the limit is reached [FUN_0001a034] |
| 27 | EXTRA BALL PERCENTAGE | 25 | 1-50 | Target % for the EB percentage check (see section 4) |
| 22 | SPECIAL LIMIT | 1 | 0-6 | LIGHT SPECIAL weight is 0 once the limit is reached |
| 24 | SPECIAL PERCENTAGE | 10 | 1-50 | Target % for the special percentage check |

## 3. State
| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| arcade_lit | 0x0211166c (u8, [player-1]) | per player | Cleared at game start (event 0x26) [0x0100dd38]. Set at every ball start (event 0x11) [LAB_0100dd64] | 1 = arcade lit [0x0100ddb0] |
| arcade_weights | 0x0003aba4 + 2*i (u16 x 12) | per pick | Rewritten at every pick | Last computed weight per award (entry i = 1..12 at 0x3aba6..0x3abbc) [bag 0x00036d68] |
| arcade_bag | 0x00036d68 | ROM-initialised RAM | - | Bag header {entries 0x040f08dc, 13, 24}. Entries are 24 bytes: {weight fn, award fn, weight out ptr, ?, default weight u16, audit u16} [0x0100debc] |
| more_time_used | game flag 0x2c | per ball (inferred) | Cleared when a TRON award starts while no timed feature runs [0x0100c7bc] | MORE TIME was given and is not offered again |

## 4. How it starts (qualifying / lighting)
1. **Every ball start** (event 0x11) lights the arcade [LAB_0100dd64 -> 0x0100ddb0(1)] (verified: deff 104 at each ball start).
2. **Right orbit** (sw46) lights it if task 0x3c is not running and no multiball is running [0x0102a794].
   - "No multiball" means FUN_0100f918 == 0. It counts the multiball tasks 0x01004be8, 0x01006eec, 0x01018240, 0x0101ce1c and 0x0102f680.
3. Lighting only plays media when the flag goes 0 -> 1: deff 104 "ARCADE IS LIT", leff 115, sound 0x0df [0x0100ddb0].
4. **Collect.** The VUK handler [0x0102eddc] tries the arcade first. Its full order is: arcade award, Portal, Simulation, CLU, Light Cycle, Quorra.
   - The arcade needs: lit, and no multiball [0x0100de3c].
   - Not lit: VUK scores 350, sound 0x0fd, leff 35 (verified).
   - The VUK skill shot (500,000, deff 103) [FUN_01029068] can score just before the arcade on the plunge-to-VUK shot.
5. **Award pick** [0x0100debc]:
   - Each entry's weight function is called with its default weight [FUN_0000c708].
   - **If any weight is >= 1000,** the first entry with the highest weight wins.
   - **Otherwise** r = floor(total * rand32 / 2^32). The award is the first entry whose running sum of weights is > r. Probability = weight / total.
   - Task 0x97 then queues deff 105 (FUN_0100fbb0(0x69, 0xea6, 0x9f)).
   - The award function runs [FUN_0000c84c]. If it returns nonzero, the entry's audit is bumped and arcade_lit is cleared. If it returns 0, task 0x97 is killed and the arcade **stays lit** (inferred from code).

### Award table [bag 0x00036d68, entries table 0x040f08dc]
The table function pointers are the real entry points. The decompile's `// ====` headers sit 4-8 bytes later for some of them (e.g. weight 0x0100df98 -> header 0x0100df9c, award 0x0100dfc4 -> header 0x0100dfcc). Audits are listed as hex (0x53-0x5e = 83-94).

| # | Award | Weight (default rule) | Condition for weight | Award effect | Audit |
|---|---|---|---|---|---|
| 1 | 500K | 100 (+1000 if adj 42 competition, or flag 0xf) [0x0100df98] | always | 500,000 points [0x0100dfc4] | 0x53 |
| 2 | ADV. GEM | 25 | no GEM hurry-up running, SOS (flag 0x34) not running, no portal [0x01013980] | GEM counter 0x02111680 += 1. At the target (3, or 5 if 0x02111678 is set) the GEM hurry-up starts. Scores 250,000 [0x01013a08(1)] | 0x54 |
| 3 | ADV. CLU | 25 | FUN_01001c98: not all items lit, not all collected, no MB, no SOS-ready, no SOS, no portal-ready, no portal | One CLU step [0x01016d14(1)]. Observed 50,000 | 0x55 |
| 4 | ADV. ZUSE | 25 | FUN_01031804 | Zuse advance [0x010339fc(1)] | 0x56 |
| 5 | ADV. QUORRA | 25 | Quorra counter 0x021117ac < 5 etc. [0x0101f384] | 10,000 and one Quorra lock-light step. At 5 it lights Quorra at the VUK (FUN_0102e8c0(2)) [0x0101f410(4,1)] (verified 10,000) | 0x57 |
| 6 | ADV. DISC | 25 | FUN_01020b4c, and not FUN_0102ec38(6), and not all items lit or collected | Disc advance [0x01020da8(2,1)]. Weight was 0 at game start in the trace | 0x58 |
| 7 | ADV. LIGHT CYCLE | 25 | FUN_0101b0dc | Collects the first lit Light Cycle target (masks table 0x040d2978) via light_cycle_target(mask,1) [0x0100e184] | 0x59 |
| 8 | ADV. RECOGNIZER | 100 | FUN_0101ffd8, same item/SOS exclusions | Recognizer advance [0x010201e4(0x32,0x36,1)] (verified: 2,500 and REC item lit, audit 0x76) | 0x5a |
| 9 | ADV. SEA OF SIMUL. | 101 + 1000 while SOS runs (flag 0x34), else 0 | SOS running | Spots the current SOS stage's shot quietly [0x010266c0]. Always chosen during SOS because the weight is > 1000 | 0x5b |
| 10 | MORE TIME | 100 | a timed feature (GEM, CLU, ZUSE or any TRON award) runs [0x0100f930] and flag 0x2c is clear | Refills every running timer to full and sets flag 0x2c [0x0100f98c] | 0x5c |
| 11 | LIGHT EXTRA BALL | 1 | EB limit not reached (adj 26) and the EB percentage check passes | Lights the extra ball at the VUK [0x0102e8c0(1,1)], counter 0x02111894 | 0x5d |
| 12 | LIGHT SPECIAL | 1 | special limit (adj 22) and the special percentage check | Lights the special [0x00024014(1)] | 0x5e |

**Percentage check** for EB and SPECIAL (inferred from the weight functions):
- r = the audit-derived award percentage from FUN_00001bc4(0x10, 0xc0).
- The weight is kept if r == adj, or r + margin < adj (EB: adj 27, margin 3; SPECIAL: adj 24, margin 2). Otherwise it is 0.
- On a fresh machine both kept weight 1 (observed).

**Observed default bag at game start (verified in emulator: traces/flynns_arcade.jsonl):**

| Weight | Award(s) | Chance each |
|---|---|---|
| 100 | 500K, ADV. RECOGNIZER | 28.4% |
| 25 | GEM, CLU, ZUSE, QUORRA, LIGHT CYCLE | 7.1% |
| 0 | DISC, SOS, MORE TIME | 0% |
| 1 | EB, SPECIAL | 0.28% |

The total is 352. While a TRON award runs, MORE TIME = 100 and the total is 452:

| Weight | Award(s) | Chance each |
|---|---|---|
| 100 | 500K, REC, MORE TIME | 22.1% |
| 25 | the five advances | 5.5% |
| 1 | EB, SPECIAL | 0.22% |

## 5. Behaviour while running
| Trigger | Condition | Effect | Display | Sound | Lamp | Next state |
|---|---|---|---|---|---|---|
| sw11 VUK | lit, no MB | random award (section 4) + VUK 350 | deff 105 | 0x0e4, 0x0e1, 0x0e3 (inside deff) | leff 116 | unlit |
| sw11 VUK | not lit, or MB | 350 points; VUK continues with Portal / SOS / CLU / LC / Quorra | - | 0x0fd | leff 35 | - |
| sw46 right orbit | not lit, no MB, task 0x3c not running | light | deff 104 | 0x0df | leff 115 | lit |

**What "advance X" means:** it calls the same function the feature's own shot uses, with a "from arcade" argument of 1. For example:
- GEM: +1 toward the 3 (or 5) needed to start the GEM hurry-up.
- QUORRA: +1 of 5 lock-light steps.
- LIGHT CYCLE: collects one lit LC target.
- SOS: completes the current stage's shot.

The scores come from those features (GEM 250,000; CLU observed 50,000; QUORRA 10,000; REC 2,500).

**What "MORE TIME" does:** every running timer goes back to its start value, for the GEM / CLU / ZUSE hurry-ups and the TRON awards (adj 72-74 seconds) [0x0100f98c]. It cannot be won twice until flag 0x2c is cleared. That happens when a TRON award starts with no timed feature running.

## 6. How it ends
- The arcade is a one-shot award. It is unlit by a successful collect and relit by the right orbit or the next ball start.
- Game start (event 0x26) clears the flag. A multiball blocks both relighting and collecting, but does not clear the flag.

## 7. Media
| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| Lit (0->1) | deff 104: images 0x7f2-0x830 at 3 ticks per frame, "ARCADE IS LIT", hold 10 ticks [0x0100ddb0] | 0x0df | leff 115 | - |
| Award | deff 105 [0x0100e8bc]: see the steps below | speech 0x0e4; 0x0e1 roll loop, stopped at the end; 0x0e3 stop sound | leff 116 | - |
| Not lit at VUK | - | 0x0fd | leff 35 | - |

deff 105 steps:
1. Three random arcade cabinets from table 0x040d2990 (images 0x5c5-0x5c8).
2. A reel of 3 award icons: 2 random decoys from ids 1-12 and the chosen award at a random slot. Icons come from table 0x040d29a0 {id, icon_a, icon_b, unused}.
3. The reel scrolls 4 px every 3 ticks with sound 0x0e1, then stops (0x0e1 stopped, 0x0e3 played).
4. The result blinks every 3 ticks for at least 21 and at most 61 frames, until 0x0e3 ends. Hold 10 ticks.

Messages 0x593 "SHOOT FLYNN'S ARCADE" and 0x61a "FLYNN'S ARCADE IS LIT" exist, but no code reference to them was found.

## 8. Lamps
| Lamp | Name | State |
|---|---|---|
| 45 | FLYNN'S ARCADE | flashing when lit and no multiball; off otherwise [0x0100df3c] |
| 39 / 38 / 40 / 28 | EJECT: QUORRA / LIGHT CYCLE / PORTAL / CLU | other VUK awards lit by FUN_0102e8c0 (counters 0x02111894 EB, 0x02111898 Quorra, 0x0211189c LC, 0x021118a0 Portal, 0x021118a4 CLU) |

## 9. Interactions
- **Multiball** (any of the 5 MB tasks) blocks lighting and collecting.
- **Sea of Simulation:**
  - The VUK collects the arcade *before* SOS can start on the same VUK shot (traces/sea_of_simulation.jsonl: 500K, then SOS starts).
  - During SOS the arcade always gives ADV. SOS. That is only possible on the first SOS VUK, since MB blocks it (inferred).
- **TRON awards / hurry-ups:** MORE TIME weight depends on FUN_0100f930 and flag 0x2c.
- **Deff 45:** **unreachable in 1.74.**
  - Its deff rule (0x3b77c, priority 0x81) needs task 0xa3.
  - Task 0xa3 is created only in FUN_0102e584 (at 0x0102e5a8). That function has no BL/B caller and no pointer anywhere in the ROM. Its neighbour FUN_0102e6a0 is also uncalled.
  - `mov r0,#0xa3` appears only at task kill/check sites. Disassembly search done over the whole game code.
- Tilt / end of ball: no special handling. The flag is relit at the next ball start anyway.

## 10. Reference scenario
`traces/flynns_arcade.txt` -> `traces/flynns_arcade.jsonl` (fixed tron_ref). Expected:
- Ball start: deff 104. A pop bumper rotates the TRON lit award 2 -> 4.
- VUK: skill shot 500,000 (deff 103), then the arcade award with deff 105 (this run: ADV. RECOGNIZER, audit 0x5a, 2,500, REC item lit).
- VUK again: 350 and sound 0x0fd. Right orbit: deff 104.
- TRON completed -> SPINNERS runs. The VUK pick shows MORE TIME weight 100 (500K picked).
- adj 42 = 1: the 500K weight is 1100 and 500K is awarded.
- Drain: next ball deff 104, TRON lit = BUMPERS.

## 11. Open questions
- Exact semantics of FUN_00001bc4(0x10,0xc0) (the EB/special percentage source). Inferred, not run with a non-fresh audit set.
- Whether the msgs 0x593 / 0x61a are used indirectly (no pointer found).
- Why ADV. DISC had weight 0 at game start (FUN_0102ec38(6) or FUN_01020b4c). Not traced further.
