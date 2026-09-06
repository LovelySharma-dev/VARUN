$ErrorActionPreference = "Stop"

$ROOT = "C:\Users\akhil\Projects\VARUN"
Set-Location $ROOT

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " VARUN FINAL ENGINE REPAIR - ACTUAL REPOSITORY" -ForegroundColor Cyan
Write-Host " Phase1=8001 | Phase2=8002 | Phase3=8003 | API=4000" -ForegroundColor Cyan
Write-Host " NO DATABASE | NO MIGRATION | NO PRISMA SCHEMA | NO FRONTEND" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

function Assert-Path($p) {
    if (!(Test-Path $p)) { throw "Required path missing: $p" }
}

function Get-Health($port) {
    try {
        return Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 2
    } catch {
        return $null
    }
}

function Stop-PortProcess($port) {
    $owners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)

    foreach ($ownerPid in $owners) {
        if ($ownerPid) {
            Write-Host "Stopping PID $ownerPid on port $port..." -ForegroundColor Yellow
            & taskkill.exe /PID $ownerPid /T /F 2>$null | Out-Null
        }
    }
}

function Wait-Engine($name, $port, $expectedService, $workingDir) {
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 1
        $r = Get-Health $port
        if ($r -and $r.status -eq "ok" -and $r.service -eq $expectedService) {
            Write-Host "$name [$port] = UP ($expectedService)" -ForegroundColor Green
            return
        }
    }

    Write-Host ""
    Write-Host "FAILED: $name did not become healthy." -ForegroundColor Red
    $log = Join-Path $ROOT ("logs\" + $name.ToLower() + "-engine.err.log")
    if (Test-Path $log) {
        Write-Host "--- $log ---" -ForegroundColor Red
        Get-Content $log -Tail 80
    }
    throw "$name engine failed on port $port."
}

# ------------------------------------------------------------
# 1. VERIFY ACTUAL REPOSITORY
# ------------------------------------------------------------
Write-Host "[1/8] Verifying actual repository..." -ForegroundColor Yellow

@(
    "apps\api",
    "apps\web",
    "packages\contracts",
    "services\detection-engine",
    "services\drift-engine",
    "services\ais-engine",
    "apps\api\prisma\schema.prisma",
    "apps\api\src\phase3\phase3.controller.ts",
    "apps\api\src\phase3\phase3.service.ts"
) | ForEach-Object { Assert-Path $_ }

Write-Host "Repository = PASS" -ForegroundColor Green

# ------------------------------------------------------------
# 2. REPAIR ONLY MISSING PHASE2/PHASE3 ENTRYPOINTS
#    These are the exact scaffold entrypoints from the supplied
#    VARUN starter repository. Phase1 is NOT overwritten.
# ------------------------------------------------------------
Write-Host ""
Write-Host "[2/8] Checking scientific entrypoints..." -ForegroundColor Yellow

$phase1Main = Join-Path $ROOT "services\detection-engine\app\main.py"
$phase2Dir  = Join-Path $ROOT "services\drift-engine\app"
$phase3Dir  = Join-Path $ROOT "services\ais-engine\app"
$phase2Main = Join-Path $phase2Dir "main.py"
$phase3Main = Join-Path $phase3Dir "main.py"

Assert-Path $phase1Main
New-Item -ItemType Directory -Force $phase2Dir | Out-Null
New-Item -ItemType Directory -Force $phase3Dir | Out-Null

$phase2Code = @'
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="VARUN Phase 2 Drift", version="0.1.0")

class DriftRequest(BaseModel):
    case_id: str
    phase2_run_id: str
    phase1_handoff_ref: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "phase2-drift"}

@app.post("/internal/v1/drift-runs")
def run(request: DriftRequest):
    return {
        "status": "QUEUED_FIXTURE",
        "identity": request.model_dump(),
        "message": "OpenDrift/OpenOil stages are intentionally not faked in scaffold."
    }
'@

$phase3Code = @'
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="VARUN Phase 3 AIS", version="0.1.0")

