from __future__ import annotations

from typing import TYPE_CHECKING

from libstp import dsl
from libstp.ui.step import UIStep

from src.service.range_finder_service import RangeFinderService

from .dataclasses import ScanData
from .scan_sweep_step import ScanSweepStep
from .screens import RangeFinderScanningScreen, RangeFinderConfirmScreen

if TYPE_CHECKING:
    from libstp.robot.api import GenericRobot


@dsl(hidden=True)
class RangeFinderCalibrationStep(UIStep):
    def __init__(self, sweep_deg: float = 180.0, turn_speed: float = 0.5):
        super().__init__()
        self.sweep_deg = sweep_deg
        self.turn_speed = turn_speed

    def _generate_signature(self) -> str:
        return f"RangeFinderCalibrationStep(sweep_deg={self.sweep_deg:.0f}, turn_speed={self.turn_speed:.2f})"

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service = robot.get_service(RangeFinderService)
        rf = service.range_finder

        while True:
            # Phase 1: sweep via a real MotionStep
            sweep = ScanSweepStep(sweep_deg=self.sweep_deg, turn_speed=self.turn_speed)
            scanning_screen = RangeFinderScanningScreen(sensor_port=rf.port)
            await self.run_with_ui(
                scanning_screen,
                sweep._execute_step(robot),
            )
            samples = sweep.samples

            if len(samples) < 20:
                self.warn("Too few samples, retrying")
                continue

            # Phase 2: compute thresholds and build scan summary
            t_enter, t_exit = RangeFinderService.compute_thresholds(samples)
            values = [v for _, v in samples]
            peak_value = max(values)
            peak_idx = values.index(peak_value)
            scan = ScanData(
                samples=samples,
                baseline=min(values),
                peak=peak_value,
                peak_heading_deg=samples[peak_idx][0],
            )

            # Phase 3: confirm
            result = await self.show(RangeFinderConfirmScreen(
                scan=scan,
                t_enter=t_enter,
                t_exit=t_exit,
            ))

            if result.confirmed:
                rf.apply_calibration(result.t_enter, result.t_exit)
                self.info(f"Range finder calibrated: T_enter={result.t_enter:.0f}, T_exit={result.t_exit:.0f}")
                return


@dsl(tags=["calibration", "sensor"])
def calibrate_range_finder(
    sweep_deg: float = 60.0,
    turn_speed: float = 0.5,
) -> RangeFinderCalibrationStep:
    """Calibrate the ET range finder by sweeping left-to-right and sampling.

    Place the robot ~15 cm from the target. It will turn through sweep_deg
    degrees, record sensor readings, and compute T_enter / T_exit thresholds
    from the resulting spike profile. The user can adjust thresholds on the
    confirm screen before applying.

    Prerequisites:
        ET range finder must be defined in defs as ``et_range_finder``.

    Args:
        sweep_deg: Total sweep arc in degrees (default 180).
        turn_speed: Angular speed in rad/s during sweep (default 0.5).

    Returns:
        A RangeFinderCalibrationStep instance.

    Example::

        from src.steps.range_finder import calibrate_range_finder

        calibrate_range_finder(sweep_deg=120, turn_speed=0.3)
    """
    return RangeFinderCalibrationStep(
        sweep_deg=sweep_deg,
        turn_speed=turn_speed,
    )
