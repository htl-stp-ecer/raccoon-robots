import asyncio
import os

from raccoon import GenericRobot, dsl
from raccoon.foundation import ChassisVelocity
from raccoon.step import Step

POSITION_HOLD_VX = 0.12  # m/s forward push to hold the robot against the wall
POSITION_HOLD_HZ = 50
POSITION_HOLD_ENV = "DRUMBOT_NO_POSITION_HOLD"  # set to disable the forward push


@dsl(hidden=True)
class PositionHoldStep(Step):
    """Continuously press the chassis forward against the wall.

    Runs forever — intended as the ``task`` of a ``do_while_active`` so it is
    cancelled automatically when the reference step finishes. Re-pushes the
    velocity target every cycle (the velocity controller is pure feedforward
    with ki=0, so pushing against the wall causes no integral windup). On
    cancellation it clears the chassis velocity target and brakes.
    """

    def __init__(self, vx: float = POSITION_HOLD_VX):
        super().__init__()
        self.vx = vx

    async def _execute_step(self, robot: "GenericRobot") -> None:
        if os.getenv(POSITION_HOLD_ENV) is not None:
            # Disabled via env var — return immediately. do_while_active simply
            # lets the reference step (collect_drums) run without the push.
            self.info(f"{POSITION_HOLD_ENV} set — position hold disabled")
            return

        update_rate = 1.0 / POSITION_HOLD_HZ
        vel = ChassisVelocity(self.vx, 0.0, 0.0)
        loop = asyncio.get_event_loop()
        last = loop.time()
        try:
            while True:
                now = loop.time()
                dt = now - last
                last = now
                robot.drive.set_velocity(vel)
                if dt > 0:
                    robot.drive.update(dt)
                await asyncio.sleep(update_rate)
        finally:
            self._stop_drive(robot)

    def _stop_drive(self, robot: "GenericRobot") -> None:
        """Halt the chassis, clearing the firmware velocity target.

        ``hard_stop()`` alone only sends a PASSIVE_BRAKE; it never sends a
        zero velocity, so the STM32 keeps the last commanded velocity-PID
        target. Push an explicit zero velocity first, then brake.
        """
        robot.drive.set_velocity(ChassisVelocity(0.0, 0.0, 0.0))
        robot.drive.update(1.0 / POSITION_HOLD_HZ)
        robot.drive.hard_stop()


@dsl()
def position_hold(vx: float = POSITION_HOLD_VX) -> PositionHoldStep:
    """Hold the robot pressed against the wall with a gentle forward push.

    Runs until cancelled — use as the ``task`` of ``do_while_active`` so it
    stops (and releases the chassis) when the reference step completes::

        do_while_active(reference_step=collect_drums(), task=position_hold())
    """
    return PositionHoldStep(vx=vx)
