"""Helper library for analysing cube-bot run artifacts.

A "run" is a directory under .raccoon/downloads/runN_YYYYMMDD-HHMMSS/ produced by
raccoon_cli. It bundles a text step log (libstp.jsonl), an MCAP sensor recording
(sensors.mcap), command traces and systemd journals.

The single most important thing this module encapsulates is the TIME MAPPING
between the two main sources, which is easy to get catastrophically wrong:

  * libstp.jsonl "t"    -> LOCAL wall-clock string (e.g. "2026-07-13T10:55:43.713").
                           The timezone is NOT in the string; derive it from run.json.
  * libstp.jsonl "elapsed" -> DO NOT USE for correlation. It resets per mission /
                           is not a monotonic run clock. It will send you ~130s off.
  * sensors.mcap log_time -> UTC epoch nanoseconds.
  * mcap message payloads often carry their own "t" -> UTC epoch MICROSECONDS.

All timestamps returned by this module are UTC epoch seconds (float), so libstp
events and mcap samples land on the same axis and can be compared directly.

Typical use:

    from runlog import Run
    run = Run("/path/to/.raccoon/downloads/run1_20260713-105246")

    # When did mission events happen, on the shared clock?
    for ev in run.libstp(grep="M060"):
        print(run.rel(ev["epoch"]), ev["msg"])

    # Pull a sensor channel over a time window (seconds relative to run start)
    for e, v in run.mcap_scalar("raccoon/odometry/pos_x", t0=168, t1=192):
        print(e, v)

    # Reproduce what on_incline() saw (raw-accel tilt, EMA alpha=0.2)
    for e, tilt in run.accel_tilt(t0=168, t1=192, alpha=0.2):
        ...
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

# libstp lines that are per-tick noise, not step milestones
_NOISE_RE = re.compile(
    r"LinearMotion update|scaled cmd|Drive::setVelocity|lf tick|black=|"
    r"estimateState|VelocityController|velocity controllers|Timing anomaly|"
    r"Establishing timing baseline"
)
_TICK_RE = re.compile(
    r"lf tick: mode=(?P<mode>\d+) err=(?P<err>-?[\d.]+) corr=(?P<corr>-?[\d.]+) -> "
    r"vx=(?P<vx>-?[\d.]+) vy=(?P<vy>-?[\d.]+) wz=(?P<wz>-?[\d.]+).*?"
    r"heading_err=(?P<hdg_err>-?[\d.]+)rad, dt=(?P<dt>[\d.]+)"
)
_NUM = r"-?[\d.]+(?:[eE][+-]?\d+)?"
_SETVEL_RE = re.compile(
    rf"Drive::setVelocity vx=(?P<vx>{_NUM}), vy=(?P<vy>{_NUM}), wz=(?P<wz>{_NUM})"
)
_LINUPD_RE = re.compile(
    r"LinearMotion update: primary=(?P<primary>-?[\d.]+) m, target=(?P<target>-?[\d.]+) m, "
    r"error=(?P<error>-?[\d.]+) m, cross_track=(?P<cross_track>-?[\d.]+) m, "
    r"heading=(?P<heading>-?[\d.]+) rad, yaw_error=(?P<yaw_error>-?[\d.]+) rad"
)


class Run:
    def __init__(self, run_dir: str | Path):
        self.dir = Path(run_dir)
        if not self.dir.is_dir():
            raise FileNotFoundError(f"run dir not found: {self.dir}")
        self.run_meta = json.loads((self.dir / "run.json").read_text())
        self._tz = self._derive_tz()
        # run-start epoch: prefer manifest window_start_us, else run.json local time
        self._t0_epoch = self._derive_t0()

    # ---- time -------------------------------------------------------------
    def _derive_tz(self) -> timezone:
        """Local offset for libstp 't' strings, derived from run.json.

        started_at_utc vs started_at_local give the offset without hardcoding.
        """
        utc = datetime.fromisoformat(self.run_meta["started_at_utc"].replace("Z", "+00:00"))
        loc = datetime.fromisoformat(self.run_meta["started_at_local"])
        off_h = (loc - utc.replace(tzinfo=None)).total_seconds() / 3600
        return timezone(timedelta(hours=round(off_h * 4) / 4))  # round to 15 min

    def _derive_t0(self) -> float:
        man = self.dir / "manifest.json"
        if man.exists():
            m = json.loads(man.read_text())
            ws = m.get("run", {}).get("start_time")
            # manifest cmd_trace.window_start_us is the most reliable epoch anchor
            wsu = m.get("cmd_trace", {}).get("window_start_us")
            if wsu:
                return wsu / 1e6
        # fallback: parse local start with derived tz
        loc = datetime.fromisoformat(self.run_meta["started_at_local"]).replace(tzinfo=self._tz)
        return loc.timestamp()

    def local_to_epoch(self, t_str: str) -> float:
        """Convert a libstp 't' local wall-clock string to UTC epoch seconds."""
        return datetime.fromisoformat(t_str).replace(tzinfo=self._tz).timestamp()

    def rel(self, epoch_s: float) -> float:
        """Seconds since run start (for readable axes). Works for any epoch_s."""
        return epoch_s - self._t0_epoch

    # ---- libstp step log --------------------------------------------------
    def libstp(self, grep: str | None = None, level: str | None = None,
               func: str | None = None, file: str | None = None):
        """Yield dicts from libstp.jsonl with an added 'epoch' (UTC epoch s) and
        'rel' (s since run start). NOTE: the original 'elapsed' field is left in
        but must NOT be used for cross-source correlation.

        Each record also carries the source location: 'file', 'line', 'func'
        (e.g. linear_motion.cpp / line_follow.py — points into raccoon-lib) and
        'level' (trace < debug < info < warning). func/file params filter by
        substring — often more precise than grep on the message text."""
        path = self.dir / "libstp.jsonl"
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if grep and grep not in line:
                    continue
                d = json.loads(line)
                if level and d.get("level") != level:
                    continue
                if func and func not in d.get("func", ""):
                    continue
                if file and file not in d.get("file", ""):
                    continue
                d["epoch"] = self.local_to_epoch(d["t"])
                d["rel"] = d["epoch"] - self._t0_epoch
                yield d

    def warnings(self):
        """All warning-and-above lines — the run-health one-shot. Catches e.g.
        'reliable command ... not acked — retransmitting' (servo/motor cmd lost),
        'background task(s) still running', calibration complaints."""
        for ev in self.libstp():
            if ev.get("level") not in ("trace", "debug", "info"):
                yield ev

    # ---- game clock ---------------------------------------------------------
    def game_start_rel(self) -> float | None:
        """rel seconds of the first NON-setup 'Starting mission:' line.

        Users think in "game seconds" (time since the pre-start gate released,
        i.e. since the first main mission started). game_t = rel - game_start_rel().
        Returns None if no main mission ever started."""
        for ev in self.libstp(grep="Starting mission:"):
            name = ev["msg"].split("Starting mission:")[-1].strip()
            if "Setup" not in name and not name.startswith("M000"):
                return ev["rel"]
        return None

    def game_to_rel(self, game_s: float) -> float:
        gs = self.game_start_rel()
        if gs is None:
            raise ValueError("no main mission start found — game clock undefined")
        return gs + game_s

    # ---- parsed step/motion streams ----------------------------------------
    # per-tick source locations (file basename, func) — filtered from steps().
    # More robust than msg regexes: survives message-text changes in raccoon.
    _TICK_FUNCS = {
        ("linear_motion.cpp", "update"), ("drive.cpp", "setVelocity"),
        ("directional_line_follow_motion.cpp", "update"),
        ("turn_motion.cpp", "update"), ("mecanum.cpp", "estimateState"),
        ("drive.cpp", "estimateState"), ("velocity_controller.cpp", "reset"),
    }

    def steps(self, t0: float | None = None, t1: float | None = None):
        """Yield only step-milestone events (per-tick noise filtered out):
        mission start/finish, step Executing/labels, condition met/advanced,
        hardStop, LinearMotion/LineFollow started, Loop stats. This is the view
        you want first when asking "what did the robot do between X and Y"."""
        for ev in self.libstp():
            if t0 is not None and ev["rel"] < t0:
                continue
            if t1 is not None and ev["rel"] > t1:
                continue
            loc = (ev.get("file", "").rsplit("/", 1)[-1], ev.get("func", "").rsplit(".", 1)[-1])
            if loc in self._TICK_FUNCS:
                continue
            if _NOISE_RE.search(ev["msg"]):
                continue
            yield ev

    def lf_ticks(self, t0=None, t1=None):
        """Parse 'lf tick' line-follow ticks -> dicts with rel, mode, err, corr,
        vx, vy, wz, hdg_err, dt (floats). err is the line error (saturates at
        ±0.5 = sensor fully off the edge), wz includes the heading-hold output."""
        for ev in self.libstp(grep="lf tick"):
            if t0 is not None and ev["rel"] < t0:
                continue
            if t1 is not None and ev["rel"] > t1:
                continue
            m = _TICK_RE.search(ev["msg"])
            if m:
                d = {k: float(v) for k, v in m.groupdict().items()}
                d["rel"] = ev["rel"]
                yield d

    def cmd_velocities(self, t0=None, t1=None):
        """Parse Drive::setVelocity lines -> (rel, {vx, vy, wz}). This is the
        COMMANDED chassis velocity; compare against odometry vx/vy/wz to see
        whether the robot actually did what it was told."""
        for ev in self.libstp(grep="Drive::setVelocity"):
            if t0 is not None and ev["rel"] < t0:
                continue
            if t1 is not None and ev["rel"] > t1:
                continue
            m = _SETVEL_RE.search(ev["msg"])
            if m:
                yield ev["rel"], {k: float(v) for k, v in m.groupdict().items()}

    def linear_updates(self, t0=None, t1=None):
        """Parse LinearMotion update lines -> dicts with rel, primary, target,
        error, cross_track, heading, yaw_error."""
        for ev in self.libstp(grep="LinearMotion update"):
            if t0 is not None and ev["rel"] < t0:
                continue
            if t1 is not None and ev["rel"] > t1:
                continue
            m = _LINUPD_RE.search(ev["msg"])
            if m:
                d = {k: float(v) for k, v in m.groupdict().items()}
                d["rel"] = ev["rel"]
                yield d

    # ---- cmd_trace ----------------------------------------------------------
    def cmd_trace(self, t0=None, t1=None, kind: str | None = None, robot: bool = True):
        """Yield (rel, dict) from cmd_trace[.robot].jsonl. 'ts_us' is UTC epoch
        microseconds. kind filters e.g. 'motor_mode', 'motor_cmd', 'servo_cmd'."""
        name = "cmd_trace.robot.jsonl" if robot else "cmd_trace.jsonl"
        path = self.dir / name
        if not path.exists():
            return
        with path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                rel = d["ts_us"] / 1e6 - self._t0_epoch
                if t0 is not None and rel < t0:
                    continue
                if t1 is not None and rel > t1:
                    continue
                if kind and d.get("kind") != kind:
                    continue
                yield rel, d

    # ---- freeze / stall detection -------------------------------------------
    def freezes(self, min_gap_s: float = 0.25):
        """Detect suspicious dead-times, sorted by rel. Sources:
          * libstp: gap between consecutive log lines (the asyncio loop logs
            every tick while a motion runs, so >250ms mid-motion is a stall;
            gaps while only servos run are normal — check context!)
          * mcap accel channel (~175 Hz ungated): publish gap => reader/SPI or
            Pi-wide stall (see project memories on freeze classes)
          * stm32 journal: 'SLOW LOOP' lines (deviceUpdate SPI stalls)
        Returns list of dicts: {rel, dur, source, detail}."""
        idle = re.compile(
            r"button|Button|UI RX|screen_answer|WaitFor|Wait\(|keypad|gate|Gate|"
            r"SetServoPosition|SlowServo|Finished Sequential|Finished Parallel")
        out = []
        prev = None
        for ev in self.libstp():
            if prev is not None and ev["rel"] - prev > min_gap_s and not idle.search(ev["msg"]):
                out.append({"rel": prev, "dur": ev["rel"] - prev,
                            "source": "libstp", "detail": f"log gap before: {ev['msg'][:60]}"})
            prev = ev["rel"]
        last = None
        for rel, _t, _d in self.mcap(["raccoon/accel/value"]):
            if last is not None and rel - last > min_gap_s:
                out.append({"rel": last, "dur": rel - last,
                            "source": "mcap/accel", "detail": "accel publish gap (reader or Pi stall)"})
            last = rel
        jr = self.dir / "journal.stm32-data-reader.jsonl"
        if jr.exists():
            with jr.open() as f:
                for line in f:
                    if "SLOW LOOP" in line:
                        try:
                            d = json.loads(line)
                            ts = d.get("__REALTIME_TIMESTAMP") or d.get("ts_us")
                            rel = int(ts) / 1e6 - self._t0_epoch if ts else float("nan")
                            out.append({"rel": rel, "dur": float("nan"),
                                        "source": "stm32-journal",
                                        "detail": (d.get("MESSAGE") or "")[:100]})
                        except (json.JSONDecodeError, TypeError, ValueError):
                            pass
        out.sort(key=lambda d: d["rel"])
        return out

    # ---- mcap sensor channels --------------------------------------------
    def channels(self) -> dict[int, str]:
        from mcap.reader import make_reader

        with (self.dir / "sensors.mcap").open("rb") as f:
            summ = make_reader(f).get_summary()
            return {ch.id: ch.topic for ch in summ.channels.values()}

    def mcap(self, topics: list[str], t0: float | None = None, t1: float | None = None):
        """Yield (rel_s, topic, payload_dict) for the given topics.

        t0/t1 are in seconds SINCE RUN START (i.e. same units as .rel()). Payload
        is the decoded JSON message (all sensor schemas here are jsonschema)."""
        from mcap.reader import make_reader

        with (self.dir / "sensors.mcap").open("rb") as f:
            for _sch, ch, msg in make_reader(f).iter_messages(topics=topics):
                rel = msg.log_time / 1e9 - self._t0_epoch
                if t0 is not None and rel < t0:
                    continue
                if t1 is not None and rel > t1:
                    continue
                yield rel, ch.topic, json.loads(msg.data)

    def mcap_scalar(self, topic: str, t0=None, t1=None):
        """Yield (rel_s, value) for a scalar_f/scalar_i32 channel."""
        for rel, _t, d in self.mcap([topic], t0, t1):
            yield rel, d["value"]

    # ---- derived: IMU tilt as on_incline/on_level see it ------------------
    def accel_tilt(self, t0=None, t1=None, alpha: float = 0.2, up_axis: str = "z"):
        """Reproduce raccoon on_incline/_InclinationCondition tilt.

        tilt = acos(|a_up| / |a|) on an EMA-smoothed raw accel vector.
        Returns (rel_s, tilt_deg). Default alpha=0.2 matches the library.

        Reality check when reading these: while driving/arm-moving the raw accel
        is dominated by vibration and the robot's own acceleration (|a| swings far
        from 1g). Compare against a strong 1s moving-average to see the TRUE tilt
        vs. what the weak EMA let through."""
        idx = {"x": 0, "y": 1, "z": 2}[up_axis]
        grav = None
        for rel, _t, d in self.mcap(["raccoon/accel/value"], t0, t1):
            a = (d["x"], d["y"], d["z"])
            if grav is None:
                grav = a
            else:
                grav = tuple(alpha * a[i] + (1 - alpha) * grav[i] for i in range(3))
            mag = math.sqrt(sum(g * g for g in grav))
            tilt = math.degrees(math.acos(min(1.0, abs(grav[idx]) / mag))) if mag > 1e-6 else 0.0
            yield rel, tilt


def _cli():
    import argparse

    p = argparse.ArgumentParser(
        description="Inspect a raccoon run dir. Subcommands: info (default), "
                    "timeline, freezes. Time args accept rel seconds; with "
                    "--game they are interpreted as game seconds (since first "
                    "main mission start).")
    p.add_argument("run_dir")
    p.add_argument("cmd", nargs="?", default="info",
                   choices=["info", "timeline", "freezes", "warnings"])
    p.add_argument("t0", nargs="?", type=float, default=None)
    p.add_argument("t1", nargs="?", type=float, default=None)
    p.add_argument("--game", action="store_true", help="t0/t1 are game seconds")
    p.add_argument("--grep", default=None, help="timeline: extra substring filter")
    p.add_argument("--level", default=None, help="timeline: only this level (trace/debug/info/warning)")
    p.add_argument("--func", default=None, help="timeline: only lines from this source func (substring)")
    p.add_argument("--loc", action="store_true", help="timeline: append file:line source location")
    args = p.parse_args()

    run = Run(args.run_dir)
    t0, t1 = args.t0, args.t1
    if args.game:
        t0 = run.game_to_rel(t0) if t0 is not None else None
        t1 = run.game_to_rel(t1) if t1 is not None else None

    gs = run.game_start_rel()

    def fmt(rel):
        g = f" game={rel - gs:7.2f}" if gs is not None else ""
        return f"rel={rel:8.2f}{g}"

    if args.cmd == "info":
        print(f"run start epoch = {run._t0_epoch:.3f}  tz = {run._tz}")
        if gs is not None:
            print(f"game start (first main mission) at rel = {gs:.2f}s  ->  game_t = rel - {gs:.2f}")
        print("channels:")
        for cid, topic in run.channels().items():
            print(f"  {cid:3d} {topic}")
        print("\nmission events (grep 'mission'):")
        for ev in run.libstp(grep="mission"):
            print(f"  {fmt(ev['rel'])}  {ev['t'][11:]}  {ev['msg'][:70]}")
    elif args.cmd == "timeline":
        for ev in run.steps(t0, t1):
            if args.grep and args.grep not in ev["msg"]:
                continue
            if args.level and ev.get("level") != args.level:
                continue
            if args.func and args.func not in ev.get("func", ""):
                continue
            loc = ""
            if args.loc and ev.get("file"):
                loc = f"  [{ev['file'].rsplit('/', 1)[-1]}:{ev.get('line', 0)} {ev.get('func', '')}]"
            print(f"{fmt(ev['rel'])}  {ev['msg'][:150]}{loc}")
    elif args.cmd == "warnings":
        n = 0
        for ev in run.warnings():
            if t0 is not None and ev["rel"] < t0:
                continue
            if t1 is not None and ev["rel"] > t1:
                continue
            src = f"{ev.get('file', '').rsplit('/', 1)[-1]}:{ev.get('line', 0)}" if ev.get("file") else ""
            print(f"{fmt(ev['rel'])}  [{ev.get('level')}] {ev['msg'][:130]}  {src}")
            n += 1
        if not n:
            print("no warnings/errors in this run")
    elif args.cmd == "freezes":
        rows = run.freezes()
        if not rows:
            print("no gaps/stalls found")
        for r in rows:
            if t0 is not None and r["rel"] < t0:
                continue
            if t1 is not None and r["rel"] > t1:
                continue
            dur = "" if r["dur"] != r["dur"] else f" dur={r['dur']*1000:6.0f}ms"
            print(f"{fmt(r['rel'])}{dur}  [{r['source']}] {r['detail']}")


if __name__ == "__main__":
    try:
        _cli()
    except BrokenPipeError:  # piping into `head` is fine
        import os
        os._exit(0)
