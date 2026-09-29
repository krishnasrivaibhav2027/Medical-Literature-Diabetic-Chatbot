@echo off
setlocal
set "SOURCE=%~dp0scripts\pgvector_binaries"
set "PGROOT=C:\Program Files\PostgreSQL\18"

echo ========================================================
echo  Installing pgvector into PostgreSQL 18
echo  Source: %SOURCE%
echo  Target: %PGROOT%
echo ========================================================

copy /Y "%SOURCE%\vector.dll" "%PGROOT%\lib\"
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to copy vector.dll to %PGROOT%\lib.
    echo Please make sure you Right-Click this file and select "Run as administrator"!
    echo.
    pause
    exit /b 1
)

copy /Y "%SOURCE%\vector.control" "%PGROOT%\share\extension\"
copy /Y "%SOURCE%\vector--*.sql" "%PGROOT%\share\extension\"

echo.
echo ========================================================
echo  [SUCCESS] pgvector extension successfully installed!
echo ========================================================
echo You can now return to the IDE.
pause
