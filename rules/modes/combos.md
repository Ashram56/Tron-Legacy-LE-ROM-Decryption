# Combos (and the End of Line combo jackpot)

Stern Tron Legacy LE 1.74. 1 tick = 16.26 ms. Code: on_combo_awards 0x01003714 and helpers
0x01003118-0x010039e0. Tables: 0x040d2324 (per shot), 0x040d236c (12 named combos).
Traces: `traces/combos.jsonl` (2-, 3- and 4-way chain plus Castor), `traces/skill_shots.jsonl`
(Last Iso), `traces/combos_eol_jackpot.jsonl` (jackpot collect).

## 1. Summary

Making certain shots lights a short combo window: the arrows of the "next" shots flash. Hitting a
flashing arrow in time scores a combo:
- 250,000 for a 2-way, then +50,000 per extra step of the chain;
- deff 138 "N WAY COMBO" with the value;
- if the shot sequence matches one of 12 named combos (CASTOR, LAST ISO, ... RINZLER), the combo's
  value is **added to the End of Line jackpot**.

The jackpot starts at 500,000 every ball. It is collected at the VUK (Flynn's Arcade) shortly after a
right-ramp shot, and is shown as "END OF LINE / JACKPOT" (deff 139).

## 2. Settings

None. No adjustment is read by the combo code.

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| combo_starters | 0x3ad58 (u32) | per ball | 0x36 at every ball start (event 0x11) [0x010031ac] | Shots that may open a window without a combo: left ramp 0x02, left inner loop 0x04, right ramp 0x10, right orbit 0x20. Never changed afterwards |
| combo_lit | 0x3ad5c (u32) | while window | set when a window opens | Shot masks that score a combo now |
| combo_count | 0x3ad54 (u32) | chain | set to 1 when a shot does not combo; +1 per combo | "N" of the N-way combo |
| combo_timer | 0x3ad60 (u32) | window | 312 (0x138) when a window opens | Countdown, -7 every 7 ticks |
| combo_history | 0x3ad64[0..4] (u32 x5), length 0x3ad78 | chain | length 0 | Recent shot masks, kept only while they are a prefix of a named combo |
| combo_base | 0x3ad10 + 4(p-1) (RAM) | per player | 250,000 (0x3d090) at the player's first ball (event 0x26) [0x0100317c] | 2-way value. A raise function FUN_010032ec (+x, cap 750,000) exists but has no caller in 1.74 |
| combo_total | 0x21115fc + 2(p-1) (u16) | per game | 0 at game start (event 0x2e) for all players [0x01003138] | Combos made this game (stops at 0xffff); shown in deff 138 |
| eol_combo_jackpot | 0x2111608 + 4(p-1) | per ball | 500,000 (0x7a120) at every ball start [0x010031ac] | Grows by each named combo's value; scored at the VUK |
| eol_jackpot_collected | 0x2111604 + (p-1) (byte) | per ball | 0 at every ball start | Times collected (stops at 0xff) |
| combo window task | 0xcd, then 0xce | | | 0xcd: main window (lamps flash). 0xce: 125-tick grace (combos still count) |
| eol jackpot lit task | 0xcf, then 0xd0 | | | 0xcf: 156 ticks, then 0xd0: 93 ticks; both allow the collect |

## 4. How it starts (a shot opens a window)

`on_combo_awards(shot)` is called from shots 0-5 (switches_and_shots.md, section 6; it is not called
for the recognizer, disc or VUK). With mask = table 0x040d2324[shot].word0 and next =
table[shot].word1 [0x01003714]:

| Shot | Mask | Next shots lit (word1) | Can open a window by itself? |
|---|---|---|---|
| 0 left orbit | 0x01 | none | no (finisher only) |
| 1 left ramp | 0x02 | 0x05 = left orbit + left inner loop | yes |
| 2 left inner loop | 0x04 | 0x18 = right inner loop + right ramp | yes |
| 3 right inner loop | 0x08 | none | no (finisher only) |
| 4 right ramp | 0x10 | 0x20 = right orbit | yes |
| 5 right orbit | 0x20 | 0x18 = right inner loop + right ramp | yes |

Step by step, for each shot:
1. **Combo test.** If task 0xcd or 0xce is running **and** combo_lit & mask, it is a combo (section 5).
2. **Otherwise:** combo_count = 1, history emptied, then the mask is appended (with prefix trimming,
   section 5).
3. Kill tasks 0xcd/0xce: any shot closes the old window.
4. **Open a new window** if no multiball is running (FUN_010032b4 = !FUN_0100f918) and either
   (combo_starters & mask), or a combo was just scored and the shot is not left orbit / right inner
   loop (mask & 9 == 0). The window opens only when next != 0: combo_lit = next, combo_timer = 312,
   task 0xcd created.
5. rules_refresh_request (lamps).

So a chain can only continue through shots that light something (left ramp, left inner loop, right
ramp, right orbit). Left orbit and right inner loop always end a chain.

**Window timing** [task_cd 0x010033c4]: sleep 7 ticks, timer -= 7 (0 when below 7), repeat until 0.
That is 45 x 7 = 315 ticks (5.12 s) as task 0xcd. The task then becomes 0xce, refreshes the lamps and
sleeps 125 ticks (2.03 s). Combos still count during 0xce. Total window is about 7.15 s
(verified: the counter fell by 7 every 0.115 s; a right orbit 8.5 s after a right ramp was not a combo,
traces/switches_and_shots.jsonl).

## 5. Behaviour while running

### Combo award (shot is lit, window running) [0x01003748-0x01003834]
1. combo_count += 1, combo_total += 1 (saturating).
2. Append the mask to the history and look up a named combo (below).
3. value = combo_base + max(combo_count - 2, 0) x 50,000. So with defaults: 2-way 250,000, 3-way
   300,000, 4-way 350,000, 5-way 400,000. **score_add(value)** (x playfield multiplier) [0x0100344c].
4. deff 138 with arg +0x30 = points scored, +0x34 = named combo entry (or 0), +0x38 = combo_count,
   +0x3c = combo_total.
5. audit 0x7a COMBO AWARDS.
6. If a named combo matched: **eol_combo_jackpot += its value** (it is not scored now), then audit
   its counter.
7. If next != 0 and no multiball is running, a new window opens with that shot's next shots (step 4
   of section 4; the starter test is waived because a combo was scored).

