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
| DMD | frame pages in external SRAM, two page registers; the Xilinx FPGA scans the display (section 3) | page flip every OS tick (16 ms) | code + emulator |
| Audio | FIQ every 250 µs; 6 stereo frames written to a 24-byte buffer the Xilinx plays | 24 kHz stereo, 16-bit | code + emulator |
| Audio volume | bit-banged 3-wire link on PIO P3-P5 to the DAC | on change | code + emulator |
| Switch matrix | 16-bit return + column strobe at 0x01100000 (section 5) | one column per 250 µs, 1 ms full scan; flippers/slings reach the coils in the same tick | code + emulator |
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

### 3.1 What the CPU sees

Everything sits on EBI chip select 3 (CSR3 = 0x01003121: 16 MB window at 0x01000000, 16-bit, 1 wait state, byte
select). Inside that window the U13 SRAM holds the frame pages, and the Xilinx FPGA decodes the registers at
0x01100000 and up (the board split is inferred; the addresses are code).

| Address | Access | Content | Tag |
|---|---|---|---|
| 0x01080000-0x0109DFFF | W 8/16-bit (read back by draw code) | 30 pages of 0x1000 bytes, page n at 0x01080000 + n x 0x1000 | code + emulator |
| 0x01100020 | W 16 | foreground page number 0-29 | code + emulator |
| 0x01100022 | W 16 | background page number 0-29 | code + emulator |
| 0x01100024 | W 16 | written 1 once at boot by 0x27fa0, probably display enable | code; meaning inferred |

There is no status register: the ROM never reads anything from the display side, so it never waits for a
frame or row boundary.

### 3.2 Page format

A page is 32 rows x 128 bytes, row-major: byte (x, y) is at page + y x 128 + x, x = 0 at the left.

| Bits | Meaning |
|---|---|
| 0-3 | shade 0-15 |
| 4-7 | mask |

PinMAME's model of the mixer (`sam_dmd` in `sam.c`), which matches every Stern SAM game it runs:

```
mask  = fg >> 4
pixel = (bg & mask) | (fg & ~mask)      (low 4 bits only)
```

So it is a bit-wise mix, not a blend: mask 0x0 shows the foreground shade, 0xF shows the background pixel. Only
the foreground page's mask nibble matters. The formula is external (PinMAME). In the game capture every byte the
ROM wrote had mask 0, so the background never showed through there; which effects set the mask was not traced.

### 3.3 How the ROM uses it (code + emulator)

- **Flip.** `0x27830(fg, bg)` rejects page numbers above 29 (error 0x20). It then writes the background
  register first, and the foreground register 19 CPU cycles (0.5 µs) later. The previous pair is kept in RAM
  0x3d534/0x3d538 and the current pair in 0x3d524/0x3d528. `0x278b8` shows the pair being drawn (0x3d530 fg,
  0x3d52c bg), then `0x2779c` hands out the next free pages for drawing.
- **Rate.** The flip runs from the display effect task, at most once per main-loop pass (16 ms). In the game
  capture it ran on 61 of 62 passes: 16.2-16.4 ms apart, with no relation to the display scan.
- **Page use.** During a game animation the background stayed on page 5. The foreground rotated through pages
  0-17 (skipping 5), one new page per frame, so a page is rewritten about 17 frames after it was shown.
- **Drawing.** Each new frame first clears the whole page with 2048 16-bit stores, then draws pixels with 8-bit
  stores: 2,896 to 5,050 stores per frame and about 243,000 per second during the animation. No 32-bit stores
  were seen. A static screen causes no writes.

### 3.4 Display scan (external, needs a scope)

The ROM never touches row timing, so this part is the FPGA's alone. PinMAME's notes, which say they were checked
against real hardware:

| Quantity | Value |
|---|---|
| Frame rate | 62.67 Hz (15.96 ms) |
| Rows | 32, one at a time |
| Per row | 12 time slots of 41.55 µs = 498.6 µs |
| Sub-frames | 4 bit planes of the shade, shown for 1, 2, 4 and 5 slots |

