from __future__ import annotations

import argparse
import csv
import html
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


BUCKET_MINUTES = 5


@dataclass
class TimeSeriesPoint:
    obs_time: datetime
    value: float


@dataclass
class BucketPoint:
    antenna_name: str
    obs_time: datetime
    rainfall_value: float
    signal_value: float


@dataclass
class RelationshipResult:
    antenna_name: str
    samples_used: int
    average_signal_drop: float
    coefficient_a: float
    coefficient_b: float
    coefficient_c: float
    correlation: float | None
    r_squared: float | None


@dataclass
class AntennaAnalysis:
    antenna_name: str
    bucketed_points: list[BucketPoint]
    raw_signal_average_by_time: dict[datetime, float]
    result: RelationshipResult


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate quadratic relationships between each antenna's signal drop and Tai Po Market "
            "rainfall using 5-minute buckets."
        )
    )
    parser.add_argument("--rainfall-input", default="rainfall.csv", help="Path to rainfall.csv (default: rainfall.csv).")
    parser.add_argument(
        "--antenna-input-dir",
        default="Antenna_HKT",
        help="Directory containing converted Antenna CSV files (default: Antenna_HKT).",
    )
    parser.add_argument(
        "--output",
        default="antenna_rainfall_relationship.csv",
        help="Path to output CSV (default: antenna_rainfall_relationship.csv).",
    )
    parser.add_argument(
        "--plot-dir",
        default="antenna_rainfall_plots",
        help="Directory for SVG validation plots (default: antenna_rainfall_plots).",
    )
    return parser.parse_args()


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_obs_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def floor_to_bucket(value: datetime) -> datetime:
    bucket_minute = (value.minute // BUCKET_MINUTES) * BUCKET_MINUTES
    return value.replace(minute=bucket_minute, second=0, microsecond=0)


def load_series(path: Path, value_column: str) -> list[TimeSeriesPoint]:
    with path.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        if "obsTime" not in reader.fieldnames:
            raise ValueError(f'Column "obsTime" not found in {path.name}.')
        if value_column not in reader.fieldnames:
            raise ValueError(f'Column "{value_column}" not found in {path.name}.')

        series: list[TimeSeriesPoint] = []
        for row in reader:
            obs_time = row.get("obsTime", "")
            value = to_float(row.get(value_column, ""))
            if obs_time and value is not None:
                series.append(TimeSeriesPoint(obs_time=parse_obs_time(obs_time), value=value))

    series.sort(key=lambda item: item.obs_time)
    return series


def list_antenna_files(antenna_input_dir: Path) -> list[Path]:
    antenna_files = sorted(antenna_input_dir.glob("*.csv"))
    if not antenna_files:
        raise ValueError(f"No CSV files found in {antenna_input_dir}")
    return antenna_files


def interpolate_linear(series: list[TimeSeriesPoint], target_time: datetime) -> float | None:
    if not series:
        return None
    if target_time < series[0].obs_time or target_time > series[-1].obs_time:
        return None

    for index, point in enumerate(series):
        if point.obs_time == target_time:
            return point.value
        if point.obs_time > target_time:
            previous_point = series[index - 1]
            span = (point.obs_time - previous_point.obs_time).total_seconds()
            if span == 0:
                return previous_point.value
            elapsed = (target_time - previous_point.obs_time).total_seconds()
            ratio = elapsed / span
            return previous_point.value + ratio * (point.value - previous_point.value)

    return series[-1].value


def solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[index]] for index, row in enumerate(matrix)]

    for pivot_index in range(size):
        pivot_row = max(range(pivot_index, size), key=lambda row_index: abs(augmented[row_index][pivot_index]))
        pivot_value = augmented[pivot_row][pivot_index]
        if abs(pivot_value) < 1e-12:
            raise ValueError("Unable to fit a linear equation because the system is singular.")

        if pivot_row != pivot_index:
            augmented[pivot_index], augmented[pivot_row] = augmented[pivot_row], augmented[pivot_index]

        pivot_value = augmented[pivot_index][pivot_index]
        for column_index in range(pivot_index, size + 1):
            augmented[pivot_index][column_index] /= pivot_value

        for row_index in range(size):
            if row_index == pivot_index:
                continue
            factor = augmented[row_index][pivot_index]
            if factor == 0.0:
                continue
            for column_index in range(pivot_index, size + 1):
                augmented[row_index][column_index] -= factor * augmented[pivot_index][column_index]

    return [augmented[row_index][size] for row_index in range(size)]


