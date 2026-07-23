# cube-bot

Team `axht-3085` · Botball Spring 2026 · mecanum drive

A mecanum-drive robot with a **3-DOF arm** that grabs cubes, stacks them, drives up a
ramp, and places cubes at an external loading dock. It's the team's cleanest 2026 robot
structurally — it introduced the `ParamSet` and `TableMap` patterns — but it still earns
its place here: the mission code is a wall of hard-coded "so we don't crash" distances.

> **Read the history warning at the bottom before you judge any single line.** This is
> end-of-season competition code. It works on the table; it is not clean.

---

## What it does, mission by mission

| Mission | What happens |
|:--------|:-------------|
| **M000 Setup** | Homes the arm, asks for table-side parameters (`MissionParams`), calibrates. |
| **M010 MoveToCenter** | Lateral line-follow to the centre while the arm pre-positions in a `background` step. |
| **M020 / M030 First / SecondBrownCube** | Grabs the two brown cubes with the arm; drops them into a container. |
| **M040 GrabRedCube** | Grabs the red cube. |
| **M050 DropFirstCubeStack** | Places the first stack. |
| **M060 DriveUpRamp** | Drives up the ramp — with a deliberately tiny steering angle so it never scrapes the left railing (line-follow compensates). |
| **M070 GrabUpperCube** | Grabs a cube from the upper level. |
| **M080 DriveToExternalLoadingDock** | Navigates to the external loading dock. |
| **M090 PlaceSecondCube** | Places the final cube. |
| **M999 Shutdown** | Safe state. |

## Hardware

- **Drive**: mecanum (4 motors), so it can strafe — used heavily for cube alignment.
- **Arm**: 3 servos (`arm_base`, `arm_sholder`, `arm_elbow`) + `arm_claw`, driven through
  `src/kinematics/arm.py` (`arm.move_angles(base_deg=…, sholder_deg=…, elbow_deg=…)`).
- **Sensing**: front + rear IR `SensorGroup`s, an ET analog sensor, a light-start sensor,
  IMU.
- **Map**: a full `TableMap` (ramp layer + transitions) is baked into `robot.py`.

## The three things worth stealing

1. **`src/mission_params.py`** — the `ParamSet` / `NumberParam` pattern. Distances you
   want to trim at the table (`first_cube_line_gap`, `left_dor_distance`) are asked for in
   setup and read with `.get()` in missions. No recompile to tune.
2. **`src/kinematics/arm.py`** — a hand-written 3-DOF arm helper. Rough, but it's the code
   that convinced RaccoonOS to later grow a proper `ArmPreset` API.
3. **The `line_follow()` fluent builder in anger** — real usage of
   `line_follow().single(...).move(strafe=1).correct_forward().hold_heading(-90).pid(...)`,
   plus `timeout_or(...)` escape hatches so a strafe that never sees black can't hang.

## What's broken / what we'd redo

The commit log is the honest changelog here — a sample of what each fix was working around:

- **Magic distances everywhere.** "drive farther forward so we defently are on the cube",
  "less drive forward at the end so we never hit the external loading dock (once dropped a
  pallet and pushed the cube stack with it)". Almost every tweak is a physical near-miss
  encoded as a number.
- **`parallel()` that could hang** was replaced with do-while patterns
  ("replaed parralel with do while so the parralel can't wait for ever").
- **Wheel-slip odometry workarounds** — several `after_cm(...)` guards added specifically
  so odometry "opfully doesn't check wheel slip".
- **Servo timing is all hand-tuned** — "slowed servos down so placing cube is better",
  "grabing stronger", "servo change because hardware was cahnged". Change the hardware and
  you re-tune all of it.
- **`AGENTS.md` is a copy-paste that was never updated.** It still opens with "ClawBot Agent
  Notes" and documents a `src/steps/bot.py` / `ServoPreset` layout this robot doesn't have. It
  was cloned from the sibling clawbot project and left as-is.

## Running it

```bash
raccoon connect <PI_ADDRESS>     # see config/connection.yml
raccoon run
```

The `[sim]` extra is pinned in `pyproject.toml`, so this one can also be driven in the
RaccoonOS simulator.

---

## ⚠️ About the commit history

**The commit history is really, really, *reaaaaally* bad, and we're keeping it that way.**

It was written at the table, mid-tournament, by several people. Expect:

- typos in almost every message — "cahnged", "opfully", "gressif", "apllet", "compleatly"
- `dont do that, was just for home not gcer`
- `new reject mark heading reference if the poms force the bot to be schräg` (German/English soup)
- the same behaviour "fixed" five commits in a row, each time "so we don't fail"

`git log` here is a record of what actually happened under pressure, not a model to copy.
The *reasoning* in the messages ("so we push the cube further in some edge cases") is often
more useful than the grammar. If a message contradicts the code, trust the code.
