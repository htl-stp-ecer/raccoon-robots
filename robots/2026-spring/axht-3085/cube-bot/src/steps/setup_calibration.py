from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from raccoon import Step
from raccoon.no_calibrate import is_no_calibrate
from raccoon.step.calibration.sensors.dataclasses import SensorCalibrationData
from raccoon.step.calibration.sensors.ir_results_screen import IRResultsDashboardScreen
from raccoon.step.motion._motion_trim import MotionTrimService
from raccoon.step.motion.drive import _drive_forward_uncalibrated
from raccoon.ui.screens.distance import DistanceDrivingScreen, DistanceMeasureScreen
from raccoon.ui.step import UIStep

from src.service.setup_calibration import CalibrationAxis, DriveCalibrationSample, SetupCalibrationSession

if TYPE_CHECKING:
    from raccoon.robot.api import GenericRobot
    from raccoon.sensor_ir import IRSensor


_IR_MIN_SAMPLES = 20
_FALLBACK_FORWARD_CM = 70.0
_FALLBACK_LATERAL_CM = 50.0
_FALLBACK_IR_DRIVE_CM = 50.0
_FALLBACK_SPEED = 0.4
# Below this, a "ground truth" board reading is treated as a board failure
# (the robot clearly drove, so a ~0cm reference means the board did not track)
# and we fall back to manual measurement instead of recording a bogus sample.
_MIN_GROUND_TRUTH_M = 0.02


def _axis_name(axis: CalibrationAxis) -> str:
    return axis.value


def _axis_abs_cm(value_m: float) -> float:
    return abs(float(value_m)) * 100.0


def _collectable_ir_sensors(
    robot: "GenericRobot",
    sensors: list["IRSensor"] | None,
) -> list["IRSensor"]:
    if sensors is not None:
        return list(sensors)
    from raccoon.sensor_ir import IRSensor as _IRSensor

    return [s for s in robot.defs.analog_sensors if isinstance(s, _IRSensor)]


async def _sample_ir_while_running(
    robot: "GenericRobot",
    step,
    sensors: list["IRSensor"],
) -> dict[int, list[float]]:
    samples: dict[int, list[float]] = {sensor.port: [] for sensor in sensors}
    stop_event = asyncio.Event()

    async def _sample_loop() -> None:
        while not stop_event.is_set():
            for sensor in sensors:
                samples[sensor.port].append(float(sensor.read()))
            await asyncio.sleep(0.01)

    sample_task = asyncio.create_task(_sample_loop())
    try:
        await step.run_step(robot)
    finally:
        stop_event.set()
        await sample_task
    return samples


class CollectDrive(UIStep):
    def __init__(self, step) -> None:
        super().__init__()
        self._step = step

    def _generate_signature(self) -> str:
        return f"CollectDrive(step={self._step})"

    async def _execute_step(self, robot: "GenericRobot") -> None:
        if is_no_calibrate():
            await self._step.run_step(robot)
            return

        session = robot.get_service(SetupCalibrationSession)
        session.ensure_board_probe(robot, self)

        internal_start = session.capture_internal_snapshot(robot)
        reference_start = session.capture_reference_snapshot(robot) if session.board_available else None

        await self._step.run_step(robot)

        internal_end = robot.odometry.get_internal_pose()
        # The driven axis is inferred from the dominant internal-odometry
        # displacement, so callers don't have to declare it up front.
        axis = session.detect_axis(internal_start, internal_end)
        session.require_axis(axis)
        odom_distance_m = session.axis_distance_m(internal_start, internal_end, axis)

        if session.board_available and reference_start is not None:
            reference_end = session.reference_pose(robot)
            ground_truth_m = session.axis_distance_m(reference_start, reference_end, axis)
            if abs(ground_truth_m) >= _MIN_GROUND_TRUTH_M:
                session.add_drive_sample(
                    DriveCalibrationSample(
                        axis=axis,
                        odom_distance_m=odom_distance_m,
                        ground_truth_distance_m=ground_truth_m,
                        source="calibration_board",
                    )
                )
                self.info(
                    f"Collected {_axis_name(axis)} drive sample: "
                    f"odom={_axis_abs_cm(odom_distance_m):.1f}cm "
                    f"ground_truth={_axis_abs_cm(ground_truth_m):.1f}cm"
                )
                return
            self.warn(
                f"Calibration board reported ~0cm ground truth for a "
                f"{_axis_abs_cm(odom_distance_m):.1f}cm {_axis_name(axis)} drive; "
                f"falling back to manual measurement"
            )

        measured_cm = await self.show(
            DistanceMeasureScreen(
                requested_distance=_axis_abs_cm(odom_distance_m),
                default_value=_axis_abs_cm(odom_distance_m),
            )
        )
        sign = 1.0 if odom_distance_m >= 0.0 else -1.0
        ground_truth_m = sign * (float(measured_cm) / 100.0)
        session.add_drive_sample(
            DriveCalibrationSample(
                axis=axis,
                odom_distance_m=odom_distance_m,
                ground_truth_distance_m=ground_truth_m,
                source="manual_entry",
            )
        )
        self.info(
            f"Collected manual {_axis_name(axis)} sample: "
            f"odom={_axis_abs_cm(odom_distance_m):.1f}cm measured={float(measured_cm):.1f}cm"
        )


