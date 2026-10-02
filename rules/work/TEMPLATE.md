# <Feature name> (one file per feature, in tron/rules/modes/)

Audience: a developer rebuilding the game in MPF/Godot who has NOT read the ROM. Everything they
need to reproduce the behaviour must be here, with exact numbers. No MPF config or code: describe
behaviour, not an implementation. Where the ROM does something odd, say so plainly.

Every rule line ends with its source in brackets: `[0x01007244]` (function address in
tron/code/tron_game_decompiled_v2.c) or `[table 0x040d26c0]`, and a confidence tag when not
read directly: `(inferred)` or `(verified in emulator: traces/<file>.jsonl)`.

## 1. Summary
2-5 sentences a player would understand: what it is, how you light/start it, what it awards, how it ends.

## 2. Settings (operator adjustments)
| Adj # | ROM name | Default | Range | Effect |

## 3. State
Every variable the feature keeps. For each: name (snake_case, prefixed with the feature, e.g. dmb_jackpot),
RAM address, size, scope (**per player** = survives ball end, kept per player; **per ball**; **per game**;
**while mode runs**), initial value, when it is reset, and what changes it.
| Name | RAM | Scope | Init / reset | Meaning |

## 4. How it starts (qualifying / lighting)
Step by step, including counts, "hits needed" formulas, and what is shown/played/lit at each step.

## 5. Behaviour while running
For each switch or shot that matters: a table row
| Trigger (switch # name / shot) | Condition | Effect: score (exact points, x playfield multiplier?) / state change | Display effect (deff id) | Sound call(s) | Lamp / lamp effect | Next state |
Phases as sub-sections if the feature has phases. Give formulas in plain math with caps.

## 6. How it ends
Timers (give ticks AND milliseconds; 1 tick = 16.26 ms unless you measured otherwise), drains,
completion, what is awarded at the end, what carries over to the next ball/feature.

## 7. Media
| When | Display effect (deff id + what it shows, text strings) | Sound calls (id, kind, samples) | Lamp effect (leff id) | Ramp tube show (id) |
Use ids from the ROM. Name the asset in tron/mpf_package only after checking it against
tron/rules/work/asset_audit.md (that package has known errors).

## 8. Lamps
Which inserts (lamp # and name from tron/io/lamps.csv) show this feature's state, and how
(on / flash / off) in each state. Lamp groups: table 0x040e3acc.

## 9. Interactions
Priorities and conflicts with other features (what it blocks, what blocks it, stacking with
multiballs, what happens on tilt, ball save, extra ball, end of ball), and which other features
read or write its state.

## 10. Reference scenario
A tron_ref scenario script that exercises the feature and the expected key events
(scores, deffs, sounds) as seen in the trace. Save the script as
tron/rules/traces/<feature>.txt and the trace as tron/rules/traces/<feature>.jsonl.

## 11. Open questions
Anything not resolved, with what you tried.
