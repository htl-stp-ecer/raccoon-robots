from __future__ import annotations
import math
from raccoon import servo, slow_servo, parallel, StepBuilder
from src.hardware.defs import Defs

# ── Link lengths — mirror of config/servos.yml arm_geometry (all in cm) ──────
UPPER_ARM_CM:       float = 12.5   # shoulder → elbow
FOREARM_CM:         float = 24   # elbow → claw tip
SHOULDER_HEIGHT_CM: float = 13.3   # base pivot → shoulder joint


# ── Interpolation helper ──────────────────────────────────────────────────────

def _interp(
    points: list[tuple[float, float]],  # [(angle_deg, servo_val), ...] ascending
    angle_deg: float,
    min_sv: float,
    max_sv: float,
) -> float:
    """
    Linear interpolation between calibration points.
    Outside the calibration range the outermost segment's slope is extrapolated,
    then the result is clamped to the hardware limit [min_sv, max_sv].
    This avoids snapping to a calibration-boundary value (e.g. exactly 0° or 90°)
    when the IK requires an angle that lies beyond the calibrated span.
    """
    if angle_deg <= points[0][0]:
        a0, v0 = points[0]
        a1, v1 = points[1]
        sv = v0 + (v1 - v0) / (a1 - a0) * (angle_deg - a0)
    elif angle_deg >= points[-1][0]:
        a0, v0 = points[-2]
        a1, v1 = points[-1]
        sv = v1 + (v1 - v0) / (a1 - a0) * (angle_deg - a1)
    else:
        sv = points[0][1]
        for i in range(len(points) - 1):
            a0, v0 = points[i]
            a1, v1 = points[i + 1]
            if a0 <= angle_deg <= a1:
                t = (angle_deg - a0) / (a1 - a0)
                sv = v0 + t * (v1 - v0)
                break
    return max(min_sv, min(max_sv, sv))


# ── Calibration tables — read from auto-generated Defs so servos.yml is canonical

def _base_cal() -> list[tuple[float, float]]:
    return [
        (-90, Defs.arm_base.m90deg.value),
        (  0, Defs.arm_base._0deg.value),
        ( 90, Defs.arm_base.p90deg.value),
    ]


def _sholder_cal() -> list[tuple[float, float]]:
    return [
        (  0, Defs.arm_sholder._0deg.value),
        ( 90, Defs.arm_sholder.p90deg.value),
    ]


def _elbow_cal() -> list[tuple[float, float]]:
    return [
        (-90, Defs.arm_elbow.m90deg.value),
        (  0, Defs.arm_elbow._0deg.value),
        ( 90, Defs.arm_elbow.p90deg.value),
    ]


# ── Kinematics ────────────────────────────────────────────────────────────────

