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


# Edge-detection tunables (see _analyze_flank / on_analog_flank).
_FLANK_TRIGGER_FRAC = 2.0 / 3.0  # Live flank must reach this fraction of the
#                                  calibrated edge amplitude before it fires.
_NOISE_BAND_FRAC = 0.10  # Samples within this fraction of the baseline define the
#                          "off" cluster whose wobble is the noise floor.
_DEFAULT_CONFIRM_SAMPLES = 2  # Consecutive confirming reads before stopping.


def _analyze_flank(
    samples: list[float],
    trigger_frac: float = _FLANK_TRIGGER_FRAC,
    noise_band_frac: float = _NOISE_BAND_FRAC,
) -> dict | None:
    """Characterise the edge in a calibration sample run, on **raw** samples.

    Returns ``None`` for a flat / too-short run, in which case calibration falls
    back to the legacy midpoint threshold.

    Worked in *signal space* ``sig = sign * value`` where ``sign`` is the edge
    direction (later-half mean vs earlier-half mean), so ``flank_threshold`` /
    ``amplitude`` / ``noise`` are sign-independent magnitudes that serve both a
    rising and a falling live flank. The noise floor is the wobble of the
    *baseline cluster* — samples within ``noise_band_frac`` of the off-state
    extremum — kept around as a diagnostic for the confirm screen.

    No smoothing: the live detector compares raw reads against a running valley,
    so the calibration statistics are derived the same way for consistency.

    * ``baseline``        — off-state level (raw units), diagnostic only.
    * ``amplitude``       — full size of the edge seen during calibration.
    * ``noise``           — baseline-cluster wobble, diagnostic only.
    * ``flank_threshold`` — ``trigger_frac*amplitude``: how far a live reading
                             must lift off its local baseline to fire. Default
                             fires once the live flank reaches 2/3 of the edge
                             seen during calibration.
    * ``trigger_level``   — ``flank_threshold`` expressed as an absolute raw
                             reading (``baseline + edge_sign*flank_threshold``),
                             for plotting alongside the raw samples.
    * ``edge_sign``       — +1 if the edge rose over the run, -1 if it fell.
    """
    n = len(samples)
    if n < 5:
        return None
    half = n // 2
    first_mean = sum(samples[:half]) / half
    second_mean = sum(samples[half:]) / (n - half)
    sign = 1.0 if second_mean >= first_mean else -1.0

    sig = [sign * v for v in samples]
    sig_min = min(sig)  # off-state extremum (baseline)
    amplitude = max(sig) - sig_min
    if amplitude <= 0.0:
        return None

    band = sig_min + noise_band_frac * amplitude
    noise = max((s - sig_min for s in sig if s <= band), default=0.0)
    noise = max(0.0, min(noise, amplitude))

    flank_threshold = trigger_frac * amplitude
    baseline = sign * sig_min
    return {
        "edge_sign": sign,
        "baseline": baseline,
        "amplitude": amplitude,
        "noise": noise,
        "flank_threshold": flank_threshold,
        "trigger_level": baseline + sign * flank_threshold,
    }


