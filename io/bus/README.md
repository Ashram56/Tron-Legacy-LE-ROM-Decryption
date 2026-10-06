# Tron LE 1.74: the CPU to IO power board bus, timing and interfaces

This folder documents every interface the SAM CPU board drives, as seen by the Tron Legacy LE v1.74 ROM
(`trn_174h`), with the timing the software produces. It builds on Vincent's schematic reading
(github.com/Ashram56/Stern-SAM-Databus-Analysis) and ends with a proposal for finer LED PWM on a
replacement CPU board.

Every number carries a tag:
- **code**: read from the ROM (address given).
- **emulator**: measured in patched libpinmame (instruction-level timing, no bus wait states).
- **hardware**: measured in Vincent's logic analyzer captures (`Tron attract.csv`, `Tron start.csv`).
- **scope**: cannot come from the ROM or the captures. It needs an oscilloscope on a real machine.

## 1. Short answer

| What | Value | Tag |
|---|---|---|
| IO tick (all power board traffic) | **250.0 µs** (4000 Hz), timer TC0 at MCK/2 with RC = 5000 | code |
| Lamp matrix | 10 strobe lines x 8 drive lines, **1 ms per strobe line**, 10 ms frame | code + hardware |
| Lamp blanking | all lines off, then the next line **20 µs** later (timer TC1) | code; 24.35 µs measured |
| Lamp brightness | **2 bit-planes weighted 1:2** (4 levels), 30 ms cycle | code |
| Coil outputs | rewritten every 250 µs, rules evaluated every **1 ms** | code + emulator |
| Ramp light tubes (LE) | **4-bit BCM**, one bit-plane per 250 µs tick, 3.75 ms frame | code + emulator |
| GI relay | bit 0 of register 0xB, written out within 250 µs | code |
| One bus write | IOSTB low about 100 ns; 650 ns between writes in a burst | hardware |
| Bus load today | about 57,000 accesses per second in a game, under 1 % of what the bus can carry | emulator |

All IO board traffic comes from interrupt code. No task-level code touches the IO board: tasks write RAM
shadows and the interrupts copy them out.

## 2. The physical bus, as the ROM configures it

The IO board sits on AT91 chip select **NCS1** (base 0x02000000, 16 MB, which also holds the boot flash,
the NVRAM at 0x02100000, the LED at 0x02500000 and the bank register at 0x02580000). The reset code
loads the EBI registers from the table at 0x54 (code at 0xd4):

| CS | Base | Value | Bus | Wait states | Use |
|---|---|---|---|---|---|
| CS0 | 0x04000000 | 0x04003131 | 16 bit | NWS 4 (5 wait states) | game flash |
| **CS1** | **0x02000000** | **0x0200212E** | **8 bit** | **NWS 3 (4 wait states)**, TDF 0, byte-write | boot flash, NVRAM, **IO board**, LED, bank select |
| CS2 | 0x03000000 | 0x0300313D | 16 bit | NWS 7 (8 wait states) | USB (per PinMAME) |
| CS3 | 0x01000000 | 0x01003121 | 16 bit | NWS 0 (1 wait state) | external RAM (game code is copied here) |

The OS (the first 0x3a1f4 bytes of the ROM) is copied into the AT91's internal SRAM and runs from address 0 with no
wait states, so the interrupt code itself is fast. (code: copy loop 0x84-0xc4, remap 0xe0)

**IO addresses.** CPU address `0x024000(20 + n)` puts n on J1 A0-A3, so the 16 IO board registers are
`0x02400020`-`0x0240002F`. The full map is in `bus_register_map.csv`.

**One bus cycle (hardware, 20 MS/s, so ±50 ns):**
- Address and data become valid in the same sample that IOSTB falls.
- IOSTB stays low for 2 samples (about 100 ns). The EBI setting predicts 1 + 4 wait states = 5 MCK = 125 ns.
- Address and data stay valid for at least 200 ns after IOSTB rises.
- The latches clock on the **rising** edge of the decoder output, so the data setup time is the whole IOSTB
  low time (about 100 ns).

