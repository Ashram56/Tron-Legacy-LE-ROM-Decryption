# Tron Legacy LE 1.74: IO controls and the ramp light tubes

## Short answer
The extra lighting has its own dedicated driver in the ROM. You do not need to recover it from generic bus traffic.

The ROM calls it the **ramp light tube**. Two console commands, `lrlt` ("perform left ramp light tube operations") and `rrlt` ("perform right ramp light tube operations"), are registered for it. There are two driver objects, one per ramp. Each one owns one strobe line on the IO board's aux connector and drives 4-bit RGB (values 0 to 15) with a timed fade. None of the 80 lamp-matrix lamps (`lamps.csv`) is a ramp tube, so these lights exist only on the aux bus.

If "fiber optics" means some other lighting on your machine, tell me which. The only other aux-bus output is the ESTB byte for coils 33-40 (ticket outputs).

## Light tube API (OS code, addresses = file offsets = runtime addresses)
| Address | Function | Notes |
|---|---|---|
| `0x0007cc` | `tube_set(obj, int rgb[3])` | sets the colour instantly. 370 calls from game code |
| `0x000800` | `tube_fade(obj, int rgb[3], ms)` | fades from the current colour to `rgb` over `ms`. 97 calls |
| `0x0007a0` | `tube_set_rgb(obj, r, g, b)` | used by the console `setcolor` command and 10 game call sites |
| `0x000728` / `0x000764` | set / fade, but only if the calling task owns the tube | |
| `0x000600`, `0x000648`, `0x0006bc`, `0x0006e0`, `0x0006f4` | ownership: claim (with priority), release, check | owner stored at obj+0x38 |
| `0x000580` | `tube_init(obj, strobe, rbit, gbit, bbit)` | |
| `0x000874` | `tube_refresh(obj)` | runs every IO interrupt tick (250 µs) from `0x100f0a4`, which the IO interrupt calls at `0x13420` |
| `0x000390` / `0x000bb4` | `lrlt` / `rrlt` console handlers | `setcolor <r> <g> <b>`, `interpolate <r> <g> <b> <msec>` |

Objects:
- Left tube: RAM `0x3b1d8`, strobe 0x10 (CSTB).
- Right tube: RAM `0x3b504`, strobe 0x20 (DSTB).
- Both tubes: R = AUX bit 5 (0x20), G = bit 4 (0x10), B = bit 3 (0x08).

How a refresh works:
1. Interpolate the current colour.
2. Pick one bit-plane per tick (binary-coded modulation, 4 planes, a 15-tick frame of about 3.75 ms).
3. Write the RGB bits to `AUX_DRV` (`0x02400026`).
4. Pulse the tube's strobe bit low then high in `0x0240002B` (shadow byte `0x3c758`).

`light_tube_calls.csv` lists all 480 call sites with the tube, the colour (when it could be resolved statically) and the fade time. 455 of them have a resolved colour. The common colours are off, white (15/15/15), yellow (15/15/0), green, blue, cyan and orange (15/4/0).

