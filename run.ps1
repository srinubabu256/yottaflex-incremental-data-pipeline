param (
    [Parameter(Position = 0)]
    [string]$Command = "help",
    [Parameter(Position = 1)]
    [string]$Arg1 = ""
)

switch ($Command.ToLower()) {
    "init" {
        python -m src.main init-db
    }
    "init-db" {
        python -m src.main init-db
    }
    { $_ -in "sample-run", "sample_run" } {
        Write-Host ">>> 1. Ingesting Valid Events (CREATE v=1)..." -ForegroundColor Cyan
        python -m src.main run --input data/sample/valid/events.csv
        Write-Host ">>> 2. Ingesting Updates (UPDATE v=2)..." -ForegroundColor Cyan
        python -m src.main run --input data/sample/updates/events.csv
        Write-Host ">>> 3. Ingesting Reversals (REVERSE v=3)..." -ForegroundColor Cyan
        python -m src.main run --input data/sample/reversals/events.csv
        Write-Host ">>> 4. Ingesting Late Events..." -ForegroundColor Cyan
        python -m src.main run --input data/sample/late_events/events.csv
        Write-Host ">>> 5. Ingesting Invalid Records (Quarantine test)..." -ForegroundColor Cyan
        python -m src.main run --input data/sample/invalid_events/events.csv
        Write-Host ">>> 6. Running Reconciliation Audit..." -ForegroundColor Cyan
        python -m src.main reconcile
        Write-Host ">>> 7. Generating Output Reports..." -ForegroundColor Cyan
        python -m src.main report
    }
    "run" {
        if (-not $Arg1) {
            $Arg1 = "data/sample/valid/events.csv"
        }
        python -m src.main run --input $Arg1
    }
    "reconcile" {
        python -m src.main reconcile
    }
    "report" {
        python -m src.main report
    }
    "runs" {
        python -m src.main runs --limit 10
    }
    "rejects" {
        python -m src.main rejects --limit 10
    }
    "test" {
        pytest -v
    }
    "cov" {
        pytest --cov=src --cov-report=term-missing
    }
    "benchmark" {
        $rows = if ($Arg1) { $Arg1 } else { "10000" }
        python -m src.main benchmark --rows $rows --seed 42
    }
    "clean" {
        Remove-Item -Force -Recurse -ErrorAction SilentlyContinue .pytest_cache, .coverage, htmlcov, yottaflex.db, yottaflex.db-wal, yottaflex.db-shm
        Get-ChildItem -Path . -Filter "__pycache__" -Recurse -Directory | Remove-Item -Force -Recurse -ErrorAction SilentlyContinue
        Write-Host "Cleanup completed." -ForegroundColor Green
    }
    default {
        Write-Host "YottaFlex PowerShell Task Runner" -ForegroundColor Yellow
        Write-Host "Usage: .\run.ps1 <command> [arg]"
        Write-Host ""
        Write-Host "Commands:"
        Write-Host "  init         Initialize SQLite schema and seed reference data"
        Write-Host "  sample-run   Run all 5 sample incremental event files & reconcile"
        Write-Host "  run <file>   Run pipeline on specified input file"
        Write-Host "  reconcile    Run cross-table parity audits"
        Write-Host "  report       Generate CSV and JSON reports"
        Write-Host "  runs         List recent pipeline runs"
        Write-Host "  rejects      List quarantined rejected records"
        Write-Host "  test         Run all pytest suites"
        Write-Host "  cov          Run pytest with coverage report"
        Write-Host "  benchmark    Run benchmark (default: 10000 rows)"
        Write-Host "  clean        Remove DB and test cache artifacts"
    }
}
