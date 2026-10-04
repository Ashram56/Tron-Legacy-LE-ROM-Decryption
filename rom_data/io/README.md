# rom_data/io: coils, lamp groups and lamp-matrix effects (Tron LE 1.74, trn_174h)

These files are machine-readable data read from the ROM, for rebuilding the game in MPF. Every row
carries the ROM address it came from and a `tag`:
- `code` means the value was read from a table or from code.
- `observed` means it was measured in the emulator.
- `inferred` means it is reasoning.

Where the emulator and the code disagree, both are given. All tables were checked against the ROM's
table of tables (RAM `0x36c00-0x36d60`, `{ptr, count, size}`):

| Table | RAM entry | ROM address | Count | Record size |
|---|---|---|---|---|
| Coil descriptors | `0x36c48` | `0x040e0f60` | 36 | 28 |
| Flipper rules | `0x36c9c` | `0x040e204c` | 3 | 12 |
| Coil groups | `0x36ca8` | `0x040e20c4` | 27 | 4 |
| Counter queues | `0x36cb4` | `0x040e2130` | 3 | 20 |
| Leffs | `0x36cf0` | `0x040e23e4` | 172 | 12 |
| Lamp records | `0x36cfc` | `0x040e338c` | 81 | 12 |
| Lamp groups | `0x36d20` | `0x040e3acc` | 109 | 4 |
| Ball devices | `0x36d44` | `0x040e41f4` | 4 | 36 |

To regenerate (the ROM is read from `/mnt/project-files/trn_174h.bin` by `tools/rom.py`):
```
cd rom_data/tools
PYTHONPATH=. python3 hw_calls.py && PYTHONPATH=. python3 hw_coils.py   # coil_calls.csv, coils.csv, coil_rules.json
PYTHONPATH=. python3 hw_lamps.py                                       # lamp_groups.json
PYTHONPATH=. python3 hw_leffs.py                                       # leff_table.csv, code_leffs.*, lamp_rules.csv
# the emulator measurements (coil_observed.json):
g++ -O2 -std=c++17 -I/home/claude/pinmame/src/libpinmame hw_trace.cpp -L/home/claude/pinmame/build -lpinmame \
    -lpthread -Wl,-rpath,/home/claude/pinmame/build -o hw_trace
PINMAME_NOJIT=1 ./hw_trace hw_scenarios/hw_s1_game.txt s1.jsonl     # also s2, s3; then hw_pulses.py
```

**Time units.** The coil driver counts in ms: the slots are serviced every 4th IO interrupt, so the
nominal tick is 1 ms; the emulator measured 1.00 to 1.02 ms. Lamp effects count in OS ticks: one tick is
about 16.26 ms, and `task_sleep(n)` sleeps n ticks.

## Coils

### coils.csv: one row per driver 1-40

Drivers 36-40 have no descriptor (`kind` = undefined).

| column | meaning |
|---|---|
| coil, name | Coil number and its coil-test name (from the name record at descriptor +0xc). |
| register, reg_address, bit | Output register and bit, the same as `io/coils.csv`. |
| desc_addr | Address of this coil's descriptor, `0x040e0f60 + 28*coil`. |
| flags_hex, flags_decoded, f_0x... | Descriptor +0 (u32), with one 0/1 column per bit that is set anywhere. Bit meanings are below. |
| test_pulse_ms | Descriptor +0x10: the coil-test pulse. The coil test calls `0x2cb0(coil, ms, sync=1)`. |
| test_fn, test_fn_name | Descriptor +0x4: a custom coil-test function (coils 5 and 6). |
| ballsearch_ms, ballsearch_fn | Descriptor +0x12 / +0x8: the pulse length and function used by ball search, read by `FUN_000030a8`. |
| devices_on_driver | Descriptor +0x19: the count shown as "(X%d)" in the coil test. |
| wire_color_1/2, *_msg | Descriptor +0x14 / +0x16: message ids and their text. |
| kind, kind_note, kind_tag | Class: flipper, autofire, pulse, pulse_hold, flasher, motor, relay, aux or undefined, plus the evidence for it. |
| auto_rules | The hardware rule that fires the coil (flipper, bumper, sling, counter queue, ball device, ticket). |
| game_calls, game_call_sites | ms values that game code uses for this coil (from `coil_calls.csv`). |
| observed_first_on_ms, observed_pwm_on_period_ms, observed_runs, observed_tag | Emulator measurements from `coil_observed.json`. |
| mpf_default_pulse_ms, mpf_default_hold_power, mpf_pulse_power, mpf_recycle_ms, mpf_note, mpf_evidence, mpf_tag | Recommended MPF values. These are inferred from the code and observed values listed in `mpf_evidence`. |

### Descriptor flag bits

