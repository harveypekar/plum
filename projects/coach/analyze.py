"""Running coach analysis — generates a self-contained HTML report from Intervals.icu data."""

import json
import math
import os
import re
import subprocess
import sys
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from vo2max import calc_uth, calc_vdot, calc_hr_speed, calc_composite, HR_MAX
from garmin_loader import (
    load_garmin_runs, find_latest_run, load_garmin_activity,
    load_garmin_daily_context, extract_steady_state_speed,
)
from db import get_connection, upsert_activity, load_all_enriched

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data" / "intervals"
ACTIVITIES_DIR = DATA_DIR / "activities"
REPORT_PATH = SCRIPT_DIR / "report.html"
METRICS_PATH = SCRIPT_DIR / "metrics.json"

RACE_DATE = datetime(2026, 7, 4)
RACE_NAME = "Backyard Ultra"
TODAY = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_activities():
    activities = []
    for act_dir in ACTIVITIES_DIR.iterdir():
        detail = act_dir / "detail.json"
        if detail.exists():
            with open(detail, encoding="utf-8") as f:
                activities.append(json.load(f))
    return activities


def filter_runs(activities):
    runs = []
    for a in activities:
        if a.get("type") != "Run":
            continue
        dist = a.get("distance", 0) or 0
        moving = a.get("moving_time", 0) or 0
        if dist < 2000 or moving < 600:
            continue
        runs.append(a)
    runs.sort(key=lambda a: a.get("start_date_local", ""))
    return runs


def load_stream(activity_id):
    path = ACTIVITIES_DIR / str(activity_id) / "streams.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    streams = {}
    for item in raw:
        t = item.get("type")
        if t and item.get("data"):
            streams[t] = item["data"]
            if item.get("data2"):
                streams[t + "_2"] = item["data2"]
    return streams


def parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00").split("+")[0])
    except ValueError:
        return None

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def pace_ms_to_minkm(pace_ms):
    """Convert pace in m/s to min/km float."""
    if not pace_ms or pace_ms <= 0:
        return 0
    return 1000.0 / (pace_ms * 60.0)


def fmt_pace(minkm):
    """Format min/km as M:SS."""
    if not minkm or minkm <= 0:
        return "--:--"
    mins = int(minkm)
    secs = int((minkm - mins) * 60)
    return f"{mins}:{secs:02d}"


def fmt_duration(seconds):
    """Format seconds as H:MM:SS or MM:SS."""
    if not seconds:
        return "0:00"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fmt_dist(meters):
    """Format meters as km with 1 decimal."""
    if not meters:
        return "0.0"
    return f"{meters / 1000:.1f}"


def linear_regression(xs, ys):
    """Returns (slope, intercept) via least squares. Returns (0,0) if degenerate."""
    n = len(xs)
    if n < 2:
        return 0, 0
    sx = sum(xs)
    sy = sum(ys)
    sxx = sum(x * x for x in xs)
    sxy = sum(x * y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return 0, sy / n if n else 0
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def rolling_avg(data, window):
    """Simple rolling average."""
    result = []
    for i in range(len(data)):
        start = max(0, i - window + 1)
        chunk = data[start:i + 1]
        result.append(sum(chunk) / len(chunk))
    return result

# ---------------------------------------------------------------------------
# SVG Chart
# ---------------------------------------------------------------------------

class SvgChart:
    """Generates inline SVG charts."""

    def __init__(self, width=700, height=260, margin=None):
        self.width = width
        self.height = height
        self.margin = margin or {"top": 20, "right": 20, "bottom": 40, "left": 55}
        self.plot_w = width - self.margin["left"] - self.margin["right"]
        self.plot_h = height - self.margin["top"] - self.margin["bottom"]

    def _sx(self, val, vmin, vmax):
        if vmax == vmin:
            return self.margin["left"] + self.plot_w / 2
        return self.margin["left"] + (val - vmin) / (vmax - vmin) * self.plot_w

    def _sy(self, val, vmin, vmax):
        if vmax == vmin:
            return self.margin["top"] + self.plot_h / 2
        return self.margin["top"] + self.plot_h - (val - vmin) / (vmax - vmin) * self.plot_h

    def _x_axis(self, labels, vmin, vmax):
        parts = []
        y = self.margin["top"] + self.plot_h
        for lbl, val in labels:
            x = self._sx(val, vmin, vmax)
            parts.append(f'<text x="{x:.1f}" y="{y + 18}" text-anchor="middle" '
                         f'font-size="11" fill="#888">{lbl}</text>')
            parts.append(f'<line x1="{x:.1f}" y1="{y}" x2="{x:.1f}" y2="{y + 4}" '
                         f'stroke="#444"/>')
        return "\n".join(parts)

    def _y_axis(self, labels, vmin, vmax):
        parts = []
        x = self.margin["left"]
        for lbl, val in labels:
            y = self._sy(val, vmin, vmax)
            parts.append(f'<text x="{x - 8}" y="{y + 4}" text-anchor="end" '
                         f'font-size="11" fill="#888">{lbl}</text>')
            parts.append(f'<line x1="{x}" y1="{y:.1f}" x2="{x + self.plot_w}" '
                         f'y2="{y:.1f}" stroke="#333"/>')
        return "\n".join(parts)

    def _auto_labels_num(self, vmin, vmax, count=5):
        if vmax == vmin:
            return [(f"{vmin:.1f}", vmin)]
        step = (vmax - vmin) / (count - 1)
        return [(f"{vmin + i * step:.1f}", vmin + i * step) for i in range(count)]

    def _begin(self, title=""):
        title_el = ""
        if title:
            title_el = (f'<text x="{self.width / 2}" y="14" text-anchor="middle" '
                        f'font-size="13" font-weight="bold" fill="#e0e0e0">{title}</text>')
        return (f'<svg width="{self.width}" height="{self.height}" '
                f'xmlns="http://www.w3.org/2000/svg" style="font-family:sans-serif">\n'
                f'<rect width="{self.width}" height="{self.height}" fill="#0a0a0a" rx="6"/>\n'
                f'{title_el}\n')

    def _end(self):
        return '</svg>'

    def line(self, xs, ys, color="#2196F3", title="", x_labels=None, y_labels=None,
             trend=False, trend_color="#FF5722", extra_lines=None):
        if not xs or not ys:
            return ""
        xmin, xmax = min(xs), max(xs)
        all_ys = list(ys)
        if extra_lines:
            for _, eys, _ in extra_lines:
                all_ys.extend(eys)
        ymin, ymax = min(all_ys), max(all_ys)
        pad = (ymax - ymin) * 0.05 or 1
        ymin -= pad
        ymax += pad

        parts = [self._begin(title)]

        if y_labels:
            parts.append(self._y_axis(y_labels, ymin, ymax))
        else:
            parts.append(self._y_axis(self._auto_labels_num(ymin, ymax), ymin, ymax))
        if x_labels:
            parts.append(self._x_axis(x_labels, xmin, xmax))

        def make_polyline(pxs, pys, c, sw="2", opacity="1"):
            pts = " ".join(f"{self._sx(x, xmin, xmax):.1f},{self._sy(y, ymin, ymax):.1f}"
                           for x, y in zip(pxs, pys))
            return (f'<polyline points="{pts}" fill="none" stroke="{c}" '
                    f'stroke-width="{sw}" opacity="{opacity}"/>')

        parts.append(make_polyline(xs, ys, color))

        if extra_lines:
            for exs, eys, ec in extra_lines:
                parts.append(make_polyline(exs, eys, ec))

        if trend and len(xs) >= 2:
            slope, intercept = linear_regression(xs, ys)
            ty = [slope * x + intercept for x in [xmin, xmax]]
            parts.append(make_polyline([xmin, xmax], ty, trend_color, "2", "0.6"))

        parts.append(self._end())
        return "\n".join(parts)

    def scatter(self, xs, ys, color="#2196F3", title="", x_labels=None, y_labels=None,
                trend=False, trend_color="#FF5722"):
        if not xs or not ys:
            return ""
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        pad_y = (ymax - ymin) * 0.05 or 1
        ymin -= pad_y
        ymax += pad_y

        parts = [self._begin(title)]

        if y_labels:
            parts.append(self._y_axis(y_labels, ymin, ymax))
        else:
            parts.append(self._y_axis(self._auto_labels_num(ymin, ymax), ymin, ymax))
        if x_labels:
            parts.append(self._x_axis(x_labels, xmin, xmax))

        for x, y in zip(xs, ys):
            cx = self._sx(x, xmin, xmax)
            cy = self._sy(y, ymin, ymax)
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="3.5" '
                         f'fill="{color}" opacity="0.6"/>')

        if trend and len(xs) >= 2:
            slope, intercept = linear_regression(xs, ys)
            ty = [slope * x + intercept for x in [xmin, xmax]]
            pts = (f"{self._sx(xmin, xmin, xmax):.1f},{self._sy(ty[0], ymin, ymax):.1f} "
                   f"{self._sx(xmax, xmin, xmax):.1f},{self._sy(ty[1], ymin, ymax):.1f}")
            parts.append(f'<polyline points="{pts}" fill="none" stroke="{trend_color}" '
                         f'stroke-width="2" opacity="0.7" stroke-dasharray="6,3"/>')

        parts.append(self._end())
        return "\n".join(parts)

    def bar(self, labels, values, color="#2196F3", title="", y_labels=None,
            colors=None):
        if not labels or not values:
            return ""
        n = len(labels)
        ymin = 0
        ymax = max(values) if values else 1
        if ymax == 0:
            ymax = 1
        pad = ymax * 0.05
        ymax += pad

        parts = [self._begin(title)]

        if y_labels:
            parts.append(self._y_axis(y_labels, ymin, ymax))
        else:
            parts.append(self._y_axis(self._auto_labels_num(ymin, ymax), ymin, ymax))

        bar_w = self.plot_w / n * 0.7
        gap = self.plot_w / n * 0.3
        baseline = self._sy(0, ymin, ymax)

        for i, (lbl, val) in enumerate(zip(labels, values)):
            x = self.margin["left"] + i * (bar_w + gap) + gap / 2
            y = self._sy(val, ymin, ymax)
            h = baseline - y
            c = colors[i] if colors else color
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                         f'height="{h:.1f}" fill="{c}" rx="2" opacity="0.85"/>')
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{baseline + 16}" '
                         f'text-anchor="middle" font-size="10" fill="#888">{lbl}</text>')

        parts.append(self._end())
        return "\n".join(parts)

    def stacked_bar(self, labels, series, title=""):
        """series: list of (name, values_list, color)."""
        if not labels or not series:
            return ""
        n = len(labels)
        totals = [sum(s[1][i] for s in series) for i in range(n)]
        ymax = max(totals) if totals else 1
        if ymax == 0:
            ymax = 1
        ymin = 0
        pad = ymax * 0.05
        ymax += pad

        parts = [self._begin(title)]
        parts.append(self._y_axis(self._auto_labels_num(ymin, ymax), ymin, ymax))

        bar_w = self.plot_w / n * 0.7
        gap = self.plot_w / n * 0.3
        baseline = self._sy(0, ymin, ymax)

        for i, lbl in enumerate(labels):
            x = self.margin["left"] + i * (bar_w + gap) + gap / 2
            cum = 0
            for name, vals, color in series:
                v = vals[i]
                y_top = self._sy(cum + v, ymin, ymax)
                h = self._sy(cum, ymin, ymax) - y_top
                if h > 0:
                    parts.append(f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{bar_w:.1f}" '
                                 f'height="{h:.1f}" fill="{color}" opacity="0.85"/>')
                cum += v
            parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{baseline + 16}" '
                         f'text-anchor="middle" font-size="10" fill="#888">{lbl}</text>')

        # Legend
        lx = self.margin["left"] + self.plot_w - len(series) * 90
        ly = self.margin["top"] - 4
        for name, _, color in series:
            parts.append(f'<rect x="{lx}" y="{ly - 8}" width="10" height="10" '
                         f'fill="{color}" rx="2"/>')
            parts.append(f'<text x="{lx + 14}" y="{ly}" font-size="10" fill="#aaa">'
                         f'{name}</text>')
            lx += 90

        parts.append(self._end())
        return "\n".join(parts)

    def area(self, xs, ys, color="#2196F3", fill_color=None, title="",
             x_labels=None, y_labels=None):
        if not xs or not ys:
            return ""
        fc = fill_color or color
        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)
        pad = (ymax - ymin) * 0.05 or 1
        ymin -= pad
        ymax += pad

        parts = [self._begin(title)]
        if y_labels:
            parts.append(self._y_axis(y_labels, ymin, ymax))
        else:
            parts.append(self._y_axis(self._auto_labels_num(ymin, ymax), ymin, ymax))
        if x_labels:
            parts.append(self._x_axis(x_labels, xmin, xmax))

        baseline_y = self._sy(ymin, ymin, ymax)
        pts_top = " ".join(f"{self._sx(x, xmin, xmax):.1f},{self._sy(y, ymin, ymax):.1f}"
                           for x, y in zip(xs, ys))
        x_first = self._sx(xs[0], xmin, xmax)
        x_last = self._sx(xs[-1], xmin, xmax)
        poly = f"{x_first:.1f},{baseline_y:.1f} {pts_top} {x_last:.1f},{baseline_y:.1f}"
        parts.append(f'<polygon points="{poly}" fill="{fc}" opacity="0.25"/>')
        parts.append(f'<polyline points="{pts_top}" fill="none" stroke="{color}" '
                     f'stroke-width="1.5"/>')

        parts.append(self._end())
        return "\n".join(parts)