So the 16 shades give only 13 distinct brightness levels (0-12 slot units). To send 128 dots in one 41.55 µs slot
the dot clock must be at least 3.1 MHz (inferred).

The display cable is the standard 14-pin Stern/Williams 128x32 DMD connector. Its odd pins carry enable, row
data, row clock, column latch, dot clock and serial dot data, and its even pins are ground. That pinout is
external knowledge, not visible in the ROM. **A scope is needed** for these:
- dot clock frequency;
- latch and row-clock timing within a slot;
- whether the page registers take effect at frame start (no tearing) or immediately.

### 3.5 What a replacement board needs

1. Two 16-bit page registers and 30 x 4 KB of page memory at the same addresses, or a translation layer.
2. The fg/bg mask mix above.
3. A scanner. Matching the original means 62.67 Hz with planes weighted 1/2/4/5. A new board is free to show
   all 16 shades linearly (for example 15 slots weighted 1/2/4/8), because the ROM only writes shade values.
4. Latching the page registers at frame start would remove any tearing. The ROM flips at random points in the
   scan, so on the original hardware it either latches or tears (needs a scope).

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

### 5.1 Registers (all on CS3, read as 16-bit, 0 = closed on the wire, the ROM inverts)

| Address | Dir | Content | Read by | Rate |
|---|---|---|---|---|
| 0x01100008 | W 16 | column strobe, value 1 << column (0x1, 0x2, 0x4, 0x8) | IO tick @0x1278c | every 250 µs |
| 0x01100000 | R 16 | 16 returns of the strobed column, bit r = row r | IO tick @0x12658 | every 250 µs |
| 0x01100002 | R 16 | dedicated D1-D16, bit k = D(k+1) | IO tick @0x127f0 | every 1 ms |
| 0x01100004 | R 16 | low byte D17-D24, high byte the 8 DIP switches (D25-D32) | IO tick @0x127f0 | every 1 ms |
| 0x01100005 | R 8 | DIP switches alone | 0xec8c | once per main-loop pass |

**Numbering.** Switch number = column x 16 + row + 1.
- Columns 0-3 are the matrix (switches 1-64). For example, trough switches 18-21 are column 1, rows 1-4.
- Columns 8 and 9 are the dedicated words 0x01100002 and 0x01100004 (switches 129-160 = D1-D32).
- The ROM keeps all of them in one set of 16-bit arrays indexed by column.

The matrix size comes from the ROM: 0x040d1c38 = 65 switch numbers, so (65 - 1) / 16 = 4 columns. The scan code
handles up to 8 columns for other games.

### 5.2 Scan timing (code + emulator, `swhit` and game captures)

Each IO tick, 2.60 µs after the handler starts:
1. Read 0x01100000. This is the column strobed one tick earlier.
2. Advance the column (wrapping after column 3).
3. 3.3 µs later, write the next strobe to 0x01100008.

So each column is driven for a whole tick, 246.7 µs on average, before it is read. That leaves plenty of
settling time for a slower or optically isolated matrix.

| Measured | Value |
|---|---|
| Read offset after tick entry | 2.60 µs typical, 70 µs worst (tick delayed by the sound FIQ) |
| Strobe offset after tick entry | 5.90 µs typical |
| Strobe to read | 124-635 µs, median 246.7 µs |
| Full matrix scan | 1.0 ms |
| Dedicated reads | 7.15 µs and 8.78 µs after tick entry, once every 4 ticks |

The column period depends on the board revision. `0x11eec` reads bits 4-6 of 0x01180000:
- revision 0: one column every 2 ticks (500 µs, 2 ms scan);
- any other revision: every tick (250 µs).

PinMAME reports revision 1. The strobe register is written as an active-high one-hot value. What polarity the
pins drive is not visible in the ROM (needs the schematic or a scope).

### 5.3 Debounce, stage 1: in the IO tick (code)

Per column, with 16-bit arrays indexed by column:

