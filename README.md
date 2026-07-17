<div align="center">

<img src="https://raw.githubusercontent.com/htl-stp-ecer/.github/main/profile/raccoon-logo.svg" alt="raccoon-robots" width="100"/>

# raccoon-robots

**Real Botball robots, real competition code, published after the season.**

A growing collection of robot programs built with [RaccoonOS](https://github.com/htl-stp-ecer) — contributed by the teams who actually drove them.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=ffdd54)
![Platform](https://img.shields.io/badge/Platform-KIPR%20Wombat-orange)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-8B6F47.svg)](CONTRIBUTING.md)

> 📖 **Platform documentation at [raccoon-docs.pages.dev](https://raccoon-docs.pages.dev/)**

</div>

---

## Why This Exists

Every Botball season, dozens of teams write a robot program, drive it, and then it dies somewhere. The next team starts from an empty folder and rediscovers the same things: that hardcoded distances drift, that a mission without a timeout hangs forever, that servo angles belong in config and not in your source.

**That's a waste.** Not of code — of learning.

So this repo collects the real thing. Not tutorials, not tidied-up demos: the actual programs that ran at competitions, with the magic numbers and the typos and the commented-out experiments still in them. That's what makes them worth reading. A clean example shows you the destination; a real robot shows you the road.

> **Looking for a clean starting point instead?** Go to **[raccoon-example](https://github.com/htl-stp-ecer/raccoon-example)** — a fully-commented reference robot with no competition pressure baked in. Come back here when you want to see how the ideas survive contact with a game table.

---

## The Robots

### 🗓️ Botball Spring Game 2026

| Robot | Team | What's interesting about it |
|:------|:-----|:----------------------------|
| **[clawbot](robots/2026-spring/axht-3085/clawbot)** | `axht-3085` | 3-DOF arm with hand-rolled inverse kinematics — the code that convinced RaccoonOS to grow a real arm API. Mecanum, ramp navigation |
| **[packing-bot](robots/2026-spring/axht-3085/packing-bot)** | `axht-3085` | Pom sorting and basket handling. The most complete failsafe layering in the collection — timeouts, budgets, `defer()` recovery |
| **[cone-bot](robots/2026-spring/axht-3085/cone-bot)** | `axht-3085` | An honest early prototype, abandoned mid-season. Differential drive. What a robot looks like two weeks in, before it gets good |

*Your robot could be the next row. See [CONTRIBUTING.md](CONTRIBUTING.md).*

---

## What You'll Actually Learn Here

Patterns that show up across the robots — worth knowing before you read any of them:

| Pattern | Why it matters |
|:--------|:---------------|
| **Your robot will fail — build for it** | Every risky step carries an escape hatch: `timeout(step, seconds=4)`, `.until(on_black(...) \| after_seconds(2))`, a `time_budget` on a mission. A hung mission doesn't cost you one action, it costs every action after it |
| **Sensor stop conditions over hardcoded distances** | `drive_forward().until(over_line(...))` survives a slipping wheel. `drive_forward(cm=30)` does not |
| **Named positions in YAML** | `Defs.claw.open()`, never `set_servo(3, 140)`. Remeasure in one place after a rebuild |
| **One mission = one scoring action** | Numbered in tens (`m010`, `m020`) so you can insert one without renaming everything |
| **`parallel()` everything** | Move the arm *while* driving. Wall-clock is the scarce resource |

Each robot's README calls out its own specifics.

---

## Layout

```
robots/
└── <season>/           # e.g. 2026-spring — the game changes every year
    └── <team>/         # e.g. htl-stp-ecer
        └── <robot>/    # a complete raccoon project, as it ran
            ├── README.md
            ├── raccoon.project.yml
            ├── config/
            └── src/
```

Each robot folder is a **complete, self-contained raccoon project** — the same shape `raccoon create` gives you.

Full history is preserved. Every robot was imported with its original commits intact, so `git log` on a robot folder shows how it actually evolved — including the reverts and the 2 a.m. commits.

---

## Contributing Your Robot

**Please do.** That's the entire point of this repo.

Publish after your season ends — keep your edge while you're competing, then hand it forward. Your rough, real, unpolished competition code is more useful to the next team than anything we could write for them.

You don't need to clean it up. You don't need to be proud of it. See **[CONTRIBUTING.md](CONTRIBUTING.md)** for the (short) checklist.

---

## Part of RaccoonOS

| Repository | What it is |
|:-----------|:-----------|
| [raccoon-example](https://github.com/htl-stp-ecer/raccoon-example) | Clean reference robot — **start here if you're new** |
| [raccoon-lib](https://github.com/htl-stp-ecer/raccoon-lib) | The core robotics library |
| [raccoon-cli](https://github.com/htl-stp-ecer/raccoon-cli) | `raccoon run`, `raccoon calibrate`, `raccoon create` |
| [WebIDE](https://github.com/htl-stp-ecer/WebIDE) | Visual flowchart editor and 3D arm visualizer |
| [botui](https://github.com/htl-stp-ecer/botui) | Wombat dashboard |
| [documentation](https://raccoon-docs.pages.dev/) | Full platform docs |

---

## License

MIT — see [LICENSE](LICENSE).

Use anything here, in any robot, without publishing your own code in return. Contributors license their robot under the same terms by opening a PR.

---

Maintained by the Botball team at **HTL St. Pölten**.