| bit | meaning | reader | tag |
|---|---|---|---|
| 0x2 | Builds the mask `0x3b984` (`FUN_000041f0` at 0x4234). The IO interrupt `0x12070` writes shadow & mask while `(RAM 0x3727c & 3) != 3`, the "50V / 20V DISABLED" state, so only these outputs drive then. | code | code |
| 0x4 | Flasher. The flash test lists coils with `(flags & 0x1004) == 4` (`FUN_01040e6c`). | code | code |
| 0x400 | Skipped by the cycling coil test task `FUN_0103f47c`. | code | code |
| 0x800 | Hidden from the coil test (`FUN_0103eb2c`, `0103ef70`, `0103efe0`). | code | code |
| 0x8, 0x10, 0x40, 0x80, 0x2000, 0x8000 | Excluded from the direct ball-search pulse: mask `0xa0dc` in `FUN_000030a8`. | code | code |
| 0x1, 0x100, 0x4000, 0x10000 | No reader found by a static scan or by the emulator table-read trace. Their names come from which coils carry them. | none | inferred |

### coil_calls.csv: every call site of the coil API (OS and game)

Each row is one call site, with its constant arguments resolved by constant propagation over the calling
function (`hw_common.resolve_call_args`).

| column | meaning |
|---|---|
| call_site, kind | Address of the call; `bl` or `b` (tail call). |
| caller_fn, caller_name | The calling function. |
| api, api_addr | The API called. Signatures are below. |
| coil / group, group_coils | The coil, or the coil group and its coils. |
| group_source | Set when a leff task gets its coil group from the leff table +8 (`leff_current_info` 0x8d90). |
| leff_ids | The leffs whose function makes this call. |
| ms, pattern, pattern_bits, on_ms, off_ms | Drive arguments. |
| strength, min_setting | Shaker arguments. |
| start_fn, end_fn, sync, waits | Callbacks, zero-cross sync, and whether the API waits for the pulse to end. |
| unresolved_args | Arguments that are variables (blank values). |
| decompile | The call as written in `code/tron_game_decompiled_v2.c`. |

API signatures:
- `coil_pulse 0x6970(coil, ms)` runs mode 3 (on for ms). It goes through the 6-slot limiter `0x3c198`.
- `coil_pulse_fn 0x69c0(coil, ms, pattern)` runs mode 1: the 32-bit pattern is played LSB first, 1 bit per ms.
- `0x2bc8` / `0x2cb0`(+wait) `(coil, ms, start_fn, end_fn, [sp]arg, [sp+4]sync)`.
- `0x2d18` / `0x2de0` `(coil, ms, pattern, bits, start, end, arg, sync)`.
- `0x2e5c` / `0x2f34` `(coil, ms, on_ms, off_ms, ...)` runs mode 2 (PWM).
- `0x2ac0` / `0x2b60`: a serialised queue.
- `coil_on 0x3034`, `coil_off 0x2fbc`, `coil_pulse_stop 0x6a20`.
- `coilgroup_pulse 0x6b24`, `coilgroup_pulse_fn 0x6b94`, `coilgroup_stop 0x6c0c`.
- `shaker_run 0x10289b8(strength, min_setting)` maps to `0x2bc8(8, table 0x040d3998[strength])`.

`sync=1` waits for the next zero-cross edge: input bit 2 of `*(0x37350)`, 60/s. Driver slots are at
`0x3b98c + (n-1)*0x28`.

### coil_rules.json: the automatic rules, decoded

- `flippers` (`0x040e204c`): switch, alt switch, coil, EOS, pulse, EOS cut, hold on/off and debounce.
  - Pulse 40 ms; hold 1 ms on / 11 ms off.
  - Upper flipper 12 has no EOS. Its button is 0x8d, or 0x89 when 0x8d is disabled.
- `bumpers` (`0x040f0a5c` records 1-3): 32 ms, recycle 16.
- `slingshots` (`0x040f0a8c` records 1-2): 32 ms, recycle 192.
- `counter_queues` (`0x040e2130`): knocker 24 at 80 ms; meter 34 at 100 ms.
- `ticket_device` (`0x040f455c`).
- `ball_devices` (`0x040e41f4`): switches and kick coil/ms.
- `coil_groups` (`0x040e20c4`, 0-terminated coil lists).
- `motors`: disc 5/30/22, recognizer bank 6, recognizer 23, post 7, drop bank 3.
- `ball_search`, `coil_test`, `zero_cross_sync`.
- Each object names its table, builder and runtime RAM, and carries a tag.

### coil_observed.json

