"""
Test configuration: mock libstp since it only exists on the robot.

This conftest runs before any test module imports, providing stubs
for the libstp hardware classes so service logic can be tested offline.
"""
import sys
from unittest.mock import MagicMock

# Create a mock libstp module hierarchy before any src imports
libstp_mock = MagicMock()

# Provide class stubs that can be subclassed
class _RobotService:
    def __init__(self, robot):
        self._robot = robot
    @property
    def robot(self):
        return self._robot
    def info(self, msg): pass
    def warn(self, msg): pass

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
    """Identity decorator replacing libstp.dsl for offline tests."""
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


libstp_mock.RobotService = _RobotService
libstp_mock.GenericRobot = _GenericRobot
libstp_mock.Motor = _Motor
libstp_mock.Servo = _Servo
libstp_mock.AnalogSensor = _AnalogSensor
libstp_mock.IRSensor = _IRSensor
libstp_mock.ETSensor = _ETSensor
libstp_mock.IMU = _IMU
libstp_mock.KMeans = _KMeans
libstp_mock.dsl = _dsl
libstp_mock.Step = _Step
libstp_mock.debug = lambda *a, **k: None
libstp_mock.info = lambda *a, **k: None
libstp_mock.warn = lambda *a, **k: None
libstp_mock.error = lambda *a, **k: None

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


class _LibstpUIModule(_types.ModuleType):
    """Dynamic libstp.ui stub: any attribute access returns a permissive stub class."""

    _cache: dict = {}

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        if name == "UIScreen":
            return _UIScreen
        if name not in self._cache:
            self._cache[name] = type(name, (_AnyClass,), {})
        return self._cache[name]


_libstp_ui = _LibstpUIModule("libstp.ui")
_libstp_ui.UIScreen = _UIScreen
# Pre-seed common symbols so `from libstp.ui import *` works.
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
    setattr(_libstp_ui, _sym, type(_sym, (_AnyClass,), {}))
_libstp_ui.__all__ = [a for a in dir(_libstp_ui) if not a.startswith("_")]

_libstp_ui_step = _types.ModuleType("libstp.ui.step")
_libstp_ui_step.UIStep = _Step

sys.modules["libstp"] = libstp_mock
sys.modules["libstp.sensor_et"] = MagicMock(ETSensor=_ETSensor)
sys.modules["libstp.step"] = MagicMock(Step=_Step)
sys.modules["libstp.ui"] = _libstp_ui
sys.modules["libstp.ui.step"] = _libstp_ui_step

# Pre-register an empty stub for `src.steps.drum_collector` so its heavy
# __init__.py (which pulls in UI screens requiring a full libstp.ui) is
# skipped during tests. Submodules can still be imported directly.
_stub_drum_collector = _types.ModuleType("src.steps.drum_collector")
_stub_drum_collector.__path__ = [
    str(__import__("pathlib").Path(__file__).resolve().parent.parent
        / "src" / "steps" / "drum_collector")
]
sys.modules["src.steps.drum_collector"] = _stub_drum_collector
