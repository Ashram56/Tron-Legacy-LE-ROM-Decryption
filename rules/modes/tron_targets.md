# TRON targets and TRON timed awards

## 1. Summary
Four drop targets spell T-R-O-N (sw1-4). Each new letter scores 10,000. Spelling all four ("TRON completed") scores 100,000 and starts the currently lit timed award: DOUBLE SCORING (all scores x2), SUPER POPS (pop bumpers x3) or SUPER SPINNERS (spinners x3). Each award runs for 30 seconds by default. The lit award flashes on lamps 5-7 and rotates on every pop bumper hit. Starting all three awards in one game collects the TRON item for Sea of Simulation. Letters are kept per player across balls. The running awards end at the end of the ball.

## 2. Settings (operator adjustments)
| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 72 | TRON "SPINNERS" TIMER | 30 | 20-40 | Starting seconds for SUPER SPINNERS [0x0100c558] |
| 73 | TRON "BUMPERS" TIMER | 30 | 20-40 | Starting seconds for SUPER POPS [0x0100c558] |
| 74 | TRON "DOUBLE SCORING" TIMER | 30 | 20-40 | Starting seconds for DOUBLE SCORING [0x0100c558] |
| 80 | DISABLE DROP TARGETS | 0 | 0-1 | Passed to the bank constructor. Disabled targets count as already collected when letters reset [0x0100b294] [0x0102c358] (inferred) |

## 3. State
Per-player arrays are indexed [player-1]. The address given is player 1's.

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| tron_letters | 0x02111848 (u8) | per player | 0 at game start. Set to the mask of disabled targets on completion [0x0102c358] | Bitmask of collected letters: T=1, R=2, O=4, N=8 [table 0x040d3c90] |
| tron_completions | 0x02111840 (u16) | per player (game) | 0 at game start | Times TRON was completed, capped at 0xffff. Shown as "%d TRON" in deff 106 [0x0102c588] |
| tron_award_lit | 0x0211163c (u8) | per player | Set to 1 then rotated (=2 BUMPERS) at every ball start [0x0100c154] | Award that TRON completion will start: 1 DS, 2 BUMPERS, 4 SPINNERS, 0 none |
| tron_award_running | 0x02111640 (u8) | per player, cleared each ball | 0 at ball start [0x0100c154] | Bitmask of running awards |
| tron_award_started_set | 0x02111644 (u8) | per player (game) | 0 at game start (event 0x26) [0x0100c0bc]; cleared when it reaches 7 | Awards started at least once since the last TRON item collect |
| tron_item_count | 0x02111648 (u8) | per player (game) | 0 at game start [0x0100c0bc] | Number of times all three awards were started |
| tron_ds_secs | 0x0003af58 (u8) | while mode runs | 0 at ball start | DOUBLE SCORING seconds left (copy of the start value at 0x3af5c) |
| tron_bumpers_secs | 0x0003af60 (u8) | while mode runs | 0 at ball start | SUPER POPS seconds left (start copy 0x3af64) |
| tron_spinners_secs | 0x0003af68 (u8) | while mode runs | 0 at ball start | SUPER SPINNERS seconds left (start copy 0x3af6c) |
| tron_repeat_sound_flag | 0x0003b740 (u8) | while machine on (inferred) | - | Picks sound 0x04a (first time) or 0x04b (later) for an already-collected letter [0x0102c588] |
| tron_bank | 0x0003b744 (object) | - | - | Generic drop-bank object: coil 3, switches {1,2,3,4}, reset task 0x76, per-player state 0x0211184c [0x0100b294] |
| (u16 counters) | 0x0211164c / 54 / 5c | per player (game) | 0 at game start [0x0100c0bc] | Cleared with the award state. Meaning not traced (inferred: per-award statistics) |

## 4. How it starts (qualifying / lighting)
1. **Targets.** A switch counts only when its drop is up (bank state == 1). The bank then marks it down. Hitting a target that is already down does nothing (verified in emulator: traces/tron_targets.jsonl) [0x0100b4b8].
2. **Hook order for every counted target** [0x0100b050]:
   - event 0x6b(sw);
   - Zuse target hit (4);
   - End of Line shot score;
   - Sea of Simulation shot id 2/3/4/5 for T/R/O/N;
   - the TRON letter rule [0x0102c588] with (mask, lamp) T=(1, lamp 4), R=(2, 3), O=(4, 2), N=(8, 1);
   - 30 points x the bank multiplier at 0x38180 [0x0102a188];
   - lamp refresh.
3. **Letter rule** [0x0102c588]. If the anti-repeat task 0x77 is running, nothing happens.
   - **New letter, not the last one, ZEN not active:** store the bit; 10,000 points; deff 107; leff 38; sound 0x04c.
   - **Last letter, or any new letter while ZEN (task 0xcc) is active:** this is TRON completed (see 5.1). With ZEN the game also plays speech 0xe6 and decrements the ZEN count 0x021118bc.
   - **Letter already collected:** 450 points; leff 39; sound 0x04a the first time, 0x04b after that (verified in emulator: traces/tron_targets.jsonl).
