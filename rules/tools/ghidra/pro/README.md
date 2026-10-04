# Pro 1.74 decompile pipeline

1. **Match LE functions into the Pro.** Run `fmatch.py`, then `python3 fprop.py match1.json`, `fextra.py`, and
   `fprop.py` / `fextra.py` again until nothing is added.
    - `fmatch.py` matches by masked byte signatures (BL offsets and pc-relative load offsets masked).
    - `fprop.py` propagates matches through pairs of BL targets.
    - `fextra.py` adds unique 20-byte signatures.
2. **Build the Pro seed files.** `mkpro.py` writes `seeds_final.tsv`, `sigs.tsv` and `ram_symbols.tsv` with Pro
   addresses. RAM names come from literal pools at equal positions in matched functions.
3. **Decompile.** Run Ghidra 11.4.2 headless as in `../run_ghidra.sh`, with `ProSetup.java` and `../TronExport.java`.
    - Import: the first 8 MB of TRN174VP.BIN at 0x04000000.
    - Blocks: OS 0-0x2f9ff, RAM 0x2fa00, GAME 0x01000000 = file 0x40000.
4. **Annotate.** `python3 pro_annotate.py pro_raw.c ../../../../code/tron_pro_decompiled.c`.

Paths inside the scripts are those of the session that ran them (`/home/claude/work/ghp/`, the
scratchpad). Adjust them before re-running.
