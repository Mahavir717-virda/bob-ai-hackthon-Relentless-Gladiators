# GridPilot AI — Setup Guide

> **Team:** Relentless Gladiators · IBM Bob AI Hackathon 2026  
> **License:** Apache-2.0

---

## 1. Prerequisites

| Dependency | Minimum Version | Verified Version | Notes |
|---|---|---|---|
| **Node.js** | ≥ 22.x | 22.17.0 | Required for API Gateway (`--experimental-strip-types`) |
| **npm** | ≥ 10.x | 10.9.2 | Ships with Node.js |
| **Python** | ≥ 3.12 | 3.13.4 | Required for ML microservices |
| **Git** | any | — | Clone the repository |
| **Ollama** | latest | — | Local LLM inference engine |

### Install Python Dependencies

```powershell
# From project root
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

The `requirements.txt` includes:

| Package | Purpose |
|---|---|
| `fastapi`, `uvicorn[standard]` | Python microservice framework |
| `lightgbm` | Demand & renewable forecasting models |
| `xgboost` | Spike classification & root-cause models |
| `scikit-learn` | Isolation Forest anomaly detection |
| `pandas`, `numpy`, `pyarrow` | Data processing |
| `ortools` | Google OR-Tools MILP optimizer |
| `pyyaml`, `python-dotenv`, `httpx` | Utilities |

### Install Node.js Dependencies

```powershell
# From project root
npm install

# Frontend dependencies
cd apps\web
npm install
cd ..\..
```

---

## 2. Project Structure

```
gridpilot-ai/
├── apps/
│   ├── api/            # Node.js API Gateway (port 8000)
│   └── web/            # React + Vite frontend (port 5173)
├── services/
│   ├── data/           # Data / Substation Telemetry (port 8001)
│   ├── forecasting/    # Demand Forecasting (port 8002)
│   ├── renewable/      # Renewable Intelligence — Kaggle (port 8003)
│   └── optimization/   # Grid Optimization — OR-Tools (port 8004)
├── agent/
│   ├── orchestration/  # OperatorCopilot, OperatorBriefGenerator
│   ├── provider/       # Ollama LLM provider (Qwen 2.5)
│   ├── tools/          # Agent tool definitions
│   ├── prompts/        # System prompt templates
│   └── policies/       # Agent guardrail policies
├── ml/
│   ├── models/
│   │   ├── demand/     # Demand LightGBM + Spike XGBoost artifacts
│   │   └── renewable/  # Solar/Wind LightGBM, Isolation Forest, Root Cause XGBoost
│   └── datasets/
│       └── kaggle_power_system/  # OPSD time-series CSV files
├── shared/
│   ├── contracts/      # TypeScript contract schemas
│   ├── types/          # Shared type definitions
│   ├── constants/      # Grid constants
│   └── errors/         # Error types
├── scripts/            # Helper scripts
├── .env.example        # Environment variable template
└── requirements.txt    # Python dependencies
```

---

## 3. Environment Variables

Copy the template and fill in values:

```powershell
copy .env.example .env
```

| Variable | Purpose | Example Value | Required |
|---|---|---|---|
| `LLM_PROVIDER` | LLM backend selector | `ollama` | Yes |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://127.0.0.1:11434` | Yes |
| `OLLAMA_MODEL` | Ollama model name | `qwen2.5:1.5b` | Yes |
| `PORT` | API Gateway port | `8000` | Yes |
| `API_HOST` | API Gateway bind address | `0.0.0.0` | No (default: `0.0.0.0`) |
| `NODE_ENV` | Environment mode | `development` | No |
| `CORS_ORIGIN` | Allowed CORS origin | `http://localhost:3000` | No (default: `*`) |
| `VITE_API_BASE_URL` | Frontend API base URL | `http://localhost:8000` | No |
| `DATA_SERVICE_PORT` | Data service port | `8001` | No (default: `8001`) |
| `FORECASTING_SERVICE_PORT` | Forecasting service port | `8002` | No (default: `8002`) |
| `RENEWABLE_SERVICE_PORT` | Renewable service port | `8003` | No (default: `8003`) |
| `OPTIMIZATION_SERVICE_PORT` | Optimization service port | `8004` | No (default: `8004`) |
| `LOG_LEVEL` | API gateway log level | `info` | No |
| `GRID_ZONE_ID` | Default grid zone | `NL_LIANDER_ZONE_1` | No |
| `GRID_TIME_STEP_MINUTES` | Grid time step | `15` | No |
| `OPTIMIZATION_SOLVER_TIMEOUT_MS` | Solver timeout | `5000` | No |