4. **Bank reset.** When all 4 drops are down, or flag 0x1d is set at a ball start (event 0x13), task 0x76 pulses coil 3 (DROP TARGET BANK). It tries up to 3 times, 15 ticks (244 ms) apart, then re-reads the switches [0x0100afac] [0x0100b1a4] [0x0100bcdc] [0x0100bf04]. Letters stay collected after a bank reset. Only the drops come back up.
5. **Lit award.**
   - At each ball start the running set is cleared, timers are zeroed and lit = 1. Lit is then rotated once, so **BUMPERS is lit at every ball start** (verified in emulator) [0x0100c154].
   - Each pop bumper hit rotates the lit award [FUN_0100c470 called from the pop handler] (verified: BUMPERS -> SPINNERS, traces/flynns_arcade.jsonl).
   - Rotation table, indexed by [running*8 + lit] [table 0x040d2848]:

| running \ lit | 0 | 1 | 2 | 4 | others |
|---|---|---|---|---|---|
| 0 | 1 | 2 | 4 | 1 | 1 |
| 1 (DS) | 2 | 2 | 4 | 2 | 2 |
| 2 (BUMPERS) | 1 | 4 | 1 | 1 | 1 |
| 3 | 4 | 4 | 4 | 4 | 4 |
| 4 (SPINNERS) | 1 | 2 | 1 | 1 | 1 |
| 5 | 2 | 2 | 2 | 2 | 2 |
| 6 | 1 | 1 | 1 | 1 | 1 |
| 7 | 0 | 0 | 0 | 0 | 0 |

  With nothing running the lit award cycles BUMPERS -> SPINNERS -> DS -> BUMPERS. A running award is never chosen. With all three running nothing is lit.

## 5. Behaviour while running

### 5.1 TRON completed [0x0102c588]
| Trigger | Condition | Effect | Display | Sound | Lamp | Next state |
|---|---|---|---|---|---|---|
| 4th new letter (or a new letter during ZEN) | task 0x77 not running | Letters reset to the disabled-target mask [0x0102c358]. Start the lit award [0x0100c7bc]. tron_completions += 1. TRON item lit (audit 0x78) [FUN_01016188(8,1)]. 100,000 points. Restart task 0x77 for 10 ticks (163 ms) to block double completion | deff 106 "%d TRON" / "COMPLETED" (task 0x9f waits up to 310 ticks for deff 107 to finish first) | speech 0x04e if the started award was BUMPERS, else 0x04d; deff 106 also plays 0x04f | leff 40 | letters cleared |

The TRON completion's own letter still scores the 30-point bank value. It does not score the 10,000 letter value (verified: 22,000 + 100,000 + 30 at completion, traces/tron_targets.jsonl).

### 5.2 Starting the lit award [0x0100c7bc]
- **If nothing is lit** (all three running): 500,000 points and sound 0x105. No award starts.
- **Otherwise:**
  - If no timed feature is running (FUN_0100f930), clear flag 0x2c. This re-enables the arcade MORE TIME award.
  - Start the award task (flags 0x100, so it is killed at the end of the ball):

    | Award | Task | Sound | Effect while its task runs |
    |---|---|---|---|
    | DS | 0xc6 | 0xff | score event 0x4c hook doubles every score [0x0100c1c0] |
    | BUMPERS | 199 (0xc7) | 0x101 | pop value x3 [0x0101c3a4] |
    | SPINNERS | 200 (0xc8) | 0x103 | spinner value x3 [0x01029ab0] [0x01029e2c] |

  - 22,000 points; deff 112 (arg = award).
  - running |= award. TRON item lit again (a second bump of audit 0x78 per completion; verified).
  - started_set |= award. When started_set == 7: tron_item_count += 1, TRON item collected (audit 0x79) [FUN_01016188(8,2)], started_set = 0.
  - lit = 0, then pick the next lit award from the table in section 4.

### 5.3 Award timer [0x0100c558]
One task per running award. Each task:
1. Loads its own counter from its adjustment (seconds).
2. Loops while **any** of the three counters is nonzero:
   - 10 x (sleep 6 ticks), so one "second" = 60 ticks = 975.6 ms (measured 0.98-1.0 s).
   - The BUMPERS task also runs a bumper lamp chase each step [0x0100c514].
   - If task 0xa0 or 0xa2 (Sea of Simulation start / skip-award shows) is running, the 10-step count restarts at 9. This pauses the clock.
   - Then **every** nonzero counter is decremented by 1.
3. At the end: running &= ~award; if nothing is lit, lit = this award; lamp refresh.

**ROM quirk (verified in emulator: traces/tron_targets.jsonl):**
- Every running award task decrements all three counters. With two awards running, each counter drops 2 per second. Example: BUMPERS 30 s ran out after 18 s once DS started 4 s in.
- Every task also stays alive until all counters are 0. So an award whose counter ran out keeps its effect until the last award finishes. In the trace the BUMPERS bit cleared 0.7 s after DS ended, 21.6 s after it started.
- DS ran 30 -> 0 in 14.7 s.
- A faithful rebuild should keep both behaviours.

