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
from datetime import datetime, timezone, timedelta
from pathlib import Path


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
    def libstp(self, grep: str | None = None, level: str | None = None):
        """Yield dicts from libstp.jsonl with an added 'epoch' (UTC epoch s) and
        'rel' (s since run start). NOTE: the original 'elapsed' field is left in
        but must NOT be used for cross-source correlation."""
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
                d["epoch"] = self.local_to_epoch(d["t"])
                d["rel"] = d["epoch"] - self._t0_epoch
                yield d

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


if __name__ == "__main__":
    import sys

    run = Run(sys.argv[1])
    print(f"run start epoch = {run._t0_epoch:.3f}  tz = {run._tz}")
    print("channels:")
    for cid, topic in run.channels().items():
        print(f"  {cid:3d} {topic}")
    print("\nmission events (grep 'mission'):")
    for ev in run.libstp(grep="mission"):
        print(f"  rel={ev['rel']:8.2f}  {ev['t'][11:]}  {ev['msg'][:70]}")
