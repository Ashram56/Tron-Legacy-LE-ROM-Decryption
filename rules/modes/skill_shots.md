# Skill shots

Stern Tron Legacy LE 1.74. 1 tick = 16.26 ms. Code block 0x01028a00-0x01029768, deffs 101-103.
Traces: `traces/skill_shots.jsonl` (left ramp), `traces/combos.jsonl` (right ramp, adj 79 = 1),
`traces/skill_shots_c.jsonl` (VUK).

## 1. Summary

Three independent skill shots are offered on each newly served ball. Each lasts until the ball has
touched 3 other playfield switches, or hits any switch that ends it at once:

| Skill shot | How it is lit | Collect | Value | Deff |
|---|---|---|---|---|
| **A: Left ramp** | Roll through the ZEN rollover (sw12) after the serve | Left ramp exit sw37 | 250,000 + 50,000 per earlier A this game, max 500,000 | 101 |
| **B: Right ramp** | Hold the **left flipper button** while (verified: traces/skill_shots_b.jsonl; the right button does nothing) the ball leaves the shooter lane. With adj 79 = 1 it is lit at every serve | Right ramp exit sw34 | 300,000 + 50,000 per earlier B, max 500,000 | 102 |
| **C: Flynn's Arcade / VUK** | Lit at every serve | VUK sw11 | 500,000 + 50,000 per earlier C, max 750,000 | 103 |

Collecting one skill shot cancels all three.

## 2. Settings

| Adj # | ROM name | Default | Range | Effect |
|---|---|---|---|---|
| 79 | DISABLE PLUNGE POST | 0 | 0-1 | 1: B starts at every serve instead of needing the held flipper, and the orbit post does not rise on plunge [0x01029148, 0x0102a31c] |

No adjustment changes values or timing.

## 3. State

| Name | RAM | Scope | Init / reset | Meaning |
|---|---|---|---|---|
| skA_armed | game flag 0x1e (30) | per serve | set by a serve (event 0xf, reason 3-5) [FUN_01028b58]; cleared when A starts, expires or is killed | ZEN may start A |
| skB_armed | game flag 0x1f (31) | per serve | set by a serve when adj 79 = 0 [FUN_01028d44]; cleared when B starts or dies | Plunge with flipper held may start B |
| skA_task | task 0x70 -> 0x71 | running | | A lit. 0x70 until expiry, then 0x71 for 93 ticks (1.51 s) grace. Both collect |
| skB_task | task 0x72 -> 0x73 | | | B lit, same scheme |
| skC_task | task 0x74 -> 0x75 | | | C lit, same scheme |
| skA_timeout | object 0x370d4 {done byte, 3 switch slots at 0x3b6fc} | per start | cleared when A starts (FUN_00010c08) | Distinct counting switches seen |
| skB_timeout | object 0x370e0, slots 0x3b700 | | cleared when B starts | |
| skC_timeout | object 0x370ec, slots 0x3b704 | | cleared when C starts | |
| skA_count | 0x2111814 + (p-1) (byte) | per game | 0 at the player's first ball (event 0x26) [0x010290ec] | A collected this game (stops at 0xff) |
| skB_count | 0x2111818 + (p-1) | per game | same | |
| skC_count | 0x211181c + (p-1) | per game | same | |

## 4. How they start

The serve event 0xf is posted by FUN_0001f258(reason) whenever the OS serves a ball. Its hook
FUN_01029148 does this [0x01029148]:
- reason 1: kill all three skill shots (FUN_010291a4).
- reason 3, 4 or 5 (3 = new ball at ball start; 5 = a trough serve from FUN_0001dd90):
  1. set skA_armed (flag 0x1e);
  2. if adj 79 = 1, start B now (FUN_01028e04); otherwise set skB_armed (flag 0x1f);
  3. start C now (FUN_01028f9c).
- Reasons 2 (ball-save re-serve), 7 and 8 do nothing here. A saved ball gets no new skill shot.

