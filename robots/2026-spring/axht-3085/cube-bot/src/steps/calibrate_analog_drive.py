"""Analog sensor drive-through calibration step and flank stop condition.

The robot drives forward (or backward) for a fixed duration while sampling
any analog sensor.  It passes over an optical obstacle whose reflection
changes the sensor reading.  After the drive the operator sees the captured
min/max/threshold and can confirm or retry.

Multiple named calibration sets are supported via *set_name*, so the same
sensor can hold independent thresholds for different field positions::

    calibrate_analog_drive(defs.et_sensor, set_name="cal1")
    calibrate_analog_drive(defs.et_sensor, set_name="cal2")

    drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor, set_name="cal1"))
    drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor, set_name="cal2"))

Supports ``--no-calibrate``: when the flag is active and a stored threshold
already exists for the requested set, the drive is skipped entirely and the
persisted value is used as-is.  If no stored data exists the drive runs
normally and stores a new value.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from raccoon import *
from raccoon.no_calibrate import is_no_calibrate
from raccoon.step.calibration.store import CalibrationStore
from raccoon.step.condition import StopCondition

if TYPE_CHECKING:
    from raccoon.hal import AnalogSensor
    from raccoon.robot.api import GenericRobot

ANALOG_DRIVE_THRESHOLD_SECTION = "analog-drive-threshold"


def _analog_store_key(sensor: "AnalogSensor", set_name: str) -> str:
    return f"port{sensor.port}_{set_name}"


# ---------------------------------------------------------------------------
# UI screens
# ---------------------------------------------------------------------------


@dataclass
class AnalogDriveConfirmResult:
    """Result from AnalogDriveConfirmScreen."""

    confirmed: bool


class AnalogDriveSamplingScreen(UIScreen[None]):
    """Shown while the robot drives and samples the analog sensor."""

    title = "Analog Drive Calibration"

    def __init__(
        self,
        port: int,
        set_name: str,
        drive_duration_s: float,
        speed: float,
    ) -> None:
        super().__init__()
        self.port = port
        self.set_name = set_name
        self.drive_duration_s = drive_duration_s
        self.speed = speed

    def build(self) -> Widget:
        direction = "forward" if self.speed > 0 else "backward"
        set_label = f"  [{self.set_name}]" if self.set_name != "default" else ""
        return Center(
            children=[
                Icon("sensors", size=48, color="cyan"),
                Spacer(16),
                Text(f"Sensor Port {self.port}{set_label}", size="title", bold=True),
                Spacer(24),
                Row(
                    children=[
                        ProgressSpinner(size=28),
                        Spacer(12),
                        Text("Sampling…", size="large"),
                    ],
                    align="center",
                ),
                Spacer(16),
                Text(
                    f"Driving {direction} at {abs(self.speed):.0%}"
                    f" for {self.drive_duration_s:.1f} s",
                    muted=True,
                    align="center",
                ),
                Spacer(32),
                HintBox("Do not touch the robot", icon="pan_tool"),
            ]
        )


class AnalogDriveConfirmScreen(UIScreen[AnalogDriveConfirmResult]):
    """Show calibration results — operator can confirm or request a retry."""

    title = "Analog Drive Calibration"
    _primary_button_id = "confirm"

    def __init__(
        self,
        port: int,
        set_name: str,
        threshold: float,
        filtered_min: float,
        filtered_max: float,
        sample_count: int,
    ) -> None:
        super().__init__()
        self.port = port
        self.set_name = set_name
        self.threshold = threshold
        self.filtered_min = filtered_min
        self.filtered_max = filtered_max
        self.sample_count = sample_count

    @property
    def _range(self) -> float:
        return self.filtered_max - self.filtered_min

    @property
    def _is_good(self) -> bool:
        return self._range >= 100

    def build(self) -> Widget:
        icon = "check" if self._is_good else "warning"
        color = "green" if self._is_good else "orange"
        status = "Good separation" if self._is_good else "Low range — consider retrying"

        return Split(
            left=[
                Row(
                    children=[
                        StatusIcon(icon=icon, color=color),
                        Spacer(12),
                        Column(
                            children=[
                                Text(f"Port {self.port}", size="title", bold=True),
                                Text(f"Set: {self.set_name}", size="small", muted=True),
                            ],
                            spacing=4,
                        ),
                    ],
                    align="center",
                ),
                Spacer(16),
                Text(status, size="medium", color=color),
                Spacer(24),
                Card(
                    children=[
                        ResultsTable(
                            rows=[
                                ("Min", f"{self.filtered_min:.0f}", "blue"),
                                ("Max", f"{self.filtered_max:.0f}", "blue"),
                                ("Threshold", f"{self.threshold:.0f}", "cyan"),
                                (
                                    "Range",
                                    f"{self._range:.0f}",
                                    "green" if self._is_good else "orange",
                                ),
                                ("Samples", str(self.sample_count), None),
                            ]
                        ),
                    ]
                ),
            ],
            right=[
                Column(
                    children=[
                        Button(
                            "confirm",
                            "Confirm",
                            style="success" if self._is_good else "warning",
                            icon="check",
                        ),
                        Button("retry", "Retry", style="secondary", icon="refresh"),
                    ],
                    spacing=16,
                ),
            ],
            ratio=(5, 4),
        )

    @on_click("confirm")
    async def on_confirm(self) -> None:
        self.close(AnalogDriveConfirmResult(confirmed=True))

    @on_click("retry")
    async def on_retry(self) -> None:
        self.close(AnalogDriveConfirmResult(confirmed=False))


# ---------------------------------------------------------------------------
# Calibration step
# ---------------------------------------------------------------------------


@dsl_step(tags=["calibration", "sensor"])
class CalibrateAnalogDrive(UIStep):
    """Drive while sampling an analog sensor to auto-calibrate a flank threshold.

    The robot drives for *drive_duration_s* seconds at *speed* (positive =
    forward, negative = backward).  While moving it samples the analog sensor
    at ~100 Hz.  After the drive the operator sees the captured min, max and
    computed midpoint threshold on a confirm screen and can either accept the
    result or retry the drive.

    The result is persisted to ``racoon.calibration.yml`` under the
    ``analog-drive-threshold`` section and consumed at runtime by
    :class:`on_analog_flank`.

    Args:
        sensor: The AnalogSensor to calibrate.
        drive_duration_s: How long to drive in seconds. Default 3.0.
        speed: Drive speed fraction. Positive = forward, negative = backward.
            Must be in (-1.0, 0) or (0.0, 1.0]. Default 0.25.
        set_name: Identifier for this calibration point. Use different names
            for independent thresholds on the same sensor port, e.g.
            ``"cal1"`` and ``"cal2"``. Default ``"default"``.
        percentile_margin: Fraction of readings to discard from each tail
            before computing min/max. Default 0.05 (5 %).

    Supports ``--no-calibrate``: if stored data exists the drive and UI are
    skipped entirely.  Warns and runs normally when no data is found.

    Example::

        from src.steps.calibrate_analog_drive import calibrate_analog_drive

        calibrate_analog_drive(defs.et_sensor, drive_duration_s=2.0, speed=-0.3, set_name="cal1")
        calibrate_analog_drive(defs.et_sensor, drive_duration_s=2.0, speed=-0.3, set_name="cal2")
    """

    def __init__(
        self,
        sensor: "AnalogSensor",
        drive_duration_s: float = 3.0,
        speed: float = 0.25,
        set_name: str = "default",
        percentile_margin: float = 0.05,
    ) -> None:
        super().__init__()
        if speed == 0.0 or abs(speed) > 1.0:
            msg = f"speed must be in (-1.0, 0) or (0.0, 1.0], got {speed}"
            raise ValueError(msg)
        if drive_duration_s <= 0.0:
            msg = f"drive_duration_s must be > 0, got {drive_duration_s}"
            raise ValueError(msg)
        if not (0.0 <= percentile_margin < 0.5):
            msg = f"percentile_margin must be in [0.0, 0.5), got {percentile_margin}"
            raise ValueError(msg)
        self._sensor = sensor
        self._drive_duration_s = drive_duration_s
        self._speed = speed
        self._set_name = set_name
        self._percentile_margin = percentile_margin

    def _generate_signature(self) -> str:
        return (
            f"CalibrateAnalogDrive(port={self._sensor.port}, "
            f"set={self._set_name!r}, duration={self._drive_duration_s:.1f}s, "
            f"speed={self._speed:.2f})"
        )

    def required_resources(self) -> frozenset[str]:
        return frozenset()

    async def _drive_and_sample(self, robot: "GenericRobot") -> list[float]:
        samples: list[float] = []
        running = True

        async def _sample_loop() -> None:
            while running:
                samples.append(float(self._sensor.read()))
                await asyncio.sleep(0.01)

        sample_task = asyncio.create_task(_sample_loop())
        abs_speed = abs(self._speed)
        if self._speed > 0:
            drive_step = drive_forward(speed=abs_speed, until=after_seconds(self._drive_duration_s))
        else:
            drive_step = drive_backward(speed=abs_speed, until=after_seconds(self._drive_duration_s))

        try:
            await drive_step._execute_step(robot)
        finally:
            running = False
            await sample_task

        return samples

    async def _execute_step(self, robot: "GenericRobot") -> None:
        if is_no_calibrate():
            store = CalibrationStore()
            key = _analog_store_key(self._sensor, self._set_name)
            data = store.load(ANALOG_DRIVE_THRESHOLD_SECTION, key)
            if data is not None:
                self.info(
                    f"--no-calibrate: loaded stored analog threshold "
                    f"port={self._sensor.port} set={self._set_name!r} "
                    f"threshold={float(data['threshold']):.0f}"
                )
                return
            self.warn(
                f"--no-calibrate but no stored data for "
                f"analog sensor port {self._sensor.port} set '{self._set_name}'"
                " — running calibration"
            )

        while True:
            # Phase 1: drive + sample; sampling screen is shown while driving
            samples: list[float] = await self.run_with_ui(
                AnalogDriveSamplingScreen(
                    port=self._sensor.port,
                    set_name=self._set_name,
                    drive_duration_s=self._drive_duration_s,
                    speed=self._speed,
                ),
                self._drive_and_sample(robot),
            )

            n = len(samples)
            self.debug(f"Collected {n} samples from port {self._sensor.port}")

            if n > 0:
                sorted_samples = sorted(samples)
                lo_idx = max(0, int(n * self._percentile_margin))
                hi_idx = min(n - 1, int(n * (1.0 - self._percentile_margin)))
                filtered_min = sorted_samples[lo_idx]
                filtered_max = sorted_samples[hi_idx]
            else:
                filtered_min = filtered_max = 0.0

            threshold = (filtered_min + filtered_max) / 2.0

            # Phase 2: confirm screen — operator can accept or retry
            result = await self.show(
                AnalogDriveConfirmScreen(
                    port=self._sensor.port,
                    set_name=self._set_name,
                    threshold=threshold,
                    filtered_min=filtered_min,
                    filtered_max=filtered_max,
                    sample_count=n,
                )
            )

            if result is not None and result.confirmed:
                store = CalibrationStore()
                key = _analog_store_key(self._sensor, self._set_name)
                store.store(
                    ANALOG_DRIVE_THRESHOLD_SECTION,
                    {
                        "threshold": threshold,
                        "min_observed": filtered_min,
                        "max_observed": filtered_max,
                        "sample_count": n,
                    },
                    key,
                )
                self.info(
                    f"Analog calibration done: port={self._sensor.port} set={self._set_name!r} "
                    f"min={filtered_min:.0f} max={filtered_max:.0f} "
                    f"threshold={threshold:.0f} (n={n})"
                )
                return
            # confirmed=False → retry, loop back to drive


def calibrate_analog_drive(
    sensor: "AnalogSensor",
    drive_duration_s: float = 3.0,
    speed: float = 0.25,
    set_name: str = "default",
    percentile_margin: float = 0.05,
) -> CalibrateAnalogDrive:
    """Drive while sampling an analog sensor to auto-calibrate a flank threshold.

    Skipped under ``--no-calibrate`` when stored data for *set_name* exists.
    Use distinct *set_name* strings (e.g. ``"cal1"``, ``"cal2"``) to maintain
    independent thresholds for different field positions on the same sensor port.
    Negative *speed* drives backward.
    """
    return CalibrateAnalogDrive(
        sensor=sensor,
        drive_duration_s=drive_duration_s,
        speed=speed,
        set_name=set_name,
        percentile_margin=percentile_margin,
    )


# ---------------------------------------------------------------------------
# Flank stop condition
# ---------------------------------------------------------------------------


class on_analog_flank(StopCondition):
    """Trigger on the first rising or falling flank of an analog sensor using a calibrated threshold.

    The direction is determined automatically at :meth:`start` time: if the
    initial sensor reading is below the calibrated threshold the condition
    waits for a *rising* flank (reading crosses above threshold); if the
    initial reading is already above the threshold it waits for a *falling*
    flank (reading drops below threshold).

    Requires a prior run of :func:`calibrate_analog_drive` for the same
    sensor port and *set_name*.

    Args:
        sensor: The AnalogSensor to monitor.
        set_name: Calibration set to use. Must match the name used during
            calibration. Default ``"default"``.

    Raises:
        RuntimeError: At ``start()`` time if no calibration data is found.

    Example::

        from src.steps.calibrate_analog_drive import on_analog_flank

        drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor))
        drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor) | after_seconds(10))
        drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor, set_name="cal1"))
    """

    def __init__(self, sensor: "AnalogSensor", set_name: str = "default") -> None:
        if not hasattr(sensor, "read"):
            msg = f"Expected an AnalogSensor with read(), got {type(sensor).__name__}"
            raise TypeError(msg)
        self._sensor = sensor
        self._set_name = set_name
        self._threshold: float = 0.0
        self._rising: bool = True

    def start(self, robot: "GenericRobot") -> None:
        store = CalibrationStore()
        key = _analog_store_key(self._sensor, self._set_name)
        data = store.load(ANALOG_DRIVE_THRESHOLD_SECTION, key)
        if data is None:
            msg = (
                f"on_analog_flank: no calibration found for port {self._sensor.port} "
                f"set '{self._set_name}'. Run calibrate_analog_drive() first."
            )
            raise RuntimeError(msg)

        self._threshold = float(data["threshold"])
        initial = float(self._sensor.read())
        self._rising = initial < self._threshold

    def check(self, robot: "GenericRobot") -> bool:
        current = float(self._sensor.read())
        if self._rising:
            return current >= self._threshold
        return current <= self._threshold
