# rom_data/pro: Tron PRO 1.74 coil data (TRN174VP.BIN)

Coil data read from the Tron **Pro** 1.74 code, next to the LE 1.74 values in `rom_data/io/`. The Pro image
is Stern's `TRN174VP.BIN` (identical to `TRN17402.BIN`, SHA1 `5026e33a8bb00c83caf06891727b8439d1274fbb`). In
PinMAME it is set **`trn_17402`**; PinMAME's `trn_174` is a different 1.74 Pro image that Stern's site does not
offer. The ROM is not in this repository.

Every row has a tag: `code` (read from the ROM) or `observed` (measured in the emulator at the 1 ms coil IRQ).

| File | What |
|---|---|
| `coils_pro.csv` | One row per Pro coil (1-35). Columns: descriptor flags, test pulse ms, ball-search ms, wire colours; every in-game coil call (API + ms); the lamp-matrix leffs whose coil group includes it; the observed on-times; and the LE coil for the same device (by name) with its flags, test ms, game calls and MPF default pulse. |
| `coil_calls_pro.csv` | Every call site of the coil API in the Pro OS + game code, with resolved constant arguments (same columns as `rom_data/io/coil_calls.csv`). |
| `coil_calls_le_vs_pro.csv` | Each LE coil call site paired with the Pro call at the same position in the matched function. Covers 105 of 198 LE call sites; the rest sit in functions the Pro changed or does not have. |
| `coil_rules_pro.json` | Flipper, bumper and sling hardware rules, knocker/meter queues, coil groups, leff coil groups and the shaker table, from the Pro tables. |
| `le_to_pro_functions.csv` | LE -> Pro function address map: 2,420 of the LE's 3,938 seeds. Method: masked byte signatures, then call-graph propagation. |
| `traces/pro_hw_s1.*` | The emulator scenario and its trace (coil driver edges `drv`, coil API `call`, `mark` segments). |

Tools: `rom_data/tools/pro_hw.py` writes the CSV/JSON files. `rom_data/tools/pro_hw_trace.cpp` is
`hw_trace.cpp` with every LE address replaced by its Pro address, run as `trn_17402`. The Pro decompile is
`code/tron_pro_decompiled.c`, annotated by `rules/tools/ghidra/pro/pro_annotate.py`.

## Findings

- **Timing is the same as the LE.** All 105 LE coil calls that pair with a Pro call use the same ms, pattern
  and API.
    - The only coil change in those pairs is the disc direction relay, LE 22 -> Pro 3.
    - The other is one LE call that pulses red disc 31 twice; the Pro pulses 31 then 32.
- **Shaker:** same as the LE. Coil 8, table 200 / 384 / 1024 ms at `0x040bc8e0`, gated by adjustment 86.
  Observed 200.5 / 385 / 1026.7 ms.
- **Back/lower flashers 19, 22, 23, 25.** In every effect where the LE pulses its ramp flashers (19 left ramp,
  25 right ramp) with the backpanel (28), the Pro pulses all four of 19 / 22 / 23 / 25 with 28, using the same
  timing:
    - single pulses: 48 ms;
    - pattern flashes: 50 ms;
    - group pulses: 32 ms;
    - Light Cycle code leff: 18 ms.
  So Pro 19 and 25 take over the LE ramp flashers' slots, and Pro 22 and 23 are extra flashers on what are
  relay outputs on the LE (inferred from the call sequences). Measured directly, a 48 ms `coil_pulse` gives 48.0-48.3 ms on every Pro flasher.
- **Flasher test differences:** Pro 20 / 21 (bottom arch) carry descriptor flags `0x800` (hidden in tests) and
  `0x1000` (left out of the flash-lamp test). The game still drives them, in the Zen effects and the
  all-flasher effects.
- **Descriptor differences:**
    - Pro coil 3 (disc direction relay) has flags `0x10000` with a 64 ms test, where LE 22 had `0x4000` (relay).
    - The wire colours of Pro 3 / 19 / 22 / 23 / 25 differ from the LE coils with those numbers.
- **Matching caveat:** a matched function name means the code has the same shape as the LE function, not that
  every constant is equal. Pairings with unequal call counts are left unpaired.
