# rom_data: machine-readable ROM data for the MPF rebuild (Tron Legacy LE 1.74)

Added 2026-10-04 in answer to the MPF build's feedback ("missing data the build had to recover or
guess", section 2, and the deliverable shapes in section 4). Everything here was read from
`trn_174h.bin` (code, tables) or seen in the patched PinMAME. Every row carries the ROM address it came
from and a `tag`: **observed** (emulator), **code** (code or table), **inferred** (reasoning; check it).

Nothing in the rest of the repo was moved or edited. Where these files contradict an older file, the
area README says so, and these files win on the data they cover.

## Where each gap is answered

| # | Gap in the feedback | File(s) | Status |
|---|---|---|---|
| 1 | Font table (ranges, glyph offsets, height, spacing) | [fonts.json](fonts.json) | Done, code: 44 fonts from RAM 0x36f48 |
| 2 | Deff text layout and argument sources | [deffs/text_draws.csv](deffs/text_draws.csv), [deffs/font_lists.csv](deffs/font_lists.csv), [deffs/deffs.json](deffs/deffs.json) | 580 draws, 452 observed; all 360 downstream draws covered |
| 3 | Screen selection per deff | [deffs/deffs.json](deffs/deffs.json) (`screens`, `selectors`) | 146 deffs, 513 screens |
| 4 | Coil pulse/hold times, `desc_flags` decoded | [io/coils.csv](io/coils.csv), [io/coil_rules.json](io/coil_rules.json), [io/coil_calls.csv](io/coil_calls.csv), [io/coil_observed.json](io/coil_observed.json) | Done; times measured at 1 ms resolution |
| 5 | Lamp groups | [io/lamp_groups.json](io/lamp_groups.json) | 109 groups; names inferred |
| 6 | Code-drawn lamp-matrix leffs | [io/leff_table.csv](io/leff_table.csv), [io/code_leffs.md](io/code_leffs.md) / `.json`, [io/lamp_rules.csv](io/lamp_rules.csv) | 58 code-drawn leffs with pseudo-code |
| 7 | Randomised deffs and RNG | [deffs/random_parts.csv](deffs/random_parts.csv), RNG in `deffs/deffs.json` and [states/os_model.md](states/os_model.md) | 102 rows, each branch forced |
| 8 | Frozen status panel, two runs per capture | `deffs/deffs.json` (status panel draws, forced runs) | Partly: the panel is now drawn from the data |
| 9 | Pricing tables | [settings/pricing.json](settings/pricing.json), [settings/pricing.csv](settings/pricing.csv) | 64 presets + CUSTOM, credit algorithm |
| 10 | Service texts, audit formulas, adj readers | [settings/service_texts.csv](settings/service_texts.csv), [settings/audits.csv](settings/audits.csv), [settings/adjustments.csv](settings/adjustments.csv), [settings/adjustment_readers.csv](settings/adjustment_readers.csv), [settings/presets.csv](settings/presets.csv) | Done (msg 0x113/0x114, audits 11/13/72, adj 25 resolved) |
| 11 | Tube strobe side, GI polarity, D22/D23 | [states/hardware_facts.md](states/hardware_facts.md) / `.json`, [states/dedicated_switches.csv](states/dedicated_switches.csv) | Done from the ROM; tube side still to confirm on the machine |
| 12 | Multi-player, tilt/slam, SoS stages 4-8, match | [states/](states/) `.md` + `.json` per topic, [states/traces/](states/traces/) | 11 reference traces |
| OS model (section 4 item 7) | Tick, task ids, event/hook order, deff queue, rule lists | [states/os_model.json](states/os_model.json) / `.md` | Done |

Each area has its own README with every field, the method and what is still open:
[deffs/](deffs/README.md), [io/](io/README.md), [settings/](settings/README.md), [states/](states/README.md).

## Headline facts (details and addresses in the area files)

- **Fonts.** Record (20 B): `+0` char-range list, `+4` glyph table (8 B: image ptr, s16 x off, s16 y off),
  `+8` height, `+0xa` spacing, `+0xc` masked, `+0x10` bank. Glyph drawn at `(pen + xoff, y - h + yoff + 1)`,
  pen += `w + xoff + spacing`. Fonts 27-32 are images 2175-2240, not the image group after font 26.
- **Deff 19 score size** comes from table 0x40d3484: >= 100M font 22 y 18, >= 1M font 17 y 18,
  >= 100K font 24 y 21, else font 26 y 21.
- **RNG**: LCG at RAM 0x372c4, `x = x*0x19660d + 1`, `random_below(n) = (n*x) >> 32` (0xc6b4), seed
  0x04277dc9, advanced every main-loop pass, so force results by hooking the call return, not by poking.
- **Coils**: driver runs every 1 ms. Flippers (table 0x040e204c) 40 ms pulse then hold 1 ms on / 11 ms
  off; bumpers 32 ms; slings 32 ms; knocker 80 ms; coil test 64 ms. Shaker strengths are 200 / 384 /
  1024 ms (table 0x040d3998), not 75 / 265 / 1100 as the package says.
- **Pricing**: USA 10 = 3 quarters per credit. **Adj 25 FREE GAME LIMIT is never read by game code.**
  Audits 13 and 72 always show 0. Adj 10 PLAYER LANGUAGE SELECT defaults to YES for USA.
- **Tubes**: strobe 0x10 = left ramp, 0x20 = right ramp (ROM console, service test labels and skill
  shot shows agree; PinMAME's labels are the reverse and unsourced). **GI**: bit 0 of 0x0240002B,
  active low, on from power-up. **D22 = Minus, D23 = Plus.**
- **Multi-player**: game flags and lamps are saved/restored per player (except flags with descriptor
  bit 0 and lamps 26/65/66). **Match**: number = random(10)*10; above adj 30's percentage the draw is
  stepped until nobody matches. **Slam**: resets the machine after 311 ticks; credits survive.
- **Sea of Simulation**: stage 6 needs all six shots; completion is deff 126 (deff 125 is never started).

## Regenerating

All scripts read the ROM from `TRON_ROM` (default `/mnt/project-files/trn_174h.bin`); the ROM is not
in this repo. `tools/rom.py` is the shared reader. Python: `fonts.py`, `deff_build.py` (after
`deff_static.py` / `deff_obs.py`), `hw_*.py`, `settings_extract.py`, `states_build.py`. The `.cpp`
harnesses link the patched libpinmame (see `rules/tools/trace/README.md` for the build) and run with
`PINMAME_NOJIT=1`: `deff_trace.cpp` (forced deffs, text/RNG hooks), `hw_trace.cpp` (1 ms coil
timing), `settings_emu.cpp` (coins, audits, formatters, country), `states_ref.cpp` (tron_ref plus
coin-door keys, GI/RNG/event tracing, watchdog reset).
