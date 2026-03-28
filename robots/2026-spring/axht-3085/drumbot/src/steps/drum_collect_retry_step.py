import asyncio

from libstp import GenericRobot, dsl
from libstp.step import Step

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService

TURN_TIMEOUT = 2.0        # max seconds to wait for one pocket retreat
RETRY_BACK_SPEED = 50     # motor speed % when backing up during retry
RETRY_BACK_DURATION = 0.15
RETRY_SERVO_OPEN = 90     # partial open during retry wiggle
RETRY_SERVO_SETTLE = 0.2  # seconds to let servo reach position
SAFETY_MARGIN = 1.0       # seconds to keep free before next drum window


@dsl(hidden=True)
class DrumMotorTurnWithRetryStep(Step):
    """Retreat one pocket + apply offset, with retry logic if the motor gets stuck.

    On each attempt:
      1. retreat(1) via the drum-motor service (light-sensor feedback, with timeout)
      2. apply the velocity offset for offset_time seconds
    If the retreat times out (motor stuck):
      - back up motor slightly
      - open pusher servo partially, then close again
      - try again
    Retries continue until the time budget is exhausted.
    On total failure: passive-brake the motor, open the servo,
    and set collection_failed so all subsequent collection blocks are skipped.
    """

    def __init__(self, time_budget: float, offset_velocity: int, offset_time: float):
        super().__init__()
        self.time_budget = time_budget
        self.offset_velocity = offset_velocity
        self.offset_time = offset_time

    async def _execute_step(self, robot: "GenericRobot") -> None:
        service = robot.get_service(DrumMotorService)
        motor = service.motor
        pusher = Defs.drum_pusher_servo

        if service.collection_failed:
            self.warn("Skipping motor turn — system is in safe mode")
            return

        loop = asyncio.get_event_loop()
        deadline = loop.time() + self.time_budget - SAFETY_MARGIN

        success = False
        attempt = 0

        while loop.time() < deadline:
            attempt += 1
            try:
                await asyncio.wait_for(service.retreat(1), timeout=TURN_TIMEOUT)

                # retreat succeeded — apply the fine-tuning offset
                speed_pct = int(self.offset_velocity / 10)  # -830 → -83
                motor.set_speed(speed_pct)
                await asyncio.sleep(self.offset_time)
                motor.set_speed(0)
                motor.brake()

                success = True
                self.info(f"Motor turn succeeded on attempt {attempt}")
                break

            except TimeoutError:
                # motor didn't complete the pocket transition in time
                motor.set_speed(0)
                motor.brake()
                self.warn(f"Motor stuck on attempt {attempt}")

                if loop.time() >= deadline:
                    break

                # --- retry sequence ---
                # 1. back up motor slightly (opposite of retreat direction)
                motor.set_speed(RETRY_BACK_SPEED)
                await asyncio.sleep(RETRY_BACK_DURATION)
                motor.set_speed(0)
                motor.brake()

                # 2. open servo partially to release pressure
                pusher.set_position(RETRY_SERVO_OPEN)
                await asyncio.sleep(RETRY_SERVO_SETTLE)

                # 3. push back in
                pusher.set_position(30)
                await asyncio.sleep(RETRY_SERVO_SETTLE)

        if not success:
            self.warn("CRITICAL: Motor turn failed — entering safe mode. "
                      "No further collect motions will be attempted.")
            motor.set_speed(0)
            motor.brake()              # passive brake
            pusher.set_position(170)   # open servo
            service.collection_failed = True


@dsl()
def drum_motor_turn_with_retry(
    time_budget: float,
    offset_velocity: int = -830,
    offset_time: float = 0.3,
) -> DrumMotorTurnWithRetryStep:
    return DrumMotorTurnWithRetryStep(
        time_budget=time_budget,
        offset_velocity=offset_velocity,
        offset_time=offset_time,
    )