There are 188 driver bursts from three scenarios (`tools/hw_scenarios/`). `hw_trace.cpp` sampled the
driver shadow `0x3b97c` at every IO interrupt, about 0.25 ms resolution. Each burst records the coil,
the time, `first_on_ms`, the pulse count, the nearest API call and the scenario. `runtime_dumps` holds
the flipper, bumper and sling runtime objects read from RAM.

## Lamp groups

### lamp_groups.json

- **`groups[g]`** describes one group, g = 0..108, read from table `0x040e3acc`. Each list is 0-terminated lamp numbers; group 0 is empty, and every group API accepts 1..0x6c only. Fields:
  - `list_addr`, `count`, `lamps`.
  - `lamp_names`, from `io/lamps.csv`.
  - `mpf_lights`, the names in `mpf_package/config/lights.yaml`.
  - `name` with `name_tag: inferred`, a name derived from the members.
  - `same_lamps_as` / `same_order_as`. Many groups are duplicates. Order matters for the fill, drain and rotate APIs.
  - `lights_yaml_rom_group`: compares the lamps tagged `rom_group_N` in lights.yaml with the ROM list.
- **`references`** lists every constant use of the group:
  - a call to a group API, with the r0 constant resolved;
  - a ROM table of group ids (`rom_table`, with the table layout);
  - the leff table field +6 (`leff_table_lamp_group`);
  - a group passed to the parametric group leffs 40/103/122/143 at task+0x30 (`leff_start param`).
- **`group_api`** gives the name and meaning of every group function. They are all at `0x7d9c-0xa10c`, and they were found as the only code that reads `0x040e3acc`.
- **`unresolved_references`** lists API calls whose group is a variable.

## Lamp-matrix effects (leffs)

### leff_table.csv: one row per leff 1-171, plus the unused record 0

| column | meaning |
|---|---|
| entry_addr, fn, fn_name, same_fn_as | Record address, function, and other leffs that share the function. |
| flags_hex, flags_decoded, task_flags_hex | Record +4 and the task flags `leff_start` gives (see below). |
| lamp_group, lamp_group_name | Record +6. `leff_start` claims this group on the shared leff layer: it calls `lampgroup_off` on image `0x3c224` and `lampgroup_bit_set` on mask `0x3c238`. Overlapping groups conflict, and the conflict is resolved by priority. |
| coil_group, coil_group_coils | Record +8. The leff gets it from `leff_current_info` 0x8d90; `leff_stop` calls `coilgroup_stop` on it. |
| priority | Record +0xa. |
| class | `exported_show`: deterministic, so the captured `mpf_package/lamp_effects.csv` show is usable. `empty_stub`: draws nothing. `code_drawn`: see code_kind. |
| code_kind | `fixed`; `stub` (`mov pc, lr`); `holder` (runs, draws nothing); `timer_only`; `parametric` (lamp or group at task+0x30); `state` (draws from game RAM); `conditional` (fixed pattern that runs only while a condition holds); `gi_only`; `random`; `service` (lamp test). |
| class_note | One-line behaviour. |
| package_show, package_kind, package_length_ms, package_loops | The row of `mpf_package/lamp_effects.csv`, for comparison. |
| gi | GI calls: claim `0xc9dc` / `0xc988`, off `0xcaf8` (sets bit 0 of `0x3c758`), on `0xcb24`. |
| lamps_const, groups_const, coils_const, sleeps | Constant arguments found in the leff function, its direct helpers and its spawned tasks. |
| reads_task_param | 1 if any of those functions reads task+0x30. |
| start_param_values | Values that `leff_start` callers store at task+0x30. |
| leff_start_sites | Every `leff_start(id)` call site, with its param. Five sites pass a variable id. |
| leff_rule_sites | `leff_rule_init` registrations that start the leff. |

Flags (from `leff_start` 0x87ac):
- **0x2:** an equal-priority leff may replace this one (code).
- **0x4:** task flags 0 (code).
- **Otherwise:** task flag 0x100 if bit 0x1 is set, else 0x2000 (code). `end_of_ball` (0x20764) waits up to `gf_eob_mode_wait` ticks while any 0x2000 task runs (`FUN_0000c044(0x2000)`). What 0x100 means is inferred: a background effect that the end of ball does not wait for.

Note: `task_spawn_child` copies task+0x30..+0x47, the leff id and the priority into the child, so a
child reads the same parameter.

### code_leffs.json and code_leffs.md

There is one entry per leff whose class is `code_drawn`, plus leffs 1 and 133. Those two are exported shows, but they read the button-lamp RAM. Fields:
- `fn`, `kind`, `priority`, `flags_hex`, and the lamp group and coil group with their members.
- `what`, plus `param` (meaning of task+0x30) and `param_values_at_leff_start`.
- `lamps_touched` / `groups_touched` / `coils_touched` / `coil_groups_touched`: constants only.
- `rom_tables`.
- `ram_read`: each RAM address with its name and meaning from `rules/work/ram/*.tsv` or from this script.
- `sleeps_ticks`, `gi`, `functions` (the call tree used), `exit`.
- `pseudo`: short pseudo-code, hand-written from the decompile or disassembly of the functions listed.
- `started_by`, `leff_rules`, `unresolved_args`.

