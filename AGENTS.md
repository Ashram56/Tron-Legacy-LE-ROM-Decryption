# AGENTS.md: Tron Legacy ROM extraction (Tron's part of agent A)

**The agent's instructions moved** to the game-agnostic repository
[Ashram56/Stern-SAM-Decryption](https://github.com/Ashram56/Stern-SAM-Decryption):
[`agents/rom_extraction.md`](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/rom_extraction.md) is agent A (how to take any Stern SAM ROM apart:
methods, tools, table layouts, mistakes, deliverables), part of the
[master plan](https://github.com/Ashram56/Stern-SAM-Decryption/blob/main/agents/README.md). Read it there (or in `../Stern-SAM-Decryption` when cloned beside this
repository), and update it there, with a PR, when you learn something another SAM ROM would need.

This repository is the **Tron result** of that agent, and this file keeps only what is true of Tron.

## What is here

The ROM is Stern Tron Legacy LE v1.74 (PinMAME set `trn_174h`), with Pro v1.74 (`trn_17402`) ported as a second
model; the ROM itself is never committed. Layout: [README.md](README.md). The reference implementation the agent
file points to: [rules/developer_guide.md](rules/developer_guide.md), [mpf_package/README.md](mpf_package/README.md),
[io/README.md](io/README.md), [io/bus/](io/bus/README.md), [rom_data/](rom_data/README.md),
[docs/PRO_VS_LE.md](docs/PRO_VS_LE.md) and [rom_data/pro/](rom_data/pro/README.md); the raw notes the Tron
threads kept are in [docs/agent_notes/](docs/agent_notes/).

## Status

Done for LE 1.74 and ported to Pro 1.74. The game repo [Tron-Legacy-MPF](https://github.com/Ashram56/Tron-Legacy-MPF)
pins this repository as a submodule at `assets/`, and a sync job there opens a PR when it moves. Tron's page for
all agents (status, open work, decisions): [Tron-Legacy-MPF `docs/agents/README.md`](https://github.com/Ashram56/Tron-Legacy-MPF/blob/main/docs/agents/README.md).

## Tron LE 1.74 quick reference

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

Owner preference for this repository: ship package updates as small zips of changed files only, never a full
rebuild ([docs/agent_notes/vincent-update-zips.md](docs/agent_notes/vincent-update-zips.md)).

Last updated 2026-10-10 (the agent moved to Stern-SAM-Decryption `agents/rom_extraction.md`; its content up to
2026-10-08 is there unchanged, except this quick reference).
