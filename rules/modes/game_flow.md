# Game flow (base game) — Stern Tron Legacy LE 1.74

Audience: a developer rebuilding the game in MPF/Godot. Almost all of this lives in the Stern SAM OS
(addresses below 0x36000); the Tron game code hooks into it through OS events (`event_post(id)`).
Sources are function addresses in `tron/code/tron_game_decompiled_v2.c`. Emulator checks use
`traces/game_flow.jsonl` and `traces/game_flow_tilt.jsonl` (both made with the shared `tron_ref` and factory
settings; the tilt run uses `button tilt` for the plumb bob).

Naming warnings (the OS API list in `work/os_api.json` has three misleading names):
- `is_tilted()` 0x0000e4c4 / `tilt_set()` 0x0000e4dc do **not** mean tilt. They read/set the
  **valid-playfield flag** at RAM 0x372e8 (event 0x6a is "playfield became valid"). The tilt state is bit
  0x200 of the game state word 0x37274. [0x0000e4c4] [0x00010c70]
- `ball_save_time_update()` 0x00019d58 is the **ball-search timer reset** (called on every score). [0x00019d58]
- `start_button_lamp_update()` 0x0001a014 drives lamp 26 **SHOOT AGAIN** (byte 0x36f62 = 26), not the start button. [0x0001a014]

## 0. OS tick (measured)

