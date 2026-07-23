"""Extra UI widgets not (yet) in the shared library."""

from dataclasses import dataclass
from typing import Optional

from raccoon.ui.widgets import Widget


@dataclass
class CamFeed(Widget):
    """Live camera feed from raccoon/cam/frame channel.

    Renders inline in a dynamic UI screen. When tappable=True, tapping
    the image sends an on_change event with {'x': float, 'y': float}
    (normalized 0-1 coordinates) to the widget id.
    """
    id: Optional[str] = None
    show_fps: bool = False
    show_detections: bool = True
    tappable: bool = False
