#!/usr/bin/env python3
"""Compare a reference trace from the real ROM (tron_ref) with a trace from the MPF/Godot rebuild.

Usage: trace_compare.py reference.jsonl candidate.jsonl [--tol 0.25] [--events score,deff_start,sound,...]

Both files are JSON lines in the schema of tools/trace/README.md ("Trace format"). The rebuild only
needs to log the event kinds it wants checked; by default: score, deff_start, sound, leff_start,
tube_show_start, audit, multiball_start, mark.

For each event kind the two sequences are aligned in order. An event matches when its key fields are
equal and its time differs by at most --tol seconds (timing is measured from the "ready" event, or the
first event, of each file). The report lists, per kind, how many events matched and the first
divergence with a few events of context. Exit code 0 = all compared kinds match.
"""
import argparse, json, sys

KEYS = {
    'score': ('player', 'delta'),
    'score_add': ('points',),
    'deff_start': ('id',),
    'deff_stop': ('id',),
    'sound': ('call',),
    'leff_start': ('id',),
    'leff_stop': ('id',),
    'tube_show_start': ('id',),
    'audit': ('id',),
    'multiball_start': ('balls',),
    'flag_set': ('flag',),
    'flag_clear': ('flag',),
    'lamp': ('lamp', 'state'),
    'coil': ('coil', 'on'),
    'var': ('name', 'value'),
    'mark': ('text',),
    'switch': ('sw',),
}
DEFAULT = 'score,deff_start,sound,leff_start,tube_show_start,audit,multiball_start,mark'


def load(path):
    evs = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                evs.append(json.loads(ln))
    t0 = next((e['t'] for e in evs if e.get('ev') == 'ready'), evs[0]['t'] if evs else 0)
    for e in evs:
        e['rt'] = e['t'] - t0
    return evs


def key(e):
    return tuple(str(e.get(k)).lower() for k in KEYS.get(e['ev'], ()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('reference'); ap.add_argument('candidate')
    ap.add_argument('--tol', type=float, default=0.25)
    ap.add_argument('--events', default=DEFAULT)
    a = ap.parse_args()
    ref, cand = load(a.reference), load(a.candidate)
    ok = True
    for kind in a.events.split(','):
        r = [e for e in ref if e.get('ev') == kind]
        c = [e for e in cand if e.get('ev') == kind]
        n = min(len(r), len(c)); bad = None
        for i in range(n):
            if key(r[i]) != key(c[i]) or abs(r[i]['rt'] - c[i]['rt']) > a.tol:
                bad = i; break
        if bad is None and len(r) != len(c):
            bad = n
        if bad is None:
            print(f'{kind:16s} OK   {len(r)} events')
            continue
        ok = False
        print(f'{kind:16s} DIFF at event #{bad} (reference has {len(r)}, candidate {len(c)})')
        for i in range(max(0, bad - 2), bad + 3):
            rs = f"{r[i]['rt']:8.3f} {key(r[i])}" if i < len(r) else '-'
            cs = f"{c[i]['rt']:8.3f} {key(c[i])}" if i < len(c) else '-'
            print(f'   {">" if i == bad else " "} ref {rs:40s} | cand {cs}')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
