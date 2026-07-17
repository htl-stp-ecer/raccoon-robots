# Contributing a robot

Thanks for publishing your code. It's the main way the next team gets to start from something real.

## Don't clean it up first

We mean this literally. The magic numbers, the servo position called `_45deg` that's actually at 47°, the mission you commented out at 2am and never deleted: that's the useful part. Tidy example code is easy to find. Code that shows what a robot looks like at the end of a season isn't.

If you polish it before submitting, you remove the thing we're collecting.

What we do ask is that you're honest about it in your README. Say what's broken, what you'd do differently, and what nobody should copy. A rough robot with an honest README is more useful than a clean one that hides its problems.

## When to publish

After your season ends, not during it. Keep your advantage while you're still competing.

## How to submit

1. Fork this repo.
2. Copy your project into `robots/<season>/<team>/<robot>/`
   - `<season>`: the game you competed in, e.g. `2026-spring`
   - `<team>`: your Botball team number or slug, e.g. `axht-3085`
   - `<robot>`: your robot's name, e.g. `clawbot`
   - Keep it as one complete raccoon project (`raccoon.project.yml`, `config/`, `src/`). Don't split it up.
3. Write a README in your robot's folder (see below).
4. Check for secrets. `config/connection.yml` usually has an IP and SSH details in it.
5. Don't commit bytecode. The root `.gitignore` covers `__pycache__/` and `*.pyc`, but check it took effect.
6. Open a PR and fill in the template.

## Your robot's README

No required format. The ones people get the most out of usually cover:

- What the robot does, mission by mission
- Hardware: drivetrain, sensors, servos, anything unusual
- What's broken or outdated, and what you'd redo
- The two or three things you got right, and where to look for them

The robots under `robots/2026-spring/axht-3085/` are examples of roughly this shape. Match the spirit rather than the structure.

## What happens next

We'll read it, maybe ask a question, and merge it. We're not going to review your code quality, that's not what this repo is for. PRs only get bounced if they're incomplete, contain secrets, or aren't a raccoon project.

## Licensing

Opening a PR licenses your contribution under the [MIT License](LICENSE), same as the rest of the repo, so other teams can use it without owing anything back. You keep the copyright. You're granting permission, not signing it over.

## Questions

Open an issue. If it's about RaccoonOS itself, the [documentation](https://raccoon-docs.pages.dev/) is probably faster.
