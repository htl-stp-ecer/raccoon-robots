#!/usr/bin/env python3
"""Compare calibration values across runs — answers "why did the sensor
instantly trigger / compare thresholds with previous runs" in one shot.

Usage:
  python3 calibdiff.py RUN_DIR [RUN_DIR ...]
  python3 calibdiff.py --last 5          # newest N runs in .raccoon/downloads

Extracted from libstp.jsonl:
  * "Applied calibration set '<set>_port<N>': black=..., white=..."
  * "Calibration successful (port N): whiteThreshold=..., blackThreshold=..."
  * "Analog calibration done: port=N set='..' min=.. max=.. threshold=.."
  * "Applied forward trim scale X"
Values that deviate > --tol (default 15%) from the column median are marked *!*.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

PATTERNS = [
    ("applied", re.compile(
        r"Applied calibration set '(?P<set>[^']+)': black=(?P<black>[\d.]+), white=(?P<white>[\d.]+)")),
    ("success", re.compile(
        r"Calibration successful \(port (?P<port>\d+)\): whiteThreshold=(?P<white>[\d.]+), "
        r"blackThreshold=(?P<black>[\d.]+), separation=(?P<sep>[\d.]+)")),
    ("analog_done", re.compile(
        r"Analog calibration done: port=(?P<port>\d+) set='(?P<set>[^']+)' min=(?P<min>\d+) "
        r"max=(?P<max>\d+) threshold=(?P<thr>\d+).*?flank_threshold=(?P<flank>\d+)")),
    ("fwd_trim", re.compile(r"Applied forward trim scale (?P<scale>[\d.]+)")),
]


def extract(run_dir: Path) -> dict[str, float]:
    """key -> value, e.g. 'default_port0.black' -> 3451.8, 'fwd_trim' -> 1.0"""
    vals: dict[str, float] = {}
    path = run_dir / "libstp.jsonl"
    if not path.exists():
        return vals
    with path.open() as f:
        for line in f:
            if "alibrat" not in line:
                continue
            try:
                msg = json.loads(line)["msg"]
            except (json.JSONDecodeError, KeyError):
                continue
            for kind, pat in PATTERNS:
                m = pat.search(msg)
                if not m:
                    continue
                g = m.groupdict()
                if kind == "applied":
                    vals[f"{g['set']}.black"] = float(g["black"])
                    vals[f"{g['set']}.white"] = float(g["white"])
                elif kind == "success":
                    # 'applied' lines carry the set name; keep success only as fallback
                    vals.setdefault(f"port{g['port']}.black", float(g["black"]))
                    vals.setdefault(f"port{g['port']}.white", float(g["white"]))
                elif kind == "analog_done":
                    base = f"{g['set']}_p{g['port']}"
                    vals[f"{base}.thr"] = float(g["thr"])
                    vals[f"{base}.flank"] = float(g["flank"])
                elif kind == "fwd_trim":
                    vals["fwd_trim"] = float(g["scale"])
    return vals


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("runs", nargs="*")
    ap.add_argument("--last", type=int, default=None,
                    help="use the newest N runs from .raccoon/downloads")
    ap.add_argument("--tol", type=float, default=0.15,
                    help="flag deviation from median beyond this fraction")
    args = ap.parse_args()

    dirs = [Path(r) for r in args.runs]
    if args.last:
        dl = Path(".raccoon/downloads")
        dirs += sorted((d for d in dl.iterdir() if d.is_dir()),
                       key=lambda d: d.name.split("_")[-1])[-args.last:]
    if not dirs:
        ap.error("no runs given (pass dirs or --last N)")

    data = {d.name: extract(d) for d in dirs}
    keys = sorted({k for v in data.values() for k in v})
    if not keys:
        sys.exit("no calibration lines found in any run")

    w = max(len(k) for k in keys) + 1
    cols = list(data)
    print(" " * w + "  ".join(f"{c[-15:]:>15}" for c in cols))
    for k in keys:
        vals = [data[c].get(k) for c in cols]
        present = [v for v in vals if v is not None]
        med = statistics.median(present)
        cells = []
        for v in vals:
            if v is None:
                cells.append(f"{'—':>15}")
            else:
                flag = " !" if med and abs(v - med) / max(abs(med), 1e-9) > args.tol else ""
                cells.append(f"{v:>13.1f}{flag:2}")
        print(f"{k:<{w}}" + "  ".join(cells))
    print(f"\n(!) = >{args.tol:.0%} deviation from row median")


if __name__ == "__main__":
    main()
