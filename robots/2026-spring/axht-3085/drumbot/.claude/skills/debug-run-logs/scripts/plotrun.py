#!/usr/bin/env python3
"""Plot run channels + step events to a PNG. Needs matplotlib (in the project
.venv — run with `.venv/bin/python`, NOT bare python3).

Usage:
  .venv/bin/python plotrun.py RUN_DIR [--t0 S --t1 S] [--game] \
      [-c CHANNEL ...] [--preset heading|line|drive] [--no-events] \
      [--hline CH=VALUE ...] [--out PATH]

Channels:
  * full mcap topic:            raccoon/odometry/wz
  * substring (unique match):   odometry/wz, imu/heading
  * vector field:               gyro/value:z   accel/value:x
  * pseudo channels parsed from libstp.jsonl:
      cmd:vx cmd:vy cmd:wz   commanded chassis velocity (Drive::setVelocity)
      lf:err lf:hdg_err      line-follow tick error / heading error
      lin:yaw_error lin:cross_track   LinearMotion controller state
  * comma-group into ONE subplot: "odometry/wz,cmd:wz" overlays both.

Presets:
  heading: imu/heading | odometry/heading | gyro:z | odometry/wz,cmd:wz
  line:    analog/0..5 | lf:err
  drive:   odometry/vx,cmd:vx | odometry/vy,cmd:vy | odometry/wz,cmd:wz | pos_x,pos_y

Event markers (default on): condition met (red), step starts (blue),
hardStop (black), mission start/finish (green). --no-events disables.

Examples:
  # the "why did it twist during the line follow" view:
  .venv/bin/python plotrun.py RUN --game --t0 12 --t1 18 --preset heading
  # line sensor vs. its black/white thresholds:
  .venv/bin/python plotrun.py RUN --t0 255 --t1 262 -c analog/1 \
      --hline analog/1=3379 --hline analog/1=654
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from runlog import Run

PRESETS = {
    "heading": ["imu/heading", "odometry/heading", "gyro/value:z",
                "odometry/wz,cmd:wz"],
    "line": ["analog/0/value", "analog/1/value", "analog/2/value",
             "analog/3/value", "analog/4/value", "analog/5/value", "lf:err"],
    "drive": ["odometry/vx,cmd:vx", "odometry/vy,cmd:vy",
              "odometry/wz,cmd:wz", "odometry/pos_x,odometry/pos_y"],
}

_EVENT_KINDS = [
    (re.compile(r"condition met:"), "red"),
    (re.compile(r"Drive::hardStop"), "black"),
    (re.compile(r"(Starting|Completed) mission:"), "green"),
    (re.compile(r"^\d+/\d+( > [^:]+)?: [A-Z]"), "tab:blue"),  # step label lines
]


def resolve_topic(run: Run, name: str) -> str:
    """Resolve a substring to a unique mcap topic."""
    topics = list(run.channels().values())
    if name in topics:
        return name
    hits = [t for t in topics if name in t]
    if len(hits) == 1:
        return hits[0]
    raise SystemExit(f"channel '{name}' matches {len(hits)} topics: {hits[:8]}")


def series_for(run: Run, spec: str, t0, t1):
    """Return (label, xs, ys) for one channel spec."""
    if spec.startswith("cmd:"):
        f = spec[4:]
        pts = [(r, d[f]) for r, d in run.cmd_velocities(t0, t1)]
    elif spec.startswith("lf:"):
        f = spec[3:]
        pts = [(d["rel"], d[f]) for d in run.lf_ticks(t0, t1)]
    elif spec.startswith("lin:"):
        f = spec[4:]
        pts = [(d["rel"], d[f]) for d in run.linear_updates(t0, t1)]
    else:
        field = None
        if ":" in spec:
            spec, field = spec.split(":", 1)
        topic = resolve_topic(run, spec)
        if field:
            pts = [(r, d[field]) for r, _t, d in run.mcap([topic], t0, t1)]
            spec = f"{topic}:{field}"
        else:
            pts = []
            for r, _t, d in run.mcap([topic], t0, t1):
                if "value" in d and isinstance(d["value"], (int, float)):
                    pts.append((r, d["value"]))
                else:  # vector channel without :field -> magnitude-less, take x/y/z later
                    return None  # signal caller to expand
            spec = topic
    # break the line at data gaps (>0.5s) instead of drawing a misleading bridge
    xs, ys = [], []
    for i, (x, y) in enumerate(pts):
        if i and x - pts[i - 1][0] > 0.5:
            xs.append(x)
            ys.append(float("nan"))
        xs.append(x)
        ys.append(y)
    return spec, xs, ys


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir")
    ap.add_argument("--t0", type=float, default=None)
    ap.add_argument("--t1", type=float, default=None)
    ap.add_argument("--game", action="store_true", help="t0/t1 + x-axis in game seconds")
    ap.add_argument("-c", "--channel", action="append", default=[],
                    help="channel spec; comma-join specs to overlay in one subplot")
    ap.add_argument("--preset", choices=sorted(PRESETS))
    ap.add_argument("--hline", action="append", default=[],
                    help="CHANNELSPEC=VALUE horizontal threshold line")
    ap.add_argument("--no-events", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    run = Run(args.run_dir)
    gs = run.game_start_rel() or 0.0
    off = gs if args.game else 0.0
    t0 = args.t0 + off if args.t0 is not None else None
    t1 = args.t1 + off if args.t1 is not None else None

    groups = [g.split(",") for g in (args.channel or PRESETS[args.preset or "drive"])]
    if args.preset and args.channel:
        groups = [g.split(",") for g in PRESETS[args.preset]] + groups

    hlines: dict[str, list[float]] = {}
    for h in args.hline:
        ch, v = h.rsplit("=", 1)
        hlines.setdefault(ch, []).append(float(v))

    fig, axes = plt.subplots(len(groups), 1, sharex=True,
                             figsize=(14, 2.2 * len(groups) + 1.5), squeeze=False)
    axes = [a[0] for a in axes]

    for ax, specs in zip(axes, groups):
        for spec in specs:
            res = series_for(run, spec, t0, t1)
            if res is None:  # vector channel: expand x/y/z
                topic = resolve_topic(run, spec.split(":")[0])
                for f in ("x", "y", "z"):
                    label, xs, ys = series_for(run, f"{topic}:{f}", t0, t1)
                    ax.plot([x - off for x in xs], ys, lw=0.8, label=label.split("raccoon/")[-1])
            else:
                label, xs, ys = res
                ax.plot([x - off for x in xs], ys, lw=0.9, marker=".", ms=2,
                        label=label.split("raccoon/")[-1])
            for v in hlines.get(spec, []):
                ax.axhline(v, color="orange", ls="--", lw=0.8)
        ax.legend(loc="upper right", fontsize=7)
        ax.grid(alpha=0.3)

    if not args.no_events:
        seen_y = 0
        for ev in run.steps(t0, t1):
            for pat, color in _EVENT_KINDS:
                if pat.search(ev["msg"]):
                    for ax in axes:
                        ax.axvline(ev["rel"] - off, color=color, lw=0.6, alpha=0.5)
                    axes[0].annotate(ev["msg"][:45], (ev["rel"] - off, 1.02 + 0.06 * (seen_y % 5)),
                                     xycoords=("data", "axes fraction"),
                                     fontsize=5.5, rotation=20, color=color)
                    seen_y += 1
                    break

    unit = "game s" if args.game else "rel s (run start)"
    axes[-1].set_xlabel(f"t [{unit}]")
    fig.suptitle(Path(args.run_dir).name, y=0.995, fontsize=9)
    fig.tight_layout()
    out = args.out or str(Path(args.run_dir) / f"plot_{args.t0 or 0:.0f}-{args.t1 or 0:.0f}{'_game' if args.game else ''}.png")
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    main()
