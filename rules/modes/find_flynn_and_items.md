# Find Flynn and the wizard items

## 1. Summary
The ZEN rollover (sw12) starts Find Flynn. A red arrow roves across the six major shots, and hitting the shot under the arrow (or the one it just left or is moving to) "finds Flynn". That scores 250,000, plus 25,000 for every earlier find, capped at 750,000. Find Flynn is one of nine "items" (FLYNN, GEM, CLU, ZUSE, QUORRA, DISC, LIGHT CYCLE, RECOGNIZER, TRON) shown on the centre inserts. Each feature *lights* its item when started and *collects* it when completed. All nine lit qualifies Sea of Simulation. All nine collected qualifies the Portal.

## 2. Settings (operator adjustments)
No adjustment specific to Find Flynn or the items was found.

## 3. State
| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| ff_pos | 0x0003af9c (u32) | while mode runs | 0 at start [0x0100d698] | Current arrow position 0-5 |
| ff_next | 0x0003afa0 (u32) | while mode runs | - | Next position |
| ff_prev | 0x0003afa4 (u32) | while mode runs | - | Previous position |
| ff_started | 0x02111664 (u8, [player-1]) | per player (game) | 0 at game start (event 0x26) | Find Flynn starts |
| ff_completed | 0x02111668 (u8, [player-1]) | per player (game) | 0 at game start | Finds. Sets the next value |
| item_stats[i] | 0x02111694 + 0x10*i + 4*(player-1) (u32) | per player (game) | - | byte 0 = times lit (0 = not lit); byte 1 = times collected [0x01016188] |
| items table | table 0x040d2dd0 (24 bytes per item) | ROM | - | {mask, name msg 0x5d3+i, lamp, audit lit, audit collected, 50,000, 250,000, leff 0x15+i, tube 0x5d+i} |

Item index i: 0 FLYNN, 1 GEM, 2 CLU, 3 ZUSE, 4 QUORRA, 5 DISC, 6 LIGHT CYCLE, 7 RECOGNIZER, 8 TRON.

## 4. How it starts (qualifying / lighting)

### Find Flynn [0x0100d698]
- sw12 ZEN rollover starts it if all of these hold:
  - task 0xd1 is not already running;
  - SOS is not running;
  - no portal;
  - no multiball.
- The ZEN award itself (42,000 etc.) is scored too [0x0103129c].
- On start:
  - ff_pos = 0 (left orbit); ff_started += 1;
  - FLYNN item lit (audit 0x68); audit 0x87 FIND FLYNN STARTED;
  - deff 136 "SHOOT ROVING RED ARROW TO FIND FLYNN", leff 156, tube 13;
  - task 0xd1 starts with flags 0, so it is not killed by the end-of-ball task kill. It does stop at ball end in practice (see section 6).

### Roving arrow (task 0xd1)
Each cycle:
1. Sleep 125 ticks (2.03 s).
2. Choose the next position. It bounces back and forth over 0..5.
3. Sleep 15 ticks (244 ms).
4. prev = cur, cur = next.
5. Sleep 31 ticks (504 ms).

One cycle = 171 ticks = 2.78 s (verified: next changed 2.06 s after the start).

| Position | Shot | Lamp group | Lamp |
|---|---|---|---|
| 0 | left orbit (sw43) | 0x40 | 16 L. LOOP ARROW |
| 1 | left ramp | 0x41 | 49 LEFT RAMP ARROW |
| 2 | left inner loop | 0x42 | 64 L. INNER LOOP ARROW |
| 3 | right inner loop (sw39) | 0x43 | 57 R. INNER LOOP ARROW |
| 4 | right ramp | 0x44 | 56 R. RAMP ARROW |
| 5 | right orbit (sw46) | 0x45 | 33 R. LOOP ARROW |

leff 157 flashes the current arrow.

### Items [0x01016188]
FUN_01016188(item, 1) = light; (item, 2) = collect. Each call increments the byte and bumps audit 0x68+2i (lit) or 0x69+2i (collected).