Starting a skill shot (FUN_01028c18 / FUN_01028e04 / FUN_01028f9c): only if its task pair is not
already running. Create task 0x70 / 0x72 / 0x74, clear the timeout object, refresh lamps.

- **A** starts when sw12 ZEN closes while flag 0x1e is set (FUN_01028b74, the first call in the sw12
  handler). Flag 0x1e is then cleared.
- **B** starts when sw23 opens (ball leaves the shooter lane) while flipper-button bit 0 is held
  (FUN_00007304() & 1) and flag 0x1f is set (FUN_01028d60). Flag 0x1f is then cleared.
  - This happens before the plunge-post logic. When B is running, the orbit up-post is **not**
    raised, which leaves the orbit open (inferred design: the held-flipper plunge is the "super"
    route).
- **C** is already running from the serve.

Verified at ball start: flags 30 and 31 set and task 0x74 started at the serve (t 9.90 s in every
trace).

## 5. Behaviour while running

### Timeout (how a skill shot is lost) [FUN_01028a00, FUN_01028a84, FUN_01028b04, OS 0x00010c70]
- **Counting switches** (event 0x6b: descriptor flag 0x1000, i.e. ZUSE 7/8/13/48, ramp entrances 35/38,
  spinners 36/44, disc 41, 3-bank 49-51, plus pop bumpers, slings and TRON targets that post it
  themselves):
  - each **different** switch fills one of the 3 slots of every running timeout object, unless the
    switch is excluded for that skill shot;
  - when the 3rd slot fills, the object is done and event 0x6a is posted;
  - the hook then kills that skill shot. Its task goes away entirely: the grace phase applies only
    when the task itself sees "done". A's arm flag 0x1e is cleared too.
- **Instant switches** (event 0x6c: flag 0x2000, i.e. ZEN 12, CLU 14/25/28, outlanes 24/29, ramp
  exits 34/37, right inner loop 39, orbits 43/46, VUK 11): every skill shot that does not exclude that
  switch is ended at once, and A's arm flag is cleared. This also applies when a skill shot is only
  armed (flags 0x1e/0x1f), even if its object was never started.
- Exclusions (a switch on this list neither counts nor ends that skill shot):
  - A (left ramp): 12 ZEN, 14 C(L)U, 28 CL(U), 35 L. ramp entrance, 37 L. ramp exit.
  - B (right ramp): 34 R. ramp exit, 38 R. ramp entrance, 43 left orbit, 46 right orbit. Orbit
    switches do not kill B, so the plunged ball can go round the orbit.
  - C (VUK): 11 only.
- Once the object is done, task 0x70 / 0x72 / 0x74 (which polls every 6 ticks) changes its id to
  0x71 / 0x73 / 0x75 and sleeps **93 ticks (1.51 s)**. The skill shot can still be collected during this
  grace period, but its lamps are already off (the lamp rules test only 0x70 / 0x72 / 0x74).

Note: the 3 distinct switches do not have to come after the start. A's object is cleared when A
starts (at ZEN), but before that the ball has usually touched the orbit and post area. Plunge-area
switches are on the exclusion lists.

### Collect

| Trigger | Condition | Effect | Display | Sound | Lamp | Next |
|---|---|---|---|---|---|---|
| sw37 L. ramp exit (on_left_ramp, 3rd hook after audit/portal/simulation) | task 0x70 or 0x71 running | score_add(min(250,000 + 50,000 x skA_count, 500,000)), x playfield multiplier; skA_count += 1 | deff 101 "SKILL SHOT" + value | 0x46 (sample 0x097) | 110 (from the deff), then lamps off | all three killed (FUN_010291a4) |
| sw34 R. ramp exit (on_right_ramp, same position) | task 0x72 or 0x73 | min(300,000 + 50,000 x skB_count, 500,000); skB_count += 1 | deff 102 | 0x47 | 112 | all killed |
| VUK (on_vuk, the first hook) | task 0x74 or 0x75 | min(500,000 + 50,000 x skC_count, 750,000); skC_count += 1 | deff 103, played through FUN_0100fbb0 (task 0x86) so the ball is held in the VUK while it shows (up to 3,750 ticks, priority 0x9f) | 0x48 | 114 | all killed |