| Trigger | Condition | Effect | Display | Sound | Lamp | Next state |
|---|---|---|---|---|---|---|
| Lit shot | task 0xcd/0xce running and combo_lit & mask | +combo_base + 50,000 x (N-2); named value -> EOL jackpot | deff 138 | 0x127 (sample by N) | lamp effect 160 + shaker | window re-opens on the shot's next mask (if any) |
| Unlit shot | | count = 1, history = [mask] | | | | window opens if it is a starter |

### Named combos (table 0x040d236c, 24-byte entries {id bit, sequence ptr, msg, check fn, value, audit | keep<<16})

Sequences are lists of shot masks, oldest first. Each check fn returns 1 (no extra conditions).

| # | Name (msg) | Shots in order | Value added to EOL jackpot | Audit | Keep history? |
|---|---|---|---|---|---|
| 0 | CASTOR COMBO (0x6a4) | left ramp -> left orbit | 350,000 | 0x7b | no |
| 1 | LAST ISO COMBO (0x6a5) | left ramp -> left inner loop | 400,000 | 0x7c | yes |
| 2 | THE OUTLANDS COMBO (0x6a6) | left ramp -> left inner loop -> right inner loop | 750,000 | 0x7d | no |
| 3 | LIGHT CYCLE COMBO (0x6a7) | left ramp -> left inner loop -> right ramp | 500,000 | 0x7e | yes |
| 4 | LIGHT RUNNER COMBO (0x6a8) | left ramp -> LIL -> right ramp -> right orbit | 650,000 | 0x7f | yes |
| 5 | THE GRID COMBO (0x6a9) | left ramp -> LIL -> right ramp -> right orbit -> right inner loop | 850,000 | 0x80 | no |
| 6 | SIREN COMBO (0x6aa) | left inner loop -> right inner loop | 500,000 | 0x81 | no |
| 7 | JARVIS COMBO (0x6ab) | left inner loop -> right ramp | 350,000 | 0x82 | yes |
| 8 | 3-MAN LIGHT JET COMBO (0x6ac) | LIL -> right ramp -> right orbit | 500,000 | 0x83 | yes |
| 9 | RICOCHET COMBO (0x6ad) | LIL -> right ramp -> right orbit -> right inner loop | 650,000 | 0x84 | no |
| 10 | END OF LINE COMBO (0x6ae) | right orbit -> right inner loop | 550,000 | 0x85 | no |
| 11 | RINZLER COMBO (0x6af) | right orbit -> right ramp | 350,000 | 0x86 | no |

History rules [FUN_010035c0, FUN_010034ac, FUN_01003618]:
- **Append:** add the mask at the end (at most 5 entries). Then, while the history is not a prefix of
  any named sequence, drop the oldest entry. The history is always the longest recent run that could
  still become a named combo.
- **Match:** a named combo matches when the history equals its whole sequence. On a match with
  keep = 0 the history is emptied. With keep = 1 it is kept, so the chain can grow into the longer
  combo (Last Iso -> Light Cycle -> Light Runner -> The Grid; Jarvis -> 3-Man Light Jet -> Ricochet).
- Lookup happens only on a combo award. The history is also reset to [mask] whenever a shot does not
  score a combo.

Every step of a chain scores its N-way value. Named values only grow the jackpot, e.g. the verified
chain LIL -> RR -> RO -> RIL: 250,000 (Jarvis, jackpot 500,000 -> 850,000), then 300,000 (3-Man,
-> 1,350,000), then 350,000 (Ricochet, -> 2,000,000).