class AnalysisRequest(BaseModel):
    contract_version: str
    case_id: str
    phase2_run_id: str
    phase3_run_id: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "phase3-ais"}

@app.post("/internal/v1/analysis-runs")
def analyse(request: AnalysisRequest):
    return {
        "status": "QUEUED_FIXTURE",
        "identity": request.model_dump(),
        "message": "Candidate ranking is added only after AIS provenance and feature tests pass."
    }
'@

if (!(Test-Path $phase2Main)) {
    Set-Content -Path $phase2Main -Value $phase2Code -Encoding UTF8
    Write-Host "Created Phase2 app\main.py" -ForegroundColor Green
} else {
    Write-Host "Phase2 app\main.py = PRESENT" -ForegroundColor Green
}

if (!(Test-Path $phase3Main)) {
    Set-Content -Path $phase3Main -Value $phase3Code -Encoding UTF8
    Write-Host "Created Phase3 app\main.py" -ForegroundColor Green
} else {
    Write-Host "Phase3 app\main.py = PRESENT" -ForegroundColor Green
}

# ------------------------------------------------------------
# 3. CHECK PYTHON DEPENDENCIES
# ------------------------------------------------------------
Write-Host ""
Write-Host "[3/8] Checking Python environment..." -ForegroundColor Yellow

$python = Join-Path $ROOT ".venv\Scripts\python.exe"
Assert-Path $python

& $python -c "import fastapi, uvicorn; print('FastAPI/Uvicorn = OK')"
if ($LASTEXITCODE -ne 0) {
    throw "The existing .venv does not contain FastAPI/Uvicorn."
}

Write-Host "Python environment = PASS" -ForegroundColor Green

# ------------------------------------------------------------
# 4. NORMALIZE API ENGINE URL CONFIGURATION
# ------------------------------------------------------------
Write-Host ""
Write-Host "[4/8] Normalizing API engine URLs..." -ForegroundColor Yellow

$envFiles = @(
    ".env",
    ".env.local",
    "apps\api\.env",
    "apps\api\.env.local"
)

$foundEnv = $false

foreach ($f in $envFiles) {
    if (Test-Path $f) {
        $foundEnv = $true
        $x = Get-Content $f -Raw

        $x = $x -replace '(?m)^\s*PHASE1_ENGINE_URL\s*=.*$', 'PHASE1_ENGINE_URL=http://127.0.0.1:8001'
        $x = $x -replace '(?m)^\s*PHASE2_ENGINE_URL\s*=.*$', 'PHASE2_ENGINE_URL=http://127.0.0.1:8002'
        $x = $x -replace '(?m)^\s*PHASE3_ENGINE_URL\s*=.*$', 'PHASE3_ENGINE_URL=http://127.0.0.1:8003'

        if ($x -notmatch '(?m)^\s*PHASE1_ENGINE_URL\s*=') { $x += "`r`nPHASE1_ENGINE_URL=http://127.0.0.1:8001" }
        if ($x -notmatch '(?m)^\s*PHASE2_ENGINE_URL\s*=') { $x += "`r`nPHASE2_ENGINE_URL=http://127.0.0.1:8002" }
        if ($x -notmatch '(?m)^\s*PHASE3_ENGINE_URL\s*=') { $x += "`r`nPHASE3_ENGINE_URL=http://127.0.0.1:8003" }

        Set-Content -Path $f -Value $x.TrimEnd() -Encoding UTF8
        Write-Host "Updated $f" -ForegroundColor Green
    }
}

if (!$foundEnv) {
    $envPath = Join-Path $ROOT ".env"
    @"
DATABASE_URL=postgresql://varun:change-me@localhost:5432/varun
PHASE1_ENGINE_URL=http://127.0.0.1:8001
PHASE2_ENGINE_URL=http://127.0.0.1:8002
PHASE3_ENGINE_URL=http://127.0.0.1:8003
ARTIFACT_ROOT=./artifacts
OFFLINE_DEMO=true
"@ | Set-Content -Path $envPath -Encoding UTF8
    Write-Host "Created root .env with engine URLs." -ForegroundColor Green
}

