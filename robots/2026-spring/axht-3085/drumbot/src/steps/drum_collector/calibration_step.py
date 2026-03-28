from dataclasses import dataclass

from libstp import GenericRobot, dsl
from libstp.step.calibration import CalibrateStep

from src.service.drum_motor_service import DrumMotorService

from .screens import DrumConfirmScreen, DrumSamplingScreen


@dataclass
class DrumCalibration:
    blocked: float
    pocket: float


@dsl(hidden=True)
class DrumCollectorCalibrationStep(CalibrateStep[DrumCalibration]):
    def __init__(self, calibration_time: float = 5.0, motor_speed: float = 0.2):
        super().__init__(
            store_section="drum-collector",
            store_set="default",
        )
        self.calibration_time = calibration_time
        self.motor_speed = motor_speed

    async def _collect(self, robot: GenericRobot) -> DrumCalibration | None:
        service = robot.get_service(DrumMotorService)

        sampling_screen = DrumSamplingScreen(sensor_port=service.light_sensor.port)
        self._last_samples = await self.run_with_ui(
            sampling_screen,
            service.sample(self.calibration_time, self.motor_speed),
        )

        if len(self._last_samples) < 20:
            self.warn("Too few samples collected, retrying")
            return None

        pocket, blocked = service.cluster(self._last_samples)
        return DrumCalibration(blocked=blocked, pocket=pocket)

    async def _confirm(
        self, robot: GenericRobot, calibration: DrumCalibration,
    ) -> tuple[bool, DrumCalibration]:
        result = await self.show(DrumConfirmScreen(
            blocked_threshold=calibration.blocked,
            pocket_threshold=calibration.pocket,
            collected_values=self._last_samples,
        ))
        return result.confirmed, DrumCalibration(
            blocked=result.blocked_threshold,
            pocket=result.pocket_threshold,
        )

    def _apply(self, robot: GenericRobot, calibration: DrumCalibration) -> None:
        service = robot.get_service(DrumMotorService)
        service.apply_calibration(calibration.blocked, calibration.pocket)

    def _serialize(self, calibration: DrumCalibration) -> dict:
        return {"blocked": calibration.blocked, "pocket": calibration.pocket}

    def _deserialize(self, data: dict) -> DrumCalibration:
        return DrumCalibration(blocked=data["blocked"], pocket=data["pocket"])


@dsl()
def calibrate_drum_collector(
    calibration_time: float = 5.0,
    motor_speed: float = -0.7,
) -> DrumCollectorCalibrationStep:
    """Calibrate the drum collector by spinning the motor and sampling the light sensor."""
    return DrumCollectorCalibrationStep(
        calibration_time=calibration_time,
        motor_speed=motor_speed,
    )