def _flank_decision(
    current: float,
    extremum: float,
    flank_threshold: float,
    rising: bool,
) -> tuple[float, bool]:
    """One live edge-mode step. Returns ``(updated_extremum, is_candidate)``.

    Pure so the trigger logic can be replay-tested off-robot. ``extremum`` is the
    running local baseline: the valley for a rising flank, the peak for falling.
    Fires once the live flank (``drawup``) reaches ``flank_threshold`` — by
    default 2/3 of the edge amplitude seen during calibration.
    """
    if rising:
        extremum = min(extremum, current)
        drawup = current - extremum
    else:
        extremum = max(extremum, current)
        drawup = extremum - current
    return extremum, drawup >= flank_threshold


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
        samples: list[float],
        analysis: dict | None = None,
    ) -> None:
        super().__init__()
        self.port = port
        self.set_name = set_name
        self.threshold = threshold
        self.filtered_min = filtered_min
        self.filtered_max = filtered_max
        self.sample_count = sample_count
        self.samples = samples
        self.analysis = analysis

    @property
    def _range(self) -> float:
        return self.filtered_max - self.filtered_min

    @property
    def _is_good(self) -> bool:
        if self._range < 100:
            return False
        # Edge calibration is only trustworthy when the real edge stands clearly
        # above the pre-edge noise floor.
        if self.analysis is not None:
            return self.analysis["amplitude"] >= 3.0 * max(self.analysis["noise"], 1.0)
        return True

    def build(self) -> Widget:
        icon = "check" if self._is_good else "warning"
        color = "green" if self._is_good else "orange"
        status = "Good separation" if self._is_good else "Low range — consider retrying"

        rows = [
            ("Min", f"{self.filtered_min:.0f}", "blue"),
            ("Max", f"{self.filtered_max:.0f}", "blue"),
            ("Threshold", f"{self.threshold:.0f}", "cyan"),
            (
                "Range",
                f"{self._range:.0f}",
                "green" if self._is_good else "orange",
            ),
        ]
        if self.analysis is not None:
            a = self.analysis
            rows += [
                ("Edge amplitude", f"{a['amplitude']:.0f}", "blue"),
                ("Pre-edge noise", f"{a['noise']:.0f}", "blue"),
                ("Flank threshold", f"{a['flank_threshold']:.0f}", "cyan"),
            ]
        rows.append(("Samples", str(self.sample_count), None))

        chart_thresholds = [
            (self.filtered_min, "Min", "blue"),
            (self.filtered_max, "Max", "blue"),
            (self.threshold, "Midpoint", "grey"),
        ]
        if self.analysis is not None:
            chart_thresholds.append((self.analysis["trigger_level"], "Flank Threshold", "cyan"))

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
                        CalibrationChart(
                            samples=self.samples,
                            thresholds=chart_thresholds,
                            height=180,
                        )
                    ]
                ),
                Spacer(16),
                Card(children=[ResultsTable(rows=rows)]),
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
            # Phase 0: wait for the operator to position the robot and confirm
            set_label = f" [{self._set_name}]" if self._set_name != "default" else ""
            await self.show(
                WaitForButtonScreen(
                    f"Position the robot for port {self._sensor.port}{set_label}, "
                    "then press the button to start calibration."
                )
            )

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
                # Trim percentile_margin from each tail; clamp so a small n never
                # produces lo_idx > hi_idx (degenerate single-sample case).
                lo_idx = min(n - 1, int(n * self._percentile_margin))
                hi_idx = max(lo_idx, min(n - 1, n - 1 - int(n * self._percentile_margin)))
                filtered_min = sorted_samples[lo_idx]
                filtered_max = sorted_samples[hi_idx]
            else:
                filtered_min = filtered_max = 0.0

            threshold = (filtered_min + filtered_max) / 2.0
            # Edge characterisation drives the earlier, glitch-resistant trigger
            # in on_analog_flank. None on a flat/too-short run -> legacy fallback.
            analysis = _analyze_flank(samples) if n > 0 else None

            # Phase 2: confirm screen — operator can accept or retry
            result = await self.show(
                AnalogDriveConfirmScreen(
                    port=self._sensor.port,
                    set_name=self._set_name,
                    threshold=threshold,
                    filtered_min=filtered_min,
                    filtered_max=filtered_max,
                    sample_count=n,
                    samples=samples,
                    analysis=analysis,
                )
            )

            if result is not None and result.confirmed:
                store = CalibrationStore()
                key = _analog_store_key(self._sensor, self._set_name)
                data = {
                    "threshold": threshold,
                    "min_observed": filtered_min,
                    "max_observed": filtered_max,
                    "sample_count": n,
                }
                if analysis is not None:
                    # Additive keys — old loaders ignore them, on_analog_flank
                    # uses them for edge mode.
                    data.update(
                        {
                            "flank_threshold": analysis["flank_threshold"],
                            "baseline": analysis["baseline"],
                            "amplitude": analysis["amplitude"],
                            "noise": analysis["noise"],
                            "edge_sign": analysis["edge_sign"],
                        }
                    )
                store.store(ANALOG_DRIVE_THRESHOLD_SECTION, data, key)
                margin_txt = (
                    f" flank_threshold={analysis['flank_threshold']:.0f}"
                    f" amplitude={analysis['amplitude']:.0f}"
                    f" noise={analysis['noise']:.0f}"
                    if analysis is not None
                    else " (legacy midpoint only)"
                )
                self.info(
                    f"Analog calibration done: port={self._sensor.port} set={self._set_name!r} "
                    f"min={filtered_min:.0f} max={filtered_max:.0f} "
                    f"threshold={threshold:.0f} (n={n}){margin_txt}"
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
    """Trigger on the first rising or falling flank of an analog sensor.

    Direction is decided automatically at :meth:`start` time from the initial
    reading vs the calibrated midpoint: below it -> wait for a *rising* flank,
    above it -> wait for a *falling* flank.

    **Edge mode (preferred).** When the calibration carries edge metrics
    (``flank_threshold``, produced by the current :func:`calibrate_analog_drive`),
    the condition tracks the *live local baseline* — the running valley for a
    rising flank, the running peak for a falling one — and fires as soon as the
    reading's lift-off from that baseline reaches ``flank_threshold``, which is
    2/3 of the edge amplitude seen during calibration. The live baseline makes
    it robust to slow lighting/surface drift.

    **Legacy mode (fallback).** When only an old midpoint ``threshold`` is
    stored, it falls back to the original crossing test.

    Both modes require the crossing to hold for ``confirm_samples`` consecutive
    reads, so a single noisy spike can no longer stop the robot early.

    Requires a prior run of :func:`calibrate_analog_drive` for the same sensor
    port and *set_name*.

    Args:
        sensor: The AnalogSensor to monitor.
        set_name: Calibration set to use. Must match the name used during
            calibration. Default ``"default"``.
        confirm_samples: Consecutive confirming reads required before triggering.
            Default 2. ``1`` restores the old single-sample behaviour.

    Raises:
        RuntimeError: At ``start()`` time if no calibration data is found.

    Example::

        from src.steps.calibrate_analog_drive import on_analog_flank

        drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor))
        drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor) | after_seconds(10))
        drive_forward(speed=0.3).until(on_analog_flank(defs.et_sensor, set_name="cal1"))
    """

    def __init__(
        self,
        sensor: "AnalogSensor",
        set_name: str = "default",
        confirm_samples: int = _DEFAULT_CONFIRM_SAMPLES,
    ) -> None:
        if not hasattr(sensor, "read"):
            msg = f"Expected an AnalogSensor with read(), got {type(sensor).__name__}"
            raise TypeError(msg)
        if confirm_samples < 1:
            msg = f"confirm_samples must be >= 1, got {confirm_samples}"
            raise ValueError(msg)
        self._sensor = sensor
        self._set_name = set_name
        self._confirm_samples = confirm_samples
        self._threshold: float = 0.0
        self._rising: bool = True
        # Edge mode state
        self._flank_threshold: float | None = None
        self._extremum: float = 0.0  # live local baseline (valley/peak)
        self._streak: int = 0

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
        self._streak = 0
        self._extremum = initial
        margin = data.get("flank_threshold")
        self._flank_threshold = float(margin) if margin is not None else None

    def check(self, robot: "GenericRobot") -> bool:
        current = float(self._sensor.read())

        if self._flank_threshold is not None:
            # Edge mode: trigger on lift-off from the live local baseline.
            self._extremum, candidate = _flank_decision(
                current, self._extremum, self._flank_threshold, self._rising
            )
        elif self._rising:
            candidate = current >= self._threshold
        else:
            candidate = current <= self._threshold

        self._streak = self._streak + 1 if candidate else 0
        return self._streak >= self._confirm_samples
