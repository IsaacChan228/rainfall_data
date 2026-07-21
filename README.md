# rainfall_data

This repository contains a PowerShell script that downloads the Hong Kong Observatory hourly rainfall record and saves it to a UTF-8 text file.

## Script

File: [fetch_rainfall.ps1](fetch_rainfall.ps1)

Default output: `hourly_rainfall.txt` in the same folder as the script.

## Run manually

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\path\to\fetch_rainfall.ps1" -OutputPath "C:\path\to\hourly_rainfall.txt"
```

## Task Scheduler

Use these values in a scheduled task:

- Program/script: `powershell.exe`
- Add arguments: `-NoProfile -ExecutionPolicy Bypass -File "C:\path\to\fetch_rainfall.ps1" -OutputPath "C:\path\to\hourly_rainfall.txt"`
- Start in: `C:\path\to`