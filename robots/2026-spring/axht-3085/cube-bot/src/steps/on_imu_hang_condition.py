import math
import time

from raccoon import *

"""
Example how to detect / grab the cube:
            arm.move_angles(0, 0, 0),
            wait_for_button(),
            Defs.arm_claw.grab(),
            arm.move_angles(90, 60, -30),
            wait_for_button(),
            mark_heading_reference(),
            Defs.arm_claw.full_open(),

            drive_backward(heading=0).until(on_imu_hang(heading_dev_deg=2.0) | after_seconds(5)),
            turn_to_heading_left(0),
"""

class OnImuHang(StopCondition):
    """Stop when the robot gets pushed off its heading — i.e. it hangs/gets stuck.

    While driving straight the heading controller keeps the robot pointed at the
    heading it started with. The instant one side catches / hangs on something,
    that side stops while the other keeps pushing, so the chassis is twisted off
    course and the controller can no longer hold it. We freeze the heading at
    ``start()`` and fire once the robot has been forced more than
    *heading_dev_deg* away from it for *confirm_samples* consecutive reads.

    Heading comes from ``robot.odometry.get_pose().heading`` — the same frame the
    motion controllers regulate on — so the deviation we see is exactly the error
    the controller is fighting.

    A short *grace_s* window at the start swallows the initial heading wobble of
    starting to drive so it doesn't false-trigger immediately.

    Args:
        imu: Unused; kept so existing call sites passing ``Defs.imu`` still work.
        heading_dev_deg: Heading deviation in degrees that counts as "hanging".
            Tune on the real robot — raise it if it stops too eagerly, lower it
            if it keeps grinding without noticing. Default 5.0.
        confirm_samples: Consecutive reads past the threshold before stopping.
            Default 2 — rejects single noisy spikes.
        grace_s: Ignore deviation during this many seconds after start.
            Default 0.25.
    """

    def __init__(
        self,
        imu=None,
        heading_dev_deg: float = 5.0,
        confirm_samples: int = 2,
        grace_s: float = 0.25,
    ) -> None:
        self._heading_dev_rad = math.radians(heading_dev_deg)
        self._confirm_samples = confirm_samples
        self._grace_s = grace_s
        self._streak = 0
        self._start_t = 0.0
        self._start_heading = 0.0

    @staticmethod
    def _heading(robot) -> float:
        return float(robot.odometry.get_pose().heading)

    def start(self, robot) -> None:
        self._streak = 0
        self._start_t = time.monotonic()
        self._start_heading = self._heading(robot)

    def check(self, robot) -> bool:
        if time.monotonic() - self._start_t < self._grace_s:
            return False
        delta = abs(self._heading(robot) - self._start_heading)
        if delta > math.pi:  # wrap to the shortest angle
            delta = 2 * math.pi - delta
        if delta >= self._heading_dev_rad:
            self._streak += 1
        else:
            self._streak = 0
        return self._streak >= self._confirm_samples
