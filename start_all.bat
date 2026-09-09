@echo off
title VARUN-ASTRA Platform Launcher
echo ===================================================================
echo   Starting VARUN-ASTRA Full Monorepo Platform
echo ===================================================================
echo.

echo [1/4] Starting Next.js Web Dashboard and NestJS API Gateway...
start "VARUN Web and API Gateway" cmd /k "pnpm dev"

echo [2/4] Starting Phase 1 SAR Detection Engine (:8101)...
start "VARUN Phase 1 Detection Engine" cmd /k "python -m uvicorn app.main:app --app-dir services/detection-engine --host 0.0.0.0 --port 8101 --reload"

echo [3/4] Starting Phase 2 Drift Engine (:8102)...
start "VARUN Phase 2 Drift Engine" cmd /k "python -m uvicorn app.main:app --app-dir services/drift-engine --host 0.0.0.0 --port 8102 --reload"

echo [4/4] Starting Phase 3 AIS Attribution Engine (:8103)...
start "VARUN Phase 3 AIS Engine" cmd /k "services\ais-engine\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir services/ais-engine --host 0.0.0.0 --port 8103 --reload"

echo.
echo ===================================================================
echo   All services launched in separate windows!
echo   - Web Dashboard : http://localhost:3000
echo   - REST API      : http://localhost:3001/api/v1
echo   - Phase 1 API   : http://localhost:8101/docs
echo   - Phase 2 API   : http://localhost:8102/docs
echo   - Phase 3 API   : http://localhost:8103/docs
echo ===================================================================
pause
