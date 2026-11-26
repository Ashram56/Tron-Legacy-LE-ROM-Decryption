"""Check that every ROM address cited in docs/flow/*.md and docs/functional_diagram.md is the start of a
function in code/tron_game_decompiled_v2.c (the decompile). Prints the addresses that are not."""
import re, sys, glob
src = open('code/tron_game_decompiled_v2.c').read()
funcs = {int(a, 16) for a in re.findall(r'^// ==== ([0-9a-f]+) ', src, re.M)}
bad = 0
for f in ['docs/functional_diagram.md'] + sorted(glob.glob('docs/flow/*.md')):
    for a in sorted(set(re.findall(r'0x0[01][0-9a-f]{6}|0x0000[0-9a-f]{4}', open(f).read()))):
        v = int(a, 16)
        if v not in funcs and v >= 0x10000 or (v < 0x10000 and v not in funcs):
            print(f, a, 'not a function start'); bad += 1
print('bad', bad)
sys.exit(1 if bad else 0)
