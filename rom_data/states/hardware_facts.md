# Hardware facts: RGB ramp tubes, GI relay, dedicated switches

Data: `hardware_facts.json` (fact rows) and `dedicated_switches.csv` (34 rows). Every row has an address and a
tag: `observed` (seen in the emulator), `code` (read from code or tables), `inferred` (reasoning).
Built by `rom_data/tools/states_build.py` and `states_static.py`. The scenarios are in `traces/`.

## 1. RGB ramp light tubes: is strobe 0x10 left or right?

**Most likely answer: strobe 0x10 = LEFT ramp, 0x20 = RIGHT ramp** (`inferred`). This is not proven on hardware.

| # | Source | 0x10 | 0x20 | Tag | Where |
|---|---|---|---|---|---|
| 1 | ROM console commands | `lrlt` "perform **left** ramp light tube operations" → handler 0x390 → object 0x3b1d8, built with strobe 0x10 | `rrlt` (right) → handler 0xbb4 → object 0x3b504, strobe 0x20 | code | strings 0xd2fcc/0xd2fd4; ctor calls 0x4f0 (r1 = 0x10), 0xd14 (r1 = 0x20) |
| 2 | ROM service test "FIBER OPTIC LIGHT TUBE TEST" | row "L. RAMP:" (msg 0x51e) drives 0x3b1d8 | row "R. RAMP:" (msg 0x51f) drives 0x3b504 | code | 0x1012b50 |
| 3 | ROM tube shows | show 11 (mask 1 = 0x3b1d8, orange) runs while skill shot A runs: task 0x70, the **left** ramp (sw37) | show 12 (mask 2 = 0x3b504, cyan) runs while skill shot B runs: task 0x72, the **right** ramp (sw34) | code | table 0x040e3c88 mask byte +6 (103 shows use 3, one each uses 1 and 2); tube rules 0x1028bac / 0x1028d98 |
| 4 | PinMAME sam.c lines 917-921 | CSTB, lamps 101-103, "Right RGB ramp" | DSTB, lamps 104-106, "Left RGB ramp" | code (external) | comment added in commit 4440bcc4 (2024-02-09, "PWM: rewrite all SAM aux board") with no cited source |
| 5 | Vincent's repo (owner's schematic notes) | bit 4 = ESTB, J3 pin 12 | bit 5 = DSTB, J3 pin 11 | code (external) | It names the strobes "Tron LE fiber optic ramps" but gives no left/right. Its strobe letters differ from PinMAME's. |

Sources 1, 2 and 3 are independent parts of the ROM, and all three pair 0x10 with the left ramp. Only PinMAME's unsourced comment says the opposite.

**How to test this on the real machine:**
1. Open the service menu and run FIBER OPTIC LIGHT TUBE TEST.
2. Use MINUS/PLUS to move the cursor to the `L. RAMP:` R field.
3. Press SELECT. The **left** ramp tube should turn red.
4. Optionally, probe J3 pin 12 at the same time (Vincent: 0x10 = ESTB) to tie the side to the connector pin.

If the right ramp lights instead, the ROM labels are swapped against the wiring, and PinMAME is right.

## 2. GI relay

| Item | Answer | Tag | Address |
|---|---|---|---|
| Bit | Bit 0 of the IO strobe/aux register 0x0240002B. The ROM keeps a shadow copy at RAM 0x3c758, and the IRQ writes it out on every interrupt (0x133e8-0x13418). | code | 0x3c758 |
| Polarity | Active low: **0 = GI on**, 1 = GI off. PinMAME agrees (`gi = (~data & 1) ? 9 : 0`), and so does Vincent (bit 0 = RLY_DRV). | code + observed | |
| Power-up | 0xc914 sets AUX_DRV = 0 and writes shadow = 0xfe, so GI is on from the first write (t 0.3665 s, caller 0x7aa4). | observed | 0xc914 |
| Attract | On. The exception is leff 133 (the game-over show after the match), which turns GI off for about 10 s. | observed | |
| Game | On. Some lamp effects turn it off briefly, for example the bonus (leff 20, about 1.6 s) and the multiball effects 44 and 48-52. | observed | |
| Tilt warning | Off for 15 ticks (leff 11). | observed | 0x2ffa4 |
| Tilt | Off until the end-of-ball task 0x2a releases leff 9 at the drain. | observed | 0x2ff44 |
| Slam | Off (leff 12, a blackout) until the machine resets. After the reset it is on again. | observed | 0x2fefc |

Only one task owns GI at a time:
- The owner (a task pointer) is stored at RAM 0x372d4.
- `gi_off` 0xcaf8 (27 call sites) and `gi_on` 0xcb24 (14) work only for the task that owns GI.
- `claim` 0xc9dc (24) takes ownership by priority.
- `claim_if_free` 0xc988 (3) takes it only when no task owns it.
- `release` 0xca5c turns GI on and clears the owner. It is called from the leff cleanup at 0x8a30, so GI comes back whenever the owning lamp effect ends or is killed.
- 0xca94 (release all) has no BL callers.
- 0xcb50 (raw aux write) is used only by the all-off routine 0x43a4.

`hardware_facts.json` → `gi_call_sites` lists every call site, and `gi_observed_transitions` lists every GI
change seen in the traced scenarios (`gi_and_tilt`, `slam_tilt`, `multiplayer_3p`, `multiplayer_4p`).

## 3. Dedicated switches (`dedicated_switches.csv`)

- The table at 0x040f4074 has 32 records of 32 B each. Its table-of-tables entry is at 0x36dd4, with count 32.
- The ROM switch number of Dn is 128 + n.
- The CSV also has two rows for the matrix cabinet buttons 15 (tournament) and 16 (start).

**D22 / D23:** D22 = **MINUS** (mask 2) and D23 = **PLUS** (mask 4). The ROM's own names, the masks passed to the
coin-door dispatcher 0xfc20, PinMAME's input port (key 8 "Minus" = bit 0x200, key 9 "Plus" = 0x400) and the emulator
all agree. For example, key 8 → `0xfc20(r0 = 0x96 = switch 150 = D22, mask 2)`. Only the comment block in PinMAME
sam.c ("D21 - DED #22 - Plus, D22 - DED #23 - Minus") swaps them.

BACK (D21), pressed in attract when the volume display is not up, adds a service credit (audit 0x24, deff 17).

## Open
- **The tube side.** Only a real machine can settle it (see the test in section 1).
- **Left flipper.** PinMAME switch 84 sent with SetSwitch did not reach the handler 0x102a1b4, while 82 and 88 did. This is a harness limit: the keyboard mapping overrides it.