# ------------------------------------------------------------
# 5. BUILD API BEFORE RESTARTING IT
# ------------------------------------------------------------
Write-Host ""
Write-Host "[5/8] Building API..." -ForegroundColor Yellow

pnpm --filter api build
if ($LASTEXITCODE -ne 0) {
    throw "API BUILD FAILED."
}

Write-Host "API BUILD = PASS" -ForegroundColor Green

# ------------------------------------------------------------
# 6. CLEANLY REPLACE ONLY PORT 8001/8002/8003 PROCESSES
#    IMPORTANT: verify service identity, so stale Phase1 on 8003
#    can never be mistaken for Phase3.
# ------------------------------------------------------------
Write-Host ""
Write-Host "[6/8] Starting correct scientific engines..." -ForegroundColor Yellow

New-Item -ItemType Directory -Force (Join-Path $ROOT "logs") | Out-Null

$engineDefs = @(
    @{Name="Phase1"; Dir="services\detection-engine"; Port=8001; Service="detection-engine"},
    @{Name="Phase2"; Dir="services\drift-engine";     Port=8002; Service="phase2-drift"},
    @{Name="Phase3"; Dir="services\ais-engine";       Port=8003; Service="phase3-ais"}
)

foreach ($e in $engineDefs) {
    $existing = Get-Health $e.Port

    if ($existing -and
        $existing.status -eq "ok" -and
        $existing.service -eq $e.Service) {
        Write-Host "$($e.Name) already correct and healthy; leaving it running." -ForegroundColor Green
        continue
    }

    if ($existing) {
        Write-Host "$($e.Name) port $($e.Port) has WRONG service '$($existing.service)'. Replacing it." -ForegroundColor Yellow
    } else {
        Write-Host "$($e.Name) port $($e.Port) is DOWN. Starting it." -ForegroundColor Yellow
    }

    Stop-PortProcess $e.Port

    $outLog = Join-Path $ROOT ("logs\" + $e.Name.ToLower() + "-engine.log")
    $errLog = Join-Path $ROOT ("logs\" + $e.Name.ToLower() + "-engine.err.log")

    Remove-Item $outLog,$errLog -Force -ErrorAction SilentlyContinue

    Start-Process `
        -FilePath $python `
        -ArgumentList @("-m","uvicorn","app.main:app","--host","127.0.0.1","--port",[string]$e.Port) `
        -WorkingDirectory (Join-Path $ROOT $e.Dir) `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -WindowStyle Hidden | Out-Null
}

foreach ($e in $engineDefs) {
    Wait-Engine $e.Name $e.Port $e.Service (Join-Path $ROOT $e.Dir)
}

# ------------------------------------------------------------
# 7. RESTART API ONLY AFTER ALL ENGINES ARE HEALTHY
#    Separate stdout/stderr files avoid the previous
#    Start-Process "same redirect" error.
# ------------------------------------------------------------
Write-Host ""
Write-Host "[7/8] Restarting API with fixed engine configuration..." -ForegroundColor Yellow

# Stop the process tree owning port 4000. Port 4000 belongs to this VARUN API.
Stop-PortProcess 4000
Start-Sleep -Seconds 1

$apiOut = Join-Path $ROOT "logs\api-runtime.log"
$apiErr = Join-Path $ROOT "logs\api-runtime.err.log"
Remove-Item $apiOut,$apiErr -Force -ErrorAction SilentlyContinue

# Force the correct values into the child process as well.
$env:PHASE1_ENGINE_URL = "http://127.0.0.1:8001"
$env:PHASE2_ENGINE_URL = "http://127.0.0.1:8002"
$env:PHASE3_ENGINE_URL = "http://127.0.0.1:8003"

$pkg = Get-Content ".\apps\api\package.json" -Raw | ConvertFrom-Json

if ($pkg.scripts.PSObject.Properties.Name -contains "start:dev") {
    $startScript = "start:dev"
} elseif ($pkg.scripts.PSObject.Properties.Name -contains "start") {
    $startScript = "start"
} else {
    throw "apps\api\package.json has neither start:dev nor start."
}

Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @("/c","pnpm --filter api $startScript") `
    -WorkingDirectory $ROOT `
    -RedirectStandardOutput $apiOut `
    -RedirectStandardError $apiErr `
    -WindowStyle Hidden | Out-Null

$apiReady = $false

for ($i = 1; $i -le 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:4000/api/v1/health" -TimeoutSec 2
        if ($h.status -eq "ok" -and
            $h.services.api -eq "up" -and
            $h.services.phase1Engine -eq "up" -and
            $h.services.phase2Engine -eq "up" -and
            $h.services.phase3Engine -eq "up") {
            $apiReady = $true
            break
        }
    } catch {}
}

if (!$apiReady) {
    Write-Host ""
    Write-Host "API did not reach full health." -ForegroundColor Red

    if (Test-Path $apiOut) {
        Write-Host "--- API stdout ---" -ForegroundColor Red
        Get-Content $apiOut -Tail 80
    }

    if (Test-Path $apiErr) {
        Write-Host "--- API stderr ---" -ForegroundColor Red
        Get-Content $apiErr -Tail 80
    }

    throw "API health is not fully OK."
}

# ------------------------------------------------------------
# 8. FINAL READ-ONLY VERIFICATION
# ------------------------------------------------------------
Write-Host ""
Write-Host "[8/8] Final verification..." -ForegroundColor Yellow

$health = Invoke-RestMethod "http://127.0.0.1:4000/api/v1/health" -TimeoutSec 5
$health | ConvertTo-Json -Depth 10

if ($health.status -ne "ok") {
    throw "FINAL FAILURE: API reports degraded health."
}

$RUN = "3ec8c5b8-345b-4a3b-8c9b-2251c469db8a"

Write-Host ""
Write-Host "PHASE3 DATABASE-BACKED ROUTE:" -ForegroundColor Cyan
$candidates = Invoke-RestMethod `
    "http://127.0.0.1:4000/api/v1/runs/$RUN/phase3/candidates" `
    -TimeoutSec 10

$candidates | ConvertTo-Json -Depth 50

if (!$candidates.candidates -or $candidates.candidates.Count -lt 1) {
    throw "FINAL FAILURE: populated Phase3 run returned zero candidates."
}

$candidateId = $candidates.candidates[0].candidateId

Write-Host ""
Write-Host "CANDIDATE DETAIL:" -ForegroundColor Cyan
$detail = Invoke-RestMethod `
    "http://127.0.0.1:4000/api/v1/runs/$RUN/phase3/candidates/$candidateId" `
    -TimeoutSec 10

$detail | ConvertTo-Json -Depth 50

$publicJson = ($candidates,$detail | ConvertTo-Json -Depth 100)

if ($publicJson -match '(?i)"mmsi"\s*:') {
    throw "PRIVACY FAILURE: MMSI found in public Phase3 response."
}

if ($publicJson -match '(?i)ground.?truth') {
    throw "PRIVACY FAILURE: ground truth found in public Phase3 response."
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " VARUN FINAL ENGINE/API INTEGRATION = PASS" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Phase1 8001        = UP"
Write-Host "Phase2 8002        = UP"
Write-Host "Phase3 8003        = UP"
Write-Host "API 4000           = UP"
Write-Host "API health         = OK"
Write-Host "Phase3 candidate   = PASS"
Write-Host "Candidate detail   = PASS"
Write-Host "MMSI leakage       = NONE"
Write-Host "Ground truth       = NONE"
Write-Host "Database migration = NONE"
Write-Host "Prisma schema      = UNTOUCHED"
Write-Host "Frontend           = UNTOUCHED"
Write-Host "============================================================" -ForegroundColor Green