# ---------------------------------------------------------------------------
# Section A: Last Run Deep-Dive
# ---------------------------------------------------------------------------

def section_last_run(runs, chart):
    last = runs[-1]
    dt = parse_date(last.get("start_date_local"))
    date_str = dt.strftime("%a %d %b %Y, %H:%M") if dt else "Unknown"
    dist = last.get("distance", 0)
    moving = last.get("moving_time", 0)
    pace = last.get("pace", 0)
    hr = last.get("average_heartrate", 0)
    max_hr = last.get("max_heartrate", 0)
    elev = last.get("total_elevation_gain", 0)
    tl = last.get("icu_training_load", 0)
    cadence = last.get("average_cadence", 0)
    stride = last.get("average_stride", 0)

    minkm = pace_ms_to_minkm(pace)

    html = '<div class="section"><h2>Last Run Deep-Dive</h2>'

    # Summary card
    html += '<div class="card-grid">'
    cards = [
        ("Date", date_str),
        ("Distance", f"{fmt_dist(dist)} km"),
        ("Duration", fmt_duration(moving)),
        ("Pace", f"{fmt_pace(minkm)} /km"),
        ("Avg HR", f"{hr:.0f} bpm" if hr else "--"),
        ("Max HR", f"{max_hr:.0f} bpm" if max_hr else "--"),
        ("Elevation", f"{elev:.0f} m" if elev else "--"),
        ("Training Load", f"{tl:.0f}" if tl else "--"),
        ("Cadence", f"{cadence * 2:.0f} spm" if cadence else "--"),
        ("Stride", f"{stride:.2f} m" if stride else "--"),
    ]
    for label, value in cards:
        html += f'<div class="stat-card"><div class="stat-value">{value}</div><div class="stat-label">{label}</div></div>'
    html += '</div>'

    # Comparison to similar distance runs
    similar = [r for r in runs[:-1]
               if r.get("distance", 0) and abs(r["distance"] - dist) / dist < 0.20
               and r.get("pace")]
    if similar:
        avg_pace = sum(pace_ms_to_minkm(r["pace"]) for r in similar) / len(similar)
        avg_hr = sum(r.get("average_heartrate", 0) for r in similar if r.get("average_heartrate")) / max(1, sum(1 for r in similar if r.get("average_heartrate")))
        diff_pace = ((minkm - avg_pace) / avg_pace * 100) if avg_pace else 0
        faster = "faster" if diff_pace < 0 else "slower"
        html += (f'<p class="insight">Compared to {len(similar)} runs at similar distance '
                 f'({fmt_dist(dist * 0.8)}-{fmt_dist(dist * 1.2)} km): '
                 f'pace was <b>{abs(diff_pace):.1f}% {faster}</b> '
                 f'({fmt_pace(minkm)} vs avg {fmt_pace(avg_pace)})')
        if avg_hr:
            html += f', avg HR {hr:.0f} vs {avg_hr:.0f} bpm'
        html += '.</p>'

    # HR zone distribution
    zone_times = last.get("icu_hr_zone_times")
    if zone_times:
        zone_names = ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"]
        zone_colors = ["#4CAF50", "#8BC34A", "#FFC107", "#FF9800", "#FF5722", "#E91E63", "#9C27B0"]
        zone_mins = [t / 60.0 for t in zone_times]
        total_zone = sum(zone_mins)
        if total_zone > 0:
            html += '<h3>HR Zone Distribution</h3>'
            html += chart.stacked_bar(
                ["This Run"],
                [(zone_names[i], [zone_mins[i]], zone_colors[i]) for i in range(7)],
                title=""
            )
            html += '<div class="zone-summary">'
            for i, (name, mins) in enumerate(zip(zone_names, zone_mins)):
                pct = mins / total_zone * 100 if total_zone else 0
                html += (f'<span class="zone-badge" style="background:{zone_colors[i]};'
                         f'color:white">{name}: {mins:.0f}min ({pct:.0f}%)</span> ')
            html += '</div>'
            easy_pct = (zone_mins[0] + zone_mins[1]) / total_zone * 100 if total_zone else 0
            hard_pct = sum(zone_mins[3:]) / total_zone * 100 if total_zone else 0
            html += f'<p class="insight">Easy (Z1-2): {easy_pct:.0f}% | Tempo (Z3): {zone_mins[2] / total_zone * 100:.0f}% | Hard (Z4+): {hard_pct:.0f}%</p>'

    # Stream-based analysis
    stream = load_stream(last.get("id", ""))
    if stream:
        vel = stream.get("velocity_smooth", [])
        dist_s = stream.get("distance", [])
        hr_s = stream.get("heartrate", [])
        alt_s = stream.get("altitude", [])
        time_s = stream.get("time", [])
        cad_s = stream.get("cadence", [])

        # Pace over distance (60s rolling avg)
        if vel and dist_s and len(vel) == len(dist_s):
            window = 60
            paces = []
            dists = []
            for i in range(len(vel)):
                start = max(0, i - window + 1)
                chunk = vel[start:i + 1]
                valid = [v for v in chunk if v and v > 0]
                if valid and dist_s[i]:
                    avg_v = sum(valid) / len(valid)
                    paces.append(pace_ms_to_minkm(avg_v))
                    dists.append(dist_s[i] / 1000.0)
            if paces:
                # Downsample for SVG
                step = max(1, len(paces) // 300)
                dp = paces[::step]
                dd = dists[::step]
                x_labels = [(f"{d:.0f}km", d) for d in range(1, int(dd[-1]) + 1)]
                y_min = min(dp)
                y_max = max(dp)
                y_labels = [(fmt_pace(v), v) for v in
                            [y_min, y_min + (y_max - y_min) * 0.33,
                             y_min + (y_max - y_min) * 0.67, y_max]]
                html += '<h3>Pace Over Distance</h3>'
                html += chart.line(dd, dp, color="#2196F3",
                                   x_labels=x_labels, y_labels=y_labels)
                html += '<p class="chart-note">60-second rolling average. Lower = faster.</p>'

        # Elevation profile
        if alt_s and dist_s and len(alt_s) == len(dist_s):
            paired = [(d / 1000.0, a) for d, a in zip(dist_s, alt_s)
                      if a is not None and d is not None]
            step = max(1, len(paired) // 300)
            paired = paired[::step]
            ed = [d for d, _ in paired]
            ea = [a for _, a in paired]
            if ea and ed:
                x_labels = [(f"{d:.0f}km", d) for d in range(1, int(ed[-1]) + 1)]
                html += '<h3>Elevation Profile</h3>'
                html += chart.area(ed, ea, color="#795548", fill_color="#A1887F",
                                   x_labels=x_labels)

        # HR drift
        if hr_s and time_s and len(hr_s) == len(time_s):
            warmup = 300  # 5min
            cooldown = 120  # 2min
            max_time = max(time_s) if time_s else 0
            valid_hr = [(t, h) for t, h in zip(time_s, hr_s)
                        if h and h > 0 and warmup <= t <= max_time - cooldown]
            if len(valid_hr) > 20:
                mid = len(valid_hr) // 2
                first_half = [h for _, h in valid_hr[:mid]]
                second_half = [h for _, h in valid_hr[mid:]]
                avg_first = sum(first_half) / len(first_half)
                avg_second = sum(second_half) / len(second_half)
                drift_pct = (avg_second - avg_first) / avg_first * 100
                drift_class = "warning" if abs(drift_pct) > 5 else "good"
                html += (f'<h3>HR Drift</h3>'
                         f'<p class="insight {drift_class}">First half avg: {avg_first:.0f} bpm | '
                         f'Second half avg: {avg_second:.0f} bpm | '
                         f'Drift: <b>{drift_pct:+.1f}%</b>')
                if abs(drift_pct) > 5:
                    html += ' &#9888; Significant drift &mdash; aerobic base may need work'
                html += '</p>'

        # Per-km splits
        if dist_s and time_s and len(dist_s) == len(time_s):
            html += '<h3>Per-km Splits</h3>'
            html += '<table class="splits"><tr><th>km</th><th>Pace</th>'
            if hr_s:
                html += '<th>Avg HR</th>'
            if alt_s:
                html += '<th>Elev +/-</th>'
            if cad_s:
                html += '<th>Cadence</th>'
            html += '</tr>'
            km = 1
            last_idx = 0
            for i in range(1, len(dist_s)):
                if dist_s[i] and dist_s[i] >= km * 1000:
                    t_split = time_s[i] - time_s[last_idx] if time_s[i] and time_s[last_idx] is not None else 0
                    d_split = dist_s[i] - (dist_s[last_idx] or 0)
                    if t_split > 0 and d_split > 0:
                        split_pace = pace_ms_to_minkm(d_split / t_split)
                        html += f'<tr><td>{km}</td><td>{fmt_pace(split_pace)}</td>'
                        if hr_s:
                            split_hrs = [h for h in hr_s[last_idx:i + 1] if h and h > 0]
                            avg_split_hr = sum(split_hrs) / len(split_hrs) if split_hrs else 0
                            html += f'<td>{avg_split_hr:.0f}</td>'
                        if alt_s:
                            split_alts = [a for a in alt_s[last_idx:i + 1] if a is not None]
                            if len(split_alts) >= 2:
                                gain = sum(max(0, split_alts[j] - split_alts[j - 1])
                                           for j in range(1, len(split_alts)))
                                loss = sum(max(0, split_alts[j - 1] - split_alts[j])
                                           for j in range(1, len(split_alts)))
                                html += f'<td>+{gain:.0f}/-{loss:.0f}</td>'
                            else:
                                html += '<td>--</td>'
                        if cad_s:
                            split_cads = [c for c in cad_s[last_idx:i + 1] if c and c > 0]
                            avg_cad = sum(split_cads) / len(split_cads) if split_cads else 0
                            html += f'<td>{avg_cad * 2:.0f}</td>'
                        html += '</tr>'
                    last_idx = i
                    km += 1
            html += '</table>'

    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Section B: Training Load & Fitness
# ---------------------------------------------------------------------------

def section_training_load(runs, chart):
    html = '<div class="section"><h2>Training Load &amp; Fitness</h2>'

    # CTL/ATL/TSB over time
    ctl_data, atl_data, tsb_data, dates_num, date_labels = [], [], [], [], []
    for r in runs:
        ctl = r.get("icu_ctl")
        atl = r.get("icu_atl")
        if ctl is not None and atl is not None:
            dt = parse_date(r.get("start_date_local"))
            if dt:
                d_num = (dt - parse_date(runs[0]["start_date_local"])).days
                ctl_data.append(ctl)
                atl_data.append(atl)
                tsb_data.append(ctl - atl)
                dates_num.append(d_num)
                date_labels.append(dt.strftime("%b %y"))

    if ctl_data:
        # Pick ~6 evenly spaced date labels
        step = max(1, len(dates_num) // 6)
        x_labels = [(date_labels[i], dates_num[i])
                    for i in range(0, len(dates_num), step)]

        html += '<h3>Fitness (CTL) / Fatigue (ATL) / Form (TSB)</h3>'
        html += chart.line(
            dates_num, ctl_data, color="#4CAF50",
            x_labels=x_labels,
            extra_lines=[
                (dates_num, atl_data, "#FF5722"),
                (dates_num, tsb_data, "#9C27B0"),
            ]
        )
        html += ('<p class="chart-note">'
                 '<span style="color:#4CAF50">&#9632; CTL (fitness)</span> &nbsp; '
                 '<span style="color:#FF5722">&#9632; ATL (fatigue)</span> &nbsp; '
                 '<span style="color:#9C27B0">&#9632; TSB (form)</span></p>')

        # Current form
        current_tsb = tsb_data[-1]
        if current_tsb < -20:
            form = "Overreaching"
            form_class = "warning"
            form_note = "TSB well below -20. High risk of overtraining. Consider a recovery week."
        elif current_tsb < -10:
            form = "Productive Overload"
            form_class = ""
            form_note = "Building fitness. Monitor fatigue carefully."
        elif current_tsb <= 5:
            form = "Productive"
            form_class = "good"
            form_note = "Good balance of fitness and freshness."
        else:
            form = "Fresh / Detraining"
            form_class = "warning"
            form_note = "Well-rested but fitness may be declining."
        html += (f'<p class="insight {form_class}">Current form: <b>{form}</b> '
                 f'(TSB = {current_tsb:.1f}). {form_note}</p>')
        html += (f'<p class="insight">CTL: {ctl_data[-1]:.1f} | '
                 f'ATL: {atl_data[-1]:.1f}</p>')

        # Acute:chronic ratio
        if ctl_data[-1] > 0:
            ac_ratio = atl_data[-1] / ctl_data[-1]
            ac_class = "warning" if ac_ratio > 1.5 else ("good" if 0.8 <= ac_ratio <= 1.3 else "")
            html += (f'<p class="insight {ac_class}">Acute:Chronic ratio: <b>{ac_ratio:.2f}</b>')
            if ac_ratio > 1.5:
                html += ' &#9888; High spike risk &mdash; ease off to reduce injury chance'
            elif ac_ratio < 0.8:
                html += ' &mdash; Training load low relative to fitness. Ramp carefully.'
            else:
                html += ' &mdash; In the sweet spot (0.8-1.3).'
            html += '</p>'

    # Weekly training load bar chart
    week_loads = {}
    for r in runs:
        dt = parse_date(r.get("start_date_local"))
        tl = r.get("icu_training_load", 0) or 0
        if dt:
            week_key = dt.strftime("%Y-W%W")
            week_loads[week_key] = week_loads.get(week_key, 0) + tl
    if week_loads:
        sorted_weeks = sorted(week_loads.keys())
        # Show last 16 weeks
        recent = sorted_weeks[-16:]
        labels = [w.split("-")[1] for w in recent]
        values = [week_loads[w] for w in recent]
        html += '<h3>Weekly Training Load (last 16 weeks)</h3>'
        html += chart.bar(labels, values, color="#2196F3")

    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Section C: Pace Trends & Progress
# ---------------------------------------------------------------------------

def section_pace_trends(runs, chart):
    html = '<div class="section"><h2>Pace Trends &amp; Progress</h2>'

    # Pace over time scatter + trend
    paces, dates_num, date_labels = [], [], []
    first_dt = parse_date(runs[0].get("start_date_local"))
    for r in runs:
        p = r.get("pace")
        dt = parse_date(r.get("start_date_local"))
        if p and p > 0 and dt and first_dt:
            paces.append(pace_ms_to_minkm(p))
            dates_num.append((dt - first_dt).days)
            date_labels.append(dt.strftime("%b %y"))

    if paces:
        step = max(1, len(dates_num) // 6)
        x_labels = [(date_labels[i], dates_num[i])
                    for i in range(0, len(dates_num), step)]
        y_min = min(paces)
        y_max = max(paces)
        y_labels = [(fmt_pace(v), v) for v in
                    [y_min, y_min + (y_max - y_min) / 3,
                     y_min + (y_max - y_min) * 2 / 3, y_max]]
        html += '<h3>Pace Over Time</h3>'
        html += chart.scatter(dates_num, paces, color="#2196F3",
                              x_labels=x_labels, y_labels=y_labels, trend=True)
        html += '<p class="chart-note">Each dot = one run. Lower = faster. Dashed = trend line.</p>'

        slope, intercept = linear_regression(dates_num, paces)
        if dates_num:
            pace_start = intercept
            pace_end = slope * dates_num[-1] + intercept
            if pace_start > 0:
                pace_change_pct = (pace_end - pace_start) / pace_start * 100
                direction = "faster" if pace_change_pct < 0 else "slower"
                html += (f'<p class="insight">Overall pace trend: '
                         f'<b>{abs(pace_change_pct):.1f}% {direction}</b> '
                         f'over the period ({fmt_pace(pace_start)} &rarr; {fmt_pace(pace_end)}).</p>')

    # Pace at comparable HR
    hr_pace_pairs = []
    for r in runs:
        p = r.get("pace")
        hr = r.get("average_heartrate")
        dt = parse_date(r.get("start_date_local"))
        if p and p > 0 and hr and hr > 0 and dt:
            hr_pace_pairs.append((dt, hr, pace_ms_to_minkm(p)))

    if len(hr_pace_pairs) >= 10:
        html += '<h3>Pace at Comparable HR (Key Progress Indicator)</h3>'
        now = hr_pace_pairs[-1][0]
        recent_cutoff = now - timedelta(weeks=8)
        prior_cutoff = recent_cutoff - timedelta(weeks=8)

        recent = [(hr, p) for dt, hr, p in hr_pace_pairs if dt >= recent_cutoff]
        prior = [(hr, p) for dt, hr, p in hr_pace_pairs
                 if prior_cutoff <= dt < recent_cutoff]

        if recent and prior:
            # Find HR bands with data in both periods
            all_hrs = [hr for _, hr, _ in hr_pace_pairs]
            hr_min = int(min(all_hrs))
            hr_max = int(max(all_hrs))
            band_size = 5
            comparisons = []
            for band_start in range(hr_min, hr_max, band_size):
                band_end = band_start + band_size
                r_paces = [p for h, p in recent if band_start <= h < band_end]
                p_paces = [p for h, p in prior if band_start <= h < band_end]
                if len(r_paces) >= 2 and len(p_paces) >= 2:
                    r_avg = sum(r_paces) / len(r_paces)
                    p_avg = sum(p_paces) / len(p_paces)
                    change_pct = (r_avg - p_avg) / p_avg * 100
                    comparisons.append((band_start, band_end, p_avg, r_avg, change_pct,
                                        len(p_paces), len(r_paces)))

            if comparisons:
                html += '<table class="splits"><tr><th>HR Band</th><th>Prior 8wk Pace</th>'
                html += '<th>Recent 8wk Pace</th><th>Change</th><th>Runs (P/R)</th></tr>'
                total_change = 0
                for bs, be, p_avg, r_avg, chg, np_, nr in comparisons:
                    color = "#4CAF50" if chg < -1 else ("#FF5722" if chg > 1 else "#888")
                    direction = "faster" if chg < 0 else "slower"
                    html += (f'<tr><td>{bs}-{be} bpm</td>'
                             f'<td>{fmt_pace(p_avg)}</td>'
                             f'<td>{fmt_pace(r_avg)}</td>'
                             f'<td style="color:{color}">{abs(chg):.1f}% {direction}</td>'
                             f'<td>{np_}/{nr}</td></tr>')
                    total_change += chg
                html += '</table>'

                avg_change = total_change / len(comparisons)
                if avg_change < -2:
                    verdict = "Progress"
                    verdict_class = "good"
                    verdict_note = "You are getting faster at the same heart rate. Aerobic fitness is improving."
                elif avg_change > 2:
                    verdict = "Regression"
                    verdict_class = "warning"
                    verdict_note = "Pace is slowing at similar heart rates. Consider fatigue, overtraining, or external factors."
                else:
                    verdict = "Maintaining"
                    verdict_class = ""
                    verdict_note = "Pace is stable at similar heart rates. Fitness is maintained."
                html += (f'<p class="insight {verdict_class}"><b>Progress Verdict: {verdict}</b> '
                         f'(avg {abs(avg_change):.1f}% change). {verdict_note}</p>')
            else:
                html += '<p class="insight">Not enough overlapping HR data between periods for comparison.</p>'
        else:
            html += '<p class="insight">Not enough data in recent or prior 8-week window.</p>'

    # Monthly summary table
    monthly = {}
    for r in runs:
        dt = parse_date(r.get("start_date_local"))
        p = r.get("pace")
        hr = r.get("average_heartrate")
        d = r.get("distance", 0)
        if dt and p:
            key = dt.strftime("%Y-%m")
            if key not in monthly:
                monthly[key] = {"paces": [], "hrs": [], "dists": [], "count": 0}
            monthly[key]["paces"].append(pace_ms_to_minkm(p))
            if hr and hr > 0:
                monthly[key]["hrs"].append(hr)
            monthly[key]["dists"].append(d)
            monthly[key]["count"] += 1

    if monthly:
        html += '<h3>Monthly Summary</h3>'
        html += '<table class="splits"><tr><th>Month</th><th>Runs</th><th>Distance</th>'
        html += '<th>Avg Pace</th><th>Avg HR</th></tr>'
        for key in sorted(monthly.keys()):
            m = monthly[key]
            avg_p = sum(m["paces"]) / len(m["paces"])
            avg_hr = sum(m["hrs"]) / len(m["hrs"]) if m["hrs"] else 0
            total_d = sum(m["dists"])
            label = datetime.strptime(key, "%Y-%m").strftime("%b %Y")
            html += (f'<tr><td>{label}</td><td>{m["count"]}</td>'
                     f'<td>{fmt_dist(total_d)} km</td>'
                     f'<td>{fmt_pace(avg_p)}</td>'
                     f'<td>{avg_hr:.0f} bpm</td></tr>')
        html += '</table>'

    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Section D: Weekly Volume & Consistency
# ---------------------------------------------------------------------------

def section_weekly_volume(runs, chart):
    html = '<div class="section"><h2>Weekly Volume &amp; Consistency</h2>'

    # Weekly distance bar chart
    weeks = {}
    for r in runs:
        dt = parse_date(r.get("start_date_local"))
        d = r.get("distance", 0) or 0
        if dt:
            week_key = dt.strftime("%Y-W%W")
            if week_key not in weeks:
                weeks[week_key] = {"dist": 0, "count": 0, "dt": dt}
            weeks[week_key]["dist"] += d
            weeks[week_key]["count"] += 1

    sorted_weeks = sorted(weeks.keys())
    if sorted_weeks:
        recent = sorted_weeks[-16:]
        labels = [w.split("-")[1] for w in recent]
        values = [weeks[w]["dist"] / 1000.0 for w in recent]
        html += '<h3>Weekly Distance (last 16 weeks)</h3>'
        html += chart.bar(labels, values, color="#4CAF50")
        html += '<p class="chart-note">km per week</p>'

        # Volume ramp warning (3-week rolling)
        if len(values) >= 4:
            for i in range(3, len(values)):
                rolling_avg = sum(values[i - 3:i]) / 3
                if rolling_avg > 0 and values[i] > rolling_avg * 1.3:
                    html += (f'<p class="insight warning">&#9888; Week {labels[i]}: '
                             f'{values[i]:.1f} km is {(values[i] / rolling_avg - 1) * 100:.0f}% '
                             f'above 3-week rolling average ({rolling_avg:.1f} km). '
                             f'Watch for injury risk.</p>')

    # Consistency score
    if sorted_weeks:
        last_12 = sorted_weeks[-12:]
        weeks_with_3plus = sum(1 for w in last_12 if weeks[w]["count"] >= 3)
        consistency = weeks_with_3plus / len(last_12) * 100
        html += (f'<p class="insight">Consistency: <b>{consistency:.0f}%</b> of last '
                 f'{len(last_12)} weeks had 3+ runs '
                 f'({weeks_with_3plus}/{len(last_12)} weeks).</p>')

    # Longest gap
    run_dates = sorted([parse_date(r.get("start_date_local")) for r in runs
                        if parse_date(r.get("start_date_local"))])
    if len(run_dates) >= 2:
        max_gap = timedelta(0)
        gap_start = None
        for i in range(1, len(run_dates)):
            gap = run_dates[i] - run_dates[i - 1]
            if gap > max_gap:
                max_gap = gap
                gap_start = run_dates[i - 1]
        if max_gap.days > 0:
            html += (f'<p class="insight">Longest gap: <b>{max_gap.days} days</b> '
                     f'(after {gap_start.strftime("%d %b %Y") if gap_start else "??"}).</p>')

    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Section E: Heart Rate Analysis
# ---------------------------------------------------------------------------

def section_hr_analysis(runs, chart):
    html = '<div class="section"><h2>Heart Rate Analysis</h2>'

    # Avg HR over time with rolling average
    hrs, dates_num, date_labels = [], [], []
    first_dt = parse_date(runs[0].get("start_date_local"))
    for r in runs:
        hr = r.get("average_heartrate")
        dt = parse_date(r.get("start_date_local"))
        if hr and hr > 0 and dt and first_dt:
            hrs.append(hr)
            dates_num.append((dt - first_dt).days)
            date_labels.append(dt.strftime("%b %y"))

    if hrs:
        rolling = rolling_avg(hrs, 4)
        step = max(1, len(dates_num) // 6)
        x_labels = [(date_labels[i], dates_num[i])
                    for i in range(0, len(dates_num), step)]
        html += '<h3>Average HR Per Run</h3>'
        html += chart.line(dates_num, rolling, color="#E91E63", x_labels=x_labels,
                           extra_lines=[(dates_num, hrs, "#F8BBD0")])
        html += ('<p class="chart-note">'
                 '<span style="color:#F8BBD0">&#9632; Individual runs</span> &nbsp; '
                 '<span style="color:#E91E63">&#9632; 4-run rolling average</span></p>')

    # HR efficiency (pace / avg HR) over time
    eff_vals, eff_dates, eff_labels = [], [], []
    for r in runs:
        hr = r.get("average_heartrate")
        p = r.get("pace")
        dt = parse_date(r.get("start_date_local"))
        if hr and hr > 0 and p and p > 0 and dt and first_dt:
            eff = p / hr  # m/s per bpm — higher is more efficient
            eff_vals.append(eff * 1000)  # scale for readability
            eff_dates.append((dt - first_dt).days)
            eff_labels.append(dt.strftime("%b %y"))

    if eff_vals:
        step = max(1, len(eff_dates) // 6)
        x_labels = [(eff_labels[i], eff_dates[i])
                    for i in range(0, len(eff_dates), step)]
        html += '<h3>HR Efficiency (speed per heartbeat)</h3>'
        html += chart.scatter(eff_dates, eff_vals, color="#9C27B0",
                              x_labels=x_labels, trend=True)
        html += '<p class="chart-note">Higher = more efficient. Dashed = trend.</p>'

        slope, _ = linear_regression(eff_dates, eff_vals)
        if slope > 0:
            html += '<p class="insight good">HR efficiency is trending upward &mdash; improving.</p>'
        elif slope < 0:
            html += '<p class="insight warning">HR efficiency is trending downward.</p>'

    # Monthly HR zone shift
    monthly_zones = {}
    zone_colors = ["#4CAF50", "#8BC34A", "#FFC107", "#FF9800", "#FF5722", "#E91E63", "#9C27B0"]
    for r in runs:
        dt = parse_date(r.get("start_date_local"))
        zt = r.get("icu_hr_zone_times")
        if dt and zt:
            key = dt.strftime("%Y-%m")
            if key not in monthly_zones:
                monthly_zones[key] = [0] * 7
            for i in range(min(7, len(zt))):
                monthly_zones[key][i] += (zt[i] or 0) / 60.0

    if monthly_zones:
        sorted_months = sorted(monthly_zones.keys())[-12:]
        labels = [datetime.strptime(m, "%Y-%m").strftime("%b") for m in sorted_months]
        # Normalize to percentages
        series = []
        for z in range(7):
            vals = []
            for m in sorted_months:
                total = sum(monthly_zones[m])
                vals.append(monthly_zones[m][z] / total * 100 if total else 0)
            series.append((f"Z{z + 1}", vals, zone_colors[z]))

        html += '<h3>Monthly HR Zone Distribution (%)</h3>'
        html += chart.stacked_bar(labels, series)
        html += '<p class="chart-note">Shift toward more Z1-Z2 time indicates better polarization.</p>'

    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Section F: Cadence & Stride
# ---------------------------------------------------------------------------

def section_cadence_stride(runs, chart):
    html = '<div class="section"><h2>Cadence &amp; Stride</h2>'

    # Raw cadence from data is single-foot; display as both-feet (*2)
    cads_raw, strides, speeds, dates_num, date_labels = [], [], [], [], []
    first_dt = parse_date(runs[0].get("start_date_local"))
    for r in runs:
        c = r.get("average_cadence")
        s = r.get("average_stride")
        p = r.get("pace")
        dt = parse_date(r.get("start_date_local"))
        if c and c > 60 and s and s > 0 and p and p > 0 and dt and first_dt:
            cads_raw.append(c)
            strides.append(s)
            speeds.append(p)
            dates_num.append((dt - first_dt).days)
            date_labels.append(dt.strftime("%b %y"))

    if cads_raw:
        cads_display = [c * 2 for c in cads_raw]
        step = max(1, len(dates_num) // 6)
        x_labels = [(date_labels[i], dates_num[i])
                    for i in range(0, len(dates_num), step)]

        html += '<h3>Cadence Over Time</h3>'
        html += chart.scatter(dates_num, cads_display, color="#FF9800",
                              x_labels=x_labels, trend=True)
        html += '<p class="chart-note">Steps per minute (both feet). Dashed = trend.</p>'

        html += '<h3>Stride Length Over Time</h3>'
        html += chart.scatter(dates_num, strides, color="#009688",
                              x_labels=x_labels, trend=True)
        html += '<p class="chart-note">Meters per stride. Dashed = trend.</p>'

        # Speed decomposition: speed = (cadence_both_feet / 60) * stride
        avg_cad_display = sum(cads_display) / len(cads_display)
        avg_stride = sum(strides) / len(strides)
        avg_speed = sum(speeds) / len(speeds)
        computed_speed = avg_cad_display / 60 * avg_stride
        html += (f'<p class="insight">Average: cadence {avg_cad_display:.0f} spm '
                 f'&times; stride {avg_stride:.2f} m = '
                 f'{computed_speed:.2f} m/s '
                 f'(actual avg speed: {avg_speed:.2f} m/s, '
                 f'pace {fmt_pace(pace_ms_to_minkm(avg_speed))} /km).</p>')

        slope_c, _ = linear_regression(dates_num, cads_display)
        slope_s, _ = linear_regression(dates_num, strides)
        notes = []
        if slope_c > 0.002:
            notes.append("cadence trending up")
        elif slope_c < -0.002:
            notes.append("cadence trending down")
        if slope_s > 0.0001:
            notes.append("stride length trending up")
        elif slope_s < -0.0001:
            notes.append("stride length trending down")
        if notes:
            html += f'<p class="insight">Trends: {", ".join(notes)}.</p>'

    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Section G: Training Plan to Race
# ---------------------------------------------------------------------------

def section_training_plan(runs, chart):
    html = '<div class="section"><h2>Training Plan &mdash; {name} ({date})</h2>'.format(
        name=RACE_NAME, date=RACE_DATE.strftime("%d %b %Y"))

    weeks_to_race = max(0, (RACE_DATE - TODAY).days // 7)
    days_to_race = (RACE_DATE - TODAY).days
    html += (f'<p class="insight"><b>{days_to_race} days</b> ({weeks_to_race} weeks) '
             f'to race day.</p>')

    # Current volume baseline from last 4 weeks
    weeks = {}
    for r in runs:
        dt = parse_date(r.get("start_date_local"))
        d = r.get("distance", 0) or 0
        t = r.get("moving_time", 0) or 0
        tl = r.get("icu_training_load", 0) or 0
        if dt:
            wk = dt.strftime("%Y-W%W")
            if wk not in weeks:
                weeks[wk] = {"dist": 0, "count": 0, "time": 0, "load": 0}
            weeks[wk]["dist"] += d
            weeks[wk]["count"] += 1
            weeks[wk]["time"] += t
            weeks[wk]["load"] += tl

    sorted_wks = sorted(weeks.keys())
    if len(sorted_wks) >= 4:
        recent_4 = sorted_wks[-4:]
        base_km = sum(weeks[w]["dist"] for w in recent_4) / len(recent_4) / 1000
        base_time_h = sum(weeks[w]["time"] for w in recent_4) / len(recent_4) / 3600
        base_runs = sum(weeks[w]["count"] for w in recent_4) / len(recent_4)
        base_load = sum(weeks[w]["load"] for w in recent_4) / len(recent_4)
    else:
        base_km = 40
        base_time_h = 4
        base_runs = 3
        base_load = 100

    html += '<h3>Current Training Baseline (last 4 weeks avg)</h3>'
    html += '<div class="card-grid">'
    html += f'<div class="stat-card"><div class="stat-value">{base_km:.0f} km</div><div class="stat-label">Weekly Distance</div></div>'
    html += f'<div class="stat-card"><div class="stat-value">{base_time_h:.1f} h</div><div class="stat-label">Weekly Time</div></div>'
    html += f'<div class="stat-card"><div class="stat-value">{base_runs:.1f}</div><div class="stat-label">Runs / Week</div></div>'
    html += f'<div class="stat-card"><div class="stat-value">{base_load:.0f}</div><div class="stat-label">Weekly Load</div></div>'
    html += '</div>'

    # Build the week-by-week plan
    # Structure: 3 build + 1 recovery, repeated. Last 2 weeks = taper.
    taper_weeks = 2
    race_week_num = weeks_to_race  # week 0 = race week
    buildable_weeks = max(0, weeks_to_race - taper_weeks)

    # Generate plan for each week
    plan_labels = []
    plan_km = []
    plan_types = []  # "build", "recovery", "taper", "race"
    plan_colors = []

    # Progressive overload: build from current base to ~peak, then taper
    # Peak target: ~130% of current base (don't exceed 10% per build cycle)
    peak_km = base_km * 1.3
    if buildable_weeks > 0:
        km_per_build_week = (peak_km - base_km) / buildable_weeks * 1.3  # accelerate slightly
    else:
        km_per_build_week = 0

    current_build_km = base_km
    cycle_pos = 0  # 0,1,2 = build, 3 = recovery

    for w in range(weeks_to_race + 1):
        week_date = TODAY + timedelta(weeks=w)
        label = week_date.strftime("%d/%m")

        if w >= weeks_to_race:
            # Race week
            plan_labels.append(label)
            plan_km.append(6.7)  # just race day
            plan_types.append("race")
            plan_colors.append("#FF5722")
        elif w >= buildable_weeks:
            # Taper weeks
            taper_pos = w - buildable_weeks  # 0 or 1
            taper_factor = 0.65 if taper_pos == 0 else 0.4
            plan_labels.append(label)
            plan_km.append(current_build_km * taper_factor)
            plan_types.append("taper")
            plan_colors.append("#FFC107")
        else:
            if cycle_pos < 3:
                # Build week
                current_build_km = min(peak_km, base_km + km_per_build_week * (w + 1))
                plan_labels.append(label)
                plan_km.append(current_build_km)
                plan_types.append("build")
                plan_colors.append("#4CAF50")
            else:
                # Recovery week (50% volume)
                plan_labels.append(label)
                plan_km.append(current_build_km * 0.5)
                plan_types.append("recovery")
                plan_colors.append("#2196F3")
            cycle_pos = (cycle_pos + 1) % 4

    if plan_labels:
        html += '<h3>Week-by-Week Volume Plan</h3>'
        html += chart.bar(plan_labels, plan_km, colors=plan_colors)
        html += ('<p class="chart-note">'
                 '<span style="color:#4CAF50">&#9632; Build</span> &nbsp; '
                 '<span style="color:#2196F3">&#9632; Recovery (50%)</span> &nbsp; '
                 '<span style="color:#FFC107">&#9632; Taper</span> &nbsp; '
                 '<span style="color:#FF5722">&#9632; Race</span></p>')

    # Week-by-week table
    html += '<table class="splits"><tr><th>Week of</th><th>Type</th><th>Target km</th><th>Target Time</th><th>Notes</th></tr>'
    for i, (lbl, km, wtype) in enumerate(zip(plan_labels, plan_km, plan_types)):
        time_h = km / base_km * base_time_h if base_km > 0 else 0
        notes = ""
        if wtype == "build":
            if i < 4:
                notes = "Build aerobic base. 80% easy, one long run."
            elif i < 10:
                notes = "Increase long run. Add back-to-back weekend runs."
            else:
                notes = "Peak volume. Practice race-pace 6.7km repeats."
        elif wtype == "recovery":
            notes = "Half volume. Easy runs only. Focus on sleep and nutrition."
        elif wtype == "taper":
            week_n = i - buildable_weeks
            if week_n == 0:
                notes = "Reduce to 65%. Keep one race-pace session."
            else:
                notes = "Reduce to 40%. Short easy runs. Rest legs."
        elif wtype == "race":
            notes = "Race day! Start conservative. Target ~50min per 6.7km yard."

        type_display = {"build": "Build", "recovery": "Recovery", "taper": "Taper", "race": "Race"}
        color = {"build": "#4CAF50", "recovery": "#2196F3", "taper": "#FFC107", "race": "#FF5722"}
        html += (f'<tr><td>{lbl}</td>'
                 f'<td style="color:{color[wtype]}"><b>{type_display[wtype]}</b></td>'
                 f'<td>{km:.0f}</td>'
                 f'<td>{time_h:.1f}h</td>'
                 f'<td>{notes}</td></tr>')
    html += '</table>'

    # Backyard ultra specific prep
    html += '<h3>Backyard Ultra Specifics</h3>'

    # What pace do they need for 6.7km/hour?
    # Must complete 6.706km in under 60 minutes = pace of ~8:57/km
    target_pace_minkm = 60.0 / 6.706
    last = runs[-1]
    current_pace = pace_ms_to_minkm(last.get("pace", 0))
    pace_margin = target_pace_minkm - current_pace if current_pace else 0

    html += '<div class="card-grid">'
    html += f'<div class="stat-card"><div class="stat-value">{fmt_pace(target_pace_minkm)}</div><div class="stat-label">Max Pace per Yard</div></div>'
    html += f'<div class="stat-card"><div class="stat-value">{fmt_pace(current_pace)}</div><div class="stat-label">Last Run Avg Pace</div></div>'
    html += f'<div class="stat-card"><div class="stat-value">{pace_margin:.1f} min</div><div class="stat-label">Margin per km</div></div>'
    html += f'<div class="stat-card"><div class="stat-value">{pace_margin * 6.706:.0f} min</div><div class="stat-label">Rest per Yard</div></div>'
    html += '</div>'

    if pace_margin > 2:
        html += (f'<p class="insight good">At last-run pace ({fmt_pace(current_pace)}/km), '
                 f'you finish each 6.7km yard in ~{current_pace * 6.706:.0f} min, '
                 f'leaving <b>{pace_margin * 6.706:.0f} min rest</b> per hour. '
                 f'Comfortable margin.</p>')
    elif pace_margin > 0.5:
        html += (f'<p class="insight">At last-run pace ({fmt_pace(current_pace)}/km), '
                 f'you have ~{pace_margin * 6.706:.0f} min rest per yard. '
                 f'Workable, but tighter than ideal for later yards.</p>')
    else:
        html += (f'<p class="insight warning">At last-run pace ({fmt_pace(current_pace)}/km), '
                 f'rest margin is only {pace_margin * 6.706:.0f} min per yard. '
                 f'Need to improve aerobic pace or this will be unsustainable.</p>')

    # Longest runs analysis — are they doing enough time on feet?
    long_runs = sorted([(r.get("moving_time", 0) or 0, r.get("distance", 0) or 0,
                         r.get("start_date_local", ""))
                        for r in runs], reverse=True)[:5]
    html += '<h3>Longest Runs (Time on Feet)</h3>'
    html += '<table class="splits"><tr><th>#</th><th>Duration</th><th>Distance</th><th>Date</th></tr>'
    for i, (t, d, date_s) in enumerate(long_runs):
        dt = parse_date(date_s)
        date_disp = dt.strftime("%d %b %Y") if dt else "?"
        html += f'<tr><td>{i + 1}</td><td>{fmt_duration(t)}</td><td>{fmt_dist(d)} km</td><td>{date_disp}</td></tr>'
    html += '</table>'

    max_time_h = long_runs[0][0] / 3600 if long_runs else 0
    if max_time_h < 2.5:
        html += ('<p class="insight warning">Longest run is only '
                 f'{max_time_h:.1f}h. For a backyard ultra, build to 3-4h long runs. '
                 f'Practice eating and drinking during long efforts.</p>')
    elif max_time_h < 4:
        html += (f'<p class="insight">Longest run: {max_time_h:.1f}h. Good start. '
                 f'Aim to hit 4h+ at least twice before taper.</p>')
    else:
        html += (f'<p class="insight good">Longest run: {max_time_h:.1f}h. '
                 f'Solid time-on-feet foundation for a backyard ultra.</p>')

    # 3:1 cycle adherence check from actual data
    if len(sorted_wks) >= 8:
        recent_8 = sorted_wks[-8:]
        wk_dists = [weeks[w]["dist"] / 1000 for w in recent_8]
        html += '<h3>Recent 3:1 Cycle Adherence</h3>'
        html += '<table class="splits"><tr><th>Week</th><th>Distance</th><th>vs Previous</th><th>Pattern</th></tr>'
        for i, w in enumerate(recent_8):
            km = weeks[w]["dist"] / 1000
            dt = weeks[w].get("dt") if isinstance(weeks[w], dict) and "dt" in weeks[w] else None
            wk_label = w
            if i > 0:
                prev_km = wk_dists[i - 1]
                change = (km - prev_km) / prev_km * 100 if prev_km > 0 else 0
                is_recovery = km < prev_km * 0.65
                pattern = "Recovery" if is_recovery else ("Build" if change > -10 else "Drop")
                color = "#2196F3" if is_recovery else ("#4CAF50" if change >= 0 else "#FF9800")
                html += (f'<tr><td>{wk_label}</td><td>{km:.0f} km</td>'
                         f'<td style="color:{color}">{change:+.0f}%</td>'
                         f'<td style="color:{color}">{pattern}</td></tr>')
            else:
                html += f'<tr><td>{wk_label}</td><td>{km:.0f} km</td><td>--</td><td>--</td></tr>'
        html += '</table>'

    html += '</div>'
    return html

# ---------------------------------------------------------------------------
# Metrics export for Claude coaching
# ---------------------------------------------------------------------------

def build_metrics(runs):
    """Build a structured metrics dict for the Claude coaching layer."""
    last = runs[-1]
    dt_last = parse_date(last.get("start_date_local"))
    first_dt = parse_date(runs[0].get("start_date_local"))

    weeks_to_race = max(0, (RACE_DATE - TODAY).days // 7)

    metrics = {
        "total_runs": len(runs),
        "date_range": {
            "first": runs[0].get("start_date_local", ""),
            "last": last.get("start_date_local", ""),
        },
        "race": {
            "name": RACE_NAME,
            "date": RACE_DATE.strftime("%Y-%m-%d"),
            "weeks_out": weeks_to_race,
            "training_structure": "3 weeks build + 1 week recovery (50% volume)",
            "taper": "2 weeks before race (progressive volume reduction)",
        },
        "last_run": {
            "date": last.get("start_date_local", ""),
            "distance_km": round((last.get("distance", 0) or 0) / 1000, 2),
            "duration_min": round((last.get("moving_time", 0) or 0) / 60, 1),
            "pace_minkm": fmt_pace(pace_ms_to_minkm(last.get("pace", 0))),
            "avg_hr": last.get("average_heartrate"),
            "max_hr": last.get("max_heartrate"),
            "elevation_m": last.get("total_elevation_gain"),
            "training_load": last.get("icu_training_load"),
            "cadence_spm": round(last.get("average_cadence", 0) * 2, 1) if last.get("average_cadence") else None,
            "stride": last.get("average_stride"),
        },
    }

    # CTL/ATL/TSB
    ctl = last.get("icu_ctl")
    atl = last.get("icu_atl")
    if ctl is not None and atl is not None:
        tsb = ctl - atl
        metrics["fitness"] = {
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(tsb, 1),
            "ac_ratio": round(atl / ctl, 2) if ctl > 0 else None,
        }

    # HR drift from stream
    stream = load_stream(last.get("id", ""))
    if stream:
        hr_s = stream.get("heartrate", [])
        time_s = stream.get("time", [])
        if hr_s and time_s:
            warmup, cooldown = 300, 120
            max_time = max(time_s) if time_s else 0
            valid = [(t, h) for t, h in zip(time_s, hr_s)
                     if h and h > 0 and warmup <= t <= max_time - cooldown]
            if len(valid) > 20:
                mid = len(valid) // 2
                first_half = [h for _, h in valid[:mid]]
                second_half = [h for _, h in valid[mid:]]
                avg1 = sum(first_half) / len(first_half)
                avg2 = sum(second_half) / len(second_half)
                metrics["last_run"]["hr_drift_pct"] = round((avg2 - avg1) / avg1 * 100, 1)

    # HR zone distribution for last run
    zt = last.get("icu_hr_zone_times")
    if zt:
        total = sum(t for t in zt if t) or 1
        metrics["last_run"]["hr_zones_pct"] = {
            f"Z{i + 1}": round((zt[i] or 0) / total * 100, 1) for i in range(len(zt))
        }
        easy = ((zt[0] or 0) + (zt[1] or 0)) / total * 100
        metrics["last_run"]["easy_pct"] = round(easy, 1)

    # Pace trend
    pace_data = [(parse_date(r.get("start_date_local")), r.get("pace"))
                 for r in runs
                 if r.get("pace") and parse_date(r.get("start_date_local"))]
    if len(pace_data) >= 5 and first_dt:
        xs = [(dt - first_dt).days for dt, _ in pace_data]
        ys = [pace_ms_to_minkm(p) for _, p in pace_data]
        slope, intercept = linear_regression(xs, ys)
        pace_start = intercept
        pace_end = slope * xs[-1] + intercept
        if pace_start > 0:
            metrics["pace_trend_pct"] = round((pace_end - pace_start) / pace_start * 100, 1)

    # Pace at comparable HR (progress verdict)
    hr_pace = []
    for r in runs:
        p = r.get("pace")
        hr = r.get("average_heartrate")
        dt = parse_date(r.get("start_date_local"))
        if p and p > 0 and hr and hr > 0 and dt:
            hr_pace.append((dt, hr, pace_ms_to_minkm(p)))
    if hr_pace and dt_last:
        recent_cutoff = dt_last - timedelta(weeks=8)
        prior_cutoff = recent_cutoff - timedelta(weeks=8)
        recent = [(hr, p) for dt, hr, p in hr_pace if dt >= recent_cutoff]
        prior = [(hr, p) for dt, hr, p in hr_pace if prior_cutoff <= dt < recent_cutoff]
        if recent and prior:
            all_hrs = [hr for _, hr, _ in hr_pace]
            changes = []
            for bs in range(int(min(all_hrs)), int(max(all_hrs)), 5):
                be = bs + 5
                r_p = [p for h, p in recent if bs <= h < be]
                p_p = [p for h, p in prior if bs <= h < be]
                if len(r_p) >= 2 and len(p_p) >= 2:
                    changes.append((sum(r_p) / len(r_p) - sum(p_p) / len(p_p))
                                   / (sum(p_p) / len(p_p)) * 100)
            if changes:
                avg_chg = sum(changes) / len(changes)
                if avg_chg < -2:
                    metrics["progress_verdict"] = "Progress"
                elif avg_chg > 2:
                    metrics["progress_verdict"] = "Regression"
                else:
                    metrics["progress_verdict"] = "Maintaining"
                metrics["progress_change_pct"] = round(avg_chg, 1)

    # Weekly volume stats
    weeks = {}
    for r in runs:
        dt = parse_date(r.get("start_date_local"))
        d = r.get("distance", 0) or 0
        if dt:
            wk = dt.strftime("%Y-W%W")
            if wk not in weeks:
                weeks[wk] = {"dist": 0, "count": 0}
            weeks[wk]["dist"] += d
            weeks[wk]["count"] += 1
    if weeks:
        sorted_wks = sorted(weeks.keys())
        recent_4 = sorted_wks[-4:]
        avg_weekly_km = sum(weeks[w]["dist"] for w in recent_4) / len(recent_4) / 1000
        avg_runs_week = sum(weeks[w]["count"] for w in recent_4) / len(recent_4)
        metrics["volume"] = {
            "avg_weekly_km_last4": round(avg_weekly_km, 1),
            "avg_runs_per_week_last4": round(avg_runs_week, 1),
        }
        last_12 = sorted_wks[-12:]
        consistent = sum(1 for w in last_12 if weeks[w]["count"] >= 3)
        metrics["volume"]["consistency_pct"] = round(consistent / len(last_12) * 100, 0)

        # Weeks since recovery: walk backwards, count until a week is <65% of prior
        wk_dists = [weeks[w]["dist"] for w in sorted_wks]
        weeks_since_recovery = 0
        for i in range(len(wk_dists) - 1, 0, -1):
            if wk_dists[i - 1] > 0 and wk_dists[i] < wk_dists[i - 1] * 0.65:
                break
            weeks_since_recovery += 1
        metrics["volume"]["weeks_since_recovery"] = weeks_since_recovery

        # Load ramp: % change between avg of last 3 weeks vs prior 3 weeks
        if len(sorted_wks) >= 6:
            recent_3 = sorted_wks[-3:]
            prior_3 = sorted_wks[-6:-3]
            avg_recent = sum(weeks[w]["dist"] for w in recent_3) / 3
            avg_prior = sum(weeks[w]["dist"] for w in prior_3) / 3
            if avg_prior > 0:
                metrics["volume"]["load_ramp_pct"] = round((avg_recent - avg_prior) / avg_prior * 100, 1)

    # Pace trend over last 4 weeks
    four_weeks_ago = TODAY - timedelta(weeks=4)
    recent_pace_data = [(parse_date(r.get("start_date_local")), r.get("pace"))
                        for r in runs
                        if r.get("pace") and parse_date(r.get("start_date_local"))
                        and parse_date(r.get("start_date_local")) >= four_weeks_ago]
    if len(recent_pace_data) >= 3 and first_dt:
        rxs = [(dt - first_dt).days for dt, _ in recent_pace_data]
        rys = [pace_ms_to_minkm(p) for _, p in recent_pace_data]
        rslope, rintercept = linear_regression(rxs, rys)
        rpace_start = rintercept + rslope * rxs[0]
        rpace_end = rintercept + rslope * rxs[-1]
        if rpace_start > 0:
            metrics["pace_trend_last4w"] = round((rpace_end - rpace_start) / rpace_start * 100, 1)

    # Days since last run
    if dt_last:
        metrics["days_since_last_run"] = (TODAY - dt_last).days

    # Longest run stats
    long_runs = sorted([(r.get("moving_time", 0) or 0, r.get("distance", 0) or 0)
                        for r in runs], reverse=True)[:3]
    if long_runs:
        metrics["longest_runs_hours"] = [round(t / 3600, 1) for t, _ in long_runs]
        metrics["longest_runs_km"] = [round(d / 1000, 1) for _, d in long_runs]

    # Cadence/stride summary
    cads = [r.get("average_cadence") for r in runs
            if r.get("average_cadence") and r["average_cadence"] > 60]
    strs = [r.get("average_stride") for r in runs
            if r.get("average_stride") and r["average_stride"] > 0]
    if cads:
        metrics["avg_cadence_spm"] = round(sum(cads) / len(cads) * 2, 1)
    if strs:
        metrics["avg_stride"] = round(sum(strs) / len(strs), 3)

    # Time-scoped data for panel discussions
    def run_summary(r):
        dt_r = parse_date(r.get("start_date_local"))
        p = r.get("pace")
        return {
            "date": r.get("start_date_local", ""),
            "distance_km": round((r.get("distance", 0) or 0) / 1000, 2),
            "duration_min": round((r.get("moving_time", 0) or 0) / 60, 1),
            "pace_minkm": fmt_pace(pace_ms_to_minkm(p)) if p else None,
            "avg_hr": r.get("average_heartrate"),
            "training_load": r.get("icu_training_load"),
            "elevation_m": r.get("total_elevation_gain"),
            "cadence_spm": round(r.get("average_cadence", 0) * 2, 1) if r.get("average_cadence") else None,
        }

    week_ago = TODAY - timedelta(days=7)
    month_ago = TODAY - timedelta(days=30)

    week_runs = [r for r in runs if parse_date(r.get("start_date_local")) and parse_date(r.get("start_date_local")) >= week_ago]
    month_runs = [r for r in runs if parse_date(r.get("start_date_local")) and parse_date(r.get("start_date_local")) >= month_ago]

    def aggregate_runs(run_list):
        if not run_list:
            return {"count": 0}
        total_dist = sum((r.get("distance", 0) or 0) for r in run_list)
        total_load = sum((r.get("icu_training_load", 0) or 0) for r in run_list)
        total_elev = sum((r.get("total_elevation_gain", 0) or 0) for r in run_list)
        paces = [pace_ms_to_minkm(r["pace"]) for r in run_list if r.get("pace") and r["pace"] > 0]
        hrs = [r["average_heartrate"] for r in run_list if r.get("average_heartrate") and r["average_heartrate"] > 0]
        return {
            "count": len(run_list),
            "total_distance_km": round(total_dist / 1000, 2),
            "avg_pace_minkm": fmt_pace(sum(paces) / len(paces)) if paces else None,
            "avg_hr": round(sum(hrs) / len(hrs), 1) if hrs else None,
            "total_load": round(total_load, 1),
            "total_elevation_m": round(total_elev, 1),
            "runs": [run_summary(r) for r in run_list],
        }

    metrics["last_week"] = aggregate_runs(week_runs)
    metrics["last_month"] = aggregate_runs(month_runs)

    # Weekly breakdown for last_month
    if month_runs:
        week_buckets = {}
        for r in month_runs:
            dt_r = parse_date(r.get("start_date_local"))
            if dt_r:
                wk = dt_r.strftime("%Y-W%W")
                if wk not in week_buckets:
                    week_buckets[wk] = []
                week_buckets[wk].append(r)
        metrics["last_month"]["weekly_breakdown"] = {
            wk: aggregate_runs(wk_runs) for wk, wk_runs in sorted(week_buckets.items())
        }

    return metrics

# ---------------------------------------------------------------------------
# Claude coaching layer
# ---------------------------------------------------------------------------

COACH_PERSONAS = {
    "Ultrarunning Coach": "#00FF41",
    "Marathon Coach": "#00FFFF",
    "Backyard Ultra World Champion": "#FF00FF",
    "Sports Physio": "#FFD600",
}

TIME_SECTIONS = [
    {
        "key": "last_run",
        "title": "Last Run",
        "focus": (
            "Discuss this runner's MOST RECENT RUN in detail. "
            "What went well? What are the warning signs? "
            "Analyze pace, HR, HR drift, cadence, elevation, and training load. "
            "Compare to their recent averages where relevant."
        ),
        "metrics_keys": ["last_run", "fitness", "avg_cadence_spm", "avg_stride", "race"],
    },
    {
        "key": "last_week",
        "title": "Last Week",
        "focus": (
            "Discuss this runner's LAST 7 DAYS of training. "
            "Was the volume appropriate? How is the load distribution? "
            "Are they recovering enough between runs? "
            "Look at the weekly pattern and consistency."
        ),
        "metrics_keys": ["last_week", "fitness", "volume", "race"],
    },
    {
        "key": "last_month",
        "title": "Last Month",
        "focus": (
            "Discuss this runner's LAST 30 DAYS of training. "
            "Are they following the 3:1 build/recovery cycle? "
            "How is the weekly volume trending? "
            "Look at the weekly breakdown and progression."
        ),
        "metrics_keys": ["last_month", "volume", "fitness", "pace_trend_pct", "progress_verdict", "progress_change_pct", "race"],
    },
    {
        "key": "big_picture",
        "title": "Big Picture",
        "focus": (
            "Discuss the runner's OVERALL trajectory toward their backyard ultra goal. "
            "Are they on track? What are the biggest risks? "
            "CTL/ATL/TSB trends, pace progress verdict, longest runs, "
            "and what needs to change in the remaining weeks."
        ),
        "metrics_keys": None,
    },
]

CONVERSATION_SYSTEM_PROMPT = (
    "You are simulating a coaching panel discussion between four experts analyzing a runner's data. "
    "The panelists are: Ultrarunning Coach, Marathon Coach, Backyard Ultra World Champion, and Sports Physio. "
    "\n\n"
    "The runner's goal is a BACKYARD ULTRA in early July 2026. "
    "They train in 3-week build / 1-week recovery (50% volume) cycles. "
    "Account for a 2-week taper before the race and adequate rest after any races. "
    "\n\n"
    "IMPORTANT: Cadence values are both-feet (steps per minute). "
    "Walking cadence is typically 100-120 spm. If cadence is in this range during a run, "
    "it likely indicates walking segments — mention this if relevant, don't confuse it with running cadence issues. "
    "Normal running cadence is 160-190 spm. "
    "\n\n"
    "FORMAT: Write as a natural conversation. Each speaker line MUST start with [Speaker Name] "
    "followed by their commentary. Speakers should reference, agree with, build on, or "
    "respectfully challenge each other's points. "
    "Keep it to 4-8 speaker lines total. Be direct and reference specific numbers from the data. "
    "No markdown headers, no bullet points. "
    "\n\n"
    "Example of the expected output style (do NOT copy this content — use the actual data):\n\n"
    "[Ultrarunning Coach] That 14.2 km long run at 6:32/km is solid — "
    "the HR staying at 142 bpm average tells me the aerobic engine is there. "
    "But I notice the HR drift was +7.3%, which means the last third was harder than it should have been. "
    "Hydration and fueling practice would help.\n\n"
    "[Sports Physio] The drift concerns me too, and I'd flag the cadence at 156 spm — "
    "that's low for someone running 6:30 pace. We typically want 170+ to reduce ground contact time "
    "and lower injury risk. A cadence drill twice a week would pay dividends.\n\n"
    "[Marathon Coach] Agreed on cadence, but let's not lose sight of the bigger picture: "
    "CTL is at 38 and they need to be closer to 50 by race week. "
    "That means the weekly volume needs to ramp from 42 km to at least 55 km over the next 8 weeks. "
    "I'd add a second easy run on Wednesdays.\n\n"
    "[Backyard Ultra World Champion] All good points. For a backyard ultra specifically, "
    "I'd prioritize the long run over total weekly volume. Getting one 3.5-4 hour effort in "
    "every two weeks matters more than hitting 55 km weeks. "
    "And practice eating real food at race pace — gels alone won't cut it past yard 10.\n"
)


def parse_conversation(raw_text):
    """Parse [Speaker Name] text format into list of (name, color, text)."""
    lines = []
    current_name = None
    current_text = []

    for line in raw_text.split("\n"):
        match = re.match(r"^\[([^\]]+)\]\s*(.*)", line)
        if match:
            if current_name is not None:
                lines.append((current_name, COACH_PERSONAS.get(current_name, "#666"),
                               "\n".join(current_text).strip()))
            current_name = match.group(1)
            current_text = [match.group(2)]
        elif current_name is not None and line.strip():
            current_text.append(line)

    if current_name is not None and current_text:
        lines.append((current_name, COACH_PERSONAS.get(current_name, "#666"),
                       "\n".join(current_text).strip()))

    return lines


def filter_metrics(metrics, keys):
    """Return a subset of metrics containing only the specified top-level keys."""
    if keys is None:
        return metrics
    filtered = {}
    for k in keys:
        if k in metrics:
            filtered[k] = metrics[k]
    # Always include context keys
    for k in ("total_runs", "date_range", "days_since_last_run"):
        if k in metrics:
            filtered[k] = metrics[k]
    return filtered


def build_rag_query(section: dict, section_metrics: dict) -> str:
    """Build retrieval query from section focus + key metric signals."""
    parts = [section["focus"]]
    signals = []

    lr = section_metrics.get("last_run", {})
    if lr.get("hr_drift_pct") and lr["hr_drift_pct"] > 5:
        signals.append("cardiac drift")
    if lr.get("avg_cadence_spm") and lr["avg_cadence_spm"] < 165:
        signals.append("low running cadence")

    fitness = section_metrics.get("fitness", {})
    if fitness.get("tsb") and fitness["tsb"] < -20:
        signals.append("high fatigue negative TSB")
    if fitness.get("acute_chronic_ratio") and fitness["acute_chronic_ratio"] > 1.3:
        signals.append("elevated acute chronic workload ratio injury risk")

    race = section_metrics.get("race", {})
    if race.get("race_name"):
        signals.append(race["race_name"].lower())

    if signals:
        parts.append("Key topics: " + ", ".join(signals))

    return " ".join(parts)


def get_panel_discussions(metrics, model="sonnet", thinking_budget=10000, use_rag=True):
    """Call claude CLI for each time section. Returns list of (section_title, [(name, color, text)])."""
    discussions = []
    prior_discussions = []

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    timeout = 300 if model == "opus" else 90

    if use_rag:
        try:
            import rag as rag_module
        except ImportError:
            print("  rag module not available — falling back to base knowledge")
            use_rag = False

    sent_chunk_ids = set()

    for section in TIME_SECTIONS:
        section_metrics = filter_metrics(metrics, section.get("metrics_keys"))
        metrics_str = json.dumps(section_metrics, indent=2)

        # RAG retrieval
        rag_context = ""
        if use_rag:
            try:
                query_text = build_rag_query(section, section_metrics)
                results = rag_module.query(query_text, top_k=5,
                                           exclude_chunk_ids=list(sent_chunk_ids))
                if results:
                    rag_context = rag_module.format_context(results)
                    sent_chunk_ids.update(r["chunk_id"] for r in results)
            except Exception as e:
                print(f"  RAG retrieval failed for {section['title']}: {e}")

        user_prompt = f"FOCUS FOR THIS SECTION: {section['focus']}\n\n"
        if rag_context:
            user_prompt += f"RELEVANT COACHING KNOWLEDGE:\n{rag_context}\n\n"
        if prior_discussions:
            user_prompt += "Previous discussion:\n" + "\n\n".join(prior_discussions) + "\n\n"
        user_prompt += f"Runner data:\n{metrics_str}"

        cmd = ["claude", "--model", model, "--system-prompt", CONVERSATION_SYSTEM_PROMPT,
               "-p", user_prompt]
        if model == "opus":
            cmd += ["--thinking-budget", str(thinking_budget)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout,
                encoding="utf-8", env=env,
            )
            if result.returncode == 0 and result.stdout.strip():
                raw_output = result.stdout.strip()
                prior_discussions.append(f"[{section['title']}]\n{raw_output}")
                conversation = parse_conversation(raw_output)
                if conversation:
                    discussions.append((section["title"], conversation))
                else:
                    print(f"  {section['title']}: could not parse conversation")
            else:
                print(f"  {section['title']}: claude returned code {result.returncode}")
        except FileNotFoundError:
            print("  claude CLI not found — skipping AI commentary")
            return []
        except subprocess.TimeoutExpired:
            print(f"  {section['title']}: timeout")
        except Exception as e:
            print(f"  {section['title']}: {e}")

    return discussions

# ---------------------------------------------------------------------------
# Technical term tooltips
# ---------------------------------------------------------------------------

GLOSSARY = {
    "HR drift": {
        "text": "Heart rate creeping upward during a steady-effort run. >5% drift suggests aerobic base needs work.",
        "url": "https://www.trainingpeaks.com/learn/articles/cardiac-drift/",
    },
    "cardiac drift": {
        "text": "Gradual rise in heart rate at constant effort due to dehydration, heat, or fatigue. Same concept as HR drift.",
    },
    "aerobic decoupling": {
        "text": "The divergence between heart rate and pace over a run. Low decoupling (<5%) indicates strong aerobic fitness.",
        "url": "https://www.trainingpeaks.com/learn/articles/aerobic-decoupling/",
    },
    "CTL": {
        "text": "Chronic Training Load — your fitness. 42-day exponentially weighted average of daily training load.",
    },
    "ATL": {
        "text": "Acute Training Load — your fatigue. 7-day exponentially weighted average of daily training load.",
    },
    "TSB": {
        "text": "Training Stress Balance (CTL minus ATL). Positive = fresh, negative = fatigued. Race-ready zone: +5 to +15.",
    },
    "acute:chronic ratio": {
        "text": "ATL divided by CTL. Sweet spot is 0.8-1.3. Above 1.5 signals high injury risk from a training spike.",
    },
    "training load": {
        "text": "A single-number measure of how hard a session was, combining duration and intensity (HRSS or TRIMP-based).",
    },
    "Z1": {"text": "Heart rate Zone 1 — very easy recovery effort. Builds base without fatigue."},
    "Z2": {"text": "Heart rate Zone 2 — easy aerobic effort. The primary zone for building endurance."},
    "Z3": {"text": "Heart rate Zone 3 — moderate/tempo effort. The 'grey zone' — harder than easy but not hard enough to build speed."},
    "Z4": {"text": "Heart rate Zone 4 — threshold effort. Sustainable for 20-60 minutes. Builds lactate clearance."},
    "Z5": {"text": "Heart rate Zone 5 — VO2max effort. Hard intervals, 3-8 minutes. Builds maximal aerobic capacity."},
    "3:1 cycle": {
        "text": "Three weeks of progressive training load followed by one recovery week at ~50% volume. Allows adaptation without overtraining.",
    },
    "polarized training": {
        "text": "Training distribution where ~80% is easy (Z1-Z2) and ~20% is hard (Z4-Z5), with minimal time in Z3.",
    },
}

def apply_tooltips(text):
    """Wrap first occurrence of each glossary term in a tooltip span. Longest-match-first."""
    sorted_terms = sorted(GLOSSARY.keys(), key=len, reverse=True)
    used = set()
    for term in sorted_terms:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        match = pattern.search(text)
        if match and term.lower() not in used:
            entry = GLOSSARY[term]
            tooltip_text = entry["text"].replace('"', "&quot;")
            link_html = ""
            if entry.get("url"):
                link_html = f'<a class="tooltip-link" href="{entry["url"]}" target="_blank">Learn more</a>'
            replacement = (
                f'<span class="has-tooltip">{match.group(0)}'
                f'<span class="tooltip-popup">{tooltip_text}{link_html}</span></span>'
            )
            text = text[:match.start()] + replacement + text[match.end():]
            used.add(term.lower())
    return text

# ---------------------------------------------------------------------------
# HTML assembly
# ---------------------------------------------------------------------------

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
    font-family: 'Lucida Console', 'Consolas', monospace;
    background: #000000; color: #00FF00; line-height: 1.6;
    max-width: 900px; margin: 0 auto; padding: 24px;
}
h1 { font-size: 28px; margin-bottom: 8px; color: #00FF41; }
h2 { font-size: 22px; margin: 24px 0 12px; color: #00FF41; border-bottom: 2px solid #1a1a1a; padding-bottom: 6px; }
h3 { font-size: 16px; margin: 18px 0 8px; color: #00FFFF; }
.subtitle { color: #888; font-size: 14px; margin-bottom: 24px; }
.section { background: #0a0a0a; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; border: 1px solid #1a1a1a; }
.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin: 12px 0; }
.stat-card { background: #111; border-radius: 6px; padding: 12px; text-align: center; }
.stat-value { font-size: 18px; font-weight: 600; color: #e0e0e0; }
.stat-label { font-size: 12px; color: #888; margin-top: 2px; }
.insight { background: #111; border-left: 3px solid #00FFFF; padding: 8px 12px; margin: 8px 0; border-radius: 0 4px 4px 0; font-size: 14px; }
.insight.good { border-left-color: #00FF41; }
.insight.warning { border-left-color: #FF00FF; }
.chart-note { font-size: 12px; color: #888; margin: 4px 0 12px; }
.zone-summary { margin: 8px 0; }
.zone-badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; margin: 2px; }
table.splits { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 14px; }
table.splits th { background: #151515; padding: 6px 10px; text-align: left; font-weight: 600; color: #00FF41; }
table.splits td { padding: 5px 10px; border-bottom: 1px solid #1a1a1a; }
table.splits tr:hover { background: #111; }
svg { display: block; margin: 8px 0; max-width: 100%; }
.coach-conversation { margin: 16px 0; }
.coach-conversation h3 { font-size: 17px; color: #00FFFF; margin: 20px 0 10px; border-bottom: 1px solid #1a1a1a; padding-bottom: 4px; }
.coach-line { display: flex; gap: 12px; padding: 10px 14px; margin: 6px 0; border-left: 3px solid; border-radius: 0 6px 6px 0; background: #0a0a0a; }
.coach-name { font-weight: 600; font-size: 13px; white-space: nowrap; min-width: 180px; }
.coach-text { font-size: 14px; line-height: 1.5; }
.has-tooltip { position: relative; border-bottom: 1px dotted #888; cursor: help; }
.tooltip-popup {
    display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%);
    background: #1a1a1a; color: #00FF00; padding: 8px 12px; border-radius: 6px; font-size: 12px;
    line-height: 1.4; width: 280px; z-index: 100; border: 1px solid #333;
    box-shadow: 0 0 12px rgba(0,255,65,0.15);
    pointer-events: auto;
}
.tooltip-popup::after {
    content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    border: 6px solid transparent; border-top-color: #1a1a1a;
}
.has-tooltip:hover .tooltip-popup { display: block; }
.tooltip-link { color: #00FFFF; margin-left: 6px; text-decoration: none; font-size: 11px; }
.tooltip-link:hover { text-decoration: underline; }
"""


def section_vo2max_trend():
    """VO2max trend chart comparing Garmin vs own estimates over time."""
    try:
        conn = get_connection()
        rows = load_all_enriched(conn)
    except Exception:
        return ""

    if not rows:
        return ""

    # Filter to rows with at least one VO2max value
    rows = [r for r in rows if r.get("garmin_vo2max") or r.get("vo2max_composite")]
    if not rows:
        return ""

    html = '<div class="section"><h2>VO2max Estimates</h2>'

    # Build chart data
    dates = []
    garmin_vals = []
    composite_vals = []
    vdot_vals = []
    for r in rows:
        d = r["activity_date"]
        if d is None:
            continue
        day_num = (d - rows[0]["activity_date"]).total_seconds() / 86400
        dates.append(day_num)
        garmin_vals.append(r.get("garmin_vo2max"))
        composite_vals.append(r.get("vo2max_composite"))
        vdot_vals.append(r.get("vo2max_vdot"))

    # Date labels for x-axis
    first_date = rows[0]["activity_date"]
    x_labels = []
    for r in rows:
        d = r["activity_date"]
        if d and d.day <= 7:
            day_num = (d - first_date).total_seconds() / 86400
            x_labels.append((d.strftime("%b %y"), day_num))

    chart = SvgChart(width=700, height=300)

    # Filter None values for each series
    garmin_xs = [dates[i] for i in range(len(dates)) if garmin_vals[i] is not None]
    garmin_ys = [v for v in garmin_vals if v is not None]
    comp_xs = [dates[i] for i in range(len(dates)) if composite_vals[i] is not None]
    comp_ys = [v for v in composite_vals if v is not None]
    vdot_xs = [dates[i] for i in range(len(dates)) if vdot_vals[i] is not None]
    vdot_ys = [v for v in vdot_vals if v is not None]

    extra_lines = []
    if comp_xs:
        extra_lines.append((comp_xs, comp_ys, "#FF6B35"))
    if vdot_xs:
        extra_lines.append((vdot_xs, vdot_ys, "#4ECDC4"))

    if garmin_xs:
        svg = chart.line(garmin_xs, garmin_ys, color="#00FF00",
                         title="VO2max Estimates Over Time",
                         x_labels=x_labels,
                         extra_lines=extra_lines if extra_lines else None,
                         trend=False)
        html += svg

    # Legend
    html += '<div style="text-align:center; margin-top:8px; font-size:13px;">'
    html += '<span style="color:#00FF00">&#9632; Garmin</span> &nbsp; '
    html += '<span style="color:#FF6B35">&#9632; Composite</span> &nbsp; '
    html += '<span style="color:#4ECDC4">&#9632; VDOT</span>'
    html += '</div>'

    # Latest values table
    latest = rows[-1]
    html += '<table style="margin:16px auto; border-collapse:collapse;">'
    html += '<tr><th style="padding:4px 16px; text-align:left;">Method</th>'
    html += '<th style="padding:4px 16px; text-align:right;">Latest</th></tr>'
    for label, key, color in [
        ("Garmin Firstbeat", "garmin_vo2max", "#00FF00"),
        ("Uth (HR ratio)", "vo2max_uth", "#FFD700"),
        ("VDOT (Daniels)", "vo2max_vdot", "#4ECDC4"),
        ("HR-speed regression", "vo2max_hr_speed", "#FF69B4"),
        ("Composite", "vo2max_composite", "#FF6B35"),
    ]:
        val = latest.get(key)
        val_str = f"{val:.1f}" if val else "—"
        html += f'<tr><td style="padding:4px 16px; color:{color};">{label}</td>'
        html += f'<td style="padding:4px 16px; text-align:right;">{val_str}</td></tr>'
    html += '</table>'

    html += '</div>'
    return html


def build_report(runs, panel_discussions):
    last = runs[-1]
    dt = parse_date(last.get("start_date_local"))
    date_str = dt.strftime("%d %b %Y") if dt else "Unknown"

    chart = SvgChart()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Running Coach Report - {date_str}</title>
<style>{CSS}</style>
</head>
<body>
<h1>Running Coach Report &mdash; {RACE_NAME} Prep</h1>
<p class="subtitle">{len(runs)} runs analyzed &middot; {runs[0].get('start_date_local','')[:10]} to {last.get('start_date_local','')[:10]} &middot; Race: {RACE_DATE.strftime('%d %b %Y')} ({(RACE_DATE - TODAY).days} days) &middot; Generated {datetime.now().strftime('%d %b %Y %H:%M')}</p>
"""

    # Coaching panel discussions
    if panel_discussions:
        html += '<div class="section"><h2>Coaching Panel</h2>'
        for section_title, conversation in panel_discussions:
            html += f'<div class="coach-conversation"><h3>{section_title}</h3>'
            for name, color, text in conversation:
                tooltip_text = apply_tooltips(text)
                html += (f'<div class="coach-line" style="border-left-color:{color}">'
                         f'<div class="coach-name" style="color:{color}">{name}</div>'
                         f'<div class="coach-text">{tooltip_text}</div></div>')
            html += '</div>'
        html += '</div>'

    # VO2max trend (from enriched Postgres data)
    print("  Section: VO2max Trend...")
    html += section_vo2max_trend()

    # Data sections
    print("  Section A: Last Run Deep-Dive...")
    html += section_last_run(runs, chart)
    print("  Section B: Training Load...")
    html += section_training_load(runs, chart)
    print("  Section C: Pace Trends...")
    html += section_pace_trends(runs, chart)
    print("  Section D: Weekly Volume...")
    html += section_weekly_volume(runs, chart)
    print("  Section E: HR Analysis...")
    html += section_hr_analysis(runs, chart)
    print("  Section F: Cadence & Stride...")
    html += section_cadence_stride(runs, chart)
    print("  Section G: Training Plan...")
    html += section_training_plan(runs, chart)

    html += """
</body>
</html>"""
    return html

# ---------------------------------------------------------------------------
# VO2max Enrichment
# ---------------------------------------------------------------------------

def enrich_activity(garmin_id: int) -> dict:
    """Load a Garmin activity, compute VO2max estimates, store in Postgres."""
    activity = load_garmin_activity(garmin_id)
    date_str = activity["activity_date"].strftime("%Y-%m-%d") if activity["activity_date"] else None

    # Daily context
    ctx = load_garmin_daily_context(date_str) if date_str else {"rhr": None, "hrv": None}
    rhr = ctx["rhr"]

    # Compute pace
    if activity["distance_m"] and activity["duration_s"]:
        activity["pace_minkm"] = activity["duration_s"] / activity["distance_m"] * 1000 / 60
    else:
        activity["pace_minkm"] = None

    # --- VO2max estimates ---
    # 1. Uth
    vo2_uth = calc_uth(HR_MAX, rhr) if rhr else None

    # 2. VDOT
    vo2_vdot = None
    if activity["distance_m"] > 0 and activity["duration_s"] > 0:
        vo2_vdot = calc_vdot(activity["distance_m"], activity["duration_s"])

    # 3. HR-speed regression (from steady-state time-series)
    vo2_hr_speed = None
    steady = extract_steady_state_speed(garmin_id)
    if steady and rhr:
        vo2_hr_speed = calc_hr_speed(
            avg_speed_m_per_min=steady["avg_speed_m_per_min"],
            avg_hr=steady["avg_hr"],
            hr_max=HR_MAX,
            rhr=rhr,
        )

    # 4. Composite
    vo2_composite = None
    pct_hrr = None
    if activity["avg_hr"] and rhr:
        pct_hrr = (activity["avg_hr"] - rhr) / (HR_MAX - rhr)
    if vo2_uth is not None and vo2_vdot is not None and pct_hrr is not None:
        vo2_composite = calc_composite(
            uth=vo2_uth,
            vdot=vo2_vdot,
            hr_speed=vo2_hr_speed,
            pct_hrr=pct_hrr,
            duration_s=activity["duration_s"],
        )

    # Build row
    row = {
        **activity,
        "vo2max_uth": vo2_uth,
        "vo2max_vdot": vo2_vdot,
        "vo2max_hr_speed": vo2_hr_speed,
        "vo2max_composite": vo2_composite,
        "rhr_on_day": rhr,
        "hrv_on_day": ctx["hrv"],
    }

    # Store in Postgres
    conn = get_connection()
    upsert_activity(conn, row)

    # Print summary
    name = f"{activity['distance_m']/1000:.1f}km" if activity["distance_m"] else "?"
    date = activity["activity_date"].strftime("%Y-%m-%d") if activity["activity_date"] else "?"
    pace = fmt_pace(activity["pace_minkm"]) if activity.get("pace_minkm") else "--:--"

    print(f"\nActivity: {date}, {name}, {pace}/km")
    print(f"\nVO2max estimates:")
    print(f"  Garmin Firstbeat:   {activity['garmin_vo2max'] or '—'}")
    print(f"  Uth (HR ratio):     {vo2_uth:.1f}" if vo2_uth else "  Uth (HR ratio):     —")
    if vo2_uth and rhr:
        print(f"                      (HRmax={HR_MAX}, RHR={rhr:.0f})")
    print(f"  VDOT (Daniels):     {vo2_vdot:.1f}" if vo2_vdot else "  VDOT (Daniels):     —")
    print(f"  HR-speed regress:   {vo2_hr_speed:.1f}" if vo2_hr_speed else "  HR-speed regress:   —")
    if pct_hrr:
        print(f"                      ({pct_hrr:.0%} HRR)")
    print(f"  {'─' * 25}")
    print(f"  Composite:          {vo2_composite:.1f}" if vo2_composite else "  Composite:          —")

    if activity.get("weather_temp_f") or ctx.get("hrv"):
        parts = []
        if activity.get("weather_temp_f"):
            parts.append(f"temp={activity['weather_temp_f']}°F")
        if ctx.get("hrv"):
            parts.append(f"HRV={ctx['hrv']}")
        print(f"\n  Context: {', '.join(parts)}")

    print(f"\n  Stored → enriched_activities (garmin_id={garmin_id})")
    return row


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate running coach report.")
    parser.add_argument("activity_id", nargs="?", default=None,
                        help="Garmin activity ID to enrich (default: latest run)")
    parser.add_argument("--all", action="store_true",
                        help="Enrich all running activities (backfill)")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip AI coach commentary (faster, no Claude CLI needed)")
    parser.add_argument("--no-rag", action="store_true",
                        help="Skip RAG retrieval (use model's base knowledge only)")
    parser.add_argument("--model", choices=["sonnet", "haiku", "opus"], default="sonnet",
                        help="Claude model for AI commentary (default: sonnet, opus uses extended thinking)")
    parser.add_argument("--thinking-budget", type=int, default=10000,
                        help="Extended thinking token budget for opus (default: 10000)")
    args = parser.parse_args()

    # --- Enrichment ---
    if args.all:
        print("Enriching all activities...")
        runs_garmin = load_garmin_runs()
        for i, run in enumerate(runs_garmin):
            print(f"\n[{i + 1}/{len(runs_garmin)}]", end="")
            try:
                enrich_activity(run["activityId"])
            except Exception as e:
                print(f"  ERROR: {e}")
    else:
        if args.activity_id:
            garmin_id = int(args.activity_id)
        else:
            latest = find_latest_run()
            if not latest:
                print("No running activities found in Garmin data.")
                sys.exit(1)
            garmin_id = latest["activityId"]
        enrich_activity(garmin_id)

    # --- Report (always) ---
    print("\nLoading activities for report...")
    activities = load_activities()
    runs = filter_runs(activities)
    print(f"  {len(runs)} runs after filtering (>2km, >10min)")

    if not runs:
        print("No qualifying runs found.")
        sys.exit(1)

    print("Computing metrics...")
    metrics = build_metrics(runs)

    print("Saving metrics.json...")
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    panel_discussions = []
    if args.no_ai:
        print("Skipping AI coach commentary (--no-ai)")
    else:
        print(f"Getting coaching panel discussions (model: {args.model})...")
        panel_discussions = get_panel_discussions(metrics, model=args.model,
                                                    thinking_budget=args.thinking_budget,
                                                    use_rag=not args.no_rag)
        if panel_discussions:
            print(f"  Got {len(panel_discussions)} panel sections")
        else:
            print("  No AI commentary (claude CLI unavailable or errored)")

    print("Building report...")
    html = build_report(runs, panel_discussions)

    print(f"Writing {REPORT_PATH}...")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print("Opening in browser...")
    webbrowser.open(str(REPORT_PATH))
    print("Done.")


if __name__ == "__main__":
    main()
