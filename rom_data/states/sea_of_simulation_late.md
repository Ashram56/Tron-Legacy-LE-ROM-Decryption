# Sea of Simulation, stages 4-8 and completion

Data: `sea_of_simulation_late.json` (facts, the stage-6 chain table, observed SOS variable changes).
Scenario: `traces/sos_stages_4_to_8.txt` → `.jsonl`, watch list `traces/sos_watch.tsv`.

**Pokes used (player 1, after start):**
- the 9 item "lit" bytes = 1;
- items 0-3 "collected" = 1 (item i at 0x2111694 + 0x10*i: byte 0 lit, byte 1 collected).

The VUK then starts SOS, and stages 0-3 are skipped. This complements `rules/modes/sea_of_simulation.md`, which
traced stages 0-3.

| Stage | Needed (sos_needed_mask 0x3b62c) | Per shot | Display | Shots used | Tag |
|---|---|---|---|---|---|
| Skip 0-3 | Collected items | One-time (k+1) M each: 1, 2, 3, 4 M | deff 115, 0x109 | none | observed (the 3 M and 4 M were paid after stage 4 had already been completed) |
| 4 QUORRA | 0x10000 left inner loop | 500,000 | deff 120 | sw44 (first spin) | observed |
| 5 DISC | 0xfc000 (all six major shots) | 600,000 | deff 121 | 43, 37, 44, 39, 34; disc opto sw41 spotted the last (right orbit) | observed |
| 6 LIGHT CYCLE | Starts 0xc8000 (left ramp, right ramp, right orbit); each made shot **adds** its chained shots and removes every shot already made; done when empty, which in practice means all six major shots | 700,000 | deff 122 | 46, 34, 37, then the chained 39, 44, 43 | observed |
| 7 RECOGNIZER | 0x2000 (shot 13, recognizer bank, posted when task 0x7b is idle); 6 counted hits (0x3b680) | 800,000 | deff 123 | 49, 50, 51, 49, 50, 51 | observed |
| 8 TRON | 0x3c (T R O N, shots 2-5) | 900,000 | deff 124 | 1, 2, 3, 4 | observed |

**Stage-6 chain table** (0x040d3748, 6 records of 16 B `{shot id, shot bit, bits added when made, lamp}`):

| Shot made | Adds |
|---|---|
| Left orbit | nothing |
| Left ramp | Left orbit + left inner loop |
| Left inner loop | Right inner loop + right ramp |
| Right inner loop | nothing |
| Right ramp | nothing |
| Right orbit | Right inner loop + right ramp |

## Completion (observed t 85.97)
1. `sos_complete` 0x1026430 sets game flag 0x36 (54).
2. `sos_end` 0x1026754 clears flag 0x34 (52), counts audit 121 and creates task 0x56.
3. Task 0x56 shows **deff 126 "TOTAL"** with sound 0x115 (at 88.25), the same screen as a drain.
4. Play continues in normal mode; the later drain shows the bonus as usual.

**deff 125 "SEA OF SIMULATION COMPLETED" was not shown.** It has no `deff_start` site in the ROM (static scan
including the indirect wrappers) and no deff rule. Its speech 0x113 is inside deff 125, so it never plays in 1.74.

## Contradictions with `rules/modes/sea_of_simulation.md`
- **Stage 6.** The doc lists the needed shots as "right orbit, right ramp, left ramp (0xc8000), chained". The chain
  makes all six shots necessary. The first version of this scenario hit only those three and stalled with mask
  0x34000.
- **Completion.** The doc says completion shows deff 125 with speech 0x113. Observed: deff 126 + 0x115. No code path
  to deff 125 was found.

## Open
- **Skip bonus on tilt.** Paying queued skip bonuses on tilt is from the existing doc and was not re-traced.
- **Stage 6 lamps.** The stage-6 lamp function (0x1025b58) flashes the lamps of the needed shots; this was not checked
  against `lamps.csv`.