class ArmKinematics:
    """
    Forward and inverse kinematics for the ClawBot arm.

    Coordinate system (origin = base pivot):
      X = forward (arm faces X at base_deg=0)
      Y = left
      Z = up

    All positions in centimetres, all angles in degrees.

    Joint sign convention:
      base_deg   : 0 = forward, + = left (CCW)
      sholder_deg: 0 = horizontal, + = up
      elbow_deg  : 0 = straight, + = forearm bends up (p), − = bends down (m)
    """

    def __init__(
        self,
        l1: float = UPPER_ARM_CM,
        l2: float = FOREARM_CM,
        z0: float = SHOULDER_HEIGHT_CM,
    ) -> None:
        self.l1 = l1   # upper arm length (cm)
        self.l2 = l2   # forearm length (cm)
        self.z0 = z0   # shoulder height above base pivot (cm)

    # ── Forward kinematics ────────────────────────────────────────────────────

    def forward(
        self,
        base_deg: float,
        sholder_deg: float,
        elbow_deg: float,
    ) -> tuple[float, float, float]:
        """Joint angles (degrees) → claw tip (x, y, z) in centimetres."""
        t0 = math.radians(base_deg)
        t1 = math.radians(sholder_deg)
        t2 = math.radians(elbow_deg)
        r = self.l1 * math.cos(t1) + self.l2 * math.cos(t1 + t2)
        z = self.l1 * math.sin(t1) + self.l2 * math.sin(t1 + t2) + self.z0
        return r * math.cos(t0), r * math.sin(t0), z

    # ── Inverse kinematics ────────────────────────────────────────────────────

    def inverse(
        self,
        x: float,
        y: float,
        z: float,
    ) -> list[tuple[float, float, float]]:
        """
        Cartesian target in centimetres → [(base°, sholder°, elbow°), ...].
        Returns up to 2 solutions (elbow-up / elbow-down).
        Raises ValueError when the target is unreachable.
        """
        t0 = math.atan2(y, x)
        r  = math.hypot(x, y)
        zs = z - self.z0                          # height relative to shoulder

        d2     = r ** 2 + zs ** 2
        cos_t2 = (d2 - self.l1 ** 2 - self.l2 ** 2) / (2 * self.l1 * self.l2)

        if abs(cos_t2) > 1.0:
            raise ValueError(f"Target ({x:.1f}, {y:.1f}, {z:.1f}) cm is out of reach")

        solutions: list[tuple[float, float, float]] = []
        for sign in (1, -1):                       # elbow-up (+) then elbow-down (−)
            sin_t2 = sign * math.sqrt(max(0.0, 1.0 - cos_t2 ** 2))
            t2 = math.atan2(sin_t2, cos_t2)
            t1 = math.atan2(zs, r) - math.atan2(
                self.l2 * sin_t2, self.l1 + self.l2 * cos_t2
            )
            solutions.append((math.degrees(t0), math.degrees(t1), math.degrees(t2)))
        return solutions

    # ── Shortest-path selection ───────────────────────────────────────────────

    def shortest_path(
        self,
        x: float,
        y: float,
        z: float,
        current: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ) -> tuple[float, float, float]:
        """Pick the IK solution minimising total joint travel from `current`."""
        return min(
            self.inverse(x, y, z),
            key=lambda s: sum(abs(s[i] - current[i]) for i in range(3)),
        )

    # ── Angle → servo value ───────────────────────────────────────────────────

    def to_servo_values(
        self,
        base_deg: float,
        sholder_deg: float,
        elbow_deg: float,
    ) -> tuple[float, float, float]:
        """Map physical joint angles (degrees) to raw servo position values."""
        bv = _interp(
            _base_cal(), base_deg,
            Defs.arm_base.max_left.value,
            Defs.arm_base.max_right.value,
        )
        sv = _interp(
            _sholder_cal(), sholder_deg,
            Defs.arm_sholder.max_up.value,
            Defs.arm_sholder.max_down.value,
        )
        ev = _interp(
            _elbow_cal(), elbow_deg,
            Defs.arm_elbow.max_minus.value,
            Defs.arm_elbow.max_max.value,
        )
        return bv, sv, ev

    # ── High-level move builder ───────────────────────────────────────────────

    def move_to(
        self,
        x: float,
        y: float,
        z: float,
        current: tuple[float, float, float] = (0.0, 0.0, 0.0),
        speed: float | None = None,
    ) -> "MoveBuilder":
        """
        Start building a move step to (x, y, z) centimetres.

        Use directly as a raccoon step for pure shortest-path motion, or chain
        .upper_arm() / .forearm() to express angle preferences first:

            arm.move_to(20, 0, 15)
            arm.move_to(20, 0, 15).upper_arm(45, precision=0.8)
            arm.move_to(20, 0, 15).forearm(10, precision=0.6)
            arm.move_to(20, 0, 15, speed=30).upper_arm(45, precision=1.0)
        """
        return MoveBuilder(self, x, y, z, current, speed)

    def move_angles(
        self,
        base_deg: float,
        sholder_deg: float,
        elbow_deg: float,
        speed: float | None = None,
    ):
        """
        Return a raccoon step that drives the arm to the given joint angles directly,
        bypassing IK.  Useful for testing or for moves where the angles are already known.

        Args:
            base_deg   : base rotation (0 = forward, + = left)
            sholder_deg: shoulder elevation (0 = horizontal, + = up)
            elbow_deg  : elbow bend (0 = straight, + = up, − = down)
            speed      : °/s for all joints; None = max hardware speed
        """
        bv, sv, ev = self.to_servo_values(base_deg, sholder_deg, elbow_deg)
        print(f"[arm] move_angles({base_deg}, {sholder_deg}, {elbow_deg}) → base={bv:.1f}, shoulder={sv:.1f}, elbow={ev:.1f}")
        if speed is None:
            return parallel(
                servo(Defs.arm_base,    bv),
                servo(Defs.arm_sholder, sv),
                servo(Defs.arm_elbow,   ev),
            )
        return parallel(
            slow_servo(Defs.arm_base,    bv, speed),
            slow_servo(Defs.arm_sholder, sv, speed),
            slow_servo(Defs.arm_elbow,   ev, speed),
        )


# ── Move builder ──────────────────────────────────────────────────────────────

