# Display effects (deffs): table, text layout, screens, random parts

Source ROM: trn_174h.bin (Tron Legacy LE 1.74). Every fact carries a ROM address and a tag:
`observed` (seen in the emulator with rom_data/tools/deff_trace.cpp), `code` (read from the code
by the static walker, not seen running) or `inferred` (not used for any value in these files).

## Files

| file | rows | content |
|---|---|---|
| deffs.json | 146 deffs, 513 screens | table fields, screens with selectors, draws, images, timing, observed runs, random parts per deff; global `text_apis`, `rng`, `components` |
| text_draws.csv | 580 (452 observed, 128 code) | one row per text call site per deff (and per shared component) |
| font_lists.csv | 66 | every font list (0-terminated u32 list) used by a fit call or font picker, with its users |
| random_parts.csv | 102 (81 observed, 21 code) | one row per RNG call site x table entry / result |
| downstream_xcheck.csv | 360 draws + 22 table guesses | the mpfgame scripts/rom_layout.py layout guesses compared with these files |

## Deff table (deffs.json `deff_table`, per-deff `table`)

- Table at 0x040e1350, 146 records. The count comes from the table of tables at RAM 0x36c54,
  which holds {0x40e1350, 146, 8}.
- Each record is 8 bytes: u32 fn, u16 flags, u8 priority, u8 unused (always 0).
- Deff 0 is a null entry. Deff 22 is a stub. Deffs 10, 15 and 17 share fn 0x1000000.
- Starting a deff: `deff_start` 0x280b0(id, queue, force) calls 0x27b94(id, queue, force, 1).
  - The deff runs as task id 2.
  - Task fields: deff id at task+0x24, parameters at task+0x30..+0x44. Callers write the parameters after the start. When a start is queued, the queue ring at 0x3d540 (0x6c-byte entries) holds them and copies them in on dequeue.
  - Active deff state: id u16 at 0x381a8, priority at 0x381aa, flags at 0x381ab. The default (background) deff is at 0x381ae.
- Flag bits:

| bit | meaning |
|---|---|
| 0x1 | background/loop deff; stored in 0x381ae |
| 0x2 | replaceable at equal priority |
| 0x4 | no task flag 0x2000; only deff 27 has it |
| 0x10 | no page allocation; not used in the table |
| 0x20 | queue when blocked; not used in the table |

- Flag counts in the table: 0x2 = 113, 0 = 17, 0x1 = 15, 0x6 = 1 (deff 27).
- Run length:
  - `run.observed_forced_runs` lists each forced run: params, number of shows, first and last show, and when the deff ended.
  - `run.capture_timing_json` comes from media/dmd/<deff>/timing.json.
  - `screens[].timing` holds the frame and hold calls with their tick counts. The calls are deff_status_frames 0x10241a0 (N frames of 1 tick), deff_hold_frames 0x1024460 and anim_play 0x1023edc / anim_play_pal 0x1023fe4.
  - One tick is 16.26 ms.

## Text APIs (deffs.json `text_apis`)

| addr | name | layout |
|---|---|---|
| 0x28ca8 | text_draw_msg | r0 msg, r1 page, r2 font, r3 flags, [sp] x, [sp+4] baseline y, [sp+8] palette |
| 0x28d5c | text_printf_msg | same layout, varargs from [sp+0xc] |
| 0x28e48 | text_draw_msg_fit | r2 = font list, [sp+0xc] max_width; returns the font used |
| 0x28eb0 | text_printf_msg_fit | as 0x28e48, varargs from [sp+0x10] (3 callers) |
| 0x28f34 | text_draw_str_page | r0 = char* |
| 0x28f74 | text_draw_str | the core renderer; r1 = buffer 0x1080000 + page*0x1000 |
| 0x29174 / 0x29178 | text_printf_str_page | 0x29174 is `mov ip,r0` and falls into 0x29178; varargs from [sp+0xc] (10 callers) |
| 0x29248 / 0x2928c | text_draw_str_fit_page / fit core | (9 callers) |
| 0x28c1c | font_fit_msgs | (u16 msg list, font list, max width) |
| 0x28c6c | font_fit_str | (str, font list, max width) |

- 0x28c1c and 0x28c6c return the first font that fits, or 0 if none does.
- These have no callers in v1.74: 0x28d08, 0x28dd8, 0x291e4/0x291e8, 0x29384/0x29388.
- Formatting uses vsprintf 0x35fb0:
  - flags `+ , -`, width digits, `l`, and `ll` (takes 2 words);
  - conversions d/i/u/x/X/s;
  - `%P<base>/opt/.../%` is a plural/ordinal selector that consumes 1 argument.
- Text flags (rom_data/fonts.json): 1 = from x, 2 = centred on x, 4 = right-aligned at x.
- Fit rule (0x2928c):
  - If max_width != 0, it takes the first font whose text width is <= max_width.
  - Otherwise flags&1 needs x+w <= 128, flags&2 needs x-w/2 >= 0 and x-w/2+w <= 128, and flags&4 needs x-2w >= 0.
  - If no font qualifies, it uses font 0.
