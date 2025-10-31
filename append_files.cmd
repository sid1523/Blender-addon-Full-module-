@echo off
setlocal enabledelayedexpansion

rem Delete old a.txt if it exists
if exist a.txt del a.txt

rem Loop through all files recursively
for /r %%f in (*) do (
    rem Skip a.txt itself to avoid infinite loop
    if /i not "%%~nxf"=="a.txt" (
        rem Skip any files inside __pycache__ folders
        echo %%~f | findstr /i "\\__pycache__\\" >nul
        if errorlevel 1 (
            echo ===== FILE: %%f ===== >> a.txt
            type "%%f" >> a.txt
            echo. >> a.txt
        )
    )
)

echo Done! All files appended to a.txt
pause
