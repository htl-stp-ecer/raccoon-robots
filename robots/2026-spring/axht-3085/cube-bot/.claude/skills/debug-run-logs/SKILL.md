---
name: debug-run-logs
description: Analyse cube-bot run artifacts under .raccoon/downloads/runN_*/ (libstp.jsonl step log, sensors.mcap, cmd traces, journals) to debug what the robot actually did during a mission. Use when investigating why a step/condition (on_incline, on_level, on_black, line_follow, over_line, wall_align, turns, drives) fired at the wrong time, why a mission misbehaved on the ramp/table, or when correlating a logged event with IMU/odometry/analog sensor data. Triggers on: "run log", "sensors.mcap", "libstp", ".raccoon/downloads", "warum hat X (nicht) getriggert", "schau mit den logs / mcap".
---

# Debugging cube-bot run logs

A "run" is a directory `.raccoon/downloads/runN_YYYYMMDD-HHMMSS/` written by
`raccoon_cli`. Debugging almost always means **correlating a logged step event
with the sensor stream** — and the correlation is where people go wrong. Read the
two pitfalls below before touching the data.

## ⚠️ Two pitfalls that will silently give you wrong answers

1. **`libstp.jsonl` `"elapsed"` is NOT a run clock. Never correlate with it.**
   It resets/wraps per mission (last line can read `elapsed=1.187`). Using it put
   an earlier analysis ~130 s off and "proved" the robot was flat when it was on
   the ramp. **Always correlate via the wall-clock `"t"` field.**

2. **Clocks are in different timezones/units.**
   - `libstp.jsonl` `"t"` → **local** wall-clock string, tz *not* in the string.
   - `sensors.mcap` `log_time` → **UTC epoch nanoseconds**.
   - mcap payloads' own `"t"` → **UTC epoch microseconds**.
   Derive the local offset from `run.json` (`started_at_utc` vs `started_at_local`);
   do not hardcode it. The helper below does all of this — use it.

## Use the helper (do this first)

`scripts/runlog.py` encapsulates the time mapping. Everything it returns is on one
shared axis: **`rel` = seconds since run start**.

```python
import sys; sys.path.insert(0, ".claude/skills/debug-run-logs/scripts")
from runlog import Run
run = Run(".raccoon/downloads/run1_20260713-105246")

# 1. Locate the mission window and the condition triggers on the shared clock
for ev in run.libstp(grep="M060"):                 # mission start/end
    print(ev["rel"], ev["msg"])
for ev in run.libstp(grep="condition met: on_"):   # when did each condition fire
    print(ev["rel"], ev["msg"])

# 2. Pull sensor channels over that window (t0/t1 are rel seconds)
for rel, v in run.mcap_scalar("raccoon/odometry/pos_x", t0=168, t1=192):
    ...
for rel, _t, d in run.mcap(["raccoon/accel/value"], t0=168, t1=192):
    ...   # d = {"x":..,"y":..,"z":..}

# 3. Reproduce exactly what on_incline/on_level saw (raw-accel tilt, EMA a=0.2)
for rel, tilt_deg in run.accel_tilt(t0=168, t1=192, alpha=0.2):
    ...
```

Quick orientation dump: `python3 scripts/runlog.py <run_dir>` prints the run-start
epoch, tz, all mcap channels, and mission events.

## Artifacts in a run dir

| file | what | notes |
|------|------|-------|
| `libstp.jsonl` | step/condition log (the "why") | JSON per line: `t`, `seq`, `level`, `msg`. `condition met:`/`condition advanced:` lines show trigger times + sensor value. `func`/`file` point at raccoon source. |
| `sensors.mcap` | IMU/odometry/analog/motor timeseries | JSON-schema channels, ~175 Hz accel, ~70 Hz gyro. |
| `cmd_trace.robot.jsonl` | per-tick motion commands | high volume. |
| `journal.stm32-data-reader.jsonl` | SPI/transport reader journal | look here for reader/SPI stalls (see project memory on freezes). |
| `journal.raccoon-server.jsonl` | server journal | small. |
| `manifest.json` / `run.json` | window bounds, tz, artifact list | tz + epoch anchor source. |

