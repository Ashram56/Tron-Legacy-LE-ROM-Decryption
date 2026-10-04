---
name: tron-lampfx-shaker-service
description: Tron MPF package 2026-10-02c: lamp-matrix effects (lampfx shows), flashers, shaker, service menu and 88 settings; how they were captured
metadata:
  type: project
  modified: 2026-10-02T18:59:06.305Z
---

Vincent (2026-10-02): wants the MPF recreation "as close as possible to the original, including lamp effects, shaker effects, etc." and a service menu offering every original option (UI may differ). Shipped as tron/mpf_package_update_2026-10-02c.zip (file list in mpf_package/UPDATE_2026-10-02c.txt), per [[vincent-update-zips]].

- Lamp effects (table 0x040e23e4, 171 entries, leff_start 0x87ac): captured with tools/lfx.cpp. It injects leff_start via the task_sleep hijack, reads the leff layer each compositor tick (0x7f68): leff image 0x3c224/mask 0x3c238 for group leffs, plus layers in list 0x3728c (img +0..0x13 two planes, mask +0x14, owner task +0x20, next +0x24) owned by a task with flag 0x20 and id at +0x28. It also logs coil_pulse 0x6970/0x69c0 (flashers) from leff tasks. Flasher-only effects need a validated playfield ("pf" mode); many also pause while task 0x2b runs.
- Outputs: config/shows/lampfx_NNN_*.yaml (130), lamp_effects.csv, config/lamp_effects.yaml (events tron_lampfx_*), and 53 deff shows start their lampfx at 0 ms. 17 effects take a lamp param (+0x30, token (lamp)), 4 take a lamp group (token (lamps), tags rom_group_N in lights.yaml). 34 are empty in v1.74 and 7 draw from mode state (not shows). Rule leffs come from leff_rule_init(obj, list, cond_fn, leff_id), meaning "run while cond".
- Shaker: shaker_run(strength, min_setting) at 0x10289b8, gated by adj 86. Strength 1/2/3 is 200/384/1024 ms on coil 8 (table 0x040d3998; the earlier 75/265/1100 ms came from 5 ms polling and was wrong, corrected 2026-10-04). Setup: config/shaker.yaml with conditional show_player `{settings.shaker_motor>=N}`; MPF support for settings in conditions is unverified.
- Service: menu items are at 0x040f4574 (20 B: vis fn, action fn, screen fn, msg u16, id, submenu) and menus at 0x040f5108 (12 B, +8 = u16 item list). Adjustments are at 0x040de218 (32 B: nvram, default, min, max, step, ?, name ptr, display type), with formatters at 0x040dd890 (fn or u16 msg list). Labels came from running the formatters in the emulator (tools/fmt.cpp). Standard adjustment order is at RAM 0x39558. Install preset lists hold (adj, value) pairs. In v1.74 the difficulty presets are empty. Outputs: config/settings.yaml, service_menu.md/json.