| Item | Lit by | Collected by |
|---|---|---|
| FLYNN | Find Flynn start | Find Flynn completed |
| GEM | GEM hurry-up start [0x01013d2c] | GEM award [0x01013e50] |
| CLU | CLU hurry-up start | CLU awards |
| ZUSE | Zuse fast scoring start | zuse_target_hit |
| QUORRA | Quorra MB start | Quorra super jackpot |
| DISC | Disc MB start | blue disc shots |
| LIGHT CYCLE | LC MB start | light_cycle_mb_shot |
| RECOGNIZER | FUN_010201e4 | FUN_010201e4 |
| TRON | each TRON award start and each TRON completion | all three TRON awards started (tron_targets.md) |

A Sea of Simulation stage completion also collects that stage's item.

## 5. Behaviour while running
| Trigger | Condition | Effect | Display | Sound | Lamp | Next state |
|---|---|---|---|---|---|---|
| Shot at position cur, next or prev | task 0xd1 running | min(250,000 + 25,000 x ff_completed, 750,000) points; ff_completed += 1; FLYNN item collected (audit 0x69); audit 0x88; kill task 0xd1 [0x0100d79c on_find_flynn_completed] | deff 137 "FLYNN FOUND" + value | 0x0e7 | leff 158 | tube 15 | ended |
| Other major shot | - | normal shot scoring only | - | - | - | running |
| sw12 again | running | ZEN only (no restart) | - | - | - | running |

Values: 1st find 250,000; 2nd 275,000 (both verified); ... 21st and later 750,000.

**Item lamps** [0x010164a0]: off = not lit; flashing = lit; on = collected.

| Lamp | Item |
|---|---|
| 27 | CENTER FLYNN |
| 25 | GEM |
| 24 | CLU |
| 23 | ZUSE |
| 22 | QUORRA |
| 21 | DISC |
| 20 | LIGHT CYCLE |
| 19 | RECOGNIZER |
| 18 | TRON |

## 6. How it ends
- Found: see section 5.
- **Drain ends it** (verified in emulator: traces/find_flynn_and_items.jsonl). The arrow was at position 1, so a left orbit (position 0 = prev) would still have counted, but the left orbit on the next ball gave nothing. The task was killed at the end of ball (inferred: by the general end-of-ball cleanup).
- There is no timer. The arrow roves until it is found or the ball drains.
- Items:
  - SOS start clears every lit byte (FUN_010160c8(1)).
  - Portal MB start clears both lit and collected (FUN_01016164).
  - All nine lit (FUN_010163ec) is the SOS qualifier. All nine collected (FUN_0101643c) is the Portal qualifier.

## 7. Media
| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| Start | deff 136 "SHOOT ROVING RED ARROW TO FIND FLYNN" | (ZEN 0x0e5 plays at the same time) | leff 156; leff 157 roving arrow | 13 |
| Found | deff 137 "FLYNN FOUND" + value | 0x0e7 | leff 158 | 15 |
| Item lit/collected | per item: name msg 0x5d3+i, leff 0x15+i, tube 0x5d+i (table 0x040d2dd0) | - | 0x15+i | 0x5d+i |

In the trace, the first find coincided with a left-orbit skill shot (deff 83). That shot's leff 91 and tube 51 replaced 158 and 15, and 0x0e7 was not heard. The second find shows the normal media.

## 8. Lamps
See section 4 (arrows 16, 49, 64, 57, 56, 33) and section 5 (item lamps 18-27).

## 9. Interactions
- Blocked by SOS, portal and any multiball.
- ZEN shares sw12: the same hit also spots TRON (tron_targets.md).
- Item lit and collected counts feed SOS (all lit) and the Portal (all collected).
- The item values 50,000 / 250,000 in the item table are read by FUN_01015f7c (callers 0x01000cf8, 0x01000e7c, the end-of-ball bonus) (inferred: bonus per item lit/collected; not traced).

## 10. Reference scenario
`traces/find_flynn_and_items.txt` -> `traces/find_flynn_and_items.jsonl`:
- sw12 at 13.75: 42,000 ZEN, audits 104 (FLYNN lit) and 135, deff 136.
- sw43: 250,000, deff 137, audits 105 and 136.
- sw12 again, then sw43: 275,000, deff 137, sound 0x0e7, leff 158, tube 15.
- sw12, drain, next ball sw43: no Find Flynn award.

## 11. Open questions
- How the 50,000 / 250,000 item values are used in bonus (FUN_01015f7c not traced).
- Which end-of-ball routine kills task 0xd1 (it has flags 0). Behaviour verified, mechanism not.
