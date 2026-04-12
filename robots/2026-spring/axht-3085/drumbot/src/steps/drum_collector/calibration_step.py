from dataclasses import dataclass, field

from raccoon import GenericRobot, dsl
from raccoon.no_calibrate import is_no_calibrate
from raccoon.step.base import Step
from raccoon.step.calibration import CalibrateStep

from src.service.drum_motor_service import DrumMotorService, NUM_POCKETS

from .screens import DrumConfirmScreen

DEFAULT_REVIEW_DELTA = 750.0


@dataclass
class DrumCalibration:
    blocked: float
    pocket: float
    ticks_per_pocket: int | None = None


@dataclass
class _PendingDrumCalibration:
    """Handoff payload from DrumCollectorSampleStep → DrumCollectorReviewStep."""
    calibration: DrumCalibration | None
    samples: list[float] = field(default_factory=list)
    stripe_count: int = 0
    spacing_deviation: float = 1.0
    error: str | None = None


# Module-level handoff so sample and review steps can run in different
# DSL invocations (and across a parallel() boundary) without wiring state
# through the robot.
_PENDING: _PendingDrumCalibration | None = None


def _analyse(service: DrumMotorService, samples: list[float]) -> _PendingDrumCalibration:
    if len(samples) < 20:
        return _PendingDrumCalibration(None, samples, 0, 1.0, "too few samples")

    pocket, blocked = service.cluster(samples)
    stripe_count, spacings, _ = service.analyse_stripe_spacing(samples, blocked, pocket)

    if stripe_count < NUM_POCKETS:
        return _PendingDrumCalibration(
            DrumCalibration(blocked=blocked, pocket=pocket),
            samples, stripe_count, 1.0,
            f"only {stripe_count}/{NUM_POCKETS} stripes detected",
        )

    ok, dev = service.check_spacing_uniformity(spacings)
    if not ok:
        return _PendingDrumCalibration(
            DrumCalibration(blocked=blocked, pocket=pocket),
            samples, stripe_count, dev,
            f"stripe spacing not uniform (deviation {dev:.1%})",
        )

    return _PendingDrumCalibration(
        DrumCalibration(blocked=blocked, pocket=pocket),
        samples, stripe_count, dev, None,
    )


class DrumCollectorSampleStep(Step):
    """Headless drum collector sampling — spins motor and collects light-sensor
    readings with zero UI. Designed to run in ``parallel()`` with
    ``calibrate_colors()``.

    Result is stashed for a downstream ``review_drum_collector()`` step.
    """

    def __init__(self, calibration_time: float = 5.0, motor_speed: float = 0.2):
        super().__init__()
        self.calibration_time = calibration_time
        self.motor_speed = motor_speed

    async def _execute_step(self, robot: GenericRobot) -> None:
        global _PENDING
        if is_no_calibrate():
            _PENDING = None
            return

        service = robot.get_service(DrumMotorService)
        samples = await service.sample(self.calibration_time, self.motor_speed)
        _PENDING = _analyse(service, samples)

        cal = _PENDING.calibration
        if cal is None:
            self.warn(f"Headless drum sampling failed: {_PENDING.error}")
        else:
            delta = abs(cal.blocked - cal.pocket)
            msg = (
                f"Headless drum sampling: blocked={cal.blocked:.0f} "
                f"pocket={cal.pocket:.0f} delta={delta:.0f} "
                f"stripes={_PENDING.stripe_count} dev={_PENDING.spacing_deviation:.1%}"
            )
            if _PENDING.error:
                self.warn(msg + f" — {_PENDING.error} (will be reviewed)")
            else:
                self.info(msg)


