# Tron Legacy LE 1.74: developer guide for the MPF/Godot rebuild

This guide and the files it links describe the complete game rules of Stern's Tron Legacy Limited
Edition, code version 1.74 (PinMAME set `trn_174h`). Everything was read from the ROM code and
checked in an emulator running the real ROM. The goal is that you can rebuild the game in MPF
without guessing. Where the ROM does something odd, the spec says so. If you copy it, the rebuild
plays like the original.

Start with sections 1-4 here, then [switches_and_shots.md](modes/switches_and_shots.md) and
[game_flow.md](modes/game_flow.md). Then read the features in any order.

## 1. How each feature file is laid out

Every file in `modes/` follows the same 11 sections: summary, settings, state, how it starts,
behaviour while running, how it ends, media, lamps, interactions, reference scenario, open questions.

- **Sources.** Every rule ends with its source in brackets: a function address such as `[0x01007244]`,
  to look up in `tron/code/tron_game_decompiled_v2.c` (search `// ==== 01007244`), or a ROM table
  address. You don't need the code to build the game. It is there to settle doubts.
- **Confidence.** Rules marked `(verified ...)` were seen in an emulator trace. Rules marked `(inferred)`
  come from reasoning, not from a direct read. Everything else was read directly from code or tables.
- **Ids.** Display effects (`deff N`), lamp effects (`leff N`), ramp tube shows, sound calls
  (`0x0NN`), audits and game flags use the ROM's own numbers, so they line up with the asset package
  and the traces.

## 2. Conventions that apply everywhere

### 2.1 Time
- The OS ticks every **16.26 ms** in play, measured between 16.25 and 16.30 ms. The ROM itself treats
  62 ticks as one second, and some countdowns use 60, 64, 66 or 68 ticks per "second". Each spec gives
  both ticks and milliseconds; copy the tick counts.
- Most mode clocks **pause** under these conditions [0x0100ff64]:
  - the playfield is not yet validated (see 2.4);
  - a "show" display task (ids 0x81-0xa7: mode intros, totals, award animations) is running;
  - a pop bumper was hit in the last 156 ticks.

  Hurry-up clocks also restart the current second after a pause.

### 2.2 Scoring
- **All rule scores go through one function**, `score_add(points)` [0x0002340c]. It multiplies by the
  playfield multiplier byte at RAM 0x38180, which is **always 1 in 1.74** (only ever written with 1).
  TRON "DOUBLE SCORING" works another way; see [tron_targets.md](modes/tron_targets.md).
- **Base switch scores** (slings 440, pops 170 and so on) go through a helper [0x0102a188] that scores
  nothing while the game is tilted.
- Values that grow by "what was scored" (for example the Disc Multiball jackpot) add the points
  actually awarded.
- The **end-of-ball bonus** is a normal score add, so it can cross a replay level.

### 2.3 Scope of state: what resets when
Each spec's State table gives a scope for every variable:

| Scope | Reset by | Meaning |
|---|---|---|
| per game / per player | event **0x26** = the player's **first ball only** (also 0x2e game start) | counts that last the whole game for that player, kept in NVRAM arrays indexed [player-1] |
| per ball | event **0x11** = every ball start, event **0x1d** = end of ball | bonus multiplier, skill shots, timed modes |
| while the mode runs | the mode's own start | jackpot values, phase, counters |

Game flags (bits set and cleared by `game_flag_set/clear`) are saved and restored per player when the
player changes (inferred from the save/restore code; not tested with 2 players).

### 2.4 Playfield validation
A new ball counts as "in play" after **1 force switch** (11, 12, 14, 24, 25, 28, 29, 34, 37, 39, 43, 46)
or **3 different counting switches** (7, 8, 13, 35, 36, 38, 41, 44, 48-51, bumpers). Slings and TRON
targets do not count. Ball save, skill-shot expiry and timer pauses depend on this
([game_flow.md](modes/game_flow.md)).

### 2.5 OS events used by the rules
| Event | When |
|---|---|
| 0x2e | game start |
| 0x26 | a player's first ball (per-player game init) |
| 0x11 | every ball start (per-ball init) |
| 0x13 | ball start finished |
| 0x0f | ball served to the shooter lane (argument = serve reason; 3 = new ball, 2 = ball-save re-serve) |
| 0x1d | end of ball: stops all modes, shows totals, then bonus |
| 0x65 / 0x66 | tilt |
| 0x6a / 0x6b / 0x6c | playfield validated / counting switch / instant switch |

