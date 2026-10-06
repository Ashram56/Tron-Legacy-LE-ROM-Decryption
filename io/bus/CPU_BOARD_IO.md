# Tron LE 1.74: every interface the SAM CPU board drives

This file covers everything except the IO power board bus, which is in `README.md`. The register list
is `cpu_board_interfaces.csv`. The power-on setup of every on-chip peripheral, in order, is
`peripheral_init.csv`, taken from an emulator trace of the first 8 seconds.

Tags as in the README: **code** (read from the ROM), **emulator** (patched libpinmame), **external**
(PinMAME's own hardware notes), **inferred**.

## 1. Overview

| Interface | How the CPU reaches it | Rate | Tag |
|---|---|---|---|
| IO power board (coils, lamps, aux, GI) | 8-bit bus at 0x02400020 (EBI CS1) | 250 µs tick | code + hardware |
| DMD | frame pages in external SRAM, two page registers; the Xilinx FPGA scans the display | page flip every OS tick (16 ms) | code + emulator |
| Audio | FIQ every 250 µs; 6 stereo frames written to a 24-byte buffer the Xilinx plays | 24 kHz stereo, 16-bit | code + emulator |
| Audio volume | bit-banged 3-wire link on PIO P3-P5 to the DAC | on change | code + emulator |
| Switch matrix | 16-bit return + column strobe at 0x01100000 | one column per 250 µs, 1 ms full scan | code + emulator |
| Dedicated switches, DIPs | 0x01100002 / 0x01100004 / 0x01100005 | 1 kHz; DIPs once per OS tick | code + emulator |
| Real-time clock | bit-banged 3-wire link on PIO P16-P18 | on demand | code |
| LED sign port | USART1, 9600 baud | boot and on demand | code + emulator |
| Second serial port | USART0, 57600 baud | no traffic seen | code |
| USB | EBI CS2 at 0x03000000, IRQ0 on P9 | not used in emulation | code |
| NVRAM | 128 KB at 0x02100000 | as needed | code |
| Flash banking | 0x02580000 write, 0x01180000 read back | thousands per second (audio) | code + emulator |
| Board LEDs | 0x02500000, 0x02F00000 | blink | code + emulator |

## 2. Interrupts and time base

| Source | AIC setup | Handler | Rate |
|---|---|---|---|
| FIQ (pin P12) | SMR0 = 0x66: positive edge | 0x2b600 → 0x2d8b4 (sound mixer) | about 4000 Hz, from the Xilinx |
| USART0 (AIC 2) | SMR2 = 0x41: level, priority 1 | 0x16900 | events |
| USART1 (AIC 3) | SMR3 = 0x42: level, priority 2 | 0x16a00 | events |
| TC0 (AIC 4) | SMR4 = 0x05: level, priority 5 | 0x13624 → 0x12070 (IO tick) | 4000 Hz (RC 5000 at MCK/2) |
| TC1 (AIC 5) | SMR5 = 0x07: level, priority 7 | 0x13688 → 0x11fbc (lamp column) | 1000 Hz, one-shot 20 µs |
| IRQ0 (pin P9) | SMR16 = 0x64: positive edge, priority 4 | 0x33300 → 0x32fec | never fired in emulation |
| spurious | SPU = 0x13600 | counts in 0x37354 | |

The OS tick, which runs the main loop `0x3405c` (lamp compositor, display effects, sound commands, rules), comes
from the IO tick: counter 0x37364 advances every 64 ticks (16.0 ms) and 0x37360 every 40 ticks (10 ms).
The emulator measures 62 main-loop passes per second. The AT91 watchdog is never enabled.

## 3. DMD

**Memory.** 30 pages of 4 KB at 0x01080000-0x0109DFFF in the external SRAM (U13, CS3). A page is 128 x 32
bytes, row-major, one byte per pixel:
- low nibble = shade 0-15;
- high nibble = mask. PinMAME's model: where the mask is 0xF the pixel comes from the background page instead.

**Page registers.** Two 16-bit registers select which pages the FPGA shows (code: flip 0x27830, pointers 0x381b8 /
0x381bc):

| Register | Meaning |
|---|---|
| 0x01100020 | foreground page (supplies the mask) |
| 0x01100022 | background page |
| 0x01100024 | written once with 1 at boot (0x27fa0), probably display enable (inferred) |

The ROM keeps three page pairs (shown, previous, being drawn: RAM 0x3d524-0x3d538) and flips once per OS tick,
so the display changes at most every 16 ms. Drawing writes the pages directly with 8, 16 and 32-bit stores:
about 243,000 stores per second during a game animation, none while the picture is static.

**Scan (external).** The Xilinx FPGA refreshes the display by itself. PinMAME's measurement: 62.67 Hz, each row shown
in 12 slots of 41.55 µs, planes weighted 1/2/4/5. The ROM never touches row timing, so a replacement board must
reproduce this scanner (or drive a different display) itself.

## 4. Audio

**Path.** Samples live ADPCM-compressed in the 32 MB flash (see `../../README.md`). The FIQ handler `0x2d8b4`:
1. reads 0x01180000 to save the current flash bank, because it changes banks to fetch sample data;
2. writes 6 stereo frames of the previous batch to 0x0109F000-0x0109F017 (each 32-bit slot as two 16-bit halves,
   left and right, signed 16-bit, clamped from 32-bit sums);
3. mixes the next 6 frames from 8 voices (voice records at 0x3da64, 0xa0 bytes each) into a double buffer
   (0x3e2e0, two halves of 12 words), applying per-voice volume ramps (0x3e144);
4. restores the bank (0x02580000 at 0x2dc24).

6 frames per FIQ at about 4000 Hz gives the 24 kHz output rate (PinMAME uses 24000 Hz). The output lags the mix
by one FIQ (250 µs). The 12 kHz speech samples are resampled by the mixer.

**Volume.** Not done in the mixer. `0x14514(volume 0-63)` sends two 16-bit words over a 3-wire link
(`0x14480`):

| Pin | Use |
|---|---|
| P3 | latch, active low |
| P4 | clock, data taken on the rising edge |
| P5 | data, MSB first |

The words are 0x10nn and 0x11nn with nn = 0x80 + 2 x volume (boot value 0xD0). That matches the left/right digital
attenuation registers 16 and 17 of a TI PCM17xx-class DAC (inferred: the chip is not named in the ROM). In the
emulator the bit period is about 0.5 µs, set only by instruction timing.

## 5. Switches

| Register | Content | Read when |
|---|---|---|
| W 0x01100008 | column strobe, 1 << column, 4 columns | every 250 µs |
| R 0x01100000 | 16 returns of that column, 0 = closed | every 250 µs, before the strobe moves on |
| R 0x01100002 | dedicated switches D1-D16 | phase 1 of the IO tick (1 kHz) |
| R 0x01100004 | dedicated switches D17-D24 (low byte) | phase 1 (1 kHz) |
| R 0x01100005 | DIP switches | once per OS tick (0xec8c) |

4 columns x 16 returns = 64 matrix switches; the column count comes from the switch table size (0x040d1c38 = 65).
A full scan takes 1 ms. Each column is read 250 µs after its strobe was set, and the next strobe is written
right after. Debouncing happens in RAM (0x3c76a onwards).

## 6. Real-time clock

A second bit-banged link on P16-P18, LSB first, 8 bits per transfer, with a bidirectional data pin (`0x15c04`
init, `0x15c54` write byte, `0x15cac` read byte, `0x15d0c` / `0x15d4c` start / stop):

| Pin | Use |
|---|---|
| P16 | chip enable, active high |
| P18 | clock |
| P17 | data, read back through PIO PDSR bit 17 |

The protocol matches a DS1302-style real-time clock (inferred). It was not accessed in 30 s of emulation; it is
used for dates in audits and the clock setting.

## 7. Serial ports

| Port | Pins | Setup | Use |
|---|---|---|---|
| USART1 | TXD1/RXD1 = P21/P22 | BRGR 260 → 9615 baud, 8N1 | LED message sign (Alpha / BetaBrite protocol). At boot it sends a sign setup and three messages: "Stern Pinball, Inc. Proudly Presents...", "Tron L.E.", "You Could Be The Next BIG WINNER!!!" |
| USART0 | TXD0/RXD0 = P14/P15 | BRGR 43 → 58140 baud (57600 nominal), 8N1 | no traffic in emulation; probably the service / debug console that has the `lrlt` / `rrlt` commands (inferred) |

## 8. Other chip-select devices

| Address | Device | Notes |
|---|---|---|
| 0x02100000 | NVRAM 128 KB (CS1) | audits, adjustments, scores; the AC line monitor keeps samples at 0x02111908 |
| 0x02500000 | CPU board LED 1 | heartbeat, about 21 writes/s from 0x34110 |
| 0x02F00000 | CPU board LED 2 | written 0 four times at boot (0x32ef0) |
| 0x02580000 | flash bank select | U42 drives flash A22-A25; selects the 8 MB window at 0x04800000 |
| 0x01180000 | bank read back + board revision | bits 0-3 bank, bits 4-6 revision (0x10 in PinMAME) |
| 0x02290000 | LE-only extra IO | written 0x3b once by 0x11f08; purpose unknown |
| 0x03000000 | USB controller (CS2, 16-bit, 8 wait states) | not accessed in emulation |

## 9. What a replacement CPU board must provide

1. The IO power board bus with the timing in `README.md`.
2. A DMD scanner equivalent to the Xilinx (62.67 Hz, 16 shades, 128 x 32), or its own display.
3. A 24 kHz stereo 16-bit audio output with volume control.
4. The switch matrix (4 strobes x 16 returns) and 24 dedicated inputs plus DIPs.
5. NVRAM and a real-time clock if audits with dates matter.
6. Optional: the 9600 baud LED sign port.

## 10. How this was measured
- `tools/pinmame_bus_hook.patch` hooks the IO handlers, the DMD page RAM (0x01080000), the sound buffer
  (0x0109F000) and every AT91 on-chip peripheral access.
- `BUSCAP_BOOT=1 PINMAME_NOJIT=1 ./bus_trace tools/s_all.txt out.jsonl` writes `boot.csv` (power-on to 8 s),
  `attract_all.csv` and `game_all.csv`. `tools/ana2.py` summarises them per peripheral and register.
- The traces are not committed (about 130 MB); rerun the command to regenerate them.
