"""Verifies the math behind the drive trim scale calibration.

Confirmed from a field test (commanding 50cm): driving with trim=1.09
actually covered 47cm, and driving with trim=0.8218978712844902 actually
covered only 37cm. Physical distance moves *with* the trim, not against it,
which means the trim pre-scales the requested distance before the raw
(uncorrected) odometry loop drives to it:

    odom_distance_m = requested_distance * active_scale
    ground_truth_distance_m = odom_distance_m * true_bias

So ground_truth / odom recovers true_bias directly (independent of
active_scale — it cancels out), and the trim that makes the robot actually
cover the requested distance is the inverse of that: odom / ground_truth.
"""

import pytest

from src.service.setup_calibration import CalibrationAxis, DriveCalibrationSample, SetupCalibrationSession


def _new_scale(session: SetupCalibrationSession, axis: CalibrationAxis) -> float:
    """Mirrors the line in CalibrationGate._finalize_drive_axes."""
    return session.median_axis_scale(axis)


def test_scale_property_is_odom_over_ground_truth() -> None:
    sample = DriveCalibrationSample(
        axis=CalibrationAxis.FORWARD,
        odom_distance_m=0.50,
        ground_truth_distance_m=0.47,
        source="test",
    )
    assert sample.scale == pytest.approx(0.50 / 0.47)


def test_new_scale_recovers_correct_trim_regardless_of_old_scale() -> None:
    """physical = requested * active_scale * true_bias. For any active_scale
    that happened to be loaded during the sample, the absolute corrective
    scale (odom / ground_truth) must come out the same, since active_scale
    cancels out of that ratio.
    """
    true_bias = 0.92
    requested_distance_m = 1.0  # arbitrary; cancels out of the ratio

    for active_scale in (1.0, 1.09, 0.75, 1.4):
        session = SetupCalibrationSession(robot=None)
        odom = requested_distance_m * active_scale
        ground_truth = odom * true_bias
        session.add_drive_sample(
            DriveCalibrationSample(
                axis=CalibrationAxis.FORWARD,
                odom_distance_m=odom,
                ground_truth_distance_m=ground_truth,
                source="test",
            )
        )

        new_scale = _new_scale(session, CalibrationAxis.FORWARD)
        assert new_scale == pytest.approx(1.0 / true_bias)


def test_applying_new_scale_makes_next_drive_hit_the_requested_distance() -> None:
    """Round-trip: once the corrected scale is applied, a drive for the same
    requested distance should land on target (within the model)."""
    true_bias = 0.92
    requested_distance_m = 0.5

    session = SetupCalibrationSession(robot=None)
    old_scale = 1.09
    odom = requested_distance_m * old_scale
    ground_truth = odom * true_bias
    session.add_drive_sample(
        DriveCalibrationSample(
            axis=CalibrationAxis.FORWARD,
            odom_distance_m=odom,
            ground_truth_distance_m=ground_truth,
            source="test",
        )
    )

    new_scale = _new_scale(session, CalibrationAxis.FORWARD)
    next_drive_odom = requested_distance_m * new_scale
    next_drive_physical = next_drive_odom * true_bias
    assert next_drive_physical == pytest.approx(requested_distance_m)


def test_field_data_direction_rules_out_inverse_compounding() -> None:
    """Regression for the actual hardware run: trim=1.09 -> 47cm and
    trim=0.8218978712844902 -> 37cm, both for a 50cm request. Physical
    distance fell *with* the scale (proportional), not against it
    (inverse) -- this is what rules out `new_scale = old_scale * ratio`
    (which assumes an inverse relationship) and confirms the fix of
    inverting the ratio instead.
    """
    requested_cm = 50.0
    scale_a, physical_a = 1.09, 47.0
    scale_b, physical_b = 0.8218978712844902, 37.0

    bias_a = physical_a / (requested_cm * scale_a)
    bias_b = physical_b / (requested_cm * scale_b)

    # Both estimates of the fixed hardware bias should roughly agree
    # (within real-world drive noise) under the proportional model.
    assert bias_a == pytest.approx(bias_b, rel=0.1)

    # Under the (now-removed) inverse model, increasing-S-decreases-physical
    # would require bias estimates computed the other way to *diverge*
    # wildly instead of agreeing.
    inverse_bias_a = physical_a * scale_a / requested_cm
    inverse_bias_b = physical_b * scale_b / requested_cm
    assert abs(inverse_bias_a - inverse_bias_b) > abs(bias_a - bias_b)