| RAM | Name used here | Meaning |
|---|---|---|
| 0x3c76a | raw | last read, 1 = closed |
| 0x3c792 | stable | the debounced state the game sees |
| 0x3c77e | diff | raw XOR stable from the previous scan |
| 0x3c7a6 | pending | differed from stable on two scans in a row |
| 0x3c7ba | bounced | was pending, then matched stable again |
| 0x3c7ce | ack | bits the main loop has handled; cleared from pending/bounced on the next scan |

```
new_diff  = raw ^ stable
pending  |= old_diff & new_diff        // changed on 2 consecutive scans (1 ms apart)
bounced  |= pending & ~new_diff
diff      = new_diff
```

The dedicated words use the same code, in columns 8 and 9, every 1 ms.

### 5.4 Debounce, stage 2: in the main loop (code)

`0xeadc` runs once per main-loop pass (16 ms), from `0x340a0`. It walks switches 1-64, then 129-160, through
`0xe85c`, which handles each pending bit:
1. It counts passes in a per-switch byte counter.
2. A closing edge must last for descriptor byte +0x1b passes, and an opening edge for byte +0x1c passes. The
   descriptors are 32 bytes each from 0x040f3574.
3. If the switch bounces back first, the event is dropped.
4. Otherwise the stable bit flips, the ack bit is set and the switch handler is queued (`0xe318`).

Counts used by Tron (close / open, in 16 ms passes):

| Close / open | Switches |
|---|---|
| 1 / 1 | right orbit spinner 36, disc opto 41, left spinner 44 |
| 1 / 2 | bumpers 30-32 |
| 1 / 3 | most rollovers, flipper buttons D9/D11/D13 |
| 1 / 4 | slingshots 26, 27 |
| 1 / 5 | targets 7, 8, 13, 48-51, video game eject 11 |
| 1 / 9 | ramp entrances and exits 34, 35, 37, 38 |
| 1 / 6 | tilt pendulum D17 |
| 2 / 2 | start, tournament, trough 18-22, motor positions 52-56, coin slots, coin door buttons |
| 2 / 4 | TRON letters 1-4 |
| 2 / 5 | shooter lane 23 |
| 0 / 0 | flipper EOS D10/D12, slam tilt D18 |
| 10 / 10 | DIP switches |

Rules-level switch events therefore arrive 1-2 ms (scan) plus 0-16 ms (waiting for the pass) after a closure,
plus (count - 1) x 16 ms.

### 5.5 Fast paths: flippers, slings, bumpers (emulator, `swhit` and `flip2` captures)

These do not wait for the main loop. The flipper, sling and bumper rules run inside the IO tick every 1 ms and
read the raw arrays directly:

| Input | Seen by the CPU | Coil write | Latency |
|---|---|---|---|
| left flipper button D9 | 0x01100002 read | SOL_A bit 6 (coil 15), same tick | 17 µs |
| left slingshot 26 | matrix column 1 read | SOL_A bit 4 (coil 13), same tick | 11 µs |
| left bumper 30 | matrix column 1 read | SOL_A bit 0 (coil 9) | 1.26 ms (its rule has a 2 ms debounce) |

Add 0-1 ms for the scan itself. So **a replacement board keeps the original feel if a switch reaches the coil
outputs within about 1 ms.** The sling pulse measured 33.6 ms and the bumper pulse 48.7 ms; the flipper fired
for 40.5 ms, then held at 1 ms on / 11 ms off.

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
- `tools/s_sw.txt` (sling, bumper, ramp hits) and `tools/s_flip.txt` (flipper press) use the `capstart` / `capsave LABEL`
  commands to capture across switch hits.
- `BUSCAP_BOOT=1 PINMAME_NOJIT=1 ./bus_trace tools/s_all.txt out.jsonl` writes `boot.csv` (power-on to 8 s),
  `attract_all.csv` and `game_all.csv`. `tools/ana2.py` summarises them per peripheral and register.
- The traces are not committed (about 130 MB); rerun the command to regenerate them.