**MORE TIME** from Flynn's Arcade refills every running counter to its start value [0x0100f98c] (refill helpers 0x0100d35c / 0x0100d3a0 / 0x0100d3e4).

## 6. How it ends
- Each award ends when the timers run out (section 5.3): 30 s nominal = 30 x 60 ticks = 1800 ticks = 29.3 s, shorter when awards overlap.
- At the end of the ball all award tasks are killed (flag 0x100). The next ball start resets running, the timers and lit (= BUMPERS) [0x0100c154].
- Carried over between balls: letters, completions, started_set and item counts (per player).
- Game start (event 0x26) clears started_set, item count and the u16 counters [0x0100c0bc]. Letters and completions are reset by the per-player NVRAM init (inferred).

## 7. Media
| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| New letter | deff 107: "COLLECT" / "FOR TIMED AWARD" with letter images (arg old letters, new letter) [0x0102c588] | 0x04c | leff 38 | - |
| Letter already collected | - | 0x04a first time, then 0x04b | leff 39 | - |
| TRON completed | deff 106: "%d TRON" / "COMPLETED", 20 frames x 6 ticks then speech, hold 10 ticks | speech 0x04e (BUMPERS) or 0x04d (others); 0x04f inside deff | leff 40 (arg 0x1f) | - |
| Award start | deff 112 (24 frames x 4 ticks, then 43 x 3 ticks): DS "DOUBLE SCORING" / "ALL SCORES DOUBLED"; BUMPERS "SUPER POPS" / "POPS SCORE 3X"; SPINNERS "SUPER SPINNERS" / "SPINNERS SCORE 3X" | start 0xff / 0x101 / 0x103; speech at frame 20: 0x100 / 0x102 / 0x104 | - | - |
| Nothing lit when TRON completes | - | 0x105 | - | - |

## 8. Lamps
| Lamp | Name | State |
|---|---|---|
| 1-4 | TRO(N), TR(O)N, T(R)ON, (T)RON | Collected = on, not collected = flashing [0x0102c3f0]. The bank rule also drives lamps 4, 3, 2, 1 [0x0100b1dc] |
| 5 | DOUBLE SCORING | running = on; lit = flashing; else off [0x0100c2a0] |
| 6 | BUMPERS | same |
| 7 | SPINNERS | same |
| 46 / 47 / 48 | LEFT / RIGHT / BOTTOM BUMPER | SUPER POPS running: 46 on, 47 and 48 off (plus the chase from 0x0100c514). Otherwise 46 and 47 on, 48 on [0x0100d20c] |
| 64 / 33 | L. INNER LOOP ARROW / R. LOOP ARROW | on while SPINNERS runs [0x0100d20c] |

## 9. Interactions
- **ZEN rollover** (sw12, 42,000, ZEN count +1, task 0xcc, deff 100, sound 0xe5) [0x0103129c]. While task 0xcc runs, the next new TRON letter completes TRON at once.
- **Pop bumpers** rotate the lit award on every hit.
- **Flynn's Arcade:**
  - MORE TIME (weight 100) is offered only while a timed feature runs (FUN_0100f930 includes the TRON awards) and flag 0x2c is clear. MORE TIME sets 0x2c.
  - The next award start clears 0x2c only if no timed feature is running.
- **Sea of Simulation:** T/R/O/N are shot ids 2-5. The TRON stage (stage 8) needs all 4 targets. The 0x0100b050 hook order means the SOS shot is posted before the letter rule.
- **Zuse** target hit (4) and the **End of Line** shot score run on every counted drop.
- DS doubles all score events (event 0x4c hook), including other modes' awards.
- Items: TRON is lit on each completion and award start, and collected when all three awards have been started.
- Dead code: FUN_0100ca20 (clear all awards) and FUN_0102c7e4 (spot a TRON letter) have no callers.

## 10. Reference scenario
`traces/tron_targets.txt` -> `traces/tron_targets.jsonl` (fixed tron_ref build). Expected:
- sw1 at 13.75: deff 107, sound 0x04c, 10,000 + 30.
- sw1 again: nothing (drop is down).
- sw2/3/4: letters 3, 7, then completion at 17.51: sound 0x101, 22,000, deff 112, 100,000, 30, completions=1, lit 2->1, running=2, started_set=2, deff 106, speech 0x04e. BUMPERS counter 30 -> 29 at +1.0 s.
- Second TRON at 23.72: DS starts (sound 0x0ff, speech 0x04d), lit=4, running=3. Both counters then drop twice per second. BUMPERS hits 0 at 35.50, DS hits 0 at 38.43, BUMPERS bit cleared at 39.12.
- Drain, ball 2: lit set to 2 (BUMPERS). T again -> 450, sound 0x04a. R again -> 450, sound 0x04b.

## 11. Open questions
- What the per-player u16 counters 0x0211164c/54/5c count. They are cleared at game start but no reader was traced.
- Exact effect of adj 80 DISABLE DROP TARGETS on the letter mask. Inferred from FUN_0102c358, not run.
