"""Hotfix: HeadingReferenceService muss Odometry statt Localization lesen.

Grund: turn_to_heading rechnete das Turn-Delta im Localization-Frame, während
die C++ TurnMotion auf Odometry regelt -> Endheading um den loc/odom-Offset
daneben. Strafe war nicht betroffen. Fix in raccoon-lib bereits gemacht; dieser
Monkeypatch zieht ihn vor dem nächsten Lib-Deploy.
"""

import raccoon.robot.heading_reference as _hr


def _world_heading_odom_first(robot) -> float:
    odom = getattr(robot, "odometry", None)
    if odom is None:
        msg = (
            "HeadingReferenceService requires robot.odometry or robot.localization "
            "(at least one heading source must be enabled)."
        )
        raise RuntimeError(msg)
    return float(odom.get_pose().heading)


def apply() -> None:
    _hr._world_heading = _world_heading_odom_first