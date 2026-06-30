import asyncio
import time

from raccoon import GenericRobot, dsl, parallel, seq, wait_for_seconds, wait_for_button
from raccoon.foundation import ChassisVelocity
from raccoon.ui.step import UIStep

from src.hardware.defs import Defs
from src.service.color_detection_service import ColorDetectionService
from src.service.drum_motor_service import DrumMotorService, MotorStalledError
from src.steps.drum_collector.screens.drum_collection_screen import DrumCollectionScreen
from src.steps.drum_collector.screens.emergency_screen import EmergencyScreen
from src.steps.drum_collector.sort_into_slot_step import (
    advance_to_midpoint,
    block_timer_check,
    block_timer_start,
    rotate_to_next_empty_pocket,
    sort_into_slot,
)
from src.steps.drum_lifting_step import drum_align_on_back, drum_lifting_down, drum_lifting_up
from src.steps.terminate_leftover_velocity import terminate_leftover_velocity
from src.steps.wait_for_drum_step import wait_for_drum

START_OFFSET = 9.5
DRUMS = 8
TIME_BETWEEN_DRUMS = 7
EXTERNAL_DRIFT_PER_DRUM = 0.25  # external dropper overshoots ~0.25s per cycle
TIMING_SAFETY_THRESHOLD = 0.5

# On an emergency the program must NOT exit (a dead robot in a competition run
# gets hit by others). Instead we abandon collection, lock the big drum, show
# the emergency screen, and hold it until this run-clock mark — then return so
# the mission sequence proceeds to the post-collection wait_for_checkpoint and
# the robot drives its path. Drum-motor commands stay locked for the rest of the
# run (see DrumMotorService.motor_locked).
EMERGENCY_RELEASE_TIME = 50.0  # robot.synchronizer.get_time() seconds

# Lift-motor-stop wait: the drum lift motor (servo_help_motor) is still moving
# when the previous mission finishes lowering the collector. Starting color
# detection before it settles picks up background through a moving camera.
LIFT_STOP_POLL = 0.03
LIFT_STOP_STABLE_WINDOW = 0.15  # motor is "stopped" when encoder hasn't moved for this long
LIFT_STOP_TICK_TOLERANCE = 3    # ignore sub-3-tick encoder jitter
LIFT_STOP_TIMEOUT = 2.0

# Position hold during collection.
#
# The forward push that keeps the robot pressed against the wall is applied
# ONCE before collection by m020's set_position_hold_velocity() step — the
# wombat firmware holds that velocity-PID target for the whole collection (the
# same persistence behind the wall_align leftover-velocity bug). We only need
# this rate here for _stop_drive's single update() tick when clearing velocity.
POSITION_HOLD_HZ = 50