class CollectIrSet(Step):
    def __init__(self, step, set_name: str, sensors: list["IRSensor"] | None = None) -> None:
        super().__init__()
        self._step = step
        self._set_name = set_name
        self._sensors = sensors

    def _generate_signature(self) -> str:
        return f"CollectIrSet(set={self._set_name!r}, step={self._step})"

    async def _execute_step(self, robot: "GenericRobot") -> None:
        session = robot.get_service(SetupCalibrationSession)
        session.require_ir_set(self._set_name)
        sensors = _collectable_ir_sensors(robot, self._sensors)
        if not sensors or is_no_calibrate():
            await self._step.run_step(robot)
            return
        samples = await _sample_ir_while_running(robot, self._step, sensors)
        session.add_ir_samples(self._set_name, [s.port for s in sensors], samples)
        self.info(
            f"Collected IR set '{self._set_name}' from {len(sensors)} sensor(s) during setup motion"
        )


class CalibrationGate(UIStep):
    def __init__(
        self,
        require_axes: list[CalibrationAxis] | None = None,
        require_ir_sets: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._require_axes = require_axes
        self._require_ir_sets = require_ir_sets

    def _generate_signature(self) -> str:
        return (
            f"CalibrationGate(axes={self._require_axes or []}, "
            f"ir_sets={self._require_ir_sets or []})"
        )

    async def _execute_step(self, robot: "GenericRobot") -> None:
        if is_no_calibrate():
            return

        session = robot.get_service(SetupCalibrationSession)
        if session.gate_completed:
            return
        axes = session.axes_to_finalize(self._require_axes)
        ir_sets = session.ir_sets_to_finalize(self._require_ir_sets)

        if not axes and not ir_sets:
            session.finish_gate()
            return

        if axes:
            session.ensure_board_probe(robot, self)
            await self._finalize_drive_axes(robot, session, axes)

        for set_name in ir_sets:
            await self._finalize_ir_set(robot, session, set_name)

        session.finish_gate()

    async def _finalize_drive_axes(
        self,
        robot: "GenericRobot",
        session: SetupCalibrationSession,
        axes: list[CalibrationAxis],
    ) -> None:
        trim_svc = robot.get_service(MotionTrimService)
        for axis in axes:
            if not session.get_drive_samples(axis):
                await self._run_drive_fallback(robot, session, axis)
            scale = session.median_axis_scale(axis)
            trim_svc.set_axis_scale(_axis_name(axis), scale)
            self.info(
                f"Applied {_axis_name(axis)} trim scale {scale:.5f} "
                f"from {len(session.get_drive_samples(axis))} sample(s)"
            )

    async def _run_drive_fallback(
        self,
        robot: "GenericRobot",
        session: SetupCalibrationSession,
        axis: CalibrationAxis,
    ) -> None:
        if axis == CalibrationAxis.FORWARD:
            from raccoon import drive_forward

            step = drive_forward(_FALLBACK_FORWARD_CM, speed=_FALLBACK_SPEED, heading=0)
            target_cm = _FALLBACK_FORWARD_CM
        else:
            from raccoon import strafe_right

            step = strafe_right(_FALLBACK_LATERAL_CM, speed=_FALLBACK_SPEED, heading=0)
            target_cm = _FALLBACK_LATERAL_CM

        await self.run_with_ui(
            DistanceDrivingScreen(target_cm),
            self._collect_fallback_drive(robot, session, step, axis),
        )

    async def _collect_fallback_drive(
        self,
        robot: "GenericRobot",
        session: SetupCalibrationSession,
        step,
        axis: CalibrationAxis,
    ) -> None:
        internal_start = session.capture_internal_snapshot(robot)
        reference_start = session.capture_reference_snapshot(robot) if session.board_available else None
        await step.run_step(robot)
        internal_end = robot.odometry.get_internal_pose()
        odom_distance_m = session.axis_distance_m(internal_start, internal_end, axis)

        ground_truth_m = None
        if session.board_available and reference_start is not None:
            reference_end = session.reference_pose(robot)
            board_m = session.axis_distance_m(reference_start, reference_end, axis)
            if abs(board_m) >= _MIN_GROUND_TRUTH_M:
                ground_truth_m = board_m
            else:
                self.warn(
                    f"Calibration board reported ~0cm ground truth for a "
                    f"{_axis_abs_cm(odom_distance_m):.1f}cm {_axis_name(axis)} drive; "
                    f"falling back to manual measurement"
                )

        if ground_truth_m is not None:
            source = "calibration_board"
        else:
            measured_cm = await self.show(
                DistanceMeasureScreen(
                    requested_distance=_axis_abs_cm(odom_distance_m),
                    default_value=_axis_abs_cm(odom_distance_m),
                )
            )
            sign = 1.0 if odom_distance_m >= 0.0 else -1.0
            ground_truth_m = sign * (float(measured_cm) / 100.0)
            source = "manual_entry"
        session.add_drive_sample(
            DriveCalibrationSample(
                axis=axis,
                odom_distance_m=odom_distance_m,
                ground_truth_distance_m=ground_truth_m,
                source=source,
            )
        )

    async def _finalize_ir_set(
        self,
        robot: "GenericRobot",
        session: SetupCalibrationSession,
        set_name: str,
    ) -> None:
        ir_set = session.get_ir_set(set_name)
        sensors = _collectable_ir_sensors(robot, None)
        if not sensors:
            self.warn(f"No IR sensors available for setup calibration set '{set_name}'")
            return
        if not ir_set.has_minimum_samples(_IR_MIN_SAMPLES):
            await self._run_ir_fallback(robot, session, set_name, sensors)
            ir_set = session.get_ir_set(set_name)
        await self._confirm_ir_set(robot, set_name, sensors, ir_set.samples_by_port)

    async def _run_ir_fallback(
        self,
        robot: "GenericRobot",
        session: SetupCalibrationSession,
        set_name: str,
        sensors: list["IRSensor"],
    ) -> None:
        proceed = await self.confirm(
            f"Place sensors on {set_name.upper()} surface, then confirm to drive.",
            title=f"IR Calibration: {set_name.upper()}",
            yes_label="Drive",
            no_label="Skip",
        )
        if not proceed:
            self.warn(f"Skipping fallback IR calibration for set '{set_name}'")
            return

        samples: dict[int, list[float]] = {sensor.port: [] for sensor in sensors}
        stop_event = asyncio.Event()

        async def _sample_loop() -> None:
            while not stop_event.is_set():
                for sensor in sensors:
                    samples[sensor.port].append(float(sensor.read()))
                await asyncio.sleep(0.01)

        async def _drive() -> None:
            sample_task = asyncio.create_task(_sample_loop())
            try:
                await _drive_forward_uncalibrated(_FALLBACK_IR_DRIVE_CM, speed=_FALLBACK_SPEED).run_step(
                    robot
                )
            finally:
                stop_event.set()
                await sample_task
            for motor in robot.drive.get_motors():
                motor.set_speed(0)

        await self.run_with_ui(DistanceDrivingScreen(_FALLBACK_IR_DRIVE_CM), _drive())
        session.add_ir_samples(set_name, [sensor.port for sensor in sensors], samples)

    async def _confirm_ir_set(
        self,
        robot: "GenericRobot",
        set_name: str,
        sensors: list["IRSensor"],
        samples_by_port: dict[int, list[float]],
    ) -> None:
        from raccoon import calibration_store as CalibrationStore
        from raccoon.calibration_store import CalibrationType

        current_samples = {port: list(values) for port, values in samples_by_port.items()}
        while True:
            sensor_data: list[SensorCalibrationData] = []
            for sensor in sensors:
                values = [float(v) for v in current_samples.get(sensor.port, [])]
                if values:
                    sensor.calibrate(values)
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
                for sensor, data in zip(sensors, sensor_data, strict=False):
                    sensor.setCalibration(data.black_threshold, data.white_threshold)
                    CalibrationStore.store_readings(
                        CalibrationType.IR_SENSOR,
                        data.white_threshold,
                        data.black_threshold,
                        f"{set_name}_port{sensor.port}",
                    )
                self.info(f"Applied IR calibration set '{set_name}'")
                return

            await self._run_ir_fallback(robot, robot.get_service(SetupCalibrationSession), set_name, sensors)
            current_samples = robot.get_service(SetupCalibrationSession).get_ir_set(set_name).samples_by_port


def collect_drive(step) -> CollectDrive:
    return CollectDrive(step)


def collect_ir_set(
    step,
    set_name: str,
    sensors: list["IRSensor"] | None = None,
) -> CollectIrSet:
    return CollectIrSet(step, set_name=set_name, sensors=sensors)


def calibration_gate(
    require_axes: list[CalibrationAxis] | None = None,
    require_ir_sets: list[str] | None = None,
) -> CalibrationGate:
    return CalibrationGate(require_axes=require_axes, require_ir_sets=require_ir_sets)


__all__ = [
    "CalibrationAxis",
    "CalibrationGate",
    "CollectDrive",
    "CollectIrSet",
    "calibration_gate",
    "collect_drive",
    "collect_ir_set",
]