The collecting shot then runs its other hooks as normal: combos, End of Line, the ramp's base 1,170 or
the VUK's 350, and so on.

## 6. How it ends

Collected, timed out (3 distinct counting switches, + 93-tick grace when the task itself saw it),
killed by an instant switch, or killed by serve reason 1. Tilt kills all three: event 0x6a from the
tilt goes through FUN_01028b04 only for matching objects; the tasks die with the ball (inferred).
Counts carry over to later balls of the same game; flags and tasks do not.

## 7. Media

| When | Display effect | Sound calls | Lamp effect | Ramp tube show |
|---|---|---|---|---|
| A lit (task 0x70) | | | 109 flashes group 28: lamps 11 LEFT RAMP (LIGHT CYCLE), 50 LEFT RAMP (DISC), 49 LEFT RAMP ARROW, chasing every 6 ticks | 11 (left tube fades on/off, 31-tick steps) |
| B lit (task 0x72) | | | 111 on group 29: lamps 42, 55, 56 (right ramp inserts) | 12 (right tube) |
| C lit (task 0x74) | | | 113 on group 30: lamp 45 FLYNN'S ARCADE | |
| Collect A/B/C | deff 101/102/103: "SKILL SHOT" (msg 0x617/0x618/0x619) with the value blinking on even frames; 21 frames x 3 ticks, then hold 10 | 0x46 / 0x47 / 0x48, all sample 0x097 | 110 / 112 / 114 | |

## 8. Lamps

See section 7. The lamp and tube rules are registered in FUN_0102976c:
- lamp effect 109 and tube show 11 while task 0x70 runs;
- 111 and tube 12 while task 0x72 runs;
- 113 while task 0x74 runs.

## 9. Interactions

- The left-ramp collect runs before disc multiball, light cycle, combos, Find Flynn and End of Line on
  the same shot. The right-ramp collect runs before CLU too. The VUK collect runs before everything
  else at the VUK.
- B blocks the orbit up-post on that plunge. adj 79 = 1 removes the post and the need to hold the
  flipper.
- ZEN (sw12) both starts A and is an instant switch for B and C. Rolling through ZEN therefore ends B
  and C (verified: the ZEN hit cleared flag 31).
- Any instant switch (e.g. right ramp exit, orbit) ends A unless excluded. Verified: the right ramp
  exit cleared flag 30.

## 10. Reference scenarios

| Trace | Steps | Expected / seen |
|---|---|---|
| `traces/skill_shots.txt` | start, auto-plunge, ZEN, then left ramp 35 -> 37 | ZEN starts task 0x70 (lamp effect 109, tube 11), flag 30 cleared; at sw37: **250,000**, deff 101, sound 0x46, skA_count 0 -> 1 |
| `traces/combos.txt` | adj 79 = 1, start, right ramp 38 -> 34 | task 0x72 started at the serve; **300,000**, deff 102, sound 0x47, skB_count 1 |
| `traces/skill_shots_c.txt` | start, VUK 11 | on_vuk after the VUK settles (0.76 s): **500,000**, task 0x86 -> deff 103, sound 0x48, skC_count 1 |
| `traces/switches_and_shots.txt` | slings 26, 27, then bumper 30 | 3 different counting switches: A and B disarmed at the bumper (flags 30/31 cleared) |

## 11. Open questions

- Resolved: flipper-table bit 0 is the left flipper button (verified in traces/skill_shots_b.jsonl).
- Serve reasons 4 and 5: 5 comes from FUN_0001dd90 (another trough serve path, probably
  shoot-again / extra ball); no caller with reason 4 was found. Reason 1 (kill all) is also from
  FUN_0001dd90; its meaning was not traced.