@dsl(hidden=True)
class CollectDrumsStep(UIStep):
    """Run drum collection with live UI overlay."""

    async def _execute_step(self, robot: "GenericRobot") -> None:
        color_service = robot.get_service(ColorDetectionService)
        drum_service = robot.get_service(DrumMotorService)

        # Clear any residual chassis velocity left by the previous mission's
        # wall_align (see POSITION_HOLD_* notes above). Without this the robot
        # keeps driving forward through the entire collection.
        self._stop_drive(robot)

        # Wait for the drum-lift motor (servo_help_motor) to fully stop before
        # we start color detection — if it's still moving the camera picks up
        # scrolling background and triggers spurious detections.
        await self._wait_for_lift_motor_stopped()
        color_service.reset()

        screen = DrumCollectionScreen()
        screen.total_drums = DRUMS
        await self.display(screen)

        self._emergency_reason: str | None = None

        ui_task = asyncio.create_task(
            self._ui_updater(screen, color_service, robot),
        )
        stuck_task = asyncio.create_task(
            self._stuck_drum_monitor(color_service, drum_service, robot),
        )
        # Stored so the emergency handler can stop the collection-screen updater
        # before showing the emergency screen (otherwise the two screens fight).
        self._ui_task = ui_task
        self._stuck_task = stuck_task

        # Collection is stricter: one retry, then emergency shutdown.
        # Restored in finally so ejection keeps the default 3-attempt budget.
        prior_stall_retries = drum_service.stall_retries
        drum_service.stall_retries = 2

        try:
            for i in range(DRUMS):
                drum_number = i + 1
                checkpoint = START_OFFSET + i * TIME_BETWEEN_DRUMS + i * EXTERNAL_DRIFT_PER_DRUM

                if drum_service.collection_failed:
                    # An emergency was raised (e.g. by the stuck-drum watchdog
                    # in a background task). Stop collecting and hand off to the
                    # emergency hold below.
                    self.warn(f"Emergency active before drum #{drum_number} — abandoning collection")
                    break

                screen.drum_number = drum_number
                screen.status = "Waiting for drum..."

                try:
                    elapsed_pre = robot.synchronizer.get_time()
                except (TypeError, AttributeError):
                    elapsed_pre = -1.0
                drum_service.info(
                    f"[DRUM-{drum_number}] START checkpoint={checkpoint:.2f}s "
                    f"elapsed={elapsed_pre:.2f}s "
                    f"pocket={drum_service.current_pocket}"
                )

                try:
                    # Wait for the drum to arrive and get captured.
                    # rotate_to_next_empty_pocket must run before pusher.open():
                    # current_pocket sits on the just-filled slot, so opening
                    # the loading hole there would let the sorted drum fall out.
                    phase1a = seq([
                        rotate_to_next_empty_pocket(),
                        Defs.drum_pusher_servo.open(),
                        wait_for_drum(checkpoint=checkpoint),
                        block_timer_start(),
                    ])
                    await phase1a.run_step(robot)

                    phase1b = seq([
                        wait_for_seconds(0.5),
                        sort_into_slot(),
                    ])
                    await phase1b.run_step(robot)
                except MotorStalledError:
                    if not drum_service.collection_failed:
                        drum_service.motor.brake()
                        await self._enter_safe_mode(robot, drum_service)
                        self._emergency_reason = f"Drum motor stuck (drum #{drum_number})"
                    break

                if i < DRUMS - 1:
                    next_checkpoint = START_OFFSET + (i + 1) * TIME_BETWEEN_DRUMS
                    try:
                        elapsed = robot.synchronizer.get_time()
                        time_until_next = next_checkpoint - elapsed
                    except (TypeError, AttributeError):
                        time_until_next = float("inf")

                    if time_until_next < TIMING_SAFETY_THRESHOLD:
                        self.warn(
                            f"TIMING BLOWN: only {time_until_next:.2f}s until "
                            f"next drum — entering safe mode to protect hardware"
                        )
                        drum_service.motor.brake()
                        await self._enter_safe_mode(robot, drum_service)
                        self._emergency_reason = "Timing too tight — protecting hardware"
                        break

                try:
                    elapsed_post = robot.synchronizer.get_time()
                except (TypeError, AttributeError):
                    elapsed_post = -1.0
                drum_service.info(
                    f"[DRUM-{drum_number}] SORTED pocket={drum_service.current_pocket} "
                    f"elapsed={elapsed_post:.2f}s"
                )

                if drum_service.collection_failed:
                    # Emergency raised during sort — keep pusher open, hand off.
                    break

                try:
                    phase3 = seq([
                        Defs.drum_pusher_servo.close(),
                        wait_for_seconds(0.5),
                        block_timer_check(drum_number),
                    ])
                    await phase3.run_step(robot)
                except MotorStalledError:
                    if not drum_service.collection_failed:
                        drum_service.motor.brake()
                        await self._enter_safe_mode(robot, drum_service)
                        self._emergency_reason = f"Drum motor stuck (closing pusher after drum #{drum_number})"
                    break

                try:
                    elapsed_done = robot.synchronizer.get_time()
                except (TypeError, AttributeError):
                    elapsed_done = -1.0
                drum_service.info(
                    f"[DRUM-{drum_number}] DONE pocket={drum_service.current_pocket} "
                    f"elapsed={elapsed_done:.2f}s"
                )
                screen.status = "Done"

            # If an emergency abandoned collection, hold the emergency screen
            # (no shutdown — the robot stays alive) until the run clock reaches
            # the release mark, then return so the mission sequence proceeds to
            # the post-collection wait_for_checkpoint and the robot drives on.
            if drum_service.collection_failed:
                await self._emergency_hold(robot)
        finally:
            if drum_service.collection_failed:
                # Safe mode: keep retries at 1 (no retry) for rest of run
                # so eject attempts don't risk hardware damage.
                drum_service.stall_retries = 1
            else:
                drum_service.stall_retries = prior_stall_retries
            for task in (ui_task, stuck_task):
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            # Guarantee the chassis is stopped on exit regardless of how the
            # collection loop above terminated.
            self._stop_drive(robot)

    def _stop_drive(self, robot: "GenericRobot") -> None:
        """Actually halt the chassis, clearing the firmware velocity target.

        ``hard_stop()`` alone only sends a PASSIVE_BRAKE mode command; it never
        sends a zero velocity, so the STM32 keeps the last commanded
        velocity-PID target. Push an explicit zero velocity through the drive
        first (same path motion steps use), then brake.
        """
        robot.drive.set_velocity(ChassisVelocity(0.0, 0.0, 0.0))
        robot.drive.update(1.0 / POSITION_HOLD_HZ)
        robot.drive.hard_stop()

    async def _wait_for_lift_motor_stopped(self) -> None:
        """Block until servo_help_motor encoder has been stable for a full window."""
        motor = Defs.servo_help_motor
        start = time.monotonic()
        last_pos = motor.get_position()
        stable_since = start
        while True:
            await asyncio.sleep(LIFT_STOP_POLL)
            cur_pos = motor.get_position()
            if abs(cur_pos - last_pos) > LIFT_STOP_TICK_TOLERANCE:
                last_pos = cur_pos
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= LIFT_STOP_STABLE_WINDOW:
                self.info(
                    f"Lift motor settled (waited {time.monotonic() - start:.2f}s "
                    f"before starting drum collection)"
                )
                return
            if time.monotonic() - start > LIFT_STOP_TIMEOUT:
                self.warn(
                    f"Lift motor did not fully stop after {LIFT_STOP_TIMEOUT}s — "
                    f"proceeding with drum collection anyway"
                )
                return

    async def _stuck_drum_monitor(
        self,
        color_service: ColorDetectionService,
        drum_service: DrumMotorService,
        robot: "GenericRobot",
    ) -> None:
        """Watchdog: if a color is continuously visible for >1.5s, the drum is stuck.

        Enters safe mode: stops collecting, keeps pusher open, disables retries,
        but lets the run finish so drums can still be ejected.
        """
        STUCK_THRESHOLD = 1.5  # seconds — normal pass-through is ~400ms
        while True:
            await asyncio.sleep(0.1)
            duration = color_service.continuous_color_seconds
            if duration is not None and duration > STUCK_THRESHOLD:
                self.warn(
                    f"Drum stuck — color visible for {duration:.2f}s "
                    f"(threshold {STUCK_THRESHOLD}s) — entering safe mode"
                )
                self._emergency_reason = f"Drum stuck in camera for {duration:.1f}s"
                await self._enter_safe_mode(robot, drum_service)
                return

    async def _enter_safe_mode(self, robot: "GenericRobot", drum_service: DrumMotorService) -> None:
        """Enter safe mode: end collection, keep pusher open, disable retries.

        The run continues so drums can still be ejected. Idempotent: if safe
        mode is already active this returns immediately, so the per-emergency
        hook below fires exactly once.
        """
        if drum_service.collection_failed:
            return
        drum_service.collection_failed = True
        drum_service.stall_retries = 1  # one attempt, zero retries
        try:
            Defs.drum_pusher_servo.device.set_position(Defs.drum_pusher_servo.open.value)
            Defs.drum_pusher_servo.device.disable()
        except Exception as e:
            self.warn(f"Safe mode pusher-open/disable failed: {e}")

        # Runs on EVERY emergency trigger: kill any residual chassis velocity so
        # the robot isn't left creeping while the emergency screen is held.
        try:
            await terminate_leftover_velocity().run_step(robot)
        except Exception as e:
            self.warn(f"Safe mode velocity termination failed: {e}")

        self.warn("Safe mode active — skipping remaining collection, retries disabled")

    async def _emergency_hold(self, robot: "GenericRobot") -> None:
        """Non-fatal emergency: show the emergency screen and wait, never exit.

        The robot is autonomous and must keep its slot in the run — a process
        exit here would leave it dead on the field. So instead of killing the
        program we:
          - stop the collection-screen updater (so it doesn't fight this screen),
          - lift the collector to secure the mechanism (lift motor, NOT the
            locked big drum),
          - display the emergency screen and hold it until the run clock reaches
            EMERGENCY_RELEASE_TIME, then return.

        On return the mission sequence proceeds normally to the post-collection
        wait_for_checkpoint and the robot drives its path. The big drum stays
        locked for the rest of the run (DrumMotorService.motor_locked), so every
        later revolver command (including ejection) is a no-op.
        """
        # Stop the collection-screen updater + stuck watchdog so they don't
        # refresh the old screen underneath the emergency screen.
        for task in (getattr(self, "_ui_task", None), getattr(self, "_stuck_task", None)):
            if task is not None:
                task.cancel()

        reason = self._emergency_reason or "Drum collection emergency"
        self.error(
            f"EMERGENCY (non-fatal): {reason} — big drum locked, holding screen "
            f"until run clock {EMERGENCY_RELEASE_TIME:.0f}s, then continuing path"
        )

        # Secure the mechanism (uses the lift motor, not the locked revolver).
        try:
            await drum_lifting_up(always_motor_support=True).run_step(robot)
        except Exception as e:
            self.error(f"Emergency drum lift failed: {e}")

        screen = EmergencyScreen()
        screen.reason = reason
        await self.display(screen)

        while True:
            try:
                elapsed = robot.synchronizer.get_time()
            except (TypeError, AttributeError):
                elapsed = None
            if elapsed is None:
                # No run clock available — show briefly, then release.
                await asyncio.sleep(5.0)
                break
            if elapsed >= EMERGENCY_RELEASE_TIME:
                break
            screen.seconds_left = max(0, int(EMERGENCY_RELEASE_TIME - elapsed))
            try:
                await screen.refresh()
            except Exception:
                pass
            await asyncio.sleep(0.2)

        self.info(
            f"Emergency hold released (run clock >= {EMERGENCY_RELEASE_TIME:.0f}s) "
            f"— returning to mission sequence (post-collection checkpoint)"
        )

    async def _ui_updater(
        self,
        screen: DrumCollectionScreen,
        color_service: ColorDetectionService,
        robot: "GenericRobot",
    ) -> None:
        while True:
            screen.detected_color = color_service.peek_color
            try:
                elapsed = robot.synchronizer.get_time()
                drum_idx = screen.drum_number - 1
                next_checkpoint = START_OFFSET + drum_idx * TIME_BETWEEN_DRUMS
                remaining = next_checkpoint - elapsed
                screen.countdown = max(0.0, remaining)
                if remaining <= 0:
                    screen.countdown = 0.0
            except (TypeError, AttributeError):
                screen.countdown = 0.0
            try:
                await screen.refresh()
            except Exception:
                pass
            await asyncio.sleep(0.15)


@dsl()
def collect_drums() -> CollectDrumsStep:
    return CollectDrumsStep()
