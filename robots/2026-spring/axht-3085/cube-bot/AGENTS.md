# ClawBot Agent Notes

## Source of Truth
- `raccoon.project.yml` is the source of truth for robot configuration.
- `src/hardware/defs.py` and `src/hardware/robot.py` are generated artifacts and should not be hand-edited for permanent changes.

## Code Structure (How To Place New Logic)
- `src/missions/`: high-level behavior sequencing only. No business logic here.
- `src/steps/bot.py`: **the single import for missions** — pre-built servo presets and sensor groups.
- `src/steps/servo_preset.py`: generic `ServoPreset` class (reusable across projects).
- `src/steps/line_sensors.py`: generic `LineSensors` class (reusable across projects).
- `src/service/`: stateful business logic and control algorithms (add when needed).
- `src/hardware/`: generated hardware definitions and robot config.

## How Servos Work
Define positions once in `bot.py` as a `ServoPreset`:
```python
pom_arm = ServoPreset(Defs.pom_arm, default_speed=250, positions={
    "down": 0, "up": 90, "start": (140, 400),
})
```
Use in missions: `pom_arm.down()`, `pom_arm.up(speed=500)`

## How Sensor Groups Work
Define sensor pairs once in `bot.py` as a `LineSensors`:
```python
front = LineSensors(left=Defs.front_left_light_sensor, right=Defs.front_right_light_sensor)
```
Use in missions: `front.lineup_on_black()`, `front.drive_over_line()`, `front.follow_right_edge(125)`

## Implementation Rules
- Import from `src.steps.bot` in missions — not from individual step files.
- Add new servo positions by editing the preset dict in `bot.py`.
- Add new sensor operations by adding methods to `LineSensors`.
- Put shared, stateful mechanism logic in services under `src/service/*`.
- Keep hardware wiring/ports/kinematics in `raccoon.project.yml`; regenerate via `raccoon run`.
- Prefer libstp primitives where available; write custom logic only for missing capabilities.

## Naming Conventions
- Missions: `M{number}{Description}Mission` (e.g., `M02GrabFirstPomsMission`)
- Servo presets: lowercase mechanism name (e.g., `pom_arm`, `shield_grabber`)
- Sensor groups: location name (e.g., `front`, `rear`)
- Preset positions: short descriptive name (e.g., `"down"`, `"high_up"`, `"pom_width"`)

## Raccoon Connection Workflow
- Call `raccoon connect <ip>` only when the target IP/device changed or there is no active connection.
- Do not reconnect before every run if connection is still valid.

## Run Workflow
- Use `raccoon run` as the default program execution command.
- Expected behavior: upload, codegen, execute `src.main`, pull files back to sync.

## libstp Capability Discovery
- If feature design depends on unknown `libstp` APIs, inspect available APIs first.
- Preferred approach: SSH to the Pi and run Python introspection (`dir()`, `help()`, `inspect`) against installed `libstp`.
- Use this discovery step before inventing unsupported calls.
