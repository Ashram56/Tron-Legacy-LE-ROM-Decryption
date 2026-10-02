# Tron Legacy LE 1.74: game rules, read from the ROM

This folder documents the complete rules of Stern's Tron Legacy Limited Edition, code 1.74
(PinMAME `trn_174h`). It is written for the developer rebuilding the game in MPF/Godot, and for
anyone who wants to know how the real game behaves. Every rule was read from the ROM code and
checked by running the real ROM in an emulator.

## Where to start

1. **[developer_guide.md](developer_guide.md)** covers the conventions (timing, scoring, what resets
   when), how features are wired together, the feature index, the operator settings, the media
   corrections and how to check the rebuild against the real game.
2. **[modes/](modes/)** has one file per feature (21 features plus a Daft Punk companion page). Each
   file has the same sections: how it starts, what each switch does, scores, timers, display, sound
   and lamp cues, how it ends, and open questions.
3. **[work/asset_audit.md](work/asset_audit.md)** lists the mistakes in the asset package
   (`tron/mpf_package`). Read it before using any of that package's config.

## Facts that change how you build it

- **Flynn's Arcade is a mystery award** at the VUK scoop (switch 11), not a video mode. Display
  effect 105 is its award reveal.
- **Daft Punk Multiball and End of Line Multiball are the same mode.** Build it once.
- **Some code is never reached in 1.74**, for example the Light Cycle maze video mode and Quorra
  "All Jackpots Doubled". The full list is in section 4 of the guide. Don't build these.
- **There are two light-effect systems:** 172 lamp-matrix effects ("leff N" in the specs) and the
  ramp tube shows ("tube show N"). The asset package only exported the tube shows.

## Other folders

| Folder | Contents |
|---|---|
| [traces/](traces/) | Scenario scripts (`.txt`) and what the real ROM did for each (`.jsonl`) |
| [tools/trace/](tools/trace/README.md) | `tron_ref` (runs the real ROM from a scenario) and `trace_compare.py` (finds the first difference with the rebuild) |
| [tools/ghidra/](tools/ghidra/) | Scripts that produce the annotated decompile |
| [work/](work/) | Supporting data: OS function names (`os_api.json`), RAM variable maps (`ram/`), the spec template |
| `../code/tron_game_decompiled_v2.c` | Annotated pseudo-C of the game code, with named functions and RAM variables |