### 2.6 Game flags (mode state bits)
| Flag | Meaning |
|---|---|
| 0x1e / 0x1f | skill shot A / B armed |
| 0x22 | Disc Battle lit (kept to the next ball) |
| 0x24 / 0x25 | Disc Multiball running / restart still possible |
| 0x27 | End of Line (Daft Punk) Multiball running |
| 0x29 | Quorra Multiball running |
| 0x2b | Light Cycle Multiball running |
| 0x2c | Flynn's Arcade MORE TIME used |
| 0x33 | Sea of Simulation played (Portal pays a 50,000,000 bonus when clear) |
| 0x34 | Sea of Simulation running |
| 0x37 | Portal Multiball running |
| 0x2d, 0x32 | tested or cleared but never set in 1.74 (dead) |

## 3. How the game is wired

### 3.1 Switches fan out to feature hooks in a fixed order
Each playfield switch has one handler. A handler does three things in order:
1. It checks its own repeat guard.
2. It calls each feature's hook in a **fixed order** (for example Portal, then Disc Multiball, CLU,
   Light Cycle, combos, Find Flynn, ZUSE fast scoring, End of Line).
3. It adds a small base score.

The order matters when one hit could serve two features. In MPF, give your handlers the same
order (event handler priorities). The full table per switch, and the 8 canonical shots with how each
is recognised (entrance/exit pairs, spinner first spin, orbit pass-through windows), is in
[switches_and_shots.md](modes/switches_and_shots.md).

Each hook numbers the shots its own way: Portal uses 6 for the disc, while Disc Multiball uses 6 for
the Recognizer and 7 for the disc. Each spec names the convention it uses.

### 3.2 The VUK (Flynn's Arcade scoop, sw11) starts most things
When a ball enters the VUK, the game checks features in this order and does every one that is lit
[0x0102eddc]:
1. Flynn's Arcade award
2. Portal Multiball
3. Sea of Simulation
4. CLU hurry-up
5. Light Cycle Multiball
6. Quorra Multiball
7. End of Line Multiball

The skill shot C award and the End of Line combo jackpot are also collected here. One VUK entry can
start Light Cycle **and** Quorra together; this was verified, with 3 balls in play.

"Lit at the VUK" states share one per-player table at 0x2111894 + 4·k, used through
add/take/test [0x0102e8c0 / 0x0102eaa4 / 0x0102ec38].

### 3.3 Which multiballs can run together
| Feature | Blocked while running |
|---|---|
| Light Cycle, Quorra | Disc, End of Line, Sea of Simulation, Portal. Light Cycle and Quorra stack with each other |
| Disc Multiball | other multiballs (see [disc_multiball.md](modes/disc_multiball.md) §9); a Light Cycle, Portal or Sea of Simulation start cancels the Disc restart window |
| End of Line | any other multiball or Sea of Simulation |
| Portal | any multiball, Sea of Simulation, or the Disc restart window |

All multiballs end when fewer than 2 balls are in play [0x0101bcec]. Each then runs its own grace
window (lit shots still score), then shows its total.

### 3.4 Items: the progression to the wizard modes
Nine items: FLYNN, GEM, CLU, ZUSE, QUORRA, DISC, LIGHT CYCLE, RECOGNIZER, TRON. Each feature
*lights* its item when it is played and *collects* it when it is beaten. The stats live at
0x2111694 + 0x10·item + 4·(player-1): byte 0 = lit, byte 1 = collected.

The rules that use the items:
- **Lighting all nine** opens [Sea of Simulation](modes/sea_of_simulation.md).
- **Collecting all nine** opens [Portal Multiball](modes/portal_multiball.md).
- **The bonus** pays per item ([bonus.md](modes/bonus.md)).

[find_flynn_and_items.md](modes/find_flynn_and_items.md) lists what lights and what collects each item.

## 4. Feature index

