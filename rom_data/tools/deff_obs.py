"""Parse deff_trace logs (deff_trace.cpp) into per-deff observations.

Usage: python3 deff_obs.py OUT.json LOG [LOG ...]
Each log is read line by line (logs can be large). Output:
  {"runs": [...], "deffs": {id: {"forced": [...], "draws": {site: {...}}, "rng": {...}, "images": {...},
                               "anims": [...], "sleeps": {...}}}, "rng_other": {...}}
A draw is keyed by its call site (return address - 4) and the text API it called; the rendered string,
font, flags, x, y and palette come from the text_draw_str 0x28f74 call that follows it in the same task.
"""
import json
import re
import sys
from collections import defaultdict

TEXT_APIS = {0x28ca8, 0x28d08, 0x28d5c, 0x28dd8, 0x28e48, 0x28eb0, 0x28f34, 0x29174, 0x29178, 0x291e4, 0x291e8,
             0x29248, 0x29384, 0x29388}
KV = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)')


def parse(line):
    p = line.split(" ", 2)
    if len(p) < 2:
        return None
    try:
        t = float(p[0])
    except ValueError:
        return None
    ev = p[1].strip()
    kv = {}
    if len(p) > 2:
        for k, v in KV.findall(p[2]):
            if v.startswith('"'):
                v = v[1:-1].replace('\\"', '"').replace('\\\\', '\\')
            kv[k] = v
    return t, ev, kv


def h(x):
    return int(x, 16)


