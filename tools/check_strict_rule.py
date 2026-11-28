#!/usr/bin/env python3
"""Mechanical check of the owner's STRICT RULE (2026-11-24) on a game repository.

    python check_strict_rule.py [REPO_ROOT]        exit 1 when a check fails

Checks (each failure is printed as FAIL, heuristics as WARN):
  1. CLAUDE.md carries the rule and the working rules 6-7 (no "I continue" turn ends, 15-minute reports).
  2. docs/boards_inventory.md exists, lists every board with its own CPU/MCU/ROM, and every row is "complet".
  3. No data file declares a PinMAME / trace / capture / emulation / render source, unless the path is
     listed in docs/pinmame_waivers.md with "approved by Vincent <date>" (last resort, owner asked first).
     Declared = CSV column source|origin|provenance (or a column ending in _source), JSON key of that name or a
     "capture" key, a "source:" line or a "captured / measured / recorded in the emulator" comment in the first
     10 lines of a text file (a show file, a YAML table). Reference traces (dirs traces/, captures/) are confirm-only and are skipped.
  4. If game code exists (game/ with a non-doc file), docs/functional_diagram.md (or docs/flow/) exists and
     cites ROM addresses: agent C codes nothing before agent A's diagram.
"""
import csv, json, os, re, sys

MARKER = "STRICT RULE: DECOMPILE EVERYTHING"
MARKERS = (MARKER, "Never end a turn by announcing", "progress report at least every 15 minutes")
STATES = {"complet": "complet", "complete": "complet", "partiel": "partiel", "partial": "partiel", "absent": "absent"}
FIELDS = {"source", "origin", "provenance", "src"}
BAD = re.compile(r"pinmame|trace|capture|emulat|render|screenshot|observed in (?:play|the emulator)", re.I)
CAPTURED = re.compile(r"(?:captured|measured|recorded|rendered)\s+(?:in|from|with)\s+(?:the\s+)?(?:emulator|pinmame|libpinmame)", re.I)


def is_source_field(name):
    n = (name or "").lower()
    return n in FIELDS or n.endswith("_source")
SKIP_DIRS = {".git", "node_modules", "traces", "trace", "captures", "__pycache__", ".godot"}
ADDR = re.compile(r"0x[0-9a-fA-F]{3,}|\b[0-9a-fA-F]{1,2}:[0-9a-fA-F]{4}\b|\bFUN_[0-9a-fA-F]+")
TEXT_EXT = (".md", ".txt", ".yaml", ".yml", ".cfg", ".csv", ".json", ".jsonl")


def walk(root):
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            yield os.path.join(base, n)


def waivers(root):
    p = os.path.join(root, "docs", "pinmame_waivers.md")
    ok = set()
    if os.path.isfile(p):
        for line in open(p, encoding="utf-8", errors="replace"):
            m = re.search(r"`([^`]+)`.*approved by Vincent\s+\d{4}-\d{2}-\d{2}", line, re.I)
            if m:
                ok.add(m.group(1).strip("/"))
    return ok


def check_rule_text(root):
    p = os.path.join(root, "CLAUDE.md")
    txt = open(p, encoding="utf-8", errors="replace").read() if os.path.isfile(p) else ""
    return [f'CLAUDE.md missing the rule text "{m}"' for m in MARKERS if m not in txt]


