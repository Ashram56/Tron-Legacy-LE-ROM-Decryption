# rom_data/states: hardware facts, OS model and game-state scenarios (Tron Legacy LE 1.74, trn_174h)

Machine-readable first; each topic also has a short `.md`.

| File | Rows | What |
|---|---|---|
| `hardware_facts.json` (+ `.md`) | 23 facts | RGB ramp tubes (left/right evidence), GI relay, dedicated switch summary |
| `dedicated_switches.csv` | 34 | D1-D32 from table 0x040f4074, plus matrix 15/16 |
| `os_model.json` (+ `.md`) | 105 events, 137 task ids, 85 rules, 56 flags | Tick, RNG, events, tasks, switch dispatch, deff scheduler, rule lists, game flags |
| `multiplayer.json` (+ `.md`) | facts, 294 state-scope rows, 3 rotations | 2/3/4-player rules |
| `tilt.json` (+ `.md`) | facts + event sequence | Tilt warnings, tilt, slam |
| `sea_of_simulation_late.json` (+ `.md`) | facts + observed SOS variables | SOS stages 4-8 and completion |
| `match.json` (+ `.md`) | facts + 3 runs | Match RNG, formula, award, media |
| `static_calls.json` | 26 APIs | Every call site of the task/event/GI/RNG/deff/leff APIs with constant r0-r3 |
| `scenarios.json` | 11 | One row per scenario: purpose, pokes/adjustments, emulated seconds, event counts |
| `traces/*.txt` / `*.jsonl` | 11 scenarios | Scenario scripts and their JSON-lines traces; `states_watch.tsv` and `sos_watch.tsv` are the RAM watch lists |

## Fields
**Fact rows** (all `*.json` `facts` lists):

| Field | Meaning |
|---|---|
| `id` | Stable key |
| `fact` | One-sentence statement |
| `value` | Structured value, or null |
| `address` | ROM/RAM addresses (hex; game code 0x01xxxxxx, data 0x04xxxxxx, OS < 0x100000) |
| `tag` | `observed` (seen in the emulator), `code` (read from code/tables) or `inferred` (reasoning) |
| `evidence` | Trace file and time, or the source |

**`dedicated_switches.csv`:**

| Column | Meaning |
|---|---|
| `dedicated` | Dn |
| `rom_switch_number` | 128 + n, as passed to handlers |
| `pinmame_switch` | The libpinmame number (sw2m = n + 7; column 0 = D17-D24 is overridden by the keyboard, so use the keys) |
| `pinmame_input` | Key / input-port bit |
| `name` | ROM name string |
| `handler`, `handler_arg` | Record words 0 and 1 |
| `function` | What the handler does |
| `descriptor_flags_0x10` | Record word 4 |
| `word_0x18` | Record word 6 |
| `id_byte` | Byte 2 of word 6 |
| `address` | Record address |
| `tag` | Source tag (see above) |

**`static_calls.json`:** per API, a list of `{site, func, func_name, kind, r0..r3 (constants found by a forward register
scan of the 24 instructions before the BL, null if not constant), bl}`.

**Trace rows** (`traces/*.jsonl`): `t` = emulated seconds since power-on, `ev` = kind. On top of tron_ref's events
(`switch`, `deff_start`, `leff_start`, `sound`, `score`, `var`, `flag_set`, `audit`, `task_start`, ...), states_ref adds:

| Event | Fields / meaning |
|---|---|
| `gi_write` | `on`, `shadow` = value before the write, caller |
| `gi_req` | gi_off/gi_on request: `on`, `task`, `owner` |
| `gi_out` | PinMAME GI output: `state` 9 = on, 0 = off |
| `rng` | `fn` random/percent/raw, `seed` before the call, `next` = the result, caller |
| `event` | event_post id (decimal), arg, caller = return address |
| `event_hook` / `rule` / `task` | RAM dumps |
| `tick` | Every 62 passes, with the hardware counter `hw` |
| `call` | `pretracepc` hits: r0-r3, task, caller |
| `reset_request` and `sim watchdog_reset` | Slam reset |
| `script pokeat` | A one-shot RAM write at a PC |

