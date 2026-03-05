"""VO2max estimation methods.

Four approaches computed per run:
1. Uth ratio — (HRmax/HRrest) × 15.3
2. VDOT (Daniels) — from run distance and time
3. HR-speed regression — Firstbeat-style from HR and pace
4. Composite — weighted blend based on effort intensity
"""
import math

HR_MAX = 179  # Observed max across all runs


def calc_uth(hr_max: float, rhr: float) -> float:
    """Uth heart rate ratio method. Returns VO2max estimate."""
    return (hr_max / rhr) * 15.3


def calc_vdot(distance_m: float, duration_s: float) -> float:
    """Daniels VDOT from a single run's distance and time."""
    t_min = duration_s / 60.0
    v = distance_m / t_min  # m/min

    vo2_cost = -4.60 + 0.182258 * v + 0.000104 * v ** 2
    pct_max = (0.8
               + 0.1894393 * math.exp(-0.012778 * t_min)
               + 0.2989558 * math.exp(-0.1932605 * t_min))
    if pct_max <= 0:
        return 0.0
    return vo2_cost / pct_max


def calc_hr_speed(avg_speed_m_per_min: float, avg_hr: float,
                  hr_max: float, rhr: float) -> float | None:
    """Firstbeat-style HR-speed regression. Returns None if HR too low."""
    pct_hrr = (avg_hr - rhr) / (hr_max - rhr)
    if pct_hrr < 0.4:
        return None

    vo2_at_pace = -4.60 + 0.182258 * avg_speed_m_per_min + 0.000104 * avg_speed_m_per_min ** 2
    return vo2_at_pace / pct_hrr


def calc_composite(uth: float, vdot: float, hr_speed: float | None,
                   pct_hrr: float, duration_s: float) -> float:
    """Weighted composite from all methods. Weights depend on effort intensity."""
    is_hard = pct_hrr > 0.8 and duration_s > 1200

    if hr_speed is not None:
        if is_hard:
            return vdot * 0.6 + hr_speed * 0.3 + uth * 0.1
        else:
            return hr_speed * 0.5 + uth * 0.3 + vdot * 0.2
    else:
        # No HR-speed available — use VDOT and Uth only
        if is_hard:
            return vdot * 0.7 + uth * 0.3
        else:
            return uth * 0.6 + vdot * 0.4
