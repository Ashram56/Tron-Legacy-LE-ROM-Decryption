# Tilt and slam

Data: `tilt.json` (`facts` + `observed_event_sequence` from `traces/tilt_modes.jsonl`). Scenarios:
- `traces/gi_and_tilt.txt`: warnings, tilt and the next ball, with GI and tick tracing.
- `traces/tilt_modes.txt`: tilt inside the ball save, Disc Multiball qualification, tilt during the multiball, all
  balls drained. Runs with event tracing and rule/hook dumps.
- `traces/slam_tilt.txt`: slam in a game, then slam in attract (machine reset, emulated watchdog).
- `traces/multiplayer_3p.txt`: tilt in a 3-player game.

Factory settings: adj 32 TILT WARNINGS = 2, adj 38 BALL SAVE = 5 s.

| Trigger | Condition | Effect | Display | Sound | Lamps / GI | Tag |
|---|---|---|---|---|---|---|
| Tilt bob (D17, 0x24564) | Within 62 ticks of the last accepted bob | Ignored | - | - | - | observed |
| Tilt bob | Warnings < adj 32 | Warnings +1 (0x3d4f8); events 0x68, 0x69 | deff 23 DANGER | 0x016, then speech 0x03d 0.5 s later | leff 11: GI off 15 ticks | observed |
| Tilt bob | Warnings = adj 32 | TILT (0x2444c): event 0x66, audit 42, event 0x65, event 0x67; `gf_state` \|= 0x200; class-8 game flags reset (flag 46); flippers/slings off; mode tasks killed | deff 21 TILT | 0x017, then speech 0x03e 1 s later | leff 9: GI off until the drain | observed |
| Any switch while tilted | Descriptor flags lack 0x200 | Handler not run (OS gate in 0xe85c); `base_score_if_not_tilted` 0x102a188 also guards scoring | - | - | - | code |
| Drain while tilted | - | Events 0x1e, 0x1d, audit 8; **no ball save, no bonus** (0x208a0 skips it); event 0x1f; next ball/player; ball start clears 0x200 and the warnings | - | - | GI on when task 0x2a releases leff 9 | observed |
| Slam (D18, 0x23e40) | Not in service | Event 0x55 (veto), `gf_state` \|= 0x200 (512 in game, 528 in attract), tasks killed, event 0x54, task 0x39 (0x23e18) | deff 24 SLAM TILT | 0x018 | leff 12: blackout + GI off | observed |
| Slam, after 311 ticks (0xda + 0x5d) | - | 0x10ce8: 0x16a94(1), then an endless loop until the hardware watchdog resets the CPU. The game is lost; credits (NVRAM) are kept | boot | boot | GI re-init on | observed (4.99 s) |

## Tilt and the other features
- **Ball save.** A tilt inside the ball-save window cancels the save. The drain is not re-served: tilt at 18.23 during
  the 5 s save, drain at 20.01, ball 2 at 21.93 (`observed`).
- **Multiball.** Tilting during Disc Multiball does not drain or stop the balls. The multiball ends normally when the
  balls drain (deff 52, leff 52, sound 0x02c). Leff 52 even takes GI ownership while tilted. The end of ball follows
  with no bonus (tilt 63.85, MB end 68.70, end of ball 69.83, ball 3 at 71.53; `observed`).
- **Modes.** Modes stop on event 0x1d as on any drain. Hooks on 0x65/0x66 run at the moment of the tilt. For example,
  SOS pays its queued skip bonuses on 0x66 (0x01026794; `code`, from sea_of_simulation.md).
- **Multi-player.** A tilt ends only the current player's ball. The next player is up with warnings reset
  (3p: P2 tilts at 34.97, P3 up at 38.67; `observed`).

## Emulator note
PinMAME does not emulate the SAM watchdog. After a slam the ROM spins in 0x10ce8 forever. `states_ref` calls
`PinmameReset()` when execution reaches 0x10ce8 (trace event `reset_request`, then `sim watchdog_reset`).

## Open
- **Slam veto.** Which hook on 0x55 can veto a slam (none seen) is not traced.
- **Warning carry-over.** Whether tilt warnings carry over a shoot-again ball is not traced. The code resets them at
  every ball start.
