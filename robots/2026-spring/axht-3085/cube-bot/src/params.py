"""Typed, string-free mission parameters entered via the setup UI.

A *parameter* is a single value the operator dials in on the robot's screen
during the setup mission (e.g. a positional offset, a speed) and that the
normal mission code then reads back for its calculations.

The design goal is to **never expose a string key at the call site**.  A
parameter is declared once as a typed descriptor on a :class:`ParamSet`.
Python's ``__set_name__`` hands the descriptor its own attribute name, so the
internal storage key is derived automatically — a typo becomes an
``AttributeError`` at import time instead of a silently-wrong ``0.0`` at
runtime, and IDE autocomplete/rename work across the whole codebase.

Declare parameters once::

    # src/mission_params.py
    from src.params import NumberParam, ParamSet


    class P(ParamSet):
        cube_offset = NumberParam(default=0.0, unit="cm", min=-20, max=20, persist=True)
        ramp_speed = NumberParam(default=0.5, min=0.1, max=1.0)

Ask for them in the setup mission — ``.ask()`` returns a ready-to-use step and
pulls unit/range/default straight off the descriptor::

    from src.mission_params import P

    class M000SetupMission(SetupMission):
        def sequence(self) -> Sequential:
            return seq([
                P.cube_offset.ask("Offset der Würfelreihe justieren"),
                P.ramp_speed.ask("Rampen-Speed"),
            ])

Read them in normal mission code — typed, autocompleted, rename-safe::

    def sequence(self) -> Sequential:
        off = P.cube_offset.get()               # -> float
        return seq([drive_forward(cm=60 + off)])

Or bind the value lazily inside a declarative ``seq([...])`` tree with the
existing :func:`defer` primitive, so the calculation happens at execution
time regardless of build order::

    seq([
        defer(lambda r: drive_forward(cm=60 + P.cube_offset.get())),
    ])

Persistence is opt-in: ``persist=True`` mirrors the value into
``racoon.calibration.yml`` (via the shared :class:`CalibrationStore`) so it
survives a process restart and is reused under ``--no-calibrate``.  Without it
a parameter lives only in RAM for the current process — set once in setup,
read by every later mission.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from raccoon import *  # noqa: F403  (UIStep, Step, etc. — matches project convention)
from raccoon.no_calibrate import is_no_calibrate
from raccoon.step.calibration.store import CalibrationStore

if TYPE_CHECKING:
    from raccoon.robot.api import GenericRobot
    from raccoon.step.base import Step


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

#: YAML section (inside ``racoon.calibration.yml``) that persisted parameters
#: live under.  Each parameter is its own ``set_name`` there, so parameters
#: never clobber each other or the sensor-calibration sections.
_PARAM_SECTION = "params"
_VALUE_KEY = "value"


class _ParamStore:
    """Runtime value cache with optional YAML persistence.

    Runtime values live in ``self._values`` for the lifetime of the process
    and are shared across every mission.  When a parameter opts into
    persistence, the value is additionally written to (and lazily read back
    from) the shared calibration YAML so it survives restarts.
    """

    def __init__(self, cal_store: CalibrationStore | None = None) -> None:
        self._values: dict[str, Any] = {}
        self._cal = cal_store or CalibrationStore()

    def set(self, key: str, value: Any, *, persist: bool = False) -> None:
        self._values[key] = value
        if persist:
            self._cal.store(_PARAM_SECTION, {_VALUE_KEY: value}, set_name=key)

    def get(self, key: str, default: Any, *, persisted: bool = False) -> Any:
        if key in self._values:
            return self._values[key]
        if persisted:
            entry = self._cal.load(_PARAM_SECTION, set_name=key)
            if entry is not None and _VALUE_KEY in entry:
                value = entry[_VALUE_KEY]
                self._values[key] = value  # cache so later reads skip disk
                return value
        return default

    def has(self, key: str, *, persisted: bool = False) -> bool:
        if key in self._values:
            return True
        if persisted:
            entry = self._cal.load(_PARAM_SECTION, set_name=key)
            return entry is not None and _VALUE_KEY in entry
        return False

    def clear(self) -> None:
        """Drop all runtime values (persisted YAML is untouched)."""
        self._values.clear()


#: Process-wide singleton.  Parameters read/write through this.
_store = _ParamStore()


def reset_params() -> None:
    """Clear all runtime parameter values (test helper).

    Only touches the in-memory cache; persisted YAML entries are left alone.
    """
    _store.clear()


# ---------------------------------------------------------------------------
# Parameter descriptors
# ---------------------------------------------------------------------------


class NumberParam:
    """A numeric mission parameter, declared once as a :class:`ParamSet` field.

    The descriptor owns the value's metadata (default, unit, valid range,
    persistence) and, via ``__set_name__``, its own storage key — so callers
    interact with the *attribute*, never a string::

        class P(ParamSet):
            cube_offset = NumberParam(default=0.0, unit="cm", min=-20, max=20)

        P.cube_offset.get()             # -> float
        P.cube_offset.ask("Offset...")  # -> Step for the setup mission

    Args:
        default: Value returned by :meth:`get` before anything is entered.
        unit: Display unit shown on the input screen (e.g. ``"cm"``).
        min: Lower clamp bound, or ``None`` for unbounded.
        max: Upper clamp bound, or ``None`` for unbounded.
        persist: When ``True``, entered values are mirrored to
            ``racoon.calibration.yml`` and reused across restarts /
            ``--no-calibrate``.
        key: Explicit storage key.  Normally omitted — the attribute name is
            used automatically.  Only needed when declaring a parameter
            outside a class body (e.g. a module-level constant).
    """

    def __init__(
        self,
        default: float = 0.0,
        *,
        unit: str = "",
        min: float | None = None,  # noqa: A002 (deliberate ergonomic name)
        max: float | None = None,  # noqa: A002
        persist: bool = False,
        key: str | None = None,
    ) -> None:
        self._key = key
        self.default = float(default)
        self.unit = unit
        self.min = None if min is None else float(min)
        self.max = None if max is None else float(max)
        self.persist = persist

    def __set_name__(self, owner: type, name: str) -> None:
        if self._key is None:
            self._key = name

    @property
    def key(self) -> str:
        if self._key is None:
            msg = (
                "NumberParam has no key — declare it as a class attribute on a "
                "ParamSet, or pass key=... for a standalone parameter."
            )
            raise RuntimeError(msg)
        return self._key

    def _clamp(self, value: float) -> float:
        if self.min is not None:
            value = max(self.min, value)
        if self.max is not None:
            value = min(self.max, value)
        return value

    def get(self) -> float:
        """Return the current value, or :attr:`default` if none was entered."""
        return float(_store.get(self.key, self.default, persisted=self.persist))

    def set(self, value: float) -> None:
        """Set the value directly (clamped to the declared range)."""
        _store.set(self.key, self._clamp(float(value)), persist=self.persist)

    def is_set(self) -> bool:
        """Whether a value has been entered/persisted (vs. falling back to default)."""
        return _store.has(self.key, persisted=self.persist)

    def ask(self, prompt: str, *, title: str = "Setup") -> "Step":
        """Return a setup step that asks the operator for this value.

        The input screen is pre-filled with the current value (persisted or
        default) and constrained to the declared unit and range.  Cancelling
        keeps the existing value.  Under ``--no-calibrate`` the UI is skipped
        and the persisted/default value is used as-is.

        Args:
            prompt: Question shown above the numeric keypad.
            title: Screen title. Defaults to ``"Setup"``.

        Returns:
            An :class:`AskNumber` step, ready to drop into a ``seq([...])``.
        """
        return AskNumber(self, prompt, title=title)


class ParamSet:
    """Base for a group of parameter declarations.

    Subclassing is optional — ``__set_name__`` works on any class — but it
    provides :meth:`all` for iterating declared parameters (handy for tests
    or a "reset everything" screen).

    Example::

        class P(ParamSet):
            cube_offset = NumberParam(default=0.0, unit="cm")
            ramp_speed = NumberParam(default=0.5)
    """

    @classmethod
    def all(cls) -> list[NumberParam]:
        """Return every :class:`NumberParam` declared on this class."""
        return [v for v in vars(cls).values() if isinstance(v, NumberParam)]


# ---------------------------------------------------------------------------
# Setup step
# ---------------------------------------------------------------------------


class AskNumber(UIStep):  # noqa: F405 (UIStep comes from `raccoon import *`)
    """Setup step: ask the operator for a numeric parameter via the screen.

    Prefer ``param.ask("...")`` or the :func:`ask` factory over constructing
    this directly.  Shows a numeric keypad pre-filled with the parameter's
    current value, clamped to its declared range, and stores whatever the
    operator confirms back into the parameter.

    Under ``--no-calibrate`` the screen is skipped entirely and the existing
    (persisted or default) value is kept, matching the behaviour of the
    calibration steps.
    """

    def __init__(self, param: NumberParam, prompt: str, *, title: str = "Setup") -> None:
        super().__init__()
        self._param = param
        self._prompt = prompt
        self._title = title

    def _generate_signature(self) -> str:
        return f"AskNumber(key={self._param.key!r}, value={self._param.get():.2f})"

    async def _execute_step(self, robot: "GenericRobot") -> None:
        if is_no_calibrate():
            self.info(
                f"--no-calibrate: {self._param.key} = "
                f"{self._param.get()}{self._param.unit} (Eingabe übersprungen)"
            )
            return

        value = await self.input_number(
            prompt=self._prompt,
            title=self._title,
            default=self._param.get(),
            unit=self._param.unit,
            min_value=self._param.min,
            max_value=self._param.max,
        )

        if value is None:
            self.warn(
                f"{self._param.key}: Eingabe abgebrochen, behalte "
                f"{self._param.get()}{self._param.unit}"
            )
            return

        self._param.set(value)
        self.info(f"{self._param.key} = {self._param.get()}{self._param.unit}")


def ask(param: NumberParam, prompt: str, *, title: str = "Setup") -> "Step":
    """Free-function alias for :meth:`NumberParam.ask`.

    Some prefer ``ask(P.cube_offset, "...")`` over ``P.cube_offset.ask("...")``;
    both build the same step.
    """
    return param.ask(prompt, title=title)
