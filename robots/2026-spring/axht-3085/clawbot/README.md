<div align="center">

<img src="https://raw.githubusercontent.com/htl-stp-ecer/.github/main/profile/raccoon-logo.svg" alt="ClawBot" width="100"/>

# clawbot

**Our 3-DOF arm robot from the Botball Spring Game 2026.**

Mecanum drive · Inverse kinematics arm · Line following · Ramp navigation

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=ffdd54)
![Platform](https://img.shields.io/badge/Platform-KIPR%20Wombat-orange)
![Status](https://img.shields.io/badge/Status-Archived%20reference-lightgrey)
![Season](https://img.shields.io/badge/Season-Botball%20Spring%202026-8B6F47)

> 📖 **Platform documentation at [raccoon-docs.pages.dev](https://raccoon-docs.pages.dev/)**

</div>

---

## ⚠️ Read This First

This robot ran at the **Botball Spring Game 2026** and is published as a **historical reference**, not as a template.

- **It is competition code.** Written against a deadline, tuned on the game table, and judged by whether it scored — not by whether it would survive a code review.
- **It does not always follow best practices.** Magic numbers, hand-measured calibration tables, commented-out experiments, and an auto-generated DSL file checked into the repo.
- **It uses an outdated RaccoonOS API.** Development has moved on considerably since this season. Don't copy calls from here expecting them to still exist — check the [documentation](https://raccoon-docs.pages.dev/).
- **What it is good for:** seeing how we *design* a robot program — mission decomposition, arm kinematics as its own layer, and reusable steps.

If you are starting a new robot, start at **[raccoon-example](https://github.com/htl-stp-ecer/raccoon-example)**. Come here when you want to see the real thing, warts included.

---

## What This Robot Does

ClawBot works the ramp side of the 2026 spring game:

1. **Drive down the ramp** — leaves the starting box and descends onto the main field
2. **Collect cones** — picks cones with the 3-DOF arm and claw
3. **Collect drums** — grabs and repositions the drums
4. **Collect Botguy** — the dedicated Botguy handling routine
5. **Drive up the ramp** — returns to the scoring area before the run ends

`M000SetupMission` runs as the setup hook, `M999ShutdownMission` as the shutdown hook, and `shutdown_in: 120` caps the whole run.

---

## The Arm — The Interesting Part

`src/kinematics/arm.py` is the piece worth reading. The arm has three joints (`arm_base`, `arm_sholder`, `arm_elbow`) plus a claw, and instead of hardcoding servo values per pose, it does real inverse kinematics:

- **Link lengths in code** mirror the physical robot — upper arm 12.5 cm, forearm 24 cm, shoulder height 13.3 cm
- **Calibration tables come from `config/servos.yml`**, not from the source — the YAML stays canonical and `Defs` feeds the interpolator
- **Linear interpolation with extrapolation** maps a joint angle to a servo value between calibration points, and *extrapolates the outermost slope* beyond the calibrated span instead of snapping to the boundary — so IK can ask for an angle nobody measured and still get something sensible
- **Hardware limits clamp the result**, so a bad IK solution can't drive a servo into the frame

That layering — physical geometry → calibration → servo value — is the part that aged well.

---

## Project Layout

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
        ├── line_follow_dsl.py         # Auto-generated builders — do not edit
        └── line_cross_detecting_turn.py
```

---

## Hardware

| Part | Setup |
|:-----|:------|
| **Drivetrain** | Mecanum — 4 motors, wheel radius 37.5 mm, track width 200 mm, wheelbase 125 mm |
| **Arm** | 3 DOF (base / shoulder / elbow) + claw, driven by inverse kinematics |
| **Sensors** | IMU, start button, 3 IR line sensors (grouped as `front` / `rear`), light sensor for the start-light |
| **Motion tuning** | Separate saturation derating for distance and heading — the robot gives up heading authority gracefully instead of oscillating |

---

## Ideas Worth Stealing

| Pattern | Where to look |
|:--------|:--------------|
| **Kinematics as its own layer** — missions ask for a position, not for servo values | `kinematics/arm.py` |
| **Calibration lives in YAML, code reads it** — one place to re-measure after a rebuild | `config/servos.yml` + `arm.py` |
| **Custom step classes with a generated DSL** — write the `Step`, get a fluent builder for free | `steps/line_follow.py` → `line_follow_dsl.py` |
| **Named servo positions** — `Defs.arm_claw.soft_close()` beats `set_servo(3, 60)` | `config/servos.yml` |
| **One mission = one scoring action**, numbered in tens so you can insert without renaming | `config/missions.yml` |
| **Saturation handling in the motion PID** — what to do when the controller asks for more than the motors have | `config/robot.yml` |

---

## Part of RaccoonOS

| Repository | What it is |
|:-----------|:-----------|
| [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) | Clean reference robot — **start here** |
| [raccoon-lib](https://github.com/htl-stp-ecer/raccoon-lib) | The core robotics library |
| [raccoon-cli](https://github.com/htl-stp-ecer/raccoon-cli) | `raccoon run`, `raccoon calibrate`, `raccoon create` |
| [packing-bot](https://github.com/htl-stp-ecer/packing-bot) | Our other Spring 2026 robot — pom sorting and baskets |
| [cone-bot](https://github.com/htl-stp-ecer/cone-bot) | Earlier Spring 2026 prototype |
| [documentation](https://raccoon-docs.pages.dev/) | Full platform docs |

---

Built by the Botball team at **HTL St. Pölten** for the Botball Spring Game 2026.