The `.md` file is the same data, written for reading.

Leffs the downstream build rebuilt by hand:
- 13, 14, 45, 76, 78, 94, 99, 136, 157 and 159 are state-drawn.
- 132 is conditional.
- 47 is a fixed loop: it fills and drains group 52 in both directions, 8 ticks per step. It is exportable.

### lamp_rules.csv: every rule registration (48 call sites)

| column | meaning |
|---|---|
| site, caller_fn, caller_name | Where the rule is registered. |
| kind | `leff_rule` (`leff_rule_init` 0x19740, list 3) or `deff_rule` (`lamp_rule_init` 0x1982c, list 2). |
| object | RAM address of the rule object. |
| list | Rule list 0-5 at `0x3e560`. |
| cond_fn, cond_name, cond_tests | The condition and a one-line decompile of what it tests. |
| leff | leff_rule only. When cond is true and the leff is not running, `leff_start`; when false, `leff_stop` (method `0x197ac`). |
| deff, sound, modify_fn, modify_fn_body | deff_rule only. When cond is true, start the deff if it is not running and play the sound if it is not playing. `modify_fn(&deff, &sound)` may change both first. The first true rule stops the list walk (method `0x198a8`). |
| mode_mask | Object +4. The rule is evaluated when `gf_state == 0` or `gf_state & mask`. |
| byte6 | Object +6. |
| priority_byte7 | Object +7, the sort key of the list; higher runs first. |

The lists are re-evaluated when `rules_refresh_request` 0x19648 sets `0x37418`.

## What is still open

- **Flag bits 0x1, 0x100, 0x4000 and 0x10000** have no reader found, so their names are inferred.
- **Flipper EOS polarity.** libpinmame mirrors the EOS switch to the button, so the EOS-cut path (8 ms) was not exercised. Its timing is from code only.
- **Upper flipper button 0x8d** is not mapped in libpinmame, so coil 12 was not measured.
- **Ball-device fields** +0x10/+0x14/+0x18 and byte +0x20 are not decoded. They are probably timeouts or retry counts.
- **87 coil-call sites have variable arguments** (blank in `coil_calls.csv`), mostly `coil_pulse_fn` patterns that come from tables. The leff ones are described in `code_leffs.json`.
- **Lamp groups 1-4, 32, 49, 53, 55, 58-61 and 107 have no constant reference.** They are probably used through variables: 84 unresolved group-API calls.
- **Group names are inferred** from the members.
- **The direction of `lampgroup_rotate_b` 0x9588 is inferred.**
- **Leffs were not run in the emulator for this work.** The behaviour is from code; the captured shows in `mpf_package` are the observed side.
- **Leff 101's child** inherits task+0x30. No `leff_start(101)` site stores a constant, so its lamp is a variable.
- **RAM `0x3908c`** (a lamp left out of the attract and tilt layers) is 0 at power-up; its run-time writer was not found.
- **Leff flag 0x1 / task flag 0x100**: the meaning of the task flag is inferred.

## Corrections to other docs

- `io/coils.csv` `desc_flags_hex` is wrong in two ways. Row n shows the flags of descriptor n+1, and it shows the raw bytes in file order instead of the little-endian u32. For example, row 11 shows `08000100`; that is coil 12's flipper flags 0x00010008, while coil 11 is 0x00012000. Use `coils.csv` here.
- **Shaker.** `mpf_package/config/shows/shaker_strength_{1,2,3}.yaml` and the silo note `tron-lampfx-shaker-service.md` give 75/265/1100 ms. Table `0x040d3998` gives 200/384/1024 ms (code), and the emulator measured 203/390/1040 ms by sampling the shadow at the IO interrupt. The earlier figures came from 5 ms polling in `tron_ref`.
- **`rules/work/os_api.json` `lamp_rule_init`** says "likely lamp-state rule" (low confidence). It is a deff/sound rule: method `0x198a8` calls `deff_start` and `snd_play`.
- **Table `0x040f0a5c`** holds the bumper rules (records 1-3), not the flippers. The flipper rules are at `0x040e204c`.
- **`mpf_package/lamp_effects.csv` kinds.** Leffs 15, 53 and 59 are listed as "state display", but they draw nothing. Leff 154 is listed as "no-op", but it blinks group 63 while task 0xca runs. Leff 129 ("no-op") is a 2-tick GI blink, and leff 11 is a 15-tick GI off.