## Method
1. **Static data.** `rom_data/tools/states_static.py` (imports `rom.py`) reads tables and does a BL scan with a small
   forward register tracker. It writes `dedicated_switches.csv` and `static_calls.json`.
2. **Scenarios.** `rom_data/tools/states_ref.cpp` is tron_ref.cpp plus the additions below. Its output is
   byte-identical to tron_ref when no new command is used (checked on `game_flow_tilt.txt`).
   - Coin-door buttons (`button back|minus|plus|select|slam|coindoor|coin`).
   - `dsw`, `trace gi|rng|events|ticks`, `pretrace` (active from power-on), `pretracepc`, `pokeat`.
   - `dump_events`, `dump_rules`, `dump_tasks`.
   - Watchdog emulation (PinmameReset when the ROM reaches 0x10ce8).

   Build:
   ```
   g++ -O2 -std=c++17 -I/home/claude/pinmame/src/libpinmame rom_data/tools/states_ref.cpp \
       -L/home/claude/pinmame/build -lpinmame -lpthread -Wl,-rpath,/home/claude/pinmame/build -o states_ref
   ```
   Run from `traces/`: `PINMAME_NOJIT=1 states_ref X.txt X.jsonl states_watch.tsv`. Every run starts from fresh NVRAM
   with factory settings; pokes and `adj` lines are listed in each scenario header and in `scenarios.json`.
3. **Build.** `rom_data/tools/states_build.py` re-asserts the quoted ROM facts (strings, constructor arguments,
   instructions, table counts) and re-reads the traces, then writes every JSON here. It takes about 2 s.
4. **Counts checked against the ROM's table of tables** (0x36c00-0x36d60; list in `os_model.json`):
   - dedicated switches 32 (0x36dd4);
   - matrix switches 65 (0x36dc8);
   - deffs 146 (0x36c54);
   - tube shows 106;
   - event hooks 131 in RAM = 131 static sites;
   - rule lists 16/32/18 in RAM = the static init sites.

## Open (details in each .md)
- **Tube left/right.** The ROM says 0x10 = left; PinMAME's comment says right. A real-machine test is described in
  `hardware_facts.md`.
- **High-score deff names.** deffs 31/32 in `deffs.json` vs observed order: initials were entered while deff 32 ran.
- **Forced-loss match number.** The stepped number was not logged.
- **Event meanings.** Many event ids are known only by their posting site.
- **Task dump.** The `dump_tasks` layout is unverified.

## Contradictions with other repo docs
- **PinMAME sam.c (external):**
  - D22 is labelled Plus and D23 Minus. The ROM, the input port and the emulator all say D22 = MINUS, D23 = PLUS.
  - CSTB is labelled the right ramp. Three ROM sources say strobe 0x10 is the left ramp.
- **`io/README.md`:** "0xbe (bit 6 low, GI on)". GI-on is bit 0 = 0; bit 6 is the aux latch pulse.
- **`io/io_registers.csv` vs Vincent:** the CSV calls bit 4 CSTB (PinMAME naming); Vincent calls it ESTB (J3 pin 12).
- **`rules/modes/sea_of_simulation.md`:**
  - Stage 6 needs all six shots through the chain, not three.
  - Completion shows deff 126 TOTAL (sound 0x115), not deff 125 / speech 0x113.
- **`rules/developer_guide.md`:** per-player game flags were "inferred, not tested". Now `code` (0x6700/0x6744, descriptor
  0x040e1f6c bit 0) and seen in 2-4 player play. Not every flag is per player: flags with class bit 0 are global.
- **Decompile name `lamp_rule_init` (0x1982c):** it builds deff rules (list 2, vtable 0x39f60, id = deff number).
