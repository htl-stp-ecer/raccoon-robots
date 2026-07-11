"""Tests for the typed, string-free mission-parameter framework (src/params.py).

Covers the parts that carry logic and don't need a live UI/transport: the
runtime + persistent store, and the NumberParam descriptor (key derivation via
__set_name__, clamping, default fallback, persistence round-trip).  The
AskNumber UI step is intentionally not exercised here — it only wires
input_number() into param.set(), which requires a robot/transport.
"""

from __future__ import annotations

import pytest

from src.params import (
    NumberParam,
    ParamSet,
    _ParamStore,
    reset_params,
)
from raccoon.step.calibration.store import CalibrationStore


@pytest.fixture(autouse=True)
def _clean_runtime():
    """Every test starts with an empty runtime cache."""
    reset_params()
    yield
    reset_params()


# --- key derivation --------------------------------------------------------


def test_key_is_derived_from_attribute_name():
    class P(ParamSet):
        cube_offset = NumberParam(default=0.0)

    assert P.cube_offset.key == "cube_offset"


def test_explicit_key_overrides_attribute_name():
    param = NumberParam(default=0.0, key="explicit")

    class P(ParamSet):
        renamed = param  # __set_name__ must NOT clobber an explicit key

    assert P.renamed.key == "explicit"


def test_standalone_param_without_key_raises():
    param = NumberParam(default=1.0)
    with pytest.raises(RuntimeError):
        _ = param.key


# --- get / set / default ---------------------------------------------------


def test_get_returns_default_when_unset():
    class P(ParamSet):
        speed = NumberParam(default=0.5)

    assert P.speed.get() == 0.5
    assert P.speed.is_set() is False


def test_set_then_get_roundtrips():
    class P(ParamSet):
        speed = NumberParam(default=0.5)

    P.speed.set(0.8)
    assert P.speed.get() == 0.8
    assert P.speed.is_set() is True


def test_set_clamps_to_range():
    class P(ParamSet):
        offset = NumberParam(default=0.0, min=-20, max=20)

    P.offset.set(999)
    assert P.offset.get() == 20.0
    P.offset.set(-999)
    assert P.offset.get() == -20.0


def test_reset_params_clears_runtime_value():
    class P(ParamSet):
        speed = NumberParam(default=0.5)

    P.speed.set(0.9)
    reset_params()
    assert P.speed.get() == 0.5
    assert P.speed.is_set() is False


# --- ParamSet.all ----------------------------------------------------------


def test_paramset_all_lists_declared_params():
    class P(ParamSet):
        a = NumberParam(default=1.0)
        b = NumberParam(default=2.0)
        not_a_param = 3

    assert set(P.all()) == {P.a, P.b}


# --- persistence (store level) --------------------------------------------


def test_store_persists_to_yaml_and_reads_back(tmp_path):
    yml = tmp_path / "cal.yml"
    store_a = _ParamStore(cal_store=CalibrationStore(path=yml))
    store_a.set("offset", 3.5, persist=True)

    # A fresh store (fresh runtime cache) still recovers the value from disk.
    store_b = _ParamStore(cal_store=CalibrationStore(path=yml))
    assert store_b.get("offset", 0.0, persisted=True) == 3.5
    assert store_b.has("offset", persisted=True) is True


def test_store_runtime_only_does_not_touch_yaml(tmp_path):
    yml = tmp_path / "cal.yml"
    store_a = _ParamStore(cal_store=CalibrationStore(path=yml))
    store_a.set("speed", 0.7, persist=False)

    store_b = _ParamStore(cal_store=CalibrationStore(path=yml))
    assert store_b.get("speed", 0.1, persisted=True) == 0.1  # falls back to default
    assert store_b.has("speed", persisted=True) is False


def test_non_persisted_get_ignores_existing_yaml(tmp_path):
    yml = tmp_path / "cal.yml"
    # Value is on disk, but the param opts out of persistence...
    _ParamStore(cal_store=CalibrationStore(path=yml)).set("k", 9.0, persist=True)
    store = _ParamStore(cal_store=CalibrationStore(path=yml))
    # ...so a non-persisted read must not see it.
    assert store.get("k", 0.0, persisted=False) == 0.0
