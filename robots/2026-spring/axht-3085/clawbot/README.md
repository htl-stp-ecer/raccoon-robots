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

## What This Became

This file is why RaccoonOS has arm support at all.

ClawBot's `arm.py` was hand-rolled: link lengths in Python, calibration tables in YAML, IK solved on the robot at match time. It worked — but it was ours alone. Every team with an arm would have had to write it again, and every one of them would have gotten the extrapolation and the clamping subtly wrong.

So the platform grew a real version of it, generalised out of exactly what's in this repo:

| ClawBot did it by hand | RaccoonOS does it now |
|:-----------------------|:----------------------|
| Link lengths hardcoded in `arm.py` | `type: ArmChain` in `raccoon.project.yml` — joints, link lengths, servo mappings, workspace limits |
| Poses computed from IK on the robot | **Codegen IK** — `raccoon codegen` solves every named position offline with `ikpy`, validates it against workspace limits and forbidden zones, and emits literal servo angles into `defs.py`. No math and no IK dependency at match time |
| Interpolation tables read from `Defs` | `ArmPreset` — generated, one method per named position: `Defs.arm.home()`, `Defs.arm.grab(speed=60)` |
| Tuned by driving servos and watching the arm | **[Arm Visualizer](https://raccoon-docs.pages.dev/03-web-ide/13-arm-panel) in the WebIDE** — the arm chain rendered in a THREE.js 3D scene: drag the end-effector to solve IK, set joint angles for FK, see the workspace envelope and joint axes, save named positions, and push angles to the physical servos live |

The trade the platform made is one this repo argued for: most arms only need a handful of named positions (home, grab, drop, handoff), so pre-solving them at build time costs nothing and catches an unreachable target on your laptop instead of on the table.

ClawBot's approach didn't disappear, though — it's the documented escape hatch. When an arm's geometry doesn't fit `ArmChain`, or when it genuinely needs runtime IK because it's tracking something a sensor found, you write kinematics in project Python. The [arm kinematics docs](https://raccoon-docs.pages.dev/02-programming/20-arm-kinematics-and-codegen) name this robot as the example of it.

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

## Your Robot Will Fail — Build For It

If you read this repo for one thing, read it for this.

A drum sits 2 cm off. The ramp gives one wheel less grip than the other. The arm closes on air. **This is normal.** A mission that assumes success hangs, and a hung mission doesn't cost you one action — it costs you every action after it. So almost every risky step here carries an escape hatch.

### The vocabulary

Stop conditions compose with three operators, and the distinction matters:

| Operator | Meaning | Used for |
|:---------|:--------|:---------|
| `A \| B` | **OR** — whichever happens first | the failsafe: *"the line, or 2 seconds, whichever comes first"* |
| `A + B` | **THEN** — A becomes true, then B | precision: *"cross both sensors, then 6 cm more"* |
| `A & B` | **AND** — both true | narrowing a stop to one exact state |

Nearly every `| after_seconds(...)` in this repo is a bail-out. Nearly every `+` is real logic.

### The layers

| Layer | What it does | Where |
|:------|:-------------|:------|
| **Global run cap** | `shutdown_in: 120` — the whole run is dead at 120 s, no matter what | `config/robot.yml` |
| **`timeout()` wrapper** | `timeout(drive_forward().until(on_black(Defs.front.left)), seconds=0.5)` — the line is normally *right there*; if it isn't, half a second and we move on rather than driving into the wall | `m030_collect_drums_mission.py` |
| **OR-ed escape** | `strafe_left(heading=0).until(on_black(Defs.front.left) \| after_seconds(2))` | `m050_drive_up_the_ramp_mission.py` |
| **`background()`** | Return the tray *while* the robot drives on. Cleanup never blocks the next scoring action | `m030_collect_drums_mission.py` |
| **Checkpoint sync** | `wait_for_checkpoint(68)` — wait on the wall clock for the other robot, don't assume it's done | `m030_collect_drums_mission.py` |
| **Shutdown hook** | `M999ShutdownMission` — registered as `shutdown`, runs even when things went badly | `config/missions.yml` |
| **IK clamping** | A bad IK solution gets clamped to the servo's hardware limits instead of driving the arm into the frame | `kinematics/arm.py` |

### The lesson

Note the pattern in `timeout(drive_forward().until(on_black(...)), seconds=0.5)`. There are **two** stop conditions on one step: the one you want, and the one that saves you. The sensor is the plan; the clock is the promise that the plan ends.

That's the whole idea. Every step that *could* not finish gets an answer to "and if it doesn't?" — because on the table, sooner or later, it doesn't.

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
| [WebIDE](https://github.com/htl-stp-ecer/WebIDE) | Visual editor — home of the 3D Arm Visualizer this robot inspired |
| [packing-bot](https://github.com/htl-stp-ecer/packing-bot) | Our other Spring 2026 robot — pom sorting and baskets |
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
