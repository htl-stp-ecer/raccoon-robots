<div align="center">

<img src="https://raw.githubusercontent.com/htl-stp-ecer/.github/main/profile/raccoon-logo.svg" alt="raccoon-robots" width="100"/>

# raccoon-robots

**Botball competition code from real teams, published after their season.**

Robot programs built with [RaccoonOS](https://github.com/htl-stp-ecer), contributed by the teams who drove them.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=ffdd54)
![Platform](https://img.shields.io/badge/Platform-KIPR%20Wombat-orange)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-8B6F47.svg)](CONTRIBUTING.md)

> 📖 Platform documentation at [raccoon-docs.pages.dev](https://raccoon-docs.pages.dev/)

</div>

---

## Why this exists

Every Botball season, dozens of teams write a robot program, drive it, and then it dies somewhere. The next team starts from an empty folder and rediscovers the same things: that hardcoded distances drift, that a mission without a timeout hangs forever, that servo angles belong in config and not in your source.

This repo collects the code that actually ran at competitions. It isn't tutorial material. The robots here still contain their magic numbers, their typos, and the experiments nobody got around to deleting. That's deliberate. Cleaned-up examples show you what the result should look like, which is a different and easier question than what to do when the robot doesn't behave.

If you want a clean starting point, use [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) instead. It's a fully commented reference robot with none of the competition mess. This repo is worth reading afterwards, when you want to see how those ideas hold up on a game table.

---

## The robots

### Botball Spring Game 2026

| Robot | Team | Notes |
|:------|:-----|:------|
| **[clawbot](robots/2026-spring/axht-3085/clawbot)** | `axht-3085` | 3-DOF arm with hand-written inverse kinematics. Mecanum drive, ramp navigation. This code is why RaccoonOS later grew a proper arm API |
| **[packing-bot](robots/2026-spring/axht-3085/packing-bot)** | `axht-3085` | Pom sorting and basket handling. Has the most thorough failsafe handling of the three: timeouts, mission budgets, `defer()` recovery |
| **[cone-bot](robots/2026-spring/axht-3085/cone-bot)** | `axht-3085` | An early prototype that was abandoned mid-season. Differential drive. Useful as a look at an unfinished robot rather than a polished one |
| **[drumbot](robots/2026-spring/axht-3085/drumbot)** | `axht-3085` | The most mechanically ambitious of the set: a USB camera identifies coloured drums and sorts them into an 8-pocket revolver. Vision daemon, learned drum-motor timing, a real `src/service/` layer — and the messiest history of them all |
| **[cube-bot](robots/2026-spring/axht-3085/cube-bot)** | `axht-3085` | Mecanum drive + a 3-DOF arm (`src/kinematics/arm.py`). Grabs and stacks cubes, climbs a ramp. Structurally the cleanest — it introduced the `ParamSet` and `TableMap` patterns |

Your robot can be the next row. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Patterns you'll see across these robots

| Pattern | Why it's there |
|:--------|:---------------|
| Escape hatches on risky steps | `timeout(step, seconds=4)`, `.until(on_black(...) \| after_seconds(2))`, `time_budget` on a mission. A step that hangs doesn't just cost you that action, it costs everything scheduled after it |
| Sensor stop conditions instead of fixed distances | `drive_forward().until(over_line(...))` still works when a wheel slips. `drive_forward(cm=30)` doesn't |
| Named positions in YAML | `Defs.claw.open()` rather than `set_servo(3, 140)`, so a rebuild means remeasuring in one place |
| One mission per scoring action | Numbered in tens (`m010`, `m020`) so a new mission can be inserted without renaming the rest |
| `parallel()` used heavily | Arm movement overlapped with driving, because the run is time-limited |

Each robot's README covers its own details.

---

## Layout

```
robots/
└── <season>/           # e.g. 2026-spring
    └── <team>/         # e.g. axht-3085
        └── <robot>/    # a complete raccoon project
            ├── README.md
            ├── raccoon.project.yml
            ├── config/
            └── src/
```

Each robot folder is a complete raccoon project, the same shape `raccoon create` produces.

---

## ⚠️ The commit history is really, really, *reaaaaally* bad

We say this up front so you calibrate your expectations before you open `git log`.

Git history **is** preserved — every robot was imported with its original commits, so
`git log robots/2026-spring/axht-3085/<robot>` shows how it actually developed. That's the
point. But "how it actually developed" means hundreds of commits written at the table,
mid-tournament, at 2am, by a rotating cast of teenagers. It is **not** a curated example of
good version control. A representative sample:

- `anti-fix: idk`
- `scheißbot >:(`
- `verschlimmbesserung: retreat should now not redo all moves on stall but broken :)`
- `dont do that, was just for home not gcer`
- `fix: add missing _`
- and dozens of typo-ridden "so we don't crash / so we defently are on the cube" one-liners, in a cheerful German-English blend

So:

- **Read the messages for the *reasoning*, not as a model.** "strafing a cm more so we push
  the cube stack further in some edge cases" tells you something real about the table. The
  spelling does not.
- **If a commit message contradicts the code, trust the code.** Several "fixes" made things
  worse and were reverted (or re-broken) a few commits later.
- **Don't @ us about it.** It's preserved on purpose. Cleaning it up would delete the actual
  history of a competition robot, which is the one thing you can't get from
  [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example).

Each robot's own README has a matching, more specific warning.

---

## Contributing

Please do. That's the point of the repo.

Publish once your season is over, not during it. Rough, unpolished competition code is more useful to the next team than anything written specifically as an example.

See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Part of RaccoonOS

| Repository | What it is |
|:-----------|:-----------|
| [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) | Clean reference robot. Start here if you're new |
| [raccoon-lib](https://github.com/htl-stp-ecer/raccoon-lib) | The core robotics library |
| [raccoon-cli](https://github.com/htl-stp-ecer/raccoon-cli) | `raccoon run`, `raccoon calibrate`, `raccoon create` |
| [WebIDE](https://github.com/htl-stp-ecer/WebIDE) | Visual flowchart editor and 3D arm visualiser |
| [botui](https://github.com/htl-stp-ecer/botui) | Wombat dashboard |
| [documentation](https://raccoon-docs.pages.dev/) | Full platform docs |

---

## License

MIT, see [LICENSE](LICENSE).

You can use anything here in your own robot without publishing your code in return. Contributors license their robot under the same terms by opening a PR.

---

Maintained by team `axht-3085` at HTL St. Pölten.
