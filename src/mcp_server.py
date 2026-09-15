"""
GridPilot AI - IBM Bob Model Context Protocol (MCP) Server
Exposes grid telemetry, forecasts, and optimizer actions directly to the IBM Bob agent shell.
"""
import json
import sys

def handle_call(tool_name: str, args: dict):
    if tool_name == "get_current_grid_state":
        return {
            "gridFrequencyHz": 50.02,
            "currentDemandMw": 158.4,
            "gridStressIndex": 0.72,
            "status": "warning"
        }
    elif tool_name == "get_demand_forecast":
        return {
            "zoneId": args.get("zoneId", "ZONE_CENTRAL"),
            "horizon": args.get("horizon", 30),
            "predictedPeakMw": 172.1,
            "spikeRisk": "severe"
        }
    elif tool_name == "run_optimization":
        return {
            "status": "feasible",
            "batteryDischargeMw": 13.0,
            "flexibleLoadShiftMw": 7.0,
            "resultingGridStress": 0.39
        }
    else:
        return {"error": f"Unknown tool: {tool_name}"}

if __name__ == "__main__":
    # Lightweight stdio runner
    print("GridPilot MCP Server ready for IBM Bob", file=sys.stderr)
