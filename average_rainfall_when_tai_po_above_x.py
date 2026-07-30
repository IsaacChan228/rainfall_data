from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AvgRainfallResult:
    location: str
    threshold_x: float
    samples_used: int
    avg_rainfall: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate average rainfall per location when Tai Po Market rainfall "
            "is above threshold x."
        )
    )
    parser.add_argument(
        "--input",
        default="rainfall.csv",
        help="Path to input rainfall CSV (default: rainfall.csv).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        required=True,
        help="Rainfall threshold x in mm. Rows are selected when Tai Po Market > x.",
    )
    parser.add_argument(
        "--output",
        default="average_rainfall_when_tai_po_above_x.csv",
        help=(
            "Path to output CSV "
            "(default: average_rainfall_when_tai_po_above_x.csv)."
        ),
    )
    return parser.parse_args()


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_average_rainfall(input_path: Path, threshold: float) -> list[AvgRainfallResult]:
    with input_path.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header.")

        if "Tai Po Market" not in reader.fieldnames:
            raise ValueError('Column "Tai Po Market" not found in input CSV.')

        locations = [name for name in reader.fieldnames if name not in {"obsTime", "Tai Po Market"}]
        rows = list(reader)

    results: list[AvgRainfallResult] = []

    for location in locations:
        total = 0.0
        count = 0

        for row in rows:
            tai_po_value = to_float(row.get("Tai Po Market", ""))
            location_value = to_float(row.get(location, ""))

            if tai_po_value is None or location_value is None:
                continue

            if tai_po_value > threshold:
                total += location_value
                count += 1

        avg_value = None if count == 0 else total / count
        results.append(
            AvgRainfallResult(
                location=location,
                threshold_x=threshold,
                samples_used=count,
                avg_rainfall=avg_value,
            )
        )

    return results


def write_results(output_path: Path, results: list[AvgRainfallResult]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(
            [
                "location",
                "threshold_x",
                "samples_used",
                "avg_location_rainfall_when_tai_po_market_above_x",
            ]
        )
        for item in results:
            avg_value = "NA" if item.avg_rainfall is None else f"{item.avg_rainfall:.6f}"
            writer.writerow([item.location, item.threshold_x, item.samples_used, avg_value])


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    results = compute_average_rainfall(input_path=input_path, threshold=args.threshold)
    write_results(output_path=output_path, results=results)


if __name__ == "__main__":
    main()
