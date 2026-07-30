# rainfall_data

This repository contains a PowerShell script that downloads the Hong Kong Observatory hourly rainfall record and saves it to a UTF-8 text file.

## Script

File: [fetch_rainfall.ps1](fetch_rainfall.ps1)

Default output: `rainfall 21Jul 1600HKT.txt`-style filenames in the same folder as the script, based on the record time returned by the API.

## Run manually

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\fetch_rainfall.ps1"
```

## Task Scheduler

Use the wrapper script so the task never pauses for an execution policy prompt:

- Program/script: `C:\path\to\fetch_rainfall.cmd`
- Add arguments: optional output path, for example `"C:\path\to\rainfall.txt"`
- Start in: `C:\path\to`

If you want to run the PowerShell script directly, make sure the command includes `-ExecutionPolicy Bypass`.

## Convert To CSV

File: [convert_rainfall_to_csv.py](convert_rainfall_to_csv.py)

This script reads every `.txt` file in [Data/](Data) and writes a wide CSV where `obsTime` is the row key, each `automaticWeatherStation` is a column, and each cell contains the matching `value`.

Run it with:

```bash
python convert_rainfall_to_csv.py --input-dir Data --output rainfall.csv
```

## Convert Antenna CSVs

File: [convert_antenna_to_csv.py](convert_antenna_to_csv.py)

This script reads every `.csv` file in [Antenna/](Antenna), converts the first UTC timestamp column to HKT, and writes `reference signal - original value` as `Signal drop` in [Antenna_HKT/](Antenna_HKT) using the same `YYYY-MM-DD HH:MM:SS` format as [rainfall.csv](rainfall.csv). Edit the `ANTENNA_REFERENCE_POINTS` table in [convert_antenna_to_csv.py](convert_antenna_to_csv.py) to set a custom reference row or UTC timestamp for each antenna; files not listed in the table still fall back to the maximum signal in that file.

Run it with:

```bash
python convert_antenna_to_csv.py --input-dir Antenna --output-dir Antenna_HKT
```

## Estimate Antenna-Rainfall Relationship

File: [estimate_antenna_rainfall_relationship.py](estimate_antenna_rainfall_relationship.py)

This script processes each file in [Antenna_HKT/](Antenna_HKT) separately, bucket-maxes the signal drop for that antenna over 5-minute windows, linearly interpolates rainfall onto the same buckets, and then fits a linear equation constrained to pass through the origin with `Tai Po Market` rainfall as the input variable and that antenna's `Signal drop` as the output variable.

It writes SVG plots to [antenna_rainfall_plots/](antenna_rainfall_plots) for each antenna: one shows the rainfall vs signal-drop relationship together with the fitted linear equation, and another shows the time-series check for rainfall and signal drop. It also writes an aggregate [average_rainfall_signal_drop_equation.svg](antenna_rainfall_plots/average_rainfall_signal_drop_equation.svg) plot that overlays all antenna bucketed points with the averaged linear equation.

The output CSV includes one row per antenna, with `antenna` and `average_signal_drop` for the 5-minute bucketed signal-drop values used in that fit, plus an `AVERAGE` summary row that averages the linear coefficients across all antenna equations.

It also writes [antenna_rainfall_buckets.csv](antenna_rainfall_buckets.csv) with `antenna`, `timebucket`, `rainfall`, and `signal_drop` for manual checking.

Run it with:

```bash
python estimate_antenna_rainfall_relationship.py --rainfall-input rainfall.csv --antenna-input-dir Antenna_HKT --output antenna_rainfall_relationship.csv
```

## Rainfall Threshold Probability

File: [naive_bayes_rainfall.py](naive_bayes_rainfall.py)

Given a rainfall threshold `x` in mm, this script estimates the probability for each location to have rainfall below `x` under the condition that Tai Po Market rainfall is above `x`, using a binary Naive Bayes model with Laplace smoothing.
If a location has no co-occurrence samples with `Tai Po Market > x`, the generated probability is written as `NA`.
You can use separate thresholds with `--x-threshold` and `--y-threshold` to estimate `P(location rainfall < Y | Tai Po Market rainfall > X)`.

Run it with:

```bash
python naive_bayes_rainfall.py --input rainfall.csv --threshold 5 --output naive_bayes_probabilities.csv
```

```bash
python naive_bayes_rainfall.py --input rainfall.csv --x-threshold 10 --y-threshold 5 --output naive_bayes_probabilities.csv
```

## Direct Conditional Probability

File: [conditional_probability_rainfall.py](conditional_probability_rainfall.py)

This script calculates direct conditional probability from observed frequency without Naive Bayes smoothing:
`P(location rainfall < Y | Tai Po Market rainfall > X) = count(location < Y and Tai Po Market > X) / count(Tai Po Market > X)`.
If no rows satisfy `Tai Po Market > X` for a location (after removing invalid/missing values), the probability is written as `NA`.

Run it with:

```bash
python conditional_probability_rainfall.py --input rainfall.csv --threshold 5 --output conditional_probabilities.csv
```

```bash
python conditional_probability_rainfall.py --input rainfall.csv --x-threshold 10 --y-threshold 5 --output conditional_probabilities.csv
```

## Average Rainfall When Tai Po Market > x

File: [average_rainfall_when_tai_po_above_x.py](average_rainfall_when_tai_po_above_x.py)

This script calculates average rainfall for each location using only rows where `Tai Po Market > x`.
If a location has no qualifying samples, the output average is written as `NA`.

Run it with:

```bash
python average_rainfall_when_tai_po_above_x.py --input rainfall.csv --threshold 5 --output average_rainfall_when_tai_po_above_x.csv
```