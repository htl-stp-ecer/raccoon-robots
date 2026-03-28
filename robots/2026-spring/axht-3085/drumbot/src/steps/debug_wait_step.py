from libstp import GenericRobot, UIStep, dsl


@dsl(hidden=True)
class DebugWaitStep(UIStep):
    """Display a message on screen and wait for button press."""

    def __init__(self, message: str):
        super().__init__()
        self._message = message

    async def _execute_step(self, robot: "GenericRobot") -> None:
        await self.wait_for_button(self._message)


@dsl()
def debug_wait(message: str) -> DebugWaitStep:
    """Show message on screen and wait for button press."""
    return DebugWaitStep(message=message)
