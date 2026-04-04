from libstp import GenericRobot, Step, dsl
from libstp.step.calibration import CalibrateStep

from src.hardware.range_finder import DEFAULT_PROFILE, CalibrationProfile
from src.service.range_finder_service import RangeFinderService

from .dataclasses import ScanData
from .scan_sweep_step import scan_sweep
from .screens import RangeFinderConfirmScreen, RangeFinderScanningScreen


@dsl(hidden=True)
class RangeFinderCalibrationStep(CalibrateStep[CalibrationProfile]):
    def __init__(
        self,
        sweep_deg: float = 90.0,
        turn_speed: float = 0.2,
        profile: str = DEFAULT_PROFILE,
        setup_steps: list[Step] | None = None,
    ):
        super().__init__(
            store_section="range-finder",
            store_set=profile,
            setup_steps=setup_steps,
        )
        self.sweep_deg = sweep_deg
        self.turn_speed = turn_speed
        self.profile = profile

    async def _collect(self, robot: GenericRobot) -> CalibrationProfile | None:
        service = robot.get_service(RangeFinderService)
        range_finder = service.range_finder

        step = scan_sweep(
            sweep_deg=self.sweep_deg,
            turn_speed=self.turn_speed,
        )

        async def run_scan(s=step) -> list[tuple[float, float]]:
            await s.run_step(robot)
            return s.samples

        samples = await self.run_with_ui(
            RangeFinderScanningScreen(sensor_port=range_finder.port),
            run_scan,
        )
        if not samples:
            self.warn("Range finder scan produced no samples, retrying")
            return None

        values = [value for _, value in samples]
        peak_heading_deg, peak_value = max(samples, key=lambda s: s[1])
        self._last_scan = ScanData(
            samples=samples,
            baseline=min(values),
            peak=peak_value,
            peak_heading_deg=peak_heading_deg,
        )
        t_enter, t_exit = service.compute_thresholds(samples)
        return CalibrationProfile(t_enter=t_enter, t_exit=t_exit)

    async def _confirm(
        self, robot: GenericRobot, calibration: CalibrationProfile,
    ) -> tuple[bool, CalibrationProfile]:
        result = await self.show(
            RangeFinderConfirmScreen(
                scan=self._last_scan,
                t_enter=calibration.t_enter,
                t_exit=calibration.t_exit,
            ),
        )
        return result.confirmed, CalibrationProfile(
            t_enter=result.t_enter, t_exit=result.t_exit,
        )

    def _apply(self, robot: GenericRobot, calibration: CalibrationProfile) -> None:
        service = robot.get_service(RangeFinderService)
        service.range_finder.apply_calibration(
            calibration.t_enter, calibration.t_exit, profile=self.profile,
        )
        self.info(
            f"Range finder calibration [{self.profile}] applied: "
            f"T_enter={calibration.t_enter:.0f}, T_exit={calibration.t_exit:.0f}",
        )

    def _serialize(self, calibration: CalibrationProfile) -> dict:
        return {"t_enter": calibration.t_enter, "t_exit": calibration.t_exit}

    def _deserialize(self, data: dict) -> CalibrationProfile:
        return CalibrationProfile(t_enter=data["t_enter"], t_exit=data["t_exit"])


@dsl()
def calibrate_range_finder(
    sweep_deg: float = 90.0,
    turn_speed: float = 0.2,
    profile: str = DEFAULT_PROFILE,
    setup_steps: list[Step] | None = None,
) -> RangeFinderCalibrationStep:
    """Sweep the ET sensor, compute thresholds, and confirm them in the UI."""
    return RangeFinderCalibrationStep(
        sweep_deg=sweep_deg,
        turn_speed=turn_speed,
        profile=profile,
        setup_steps=setup_steps,
    )
