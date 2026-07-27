from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NBResult:
    location: str
    probability: float
    samples_used: int
    event_count: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Estimate P(location > x | Tai Po Market > x) using binary Naive Bayes "
            "from rainfall.csv."
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
        help="Threshold x. A station is considered positive when value > x.",
    )
    parser.add_argument(
        "--output",
        default="naive_bayes_probabilities.csv",
        help="Path to output CSV (default: naive_bayes_probabilities.csv).",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=1.0,
        help="Laplace smoothing parameter (default: 1.0).",
    )
    return parser.parse_args()


def to_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def posterior_x1(prior_y1: float, p_x1_given_y1: float, p_x1_given_y0: float) -> float:
    numerator = p_x1_given_y1 * prior_y1
    denominator = numerator + (p_x1_given_y0 * (1.0 - prior_y1))
    if denominator == 0.0:
        return 0.0
    return numerator / denominator


def compute_probabilities(
    input_path: Path, threshold: float, alpha: float
) -> list[NBResult]:
    with input_path.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.DictReader(file_handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header.")

        if "Tai Po Market" not in reader.fieldnames:
            raise ValueError('Column "Tai Po Market" not found in input CSV.')

        locations = [name for name in reader.fieldnames if name != "obsTime"]
        target_locations = [name for name in locations if name != "Tai Po Market"]

        rows = list(reader)

    results: list[NBResult] = []

    for location in target_locations:
        n = 0
        n_y1 = 0
        n_x1_y1 = 0
        n_y0 = 0
        n_x1_y0 = 0

        for row in rows:
            tai_po_value = to_float(row.get("Tai Po Market", ""))
            location_value = to_float(row.get(location, ""))

            if tai_po_value is None or location_value is None:
                continue

            x_is_1 = tai_po_value > threshold
            y_is_1 = location_value > threshold
            n += 1

            if y_is_1:
                n_y1 += 1
                if x_is_1:
                    n_x1_y1 += 1
            else:
                n_y0 += 1
                if x_is_1:
                    n_x1_y0 += 1

        if n == 0:
            results.append(
                NBResult(
                    location=location,
                    probability=0.0,
                    samples_used=0,
                    event_count=0,
                )
            )
            continue

        prior_y1 = (n_y1 + alpha) / (n + 2 * alpha)
        p_x1_given_y1 = (n_x1_y1 + alpha) / (n_y1 + 2 * alpha)
        p_x1_given_y0 = (n_x1_y0 + alpha) / (n_y0 + 2 * alpha)

        p_y1_given_x1 = posterior_x1(
            prior_y1=prior_y1,
            p_x1_given_y1=p_x1_given_y1,
            p_x1_given_y0=p_x1_given_y0,
        )

        event_count = sum(
            1
            for row in rows
            if to_float(row.get("Tai Po Market", "")) is not None
            and to_float(row.get(location, "")) is not None
            and to_float(row.get("Tai Po Market", "")) > threshold
            and to_float(row.get(location, "")) > threshold
        )

        results.append(
            NBResult(
                location=location,
                probability=p_y1_given_x1,
                samples_used=n,
                event_count=event_count,
            )
        )

    results.sort(key=lambda item: item.probability, reverse=True)
    return results


def write_results(output_path: Path, threshold: float, results: list[NBResult]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(
            [
                "location",
                "threshold_x",
                "probability_location_gt_x_given_tai_po_market_gt_x",
                "samples_used",
                "co_occurrence_count",
            ]
        )
        for item in results:
            probability_value = "NA" if item.samples_used == 0 else f"{item.probability:.6f}"
            writer.writerow(
                [
                    item.location,
                    threshold,
                    probability_value,
                    item.samples_used,
                    item.event_count,
                ]
            )


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    results = compute_probabilities(
        input_path=input_path,
        threshold=args.threshold,
        alpha=args.alpha,
    )
    write_results(output_path=output_path, threshold=args.threshold, results=results)


if __name__ == "__main__":
    main()