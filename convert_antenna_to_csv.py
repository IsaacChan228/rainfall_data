from __future__ import annotations

import argparse
import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta, timezone
from pathlib import Path


UTC_INPUT_FORMAT = "%a %b %d %H:%M:%S UTC %Y"
HKT = timezone(timedelta(hours=8))


# Edit this table when an antenna needs a different reference point.
# Each entry can use either `reference_row` (1-based row number) or
# `reference_obs_time` (the original UTC timestamp string from the input CSV).
ANTENNA_REFERENCE_POINTS: dict[str, dict[str, str | int]] = {
    "TP4": {"reference_row": 51},
    "TP5": {"reference_row": 3},
    "TP10": {"reference_row": 165},
    "TP15": {"reference_row": 11},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Antenna CSV files from UTC timestamps to HKT timestamps."
    )
    parser.add_argument(
        "--input-dir",
        default="Antenna",
        help="Directory containing Antenna CSV files (default: Antenna).",
    )
    parser.add_argument(
        "--output-dir",
        default="Antenna_HKT",
        help="Directory for converted CSV files (default: Antenna_HKT).",
    )
    return parser.parse_args()


def convert_timestamp(raw_timestamp: str) -> str:
    parsed = datetime.strptime(raw_timestamp, UTC_INPUT_FORMAT).replace(tzinfo=timezone.utc)
    return parsed.astimezone(HKT).strftime("%Y-%m-%d %H:%M:%S")


def format_decimal(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def select_reference_signal(rows: list[list[str]], reference_config: dict[str, str | int] | None) -> Decimal:
    if reference_config is not None:
        reference_row = reference_config.get("reference_row")
        reference_obs_time = reference_config.get("reference_obs_time")

        if reference_row is not None and reference_obs_time is not None:
            raise ValueError("Specify only one of reference_row or reference_obs_time for an antenna.")

        if reference_row is not None:
            if not isinstance(reference_row, int):
                raise ValueError("reference_row must be an integer.")
            if reference_row < 1 or reference_row > len(rows):
                raise ValueError(f"Reference row {reference_row} is out of range for the input file.")
            reference_row_data = rows[reference_row - 1]
            if len(reference_row_data) < 4 or reference_row_data[3] == "":
                raise ValueError(f"Reference row {reference_row} does not contain a valid signal value.")
            return Decimal(reference_row_data[3])

        if reference_obs_time is not None:
            if not isinstance(reference_obs_time, str):
                raise ValueError("reference_obs_time must be a string.")
            for row in rows:
                if len(row) < 4 or row[3] == "":
                    continue
                if row[0] == reference_obs_time:
                    return Decimal(row[3])
            raise ValueError(f"Reference timestamp {reference_obs_time!r} was not found in the input file.")

    signal_values = [Decimal(row[3]) for row in rows if len(row) >= 4 and row[3] != ""]
    if not signal_values:
        raise ValueError("No valid signal values found in the input file.")

    return max(signal_values)


def convert_csv_file(
    input_path: Path,
    output_path: Path,
) -> None:
    with input_path.open("r", encoding="utf-8", newline="") as file_handle:
        rows = list(csv.reader(file_handle))

    if not rows:
        return

    reference_config = ANTENNA_REFERENCE_POINTS.get(input_path.stem)
    reference_signal = select_reference_signal(rows, reference_config)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.writer(file_handle)
        writer.writerow(["obsTime", "Signal drop"])

        for row in rows:
            if len(row) < 4:
                continue

            if row[3] == "":
                continue

            signal_drop = reference_signal - Decimal(row[3])
            writer.writerow([convert_timestamp(row[0]), format_decimal(signal_drop)])


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    for input_path in sorted(input_dir.glob("*.csv")):
        output_path = output_dir / input_path.name
        convert_csv_file(input_path, output_path)


if __name__ == "__main__":
    main()