from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ConditionalProbabilityResult:
    location: str
    x_threshold: float
    y_threshold: float
    probability: float | None
    condition_count: int
    co_occurrence_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate direct conditional probability from rainfall data: "
            "P(location rainfall < Y | Tai Po Market rainfall > X)."
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
        default=None,
        help=(
            "Single threshold for both X and Y (backward compatible). "
            "Equivalent to setting both --x-threshold and --y-threshold."
        ),
    )
    parser.add_argument(
        "--x-threshold",
        type=float,
        default=None,
        help="Rainfall threshold X in mm for condition event: Tai Po Market > X.",
    )
    parser.add_argument(
        "--y-threshold",
        type=float,
        default=None,
        help=(
            "Rainfall threshold Y in mm for target event: location rainfall < Y."
        ),
    )
    parser.add_argument(
        "--output",
        default="conditional_probabilities.csv",
        help="Path to output CSV (default: conditional_probabilities.csv).",
    )
    return parser.parse_args()


def resolve_thresholds(args: argparse.Namespace) -> tuple[float, float]:
    x_threshold = args.x_threshold
    y_threshold = args.y_threshold

    if args.threshold is not None:
        if x_threshold is None:
            x_threshold = args.threshold
        if y_threshold is None:
            y_threshold = args.threshold

    if x_threshold is None or y_threshold is None:
        raise ValueError(
            "Provide --threshold, or provide both --x-threshold and --y-threshold."
        )

    return x_threshold, y_threshold


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compute_conditional_probabilities(
    input_path: Path, x_threshold: float, y_threshold: float
) -> list[ConditionalProbabilityResult]:
    with input_path.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header.")

        if "Tai Po Market" not in reader.fieldnames:
            raise ValueError('Column "Tai Po Market" not found in input CSV.')

        locations = [name for name in reader.fieldnames if name not in {"obsTime", "Tai Po Market"}]
        rows = list(reader)

    results: list[ConditionalProbabilityResult] = []

    for location in locations:
        condition_count = 0
        co_occurrence_count = 0

        for row in rows:
            tai_po_value = to_float(row.get("Tai Po Market", ""))
            location_value = to_float(row.get(location, ""))

            if tai_po_value is None or location_value is None:
                continue

            if tai_po_value > x_threshold:
                condition_count += 1
                if location_value < y_threshold:
                    co_occurrence_count += 1

        probability = None
        if condition_count > 0:
            probability = co_occurrence_count / condition_count

        results.append(
            ConditionalProbabilityResult(
                location=location,
                x_threshold=x_threshold,
                y_threshold=y_threshold,
                probability=probability,
                condition_count=condition_count,
                co_occurrence_count=co_occurrence_count,
            )
        )

    return results


def write_results(output_path: Path, results: list[ConditionalProbabilityResult]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(
            [
                "location",
                "threshold_x_condition_tai_po_market_above",
                "threshold_y_target_location_below",
                "direct_conditional_probability_location_rainfall_below_y_given_tai_po_market_rainfall_above_x",
                "condition_count_tai_po_market_above_x",
                "co_occurrence_count",
            ]
        )

        for item in results:
            probability_value = "NA" if item.probability is None else f"{item.probability:.6f}"
            writer.writerow(
                [
                    item.location,
                    item.x_threshold,
                    item.y_threshold,
                    probability_value,
                    item.condition_count,
                    item.co_occurrence_count,
                ]
            )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    x_threshold, y_threshold = resolve_thresholds(args)

    results = compute_conditional_probabilities(
        input_path=input_path,
        x_threshold=x_threshold,
        y_threshold=y_threshold,
    )
    write_results(output_path=output_path, results=results)


if __name__ == "__main__":
    main()
