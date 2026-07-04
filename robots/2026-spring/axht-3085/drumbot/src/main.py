from src.patches.heading_frame import apply as _apply_heading_patch
_apply_heading_patch()

import os

from raccoon.foundation import Level, set_file_level, set_global_level
from src.hardware.robot import Robot


def _configure_debug_logging() -> None:
    """Enable DEBUG/TRACE logging for diagnosis without flooding every module.

    The global runtime level defaults to INFO, which swallows the rich drum
    diagnostics — ``[MOVE-STOP] tick_error`` (commanded vs. counted ticks),
    ``[IR-EDGE] COUNTED/REJECTED`` (every stripe crossing), ``[COAST]`` and the
    coast-drift correction. Those are exactly what we need to catch a silent IR
    miscount ("moved one pocket too far" with an otherwise clean INFO log).

    Per-file filtering keeps the firehose scoped to the drum motor service.
    Controls:
      * ``DRUMBOT_DRUM_DEBUG=0``      → off (default on)
      * ``DRUMBOT_DEBUG_FILES=a.py,b.py`` → override which files get DEBUG
      * ``DRUMBOT_LOG_GLOBAL_DEBUG=1`` → set the global level to DEBUG (very verbose)
    """
    if os.getenv("DRUMBOT_LOG_GLOBAL_DEBUG") == "1":
        set_global_level(Level.debug)
        return
    if os.getenv("DRUMBOT_DRUM_DEBUG", "1") != "1":
        return
    files = os.getenv("DRUMBOT_DEBUG_FILES", "drum_motor_service.py")
    for name in (f.strip() for f in files.split(",") if f.strip()):
        set_file_level(name, Level.debug)


def main():
    _configure_debug_logging()

    robot = Robot()

    if os.getenv("DRUMBOT_FAKE_CAMERA") == "1":
        from src.service.fake_color_detection_service import install_fake_color_service
        install_fake_color_service(robot)

    robot.start()

if __name__ == "__main__":
    main()