**16-bit stores.** The ROM writes LMP_STB and AUX_LMP with one 16-bit store. The 8-bit chip select splits it
into two byte cycles (A = 8, then A = 9), 150 ns apart, and **IOSTB stays low across both**. The LMP_STB
latch is therefore clocked by the address change from 8 to 9, not by IOSTB rising. It works, but a
replacement board should issue two separate, clean byte cycles. (hardware: `Tron start.csv` samples 15718-15722)

**What needs a scope:** data setup and hold to IOSTB at ns resolution, IOSTB edge rates, the decoder glitch
when A changes while IOSTB is low, output switching times of the lamp and coil drivers (needed for the PWM
proposal below), and the IO board watchdog timeout.

## 3. Interrupts

| Source | Setup (code) | Rate | Handler | Job |
|---|---|---|---|---|
| **TC0** (AIC 4, priority 5) | CMR 0x4000 (MCK/2, RC trigger), RC 5000, at 0x13484 | 4000 Hz | 0x13624 → **0x12070** | the IO tick: everything on J1 |
| **TC1** (AIC 5, priority 7) | CMR 0x4000, RC 400, started with CCR = 5 from the IO tick | 1000 Hz, 20 µs after each lamp blank | 0x13688 → 0x13440 → **0x11fbc** | writes the next lamp strobe line; stops itself (CCR = 2) |
| FIQ (pin P12, edge) | AIC 0 | about 4 kHz | 0x2b600 → 0x2d8b4 | sound mixer: 12 samples to 0x0109F000 |
| IRQ0 (pin P9, edge, priority 4) | AIC 16 | event | 0x33300 → 0x32fec | probably the USB controller |
| USART0 / USART1 | 57.6 kbaud / 9600 baud, 8N1 | event | 0x16900 / 0x16a00 | serial ports |

The record tables are at 0x040d7ff4 (timers), 0x040d8024-0x040d8054 (USARTs, IRQ0, FIQ).

PinMAME's comment "FIRQ frequency of 4008 Hz was measured on real machine" refers to the sound FIQ. The IO tick
is TC0, derived from the CPU crystal, and Vincent's captures confirm it: 4 ticks take 20002 samples, which
also means his analyzer sampled at 20.0 MS/s.

`0x11f2c` masks TC0 (AIC IDCR 0x10) as a critical section, for example inside the tube API. In the emulator 3 %
of ticks arrive late (up to one missed tick). Real-machine jitter needs a long capture (section 9).

## 4. The 250 µs IO tick

The ISR at 0x12070 runs a set of blocks. Each has a down-counter in RAM; most reload with 4, so they run once per
millisecond, in four fixed phases. `isr_schedule.csv` has the full table with offsets.

| Phase | Blocks | J1 traffic |
|---|---|---|
| every tick | switch matrix column (CPU board), AC accounting | none |
| **0** | STATUS read (zero cross, interlocks), 40 coil slots | R STATUS, then a coil burst |
| **1** | dedicated switches, flipper rules (list 0x3726c) | coil burst |
| **2** | rule lists 0x37250 and 0x37258 (slings) | coil burst while those rules are enabled (game) |
| **3** | bumpers (0x37254), ball devices (0x040f4548), **lamp blank**, aux register rewrite | LMP_DRV = 0, LMP_STB/AUX_LMP = 0, reg 0xB = shadow, then a coil burst if bumpers/devices ran |
| every tick, last | ramp tube refresh, left then right (LE) | AUX_DRV, reg 0xB low, reg 0xB high, twice |
| phase 3 + 20 µs | TC1 lamp column | LMP_STB/AUX_LMP = 1 << line, then LMP_DRV = data |

A **coil burst** (0x133cc-0x13418) always writes, in this order:
SOL_B, SOL_A, SOL_C, FLSH_LMP (pointer table 0x37334), then AUX_DRV = aux coil byte, reg 0xB = shadow & ~0x40,
reg 0xB = shadow | 0x40. In a game a burst goes out every tick. In attract only phases 0 and 1 have one, which is
exactly what both captures show.

Measured on hardware, phase 0 (`Tron start.csv`, t = 0 at the STATUS read):