- Language:
  - language_get is 0xa3b4 / 0xa424. It returns 0..4, from the RAM 0x372a0 override or else NVRAM 0x2102038.
  - Per-language font tables are indexed by lang*4. The text uses English (language 0).
  - When a font, msg or list depends on the language, `notes` lists the values for languages 0-4.

## text_draws.csv

- Required columns:
  - `deff`: the deff id, or `status_panel` for the shared panel 0x10230ec used by many deffs.
  - `screen`, `call_site` (address of the bl), `api`.
  - `msg_id` and `format` (English).
  - `font`, or `font_list` (`addr=f1,f2,..`).
  - `flags`, `x`, `y` (baseline), `max_width`.
  - `args`: a JSON list of {order, conversion, source, ram_addr, name, meaning}.
  - `tag`.
- Extra columns:
  - `function`, `path` (the call chain from the deff function) and `api_addr`.
  - `text_value` (the string source for str APIs), `color` (the palette description) and `page`.
  - `selector`: the path condition under which this site draws.
  - Observed values: `observed_n`, `observed_strings`, `observed_font`, `observed_flags`, `observed_xy`, `observed_font_list`.
  - `notes`: font pickers, per-language values, English evaluation of y expressions, and hand-resolved tables.
- Values the code computes from font heights or fit choices are evaluated for English with fonts.json, and the note says so.
  - Example: y = font_height(15) + (32 - font_height(15))/2 - 1 = 20.
  - 49 rows still have a symbolic value for font, x or y. These are loop variables, runtime strings measured by text_width, or record fields. Most of them are observed, so `observed_*` gives the values.
- The score of deff 19 (site 0x1023994) takes its font and y from the score-size table. RAM 0x370ac points to ROM 0x40d3484, a list of 20-byte records {min score, font, y, band top, band bottom}:

| score | font | y |
|---|---|---|
| >= 100,000,000 | 22 | 18 |
| >= 1,000,000 | 17 | 18 |
| >= 100,000 | 24 | 21 |
| below 100,000 | 26 | 21 |

  Each value was confirmed by poking gf_scores 0x21109e4.

## Screens (deffs.json `deffs[].screens`)

- A screen is identified by (function, path condition set). Each screen has:
  - `selector`: a list of {expr, ram_addrs, task_fields, functions}.
  - `draws`: keys into text_draws as `deff:site`.
  - `images`: bitmap_draw 0x2b378/0x2b424 and anim_play, with image ids, x/y, palette and the observed image ids.
  - `timing`.
- Selectors are path conditions from the symbolic walker (rom_data/tools/deff_sym.py):
  - comparisons of RAM, task+0x30.. parameters and call results;
  - switch-table cases (`== k`);
  - `indirect table entry k` for function-pointer tables indexed by an RNG.
- Deff 1 (attract) walks attr_page_table at RAM 0x36e10 (initial values in the ROM), as {cond_fn, page_fn} pairs until page_fn == 0. Pages run as child tasks with task+0x30 = the pass number. `attract_pages` lists them.

## Random parts (random_parts.csv, deffs.json `rng`)

- RNG state is the u32 at RAM 0x372c4. The functions:

| addr | name | result |
|---|---|---|
| 0xc684 | lcg_next | state = state*0x19660d + 1 |
| 0xc6b4 | random_below(n) | (n*lcg) >> 32 |
| 0xc6d4 | random_percent(p) | 1 when 1 + ((lcg*100) >> 32) <= p |
| 0xc708 | bag_weighted_pick | weighted pick |

- Seeding: the state is seeded with 0x04277dc9 at boot (0xc668, called at 0x7b10). The boot decrypt code reseeds it (0xc674).
- The main loop advances the state once per pass (0x34098). So a scenario cannot pick a value by poking 0x372c4.
- **How to force a branch:** hook the return of random_below (pc 0xc6d0) or random_percent (pc 0xc704). Set r0 when the saved lr at [sp+4] is the call site + 4.
  - deff_trace.cpp does this with `-rng <site+4>=v1,v2,..`. A value list is used in order, one per call.
- Every deff RNG site is listed, with the table it indexes and each entry resolved to its clip (first..last image, ticks per frame) or award.
  - Clip tables: 48/49 (0x40d2804, 12 clips), 68 (0x40d327c, 3), 69 (0x40d3288, 2), 97 (0x40d6fd4, 2), 111 (0x40d337c, 11).
  - 108 uses a switch with 4 clips.
  - 116-124 use helpers FUN_01027374 (rand(2) over 0x40d3980) and FUN_01027478 (rand(1) over 0x40d3990).
  - 87 calls percent(50) and 90 calls percent(20); each picks a speech call.
  - 38: the spinning match digits.
  - 96: the position of the floating "%luK" text.
  - 105 (mystery award): the cabinet image per slot is 0x40d2990[rand(4)]; the decoy awards are rand(13)+1; the slot of the real award is rand(3). The award table 0x40d29a0 holds 16-byte records {u16 id, u16 0, u32 lit icon, u32 unlit icon, u32 fn}.
