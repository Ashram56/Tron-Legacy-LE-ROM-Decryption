"""Summarise coil driver activity from a hw_trace JSON-lines log (drv events, IRQ-accurate).

Groups each coil's on/off edges into bursts (gap > 40 ms ends a burst). A burst is reported as
first on-time, then any PWM tail (on width, period, duty) and total length, plus the nearest preceding
coil API call for that coil (fn, ms, pattern, caller). Usage: python3 hw_pulses.py log.jsonl [--json out]
"""
import json, sys, collections


def bursts(path, gap=0.040):
    ev = collections.defaultdict(list)
    calls = collections.defaultdict(list)
    marks = []
    for line in open(path):
        if '"drv"' not in line and '"call"' not in line and '"mark"' not in line and '"switch"' not in line and '"button"' not in line:
            continue
        e = json.loads(line)
        if e['ev'] == 'drv':
            ev[e['coil']].append(e)
        elif e['ev'] == 'call' and 'coil' in e:
            calls[e['coil']].append(e)
        elif e['ev'] in ('mark', 'switch', 'button'):
            marks.append(e)
    out = []
    for coil, es in sorted(ev.items()):
        pulses = []  # (t_on, on_ms)
        t_on = None
        for e in es:
            if e['on'] == 1:
                t_on = e['t']
            elif t_on is not None:
                pulses.append((t_on, (e['t'] - t_on) * 1000.0))
                t_on = None
        if t_on is not None:
            pulses.append((t_on, None))
        cur = []
        groups = []
        for p in pulses:
            if cur and p[0] - (cur[-1][0] + (cur[-1][1] or 0) / 1000.0) > gap:
                groups.append(cur)
                cur = []
            cur.append(p)
        if cur:
            groups.append(cur)
        for g in groups:
            t0 = g[0][0]
            first = g[0][1]
            tail = g[1:]
            d = {'coil': coil, 't': round(t0, 4), 'first_on_ms': None if first is None else round(first, 2), 'n_pulses': len(g)}
            if tail:
                widths = [w for _, w in tail if w is not None]
                periods = [(b[0] - a[0]) * 1000 for a, b in zip(tail, tail[1:])]
                d['tail_on_ms'] = round(sum(widths) / len(widths), 2) if widths else None
                d['tail_period_ms'] = round(sum(periods) / len(periods), 2) if periods else None
                if d['tail_on_ms'] and d['tail_period_ms']:
                    d['tail_duty'] = round(d['tail_on_ms'] / d['tail_period_ms'], 3)
                last = g[-1]
                d['total_ms'] = round((last[0] - t0) * 1000 + (last[1] or 0), 1)
            c = [x for x in calls[coil] if x['t'] <= t0 + 0.0001 and t0 - x['t'] < 0.2 and x['fn'] not in ('coil_off',)]
            if c:
                c = c[-1]
                d['call'] = {k: v for k, v in c.items() if k not in ('t', 'ev', 'coil')}
            m = [x for x in marks if x['t'] <= t0 + 0.0001]
            if m:
                m = m[-1]
                d['after'] = m.get('text') or ('sw %s' % m['sw'] if 'sw' in m else 'button %s' % m.get('button'))
                d['after_dt_ms'] = round((t0 - m['t']) * 1000, 1)
            out.append(d)
    return out


if __name__ == '__main__':
    res = bursts(sys.argv[1])
    if '--json' in sys.argv:
        json.dump(res, open(sys.argv[sys.argv.index('--json') + 1], 'w'), indent=1)
    for d in res:
        print(json.dumps(d))
