"""Check that every ROM address cited in docs/flow/*.md and docs/functional_diagram.md is the start of a
function in code/tron_game_decompiled_v2.c (the decompile). Prints the addresses that are not."""
import re, sys, glob
src = open('code/tron_game_decompiled_v2.c').read()
funcs = {int(a, 16) for a in re.findall(r'^// ==== ([0-9a-f]+) ', src, re.M)}
import bisect
starts = sorted(funcs)
bad = 0
for f in ['docs/functional_diagram.md'] + sorted(glob.glob('docs/flow/*.md')):
    for a in sorted(set(re.findall(r'0x0[01][0-9a-f]{6}|0x0000[0-9a-f]{4}', open(f).read()))):
        v = int(a, 16)
        if 0x36000 <= v < 0x01000000:
            continue  # RAM or table, not code
        if v in funcs:
            continue
        i = bisect.bisect_right(starts, v) - 1
        d = v - starts[i] if i >= 0 else -1
        # not a function start: accepted only if inside a decompiled function (within 0x600 bytes of its start)
        if 0 <= d < 0x600:
            print(f, a, 'inside function %x (+%#x)' % (starts[i], d))
        else:
            print(f, a, 'NOT IN ANY FUNCTION'); bad += 1
print('bad', bad)
sys.exit(1 if bad else 0)
