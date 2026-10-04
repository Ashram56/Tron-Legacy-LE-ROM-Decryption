"""Cross-check the downstream text layout guesses (mpfgame scripts/rom_layout.py) against rom_data/deffs.

Usage: python3 deff_xcheck.py [ROM_LAYOUT_DIR]
Reads rom_layout.py (read only; its source paths are pointed at this repo's decompile and the
project-files event_map.csv), runs its deff_calls() and compares each draw with text_draws.csv,
its FONT_LISTS / FONT_TABLES guesses with the ROM data, and writes rom_data/deffs/downstream_xcheck.csv.
"""
import csv
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import rom  # noqa: E402

OUT = os.path.join(REPO, "rom_data", "deffs")


def ilist(a, n=12):
    out = []
    for i in range(n):
        v = rom.u32(a + 4 * i)
        if v == 0 and out:
            break
        out.append(v)
        if v == 0:
            break
    return out


def font_list(a):
    """0-terminated list of u32 font ids (font 0 can only be the terminator after the first entry)."""
    out = []
    for i in range(16):
        v = rom.u32(a + 4 * i)
        if v == 0:
            break
        out.append(v)
    return out


def intval(s):
    try:
        return int(s, 0)
    except (TypeError, ValueError):
        return None


def obs_first(s):
    """'84,20' or '15' observed fields hold the most frequent value first."""
    return s.split(";")[0].split(" ")[0] if s else ""


def main(layout_dir="/home/claude/mpfgame/scripts"):
    sys.path.insert(0, layout_dir)
    rl = importlib.import_module("rom_layout")
    rl.SRC = os.path.join(REPO, "code", "tron_game_decompiled_v2.c")
    rl.EVENT_MAP = "/mnt/project-files/tron/mpf_package/event_map.csv"
    rows = list(csv.DictReader(open(os.path.join(OUT, "text_draws.csv"))))
    by_deff = {}
    for r in rows:
        k = int(r["deff"]) if r["deff"].lstrip("-").isdigit() else "components"
        by_deff.setdefault(k, []).append(r)
    out = []
    calls = rl.deff_calls()
    seen = set()
    for deff, cl in sorted(calls.items()):
        for c in cl:
            key = (deff, c["text"], c.get("font"), c.get("font_list"), c["flags"], c["x"], c["y"])
            if key in seen:
                continue
            seen.add(key)
            cands = [r for r in by_deff.get(deff, []) + by_deff.get("components", []) if r["format"] == c["text"]
                     or (c["text"] == "%s" and r["format"] in ("%s", ""))]
            best, score = None, -1
            for r in cands:
                s = 0
                s += intval(r["flags"]) == c["flags"]
                s += intval(r["x"]) == c["x"]
                s += intval(r["y"]) == c["y"]
                if c.get("font") is not None:
                    s += intval(r["font"]) == c["font"] or obs_first(r["observed_font"]) == str(c["font"])
                if c.get("font_list"):
                    s += r["font_list"].lower().startswith(c["font_list"].lower().replace("0x0", "0x"))
                if s > score:
                    best, score = r, s
            row = {"deff": deff, "text": c["text"], "ds_font": c.get("font"), "ds_font_list": c.get("font_list") or "",
                   "ds_font_table": c.get("font_table") or "", "ds_flags": c["flags"], "ds_x": c["x"], "ds_y": c["y"],
                   "ds_max_width": c.get("max_width", "")}
            if best is None:
                row.update(status="not_in_rom_data", call_site="", font="", font_list="", flags="", x="", y="",
                           observed_font="", observed_xy="", tag="")
            else:
                diffs = []
                if intval(best["flags"]) != c["flags"]:
                    diffs.append("flags")
                if intval(best["x"]) != c["x"]:
                    diffs.append("x")
                if intval(best["y"]) != c["y"]:
                    diffs.append("y")
                f_rom = intval(best["font"])
                f_obs = intval(obs_first(best["observed_font"]))
                if c.get("font") is not None:
                    eff = f_obs if f_obs is not None else f_rom
                    if eff is not None and eff != c["font"]:
                        diffs.append("font")
                if c.get("font_list"):
                    rl_ = best["font_list"].split("=", 1)[1] if "=" in best["font_list"] else ""
                    guess = ",".join(map(str, rl.FONT_LISTS.get(c["font_list"], rl.DEFAULT_LIST)))
                    if rl_ and rl_ != guess:
                        diffs.append("font_list(guess %s)" % guess)
                row.update(status="match" if not diffs else "differs: " + " ".join(diffs), call_site=best["call_site"],
                           font=best["font"], font_list=best["font_list"], flags=best["flags"], x=best["x"],
                           y=best["y"], observed_font=best["observed_font"], observed_xy=best["observed_xy"],
                           tag=best["tag"])
            out.append(row)
    # guessed tables
    extra = []
    for a, guess in rl.FONT_LISTS.items():
        real = font_list(int(a, 16))
        extra.append({"deff": "", "text": "FONT_LISTS " + a, "ds_font_list": ",".join(map(str, guess)),
                      "font_list": "%s=%s" % (a, ",".join(map(str, real))),
                      "status": "match" if real == guess else "differs", "tag": "code"})
    for a, guess in rl.FONT_TABLES.items():
        real = [rom.u32(int(a, 16) + 4 * i) for i in range(5)]
        extra.append({"deff": "", "text": "FONT_TABLES " + a, "ds_font": guess,
                      "font": "%d (by language %s)" % (real[0], ",".join(map(str, real))),
                      "status": "match" if real[0] == guess else "differs", "tag": "code"})
    cols = ["deff", "text", "status", "call_site", "tag", "ds_font", "font", "observed_font", "ds_font_list",
            "font_list", "ds_font_table", "ds_flags", "flags", "ds_x", "x", "ds_y", "y", "observed_xy", "ds_max_width"]
    with open(os.path.join(OUT, "downstream_xcheck.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, cols, extrasaction="ignore")
        w.writeheader()
        for r in out + extra:
            w.writerow(r)
    from collections import Counter
    print(len(out), "downstream draws;", Counter(r["status"].split(":")[0] for r in out))
    print(Counter(r["status"] for r in extra))


if __name__ == "__main__":
    main(*sys.argv[1:])
