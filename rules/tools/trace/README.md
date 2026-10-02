# Reference traces: run the real ROM, compare with the rebuild

`tron_ref` runs the real Tron Legacy LE 1.74 ROM in libpinmame from a scenario script and logs what
the game rules do. Run the same scenario on the MPF/Godot rebuild, log the same events, and
`trace_compare.py` tells you the first place they differ.

Runs are deterministic: the same scenario gives the same trace, byte for byte. That holds because
each run starts from factory settings (fresh NVRAM in a temp folder) and the emulator is paused at
fixed emulated times while the script acts.

## Build (Linux)

```sh
git clone --depth 1 https://github.com/vpinball/pinmame && cd pinmame
git apply /path/to/tron/rules/tools/trace/pinmame_arm_hook.patch     # adds a per-instruction ARM hook
cp cmake/libpinmame/CMakeLists.txt . && mkdir build && cd build
cmake -DPLATFORM=linux -DARCH=x64 -DBUILD_STATIC=OFF -DCMAKE_BUILD_TYPE=Release .. && make -j4
cd ../..
g++ -O2 -std=c++17 -Ipinmame/src/libpinmame tron_ref.cpp -Lpinmame/build -lpinmame -lpthread \
    -Wl,-rpath,$PWD/pinmame/build -o tron_ref
mkdir -p ~/.pinmame/roms && (cd /tmp && cp /path/to/trn_174h.bin . && zip ~/.pinmame/roms/trn_174h.zip trn_174h.bin)
```

Run: `PINMAME_NOJIT=1 ./tron_ref scenario.txt out.jsonl [watch.tsv]`. `PINMAME_NOJIT=1` is required
(the hook needs the interpreter). `TRON_ROMS=/dir` overrides the ROM folder. Speed is about real time.

## Scenario commands

One command per line; `#` starts a comment. The machine boots for 8 s (emulated) before line 1.

| Command | Effect |
|---|---|
| `start N` | 3 coins per player, then press Start N times |
| `wait S` | let S seconds of emulated time pass |
| `hit SW [ms]` | pulse switch SW closed for ms (default 60), then 100 ms settle. Disc opto (41) is pulsed open, as it is normally closed. Switch 11 (VUK) stays closed until coil 4 fires |
| `hold SW` / `release SW` | close / open a switch |
| `plunge` | the ball in the shooter lane leaves it |
| `autoplunge S` | auto-plunge S seconds after a ball reaches the shooter lane (default 1, 0 = never) |
| `drain [left\|right]` | one ball in play drains, optionally through the left/right outlane switch first |
| `adj ID VALUE` | set operator adjustment ID (see developer guide, settings table) |
| `poke HEXADDR VALUE [1\|4]` | write RAM (to jump straight into a state; mark such scenarios) |
| `button B [ms]` | press a cabinet button: `left`/`right` flipper, `tilt` (plumb bob), `tournament`, `start`; ms defaults to 100, `-1` holds, `0` releases |
| `mark TEXT` | write a marker event, useful to line up both traces |

Ball simulation: a 4-ball trough (switches 18-21), coil 1 ejects a ball to the shooter lane (switch 23),
coil 2 auto-launches it, coil 4 kicks the VUK, coil 6 moves the Recognizer 3-bank (switches 52/53),
coil 23 walks the Recognizer motor (switches 54-56). Balls only leave play through `drain`.

## Trace format (JSON lines)

Every line has `t` (emulated seconds since power-on) and `ev`. `caller` (ROM address of the calling
code) is for looking things up in `tron/code/tron_game_decompiled_v2.c`; the rebuild does not need it.

| ev | fields | meaning |
|---|---|---|
| `ready` | | boot finished, script starts (time 0 for comparisons) |
| `switch`, `switch_hold`, `switch_release` | `sw` | script input |
| `button` | `button`, `ms` | script input (flipper, tilt, ...) |
| `score` | `player`, `delta`, `total` | a player's score changed |
| `score_add` | `points`, `multiplier`, `player` | the rules awarded `points` (before the playfield multiplier) |
| `deff_start` / `deff_stop` | `id` | display effect (DMD animation) started / stopped |
| `sound` | `call`, `in_deff` | sound call played (`tron/sound_calls.csv`); `in_deff` = display effect that played it, 0 = rules code |
| `leff_start` / `leff_stop` | `id` | lamp-matrix light effect (table 0x040e23e4) |
| `tube_show_start` / `tube_show_stop` | `id` | ramp light-tube show (table 0x040e3c88, `tron/io/mpf/shows/leff_NNN.yaml`) |
| `audit` | `id`, `n` | audit counter bumped (feature counters, names in the developer guide) |
| `flag_set` / `flag_clear` | `flag` | game flag (mode state bits, see mode files) |
| `multiball_start` | `balls`, `save_ticks`, `grace_ticks` | multiball/ball-save request |
| `task_start` | `task`, `fn` | ROM task (timer or mode thread) started |
| `lamp` | `lamp`, `state` | lamp output changed; `lamp` 1-80 = `tron/io/lamps.csv` numbers (verified on lamp 65 START BUTTON), 101+ = other outputs |
| `coil` | `coil`, `on` | coil driver on/off |
| `var` | `name`, `value`, `old` | a watched RAM variable changed (watch.tsv: `name hexaddr size`) |
| `sim` | `what`, ... | ball simulation (eject, launch, drain) |
| `mark`, `script`, `end` | | script markers |

## Comparing

`trace_compare.py reference.jsonl candidate.jsonl [--tol 0.25] [--events score,deff_start,sound]`

The rebuild writes the same JSON lines for the events it implements, with `t` in seconds and a
`ready` event when its game can accept the scenario. Map MPF events to these kinds (for example a
show named after display effect 48 logs `{"ev":"deff_start","id":48}`). Reference scenarios and
traces for each feature are in `tron/rules/traces/`.
