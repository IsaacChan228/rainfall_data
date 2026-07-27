from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert rainfall txt files in Data/ into a wide CSV by obsTime."
    )
    parser.add_argument(
        "--input-dir",
        default="Data",
        help="Directory containing rainfall txt files (default: Data).",
    )
    parser.add_argument(
        "--output",
        default="rainfall.csv",
        help="Output CSV path (default: rainfall.csv).",
    )
    return parser.parse_args()


def load_rainfall_records(input_dir: Path) -> tuple[list[str], list[dict[str, str]]]:
    records: list[dict[str, str]] = []
    station_names: set[str] = set()

    def format_obs_time(raw_obs_time: str) -> str:
        return datetime.fromisoformat(raw_obs_time).strftime("%Y-%m-%d %H:%M:%S")

    for file_path in sorted(input_dir.glob("*.txt")):
        with file_path.open("r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)

        obs_time = format_obs_time(data["obsTime"])
        record: dict[str, str] = {"obsTime": obs_time}

        for rainfall in data.get("hourlyRainfall", []):
            station_name = rainfall["automaticWeatherStation"]
            station_names.add(station_name)
            record[station_name] = rainfall.get("value", "")

        records.append(record)

    def sort_key(item: dict[str, str]) -> datetime:
        return datetime.fromisoformat(item["obsTime"])

    records.sort(key=sort_key)

    ordered_station_names = sorted(station_names)
    if "Tai Po Market" in ordered_station_names:
        ordered_station_names.remove("Tai Po Market")
        ordered_station_names.insert(0, "Tai Po Market")

    return ordered_station_names, records


def write_csv(output_path: Path, station_names: list[str], records: list[dict[str, str]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["obsTime", *station_names]
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_path = Path(args.output)

    station_names, records = load_rainfall_records(input_dir)
    write_csv(output_path, station_names, records)


if __name__ == "__main__":
    main()