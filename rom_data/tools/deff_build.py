"""Build rom_data/deffs/ from the static pass (deff_static.py) and emulator observations (deff_obs.py).

Usage: python3 deff_build.py STATIC.json OBS.json [OBS2.json ...]
Writes deffs.json, text_draws.csv, font_lists.csv, random_parts.csv into rom_data/deffs/.
"""
import csv
import json
import os
import re
import sys
from collections import defaultdict, OrderedDict

import rom
from rom import u32, u16, u8, foff, msg, hx
import deff_sym as S

REPO = "/home/claude/tron-legacy-le-rom-decryption"
OUT = REPO + "/rom_data/deffs"
PF = "/mnt/project-files/tron/mpf_package"
TICK_MS = 16.26

# hand-resolved facts per call site (tag code; address cited in the text)
SITE_NOTES = {
    0x1023994: ("font and y from the score size table FUN_01022f5c(score, 0): RAM 0x370ac[0] -> ROM 0x40d3484, "
                "20-byte records {u32 min score, u32 font, u32 y, u32 band_top, u32 band_bottom}, first record (in order) "
                "with min <= current player's score (FUN_000233c8 = gf_scores[current_player-1]): "
                ">=100,000,000 font 22 y 18; >=1,000,000 font 17 y 18; >=100,000 font 24 y 21; else font 26 y 21 "
                "(fallback record 0x40d34c0 = font 26 y 21); tables 1/2 (0x40d34d4, 0x40d3524) serve the other "
                "FUN_01022f5c callers; observed with gf_scores[0] 0x21109e4 poked: 150,000 -> font 24 y 21, "
                "2,000,000 -> font 17 y 18, 200,000,000 -> font 22 y 18, 0 -> font 26 y 21 (downstream SCORE_FIT "
                "[26,23,21,19] / rows [21,21,18,16] is wrong)"),
}

FLAG_BITS = OrderedDict([
    ("0x1", "background/loop deff: stored as the default deff RAM 0x381ae and restarted when the foreground deff ends "
            "(deff_start 0x27b94, 0x282e0); it may only replace a running deff when that deff is the default one"),
    ("0x2", "replaceable at equal priority: a new deff of the same priority may replace it (0x381ab & 3 test in 0x27b94)"),
    ("0x4", "no task flag 0x2000 (with 0x1 also clears it; only deff 27 instant info has 0x4)"),
    ("0x10", "do not allocate a fresh DMD page pair on start (none in the table)"),
    ("0x20", "queue when blocked even if the caller did not ask to queue (none in the table)"),
])

TEXT_API_DOC = [
    ("0x28ca8", "text_draw_msg", "r0 msg, r1 page, r2 font, r3 flags, [sp] x, [sp+4] y, [sp+8] palette", None),
    ("0x28d08", "text_draw_msg_buf", "as text_draw_msg but r1 = buffer address (no callers in v1.74)", None),
    ("0x28d5c", "text_printf_msg", "r0 msg (format), r1 page, r2 font, r3 flags, [sp] x, [sp+4] y, [sp+8] palette, varargs from [sp+0xc]", 3),
    ("0x28dd8", "text_printf_msg_buf", "as text_printf_msg but r1 = buffer (no callers in v1.74)", 3),
    ("0x28e48", "text_draw_msg_fit", "r0 msg, r1 page, r2 font list, r3 flags, [sp] x, [sp+4] y, [sp+8] palette, [sp+0xc] max_width; returns font used", None),
    ("0x28eb0", "text_printf_msg_fit", "r0 msg (format), r1 page, r2 font list, r3 flags, [sp] x, [sp+4] y, [sp+8] palette, [sp+0xc] max_width, varargs from [sp+0x10]", 4),
    ("0x28f34", "text_draw_str_page", "r0 char*, r1 page, r2 font, r3 flags, [sp] x, [sp+4] y, [sp+8] palette", None),
    ("0x28f74", "text_draw_str", "core renderer: r0 char*, r1 buffer (0x1080000 + page*0x1000), r2 font, r3 flags, [sp] x, [sp+4] baseline y, [sp+8] palette", None),
    ("0x29174", "text_printf_str_page", "r0 format char*, r1 page, r2 font, r3 flags, [sp] x, [sp+4] y, [sp+8] palette, varargs from [sp+0xc] (mov ip,r0 then falls into 0x29178)", 3),
    ("0x29178", "text_printf_str_page_ip", "entry of 0x29174 with the format in ip (no direct callers)", 3),
    ("0x291e4", "text_printf_str_buf", "r0 format, r1 buffer, ... (no callers in v1.74)", 3),
    ("0x29248", "text_draw_str_fit_page", "r0 char*, r1 page, r2 font list, r3 flags, [sp] x, [sp+4] y, [sp+8] palette, [sp+0xc] max_width", None),
    ("0x2928c", "text_draw_str_fit", "core fit renderer: r0 char*, r1 buffer, r2 font list, ...; picks the first font that fits, calls 0x28f74", None),
    ("0x29384", "text_printf_str_fit_page", "r0 format, r1 page, r2 font list, ..., [sp+0xc] max_width, varargs from [sp+0x10] (no callers in v1.74)", 4),
    ("0x28c1c", "font_fit_msgs", "r0 u16 msg list (0-terminated), r1 font list, r2 max width: first font in which every message fits; 0 if none", None),
    ("0x28c6c", "font_fit_str", "r0 char*, r1 font list, r2 max width: first font in which the string fits; 0 if none", None),
]


