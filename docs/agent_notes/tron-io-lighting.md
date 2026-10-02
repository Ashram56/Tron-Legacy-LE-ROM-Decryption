---
name: tron-io-lighting
description: Tron ROM IO map - register pointer block, coil/lamp tables, dedicated ramp light tube (RGB aux bus) driver addresses
metadata:
  type: project
  modified: 2026-10-01T14:49:26.118Z
---

Found 2026-10-01 (thread "IO controls / fiber optics"). Outputs in /mnt/project-files/tron/io/ (README.md, io_registers.csv, coils.csv, lamps.csv, light_tube_calls.csv).

- The extra RGB lighting is a dedicated driver called the "ramp light tube" in the ROM (console cmds lrlt/rrlt). Left obj RAM 0x3b1d8 on CSTB (0x10), right obj 0x3b504 on DSTB (0x20); RGB = AUX_DRV bits 5/4/3, 4-bit BCM. API: 0x7cc set(obj,rgb[3]), 0x800 fade(obj,rgb[3],ms), 0x7a0 set_rgb(obj,r,g,b); refresh 0x874 each 250us IO tick via 0x100f0a4.
- IO register pointers live in a RAM block 0x37280-0x37350 (e.g. 0x372c8 -> AUX_DRV 0x02400026, 0x372d0 -> 0x0240002B, 0x37334 -> table of SOL_B/A/C/FLSH). The IO interrupt ends at 0x13420.
- Coil name table 0xe0c00 (24-byte records), coil descriptors 0xe0f78 (28-byte records); lamp names 0xe2bf4. Coil shadow bytes 0x3b97c[0..4] (byte 4 = aux coils 33-40 via ESTB).
- Vincent's schematic analysis (github.com/Ashram56/Stern-SAM-Databus-Analysis) names strobe bits bit3=ASTB, bit4=ESTB, bit5=DSTB, bit6=CSTB, bit7=BSTB, which is the reverse of PinMAME. On that basis the left tube (0x10) is ESTB on J3 pin 12 and the right tube (0x20) is DSTB on J3 pin 11. He calls these the 'fiber optics'. PinMAME's left/right labelling disagrees with the ROM console.

Related: [[tron-rom-format]]

Light effects (leffs, added 2026-10-01): leff_start 0x101b824, leff_stop 0x101baac. The table is at 0x040e3c88 (106 x 12 bytes: fn, flags, tube mask 1=L 2=R 3=both, prio) and is listed in the table-of-tables at RAM 0x36ce4 (entry 7; the deff table is 0x040e1350). Each leff was emulated with unicorn (hooks on 0x7cc/0x800/0x7a0 and task_sleep 0xb91c, tick 16 ms) into MPF shows at tron/io/mpf/shows/leff_NNN.yaml, with tron/io/light_effects.csv mapping each leff to its deff and mode. Vincent is recoding the game in MPF, and a separate thread, "Build Tron MPF asset package", assembles the package.
