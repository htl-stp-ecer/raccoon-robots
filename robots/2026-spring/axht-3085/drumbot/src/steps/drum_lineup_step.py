import math
import time

from raccoon import *
from raccoon.robot.heading_reference import HeadingReferenceService

from src.hardware.defs import Defs

# When the drum misses the pipe, back off, nudge forward this far and retry.
FALLBACK_FORWARD_CM = 5.0

# Restoring the captured heading (turning back after a missed sweep) can itself
# jam: if the robot slipped, a wheel can catch on the wrong side and the turn
# can no longer complete — it would hang or settle well short of the target. In
# that case we free the chassis by backing up this far and then finish the turn.
RESTORE_STUCK_BACKUP_CM = 2.0
# A restore turn that ends this close to the captured heading counts as done. A
# turn that completes normally settles to ~2°, so this cleanly separates success
# from a jammed turn that was cancelled far from target.
RESTORE_HEADING_TOL_DEG = 1.5
# Max back-up-and-retry attempts for a jammed restore turn before giving up and
# continuing the run anyway.
RESTORE_MAX_ATTEMPTS = 3

# Max degrees the search turn is allowed to sweep before giving up.
MAX_SEARCH_TURN_DEG = 60.0

# When the drum hits the pipe the turn stops early (~35°). If it sweeps past
# this threshold it never got stopped by the pipe -> pipe missed. Keep this
# between the usual find angle and MAX_SEARCH_TURN_DEG.
PIPE_MISS_TURN_DEG = 50.0


def _heading_stuck(grace_seconds: float = 0.3, threshold_deg: float = 5.0, stuck_duration: float = 0.2):
    """Stop when heading hasn't changed beyond threshold for stuck_duration, after an initial grace period."""
    start_time = None
    last_heading = None
    last_change_time = None

    def _check(robot):
        nonlocal start_time, last_heading, last_change_time
        now = time.monotonic()
        if start_time is None:
            start_time = now
            last_heading = math.degrees(Defs.imu.get_heading())
            last_change_time = now
            return False
        if now - start_time < grace_seconds:
            last_heading = math.degrees(Defs.imu.get_heading())
            last_change_time = now
            return False
        heading = math.degrees(Defs.imu.get_heading())
        if abs(heading - last_heading) > threshold_deg:
            last_heading = heading
            last_change_time = now
        return now - last_change_time >= stuck_duration

    return custom(_check)


def _drive_to_drum_button():
    """Drive forward until drum button is pressed; retry if already pressed."""

    def _build(_):
        if Defs.drum_found_button.read():
            return seq([
                drive_backward(speed=0.2).until(on_digital(Defs.drum_found_button, pressed=False)),
                drive_backward(2, speed=0.2),
                drive_forward(speed=0.2).until(on_digital(Defs.drum_found_button) | after_cm(8)),
            ])
        else:
            return seq([
                drive_forward(speed=0.2).until(on_digital(Defs.drum_found_button) | after_cm(15)),
            ])

    return defer(_build)


def _search_turn():
    """Sweep-turn to find the pipe. Stops early when the drum hits the pipe
    (heading stuck / button pressed); otherwise runs out to the full sweep."""
    return turn_right().until(
        _heading_stuck(stuck_duration=0.2, threshold_deg=4)
        | on_digital(Defs.drum_found_button)
        | after_degrees(MAX_SEARCH_TURN_DEG)
    )


