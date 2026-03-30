from dataclasses import dataclass

from libstp import GenericRobot, dsl
from libstp.step.calibration import CalibrateStep

from src.service.drum_motor_service import DrumMotorService, NUM_POCKETS

from .screens import DrumConfirmScreen, DrumSamplingScreen


@dataclass
class DrumCalibration:
    blocked: float
    pocket: float
    ticks_per_pocket: int | None = None


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

        # Phase 1: spin motor and collect sensor + encoder samples
        sampling_screen = DrumSamplingScreen(sensor_port=service.light_sensor.port)
        self._last_samples = await self.run_with_ui(
            sampling_screen,
            service.sample(self.calibration_time, self.motor_speed),
        )

        if len(self._last_samples) < 20:
            self.warn("Too few samples collected, retrying")
            return None

        pocket, blocked = service.cluster(self._last_samples)

        # Phase 2: verify we saw all 9 stripes and they are evenly spaced
        stripe_count, spacings, _ = service.analyse_stripe_spacing(
            self._last_samples, blocked, pocket,
        )
        if stripe_count < NUM_POCKETS:
            self.warn(
                f"Only detected {stripe_count}/{NUM_POCKETS} stripes — "
                f"need longer sampling or slower speed, retrying"
            )
            return None

        ok, dev = service.check_spacing_uniformity(spacings)
        if not ok:
            self.warn(
                f"Stripe spacing not uniform (max deviation {dev:.1%}) — "
                f"retrying"
            )
            return None

        self.info(
            f"Stripe analysis: {stripe_count} stripes, "
            f"spacing deviation {dev:.1%}, median gap {sorted(spacings)[len(spacings)//2]}"
        )

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
        samples = getattr(self, "_last_samples", None)
        service.apply_calibration(
            calibration.blocked,
            calibration.pocket,
            samples=samples,
            ticks_per_pocket=calibration.ticks_per_pocket,
        )
        # Store ticks_per_pocket back into calibration so it gets serialized
        if service._ticks_per_pocket is not None:
            calibration.ticks_per_pocket = service._ticks_per_pocket

    def _serialize(self, calibration: DrumCalibration) -> dict:
        d = {"blocked": calibration.blocked, "pocket": calibration.pocket}
        if calibration.ticks_per_pocket is not None:
            d["ticks_per_pocket"] = calibration.ticks_per_pocket
        return d

    def _deserialize(self, data: dict) -> DrumCalibration:
        return DrumCalibration(
            blocked=data["blocked"],
            pocket=data["pocket"],
            ticks_per_pocket=data.get("ticks_per_pocket"),
        )


@dsl()
def calibrate_drum_collector(
    calibration_time: float = 12.0,
    motor_speed: float = 1.0,
) -> DrumCollectorCalibrationStep:
    """Calibrate the drum collector by spinning the motor and sampling the light sensor.

    Default 12 s at 0.7 speed guarantees at least one full revolution
    so that all 9 stripes are sampled and spacing can be verified.
    """
    return DrumCollectorCalibrationStep(
        calibration_time=calibration_time,
        motor_speed=motor_speed,
    )