| Offset | Access |
|---|---|
| 0.00 µs | R STATUS |
| 24.40 µs | W SOL_B |
| +0.65 µs each | W SOL_A, W SOL_C, W FLSH_LMP |
| 27.05 µs | W AUX_DRV |
| 27.35 µs | W reg 0xB = 0xBE (bit 6 low: aux coil latch) |
| 27.70 µs | W reg 0xB = 0xFE |

Phase 3 (`Tron start.csv` sample 15231): LMP_DRV = 0, LMP_STB = 0 (+0.30 µs), AUX_LMP = 0 (+0.45 µs),
reg 0xB = 0xFE (+1.75 µs), then 24.35 µs after the blank LMP_STB = 0x04 / AUX_LMP = 0, and LMP_DRV = 0xE3 0.60 µs later.

The emulator gives the same order and offsets within a few µs (`traces/emu_attract.csv.gz`).

## 5. Lamp matrix

**Scan.** `0x11fbc` drives one strobe line per millisecond:
1. Phase 3 of the tick blanks everything: LMP_DRV = 0, then LMP_STB and AUX_LMP = 0 (0x132f0, 0x132fc).
2. TC1 fires 20 µs later (24.35 µs on hardware): LMP_STB/AUX_LMP = `1 << line` (lines 0-7 on LMP_STB, 8-9 on
   AUX_LMP bits 0-1), then LMP_DRV = the 8 drive bits of that line.
3. The line stays on for the rest of the millisecond, about 975 µs.

Ten lines give a 10 ms frame (100 Hz). Each lamp is on at most 9.76 % of the time.

**Brightness.** The output buffer at RAM 0x3c1f0 holds two planes of 10 bytes. Plane 0 is shown for one frame,
plane 1 for two frames (counter 0x3728a), so a lamp has 4 levels: off, 1/3, 2/3, full, over a 30 ms cycle (33 Hz).
Game code sets lamps with a plane mask (`0x833c` on, `0x81f8` off, `0x83f4`, `0x82b0`). Nearly every call passes
0xff (both planes, full brightness). About 10 call sites pass 1 or 2 for a dim level.

**Image.** The compositor `0x7f68` builds 0x3c1f0 once per OS tick (16.1 ms, from 0x3405c): the base image
0x3c204, minus blinking lamps (mask 0x3c218, toggled every 5 OS ticks, about 81 ms), plus the lamp-effect layer
0x3c224/0x3c238 and the layer list at 0x3728c. The scan reads whatever is there, so a new image appears at the
next strobe line.

