"""
Test configuration: mock raccoon since it only exists on the robot.

This conftest runs before any test module imports, providing stubs
for the raccoon hardware classes so service logic can be tested offline.
"""
import sys
from unittest.mock import MagicMock

# Create a mock raccoon module hierarchy before any src imports
raccoon_mock = MagicMock()

# Provide class stubs that can be subclassed
class _RobotService:
    def __init__(self, robot):
        self._robot = robot
    @property
    def robot(self):
        return self._robot
    def info(self, msg): pass
    def warn(self, msg): pass
    def error(self, msg): pass

class _GenericRobot: pass
class _Motor: pass
class _Servo: pass
class _AnalogSensor: pass
class _IRSensor(_AnalogSensor): pass
class _ETSensor: pass
class _IMU: pass
class _KMeans:
    def __init__(self, max_iterations=10):
        self.max_iterations = max_iterations
    def fit(self, data):
        result = MagicMock()
        if data:
            sorted_data = sorted(data)
            mid = len(sorted_data) // 2
            result.centroid1 = sum(sorted_data[:mid]) / max(mid, 1)
            result.centroid2 = sum(sorted_data[mid:]) / max(len(sorted_data) - mid, 1)
        else:
            result.centroid1 = 0
            result.centroid2 = 0
        return result

def _dsl(*args, **kwargs):
    """Identity decorator replacing raccoon.dsl for offline tests."""
    # Usage: @dsl  (no parens) — args == (target,)
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return args[0]
    # Usage: @dsl() or @dsl(hidden=True) — return decorator that returns target unchanged
    def _decorator(target):
        return target
    return _decorator


class _Step:
    """Minimal Step base class for offline tests."""
    def __init__(self, *args, **kwargs):
        pass
    def info(self, msg): pass
    def warn(self, msg): pass


raccoon_mock.RobotService = _RobotService
raccoon_mock.GenericRobot = _GenericRobot
raccoon_mock.Motor = _Motor
raccoon_mock.Servo = _Servo
raccoon_mock.AnalogSensor = _AnalogSensor
raccoon_mock.IRSensor = _IRSensor
raccoon_mock.ETSensor = _ETSensor
raccoon_mock.IMU = _IMU
raccoon_mock.KMeans = _KMeans
raccoon_mock.dsl = _dsl
raccoon_mock.Step = _Step
raccoon_mock.debug = lambda *a, **k: None
raccoon_mock.info = lambda *a, **k: None
raccoon_mock.warn = lambda *a, **k: None
raccoon_mock.error = lambda *a, **k: None

class _UIScreen:
    """Generic-capable UIScreen stub (supports UIScreen[T] subscript)."""
    title = ""
    def __class_getitem__(cls, item):
        return cls
    def __init__(self, *args, **kwargs):
        pass
    async def refresh(self):
        pass


class _AnyClass:
    """Catch-all class that accepts any args, is subscriptable, and is callable."""
    def __class_getitem__(cls, item):
        return cls
    def __init__(self, *args, **kwargs):
        pass
    def __call__(self, *args, **kwargs):
        return self


import types as _types


class _raccoonUIModule(_types.ModuleType):
    """Dynamic raccoon.ui stub: any attribute access returns a permissive stub class."""

    _cache: dict = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name == "UIScreen":
            return _UIScreen
        if name not in self._cache:
            self._cache[name] = type(name, (_AnyClass,), {})
        return self._cache[name]


_raccoon_ui = _raccoonUIModule("raccoon.ui")
_raccoon_ui.UIScreen = _UIScreen
# Pre-seed common symbols so `from raccoon.ui import *` works.
for _sym in ["UIScreen", "Widget", "Text", "Box", "Column", "Row", "Spacer",
             "Button", "Label", "Container", "Center", "Align", "Padding",
             "Border", "Stack", "VStack", "HStack", "Divider", "ProgressBar",
             "TextInput", "Spinner", "Image", "Icon", "ListView", "ScrollView",
             "Table", "TableRow", "TableCell", "Header", "Footer", "Menu",
             "MenuItem", "Dialog", "Modal", "Tooltip", "Tabs", "Tab",
             "Checkbox", "Radio", "Slider", "Switch", "Dropdown", "Select",
             "Grid", "GridItem", "Card", "Panel", "Section", "Field", "Form",
             "Color", "Style", "Theme", "Layout", "Screen"]:
    if _sym == "UIScreen":
        continue
    setattr(_raccoon_ui, _sym, type(_sym, (_AnyClass,), {}))
_raccoon_ui.__all__ = [a for a in dir(_raccoon_ui) if not a.startswith("_")]

_raccoon_ui_step = _types.ModuleType("raccoon.ui.step")
_raccoon_ui_step.UIStep = _Step

sys.modules["raccoon"] = raccoon_mock
sys.modules["raccoon.sensor_et"] = MagicMock(ETSensor=_ETSensor)
sys.modules["raccoon.step"] = MagicMock(Step=_Step)
sys.modules["raccoon.ui"] = _raccoon_ui
sys.modules["raccoon.ui.step"] = _raccoon_ui_step

# Pre-register an empty stub for `src.steps.drum_collector` so its heavy
# __init__.py (which pulls in UI screens requiring a full raccoon.ui) is
# skipped during tests. Submodules can still be imported directly.
_stub_drum_collector = _types.ModuleType("src.steps.drum_collector")
_stub_drum_collector.__path__ = [
    str(__import__("pathlib").Path(__file__).resolve().parent.parent
        / "src" / "steps" / "drum_collector")
]
sys.modules["src.steps.drum_collector"] = _stub_drum_collector