class DrumCollectorReviewStep(CalibrateStep[DrumCalibration]):
    """Apply drum calibration. Auto-confirms when the pending result is clean
    and ``|blocked - pocket| >= review_delta``. Otherwise shows the existing
    ``DrumConfirmScreen`` for manual review.

    If no pending result is present (e.g. run standalone), falls back to
    sampling in-place — behaves like the legacy single-step flow.
    """

    def __init__(
        self,
        review_delta: float = DEFAULT_REVIEW_DELTA,
        calibration_time: float = 5.0,
        motor_speed: float = 0.2,
    ):
        super().__init__(
            store_section="drum-collector",
            store_set="default",
        )
        self.review_delta = review_delta
        self.calibration_time = calibration_time
        self.motor_speed = motor_speed
        self._pending_error: str | None = None
        self._last_samples: list[float] = []

    async def _collect(self, robot: GenericRobot) -> DrumCalibration | None:
        global _PENDING
        service = robot.get_service(DrumMotorService)

        if _PENDING is not None:
            pending = _PENDING
            _PENDING = None  # consume once
            self._last_samples = pending.samples
            self._pending_error = pending.error
            if pending.calibration is None:
                self.warn(f"Sample step failed ({pending.error}) — resampling")
                return await self._fresh_sample(service)
            return pending.calibration

        return await self._fresh_sample(service)

    async def _fresh_sample(self, service: DrumMotorService) -> DrumCalibration | None:
        samples = await service.sample(self.calibration_time, self.motor_speed)
        result = _analyse(service, samples)
        self._last_samples = result.samples
        self._pending_error = result.error
        if result.calibration is None:
            self.warn(f"Resampling failed: {result.error} — retrying")
            return None
        return result.calibration

    async def _confirm(
        self, robot: GenericRobot, calibration: DrumCalibration,
    ) -> tuple[bool, DrumCalibration]:
        delta = abs(calibration.blocked - calibration.pocket)
        if self._pending_error is None and delta >= self.review_delta:
            self.info(
                f"Auto-confirmed drum calibration: blocked={calibration.blocked:.0f} "
                f"pocket={calibration.pocket:.0f} delta={delta:.0f} "
                f">= review_delta={self.review_delta:.0f}"
            )
            return True, calibration

        reason = self._pending_error or (
            f"delta {delta:.0f} < review_delta {self.review_delta:.0f}"
        )
        self.warn(f"Drum calibration needs review: {reason}")

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
        samples = self._last_samples or None
        service.apply_calibration(
            calibration.blocked,
            calibration.pocket,
            samples=samples,
            ticks_per_pocket=calibration.ticks_per_pocket,
        )
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
def sample_drum_collector(
    calibration_time: float = 5.0,
    motor_speed: float = 0.2,
) -> DrumCollectorSampleStep:
    """Headless drum collector sampling — no UI. Run in ``parallel()`` with
    ``calibrate_colors()`` so the motor spins while the human clicks through
    color calibration. Pair with ``review_drum_collector()`` afterwards.
    """
    return DrumCollectorSampleStep(
        calibration_time=calibration_time,
        motor_speed=motor_speed,
    )


@dsl()
def review_drum_collector(
    review_delta: float = DEFAULT_REVIEW_DELTA,
    calibration_time: float = 5.0,
    motor_speed: float = 0.2,
) -> DrumCollectorReviewStep:
    """Apply the pending drum calibration from ``sample_drum_collector()``.

    Silent when ``|blocked - pocket| >= review_delta`` and stripe checks
    passed. Shows ``DrumConfirmScreen`` only when the result is questionable
    or needs a human.
    """
    return DrumCollectorReviewStep(
        review_delta=review_delta,
        calibration_time=calibration_time,
        motor_speed=motor_speed,
    )


@dsl()
def calibrate_drum_collector(
    calibration_time: float = 5.0,
    motor_speed: float = 0.2,
    review_delta: float = DEFAULT_REVIEW_DELTA,
) -> DrumCollectorReviewStep:
    """Single-step drum collector calibration (legacy). Samples and reviews
    in one shot; auto-confirms when ``|blocked - pocket| >= review_delta``.
    Prefer ``sample_drum_collector()`` + ``review_drum_collector()`` when you
    want sampling to overlap with another UI step.
    """
    return DrumCollectorReviewStep(
        review_delta=review_delta,
        calibration_time=calibration_time,
        motor_speed=motor_speed,
    )
