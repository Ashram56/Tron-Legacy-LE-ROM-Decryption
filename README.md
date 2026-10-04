# Tron-Legacy-MPF

Everything needed to rebuild **Stern Tron Legacy Limited Edition, code v1.74** (PinMAME set
`trn_174h`, SAM hardware) in the Mission Pinball Framework (MPF), as close to the original as possible:
rules, sounds, DMD animations, lamp and flasher effects, ramp light tubes, shaker, service menu and
operator settings.

All of it was reverse engineered from the original ROM image (`trn_174h.bin`, SHA1
`40e36764af332175f653e8ddc2a8bb77891c1230`) by reading the decompiled code and running the ROM in a
patched PinMAME. The ROM image itself is not in this repository.

## If you are the agent building the MPF game, start here

1. **[rules/README.md](rules/README.md)**, then **[rules/developer_guide.md](rules/developer_guide.md)**.
   These describe how the game plays: conventions (timing, scoring, what resets when), how the
   features are wired together, the feature index and the operator settings.
2. **[rules/modes/](rules/modes/)**: one spec per feature (21 features plus a Daft Punk companion
   page), each with start conditions, per-switch behaviour, scores, timers, display, sound and lamp
   cues, how it ends and open questions. Build each mode from its spec.
3. **[mpf_package/README.md](mpf_package/README.md)**: the ready-made MPF config and media
   (switches, coils, lights, sounds and sound pools, DMD slides and shows, lamp effects, shaker,
   settings, game flow) and how to wire them in.
4. **[mpf_package/service_menu.md](mpf_package/service_menu.md)**: the original service menu tree,
   all 88 adjustments with their values, install presets and the 150 audits.
5. **Check your build against the real game** with the reference traces in
   [rules/traces/](rules/traces/) and the compare tool in [rules/tools/trace/](rules/tools/trace/README.md)
   (see section 7 of the developer guide).

When a spec and the package disagree, the spec in `rules/` wins on rules; the package wins on
media and names (it was corrected after the specs were written, see "Known gaps" below).

## Layout

| Path | What it is |
|---|---|
| [rules/](rules/) | Full game rules read from the ROM: developer guide, 21 mode specs, reference traces (`traces/*.txt` scenarios and `*.jsonl` real-ROM output), trace and Ghidra tools, RAM variable maps and OS API (`work/`) |
| [mpf_package/](mpf_package/) | MPF config (`config/`), media (`media/sounds`, `media/dmd`, `media/dmd_library`, `media/rom_images_all.zip`), data maps (`event_map.csv`, `lamp_effects.csv`, `animation_map.csv`, `service_menu.json`) and the extraction tools |
| [io/](io/) | IO controls: coils, lamps, IO registers, and the ramp light tube (fiber optic) driver with its effect table and call sites; `io/mpf/` is the original tube-show export (the same shows are in `mpf_package/config/shows/leff_NNN.yaml`) |
| [callouts/](callouts/) | First-pass sound analysis: every sound call, the samples it picks from, and which switches or modes trigger it (`switch_sound_map.csv`, `callout_triggers.csv`, `sound_calls.csv`, `samples_index.csv`, `switch_names.json`) |
| [code/](code/) | Ghidra pseudo-C of the whole game: `tron_game_decompiled_v2.c` is the annotated one to use (named functions and RAM variables, decoded sound/message/lamp/deff comments); `tron_game_decompiled.c` is the older first pass and mislabels some functions |
| [rom_data/](rom_data/README.md) | Machine-readable ROM data added 2026-10-04: fonts, deff text layout and screens, decoded coils, lamp groups, code-drawn lamp effects, RNG, pricing, service texts, audit formulas, hardware facts, OS model and late-state traces. Wins over older files where they disagree |
| [AGENTS.md](AGENTS.md) | Reusable guide for agents reverse engineering any Stern SAM ROM: methods, tools, table layouts, and the mistakes made on this one (Tron values as worked examples) |
| [docs/agent_notes/](docs/agent_notes/) | Condensed notes the agents kept while working: ROM format (memory map, image and sound formats), DMD capture method, IO and lighting, lamp effects/shaker/service capture, rules extraction |
| [docs/PRO_VS_LE.md](docs/PRO_VS_LE.md) | Tron Pro 1.74 vs LE 1.74: switch, coil, lamp and aux differences, rule and adjustment differences, Pro table addresses (`io/pro_vs_le_io_map.csv`, `io/le_vs_pro_io.csv`) |

### Paths inside the documents

The documents were written in a shared folder where this repository's root was called `tron/`.
Read `tron/X` as `X` from the repo root. Two moves were made when assembling the repo:

- `tron/README.md`, `tron/*.csv` and `tron/switch_names.json` are now in `callouts/`.
- `tron/samples/{speech,sfx,music}/XXXX.wav` were dropped as duplicates. The same files (plus 17
  streams decoded later) are in `mpf_package/media/sounds/{speech,sfx,music}/XXXX.wav`, so a
  `samples/...` path in `callouts/*.csv` means `mpf_package/media/sounds/...`.

