# Tron Legacy Pro 1.74 vs LE 1.74

The LE 1.74 ROM (`trn_174h.bin`) has no Pro mode: no model flag, no "PRO" string, and no code path
for Pro hardware. Stern's Pro 1.74 is a separate image. The two Pro downloads Stern offers
(TRNenglish00 and TRNenglish02) hold byte-identical binaries (`TRN174VP.BIN` = `TRN17402.BIN`, SHA1
`5026e33a8bb00c83caf06891727b8439d1274fbb`). The only difference is one README line in the 02 zip:
"CPU [Part #520-5246-02]", a revision of the SAM CPU board. So both Pro builds share one IO map. The
Pro ROM itself is not in this repository.

Data:

- [io/pro_vs_le_io_map.csv](../io/pro_vs_le_io_map.csv): every switch, coil and lamp, side by side by
  number, with where each item sits on the other model.
- [io/le_vs_pro_io.csv](../io/le_vs_pro_io.csv): LE-only devices, the LE code that drives them, and
  their disable adjustments.

## Table addresses

Both ROMs use 24-byte name records (five language pointers, then a zero word). Entry 0 is "INVALID".

| Item | LE 1.74 | Pro 1.74 |
|---|---|---|
| Size | 33,110,916 bytes | 33,005,168 bytes |
| Game info block | 0x36f20: "TRON L.E.", "TRN", "C2" | 0x2fd18: "TRON", "TRN", "B9" |
| Coil names | 0xe0c00 | 0xc5ef4 |
| Coil descriptors (28 bytes) | 0xe0f60 | 0xc6254 |
| Lamp names | 0xe2bf4 | 0xc7e30 |
| Switch names | 0xf2f3c | 0xd79b0 |
| Shaker time table | 0x040d3998 | 0x040bc8e0 |

## IO differences

| IO | Number | LE 1.74 | Pro 1.74 |
|---|---|---|---|
| Switch | 1-4 | T-R-O-N drop targets, sw1 = (T)RON | T-R-O-N standups in reverse order, sw1 = TRO(N) |
| Switch | 54-56 | Recognizer motor positions 1-3 | Not used |
| Coil | 3 | Drop target bank reset | Disc direction relay |
| Coil | 19 | Flash: left ramp | Flash: back center |
| Coil | 22 | Disc direction relay | Flash: lower left |
| Coil | 23 | Recognizer motor relay | Flash: lower right |
| Coil | 25 | Flash: right ramp | Flash: back left |
| Coil | 31 | Flash: red disc | Flash: red disc (left) |
| Coil | 32 | Flash: blue disc | Flash: red disc (right) |
| Lamps | 1-66 | LE matrix | Renumbered almost completely; no Recognizer position lamps |
| Aux | AUX_DRV bits 5/4/3, strobes 0x10/0x20 | Left and right ramp light tubes (RGB) | None: no light tube driver, test or console commands |

These are the same on both models:

- **Shaker:** coil 8, SHAKER MOTOR (OPTIONAL), SOL_B bit 7, wires RED-WHT / BRN-GRY.
    - The coil descriptor matches apart from its name pointer.
    - The time table is 200 / 384 / 1024 ms on both.
    - Adjustment 86 (NONE / MINIMAL / MODERATE / MAXIMAL USE) gates it on both.
- **3-bank motor:** coil 6 and switches 49-53.
- **Disc motor:** coils 5 and 30.
- **Ticket outputs:** aux coils 33-35.
- **All other switches.**

## Rules and adjustments

| Area | LE 1.74 only | Pro 1.74 only |
|---|---|---|
| Adjustments | 1ST / 2ND+ END OF LINE M.B. LETTERS, END OF LINE EXTRA BALL, DISABLE DROP TARGETS, DISABLE RECOGNIZER MOTOR | 1ST LIGHT CYCLE RAMP E.B., 2ND+ LIGHT CYCLE RAMP E.B. EVERY |
| Diagnostics | Recognizer motor test, fiber optic light tube test | None extra |
| Modes | End of Line (Daft Punk) multiball, double jackpot | None extra |

- **Unconditional LE hardware:** the LE builds every LE device without checking for it (for example
  `tron_bank_setup` at 0x0100b294).
- **Disable adjustments:** adjustments 76, 77, 80, 81 and 86 are workarounds for broken hardware, not
  a Pro mode. With 80 on, the code stops firing the reset coil and resets the T-R-O-N bank state in
  software. That is probably close to Pro play, but it is untested.
- **Combo jackpot:** both models keep the End of Line combo jackpot.
- **OS texts:** the Pro adds Norway 5-8 pricing and USB audit-dump and verify texts.

## Method and limits

- **How names were matched:** by number, from each ROM's own name tables. The rules comparison uses
  uppercase strings in the first 0x120000 bytes of each ROM and the Pro README.
- **Pro not decompiled:** the Pro has not been decompiled.
- **Pro lamp matrix:** Pro lamp numbers are not yet mapped to matrix row and column.
- **Model and board checks:** the hardware/software mismatch and country checks are only noted here.
  They are not analysed.
