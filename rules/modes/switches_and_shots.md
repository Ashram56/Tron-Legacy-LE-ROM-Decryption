# Switches and shots (the layer every mode hangs off)

Stern Tron Legacy LE 1.74. Ticks: 1 tick = 16.26 ms. Trace references: `traces/switches_and_shots.jsonl`
(base scores), `traces/skill_shots.jsonl` (disc guard, spinner queue, pop bumper level),
`traces/combos.jsonl` (orbit pass-through). Every handler named below is in
`tron/code/tron_game_decompiled_v2.c`. Call orders were checked against the ARM disassembly,
because the decompile inlines tail calls and shows wrong constants in places.

## 1. Summary

Each playfield switch has one handler in the switch table (0x040f3574, 32 bytes per switch, word 0 =
handler). A handler does three things, in a fixed order:
1. It applies its own repeat guard (a short timer task).
2. It calls every feature hook that cares about the switch: disc multiball, portal, CLU, light cycle,
   combos, Find Flynn, Zuse, End of Line and so on.
3. It adds a small fixed **base score** through `FUN_0102a188(points)`. That function scores nothing
   while tilted and otherwise calls `score_add(points)`, which applies the playfield multiplier.

The eight **shots** are numbered 0-7: left orbit, left ramp, left inner loop, right inner loop,
right ramp, right orbit, recognizer, disc. The disc multiball, portal multiball, combo and Find Flynn
hooks all use these index numbers. Other hooks use a bit mask instead (section 5.3).

## 2. Settings (operator adjustments)

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 65 | POP BUMPER DIFFICULTY | 1 | 0-2 | Hits per pop-bumper level = min((adj65 + levels done this game) x 5 + 20, 50) [0x0101c244] (verified in emulator: 25 then 30, traces/skill_shots.jsonl) |
| 78 | DISABLE ORBIT UP-POST | 0 | 0-1 | Passed to the orbit up-post object 0x3b4e8 when it is built [0x00000b04 / 0x01009e94] (inferred: 1 = post never rises) |
| 79 | DISABLE PLUNGE POST | 0 | 0-1 | 0: the orbit post rises when a plunged ball leaves the shooter lane. 1: no post on plunge, and the right-ramp skill shot starts at every serve (see skill_shots.md) [0x0102a31c, 0x01029148] |
| 82 | INSULT LEVEL | 1 | 0-2 | 0 turns off the left-outlane insult speech [0x010127c0] |
| 72/73/74 | TRON "SPINNERS"/"BUMPERS"/"DOUBLE SCORING" TIMER | 30 | 20-40 | Lengths of tasks 200 / 199 / 0xc6. While task 200 runs, spinner values x3. While task 199 runs, pop values x3. Their logic belongs to the TRON-targets worker [0x0100c558, 0x0100d3a0, 0x0100d3e4] |

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| playfield_multiplier | 0x38180 (byte) | per ball | OS | Multiplier applied by score_add to every base score |
| game_state_bits | 0x37274 (u16) | game | OS | Bit 0x10 = tilted (FUN_0102a188 scores nothing). Bits 0x312/0x311/0x211 = not in normal play; many hooks test these |
| sw_lorbit_repeat | task 0x67 | 125 ticks (2.03 s) | started by a counted sw43 | A second sw43 inside the window is not a shot |
| sw_rorbit_after_lorbit | task 0x68 | 187 ticks (3.04 s) | started by a counted sw43 and by every plunge | The next sw46 is the far end of the same orbit and is not counted |
| sw_rorbit_repeat | task 0x69 | 125 ticks | started by a counted sw46 | Repeat guard for sw46 |
| sw_lorbit_after_rorbit | task 0x66 | 187 ticks | started by a counted sw46, and by a plunge when the post stayed down | The next sw43 is not counted |
| sw_disc_repeat | task 0x3f | 125 ticks | started by a counted sw41 | A second disc hit inside the window gets sound 0x54 only, and the window is cancelled |
| sw_shooter_settle | task 0x3d | 6 ticks (98 ms) | sw23 closes | The ball must sit 6 ticks in the shooter lane before its exit counts as a plunge |
| sw_shooter_exit | task 0x3e | 125 ticks | sw23 opens | No reader found in game code |
| sw_3bank_guard | task 0x7b | 10 ticks (163 ms), restarted by every hit | any of sw49-51 | Hits during the window are ignored (one hit per bank volley) |
| lspin_session | task 0x64 | ends after 62 idle ticks (1.01 s) | first sw44 spin | While it runs, spins are only queued: no left-inner-loop shot |
| lspin_pending | 0x3b70c (byte) | session | 0 at session start | Spins waiting to be scored (task 0x64 scores one per tick) |
| lspin_last / lspin_total | 0x3b710 / 0x3b714 | session | 0 at session start | Last spin value / sum of this session (read by deff 41) |
| rspin_session | task 0x65 | ends after 93 idle ticks (1.51 s) | first sw36 spin | Same for the right orbit spinner |
| rspin_pending / rspin_last / rspin_total | 0x3b718 / 0x3b71c / 0x3b720 | session | 0 | Same as the left side |
| lspin_value | 0x2111820 + 4(p-1) | per player | 10,000 at each ball start unless game flag 0x10 is set (then the flag is cleared) [0x010299bc] | Points per left spin. A +2,500 step (cap 100,000) exists at 0x01029a5c but has no caller in 1.74 |
| rspin_value | 0x2111830 + 4(p-1) | per player | the same, with flag 0x11 | Points per right-orbit spin. Step function 0x01029dd8 has no caller |
| pop_hits_left | 0x211179b + p | per player | FUN_0101c244() at the player's first ball (event 0x26) and after each level | Hits left until the pop level completes |
| pop_levels_done | 0x21117a3 + p | per game | 0 at the player's first ball | Difficulty level (feeds the hits formula) |
| pop_value_level | 0x21117a7 + p | per ball | 0 at each ball start unless game flag 0x19 is set [0x0101c30c] | Value level: pop value 10,000 + 2,500 x level |
| pop_level_counter | 0x211179f + p | per game | 0 | Cleared at the player's first ball (no other use seen) |
| bumper_busy | task 0x40, 0x36fd8 | 156 ticks (2.54 s) after the latest valid pop hit | FUN_0100f75c(0x9c) | "Ball in the bumpers" window, read by FUN_0100ff64 (inferred: defers other effects) |
| big_bumps_count / total | 0x3b2ec / 0x3b2f0 | while Big Bumps runs | 0 at the player's first ball | Big Bumps (task 0xcb): +25,000 per pop hit; shown by deff 135 |
| orbit_post_state | 0x3b4f0 | live | 0 | 1 = orbit up-post raised (coil 7). It rises on plunge and drops by itself about 2.04 s later (verified in emulator: traces/switches_and_shots.jsonl, t = 11.55 to 13.59 s) |
| playfield_valid | object 0x372e8 (done byte) | per ball | reset at ball start [0x0000eb5c] | Becomes 1 after 3 different "counting" switches (descriptor flag 0x1000, pops, slings, TRON) or after any "instant" switch (flag 0x2000). os_api calls the reader `is_tilted`; that name is wrong for this use |
| zen_count | 0x21118bc + 2(p-1) (u16) | per player | | ZEN rollover awards |