## Key facts for the rebuild

- **Hardware numbering.** Switch, coil and lamp numbers are the original SAM ones. Map them to your
  controller. The ramp light tubes are on the IO board's aux bus, not in the lamp matrix (`io/README.md`).
- **Sounds.** Each ROM "sound call" picks one sample from a list; MPF gets one sound pool per call
  (290 pools). Speech is 12 kHz mono, sfx and music 24 kHz mono.
- **Two light-effect systems.** "leff N" in the specs is the lamp-matrix table (171 effects,
  `config/shows/lampfx_NNN_*.yaml`, events `tron_lampfx_*`); "tube show N" is the ramp tubes
  (`config/shows/leff_NNN.yaml`). Display effects already start their lamp effect and tube show.
- **Flynn's Arcade is a mystery award** at the VUK scoop (switch 11), not a video mode.
- **Daft Punk Multiball and End of Line Multiball are the same mode.**
- **Some code is never reached in v1.74** (for example the Light Cycle maze video mode, deff 45).
  The list is in section 4 of the developer guide. Don't build these.
- **This is the LE code.** The Pro 1.74 uses a different IO map (T-R-O-N standups, no Recognizer
  motor, no ramp tubes, renumbered lamps). See [docs/PRO_VS_LE.md](docs/PRO_VS_LE.md).
- **Starting a game in the emulator** needs trough switches 18-21 held closed (ball count check).

## Known gaps and open questions

- `rules/work/asset_audit.md` was written before the package updates of 2026-10-02. These findings
  are **fixed** in this `mpf_package`: deff renames (22, 105, 111, 127, 128, 129), duplicate
  TRON/ZUSE/CLU switch and lamp names (now `s_tron_t`, `l_tron_n`, ...), the 17 missing audio
  streams (now decoded, 290 pools), deff 108's four clip variants, and the lamp-matrix effects
  (now exported). The audit now marks each of these **RESOLVED**, and section 6 of
  `rules/developer_guide.md` was rewritten to match.
  The `mode_by_code_location` column was removed from `event_map.csv`; the remaining location-based
  guesses (`feature_guess_by_code_location` in `callouts/callout_triggers.csv`,
  `mode_guess_by_code_location` in `io/light_effects.csv`) are unreliable, so use the mode specs.
- **Naming:** `leff_NNN` shows in `mpf_package/config/shows/` and `io/mpf/shows/` are **ramp tube shows**
  (table 0x040e3c88), not lamp-matrix leffs; the lamp-matrix effects are `lampfx_NNN_*`. The names are
  kept because the MPF repo pins these paths.
- Every generated MPF config file now starts with `#config_version=6` (shows with `#show_version=6`).
- **Data the MPF build had to recover or guess** (from its feedback, 2026-10-04; not extracted here yet):
  the font table (RAM 0x36f48), per-deff text layout and argument sources, per-deff screen selection,
  decoded coil pulse/hold times (coil table 0xe0c00), named lamp groups (0x040e3acc), pricing tables other
  than USA 10, a few service texts and audit formulas, and multi-player / rare-state traces.
  See section 14 of [AGENTS.md](AGENTS.md).
- Display effects not captured: 27 (instant info, needs flipper buttons held) and 45 (no caller in
  v1.74). 24 library animations are never referenced by v1.74 code (likely unused).
- Lamp effects: 34 are empty in v1.74 and 7 draw from live mode state, so they are not shows; your
  modes must drive those lamps (see `mpf_package/lamp_effects.csv`).
- `config/shaker.yaml` gates shows with `{settings.shaker_motor>=N}`; whether MPF allows settings in
  show conditions is unverified. If not, gate the shaker in code.
- `config/settings.yaml` loads as YAML but was not run in MPF. Difficulty presets are empty in v1.74.
- Whether the ROM loops music beds was not verified.
- Ramp tube colours computed at runtime show as `?`, and which mode picks ambient tube effects 1-9
  was not traced (`io/README.md`).
- Physical timing (ball save, orbits, motors) was checked against code, not a real machine. A few
  rare states (Sea of Simulation stages 4-8, match odds, slam tilt) and multi-player behaviour were
  read from code only. Each mode spec ends with its own open questions.
- Each fact is marked **observed** (emulator), **code** (decompile) or **inferred**. Check
  inferred ones before relying on them.

## Rebuilding the analysis

The tools that produced everything are included: `mpf_package/tools/` (PinMAME ARM hook patch,
`tracer.cpp`, `lfx.cpp`, `fmt.cpp`, image and ADPCM decoders, build scripts) and `rules/tools/`
(`tron_ref.cpp`, `trace_compare.py`, Ghidra scripts). They need your own copy of `trn_174h.bin`.

Related: Vincent's SAM data bus analysis, https://github.com/Ashram56/Stern-SAM-Databus-Analysis