@dsl
def lineup_drum_with_pipe():
    # start_heading_deg: absolute heading (reference-relative deg) captured
    # right before each search turn, so we can rotate back to it.
    # missed: True if the last search turn swept past PIPE_MISS_TURN_DEG.
    state = {"start_heading_deg": None, "missed": False, "skipped": False}

    def _capture_start(robot):
        state["start_heading_deg"] = robot.get_service(
            HeadingReferenceService
        ).current_relative_deg()
        return run(lambda _: None)

    def _heading_error_deg(robot):
        # Signed [-180, 180] delta from the captured start heading to now.
        if state["start_heading_deg"] is None:
            return 0.0
        svc = robot.get_service(HeadingReferenceService)
        return (svc.current_relative_deg() - state["start_heading_deg"] + 180) % 360 - 180

    def _restore_heading(attempt: int = 1):
        # Turn back to the captured absolute heading. turn_to_heading_left restores
        # it regardless of the reference's positive direction.
        #
        # The turn can physically jam: if the robot slipped, a wheel can catch on
        # the wrong side and the heading turn can no longer complete, leaving the
        # robot stuck. Guard the turn with the same heading-stuck detector used for
        # the search sweep, run concurrently: the moment the robot stops rotating
        # before reaching the target, the turn is cancelled instead of hanging.
        # We then back up RESTORE_STUCK_BACKUP_CM to free the chassis and retry the
        # turn, up to RESTORE_MAX_ATTEMPTS times.
        def _build(robot):
            if state["start_heading_deg"] is None:
                return run(lambda _: None)
            # Already on target (e.g. the sweep barely moved) — nothing to restore.
            if abs(_heading_error_deg(robot)) <= RESTORE_HEADING_TOL_DEG:
                return run(lambda _: None)

            guarded_turn = do_while_active(
                reference_step=wait_for(
                    _heading_stuck(grace_seconds=0.4, threshold_deg=3, stuck_duration=0.3)
                ),
                task=turn_to_heading_left(state["start_heading_deg"]),
            )

            def _after(robot2):
                err = abs(_heading_error_deg(robot2))
                svc = robot2.get_service(HeadingReferenceService)
                if err <= RESTORE_HEADING_TOL_DEG:
                    return run(lambda _: None)  # heading restored
                if attempt >= RESTORE_MAX_ATTEMPTS:
                    svc.warn(
                        f"[lineup_drum_with_pipe] heading still {err:.0f}° off after "
                        f"{attempt} restore attempts — continuing run anyway"
                    )
                    return run(lambda _: None)
                svc.warn(
                    f"[lineup_drum_with_pipe] restore turn jammed ({err:.0f}° off "
                    f"target) — backing up {RESTORE_STUCK_BACKUP_CM:.0f}cm and "
                    f"completing the turn (attempt {attempt + 1})"
                )
                return seq([
                    drive_backward(RESTORE_STUCK_BACKUP_CM),
                    _restore_heading(attempt + 1),
                ])

            return seq([guarded_turn, defer(_after)])

        return defer(_build)

    def _evaluate_turn(robot):
        # Right after the turn we already know whether the pipe was missed: a
        # successful hit stops the turn early, a miss sweeps the full range.
        svc = robot.get_service(HeadingReferenceService)
        # Normalize to [-180, 180]: both headings are already wrapped to that
        # range, so a raw subtraction wraps around (e.g. -175° -> +163° reads
        # as 338° instead of the real 22°) and would flag a hit as a miss.
        delta = (svc.current_relative_deg() - state["start_heading_deg"] + 180) % 360 - 180
        turned = abs(delta)
        state["missed"] = turned >= PIPE_MISS_TURN_DEG
        if state["missed"]:
            svc.warn(
                f"[lineup_drum_with_pipe] pipe missed — turned {turned:.0f}° "
                f"(>= {PIPE_MISS_TURN_DEG:.0f}°)"
            )
        return run(lambda _: None)

    def _retry_if_missed(robot):
        # Hit the pipe on the first turn — nothing to do here.
        if not state["missed"]:
            return run(lambda _: None)
        # Missed: rotate back to the start heading, nudge forward and only THEN
        # sweep again.
        robot.get_service(HeadingReferenceService).warn(
            "[lineup_drum_with_pipe] restoring heading, driving forward "
            f"{FALLBACK_FORWARD_CM:.0f}cm and retrying"
        )
        return seq([
            _restore_heading(),
            drive_forward(FALLBACK_FORWARD_CM),
            defer(_capture_start),
            _search_turn(),
            defer(_evaluate_turn),
        ])

    def _skip_if_still_missed(robot):
        # First or retried turn hit the pipe — proceed normally.
        if not state["missed"]:
            return run(lambda _: None)
        # Still missed: give up on this pipe, restore heading and continue the
        # run so the second pipe can still be attempted.
        state["skipped"] = True
        robot.get_service(HeadingReferenceService).warn(
            "[lineup_drum_with_pipe] pipe still missed after retry — skipping, "
            "restoring heading and continuing run"
        )
        return _restore_heading()

    def _finish(_):
        steps = []
        # Only drive onto / against the pipe if we actually found it.
        if not state["skipped"]:
            steps += [
                wait_for_seconds(0.5),
                _drive_to_drum_button(),
                drive_backward(6.5, speed=0.2),
            ]
        # ALWAYS park the servo in the drop position — even when we skipped this
        # pipe — so downstream missions find it where they expect. This rotation
        # drops nothing because the eject mechanism is still disengaged.
        steps += [
            Defs.lift_drums_servo.eject_position(70),
            wait_for_seconds(0.5),
        ]
        return seq(steps)

    return seq([
        # drum_servo_step,
        Defs.lift_drums_servo.seek_position(),
        wait_for_seconds(0.5),
        defer(_capture_start),
        _search_turn(),
        defer(_evaluate_turn),
        defer(_retry_if_missed),
        defer(_skip_if_still_missed),
        defer(_finish),
    ])
