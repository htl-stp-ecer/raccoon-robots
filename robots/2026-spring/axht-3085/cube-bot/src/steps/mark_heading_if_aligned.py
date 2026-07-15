"""Re-mark the heading reference only when the robot is still well aligned.

Re-marking (``HeadingReferenceService.mark()``) re-captures the current absolute
world heading as the new zero. Doing this periodically corrects accumulated
odometry drift — but ONLY makes sense when the robot is actually sitting at (or
very near) the orientation the reference already describes. If the robot has
drifted or turned far away, re-marking would zero the origin at the *wrong*
heading and corrupt every absolute turn that follows.

This step reads the current heading error relative to the existing reference and:
  - error within tolerance  -> re-mark the reference (drift correction)
  - error too great          -> leave the reference UNCHANGED (and warn)
"""

from raccoon import *
from raccoon.robot.heading_reference import HeadingReferenceService

# ---------------------------------------------------------------------------
# Tunables — edit these to control how much heading error is accepted.
# ---------------------------------------------------------------------------

# Maximum heading error (degrees, absolute) tolerated when re-marking. If the
# robot's current heading is within this many degrees of the existing reference,
# the reference is re-marked. If it is off by more than this, the reference is
# left as-is so a bad heading can't corrupt the origin.
HEADING_MARK_TOLERANCE_DEG = 3.0

def mark_heading_if_aligned():
    def _build(robot: "Robot"):
        heading_service = robot.get_service(HeadingReferenceService)
        error_deg = heading_service.current_relative_deg()

        if abs(error_deg) > HEADING_MARK_TOLERANCE_DEG:
            heading_service.warn(
                f"HEADING: Skipping heading reference mark — error {error_deg:.1f}° "
                f"exceeds tolerance {HEADING_MARK_TOLERANCE_DEG:.1f}°"
            )
            return run(lambda robot: None)
        heading_service.warn(
            f"HEADING:heading reference okay — error {error_deg:.1f}° "
        )
        return mark_heading_reference()

    return defer(_build)
