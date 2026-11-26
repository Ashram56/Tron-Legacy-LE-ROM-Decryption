# Timing rows removed on 2026-11-26 and what the code gives instead

Owner decision: the emulator-measured rows of `timing_measurements.csv` are deleted and redone from the ROM code. Each of the
15 removed rows is below with its code value (address) or the reason the code cannot give it. Nothing here comes from PinMAME.

| Removed row (old value) | From the code | Where |
|---|---|---|
| MCK 40 MHz (PinMAME SAM_CPUFREQ) | **Hardware, not in the code**: the AT91x40 has no PLL, MCK is the board oscillator; no clock register is written in `peripheral_init.csv`. Everything below is expressed in ticks of TC0, which the code sets (RC=5000 at MCK/2 = 250.0 us only if MCK = 40 MHz). The owner can confirm 40 MHz on the board. | `io/bus/peripheral_init.csv`, 0x13484 |
| lamp column on-time ~975 us | 1000 us column period (blank every 4th tick) minus the TC1 one-shot delay 20.0 us = **980 us** | 0x11fbc, 0x12070 phase 3 |
| lamp image update 16.1 ms (OS tick ~62/s) | **16.000 ms**: the IO ISR decrements RAM 0x37368 each 250 us tick, reload 0x40 = 64 ticks, then increments `gf_tick_counter` (the OS tick that paces the main loop, 0x3405c). The 16.26 ms in AGENTS.md and 15.41 ms in the game were measured in the emulator; the code says 16.000 ms | 0x12070 (0x37368, 0x40) |
| coil output refresh 250 us | **1 ms for the slot burst**: phase 0 (RAM 0x37370, reload 4, so every 4th tick) samples STATUS and bursts the 40 coil slots; phases 1 and 3 burst only when their lists are active | 0x12070, `isr_schedule.csv` |
| switch matrix scan 250 us per column (4 columns = 1 ms) | **250 us per column**: one matrix column is read and the next strobed on every tick (reload 1 at RAM 0x37378); 4 columns per 1 ms | 0x12070, `isr_schedule.csv` row 1 |
| IO ISR length p50 29 / p95 81 / max 87 us | **Instructions per tick from the code**: 634 instructions for the phase-0 tick, 210 for another phase (`tools/isr_length.py`, Unicorn on 0x12070). Microseconds need the EBI wait states (`peripheral_init.csv` CSR0-3) and an ARM7 cycle model; not computed | 0x12070 |
| IO tick jitter 131 of 3967 ticks | **Not in the code**: the tick is TC0-driven, so the code has no jitter; real jitter is interrupt latency behind the sound FIQ (0x2b600), a hardware measurement | n/a |
| bus load 57000 accesses/s | **Computed from the schedule**: per 1 ms (4 ticks) about 8 matrix accesses + 1 STATUS read + the coil burst of 7 writes + dedicated switch reads and lamp column writes, about 30,000/s; the LE ramp tube refresh adds 3 writes x 2 tubes x 4000 ticks = 24,000/s | `isr_schedule.csv` `bus_accesses` |
| switch return read offset 2.60 us after tick entry | **Not a code constant**: the read is the first bus access of the ISR (0x12070) so the offset is the ISR prologue plus the FIQ wait; the old worst case (70 us) is the FIQ preempting. Hardware measurement, kept only from the analyzer rows | 0x12070 |
| switch strobe to read (settle) 246.7 us | **One IO tick, 250 us** minus the gap between the read and the next strobe write (code order: read column N, write strobe N+1, at the next tick read N+1) | 0x12070 |
| flipper button to coil 17 us / sling 11 us | **Same IO tick**: the dedicated switches are read in phase 1 (every 4th tick) and the hardware rule list (flippers 0x3726c, slings 0x37250/0x37258) fires its coil burst in the same ISR; latency 0 to 1 ms from the 1 ms phase period | 0x12070 phases 1-2 |
| bumper switch to coil 1.26 ms | **1 ms phase 3 period** (bumper list 0x37254) plus the rule's own debounce counter; 1 to 2 ms | 0x12070 phase 3 |
| DMD page flip interval 16.2-16.4 ms | **16.000 ms**: one flip per main-loop pass (0x27830), the loop being paced by `gf_tick_counter` (above) | 0x27830, 0x12070 |
| DMD draw stores per frame 2896-5050 | **Per effect, not a constant**: it follows the draw calls of each deff; the calls are in `rom_data/deffs/code_runs.csv` (`tools/deff_runs.py`) | `deff_runs.py` |

The last measured-only row, the DMD scan 62.67 Hz (PinMAME `sam.c` notes), is the FPGA's and the display board's: **not in the ROM** (boards_inventory.md: no bitstream), so it needs a scope. It is not kept.
