---
name: tron-rules-extraction
description: Tron rules rebuild docs for the MPF dev: cleaned decompile v2, tron_ref trace recorder, mode specs in tron/rules (2026-10-02)
metadata:
  type: project
---

Thread "Rebuild Tron rules for MPF". Vincent (2026-10-02): write specs only, NOT MPF config (another agent builds MPF/Godot); docs must be human readable and detailed enough that the MPF dev never guesses. Flynn's Arcade is a mystery award at the VUK (sw11), not a video game.

Outputs (/mnt/project-files/tron/):
- code/tron_game_decompiled_v2.c: Ghidra re-run with 166 OS signatures (rules/work/os_api.json), RAM as globals, phantom +4 functions dropped, comments decoding sounds/msgs/adjs/audits/lamps. Pipeline + scripts in rules/tools/ghidra (seeds_named.tsv names, ram_symbols.tsv labels if present).
- rules/tools/trace: tron_ref.cpp (libpinmame + ARM hook patch; deterministic, fresh NVRAM per run), trace_compare.py, README (format, scenario commands).
- rules/modes/*.md per feature (template rules/work/TEMPLATE.md, brief rules/work/AGENT_BRIEF.md), rules/traces/, rules/work/ram/*.tsv.
- rules/work/asset_audit.md: errors in mpf_package (deff 105 = arcade award, duplicate yaml keys, 17 unexported streams, lamp-matrix leffs 0x040e23e4 never exported; package leff_NNN are ramp tube shows).

Status 2026-10-02: DONE. Entry point rules/README.md -> rules/developer_guide.md (conventions, wiring, feature index, adjustments, media fixes, verification). 21 mode specs + ~60 reference traces. Daft Punk MB = End of Line MB. Dead code in 1.74: LC maze video (deff 45), Quorra all-jackpots-doubled, deffs 22/93/110/127/128/129. tron_ref polls coils 1-39 (OnSol callback misses 1-32); `button left` while plunging = skill shot B. Open questions in each mode file section 11.

Facts: score_add 0x2340c (x mult RAM 0x38180); 0x87ac = lamp leff_start, 0x0101b824 = tube show; error_log 0x5ac8 (not fatal); 1 tick ~16.26 ms; current player RAM 0x3817c, scores 0x21109e4; lamp numbers in libpinmame = lamps.csv numbers.
Build env (container is ephemeral): Ghidra 11.4.2 zip + git clone vpinball/pinmame work from GitHub.

Related: [[tron-rom-format]] [[tron-dmd-mpf-package]] [[tron-io-lighting]]