- One `task_sleep(1)` unit = one scheduler pass, counted by the hardware tick counter RAM 0x37364.
- Measured in emulation (local runner, `TRACE_SLEEP_TASK=0x31`: 352 consecutive returns of the ball-save
  task's `task_sleep(6)` loop): every sleep(6) lasted exactly 6 counter ticks, mean **97.69 ms**
  (mode 97.5 ms, range 95.8-101.1 ms) → **16.28 ms per tick in game** (mode 16.25 ms).
  Over a whole 63 s game span the counter ran at 16.30 ms/tick; in attract mode (light CPU load) it ran at
  **16.00 ms/tick** (125-tick attract pages took 126 ticks = 2.016 s). Use **16.26 ms** (brief value) as the
  nominal tick; expect ±0.3 ms/tick drift in emulation. (verified in emulator: scratch run with a patched runner logging
  task 0x31 sleeps, not kept; cross-check in traces/game_flow.jsonl: valid → leff 14 stop = 5.141 s for 312-318 ticks ≈ 16.2-16.5 ms)
- The ROM treats **62 ticks (0x3e) as one second** everywhere (ball save, ball search, timers):
  62 × 16.26 ms = 1.008 s. [0x00019a20] [0x00019bf8]

## 1. Summary

1-4 players, 3 balls each (adj 31). Pressing START with credits starts a game; more players can be
added while player 1... is still on ball 1. Each ball: the ball is served to the shooter lane and
plunged by the player; the first 5 s of real play (after the playfield becomes "valid") are covered by
a ball saver plus a 3.5 s grace. When the last ball drains: all modes stop, the end-of-ball bonus is
counted (unless tilted), then either the same player shoots again (extra ball), the next player is up,
or the game ends with high-score entry, match and game-over music. A playfield-wide score multiplier
exists in the OS (RAM 0x38180) but Tron never sets it above 1.

## 2. Settings (operator adjustments)

ROM table 0x040de218 (index = adj number). [table 0x040de218]

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 31 | BALLS PER GAME | 3 | 1-10 | Balls per player (tournament can override) [0x000213bc] |
| 38 | BALL SAVE TIME | 5 | 0-16 | Seconds of ball save (×62 ticks); 0 = no ball save [0x00019ac4] |
| 32 | TILT WARNINGS | 2 | 0-3 | Number of DANGER warnings before tilt (0 = first bob tilts) [0x00024398] |
| 64 | COIN DOOR DISABLE TILT | 0 | 0-1 | 1 = tilt bob ignored while coin door open [0x00024344] |
| 26 | EXTRA BALL LIMIT | 5 | 0-10 | Max extra balls collected per player per game; above it the award becomes 3,000,000 points [0x0001a034] [0x0001a168] |
| 27 | EXTRA BALL PERCENTAGE | 25 | 1-50 | Target % of games with an extra ball; used to weight the Flynn's Arcade "light extra ball" award [0x0100e2e0] [0x010009a8] |
| 22 | SPECIAL LIMIT | 1 | 0-6 | Max specials per player per game; above it the award is 5,000,000 points [0x00023f74] [0x000240ac] |
| 23 | SPECIAL AWARD | 0 | 0-4 | 0 credit, 1 ticket, 2 nothing, 3 = 5,000,000 points, 4 extra ball [0x000240ac] |
| 11-21 | REPLAY TYPE / % / AWARD / LEVELS / AUTO START 20,000,000 / DYNAMIC START / LEVEL #1-#4 / BOOST | see table | | Replay levels per player [0x00022f18] [0x00022d2c] |
| 13 | REPLAY AWARD | 0 | 0-3 | 0 credit, 1 ticket, 3 extra ball [0x00022d2c] |
| 29 | MATCH AWARD | 0 | 0-2 | 0 credit (+knocker), 1 ticket, 2 nothing [0x0001b86c] |
| 30 | MATCH PERCENTAGE | 9 | 0-11 | 11 = match off [0x0001b660] |
| 36 | GAME RESTART | 1 | 0-1 | Holding START 1 s on ball 2+ restarts the game [0x00020d1c] |
| 39 | TIMED PLUNGER | 0 | 0-60 | >0: auto-launch a ball left in the shooter lane after N s [0x0001e614] |
| 40 | FLIPPER BALL LAUNCH | 0 | 0-4 | Flipper button launches the ball (OS) [line 48023 of the decompile] |
| 41 | COINDOOR BALL SAVER | 0 | 0-1 | Pauses ball serving while the coin door is open [0x0001ea28] |
| 42 / 46 | COMPETITION MODE / PLAYER COMPETITION | 0 / 1 | | Competition start (deff 39) [0x00019e98] [0x00019f20] |
| 43 | CONSOLATION BALL | 1 | 0-1 | not traced (open question) |
| 48-61 | ALLOW HIGH SCORES, GRAND CHAMPION 75,000,000, HIGH SCORE #1-#4 55/40/30/25 M, awards | | | High score table [0x0001ad4c] |
| 63 | LOST BALL RECOVERY | 1 | 0-1 | 5th failed ball search → "PINBALL MISSING", ball re-served [0x0001f79c] |

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| gf_state | 0x37274 (u16) | machine | 0x10 in attract | Game state bits: 0x01 bonus running, 0x02 (cleared at drain), 0x04 end-of-ball in progress, 0x08 game-over sequence, 0x10 no game / attract, 0x20 game starting, 0x80 match running, 0x100 (OS wait bit, service), 0x200 **tilted**. Observed: attract 16, play 0, bonus 5, tilt 512, match 152 [0x00020764] [0x0002444c] (verified in emulator: traces/game_flow.jsonl) |
| gf_num_players | 0x2110900 (u8) | game | 1 at game start | Players in game [0x000214a4] [0x00021304] |
| gf_cur_player | 0x3817c (u8) | game | 1 | Player up, 1-4 [0x00021360] |
| gf_ball | 0x3817d (u8) | game | 1 | Ball number (shared: advances after the last player's ball) [0x000214d0] |
| gf_scores | 0x21109e4 (u32[4]) | game | 0 at game start | Player scores [0x00023728] |
| gf_pf_mult | 0x38180 (u8) | per ball | 1 | Playfield multiplier applied by score_add (see §5.6) [0x0002373c] |
| gf_ball_scored | 0x38181 (u8) | per ball | 0 at serve | First score of the ball clears shoot-again flag 9, posts event 0x50 [0x0002340c] |
| gf_pf_valid | 0x372e8 (u8) + list 0x3c94c, count 3 at 0x372f0 | per ball | 0 at every serve | Valid playfield flag (§4.3) [0x0000e4b8] [0x00010c70] |
| gf_tilt_warnings | 0x3d4f8 (u8) | per ball | 0 at ball start | DANGER warnings given this ball [0x00024320] [0x00024398] |
| gf_ball_search_delay | 0x37420 (u32) | machine | reload = 10 s ×62 = 620 ticks (byte 0x39018=10); 15 s after a tilt | Countdown to the next ball search, reloaded by playfield switches and scores [0x00019c58] [0x00019d58] |
| gf_ball_search_count | 0x3741c (u16) | per ball | 0 | Consecutive ball searches [0x00019c58] |
| gf_eb_lit_player | 0x3d46c + p-1 (u8[4]) | per game | 0 at game start | Extra balls lit (OS count) for player p [0x0001a0c0] |
| gf_eb_lit_shared | 0x3d468 (u8) | per game | 0 | Extra balls lit for whoever is up [0x0001a0c0] |
| gf_eb_collected | 0x3d470 + p-1 (u8[4]) | per game | 0 | Extra balls collected (compared with adj 26) [0x0001a168] |
| gf_shoot_again_pending | 0x37430 (u8) | per game | 0 | Extra balls earned but not yet played [0x0001a168] [0x0001a27c] |
| gf_eb_scoop_lit | 0x2111894 + p-1 (u8[4]) | per player | 0 at player's first ball | Game-side "extra ball lit at the VUK scoop" count (lamp 37 EJECT: EXTRA BALL) [0x0102e8c0] [0x0102eaa4] |
| gf_special_lit | 0x3d4ef + p-1 / shared 0x3d4ec | per game | 0 | Specials lit [0x00024014] |
| gf_special_collected | 0x3d4f3 + p-1 | per game | 0 | Specials collected (vs adj 22) [0x000240ac] |
| gf_replay_levels | 0x2110984 + (p-1)*0x14 (u32[4]) / awarded flags 0x2110994+ | per game | at game start | Per-player replay thresholds [0x00022c08] [0x00022f18] |
| gf_flag_shoot_again | game flag 9 | per ball | set at next-up when EB pending, cleared by first score | Shoot-again ball in progress [0x000214d0] [0x0002340c] |

## 4. How it starts

### 4.1 Game start [0x00020d1c] [0x00020afc] [0x00020584]
1. START (sw16) in attract with a credit (or free play) and all balls home (else deff 11 "LOCATING
   PINBALLS"). Event 0x2c may veto. State |= 0x20, task id 0x29.
2. `0x00020584`: event 0x2f (veto); state = (state & 0x120) | 0x20; competition flag 0xf; kill tasks with
   flag 0x400; players = 1, player = 1, ball = 1; extra-ball counters and shoot-again cleared
   [0x00019fd4]; scores cleared [0x00023728]; replay levels reset [0x00022c08]; valid playfield cleared;
   event 0x2e (game start: Tron handlers 0x01003138, 0x0102f2a4 initialise all 4 players' data); then
   ball start (§4.2). Audit 0x11 (games started).
3. More players: START again while the current ball number is 1 and fewer than 4 players → player
   added (event 0x45/0x46), credit taken. On ball 2+ with adj 36 = 1, holding START for 62 ticks restarts
   the game. [0x00020d1c] [0x00021304]
4. Trace: game start at t = 9.90 s: deff 104 (Flynn's Arcade is lit, game feature), deff 19 score display,
   music call 0x01a, leff 14 (ball-save lamp effect) — all within 7 ms. (verified in emulator: traces/game_flow.jsonl)

### 4.2 Ball start [0x00020650]
In this order:
1. event 0x12 (veto); kill tasks with flag 0x80.
2. `first_ball_of_player` = (ball == 1 and not shoot-again flag 9).
3. ball-search counters reset [0x00019d24]; shoot-again lamp update; special lamps; valid-playfield reset
   [0x0000eb5c]; **playfield multiplier = 1, ball_scored = 0** [0x0002373c]; tilt warnings = 0 [0x00024320].
4. If `first_ball_of_player`: event 0x26 = **per-player game initialisation** (24 Tron handlers, e.g.
   item ladders reset 0x010160b8, scoop awards reset 0x0102e834, light cycle 0x010181b8, Quorra 0x0101cd78 ...).
5. event 0x11 = **per-ball initialisation** (Tron handlers: bonus reset 0x01000a84, 0x0100dd64, 0x010031ac);
   event 0x27.
6. Flippers/slings enabled [0x000041b4] (PinMAME solenoids 33-36 on in the trace).
7. If shoot-again flag 9: deff 26 "PLAYER n / SHOOT AGAIN" (player in arg +0x30), leff 16, speech 0x11b.
8. deff 19 (score display, background), music 0x01a (sample 0x45a).
9. Serve the ball: `serve(3)` [0x0001f258] → event 0x0f; **ball save armed** [0x00019ac4]; trough eject
   task; timed plunger task if adj 39 > 0.
- Serve types (arg of 0x0001f258): 3 = new ball (manual plunge, arms ball save), 1 = ball-save
  replacement (auto-launched, coil 2), 2 = outlane early save (auto-launched), 7 = re-serve after a drain
  with no valid playfield (manual plunge), 5 = lost-ball recovery. Auto-launch = type 1, 2 or 6.
  (verified in emulator: traces/game_flow.jsonl coil 2 after BALL SAVED)
- Reminder: ~1250 ticks (20.3 s) after a serve, if the ball still sits in the shooter lane, deff 40
  "PLAYER n" + speech 0x0f9 (task 0x43). [0x0100f1d0] (verified in emulator: a run without valid playfield, deff 40 at +20.3 s)

### 4.3 Valid playfield [0x0000e85c] [0x00010c70] [0x0000ee48]
The ball is "in play" (ball save starts counting, drains count) only after:
- one hit on a **force** switch: 11 VUK, 12 ZEN, 14 C(L)U, 24/29 outlanes, 25 (C)LU, 28 CL(U), 34 R. ramp exit,
  37 L. ramp exit, 39 R. inner loop, 43 left orbit, 46 right orbit (switch descriptor flag 0x2000 → event 0x6c); or
- hits on **3 different** "valid" switches: 7, 8, 13, 48 (ZUSE), 35 L. ramp entrance, 36 R. orbit spinner,
  38 R. ramp entrance, 41 disc opto, 44 left spinner, 49-51 Recognizer 3-bank (descriptor flag 0x1000 →
  event 0x6b), plus the pop bumpers 30-32 whose handlers post 0x6b themselves. Slingshots and the TRON
  targets do not count. [table 0x040f3574 word +0xc]
- When it becomes valid: event 0x6a. A drain **before** the playfield is valid is not a lost ball: the ball
  is re-served (type 7), same ball number, no bonus. (verified in emulator: run "a", sling hits only, drains re-served)

## 5. Behaviour while running

### 5.1 Ball save (adj 38) [0x00019ac4] [0x00019a20] [0x00019b34] [0x0001dd90]
- Armed at every **new-ball** serve (type 3) as task 0x31 with T = adj38 × 62 ticks (5 s → 310 ticks).
  Lamp effect leff 14 runs from the serve (it is the flashing SHOOT AGAIN / save effect).
- The countdown is **paused until the playfield is valid** (polled every 6 ticks). Then it counts in steps of
  6 ticks until ≤ 6 remain: effective 312 ticks plus up to 6 ticks of polling phase.
- At expiry: task renamed 0x32, leff 14 stopped, then a **grace of 218 ticks (0xda ≈ 3.54 s)** during
  which a drain is still saved, with no lamp effect.
- Measured: valid → leff 14 stop = 5.141 s (traces/game_flow.jsonl t 34.849 → 39.990); a drain 6.67 s after
  valid (1.5 s into the grace) was saved. Total protection ≈ 5.1 s + 3.54 s ≈ 8.6-8.7 s after the
  playfield became valid. (verified in emulator: traces/game_flow.jsonl)
- When the last ball drains while task 0x31/0x32 runs and the playfield is valid: ball-save tasks killed,
  deff 20 "BALL SAVED / KEEP SHOOTING", leff 15, audit 0x2b TOTAL BALLS SAVED, ball re-served with
  **auto-launch** (type 1). The replacement ball has **no ball save of its own** (only type 3 arms it):
  a second drain ends the ball. (verified in emulator: traces/game_flow.jsonl t 15.96 save, t 22.73 drain → bonus)
- Outlanes (sw24/sw29) call 0x00019b34(1/2): starts a 625-tick drain-side timer (task 0x37/0x38, for the
  LEFT/RIGHT DRAINS audits) and, if ball save is running, serves the replacement immediately (type 2)
  with deff 20 — before the ball reaches the trough. (inferred from code, not traced)
- Multiball start kills the single-ball save (0x00019bdc); multiballs use their own save
  (`multiball_start(balls, …, save_ticks, grace_ticks)`). [0x0001ed7c]
- Tilt: no save (needs valid playfield and no tilt). [0x0001dd90]

### 5.2 Ball search [0x00019c58] [0x0001f79c] [0x0001f634]
- Each tick while a game runs, the playfield is valid, no end-of-ball/start task runs and no search runs:
  decrement 0x37420; at 0: count+1, start a search (task 0x2b: audit 0x25 BALL SEARCH STARTED, pulse the
  playfield coils/eject devices, events 0xd/0xc/0xe), reload 620 ticks (10 s).
- Reloaded by every valid-playfield switch (event 0x6b handler) and every score_add.
- After a tilt the reload is 15 s. With adj 63 = 1 the **5th** consecutive search declares a lost ball:
  deff 13 "PINBALL MISSING / PLEASE WAIT", a ball is re-served from the trough.
- Measured: first search 10.09 s after the last switch (traces/game_flow.jsonl t 86.61 → 96.71, audit 37).
  (verified in emulator: traces/game_flow.jsonl)

### 5.3 Tilt (adj 32) [0x00024564] [0x00024398] [0x0002444c] [task_2e 0x00024520]
| Trigger | Condition | Effect | Display | Sound | Lamp |
|---|---|---|---|---|---|
| Tilt pendulum closes | not tilted, coin-door rule (adj 64), not within 62 ticks of the previous accepted bob hit | warnings < adj32: warnings+1 | deff 23 "DANGER" | 0x016 (sample 0x0ae), then a speech 0x03d about 0.5 s later (game hook) | leff 11 |
| same | warnings ≥ adj32 | **TILT**: event 0x66, state \|= 0x200, audit 0x2a TILTS, flippers and slings off, kill tasks with flag 0x1000 (running modes), sounds stopped, event 0x65 (Tron handlers 0x01010b6c, 0x010067a4, 0x0100a1d0, 0x01031654), ball-search delay 15 s, event 0x67 | deff 21 "TILT" (background) | 0x017 (sample 0x0b0), speech 0x03e ~1 s later | leff 9 |
| Pendulum held closed | — | warning every 62 ticks, after 2 warnings tilt, and the switch is flagged bad | | | |
| Slam tilt (dedicated switch D-18) | — | state \|= 0x200, flippers off, kill tasks, deff 24 "SLAM TILT", leff 12, sound 0x018; after 218+93 ticks (≈5 s) the machine **resets** (game lost) [0x00023e40] [task_39 0x00023e18] | | | |
- While tilted: score_add does nothing (state & 0x210), no ball save, no bonus. The ball(s) drain; the
  end-of-ball runs without bonus; the tilt bit and warnings are cleared for the next ball. [0x00020764]
- Verified: factory adj 32 = 2: bob 1 (t 14.44) → deff 23 + leff 11 + snd 0x016, warnings=1; bob 2 (t 16.12) → same,
  warnings=2; bob 3 (t 17.80) → deff 21 + leff 9 + snd 0x017, state 512, speech 0x03e at t 18.83; drain (t 21.09) →
  no deff 25, no bonus, ball 2 starts 0.53 s later with state 0 and warnings 0. (verified in emulator: traces/game_flow_tilt.jsonl)

### 5.4 Extra ball [0x0001a0c0] [0x0001a1fc] [0x0001a168] [0x000214d0] [0x01012190] [0x01012228]
- **Lighting** (game side): `award_scoop(1, …)` 0x0102e8c0 adds 1 to gf_eb_scoop_lit (lamp 37 EJECT:
  EXTRA BALL) and calls 0x01012190 → OS lit count +1 for the current player, deff 132 "EXTRA BALL / IS LIT"
  (leff 152, sounds 0x116 then speech 0x117), speech 0x118 later if still uncollected. Sources found:
  End of Line multiball (adj 85 END OF LINE EXTRA BALL: lit when that EOL count is reached, once per game,
  flag 0x28) [0x01004238]; Flynn's Arcade award "LIGHT EXTRA BALL" [0x0100e344] (weighted by adj 27
  [0x0100e2e0]); a two-part qualifier at 0x2111670 (bits 1+2) [0x01012030]; light cycle targets
  [0x010186bc]; 0x0102db1c (video-mode award 1). These belong to the other feature specs.
- **Collecting**: shooting the VUK scoop (sw11) while gf_eb_scoop_lit > 0 → 0x01012228 → OS: lit −1,
  then if collected < adj 26 (5) and not in tournament: collected +1, shoot_again_pending +1, audit 9
  TOTAL EXTRA BALLS, SHOOT AGAIN lamp 26 solid; deff 133 "EXTRA / BALL" (leff 153, sfx 0x119, speech 0x11a).
  Over the limit: score 3,000,000 (RAM 0x36f6c) instead, deff 133 shows the value.
  (verified in emulator: traces/game_flow.jsonl t 47.07: audit 9, eb_lit 1→0, collected 0→1, shoot_again 0→1, deff 133)
- **Playing it**: at end of ball (after bonus) if shoot_again_pending > 0 → −1, set game flag 9; the
  **same player** plays again with the **same ball number** (no player-first-ball init). Ball start shows
  deff 26 "PLAYER n / SHOOT AGAIN" + leff 16 + speech 0x11b; SHOOT AGAIN lamp flashes until the first
  score (score_add clears flag 9). Ball save is armed again (new-ball serve).
  (verified in emulator: traces/game_flow.jsonl t 68.60 deff 26, ball_num stays 2)
- Replay award "extra ball" (adj 13 = 3) and special award 4 use the same 0x0001a168 path.

### 5.5 Special, replay, match, high score, grand champion
- **Special** [0x00024014] [0x00024218] [0x000240ac] [0x01016e58]: lit by the Flynn's Arcade award "LIGHT
  SPECIAL" (0x0100e3b8; deff 81 "SPECIAL IS LIT"); collected at an **outlane** (sw24/sw29 handler) whose
  lamp is lit: deff 82 "SPECIAL", leff 90, sfx 0x09e, +100,000 points (×pf mult), then the special award
  per adj 23; over adj 22 limit → 5,000,000 points (RAM 0x36f70). Audit 0x0e.
- **Replay** [0x00022f18] [0x00022d2c]: checked on every score_add against the player's replay levels
  (factory: auto replay, first level 20,000,000). Award per adj 13; task 0x33 shows deff 28 "REPLAY",
  leff 17, knocker sound 0x019. The end of ball waits for tasks 0x33-0x34 to finish before the next ball.
  (verified in emulator: traces/bonus_skip.jsonl t 28.49-28.51, bonus took the score to 32,543,090 → snd 0x019 + deff 28 right after the bonus)
- **Match** [0x0001b660] [0x0001b86c]: at game end, random tens 00-90 vs each score mod 100; if the real
  match rate ≥ adj 30 % the number is forced to a non-matching value. deff 38 "MATCH" (music 0x01c,
  sfx 0x041/0x03f/0x040/0x042/0x043, speech 0x045). Award per adj 29. (verified in emulator: traces/game_flow.jsonl t 122.26)
- **High scores / Grand Champion** [0x0001ad4c] [0x0001abfc]: at game end, before match: scores beating
  GRAND CHAMPION (75 M) or HIGH SCORE #1-#4 (55/40/30/25 M) → deff 33 "PLAYER n", deff 31 initials entry,
  deff 32 value; awards adj 55-59 (credits). No effect on play. (not traced: needs ≥ 25 M)

### 5.6 Playfield multiplier RAM 0x38180 [0x0002340c] [0x0002373c] [0x000235fc]
- `score_add(points)` adds `points × byte[0x38180]` (event 0x4c may change the value; event 0x4d after).
- Written only by the OS: **= 1 at every ball start** (0x0002373c) and **= 1 just before the bonus**
  (0x000235fc(1) in end-of-ball). The setter 0x000235fc accepts 1-5 but has no other caller, and no Tron
  game code writes 0x38180 (all ~25 inlined score_add copies only read it).
- So in Tron 1.74 the playfield multiplier is **always 1**. Tron's "double scoring" doubles values in game
  code instead. Every score_add in all traces shows `multiplier: 1`. (verified in emulator: all traces)
- The bonus is added with the same multiplier (1) through 0x00023428.

## 6. How it ends

### 6.1 End of ball [0x0001dd90] [0x00020764]
Triggered when the trough holds all balls not in play and the last ball was not saved. Order:
1. event 0x1e (veto); state |= 0x04; task id 0x2a.
2. event 0x1d = **stop everything running**: Tron handlers end End-of-Line MB (flag 0x27), Disc MB (0x24),
   Light Cycle MB (0x2b), Quorra MB (0x29), Portal MB (0x37), CLU hurry-up (0x01001c88), GEM (0x01013970),
   Sea of Simulation (0x01026784), Zuse (0x01031664), mode objects (0x0100a244).
3. Coils off/flippers and slings off [0x000041a0]; ball-search delay reset; audit 8 TOTAL BALLS PLAYED,
   LEFT/RIGHT DRAINS audit if an outlane timer runs.
4. Wait up to 169 ticks (byte 0x3901c) while tasks with flag 0x2000 run — this is where mode "TOTAL"
   displays finish (e.g. GEM total deff 79 delayed the bonus by 2.4 s in traces/bonus.jsonl).
5. Kill tasks with flag 0x100; **playfield multiplier = 1**.
6. If not tilted: event 0x14 (veto) → state |= 0x01 → **bonus deff 25** (see bonus.md; holding both flipper buttons skips to the total, verified in traces/bonus_skip.jsonl); wait for it; then
   event 0x16 gathers the bonus value and adds it to the player's score [0x00023428]; event 0x15.
7. Clear bonus bit; wait for replay/award tasks 0x33-0x34; wait for an OS timer; clear tilt (0x200) and 0x02.
8. event 0x1f; clear 0x04.
9. **Next up** [0x000214d0]: event 0x47; if shoot_again_pending → same player, flag 9; else next player;
   after the last player ball+1; if ball > balls per game → **game over** (§6.2), else ball start (§4.2).
- Measured: drain → audit 8/deff 25 = 0.535 s (trough settle), 1-line bonus lasts 1.59 s, ball start
  right after the bonus score. (verified in emulator: traces/game_flow.jsonl t 22.73 → 23.26 → 24.85)

What resets when (summary):
| Scope | What | Where |
|---|---|---|
| per ball (event 0x11 / ball start) | bonus X → 1 (unless flag 0x2d), bonus base → 50,000, pf mult 1, tilt warnings, valid playfield, ball search, ball save | 0x01000a84, 0x00020650 |
| ball end (event 0x1d) | all multiballs, hurry-ups and timed modes stop | handlers above |
| per player (event 0x26, player's first ball) | item ladders, scoop awards, feature progress (24 handlers) | 0x00020650 |
| per game | scores, EB/special counters, replay levels | 0x00020584 |
| kept per player all game | item ladder levels, Sea of Simulation/Portal counts, everything in NVRAM arrays [p-1] | (verified in emulator: traces/bonus.jsonl, ball 2 bonus) |

### 6.2 Game over [0x00020a64]
event 0x2a; state |= 0x18; kill tasks flag 0x200; game-time audit (0x2e..), score-range audit (0x13..);
replay statistics / dynamic replay update [0x000231a4]; score audits [0x00023774]; tournament results
(deffs 34-37) [0x0002511c]; **high score entry** [0x0001ad4c]; **match** deff 38 [0x0001b660]; event 0x2b →
Tron task 0x45: game-over music 0x01d with leff 133 (all lamps + flashers) for 625 ticks, speech 0x01e
every 4-6 games [0x0100f29c]; attract (deff 1, leff 1) [0x000015d4].
Measured: last bonus end → match deff 38 at once → attract deff 1 7.84 s later, music 0x01d.
(verified in emulator: traces/game_flow.jsonl t 122.26 → 130.10)

## 7. Media

| When | Display effect | Sound calls | Lamp effect | Tube show |
|---|---|---|---|---|
| Ball start | deff 19 score display (background, "BALL %d / score") | 0x01a music (0x45a) | leff 14 (ball-save, until timer end) | — |
| Shoot again ball | deff 26 "PLAYER %d / SHOOT AGAIN" | 0x11b speech (0x184) | leff 16 | — |
| Ball saved | deff 20 "BALL SAVED / KEEP SHOOTING" (prio 223) | — | leff 15 | — |
| Ball in shooter 20 s | deff 40 "PLAYER %d" | 0x0f9 speech | — | — |
| Tilt warning | deff 23 "DANGER" (deff 22 is an empty stub) | 0x016, later 0x03d | leff 11 | — |
| Tilt | deff 21 "TILT" | 0x017, later 0x03e | leff 9 | — |
| Slam tilt | deff 24 "SLAM TILT" | 0x018 | leff 12 | — |
| EB lit / collected | deff 132 / deff 133 | 0x116+0x117 / 0x119+0x11a | leff 152 / 153 | — |
| Special lit / collected | deff 81 / deff 82 | — / 0x09e | — / leff 90 | — |
| Replay | deff 28 "REPLAY" | 0x019 knocker | leff 17 | — |
| Pinball missing / locating | deff 13 / deff 11 | | | |
| Match | deff 38 | 0x01c, 0x041, 0x03f, 0x040, 0x042, 0x043, 0x045 | | |
| Game over | (attract pages, see attract_and_service.md) | 0x01d music, 0x01e speech | leff 133 | |
Bonus media: see bonus.md. Asset names in mpf_package: deff 22 is wrongly described there (W6).

## 8. Lamps
- 26 SHOOT AGAIN: flashing while shoot-again flag 9 (until first score), solid while an extra ball is
  pending, off otherwise. [0x0001a014]
- 65 START BUTTON: flashing in attract with credits; 66 TOURNAMENT START BUTTON similar. [0x00020448]
- 37 EJECT: EXTRA BALL: lit while gf_eb_scoop_lit > 0 (game lamp rule, inferred).
- Outlane lamps (32 RIGHT OUTLANE, left outlane lamp) show special lit [0x00024298] (inferred).

## 9. Interactions
- Every feature's per-ball reset hangs on event 0x11, per-player on 0x26, game on 0x2e, ball-end stop on 0x1d.
- Multiball: the end of ball runs only when all balls are drained; multiball start kills the single-ball
  save. Tilt during multiball: all balls must drain; no saves.
- score_add is ignored while tilted or out of game (state & 0x210).
- Extra ball, special and replay awards share 0x0001a168 (EB limit adj 26).

## 10. Reference scenario
`traces/game_flow.txt` (shared tron_ref) → `traces/game_flow.jsonl`; watch list = the gf_* addresses above.
Key events:
- t 15.96 deff 20, leff 15, audit 43 (save 2.2 s after valid); coil 2 auto-launch.
- t 22.73 drain of the replacement → t 23.26 audit 8 + deff 25 → t 24.85 score +100,000, ball 2.
- t 34.85 valid → t 39.99 leff 14 stop (5.14 s) → t 41.51 drain in grace → t 42.05 deff 20.
- t 47.07 extra ball collected (audit 9, deff 133); t 66.48 drain → bonus → t 68.60 deff 26, same ball 2.
- t 96.71 ball search (audit 37) 10.1 s after the last switch.
- t 122.26 match deff 38 after the last bonus; t 130.10 attract deff 1, music 0x01d.
`traces/game_flow_tilt.txt` (shared tron_ref, `button tilt`) → t 14.44/16.12 DANGER ×2, t 17.80 TILT,
t 21.09 drain → t 21.62 ball 2 with no bonus and warnings 0; t 34.39 drain 3.2 s after valid → t 34.92 deff 20 BALL SAVED.

## 11. Open questions
- Events 10/11 can extend the ball-save pause (no Tron handler registered; OS only).
- Adj 43 CONSOLATION BALL and adj 40 FLIPPER BALL LAUNCH were not traced.
- Game flag 0x2d ("hold bonus X") is tested at ball start but no setter was found in 1.74.
- Tick length differs between attract (16.00 ms) and play (16.25-16.30 ms) in emulation; real hardware not measured.
- The outlane early ball save (serve type 2) was read from code, not traced.
