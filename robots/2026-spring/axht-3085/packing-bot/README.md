<div align="center">

<img src="https://raw.githubusercontent.com/htl-stp-ecer/.github/main/profile/raccoon-logo.svg" alt="PackingBot" width="100"/>

# packing-bot

**Our pom-sorting competition robot from the Botball Spring Game 2026.**

Mecanum drive · Shield + pom arm · Line-following pom collection · Basket handling

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=ffdd54)
![Platform](https://img.shields.io/badge/Platform-KIPR%20Wombat-orange)
![Status](https://img.shields.io/badge/Status-Archived%20reference-lightgrey)
![Season](https://img.shields.io/badge/Season-Botball%20Spring%202026-8B6F47)

> 📖 **Platform documentation at [raccoon-docs.pages.dev](https://raccoon-docs.pages.dev/)**

</div>

---

## ⚠️ Read This First

This robot ran at the **Botball Spring Game 2026** and is published as a **historical reference**, not as a template.

- **It is competition code.** Written under time pressure, on the game table, hours before matches. It optimises for scoring points, not for being pretty.
- **It does not always follow best practices.** There are magic numbers, typos in mission names (`m060drop_maching_poms_mission.py`, `M070RetrunBasketsMission`), commented-out blocks, and servo positions tuned by hand until they worked.
- **It uses an outdated RaccoonOS API.** A lot has changed since this season. Do not copy calls from here and expect them to work on the current library — check the [documentation](https://raccoon-docs.pages.dev/) instead.
- **What it is good for:** seeing how we actually *structure and design* a real competition robot — how a run gets sliced into missions, how steps compose, how sensor-driven stop conditions replace hardcoded distances.

If you are starting a new robot, start at **[raccoon-example](https://github.com/htl-stp-ecer/raccoon-example)**. Come back here when you want to see what a full season's robot ends up looking like.

---

## What This Robot Does

PackingBot plays the pom-sorting side of the 2026 spring game:

1. **Grab the first poms** — strafes into position, drops the pom arm, follows a line sideways to sweep poms into the claw
2. **Collect the sorted pom** — uses the shield and claw to secure poms that are already sorted
3. **Collect the last poms** — clears the remaining field poms
4. **Drive to the baskets** — repositions across the table
5. **Pull the baskets out** — hooks and drags the baskets into reach
6. **Drop matching poms** — deposits each pom into the basket that matches it
7. **Return the baskets** — pushes the baskets back where they score
8. **Drive away** — clears the scoring area before time runs out

A `M999ShutdownMission` is registered as the shutdown hook, and `M010` carries a `time_budget = 30.0` so a stuck mission kills itself instead of eating the whole run.

---

## Project Layout

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
    ├── main.py               # Entry point — builds Robot() and starts it
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
| **Drivetrain** | Mecanum — 4 motors, wheel radius 37.5 mm, track width 200 mm, wheelbase 125 mm |
| **Odometry** | `FusedOdometry` — wheel encoders fused with IMU |
| **Sensors** | IMU, start button, ET distance sensor, 3 IR line sensors (grouped as `front` / `rear`), light sensor for the start-light |
| **Servos** | `shild` (protects the claw while driving), `pom_arm`, `shild_graber`, `pom_grab` — all with named positions instead of raw angles |

---

## Ideas Worth Stealing

Even with the rough edges, a few patterns in here held up well and are still how we build robots today:

| Pattern | Where to look |
|:--------|:--------------|
| **Named servo positions in YAML** — `Defs.pom_grab.open()` instead of `set_servo(3, 140)` | `config/servos.yml` |
| **`defer()` for runtime decisions** — build a sub-sequence only when the step actually executes, so it can read live sensor values | `m010_grab_first_poms_mission.py` |
| **Sensor stop conditions over hardcoded distances** — `drive_forward().until(over_line(...) \| over_line(...))` | `m010_grab_first_poms_mission.py` |
| **`parallel()` for arm + drive** — move the arm into position *while* driving, not after | every mission |
| **Custom `Step` classes** — `EtScanAlign` sweeps the ET sensor, finds an object's edges, and centres the heading between them | `steps/et_scan_align.py` |
| **One mission = one scoring action** — numbered in tens (`m010`, `m020`) so you can insert a mission without renaming everything | `config/missions.yml` |
| **Time budgets** — `time_budget = 30.0` on a risky mission | `m010_grab_first_poms_mission.py` |

---

## Part of RaccoonOS

| Repository | What it is |
|:-----------|:-----------|
| [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) | Clean reference robot — **start here** |
| [raccoon-lib](https://github.com/htl-stp-ecer/raccoon-lib) | The core robotics library |
| [raccoon-cli](https://github.com/htl-stp-ecer/raccoon-cli) | `raccoon run`, `raccoon calibrate`, `raccoon create` |
| [clawbot](https://github.com/htl-stp-ecer/clawbot) | Our other Spring 2026 robot — 3-DOF arm with inverse kinematics |
| [cone-bot](https://github.com/htl-stp-ecer/cone-bot) | Earlier Spring 2026 prototype |
| [documentation](https://raccoon-docs.pages.dev/) | Full platform docs |

---

Built by the Botball team at **HTL St. Pölten** for the Botball Spring Game 2026.
