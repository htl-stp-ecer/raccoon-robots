# drumbot

Team `axht-3085` · Botball Spring 2026 · differential drive

The most mechanically ambitious of the team's 2026 robots: it collects colour-coded
drums from a dispenser, **identifies each drum's colour with a USB camera**, and sorts
them into an 8-pocket revolver so the two colours end up grouped. It also clears poms
and returns cones. Two minutes, one camera, a lot of moving parts.

> **Read the history warning at the bottom before you judge any single line.** This is
> end-of-season competition code. It works on the table; it is not clean.

---

## What it does, mission by mission

`config/missions.yml` runs these in order (setup and shutdown are special roles):

| Mission | What happens |
|:--------|:-------------|
| **M000 Setup** | Opens the USB camera once (stays open the whole run), colour-calibrates the drums, calibrates the IR + distance sensors with a `collect_drive`, samples the drum-collector light sensor, and asks up front whether to use position holding. This is a *big* setup — most of the fragility budget is spent here so the match itself is deterministic. |
| **M010 DriveToDrums** | Drives out of the start box and over to the drum dispenser, clearing poms on the way with the `pom_remover` servo. |
| **M020 CollectDrums** | The heart of the robot. Waits for a drum, reads its colour from the vision daemon, decides which revolver pocket it belongs in (`SortingService`), rotates the drum motor to that pocket (`DrumMotorService`, with learned ticks-per-pocket + stall detection), and ejects. Repeats for all 8 drums. |
| **M030 / M040 DriveToPipe / DriveToOtherPipe** | Positions at the delivery pipes. |
| **M050 ReturnCones** | Uses the cone pusher to return cones. |
| **M999 Shutdown** | Stops the camera, disables servos, cuts the cone-pusher motor. |

## Hardware

- **Drive**: differential, two encoder motors.
- **Drum mechanism**: `drum_motor` (revolver), `drum_pusher_servo`, `lift_drums_servo`
  (many named positions — `eject_position`, `seek_position`, `align_on_back`, …),
  `drum_light_sensor` for pocket detection.
- **Poms/cones**: `pom_remover_servo`, `cone_pusher_motor`.
- **Sensing**: front-right + rear-left IR line sensors, IMU, and a **USB camera** driven
  by a background vision daemon (`src/daemons/vision.py`, registered in
  `config/services.yml` as a systemd service that restarts on change).

## The three things worth stealing

1. **A real service layer.** `src/service/` is the good part: `ColorDetectionService`
   (talks to the vision daemon over raccoon-transport), `SortingService` (bidirectional
   revolver sort — two colours grow inward from opposite ends so same-colour drums are
   always one slot apart), and `DrumMotorService` (learns ticks-per-pocket, detects
   stalls). Steps stay thin; the algorithms live here.
2. **A camera as a background daemon.** The vision process runs independently and the
   robot subscribes to detections — the pattern to copy if you ever need a camera in a
   time-limited run. This robot is why the config gained `services.yml`.
3. **A heavy, honest setup mission.** Colour calibration, IR/distance calibration, and a
   `calibration_gate` that refuses to continue if the data is missing — fail in setup,
   not mid-match. It even ships its own `.claude/skills/debug-run-logs/` with plotting
   scripts.

## What's broken / what we'd redo

Straight from the `todo` file and the commit log, honestly:

- **Colour detection falls back to guessing.** When the camera fails to lock a colour in
  time, it effectively defaults to blue. The `todo` wants probability-weighted guessing
  from learned timing instead — never finished.
- **Stall-retry is half-reworked.** See the commit literally titled
  *"verschlimmbesserung: retreat should now not redo all moves on stall but broken :)"*.
  The retry logic on a jammed drum motor is not fully trustworthy.
- **Timing windows can hurt the hardware.** If a new drum arrives before the previous one
  is processed, the servo can close on nothing / the mechanism can bind. The `todo` notes
  a planned safety cutout that was never added.
- **Corrupt JPEG spam.** The camera stream logs `Corrupt JPEG data: N extraneous bytes`
  constantly. Cosmetic, but it drowns the logs.
- **Ad-hoc notes checked into the repo root.** `DRUM_KALIBRIERUNG_FIX.md`, `EJECT_VERIFICATION.md`,
  and a free-text `todo` (half German, half English, with a line of JPEG-corruption spam pasted
  in) live right next to the code. Loose binary debug frames were stripped when the robot was
  published, but the notes stayed — they're part of the story.

## Running it

```bash
raccoon connect drumbot.local
raccoon run                 # or: raccoon run --config dev / dev-nc / dev-fake
```

`dev-fake` swaps the real camera for `FakeColorDetectionService` so you can iterate
without a working vision daemon. See `config/run-configurations.yml`.

---

## ⚠️ About the commit history

**The commit history is really, really, *reaaaaally* bad, and we're keeping it that way.**

It was written at 2am between test runs by a rotating cast of team members. You will find:

- `anti-fix: idk`
- `fix: add missing _`
- `verschlimmbesserung: ... but broken :)` (German for "dis-improvement")
- a merry mix of German and English, profanity, and "improve reliability" for the tenth time on the same line

`git log` on this folder is **not** a clean narrative of good decisions. It's a record of
what actually happened: guesses, reverts, re-reverts, and things that only made sense with
the robot physically in front of you. Read it for *how a robot really evolves under
competition pressure*, not as an example to imitate. If a commit message contradicts the
code, trust the code.
