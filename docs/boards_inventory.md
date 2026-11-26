# Boards inventory (step zero, STRICT RULE: DECOMPILE EVERYTHING)

States: `complet`, `partiel`, `absent`. The strict check fails while a row is not `complet`. Started 2026-11-25
from the existing decompile; states are what is evidenced today, to be confirmed in the decompile.

| Board | CPU / MCU | ROM file(s) | Decompile state | Where (decompile, notes) | Open |
|---|---|---|---|---|---|
| Main CPU board (rules, OS, DMD drawing, sound mixing) | ARM7 / AT91 | trn_174h (LE), trn_17402 (Pro) | partiel | assets `code/tron_game_decompiled_v2.c` (LE), `tron_pro_decompiled.c`; functions named where the rules use them | many routines unnamed; dead-code list and per-deff draw routines not complete |
| DMD output (FPGA / page registers on the CPU board) | Xilinx FPGA, configured by the board (no bitstream in the 33110916-byte ROM image: no 0xAA995566 sync word, no "Xilinx"/"FPGA" string, checked 2026-11-26) | n/a | complet (nothing to decompile in the ROM; the CPU side is fully in the main decompile) | page registers 0x01100020/22, DMD pages 0x01080000 (assets `io/bus/`) | confirm there is no DMD firmware to decompile |
| Sound (sample streaming on the CPU board) | none of its own: ADPCM mixed by the ARM FIQ 0x2b600 to 0x2d8b4, DAC on a 3-wire port (P3/P4/P5) | n/a | complet (mixer in the main decompile; no sound CPU firmware in the ROM image) | `snd_play 0x2c8f4` etc. | confirm no separate sound CPU |
| Power driver / I/O board, ramp tube RGB board | to be confirmed | n/a | absent | `io/` tables; tube wiring open (docs/hardware.md) | check whether any board carries a MCU with firmware |