## 4. How a switch reaches its handler (OS layer, descriptor table 0x040f3574)

Descriptor layout (32 bytes): +0 handler. +4 argument passed to the handler task at +0x34 (the
insert lamp for most playfield switches, e.g. sw24 -> lamp 8 LEFT OUTLANE). +8 name. +0xc handler
task flags. +0xe event flags. +0x14 handler task id. +0x1a switch number. +0x1b / +0x1c debounce
counts [table 0x040f3574, dispatcher 0x0000e85c].
- Event flags +0xe:
  - 0x0400: the handler runs when the switch closes.
  - 0x0800: it also runs on open. Both bits are set in 0x0fff (TRON targets, trough, shooter lane)
    and 0x2fff (VUK), so those handlers run on both edges (verified: two handler tasks per TRON hit).
  - **0x1000**: the dispatcher posts event 0x6b with the switch number. This is a "counting"
    switch: it advances the 3-switch timeout of the playfield-valid object and of each skill shot.
  - **0x2000**: the dispatcher posts event 0x6c. This is an "instant" switch: it validates the
    playfield and ends the skill shots at once, except on that skill shot's own excluded switches.
  - Pop bumpers, slingshots and TRON targets post 0x6b themselves from their handlers.
- The handler runs only when the game-state word 0x37274 is 0, or shares a bit with the low 12 bits of
  +0xe. Playfield switches (0x0400/0x1400/0x2400) therefore do nothing while tilted or out of normal
  play [0x0000ea18].
- Debounce counts: +0x1b = scans needed to accept a close, +0x1c = scans needed to accept an open
  (inferred from 0x0000e85c; the scan period was not measured).
- The handler runs as a task about one tick after the switch closes (measured 16 ms).

## 5. Behaviour: one row per switch

Base = points added at the end of the handler through FUN_0102a188 (x playfield multiplier,
nothing while tilted). "z4, eol" means `zuse_target_hit(4)` (Zuse fast-scoring per-switch hook) and then
`eol_shot_score()`. eol_shot_score adds the End of Line per-switch value 0x3ae00 (10,000 rising to a
50,000 cap) while game flag 0x27 or tasks 0xb0-0xb1 run [0x01005074].

