#!/bin/sh
# usage: run_ghidra.sh out.c
cd /home/claude/work && ./ghidra_11.4.2_PUBLIC/support/analyzeHeadless /home/claude/work/gh proj -import gh/flash8m.bin -overwrite -loader BinaryLoader -loader-baseAddr 0x04000000 -processor ARM:LE:32:v4t -scriptPath gh/scripts -preScript TronSetup.java -postScript TronExport.java "$1" > "$1.log" 2>&1
grep -E 'seeded|label fail|Exception' "$1.log" | head
