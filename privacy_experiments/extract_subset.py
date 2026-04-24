#!/usr/bin/env python3
"""Extract a manageable subset of edges from stackoverflow + wiki-talk datasets."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Dataset"
OUT = ROOT / "privacy_experiments" / "data"
OUT.mkdir(exist_ok=True, parents=True)

SUBSETS = {
    "stackoverflow": (DATA / "sx-stackoverflow" / "out.sx-stackoverflow", 500_000),
    "wiki-talk":     (DATA / "wiki-talk"       / "out.wiki_talk_en",      500_000),
}

def parse_line(line: str):
    # "% asym positive" — skip header
    if line.startswith("%"):
        return None
    # wiki-talk lines use a mix of tabs/spaces: "src\tdst w t"
    parts = line.replace("\t", " ").split()
    if len(parts) < 2:
        return None
    try:
        s = int(parts[0]); d = int(parts[1])
    except ValueError:
        return None
    w = 1
    t = 0
    if len(parts) >= 3:
        try: w = int(parts[2])
        except ValueError: w = 1
    return s, d, w

for name, (path, N) in SUBSETS.items():
    if not path.exists():
        print(f"[skip] {path} missing"); continue
    out = OUT / f"{name}.edges"
    count = 0
    with path.open("r", errors="ignore") as f, out.open("w") as g:
        for line in f:
            r = parse_line(line)
            if r is None: continue
            s, d, w = r
            g.write(f"{s} {d} {w}\n")
            count += 1
            if count >= N:
                break
    print(f"[ok] {name}: {count} edges -> {out}")
