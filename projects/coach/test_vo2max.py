"""Tests for VO2max estimation methods."""
import math
import pytest
from vo2max import calc_uth, calc_vdot, calc_hr_speed, calc_composite


def test_uth_basic():
    """Uth formula: (HRmax/HRrest) * 15.3"""
    result = calc_uth(hr_max=179, rhr=60)
    assert abs(result - 45.6) < 0.5  # (179/60)*15.3 = 45.6


def test_uth_lower_rhr_means_higher_vo2():
    high = calc_uth(hr_max=179, rhr=50)
    low = calc_uth(hr_max=179, rhr=70)
    assert high > low


def test_vdot_5k_25min():
    """Known example from Daniels: 5K in 25:00 -> VDOT ~38.3"""
    result = calc_vdot(distance_m=5000, duration_s=25 * 60)
    assert 37 < result < 40


def test_vdot_longer_slower_gives_lower():
    fast = calc_vdot(distance_m=5000, duration_s=25 * 60)
    slow = calc_vdot(distance_m=5000, duration_s=35 * 60)
    assert fast > slow


def test_vdot_half_marathon():
    """HM in 2:10 -> VDOT ~33"""
    result = calc_vdot(distance_m=21097, duration_s=130 * 60)
    assert 32 < result < 35


def test_hr_speed_moderate_effort():
    """Moderate run: 6:30/km pace at 77% HRR should give VO2max ~30-35."""
    speed_m_per_min = 1000 / 6.5  # ~154 m/min
    result = calc_hr_speed(
        avg_speed_m_per_min=speed_m_per_min,
        avg_hr=152, hr_max=179, rhr=60
    )
    assert 28 < result < 40


def test_hr_speed_rejects_low_hr():
    """Below 40% HRR should return None (not meaningful)."""
    speed_m_per_min = 1000 / 8.0
    result = calc_hr_speed(
        avg_speed_m_per_min=speed_m_per_min,
        avg_hr=90, hr_max=179, rhr=60  # ~25% HRR
    )
    assert result is None


def test_composite_hard_effort():
    """Hard effort weights VDOT highest."""
    result = calc_composite(
        uth=46.0, vdot=38.0, hr_speed=35.0,
        pct_hrr=0.85, duration_s=1800
    )
    # Hard effort: VDOT 60% + HR-speed 30% + Uth 10%
    expected = 38.0 * 0.6 + 35.0 * 0.3 + 46.0 * 0.1
    assert abs(result - expected) < 0.1


def test_composite_easy_effort():
    """Easy effort weights HR-speed highest."""
    result = calc_composite(
        uth=46.0, vdot=30.0, hr_speed=35.0,
        pct_hrr=0.55, duration_s=3600
    )
    # Easy: HR-speed 50% + Uth 30% + VDOT 20%
    expected = 35.0 * 0.5 + 46.0 * 0.3 + 30.0 * 0.2
    assert abs(result - expected) < 0.1


def test_composite_handles_none_hr_speed():
    """When HR-speed is None (low HR), redistribute weights."""
    result = calc_composite(
        uth=46.0, vdot=30.0, hr_speed=None,
        pct_hrr=0.85, duration_s=1800
    )
    assert result is not None
    # Should be between uth and vdot
    assert 30.0 < result < 46.0
