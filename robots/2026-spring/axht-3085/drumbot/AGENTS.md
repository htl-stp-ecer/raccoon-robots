# Drumbot Agent Notes

## Source of Truth
- `raccoon.project.yml` is the source of truth for robot configuration.
- `src/hardware/defs.py` and `src/hardware/robot.py` are generated artifacts and should not be hand-edited for permanent changes.

## Code Structure (How To Place New Logic)
- `src/missions/`: high-level behavior sequencing only.
- `src/steps/`: reusable mission actions and UI-driven steps.
- `src/service/`: stateful business logic and control algorithms used by steps.
- `src/hardware/`: generated hardware definitions and robot config.

## Implementation Rules
- Add or change mission flow in `src/missions/*`.
- Put operation boundaries in steps (`@dsl`, `Step`, `UIStep`) under `src/steps/*`.
- Put shared, stateful mechanism logic in services under `src/service/*`.
- Keep hardware wiring/ports/kinematics in `raccoon.project.yml`; regenerate via `raccoon run` workflow.
- Avoid placing long control logic directly inside mission files.
- Prefer mission -> step -> service call flow for mechanism features.
- Many functionalities are already provided by `raccoon`; first check what exists before implementing custom code.
- Default strategy: use `raccoon` primitives where available, write custom logic only for missing capabilities.

## Raccoon Connection Workflow
- Call `raccoon connect <ip>` only when:
  - the target IP/device changed, or
  - there is no active connection.
- Do not reconnect before every run if connection is still valid.

## Run Workflow
- Use `raccoon run` as the default program execution command.
- Expected behavior of `raccoon run`:
  - upload local project to the device,
  - run codegen on the device,
  - execute `src.main`,
  - pull files back to keep local and remote in sync.

## Calibration Command Note
- `raccoon calibrate motors` / `raccoon calibrate motors -y` are considered not part of the active workflow here.

## raccoon Capability Discovery
- If feature design depends on unknown `raccoon` APIs, inspect available APIs first.
- Preferred approach when needed: SSH to the Pi and run Python introspection (`python3`, `dir()`, `help()`, `inspect`) against installed `raccoon`.
- Use this discovery step before inventing unsupported calls.
