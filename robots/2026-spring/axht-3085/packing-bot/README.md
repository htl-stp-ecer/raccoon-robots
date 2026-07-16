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

## Your Robot Will Fail — Build For It

If you read this repo for one thing, read it for this.

A pom slips. A wheel spins on a seam. The other robot is 3 cm off and yours pushes against it forever. **This is normal.** A mission that assumes success hangs, and a hung mission doesn't cost you one action — it costs you every action after it. So almost every risky step here carries an escape hatch.

### The vocabulary

Stop conditions compose with three operators, and the distinction matters:

| Operator | Meaning | Used for |
|:---------|:--------|:---------|
| `A \| B` | **OR** — whichever happens first | the failsafe: *"the line, or 2 seconds, whichever comes first"* |
| `A + B` | **THEN** — A becomes true, then B | precision: *"cross the line, then 7 cm more"* |
| `A & B` | **AND** — both true | narrowing a stop to one exact state |

Nearly every `| after_seconds(...)` in this repo is a bail-out. Nearly every `+` is real logic.

### The layers

| Layer | What it does | Where |
|:------|:-------------|:------|
| **Global run cap** | `shutdown_in: 120` — the whole run is dead at 120 s, no matter what | `config/robot.yml` |
| **Mission budget** | `time_budget = 30.0` — this mission kills itself at 30 s and the run moves on | `m010_grab_first_poms_mission.py` |
| **`timeout()` wrapper** | Wraps a step that could hang: `timeout(strafe_arc_left(radius_cm=45, degrees=70), seconds=5.5)` | `m070_retrun_baskets_mission.py` |
| **Sensor + timeout** | `timeout(strafe_right().until(on_black(Defs.rear.right)), seconds=4)` — normally the line stops it; if the line never comes, 4 s does | `m070_retrun_baskets_mission.py` |
| **OR-ed escape** | `turn_left().until(after_degrees(50) \| after_seconds(3.0))` — turn 50°, but never spin forever | `m040_drive_to_baskets_mission.py` |
| **Runtime recovery** | `defer()` + a sensor check: *only* correct if we're actually wrong. `strafte_if_on_black()`, `drive_if_sensor_tirggerd()` | `m070`, `m010` |
| **Shutdown hook** | `M999ShutdownMission` — registered as `shutdown`, runs even when things went badly | `config/missions.yml` |

### The lesson

Note the pattern in `timeout(strafe_right().until(on_black(...)), seconds=4)`. There are **two** stop conditions on one step: the one you want, and the one that saves you. The sensor is the plan; the clock is the promise that the plan ends.

That's the whole idea. Every step that *could* not finish gets an answer to "and if it doesn't?" — because on the table, sooner or later, it doesn't.

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

---

## License

MIT — see [LICENSE](LICENSE).

Use it, copy it, build your competition robot on it. **You do not have to publish your own robot code because you read or reused this repo.** That's deliberate: MIT is what [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) uses, and the whole point of opening these robots up is that you *can* learn from them without strings attached.

### A request, not a requirement

We'd love it if you published your robot code **after your season ends** — not during it.

That's a norm, not a licence clause, because no licence can express it. Copyleft triggers on *distribution*, not on a date, and driving a robot at a competition isn't distribution. So GPL wouldn't protect you during the season or oblige you after it — it would just make teams nervous enough to not learn from us at all.

Keep your edge while you're competing. Then hand it forward, the way this repo does. That's how the next team starts further along than you did.