def main(out, logs):
    D = defaultdict(lambda: {"forced": [], "draws": {}, "rng": {}, "images": {}, "anims": {}, "sleeps": {},
                             "starts": defaultdict(int)})
    rng_other = defaultdict(lambda: {"n": 0, "results": defaultdict(int)})
    runs = []
    for log in logs:
        run = {"log": log, "forced": []}
        items = None
        try:
            items = [x.split(":", 1)[1] if ":" in x else "" for x in open(log + ".items").read().split()]
        except OSError:
            pass
        pending = None      # last TXT event waiting for its STR
        fit = None
        cur = None
        last_txt_lr = None
        for line in open(log, errors="replace"):
            r = parse(line)
            if r is None:
                continue
            t, ev, kv = r
            if ev == "FORCE":
                cur = {"id": int(kv["id"]), "t0": t, "params": None, "shows": 0, "first_show": None, "end": None,
                       "end_active": None, "active_changes": [], "rng": [], "imgs": [], "strings": [], "events": 0,
                       "words": kv.get("w") or (items[int(kv["idx"])] if items and int(kv["idx"]) < len(items) else "")}
                run["forced"].append(cur)
                continue
            if ev == "FORCE_END" and cur is not None:
                cur["end"] = t
                cur["end_active"] = int(kv["active"])
                D[cur["id"]]["forced"].append(cur)
                cur = None
                continue
            if ev == "ACTIVE" and cur is not None:
                cur["active_changes"].append((round(t - cur["t0"], 4), int(kv["id"])))
                continue
            if ev == "SHOW" and cur is not None and int(kv["deff"]) == cur["id"]:
                cur["shows"] += 1
                if cur["first_show"] is None:
                    cur["first_show"] = round(t - cur["t0"], 4)
                cur["last_show"] = round(t - cur["t0"], 4)
                continue
            if ev == "DEFF_START":
                continue
            if ev == "TXT":
                api = h(kv["api"])
                lr = h(kv["lr"])
                if api == 0x29178 and last_txt_lr == lr:
                    continue           # 0x29174 falls through into 0x29178
                last_txt_lr = lr
                deff = int(kv["deff"]) if kv["tid"] == "2" else int(kv["active"])
                if kv["tid"] != "2":
                    deff = -1          # not drawn by a deff task (attract pages run as children with tid 2 too)
                pending = {"deff": deff, "api": api, "site": lr - 4, "regs": [h(kv[k]) for k in ("r0", "r1", "r2", "r3", "ip")],
                           "stack": [h(x) for x in kv["s"].split(",")], "t": t, "forced": cur["id"] if cur else None}
                fit = None
                continue
            if ev == "FIT":
                fit = {"fonts": [int(x) for x in kv["fonts"].split(",")], "list": h(kv["list"]), "maxw": int(kv["maxw"])}
                continue
            if ev == "STR" and pending is not None:
                p = pending
                if cur is not None and p["deff"] == cur["id"]:
                    cur["events"] += 1
                    if kv["str"] not in cur["strings"] and len(cur["strings"]) < 40:
                        cur["strings"].append(kv["str"])
                pending = None
                key = "%x" % p["site"]
                dd = D[p["deff"]]["draws"].setdefault(key, {"api": "%x" % p["api"], "n": 0, "strings": defaultdict(int),
                                                             "fonts": defaultdict(int), "flags": defaultdict(int),
                                                             "xy": defaultdict(int), "colors": defaultdict(int),
                                                             "font_lists": defaultdict(int), "raw": [], "forced_by": defaultdict(int)})
                dd["n"] += 1
                if len(dd["strings"]) < 40:
                    dd["strings"][kv["str"]] += 1
                dd["fonts"][kv["font"]] += 1
                dd["flags"][kv["flags"]] += 1
                dd["xy"]["%s,%s" % (kv["x"], kv["y"])] += 1
                dd["colors"][kv["color"]] += 1
                if fit:
                    dd["font_lists"]["%x:%s:maxw=%d" % (fit["list"], ",".join(map(str, fit["fonts"])), fit["maxw"])] += 1
                dd["forced_by"][str(p["forced"])] += 1
                if len(dd["raw"]) < 6:
                    dd["raw"].append({"regs": ["%x" % x for x in p["regs"]], "stack": ["%x" % x for x in p["stack"]],
                                      "str": kv["str"], "t": p["t"]})
                fit = None
                continue
            if ev == "RNG":
                caller = h(kv["caller"])
                deff = int(kv["deff"]) or int(kv["active"])
                if cur is not None and int(kv["deff"]) == cur["id"]:
                    cur["rng"].append(["%x" % (caller - 4), int(kv["final"])])
                key = "%x" % (caller - 4)
                target = D[deff]["rng"] if int(kv["deff"]) else rng_other
                rr = target.setdefault(key, {"fn": kv["fn"], "n": 0, "results": defaultdict(int), "forced": 0}) if target is not rng_other else rng_other[key]
                rr["n"] += 1
                rr["results"][kv["final"]] += 1
                if kv.get("forced") == "1":
                    rr["forced"] = rr.get("forced", 0) + 1
                continue
            if ev == "IMG":
                deff = int(kv["deff"])
                if cur is not None and deff == cur["id"]:
                    cur["events"] += 1
                    if len(cur["imgs"]) < 2000:
                        cur["imgs"].append(int(kv["img"]))
                key = "%x" % (h(kv["lr"]) - 4)
                im = D[deff]["images"].setdefault(key, {"api": kv["api"], "n": 0, "imgs": set(), "xy": set(), "pal": set()})
                im["n"] += 1
                if len(im["imgs"]) < 400:
                    im["imgs"].add(int(kv["img"]))
                im["xy"].add("%s,%s" % (kv["x"], kv["y"]))
                im["pal"].add(kv["pal"])
                continue
            if ev == "ANIM":
                deff = int(kv["deff"])
                key = "%x:%s-%s:tpf=%s:loops=%s:cues=%s" % (h(kv["lr"]) - 4, kv["first"], kv["last"], kv["tpf"], kv["loops"], kv["cues"])
                D[deff]["anims"][key] = D[deff]["anims"].get(key, 0) + 1
                continue
            if ev == "SLEEP":
                deff = int(kv["deff"])
                key = "%x:%s" % (h(kv["lr"]) - 4, kv["ticks"])
                D[deff]["sleeps"][key] = D[deff]["sleeps"].get(key, 0) + 1
                continue
        runs.append({"log": log, "forced": [(f["id"], round((f["end"] or 0) - f["t0"], 3)) for f in run["forced"]]})

    def plain(o):
        if isinstance(o, dict):
            return {str(k): plain(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [plain(x) for x in o]
        if isinstance(o, set):
            return sorted(o)
        return o
    json.dump({"runs": runs, "deffs": plain(D), "rng_other": plain(rng_other)}, open(out, "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
