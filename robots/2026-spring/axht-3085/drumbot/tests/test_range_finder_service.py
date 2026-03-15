"""Offline tests for RangeFinderService threshold computation."""
import pytest

from src.service.range_finder_service import RangeFinderService


class TestComputeThresholds:
    def test_basic_thresholds(self):
        """T_enter should be higher than T_exit."""
        scan_data = [(0.0, 100), (1.0, 200), (2.0, 500), (3.0, 300), (4.0, 100)]
        t_enter, t_exit = RangeFinderService.compute_thresholds(scan_data)
        assert t_enter > t_exit

    def test_default_factors(self):
        """With default factors (0.6 enter, 0.4 exit), verify exact values."""
        # baseline=100, peak=500, spread=400
        scan_data = [(0.0, 100), (1.0, 500)]
        t_enter, t_exit = RangeFinderService.compute_thresholds(scan_data)
        assert t_enter == pytest.approx(340.0)  # 100 + 0.6 * 400
        assert t_exit == pytest.approx(260.0)   # 100 + 0.4 * 400

    def test_custom_factors(self):
        """Custom enter/exit factors are applied correctly."""
        scan_data = [(0.0, 0), (1.0, 1000)]
        t_enter, t_exit = RangeFinderService.compute_thresholds(
            scan_data, enter_factor=0.8, exit_factor=0.2
        )
        assert t_enter == pytest.approx(800.0)
        assert t_exit == pytest.approx(200.0)

    def test_empty_scan_raises(self):
        """Empty scan data should raise ValueError."""
        with pytest.raises(ValueError, match="No scan data"):
            RangeFinderService.compute_thresholds([])

    def test_flat_signal(self):
        """When all readings are the same, thresholds equal the baseline."""
        scan_data = [(i, 300.0) for i in range(10)]
        t_enter, t_exit = RangeFinderService.compute_thresholds(scan_data)
        assert t_enter == pytest.approx(300.0)
        assert t_exit == pytest.approx(300.0)

    def test_single_sample(self):
        """Single sample means baseline == peak, so spread is 0."""
        scan_data = [(0.0, 42.0)]
        t_enter, t_exit = RangeFinderService.compute_thresholds(scan_data)
        assert t_enter == pytest.approx(42.0)
        assert t_exit == pytest.approx(42.0)