def fit_linear_polynomial(x_values: list[float], y_values: list[float], ridge: float = 1e-9) -> list[float]:
    xtx = [[0.0]]
    xty = [0.0]

    for x_value, y_value in zip(x_values, y_values):
        xty[0] += x_value * y_value
        xtx[0][0] += x_value * x_value

    xtx[0][0] += ridge

    return solve_linear_system(xtx, xty)


def evaluate_linear(coefficients: list[float], x_value: float) -> float:
    (a,) = coefficients
    return a * x_value


def compute_correlation(x_values: list[float], y_values: list[float]) -> tuple[float | None, float | None]:
    count = len(x_values)
    if count == 0:
        return None, None

    x_mean = sum(x_values) / count
    y_mean = sum(y_values) / count
    x_variance = sum((x - x_mean) ** 2 for x in x_values)
    y_variance = sum((y - y_mean) ** 2 for y in y_values)
    covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))

    if x_variance == 0.0 or y_variance == 0.0:
        return None, None

    correlation = covariance / math.sqrt(x_variance * y_variance)
    return correlation, correlation * correlation


def build_rainfall_buckets(rainfall_series: list[TimeSeriesPoint]) -> list[tuple[datetime, float]]:
    if not rainfall_series:
        return []

    start_time = floor_to_bucket(rainfall_series[0].obs_time)
    end_time = floor_to_bucket(rainfall_series[-1].obs_time)

    buckets: list[tuple[datetime, float]] = []
    current_time = start_time
    while current_time <= end_time:
        rainfall_value = interpolate_linear(rainfall_series, current_time)
        if rainfall_value is not None:
            buckets.append((current_time, rainfall_value))
        current_time += timedelta(minutes=BUCKET_MINUTES)

    return buckets


def build_bucketed_points(
    antenna_name: str,
    rainfall_buckets: list[tuple[datetime, float]],
    signal_series: list[TimeSeriesPoint],
) -> list[BucketPoint]:
    signal_bucket_values: dict[datetime, list[float]] = {}
    for point in signal_series:
        bucket_time = floor_to_bucket(point.obs_time)
        signal_bucket_values.setdefault(bucket_time, []).append(point.value)

    bucketed_points: list[BucketPoint] = []
    for bucket_time, rainfall_value in rainfall_buckets:
        signal_values = signal_bucket_values.get(bucket_time)
        if not signal_values:
            continue
        bucketed_points.append(
            BucketPoint(
                antenna_name=antenna_name,
                obs_time=bucket_time,
                rainfall_value=rainfall_value,
                signal_value=max(signal_values),
            )
        )
    return bucketed_points


def build_raw_signal_by_time(signal_series: list[TimeSeriesPoint]) -> dict[datetime, float]:
    bucket_values: dict[datetime, list[float]] = {}
    for point in signal_series:
        bucket_values.setdefault(point.obs_time, []).append(point.value)

    return {obs_time: sum(values) / len(values) for obs_time, values in bucket_values.items()}


def analyze_antenna(
    antenna_path: Path,
    rainfall_buckets: list[tuple[datetime, float]],
) -> AntennaAnalysis | None:
    antenna_name = antenna_path.stem
    signal_series = load_series(antenna_path, "Signal drop")
    bucketed_points = build_bucketed_points(antenna_name, rainfall_buckets, signal_series)
    if not bucketed_points:
        return None

    x_values = [point.rainfall_value for point in bucketed_points]
    y_values = [point.signal_value for point in bucketed_points]
    coefficients = fit_linear_polynomial(x_values, y_values)
    correlation, r_squared = compute_correlation(x_values, y_values)
    average_signal_drop = sum(y_values) / len(y_values)

    result = RelationshipResult(
        antenna_name=antenna_name,
        samples_used=len(bucketed_points),
        average_signal_drop=average_signal_drop,
        coefficient_a=coefficients[0],
        coefficient_b=0.0,
        coefficient_c=0.0,
        correlation=correlation,
        r_squared=r_squared,
    )

    return AntennaAnalysis(
        antenna_name=antenna_name,
        bucketed_points=bucketed_points,
        raw_signal_average_by_time=build_raw_signal_by_time(signal_series),
        result=result,
    )