def load_names():
    names = {}
    p = PF + "/event_map.csv"
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            names[int(r["deff"])] = r
    return names


def timing_json(d, name):
    p = "%s/media/dmd/%s/timing.json" % (PF, name)
    if os.path.exists(p):
        j = json.load(open(p))
        return {"run_seconds": j.get("run_seconds"), "ended_by_timeout": j.get("ended_by_timeout"),
                "frames": len(j.get("graphics_frames", []))}
    return None


def ram_addrs(expr):
    return sorted(set(re.findall(r"RAM\[(0x[0-9a-f]+)", expr)))


def task_fields(expr):
    return sorted(set(re.findall(r"task\+(0x[0-9a-f]+)", expr)))


def fns(expr):
    return sorted(set(re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\([^()]*\)@(0x[0-9a-f]+)", expr)))


def first(v):
    return v[0] if isinstance(v, list) and v else None


def lst(v):
    if v is None:
        return ""
    if isinstance(v, list):
        return "|".join(str(x) for x in v)
    return str(v)


def main(static_path, obs_paths):
    st = json.load(open(static_path))
    obs_deffs = defaultdict(lambda: {"forced": [], "draws": {}, "rng": {}, "images": {}, "anims": {}, "sleeps": {}})
    rng_other = {}
    for p in obs_paths:
        o = json.load(open(p))
        for k, v in o["deffs"].items():
            od = obs_deffs[int(k)]
            od["forced"] += v["forced"]
            for s, dv in v["draws"].items():
                cur = od["draws"].get(s)
                if cur is None:
                    od["draws"][s] = dv
                else:
                    cur["n"] += dv["n"]
                    for f in ("strings", "fonts", "flags", "xy", "colors", "font_lists", "forced_by"):
                        for kk, vv in dv[f].items():
                            cur[f][kk] = cur[f].get(kk, 0) + vv
                    cur["raw"] = (cur["raw"] + dv["raw"])[:8]
            for s, rv in v["rng"].items():
                cur = od["rng"].setdefault(s, {"fn": rv["fn"], "n": 0, "results": {}, "forced": 0})
                cur["n"] += rv["n"]
                cur["forced"] += rv.get("forced", 0)
                for kk, vv in rv["results"].items():
                    cur["results"][kk] = cur["results"].get(kk, 0) + vv
            for s, iv in v["images"].items():
                cur = od["images"].setdefault(s, {"api": iv["api"], "n": 0, "imgs": [], "xy": [], "pal": []})
                cur["n"] += iv["n"]
                cur["imgs"] = sorted(set(cur["imgs"]) | set(iv["imgs"]))
                cur["xy"] = sorted(set(cur["xy"]) | set(iv["xy"]))
            for s, n in v["anims"].items():
                od["anims"][s] = od["anims"].get(s, 0) + n
            for s, n in v["sleeps"].items():
                od["sleeps"][s] = od["sleeps"].get(s, 0) + n
        for k, v in o.get("rng_other", {}).items():
            cur = rng_other.setdefault(k, {"n": 0, "results": {}})
            cur["n"] += v["n"]
            for kk, vv in v["results"].items():
                cur["results"][kk] = cur["results"].get(kk, 0) + vv

    names = load_names()
    deffs_out = []
    draw_rows = []
    rand_rows = []
    font_lists = {}

    def note_list(addr, src, fonts=None):
        if addr is None:
            return
        a = addr if isinstance(addr, int) else int(addr, 16)
        if a == 0 or foff(a) is None:
            return
        rec = font_lists.setdefault(a, {"fonts": fonts or font_list_rom(a), "used_by": set()})
        rec["used_by"].add(src)

    def font_list_rom(a):
        out = []
        while len(out) < 16:
            w = u32(a)
            if w == 0:
                break
            if w > 64:
                return None
            out.append(w)
            a += 4
        return out

    comp_draw_ids = {}
    for cname, comp in st["components"].items():
        ids = []
        for dr in comp["draws"]:
            ids.append("%s:%x" % (cname, dr["site"]))
        comp_draw_ids[cname] = ids

    def process_draws(label, draws, od, screens_out, is_component=False):
        # merge per call site
        by_site = OrderedDict()
        for dr in draws:
            k = dr["site"]
            if k not in by_site:
                by_site[k] = dict(dr)
                by_site[k]["cond_sets"] = [dr["conds"]]
            else:
                if dr["conds"] not in by_site[k]["cond_sets"]:
                    by_site[k]["cond_sets"].append(dr["conds"])
        # screens: same function + same condition set
        screen_of = {}
        groups = OrderedDict()
        for site, dr in by_site.items():
            key = (dr["fn"], tuple(dr["cond_sets"][0]))
            groups.setdefault(key, []).append(site)
        for n, (key, sites) in enumerate(groups.items()):
            sid = "S%d" % (n + 1)
            for s in sites:
                screen_of[s] = sid
            screens_out.append({"id": sid, "function": hx(key[0]), "function_name": S.FNAME.get(key[0]),
                                "selector": [{"expr": e, "ram_addrs": ram_addrs(e), "task_fields": task_fields(e),
                                              "functions": ["%s@%s" % f for f in fns(e)]} for e in key[1]],
                                "draws": ["%s:%x" % (label, s) for s in sites]})
        rows = []
        for site, dr in by_site.items():
            obs = od["draws"].get("%x" % site) if od else None
            msg_ids = dr.get("msg_ids")
            fmts = dr.get("formats") or []
            font = dr.get("font")
            fl = dr.get("font_lists") or {}
            for a, fonts in fl.items():
                note_list(a, "%s:%x" % (label, site), fonts)
            fp = dr.get("font_picker")
            if fp and fp.get("font_list_addr", "").startswith("0x"):
                note_list(fp["font_list_addr"], "%s:%x (%s)" % (label, site, fp["picker_name"]), fp.get("font_list"))
            notes = []
            if fp:
                notes.append("font chosen at run time by %s at %s (list %s %s, max width %s%s)" % (
                    fp["picker_name"], fp["call_site"], fp.get("font_list_addr"), fp.get("font_list"), fp.get("max_width"),
                    ", English choice %s" % fp["english_choice"] if "english_choice" in fp else ""))
            if dr.get("font_by_language"):
                notes.append("font by language 0-4: %s" % dr["font_by_language"])
            if dr.get("font_list_by_language"):
                notes.append("font list by language 0-4: %s" % dr["font_list_by_language"])
            if dr.get("msg_by_language"):
                notes.append("msg by language 0-4: %s" % dr["msg_by_language"])
            if dr.get("str_source"):
                notes.append("string source: %s%s" % (dr["str_source"], (" " + dr["text_value"]) if dr["str_source"] not in ("rom_string",) else ""))
            if dr.get("english_font_choice") is not None:
                notes.append("English: fit picks font %s" % dr["english_font_choice"])
            for k in ("font", "x", "y", "max_width"):
                if dr.get(k + "_evaluated"):
                    notes.append("%s %s" % (k, dr[k + "_evaluated"]))
            if site in SITE_NOTES:
                notes.append(SITE_NOTES[site])
            x = first(dr.get("x"))
            y = first(dr.get("y"))
            flags = first(dr.get("flags"))
            mw = first(dr.get("max_width")) if dr.get("max_width") else None
            row = OrderedDict()
            row["deff"] = label
            row["screen"] = screen_of[site]
            row["call_site"] = hx(site)
            row["api"] = dr["api"]
            row["api_addr"] = hx(dr["api_addr"])
            row["function"] = hx(dr["fn"])
            row["path"] = ">".join(dr["path"])
            row["msg_id"] = lst([hx(i) for i in msg_ids]) if msg_ids else ""
            row["format"] = lst(fmts)
            row["text_value"] = "" if msg_ids else dr.get("text_value", "")
            row["font"] = lst(font) if font else ("" if fl else dr.get("font_value", ""))
            row["font_list"] = "|".join("%s=%s" % (a, ",".join(map(str, f or []))) for a, f in fl.items()) if fl else (
                "" if not (fp and fp.get("font_list")) else "%s=%s" % (fp["font_list_addr"], ",".join(map(str, fp["font_list"]))))
            row["flags"] = lst(dr.get("flags")) if dr.get("flags") else dr.get("flags_value", "")
            row["x"] = lst(dr.get("x")) if dr.get("x") else dr.get("x_value", "")
            row["y"] = lst(dr.get("y")) if dr.get("y") else dr.get("y_value", "")
            row["max_width"] = (lst(dr.get("max_width")) if dr.get("max_width") else dr.get("max_width_value", "")) if "max_width_value" in dr else ""
            row["color"] = dr.get("color", "")
            row["page"] = dr.get("page", "")
            row["args"] = json.dumps(dr.get("args", []))
            row["selector"] = " OR ".join("(" + " AND ".join(cs) + ")" for cs in dr["cond_sets"] if cs) if any(dr["cond_sets"]) else ""
            if obs:
                strs = sorted(obs["strings"].items(), key=lambda kv: -kv[1])
                row["observed_n"] = obs["n"]
                row["observed_strings"] = json.dumps([s for s, _ in strs[:12]])
                row["observed_font"] = "|".join(sorted(obs["fonts"]))
                row["observed_flags"] = "|".join(sorted(obs["flags"]))
                row["observed_xy"] = "|".join(sorted(obs["xy"]))
                row["observed_font_list"] = "|".join(sorted(obs.get("font_lists", {})))
                row["tag"] = "observed"
                for k in obs.get("font_lists", {}):
                    a, fonts, _ = k.split(":")
                    note_list(int(a, 16), "%s:%x (observed)" % (label, site), [int(f) for f in fonts.split(",") if f != "0"])
                # consistency checks static vs observed
                if font and not fl and not set(obs["fonts"]) <= set(map(str, font)) and not fp:
                    notes.append("observed font %s differs from code %s" % (sorted(obs["fonts"]), font))
                if x is not None and y is not None and dr.get("x") and dr.get("y") and len(dr["x"]) == 1 and len(dr["y"]) == 1 and not (flags or 0) & 6:
                    if "%d,%d" % (x, y) not in obs["xy"] and obs["api"] not in ("28e48", "29248", "28eb0"):
                        notes.append("observed x,y %s differs from code %d,%d" % (sorted(obs["xy"]), x, y))
            else:
                row["observed_n"] = 0
                for k in ("observed_strings", "observed_font", "observed_flags", "observed_xy", "observed_font_list"):
                    row[k] = ""
                row["tag"] = "code"
            row["notes"] = "; ".join(notes)
            rows.append(row)
        # observed sites the static walk did not reach
        if od:
            for s, obs in od["draws"].items():
                site = int(s, 16)
                if site in by_site or is_component:
                    continue
                if label != "status_panel" and site in (0x10231dc, 0x1023258):
                    continue
                strs = sorted(obs["strings"].items(), key=lambda kv: -kv[1])
                row = OrderedDict((k, "") for k in ("deff", "screen", "call_site", "api", "api_addr", "function", "path", "msg_id", "format",
                                                    "text_value", "font", "font_list", "flags", "x", "y", "max_width", "color", "page", "args", "selector"))
                row.update(deff=label, screen="observed_only", call_site=hx(site), api=S.FNAME.get(int(obs["api"], 16), obs["api"]),
                           api_addr="0x" + obs["api"], function=hx(S.func_of(site) or 0))
                row["observed_n"] = obs["n"]
                row["observed_strings"] = json.dumps([s2 for s2, _ in strs[:12]])
                row["observed_font"] = "|".join(sorted(obs["fonts"]))
                row["observed_flags"] = "|".join(sorted(obs["flags"]))
                row["observed_xy"] = "|".join(sorted(obs["xy"]))
                row["observed_font_list"] = "|".join(sorted(obs.get("font_lists", {})))
                row["tag"] = "observed"
                row["notes"] = "drawn while this deff ran but not reached by the static walk (another task or an unresolved pointer)"
                rows.append(row)
        return rows

    for d in st["deffs"]:
        did = d["id"]
        nm = names.get(did, {}).get("name") or "deff_%03d" % did
        od = obs_deffs.get(did)
        rec = OrderedDict()
        rec["id"] = did
        rec["name"] = nm
        rec["table"] = OrderedDict([("entry_addr", hx(d["entry_addr"])), ("fn", hx(d["fn"])), ("fn_name", S.FNAME.get(d["fn"])),
                                    ("flags", hx(d["flags"])), ("flag_bits", [b for b in FLAG_BITS if d["flags"] & int(b, 16)]),
                                    ("background_loop", bool(d["flags"] & 1)), ("priority", d["priority"]), ("byte7", d["byte7"]), ("tag", "code")])
        if d["fn"] == 0:
            rec["stub"] = "null table entry (deff ids start at 1; deff_start 0x27b94 rejects 0 and > 0x91)"
            deffs_out.append(rec)
            continue
        rec["stub"] = d.get("stub") and "function is a bare return (mov pc, lr)"
        screens = []
        rows = process_draws(did, d.get("draws", []), od, screens)
        draw_rows += rows
        # images/timing/fx attached to screens by (function, conds)
        sc_by_key = {}
        for sc in screens:
            sc_by_key[(sc["function"], tuple(x["expr"] for x in sc["selector"]))] = sc
        img_out = []
        for im in d.get("images", []):
            fn_ = hx(S.func_of(im["site"]) or 0)
            key = (fn_, tuple(im["conds"]))
            item = OrderedDict((k, v) for k, v in im.items() if k not in ("path",))
            item["site"] = hx(im["site"])
            item["function"] = fn_
            if im["api"] in ("anim_play", "anim_play_pal") and im.get("first_image_ids") and im.get("last_image_ids"):
                f0, l0 = im["first_image_ids"][0], im["last_image_ids"][0]
                item["frames"] = l0 - f0 + 1
            sc = sc_by_key.get(key)
            if sc is None:
                sc = {"id": "S%d" % (len(screens) + 1), "function": fn_, "function_name": S.FNAME.get(int(fn_, 16)),
                      "selector": [{"expr": e, "ram_addrs": ram_addrs(e), "task_fields": task_fields(e),
                                    "functions": ["%s@%s" % f for f in fns(e)]} for e in im["conds"]], "draws": []}
                screens.append(sc)
                sc_by_key[key] = sc
            sc.setdefault("images", []).append(item)
            ob = od["images"].get("%x" % im["site"]) if od else None
            item["tag"] = "observed" if ob else "code"
            if ob:
                item["observed_images"] = ob["imgs"][:200]
                item["observed_xy"] = ob["xy"]
            img_out.append(item)
        for tm in d.get("timing", []):
            fn_ = hx(S.func_of(tm["site"]) or 0)
            key = (fn_, tuple(tm["conds"]))
            sc = sc_by_key.get(key)
            item = {k: v for k, v in tm.items() if k not in ("path", "conds")}
            item["site"] = hx(tm["site"])
            if sc is not None:
                sc.setdefault("timing", []).append(item)
        for sc in screens:
            sc["components"] = []
        rec["components"] = d.get("components", [])
        rec["functions_reached"] = [{"fn": hx(f["fn"]), "name": f["name"], "depth": f["depth"], "via": f["path"]} for f in d.get("functions", [])]
        rec["screens"] = screens
        rec["selectors"] = []
        for sc in screens:
            for sel in sc["selector"]:
                rec["selectors"].append({"expr": sel["expr"], "ram_addrs": sel["ram_addrs"], "task_fields": sel["task_fields"], "screen": sc["id"]})
        rec["draws"] = [r["deff"] if False else "%s:%s" % (did, r["call_site"][2:]) for r in rows]
        rec["status_panel"] = bool(set(d.get("components", [])) & {"status_panel", "deff_status_frames", "deff_hold_frames", "anim_play", "anim_play_pal"})
        rec["fx"] = [{k: (hx(v) if k == "site" else v) for k, v in f.items()} for f in d.get("fx", [])]
        rec["timing_calls"] = [{k: (hx(v) if k == "site" else v) for k, v in t.items() if k != "path"} for t in d.get("timing", [])]
        rec["indirect_calls"] = d.get("indirect", [])
        if d.get("attract_pages"):
            rec["attract_pages"] = d["attract_pages"]
        # run length
        run = OrderedDict()
        tj = timing_json(did, nm)
        if tj:
            run["capture_timing_json"] = tj
        if od and od["forced"]:
            fr = []
            for f in od["forced"]:
                end = f["end"] - f["t0"] if f["end"] else None
                leave = next((t for t, a in f["active_changes"] if a != did and t > 0.05), None)
                fr.append({"forced_at": round(f["t0"], 3), "task_params_hex": f.get("words") or "",
                           "shows": f["shows"], "strings": f.get("strings", [])[:12], "first_show_s": f["first_show"],
                           "last_show_s": f.get("last_show"), "active_left_s": leave, "ended_s": round(end, 3) if end else None,
                           "hit_hold_limit": bool(end and end > 9.9 and f["shows"] > 0 and (leave is None))})
            run["observed_forced_runs"] = fr
            run["quit_when_forced"] = all(f["shows"] == 0 for f in od["forced"])
        sleeps = od["sleeps"] if od else {}
        run["observed_sleeps"] = sleeps
        rec["run"] = run
        rec["observed"] = bool(od and any(f["shows"] > 0 for f in od["forced"])) if od else False
        # random parts
        rparts = []
        for rr in d.get("rng", []):
            site = rr["site"]
            ob = od["rng"].get("%x" % site) if od else None
            item = OrderedDict([("call_site", hx(site)), ("function", hx(rr["fn"])), ("rng_fn", hx(rr["rng_fn"])), ("rng_name", rr["rng_name"]),
                                ("range", rr.get("n") or rr.get("p") or rr.get("bag")), ("selector", rr["conds"]), ("uses", rr["uses"]),
                                ("observed_results", ob["results"] if ob else None), ("tag", "observed" if ob else "code")])
            rparts.append(item)
        rec["random"] = rparts
        deffs_out.append(rec)

    comps_out = OrderedDict()
    for cname, comp in st["components"].items():
        screens = []
        od = None
        rows = process_draws(cname, comp["draws"], None, screens, is_component=True)
        # observed: status panel draws appear under every deff
        for r in rows:
            n = 0
            strs = defaultdict(int)
            xy = set()
            fonts = set()
            for did, odd in obs_deffs.items():
                ob = odd["draws"].get(r["call_site"][2:])
                if ob:
                    n += ob["n"]
                    for s_, c_ in ob["strings"].items():
                        strs[s_] += c_
                    xy |= set(ob["xy"])
                    fonts |= set(ob["fonts"])
            if n:
                r["observed_n"] = n
                r["observed_strings"] = json.dumps(sorted(strs, key=lambda s_: -strs[s_])[:12])
                r["observed_xy"] = "|".join(sorted(xy))
                r["observed_font"] = "|".join(sorted(fonts))
                r["tag"] = "observed"
        draw_rows += rows
        comps_out[cname] = {"fn": hx(comp["fn"]), "draws": ["%s:%s" % (cname, r["call_site"][2:]) for r in rows], "screens": screens,
                            "timing": [{k: (hx(v) if k == "site" else v) for k, v in t.items() if k != "path"} for t in comp["timing"]],
                            "images": [{k: (hx(v) if k == "site" else v) for k, v in t.items() if k != "path"} for t in comp["images"]]}

    # font lists used anywhere in the ROM by fit calls (global scan)
    for a, fonts, src in global_font_lists():
        note_list(a, src, fonts)

    os.makedirs(OUT, exist_ok=True)
    cols = list(draw_rows[0].keys())
    for r in draw_rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    with open(OUT + "/text_draws.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in draw_rows:
            w.writerow(r)
    with open(OUT + "/font_lists.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["address", "fonts", "count", "used_by", "tag"])
        for a in sorted(font_lists):
            fl = font_lists[a]
            ub = sorted(fl["used_by"])
            tag = "observed" if any("observed" in u for u in ub) else "code"
            w.writerow([hx(a), ",".join(map(str, fl["fonts"] or [])), len(fl["fonts"] or []), " ".join(ub[:30]) + (" ..." if len(ub) > 30 else ""), tag])
    rng_doc = OrderedDict([
        ("state_ram", "0x372c4"),
        ("lcg_next", OrderedDict([("addr", "0xc684"), ("algorithm", "state = state * 0x19660d + 1 (mod 2^32); returns the new state"),
                                  ("tag", "code")])),
        ("random_below", OrderedDict([("addr", "0xc6b4"), ("algorithm", "(n * lcg_next()) >> 32 = uniform 0..n-1"), ("tag", "code")])),
        ("random_percent", OrderedDict([("addr", "0xc6d4"), ("algorithm", "1 if 1 + ((lcg_next() * 100) >> 32) <= p else 0 (p % chance)"), ("tag", "code")])),
        ("bag_weighted_pick", OrderedDict([("addr", "0xc708"), ("algorithm", "weights from an array (fn or constant per entry); entry with weight >= 1000 wins outright, else random_below(sum)"), ("tag", "code")])),
        ("seeding", "rng_seed_default 0xc668 sets 0x04277dc9 at boot (0x7b10); the boot code at 0x119bc/0x11b54 reseeds it (0xc674) for its own use; "
                    "the main loop calls lcg_next once per pass (0x34098), so the state at any deff call depends on how many loop passes ran since boot "
                    "(deterministic in the emulator, not predictable from game state)"),
        ("force", "hook the return of random_below (pc 0xc6d0) or random_percent (pc 0xc704) and set r0 when the caller (saved lr at [sp+4]) "
                  "is the call site + 4; deff_trace.cpp: -rng <site+4>=<value>. A RAM poke of 0x372c4 from a scenario cannot target a value "
                  "because of the per-loop-pass advance"),
        ("other_callers_seen", rng_other),
    ])
    res = OrderedDict([
        ("source", "trn_174h (Tron Legacy LE 1.74); generated by rom_data/tools/deff_static.py + deff_trace.cpp + deff_obs.py + deff_build.py"),
        ("tick_ms", TICK_MS),
        ("deff_table", OrderedDict([("addr", "0x040e1350"), ("count", st["table"]["count"]), ("count_source", st["table"]["count_source"]),
                                    ("record", "8 bytes: u32 fn, u16 flags, u8 priority, u8 unused (always 0)"),
                                    ("flag_bits", FLAG_BITS), ("start_fn", "deff_start 0x280b0(id, queue, force) -> 0x27b94(id, queue, force, 1)"),
                                    ("params", "callers write parameters into the returned task block +0x30..+0x44 (copied from the queue entry when queued)"),
                                    ("tag", "code")])),
        ("text_apis", [dict(zip(("addr", "name", "args", "varargs_from_stack_word"), t)) for t in TEXT_API_DOC]),
        ("rng", rng_doc),
        ("components", comps_out),
        ("deffs", deffs_out),
    ])
    json.dump(res, open(OUT + "/deffs.json", "w"), indent=1, default=str)
    rr = random_rows(deffs_out, st, obs_deffs)
    print("text_draws rows", len(draw_rows), "font lists", len(font_lists), "random rows", len(rr))
    return draw_rows, deffs_out


def global_font_lists():
    """Font lists passed to any fit API / font picker anywhere in the ROM (static, constant arguments)."""
    out = []
    apis = {0x28e48: 2, 0x28eb0: 2, 0x29248: 2, 0x2928c: 2, 0x28c1c: 1, 0x28c6c: 1}
    seen = set()
    for t, reg in apis.items():
        for site, _ in rom.find_bl_callers(t):
            fs = S.func_of(site)
            if fs is None:
                continue
            try:
                f = S.analyse(fs)
            except Exception:
                continue
            c = f.calls.get(site)
            if c is None:
                continue
            v = c.regs[reg]
            vals = [v[1]] if v[0] == "c" else [x[1] for x in v[1] if x[0] == "c"] if v[0] == "phi" else []
            for a in vals:
                if foff(a) is None or a < 0x04000000:
                    continue
                fl = []
                b = a
                while len(fl) < 16:
                    w = u32(b)
                    if w == 0 or w > 64:
                        break
                    fl.append(w)
                    b += 4
                if u32(b) != 0 or not fl:
                    continue
                out.append((a, fl, "%s@%s" % (S.FNAME.get(t, hx(t)), hx(site))))
    return out




# ---------------------------------------------------------------- random parts
CURATED = {
    0x100e900: ("cabinet picture of reel slot k (k = 0,1,2, one call per slot)", "ROM 0x040d2990 u32[4] = cabinet image ids",
                lambda: [(k, "cabinet image %d" % u32(0x040d2990 + 4 * k)) for k in range(4)]),
    0x100e91c: ("decoy award number of reel slot k: (random_below(13) + 1), values >= 13 wrap to 1, bumped by +1 until it differs "
                "from the slots before it (0x0100e960-0x0100e994)", "award table ROM 0x040d29a0 (16 B: u16 id, u16 0, u32 lit icon, u32 unlit icon, u32 fn)",
                lambda: [(k, "award %d icon lit %d / unlit %d" % (u16(0x040d29a0 + 16 * (k - 1)), u32(0x040d29a0 + 16 * (k - 1) + 4), u32(0x040d29a0 + 16 * (k - 1) + 8)))
                         for k in range(1, 13)]),
    0x100ea20: ("slot that shows the real award (task+0x30.u16) when none of the 3 decoys already equals it; that slot's decoy is replaced", None,
                lambda: [(k, "real award in slot %d (x = scroll position + sum of widths of slots before it + 5 px gaps)" % k) for k in range(3)]),
    0x1032934: ("base x of the floating '%luK' score text: {0x21, 0x57, 0x3c}[k] (stack table built at 0x01032908)", None,
                lambda: [(k, "x base %d (x = base + random_below(15) + 16)" % v) for k, v in enumerate((0x21, 0x57, 0x3c))]),
    0x1032940: ("x jitter of the floating '%luK' score text (0..14 px)", None, lambda: [("0..14", "x += value")]),
    0x1032954: ("y start of the floating '%luK' score text: y = value - 1 + 14, then rises 2 px per 6 frames", None, lambda: [("0..7", "y = value + 13")]),
    0x102cf54: ("spinning match digits: random_below(10)*10, redrawn each 4-tick frame for 64 frames, never equal to the previous value; "
                "the final match number is task+0x34 chosen by match() 0x1b660 (random_below(10) at 0x1b6ac)", None, lambda: [("0..9", "match value shown = 10*k")]),
    0x1027380: ("which of 2 clips plays (FUN_01027374, used by deffs 116-124)", "ROM 0x040d3980 {u32 first, u32 last}[2]",
                lambda: [(k, "anim images %d..%d, 3 ticks per frame (deff_status_frames(3))" % (u32(0x040d3980 + 8 * k), u32(0x040d3984 + 8 * k))) for k in range(2)]),
    0x1027484: ("random_below(1) always returns 0: the clip of FUN_01027478 is fixed", "ROM 0x040d3990 {u32 first, u32 last}[1]",
                lambda: [(0, "anim images %d..%d, then speech call 0x111 (round robin index RAM 0x3b620)" % (u32(0x040d3990), u32(0x040d3994)))]),
    0x1019f54: ("50% chance of the speech call 0x0c7 before the jackpot sfx 0x0c6", None, lambda: [(1, "snd_play(0x0c7)"), (0, "no speech")]),
    0x101ab14: ("20% chance of the speech call 0x0cd at the end of the Light Cycle total", None, lambda: [(1, "snd_play(0x0cd)"), (0, "no speech")]),
}


def table_rows(table, n):
    out = []
    for k in range(n):
        e = u32(table + 4 * k)
        f = S.analyse(e)
        anims = [(c.regs[0], c.regs[1], c.regs[2]) for s, c in sorted(f.calls.items()) if c.target in (0x1023edc, 0x1023fe4)]
        desc = "; ".join("anim %s..%s at %s ticks/frame" % (a[1] if a[0] == "c" else "?", b[1] if b[0] == "c" else "?", t[1] if t[0] == "c" else "?")
                         for a, b, t in anims)
        ret = f.ret[1] if f.ret and f.ret[0] == "c" else None
        out.append((k, "fn %s: %s; returns image %s (held as background under the text)" % (hx(e), desc, ret)))
    return out


def random_rows(deffs_out, st, obs_deffs):
    rows = []
    seen = set()
    for rec, d in zip(deffs_out, st["deffs"]):
        for rr in d.get("rng", []):
            site = rr["site"]
            key = (rec["id"], site)
            if key in seen:
                continue
            seen.add(key)
            obs = None
            for rp in rec.get("random", []):
                if rp["call_site"] == hx(site):
                    obs = rp.get("observed_results")
            rng = rr["rng_name"]
            rng_range = rr.get("n") or rr.get("p")
            force = "deff_trace -rng %s=<value>; or hook pc %s (return of %s) and set r0 when [sp+4] == %s" % (
                hx(site + 4), "0xc6d0" if rr["rng_fn"] == 0xc6b4 else "0xc704", rng, hx(site + 4))
            entries = None
            table = ""
            what = ""
            if site in CURATED:
                what, table, fn = CURATED[site]
                entries = fn()
                table = table or ""
            else:
                tu = [u for u in rr["uses"] if u["use"] == "indirect call through table"]
                if tu:
                    tb = int(tu[0]["table"], 16)
                    n = rr.get("n_const") or 0
                    table = "%s (u32 function pointers, %d entries)" % (hx(tb), n)
                    what = "clip played before the text screen; the returned last frame stays as the background"
                    entries = table_rows(tb, n)
                elif rec["id"] == 108:
                    what = "which of 4 clips (switch at 0x010209e0, one function per case)"
                    entries = []
                    for k in range(4):
                        ims = [im for im in d["images"] if any(("== %d" % k) in c and "random_below(4)" in c for c in im["conds"])]
                        entries.append((k, "; ".join("%s %s at x=%s y=%s" % (im["api"], im.get("image"), im.get("x"), im.get("y")) for im in ims)))
            if entries is None:
                entries = [("?", "see uses: " + json.dumps(rr["uses"][:3]))]
            runs = obs_deffs[rec["id"]]["forced"] if rec["id"] in obs_deffs else []
            for k, res in entries:
                ok = obs and str(k) in obs
                if obs and isinstance(k, str) and ".." in k:
                    lo, hi = (int(x) for x in k.split(".."))
                    ok = all(str(v) in obs for v in range(lo, hi + 1))
                seen_runs = [f for f in runs if any(x[0] == "%x" % site and str(x[1]) == str(k) for x in f.get("rng", []))]
                if seen_runs:
                    ims = sorted({i for f in seen_runs for i in f.get("imgs", [])})
                    strs = []
                    for f in seen_runs:
                        for s_ in f.get("strings", []):
                            if s_ not in strs:
                                strs.append(s_)
                    if ims:
                        res = res + " | observed images %d..%d (%d distinct)" % (ims[0], ims[-1], len(ims))
                    if strs:
                        res = res + " | observed text %s" % json.dumps(strs[:8])
                    ok = True
                rows.append(OrderedDict([("deff", rec["id"]), ("call_site", hx(site)), ("function", hx(rr["fn"])), ("rng_fn", hx(rr["rng_fn"])),
                                         ("rng_name", rng), ("range", rng_range), ("picks", what), ("table_addr", table), ("entry", k),
                                         ("result", res), ("how_to_force", force),
                                         ("observed_results", json.dumps(obs) if obs else ""),
                                         ("tag", "observed" if ok else "code")]))
    with open(OUT + "/random_parts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return rows


if __name__ == "__main__":
    import deff_static  # noqa: F401  (loads names into S.FNAME)
    main(sys.argv[1], sys.argv[2:])
