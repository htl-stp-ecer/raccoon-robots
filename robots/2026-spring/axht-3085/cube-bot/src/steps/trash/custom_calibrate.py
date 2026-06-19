"""Custom calibration step with optional distance calibration.

Wraps raccoon's built-in ``calibrate()`` but adds a ``calibrate_distance``
flag so you can run IR sensor calibration independently of the distance/motor
calibration.  This makes it safe to call twice with different calibration sets
without re-running the distance drive each time::

    # First call: distance + IR set "default"
    custom_calibrate(
        calibration_sets=["default"],
        distance_cm=70,
        calibrate_distance=True,
    )

    # ... do something here ...

    # Second call: IR set "upper" only — distance calibration is skipped
    custom_calibrate(
        calibration_sets=["upper"],
        calibrate_distance=False,
    )

Each calibration set is stored under a distinct key
(``"{set_name}_port{sensor_port}"``), so different sets never overwrite
each other.

Supports ``--no-calibrate``: loads stored values and skips all drives.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from raccoon import *
from raccoon.no_calibrate import is_no_calibrate

if TYPE_CHECKING:
    from raccoon.robot.api import GenericRobot
    from raccoon.sensor_ir import IRSensor

_SENSOR_DRIVE_CM = 50.0  # distance used for each IR sampling drive


class CustomCalibrate(UIStep):
    """Calibrate distance and/or IR sensors with full control over which sets to run.

    When ``calibrate_distance=True`` the full raccoon ``Calibrate`` flow runs
    (motor encoder measurement + IR sensor drive) exactly as before.

    When ``calibrate_distance=False`` only the IR sensor drive-and-sample phase
    runs for each requested calibration set, leaving any previously stored
    distance calibration untouched.

    Each set is stored under an independent key so calling the step twice with
    two different set names never overwrites the first result.

    Args:
        calibration_sets: Named IR surface sets to calibrate, e.g.
            ``["default"]`` or ``["default", "upper"]``. Default
            ``["default"]``.
        distance_cm: Drive distance used for the distance calibration step.
            Ignored when ``calibrate_distance=False``. Default 70.
        sensor_drive_cm: Drive distance used for each IR sensor sampling drive
            when ``calibrate_distance=False``. Default 50.
        speed: Drive speed fraction (0.0-1.0) for both drives. Default 1.0.
        calibrate_distance: Whether to run the distance (motor encoder)
            calibration. Set to ``False`` to only calibrate IR sensors.
            Default ``True``.
        ema_alpha: EMA smoothing coefficient for the distance calibration
            baseline. Ignored when ``calibrate_distance=False``. Default 0.3.
        exclude_ir_sensors: IR sensor instances to skip entirely.

    Supports ``--no-calibrate``: all drives are skipped; stored values are
    loaded from ``raccoon.calibration.yml`` / the C++ ``CalibrationStore``.

    Example::

        from src.steps.custom_calibrate import custom_calibrate

        custom_calibrate(calibration_sets=["default"], distance_cm=70)
        custom_calibrate(calibration_sets=["upper"], calibrate_distance=False)
    """

    def __init__(
        self,
        calibration_sets: list[str] | None = None,
        distance_cm: float = 70.0,
        sensor_drive_cm: float = _SENSOR_DRIVE_CM,
        speed: float = 1.0,
        calibrate_distance: bool = True,
        ema_alpha: float = 0.3,
        exclude_ir_sensors: list["IRSensor"] | None = None,
    ) -> None:
        super().__init__()
        self._calibration_sets = calibration_sets or ["default"]
        self._distance_cm = distance_cm
        self._sensor_drive_cm = sensor_drive_cm
        self._speed = speed
        self._calibrate_distance = calibrate_distance
        self._ema_alpha = ema_alpha
        self._exclude_ir_sensors: list["IRSensor"] = exclude_ir_sensors or []

    def _generate_signature(self) -> str:
        return (
            f"CustomCalibrate(sets={self._calibration_sets}, "
            f"distance={'yes' if self._calibrate_distance else 'no'}, "
            f"distance_cm={self._distance_cm:.0f})"
        )

    def required_resources(self) -> frozenset[str]:
        # Child steps (Calibrate / drive steps) acquire "drive" themselves.
        return frozenset()

    # ------------------------------------------------------------------
    # Main execute
    # ------------------------------------------------------------------

    async def _execute_step(self, robot: "GenericRobot") -> None:
        if self._calibrate_distance:
            await self._run_full_calibration(robot)
        else:
            await self._run_ir_only(robot)

    # ------------------------------------------------------------------
    # Full calibration path (distance + IR) — delegate to raccoon Calibrate
    # ------------------------------------------------------------------

    async def _run_full_calibration(self, robot: "GenericRobot") -> None:
        cal_step = Calibrate(
            distance_cm=self._distance_cm,
            speed=self._speed,
            persist_to_yaml=True,
            ema_alpha=self._ema_alpha,
            calibration_sets=self._calibration_sets,
            exclude_ir_sensors=self._exclude_ir_sensors,
        )
        await cal_step.run_step(robot)

    # ------------------------------------------------------------------
    # IR-only calibration path
    # ------------------------------------------------------------------

    async def _run_ir_only(self, robot: "GenericRobot") -> None:
        from raccoon.sensor_ir import IRSensor as _IRSensor

        ir_sensors = [
            s
            for s in robot.defs.analog_sensors
            if isinstance(s, _IRSensor) and s not in self._exclude_ir_sensors
        ]

        if not ir_sensors:
            self.warn("custom_calibrate: no IR sensors found in robot.defs.analog_sensors")
            return

        if is_no_calibrate():
            self._load_stored_ir(ir_sensors)
            return

        for set_name in self._calibration_sets:
            await self._calibrate_ir_set(robot, ir_sensors, set_name)

    def _load_stored_ir(self, ir_sensors: list) -> None:
        from raccoon import calibration_store as CalibrationStore
        from raccoon.calibration_store import CalibrationType

        for set_name in self._calibration_sets:
            for sensor in ir_sensors:
                key = f"{set_name}_port{sensor.port}"
                if CalibrationStore.has_readings(CalibrationType.IR_SENSOR, key):
                    readings = CalibrationStore.get_readings(CalibrationType.IR_SENSOR, key)
                    sensor.setCalibration(readings[1], readings[0])
                    self.info(
                        f"--no-calibrate: IR port {sensor.port} set '{set_name}': "
                        f"black={readings[1]:.0f} white={readings[0]:.0f}"
                    )
                else:
                    self.warn(
                        f"--no-calibrate: no stored data for IR port {sensor.port}"
                        f" set '{set_name}'"
                    )

    async def _calibrate_ir_set(
        self,
        robot: "GenericRobot",
        ir_sensors: list,
        set_name: str,
    ) -> None:
        label = set_name.upper()

        proceed = await self.confirm(
            f"Place sensors on {label} surface, then confirm to drive.",
            title=f"IR Calibration: {label}",
            yes_label="Drive",
            no_label="Skip",
        )
        if not proceed:
            self.debug(f"Skipping calibration set '{set_name}'")
            return

        samples = await self._drive_and_sample_ir(robot, ir_sensors)
        await self._confirm_ir_set(robot, ir_sensors, samples, set_name)

    async def _drive_and_sample_ir(
        self,
        robot: "GenericRobot",
        ir_sensors: list,
    ) -> dict[int, list[float]]:
        from raccoon.step.motion.drive import _drive_forward_uncalibrated

        samples: dict[int, list[float]] = {s.port: [] for s in ir_sensors}
        stop_event = asyncio.Event()

        async def _sample_loop() -> None:
            while not stop_event.is_set():
                for sensor in ir_sensors:
                    samples[sensor.port].append(float(sensor.read()))
                await asyncio.sleep(0.01)

        async def _do_drive() -> None:
            sample_task = asyncio.create_task(_sample_loop())
            drive_step = _drive_forward_uncalibrated(self._sensor_drive_cm, speed=self._speed)
            try:
                await drive_step.run_step(robot)
            finally:
                stop_event.set()
                await sample_task
            for motor in robot.drive.get_motors():
                motor.set_speed(0)

        await self.run_with_ui(DistanceDrivingScreen(self._sensor_drive_cm), _do_drive())
        return samples

    async def _confirm_ir_set(
        self,
        robot: "GenericRobot",
        ir_sensors: list,
        samples: dict[int, list[float]],
        set_name: str,
    ) -> None:
        from raccoon import calibration_store as CalibrationStore
        from raccoon.calibration_store import CalibrationType
        from raccoon.step.calibration.sensors.dataclasses import SensorCalibrationData
        from raccoon.step.calibration.sensors.ir_results_screen import IRResultsDashboardScreen

        current_samples = samples

        while True:
            for sensor in ir_sensors:
                values = current_samples.get(sensor.port, [])
                if values:
                    sensor.calibrate(values)

            sensor_data: list[SensorCalibrationData] = []
            for sensor in ir_sensors:
                values = [float(v) for v in current_samples.get(sensor.port, [])]
                sensor_data.append(
                    SensorCalibrationData(
                        port=sensor.port,
                        samples=values,
                        black_threshold=float(getattr(sensor, "blackThreshold", 0.0)),
                        white_threshold=float(getattr(sensor, "whiteThreshold", 0.0)),
                        black_mean=float(getattr(sensor, "blackMean", 0.0)),
                        white_mean=float(getattr(sensor, "whiteMean", 0.0)),
                        black_std=float(getattr(sensor, "blackStdDev", 0.0)),
                        white_std=float(getattr(sensor, "whiteStdDev", 0.0)),
                    )
                )

            result = await self.show(IRResultsDashboardScreen(sensors=sensor_data))

            if result is None:
                self.warn(f"IR calibration dashboard dismissed for set '{set_name}'")
                return

            if result.confirmed:
                for sensor, data in zip(ir_sensors, sensor_data, strict=False):
                    sensor.setCalibration(data.black_threshold, data.white_threshold)
                    CalibrationStore.store_readings(
                        CalibrationType.IR_SENSOR,
                        data.white_threshold,
                        data.black_threshold,
                        f"{set_name}_port{sensor.port}",
                    )
                    self.info(
                        f"IR calibration stored: port={sensor.port} set='{set_name}' "
                        f"black={data.black_threshold:.0f} white={data.white_threshold:.0f}"
                    )
                return

            # retry -> drive again
            current_samples = await self._drive_and_sample_ir(robot, ir_sensors)


def custom_calibrate(
    calibration_sets: list[str] | None = None,
    distance_cm: float = 70.0,
    sensor_drive_cm: float = _SENSOR_DRIVE_CM,
    speed: float = 1.0,
    calibrate_distance: bool = True,
    ema_alpha: float = 0.3,
    exclude_ir_sensors: list["IRSensor"] | None = None,
) -> CustomCalibrate:
    """Calibrate distance and/or IR sensors with control over which sets to run.

    Use ``calibrate_distance=False`` to skip the motor encoder drive and only
    run IR sensor calibration for the requested *calibration_sets*.  Safe to
    call multiple times with different sets -- each set is stored under a
    distinct key and never overwrites another.

    Supports ``--no-calibrate``.
    """
    return CustomCalibrate(
        calibration_sets=calibration_sets,
        distance_cm=distance_cm,
        sensor_drive_cm=sensor_drive_cm,
        speed=speed,
        calibrate_distance=calibrate_distance,
        ema_alpha=ema_alpha,
        exclude_ir_sensors=exclude_ir_sensors,
    )