### End of Line combo jackpot (collect)
- Lit by every right-ramp shot [FUN_0100396c]: kill 0xcf/0xd0, create task 0xcf (task fn at 0x01003948:
  sleep 156 ticks, become 0xd0, refresh, sleep 93 ticks). Lit for 249 ticks (4.05 s) after the right
  ramp. Lamp effect 161 (lamp list 0x040d248c) runs while task 0xcf runs [leff rule 0x01004010].
- Collected in on_vuk (sw11, after the ball settles) by FUN_010039e0:
  - if 0xcf or 0xd0 is running: score_add(eol_combo_jackpot);
  - task 0x87 holds the ball while deff 139 "END OF LINE / JACKPOT / value" plays (FUN_0100fbb0,
    priority 0x9f, up to 3,750 ticks);
  - eol_jackpot_collected += 1, kill 0xcf/0xd0.
  - The jackpot value is **not reset** on collect. It stays until the next ball start.
- VUK hook order: VUK skill shot, simulation_shot, CLU, then this collect.

## 6. How it ends

- Window: ends after about 7.15 s (315 + 125 ticks), at any shot (tasks killed, maybe re-opened), or
  at a combo on a finisher shot.
- Starting a window is blocked during any multiball (FUN_0100f918). An already open window still
  scores, because the combo test itself does not check multiball.
- Ball end: combo_starters, the jackpot (500,000) and the collect counter are reset at the next ball
  start. combo_base is reset at the player's first ball; combo_total at game start.

## 7. Media

| When | Display effect | Sound | Lamp effect | Tube |
|---|---|---|---|---|
| Combo | deff 138 (0x01003c30): 41 frames x 3 ticks then hold; big "%u" N (fonts 0x2a/0x2b blinking every 2 frames), "WAY", "COMBO", points, named combo text (msg at entry +8) if any, "JACKPOT=%,02lu" = current eol_combo_jackpot | 0x127 played with index min(N, 6): sample list 0x023 0x023 0x024 0x025 0x026 0x027 0x028, so 2-way -> 0x024, 3-way -> 0x025 ... | 160 (from deff 138) + shaker_run(2,3) | |
| Window open | | | 159: flashes the arrow lamps of combo_lit shots | |
| EOL jackpot lit | | | 161 | |
| EOL jackpot collect | deff 139 "END OF LINE" / "JACKPOT" / value, 31 frames x 3 ticks | | 162 | |

## 8. Lamps

Combo arrows (lamp group per shot from table 0x040d2324 word 2): left orbit lamp 16 L. LOOP ARROW (group
70), left ramp 49 (71), left inner loop 64 (72), right inner loop 57 (73), right ramp 56 (74), right orbit 33
R. LOOP ARROW (75).

Lamp effect 159 [0x01003a74] runs while no multiball is running and (combo_starters != 0 or task 0xcd
runs). In practice that is always during single-ball play, but it only claims lamps while task 0xcd
runs:
- lit shots' arrows alternate on/off;
- the period is combo_timer / 31 ticks (10 at the start), at least 2, so the flashing speeds up as the
  window runs out;
- unlit arrows are released to other modes.

During the 0xce grace period the arrows are released, but combos still score.

## 9. Interactions

- Called from inside each shot's hook chain. The order matters: left orbit, left ramp, right ramp and
  right orbit call combos after disc multiball and light cycle; the right inner loop calls it before
  them (switches_and_shots.md, section 6).
- Multiball blocks new windows only.
- The right-orbit spinner checks FUN_01003370(5) (right orbit lit for combo) before raising the orbit
  post, so the post does not block a lit right-orbit combo.
- Other workers: eol_combo_jackpot (0x2111608) is the "JACKPOT" shown in the End of Line / combo
  displays. on_vuk order is VUK skill shot -> CLU -> EOL combo jackpot.

## 10. Reference scenario

`traces/combos.txt` (adj 79 = 1, so the right-ramp skill shot fires first). Seen in `traces/combos.jsonl`:

| Marker | Expected |
|---|---|
| skillB_right_ramp | right-ramp skill shot 300,000; no combo; window opens with lit 0x20 |
| (8 s wait) | window expires |
| combo_LIL_start | no combo (count 1); lit 0x18 |
| combo_RR_jarvis | 250,000, deff 138, audits 0x7a + 0x82; jackpot 500,000 -> 850,000; lit 0x20 |
| combo_RO_3man | 300,000, audit 0x83; jackpot -> 1,350,000; lit 0x18 |
| combo_RIL_ricochet | 350,000, audit 0x84; jackpot -> 2,000,000; history emptied; no new window |
| castor_LR then castor_LO | 250,000, audit 0x7b; jackpot -> 2,350,000 |

`traces/skill_shots.jsonl`: left ramp then left spinner = LAST ISO (250,000, audit 0x7c, jackpot
500,000 -> 900,000).
`traces/combos_eol_jackpot.txt`: right ramp, then VUK 1.2 s later -> 500,000 (FUN_010039e0) + deff 139.

## 11. Open questions

- combo_base can never change in 1.74: FUN_010032ec (raise, cap 750,000) has no caller.
- FUN_010033bc (a "pause window" test inside task_cd) always returns 0. The window never pauses.
