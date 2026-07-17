<div align="center">

<img src="https://raw.githubusercontent.com/htl-stp-ecer/.github/main/profile/raccoon-logo.svg" alt="ConeBot" width="100"/>

# cone-bot

**Early cone-collecting prototype from the Botball Spring Game 2026.**

Differential drive · Single arm + claw · Cone container · Botguy experiments

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=ffdd54)
![Platform](https://img.shields.io/badge/Platform-KIPR%20Wombat-orange)
![Season](https://img.shields.io/badge/Season-Botball%20Spring%202026-8B6F47)

> 📖 Platform documentation at [raccoon-docs.pages.dev](https://raccoon-docs.pages.dev/)

</div>

---

## Before you read this

This is an early prototype from the Botball Spring Game 2026 season, and it's the roughest of the three robots in this collection.

- It's unfinished. Whole missions are commented out (`M010DriveToConeMission` is one large comment block, `M027` and `M030` are disabled in `missions.yml`). It was replaced by [clawbot](../clawbot) before the season ended.
- It doesn't follow best practices. Typos in filenames (`m060_drop_conees_mission.py`), hardcoded magic values with comments saying as much, an unused `pydantic` import, and PID gains left at zero where nobody got around to tuning them.
- It uses an outdated RaccoonOS API. Treat everything here as how it was, not how it works. The [documentation](https://raccoon-docs.pages.dev/) is authoritative.
- What it's useful for is seeing an early draft. This is what a robot program looks like two weeks in, including the parts that got thrown away.

If you're starting a new robot, use [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example).

---

## What it does

ConeBot was our first attempt at the cone side of the 2026 spring game:

1. Drive down the ramp out of the starting box
2. Drive to the cone and line up
3. Collect the cone: turn to heading, drop the arm, drive in, close the claw, lift into the container
4. Collect the second cone the same way
5. Botguy missions, written and then disabled in `missions.yml`
6. Drive to the ramp, then back to the starting box
7. Drop the cones: turn to 135°, tip the container, clear out

---

## Project layout

```
cone-bot/
├── raccoon.project.yml       # Project entry point (name, UUID, config includes)
├── config/
│   ├── connection.yml        # SSH / deploy settings
│   ├── hardware.yml          # IMU, button, one IR sensor, start-light sensor
│   ├── motors.yml            # Motor ports + encoder calibration
│   ├── servos.yml            # cone_arm_servo, claw_servo + named positions
│   ├── missions.yml          # Mission order, note the commented-out entries
│   └── robot.yml             # Differential kinematics, PID, fused odometry
└── src/
    ├── main.py               # Entry point
    ├── hardware/             # Generated from config/
    ├── missions/
    │   ├── m000_setup_mission.py
    │   ├── m010_drive_to_cone_mission.py         # fully commented out
    │   ├── m020_collect_cone_mission.py
    │   ├── m025_collect_second_cone_mission.py
    │   ├── m027_drive_to_botguy_mission.py       # disabled
    │   ├── m030_collect_botguy_mission.py        # disabled
    │   ├── m040_drive_to_ramp_mission.py
    │   ├── m050_drive_to_starting_box_mission.py
    │   └── m060_drop_conees_mission.py
    └── steps/
        └── cone_container_steps.py               # Reusable container tip/reset sequences
```

---

## Hardware

| Part | Setup |
|:-----|:------|
| Drivetrain | Differential, 2 motors, wheel radius 34.5 mm, wheelbase 160 mm. The later robots used mecanum |
| Odometry | `FusedOdometry`, encoders fused with IMU |
| Sensors | IMU, start button, one front IR sensor, light sensor for the start light |
| Servos | `cone_arm_servo` (down / 20° / 45° / 90° / container position), `claw_servo` (open / half open / closed, plus Botguy-specific grips) |

---

## Patterns worth copying

Even an abandoned prototype gets some things right:

| Pattern | Where to look |
|:--------|:--------------|
| Named servo positions from the start: `Defs.claw_servo.half_open()`, never a raw angle | `config/servos.yml` |
| Reusable steps extracted early: `down_cone_container()` is called from more than one mission | `steps/cone_container_steps.py` |
| `.until()` with an OR-ed timeout: `turn_right().until(after_degrees(45) \| after_seconds(1.0))` can't hang | `m030_collect_botguy_mission.py` |
| Missions numbered in tens, so inserting `m025` between `m020` and `m030` cost nothing | `config/missions.yml` |
| Disabling a mission in YAML rather than deleting code: comment the entry out, keep the file | `config/missions.yml` |
| Comments that admit what's going on: *"hardcodes magic value to controll how hard we push into the dor"* | `m030_collect_botguy_mission.py` |

---

## Part of RaccoonOS

| Repository | What it is |
|:-----------|:-----------|
| [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) | Clean reference robot, start here |
| [raccoon-lib](https://github.com/htl-stp-ecer/raccoon-lib) | The core robotics library |
| [raccoon-cli](https://github.com/htl-stp-ecer/raccoon-cli) | `raccoon run`, `raccoon calibrate`, `raccoon create` |
| [clawbot](../clawbot) | The robot that replaced this one, 3-DOF arm with inverse kinematics |
| [packing-bot](../packing-bot) | Our other Spring 2026 robot, pom sorting and baskets |
| [documentation](https://raccoon-docs.pages.dev/) | Full platform docs |

---

Built by team `axht-3085`, the Botball team at HTL St. Pölten, for the Botball Spring Game 2026.

---

## License

MIT, see the [LICENSE](../../../../LICENSE) at the root of this collection.
