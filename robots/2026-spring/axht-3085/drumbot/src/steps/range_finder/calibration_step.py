from libstp import GenericRobot, dsl
from libstp.ui.step import UIStep

from src.hardware.range_finder import DEFAULT_PROFILE
from src.service.range_finder_service import RangeFinderService

from .dataclasses import ScanData
from .scan_sweep_step import scan_sweep
from .screens import RangeFinderConfirmScreen, RangeFinderScanningScreen


@dsl(hidden=True)
class RangeFinderCalibrationStep(UIStep):
    def __init__(
        self,
        sweep_deg: float = 90.0,
        turn_speed: float = 0.2,
        profile: str = DEFAULT_PROFILE,
    ):
        super().__init__()
        self.sweep_deg = sweep_deg
        self.turn_speed = turn_speed
        self.profile = profile

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service = robot.get_service(RangeFinderService)
        range_finder = service.range_finder

        while True:
            scan_step = scan_sweep(
                sweep_deg=self.sweep_deg,
                turn_speed=self.turn_speed,
            )

            async def run_scan(step=scan_step) -> list[tuple[float, float]]:
                await step.run_step(robot)
                return step.samples

            samples = await self.run_with_ui(
                RangeFinderScanningScreen(sensor_port=range_finder.port),
                run_scan,
            )
            if not samples:
                self.warn("Range finder scan produced no samples, retrying")
                continue

            values = [value for _, value in samples]
            peak_heading_deg, peak_value = max(samples, key=lambda sample: sample[1])
            scan = ScanData(
                samples=samples,
                baseline=min(values),
                peak=peak_value,
                peak_heading_deg=peak_heading_deg,
            )
            t_enter, t_exit = service.compute_thresholds(samples)

            result = await self.show(
                RangeFinderConfirmScreen(
                    scan=scan,
                    t_enter=t_enter,
                    t_exit=t_exit,
                ),
            )

            if result.confirmed:
                range_finder.apply_calibration(
                    result.t_enter, result.t_exit, profile=self.profile,
                )
                service.info(
                    f"Range finder calibration [{self.profile}] applied: "
                    f"T_enter={result.t_enter:.0f}, T_exit={result.t_exit:.0f}",
                )
                return


@dsl()
def calibrate_range_finder(
    sweep_deg: float = 90.0,
    turn_speed: float = 0.2,
    profile: str = DEFAULT_PROFILE,
) -> RangeFinderCalibrationStep:
    """Sweep the ET sensor, compute thresholds, and confirm them in the UI."""
    return RangeFinderCalibrationStep(
        sweep_deg=sweep_deg,
        turn_speed=turn_speed,
        profile=profile,
    )