class MoveBuilder(StepBuilder):
    """
    Fluent builder for a single arm move step.

    Extends StepBuilder so it passes raccoon's isinstance check and integrates
    with seq() / parallel() like any other step.  Chain .upper_arm() and/or
    .forearm() BEFORE placing the builder in a sequence — StepBuilder calls
    _build() once at resolve() time (sequence construction), not at execution.

    precision=1.0 → angle dominates; 0.0 → joint-travel dominates.
    """

    def __init__(
        self,
        kin: ArmKinematics,
        x: float,
        y: float,
        z: float,
        current: tuple[float, float, float],
        speed: float | None,
    ) -> None:
        super().__init__()
        self._kin     = kin
        self._x       = x
        self._y       = y
        self._z       = z
        self._current = current
        self._speed   = speed
        self._base_deg:        float | None = None
        self._base_precision:  float        = 0.5
        self._upper_arm_deg:   float | None = None
        self._upper_precision: float        = 0.5
        self._forearm_deg:     float | None = None
        self._lower_precision: float        = 0.5

    # ── Preference setters ────────────────────────────────────────────────────

    def base(self, angle: float, precision: float = 0.5) -> "MoveBuilder":
        """
        Prefer the IK solution where the base is at `angle`° (0 = forward, + = left).
        precision: 0 = travel matters more, 1 = angle matters more.
        Note: both IK solutions share the same base angle for a given (x, y) target,
        so this mainly acts as a weight modifier and matters most when x=y=0.
        """
        self._base_deg       = angle
        self._base_precision = precision
        return self

    def upper_arm(self, angle: float, precision: float = 0.5) -> "MoveBuilder":
        """
        Prefer the IK solution where the upper arm is at `angle`° above horizontal.
        precision: 0 = travel matters more, 1 = angle matters more.
        """
        self._upper_arm_deg   = angle
        self._upper_precision = precision
        return self

    def forearm(self, angle: float, precision: float = 0.5) -> "MoveBuilder":
        """
        Prefer the IK solution where the lower arm (forearm) points at `angle`°
        above horizontal.  Forearm direction = shoulder_deg + elbow_deg.
        precision: 0 = travel matters more, 1 = angle matters more.
        """
        self._forearm_deg   = angle
        self._lower_precision = precision
        return self

    # ── Solution selection ────────────────────────────────────────────────────

    def _select(self) -> tuple[float, float, float]:
        solutions = self._kin.inverse(self._x, self._y, self._z)
        has_base  = self._base_deg is not None
        has_upper = self._upper_arm_deg is not None
        has_lower = self._forearm_deg is not None

        if not has_base and not has_upper and not has_lower:
            return min(
                solutions,
                key=lambda s: sum(abs(s[i] - self._current[i]) for i in range(3)),
            )

        travels = [sum(abs(s[i] - self._current[i]) for i in range(3)) for s in solutions]

        angle_errs = []
        for s in solutions:
            err = 0.0
            if has_base:
                err += self._base_precision  * abs(s[0] - self._base_deg)
            if has_upper:
                err += self._upper_precision * abs(s[1] - self._upper_arm_deg)
            if has_lower:
                # forearm absolute angle = shoulder + elbow (both relative to horizontal)
                err += self._lower_precision * abs((s[1] + s[2]) - self._forearm_deg)
            angle_errs.append(err)

        active_precisions = [
            p for p, active in (
                (self._base_precision,  has_base),
                (self._upper_precision, has_upper),
                (self._lower_precision, has_lower),
            ) if active
        ]
        angle_w = sum(active_precisions) / len(active_precisions)

        def _norm(v: float, lo: float, hi: float) -> float:
            return (v - lo) / (hi - lo) if hi > lo else 0.0

        t_lo, t_hi = min(travels),    max(travels)
        a_lo, a_hi = min(angle_errs), max(angle_errs)

        scores = [
            (1 - angle_w) * _norm(travels[i],    t_lo, t_hi)
            +      angle_w  * _norm(angle_errs[i], a_lo, a_hi)
            for i in range(len(solutions))
        ]
        return solutions[scores.index(min(scores))]

    # ── StepBuilder protocol ──────────────────────────────────────────────────

    def _build(self) -> StepBuilder:
        bv, sv, ev = self._kin.to_servo_values(*self._select())
        if self._speed is None:
            return parallel(
                servo(Defs.arm_base,    bv),
                servo(Defs.arm_sholder, sv),
                servo(Defs.arm_elbow,   ev),
            )
        return parallel(
            slow_servo(Defs.arm_base,    bv, self._speed),
            slow_servo(Defs.arm_sholder, sv, self._speed),
            slow_servo(Defs.arm_elbow,   ev, self._speed),
        )


# Module-level singleton
arm = ArmKinematics()