The API Gateway reads `.env` from the project root automatically via `apps/api/src/config.ts`. No additional dotenv setup is needed.

---

## 4. ML Model Artifacts

All trained models are pre-committed in the repository and loaded automatically by the Python services at first request. **No manual training step is required.**

### Demand Models — `ml/models/demand/`

| File | Model | Framework | Task |
|---|---|---|---|
| `demand_lgbm.pkl` | Demand LightGBM | LightGBM | Load demand forecasting (15/30/60 min) |
| `demand-lgbm-v1_h15min.txt` | LightGBM (text) | LightGBM | 15-minute horizon booster |
| `demand-lgbm-v1_h30min.txt` | LightGBM (text) | LightGBM | 30-minute horizon booster |
| `demand-lgbm-v1_h60min.txt` | LightGBM (text) | LightGBM | 60-minute horizon booster |
| `demand-spike-xgb-v1.joblib` | Spike XGBoost | XGBoost | Demand spike classification |
| `spike_xgb.pkl` | Spike XGBoost | XGBoost | Spike classifier (pkl format) |

### Renewable Models — `ml/models/renewable/`

| File | Model | Framework | Task |
|---|---|---|---|
| `solar_lgbm_solar_park_synth_01.pkl` | Solar LightGBM | LightGBM | Solar generation forecasting |
| `wind_lgbm_wind_park_synth_01.pkl` | Wind LightGBM | LightGBM | Wind generation forecasting |
| `root_cause_xgb_solar.pkl` | Solar Root Cause | XGBoost | Solar anomaly root cause |
| `root_cause_xgb_wind.pkl` | Wind Root Cause | XGBoost | Wind anomaly root cause |

### Kaggle Renewable Models — `ml/models/renewable/artifacts/kaggle/`

| Pattern | Count | Model | Task |
|---|---|---|---|
| `kaggle_lgbm_*.pkl` | ~120 | LightGBM | Per-country solar/wind forecasting |
| `kaggle_root_cause_xgb_solar.pkl` | 1 | XGBoost | Kaggle solar root cause |
| `kaggle_root_cause_xgb_wind.pkl` | 1 | XGBoost | Kaggle wind root cause |

### Kaggle Anomaly Models — `ml/models/renewable/artifacts/kaggle_anomaly/`

| Pattern | Count | Model | Task |
|---|---|---|---|
| `kaggle_isolation_forest_*.pkl` | ~120 | Isolation Forest | Per-country anomaly detection |

### Dataset — `ml/datasets/kaggle_power_system/`

| File | Description |
|---|---|
| `time_series_60min_singleindex.csv` | OPSD European power system data (~130 MB) |
| `at.csv`, `be.csv`, `de.csv`, ... | Country-specific CSVs |

