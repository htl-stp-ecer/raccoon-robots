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

libstp_mock.RobotService = _RobotService
libstp_mock.GenericRobot = _GenericRobot
libstp_mock.Motor = _Motor
libstp_mock.Servo = _Servo
libstp_mock.AnalogSensor = _AnalogSensor
libstp_mock.IRSensor = _IRSensor
libstp_mock.ETSensor = _ETSensor
libstp_mock.IMU = _IMU
libstp_mock.KMeans = _KMeans

sys.modules["libstp"] = libstp_mock
sys.modules["libstp.sensor_et"] = MagicMock(ETSensor=_ETSensor)