| Sw | Name | Event flag / debounce (close/open) | Guard | Ordered hook calls (handler address) | Base | Sound / lamp effect | Verified |
|---|---|---|---|---|---|---|---|
| 1-4 | (T)RON, T(R)ON, TR(O)N, TRO(N) | 0x0fff (both edges, no event) / 2/4 | Target object 0x3b744 (FUN_0100b4b8) accepts a hit only when that target's slot in 0x3b764 is 1; it then clears the slot | FUN_0100b050: only if (0x37274 & 0x312) == 0: post 0x6b(sw), z4, eol, simulation_shot(2/3/4/5), FUN_0102c588(bit 1/2/4/8, letter 4/3/2/1) = TRON letter hook (10,000 + deff 107 + lamp effect 38 + sound 0x4c in normal play), rules refresh | 30 | (from the TRON hook) | sw1: 10,000 + 30 |
| 7, 8, 48, 13 | (Z)USE, Z(U)SE, ZU(S)E, ZUS(E) | 0x1400 / 1/5 | none | zuse_target_hit(0/1/2/3), eol, simulation_shot(9/10/11/12), FUN_01033790(0..3, lamp) = Zuse hook: 5,000 + lamp effect 119 + sound 0xa4 when Zuse is not qualifiable, otherwise Zuse logic (other worker) [0x0102b08c...] | 1,130 | (Zuse hook) | sw7: 75,000 + 1,130 |
| 11 | VIDEO GAME EJECT (VUK, Flynn's Arcade) | 0x2fff (instant) / 1/5 | ball device | The handler feeds the VUK ball device (generic handler 0x0001d994). When the ball has settled (about 0.76 s later in the emulator), device event 2 -> **on_vuk** [0x0102eddc]: audit 0x66, FUN_01029068 (VUK skill shot), simulation_shot(0), on_clu_hurryup_awards(0x100), FUN_010039e0 (End of Line combo jackpot), then the Quorra/arcade/portal/light-cycle/disc VUK hooks, FUN_01004ddc, z4, eol | 350 | | 350 |
| 12 | ZEN ROLLOVER | 0x2400 instant / 1/3 | none | FUN_01028b74 (starts the left-ramp skill shot if game flag 0x1e is set), z4, eol, on_find_flynn_started, FUN_0103129c (outside multiball: zen_count+1, **+42,000**, deff 100 ZEN + task 0xcc unless FUN_01031208, sound 0xe5) | 1,090 | 0xe5; deff 100 starts lamp effect 117 | 42,000 + 1,090 |
| 14, 25, 28 | C(L)U, (C)LU, CL(U) | 0x2400 instant / 1/3 | none | z4, eol, simulation_shot(7/6/8), FUN_01016b0c(1/0/2) = CLU letter hook: a new letter scores 10,000 + lamp effect 86 + its sound, a lit one 1,000 + lamp effect 87 (CLU worker) | 1,090 | (CLU hook) | sw25: 10,000 + 1,090 |
| 23 | SHOOTER LANE | 0x0fff (both edges) / 2/5 | task 0x3d | Close: restart 0x3d (6 ticks). Open (ball leaves): restart 0x3e (125); if flipper-button bit 0 is held (FUN_00007304 & 1) -> FUN_01028d60 (right-ramp skill shot, skill_shots.md). Then, if 0x3d has expired and the state is clean: sound 0xea, task 0x68 (187); if adj 79 = 0, task 0x3c is not running and the right-ramp skill shot is not running -> raise the orbit post (FUN_0100a614(0x3b4e8)); if the post is still down -> task 0x66 (187). Finally the generic ball-device handler [0x0102a31c] | 0 | 0xea | plunge: 0xea, task 0x68, post up, coil 7 on |
| 24 | LEFT OUTLANE | 0x2400 instant / 1/3 | none | FUN_00019b1c / FUN_0001e454 / FUN_00019b34(1) (outlane ball save: restarts task 0x37 for 625 ticks; deff 20 "ball saved" + audit 0x2b when a save is running). With no save, the playfield valid and exactly 1 ball in play: FUN_010127c0 (insult speech 0x129, adj 82 > 0, random, 37,500-tick cooldown timer 9). Then FUN_01016e58(lamp 8, insult_played): if lamp 8 LEFT OUTLANE is lit and FUN_00024218 allows it -> **special**: deff 82, lamp effect 90, sound 0x9e (unless insult), +100,000, lamp off. Otherwise sound 0xa2 (unless insult). Then z4, eol | 100,000 | 0xa2 | 100,000 + 0xa2 |
| 29 | RIGHT OUTLANE | as sw24 | none | Same as sw24 with FUN_00019b34(2) and lamp 32 RIGHT OUTLANE. The insult result is computed but never passed on (r1 = 0), so the right outlane never plays the insult and always plays 0xa2 when not lit. A ROM quirk [0x0102adbc] | 100,000 | 0xa2 | |
| 26, 27 | LEFT / RIGHT SLINGSHOT | 0x0400 (self-posts 0x6b) / 1/4 | OS sling object (FUN_00003e30(1/2)) must report a real fire, otherwise nothing happens | post 0x6b(sw), z4, eol, FUN_01017128 (lamp rotation of lamp 8 through list 0x040e39b4, i.e. lane-change style; stops lamp effects 89/90), sound 0xe8 (left) / 0xe9 (right) | 440 | 0xe8 / 0xe9 | 440 each |
| 30, 31, 32 | LEFT / RIGHT / BOTTOM BUMPER | 0x0400 (self-posts 0x6b) / 1/2 | OS jet object FUN_00003938(1/2/3) must report a real fire | FUN_0100f75c(0x9c) (bumper_busy, task 0x40), post 0x6b(sw), z4, eol, **FUN_0101c3a4(sw)** = pop bumper value (section 5.2) | 170 | sound 0x50 (0x51 at x3), lamp effect 41 / 42 | 10,000 + 170 |
| 34 | R. RAMP EXIT | 0x2400 instant / 1/9 | none | **on_right_ramp** [0x0102aa50] (section 6, shot 4) | 1,170 | 0xeb | 1,170 |
| 35 | L. RAMP ENTRANCE | 0x1400 / 1/9 | none | sound 0xeb, z4, eol. No shot hooks | 560 | 0xeb | 560 |
| 36 | RIGHT ORBIT SPINNER | 0x1400 / 1/1 | rspin_session | FUN_01029f20 (spin, section 5.1), z4, eol, FUN_01013eac (GEM hurry-up spin hook: while tasks 0xc2/0xc3 run, restart 0xc2 and raise 0x3b12c to at least 5, +1 per spin, max 40) | 90 per spin | 0xee per scored spin | 10,000 + 90 |
| 37 | L. RAMP EXIT | 0x2400 instant / 1/9 | none | **on_left_ramp** [0x0102a940] (shot 1) | 1,170 | 0xeb | 1,170 |
| 38 | R. RAMP ENTRANCE | 0x1400 / 1/9 | none | sound 0xeb, z4, eol | 560 | 0xeb | 560 |
| 39 | RIGHT INNER LOOP | 0x2400 instant / 1/3 | none | shot 3 hooks (section 6) | 1,190 | none of its own | 250,000 (GEM qualify) + 1,190 |
| 41 | DISC OPTO (normally closed) | 0x1400 / 1/1 | task 0x3f (125 ticks) | If 0x3f is running: kill 0x3f, play sound 0x54, **no score, no hooks**. Otherwise: restart 0x3f, portal_mb_shot(6), simulation_shot(1), on_disc_m_b_blue_disc_shots(7), FUN_0100781c (disc MB restart autofire, adj 71), z4, eol, FUN_01004e94(2) (End of Line disc jackpot), FUN_01020da8(2,0) (disc battle / disc MB start), lamp effect 75 (disc flashers coils 26/27 alternate, 8 x 4 ticks), sound 0x52 chained with 0x53 [0x0102ab6c] | 2,310 | 0x52 + 0x53; 0x54 on a re-hit | hit, re-hit 0.67 s later (0x54 only), third hit scores again |
| 43 | LEFT ORBIT | 0x2400 instant / 1/3 | tasks 0x67, 0x66 | If 0x67 is running: kill 0x67, base only. Else if 0x66 is running (right orbit made, ball exiting here): kill 0x66 and 0x69, base only. Otherwise: audit 0x60, **FUN_0102a728** shot 0 hooks, restart 0x67 (125) and 0x68 (187), sound 0xed [0x0102a808] | 1,220 (always, guards included) | 0xed | pass-through scored 1,220 with no audit |
| 44 | LEFT SPINNER | 0x1400 / 1/1 | lspin_session | **on_l_inner_loop** (spin; the first spin is shot 2, section 5.1), z4, eol, FUN_01013eac | 90 per spin | 0xec per scored spin | 3 spins: 3 x (10,000 + 90), LIL hooks once |
| 46 | RIGHT ORBIT | 0x2400 instant / 1/3 | tasks 0x69, 0x68 | Mirror of sw43: 0x69 running -> kill it; else 0x68 running -> kill 0x68 and 0x67; else audit 0x61, **FUN_0102a794** shot 5 hooks, restart 0x69 (125) and 0x66 (187), sound 0xef [0x0102a8a4] | 1,220 | 0xef | 1,220 |
| 49, 50, 51 | RECOGNIZ. 3-BANK L / C / R | 0x1400 / 1/5 | task 0x7b (10 ticks, restarted by every hit, accepted or not) | If 0x7b is not running: on_quorra_m_b_super_jackpots(0x10), on_disc_m_b_blue_disc_shots(6), z4, eol, simulation_shot(0xd), FUN_010201e4(bit 1/2/4, lamp, 0) (recognizer hook: 1,000 + lamp effect 100 + sound 0xce when the recognizer cannot be lit, otherwise +2,500 + deff 108 per step, other worker), base. Always: restart 0x7b [0x0102aec8] | 1,080 | (recognizer hook) | 2,500 + 1,080 |
| 52 | 3-BANK MOTOR (DN) | 0x07ff | | In normal play, if OS timer 8 is running, it is reset (FUN_00010b18(8,0,0,0)) [0x0102b03c] | none | | |
| 53 | 3-BANK MOTOR (UP) | 0x07ff | | empty handler | none | | |
| 54-56 | RECOG. MOTOR POS. 1-3 | 0x07ff | | FUN_010226c8(0x3b47c, sw): stores the position at 0x3b49f. In test state (0x37274 & 0x100, mode 0x81) plays sound 0x0f when it closes | none | | |
| 15, 16 | TOURNAMENT START, START BUTTON | 0x07ff | | OS handlers 0x0002101c / 0x00021004 (not game rules) | | | |
| 18-22 | TROUGH 1-4, JAM | 0x0fff | | generic ball-device handler 0x0001d994 | | | |

### 5.1 Spinners

- **Left spinner, sw44** [on_l_inner_loop 0x01029ba4, task_64 0x01029b54, FUN_01029ab0]:
  - First spin while task 0x64 is not running: lspin_total = 0 and pending = 0, then score one spin
    and show deff 41 (left spinner) unless it is already running. Then start task 0x64, audit 0x64
    L. INNER LOOP, and fire the **shot 2 hooks** (section 6).
  - Later spins while the task runs only add 1 to pending. The task scores one pending spin per tick
    and ends after 62 ticks without a pending spin.
  - Each scored spin: score_add(lspin_value x (3 if task 200 TRON SPINNERS is running, else 1)),
    lamp effect 33, sound 0xec.
  - The handler adds the base 90 for every spin. A spin is therefore 10,000 + 90 by default
    (verified).
- **Right orbit spinner, sw36** [FUN_01029f20, task_65, FUN_01029e2c]:
  - Same pattern: deff 42, lamp effect 34, sound 0xee, idle timeout 93 ticks, rspin_value.
  - On the first spin of a session it also does two things. If task 199 (TRON BUMPERS) is running,
    no multiball is running (FUN_0100f918) and the right orbit is not a lit combo shot
    (FUN_01003370(5)), it raises the orbit post. If the post is up (0x3b4f0 == 1), it fires the
    **shot 5 (right orbit) hooks** FUN_0102a794. With the post up the ball cannot reach sw46, so the
    spinner stands in for the orbit switch (inferred).
  - The right spinner does **not** count as the right-orbit audit 0x61 or start the orbit guard tasks.

### 5.2 Pop bumpers [FUN_0101c3a4]

For each valid jet fire (in this order):
1. mult = 3 if task 199 (TRON "BUMPERS") is running, else 1.
2. FUN_0100c470: advance the pop-lamp pattern from table 0x040d2848 (state 0x211163b / 0x211163f).
3. If Big Bumps (task 0xcb) is running: +25,000, then deff 135 with the hit count and running total.
4. If pop_hits_left is not 0 and not 1:
   - points = min(10,000 + 2,500 x pop_value_level, 50,000) x mult.
   - deff 43 ("%d MORE / POP BUMPERS = value / total"), shown with hits_left - 1. If deff 43 is not
     already running, its accumulator is reset first.
   - Lamp effect 41 on that bumper's lamp, sound 0x50 (x1) or 0x51 (x3), hits_left -= 1.
5. Otherwise the level is complete:
   - points = min(100,000 + 25,000 x pop_value_level, 500,000) x mult.
   - pop_levels_done += 1 and pop_value_level += 1 (both stop at 0xff).
   - deff 44 (level completed: level, value, mult, points), lamp effect 42, sound 0x50.
   - pop_hits_left = min((adj65 + pop_levels_done) x 5 + 20, 50).
6. The handler then adds the base 170.

With the defaults, the first level takes 25 hits: 24 x (10,000 + 170), then 100,000 + 170. The second
level takes 30 hits at 12,500 (verified in emulator: traces/skill_shots.jsonl, marker bumpers_x26).

### 5.3 Hook argument conventions (the same shot, numbered per hook)

| Shot | Index (portal_mb_shot, on_disc_m_b_blue_disc_shots, on_combo_awards, on_find_flynn_completed) | Bit (on_clu_hurryup_awards, light_cycle_mb_shot, light_cycle_target) | on_quorra_m_b_super_jackpots bit | simulation_shot id | Combo mask | Arrow lamp (combo lamp group) |
|---|---|---|---|---|---|---|
| left orbit | 0 | 0x01 | | 0x0e | 0x01 | 16 L. LOOP ARROW (group 70) |
| left ramp | 1 | 0x02 (CLU hook: not called) | | 0x0f | 0x02 | 49 LEFT RAMP ARROW (71) |
| left inner loop | 2 | 0x04 | 0x04 | 0x10 | 0x04 | 64 L. INNER LOOP ARROW (72) |
| right inner loop | 3 | 0x08 (CLU: not called) | 0x08 | 0x11 | 0x08 | 57 R. INNER LOOP ARROW (73) |
| right ramp | 4 | 0x40 | | 0x12 | 0x10 | 56 R. RAMP ARROW (74) |
| right orbit | 5 | 0x80 | | 0x13 | 0x20 | 33 R. LOOP ARROW (75) |
| recognizer 3-bank | 6 (disc MB only) | | 0x10 | 0x0d | | |
| disc | 6 (portal) / 7 (disc MB) | | | 0x01 | | |
| VUK | | 0x100 (CLU only) | | 0x00 | | |

Other simulation_shot ids: 2-5 TRON letters T,R,O,N; 6-8 CLU C,L,U; 9-12 ZUSE Z,U,S,E.
Note: portal_mb_shot uses **6** for the disc, while disc multiball uses 6 for the recognizer and 7 for
the disc.

## 6. The canonical shots (how each is recognised, and its exact hook order)

All shot hook functions below are written out in the disassembly; the order is exact.

### Shot 0: Left orbit (sw43)
- Counted when sw43 closes, task 0x67 is not running, and task 0x66 is not running (the ball is not
  finishing a right-orbit pass). 0x67 then blocks a repeat for 125 ticks (2.03 s). 0x68 makes the
  next sw46 within 187 ticks (3.04 s) the orbit exit, not a right-orbit shot. [0x0102a808]
- Order: audit 0x60 LEFT ORBIT -> FUN_0102a728 { return at once if task 0x3c is running (creator not
  found, see Open questions); portal_mb_shot(0); simulation_shot(0xe); on_clu_hurryup_awards(1);
  on_disc_m_b_blue_disc_shots(0); light_cycle_mb_shot(1); light_cycle_target(1);
  **on_combo_awards(0)**; on_find_flynn_completed(0); zuse_target_hit(4); eol_shot_score() }
  -> restart 0x67 (125), 0x68 (187) -> sound 0xed -> base 1,220.

### Shot 1: Left ramp (sw35 entrance, sw37 exit)
- Only the exit sw37 counts. The entrance gives 560 + sound 0xeb and nothing else.
- Order at sw37 [on_left_ramp 0x0102a940]: audit 0x62 -> portal_mb_shot(1) -> simulation_shot(0xf,0) ->
  **FUN_01028cb8** (left-ramp skill shot) -> on_disc_m_b_blue_disc_shots(1) -> light_cycle_mb_shot(2) ->
  light_cycle_target(2) -> **on_combo_awards(1)** -> on_find_flynn_completed(1) -> zuse_target_hit(4)
  -> eol_shot_score -> FUN_01004e94(0) (End of Line ramp jackpot) -> FUN_010042d0(0) (End of Line
  letter, deff 55) -> sound 0xeb -> base 1,170.
- No CLU hurry-up hook on the left ramp.
- `on_left_ramp_2` (0x0102a9bc) is a variant that waits a delay and checks sw37. Nothing calls it in
  1.74 (dead code).

### Shot 2: Left inner loop (sw44 left spinner)
- There is no loop switch. The first spin of a spinner session counts as the shot: task 0x64 not
  running, i.e. at least 62 ticks (1.01 s) after the last processed spin.
- Order [on_l_inner_loop 0x01029ba4]: reset the session, score the first spin (deff 41), start task
  0x64 -> audit 0x64 -> portal_mb_shot(2) -> simulation_shot(0x10) -> on_clu_hurryup_awards(4) ->
  on_disc_m_b_blue_disc_shots(2) -> on_quorra_m_b_super_jackpots(4) -> light_cycle_mb_shot(4) ->
  light_cycle_target(4) -> FUN_0101f410(4,0) (Quorra "to light": 10,000 + deff 62) ->
  **on_combo_awards(2)** -> on_find_flynn_completed(2). Then the sw44 handler adds z4, eol,
  FUN_01013eac and base 90.
- Here, unlike the other shots, combos run **after** disc, Quorra and light cycle.

### Shot 3: Right inner loop (sw39)
- Every close counts. There is no guard.
- Order [0x0102ae3c]: audit 0x65 -> portal_mb_shot(3) -> simulation_shot(0x11) -> **on_combo_awards(3)**
  -> on_find_flynn_completed(3) -> on_disc_m_b_blue_disc_shots(3) -> on_quorra_m_b_super_jackpots(8)
  -> light_cycle_mb_shot(8) -> light_cycle_target(8) -> zuse_target_hit(4) -> eol_shot_score ->
  FUN_01000b28(1) (adds 1 to per-player counter 0x21115d3+p, cap 25) -> on_gem_hurryup_awards(8) ->
  FUN_01013a08(0) -> base 1,190.
- FUN_01013a08 is the GEM qualifier. When no GEM hurry-up is running and no blocking mode is on, it
  adds 1 to 0x2111680[p-1]. It shows deff 75 "n MORE TO START" until 3 (5 once GEM has been played,
  flag 0x2111677+p), then starts the GEM hurry-up. It always scores **250,000** when allowed
  (verified).
- Here combos and Find Flynn run **before** disc and Quorra. No CLU hook.

### Shot 4: Right ramp (sw38 entrance, sw34 exit)
- Order at sw34 [on_right_ramp 0x0102aa50]: audit 0x63 -> portal_mb_shot(4) -> simulation_shot(0x12) ->
  **FUN_01028ea4** (right-ramp skill shot) -> on_clu_hurryup_awards(0x40) ->
  on_disc_m_b_blue_disc_shots(4) -> light_cycle_mb_shot(0x40) -> light_cycle_target(0x40) ->
  **on_combo_awards(4)** -> on_find_flynn_completed(4) -> zuse_target_hit(4) -> eol_shot_score ->
  FUN_01004e94(1) -> FUN_010042d0(1) -> **FUN_0100396c** (lights the End of Line combo jackpot at the
  VUK, see combos.md) -> sound 0xeb -> base 1,170.
- `on_right_ramp_2` (0x0102aad8) is dead code like the left one.

### Shot 5: Right orbit (sw46, or the first sw36 spin while the post is up)
- Same guard scheme as the left orbit, mirrored: 0x69 repeat (125), 0x66 makes the next sw43 an exit
  (187), 0x68 (set by a left orbit **or by any plunge**) makes this sw46 an exit.
- Order [FUN_0102a794]: return if task 0x3c is running; portal_mb_shot(5); simulation_shot(0x13);
  on_clu_hurryup_awards(0x80); on_disc_m_b_blue_disc_shots(5); light_cycle_mb_shot(0x80);
  light_cycle_target(0x80); **on_combo_awards(5)**; on_find_flynn_completed(5); zuse_target_hit(4);
  eol_shot_score; FUN_0100ddb0(1). FUN_0100ddb0 lights Flynn's Arcade when no multiball is running:
  per-player flag 0x211166b+p, deff 104 the first time.
- From sw46 it then runs: restart 0x69 and 0x66, sound 0xef, base 1,220.
- From the spinner, the orbit audit, guards and base are not applied (inferred quirk).

### Shot 6: Recognizer (3-bank sw49-51)
- One hit per 10-tick quiet window. Hook order: on_quorra_m_b_super_jackpots(0x10) ->
  on_disc_m_b_blue_disc_shots(6) -> zuse_target_hit(4) -> eol_shot_score -> simulation_shot(0xd) ->
  FUN_010201e4(bit, lamp, 0) -> base 1,080.

### Shot 7: Disc (sw41)
- One hit per 125-tick window. A second hit inside the window cancels it, so a third hit scores again.
- Hook order: portal_mb_shot(6) -> simulation_shot(1) -> on_disc_m_b_blue_disc_shots(7) ->
  FUN_0100781c -> zuse_target_hit(4) -> eol_shot_score -> FUN_01004e94(2) -> FUN_01020da8(2,0) ->
  lamp effect 75 -> sounds 0x52 and 0x53 -> base 2,310.

### Not a numbered shot: VUK / Flynn's Arcade (sw11)
See the table. on_vuk runs the VUK skill shot first, then simulation_shot(0), CLU (0x100) and the End
of Line combo jackpot, and only then the mode-specific VUK hooks.

## 7. Media

| When | Display effect | Sound calls | Lamp effect | Tube show |
|---|---|---|---|---|
| Slingshot | none | 0xe8 L (sample 0x0e2), 0xe9 R (0x0e3) | lamp rotation FUN_01017128 | |
| Pop hit | deff 43 "%d MORE / POP BUMPERS =" | 0x50 (0x077-0x07a), 0x51 at x3 (0x042-0x044) | 41 (bumper lamps 46-48) | |
| Pop level complete | deff 44 | 0x50 | 42 | |
| Big Bumps pop | deff 135 | | | |
| Left / right spin (first of a session) | deff 41 / deff 42 | 0xec (0x0cb/0x0cc) / 0xee (0x0ca) every scored spin | 33 / 34 | |
| Ramp entrance or exit | | 0xeb (0x0cd-0x0cf) | | |
| Left / right orbit counted | | 0xed / 0xef (0x07b-0x07d) | | |
| Disc | | 0x52 (0x0e4-0x0e7), then 0x53 (0x05f/0x060); re-hit 0x54 (0x0e8-0x0eb) | 75 (disc flashers) | |
| ZEN | deff 100 | 0xe5 (0x051) | 117 (from deff 100) | |
| Plunge | | 0xea (0x0d0) | | |
| Outlane unlit / special | deff 82 when special | 0xa2 (0x0a1-0x0a4) / 0x9e (0x0ed); insult 0x129 (left only) | 90 when special | |
| Recognizer motor position (test state) | | 0x0f | | |

## 8. Lamps

Descriptor word +4 links a switch to its insert: sw1-4 -> lamps 4,3,2,1; sw7/8/48/13 -> 12/10/43/29;
sw25/14/28 -> 9/30/31; sw24/29 -> 8/32; sw30-32 -> 46-48; sw49-51 -> 53/52/51. Mode hooks use these
inserts; this layer only blinks them through the lamp effects above. The outlane special lamps 8 / 32
are read by FUN_01016e58 and turned off when collected (while FUN_00023fc8() < 2).

## 9. Interactions

- **Tilt:** playfield handlers are not dispatched while the state word is not 0 (section 4), and
  FUN_0102a188 drops base scores while tilted. TRON targets need (0x37274 & 0x312) == 0.
- **Multiball:** FUN_0100f918 (any multiball: disc, Quorra, light cycle, portal, End of Line, via
  FUN_0100f8b0) blocks the ZEN 42,000 award, the right-spinner post raise, arcade lighting, the
  insult speech, and starting a combo window.
- **Playfield validation:** the first instant switch, or 3 different counting switches, validates the
  ball (object 0x372e8). Event 0x6a then sets game flag 0x1c and kills task 0x43 [0x0100f25c], i.e.
  ends the start-of-ball state. The same expiry logic drives the skill shots (skill_shots.md).
- **Shared counters other workers need:** combo state (combos.md); skill-shot counts
  0x2111814/18/1c; End of Line per-switch value 0x3ae00 / total 0x3ae04; GEM qualify counter
  0x2111680; zen_count 0x21118bc.

## 10. Reference scenario

`traces/switches_and_shots.txt` hits each switch once on ball 1 (after the auto-plunge), watching the
combo variables. Expected key events (all seen in `traces/switches_and_shots.jsonl`):

| Marker | Expected |
|---|---|
| plunge (t 11.55) | sound 0xea, task 0x68, orbit_post_state 0->1, coil 7 on; post drops at t 13.59 |
| sling_L / sling_R | 440, sound 0xe8 / 0xe9 |
| bumper_L | 10,000 (pop) + 170, deff 43, lamp effect 41, sound 0x50. The third distinct counting switch expires both armed skill shots (flags 30/31 cleared) |
| zuse_Z | 75,000 (Zuse hook) + 1,130 |
| clu_C | 10,000 + 1,090, lamp effect 86, sound 0x99 |
| tron_T | 10,000 + deff 107 (TRON hook) + 30 |
| bank_L | 2,500 + deff 108 + 1,080 |
| lspinner | 10,000 + 90, deff 41, audit 0x64, combo window opens (lit 0x18) |
| rspinner | 10,000 + 90, deff 42 |
| lramp_ent / lramp_exit | 560 / 1,170 + audit 0x62 |
| rramp_ent / rramp_exit | 560 / 1,170 + audit 0x63, task 0xcf (EOL combo jackpot lit) |
| rinner | 250,000 (GEM qualify, deff 75) + 1,190 |
| lorbit / rorbit | 1,220 each, audits 0x60 / 0x61 |
| disc / disc_again (3 s apart) | 2,310 each, lamp effect 75, sounds 0x52 + 0x53 |
| zen | 42,000 + deff 100 + 1,090; Find Flynn started (deff 136) |
| loutlane | 100,000, sound 0xa2 |

Also: `traces/skill_shots.jsonl` (disc re-hit gives 0x54 only; 3 fast spins = 3 scored spins and one
LIL shot; 26 pop hits = level complete on hit 25 at 100,000, then 30 hits needed at 12,500), and
`traces/combos.jsonl` marker orbit_passthrough_RO_then_LO (sw43 0.99 s after sw46 gives only 1,220,
no audit).

## 11. Open questions

- Task 0x3c, which gates the orbit shot hooks and the post raise: no creator found in game or OS code
  (searched for task_create/recreate/timer_restart with r0 = 0x3c). Probably an OS ball-device task
  id set elsewhere.
- FUN_00007304 & 1: which flipper button bit 0 is (the flipper table is built at runtime from
  FUN_00006ce4). Resolved: it is the left flipper button (verified with `button left`, traces/skill_shots_b.jsonl).
- Spinner value step functions 0x01029a5c / 0x01029dd8 (+2,500, cap 100,000) have no caller or
  pointer anywhere in the image, so spinner values stay 10,000 in 1.74 (unless another worker finds an
  indirect path).
- Debounce counts +0x1b/+0x1c are raw scan counts; the scan period was not measured.
- What the orbit up-post object does internally (vtable 0x39c00); its timing (about 2.04 s up) was
  only measured.
