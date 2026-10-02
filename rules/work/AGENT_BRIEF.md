# Brief for rule-extraction workers (Tron Legacy LE 1.74)

Goal: document game rules so precisely that an MPF/Godot developer can rebuild them without guessing.
You write specs, not MPF config or code.

## Inputs
- Cleaned decompile: /mnt/project-files/tron/code/tron_game_decompiled_v2.c (`// ==== <addr> <name>` headers;
  read its header comment). OS API names/signatures: /mnt/project-files/tron/rules/work/os_api.json
  (e.g. score_add(points) applies the playfield multiplier; task_create/recreate(id, fn, ...); task_sleep(ticks);
  leff_start = lamp-matrix effect (table 0x040e23e4); tube_show_start = ramp light tube show (table 0x040e3c88);
  lamp_on/off/flash, lampgroup_* (groups table 0x040e3acc); adj_get(id) = operator setting;
  game_flag_set/clear/test(flag); event_hook_add/event_post).
- ROM /mnt/project-files/trn_174h.bin. Address map: 0x0-0x35fff OS code; 0x36000-0xfffff RAM (initial values
  from ROM bytes); 0x01000000+ game code = file 0x40000+; 0x02100000 NVRAM (per-player arrays are indexed
  [player-1]); 0x04000000+ data = file offset (addr-0x04000000). Helper module with ROM table readers
  (messages, adjustments, audits, sound calls, lamps, deff/leff/tube tables):
  /mnt/project-files/tron/rules/tools/ghidra/romtables.py (`import sys; sys.path.insert(0, that dir)`).
- Data: /mnt/project-files/tron/sound_calls.csv, samples_index.csv, switch_names.json, io/lamps.csv,
  io/coils.csv, mpf_package/event_map.csv (made by another agent; known errors are listed in
  /mnt/project-files/tron/rules/work/asset_audit.md, read it before trusting the package).
- Disassembly: python3 `import capstone` (ARM mode) to check anything the decompile hides.
- 1 OS tick = 16.26 ms (measured); say ticks and ms.

## Emulator check (strongly encouraged for every number that matters)
`PINMAME_NOJIT=1 /home/claude/work/trace/tron_ref scenario.txt out.jsonl [watch.tsv]` runs the real ROM
deterministically from factory settings and writes JSON lines: score / score_add (points, multiplier, caller),
deff_start/stop, sound (call), leff_start/stop, tube_show_start/stop, audit, flag_set/clear, task_start,
multiball_start, coil, lamp (raw libpinmame lamp numbers), sim (ball simulation), var (watched RAM).
watch.tsv lines: `name hexaddr size(1|2|4)`, e.g. `dmb_jackpot 3af18 4`.
Scenario commands (one per line, # comments): `start N` (coins + start, N players), `wait S`,
`hit SW [ms]` (pulse a switch; 41 disc opto is handled as NC; 11 holds the VUK until its eject coil fires),
`hold SW`/`release SW`, `plunge` (shooter ball leaves; auto-plunge after 1 s by default, `autoplunge S`, 0 = off),
`drain [left|right]` (one ball drains, optionally through an outlane), `adj ID VALUE`, `poke HEXADDR VALUE [1|4]`
(set RAM to jump into a state; say so when you use it), `mark TEXT`.
The game boots for 8 s before the script starts. A run takes roughly real time; keep runs short (< 3 min emulated),
run at most one at a time, and use poke to reach late-game states instead of long play.
Ball sim: 4-ball trough (sw18-21), coil 1 ejects to shooter (sw23), coil 2 auto-launches.

## Output (only these paths; the shared folder is used by other sessions)
- /mnt/project-files/tron/rules/modes/<feature>.md following /mnt/project-files/tron/rules/work/TEMPLATE.md.
- /mnt/project-files/tron/rules/traces/<feature>.txt and .jsonl (reference scenario + its trace).
- /mnt/project-files/tron/rules/work/ram/<feature>.tsv: `0xADDR<TAB>name<TAB>size<TAB>scope<TAB>meaning` for every RAM/NVRAM variable you identified.
- /mnt/project-files/tron/rules/work/ram/<feature>_functions.tsv: `0xADDR<TAB>better_function_name` for functions you understood.
Do not modify any other file. Do not install packages except well-known ones with `python3 -m pip install`
if truly needed. Do not call any mcp__hearthbot__ tools. Do not write MPF yaml or code.
Final message: a short summary (what is covered, confidence, open questions, cross-feature facts other
workers need, e.g. shared counters or shot hook order).
