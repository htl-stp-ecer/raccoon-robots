"""Project-specific mission parameters dialled in via the setup UI.

Declared once here as typed :class:`NumberParam` descriptors; the setup
mission asks for them (``.ask(...)``) and normal mission code reads them back
(``.get()``) — always through the attribute, never a string key.

See :mod:`src.params` for the framework.
"""

from __future__ import annotations

from raccoon import NumberParam, ParamSet


class MissionParams(ParamSet):
    """Tunable values entered on the robot screen during setup."""

    first_cube_line_gap = NumberParam(
        default=26.0,
        unit="cm",
        min=20.0,
        max=35.0,
        persist=False,
    )