## Generic IO (for the other outputs)
`io_registers.csv` maps every IO register to the RAM pointer variable the OS reads it through, and to the code that drives it. The OS never hard-codes register addresses. It loads pointers from a block at RAM `0x37280` to `0x37350`, so searching for those pointers finds every hardware access.
- **Coils** (`coils.csv`, names from the ROM's coil table at `0xe0c00`):
  - Game code sets shadow bytes `0x3b97c[0..4]`.
  - The IO interrupt (around `0x13360`) copies them to SOL_B, SOL_A, SOL_C and FLSH_LMP (coils 1-32), then latches byte 4 to the aux bus with ESTB (coils 33-40).
  - `0x43a4` turns all outputs off.
- **Lamps**: 80-lamp matrix through LMP_STB/LMP_DRV in the IO interrupt (`0x132e0`). Names are in `lamps.csv` (table `0xe2bf4`).
- **GI relay**: bit 0 of `0x0240002B`. `0xcaf8` turns it off and `0xcb24` turns it on, both through an ownership claim at `0xc9dc`. 27 and 14 game call sites.
- **Generic aux write** `0xcb50(strobe_mask, data)`: has only one caller (the all-off reset). The tube driver does its own bus writes.

## Cross-check with PinMAME (`src/wpc/sam.c`)
- PinMAME flags Tron with `SAM_GAME_TRON` ("Board 511-6927-01 TriColor Assembly strobed on C and D outputs").
- It turns `AUX_DRV >> 3` into 3 PWM lamps on each strobe edge: CSTB to lamps 101-103 and DSTB to lamps 104-106. In each group the order is B, G, R.
- **Discrepancy**: PinMAME's comments call CSTB the *right* ramp, but the ROM's own console labels CSTB as the *left* ramp light tube. Either the board is wired crossed or PinMAME's comment is wrong. Check this on the real machine before relying on left/right in PinMAME.

## Cross-check with Vincent's bus analysis (github.com/Ashram56/Stern-SAM-Databus-Analysis)
- His schematic reading confirms the register map above. It also says strobes B to E on J3 pins 9 to 12 drive the Tron LE fiber optic ramps, so the ROM's "ramp light tubes" are those fiber optics.
- **Strobe bit naming**: his schematic gives bit3 = ASTB, bit4 = ESTB, bit5 = DSTB, bit6 = CSTB, bit7 = BSTB. PinMAME uses the reverse (bit3 = BSTB through bit7 = ASTB). With his mapping, the ROM's strobes are:
  - Left tube (0x10) = ESTB, J3 pin 12
  - Right tube (0x20) = DSTB, J3 pin 11
  - Aux coil latch 33-40 (0x40) = CSTB, J3 pin 10
- The tube colour data goes out on J2: R = bit5 = pin 2, G = bit4 = pin 1, B = bit3 = pin 9.
- His captures (`Tron attract.csv`, `Tron start.csv`) are only about 4 IO cycles long. They show the IO interrupt's aux coil latch: `AUX_DRV=0x00`, then strobe register `0xbe` (bit 6 low, GI on), then `0xfe`. That matches the ROM at `0x133d4`. No tube colour writes (strobe register `0xee` or `0xde`) were captured. To see them, capture while a ramp is lit, triggering on address 0xB with data bit 4 or bit 5 low.


## Light effects: the fiber optic shows, mapped to modes
The game never drives the tubes directly from rules code. It starts **light effects** (Stern's "leffs"), much like it starts display effects:
- `leff_start(id)` at `0x101b824`, `leff_stop(id)` at `0x101baac`.
- Table at `0x040e3c88`: 106 records of 12 bytes, `{function, flags, tube mask, priority}`. Tube mask 1 = left, 2 = right, 3 = both. A higher-priority effect takes the tubes from a lower one.
- 99 of the 105 effects produce tube colours. The other 6 (13, 14, 15, 64, 79, 86) claim both tubes but set no colour.

`light_effects.csv` has one row per effect:
- `display_effects`: the DMD effect (deff) that starts it. 65 effects are started from a deff, so the fiber optics show plays alongside that DMD animation.
- `started_by`: the switch or audit-named feature that starts it, when one is found in the call graph.
- `mode_guess_by_code_location`: the feature whose code sits next to the effect. 94 effects have one. Treat it as a likely guess, not a proof.
  - Disc, Quorra, Light Cycle, Daft Punk and Portal multiball
  - Clu and Gem hurry-ups
  - Zuse fast scoring
  - Recognizer battle
  - combos
- Effects 1 to 9 are started with an id from a variable, not a constant. Their sources:
  - Effect 1 cycles 7 colours.
  - Effects 2 to 9 hold one solid colour each: blue, yellow, green, orange, red, white, cyan and amber.
  - They look like per-mode ambient colours. Which mode picks which id has not been traced yet.

**MPF shows**: `mpf/shows/leff_NNN.yaml`. Each effect was run in a CPU emulator (unicorn) with a hook on the tube API and on `task_sleep`. That gives the exact colour, fade and timing sequence. Tick = 16 ms, checked against the ROM's own fade lengths. The 4-bit colours are scaled to hex (15 = ff). Lights are named `l_left_ramp_tube` and `l_right_ramp_tube` (`mpf/lights.yaml`). Kinds:
- `once`: 65
- `loop`: 24, trimmed to one period
- `hold`: 10, a single colour held until stopped

Caveat: emulation follows the default game state. In 2 effects (36 and 88) some colours depend on game state and were not reached. Those shows carry a NOTE line.

## Driving the tubes (for the MPF platform)
1. Every 250 µs, for each tube, write the current bit-plane of R, G and B to AUX_DRV (register 6). Use bit 5 = R, bit 4 = G, bit 3 = B.
2. Then pulse that tube's strobe bit low and back high in register 0xB, keeping bit 0 (GI) and the other strobes as they were.
3. Colours are 4-bit. Cycle bit-planes 0 to 3, holding plane n for 2^n ticks (binary-coded modulation, a 15-tick frame).
4. Fades interpolate linearly in that loop.
5. A host that can only write a colour occasionally can instead write 1-bit colours (each channel on or off). Every colour in the shows is 0 or 15 per channel except orange 15/4/0 and amber 15/8/0.

## Not done yet
- The colour column comes from static analysis. Colours computed at runtime show as `?`.
- Which mode selects the ambient colour effects 1 to 9 has not been traced.
