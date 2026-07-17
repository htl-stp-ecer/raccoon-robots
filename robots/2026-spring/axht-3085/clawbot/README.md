<div align="center">

<img src="https://raw.githubusercontent.com/htl-stp-ecer/.github/main/profile/raccoon-logo.svg" alt="ClawBot" width="100"/>

# clawbot

**3-DOF arm robot from the Botball Spring Game 2026.**

Mecanum drive · Inverse kinematics arm · Line following · Ramp navigation

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=ffdd54)
![Platform](https://img.shields.io/badge/Platform-KIPR%20Wombat-orange)
![Season](https://img.shields.io/badge/Season-Botball%20Spring%202026-8B6F47)

> 📖 Platform documentation at [raccoon-docs.pages.dev](https://raccoon-docs.pages.dev/)

</div>

---

## Before you read this

This robot ran at the Botball Spring Game 2026. It's competition code, written against a deadline and tuned on the game table. It was judged by whether it scored, not by whether it would pass a code review.

A few things to know:

- It doesn't consistently follow best practices. There are magic numbers, hand-measured calibration tables, commented-out experiments, and an auto-generated DSL file checked into the repo.
- It uses an outdated RaccoonOS API. Development has moved on a lot since this season, so don't copy calls from here and expect them to exist. Check the [documentation](https://raccoon-docs.pages.dev/).
- What it's useful for is seeing how a robot program gets structured: mission decomposition, arm kinematics as a separate layer, reusable steps.

If you're starting a new robot, [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) is the better starting point.

---

## What it does

ClawBot handles the ramp side of the 2026 spring game:

1. Drive down the ramp out of the starting box
2. Collect cones with the arm and claw
3. Collect drums
4. Collect Botguy
5. Drive back up the ramp to the scoring area

`M000SetupMission` runs as the setup hook, `M999ShutdownMission` as the shutdown hook, and `shutdown_in: 120` caps the run.

---

## The arm

`src/kinematics/arm.py` is the part worth reading. The arm has three joints (`arm_base`, `arm_sholder`, `arm_elbow`) plus a claw. Rather than hardcoding servo values per pose, it runs inverse kinematics:

- Link lengths in the code mirror the physical robot: upper arm 12.5 cm, forearm 24 cm, shoulder height 13.3 cm.
- Calibration tables are read from `config/servos.yml` rather than being duplicated in the source, so the YAML stays canonical and `Defs` feeds the interpolator.
- Joint angles map to servo values by linear interpolation between calibration points. Outside the calibrated range it extrapolates the outermost slope instead of snapping to the boundary, so IK can ask for an angle nobody measured and still get a sensible value.
- Hardware limits clamp the result, so a bad IK solution can't drive a servo into the frame.

The layering (physical geometry, then calibration, then servo value) is the part that held up.

---

## How this fed back into RaccoonOS

RaccoonOS has arm support largely because of this file.

ClawBot's `arm.py` was written by hand: link lengths in Python, calibration tables in YAML, IK solved on the robot at match time. It worked, but every team with an arm would have had to write the same thing, and most would have gotten the extrapolation and clamping wrong.

The platform now has a general version of it:

| ClawBot | RaccoonOS today |
|:--------|:----------------|
| Link lengths hardcoded in `arm.py` | `type: ArmChain` in `raccoon.project.yml`: joints, link lengths, servo mappings, workspace limits |
| IK solved on the robot | Codegen IK. `raccoon codegen` solves each named position offline with `ikpy`, validates it against workspace limits and forbidden zones, and writes literal servo angles into `defs.py`. No math or IK dependency at match time |
| Interpolation tables read from `Defs` | `ArmPreset`, generated, with one method per named position: `Defs.arm.home()`, `Defs.arm.grab(speed=60)` |
| Tuned by driving servos and watching | The [Arm Visualizer](https://raccoon-docs.pages.dev/03-web-ide/13-arm-panel) in the WebIDE renders the chain in a THREE.js scene: drag the end effector to solve IK, set joint angles for FK, see the workspace envelope and joint axes, save named positions, push angles to the servos live |

The reasoning behind codegen IK is that most arms only need a handful of named positions (home, grab, drop, handoff), so solving them at build time is cheap and catches an unreachable target on your laptop instead of on the table.

ClawBot's approach is still supported as the fallback. If an arm's geometry doesn't fit `ArmChain`, or it genuinely needs runtime IK because it's tracking something a sensor found, you write kinematics in project Python. The [arm kinematics docs](https://raccoon-docs.pages.dev/02-programming/20-arm-kinematics-and-codegen) use this robot as the example.

---

## Project layout

```
clawbot/
├── raccoon.project.yml       # Project entry point (name, UUID, config includes)
├── config/
│   ├── connection.yml        # SSH / deploy settings
│   ├── hardware.yml          # IMU, button, IR sensors, sensor groups
│   ├── motors.yml            # 4 mecanum motor ports + encoder calibration
│   ├── servos.yml            # arm_base, arm_sholder, arm_elbow, arm_claw + calibration
│   ├── missions.yml          # Mission order (read by raccoon-cli and BotUI)
│   ├── robot.yml             # Mecanum kinematics, PID, saturation handling
│   └── 2026-game-table.ftmap # Game table map
└── src/
    ├── main.py               # Entry point
    ├── hardware/             # defs.py / defs.pyi (generated from config/)
    ├── kinematics/
    │   └── arm.py            # 3-DOF inverse kinematics + servo calibration interpolation
    ├── missions/
    │   ├── m000_setup_mission.py
    │   ├── m010_drive_down_ramp_mission.py
    │   ├── m020_collect_cones_mission.py
    │   ├── m030_collect_drums_mission.py
    │   ├── m040_collect_botguy_mission.py
    │   ├── m050_drive_up_the_ramp_mission.py
    │   └── m999_shutdown_mission.py
    └── steps/
        ├── arm_steps.py               # Reusable arm sequences
        ├── line_follow.py             # Custom line-following steps
        ├── line_follow_dsl.py         # Auto-generated builders, do not edit
        └── line_cross_detecting_turn.py
```

---

## Hardware

| Part | Setup |
|:-----|:------|
| Drivetrain | Mecanum, 4 motors, wheel radius 37.5 mm, track width 200 mm, wheelbase 125 mm |
| Arm | 3 DOF (base / shoulder / elbow) plus claw, driven by inverse kinematics |
| Sensors | IMU, start button, 3 IR line sensors (grouped as `front` / `rear`), light sensor for the start light |
| Motion tuning | Separate saturation derating for distance and heading, so the robot gives up heading authority gradually instead of oscillating |

---

## Failure handling

This is probably the most useful thing to take from the repo.

A drum sits 2 cm off. The ramp gives one wheel less grip than the other. The arm closes on air. This is normal, and a mission that assumes success will hang. A hung mission doesn't just cost you that action, it costs everything scheduled after it. So most risky steps here have an escape hatch.

Stop conditions compose with three operators, and the difference matters:

| Operator | Meaning | Typical use |
|:---------|:--------|:------------|
| `A \| B` | OR, whichever happens first | the failsafe: the line, or 2 seconds, whichever comes first |
| `A + B` | THEN, A becomes true, then B | precision: cross both sensors, then 6 cm more |
| `A & B` | AND, both true | narrowing a stop to one exact state |

Most `| after_seconds(...)` in this repo is a bail-out. Most `+` is actual logic.

| Layer | What it does | Where |
|:------|:-------------|:------|
| Global run cap | `shutdown_in: 120`, the run is dead at 120 s regardless | `config/robot.yml` |
| `timeout()` wrapper | `timeout(drive_forward().until(on_black(Defs.front.left)), seconds=0.5)`. The line is normally right there; if it isn't, half a second and we move on rather than driving into the wall | `m030_collect_drums_mission.py` |
| OR-ed escape | `strafe_left(heading=0).until(on_black(Defs.front.left) \| after_seconds(2))` | `m050_drive_up_the_ramp_mission.py` |
| `background()` | Return the tray while the robot drives on, so cleanup doesn't block the next scoring action | `m030_collect_drums_mission.py` |
| Checkpoint sync | `wait_for_checkpoint(68)` waits on the clock for the other robot instead of assuming it's done | `m030_collect_drums_mission.py` |
| Shutdown hook | `M999ShutdownMission`, registered as `shutdown`, runs even after a bad run | `config/missions.yml` |
| IK clamping | A bad IK solution gets clamped to the servo's hardware limits instead of driving the arm into the frame | `kinematics/arm.py` |

The pattern to notice is `timeout(drive_forward().until(on_black(...)), seconds=0.5)`: two stop conditions on one step. The sensor is what you want to happen, the timeout is what guarantees the step ends either way.

---

## Patterns worth copying

| Pattern | Where to look |
|:--------|:--------------|
| Kinematics as its own layer, so missions ask for a position rather than servo values | `kinematics/arm.py` |
| Calibration in YAML, read by code, so there's one place to remeasure after a rebuild | `config/servos.yml` + `arm.py` |
| Custom step classes with a generated DSL: write the `Step`, get a fluent builder | `steps/line_follow.py` → `line_follow_dsl.py` |
| Named servo positions: `Defs.arm_claw.soft_close()` instead of `set_servo(3, 60)` | `config/servos.yml` |
| One mission per scoring action, numbered in tens so you can insert without renaming | `config/missions.yml` |
| Saturation handling in the motion PID, for when the controller asks for more than the motors have | `config/robot.yml` |

---

## Part of RaccoonOS

| Repository | What it is |
|:-----------|:-----------|
| [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) | Clean reference robot, start here |
| [raccoon-lib](https://github.com/htl-stp-ecer/raccoon-lib) | The core robotics library |
| [raccoon-cli](https://github.com/htl-stp-ecer/raccoon-cli) | `raccoon run`, `raccoon calibrate`, `raccoon create` |
| [WebIDE](https://github.com/htl-stp-ecer/WebIDE) | Visual editor, home of the 3D arm visualiser this robot led to |
| [packing-bot](../packing-bot) | Our other Spring 2026 robot, pom sorting and baskets |
| [cone-bot](../cone-bot) | Earlier Spring 2026 prototype |
| [documentation](https://raccoon-docs.pages.dev/) | Full platform docs |

---

Built by team `axht-3085`, the Botball team at HTL St. Pölten, for the Botball Spring Game 2026.

---

## License

MIT, see the [LICENSE](../../../../LICENSE) at the root of this collection.