def build_average_result(results: list[RelationshipResult]) -> RelationshipResult:
    if not results:
        raise ValueError("Cannot build an average equation without any antenna results.")

    return RelationshipResult(
        antenna_name="AVERAGE",
        samples_used=sum(result.samples_used for result in results),
        average_signal_drop=sum(result.average_signal_drop for result in results) / len(results),
        coefficient_a=sum(result.coefficient_a for result in results) / len(results),
        coefficient_b=0.0,
        coefficient_c=0.0,
        correlation=None,
        r_squared=None,
    )


def build_all_bucketed_points(analyses: list[AntennaAnalysis]) -> list[BucketPoint]:
    bucketed_points: list[BucketPoint] = []
    for analysis in analyses:
        bucketed_points.extend(analysis.bucketed_points)
    return bucketed_points


def format_equation(coefficients: list[float]) -> str:
    (a,) = coefficients
    return f"Signal drop = {a:.6f} * Tai Po Market rainfall"


def create_svg_plot(
    plot_path: Path,
    title: str,
    subtitle: str,
    bucketed_points: list[BucketPoint],
    coefficients: list[float],
    show_polyline: bool = True,
) -> None:
    width = 1400
    height = 920
    left = 90
    right = 40
    top = 70
    panel_height = 670
    plot_width = width - left - right

    x_values = [point.rainfall_value for point in bucketed_points]
    y_values = [point.signal_value for point in bucketed_points]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)

    if x_min == x_max:
        x_padding = 1.0 if x_min == 0.0 else abs(x_min) * 0.1
        x_min -= x_padding
        x_max += x_padding
    else:
        x_padding = (x_max - x_min) * 0.1
        x_min -= x_padding
        x_max += x_padding

    if y_min == y_max:
        y_padding = 1.0 if y_min == 0.0 else abs(y_min) * 0.1
        y_min -= y_padding
        y_max += y_padding
    else:
        y_padding = (y_max - y_min) * 0.1
        y_min -= y_padding
        y_max += y_padding

    def svg_escape(value: str) -> str:
        return html.escape(value, quote=True)

    def x_to_svg(value: float) -> float:
        ratio = 0.0 if x_max == x_min else (value - x_min) / (x_max - x_min)
        return left + ratio * plot_width

    def y_to_svg(value: float) -> float:
        ratio = 0.0 if y_max == y_min else (value - y_min) / (y_max - y_min)
        return top + panel_height - ratio * panel_height

    def ticks_for_axis(minimum: float, maximum: float, count: int = 5) -> list[float]:
        if minimum == maximum:
            return [minimum]
        step = (maximum - minimum) / (count - 1)
        return [minimum + index * step for index in range(count)]

    curve_points = [x_min + (x_max - x_min) * index / 200 for index in range(201)]
    curve_pairs = [(x_value, evaluate_linear(coefficients, x_value)) for x_value in curve_points]

    svg_lines: list[str] = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg_lines.append('<rect width="100%" height="100%" fill="#f6f8fb"/>')
    svg_lines.append(f'<text x="90" y="34" font-size="24" font-weight="700" fill="#212529">{html.escape(title, quote=True)}</text>')
    svg_lines.append(f'<text x="90" y="52" font-size="13" fill="#5c677d">{html.escape(subtitle, quote=True)}</text>')
    svg_lines.append(f'<rect x="{left}" y="{top}" width="{plot_width}" height="{panel_height}" fill="#ffffff" stroke="#d0d7de" stroke-width="1"/>')

    for tick_value in ticks_for_axis(x_min, x_max):
        x = x_to_svg(tick_value)
        svg_lines.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + panel_height}" stroke="#eef1f4" stroke-width="1"/>')
        svg_lines.append(f'<text x="{x:.2f}" y="{top + panel_height + 22}" text-anchor="middle" font-size="12" fill="#495057">{tick_value:.2f}</text>')

    for tick_value in ticks_for_axis(y_min, y_max):
        y = y_to_svg(tick_value)
        svg_lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#eef1f4" stroke-width="1"/>')
        svg_lines.append(f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#495057">{tick_value:.2f}</text>')

    if show_polyline:
        polyline = " ".join(f"{x_to_svg(point.rainfall_value):.2f},{y_to_svg(point.signal_value):.2f}" for point in bucketed_points)
        svg_lines.append(f'<polyline points="{polyline}" fill="none" stroke="#8a8f98" stroke-width="1.8" opacity="0.55"/>')
    for point in bucketed_points:
        svg_lines.append(
            f'<circle cx="{x_to_svg(point.rainfall_value):.2f}" cy="{y_to_svg(point.signal_value):.2f}" r="3" fill="#8a8f98" stroke="#ffffff" stroke-width="1"/>'
        )

    curve_polyline = " ".join(f"{x_to_svg(x_value):.2f},{y_to_svg(y_value):.2f}" for x_value, y_value in curve_pairs)
    svg_lines.append(f'<polyline points="{curve_polyline}" fill="none" stroke="#d63384" stroke-width="2.8"/>')

    equation_text = svg_escape(format_equation(coefficients))
    average_signal = sum(y_values) / len(y_values)
    svg_lines.append('<rect x="108" y="86" width="1190" height="70" rx="10" fill="#f8f9fb" stroke="#e3e7eb"/>')
    svg_lines.append(f'<text x="120" y="116" font-size="13" fill="#212529">{equation_text}</text>')
    svg_lines.append(f'<text x="120" y="140" font-size="12" fill="#5c677d">Average signal drop used in fit: {average_signal:.4f}</text>')
    svg_lines.append('<text x="120" y="164" font-size="12" fill="#5c677d">Gray dots: bucketed maximums; pink curve: linear fit</text>')
    svg_lines.append('</svg>')

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plot_path.write_text("\n".join(svg_lines), encoding="utf-8")


def create_time_series_plot(
    plot_path: Path,
    antenna_name: str,
    rainfall_series: list[TimeSeriesPoint],
    raw_signal_average_by_time: dict[datetime, float],
    bucketed_points: list[BucketPoint],
) -> None:
    width = 1400
    height = 1040
    left = 90
    right = 40
    top = 70
    panel_gap = 70
    panel_height = 360
    plot_width = width - left - right

    if not rainfall_series or not raw_signal_average_by_time or not bucketed_points:
        return

    bucketed_rainfall_pairs = [(point.obs_time, point.rainfall_value) for point in bucketed_points]
    bucketed_signal_pairs = [(point.obs_time, point.signal_value) for point in bucketed_points]
    rainfall_raw_pairs = [(point.obs_time, point.value) for point in rainfall_series]
    signal_raw_pairs = sorted(raw_signal_average_by_time.items())

    time_points = [point.obs_time for point in rainfall_series] + [obs_time for obs_time, _ in signal_raw_pairs] + [point.obs_time for point in bucketed_points]
    min_time = min(time_points)
    max_time = max(time_points)
    if min_time == max_time:
        max_time = min_time + timedelta(minutes=BUCKET_MINUTES)

    def svg_escape(value: str) -> str:
        return html.escape(value, quote=True)

    def time_to_x(value: datetime) -> float:
        span = (max_time - min_time).total_seconds()
        ratio = 0.0 if span == 0 else (value - min_time).total_seconds() / span
        return left + ratio * plot_width

    def scale_y(value: float, minimum: float, maximum: float, top_y: float, bottom_y: float) -> float:
        if minimum == maximum:
            return (top_y + bottom_y) / 2
        ratio = (value - minimum) / (maximum - minimum)
        return bottom_y - ratio * (bottom_y - top_y)

    def build_y_scale(pairs: list[tuple[datetime, float]]) -> tuple[float, float]:
        values = [value for _, value in pairs]
        if not values:
            return 0.0, 1.0
        minimum = min(values)
        maximum = max(values)
        if minimum == maximum:
            padding = 1.0 if minimum == 0.0 else abs(minimum) * 0.1
            return minimum - padding, maximum + padding
        padding = (maximum - minimum) * 0.1
        return minimum - padding, maximum + padding

    def ticks_for_axis(minimum: float, maximum: float, count: int = 5) -> list[float]:
        if minimum == maximum:
            return [minimum]
        step = (maximum - minimum) / (count - 1)
        return [minimum + index * step for index in range(count)]

    def render_series_points(
        pairs: list[tuple[datetime, float]],
        minimum: float,
        maximum: float,
        top_y: float,
        bottom_y: float,
        color: str,
        radius: int,
        opacity: float = 1.0,
    ) -> list[str]:
        if not pairs:
            return []
        lines: list[str] = []
        polyline = " ".join(
            f"{time_to_x(time):.2f},{scale_y(value, minimum, maximum, top_y, bottom_y):.2f}"
            for time, value in pairs
        )
        lines.append(
            f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2.2" opacity="{opacity}"/>'
        )
        for time, value in pairs:
            lines.append(
                f'<circle cx="{time_to_x(time):.2f}" cy="{scale_y(value, minimum, maximum, top_y, bottom_y):.2f}" '
                f'r="{radius}" fill="{color}" stroke="#ffffff" stroke-width="1" opacity="{opacity}"/>'
            )
        return lines

    svg_lines: list[str] = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    svg_lines.append('<rect width="100%" height="100%" fill="#f6f8fb"/>')
    svg_lines.append(f'<text x="90" y="34" font-size="24" font-weight="700" fill="#212529">{html.escape(antenna_name, quote=True)} time-series check</text>')
    svg_lines.append('<text x="90" y="52" font-size="13" fill="#5c677d">Rainfall and signal-drop values shown against time for manual bucket verification</text>')

    # Rainfall panel
    rainfall_top = top
    rainfall_bottom = rainfall_top + panel_height
    rainfall_pairs = rainfall_raw_pairs + bucketed_rainfall_pairs
    rainfall_min, rainfall_max = build_y_scale(rainfall_pairs)
    svg_lines.append(f'<text x="{left}" y="{rainfall_top - 18}" font-size="20" font-weight="600">Tai Po Market rainfall</text>')
    svg_lines.append(f'<rect x="{left}" y="{rainfall_top}" width="{plot_width}" height="{panel_height}" fill="#ffffff" stroke="#d0d7de" stroke-width="1"/>')
    y_top = rainfall_top + 10
    y_bottom = rainfall_bottom - 30
    for tick_value in ticks_for_axis(rainfall_min, rainfall_max):
        y = scale_y(tick_value, rainfall_min, rainfall_max, y_top, y_bottom)
        svg_lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#eef1f4" stroke-width="1"/>')
        svg_lines.append(f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#495057">{tick_value:.2f}</text>')
    for tick_value in ticks_for_axis(0.0, 1.0):
        tick_time = min_time + (max_time - min_time) * tick_value
        x = time_to_x(tick_time)
        svg_lines.append(f'<line x1="{x:.2f}" y1="{y_top}" x2="{x:.2f}" y2="{y_bottom}" stroke="#eef1f4" stroke-width="1"/>')
        svg_lines.append(f'<text x="{x:.2f}" y="{rainfall_bottom - 8}" text-anchor="middle" font-size="12" fill="#495057">{tick_time.strftime("%m-%d %H:%M")}</text>')
    svg_lines.extend(render_series_points(rainfall_raw_pairs, rainfall_min, rainfall_max, y_top, y_bottom, "#8a8f98", 2, 0.5))
    svg_lines.extend(render_series_points(bucketed_rainfall_pairs, rainfall_min, rainfall_max, y_top, y_bottom, "#007acc", 3, 1.0))
    svg_lines.append(f'<text x="{left + 18}" y="{rainfall_top + 24}" font-size="12" fill="#5c677d">Gray: raw rainfall observations; blue: 5-minute interpolated rainfall</text>')

    # Signal panel
    signal_top = rainfall_bottom + panel_gap
    signal_bottom = signal_top + panel_height
    signal_pairs = signal_raw_pairs + bucketed_signal_pairs
    signal_min, signal_max = build_y_scale(signal_pairs)
    svg_lines.append(f'<text x="{left}" y="{signal_top - 18}" font-size="20" font-weight="600">Signal drop</text>')
    svg_lines.append(f'<rect x="{left}" y="{signal_top}" width="{plot_width}" height="{panel_height}" fill="#ffffff" stroke="#d0d7de" stroke-width="1"/>')
    y_top = signal_top + 10
    y_bottom = signal_bottom - 30
    for tick_value in ticks_for_axis(signal_min, signal_max):
        y = scale_y(tick_value, signal_min, signal_max, y_top, y_bottom)
        svg_lines.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#eef1f4" stroke-width="1"/>')
        svg_lines.append(f'<text x="{left - 12}" y="{y + 4:.2f}" text-anchor="end" font-size="12" fill="#495057">{tick_value:.2f}</text>')
    for tick_value in ticks_for_axis(0.0, 1.0):
        tick_time = min_time + (max_time - min_time) * tick_value
        x = time_to_x(tick_time)
        svg_lines.append(f'<line x1="{x:.2f}" y1="{y_top}" x2="{x:.2f}" y2="{y_bottom}" stroke="#eef1f4" stroke-width="1"/>')
        svg_lines.append(f'<text x="{x:.2f}" y="{signal_bottom - 8}" text-anchor="middle" font-size="12" fill="#495057">{tick_time.strftime("%m-%d %H:%M")}</text>')
    svg_lines.extend(render_series_points(signal_raw_pairs, signal_min, signal_max, y_top, y_bottom, "#8a8f98", 2, 0.35))
    svg_lines.extend(render_series_points(bucketed_signal_pairs, signal_min, signal_max, y_top, y_bottom, "#d63384", 3, 1.0))
    svg_lines.append(f'<text x="{left + 18}" y="{signal_top + 24}" font-size="12" fill="#5c677d">Gray: raw signal drop observations; pink: 5-minute bucket maximum</text>')

    svg_lines.append('</svg>')

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    plot_path.write_text("\n".join(svg_lines), encoding="utf-8")


def write_results(output_path: Path, results: list[RelationshipResult]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(
            [
                "antenna",
                "samples_used",
                "average_signal_drop",
                "equation",
                "coefficient_a",
                "coefficient_b",
                "coefficient_c",
                "correlation",
                "r_squared",
            ]
        )
        for result in results:
            writer.writerow(
                [
                    result.antenna_name,
                    result.samples_used,
                    f"{result.average_signal_drop:.6f}",
                    format_equation([result.coefficient_a]),
                    f"{result.coefficient_a:.6f}",
                    f"{result.coefficient_b:.6f}",
                    f"{result.coefficient_c:.6f}",
                    "NA" if result.correlation is None else f"{result.correlation:.6f}",
                    "NA" if result.r_squared is None else f"{result.r_squared:.6f}",
                ]
            )


def write_results_with_average(output_path: Path, results: list[RelationshipResult]) -> None:
    average_result = build_average_result(results)
    write_results(output_path, [*results, average_result])


def write_bucket_csv(output_path: Path, bucketed_points: list[BucketPoint]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(["antenna", "timebucket", "rainfall", "signal_drop"])
        for point in bucketed_points:
            writer.writerow(
                [
                    point.antenna_name,
                    point.obs_time.strftime("%Y-%m-%d %H:%M:%S"),
                    f"{point.rainfall_value:.6f}",
                    f"{point.signal_value:.6f}",
                ]
            )


def main() -> None:
    args = parse_args()
    rainfall_path = Path(args.rainfall_input)
    antenna_input_dir = Path(args.antenna_input_dir)
    output_path = Path(args.output)
    plot_dir = Path(args.plot_dir)
    bucket_output_path = output_path.with_name("antenna_rainfall_buckets.csv")

    rainfall_series = load_series(rainfall_path, "Tai Po Market")
    rainfall_buckets = build_rainfall_buckets(rainfall_series)
    antenna_files = list_antenna_files(antenna_input_dir)

    analyses: list[AntennaAnalysis] = []
    for antenna_path in antenna_files:
        analysis = analyze_antenna(antenna_path, rainfall_buckets)
        if analysis is None:
            continue
        analyses.append(analysis)

    if not analyses:
        raise ValueError("No overlapping 5-minute buckets were found across rainfall and antenna data.")

    write_results_with_average(output_path, [analysis.result for analysis in analyses])
    all_bucketed_points = build_all_bucketed_points(analyses)
    write_bucket_csv(bucket_output_path, all_bucketed_points)

    for analysis in analyses:
        coefficients = [
            analysis.result.coefficient_a,
        ]
        create_svg_plot(
            plot_dir / f"{analysis.antenna_name}_rainfall_signal_drop_equation.svg",
            f"{analysis.antenna_name} rainfall vs signal drop",
            "5-minute rainfall buckets linearly interpolated from rainfall.csv and antenna signal drops for this antenna only",
            analysis.bucketed_points,
            coefficients,
            show_polyline=True,
        )
        create_time_series_plot(
            plot_dir / f"{analysis.antenna_name}_rainfall_signal_drop_time_check.svg",
            analysis.antenna_name,
            rainfall_series,
            analysis.raw_signal_average_by_time,
            analysis.bucketed_points,
        )

    average_result = build_average_result([analysis.result for analysis in analyses])
    create_svg_plot(
        plot_dir / "average_rainfall_signal_drop_equation.svg",
        "Average equation vs all antenna data",
        "All 5-minute bucketed points from every antenna; pink line shows the averaged linear equation",
        all_bucketed_points,
        [average_result.coefficient_a],
        show_polyline=False,
    )


if __name__ == "__main__":
    main()