- The sound sample choice (0x2c7f8, called from snd_resolve_call 0x2c7fc) also draws from the same RNG. Every deff that plays a sound call with several samples therefore advances the state.

## Method

1. **Static.** deff_static.py walks each deff function with a symbolic ARM interpreter (deff_sym.py, capstone). It:
   - follows bl, tail calls, task_create/spawn/exit-handler pointers, `mov lr,pc; ldr pc,[..]` tables and `ldr pc,[pc,rX,lsl #2]` switch tables, up to depth 9;
   - substitutes arguments into callees, and records every text, image, timing and RNG call with its path condition.
   Output: static.json in the work directory, about 6 s.
2. **Dynamic.** deff_trace.cpp is built on mpf_package/tools/tracer.cpp.
   - It injects deff_start(id, 0, 1) through the task_sleep 0xb91c hijack during a running game, with a ball in the shooter lane.
   - It writes parameter words into task+0x30.. and logs every text API, the core renderer 0x28f74 (string, font, flags, x, y, palette), the fit core 0x2928c, font pickers, the RNG (with forcing), image and anim draws, sleeps, and shows.
   - deff_obs.py parses the logs, and deff_build.py merges static and observed data into these files.
   - Runs: A/B (every deff forced, in game); C (RNG forcing of every branch); D (parameter variants: 38, 48, 60, 64, 68, 69, 80, 85, 87 levels 1-5, 88, 89, 91, 92, 105 awards 1-12, 112 kinds 1/2/4, 116, 130, 133, 138, 140, and 4); E (420 s of simulated play, seed 7: the tracer.cpp ball simulation with trough, shooter, scoop, random shots and drains; 48 deffs seen); F (attract, 100 s); G (27, 25, 14 with long holds); H (deff 19 with score pokes).
3. **Cross-check.** deff_xcheck.py compares the downstream rom_layout.py guesses with these files and writes downstream_xcheck.csv.
   - All 360 unique downstream draws are present here; 349 match and 11 differ.
   - All 7 differences are font lists the downstream guessed shorter than the ROM list. 6 of them still give the same English font. The exception is deff 99's total: the ROM list 0x40d6ff4 is 16,13,11,7,1 and the observed font is 16, while the downstream guessed 15,12,2.
   - All 13 FONT_TABLES guesses match the ROM English entries.

Rebuild:
```
python3 rom_data/tools/deff_static.py /tmp/.../static.json
python3 rom_data/tools/deff_obs.py obsX.json runX.log            # per run
python3 rom_data/tools/deff_build.py static.json obsAB.json obsC.json obsD.json obsE.json obsF.json obsG.json obsH.json
python3 rom_data/tools/deff_xcheck.py
```
Build the harness with
`g++ -O2 -std=c++17 -I/home/claude/pinmame/src/libpinmame rom_data/tools/deff_trace.cpp -L/home/claude/pinmame/build -lpinmame -lpthread -Wl,-rpath,/home/claude/pinmame/build -o deff_trace`. Run it with `PINMAME_NOJIT=1 deff_trace LOG force|play [-rng SITE+4=V,..] [-poke ADDR=VAL[:SZ]] [-hold SEC] [-nogame] ID:w30:w34:..`.

## Open items

- **Deff 45** never ran. It needs task 0xa3 running (FUN_0102e608 = task_running(0xa3)), which is the video-mode path and dead in normal play. Its 21 rows are `code`.
- **Deff 22** is a stub, and deff 0 is a null entry.
- **Deff 27** (instant info) has 35 `code` rows. Its pages advance on flipper presses, which the harness does not simulate. Only the INSTANT INFO title was observed.
- **Deff 1:** 20 attract-page rows are `code`. These pages did not come up in 100 s of attract mode (tournament and other conditional pages).
- **Deffs 32 and 33** (initials entry) need real initials-entry pointer parameters. Forcing them with dummy pointers drew garbage, so only the static rows plus the observed shared helpers 0x33cb8/0x33e18 are given.
- **Deffs 3, 25, 14, 65, 47, 55 and 141** have a few branches that the parameters and game state of these runs did not reach. Those rows are `code`.
- **Deff 96:** the floating-text RNG runs in child task FUN_01032900, spawned per hit. No hit happened while it was forced, so its 3 RNG rows are `code`.
- **Unresolved values:** 49 rows keep a symbolic font, x or y. These are loop variables, runtime strings measured by text_width, or record fields.
- **Other languages:** only English text and fonts are resolved. The per-language values are in `notes`.
- **Task flag 0x2000**, which 0x27b94 sets when flags & 5 == 0, is not decoded.
