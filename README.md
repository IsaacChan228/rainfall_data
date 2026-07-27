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

## Naive Bayes Probability

File: [naive_bayes_rainfall.py](naive_bayes_rainfall.py)

Given a threshold `x`, this script estimates the probability for each location to satisfy `value > x` under the condition `Tai Po Market > x`, using binary Naive Bayes with Laplace smoothing.

Run it with:

```bash
python naive_bayes_rainfall.py --input rainfall.csv --threshold 5 --output naive_bayes_probabilities.csv
```