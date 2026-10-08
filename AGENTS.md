# AGENTS.md: reverse engineering a Stern SAM pinball ROM

This file is for an agent (or a person) who has to take a **Stern SAM** game ROM apart: extract the
sounds, DMD animations and light shows, map switches to callouts, recover the full rules, and package it
all for a rebuild in MPF (Mission Pinball Framework) or another engine.

It condenses what was learned doing this for **Tron Legacy Limited Edition v1.74** (PinMAME set
`trn_174h`), including the mistakes that were made and how they were caught. Every Tron address is
given as a **worked example**: on another SAM ROM the address will differ, so each section says how to
find the same thing again. Anything marked *(Tron only, untested elsewhere)* is a guess about other
games that nobody has checked yet.

**A second game confirms the method.** **Transformers Pro 1.80** (PinMAME set `tf_180`) was taken apart with
this file. Where it showed something general, its value is given next to Tron's as "TF" (its result is
[Transformers-MPF](https://github.com/Ashram56/Transformers-MPF) `rom/`: `rom/README.md`, `rom/tools/trace/README.md`). A Tron fact that TF also showed is no longer
"Tron only".

The rest of this repository is the Tron result. Read it as a reference implementation:
[README.md](README.md) (layout), [rules/developer_guide.md](rules/developer_guide.md) (rules spec
conventions), [mpf_package/README.md](mpf_package/README.md) (asset package),
[io/README.md](io/README.md) (IO and RGB tubes), [docs/agent_notes/](docs/agent_notes/) (raw notes),
[rules/work/asset_audit.md](rules/work/asset_audit.md) (an audit that found real extraction errors),
[io/bus/README.md](io/bus/README.md) and [io/bus/CPU_BOARD_IO.md](io/bus/CPU_BOARD_IO.md) (every interface
the CPU board drives, with timing), [docs/PRO_VS_LE.md](docs/PRO_VS_LE.md) and
[rom_data/pro/](rom_data/pro/README.md) (a second model of the same game, ported from the first).

**Where this agent fits.** This is agent A of a pipeline whose master plan lives in the game repo:
[Tron-Legacy-MPF `docs/agents/README.md`](https://github.com/Ashram56/Tron-Legacy-MPF/blob/main/docs/agents/README.md).
Its output feeds the strict MPF recreation (agent C), the VPX extraction and bridge agents (B, D) and the
optional improvements (E). **What the owner provides for this agent:** the ROM image of every model to
cover (the PinMAME set zip, e.g. `trn_174h.zip`; never committed), and optionally the operator manual,
schematics and logic analyzer captures (say which ROM the machine ran). A Visual Pinball X table of the game
is not needed here; it goes to agent B.

**Keep this file current.** It is the project's memory for the next ROM. Whenever a thread learns
something that would change how another SAM ROM is taken apart (a new method, a hardware fact, a
mistake and its fix, a correction to this file), fold it in here in the same session, in the generic
section it belongs to, with the Tron value as the worked example. Last updated 2026-10-08 (Transformers
Pro 1.80 lessons: OS table registry, carried names, capture batches, hook patches, text helpers, image ids,
sound, leffs, task struct; before that: pipeline placement, owner inputs, per-frame text, PinMAME
numbering, coin door and service suspend).

---

## 0. Ground rules that saved (or would have saved) the most time

1. **Use the ROM's own fields to check your output.** The sound export was wrong for a day (wrong
   rate, truncated clips) until someone compared each WAV's length with the length the ROM stores for
   that sample. Any time the ROM stores a size, count, duration or checksum, compare against it.
2. **Label every fact by source**: **observed** (seen in the emulator), **code** (read from the
   decompile or a table), **inferred** (reasoning). Downstream agents build on these labels; an
   inferred fact presented as code costs someone a debugging session.
3. **"Where the code sits" is a guess, not a proof.** Columns like `mode_by_code_location` were often
   wrong (the audit found attract and match effects attributed to unrelated modes). Prove a link with a
   call chain (switch handler → ... → `deff_start(id)`) or an emulator trace.
4. **Name a function from what it does, not from its neighbours.** The first decompile called
   `score_add` "`lamp_show_start`". Every later reader was misled until the rules thread re-derived it.
5. **Before calling code dead, search the whole image.** A function is dead only if there is no `BL`
   to it in any code block *and* its address (as a little-endian u32) appears nowhere in the full ROM
   file (pointer tables live in the data banks). Tron 1.74 has real dead code (a whole video mode).
6. **Check table entries for stubs.** Deff 22 pointed at a function whose only instruction was
   `mov pc, lr`. It was reported as "an uncaptured tilt warning" until someone disassembled it.
7. **Every path a README mentions must exist in the deliverable.** A `parts/` folder was written to a
   scratch staging directory and never copied in, so the README described files nobody had. Run a
   reference checker over READMEs, YAML and file lists before shipping.
8. **Load every YAML with a duplicate-key check.** PyYAML silently keeps the last duplicate key: 8
   switches and 8 lamps vanished (`s_tron` x4, `l_zuse` x4 ...). Use a loader that raises on
   duplicates, over every file.
9. **Count what you exported against what the directory says exists.** 17 sound streams were missed
   because they used a header variant the decoder skipped. A simple "directory entries vs files
   written" count would have caught it, as would "every sound call has a pool".
10. **Ship updates as small zips of changed files only**, with a file list and a REMOVED list, and
    state exactly which folder to unzip in (one update zip said "inside `mpf_package/`" while its paths
    started with `mpf_package/`). The project owner asked for this explicitly; full rebuilds of a
    150 MB zip are not wanted.
11. **Emulator runs are slow; plan them.** With the per-instruction hook a run is about real time.
    Keep scenarios short, use RAM pokes to jump to late states (and say so), run at most a few in
    parallel, and filter logs line by line (loading a 25-minute play log whole ran out of memory).
12. **Machine-readable first.** The downstream MPF build read prose specs once but read tables on
    every build. Every fact a rebuild needs (fonts, text layout, coil timings, deff screens) belongs in a
    CSV or JSON with its ROM address and an observed/code/inferred tag. See section 14 for the list.
13. **Close the loop on audits.** Once a finding is fixed, mark it RESOLVED where it was reported. Stale
    audit notes made the next agent work around defects that were already gone.
14. **Hardware data is a required deliverable, not a side note.** A rebuild that drives real coils
    needs the ROM's own drive parameters for every output, in game play, measured at 1 ms. On Tron they
    were left out at first, the MPF build had to guess them, and the shaker shipped with wrong times.
    Section 8.1 is the procedure.
15. **Hardware labels disagree between sources.** PinMAME, the ROM's own console strings and the
    owner's schematic analysis gave three different left/right and strobe-letter namings for the RGB
    tubes. Report all of them and flag "check on the real machine"; do not silently pick one.
16. **The decompile is for reading, not for rebuilding.** Ghidra pseudo-C has no real types or struct
    layouts, many unnamed functions, and data, graphics and sound referenced only by address. It will
    not compile back into a working ROM. If the owner wants to change game behaviour on the original
    hardware, the route is binary patching (section 16). Say so plainly when asked; nobody has tried to
    compile it, so label that answer inferred.
17. **Hardware facts need more tags.** For bus and board work, tag every number **code** (read from the
    ROM, with address), **emulator** (patched libpinmame), **hardware** (owner's logic analyzer
    capture), **scope** (cannot come from ROM or captures; needs an oscilloscope on the machine) or
    **external** (PinMAME source notes, public pinouts). A board designer needs to know which numbers
    still have to be measured.
18. **Verify register addresses from runtime values.** Early IO notes on Tron had the switch strobe and
    the flash bank-select addresses wrong, and gave the switch matrix 8 columns instead of 4. Read the
    IO pointer block (section 8) in the emulator after boot and confirm each address against the code
    that uses it before publishing a register map.
19. **Model and region checks: document, don't defeat.** ROMs carry hardware/software mismatch and
    country-lock checks. Note that they exist and where; do not analyse how to bypass them.
20. **Find the OS table registry first.** The OS keeps a table of tables: `(address, count, record
    size)` triples covering adjustments, audits, coils, deffs, leffs, lamps, lamp groups, messages,
    sound calls, switches and more. Finding it gives every table at once, and per-table searches
    (section 5.2) become checks rather than hunts. Look for a run of triples whose addresses fall in
    `0x04000000-0x04800000`. TF: file `0x30b00-0x30d10`, 43 tables (code).
21. **Never trust names carried over from another game's decompile.** Seeding a new ROM's Ghidra
    project with the last game's names puts them on functions at the same address with a different
    meaning (TF got `deff_093_zuse...`). Port names only by signature match (section 15, step 2),
    rename deff and leff functions from this ROM's own tables (TF: `tools/event_map.py`), and treat
    any other carried name as unreliable until checked.
22. **Re-capture in small batches and diff against the last run before replacing it.** A full
    re-capture of TF's display effects (33 effects per emulator run) came back empty for 25 effects
    that had rendered before; re-running them 4 per run recovered 21. Compare page and frame counts per
    effect with the previous capture and merge per effect; never replace the whole folder.

---

## 1. Identify the ROM

- Hash the file (SHA1) and match it against PinMAME's `src/wpc/sams.c` / `sam.c` game list to get the
  set name, game and code version. Tron: 33,110,916 bytes, SHA1
  `40e36764af332175f653e8ddc2a8bb77891c1230` = `trn_174h`, Tron Legacy LE 1.74.
- Check the PinMAME driver for a per-game flag (Tron has `SAM_GAME_TRON`, "TriColor Assembly strobed
  on C and D outputs"). Such flags point at game-specific hardware you will need to decode.
- Run an entropy scan in 64 KB windows. Tron: code, strings, tables and DMD graphics up to about
  0x840000, then high-entropy compressed audio up to about 0x1F80000, then a low-entropy tail.
- Find out which **models** of the game exist (Pro, Premium, LE). On SAM each model is a **separate
  image**; the LE ROM had no Pro flag, no "PRO" string and no code path for Pro hardware. The game
  info block names the model (Tron LE `0x36f20`: "TRON L.E.", "TRN", "C2"; Pro: "TRON", "B9"). See
  section 15.
- Match vendor downloads to PinMAME sets by SHA1, not by name. Stern's two Tron Pro 1.74 downloads
  (TRNenglish00 / 02) hold byte-identical binaries (only a README line naming CPU board 520-5246-02
  differs); that image is PinMAME `trn_17402`, while PinMAME's `trn_174` is a different Pro 1.74.

## 2. Memory map (SAM, ARM7 / AT91)

Tron 1.74 as used by the emulator and the decompile:

| Runtime address | What | File offset |
|---|---|---|
| `0x00000000-0x00035fff` | OS code | same |
| `0x00036000-0x000fffff` | RAM; initial values come from the ROM bytes at the same offset | same |
| `0x01000000-0x0107ffff` | game (rules) code, copied at boot to external RAM (EBI CS3) | `addr - 0x01000000 + 0x40000` |
| `0x01080000-0x0109dfff` | DMD frame pages (30 x 0x1000), then the sound output buffer `0x0109f000` | none |
| `0x01100000-0x01180000` | switch matrix, dedicated switches/DIPs, DMD page registers, bank read-back + board revision | none |
| `0x02100000` (+0x20000) | NVRAM (audits, adjustments, per-player arrays) | none |
| `0x02400020-0x0240002f` | IO power board bus: 16 registers on J1 (solenoids, lamps, aux bus, STATUS) | none |
| `0x02580000` | flash bank select (write) | none |
| `0x04000000-0x047fffff` | data: first 8 MB of the file | `addr - 0x04000000` |
| `0x04800000` window | other 8 MB banks, selected by a bank register (`flash_bank_select`, Tron `0x11e8c`) | bank N = `N * 0x800000` |

How to confirm the code base on another ROM: game-code `BL` targets only resolve to sane function
prologues with the right base. Data pointers in banked form are `bank << 24 | offset`, so the file
offset is `(p >> 24) * 0x800000 + (p & 0xffffff)`. That formula decodes both image and sound pointers.

**The OS size, and so the RAM start, differs per ROM.** Tron LE's OS runs to `0x36000`; Tron Pro's ends
at `0x2fa00`, so its RAM block starts there and every RAM address moves. Read the reset code: it copies
the OS into the AT91's internal SRAM (Tron LE: copy loop `0x84-0xc4`, remap `0xe0`) and loads the chip
selects from a table of EBI values (Tron `0x54`, code `0xd4`). Those two give you the real memory map;
the full chip-select table is in section 8.2. TF: OS `0x0-0x34057` (copy loop at `0x84`), RAM from
`0x34058`, game code at `0x01000000` = file `0x40000` (`0x6f090` bytes, copied at `0x160`), data at
`0x04000000` = the first 8 MB of the file. Always read the OS end from the copy loop, never from
another game's value.

**Scratch RAM for injected calls.** Find a block of RAM nothing uses (watch it stay zero through attract
and a game) and use it for the stack and buffers of injected calls (section 4). TF: `0x39400-0x3fc00`
unused, stack `0x3f400`, buffer `0x3ee80`.

---

## 3. Tooling that worked

### 3.1 Ghidra headless decompile
- Ghidra 11.4.2 (zip from the GitHub releases page) runs headless in the container.
- Import a raw binary (`-loader BinaryLoader -loader-baseAddr 0x04000000 -processor ARM:LE:32:v4t`), then
  a pre-script creates the real blocks (OS at 0, RAM at 0x36000, GAME at 0x01000000, NVRAM, IO as
  volatile), seeds functions and applies signatures. See `rules/tools/ghidra/run_ghidra.sh`,
  `TronSetup.java`, `TronExport.java`.
- **Quality fixes that mattered** (the v2 decompile):
  - Give the OS API real signatures (`rules/tools/ghidra/sigs.tsv`, 166 functions). Without them
    Ghidra drops arguments: `score_add` lost its argument in 19 of 90 calls.
  - Seed function starts from a list (`seeds_*.tsv`) and drop Ghidra's phantom functions at `+4` of a
    real one (211 of them in the first pass).
  - Label RAM globals (`ram_symbols.tsv`) and annotate constants in comments: sound call → sample list,
    message id → string, adjustment id → name, audit id → name, lamp id → name, deff id → name.
  - Function-pointer calls (tables, vtables) are not linked by Ghidra; resolve them from the tables in
    section 5.
- Output format that worked for agents: one big `.c` file with `// ==== <addr> <name>` headers, so a
  spec can cite `[0x01007244]` and a reader can grep it.
- Keep `capstone` (ARM mode) for anything the decompile hides; disassemble before trusting a claim.

### 3.2 PinMAME as a library, with an ARM hook
- `git clone --depth 1 https://github.com/vpinball/pinmame`, apply
  `rules/tools/trace/pinmame_arm_hook.patch`, build `libpinmame` with CMake
  (`cp cmake/libpinmame/CMakeLists.txt .`, `-DPLATFORM=linux -DARCH=x64 -DBUILD_STATIC=OFF`).
- The patch adds a callback `hook(pc, regs)` before **every** ARM instruction, plus
  `PinmameArmRead32/8` and `Write32/8`. It only works with the interpreter: run with
  **`PINMAME_NOJIT=1`**, or the JIT skips the hook. The `src/cpu/arm7/*` hunks are what actually call
  the hook; a patch that only declares `pinmame_arm_hook` and `PinmameSetArmHook` builds fine and the
  hook is simply never called. Check for those hunks in any patch you apply.
- The hook is how everything was observed: switch a on `pc` to catch calls to `deff_start`,
  `snd_resolve_call`, `leff_start`, `score_add`, `audit_add`, `coil_pulse` and log `r0..r3` and `lr`.
- ROM goes in `~/.pinmame/roms/<set>.zip`. Use a fresh temp NVRAM folder per run for determinism
  (factory settings). Pause the emulator at fixed emulated times while the script acts, and runs are
  byte-for-byte reproducible.
- Reference harness: `rules/tools/trace/tron_ref.cpp` (scenario language, JSON-lines trace, ball sim)
  and `trace_compare.py`. Asset capture: `mpf_package/tools/tracer.cpp` (forced deffs, play mode),
  `lfx.cpp` (lamp effects), `fmt.cpp` (run adjustment formatters).
- **Add the bus hook from the start**, not only for board work: `PinmameSetBusHook(addr, data, mask,
  write)` sees every solenoid register write (SOL_B `0x02400021` = coils 1-8, SOL_A `0x02400020` =
  9-16, SOL_C `0x02400022` = 17-24, FLSH_LMP `0x02400023` = 25-32, written every 250 µs), which gives
  exact coil pulse and hold times; `PinmameGetSolenoid` polling cannot (section 8.1). TF's
  `rom/tools/trace/pinmame_hooks.patch` is one patch with both hooks, RAM access and emulated time, and
  is the one to start from.
- For bus and board work, `io/bus/tools/pinmame_bus_hook.patch` (a full diff against stock PinMAME)
  adds a callback with cycle stamps on every IO board access, the DMD page RAM,
  the sound buffer and every AT91 on-chip peripheral. It declares the ARM hook but lacks the
  `src/cpu/arm7/*` hunks that call it, so apply `pinmame_arm_hook.patch`'s arm7 hunks too if you need
  both. `io/bus/tools/bus_trace.cpp` runs it
  (`BUSCAP_BOOT=1 PINMAME_NOJIT=1 ./bus_trace s_all.txt out.jsonl` logs power-on to 8 s, attract and a
  game). Emulator timing has no bus wait states, so check µs offsets against a hardware capture.

### 3.3 Unicorn for small isolated routines
Running one light-effect function in `unicorn` with hooks on the tube API and on `task_sleep` (advance a
fake 16 ms clock and continue) produced exact colour/fade/timing sequences far faster than full
emulation. Good for any effect that only calls a few OS functions; use full PinMAME when the effect
reads game state.

---

## 4. Getting a game to actually start in the emulator

This took longer than anything else on day one. Checklist:

1. **Switch numbers.** With libpinmame on SAM, `PinmameSetSwitch(n)` takes the **Stern switch number
   directly** (1-based, as in the switch test). An early bug converted numbers to a matrix scheme and
   the "trough" landed on switches 32-35. Verify by watching the switch handler you expect fire.
2. **Ball count.** The game refuses to start ("FINDING PINBALLS", ball search) until the trough
   switches report a full trough. Tron: hold 18-21 closed.
3. **Normally-closed optos.** Some switches must read closed at rest, or the game thinks a ball is
   stuck and ball search runs. Tron: disc opto 41 (and the switch descriptor flag `0x80` is also set on
   trough 21 and trough jam 22; meaning unverified). Find them with the descriptor flag or by watching
   which switch ball search complains about.
4. **Mechanisms.** Motors with position switches (Tron: Recognizer 3-bank 52/53, Recognizer motor
   54-56) need a tiny simulation, or the game logs faults and may hold up play. See the ball sim in
   `tron_ref.cpp`: trough eject coil → shooter switch, launch coil → ball in play, scoop kick coil →
   release scoop switch.
5. **Credits and the coin door.** `PinmameSetHandleKeyboard(1)`; coin keys 3-6 = coin slots 1-4,
   start key 1. Factory pricing on Tron (USA 10) is 3 quarters per credit, so insert several coins and
   watch the credit count. The libpinmame keyboard handler **overwrites switch column 0 (dedicated
   switches D17-D24) every frame**, so `PinmameSetSwitch` on the coin door, service buttons or tilt is
   undone at once: drive them with keys instead.
6. **Solenoids.** The `OnSolenoidUpdated` callback missed coils 1-32 on Tron; poll
   `PinmameGetSolenoid(i)` every step instead. Polling is only good to a few ms: for ms-accurate on-times
   sample the coil shadow bytes (Tron `0x3b97c`) inside the coil IRQ (Tron `0x12070`), which the 1 ms
   coil driver runs. 5 ms polling gave the shaker as 75/265/1100 ms; the real values are 200/384/1024.
7. **Country and DIPs.** `PinmameSetDIP` did not change the country. Write the country bytes in NVRAM
   (Tron `0x21100d8`/`0x21100d9`), fix the checksum (`0x21100da`, `checksum16` `0x27a0`) and call the
   factory-install function (Tron `0x1278`; TF: same bytes, checksum fn `0x1c50`, factory reset `0x728`).
8. **Watchdog and resets.** The SAM watchdog is not emulated: after a slam tilt the ROM spins in its
   halt loop (Tron `0x10ce8`) forever. Detect it and call `PinmameReset`.
9. **Forced effects have side effects.** Forcing a background-loop deff makes it the default display
   for the rest of the run, and an active service-menu deff blocks forced deffs. Start a fresh run per
   background deff.
10. **Process control.** `pgrep -f` / `pkill -f` inside a shell loop also match the loop's own command
    line; match on a pid file or an exact binary name.
11. **Lamps.** libpinmame lamp numbers 1-80 equal the ROM's lamp table numbers; 101+ are extra outputs
   PinMAME synthesises (Tron's RGB tubes are 101-106).
12. **Timing.** One OS tick is about **16.26 ms** in play (measured 16.25-16.30). The ROM itself
   treats 62 ticks as a "second", and some countdowns use 60, 64, 66 or 68. Give specs in ticks and ms.
   The main loop is paced from the 250 µs IO interrupt (a counter that steps every 64 IO ticks, 16.0 ms
   nominal; section 8.2); the measured pass interval is a little longer because a pass can overrun.
13. **PinMAME's "4008 Hz" is the sound FIQ, not the IO tick.** The IO tick is a CPU timer (TC0) at
   exactly 4000 Hz. Don't take timer rates from PinMAME comments; read the timer setup in the ROM.

### Forcing the ROM to run something (call injection)
To start any display effect, lamp effect or formatter on demand, hijack the OS sleep function:

1. Hook the entry of `task_sleep` (Tron `0xb91c`), which every task calls every frame.
2. When you want to inject, save all registers, set `r0..r3` to your arguments, `lr = task_sleep`
   entry, `pc = target` (for example `deff_start` `0x280b0` with `r0 = id, r1 = 0, r2 = 1`).
3. The target runs in that task's context and returns to `task_sleep`. When the hook sees
   `task_sleep` again **with the same `sp` as saved**, restore the saved registers and let the original
   sleep continue.
4. To pass a parameter the effect reads from its task block (Tron leffs read `task+0x30`), walk the
   task list (head RAM `0x372b0`, next at `+0x1c`, flags `+2`, id `+0x28`) and poke it after creation.
   The layout held on TF (code): deff id `+0x24`, flags u16 `+2` (`0x20` = leff task), leff id
   `+0x28`, prio `+0x2a`, task argument `+0x30`, next `+0x1c`; list head `0x314a0`, current task
   `0x314b0`, `task_sleep` `0xacfc`.

The same trick stops effects (`pc = leff_stop`), runs formatters to get adjustment labels, and so on.

### Random numbers
Tron's RNG is an LCG at RAM `0x372c4`: `x = x * 0x19660d + 1` (seed `0x04277dc9`), with
`random_below(n) = (n * x) >> 32` at `0xc6b4` (and a `random_percent` variant). The main loop advances it
on every pass, so **poking the seed in RAM cannot force a result**: the value has moved on by the time
the effect calls it. To force a branch, hook the return of `random_below` / `random_percent` at the
call site you care about and overwrite `r0`, or poke the seed at that call's PC. Name the RNG and the
forcing method in every trace that depends on a random branch.

---

## 5. The OS API and the data tables, and how to find them

On Tron the OS (0x0-0x36000) holds the framework and the game code calls into it. The full list of 160
identified OS functions with signatures and evidence is [rules/work/os_api.json](rules/work/os_api.json).
*(Tron only, untested elsewhere:)* other SAM games of the same OS generation likely share most of this
code at different addresses. A good first move on a new ROM is to build byte signatures of Tron's OS
functions (mask `BL` offsets and literal-pool loads) and search the new OS block for them.

### 5.1 Core OS functions (Tron addresses) and how to find each

| Function | Tron | How to find it in another ROM |
|---|---|---|
| `task_sleep(ticks)` | `0xb91c` | The most-called function; called in loops by every effect. Breakpoint on any running animation and look at the call it makes once per frame. |
| `task_create(id, fn, ...)`, `task_kill(id)`, `task_running(id)` | `0xb624`, `0xba3c`, `0xbe68` | Called with a small constant id and a code pointer. Task list head in RAM (Tron `0x372b0`), current task `0x372c0`. |
| `event_post(id)`, `event_hook_add(id, fn, prio)` | `0x79ec`, `0x7944` | Called with constants < 0x70 around game start, ball start, end of ball. Handlers are sorted by priority, so hook order matters. |
| `deff_start(id)` (display effect) | `0x280b0` | Called with small constants from switch handlers and modes; looks up an 8-byte table of `{fn, prio}`. |
| `leff_start(id)` (lamp-matrix effect) | `0x87ac` | Same pattern, 12-byte table, spawns a task with flag `0x20`. |
| `snd_play(call)` → `snd_resolve_call` → `snd_start_sample` | `0x2c8f4` → `0x2c744` → `0x2c1e4` | Insert a coin in the emulator and log calls with a small constant; or find the function that indexes a 20-byte table whose `+8` points to u16 lists. |
| `score_add(points)` | `0x2340c` | Called from almost every switch handler with round decimal constants (10, 170, 440 ...), multiplies by a playfield multiplier byte. On TF `score_add` (`0x1caf0`) tail-calls `score_add_player` (`0x1cb0c`): hooking both logs every award twice, so hook only the inner one (TF's first trace mismatch came from this). |
| `adj_get(id)` | `0xe90` | Small constants; result compared to ranges. Ids match the adjustment table order. |
| `audit_add(id, n)` | `0x178c` | Small constants; each id matches an audit name like "DISC MULTIBALL STARTED". |
| `msg_get(id)` and text drawing (`text_draw_msg`, `text_printf_msg`, `text_draw_msg_fit`) | `0xa58c`, `0x28ca8`, `0x28d5c`, `0x28e48` | Index the message table. **Include every text API** when extracting on-screen text; the first pass missed strings drawn with the "fit" variant. Text also reaches the renderer through vsprintf wrappers, font-picker functions, switch tables and function pointers, and some message ids are computed in registers (`mov r0,#imm` just before `0x28d5c`), so a grep of the decompile misses them. Hook the renderer in the emulator to be complete. Better: hook every text helper with its format and arguments (below the table). |
| `random_below(n)` | `0xc6b4` | Multiplies `n` by an LCG state and keeps the high word; see "Random numbers" in section 4. |
| `task_spawn_child` | `0xb840` | Child task with the current task's id; copies `task+0x30..0x47` (effect arguments) to the child. |
| `lamp_rule_init` | `0x1982c` | Despite the old name, it registers **deff/sound rules**, not lamp rules (method `0x198a8` calls `deff_start` and `snd_play`). On a rules refresh the first true deff rule ends the walk, while every leff rule (`leff_rule_init` `0x19740`) is evaluated. |
| `lamp_on/off/flash`, `lampgroup_*` | `0x833c`, `0x81f8`, `0x9200` ... | Take lamp numbers 1-80; groups are 0-terminated lists. |
| `coil_pulse(coil, ms)` | `0x6970` | Flashers and kickers from effects. |
| `game_flag_set/clear/test(flag)` | see decompile | Bit flags per player for mode state; very useful anchors. |
| `error_log(code)` | `0x5ac8` | Non-fatal error ring; `fatal_halt` `0x5aa8` resets. Don't mistake `error_log` for a crash. |
| RGB tube API (Tron-specific) | `0x7cc` set, `0x800` fade, `0x7a0` set_rgb | Console command strings (`lrlt`, `rrlt`) point straight at the handlers. |
| `shaker_run(strength, min_setting)` | `0x10289b8` | Pulses/holds the shaker coil, gated by an adjustment. |

**Text helpers: hook them all, with their arguments.** Hooking only the low-level `text_draw_str` gives
the drawn string but not the format and arguments behind it. TF has seven helpers (code): message id in
`r0`: `0x21660` text_printf_msg, `0x215ac` text_draw_msg_page, `0x217b4` text_printf_msg_fit_page,
`0x2174c` text_draw_msg_fit; string or format in `r0`: `0x21838` text_draw_str_page, `0x21a78`
text_printf_page, `0x21b4c` text_draw_str_fit_page. Printf varargs start at entry `sp+12` for `0x21660` /
`0x21a78` (7 fixed arguments) and `sp+16` for `0x217b4` (8). **Fit fonts:** a font operand that is a
pointer names a 0-terminated u32 list of font ids; `text_draw_str_fit` (TF `0x21b90`) uses the first that
fits the width argument (or the 128-px screen, for alignment, when the width is 0); font 0 is the last
resort.

**Ghidra pointer arithmetic.** Ghidra sometimes renders a scaled value as pointer arithmetic
(`(int *)x + n` means `x + 4n`). A literal read of TF's per-completion terms gave 6,250 instead of
25,000. Check every scaled value from the decompile against a trace before it goes in a spec.

**Settings code is shared between games.** On TF every adjustment, audit, pricing and menu function has
the same body as Tron's at a new address, so the settings extractor ports by address map
(TF: `rom/rom_data/settings/README.md`, `tools/settings_extract.py`).

**Anchoring rules code in a new ROM:** the audit names are the best map. The function that bumps
"DISC MULTIBALL STARTED" *is* the mode start; work outward from there. Display-effect text strings are
the second-best map.

### 5.2 Data tables (Tron addresses, record layouts, how to find)

The game registers several of its tables with the OS through a **table of tables** in RAM (Tron
`0x36ce4`; the deff table and the tube-show table are entries in it). Finding this block on a new ROM
hands you most tables at once: look for the RAM block the deff-start function loads its table pointer
from. The OS also keeps its own registry of `(address, count, record size)` triples (ground rule 20;
TF file `0x30b00`), which covers nearly every table below.

| Table | Tron address | Record | How to find |
|---|---|---|---|
| Switch descriptors | `0x040f3574` | 32 B per switch, index i = switch i+1; `+0` handler fn, `+8` name ptr, `+0x10` flags (bit `0x80` on NC optos?), `+0x1b` / `+0x1c` debounce passes to close / open (section 8.2) | Search for pointers to the switch-test name strings ("TROUGH #1"); the stride between them gives the record size. |
| Coil names | `0x040e0c00` (24 B) | name | Search for the coil test names. |
| Coil descriptors | `0x040e0f60` (28 B, indexed by coil number, record 0 = INVALID; pointer at RAM `0x36c48`) | `+0` flags (`0x2` drivable with HV off, `0x4` flasher, `0x400` skipped by the cycling test, `0x800` hidden from test), `+0x10` coil-test ms, `+0x12` ball-search ms, `+0x14`/`+0x16` wire colour msg ids | Indexed by the coil test. Read the flags as a little-endian u32 (an early CSV byte-swapped them and was off by one coil). |
| Coil rules | flippers `0x040e204c`, bumpers `0x040f0a5c`, slings `0x040f0a8c` | pulse ms, then hold pattern (Tron flippers: 40 ms, then 1 ms on / 11 ms off) | The coil driver ticks every 1 ms and supports a pulse, a 32-bit pattern, or on/off PWM. Decoded in `rom_data/io/`. |
| Shaker strengths | `0x040d3998` | ms per strength (200 / 384 / 1024) | Argument table of `shaker_run`. |
| Fonts | RAM `0x36f48`, count `0x36f44` | 20 B: `+0` char-range list, `+4` glyph table (8 B each: image ptr, s16 x off, s16 y off), `+8` height, `+0xa` spacing, `+0xc` masked, `+0x10` bank | The text renderer `text_draw_str` loads it. Tron: 44 fonts (`rom_data/fonts.json`). |
| Lamp names | `0x040e2bf4` | | Lamp test names. Lamp letter order may be the **reverse** of switch letter order (Tron: lamp 1 = TRO(N), switch 1 = (T)RON). |
| Lamp records / groups | `0x040e338c` (12 B) / `0x040e3acc` (109 0-terminated lists) | | Referenced by `lamp_lookup` and `lampgroup_*`. |
| Coil groups | `0x040e20c4` | | `coilgroup_pulse`. |
| Display effects (deffs) | `0x040e1350` | 8 B `{fn, flags/prio}`; prio = high half of word 2, flag bit 0 (value 1) = background loop (TF: bit 0, not bit 1) | `deff_start`. Tron has 146. |
| Lamp-matrix effects | `0x040e23e4` | 12 B `{fn, u16 flags, u16 lamp group, u16 coil group, u16 prio}` (the second group is a coil group, code on TF); count at `0x040c1fcc` | `leff_start`. Tron has 171-172; TF `0x040cfe00`, 178. |
| RGB tube shows (Tron-specific) | `0x040e3c88` | 12 B `{fn, flags, tube mask 1=L 2=R 3=both, prio}` | `tube_show_start` `0x0101b824`. |
| Sound calls | `0x040f16b4` | 20 B; `+8` → 0-terminated u16 sample list, `+12` loop/marker index, `+18` speech flag | `snd_resolve_call`. Tron: 299 calls. |
| Sample directory | file `0x120048` | 20 B per sample, points to a stream script | Referenced by `snd_start_sample`. |
| Messages (strings) | `0x040eeb7c`, count at `0x040d0da0` | u32 ptr → ptr → C string (per language) | `msg_get`. |
| Images | count RAM `0x36f4c`, table ptr RAM `0x36f50` | u32 `bank<<24 | offset` | `bitmap_draw` reads it. Tron: 8,181 images; TF: 10,212 (resource block file `0x123694`). The table index is not the header `rid` (section 7). |
| Adjustments | `0x040de218`, count `0x040bd398` | 32 B: `nvram, default, min, max, step, ?, name ptr, display type` | Search for "BALLS PER GAME". Standard order list in RAM (Tron `0x39558`). |
| Adjustment formatters | `0x040dd890` | fn, or u16 list of message ids | Run them in the emulator to get exact value labels (`fmt.cpp`). |
| Audits | `0x040e022c` | 16 B; `w3 >> 16` = counter id | Search for "GAMES STARTED". |
| Service menu items / menus | `0x040f4574` (20 B: visible fn, action fn, screen fn, msg u16, id, submenu) / `0x040f5108` (12 B, `+8` u16 item list) | | Search for "SWITCH TEST" message ids. |
| Install presets | lists of `(adj, value)` pairs | | OS lists sit in the RAM-init area (Tron `0x394xx`), game lists from `0x36f7c`; both are referenced from the install functions (Tron `0x1041d38`...). Tron 1.74's difficulty presets are empty. Country factory defaults come from per-country OS lists (USA `0x38fd4`). |
| Ball devices | `0x040e41f4` | 4 devices (trough + 3) | `ball_dev_call`. |
| Music / background | TF: walked by `0x178b0` | `+4` mask, `+0xc` condition fn, `+0x10` deff, `+0x12` sound call, `+0x14` chooser fn | Picks both the background display effect and the music for the game state (code, TF). |
| Random clip / award tables | e.g. `0x040d2804` (deff 48 clips), `0x040d29a0` (12 arcade awards) | per effect | Effects that call `random(n)` and index a pointer table. |

**Service menu numbers are list positions, not table ids.** "STANDARD AUDIT #1" on Tron is audit 14,
"FEATURE AUDIT #1" is audit 73, and standard adjustments follow an order list (Tron RAM `0x39558`, where
adj 1 COIL PULSE POWER is STANDARD ADJUSTMENT #43). Export both numbers.

Some table entries do nothing: on Tron adj 25 FREE GAME LIMIT has no reader in game logic, and audits
13 and 72 always show 0 (their functions return 0). Check for a reader before documenting a setting's
effect.

`rules/tools/ghidra/romtables.py` has readers for most of these (`msg(i)`, `adj(i)`, audits, deff,
leff and tube tables), and is the quickest way to start a table reader for a new ROM.

---

## 6. Sound

**Format (verified on all 1,090 Tron samples):**
- The sample directory points to a small stream script. Script `05 mask n len32 ...` describes a
  stream; `len32 / 4000` = duration in seconds. A `0a 00 <ptr>` followed by `10 01` plays a whole
  stream; the pointer is banked (`(p>>24)*0x800000 + (p & 0xffffff)`).
- Each ADPCM stream starts with an **8-byte header**: `u32 sample_count, u16 1, u8 rate_divisor,
  u8 same`. Rate = 24000 / divisor: **2 = 12 kHz, 1 = 24 kHz**. Data (IMA ADPCM, 4-bit, low nibble
  first, standard step table) follows the header. Decode exactly `sample_count` samples.
- Decoder: `mpf_package/tools/adpcm.py`.

**Mistakes made and fixed:**
- *Rate assumed per class.* The first export played everything at 24 kHz, so speech came out double
  speed. Read the divisor per sample: on Tron most speech is 12 kHz but 53 speech samples are 24 kHz.
- *Length from the wrong field.* The length of the `0f` opcode in the script is not the stream
  length; 123 sfx were cut wrong. Use the header count, and check `duration == len32/4000`.
- *Header decoded as audio* gave a click at the start of every file.
- *Header variant skipped.* 16 sfx streams (samples 0x09-0x14, 0x16-0x19) use a `...46 0a...` header
  variant, and one music stream (0x44d) was missed; 44 calls had no pool. Samples 0x01-0x08 have
  length 1: they are channel-stop stubs, not audio.
- Checking against the emulator's mixed audio output was inconclusive (music under everything). The
  ROM's own duration field was the reliable check.

- *Stream scripts searched in the wrong place.* On TF they sit in bank 3, near the end of the file
  (`0x1d1a664`); a search of the first 12 MB for stream pointers found nothing. Search the whole image.
- *Call numbers parsed as decimal.* The tracer prints sound calls with `%x`; parsing `call=` as decimal
  silently mapped calls to the wrong sounds. Store calls as hex strings everywhere.
- *Wrong caller logged.* Hook `snd_play` (TF `0x251f4`) and save its caller there: inside
  `snd_resolve_call` (TF `0x25044`) `lr` always points back into `snd_play`.

**Model for the rebuild:** the ROM never plays a sample directly. Code plays a **sound call**; the call
picks one sample from its list (random start index, skipping recently played). In MPF that is one
`sound_pool` per call (`call_XXX`, `random_force_all`), 290 pools on Tron. `snd_play_after` chains a
call after another finishes. Whether music beds loop is set in the stream script and was not decoded.

**Switch to callout mapping** used both static paths (switch handler → `snd_play`, N calls deep) and
emulated sweeps (every playfield switch hit once, then 6 times in a row, during a running game).
Speech often fires only on the hit that completes a set (TRON letters: 0x04c per hit, 0x102 on the
word). Mode callouts only appear once the mode runs; static analysis from audit anchors filled most.

---

## 7. DMD graphics and display effects

**Image format** (`mpf_package/tools/imgdec.py`): 13-byte header `u16 rid, u16 group, u32 flags, s16 w,
s16 h, u8 format`. Flags: 1 delta, 2 last frame of an animation, 4 cache. Formats:
- 0 raw, 1 byte per pixel
- 1 RLE column-major, 7 RLE row-major: `op = b & 3` (0 literal, 1 zeros, 2 run of 0xF, 3 repeat),
  `n = b >> 2`
- 12 packed 4 bpp, low nibble first
- 3 / 9 delta column / row: signed byte, `< 0` skip, `> 0` literal, applied on the image whose
  **header** `rid` is one less. The image table index is not the header `rid` (TF, code): look the base
  frame up by `rid`, not by table position.
- pixel 255 = transparent. Display 128x32, 16 levels. Tron animations are 87x32 drawn at x = 41
  (the left 41 columns are the score/status panel).
- The "last frame" flag is how to split the image list into animations (Tron: 145 animations).

**Capturing display effects:** force each deff with the call-injection trick during a running game
and log every image draw (`bitmap_blit` / `bitmap_blit_masked`, Tron `0x2b194` / `0x2b2a0`, `r0` =
image record), frame flip (`dmd_show_pages` `0x27830`), sound call and tube colour. That gives frames,
real per-frame timing, sounds and light shows with offsets. Also save a full-screen reference capture
(text and score panel included), because **text is not in the images**: the ROM draws it with its fonts,
so export the strings per effect. Better still, export the **text layout** itself: for each deff,
every draw call (font or font list, flags, x, baseline y, fit width), its format string, and where each
argument comes from (RAM address, order). The MPF build had to parse this out of the decompile two call
levels deep. Also export the **font table** (Tron: RAM `0x36f48`, 0x14-byte records: character ranges,
glyph image ids, x/y offsets, height, spacing); the build had to fit offsets to captures by hand.
**Extract fonts directly from the table; don't fit them to captures.** A glyph is drawn at
`(pen + xoff, y - h + yoff + 1)` and the pen then advances by `w + xoff + spacing`. Font images are not
always one contiguous image group (Tron fonts 27-32 are images 2175-2240).

**Capture hygiene** (each of these cost the downstream build time):
- Record the arguments and RNG state that produced each capture, so a variant can be reproduced.
- Keep exactly one run of the effect per capture (deff 115 was captured running twice, so its sounds
  appeared twice).
- Record the status-panel region and its live content; captures with a frozen panel (score 00) can only
  be compared outside that region.
- **Log the text draws of every captured frame** (frame index, font, x, baseline y, string, shade, and
  whether it was drawn by a font call or as a picture). Captures bake the ROM's text into the frames; an HD
  rebuild that redraws text in a smooth or different font must first remove it. The Tron HD build had to
  find it again by matching glyphs dot for dot (`scripts/frame_text.py` in the game repo: 50 captured
  effects); text that zooms or scatters (deff 100, ZEN) is drawn as blocks, not with a font. Better still,
  also save each capture once with the text calls suppressed.

**What forcing misses:**
- Effects that check game state quit at once when forced (7 on Tron). Run long automated play
  (trough, shooter, scoop, random shots; ~12 emulated seconds per real minute, 4 in parallel) to catch
  them, and to record the game-flow sequences (attract, game start, ball start, bonus, match).
- Many effects pick a **random film clip** from a pointer table, or one by mode level. One capture is
  one random pick: read the table and export every variant. Deff 108 was first shipped with 1 of its 4.
- **Background effects** (deff flag bit 0) never get a forced end: close their capture window at the
  end of the log, or they are lost. Give them at least 14 s per run (10 s ended before some rendered on TF).
- Effects that read game state end within a fraction of a second when forced (TF: about 35 end within
  0.3 s). Poke the state they need (TF tracer: `POKE=addr=value[:size],...`) or catch them in live play.
- Composite effects (Tron deff 105, the mystery award: 3 cabinets, 2 decoys, chosen award blinking)
  should be shipped as parts plus the logic, not as a single captured GIF.
- "There is no start-of-game animation" was a real answer: Tron starts music, a tube show and an
  effect that only shows because the arcade starts lit. Check *why* an effect plays before wiring it
  to an MPF event.

---

## 8. Lights, coils and IO

**Two (or three) light-effect systems.** Keep them apart by name from the start; mixing them up caused
confusion across threads:
1. **Lamp states** set by modes (`lamp_on`, rules objects). Your rebuild's modes recreate these.
2. **Lamp-matrix effects** ("leffs", table `0x040e23e4`): scripted sweeps and blinks layered on top.
   Captured with `lfx.cpp`: inject `leff_start`, then on each lamp compositor tick (Tron `0x7f68`) read
   the leff layer (image `0x3c224`, mask `0x3c238`) and the layer list (RAM `0x3728c`: image `+0..0x13`
   two planes, mask `+0x14`, owner task `+0x20`, next `+0x24`), and log `coil_pulse` from leff tasks
   for flashers. Some take a lamp or lamp group from the caller (task `+0x30`), some are empty, some
   draw from live mode state (not exportable as shows). Rule leffs come from
   `leff_rule_init(obj, list, cond_fn, leff_id)` = "run while cond is true".
   Flasher-only effects may only run with a validated playfield.
   Counting only lamps whose layer owner is the leff task gives clean shows. The same compositor and
   layer list held on TF (code + observed): tick `0x73cc`, leff layer image `0x36394` / mask `0x363a8`,
   layer list `0x31480`, same offsets; `tools/emu/lfx.cpp` (the Tron lfx port) gave 178 leffs, 119
   that end by themselves and 59 that loop until stopped.
3. **Game-specific outputs.** On Tron, RGB "ramp light tubes" (the owner's "fiber optics") on the IO
   board aux bus: `AUX_DRV` `0x02400026` bits 5/4/3 = R/G/B, strobe register `0x0240002B` (shadow
   `0x3c758`), refreshed every 250 µs IO interrupt with 4-bit binary-coded modulation. They have their
   own effect table and API (section 5).

**Finding IO on another ROM:** the OS never hard-codes register addresses. It loads them from a block
of pointers in RAM (Tron `0x37280-0x37350`). Search for that block, and every hardware access follows.
Coils are written as shadow bytes (Tron `0x3b97c[0..4]`) that the IO interrupt copies out; GI relay is
a bit of the strobe register. Console command strings (Tron has a debug console with named commands)
are a great shortcut to driver functions. Section 8.2 describes the whole bus and every CPU-board
interface behind these pointers.

**Coin meter.** A coil that fires once per coin is the coin meter (TF coil 24, 81 ms per coin;
inferred). Don't mistake it for a game coil.

**Coil types:** motors and relays (disc motor, 3-bank motor, shaker, direction relays) are held outputs,
not pulse coils. Mark them hold/enable in the rebuild config.

**Shaker:** `shaker_run(strength, min_setting)`, gated by the SHAKER MOTOR adjustment. Read the
strengths from its argument table (Tron `0x040d3998`: 200 / 384 / 1024 ms; measured 203 / 390 / 1040 ms
at the coil IRQ). Don't measure coil times by polling; see section 4.

**Coin door interlock:** with the door open the 50 V / 20 V are cut and the ROM masks its own outputs: on
Tron the IO interrupt `0x12070` writes the coil shadow ANDed with the mask at `0x3b984` while RAM
`0x3727c & 3 != 3`, so only the optional coil 24 can fire, and the power handler (LE `FUN_00007bc4`, Pro
`FUN_000071a0`) starts deff 4 ("50V / 20V DISABLED", priority 247, never ends by itself; BACK clears it with
sound 0x009). A rebuild must model this; it is easy to miss, since emulator runs keep the door closed.

**Service menu during a game:** SELECT in a game suspends the game task (`task_suspend(0, 0x800)`, Tron
`FUN_0000f9b0`) and the menu exit resumes it (`FUN_0000fa34`). Export this with the OS model: an engine whose
timers cannot be suspended (MPF) needs a stated departure.

**GI:** on Tron it is bit 0 of `0x0240002B`, **active low** (0 = on), on from power-up, owned by one
task at a time and released when the owning lamp effect ends. **Dedicated switches:** the ROM names
D22 Minus and D23 Plus; PinMAME's labels are reversed, as are its ramp tube left/right labels.

---

### 8.1 Required: hardware drive data for every output

Do this as its own step (section 13, step 8), for every coil, flasher, motor, relay and aux output, and
ship it as one CSV row per output. Test-menu values are not enough: the coil test and ball search use
their own times (Tron descriptor `+0x10` / `+0x12`), which differ from what game play fires.

1. **Static read.** For each output, read its descriptor (flags: flasher, drivable with HV off, hidden
   from test), its coil rule if it has one (flippers, bumpers, slings: initial pulse, then hold pattern
   or PWM), and every `coil_pulse` call site with its constant time or pattern argument and any
   argument tables (Tron: shaker `0x040d3998`). Record the address of each value.
2. **Decode the driver.** Find the coil driver tick (Tron: every 1 ms from the coil IRQ `0x12070`) and
   how it interprets each request: plain pulse in ms, 32-bit repeating pattern, on/off PWM, or held
   until released. Note any global scaling, such as a COIL PULSE POWER adjustment.
3. **Measure in game play at 1 ms.** Sample the coil shadow bytes (Tron `0x3b97c`) inside the coil IRQ
   (or log the solenoid register writes with the bus hook, section 3.2, which TF did)
   and log every on/off edge per coil while a scripted game exercises each output (flippers held and
   tapped, every kicker, every flasher effect, motors, shaker at each strength). Do not poll from the
   host loop: 5 ms polling produced shaker times that were 2-4x too short.
4. **Reconcile.** Each output gets: pulse ms, hold pattern or PWM duty, max on-time, source address,
   static value, measured value, and tag (code / observed / inferred). Static and measured must agree
   within a tick; investigate any that do not.
5. **Map to the rebuild.** Give MPF the values directly (`default_pulse_ms`, `default_hold_power` or
   `pwm` settings, `allow_enable` for motors and relays), and say which values came from the ROM and
   which are platform choices.

**Lessons from doing this on Tron:**
- **Zero-cross sync.** Many kicks pass `sync = 1`, which waits for the next AC zero-cross edge (Tron:
  input bit 2 of `*(0x37350)`, 60 per second) before firing. A 64 ms request then measures about
  64-66 ms of on-time, and the start is delayed by up to one half-cycle. Record the sync flag per call
  and don't mistake the extra ms for a different pulse length.
- **Repeats are part of the behaviour.** The drop bank reset fires again about every 0.25 s while a
  drop target still reads down, and pops and slings have a recycle time. Record repeat and recycle rules,
  not only the single pulse.
- **Variable-time calls.** 87 Tron call sites take their time or pattern from a variable or table
  (mostly flasher patterns), so static reading leaves them blank. Only run-time hooks on the coil API
  give their values; list them as unresolved until seen.
- **Untestable outputs.** Some outputs cannot be exercised in the emulator: Tron's upper left flipper
  has no emulator button, and the ticket outputs never fire at factory settings. Mark these
  code-only, and say how they could be measured (a different setting, a poke, real hardware).
- **API variants.** The driver API has plain pulse, pulse-and-wait, pattern, PWM and serialised-queue
  variants (Tron `0x2bc8`, `0x2cb0`, `0x2d18`, `0x2e5c`, `0x2b60`); hook all of them, or calls slip through.

**Tron worked example** (`rom_data/io/coils.csv`, `coil_calls.csv`, `coil_rules.json`; commit 8cd7439):

| Output | In-game drive |
|---|---|
| Trough kicker, auto launch, drop bank reset | 64 ms (zero-cross synced, ~64-66 ms on); drop reset repeats ~0.25 s while a target reads down |
| Scoop (VUK) | soft kick: 1 ms on / 1 ms off for 64 ms |
| Orbit up/down post | 64 ms, then hold 1 ms on / 6 ms off for 1.5-2 s |
| Pop bumpers | 32 ms, recycle 16 ms |
| Slingshots | 32 ms, recycle 192 ms |
| Flippers | 40 ms, then hold 1 ms on / 11 ms off |
| Knocker | 80 ms per count |
| Ticket meter | 100 ms per count (code only) |
| Shaker | 200 / 384 / 1024 ms by strength |
| Motors and relays | held by code, or until a position switch |
| Flashers | set per effect, mostly 24 / 32 / 48 ms; some patterned runs of 50-750 ms |
| Coil test / ball search | separate values in the descriptor (`+0x10` / `+0x12`); not the in-game times |

The same applies to other hardware the ROM drives: GI (bit, polarity, power-up state), aux-bus outputs
(strobe, data bits, refresh rate), and dedicated switches (D1-D24 meanings, which differ from PinMAME's
labels on Tron).

### 8.2 CPU board interfaces and bus timing

Needed when the owner wants to repair, replace or improve the hardware (Tron: a replacement CPU board
with finer LED PWM), and useful for any rebuild that drives real boards. Everything below is the ROM's
software timing; the board itself has no timing of its own. Tron's full result is
[io/bus/README.md](io/bus/README.md) (power board bus, lamp matrix, PWM proposal) and
[io/bus/CPU_BOARD_IO.md](io/bus/CPU_BOARD_IO.md) (DMD, audio, switches, RTC, serial), with CSVs beside them.

**Procedure:**
1. **Chip selects and boot setup.** Log every AT91 on-chip peripheral write from power-on (EBI, AIC,
   PIO, PS, TC, USART) in the emulator, in order (Tron: `peripheral_init.csv`). The EBI values give each
   device's bus width and wait states; the AIC values give every interrupt source, priority and handler.
2. **Interrupts.** Find each timer's clock and RC (rate = MCK / divider / RC) and follow the AIC vector to
   the handler. Expect one fast IO tick that does all power board traffic, a lamp one-shot, and the
   sound FIQ. Tasks never touch the IO board: they write RAM shadows and the interrupts copy them out.
3. **Tick schedule.** The IO tick runs blocks on down-counters (most reload with 4, so 1 ms in four fixed
   phases). Tabulate phase, block, registers written and order (Tron: `isr_schedule.csv`).
4. **Bus trace.** Run the bus hook (section 3.2) over attract, a game, a held flipper and each special
   output, and print per-tick write sequences with µs offsets.
5. **Hardware cross-check.** If the owner has logic analyzer captures, decode them into bus cycles
   (`io/bus/tools/la_capture_decode.py` reads PulseView CSV) and line them up with the emulator. Derive
   the analyzer's sample rate from a known period (Tron: 4 ticks = 20,002 samples, so 20 MS/s), and check
   the capture came from the ROM you think: Tron LE sends ramp tube writes every tick, the owner's
   captures had none, so they were most likely taken on Pro code.
6. **Per interface, write down:** registers and bit layout, who writes or reads them (address), rate, the
   order of writes, and what a replacement must reproduce. List the items that need a scope.

**What SAM does (Tron LE 1.74, worked example):**

| Interface | Finding | Tag |
|---|---|---|
| Chip selects | CS0 `0x04000000` game flash 16-bit, 5 wait states; **CS1 `0x02000000` 8-bit, 4 wait states**: boot flash, NVRAM, IO board, LED, bank select; CS2 `0x03000000` USB; CS3 `0x01000000` external RAM, 16-bit, 1 wait state (game code, DMD pages, switch and DMD registers) | code |
| IO tick | TC0, MCK/2, RC 5000 = **250.0 µs**, handler `0x12070` (via `0x13624`); `0x11f2c` masks it as a critical section | code + hardware |
| Lamp matrix | 10 strobe lines x 8 drive lines, **1 ms per line**, 10 ms frame. Phase 3 blanks all lines, then TC1 (`0x11fbc`) writes the next line **20 µs** later (24.35 µs on hardware). Lamp n = line (n-1)/8, drive bit 7-((n-1) mod 8). Max on-time 9.76 %. | code + hardware |
| Lamp brightness | **2 bit-planes weighted 1:2** (4 levels) over 30 ms; `lamp_on/off` take a plane mask, almost always `0xff`. Compositor `0x7f68` rebuilds the buffer once per OS tick; blink mask toggles every 5 OS ticks. | code |
| Coils | shadows rewritten every 250 µs, but coil slots and flipper/sling/bumper rules run every **1 ms**, so timing resolution is 1 ms. Slot modes: bit pattern, pulse then hold, timed on, optional zero-cross wait. Interlocks mask the driver bytes. | code + emulator |
| Coil burst | always SOL_B, SOL_A, SOL_C, FLSH_LMP, AUX_DRV, then reg 0xB strobe low/high; 650 ns between writes on hardware | code + hardware |
| Aux port / GI | reg 0xB is one latch: bit 0 GI (active low), bits 3-7 five aux strobes, idle high, always written whole from a shadow. Aux boards latch AUX_DRV on their strobe's rising edge. | code + hardware |
| Ramp tubes (LE only) | 4-bit BCM, one bit-plane per tick, 3.75 ms frame; fades step once per tick | code + emulator |
| STATUS | read at 1 kHz: bit 2 zero cross, bits 0-1 the 20 V / 50 V interlocks; lamp fault bits 3-4 are never tested | code |
| Switches | 4 strobes x 16 returns (`0x01100008` / `0x01100000`), one column per 250 µs (every 500 µs on board revision 0, read from bits 4-6 of `0x01180000`), dedicated D1-D24 and DIPs at `0x01100002/4`. Switch number = column x 16 + row + 1; dedicated = 129-160. | code + emulator |
| Debounce | stage 1 in the IO tick: changed on 2 scans in a row; stage 2 in the main loop (`0xeadc`): per-switch pass counts from the switch descriptor `+0x1b` (close) / `+0x1c` (open). Flipper EOS and slam are 0/0. | code |
| Fast paths | flipper and sling rules read raw switch state in the IO tick: switch to coil in **11-17 µs** after the read; bumpers 1.3 ms. A replacement needs switch-to-coil within about 1 ms. | emulator |
| DMD | 30 pages of 128x32 bytes at `0x01080000` (low nibble shade, high nibble mask); fg/bg page registers `0x01100020` / `0x01100022`, flipped once per OS tick, background first, never synced to the scan. The FPGA scans by itself (62.67 Hz, 4 planes weighted 1/2/4/5 per PinMAME). | code + emulator + external |
| Audio | FIQ about 4 kHz from the FPGA; each writes 6 stereo 16-bit frames to `0x0109f000`: 24 kHz output from an 8-voice mixer that switches flash banks and restores them. Volume is a bit-banged 3-wire link on P3-P5 (words match a TI PCM17xx-class DAC, inferred). | code + emulator |
| Other | RTC bit-banged on P16-P18 (DS1302-style, inferred); USART1 9600 baud LED sign (BetaBrite); USART0 57600 baud unused (probably the debug console); NVRAM 128 KB; board LEDs `0x02500000` / `0x02F00000`; the AT91 watchdog is never enabled | code + emulator |
| Bus cycle | IOSTB low about 100 ns; latches clock on the rising edge; about 57,000 accesses per second in a game, under 1 % of the bus | hardware + emulator |

**Gotchas found on Tron:**
- **16-bit stores on an 8-bit chip select.** The ROM writes two adjacent IO registers (lamp strobe and
  aux lamp) with one 16-bit store. The EBI splits it into two byte cycles with IOSTB held low across
  both, so the first latch is clocked by the address change, not by IOSTB rising. It works on the
  original board; a replacement should issue two clean byte cycles.
- **PinMAME's IO register notes were wrong in places** (switch strobe, bank select). Confirm each
  register from the runtime pointer block (ground rule 18).
- **The IO board watchdog** is said to be fed from the lamp strobe logic: a replacement must keep
  strobing at least as often as the ROM. The condition and timeout need the schematic and a scope.
- **The ROM never reads the display side**, so it never waits for a frame. Whether the original page
  registers latch at frame start or tear needs a scope.
- **Finer PWM does not need a new bus protocol.** The ROM's coarse brightness comes from its own
  scheduling, not from bus bandwidth. Edge-sorted PWM inside each lamp slot (write all on, then turn
  lamps off in order) gives about 10-bit brightness at 400 Hz with at most 9 writes per slot; the
  1/10 duty ceiling of a 10-line matrix stays unless the power board changes.

## 9. Rules extraction

How the full rules came out (21 feature specs, about 60 reference traces):

1. Clean the decompile first (section 3.1). Then write a short **OS API brief** (`os_api.json`) and a
   **spec template** (`rules/work/TEMPLATE.md`: summary, settings, state, start, running, end, media,
   lamps, interactions, reference scenario, open questions) so parallel workers produce the same shape.
2. Build the **reference trace recorder** before writing specs. A short scenario script (`start`,
   `hit SW`, `wait`, `drain`, `adj`, `poke`, `button`) drives the real ROM and writes JSON lines
   (`score_add`, `deff_start`, `sound`, `leff_start`, `audit`, `flag_set`, `coil`, `lamp`, watched RAM
   `var`). Every number that matters gets checked this way. The rebuild later emits the same events, and
   `trace_compare.py` reports the first difference.
3. Split features across workers by mode family, each writing only its own files (spec, scenario,
   trace, RAM map, function names). Merge their function names back into the decompile at the end.
4. Things to extract that people forget:
   - **Switch hook order.** Each switch handler calls feature hooks in a fixed order; copy it as
     handler priorities.
   - **Scope of every variable**: per game/player (reset on the player's first ball), per ball, per
     mode. Per-player data lives in NVRAM arrays indexed `[player-1]`.
   - **Playfield validation** rules (which switches count), because ball save and timers depend on it.
   - **What pauses timers** (Tron: unvalidated playfield, a "show" display task running, a recent pop
     bumper hit).
   - **Which multiballs block or stack with which.**
   - Dead code and unreachable features, listed so nobody builds them.
   - **Per-player array indexing, one array at a time.** Not every array uses `[player-1]`: TF's side
     byte (Autobot / Decepticon) is at `0x02112107 + player`. Check each array's index from its code.
   - **Ball save in scenarios.** Ball save blocks drains; an end-of-ball scenario must wait it out or
     turn it off with an adjustment.
5. Mark every rule `(verified ...)`, from code (with the address), or `(inferred)`.

The project owner's correction is worth remembering: Flynn's Arcade, which code text suggested was a
video mode, is a **mystery award**. Ask the owner when the domain knowledge is theirs.

---

## 10. Packaging for MPF (or another engine)

- **Valid MPF files:** every config file starts with `#config_version=6` and every show file with
  `#show_version=6`, or MPF refuses to load it. Unique keys everywhere. Ideally add a CI job that loads
  the config with `mpf` itself, not only with a YAML parser.
- **Name each effect system distinctly from day one.** On Tron the ramp tube shows were exported as
  `leff_NNN`, which collides with the ROM's own "leff" (lamp-matrix effect) name; the MPF repo now pins
  those paths, so they stay. On a new game use `tube_show_NNN` (or the game's own output name) for
  game-specific outputs and `lampfx_NNN` for the lamp matrix.
- Keep the ROM's own numbering in every name and event (`deff_046_*`, `call_0f0`, `lampfx_133_*`) so
  specs, traces and assets line up.
- One `sound_pool` per sound call. One show per display effect (slide + sounds + tube show + lamp
  effect + shaker at captured offsets). Background-loop effects run until the mode stops them.
- Letter targets need letter-based names (`s_tron_t`, `l_tron_n`), not one name per word.
- Hardware numbers stay the original SAM numbers; the builder maps them to their controller. Flipper
  buttons, EOS and coin door are SAM "dedicated" switches, not in the ROM switch table.
- Settings: every adjustment as an MPF setting with ROM labels, defaults and ranges; the service menu
  tree and audits as a document. Check that MPF accepts what you use (for example settings in
  `show_player` conditions was not verified on Tron).
- Before shipping: duplicate-key YAML check, reference checker (every show, sound, image, light, file
  referenced exists), and a count of pools vs calls and files vs directory entries.
- **PinMAME's numbers next to the ROM's.** A Visual Pinball X table talks to PinMAME, not to the ROM's
  numbering, and a rebuild played from VPX (agent D) must answer in PinMAME's numbers. On SAM, matrix
  switches, coils 1-32 and lamps 1-80 are the ROM's numbers; the rest differs. Tron already exports the
  dedicated switches' PinMAME numbers (`rom_data/states/dedicated_switches.csv`, `pinmame_switch`: flipper
  buttons 84 / 82, tilt -7, slam -6, coins 65-68, service BACK/MINUS/PLUS/SELECT -3 / -2 / -1 / 0; the coin
  door has no PinMAME switch, the VPX build uses D20's -4). Also export the outputs PinMAME adds: solenoid
  33 is the "flippers enabled" input of `sam.vbs` fast flips, and game-specific outputs get lamp numbers
  above 100 (Tron ramp tubes 101-106 from `SAM_GAME_TRON`, strobe 0x10 / 0x20, each blue, green, red). Tag
  them **external** (PinMAME `src/wpc/sam.c`, VPX `sam.vbs`).
- The ROM image is copyrighted: never commit it. The extracted media were committed as plain git
  (Tron: 291 MB, largest file 6 MB).

---

## 11. Mistakes log (Tron project)

| Mistake | How it showed up | Fix / rule |
|---|---|---|
| Wrong switch numbers sent to libpinmame | Game stuck in ball search; "trough" was switches 32-35 | Pass Stern numbers directly; verify handler fires |
| Disc opto left open | Ball search at game start | Hold NC optos closed |
| Speech decoded at 24 kHz, lengths from `0f` opcode | Owner heard garbled, fast, cut-off callouts | Read per-sample header; check vs ROM duration |
| 17 audio streams skipped (header variant) | Audit: 44 calls with no pool | Count directory entries vs exports |
| "53 speech at 24 kHz" stated as "speech is 12 kHz" | Misleading docs | State the per-sample rule, not a class rule |
| Duplicate YAML keys (`s_tron` x4 ...) | 8 switches and 8 lamps silently dropped | Duplicate-key loader on every file |
| `score_add` named `lamp_show_start`; args dropped | Misread rules | OS signatures in Ghidra; name from behaviour |
| Mode guesses from code location | Wrong mode for many effects | Prove with call chains or traces |
| Deff 22 "tilt warning" | Was an empty `mov pc, lr` stub | Disassemble table targets |
| Deff 105 "video mode intro" | It is the mystery award reveal | Follow the call path from the switch |
| Deff 45 tied to Flynn's Arcade | Its start function has no caller | Search for BLs and stored pointers |
| Only lamp-matrix *or* tube shows considered | A whole effect system unexported | Inventory every effect table first |
| Deff 108 single clip | Random clip effect | Read `random(n)` tables |
| `parts/` written to staging, never copied | README described missing files; owner noticed | Reference checker before shipping |
| Update zip unzip-location wrong | Files land in the wrong folder | Test-unzip in a clean folder |
| Full 150 MB zip rebuilt for each fix | Owner asked to stop | Small update zips of changed files |
| `OnSolenoidUpdated` missed coils 1-32 | Missing coil events | Poll `PinmameGetSolenoid` |
| Repo rename attempted by the agent | Proxy refused settings writes | Owner renames in GitHub settings |
| Generated MPF config had no `#config_version=6` header | MPF refused it; the build had to add it | Header on every config file, `#show_version=6` on shows |
| Audit findings fixed but never marked resolved | Next agent worked around fixed defects | Mark RESOLVED where reported |
| Font table and deff text layout not exported | MPF build re-derived them from captures and decompile | Export as JSON (section 14) |
| Coil pulse/hold times not decoded | MPF build guessed values for real hardware | Decode the coil table |
| Deff 115 captured running twice; frozen score panel | Doubled sounds, unusable panel pixels | One run per capture, note panel region |
| Shaker timed by 5 ms polling (75/265/1100 ms) | Real values 200/384/1024 ms | Read the ROM table; time coils at the 1 ms IRQ |
| `coils.csv` `desc_flags` off by one coil and byte-swapped | Wrong flags per coil | Index by coil number; read as LE u32 |
| `lamp_rule_init` named from a guess | It registers deff/sound rules | Name from the method it calls |
| Sea of Simulation stage 6 and completion read from code only | Wrong shot count; deff 125 never plays | Trace late states (poke into them) |
| Adj 10 default taken from the adjustment table | USA factory default differs (YES) | Read the per-country install lists |
| Service menu numbers taken as table ids | Audit #1 is not audit 1 | Export menu position and table id |
| PinMAME labels trusted (tube sides, D22/D23) | Both reversed vs the ROM | Prefer the ROM's own strings and tests |
| Coil times not extracted until the MPF build asked | Build guessed pulse times for real hardware | Section 8.1 as a required step |
| `io_registers.csv` switch strobe and bank-select addresses wrong | Caught only when the bus was traced | Confirm registers from the runtime pointer block |
| Switch matrix first reported as 8 columns | Corrected to 4 from the switch count `0x040d1c38` | Size the matrix from the ROM's own count |
| PinMAME's 4008 Hz taken as the IO tick | It is the sound FIQ; the IO tick is TC0 at 4000 Hz | Read the timer setup in the ROM |
| Owner's bus captures assumed to be LE code | No tube writes in them; LE sends them every tick | Check a capture against a model-specific signature |
| Owner asked whether the pseudo-C recompiles | It does not; mode changes need binary patches | Ground rule 16, section 16 |
| Text left baked into the deff captures only | The HD rebuild matched glyphs dot for dot to clear and redraw it | Log text draws per captured frame (section 7) |
| PinMAME's extra outputs not exported | The VPX bridge re-derived solenoid 33 (fast flips) and the tube lamps 101-106 from `sam.vbs` and PinMAME source | Export PinMAME numbers for every output (section 10) |
| Coin door interlock and in-game service suspend not in the OS model | Found by the MPF build from the owner's play tests, after the rules were built | Export them with the OS model (section 8) |
| TF: Tron function names carried into the TF decompile | Functions named for the wrong effect (`deff_093_zuse...`) | Ground rule 21 |
| TF: full re-capture replaced a good one | 25 effects came back empty | Ground rule 22 |
| TF: hook patch without the arm7 hunks | Hook never called | Section 3.2 |
| TF: both `score_add` and its inner call hooked | Every award logged twice; first trace mismatch | Hook the inner one only (section 5.1) |
| TF: Ghidra pointer arithmetic read literally | Scores 4x too small | Check scaled values against a trace |
| TF: sound calls parsed as decimal | Calls mapped to the wrong sounds | Hex strings everywhere (section 6) |
| TF: stream scripts searched in the first 12 MB | No streams found | Search the whole image |

---

## 12. Tron LE 1.74 quick reference (worked example)

- OS: `task_sleep 0xb91c`, `task_create 0xb624`, `event_post 0x79ec`, `deff_start 0x280b0`,
  `leff_start 0x87ac`, `leff_stop 0xc404`, `snd_play 0x2c8f4`, `snd_resolve_call 0x2c744`,
  `snd_start_sample 0x2c1e4`, `score_add 0x2340c` (multiplier byte `0x38180`), `adj_get 0xe90`,
  `audit_add 0x178c`, `msg_get 0xa58c`, `coil_pulse 0x6970`, `error_log 0x5ac8`.
- Game: `tube_show_start 0x0101b824`, `shaker_run 0x010289b8`, VUK feature dispatcher `0x0102eddc`.
- RAM: task list `0x372b0`, current task `0x372c0`, IO pointer block `0x37280-0x37350`, active deff
  u16 `0x381a8`, current player `0x3817c`, scores `0x021109e4`, image count/table `0x36f4c/0x36f50`.
- Tables: see section 5.2.
- Emulator start: trough 18-21 closed, disc opto 41 closed, 3+ coins, start; `PINMAME_NOJIT=1`.
- Tick 16.26 ms; DMD 128x32, anims 87x32 at x = 41; speech mostly 12 kHz, sfx/music 24 kHz.
- RNG: LCG at RAM `0x372c4`, `random_below 0xc6b4`. Fonts: RAM `0x36f48` (44). Coil descriptors `0x040e0f60`;
  coil IRQ `0x12070` (1 ms); shaker table `0x040d3998`; slam halt loop `0x10ce8`. Machine-readable data: `rom_data/`.
- Hardware: IO tick TC0 250 µs (`0x13624` → `0x12070`), lamp one-shot TC1 (`0x11fbc`), sound FIQ
  (`0x2b600` → `0x2d8b4`), IO bus `0x02400020-2f`, switch return/strobe `0x01100000`/`0x01100008`,
  DMD pages `0x01080000`, page registers `0x01100020/22`, sound buffer `0x0109f000`, bank select
  `0x02580000`, board revision bits 4-6 of `0x01180000`. Details: `io/bus/`.
- Pro 1.74 (`trn_17402`): OS ends `0x2fa00`, coil descriptors at file `0xc6254`, shaker table `0x040bc8e0`,
  LE → Pro function map `rom_data/pro/le_to_pro_functions.csv`. Differences: `docs/PRO_VS_LE.md`.

## 13. Suggested order for a new SAM ROM

(Section 14 is the checklist of what the result must contain.)

1. Identify the set; map memory; entropy scan.
2. Build libpinmame with the hook; get a game started (section 4). Find `task_sleep`.
3. Find the strings tables (switch, coil, lamp, adjustment, audit, message names) and the switch
   descriptor table. Dump them to CSV/JSON.
4. Find `snd_play` (coin sound), the call table and the sample directory; decode and **check lengths
   against the ROM**.
5. Run Ghidra with seeds and OS signatures; annotate constants. Iterate names as you learn.
6. Find `deff_start` and the image table; decode images; capture every effect by injection.
7. Inventory every effect table (lamp, display, game-specific outputs) and capture each.
8. **Hardware drive data for every output** (section 8.1): descriptors, coil rules, call-site
   arguments, driver decode, and a 1 ms in-game measurement per coil. Required, not optional.
9. Adjustments, formatters, audits, service menu.
10. Build the trace recorder, then write rules specs mode by mode, anchored on audit counters.
11. Package; run the duplicate-key, reference and count checks; ship; then audit the package against
    the ROM with fresh eyes (on Tron that audit found 8 real errors).
12. If the owner works on hardware: CPU board interfaces and bus timing (section 8.2).
13. If other models of the game exist: port the pipeline to each image (section 15).

---

## 14. Deliverables checklist for the next SAM game

This list comes from the agent that built the Tron MPF recreation on top of this repository
(feedback dated 2026-10-04). Produce each item as a table (CSV or JSON) first and prose second, and give
every row the ROM address it came from and an observed/code/inferred tag.

**What the downstream build valued most (keep doing it):**
- Reference traces plus the compare tool. Every rules feature was accepted only when its trace matched;
  the scenario language (`start`, `hit`, `wait`, `mark`, `adj`) was easy to replay on MPF.
- ROM addresses everywhere (task ids, functions, tables) in specs and the decompile: every dispute was
  settled with a grep.
- Fact tags, and a stated conflict rule (rules spec wins on rules, package wins on media and names).
- A read order (`rules/README.md` → `developer_guide.md` → `modes/`) and a "do not build unreachable
  code" list.
- All ROM images as PNG (`rom_images_all.zip`): enough to rebuild all 44 fonts and the service icons.
- One sound pool per sound call, `timing.json` and `reference_capture.gif` per deff.

**Deliverables:**
1. **IO:** switches (matrix plus dedicated D1-D24), coils with **decoded pulse and hold times**, lamps,
   flashers, aux-bus outputs. One CSV each, SAM numbers, no duplicate names. For every output, the
   in-game drive parameters (pulse ms, hold pattern or PWM, max on-time) from the ROM **and** a 1 ms
   measurement, per section 8.1.
2. **Fonts:** the font table as JSON (character ranges, glyph image id, x/y offset, height, spacing per font).
3. **Deffs:** one row per deff: priority, run length, background flag, hold, function address, screens
   (selector → draw calls with font or font list, flags, x, y, format string, argument sources), the
   lamp effects, tube shows and sounds it starts with their offsets, and its randomised parts with
   their RNG source.
4. **Lamp effects:** the lamp-matrix table with each effect's priority and lamp group; for code-drawn
   effects, the function and short pseudo-code. Lamp groups as named lists.
5. **Sounds:** call → samples, track (voice/sfx/music), loop flag, channel-stop calls. Export every stream.
6. **Settings:** adjustments (number, name, default, range, value labels, reader address), audits with
   their formulas, **all pricing tables**, and the service menu tree with every message text.
7. **OS model:** tick length, task id names, switch → hook order, show queue thresholds, deff rule and
   lamp rule lists. These made or broke trace matches.
8. **Traces:** one per mode, plus multi-player, tilt and slam tilt, every random branch (seeded or
   forced), and lamp and coil events in every trace. Name the RNG and say how a scenario forces it.
9. **Captures:** per deff, the arguments and RNG that produced it, one run only, and the status-panel
   region, so a rebuild can compare the rest dot by dot.
10. **Valid MPF YAML** (headers, unique keys) and a CI check that loads it with `mpf`.
11. **Board interfaces** (when hardware work is in scope): register map, interrupt schedule, lamp
    matrix map, switch scan and debounce counts, DMD and audio paths, peripheral boot setup, each
    number tagged code / emulator / hardware / scope / external (section 8.2).
12. **Model differences**: switch, coil and lamp maps side by side, per-model coil timing, and a
    function address map between the images (section 15).
13. **PinMAME numbering** for every switch, coil and lamp next to the SAM number, including the outputs
    PinMAME adds (fast-flip solenoid, lamps above 100), so a VPX table can drive the rebuild (section 10).
14. **Per-frame text draws** for every capture, or a text-free copy of each capture (section 7).
15. **Power and service behaviour**: coin door interlock masking, the power warning effect, what the OS
    does when the service menu opens during a game (section 8).

**Status on Tron:** every item in the MPF build's "missing data" list was then extracted from the ROM
into [rom_data/](rom_data/README.md) (commit 69fba72): fonts, deff text layout and screens, decoded
coils, lamp groups, code-drawn lamp effects, randomised parts and the RNG, pricing tables, service
texts, audit formulas and adjustment readers, hardware facts (tube sides, GI, D22/D23), the OS model, and
traces for multi-player, tilt and slam, match and Sea of Simulation stages 4-8. `rom_data/README.md`
maps each gap to its file and lists what is still open (for example lamp group names are inferred, the
tube sides are still worth one look on the real machine, and CUSTOM pricing was not captured). Where
`rom_data/` contradicts an older file, `rom_data/` wins.

---

## 15. Other models of the same game (Pro / Premium / LE)

Each model runs its own ROM image, built from the same source with different hardware tables and some
different rules. Once one model is done, the second is mostly a port. How Tron Pro 1.74 was done from
the LE in one session ([rules/tools/ghidra/pro/README.md](rules/tools/ghidra/pro/README.md),
[rom_data/pro/](rom_data/pro/README.md), [docs/PRO_VS_LE.md](docs/PRO_VS_LE.md)):

1. **Name tables first.** Both images use the same record formats (Tron: 24-byte name records, five
   language pointers then a zero word, entry 0 "INVALID"). Find the coil, lamp and switch name tables
   and descriptors in the new image and compare **by number**: that gives the IO map at once
   (`io/pro_vs_le_io_map.csv`). Expect switches mostly equal, several coils reassigned, and the lamp
   matrix renumbered almost completely.
2. **Port the function names.** Match functions by masked byte signatures (BL offsets and pc-relative
   load offsets masked), then propagate through pairs of BL targets, then add unique 20-byte
   signatures, and repeat until nothing is added (`fmatch.py`, `fprop.py`, `fextra.py`). Tron: 2,420 of
   3,938 LE seeds matched. RAM names come from literal pools at equal positions in matched functions.
3. **Re-run the decompile** with the new memory map (the OS size, and so the RAM base, moves; section 2)
   and the ported seeds, signatures and RAM symbols.
4. **Port the harness, not the scenarios.** Replace every address in the trace harness with its mapped
   address (`pro_hw_trace.cpp` from `hw_trace.cpp`) and run the same scenarios as the other PinMAME set.
5. **Pair call sites.** For coil timing, pair each call with the call at the same position in the
   matched function (`coil_calls_le_vs_pro.csv`: 105 of 198 paired). A matched name means the same code
   shape, not equal constants; leave pairings with unequal call counts unpaired.
6. **Check the owner's hypothesis directly.** On Tron it was "timings are the same, only the outputs
   move": confirmed by pairing and by a 1 ms emulator measurement on every Pro flasher.

What the Tron comparison found, as a hint for other games:
- The LE built all LE-only hardware unconditionally (no "is it fitted" check). "Disable" operator
  adjustments for broken mechs (Tron 76, 77, 80, 81, 86) are workarounds, not a hidden Pro mode.
- Outputs the cheaper model lacks are often reused as flashers there (Tron Pro 19/22/23/25), driven in
  the same effects with the same timing.
- A whole subsystem can be missing from one image (Tron Pro has no ramp tube driver, test or console
  commands), which is also a quick way to tell which model a capture came from.
- Hardware/software mismatch and country checks exist; document them only (ground rule 19).

## 16. Changing game behaviour: patch the binary

The decompile cannot be rebuilt (ground rule 16), so a behaviour change on the original hardware is a
binary patch:

1. Find the routine and its constants in the decompile (timers, targets, scores, which shots count),
   and confirm them in the disassembly; the decompile can hide or reorder code.
2. Change the ARM instructions or data in the image. Constants often sit in literal pools or data
   tables shared with other code: check every reader before changing a shared value.
3. Find whether the ROM verifies its own image (a checksum at boot or in diagnostics) and update it.
   This was not explored on Tron.
4. Prove the change in PinMAME with a reference trace before and after (section 9) before anyone flashes
   a machine.

Small changes (targets, timers, scoring, which shots count) fit this well. A new mode does not: it needs
free space, new display and sound effects wired into the existing tables, and is effectively a new
program. For that, a rebuild in MPF on the extracted assets and specs is the realistic route.