### Key mcap channels
`raccoon/accel/value` (accel incl. gravity, m/s², z≈+9.8 up when level; UNGATED so
~175 Hz — but corrupted by vibration/own-acceleration while driving, NOT a clean
tilt source), `.../gyro/value` (rad/s), `.../linear_accel/value` (gravity-removed),
`.../imu/quaternion` (**DMP 6-axis fused orientation** — roll/pitch is
gravity-referenced & drift/vibration-immune, the *good* tilt source. Publish is
change-gated [noiseEpsilon 0.001] + 50 Hz cap, so its rate COLLAPSES to ~0.02 Hz
while still and rises toward 50 Hz while moving — thousands of samples/run, not
frozen. Non-zero baseline pitch [~-4°; ~18° before it converges after motion] → use
RELATIVE to a flat reference, not as an absolute angle), `.../imu/heading` (yaw,
ZUPT-corrected), `.../odometry/{pos_x,pos_y,heading,vx,vy,wz}` (SI: m, m/s, deg),
`.../analog/N/value` (line sensors — black = high raw, white = low raw),
`.../digital/N/value`, `.../motor/N/position`, `.../bemf/N/value`.

> IMU firmware source: `raccoon/stm32-data-reader/firmware/Firmware/src/Sensors/IMU/`
> (MPU9250 + Invensense DMP). Reader publish gating:
> `raccoon/stm32-data-reader/src/wombat/services/DataPublisher.cpp`.

## Where the raccoon condition/step source lives

`on_incline`, `on_level`, etc. are **not** in the local `.venv` raccoon (it's an
older build). The deployed source is cached by uv. Find the current one with:

```bash
# grep for the class (note: it's `class on_incline`, not `def`); several raccoon
# versions live in the cache — this finds the build that actually has the feature:
grep -rl "class _InclinationCondition" ~/.cache/uv/archive-v0/ 2>/dev/null
```

Read that `raccoon/step/condition.py` to see the real implementation (e.g.
`on_incline`/`on_level` derive tilt from `IMU().read()[0]` = raw accel,
`tilt = acos(|a_up|/|a|)`, EMA `smoothing=0.2`, default `up_axis="z"`).

## Interpreting IMU tilt during motion (worked example)

The raw accelerometer is only "gravity" when the robot is still or at steady
velocity. **While driving/arm-moving it is dominated by vibration + the robot's
own acceleration** — `|a|` swings ~0.4 g…2.0 g, per-sample tilt jumps 1.5°…66° in
milliseconds, gyro RMS ~10 vs ~0.06 rad/s at rest. So:

- To see the **true** chassis tilt, compute a strong moving-average (≈1 s window)
  of the accel-tilt, not the raw or the weak EMA.
- A condition that fires off the α=0.2 EMA can trigger on a single vibration
  spike. In `run1_20260713-105246`, `on_incline(13)` fired at rel=179.14 while the
  1 s-averaged tilt was **0.6°** (still flat); the real 13° ramp only came at
  rel≈184. `on_level(3)` fired on a transient dip mid-drive. Cross-check any
  accel-based trigger against the 1 s average + odometry velocity before believing
  it reflects real geometry.

## Recommended workflow

1. `Run(dir)`; dump mission events + `condition met:` lines to get the timeline.
2. For the suspect trigger, extract the relevant channel(s) over `[start-1s, +2s]`.
3. Compare the raw signal, the condition's own smoothing, **and** a strong 1 s
   average. Add odometry `vx/vy/pos` to know if the robot was moving/stationary.
4. If the condition looks buggy, read the deployed `condition.py` (uv cache) to
   confirm what signal + smoothing it actually uses.
