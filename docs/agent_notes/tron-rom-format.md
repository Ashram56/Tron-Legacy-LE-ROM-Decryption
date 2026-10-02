---
name: tron-rom-format
description: Reverse-engineered layout of Stern Tron Legacy LE 1.74 ROM (trn_174h.bin) - sound tables, ADPCM format, switch/deff/audit tables, emulator setup
metadata:
  type: project
---

ROM (2026-10-01): /mnt/project-files/trn_174h.bin = PinMAME trn_174h, Tron Legacy LE v1.74, SAM/ARM7. Outputs in /mnt/project-files/tron/ (README.md lists them).

Address map: file[0:0x40000] at 0x0 (OS); file[0x40000:] at 0x01000000 (game rules); file[0:8MB] at 0x04000000 (data).

Sound: all plays funnel to 0x2c744(call_id); 0x2c1e4(call_id, entry, sample_id) starts the sample. Call table 0x040f16b4 (20-byte, 299 entries, +8 -> u16 sample list). Sample dir file 0x120048. Each ADPCM stream has an 8-byte header: u32 sample count, u16 1, u8 rate divisor (2 = 12 kHz speech, 1 = 24 kHz), u8 same; data follows. Decode count samples; the 0f opcode length is NOT the stream length. Fixed 2026-10-02 (first export was wrong).

Tables: switch descriptors 32-byte at 0x040f3574 (w0 handler). Display effects (deffs) 8-byte {fn, prio} at 0x040e1350 (146), started by 0x280b0(id). Audit descriptors 16-byte at 0x040e022c, w3>>16 = counter id, bumped by 0x178c(id, n). Audit names give mode anchors (e.g. 0x01007128 disc multiball start).

Decompile: Ghidra 11.4.2 downloads fine from GitHub releases now; headless import as raw ARM:LE:32:v4t plus blocks via script. Output: tron/code/tron_game_decompiled.c.

Emulator: in libpinmame, SAM switch n = PinmameSetSwitch(n) directly (Stern number). Close trough 18-21, run ballsim (trough coil 1, launch coil 2) and coin/start via keys, and a game starts. Use PINMAME_NOJIT=1 for the BL hook. Task list head RAM 0x372b0.
