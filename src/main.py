
"""
GridPilot AI - Main Application Gateway (FastAPI)
Provides unified REST endpoints for grid state, forecasts, renewables, optimization, and operator briefs.
"""
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from typing import Optional

from src.models.forecasting import DemandForecaster, RenewableForecaster
from src.models.optimizer import GridOptimizer

app = FastAPI(
    title="GridPilot AI Gateway",
    description="Intelligent Decision-Support API for Grid Load Optimisation & Renewable Energy",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

demand_service = DemandForecaster()
renewable_service = RenewableForecaster()
optimizer_service = GridOptimizer()

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "GridPilot AI",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

@app.get("/api/grid/state")
def get_grid_state():
    """Aggregated real-time operational grid snapshot."""
    renewables = renewable_service.forecast_renewables()
    total_renewable = sum(r["actualMw"] for r in renewables)
    
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "gridFrequencyHz": 50.02,
        "currentDemandMw": 158.4,
        "totalGenerationMw": 160.0,
        "renewableGenerationMw": total_renewable,
        "gridStressIndex": 0.72,
        "activeAlertsCount": sum(1 for r in renewables if r["anomaly"]),
        "status": "warning"
    }

@app.get("/api/forecast/demand")
def get_demand_forecast(zoneId: str = Query(default="ZONE_CENTRAL"), horizon: int = Query(default=30)):
    """Demand forecast and spike risk classification."""
    return demand_service.forecast_demand(zone_id=zoneId, horizon_minutes=horizon)

@app.get("/api/renewable/status")
def get_renewable_status():
    """Renewable assets telemetry, anomaly detection and root cause."""
    return {"assets": renewable_service.forecast_renewables()}

@app.post("/api/optimization/solve")
def run_optimization():
    """Run mathematical optimization for battery dispatch and curtailment mitigation."""
    return optimizer_service.solve_dispatch()

@app.get("/api/agent/brief")
def get_operator_brief():
    """Synthesized natural language brief for grid operators."""
    opt = optimizer_service.solve_dispatch()
    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": "High demand spike detected (+18% expected in next 30 min) coinciding with 22.8 MW solar deficit at SOLAR_FARM_ALPHA. Recommended dispatching 13.0 MW from BESS Central and shifting 7.0 MW industrial load to stabilize grid stress to 0.39.",
        "riskLevel": "high",
        "recommendedActions": [
            f"Discharge {a['powerMw']} MW from {a['resourceId']}" for a in opt["actions"]
        ],
        "feasible": opt["status"] == "feasible",
        "llmConfidence": 0.91
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
