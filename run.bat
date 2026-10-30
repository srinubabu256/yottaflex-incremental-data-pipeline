@echo off
setlocal

set CMD=%1
if "%CMD%"=="" set CMD=help
shift

if /i "%CMD%"=="init" goto init
if /i "%CMD%"=="init-db" goto init
if /i "%CMD%"=="sample-run" goto sample_run
if /i "%CMD%"=="run" goto run_single
if /i "%CMD%"=="reconcile" goto reconcile
if /i "%CMD%"=="report" goto report
if /i "%CMD%"=="runs" goto runs
if /i "%CMD%"=="rejects" goto rejects
if /i "%CMD%"=="test" goto test
if /i "%CMD%"=="cov" goto cov
if /i "%CMD%"=="benchmark" goto benchmark
if /i "%CMD%"=="clean" goto clean
goto help

:init
python -m src.main init-db
goto end

:sample_run
echo [1/7] Ingesting initial valid transactions...
python -m src.main run --input data\sample\valid\events.csv
echo [2/7] Ingesting transaction updates...
python -m src.main run --input data\sample\updates\events.csv
echo [3/7] Ingesting transaction reversals...
python -m src.main run --input data\sample\reversals\events.csv
echo [4/7] Ingesting late-arriving events...
python -m src.main run --input data\sample\late_events\events.csv
echo [5/7] Ingesting invalid events (quarantine check)...
python -m src.main run --input data\sample\invalid_events\events.csv
echo [6/7] Running reconciliation check...
python -m src.main reconcile
echo [7/7] Generating output reports...
python -m src.main report
goto end

:run_single
set INPUT_FILE=%1
if "%INPUT_FILE%"=="" set INPUT_FILE=data\sample\valid\events.csv
python -m src.main run --input %INPUT_FILE%
goto end

:reconcile
python -m src.main reconcile
goto end

:report
python -m src.main report
goto end

:runs
python -m src.main runs --limit 10
goto end

:rejects
python -m src.main rejects --limit 10
goto end

:test
pytest -v
goto end

:cov
pytest --cov=src --cov-report=term-missing
goto end

:benchmark
python -m src.main benchmark --rows 10000 --seed 42
goto end

:clean
if exist yottaflex.db del /f /q yottaflex.db*
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist .coverage del /f /q .coverage
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo Cleaned successfully.
goto end

:help
echo YottaFlex Command Line Runner
echo Usage: run.bat [command]
echo.
echo Available commands:
echo   init         Initialize database and seed reference data
echo   sample-run   Run all 5 sample incremental stages and reconcile
echo   run [file]   Run pipeline on specified input file
echo   reconcile    Run metric reconciliation check
echo   report       Export CSV and JSON reports
echo   runs         Show recent pipeline runs
echo   rejects      Show quarantined invalid records
echo   test         Run pytest test suite
echo   cov          Run pytest with coverage
echo   benchmark    Run 10,000-row performance benchmark
echo   clean        Clean database and cache files
goto end

:end
endlocal