| Feature | File | How it starts | Reference trace |
|---|---|---|---|
| Game flow, ball save, tilt, extra ball, match, high scores | [game_flow.md](modes/game_flow.md) | - | traces/game_flow, game_flow_tilt |
| End-of-ball bonus | [bonus.md](modes/bonus.md) | every drain | traces/bonus, bonus_skip |
| Attract, tournament (short) | [attract_and_service.md](modes/attract_and_service.md) | no game | traces/attract_and_service |
| Switches, base scores, shots, hook order | [switches_and_shots.md](modes/switches_and_shots.md) | - | traces/switches_and_shots |
| Skill shots A/B/C | [skill_shots.md](modes/skill_shots.md) | every new ball | traces/skill_shots, skill_shots_b, skill_shots_c |
| Combos and End of Line combo jackpot | [combos.md](modes/combos.md) | shot sequences | traces/combos, combos_eol_jackpot |
| TRON targets and timed awards | [tron_targets.md](modes/tron_targets.md) | sw1-4 | traces/tron_targets |
| ZEN rollover | [zen_rollover.md](modes/zen_rollover.md) | sw12 | traces/zen_rollover |
| Find Flynn and the 9 items | [find_flynn_and_items.md](modes/find_flynn_and_items.md) | ZEN rollover | traces/find_flynn_and_items |
| Flynn's Arcade mystery award | [flynns_arcade.md](modes/flynns_arcade.md) | VUK when lit | traces/flynns_arcade |
| CLU hurry-up | [clu_hurryup.md](modes/clu_hurryup.md) | CLU lanes, then VUK | traces/clu_hurryup |
| GEM hurry-up | [gem_hurryup.md](modes/gem_hurryup.md) | right inner loops | traces/gem_hurryup |
| ZUSE fast scoring | [zuse_fast_scoring.md](modes/zuse_fast_scoring.md) | ZUSE targets | traces/zuse_fast_scoring |
| Recognizer and Disc Battle | [recognizer_and_disc_battle.md](modes/recognizer_and_disc_battle.md) | Recognizer 3-bank | traces/recognizer_and_disc_battle |
| Disc Multiball | [disc_multiball.md](modes/disc_multiball.md) | Disc Battle, then disc hits | traces/disc_multiball, disc_multiball_restart |
| Quorra Multiball | [quorra_multiball.md](modes/quorra_multiball.md) | 5 left inner loops, then VUK | traces/quorra_multiball |
| Light Cycle Multiball | [light_cycle_multiball.md](modes/light_cycle_multiball.md) | 4 (then 6) Light Cycle shots, then VUK | traces/light_cycle_multiball, ..._repeat_and_stack |
| End of Line Multiball (= "Daft Punk") | [end_of_line_multiball.md](modes/end_of_line_multiball.md) | DAFT/PUNK ramps, then VUK | traces/end_of_line_multiball, ..._scoring |
| Daft Punk naming and music (companion page) | [daft_punk_multiball.md](modes/daft_punk_multiball.md) | same mode | traces/daft_punk_multiball |
| Sea of Simulation (mini wizard) | [sea_of_simulation.md](modes/sea_of_simulation.md) | all 9 items lit, then VUK | traces/sea_of_simulation |
| Portal Multiball (wizard) | [portal_multiball.md](modes/portal_multiball.md) | all 9 items collected, then VUK | traces/portal_multiball, ..._shots |

**Daft Punk and End of Line are one feature.** In 1.74, "Daft Punk Multiball" (the audit name and
the letters on the display) and "End of Line Multiball" (the screen title and settings 83-85) are the
same mode. Build it once.

**Unused or unreachable code in 1.74.** Don't build these:
- Light Cycle Maze video mode (deff 45): its start routine has no caller.
- Quorra "All Jackpots Doubled": its enable flag is never set.
- ZUSE "READY" (deff 93, flag 0x31).
- Deff 22: an empty function.
- Deff 110 "RECOGNIZER BATTLE!".
- Deff 127: a debug image viewer.
- Deffs 128/129: clip players with no caller.
- 0x0101283c: ends CLU, GEM and ZUSE together; it has no caller.
- The spinner and combo value raises: these functions have no caller.

## 5. Operator settings (adjustments)

The rules read these settings; defaults are factory values, and the traces use factory values.
Each mode file explains how its settings are used.

| Adj | Name | Default | Range | Used in |
|---|---|---|---|---|
| 26 / 27 | EXTRA BALL LIMIT / PERCENTAGE | 5 / 25 | 0-10 / 1-50 | game_flow, flynns_arcade |
| 31 | BALLS PER GAME | 3 | 1-10 | game_flow |
| 32 | TILT WARNINGS | 2 | 0-3 | game_flow |
| 38 | BALL SAVE TIME | 5 s | 0-16 | game_flow |
| 42 | COMPETITION MODE | 0 | 0-1 | flynns_arcade (500K weight 1100) |
| 65 | POP BUMPER DIFFICULTY | 1 | 0-2 | switches_and_shots |
| 66 | ZUSE FAST SCORING TIMER | 25 | 15-45 | zuse_fast_scoring |
| 67 | RECOGNIZER DIFFICULTY | 1 | 0-2 | recognizer_and_disc_battle |
| 68 / 69 | DISC MULTIBALL DISC / RECOGNIZER SHOTS | 6 / 3 | 4-8 / 1-5 | disc_multiball |
| 70 / 71 | DISC M.B. RESTART TIMER / AUTOFIRE TIMER | 10 / 10 | 4-20 / 0-20 | disc_multiball |
| 72-74 | TRON "SPINNERS" / "BUMPERS" / "DOUBLE SCORING" TIMER | 30 | 20-40 | tron_targets |
| 76, 81 | DISABLE RECOGNIZER 3-BANK MOTOR / RECOGNIZER MOTOR | 0 | 0-1 | recognizer_and_disc_battle |
| 77 | DISABLE DISC MOTOR | 0 | 0-1 | disc_multiball |
| 79 | DISABLE PLUNGE POST | 0 | 0-1 | skill_shots (B lit every serve) |
| 80 | DISABLE DROP TARGETS | 0 | 0-1 | tron_targets |
| 83 / 84 / 85 | 1ST / 2ND+ END OF LINE M.B. LETTERS, END OF LINE EXTRA BALL | 2 / 8 / 1 | | end_of_line_multiball (unit = whole DAFT+PUNK sets) |