> **Note:** If `time_series_60min_singleindex.csv` is missing, download the [Open Power System Data](https://open-power-system-data.org/) time series dataset and place it in `ml/datasets/kaggle_power_system/`.

---

## 5. Ollama / Qwen Setup

### Install Ollama

Download and install Ollama from [https://ollama.com](https://ollama.com).

### Pull the Required Model

```powershell
ollama pull qwen2.5:1.5b
```

### Start Ollama

```powershell
ollama serve
```

Ollama runs on `http://127.0.0.1:11434` by default.

### Verify Model is Available

```powershell
ollama list
```

Expected output should include:

```
qwen2.5:1.5b    ...    986 MB
```

### Test Ollama Manually

```powershell
curl http://127.0.0.1:11434/api/tags
```

Or in PowerShell:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:11434/api/tags | ConvertTo-Json -Depth 5
```

Expected: JSON response listing `qwen2.5:1.5b` in the `models` array.

### Configuration Reference

These values are read from `.env` or default in `agent/provider/ollama.ts`:

| Setting | Value |
|---|---|
| Base URL | `http://127.0.0.1:11434` |
| Model | `qwen2.5:1.5b` |
| Timeout | `90000 ms` (90 seconds) |
| Temperature | `0.1` |

---

## 6. Starting the Backend Services

Each service runs in a **separate terminal**. Activate the virtual environment in each terminal first.

### Terminal 1 — Data / Substation Telemetry (port 8001)

```powershell
.\venv\Scripts\activate
$env:PYTHONPATH="."
.\venv\Scripts\python.exe -m uvicorn services.data.api:app --host 127.0.0.1 --port 8001
```

### Terminal 2 — Demand Forecasting (port 8002)

```powershell
.\venv\Scripts\activate
$env:PYTHONPATH="."
.\venv\Scripts\python.exe -m uvicorn services.forecasting.api:app --host 127.0.0.1 --port 8002
```

### Terminal 3 — Renewable Intelligence (port 8003)

```powershell
.\venv\Scripts\activate
$env:PYTHONPATH="."
.\venv\Scripts\python.exe -m uvicorn services.renewable.kaggle_api:app --host 127.0.0.1 --port 8003
```

### Terminal 4 — Grid Optimization (port 8004)

```powershell
.\venv\Scripts\activate
$env:PYTHONPATH="."
.\venv\Scripts\python.exe -m uvicorn services.optimization.api:app --host 127.0.0.1 --port 8004
```

### Terminal 5 — API Gateway (port 8000)

```powershell
npm run start:api
```

This runs: `node --experimental-strip-types apps/api/src/index.ts`

The API Gateway automatically reads `.env` and proxies requests to the Python services at `localhost:8001`–`8004`.

---

## 7. Starting the Frontend

### Terminal 6 — React/Vite Dev Server (port 5173)

```powershell
npm run start:web
```

This runs `vite` inside `apps/web/`. The Vite dev server proxies `/api/*` and `/health` requests to `http://127.0.0.1:8000` (the API Gateway).

### Access the Dashboard

Open: **http://localhost:5173**

---

## 8. Recommended Startup Order

Start services in this order (dependencies flow downward):

| Step | Service | Port | Why |
|---|---|---|---|
| 1 | **Ollama** | 11434 | LLM inference backend — must be ready before copilot queries |
| 2 | **Data service** | 8001 | Grid telemetry — no upstream dependencies |
| 3 | **Forecasting service** | 8002 | Demand models — no upstream dependencies |
| 4 | **Renewable service** | 8003 | Kaggle models + anomaly detection — no upstream dependencies |
| 5 | **Optimization service** | 8004 | OR-Tools solver — no upstream dependencies |
| 6 | **API Gateway** | 8000 | Routes to all Python services + Ollama |
| 7 | **Frontend** | 5173 | Proxies to API Gateway |

---

## 9. Verify Everything Is Running

### Quick Health Checks (PowerShell)

```powershell
# Data service
Invoke-RestMethod http://127.0.0.1:8001/health
# Expected: { "status": "ok", "service": "data_telemetry" }

# Forecasting service
Invoke-RestMethod http://127.0.0.1:8002/health
# Expected: { "status": "ok", "service": "demand_forecasting" }

# Renewable service
Invoke-RestMethod http://127.0.0.1:8003/health
# Expected: { "status": "ok", "source": "kaggle_power_system" }

# Optimization service
Invoke-RestMethod http://127.0.0.1:8004/health
# Expected: { "status": "ok", "service": "grid_optimization" }

# API Gateway
Invoke-RestMethod http://127.0.0.1:8000/health
# Expected: { "success": true, "data": { "status": "ok", ... } }

# Ollama
Invoke-RestMethod http://127.0.0.1:11434/api/tags
# Expected: JSON with "models" array containing "qwen2.5:1.5b"
```

### Gateway Endpoint Checks

```powershell
# Grid state
Invoke-RestMethod http://127.0.0.1:8000/api/grid

# Demand forecast
Invoke-RestMethod http://127.0.0.1:8000/api/forecast

# Renewable status
Invoke-RestMethod http://127.0.0.1:8000/api/renewable

# Renewable anomalies
Invoke-RestMethod http://127.0.0.1:8000/api/renewable/anomalies
```

All should return `{ "success": true, "data": ... }`.

---

## 10. Verify ML Pipeline

### End-to-End Pipeline Test

Test the full analytical pipeline through the API Gateway:

#### 1. Demand Forecast + Spike Detection

```powershell
# 15-minute horizon forecast with spike classification
Invoke-RestMethod "http://127.0.0.1:8000/api/forecast?horizon=15"
```

Expected response contains `forecastMw`, `spikeClass`, `spikeConfidence`.

#### 2. Solar/Wind Prediction + Anomaly Detection + Root Cause

```powershell
# All renewable asset statuses (includes anomaly flags + root cause)
Invoke-RestMethod http://127.0.0.1:8000/api/renewable
```

Each item contains `expectedMw`, `actualMw`, `performanceRatio`, `anomaly`, and optionally `likelyRootCause`.

#### 3. Anomaly-Only Scan

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/renewable/anomalies
```

Returns only items where `anomaly: true`.

#### 4. Grid State → Optimization

```powershell
# GET request triggers automatic grid state aggregation + optimization solve
Invoke-RestMethod http://127.0.0.1:8000/api/optimization
```

Returns `solverStatus`, `batterySchedule`, `totalCostReduction`, etc.

#### 5. Scenario Simulation

```powershell
$body = '{"scenarioId": "NORMAL_DAY"}' 
Invoke-RestMethod -Uri http://127.0.0.1:8004/simulate -Method POST -Body $body -ContentType "application/json"
```

#### 6. Operator Copilot (Qwen)

```powershell
$body = '{"query": "What is the current grid status?"}'
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/agent/copilot -Method POST -Body $body -ContentType "application/json"
```

This exercises: tool orchestration → ML services → OR-Tools → Qwen LLM → operator response.

> **Note:** The copilot request may take 30–90 seconds on the first call due to Qwen model loading.

---

## 11. Frontend Usage

Navigate to **http://localhost:5173** to access the GridPilot dashboard.

| Page | Description |
|---|---|
| **Command Center** | Real-time operational overview — grid state, active anomalies, system health indicators |
| **Demand Forecast** | Interactive demand forecasting with LightGBM — supports 15/30/60 min horizons, spike detection |
| **Renewable Assets** | Solar & wind asset performance monitoring — anomaly flags, root cause analysis |
| **Optimization Center** | OR-Tools MILP battery dispatch visualization — curtailment minimization, load shifting |
| **AI Copilot** | Interactive Qwen-powered operator assistant — ask natural-language questions about grid state |
| **Scenario Simulator** | Run predefined grid scenarios through the real optimizer and compare outcomes |

---

## 12. Common Errors & Fixes

### Port Already in Use (`WinError 10048`)

```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8001)
```

**Fix:** Kill the process occupying the port:

```powershell
# Find process on port 8001
netstat -ano | findstr :8001

# Kill by PID
taskkill /PID <PID> /F
```

### Python Service Not Reachable

```
Downstream grid data telemetry service unavailable
```

**Fix:** Ensure the Python service is running and `$env:PYTHONPATH="."` is set:

```powershell
.\venv\Scripts\activate
$env:PYTHONPATH="."
.\venv\Scripts\python.exe -m uvicorn services.data.api:app --host 127.0.0.1 --port 8001
```

### API Returns 503 / Service Unavailable

**Fix:** Verify the downstream Python service is running on the expected port. Check the terminal running that service for errors.

### Renewable Service Unavailable / Kaggle Dataset Not Found

```
KAGGLE_DATASET_UNAVAILABLE: Kaggle renewable time-series dataset not found.
```

**Fix:** Ensure `ml/datasets/kaggle_power_system/time_series_60min_singleindex.csv` exists. Download it from the [Open Power System Data](https://open-power-system-data.org/) project if missing.

### Forecast Service Unavailable / Model Not Found

**Fix:** Verify `ml/models/demand/demand_lgbm.pkl` and `ml/models/demand/spike_xgb.pkl` exist. These are pre-committed and should be present after cloning.

### Ollama Unavailable

```
Failed to communicate with local Ollama service
```

**Fix:**

```powershell
# Start Ollama
ollama serve

# Verify it's running
curl http://127.0.0.1:11434/api/tags
```

### Qwen Timeout / 504 Gateway Timeout

```
Ollama request timed out after 90000ms
```

**Fix:**
- First run is slow because Ollama loads the model into memory. Wait ~60s.
- Pre-warm the model: `ollama run qwen2.5:1.5b "Hello"`
- Ensure your machine has sufficient RAM (~2 GB for qwen2.5:1.5b).

### Python Import Errors

```
ModuleNotFoundError: No module named 'services'
```

**Fix:** Ensure `PYTHONPATH` is set to the project root:

```powershell
$env:PYTHONPATH="."
```

### Vite Proxy Errors (`ECONNREFUSED 127.0.0.1:8000`)

```
[vite] http proxy error: /api/renewable
Error: connect ECONNREFUSED 127.0.0.1:8000
```

**Fix:** The API Gateway (port 8000) is not running. Start it:

```powershell
npm run start:api
```

### Missing Model Artifact

```
MISSING_FORECAST_MODEL / MISSING_ROOT_CAUSE_MODEL
```

**Fix:** Verify the model `.pkl` files exist in `ml/models/demand/` and `ml/models/renewable/`. Run `git lfs pull` if using Git LFS, or re-clone the repository.

---

## 13. Production / Demo Startup Checklist

```
[ ] Ollama running          → ollama serve
[ ] Qwen model available    → ollama list  (shows qwen2.5:1.5b)
[ ] Python venv activated   → .\venv\Scripts\activate
[ ] Data service running    → port 8001 /health = 200
[ ] Forecast service running → port 8002 /health = 200
[ ] Renewable service running → port 8003 /health = 200
[ ] Optimization service running → port 8004 /health = 200
[ ] API Gateway running     → port 8000 /health = 200
[ ] Frontend running        → port 5173, open http://localhost:5173
[ ] /api/forecast works     → returns forecastMw + spikeClass
[ ] /api/renewable works    → returns asset statuses with anomaly flags
[ ] /api/renewable/anomalies → returns anomalous assets
[ ] /api/optimization works → returns solver result
[ ] Operator Copilot works  → POST /api/agent/copilot returns LLM response
[ ] No runtime fallback/mock data — all responses from real ML models
```

---

## 14. Architecture Overview

```
┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Kaggle CSV  │   │  OpenSTEF    │   │  Trained ML  │   │   Ollama     │
│  Dataset     │   │  Parquet     │   │  .pkl Models │   │  qwen2.5:1.5b│
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                  │                   │                  │
       ▼                  ▼                   ▼                  │
┌──────────────────────────────────────────────────┐             │
│         Python Microservices (FastAPI)            │             │
│  :8001 Data  :8002 Forecast  :8003 Renewable     │             │
│                              :8004 Optimization  │             │
└──────────────────────┬───────────────────────────┘             │
                       │                                         │
                       ▼                                         ▼
              ┌────────────────────────────────────────────────────┐
              │          Node.js API Gateway (:8000)               │
              │  Routes → ServiceClient → Agent/Copilot → Ollama  │
              └────────────────────────┬───────────────────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────┐
                        │  React + Vite (:5173)    │
                        │  Dashboard / Copilot UI  │
                        └──────────────────────────┘
```

| Stage | What It Does |
|---|---|
| **Real Data** | Kaggle OPSD CSV + OpenSTEF parquet — real European power system measurements |
| **ML Models** | LightGBM forecasts demand/solar/wind; XGBoost classifies spikes & root causes; Isolation Forest detects anomalies |
| **GridState** | Aggregates telemetry + forecast + renewable status into a unified snapshot |
| **Optimization** | Google OR-Tools MILP solver calculates optimal battery dispatch, load shifting, curtailment minimization |
| **Qwen Copilot** | Operator Copilot orchestrates tools, collects structured ML/optimizer results, sends to Qwen for natural-language briefing |
| **Dashboard** | React frontend presents real-time data, charts, and copilot interactions |

---

## 15. Team / Demo Notes

### Before the Demo

1. **Pre-warm all services** — start them 2–3 minutes before presenting
2. **Pre-warm Qwen** — run `ollama run qwen2.5:1.5b "Hello"` once to load the model into memory
3. **Verify health** — run all health checks from Section 9
4. **Open the dashboard** — navigate to http://localhost:5173 and confirm data is loading

### Terminal Assignment (Recommended)

| Terminal | Service | Command |
|---|---|---|
| T1 | Ollama | `ollama serve` |
| T2 | Data Service | `uvicorn services.data.api:app --host 127.0.0.1 --port 8001` |
| T3 | Forecasting | `uvicorn services.forecasting.api:app --host 127.0.0.1 --port 8002` |
| T4 | Renewable | `uvicorn services.renewable.kaggle_api:app --host 127.0.0.1 --port 8003` |
| T5 | Optimization | `uvicorn services.optimization.api:app --host 127.0.0.1 --port 8004` |
| T6 | API Gateway | `npm run start:api` |
| T7 | Frontend | `npm run start:web` |

> All Python terminals require `.\venv\Scripts\activate` and `$env:PYTHONPATH="."` first.

### Quick Verification Before Presenting

```powershell
# One-liner health check for all services
@(8001,8002,8003,8004) | ForEach-Object { 
    try { 
        $r = Invoke-RestMethod "http://127.0.0.1:$_/health" -TimeoutSec 5
        Write-Host "Port $_ ✓ $($r.status)" -ForegroundColor Green
    } catch { 
        Write-Host "Port $_ ✗ DOWN" -ForegroundColor Red 
    } 
}

# Gateway
try { 
    $r = Invoke-RestMethod "http://127.0.0.1:8000/health" -TimeoutSec 5
    Write-Host "Gateway ✓" -ForegroundColor Green
} catch { 
    Write-Host "Gateway ✗" -ForegroundColor Red 
}

# Ollama
try { 
    $r = Invoke-RestMethod "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
    Write-Host "Ollama ✓ models: $($r.models.Count)" -ForegroundColor Green
} catch { 
    Write-Host "Ollama ✗" -ForegroundColor Red 
}
```
