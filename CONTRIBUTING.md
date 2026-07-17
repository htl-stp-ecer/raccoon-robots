# Contributing a Robot

Thanks for publishing your code. Seriously — this is how the next team starts further along than you did.

## The one rule

**Don't clean it up.**

We mean it. The magic numbers, the servo position called `_45deg` that is actually 47°, the mission you commented out at 2 a.m. and never deleted — that's the valuable part. Anyone can read a tidy example. Almost nobody gets to read what a real competition robot looks like at the end of a season.

If you polish your code before submitting it, you delete exactly the thing we're collecting.

The one thing we do ask: **be honest about it in your README.** Say what's broken, what you'd do differently, what the reader should not copy. An honest rough robot teaches more than a dishonest clean one.

## When to publish

**After your season ends.** Not during it.

Keep your edge while you're competing. Nobody here wants you to hand your strategy to the team you're about to face. When the season's over, hand it forward.

## How to submit

1. **Fork** this repo.
2. **Copy your project** into `robots/<season>/<team>/<robot>/`
   - `<season>` — the game you competed in, e.g. `2026-spring`, `2027-spring`
   - `<team>` — your team or school slug, e.g. `axht-3085`
   - `<robot>` — your robot's name, e.g. `clawbot`
   - Keep the folder a **complete raccoon project** — `raccoon.project.yml`, `config/`, `src/`. Don't split it up.
3. **Write a README** in your robot's folder (see below).
4. **Strip secrets.** `config/connection.yml` often has an IP or SSH details. Check it.
5. **Don't commit bytecode.** No `__pycache__/`, no `.pyc`. The root `.gitignore` covers this — make sure it took effect.
6. **Open a PR.** Fill in the template.

## Your robot's README

There's no required format, but the ones people actually read tend to have:

- **What the robot does** — the run, mission by mission, in plain language
- **Hardware** — drivetrain, sensors, servos, anything unusual
- **What's honest about it** — what's broken, what's outdated, what you'd redo
- **Ideas worth stealing** — the two or three things you got *right*, and where to look

The existing robots under `robots/2026-spring/axht-3085/` are examples of this shape. Match the spirit, not the structure.

## What we'll do

We'll read it, maybe ask a question or two, and merge it. We are not going to review your code quality — that's not what this is for. A PR gets bounced only if it's incomplete, contains secrets, or isn't a raccoon project.

## Licensing

By opening a PR you agree to license your contribution under the [MIT License](LICENSE), the same as everything else here — so any team can learn from it and build on it without owing anything back.

You keep the copyright on your code. You're granting permission, not giving it away.

## Questions

Open an issue. Or check the [documentation](https://raccoon-docs.pages.dev/) if it's about RaccoonOS itself.