**Mapping.** Lamp n uses strobe line (n-1)/8 and LMP_DRV bit 7-((n-1) mod 8). `lamp_matrix_map.csv` lists all
80 lamps with J12 and J13 pins (from Vincent's pin list). Lamps 65 and 66 are the start and tournament buttons,
67-80 are unused, so lines 8 and 9 carry almost nothing.

**Not used by the ROM:** STATUS bits 3 and 4 (LMP1STAT, LMP2STAT, lamp driver faults) are never tested.

**Keep in mind for a new CPU board.** Vincent's notes say a watchdog on the IO board is fed from the lamp
strobe logic. A replacement must keep strobing at least as often as the ROM does. The exact condition and timeout
need the schematic and a scope.

## 6. Coils

- Game code writes shadow bytes 0x3b97c-0x3b980. The IO tick copies them out. When the interlocks are not both
  present (`0x3727c & 3 != 3`) the four driver bytes are ANDed with the mask at 0x3b984 first.
- Coil slots (0x3b98c, 40 x 0x28 bytes) run every 1 ms, in three modes: 1 = shift out a bit pattern,
  2 = pulse then on/off hold, 3 = timed on. A slot can wait for a zero-cross phase before it starts.
- Flipper, sling, bumper and ball device rules also run every 1 ms (phases 1-3).
- So **coil timing has 1 ms resolution** even though outputs are refreshed every 250 µs. Example (emulator):
  left flipper held = 40 ms on, then 1 ms on / 11 ms off.
- Per-coil pulse and hold times are in `../../rom_data/io/coils.csv`.
- Aux coils 33-40: byte 4 of the shadow goes out on AUX_DRV and is latched with reg 0xB bit 6 in every coil burst.

## 7. Aux port (J2 / J3) and GI

Register 0xB is one latch: bit 0 = GI relay (0 = on), bits 1-2 unused, bits 3-7 = the five aux strobes, idle
high. The ROM keeps a shadow at 0x3c758 and always writes the whole byte, so a GI change goes out with the next
strobe pulse or the phase 3 rewrite, within 250 µs.

To latch a byte on an aux board the ROM writes AUX_DRV, then reg 0xB with the strobe bit low, then reg 0xB
with it high (300 ns and 350 ns apart on hardware). The board latches on the rising edge.

| Reg 0xB bit | Vincent's name / pin | PinMAME name | Tron LE use |
|---|---|---|---|
| 3 | ASTB, J2 pin 10 | BSTB | unused |
| 4 | ESTB, J3 pin 12 | CSTB | left ramp tube |
| 5 | DSTB, J3 pin 11 | DSTB | right ramp tube |
| 6 | CSTB, J3 pin 10 | ESTB | aux coils 33-40 |
| 7 | BSTB, J3 pin 9 | ASTB | unused |

**Ramp light tubes (LE only).** At the end of every tick, `0x874` sends one bit-plane per tube: R = AUX_DRV bit 5,
G = bit 4, B = bit 3, plane n held for 2^n ticks (1, 2, 4, 8), so 4-bit colour in a 15-tick (3.75 ms, 267 Hz)
frame. Fades interpolate linearly, one step per tick (`0x800` converts ms to 4 x ms steps). Checked in the
emulator: left set to 15/4/0 shows G on for exactly 4 of 15 ticks; right 5/10/15 shows R on 5, G on 10
(`traces/emu_tubeset.csv.gz`).

**Captures.** Neither of Vincent's captures has a tube write, while the LE ROM sends four aux cycles every tick.
The Pro ROM has no tube driver at all, so the captures most likely come from a Pro (or a non-1.74 LE) ROM.
The rest of the traffic matches the LE ROM exactly.

## 8. STATUS input

Read at phase 0 (1 kHz). Bit 2 = zero cross: edges are counted over 250 ms windows to measure the line frequency
(0x3731c) and coil slots can sync to its phase. Bits 0-1 = 20 V and 50 V interlocks, latched to 0x3734c and
debounced over 8 OS ticks in `0x7c24` before the coil power mask changes. Bits 3-7 are not used.

## 9. CPU board interfaces (not on J1)

`cpu_board_interfaces.csv` lists the rest: switch matrix (16-bit return at 0x01100000, column strobe at 0x01100008,
one column per tick, 2 ms per scan), dedicated switches (0x01100002 / 0x01100004, 1 ms), DMD page register
(0x01100020), sound buffer and FIQ, NVRAM, LED (0x02500000), flash bank select (0x02580000), an LE-only write of
0x3b to 0x02290000 (purpose unknown), the timers and the two USARTs.

**Correction to `../io_registers.csv`:** the switch return is 0x01100000, the column strobe is 0x01100008 (it is
not the DMD page), the dedicated switch inputs are 0x01100002/4, and 0x02580000 is the flash bank select, not
the LED. The runtime values of the pointer block 0x37280-0x37350 were read in the emulator to confirm this.

**Next captures worth taking on the machine** (analyzer at 20 MS/s or more, at least 1 s long):
1. Trigger on reg 0xB data bit 4 or 5 low, to see the tube traffic on an LE.
2. A long attract capture, to measure real tick jitter.
3. A scope on IOSTB, A0-A3 and one data line, for the ns-level items in section 2.

## 10. Improving the bus for finer LED PWM

### What the power board fixes
The IO board is decoders plus edge-triggered octal latches. It has no timing of its own: every pulse width is
whatever the CPU writes. Its limits are physical:
- A matrix lamp can be on at most 1/10 of the time (10 strobe lines). Only a hardware change raises that.
- How short a pulse can be depends on the lamp and coil driver transistors (scope).
- The bus itself is fast: a byte cycle takes about 150 ns, so about 6 million writes per second. The ROM uses
  about 57,000 per second in a game.

So the bus does not need a new protocol to get finer PWM. A faster CPU or FPGA just has to write more often and
with better timing. The ROM's coarse PWM comes from its own scheduling (1 ms lamp slots, 2 planes, 250 µs tube planes).

### A. Lamp matrix with the existing IO board
Keep 10 strobe lines and the blank before each line, then PWM inside each slot by rewriting LMP_DRV:
- **Edge-sorted PWM (recommended).** At the start of the slot write the 8 drive bits with every lamp that should be
  on. Turn lamps off in order of brightness by rewriting LMP_DRV at each off time. That is at most 9 writes per slot,
  with any resolution the timer offers. With a 250 µs slot (2.5 ms frame, 400 Hz) and a 0.25 µs timer you get about
  10 bits per lamp for 36,000 writes per second, still under 1 % of the bus.
- **BCM in the slot.** 8 writes per slot with weights 1, 2, 4 ... 128. Simpler in hardware, but the shortest plane
  is about 1 µs, which the drivers may not follow.
- Keep a blank gap between lines for ghosting. The ROM uses about 24 µs; measure how much the LED boards need.
- Apply gamma in software. LEDs look linear only with a gamma table, and the 1/10 duty ceiling stays.

### B. Ramp tubes and other strobed aux boards
The tri-colour board latches 3 bits per strobe, so the CPU still does the PWM:
- Same edge-sorted method per tube: at most 4 latch cycles (each = AUX_DRV + strobe low + strobe high,
  about 0.5 µs) per PWM period. 8 to 12 bits at 400 Hz or more is easy.
- Or 8-bit BCM with a 10 µs unit: 2.55 ms frame, 8 latch cycles per frame.

### C. A smart LED board on the aux port
For many LEDs or RGB strips, stop doing PWM over the bus. Use the aux port as an 8-bit parallel link to a
microcontroller on the LED board and let it do the PWM:
- AUX_DRV carries a byte. A free strobe (bit 3 or bit 7 on Tron LE) clocks it into the board on its rising edge.
  At three bus cycles per byte, that is about 2 MB/s.
- Suggested framing: `0xA5` sync, address, length, payload, CRC-8. Use a second free strobe as "start of frame"
  so a lost byte cannot misalign the stream.
- Commands: set colour, fade to colour over N ms, run a stored pattern. Local PWM at 12 to 16 bits with gamma,
  for example with a PWM LED driver chip or WS2812-style strips.
- Rules for coexisting with the original boards: write the whole reg 0xB byte from a shadow (GI bit and other strobes
  unchanged), and only pulse your own strobe. Boards latch AUX_DRV only on their own strobe, so they ignore your traffic.

### D. If the IO board can change too
A new power board could take a serial link (SPI or a UART at several Mbaud) and drive constant-current LED drivers per
lamp. That removes the 1/10 duty limit and the matrix ghosting, but it is a new board, not a new bus.

## Files
| File | Content |
|---|---|
| `bus_register_map.csv` | the 16 J1 registers: address, A3-A0, direction, ROM pointer, writer code, rate |
| `isr_schedule.csv` | the 4-phase IO tick schedule with emulator and hardware offsets |
| `timing_measurements.csv` | every timing number above, with its source and tag |
| `lamp_matrix_map.csv` | 80 lamps: strobe line, drive bit, J12/J13 pins, RAM bit |
| `cpu_board_interfaces.csv` | everything else the CPU drives: switches, DMD, sound, timers, serial, chip selects |
| `traces/emu_*.csv.gz` | emulator bus traces with cycle stamps (attract 0.1 s, flipper hold 0.3 s, tube colour test) |
| `tools/pinmame_bus_hook.patch` | adds a bus callback to libpinmame (apply on top of `rules/tools/trace/pinmame_arm_hook.patch`) |
| `tools/bus_trace.cpp` + `s_*.txt` | harness (hw_trace plus `buscap SECONDS LABEL` and `peek`) and the scenarios used |
| `tools/seq.py`, `stats.py`, `ana.py` | print per-tick sequences, timing statistics, access counts from a trace |
| `tools/la_capture_decode.py` | decodes Vincent's PulseView CSV exports into bus cycles |