The full list of 88 adjustments, with names, defaults and ranges, can be read from the ROM with
`tools/ghidra/romtables.py` (`adj(i)`).

## 6. Media: what to use from the asset package, and what to fix

The asset package (`tron/mpf_package`) has the right media, but some labels and gaps are wrong.
Before using it, read [work/asset_audit.md](work/asset_audit.md). In short:

- **Deff 105 is the Flynn's Arcade award reveal**, not a video mode intro. Build it from the chosen
  award: three cabinets, two decoy awards, and the chosen award blinking.
- **Duplicate YAML keys** in `switches.yaml` and `lights.yaml` silently drop 8 switches and 8 lamps
  (TRON, ZUSE, CLU). Lamp letter order is the reverse of switch order.
- **17 audio streams were never exported** (samples 0x09-0x14 and 0x16-0x19, and music 0x44d), so
  44 sound calls have no pool.
- **Two light-effect systems.** The package's `leff_NNN` are **ramp tube shows** (table 0x040e3c88).
  The ROM also has **172 lamp-matrix light effects** (table 0x040e23e4, `leff_start` 0x87ac), which
  70 display effects and many modes start. These were not exported.
  - In the specs, "leff N" always means the lamp-matrix table and "tube show N" the ramp tubes.
- **`mode_by_code_location` in `event_map.csv` is often wrong.** Use the mode files instead.
- **Deff 108 has 4 random clips** and deff 22 is empty.
- **Effect 104** is "FLYNN'S ARCADE IS LIT", not a game-start animation.

Lamps 1-80 are numbered as in `tron/io/lamps.csv` (66 are used). Lamp groups are 0-terminated lists
in table 0x040e3acc. Sound calls are in `tron/sound_calls.csv`. Each call picks one sample from its list.

## 7. Checking the rebuild against the real game

`tools/trace/` has `tron_ref`, which runs the real ROM from a scenario script and writes a
deterministic event trace. It also has `trace_compare.py`, which compares that trace with one from
your rebuild. [tools/trace/README.md](tools/trace/README.md) covers the build, the scenario language
and the trace format.

The suggested loop:
1. Take a feature's reference scenario from `traces/<feature>.txt`. The matching
   `traces/<feature>.jsonl` is the real ROM's output.
2. Drive your MPF/Godot build with the same switch sequence, and log `score`, `deff_start`, `sound`,
   `leff_start` and so on in the same JSON-lines format.
3. Run `trace_compare.py traces/<feature>.jsonl yours.jsonl`. It prints the first difference for
   each event kind.

Some scenarios use `poke` to jump straight into a late state, such as items already collected; the
scenario header says so. Your build needs an equivalent test hook.

## 8. Code and tools

- `tron/code/tron_game_decompiled_v2.c`: the cleaned decompile.
  - 166 OS functions have correct signatures, so call arguments are no longer lost.
  - About 570 game functions and 250 RAM variables are named after the specs (for example
    `dmb_jackpot`, `dmb_shot`).
  - Comments decode sound calls, messages, settings, audits, lamps and display effects.
  - The older `code/tron_game_decompiled.c` drops arguments and mislabels functions (for example
    `lamp_show_start` is really `score_add`). Do not use it.
- `work/os_api.json`: every OS function the rules call, with its meaning.
- `work/ram/*.tsv`: every RAM variable per feature (address, size, scope, meaning).
- `tools/ghidra/`: the scripts that rebuild the decompile (`run_ghidra.sh`).

## 9. Known limits of this documentation

- **Real hardware.** The ball model in the emulator is simple, so physical timing (ball save start,
  orbit detection with real balls, motors) was checked against code, not against a real machine.
- **Untested states.** A few late or rare states were read from code only. Each file's last section
  lists them, for example Sea of Simulation stages 4-8, match odds and slam tilt.
- **Multi-player.** Multi-player behaviour of per-player flags is inferred, not traced.
