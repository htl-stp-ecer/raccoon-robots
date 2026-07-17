<div align="center">

<img src="https://raw.githubusercontent.com/htl-stp-ecer/.github/main/profile/raccoon-logo.svg" alt="PackingBot" width="100"/>

# packing-bot

**Pom-sorting robot from the Botball Spring Game 2026.**

Mecanum drive · Shield + pom arm · Line-following pom collection · Basket handling

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=ffdd54)
![Platform](https://img.shields.io/badge/Platform-KIPR%20Wombat-orange)
![Season](https://img.shields.io/badge/Season-Botball%20Spring%202026-8B6F47)

> 📖 Platform documentation at [raccoon-docs.pages.dev](https://raccoon-docs.pages.dev/)

</div>

---

## Before you read this

This robot ran at the Botball Spring Game 2026. It's competition code, written under time pressure on the game table, sometimes hours before a match. It optimises for scoring points.

A few things to know:

- It doesn't consistently follow best practices. There are magic numbers, typos in mission names (`m060drop_maching_poms_mission.py`, `M070RetrunBasketsMission`), commented-out blocks, and servo positions tuned by hand until they worked.
- It uses an outdated RaccoonOS API. A lot has changed since this season, so don't copy calls from here and expect them to work against the current library. Check the [documentation](https://raccoon-docs.pages.dev/).
- What it's useful for is seeing how a real run gets structured: how it's sliced into missions, how steps compose, how sensor-driven stop conditions replace hardcoded distances.

If you're starting a new robot, [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) is the better starting point. This is worth reading when you want to see what a full season's robot ends up looking like.

---

## What it does

PackingBot plays the pom-sorting side of the 2026 spring game:

1. Grab the first poms: strafe into position, drop the pom arm, follow a line sideways to sweep poms into the claw
2. Collect the sorted pom using the shield and claw
3. Collect the last poms from the field
4. Drive to the baskets
5. Pull the baskets out into reach
6. Drop each pom into the basket that matches it
7. Return the baskets to where they score
8. Drive away and clear the scoring area

`M999ShutdownMission` is registered as the shutdown hook. `M010` carries `time_budget = 30.0`, so if it gets stuck it kills itself instead of consuming the rest of the run.

---

## Project layout

```
packing-bot/
├── raccoon.project.yml       # Project entry point (name, UUID, config includes)
├── config/
│   ├── connection.yml        # SSH / deploy settings
│   ├── hardware.yml          # IMU, button, ET sensor, IR sensors, sensor groups
│   ├── motors.yml            # 4 mecanum motor ports + encoder calibration
│   ├── servos.yml            # shield, pom_arm, shield_grabber, pom_grab + named positions
│   ├── missions.yml          # Mission order (read by raccoon-cli and BotUI)
│   ├── robot.yml             # Mecanum kinematics, PID, fused odometry
│   └── 2026-game-table.ftmap # Game table map
└── src/
    ├── main.py               # Entry point, builds Robot() and starts it
    ├── hardware/             # defs.py / robot.py (generated from config/)
    ├── missions/
    │   ├── m000_setup_mission.py
    │   ├── m010_grab_first_poms_mission.py
    │   ├── m020_collect_sorted_pom_mission.py
    │   ├── m030_collect_last_poms_mission.py
    │   ├── m040_drive_to_baskets_mission.py
    │   ├── m050_pull_baskets_out_mission.py
    │   ├── m060drop_maching_poms_mission.py
    │   ├── m070_retrun_baskets_mission.py
    │   ├── m080_drive_away_mission.py
    │   └── m999_shutdown_mission.py
    └── steps/
        ├── et_scan_align.py           # Custom step: sweep the ET sensor, centre on an object
        └── line_cross_detecting_turn.py
```

---

## Hardware

| Part | Setup |
|:-----|:------|
| Drivetrain | Mecanum, 4 motors, wheel radius 37.5 mm, track width 200 mm, wheelbase 125 mm |
| Odometry | `FusedOdometry`, wheel encoders fused with IMU |
| Sensors | IMU, start button, ET distance sensor, 3 IR line sensors (grouped as `front` / `rear`), light sensor for the start light |
| Servos | `shild` (protects the claw while driving), `pom_arm`, `shild_graber`, `pom_grab`, all with named positions rather than raw angles |

---

## Failure handling

This is probably the most useful thing to take from the repo.

A pom slips. A wheel spins on a seam. The other robot is 3 cm off and yours pushes against it indefinitely. This is normal, and a mission that assumes success will hang. A hung mission doesn't just cost you that action, it costs everything scheduled after it. So most risky steps here have an escape hatch.

Stop conditions compose with three operators, and the difference matters:

| Operator | Meaning | Typical use |
|:---------|:--------|:------------|
| `A \| B` | OR, whichever happens first | the failsafe: the line, or 2 seconds, whichever comes first |
| `A + B` | THEN, A becomes true, then B | precision: cross the line, then 7 cm more |
| `A & B` | AND, both true | narrowing a stop to one exact state |

Most `| after_seconds(...)` in this repo is a bail-out. Most `+` is actual logic.

| Layer | What it does | Where |
|:------|:-------------|:------|
| Global run cap | `shutdown_in: 120`, the run is dead at 120 s regardless | `config/robot.yml` |
| Mission budget | `time_budget = 30.0`, the mission kills itself at 30 s and the run continues | `m010_grab_first_poms_mission.py` |
| `timeout()` wrapper | Wraps a step that could hang: `timeout(strafe_arc_left(radius_cm=45, degrees=70), seconds=5.5)` | `m070_retrun_baskets_mission.py` |
| Sensor plus timeout | `timeout(strafe_right().until(on_black(Defs.rear.right)), seconds=4)`. Normally the line stops it; if the line never comes, 4 s does | `m070_retrun_baskets_mission.py` |
| OR-ed escape | `turn_left().until(after_degrees(50) \| after_seconds(3.0))`, turn 50° but never spin forever | `m040_drive_to_baskets_mission.py` |
| Runtime recovery | `defer()` plus a sensor check, so we only correct if we're actually wrong: `strafte_if_on_black()`, `drive_if_sensor_tirggerd()` | `m070`, `m010` |
| Shutdown hook | `M999ShutdownMission`, registered as `shutdown`, runs even after a bad run | `config/missions.yml` |

The pattern to notice is `timeout(strafe_right().until(on_black(...)), seconds=4)`: two stop conditions on one step. The sensor is what you want to happen, the timeout is what guarantees the step ends either way.

---

## Patterns worth copying

Despite the rough edges, some of this is still how we build robots:

| Pattern | Where to look |
|:--------|:--------------|
| Named servo positions in YAML: `Defs.pom_grab.open()` instead of `set_servo(3, 140)` | `config/servos.yml` |
| `defer()` for runtime decisions, building a sub-sequence only when the step executes so it can read live sensor values | `m010_grab_first_poms_mission.py` |
| Sensor stop conditions instead of hardcoded distances: `drive_forward().until(over_line(...) \| over_line(...))` | `m010_grab_first_poms_mission.py` |
| `parallel()` for arm and drive, moving the arm into position while driving rather than after | every mission |
| Custom `Step` classes: `EtScanAlign` sweeps the ET sensor, finds an object's edges, and centres the heading between them | `steps/et_scan_align.py` |
| One mission per scoring action, numbered in tens so you can insert without renaming | `config/missions.yml` |
| Time budgets on risky missions: `time_budget = 30.0` | `m010_grab_first_poms_mission.py` |

---

## Part of RaccoonOS

| Repository | What it is |
|:-----------|:-----------|
| [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) | Clean reference robot, start here |
| [raccoon-lib](https://github.com/htl-stp-ecer/raccoon-lib) | The core robotics library |
| [raccoon-cli](https://github.com/htl-stp-ecer/raccoon-cli) | `raccoon run`, `raccoon calibrate`, `raccoon create` |
| [clawbot](../clawbot) | Our other Spring 2026 robot, 3-DOF arm with inverse kinematics |
| [cone-bot](../cone-bot) | Earlier Spring 2026 prototype |
| [documentation](https://raccoon-docs.pages.dev/) | Full platform docs |

---

Built by team `axht-3085`, the Botball team at HTL St. Pölten, for the Botball Spring Game 2026.

---

## License

MIT, see the [LICENSE](../../../../LICENSE) at the root of this collection.