def check_inventory(root):
    p = os.path.join(root, "docs", "boards_inventory.md")
    if not os.path.isfile(p):
        return ["docs/boards_inventory.md missing (step zero: every board with its own CPU/MCU/ROM)"]
    rows, col = [], None
    for line in open(p, encoding="utf-8"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        low = [c.lower() for c in cells]
        if low[0] == "board":                       # a table header: only a table with a decompile column counts
            col = next((i for i, c in enumerate(low) if "decompil" in c), None)
        elif col is not None and not set("".join(cells)) <= set("-: "):
            rows.append((cells + [""] * (col + 1 - len(cells)), col))
    if not rows:
        return ["docs/boards_inventory.md has no board row (columns: Board | CPU | ROM | Decompile state ...)"]
    out = []
    for c, col in rows:
        st = STATES.get(c[col].lower().split()[0] if c[col].strip() else "", None)
        if st is None:
            out.append(f"boards_inventory: board '{c[0]}' has no valid state (complet / partiel / absent): '{c[col]}'")
        elif st != "complet":
            out.append(f"boards_inventory: board '{c[0]}' is {st}, must be complet before any rule is coded from it")
    return out


def declared_sources(path):
    ext = path.lower().rsplit(".", 1)[-1]
    try:
        if ext == "csv":
            with open(path, newline="", encoding="utf-8", errors="replace") as f:
                r = csv.DictReader(f)
                cols = [c for c in (r.fieldnames or []) if is_source_field(c)]
                for row in r:
                    for c in cols:
                        yield row.get(c) or ""
        elif ext in ("json", "jsonl"):
            txt = open(path, encoding="utf-8", errors="replace").read()
            docs = [txt] if ext == "json" else txt.splitlines()[:50]
            for d in docs:
                try:
                    obj = json.loads(d)
                except ValueError:
                    continue
                stack = [obj]
                while stack:
                    o = stack.pop()
                    if isinstance(o, dict):
                        for k, v in o.items():
                            if is_source_field(k) and isinstance(v, str):
                                yield v
                            elif k.lower() == "capture" and isinstance(v, (str, bool)) and v:
                                yield "capture"
                            elif isinstance(v, (dict, list)):
                                stack.append(v)
                    elif isinstance(o, list):
                        stack.extend(o[:2000])
        else:
            for line in list(open(path, encoding="utf-8", errors="replace"))[:10]:
                m = re.match(r"\s*(?:#|//|<!--)?\s*\**(?:source|provenance)\**\s*:\s*(.+)", line, re.I)
                if m and not re.search(r"src/|\.(c|cpp|h)\b", m.group(1)):   # a cited PinMAME source file is documentation
                    yield m.group(1)
                elif re.match(r"\s*(?:#|//|<!--|;)", line) and CAPTURED.search(line):
                    yield CAPTURED.search(line).group(0)
    except OSError:
        return


def check_sources(root):
    ok, out = waivers(root), []
    for p in walk(root):
        rel = os.path.relpath(p, root).replace(os.sep, "/")
        if not rel.lower().endswith(TEXT_EXT) or rel == "docs/pinmame_waivers.md":
            continue
        if os.path.getsize(p) > 50_000_000:
            continue
        for v in declared_sources(p):
            if BAD.search(v):
                if any(rel == w or rel.startswith(w + "/") for w in ok):
                    break
                out.append(f"{rel}: declared source '{v.strip()[:60]}' is an emulator capture (forbidden; decode from the ROM, or ask the owner and list it in docs/pinmame_waivers.md)")
                break
    return out


def check_diagram(root):
    g = os.path.join(root, "game")
    code = [p for p in walk(g) if not p.lower().endswith((".md", ".txt"))] if os.path.isdir(g) else []
    if not code:
        return []
    cands = [os.path.join(root, "docs", "functional_diagram.md")]
    fd = os.path.join(root, "docs", "flow")
    if os.path.isdir(fd):
        cands += list(walk(fd))
    hits = [c for c in cands if os.path.isfile(c) and c.lower().endswith(TEXT_EXT + (".svg", ".html", ".mmd"))
            and ADDR.search(open(c, encoding="utf-8", errors="replace").read())]
    if not hits:
        return ["game/ has code but docs/functional_diagram.md (or docs/flow/) is missing or cites no ROM address: agent A's diagram comes before agent C's code"]
    return []


def warnings(root):
    out = []
    for p in walk(os.path.join(root, "game")):
        if re.search(r"gen_media|from_pinmame|capture", os.path.basename(p), re.I) and p.endswith((".py", ".sh", ".gd")):
            out.append(f"{os.path.relpath(p, root)}: builds game assets from captures? check it decodes the ROM instead")
    return out


def run(root):
    fails = check_rule_text(root) + check_inventory(root) + check_sources(root) + check_diagram(root)
    return fails, warnings(root)


if __name__ == "__main__":
    root = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    fails, warns = run(root)
    for w in warns:
        print("WARN", w)
    for f in fails:
        print("FAIL", f)
    print(f"strict rule: {len(fails)} failure(s), {len(warns)} warning(s)")
    sys.exit(1 if fails else 0)
